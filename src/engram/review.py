"""The value review (.engram/README.md, "Every repo on engram can call a review"; docs/technical.md, "The value
review"). Once a session in a repo engram serves has idled an hour (the hourly job), or when the owner says the
value isn't there (`engram review <session>`), one model call reads what they asked, each engram call the advisor made
and what it returned, what it answered, and what the record held that day through engram's own first call. It asks
three things (QUESTIONS), and each finding is recorded with its cause in the data folder (`review/`); the weekly pass
on engram's own repo reads the `tools` ones beside the week's conversations (`tools`). The review lands no code.
A repo turns it on with `[review] on = true` in its engram.toml.

The release step lives here too: `engram review --release` moves the release clone to a tag (`advance`)."""
import contextlib
import json
import os
import re
import shlex
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from engram import llm
from engram import config as config_mod
from engram.paths import data_path, record_conf
from engram.sources import sessions

QUESTIONS = {"data": "the right data", "path": "a path given up on or missed", "balance": "incomplete or one-sided"}
CAUSES = ("advisor", "tools", "unrecorded")
CALLS = ("search", "timeline", "now", "show", "theory")
CAP, ASKS = 4000, 40  # characters of each output the review reads; the last asks of a long session
MODEL = "claude-opus-5-5"
MARK = "engram value review"  # every prompt of its own opens with it: a session that does is never reviewed

SCHEMA = """
CREATE TABLE IF NOT EXISTS review (session TEXT, domain TEXT, at TEXT, how TEXT, findings INTEGER, usd REAL);
CREATE TABLE IF NOT EXISTS finding (id INTEGER PRIMARY KEY, session TEXT, domain TEXT, day TEXT, question TEXT,
  ref TEXT, call TEXT, cause TEXT, what TEXT, at TEXT);
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
- "what": one sentence on what was missed
No finding is better than a guessed one. Reply with JSON only: {{"findings": [...]}}

{body}"""


# --- where things are ---------------------------------------------------------------------------------------------

def state_dir() -> Path:
    d = Path(os.environ.get("ENGRAM_REVIEW_DIR") or data_path("review"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def db() -> sqlite3.Connection:
    c = sqlite3.connect(state_dir() / "review.sqlite", timeout=30)
    c.executescript(SCHEMA)
    return c


def on(root: Path | None) -> bool:
    """A repo's switch, off by default."""
    return bool(((record_conf(root) if root else {}).get("review") or {}).get("on"))


def _now() -> datetime:
    return datetime.now().astimezone()


# --- the release --------------------------------------------------------------------------------------------------

def config() -> dict:
    """engram's own `[review]` settings the release reads: `release` (the clone the hourly job runs), `gate` (the domain
    whose frozen gate, `bench/gate.py`, a release passes) and `gate_base` (its baseline)."""
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


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


def release() -> Path:
    return Path(config().get("release") or data_path("release")).expanduser()


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
                return [x for x in words[i + 1:] if not REDIRECT.fullmatch(x)]  # `2>&1` and the like aren't arguments
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
                        "what": str(f.get("what") or "")})
    return out


def _ask(text: str) -> tuple[dict | None, float]:
    """The review's one model call: no tools, a clean env, no session kept (so it's never captured)."""
    out, cost = llm.ask_json(text, MODEL, "high", state_dir() / "cache")
    return out, cost.get("usd", 0.0)


# --- the review -----------------------------------------------------------------------------------------------------

def review(path: Path, domain: str, how: str, now: datetime | None = None) -> dict:
    """Review one session and record every finding, the call it names written out. Returns the findings and the cost."""
    view = read(path)
    if view["own"]:
        return {"skipped": "the review's own run", "findings": [], "usd": 0.0}
    reply, usd = _ask(prompt(domain, view))
    found = parse(reply)
    calls = {c["n"]: f"engram {shlex.join(c['args'])}" for t in view["turns"] for c in t["calls"]}
    at = (now or _now()).isoformat(timespec="seconds")
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO review VALUES (?, ?, ?, ?, ?, ?)", (view["stem"], domain, at, how, len(found), usd))
        c.executemany("INSERT INTO finding (session, domain, day, question, ref, call, cause, what, at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(view["stem"], domain, view["day"], f["question"], f["ref"],
                      calls.get(f["call"], f["call"]), f["cause"], f["what"], at) for f in found])
    return {"findings": found, "usd": usd}


def tools(since: datetime) -> list[dict]:
    """The findings on engram's tools recorded since `since`: the weekly pass's evidence beside the conversations."""
    if not (state_dir() / "review.sqlite").exists():
        return []
    with contextlib.closing(db()) as c:
        rows = c.execute("SELECT day, domain, question, ref, call, what FROM finding WHERE cause = 'tools' AND at >= ? "
                         "ORDER BY at", (since.astimezone().isoformat(timespec="seconds"),)).fetchall()
    return [dict(zip(("day", "domain", "question", "ref", "call", "what"), r)) for r in rows]


def reviewed_today(domain: str, now: datetime | None = None) -> bool:
    with contextlib.closing(db()) as c:
        return bool(c.execute("SELECT 1 FROM review WHERE domain = ? AND how = 'auto' AND substr(at, 1, 10) = ?",
                              (domain, (now or _now()).date().isoformat())).fetchone())


# --- the triggers ---------------------------------------------------------------------------------------------------

def hourly(domain: str, root: Path, idle: list[Path], now: datetime | None = None) -> dict | None:
    """The hourly job's review: the latest session idle an hour, at most one a day per repo, never its own runs."""
    if not on(root) or reviewed_today(domain, now):
        return None
    with contextlib.closing(db()) as c:
        done = {s for (s,) in c.execute("SELECT session FROM review WHERE domain = ?", (domain,))}
    for p in sorted((p for p in idle if p.stem not in done), key=lambda p: p.stat().st_mtime, reverse=True):
        r = review(p, domain, "auto", now=now)
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
    """`engram review <session>`: the owner said the value isn't there. A dry run keeps its findings in scratch, out of
    the weekly pass's evidence."""
    path, domain = find(prefix)
    if dry_run:
        os.environ["ENGRAM_REVIEW_DIR"] = str(data_path("scratch") / f"review/dry-{_now():%Y%m%d-%H%M%S}")
    r = review(path, domain, "dry" if dry_run else "asked")
    return {**r, "state": str(state_dir())}


def summary(r: dict) -> str:
    """Findings by count, by question and by cause, and the cost; never their content."""
    if r.get("skipped"):
        return f"engram review: skipped ({r['skipped']})"
    f = r["findings"]
    count = lambda k: ", ".join(f"{v} {n}" for n, v in sorted(Counter(x[k] for x in f).items())) or "none"
    return f"engram review: {len(f)} findings; by question {count('question')}; by cause {count('cause')}; ${r['usd']:.2f}"
