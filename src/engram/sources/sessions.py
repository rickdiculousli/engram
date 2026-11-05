"""Claude Code sessions, filed into one domain each. Nothing of a session is indexed from here: a domain's index holds
its record and the checked session summaries (the owner: "DO NOT STORE GARBAGE"); the transcripts stay where
Claude Code keeps them, read by the summaries and the capture job.

A session belongs to a domain only if it was started in that domain's repo (or a worktree of it): the owner's call,
"sessions only count in the repo". Touching a repo's files or naming its medications from elsewhere doesn't count;
everything else is general, searched only on request. Files that haven't changed since the last run are skipped; a changed file is
re-read whole, so a rewritten (compacted) file is handled the same way as a grown one.
"""
from collections import defaultdict
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from engram.config import GENERAL, Domain
from engram.index import now, open_index
from engram.paths import data_path, index_path

ROOT = Path(os.environ.get("ENGRAM_SESSIONS_ROOT", Path.home() / ".claude/projects")).expanduser()
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
NOT_A_TURN = ("<task-notification", "<command-", "<local-command", "<bash-", "Caveat:", "[Request interrupted",
              "Delegated task ", "<agent-message ")  # a T3 delegate's report, an agent's hand-back
SUMMARY = "This session is being continued from a previous conversation"
# T3 runs a throwaway session to title each thread; it repeats the thread's first message, which the real session holds.
SKIP_PROJECTS = ("-T-t3code-claude-title-",)
# Sessions that build or review engram's question sets hold the answer keys; indexed, a test run could read them back.
EVAL_WORK = "/.local/share/engram/eval"
# Bump when classification changes, so every known file is filed again on the next ingest.
CLASSIFY_VERSION = "5"
HEAD = 65536
# How a session an agent started opens. T3 puts "Act as the <role> sub-agent for this task." before every brief it
# delegates, and nothing else tells such a session from the owner's own: both are `sdk-ts`, in a worktree, in auto mode.
AGENT_OPENERS = ("Act as the", "Read your brief at", "You are executor", "You generate", "=== QUEUED")
BRIEF_CHARS = 1500  # a message this long with headings is an agent's brief, written for an agent: no quote comes from one
HEADINGS = re.compile(r"^#{1,6} ", re.M)


@dataclass
class Exchange:
    line: int
    ts: str | None
    asked: str
    uuid: str = ""
    summary: bool = False
    replies: list[str] = field(default_factory=list)
    ran: list[str] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    queued: list[tuple[int, str]] = field(default_factory=list)  # (replies before it, words): sent while Claude worked
    narration: set[int] = field(default_factory=set)  # replies Claude wrote between commands, before its final reply
    meta: bool = False  # text Claude Code injected as a user turn, such as a skill's instructions


@dataclass
class Session:
    path: Path
    stem: str
    project: str
    title: str = ""
    entrypoint: str = ""  # sdk-cli is a headless `claude -p` run, started by a program
    cwds: set = field(default_factory=set)
    cwd: str = ""  # the first working folder
    exchanges: list[Exchange] = field(default_factory=list)


def _text_of(content) -> tuple[list[str], list[str]]:
    if isinstance(content, str):
        return [content], []
    texts, results = [], []
    for b in content if isinstance(content, list) else []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            texts.append(b.get("text", ""))
        elif b.get("type") == "tool_result":
            c = b.get("content")
            if isinstance(c, list):
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
            results.append(str(c or ""))
    return texts, results


def _tool_line(b: dict) -> str:
    inp = b.get("input") or {}
    name = b.get("name", "")
    for k in ("command", "pattern", "url", "query", "prompt", "description"):
        if inp.get(k):
            return f"{name}: {str(inp[k])[:600]}"
    return f"{name}: {' '.join(str(inp[k]) for k in ('file_path', 'path', 'notebook_path') if inp.get(k))}".strip()


def _typed(e: dict) -> bool:
    """Whether a line is a message someone typed, not a tool's result or text the harness added."""
    msg = e.get("message")
    if e.get("type") != "user" or e.get("isMeta") or e.get("isSidechain") or not isinstance(msg, dict):
        return False
    asked = REMINDER.sub("", "\n".join(_text_of(msg.get("content"))[0])).strip()
    return bool(asked) and not asked.startswith(NOT_A_TURN)


