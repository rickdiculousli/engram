"""The value review (.engram/README.md, "Every repo on engram can call a review"; docs/technical.md, "The value
review"). Once a session in a repo engram serves has idled an hour (the hourly job), or when the owner says the
value isn't there (`engram review <session>`), one model call reads what they asked, each engram call the advisor made
and what it returned, what it answered, and what the record held that day through engram's own first call. It asks
three things (QUESTIONS), and each finding names its cause; the fix goes where the cause is:
- the advisor stopped early: a proposal for that repo's instructions, which 4-7's instruction diff reads, never applied
- engram didn't surface it: a fix drafted by one model run in a scratch clone of engram's release, replayed on the
  session's own calls, then the tests, the frozen gate (run with the packs the box pins) and the repo's measure. It
  lands as a pushed branch with its evidence and its entry in the commit message (`propose`), or merged with the release
  tag advanced and the tag logged with the pins it ran with (`auto`); otherwise dropped.
- never recorded: a filing-rule proposal, or a lead to dig for the advisor's lane
A finding whose fix would change what goes into their record, or where their data lives, only asks them. The limits are in
code (LIMITS); each run's cost is logged. A repo turns it on with `[review] on = true` in its engram.toml. State lives
in the data folder (`review/`), clones in `scratch/review/`, never in a repo."""
import contextlib
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from engram import claude_env, commitmsg, llm, refine
from engram import config as config_mod
from engram.paths import data_path, record_conf
from engram.sources import sessions

QUESTIONS = {"data": "the right data", "path": "a path given up on or missed", "balance": "incomplete or one-sided"}
CAUSES = ("advisor", "tools", "unrecorded")
CALLS = ("search", "timeline", "now", "show", "theory")
AS_OF = ("search",)  # the calls that read as of a day
LIMITS = {"per_day": 1, "fixes_a_week": 2, "drops_in_a_row": 2, "heldout_every": 3, "fixes_a_review": 2}
CAP, ASKS = 4000, 40  # characters of each output the review reads; the last asks of a long session
MODEL = "claude-opus-5-5"
MARK = "engram value review"  # every prompt of its own opens with it: a session that does is never reviewed
LOWER_BETTER = re.compile(r"token|chars|miss|unrun|usd")

SCHEMA = """
CREATE TABLE IF NOT EXISTS review (session TEXT, domain TEXT, at TEXT, how TEXT, findings INTEGER, usd REAL);
CREATE TABLE IF NOT EXISTS finding (id INTEGER PRIMARY KEY, session TEXT, domain TEXT, day TEXT, question TEXT,
  ref TEXT, call TEXT, cause TEXT, rule INTEGER, what TEXT, state TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS fix (finding INTEGER, domain TEXT, key TEXT, at TEXT, outcome TEXT, branch TEXT, usd REAL,
  evidence TEXT, line TEXT);
CREATE TABLE IF NOT EXISTS stop (at TEXT, why TEXT, cleared TEXT);
CREATE TABLE IF NOT EXISTS heldout (at TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS note (id INTEGER PRIMARY KEY, domain TEXT, kind TEXT, line TEXT, at TEXT, shown TEXT);
"""

PROMPT = """{mark}. Below is one session of {owner} with Claude, the advisor of their {domain} record, which it reads
through engram's calls. For each of their asks: their words, each engram call the advisor made (numbered c1, c2, ...) with
what it returned, and the advisor's answer; then what engram's own first call returned for that ask as of the
session's day ({day}), which is what the record held then.

Answer three questions from what the record held that day, never from what you know:
- data: was the advisor served the right data?
- path: did it give up on, or miss, a path that would have made things clearer?
- balance: was what it served incomplete or one-sided?

One finding per problem:
- "question": "data", "path" or "balance"
- "ref": the record it's about, exactly as engram printed its ref
- "call": the number of the call that should have surfaced it ("c3"), or "" if no call was made
- "cause": "advisor" when a call returned it and the advisor stopped early or left it out; "tools" when the record
  held it that day but no call the advisor made surfaced it; "unrecorded" when the record never held it
- "rule": for "unrecorded", true when a filing rule should have caught it from a session; false for a lead to dig
- "what": one sentence on what was missed
- "ask": only when fixing it would change what goes into their record or where their data lives, one sentence to {owner}
  with your recommendation; otherwise ""
No finding is better than a guessed one. Reply with JSON only: {{"findings": [...]}}

{body}"""

