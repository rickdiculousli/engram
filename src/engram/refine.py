"""The weekly refinement (docs/operations.md, "The weekly refinement"): `engram refine run` starts one `claude -p` pass
per repo engram owns, its own repo first and then each configured domain's with a page, under the week's cap. The pass
follows skills/engram-refine/SKILL.md in engram's own repo; each change it lands carries a `Refinement:` trailer, its
one line for the owner, and each idea it can't land is a spec in the repo's .engram/specs/. After the passes, `digest` writes
the week's one page of both across the repos, and `install` writes the timed job that runs the week's passes."""
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from engram import claude_env, config, frontmatter, pack, review, rewire
from engram.paths import PAGE, SPECS, data_dir, data_path, record_conf
from engram.sources import sessions

DEFAULTS = {"weekly_cap": 100.0, "pass_cap": 40.0, "hours": 4.0, "model": "opus", "permission_mode": "auto"}
SKILL = "skills/engram-refine/SKILL.md"  # in engram's own repo, so an edit there steers the next pass
TRAILER = "Refinement"
UNSEEN = "none:"  # a trailer opening with it: a change the owner wouldn't see, kept off their page
REVERTS = "This reverts commit "  # git revert's line
SWEEP = "sweep"  # the job of the evidence sweep's ledger rows: they count toward the week, never as a pass
PAGE_JOB = "page"  # the job of the week's page's ledger row: it counts toward the week, never as a pass
BUILD = "build"  # the job of a build on request's ledger row: it counts toward the week, never as the week's pass
LABEL = "engram.refine"
# Saturday 04:00, with catch-ups on Sunday and Monday for a box asleep then; a repo whose pass this week landed, is
# running, or cost something is skipped, and one whose pass failed for nothing is tried again
SCHEDULE = [{"Weekday": 6, "Hour": 4, "Minute": 0}, {"Weekday": 0, "Hour": 9, "Minute": 30},
            {"Weekday": 1, "Hour": 19, "Minute": 30}]
ALLOW = ("The weekly refinement pass: editing files in the repo it was given and in its own worktrees, running that "
         "repo's checks, committing on a refinement branch, running `engram refine review` and `engram refine land` on it, "
         "which merge and push it when a review passed it, and pushing its specs, when the rules section of the repo's "
         ".engram/README.md allows it.")
# what the pass may not change in engram's own repo: denied to its edits here, refused at commit by engram's pre-commit
OFF_LIMITS = ("bench/gate.py", "skills/engram-refine/**", ".githooks/**", "src/engram/landing.py")
# how a pass could stop short or land past the review: waiting needs something to wake it, and a pass ends with its turn
NO_WAITING = ("Monitor", "ScheduleWakeup")
NO_LANDING = ("Bash(git merge *)", "Bash(git -C * merge *)")
REVIEW_TIMEOUT = 1800  # seconds one review may run; a pass's Bash calls wait this long and a little more
DIGEST_CAP = 3.0  # what one digest may spend
DIGEST = """Write one self-contained HTML page (inline CSS, no scripts, nothing loaded from elsewhere) that tells {owner} \
what this week's refinement of their repos brings them to decide. Reply with the page alone, from <!doctype html> \
to </html>.

It's for reading, not acting. For each item below that needs them: a plain title; what it would change for them; its \
cost; the recommendation; the evidence; then the answers they can give: yes, no, defer, or tell me more. A spec \
approved but not built says why it waits, or if it gives no reason, that the week's pass didn't finish it; jobs still proposed are shown as written, asking if that's it. A pass \
that didn't finish is one plain line, with no answers: what it left undone, unless a spec here already says so. Changes \
already made are one plain line each, with no answers. Each item says which repo it's in. Write in the specs' own plain voice, to {owner} as "you", with \
no file paths, commands, field names, statuses or other machinery; leave out what an item doesn't say, and add nothing.

End with this line, alone: "Bring each up in a regular session in its repo when you want to deal with it."
"""


def settings() -> dict:
    """`[refine]` in the config: the caps, the hours a pass may run, the model and permission mode, and `repo`, engram's
    own."""
    return {**DEFAULTS, **config.raw().get("refine", {})}