def _rewound(lines: list[tuple[int, dict]]) -> set[int]:
    """The lines a rewind left behind. A rewind keeps the old messages in the file, so where the owner went back and
    typed again, two typed messages follow the same one: the one off the branch the session ended on goes, with all
    that followed it. Only that goes, since a tool call's parallel results also fork the chain, and aren't taken back."""
    by, kids, last = {}, defaultdict(list), None
    for _, e in lines:
        if u := e.get("uuid"):
            by[u] = e
            kids[e.get("parentUuid")].append(e)
            if e.get("type") in ("user", "assistant") and not e.get("isSidechain"):
                last = u
    live, u = set(), last
    while u in by and u not in live:
        live.add(u)
        u = by[u].get("parentUuid") or by[u].get("logicalParentUuid")
    gone, walk = set(), []
    for parent, follow in kids.items():
        typed = [e["uuid"] for e in follow if _typed(e)]
        if parent and len(typed) > 1 and live.intersection(typed):
            walk += [u for u in typed if u not in live]
    while walk:
        u = walk.pop()
        if u not in gone:
            gone.add(u)
            walk += [e["uuid"] for e in kids[u]]
    return {n for n, e in lines if e.get("uuid") in gone}


def parse(path: Path, root: Path | None = None) -> Session:
    root = root or ROOT
    s = Session(path, path.stem, path.relative_to(root).parts[0])
    cur: Exchange | None = None
    with path.open(errors="replace") as f:
        lines = []
        for n, line in enumerate(f, 1):
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict):
                lines.append((n, e))
        rewound = _rewound(lines)
        for n, e in lines:
            if n in rewound:
                continue
            if e.get("cwd"):
                s.cwds.add(e["cwd"])
                s.cwd = s.cwd or e["cwd"]
            t = e.get("type")
            att = e.get("attachment") if t == "attachment" else None
            if isinstance(att, dict) and att.get("type") == "queued_command" and cur is not None:
                said = REMINDER.sub("", "\n".join(_text_of(att.get("prompt"))[0])).strip()
                if said and not said.startswith(NOT_A_TURN):
                    cur.queued.append((len(cur.replies), said))
                continue
            if t == "ai-title":
                s.title = str(e.get("aiTitle") or e.get("title") or s.title)
                continue
            msg = e.get("message")
            if not isinstance(msg, dict):
                continue
            if t == "user":
                s.entrypoint = s.entrypoint or str(e.get("entrypoint") or "")
                texts, results = _text_of(msg.get("content"))
                asked = REMINDER.sub("", "\n".join(texts)).strip()
                if asked and not asked.startswith(NOT_A_TURN):
                    cur = Exchange(n, e.get("timestamp"), asked, str(e.get("uuid") or ""), summary=asked.startswith(SUMMARY),
                                   meta=bool(e.get("isMeta")))
                    s.exchanges.append(cur)
                if cur and results:
                    cur.results += results
            elif t == "assistant" and cur is not None:
                for b in msg.get("content") if isinstance(msg.get("content"), list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        if msg.get("stop_reason") == "tool_use":
                            cur.narration.add(len(cur.replies))
                        cur.replies.append(b["text"].strip())
                    elif b.get("type") == "tool_use":
                        cur.ran.append(_tool_line(b))
    return s


def brief(text: str) -> bool:
    return len(text) > BRIEF_CHARS and bool(HEADINGS.search(text))


def by_agent(s: Session) -> bool:
    """A session no person typed into: a headless run (`sdk-cli`, the filer's own), or one that opens the way a delegated
    agent's brief does. None of its messages are the owner's words. A long first message alone doesn't count: the owner
    opens with long pastes too, and each message is judged a brief on its own where it matters."""
    first = next((e.asked for e in s.exchanges if not e.meta and not e.summary), "")
    return s.entrypoint == "sdk-cli" or first.startswith(AGENT_OPENERS)


def _dashed(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", name)


def started_in(s: Session, repo: Path | None) -> bool:
    """Whether the session was started in the repo or below it, or in a worktree of it. Claude Code names a session's
    project folder after the folder it started in (every character but letters and digits a dash), so the folder name
    is the test; a session's first working folder is the fallback for one filed elsewhere."""
    if not repo:
        return False
    if re.search(rf"-{re.escape(_dashed(repo.name))}(-|$)", s.project):
        return True
    return bool(s.cwd) and (s.cwd == str(repo) or s.cwd.startswith(str(repo) + "/"))


def classify(s: Session, doms: dict[str, Domain]) -> str:
    """The first configured domain whose repo the session started in, or one of the other folders its sessions start
    in (`sessions_from`, such as a harness's temp folders); else the general pile."""
    for d in doms.values():
        if started_in(s, d.repo) or any(m in s.project or m in s.cwd for m in d.sessions_from):
            return d.name
    return GENERAL


def _local_date(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return None


def _state() -> sqlite3.Connection:
    c = sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS file (path TEXT PRIMARY KEY, bytes INTEGER, mtime_ns INTEGER, head_sha TEXT, "
              "domain TEXT, exchanges INTEGER, docs INTEGER, rewrites INTEGER DEFAULT 0, seen TEXT, gone TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    return c


def eval_work(path: Path, root: Path) -> bool:
    """A session, or a subagent of one, that touched engram's eval directory."""
    def has(p: Path) -> bool:
        try:
            return EVAL_WORK.encode() in p.read_bytes()
        except OSError:
            return False
    parts = path.relative_to(root).parts
    if "subagents" in parts:
        i = parts.index("subagents")
        parent = root.joinpath(*parts[:i - 1], f"{parts[i - 1]}.jsonl")
        if has(parent):
            return True
    return has(path)


def _head_sha(p: Path) -> str:
    with p.open("rb") as f:
        return hashlib.sha256(f.read(HEAD)).hexdigest()


def _drop(idx, source: str) -> bool:
    if not idx.db.execute("SELECT 1 FROM doc WHERE source = ? LIMIT 1", (source,)).fetchone():
        return False
    idx.sync_source(source, [])
    idx.db.execute("DELETE FROM ingest_state WHERE source = ?", (source,))
    idx.db.commit()
    return True


def ingest(doms: dict[str, Domain], root: Path | None = None) -> dict:
    """File each new or changed session into the domain it was started in. Nothing of a session is indexed here: a
    domain's index holds its record and the session summaries that passed their checks (summarize.index_all), and raw
    turns, tool output, subagents and Claude's memory files are kept out of every index (the owner: "DO NOT STORE GARBAGE").
    Rows an earlier version indexed are removed."""
    root = root or ROOT
    st = _state()
    known = {r[0]: r[1:] for r in st.execute("SELECT path, bytes, mtime_ns, head_sha, domain FROM file")}
    row = st.execute("SELECT value FROM meta WHERE key = 'classify_version'").fetchone()
    refile = (row[0] if row else None) != CLASSIFY_VERSION
    files = sorted((p for p in root.rglob("*.jsonl") if p.is_file()), key=lambda p: p.stat().st_mtime)
    idx = {d: open_index(index_path(d)) for d in doms}
    counts = {"files": len(files), "read": 0, "rewritten": 0, "removed": 0, "gone": 0}
    try:
        if refile:  # raw session rows and memory files an earlier version indexed
            for i in idx.values():
                for (source,) in i.db.execute("SELECT DISTINCT source FROM doc WHERE source LIKE 'memory:%' OR "
                                              "(source LIKE 'sessions:%' AND source NOT LIKE '%:summary')").fetchall():
                    counts["removed"] += _drop(i, source)
        for p in files:
            stt = p.stat()
            prev = known.get(str(p))
            if not refile and prev and (prev[0], prev[1]) == (stt.st_size, stt.st_mtime_ns):
                continue
            if any(m in str(p.relative_to(root)) for m in SKIP_PROJECTS) or eval_work(p, root):
                with st:
                    st.execute("INSERT OR REPLACE INTO file (path, bytes, mtime_ns, domain, exchanges, docs, seen) VALUES (?, ?, ?, 'skipped', 0, 0, ?)",
                               (str(p), stt.st_size, stt.st_mtime_ns, now()))
                continue
            head = _head_sha(p)
            rewritten = bool(prev) and (stt.st_size < prev[0] or (prev[0] >= HEAD and head != prev[2]))
            s = parse(p, root)
            domain = classify(s, doms)
            counts["read"] += 1
            counts["rewritten"] += rewritten
            with st:
                st.execute("INSERT INTO file (path, bytes, mtime_ns, head_sha, domain, exchanges, docs, rewrites, seen) "
                           "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?) ON CONFLICT(path) DO UPDATE SET bytes = excluded.bytes, "
                           "mtime_ns = excluded.mtime_ns, head_sha = excluded.head_sha, domain = excluded.domain, "
                           "exchanges = excluded.exchanges, docs = 0, rewrites = file.rewrites + excluded.rewrites, "
                           "seen = excluded.seen, gone = NULL",
                           (str(p), stt.st_size, stt.st_mtime_ns, head, domain, len(s.exchanges), int(rewritten), now()))
        with st:
            st.execute("INSERT OR REPLACE INTO meta VALUES ('classify_version', ?)", (CLASSIFY_VERSION,))
        present = {str(p) for p in files}
        with st:
            for path in known:
                if path not in present:
                    st.execute("UPDATE file SET gone = coalesce(gone, ?) WHERE path = ?", (now(), path))
                    counts["gone"] += 1
    finally:
        for i in idx.values():
            i.close()
        st.close()
    return counts


def summary() -> dict:
    st = _state()
    rows = st.execute("SELECT domain, count(*), sum(exchanges), sum(docs), sum(bytes), sum(gone IS NOT NULL), sum(rewrites) "
                      "FROM file GROUP BY domain").fetchall()
    st.close()
    return {r[0]: {"files": r[1], "exchanges": r[2], "docs": r[3], "mb": round((r[4] or 0) / 1e6), "gone": r[5], "rewrites": r[6]}
            for r in rows}