FIX_PROMPT = """{mark}: a fix to engram's tools. You're in a scratch clone of engram, the store and search layer under
{owner}'s record repos. Edit only files in this folder. A review of a {domain} session found that the call
`engram {call}` didn't surface a record the record held that day ({ref}), though the question needed it: {what}

Change engram's code (its search, ranking, routing or calls; never a test's expectation, a question or a record) so
the same call surfaces it, without making other questions worse. Keep it small and in the code's style, with a test on
a synthetic fixture. Then reply with one line of JSON: {{"summary": "<what changed, in code terms, no record content>"}}"""


# --- where things are ---------------------------------------------------------------------------------------------

def state_dir() -> Path:
    d = Path(os.environ.get("ENGRAM_REVIEW_DIR") or data_path("review"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def clones() -> Path:
    return state_dir() / "fixes" if os.environ.get("ENGRAM_REVIEW_DIR") else data_path("scratch") / "review"


def db() -> sqlite3.Connection:
    c = sqlite3.connect(state_dir() / "review.sqlite", timeout=30)
    c.executescript(SCHEMA)
    return c


def config() -> dict:
    """engram's own `[review]` settings: `release` (the clone the hourly job runs), `remote`, `heldout`,
    `measure.<domain>` (commands printing a JSON object of numbers), `gate` (the domain whose frozen gate,
    `bench/gate.py`, every fix passes) and `gate_base` (its baseline)."""
    return config_mod.raw().get("review", {})


def gate() -> tuple[str, Path]:
    """The gate's domain and its baseline."""
    c = config()
    name = str(c.get("gate") or "")
    if name and not c.get("gate_base"):
        raise RuntimeError("engram: [review] names a gate but no gate_base, the run it's compared against")
    return name, Path(c.get("gate_base") or "").expanduser()


def pins() -> dict[str, str]:
    """The pack commit each domain's config pins."""
    from engram import pack
    return {n: d.pack for n, d in config_mod.load().items() if pack.SHA.match(d.pack)}


def advance(tag: str, source: Path, gated: dict | None = None) -> str:
    """The release clone moved to `tag` (fetched from `source`) and the tag logged with the pins it runs with, so a
    rollback moves both back. Refuses when the gate's run measured another pack than the one pinned."""
    from engram import pack
    dom, _ = gate()
    if gated is not None and dom in pins():
        have = pack.tree(config_mod.load()[dom].repo, pins()[dom])
        if have != gated.get("pack_tree"):
            raise SystemExit(f"engram: {dom}'s pin {pins()[dom][:12]} isn't the pack the gate measured; the release stays")
    if source.resolve() != release().resolve():
        _git(release(), "fetch", "-q", str(source), f"refs/tags/{tag}:refs/tags/{tag}")
    _git(release(), "checkout", "-q", tag)
    with (data_path("releases.jsonl")).open("a") as f:
        f.write(json.dumps({"tag": tag, "pins": pins(), "at": _now().isoformat(timespec="seconds")}) + "\n")
    return tag


def settings(root: Path | None) -> dict:
    """A repo's switch, off by default, and its landing, `propose` by default."""
    r = (record_conf(root) if root else {}).get("review") or {}
    return {"on": bool(r.get("on")), "landing": "auto" if r.get("landing") == "auto" else "propose"}


def on(root: Path | None) -> bool:
    return settings(root)["on"]


def _now() -> datetime:
    return datetime.now().astimezone()


# --- what the review reads ----------------------------------------------------------------------------------------

REDIRECT = re.compile(r"\d?[<>]{1,2}&?\S*")


def engram_args(command: str) -> list[str] | None:
    """The engram call in a shell command (`engram search "x" --domain notes | head`), or None."""
    for part in re.split(r"&&|\|\||[;|]", command):
        try:
            words = shlex.split(part)
        except ValueError:
            continue
        for i, w in enumerate(words):
            if (w == "engram" or w.endswith("/engram")) and i + 1 < len(words) and words[i + 1] in CALLS:
                args = [x for x in words[i + 1:] if not REDIRECT.fullmatch(x)]  # `2>&1` and the like aren't arguments
                return None if any("$" in x for x in args) else args  # a loop's `$i` can't be replayed
    return None


def read(path: Path) -> dict:
    """The session as the review reads it: each ask of theirs, the engram calls made with their output, the answer."""
    s = sessions.parse(path, path.parent.parent)
    turns, n = [], 0
    for e in s.exchanges:
        if e.meta or e.summary:
            continue
        calls = []
        for ran, out in zip(e.ran, e.results):
            args = engram_args(ran.split(": ", 1)[1]) if ran.startswith("Bash: ") else None
            if args:
                n += 1
                calls.append({"n": f"c{n}", "args": args, "out": out[:CAP]})
        answer = [r for i, r in enumerate(e.replies) if i not in e.narration]
        turns.append({"asked": e.asked, "ts": e.ts, "calls": calls, "answer": "\n".join(answer)[:CAP]})
    day = sessions._local_date(turns[0]["ts"]) if turns else None
    return {"stem": s.stem, "own": bool(turns) and turns[0]["asked"].startswith(MARK), "day": day, "turns": turns[-ASKS:]}


def held(domain: str, question: str, day: str | None) -> str:
    """What the record held on the day, through engram's own first call."""
    from engram import cli, search
    return cli.render(search.search(question, [domain], limit=10, as_of=day, as_it_stood=True))


def prompt(domain: str, view: dict) -> str:
    body = []
    for i, t in enumerate(view["turns"], 1):
        body += [f"## Ask {i}", f"{config_mod.owner()}: {t['asked'][:CAP]}"]
        for c in t["calls"]:
            body += [f"{c['n']}: engram {shlex.join(c['args'])}", c["out"]]
        body += [f"Advisor: {t['answer']}", "Held that day:", held(domain, t["asked"][:500], view["day"])[:CAP], ""]
    return config_mod.voice(PROMPT).format(mark=MARK, domain=domain, day=view["day"], body="\n".join(body))


def parse(reply: dict | None) -> list[dict]:
    """The findings a reply holds, each checked: a question and a cause it names, a ref. Others are left out."""
    out = []
    for f in (reply or {}).get("findings") or []:
        if isinstance(f, dict) and f.get("question") in QUESTIONS and f.get("cause") in CAUSES and f.get("ref"):
            out.append({"question": f["question"], "cause": f["cause"], "ref": str(f["ref"]), "call": str(f.get("call") or ""),
                        "rule": bool(f.get("rule")), "what": str(f.get("what") or ""), "ask": str(f.get("ask") or "")})
    return out


def _ask(text: str) -> tuple[dict | None, float]:
    """The review's one model call: no tools, a clean env, no session kept (so it's never captured)."""
    out, cost = llm.ask_json(text, MODEL, "high", state_dir() / "cache")
    return out, cost.get("usd", 0.0)


# --- the review -----------------------------------------------------------------------------------------------------

def review(path: Path, domain: str, root: Path | None, how: str, landing: str | None = None, push: bool = True,
           now: datetime | None = None) -> dict:
    """Review one session and route every finding. Returns the findings with their routes, and the cost."""
    view = read(path)
    if view["own"]:
        return {"skipped": "the review's own run", "findings": [], "usd": 0.0}
    reply, usd = _ask(prompt(domain, view))
    found = parse(reply)
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO review VALUES (?, ?, ?, ?, ?, ?)", (view["stem"], domain,
                  (now or _now()).isoformat(timespec="seconds"), how, len(found), usd))
    landing = landing or settings(root)["landing"]
    drafted = 0
    for f in found:
        f["route"], cost = route(f, view, domain, root, landing, push, drafted >= LIMITS["fixes_a_review"])
        drafted += bool(f.get("drafted"))
        usd += cost
    return {"findings": found, "usd": usd}


