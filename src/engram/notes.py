"""Notes (docs/technical.md, "Notes"): a working session saved as one file in the repo, in the owner's and the guide's
own words, each line naming its speaker and its line of the chat; and what a chat starts with from the latest one.

A chat is split into sessions at pauses (`[sessions] pause`, minutes). The filer's call for a session also says whether
it was a working session and, if so, gives its note; code checks every line against the message it cites (`check`) and
writes the note once, never again: a session is known by its first message's id, so a chat rewritten by a rewind or a
compaction keeps its sessions. A repo without `[notes]` sections, or whose pack has no `note` words, has no notes."""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engram import config, frontmatter, verbatim
from engram.paths import record_conf

GUIDE = "the guide"
NOT_SAID = "not said"
UNANSWERED = "guide unanswered"  # a section's `by` for what the guide offered that the owner didn't answer
STOPPED_ROOM = 2_500  # characters of "where you stopped" a chat starts with; past it, its last lines
SINCE_MAX = 20  # lines for what was saved since the note


@dataclass(frozen=True)
class Settings:
    folder: str
    sections: tuple[tuple[str, frozenset[str]], ...]  # each section's name and whose words go in it
    line_words: int  # past it, a line of the guide's is kept by its opening words, a question by its closing ones
    stopped: str
    words: str  # the pack's `note` words


def _conf(root: Path | None) -> dict:
    conf = (record_conf(root).get("notes") or {}) if root else {}
    return conf if conf.get("folder") and conf.get("sections") else {}


def folder(root: Path | None) -> str:
    """The repo's notes folder, or "" when it keeps none."""
    return str(_conf(root).get("folder", "")).strip("/")


def stopping(root: Path | None) -> str:
    """The section a chat starts with (`[notes] stopped`), or "" when the repo keeps no notes."""
    return str(_conf(root).get("stopped") or "")


def settings(root: Path, words: str) -> Settings | None:
    """The repo's note settings, or None: notes need a folder, sections and the pack's `note` words."""
    conf = _conf(root)
    if not conf or not words:
        return None
    secs = tuple((str(s["name"]), frozenset(s.get("by") or ())) for s in conf["sections"] if isinstance(s, dict) and s.get("name"))
    return Settings(str(conf["folder"]).strip("/"), secs, int(conf.get("line_words") or 40), str(conf.get("stopped") or ""), words)


def pause(root: Path | None) -> timedelta | None:
    """`[sessions] pause`: the silence that ends a session, and how long a chat waits before it's saved."""
    minutes = ((record_conf(root).get("sessions") or {}) if root else {}).get("pause")
    return timedelta(minutes=float(minutes)) if minutes else None


@dataclass
class Part:
    """One session of a chat: its exchanges, its first and last line of the chat file, and its first message's id."""
    exchanges: list
    first: int
    last: int
    start: str


