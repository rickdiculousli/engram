"""A fact and its corrections as one unit (the owner; .engram/README.md, "A fact comes with its corrections").

From a record, its revision chain: up what it revises or supersedes, down what revises or supersedes it, each
recursively, never down an ancestor's other branches; plus its own and its current version's direct disagreements. The unit counts as one result. Its current version (the newest one not superseded, reached from the
record by following its corrections forward) comes in full; every other version gets one line: date, who said it, what
changed (the link's note) and its id. Versions that disagree sit side by side and none is marked as the answer. Six
versions are shown, then a line "N more versions".

Ordinary change over time isn't a correction: a medication's dose step is the next entry on the thing's chain in
`engram now`, never a link here. A unit holding an entry on such a chain carries one `now:` line instead.

As of a date (a question about the past, `--as-of`, or a hidden session in the evals), the unit centres on the version
current then; later versions show as "changed later, <date>", or not at all when the record is read as it stood."""
import os
import re
from dataclasses import dataclass, field

from engram import labels
from engram.sources.events import ID

CHAIN = ("revises", "supersedes", "disagrees")
CAP = 6  # versions shown, the current one included
NOTE = 50  # characters of a link's note on a version's line (docs/search.md, "A fact and its corrections")


def corrected(st) -> set[str]:
    """The entries something revises or supersedes, by id; an entry not among them heads its chain (its current
    version)."""
    return {norm(str(e.fm.get("to"))) for e in st.events(kind="link") if e.fm.get("rel") in CHAIN[:2]}


def norm(ref: str) -> str:
    """The record a ref is: an entry's section is the entry."""
    m = ID.match(ref)
    return m.group(0) if m else ref


@dataclass
class Graph:
    edges: dict[str, list[tuple[str, str, str, str]]] = field(default_factory=dict)  # ref -> (other, rel, "newer"|"older"|"peer", note)

    def add(self, a: str, b: str, rel: str, note: str):
        a, b = norm(a), norm(b)
        if a == b:
            return
        self.edges.setdefault(a, []).append((b, rel, "peer" if rel == "disagrees" else "older", note))
        self.edges.setdefault(b, []).append((a, rel, "peer" if rel == "disagrees" else "newer", note))


def graph(db) -> Graph:
    g = Graph()
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'link'").fetchone():
        return g
    for a, b, rel, note in db.execute(f"SELECT from_ref, to_ref, rel, note FROM link WHERE rel IN {CHAIN}"):
        g.add(a, b, rel, note or "")
    return g


def members(g: Graph, start: str) -> list[str]:
    """The revision chain through `start`, nearest first, no repeats: a line through time, not a component of the
    graph. Up: what it revises or supersedes, recursively. Down: what revises or supersedes it, recursively, every
    branch from it. Never down from an ancestor into its other branches: siblings correcting the same target are
    separate chains that share it. Plus its direct disagreements only."""
    start = norm(start)
    order, seen = [start], {start}
    for way in ("older", "newer"):
        todo = [start]
        while todo:
            nxt = []
            for x in todo:
                for y, rel, w, _ in g.edges.get(x, ()):
                    if w == way and y not in seen:
                        seen.add(y)
                        order.append(y)
                        nxt.append(y)
            todo = nxt
    return order + peers_of(g, start, seen)


def peers_of(g: Graph, ref: str, seen: set[str]) -> list[str]:
    """A record's direct disagreements not already in `seen` (added to it), never through another's."""
    out = []
    for y, rel, w, _ in g.edges.get(ref, ()):
        if w == "peer" and y not in seen:
            seen.add(y)
            out.append(y)
    return out


def _doc(db, ref: str):
    return db.execute("SELECT title, date, date_key, author, nid, source, ref FROM doc WHERE ref = ? OR parent = ? "
                      "ORDER BY rowid LIMIT 1", (ref, ref)).fetchone()


def said_on(ref: str, date_key: str | None) -> str | None:
    """When a version was said, YYYY-MM-DD: an entry when it was written (its id), a document by its date."""
    if m := ID.match(ref):
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if date_key and len(date_key) >= 8 and date_key[:8].isdigit():
        return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    if date_key and re.match(r"\d{4}-\d\d-\d\d", date_key):
        return date_key[:10]
    return None


def session_day(db) -> str | None:
    """The day of the session ENGRAM_EXCLUDE_SOURCES hides, from its summary's rows."""
    for src in filter(None, os.environ.get("ENGRAM_EXCLUDE_SOURCES", "").split(",")):
        if src.startswith("sessions:"):
            row = db.execute("SELECT min(date_key) FROM doc WHERE source LIKE ?", (src + "%",)).fetchone()
            if row and row[0]:
                return said_on("", row[0])
    return None


@dataclass
class Unit:
    hit: str
    centre: str
    members: list[str]  # every version in the unit, the centre first (not those hidden)
    lines: list[dict]  # the other versions shown, one line each: ref, nid, date, who, note, later, side
    more: int = 0  # versions past the cap
    disagree: bool = False  # the centre has a version beside it that disagrees: none is the answer
    hidden: list[str] = field(default_factory=list)  # later versions left out, reading as it stood
    now: str = ""  # where the thing stands, for an entry on a `now` chain

    @property
    def shown(self) -> list[str]:
        return [self.centre] + [l["ref"] for l in self.lines]

    @property
    def size(self) -> int:
        return len(self.members)