def route(f: dict, view: dict, domain: str, root: Path | None, landing: str, push: bool,
          full: bool = False) -> tuple[str, float]:
    """Send a finding where its cause is: an ask, a proposal, a lead, or a fix. One attempt per cause."""
    key = f"{domain}:{f['cause']}:{f['ref']}"
    with contextlib.closing(db()) as c, c:
        seen = c.execute("SELECT 1 FROM finding WHERE domain = ? AND cause = ? AND ref = ? AND state NOT LIKE 'waiting%'",
                         (domain, f["cause"], f["ref"])).fetchone()
        fid = c.execute("INSERT INTO finding (session, domain, day, question, ref, call, cause, rule, what, state, at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)", (view["stem"], domain, view["day"], f["question"],
                        f["ref"], f["call"], f["cause"], int(f["rule"]), f["what"], _now().isoformat(timespec="seconds"))).lastrowid
    f["id"], f["day"] = fid, view["day"]
    if seen:
        return _state(fid, "tried"), 0.0
    if f["ask"]:
        _note(domain, "ask", f["ask"])
        return _state(fid, "asked"), 0.0
    if f["cause"] == "advisor" or (f["cause"] == "unrecorded" and f["rule"]):
        kind = "instructions" if f["cause"] == "advisor" else "filing rule"
        _append(f"proposals-{domain}.jsonl", {"finding": fid, "kind": kind, "session": view["stem"], "day": view["day"],
                                              "question": f["question"], "ref": f["ref"], "what": f["what"]})
        return _state(fid, "proposed"), 0.0
    if f["cause"] == "unrecorded":
        _note(domain, "lead", f"{f['what']} (ref {f['ref']})")
        return _state(fid, "lead"), 0.0
    blocked = "the review's fixes are drafted" if full else limited()  # at most two fix drafts a review
    if blocked:
        return _state(fid, f"waiting: {blocked}"), 0.0
    return fix(f, view, domain, root, key, landing, push)