def _ts(ts: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def parts(s, gap: timedelta) -> list[Part]:
    """The chat's sessions: a silence of `gap` or more after an exchange's last row starts the next."""
    out: list[Part] = []
    for x in s.exchanges:
        prev = out[-1].exchanges[-1] if out else None
        a, b = (_ts(prev.end or prev.ts), _ts(x.ts)) if prev else (None, None)
        if prev and not (a and b and b - a >= gap):
            out[-1].exchanges.append(x)
        else:
            out.append(Part([x], x.line, x.line, x.uuid or str(x.line)))
    for p, nxt in zip(out, out[1:] + [None]):
        p.last = nxt.first - 1 if nxt else max(s.lines, p.exchanges[-1].line)
    return out


def read(root: Path | None) -> list[dict]:
    """The repo's notes, oldest first: each its front matter, path in the repo and body."""
    conf = _conf(root)
    base = Path(root) / conf["folder"] if conf else None
    out = []
    for p in sorted(base.rglob("*.md")) if base and base.exists() else []:
        fm, body = frontmatter.split(p.read_text())
        if fm and fm.get("id"):
            out.append({"fm": fm, "path": p.relative_to(root).as_posix(), "body": body})
    return sorted(out, key=lambda n: (str(n["fm"].get("date", "")), n["fm"]["id"]))


def _lines(n: dict) -> range:
    try:
        a, b = (int(x) for x in n["fm"].get("lines") or ())
    except (TypeError, ValueError):
        return range(0)
    return range(a, b + 1)


def first_line(n: dict) -> int:
    return (_lines(n) or [0])[0]


def held(root: Path | None, stem: str) -> set[int]:
    """The lines of a chat its notes hold: what its summary leaves out, since the note stands for them."""
    return {l for n in read(root) if n["fm"].get("chat") == stem for l in _lines(n)}


def noted(root: Path, stem: str, part: Part) -> dict | None:
    """The note a session already has, found by its chat and first message."""
    return next((n for n in read(root) if n["fm"].get("chat") == stem and n["fm"].get("start") == part.start), None)


def refs(root: Path | None) -> dict[str, str]:
    """note id -> the ref its note is indexed as (a whole note is one record)."""
    return {n["fm"]["id"]: f"{n['path']}#" for n in read(root)}


def note_id(stem: str, part: Part) -> str:
    t = _ts(part.exchanges[0].ts)
    t = t.astimezone() if t else datetime.now().astimezone()
    return f"{t:%Y%m%d-%H%M%S}-note-{hashlib.sha256((stem + part.start).encode()).hexdigest()[:4]}"


def note_path(cfg: Settings, nid: str) -> str:
    return f"{cfg.folder}/{nid[:4]}/{nid[4:6]}/{nid}.md"


def recent(root: Path, n: int = 5) -> list[dict]:
    return read(root)[-n:]


def prompt(cfg: Settings, part: Part, near: list[dict]) -> str:
    """The pack's `note` words for one session, asked in the filer's call."""
    shown = "; ".join(f"{x['fm']['id']} ({x['fm'].get('date', '')}: {_opening(x['body'])})" for x in near) or "none"
    me = config.owner()
    whose = {"owner": f"{me}'s words", "guide": "Claude's words", UNANSWERED: f"what Claude offered that {me} didn't answer"}
    sections = "; ".join(f"“{name}” ({' and '.join(whose.get(b, b) for b in sorted(by, key=lambda b: b != 'owner'))})"
                         for name, by in cfg.sections)
    return config.voice(cfg.words).format(first=part.first, last=part.exchanges[-1].line, sections=sections, recent=shown)


def _opening(body: str) -> str:
    line = next((l for l in body.splitlines() if l.startswith("- ")), "")
    return " ".join(line.split())[:120]


@dataclass
class Line:
    at: int
    who: str  # owner or guide
    quote: str
    answering: str = field(default="", compare=False)


def _cut(text: str, words: int) -> str:
    w = text.split()
    return " ".join(w) if len(w) <= words else " ".join(w[:words]) + " …"


def _tail(text: str, words: int) -> str:
    w = text.split()
    return " ".join(w) if len(w) <= words else "… " + " ".join(w[-words:])


def _resolve(item: dict, part: Part, mine: dict[int, str], before: dict[int, str]) -> tuple[Line | None, str]:
    """The line an item cites, by whose words its quote is in at that point of the chat: the owner's message there or
    one of the guide's replies to it, whoever the item credits. None, and why, when it's in neither."""
    try:
        at = int(item.get("line"))
    except (TypeError, ValueError):
        return None, "a line with no line number"
    quote = " ".join(str(item.get("quote") or "").split())
    if not quote:
        return None, f"line {at} has no words"
    x = next((x for x in reversed(part.exchanges) if x.line <= at), None) if part.first <= at <= part.last else None
    if x is None:
        return None, f"line {at} isn't in this session"
    def owner():
        if x.line in mine and verbatim.found(quote, mine[x.line]):
            asked = before.get(x.line, "").strip()
            return Line(x.line, "owner", quote, asked if asked.endswith("?") else "")
    def guide():
        for ln, r in sorted(zip(x.reply_lines, x.replies), key=lambda g: g[0] != at):
            if verbatim.found(quote, r):
                return Line(ln, "guide", quote)
    for find in (guide, owner) if item.get("by") == "guide" else (owner, guide):
        if got := find():
            return got, ""
    return None, f"line {at}: “{_cut(quote, 12)}” isn't in {config.owner()}'s words there, nor the guide's"


def check(reply: dict, part: Part, cfg: Settings, mine: dict[int, str], before: dict[int, str]
          ) -> tuple[dict[str, list[Line]], list[tuple[int, str]], tuple[int | None, str] | None]:
    """A note's sections as code keeps them, the lines left out (line, why), and why the whole note is refused, if it
    is: a line that's in nobody's words where it cites, or no words of the owner's at all. A line of the guide's in a
    section only the owner's words go in is left out, whoever the reply credits, as is one in a section of what he
    didn't answer when a message of his in the session comes after it; a section left empty reads "not said"."""
    given = (reply.get("sections") if isinstance(reply, dict) else None) or {}
    given = given if isinstance(given, dict) else {}
    out, left = {}, []
    for name, by in cfg.sections:
        got: list[Line] = []
        for item in given.get(name) or []:
            if not isinstance(item, dict):
                continue
            line, why = _resolve(item, part, mine, before)
            if line is None:
                return {}, left, (item.get("line"), why)
            later = [l for l in mine if line.at < l <= part.last] if line.who == "guide" and "guide" not in by else []
            if not (("owner" in by) if line.who == "owner" else bool({"guide", UNANSWERED} & by)):
                left.append((line.at, f"{config.owner() if line.who == 'owner' else GUIDE}'s words don't go under “{name}”"))
            elif later:  # what the guide offered goes there only while he hasn't answered it
                left.append((line.at, f"the guide's line was answered at line {min(later)}, so it isn't under “{name}”"))
            elif line not in got:
                got.append(line)
        out[name] = got
    if not any(l.who == "owner" for ls in out.values() for l in ls):
        return {}, left, (None, f"none of {config.owner()}'s words in it")
    return out, left, None


def render(fm: dict, sections: dict[str, list[Line]], cfg: Settings) -> str:
    from engram import store
    me, body = config.owner(), []
    for name, _ in cfg.sections:
        body.append(f"## {name}")
        for l in sections.get(name) or []:
            if l.who == "guide":
                body.append(f"- {GUIDE} (line {l.at}): “{_cut(l.quote, cfg.line_words)}”")
            else:
                asked = f", answering “{_tail(l.answering, cfg.line_words)}”" if l.answering else ""
                body.append(f"- {me} (line {l.at}){asked}: “{l.quote}”")  # his words are his, of any length
        if not sections.get(name):
            body.append(NOT_SAID)
        body.append("")
    return store.render_event(fm, "\n".join(body))


SPOKEN = re.compile(r"^- (?P<who>[^“(:\n]+?)(?: \(line \d+\))?(?:, answering “.*?”)?: “(?P<quote>.*)”\s*$", re.M)


CITED = re.compile(r"^- (?P<who>[^“(:\n]+?) \(line (?P<at>\d+)\)(?:, answering “.*?”)?: “(?P<quote>.*)”\s*$", re.M)


def cited(n: dict) -> list[Line]:
    """The lines a stored note cites, read back as `render` wrote them."""
    return [Line(int(m["at"]), "owner" if m["who"] == config.owner() else "guide", m["quote"]) for m in CITED.finditer(n["body"])]


def spoken(body: str) -> list[tuple[str, str]]:
    """(speaker, words) for each line that names its speaker, as `render` writes a note's and the filer an entry's
    quote (`- <who>[ (line N)][, answering “<question>”]: “<words>”`): the question a reply answers is the guide's, never
    his, and a headline is nobody's words."""
    return [(m["who"], m["quote"]) for m in SPOKEN.finditer(body)]


def _section(body: str, name: str) -> list[str]:
    out, inside = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == name
        elif inside and line.strip():
            out.append(line)
    return out


def _themes(fm: dict) -> str:
    about = fm.get("about") or []
    return ", ".join(a.split("/", 1)[-1].replace("-", " ") for a in (about if isinstance(about, list) else [about]))


def stopped(root: Path, events: list) -> str:
    """What a chat starts with in a repo with notes: the latest note's "where you stopped" lines with its date and
    themes, its last lines when they're too long, then one line for each entry saved since that he didn't say before the
    note's day (`reported`, where it's kept: a row typed or a chat filed late is saved after the day it was said). Empty
    with no notes."""
    name, notes = stopping(root), read(root)
    if not name or not notes:
        return ""
    last = notes[-1]
    fm, lines = last["fm"], _section(last["body"], name)
    themes = _themes(fm)
    out = [f"Where the last session stopped ({fm.get('date', '')}{'; ' + themes if themes else ''}), its note {last['path']}:"]
    if sum(len(l) + 1 for l in lines) > STOPPED_ROOM:
        kept = []
        for l in reversed(lines):
            if sum(len(k) + 1 for k in kept) + len(l) > STOPPED_ROOM:
                break
            kept.insert(0, l)
        lines = [f"… the rest is in {last['path']}", *kept]
    out += lines
    since = [e for e in events if e.kind != "link" and e.fm.get("note") != fm["id"]
             and (t := _ts(e.fm.get("recorded"))) and (n := _ts(fm.get("recorded"))) and t >= n
             and not (e.fm.get("reported") and str(e.fm["reported"]) < str(fm.get("date", "")))]
    since.sort(key=lambda e: str(e.fm.get("recorded")))
    if since:
        out.append("Saved since:")
        out += [f"- {e.date} {e.fm.get('title', '')}" for e in since[:SINCE_MAX]]
        if len(since) > SINCE_MAX:
            out.append(f"- and {len(since) - SINCE_MAX} more: `engram now`")
    return "\n".join(out)