def build(db, g: Graph, hit: str, when: str | None = None, hide: bool = False, known: dict | None = None,
          excluded=None, now_of=None) -> Unit | None:
    """The unit a record belongs to, or None when it has no other version and no `now` line. `excluded(source, ref)`
    drops versions the caller can't see; `now_of(ref)` gives the `now:` line for an entry on a thing's chain, "" off
    any chain, and None for the chain's latest entry."""
    hit = norm(hit)
    all_ = members(g, hit)
    info = {m: _doc(db, m) for m in all_}
    ms = [m for m in all_ if info[m] is not None and not (excluded and excluded(info[m][5], m))]
    if hit not in ms:
        ms.insert(0, hit)
    day = {m: said_on(m, info[m][2] if info.get(m) else None) for m in ms}
    later = {m for m in ms if when and day[m] and day[m] > when}
    vis = [m for m in ms if m not in later]
    newest = lambda xs: max(xs, key=lambda m: (day[m] or "", m))

    def reach(start: str, way: str, pool: set[str]) -> set[str]:
        out, todo = set(), [start]
        while todo:
            x = todo.pop()
            for y, rel, w, _ in g.edges.get(x, ()):
                if w == way and y in pool and y not in out:
                    out.add(y)
                    todo.append(y)
        return out

    def superseded(pool: set[str]) -> set[str]:
        return {y for x in pool for y, rel, w, _ in g.edges.get(x, ()) if w == "older" and y in pool}
    pool = set(vis)
    current = lambda pool: (reach(hit, "newer", pool) | {hit}) - superseded(pool)
    if hit in pool:  # the hit's own current version: its corrections followed forward, the newest not corrected again
        cand = current(pool)
    else:  # said after the date: the version it corrects that stood then
        cand = reach(hit, "older", pool) - superseded(pool)
    if not cand and not hide:  # every version was said after the date: none stood then, so centre as with no date
        pool = set(ms)
        cand = current(pool)
    centre = newest(cand) if cand else hit
    for y in peers_of(g, centre, set(ms)):  # the current version's own disagreements, beside it
        if (d := _doc(db, y)) is not None and not (excluded and excluded(d[5], y)):
            info[y], day[y] = d, said_on(y, d[2])
            ms.append(y)
            if when and day[y] and day[y] > when:
                later.add(y)
    hidden = [m for m in ms if m in later and m != centre] if hide else []  # read as it stood: not said yet
    inside = set(ms) - set(hidden)
    old = superseded(pool)
    peers = {y for y, rel, w, _ in g.edges.get(centre, ()) if w == "peer" and y in inside and y not in old}
    others = [m for m in ms if m != centre and m not in hidden]
    near, via = paths(g, centre, inside)
    others.sort(key=lambda m: (m != hit, m not in peers, near.get(m, 99), -(int((day[m] or "0").replace("-", "")))))
    lines = []
    for m in others[:CAP - 1]:
        title, date, _, author, nid, _, _ = info[m] if info.get(m) else (m, None, None, "", m, "", m)
        lines.append({"ref": m, "nid": nid, "date": date or day[m] or "", "who": labels.who(author or "", known or {}),
                      "note": _note(via.get(m), title), "later": m in later, "side": m in peers, "said": day[m] or ""})
    standing = ""
    if now_of and not hide:  # none when a version here is its thing's latest entry: then this is where it stands
        got = [now_of(m) for m in dict.fromkeys([centre, hit]) if m not in later]  # the fact's own thing, not a far version's
        standing = "" if None in got else next((x for x in got if x), "")
    if len(ms) < 2 and not standing:
        return None
    return Unit(hit, centre, [centre] + others, lines, max(0, len(others) - (CAP - 1)), bool(peers), hidden, standing)


def paths(g: Graph, centre: str, inside: set[str]) -> tuple[dict[str, int], dict[str, tuple]]:
    """(each version's distance from the centre, the link that reaches it on the way out from the centre: (rel, whether
    the version is that link's "older" end, its "newer" one or a "peer", note))."""
    near, via, todo = {centre: 0}, {}, [centre]
    while todo:
        nxt = []
        for x in todo:
            for y, rel, w, note in g.edges.get(x, ()):
                if y in inside and y not in near:
                    near[y] = near[x] + 1
                    via[y] = (rel, w, note)  # w: y is the older end, the newer one, or a peer
                    nxt.append(y)
        todo = nxt
    return near, via


def _note(via: tuple | None, title: str) -> str:
    """What a version changed, from the link that ties it to the chain on the way from the current version: what it
    corrects (the newer end), that it was corrected (the older end), or that it disagrees; else its own headline."""
    if via and via[2]:
        rel, way, note = via
        return f"{ {'newer': rel, 'older': 'corrected', 'peer': 'disagrees'}[way]}: {_cut(note)}"  # newer: it revises
    return _cut(title.split(" › ")[-1])


def _cut(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= NOTE else text[:NOTE].rsplit(" ", 1)[0] + " …"


def line(l: dict) -> str:
    """One version on one line: date, who, what, id; "changed later, <the day it was said>" first when that came after
    the date the record is read as of."""
    bits = [b for b in (f"changed later, {l['said']}" if l["later"] else l["date"], l["who"]) if b]
    lead = " ".join(bits)
    return f"{lead}: {l['note']} [{l['nid']}]" if lead else f"{l['note']} [{l['nid']}]"


def text_lines(u: Unit) -> list[str]:
    """The unit's lines under its current version, as search and the timeline print them."""
    out = []
    if u.lines or u.more:
        head = "versions that disagree, side by side (none is the answer)" if u.disagree else "other versions (current above)"
        out.append(f"{head}:")
        out += [("beside it: " if l["side"] else "") + line(l) for l in u.lines]
        if u.more:
            out.append(f"{u.more} more versions")
    if u.now:
        out.append(f"now: {u.now}")
    return out