def _state(fid: int, state: str) -> str:
    with contextlib.closing(db()) as c, c:
        c.execute("UPDATE finding SET state = ? WHERE id = ?", (state, fid))
    return state


def _append(name: str, row: dict):
    with (state_dir() / name).open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _note(domain: str, kind: str, line: str):
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO note (domain, kind, line, at) VALUES (?, ?, ?, ?)", (domain, kind, line, _now().isoformat(timespec="seconds")))


# --- the limits -----------------------------------------------------------------------------------------------------

def stopped() -> str | None:
    with contextlib.closing(db()) as c:
        row = c.execute("SELECT why FROM stop WHERE cleared IS NULL ORDER BY rowid DESC").fetchone()
    return row[0] if row else None


def limited(now: datetime | None = None) -> str | None:
    """Why no fix may be tried now, or None: a stop, or the week's landed fixes."""
    if why := stopped():
        return f"stopped ({why})"
    since = ((now or _now()) - timedelta(days=7)).isoformat(timespec="seconds")
    with contextlib.closing(db()) as c:
        n = c.execute("SELECT count(*) FROM fix WHERE outcome = 'landed' AND at >= ?", (since,)).fetchone()[0]
    return "two fixes landed this week" if n >= LIMITS["fixes_a_week"] else None


def reviewed_today(domain: str, now: datetime | None = None) -> bool:
    with contextlib.closing(db()) as c:
        return bool(c.execute("SELECT 1 FROM review WHERE domain = ? AND how = 'auto' AND substr(at, 1, 10) = ?",
                              (domain, (now or _now()).date().isoformat())).fetchone())


def stop(why: str):
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO stop (at, why) VALUES (?, ?)", (_now().isoformat(timespec="seconds"), why))


def clear_stop() -> int:
    with contextlib.closing(db()) as c, c:
        return c.execute("UPDATE stop SET cleared = ? WHERE cleared IS NULL", (_now().isoformat(timespec="seconds"),)).rowcount


def _after(outcome: str, code: Path):
    """After a fix: two drops in a row stop the review; every third landing runs the held-out set by script."""
    with contextlib.closing(db()) as c:
        last = [o for (o,) in c.execute("SELECT outcome FROM fix ORDER BY rowid DESC LIMIT ?", (LIMITS["drops_in_a_row"],))]
        landed = c.execute("SELECT count(*) FROM fix WHERE outcome = 'landed'").fetchone()[0]
        prior = c.execute("SELECT result FROM heldout ORDER BY rowid DESC").fetchone()
    if outcome == "dropped" and last == ["dropped"] * LIMITS["drops_in_a_row"]:
        stop(f"{LIMITS['drops_in_a_row']} fixes dropped in a row")
    if outcome != "landed" or landed % LIMITS["heldout_every"]:
        return
    cmd = config().get("heldout")
    if not cmd:
        return stop("no held-out script set")
    now = measure(cmd, code)
    if now is None or (prior and worse(json.loads(prior[0]), now)):
        return stop("the held-out set dropped")
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO heldout VALUES (?, ?)", (_now().isoformat(timespec="seconds"), json.dumps(now)))