def own() -> Path | None:
    return Path(r).expanduser() if (r := settings().get("repo")) else None


def repos() -> dict[str, Path]:
    """The repos the pass serves, by name: engram's own, then each configured domain's that has the one page the pass
    answers to; a folder configured only for search has none, and gets no specs."""
    return ({"engram": own()} if own() else {}) | {n: d.repo for n, d in config.load().items()
                                                   if d.repo and (d.repo / PAGE).exists()}


def paused(repo: Path) -> bool:
    return bool(record_conf(repo).get("refine", {}).get("paused"))


def week(now: datetime | None = None) -> str:
    """The Saturday a week starts on, so its Sunday and Monday catch-ups fall in it."""
    d = (now or datetime.now()).date()
    return (d - timedelta(days=(d.weekday() - 5) % 7)).isoformat()


def _dir() -> Path:
    """The ledger's folder, the real one under a pass too (`fenced` names it), so its reviews are counted and kept."""
    d = Path(os.environ.get("ENGRAM_REFINE") or data_path("refine"))
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
    """This week's pass on each repo, for `engram health`: where a failure is told, never at session start. Then a page
    for the owner that couldn't be opened here, and where it is."""
    held = [f"the weekly page couldn't be opened on this box; it's at {p}"] if (p := _unshown().get("page")) else []
    try:
        rows = [r for r in ledger() if r["week"] == week() and not r["dry_run"]]
    except ValueError as e:
        return [f"weekly pass: the ledger doesn't read ({e}); no pass runs until it's fixed", *held]
    out = [f"build on request on {r['repo']}: " + (("running" if _held() else "stopped mid-run") if r.get("running")
           else f"FAILED ({r.get('error', '')})" if not r["ok"] else "ok") + f", ${r['cost_usd']:.2f}" for r in rows if r.get("job") == BUILD]
    for r in [r for r in rows if r.get("job") == SWEEP]:
        out.append(f"evidence sweep on {r['repo']}: " + ("running" if r.get("running") else f"FAILED ({r.get('error', '')})"
                   if not r["ok"] else "stopped at its $10 cap" if r.get("stopped") else "ok") + f", ${r['cost_usd']:.2f}"
                   + ("; the next run picks up" if r["ok"] and r.get("stopped") else ""))
    rows = [r for r in rows if r.get("job") not in (SWEEP, BUILD)]
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
    return out + held


def reviews() -> list[dict]:
    """Each review `landing.review` ran and each landing `landing.land` made."""
    f = _dir() / "reviews.jsonl"
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []


def spent(rows: list[dict], wk: str) -> float:
    return round(sum(r["cost_usd"] for r in [*rows, *reviews()] if r["week"] == wk), 4)


def _work() -> Path:
    """Where a pass runs and keeps its worktrees: outside every repo, so no repo's hooks or filer see it."""
    return data_path("scratch") / "refine"


def copy_data(to: Path):
    """The data folder's SQLite files (the value review's too), each through SQLite's backup (whole, while a writer
    runs), and what the index is re-read from beside them: the session and record summaries, and the moved refs."""
    to.mkdir(parents=True, exist_ok=True)
    for f in [*data_dir().glob("*.sqlite"), *data_dir().glob("review/*.sqlite")]:
        (to / f.relative_to(data_dir())).parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(f"file:{f}?mode=ro", uri=True)) as src, \
                contextlib.closing(sqlite3.connect(to / f.relative_to(data_dir()))) as dst:
            src.backup(dst)
    for d in ("summaries", "record-summaries", "moved"):
        if data_path(d).is_dir():
            shutil.copytree(data_path(d), to / d, dirs_exist_ok=True)


