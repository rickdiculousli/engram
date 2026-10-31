"""The weekly refinement (docs/operations.md, "The weekly refinement"): `engram refine run` starts one `claude -p` pass
per repo engram serves, its own repo first and then each configured domain's, under the week's cap. The pass follows
skills/engram-refine/SKILL.md in engram's own repo; each change it lands carries a `Refinement:` trailer, its one line
for the owner, and each idea it can't land is a spec in the repo's .engram/specs/. `surface` shows both at a session
start, and `install` writes the launchd job that runs the week's passes."""
import contextlib
import fcntl
import json
import math
import re
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from engram import claude_env, config, frontmatter, rewire
from engram.paths import PAGE, SPECS, data_path, record_conf
from engram.sources import sessions

DEFAULTS = {"weekly_cap": 100.0, "pass_cap": 40.0, "hours": 4.0, "model": "opus", "permission_mode": "auto"}
SKILL = "skills/engram-refine/SKILL.md"  # in engram's own repo, so an edit there steers the next pass
TRAILER = "Refinement"
REVERTS = "This reverts commit "  # git revert's line
LABEL = "engram.refine"
# Saturday 04:00, with catch-ups on Sunday and Monday for a Mac asleep then; a repo whose pass this week landed, is
# running, or cost something is skipped, and one whose pass failed for nothing is tried again
SCHEDULE = [{"Weekday": 6, "Hour": 4, "Minute": 0}, {"Weekday": 0, "Hour": 9, "Minute": 30},
            {"Weekday": 1, "Hour": 19, "Minute": 30}]
ALLOW = ("The weekly refinement pass: editing files in the repo it was given and in its own worktrees, running that "
         "repo's checks, committing on a refinement branch, fast-forward merging it into the repo's default branch and "
         "pushing to origin, when the rules section of the repo's .engram/README.md allows it.")
REMINDER = ("You can refine this weekly pass too: say what it should stop touching, to be bolder, or to pause, in any "
            "session.")


def settings() -> dict:
    """`[refine]` in the config: the caps, the hours a pass may run, the model and permission mode, and `repo`, engram's
    own."""
    return {**DEFAULTS, **config.raw().get("refine", {})}


def own() -> Path | None:
    return Path(r).expanduser() if (r := settings().get("repo")) else None


def repos() -> dict[str, Path]:
    """The repos the pass serves, by name: engram's own, then each configured domain's."""
    return ({"engram": own()} if own() else {}) | {n: d.repo for n, d in config.load().items() if d.repo}


def paused(repo: Path) -> bool:
    return bool(record_conf(repo).get("refine", {}).get("paused"))


def week(now: datetime | None = None) -> str:
    """The Saturday a week starts on, so its Sunday and Monday catch-ups fall in it."""
    d = (now or datetime.now()).date()
    return (d - timedelta(days=(d.weekday() - 5) % 7)).isoformat()


def _dir() -> Path:
    d = data_path("refine")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ledger() -> list[dict]:
    """The spend ledger; a row that isn't one (a hand edit) raises ValueError, so nothing is spent on a ledger misread."""
    f = _dir() / "ledger.jsonl"
    rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    for r in rows:
        if not (isinstance(r, dict) and {"week", "repo", "dry_run", "ok", "started"} <= r.keys()
                and isinstance(r.get("cost_usd"), (int, float)) and not isinstance(r.get("cost_usd"), bool)
                and math.isfinite(r["cost_usd"])):
            raise ValueError(f"a ledger row isn't one: {json.dumps(r)[:120]}")
    return rows


def _write(rows: list[dict]) -> None:
    """The ledger, written whole."""
    tmp = _dir() / "ledger.jsonl.tmp"
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    tmp.replace(_dir() / "ledger.jsonl")