# --- a fix to engram's tools ------------------------------------------------------------------------------------------

def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


def release() -> Path:
    return Path(config().get("release") or data_path("release")).expanduser()


def remote() -> str:
    """Where a fix is pushed: `[review] remote`, else the release clone's origin (or that checkout's own origin)."""
    if r := config().get("remote"):
        return r
    url = _git(release(), "remote", "get-url", "origin")
    with contextlib.suppress(subprocess.CalledProcessError):
        if Path(url).is_dir():
            return _git(Path(url), "remote", "get-url", "origin")
    return url


def _draft(text: str, cwd: Path) -> tuple[str, float]:
    """One model run with edit tools in the scratch clone only; no Bash, no session kept."""
    cmd = ["claude", "-p", "--model", MODEL, "--effort", "high", "--output-format", "json", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--tools", "Read,Edit,Write,Glob,Grep",
           "--permission-mode", "acceptEdits"]
    r = subprocess.run(cmd, input=text, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=3600)
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        return "", 0.0
    m = re.search(r"\{.*\}", res.get("result") or "", re.S)
    with contextlib.suppress(json.JSONDecodeError, AttributeError):
        return str(json.loads(m.group(0)).get("summary", "")), res.get("total_cost_usd", 0.0)
    return "", res.get("total_cost_usd", 0.0)


def _engram(code: Path, args: list[str], root: Path | None, data: Path) -> str:
    env = claude_env.clean(ENGRAM_DATA=str(data), ENGRAM_FROZEN="1")
    r = subprocess.run(["uv", "run", "-q", "--project", str(code), "engram", *args], cwd=root or code, env=env,
                       capture_output=True, text=True, timeout=600)
    return r.stdout


def replay(code: Path, calls: list[list[str]], root: Path | None, day: str | None, data: Path) -> str:
    """The session's own calls through `code`, as of its day, on a copy of the data."""
    return "\n".join(_engram(code, a + (["--as-of", day] if a[0] in AS_OF and "--as-of" not in a and day else []), root, data)
                     for a in calls)


def measure(cmd: list[str], code: Path) -> dict | None:
    r = subprocess.run(cmd, cwd=code, env=claude_env.clean(ENGRAM_FROZEN="1"), capture_output=True, text=True, timeout=7200)
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(r.stdout)
    return None


def _numbers(d, at: str = "") -> dict:
    if isinstance(d, dict):
        return {k: v for key, val in d.items() for k, v in _numbers(val, f"{at}.{key}" if at else key).items()}
    return {at: d} if isinstance(d, (int, float)) and not isinstance(d, bool) else {}


def worse(before: dict, after: dict) -> list[str]:
    """Each number that got worse: lower, or higher for tokens, characters, misses, unrun and cost."""
    a, b = _numbers(before), _numbers(after)
    return [k for k in a if k in b and ((b[k] > a[k]) if LOWER_BETTER.search(k) else (b[k] < a[k]))]


def check_tests(base: Path, fixed: Path, domain: str, work: Path) -> tuple[bool, str]:
    r = subprocess.run(["uv", "run", "-q", "pytest", "-q"], cwd=fixed, env=claude_env.clean(), capture_output=True, text=True)
    return r.returncode == 0, "tests pass" if r.returncode == 0 else "tests fail"