def fenced(name: str, repo: Path, wk: str) -> dict:
    """The env a pass runs in: engram on a copy of the data folder, its repo rows dropped so nothing there serves a
    real repo, cleared at the next pass's start; the real gate folder for the baseline; a config laid over the box's
    that keeps a repo only for the domain under pass (none for engram's own), as the gate's freeze writes it; the
    mark engram's pre-commit refuses OFF_LIMITS under, naming the real ledger's folder; and no background work: a pass
    ends with its turn, so what it left running dies unfinished, and a long check or review holds its turn open."""
    shutil.rmtree(data_path("scratch") / "refine-data", ignore_errors=True)
    at = data_path("scratch") / "refine-data" / f"{wk}-{name}"
    copy_data(at / "data")
    if (at / "data/capture.sqlite").exists():
        with contextlib.closing(sqlite3.connect(at / "data/capture.sqlite")) as c:
            c.execute("DELETE FROM repo")
            c.commit()
    (at / "config.toml").write_text("".join(f"[domains.{n}]\nrepo = {json.dumps(str(repo) if n == name else '')}\n"
                                            for n in config.load()))
    return {"ENGRAM_DATA": str(at / "data"), "ENGRAM_CONFIG": str(at / "config.toml"),
            "ENGRAM_GATE": str(data_path("gate")), "ENGRAM_REFINE": str(_dir()), "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "BASH_DEFAULT_TIMEOUT_MS": str((REVIEW_TIMEOUT + 300) * 1000), "BASH_MAX_TIMEOUT_MS": str((REVIEW_TIMEOUT + 300) * 1000)}


def command(name: str, repo: Path, cap: float, dry_run: Path | None = None, approved: bool = False) -> list[str]:
    """The pass for one repo: the skill handed to `claude -p` by its path, with the repo, its mode and the folder its
    worktrees go in."""
    s, work = settings(), _work()
    mode = f"dry-run {dry_run / f'{name}.md'}" if dry_run else "approved" if approved else "land"
    cmd = ["claude", "-p", f"Follow {own() / SKILL}: repo={repo} mode={mode} worktrees={work}",
           "--output-format", "json", "--max-budget-usd", f"{cap:.2f}", "--permission-mode", s["permission_mode"],
           "--model", s["model"], "--settings", json.dumps({"autoMode": {"allow": ["$defaults", ALLOW]}, "permissions": {
               "deny": [f"{t}(**/{p})" for p in OFF_LIMITS for t in ("Edit", "Write")] + [*NO_WAITING, *NO_LANDING]}}),
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


def start(name: str, approved: bool = False) -> str:
    """A pass on one repo, started detached: a session's background command is stopped after its time limit, and a pass
    may run for hours. Its result shows in `engram health`. `approved` has it build only the specs the owner said yes to."""
    if name not in repos():
        sys.exit(f"engram refine: {name} is none of {', '.join(repos())}")
    if approved and not _approved(repos()[name]):
        sys.exit(f"engram refine: {name} has no approved spec a pass can build; nothing started. One marked `blocked:` says why")
    if approved and subprocess.run(["git", "-C", str(repos()[name]), "status", "--porcelain", "--", SPECS], capture_output=True,
                                   text=True).stdout.strip():
        sys.exit(f"engram refine: {name}'s specs have uncommitted changes, which its landing would refuse; commit them first")
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
    from engram import jobs
    subprocess.Popen(jobs.awake([sys.executable, "-m", "engram.cli", "refine", "run", "--repo", name, "--attached", *(["--approved"] if approved else [])]),
                     pass_fds=(fh.fileno(),),
                     stdout=log.open("a"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    return f"engram refine: the pass on {name} started on its own; its result shows in `engram health`"


def run(only: str | None = None, dry_run: Path | None = None, show: bool = False, runner=subprocess.run,
        attached: bool = False, approved: bool = False) -> list[str]:
    """One pass per repo under the weekly cap, each pass's line for the log. `show` prints each pass's command instead
    of running it; `dry_run` has each pass write its plan to that folder and land nothing; `approved` has it build only
    the approved specs, with no sweep, health check or page, and leaves the week's pass to run as usual."""
    if not own():
        sys.exit("engram refine: set [refine] repo, engram's own repo, in the config: the pass's instructions live there")
    s, wk, targets = settings(), week(), repos()
    if only and only not in targets:
        sys.exit(f"engram refine: {only} is none of {', '.join(targets)}")
    out, ran = [], False
    # the schedule waits out a pass on request; a pass `start` launched holds the lock it inherited
    with contextlib.nullcontext() if attached else _lock(wait=not (only or show or dry_run)):
        rows = ledger()
        out += [] if approved else _sweeps(rows, wk, s, only, bool(dry_run or show))
        for name, repo in targets.items():
            left = s["weekly_cap"] - spent(rows, wk)
            if only and name != only:
                continue
            if paused(repo):
                out.append(f"{name}: paused in its rules; skipped")
                continue
            done = [r for r in rows if r["week"] == wk and r["repo"] == name and not r["dry_run"] and r.get("job") not in (SWEEP, BUILD)]
            if not (only or dry_run) and done and (done[-1]["ok"] or done[-1].get("running") or done[-1]["cost_usd"] >= 1):
                out.append(f"{name}: already ran this week" + ("" if done[-1]["ok"] else ", stopped mid-run"
                           if done[-1].get("running") else ", and failed"))  # --repo runs it again
                continue
            if left < 1:
                out.append(f"{name}: the weekly cap of ${s['weekly_cap']:.0f} is reached; stopping")
                break
            cap = min(left, s["pass_cap"])
            cmd = command(name, repo, cap, dry_run, approved)
            if show:
                out.append(f"{name}: {shlex.join(cmd)}")
                continue
            _work().mkdir(parents=True, exist_ok=True)
            if dry_run:
                dry_run.mkdir(parents=True, exist_ok=True)
            started = datetime.now().isoformat(timespec="seconds")
            settle, head, before = _approved(repo), _head(repo), _branches(repo) if approved else []
            job = {"job": BUILD} if approved else {}
            row = {"week": wk, "repo": name, **job, "started": started, "dry_run": bool(dry_run), "cost_usd": cap, "ok": False,
                   "running": True}  # a pass stopped mid-run keeps its cap spent, so nothing reruns it for free
            rows.append(row)
            _write(rows)
            ran = not (dry_run or approved)
            try:
                proc = runner(cmd, cwd=_work(), capture_output=True, text=True,
                              env=claude_env.clean(**fenced(name, repo, wk)), timeout=s["hours"] * 3600)
            except subprocess.TimeoutExpired:  # an unknown cost is the whole cap
                cost, error, said = cap, f"timed out after {s['hours']:g} hours", ""
            except (OSError, sqlite3.Error) as e:  # never started (its data copy failed, say): nothing spent
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
            if not dry_run and (left_undone := _unfinished(repo, settle, head, before)):
                error = "; ".join(filter(None, [error, *left_undone]))
            rows[-1] = {"week": wk, "repo": name, **job, "started": started, "dry_run": bool(dry_run), "cost_usd": round(cost, 4),
                        "ok": not error} | ({"error": " ".join(error.split())[:400]} if error else {})
            row = rows[-1]
            _write(rows)
            (_dir() / "runs" / wk).mkdir(parents=True, exist_ok=True)
            (_dir() / "runs" / wk / f"{name}{'-dry' if dry_run else '-build' if approved else ''}.md").write_text(said or "")
            if not dry_run and not approved and name in config.load() and pack.load(name).prompts.get("compile"):
                from engram import compile as compile_mod
                try:  # the compiled wiki's health check runs with the pass, its cost the pass's
                    row["cost_usd"] = round(row["cost_usd"] + compile_mod.health(name)["usd"], 4)
                except Exception as e:
                    out.append(f"{name}: the wiki's health check failed: {type(e).__name__}: {e}")
            _write(rows)
            out.append(f"{name}: {'ok' if row['ok'] else 'failed'}, ${cost:.2f}; week ${spent(rows, wk):.2f} of "
                       f"${s['weekly_cap']:.0f}")
        page = _dir() / "digests" / f"{wk}.html"
        if ran and page.exists():  # one page a week: a later pass's items wait for the next
            out.append(f"the week's page is already {page}; what this run brought waits for the next")
        elif ran:
            started = datetime.now().isoformat(timespec="seconds")
            paid, line = digest(targets, min(DIGEST_CAP, s["weekly_cap"] - spent(rows, wk)), runner, rows)
            if paid:
                rows.append({"week": wk, "repo": "", "job": PAGE_JOB, "started": started, "dry_run": False,
                             "cost_usd": round(paid, 4), "ok": page.exists()})
                _write(rows)
            if line:
                out.append(f"the week's page: {line}")
    return out


def _sweeps(rows: list[dict], wk: str, s: dict, only: str | None, dry: bool) -> list[str]:
    """The evidence sweep of each domain whose pack has `sweep` words, before the passes (docs/technical.md, "The
    evidence sweep"): once a week, by its own mark, so a `--repo` run or a catch-up doesn't repeat it; skipped when the
    repo is paused; a dry run says what would run and runs nothing. Its rows count toward the week's spend, so the
    passes' money left is recomputed after it; an unknown cost (a failure) is its whole cap."""
    from engram import relink
    out = []
    for name, d in config.load().items():
        if not d.repo or (only and name != only) or not pack.load(name).prompts.get("sweep"):
            continue
        if paused(d.repo):
            out.append(f"{name}: evidence sweep paused with the repo; skipped")
            continue
        if any(r["week"] == wk and r["repo"] == name and r.get("job") == SWEEP and not r["dry_run"] for r in rows):
            continue
        left = s["weekly_cap"] - spent(rows, wk)
        if left < 1:
            out.append(f"{name}: the weekly cap of ${s['weekly_cap']:.0f} is reached; no evidence sweep")
            continue
        cap = min(left, relink.SWEEP_CAP)
        if dry:
            out.append(f"{name}: would sweep the evidence, up to ${cap:.2f}")
            continue
        head = {"week": wk, "repo": name, "job": SWEEP, "started": datetime.now().isoformat(timespec="seconds"), "dry_run": False}
        rows.append(head | {"cost_usd": cap, "ok": False, "running": True})
        _write(rows)
        try:
            res = relink.sweep(d.repo, cap=cap)
            rows[-1] = head | {"cost_usd": round(res["usd"], 4), "ok": True, "filed": len(res["confirmed"])} | \
                ({"stopped": True} if res["stopped"] else {})
            out.append(f"{name}: evidence sweep " + ("stopped at its cap" if res["stopped"] else "ok") +
                       f", {len(res['confirmed'])} filed, ${res['usd']:.2f}" + ("; the next run picks up" if res["stopped"] else ""))
        except Exception as e:
            rows[-1] = head | {"cost_usd": cap, "ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
            out.append(f"{name}: evidence sweep failed: {rows[-1]['error']}")
        _write(rows)
    return out


def conversations(repo: Path, days: float = 7, session: str | None = None, cap: int = 60000) -> str:
    """The owner's messages in the repo's sessions of the last `days`, each with the reply they read: the pass's
    evidence of use, with, for engram's own repo, the value review's findings on engram's tools. Subagents and sessions
    an agent started (`sessions.by_agent`) are left out; past `cap` characters a session is only counted, and `session`
    reads one whole."""
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
    if left:
        out += ["\n## Left out at the size cap; read each with --session <id>", *left]
    if not session and own() and repo.resolve() == own().resolve():
        found = review.tools(since)
        out += [f"\n# {len(found)} value review findings on engram's tools since {since:%Y-%m-%d}"]
        out += [f"- {f['day']} {f['domain']}, {review.QUESTIONS[f['question']]}: {f['what']} (ref {f['ref']}"
                + (f"; {f['call']}" if f["call"] else "") + ")" for f in found]
    return "\n".join(out)


def _approved(repo: Path) -> list[Path]:
    """The specs the owner approved that the pass still has to settle: build, or mark `blocked:`."""
    out = []
    for spec in sorted((repo / SPECS).glob("*.md")):
        with contextlib.suppress(ValueError, yaml.YAMLError):  # one that won't parse is told at session start
            fields = frontmatter.split(spec.read_text())[0] or {}
            if fields.get("status") == "approved" and "blocked" not in fields:
                out.append(spec)
    return out


def _head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def _branches(repo: Path) -> list[str]:
    return subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname:short)", "refs/heads/refinement/"],
                          capture_output=True, text=True).stdout.split()


def _unfinished(repo: Path, approved: list[Path], head: str, leave: list[str] = ()) -> list[str]:
    """What a pass that says it's fine left undone, read from the repo rather than taken from its word: an approved spec
    it neither built nor marked blocked, a refinement branch still standing (work that never landed; `leave` names ones
    a build on request found and isn't to touch), and a change that reached the default branch with no reviewed landing."""
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.split()
    title = lambda p: next((l[2:] for l in p.read_text().splitlines() if l.startswith("# ")), p.stem)
    still = set(_approved(repo))
    out = [f"approved and not built: {title(p)}" for p in approved if p in still]
    out += [f"work left unlanded on {b}" for b in _branches(repo) if b not in leave]
    reviewed = {c for r in reviews() for c in r.get("landed", [])}
    if unreviewed := [c for c in git("log", f"--grep=^{TRAILER}: ", "--format=%H", f"{head}..HEAD") if c not in reviewed]:
        out.append("landed with no review: " + ", ".join(c[:8] for c in unreviewed))
    return out


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


def _specs(repo: Path) -> tuple[list[Path], list[str]]:
    """(each spec on the owner's page: open, or approved and not yet built, as a pass that didn't land one leaves it; each
    spec whose front matter won't parse). A deferred spec waits for the owner to raise it again, so it's in neither."""
    out, broken = [], []
    for spec in sorted((repo / SPECS).glob("*.md")):
        try:
            fields = frontmatter.split(spec.read_text())[0] or {}
        except (ValueError, yaml.YAMLError) as e:
            broken.append(f"- {spec}: {str(e).splitlines()[0]}")
            continue
        if fields.get("status", "open") in ("open", "approved"):
            out.append(spec)
    return out, broken


def _portrait(repo: Path) -> str:
    """The rewiring's portrait of the owner's jobs, while they're still proposed: in each digest until the owner confirms
    or corrects it."""
    page = repo / PAGE
    fields = frontmatter.split(page.read_text())[0] if page.exists() else None
    return str(fields.get("portrait", "")).strip() if fields and fields.get("jobs") == "proposed" else ""


def surface(here: Path) -> str:
    """What a session start shows from the weekly pass: only, for the agent, a spec or page here or in engram's own repo
    whose front matter won't parse. A session's edit (a status set, jobs confirmed) is how one breaks, and a broken one
    drops out of the digest unseen, so the next session start is where it gets fixed."""
    broken = []
    for src in dict.fromkeys([here.resolve()] + ([own().resolve()] if own() else [])):
        broken += _specs(src)[1]
    try:
        _portrait(here)
    except (ValueError, yaml.YAMLError) as e:
        broken.append(f"- {here / PAGE}: {str(e).splitlines()[0]}")
    return "\n".join(["For you, not the owner (fix the file; never raise it with them):", *broken]) if broken else ""


def _seen() -> set[str]:
    try:
        return set(json.loads((_dir() / "seen.json").read_text()))
    except (OSError, ValueError):  # none yet, or half written: showing a change again beats hiding every one
        return set()


def _failures(rows: list[dict], seen: set[str]) -> dict[str, tuple[str, str]]:
    """Each repo's pass that didn't finish and no page has named, by repo: (its mark in `seen`, what stopped it). A week's
    last pass on the repo speaks for it, and this week's free failure doesn't yet: a catch-up tries it again."""
    last = {(r["week"], r["repo"], r.get("job")): r for r in rows if not r["dry_run"] and r.get("job") not in (SWEEP, PAGE_JOB)}
    return {r["repo"]: (m, r.get("error") or "it stopped before it finished") for r in last.values()
            if not r["ok"] and (r["week"] != week() or r["cost_usd"] >= 1)
            and (m := f"pass:{r['week']}:{r['repo']}:{r['started']}") not in seen}


def digest(targets: dict[str, Path], budget: float, runner=subprocess.run, rows: list[dict] | None = None) -> tuple[float, str]:
    """The week's one page for the owner, across the repos, when something there needs them: each pass that didn't
    finish, each spec waiting on them, each landed change not yet in a page, and their jobs while still proposed. One `claude -p` with no tools
    writes it, the page goes in the data folder and opens in the browser, and only once it opens are its changes marked shown;
    one that can't open waits for its items to change before another is written.
    Returns (cost, a line for the log, empty when nothing needed them: then nothing is written or opened)."""
    seen, items, changed = _seen(), [], set()
    failed = _failures(rows or [], seen)
    for name, repo in targets.items():
        new = [(sha, day, line) for sha, day, line in _landed(repo) if sha not in seen and not line.startswith(UNSEEN)]
        portrait = ""
        with contextlib.suppress(ValueError, yaml.YAMLError):  # a broken page is told at session start
            portrait = _portrait(repo)
        part = ([f"## A pass that didn't finish\n\n{failed[name][1]}"] if name in failed else []) + \
            ([f"## Jobs still proposed\n\n{portrait}"] if portrait else []) + \
            [f"## A spec\n\n{p.read_text()}" for p in _specs(repo)[0]] + \
            (["## Changed since the last page\n\n" + "\n".join(f"- {day}: {line}" for _, day, line in new)] if new else [])
        if part:
            items.append(f"# In {repo.name}\n\n" + "\n\n".join(part))
        changed |= {sha for sha, _, _ in new} | ({failed[name][0]} if name in failed else set())
    if not items:
        _put("unshown.json", {})  # nothing waits, so no page is waiting to be seen
        return 0.0, ""
    held = _unshown()
    if held.get("items") == (key := hashlib.sha256("\n\n".join(items).encode()).hexdigest()):
        return 0.0, f"none, nothing new since the page that wasn't opened, {held['page']}"
    if budget < 0.5:
        return 0.0, "none, the week's cap is spent; its items wait for the next"
    cmd = ["claude", "-p", "--output-format", "json", "--model", settings()["model"], "--max-budget-usd", f"{budget:.2f}",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "project", "--no-session-persistence"]
    prompt = DIGEST.format(owner=config.owner()) + "\n\n" + "\n\n".join(items)
    _work().mkdir(parents=True, exist_ok=True)
    try:
        proc = runner(cmd, input=prompt, cwd=_work(), capture_output=True, text=True, env=claude_env.clean(), timeout=1800)
        res = json.loads(proc.stdout)
        cost = float(res.get("total_cost_usd", budget))
        html = re.search(r"<!doctype html.*</html>", res.get("result") or "", re.S | re.I)
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):  # an unknown cost is the cap
        return budget, "none, the writer gave no answer; its items wait for the next"
    if not html:
        return cost, "none, the writer's answer wasn't one; its items wait for the next"
    page = _dir() / "digests" / f"{week()}.html"
    page.parent.mkdir(exist_ok=True)
    page.write_text(html.group(0))
    opened = sys.platform == "darwin" and runner(["open", str(page)]).returncode == 0
    _put("unshown.json", {} if opened else {"page": str(page), "items": key})
    if opened:  # a page no one could see shows nothing: its items wait, and `engram health` says where it is
        _put("seen.json", sorted(seen | changed))
    return cost, str(page)


def _put(name: str, value):
    tmp = _dir() / f"{name}.tmp"  # written whole
    tmp.write_text(json.dumps(value))
    tmp.replace(_dir() / name)


def _unshown() -> dict:
    """The last page written that couldn't be opened (a box with no screen), and the items it held; {} when there's none."""
    try:
        return json.loads((_dir() / "unshown.json").read_text())
    except (OSError, ValueError):
        return {}


def install(agents: Path | None = None, load: bool = True) -> Path:
    """The timed job that runs the week's passes, kept awake until they end; a time missed asleep fires on wake.
    Running it again rewrites and reloads the same job."""
    from engram import jobs, setup
    return setup.timed_job(agents, LABEL, jobs.awake([*setup.engram_cmd(), "refine", "run"]), _dir() / "launchd.log", load,
                           at=SCHEDULE)