def _held() -> bool:
    """Whether a pass holds the lock now."""
    with open(_dir() / "lock", "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def status() -> list[str]:
    """This week's pass on each repo, for `engram health`: where a failure is told, never at session start."""
    try:
        rows = [r for r in ledger() if r["week"] == week() and not r["dry_run"]]
    except ValueError as e:
        return [f"weekly pass: the ledger doesn't read ({e}); no pass runs until it's fixed"]
    out = []
    for name in repos():
        last = [r for r in rows if r["repo"] == name][-1:]
        if not last:
            out.append(f"weekly pass on {name}: not run this week")
        elif last[0].get("running"):
            out.append(f"weekly pass on {name}: " + (f"running since {last[0]['started']}" if _held() else
                       f"stopped mid-run, started {last[0]['started']} (its cap is counted spent)"))
        else:
            out.append(f"weekly pass on {name}: " + ("ok" if last[0]["ok"] else f"FAILED ({last[0].get('error', '')})")
                       + f", ${last[0]['cost_usd']:.2f}")
    return out


def spent(rows: list[dict], wk: str) -> float:
    return round(sum(r["cost_usd"] for r in rows if r["week"] == wk), 4)


def _work() -> Path:
    """Where a pass runs and keeps its worktrees: outside every repo, so no repo's hooks or filer see it."""
    return data_path("scratch") / "refine"


def command(name: str, repo: Path, cap: float, dry_run: Path | None = None) -> list[str]:
    """The pass for one repo: the skill handed to `claude -p` by its path, with the repo, its mode and the folder its
    worktrees go in."""
    s, work = settings(), _work()
    mode = f"dry-run {dry_run / f'{name}.md'}" if dry_run else "land"
    cmd = ["claude", "-p", f"Follow {own() / SKILL}: repo={repo} mode={mode} worktrees={work}",
           "--output-format", "json", "--max-budget-usd", f"{cap:.2f}", "--permission-mode", s["permission_mode"],
           "--model", s["model"], "--settings", json.dumps({"autoMode": {"allow": ["$defaults", ALLOW]}}),
           "--add-dir", str((own() / SKILL).parent), "--add-dir", str(repo), "--add-dir", str(work)]
    return cmd + (["--add-dir", str(dry_run)] if dry_run else [])


@contextlib.contextmanager
def _lock(wait: bool = False):
    with open(_dir() / "lock", "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            sys.exit("engram refine: another run holds the lock")
        yield


def start(name: str) -> str:
    """A pass on one repo, started detached: a session's background command is stopped after its time limit, and a pass
    may run for hours. Its result shows in `engram health`."""
    if name not in repos():
        sys.exit(f"engram refine: {name} is none of {', '.join(repos())}")
    if paused(repos()[name]):
        sys.exit(f"engram refine: {name} is paused in its rules; nothing started")
    fh = open(_dir() / "lock", "w")  # taken here and inherited by the pass, which holds it till it ends
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("engram refine: a pass is running now; nothing started, ask again when it's done")
    if settings()["weekly_cap"] - spent(ledger(), week()) < 1:
        sys.exit(f"engram refine: this week's ${settings()['weekly_cap']:.0f} is spent; nothing started")
    log = _dir() / "launchd.log"
    subprocess.Popen(["/usr/bin/caffeinate", "-i", sys.executable, "-m", "engram.cli", "refine", "run", "--repo", name, "--attached"],
                     pass_fds=(fh.fileno(),),
                     stdout=log.open("a"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    return f"engram refine: the pass on {name} started on its own; its result shows in `engram health`"


def run(only: str | None = None, dry_run: Path | None = None, show: bool = False, runner=subprocess.run,
        attached: bool = False) -> list[str]:
    """One pass per repo under the weekly cap, each pass's line for the log. `show` prints each pass's command instead
    of running it; `dry_run` has each pass write its plan to that folder and land nothing."""
    if not own():
        sys.exit("engram refine: set [refine] repo, engram's own repo, in the config: the pass's instructions live there")
    s, wk, targets = settings(), week(), repos()
    if only and only not in targets:
        sys.exit(f"engram refine: {only} is none of {', '.join(targets)}")
    out = []
    # the schedule waits out a pass on request; a pass `start` launched holds the lock it inherited
    with contextlib.nullcontext() if attached else _lock(wait=not (only or show or dry_run)):
        rows = ledger()
        for name, repo in targets.items():
            left = s["weekly_cap"] - spent(rows, wk)
            if only and name != only:
                continue
            if paused(repo):
                out.append(f"{name}: paused in its rules; skipped")
                continue
            done = [r for r in rows if r["week"] == wk and r["repo"] == name and not r["dry_run"]]
            if not (only or dry_run) and done and (done[-1]["ok"] or done[-1].get("running") or done[-1]["cost_usd"] >= 1):
                out.append(f"{name}: already ran this week" + ("" if done[-1]["ok"] else ", stopped mid-run"
                           if done[-1].get("running") else ", and failed"))  # --repo runs it again
                continue
            if left < 1:
                out.append(f"{name}: the weekly cap of ${s['weekly_cap']:.0f} is reached; stopping")
                break
            cap = min(left, s["pass_cap"])
            cmd = command(name, repo, cap, dry_run)
            if show:
                out.append(f"{name}: {shlex.join(cmd)}")
                continue
            _work().mkdir(parents=True, exist_ok=True)
            if dry_run:
                dry_run.mkdir(parents=True, exist_ok=True)
            started = datetime.now().isoformat(timespec="seconds")
            row = {"week": wk, "repo": name, "started": started, "dry_run": bool(dry_run), "cost_usd": cap, "ok": False,
                   "running": True}  # a pass stopped mid-run keeps its cap spent, so nothing reruns it for free
            rows.append(row)
            _write(rows)
            try:
                proc = runner(cmd, cwd=_work(), capture_output=True, text=True, env=claude_env.clean(),
                              timeout=s["hours"] * 3600)
            except subprocess.TimeoutExpired:  # an unknown cost is the whole cap
                cost, error, said = cap, f"timed out after {s['hours']:g} hours", ""
            except OSError as e:  # never started: nothing spent
                cost, error, said = 0.0, f"didn't start: {type(e).__name__}: {e}", ""
            else:
                try:
                    res = json.loads(proc.stdout)
                    cost, said = float(res.get("total_cost_usd", cap)), res.get("result", "")
                    why = str(res.get("subtype") or "").replace("_", " ")
                    error = (said or why if res.get("is_error") else "") or \
                        (f"exit {proc.returncode}" + (f", {why}" if why and why != "success" else "") if proc.returncode else "")
                except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
                    cost, said = cap, (proc.stdout + proc.stderr)[-2000:]
                    error = said.strip().splitlines()[-1] if said.strip() else f"exit {proc.returncode}, no output"
            rows[-1] = {"week": wk, "repo": name, "started": started, "dry_run": bool(dry_run), "cost_usd": round(cost, 4),
                        "ok": not error} | ({"error": " ".join(error.split())[:200]} if error else {})
            row = rows[-1]
            _write(rows)
            (_dir() / "runs" / wk).mkdir(parents=True, exist_ok=True)
            (_dir() / "runs" / wk / f"{name}{'-dry' if dry_run else ''}.md").write_text(said or "")
            out.append(f"{name}: {'ok' if row['ok'] else 'failed'}, ${cost:.2f}; week ${spent(rows, wk):.2f} of "
                       f"${s['weekly_cap']:.0f}")
    return out


def conversations(repo: Path, days: float = 7, session: str | None = None, cap: int = 60000) -> str:
    """The owner's messages in the repo's sessions of the last `days`, each with the reply they read: the pass's only
    evidence of use. Subagents and sessions an agent started (`sessions.by_agent`) are left out; past `cap` characters
    a session is only counted, and `session` reads one whole."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    found = {}
    for root in rewire.roots():
        for p in root.rglob("*.jsonl"):
            if "subagents" in p.parts or (session and not p.stem.startswith(session)) or p.stem in found \
                    or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < since:
                continue
            s = sessions.parse(p, root)
            said = [e for e in s.exchanges if e.ts and not e.meta and not e.summary and not sessions.brief(e.asked)]
            if sessions.by_agent(s) or not said or not sessions.started_in(s, repo):
                continue
            if said := [e for e in said if rewire._when(e.ts) >= since]:
                found[p.stem] = said
    cut = lambda t, n: t if len(t := " ".join(t.split())) <= n else t[:n] + f" […{len(t) - n} more chars]"
    out, size, left = [f"# {len(found)} sessions, {sum(map(len, found.values()))} messages since {since:%Y-%m-%d}"], 0, []
    for stem, said in sorted(found.items(), key=lambda kv: kv[1][0].ts):
        head = f"{said[0].ts[:10]} session {stem[:8]} ({len(said)} messages)"
        block = [f"\n## {head}"]
        for e in said:
            block.append(f"- **user** {rewire._when(e.ts):%m-%d %H:%M}: {cut(e.asked, 1500)}")
            if reply := [r for i, r in enumerate(e.replies) if i not in e.narration][-1:]:
                block.append(f"  - reply: {cut(reply[0], 600)}")
        text = "\n".join(block)
        if not session and size + len(text) > cap:
            left.append(f"- {head}")
            continue
        out.append(text)
        size += len(text)
    return "\n".join(out + (["\n## Left out at the size cap; read each with --session <id>", *left] if left else []))


def _landed(repo: Path) -> list[tuple[str, str, str]]:
    """(commit, day, line) for each commit on the repo's branch whose message has a `Refinement:` line and that no later
    commit reverts, oldest first. The line is read wherever it sits in the message: a blank line before Claude's
    co-author line takes it out of git's trailer block."""
    log = subprocess.run(["git", "-C", str(repo), "log", "--reverse", f"--grep=^{TRAILER}: ", f"--grep={REVERTS}",
                          "--format=%H %as%n%B%x00"], capture_output=True, text=True).stdout
    out, reverters = [], {}
    for c in log.split("\0"):
        head, _, body = c.strip().partition("\n")
        for target in re.findall(rf"{REVERTS}([0-9a-f]{{40}})", body):
            reverters.setdefault(target, []).append(head.split(" ", 1)[0])
        line = next((l.split(":", 1)[1].strip() for l in body.splitlines() if l.startswith(f"{TRAILER}: ")), "")
        if head and line:
            out.append((*head.split(" ", 1), line))

    standing: dict[str, bool] = {}  # a commit stands unless a standing commit reverts it

    def stands(sha: str) -> bool:
        stack = [sha]
        while stack:  # a commit is settled once every commit reverting it is
            s = stack[-1]
            if todo := [r for r in reverters.get(s, []) if r not in standing]:
                stack += todo
            else:
                standing[s] = not any(standing[r] for r in reverters.get(s, []))
                stack.pop()
        return standing[sha]
    return [c for c in out if stands(c[0])]


def _specs(repo: Path) -> tuple[list[str], list[str]]:
    """(each spec waiting on the owner, or approved but blocked with its why; each spec whose front matter won't parse)."""
    out, broken = [], []
    for spec in sorted((repo / SPECS).glob("*.md")):
        try:
            fields, body = frontmatter.split(spec.read_text())
        except (ValueError, yaml.YAMLError) as e:
            broken.append(f"- {spec}: {str(e).splitlines()[0]}")
            continue
        fields = fields or {}
        title = next((line[2:] for line in body.splitlines() if line.startswith("# ")), spec.stem)
        if fields.get("status", "open") == "open":
            out.append(f"- {title} ({spec})")
        elif fields.get("status") == "approved" and "blocked" in fields:
            out.append(f"- approved but not built: {title}, because {fields['blocked'] or 'the pass gave no reason'} ({spec})")
    return out, broken


def _portrait(repo: Path) -> str:
    """The rewiring's portrait of the owner's jobs, while they're still proposed: shown at every session start in the
    repo until the owner confirms or corrects it."""
    page = repo / PAGE
    fields = frontmatter.split(page.read_text())[0] if page.exists() else None
    return str(fields.get("portrait", "")).strip() if fields and fields.get("jobs") == "proposed" else ""


def surface(here: Path) -> str:
    """What a session start in a repo shows from the weekly pass: the portrait of jobs still proposed there, each landed
    change not yet shown anywhere, and each open spec, from the repo and from engram's own; for the agent alone, front
    matter that won't parse. A change shows once. A failed pass is told in `engram health`, never here."""
    here = here.resolve()
    seen_f = _dir() / "seen.json"
    try:
        seen = set(json.loads(seen_f.read_text())) if seen_f.exists() else set()
    except ValueError:  # half written: showing a change again beats hiding every one
        seen = set()
    changed, needs, broken = [], [], []
    for src in dict.fromkeys([here] + ([own().resolve()] if own() else [])):
        tag = "" if src == here else f" ({src.name})"
        for sha, day, line in _landed(src):
            if sha not in seen:
                changed.append(f"- {day}: {line}{tag}")
                seen.add(sha)
        waiting, unreadable = _specs(src)
        needs, broken = needs + waiting, broken + unreadable
    try:
        portrait = _portrait(here)
    except (ValueError, yaml.YAMLError) as e:
        portrait, broken = "", broken + [f"- {here / PAGE}: {str(e).splitlines()[0]}"]
    if not changed and not needs and not portrait and not broken:
        return ""
    agent = ["For you, not the owner (fix the file; never raise it with them):", *broken] if broken else []
    if not changed and not needs and not portrait:
        return "\n".join(agent)
    out = ["Weekly refinement (open your first reply with these, one line each, in plain words):"]
    out += ["Their jobs here, still proposed (say it as written; \"spot on\" sets `jobs: confirmed` and drops `portrait:` "
            "in .engram/README.md's front matter; a correction rewrites the jobs, then does the same, since it is the answer):",
            portrait] if portrait else []
    out += ["Changed since the last session:", *changed] if changed else []
    out += ["Needs you (the owner answers yes, no or tell me more; set the spec's status to approved or rejected):",
            *needs] if needs else []
    if changed:  # marked shown only once the lines are built, and written whole
        tmp = seen_f.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(seen)))
        tmp.replace(seen_f)
    return "\n".join(out + [REMINDER] + ([""] + agent if agent else []))


def install(agents: Path = Path.home() / "Library/LaunchAgents", load: bool = True) -> Path:
    """The launchd job that runs the week's passes, kept awake until they end; a time missed asleep fires on wake.
    Running it again rewrites and reloads the same job."""
    from engram import setup
    plist = agents / f"{LABEL}.plist"
    setup.launch_job(plist, LABEL, ["/usr/bin/caffeinate", "-i", *setup.engram_cmd(), "refine", "run"],
                     _dir() / "launchd.log", load, StartCalendarInterval=SCHEDULE)
    return plist