def check_gate(base: Path, fixed: Path, domain: str, work: Path) -> tuple[bool, str]:
    """The frozen gate says "same", run with the pack the box pins for its domain; for a fix meant for that domain,
    nothing in it may get worse."""
    dom, baseline = gate()
    if not dom:
        return False, "no gate set ([review] gate)"
    script, out = "bench/gate.py", work / "gate.json"
    gate_py, ours = fixed / script, Path(__file__).resolve().parents[2] / script
    if not gate_py.exists() and ours.exists():  # a release older than the gate: the gate of record is the running engram's
        shutil.copy(ours, gate_py)
    d = config_mod.load().get(dom)
    pinned = ["--pack", f"{d.repo}@{d.pack}"] if d and d.repo and dom in pins() else []
    subprocess.run(["uv", "run", "-q", "python", script, "run", str(out), *pinned], cwd=fixed, env=claude_env.clean(),
                   capture_output=True, text=True)
    if not out.exists():
        return False, f"the {dom} gate didn't run"
    r = subprocess.run(["uv", "run", "-q", "python", script, "compare", str(baseline), str(out)], cwd=fixed,
                       env=claude_env.clean(), capture_output=True, text=True)
    if r.stdout.strip() == "same":
        return True, f"{dom} gate same"
    if domain == dom:
        down = worse(json.loads(baseline.read_text()), json.loads(out.read_text()))
        return not down, f"{dom} gate moved, {len(down)} values worse"
    return False, f"{dom} gate moved ({len(r.stdout.splitlines())} values)"


def check_measure(base: Path, fixed: Path, domain: str, work: Path) -> tuple[bool, str]:
    """The repo's measure by script on the release and on the fix: nothing worse. The gate's domain's is the gate."""
    if domain == gate()[0]:
        return True, "measure: the gate"
    cmd = (config().get("measure") or {}).get(domain)
    if not cmd:
        return False, f"no measure set for {domain}"
    a, b = measure(cmd, base), measure(cmd, fixed)
    if a is None or b is None:
        return False, "the measure didn't run"
    down = worse(a, b)
    return not down, f"measure: {len(_numbers(b))} values, {len(down)} worse"


CHECKS = [check_tests, check_gate, check_measure]


def fix(f: dict, view: dict, domain: str, root: Path | None, key: str, landing: str, push: bool) -> tuple[str, float]:
    """Draft, replay and check a fix in a scratch clone; land it, or drop it and keep the finding open."""
    work = clones() / f"fix-{f['id']}"
    shutil.rmtree(work, ignore_errors=True)
    base, fixed, branch = work / "base", work / "fixed", f"review/fix-{f['id']}"
    for d in (base, fixed):
        subprocess.run(["git", "clone", "-q", str(release()), str(d)], check=True, capture_output=True)
    _git(fixed, "checkout", "-q", "-b", branch)
    made = [c for t in view["turns"] for c in t["calls"]]  # the call named, else every call made, else engram's first call
    calls = ([c["args"] for c in made if c["n"] == f["call"]] or [c["args"] for c in made]
             or [["search", t["asked"][:500]] for t in view["turns"]])
    call = shlex.join(calls[0]) if calls else "search"
    refine.copy_data(work / "data")
    if f["ref"] in replay(base, calls, root, view["day"], work / "data"):  # engram already surfaces it: the advisor's to use
        _append(f"proposals-{domain}.jsonl", {"finding": f["id"], "kind": "instructions", "session": view["stem"],
                                              "day": view["day"], "question": f["question"], "ref": f["ref"],
                                              "what": f["what"], "why": f"engram's {call.split(' ')[0]} already surfaces it"})
        return _state(f["id"], "proposed: engram already surfaces it"), 0.0
    f["drafted"] = True
    summary, usd = _draft(config_mod.voice(FIX_PROMPT).format(mark=MARK, domain=domain, call=call, ref=f["ref"], what=f["what"]), fixed)
    _git(fixed, "add", "-A")
    evidence = {"replay": {"of": 1}}
    if not _git(fixed, "status", "--porcelain"):
        return _drop(f, domain, key, usd, evidence, "no change drafted", fixed)
    _git(fixed, "-c", "user.name=engram review", "-c", "user.email=engram@localhost", "commit", "-q", "-m",
         commitmsg.message("review", id=f["id"], question=f["question"], call=calls[0][0] if calls else "search"))
    evidence["replay"]["before"] = 0
    evidence["replay"]["after"] = int(f["ref"] in replay(fixed, calls, root, view["day"], work / "data"))
    if not evidence["replay"]["after"]:
        return _drop(f, domain, key, usd, evidence, "the replay still misses it", fixed)
    for check in CHECKS:
        ok, line = check(base, fixed, domain, work)
        evidence[check.__name__.removeprefix("check_")] = line
        if not ok:
            return _drop(f, domain, key, usd, evidence, line, fixed)
    return _land(f, domain, key, usd, evidence, summary, fixed, branch, landing, push), usd


def _drop(f: dict, domain: str, key: str, usd: float, evidence: dict, why: str, code: Path) -> tuple[str, float]:
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO fix VALUES (?, ?, ?, ?, 'dropped', NULL, ?, ?, NULL)", (f["id"], domain, key,
                  _now().isoformat(timespec="seconds"), usd, json.dumps({**evidence, "why": why})))
    _after("dropped", code)
    return _state(f["id"], f"open: dropped, {why}"), usd


def entry(f: dict, domain: str, day: str | None, summary: str, evidence: dict) -> str:
    """The fix's plain entry, in its commit message: what was missed, why, what changed, and what it measured, by counts."""
    r = evidence["replay"]
    return (f"{domain}, finding {f['id']}\n\n"
            f"- **Missed:** a record a question needed in a session of {day} ({QUESTIONS[f['question']]}).\n"
            f"- **Why:** engram's call didn't surface it, though the record held it that day.\n"
            f"- **Changed:** {summary or 'see the commit'}\n"
            f"- **Measured:** the session's calls replayed found it {r['after']} of {r['of']} (before: {r['before']}); "
            + "; ".join(v for k, v in evidence.items() if k != "replay") + ".\n")


def _land(f, domain, key, usd, evidence, summary, fixed, branch, landing, push) -> str:
    _git(fixed, "-c", "user.name=engram review", "-c", "user.email=engram@localhost", "commit", "-q", "--amend", "-m",
         f"{_git(fixed, 'log', '-1', '--format=%B')}\n\n{entry(f, domain, f.get('day'), summary, evidence)}\n"
         + json.dumps(evidence, sort_keys=True))
    line = "Engram found a record it had left out of one of your answers, and now brings it back."
    done = "proposed"
    if push:
        url = remote()
        _git(fixed, "push", "-q", url, branch)
        if landing == "auto":
            done = _release(fixed, url, branch)
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO fix VALUES (?, ?, ?, ?, 'landed', ?, ?, ?, ?)", (f["id"], domain, key,
                  _now().isoformat(timespec="seconds"), branch, usd, json.dumps(evidence), line))
    if done == "released":
        _note(domain, "fix", line)
    _after("landed", fixed)
    return _state(f["id"], done)


def _release(fixed: Path, url: str, branch: str) -> str:
    """`auto`: the fix (on the release it was checked on) becomes the next release tag, and is merged into main."""
    tags = set(_git(fixed, "tag").split()) | {l.rsplit("/", 1)[-1] for l in _git(fixed, "ls-remote", "--tags", url).splitlines()}
    tag = next(t for n in range(1, 100) if (t := f"release-{_now():%Y-%m-%d}" + (f"-{n}" if n > 1 else "")) not in tags)
    try:
        _git(fixed, "tag", tag)
        _git(fixed, "push", "-q", url, tag)
        advance(tag, fixed)
    except subprocess.CalledProcessError:
        return "proposed; the release didn't advance"
    try:
        _git(fixed, "fetch", "-q", url, "main")
        _git(fixed, "checkout", "-q", "-B", "land", "FETCH_HEAD")
        _git(fixed, "-c", "user.name=engram review", "-c", "user.email=engram@localhost", "merge", "-q", "--no-ff", "-m",
             f"Merge {branch}", branch)
        _git(fixed, "push", "-q", url, "land:main")
    except subprocess.CalledProcessError:
        return "released; main not merged"
    return "released"


def landed(fid: int) -> str | None:
    """The lead merged a proposed fix and advanced the release: its line goes into the owner's next note."""
    with contextlib.closing(db()) as c:
        row = c.execute("SELECT domain, line FROM fix WHERE finding = ? AND outcome = 'landed'", (fid,)).fetchone()
    if row:
        _note(row[0], "fix", row[1])
        _state(fid, "released")
    return row and row[1]


# --- what reaches the owner, and the advisor ---------------------------------------------------------------------------

def opening(domain: str) -> str | None:
    """His next note's one line: the oldest ask waiting on them (asked every session until answered), else a fix not
    yet told, once."""
    with contextlib.closing(db()) as c, c:
        row = (c.execute("SELECT id, line, kind FROM note WHERE domain = ? AND kind = 'ask' AND shown IS NULL ORDER BY id", (domain,)).fetchone()
               or c.execute("SELECT id, line, kind FROM note WHERE domain = ? AND kind = 'fix' AND shown IS NULL ORDER BY id", (domain,)).fetchone())
        if row and row[2] == "fix":
            c.execute("UPDATE note SET shown = ? WHERE id = ?", (_now().isoformat(timespec="seconds"), row[0]))
    return row[1] if row else None


def answered(nid: int):
    with contextlib.closing(db()) as c, c:
        c.execute("UPDATE note SET shown = ? WHERE id = ? AND kind = 'ask'", (_now().isoformat(timespec="seconds"), nid))


def leads(domain: str) -> list[str]:
    """Leads to dig, for the advisor's lane, each handed over once."""
    with contextlib.closing(db()) as c, c:
        rows = c.execute("SELECT id, line FROM note WHERE domain = ? AND kind = 'lead' AND shown IS NULL", (domain,)).fetchall()
        c.executemany("UPDATE note SET shown = ? WHERE id = ?", [(_now().isoformat(timespec="seconds"), i) for i, _ in rows])
    return [l for _, l in rows]


def session_start(domain: str, root: Path) -> list[str]:
    """What the session-start hook adds when the review is on: the line to open with, and leads to dig."""
    if not on(root):
        return []
    out = [f"Open your first reply to {config_mod.owner()} with this one line: {line}"] if (line := opening(domain)) else []
    return out + [f"engram's value review left a lead to dig in your lane, if their question touches it: {l}" for l in leads(domain)]


# --- the triggers ---------------------------------------------------------------------------------------------------

def hourly(domain: str, root: Path, idle: list[Path], now: datetime | None = None) -> dict | None:
    """The hourly job's review: the latest session idle an hour, at most one a day per repo, never its own runs."""
    if not on(root) or reviewed_today(domain, now):
        return None
    with contextlib.closing(db()) as c:
        done = {s for (s,) in c.execute("SELECT session FROM review WHERE domain = ?", (domain,))}
    for p in sorted((p for p in idle if p.stem not in done), key=lambda p: p.stat().st_mtime, reverse=True):
        r = review(p, domain, root, "auto", now=now)
        if not r.get("skipped"):
            return r
    return None


def find(prefix: str) -> tuple[Path, str]:
    """A session by id prefix, and its domain, from the sessions' state."""
    with contextlib.closing(sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)) as st:
        rows = st.execute("SELECT path, domain FROM file WHERE gone IS NULL AND path NOT LIKE '%/subagents/%'").fetchall()
    hits = [(Path(p), d) for p, d in rows if Path(p).stem.startswith(prefix)]
    if len(hits) != 1:
        raise LookupError(f"{len(hits)} sessions start with {prefix!r}")
    return hits[0]


def on_demand(prefix: str, dry_run: bool = False) -> dict:
    """`engram review <session>`: the owner said the value isn't there. A dry run keeps its state and clones in scratch,
    proposes and pushes nothing."""
    path, domain = find(prefix)
    if dry_run:
        os.environ["ENGRAM_REVIEW_DIR"] = str(data_path("scratch") / f"review/dry-{_now():%Y%m%d-%H%M%S}")
    root = d.repo if (d := config_mod.load().get(domain)) else None
    r = review(path, domain, root, "dry" if dry_run else "asked", landing="propose", push=not dry_run)
    return {**r, "state": str(state_dir())}


def summary(r: dict) -> str:
    """Findings by count, by question and by cause and route, and the cost; never their content."""
    if r.get("skipped"):
        return f"engram review: skipped ({r['skipped']})"
    f = r["findings"]
    count = lambda k: ", ".join(f"{v} {n}" for n, v in sorted(Counter(x[k] for x in f).items())) or "none"
    routes = Counter(x.get("route", "").split(":")[0] for x in f)
    return (f"engram review: {len(f)} findings; by question {count('question')}; by cause {count('cause')}; "
            f"routed {', '.join(f'{v} {k}' for k, v in sorted(routes.items())) or 'none'}; ${r['usd']:.2f}")
