"""Threads: the `about` values a record's entries sit on, read with the dated links that change which thread an entry
is on. A story is one in any record; in a record whose `[threads] create` lists kinds (theme, person, event), the
filer may also start one of those kinds, named only with the owner's words (docs/technical.md, "Threads").

A thread of a created kind is an `about` value like any other, `<kind>/<its first name, slugged>`, and a `thread`
entry gives each of its names, in the owner's words: two names for one person are two such entries on one id, and two
people he calls by one word are two ids that word finds. What changes a thread is a dated link, never an edit:
`joined-into` puts two threads' entries on both, `split-into` puts what the old one held up to that day on the new
one too, `ended` closes one, and `placed-on` puts an entry on a thread, taking it off another when it names one (a
correction that moves it). Only a conversation makes a join, a split or an end; the filer never does."""
import re

from engram import dates, verbatim

KIND = "thread"  # the entry that names a thread
JOIN, SPLIT, END, PLACE = "joined-into", "split-into", "ended", "placed-on"
PAST = "event"  # the kind that is a past event: it has happened, and a rough age dates it
THEME = "theme"  # the kind that is what he keeps coming back to: it gathers the earlier tellings, named in words they share
WORD = re.compile(r"[\w']+")


def creatable(conf: dict) -> tuple[str, ...]:
    """The kinds of thread the record's filer may create; none in a record that doesn't say."""
    return tuple((conf.get("threads") or {}).get("create") or ())


def tid(kind: str, name: str) -> str:
    return f"{kind}/" + re.sub(r"[^\w]+", "-", name.lower()).strip("-")


def shares(name: str, told: list[str]) -> bool:
    """Whether a name has a word of substance (four letters or more, or a number) in what was told before."""
    said = {w for t in told for w in WORD.findall(verbatim.norm(t))}
    return any(w in said for w in WORD.findall(verbatim.norm(name)) if len(w) >= 4 or any(c.isdigit() for c in w))


def key(about: str) -> str:
    """A thread's name in the index: a story by its slug, as it always was; any other by its id."""
    return about.split("/", 1)[1] if about.startswith("story/") else about


def _day(e) -> str:
    d = str(e.fm.get("date") or "")
    return d if dates.key(d) and d != "not-sure" else str(e.fm.get("recorded") or "")[:10]


class Threads:
    """A record's threads: what each is called, and which an entry is on once its record's links are read."""

    def __init__(self, events, made: tuple[str, ...]):
        self.made = made
        self.prefixes = ("story", *made)
        self.names: dict[str, list[str]] = {}  # a created thread -> its names, first given first
        self.joined: dict[str, set[str]] = {}
        self.splits: list[tuple[str, str, str]] = []  # (from, into, day)
        self.ended: dict[str, str] = {}
        self.placed: dict[str, list[tuple[str, str]]] = {}  # entry -> (onto, off), in the order filed
        for e in sorted(events, key=lambda e: str(e.fm.get("recorded") or "")):
            if e.kind == KIND and e.fm.get("name"):
                for a in e.about:
                    if self.created(a):
                        names = self.names.setdefault(a, [])
                        if str(e.fm["name"]) not in names:
                            names.append(str(e.fm["name"]))
            elif e.kind == "link":
                rel, a, b = e.fm.get("rel"), str(e.fm.get("from") or ""), str(e.fm.get("to") or "")
                if rel == JOIN and self.thread(a) and self.thread(b):
                    self.joined.setdefault(a, set()).add(b)
                    self.joined.setdefault(b, set()).add(a)
                elif rel == SPLIT and self.thread(a) and self.thread(b):
                    self.splits.append((a, b, _day(e)))
                elif rel == END and self.thread(a):
                    self.ended[a] = _day(e)
                elif rel == PLACE and self.thread(b):
                    self.placed.setdefault(a, []).append((b, str(e.fm.get("off") or "")))
        for e in events:  # a thread written before threads had names goes by its slug
            for a in e.about:
                if self.created(a) and a not in self.names:
                    self.names[a] = [a.split("/", 1)[1].replace("-", " ")]

    def thread(self, about: str) -> bool:
        return about.split("/", 1)[0] in self.prefixes and "/" in about

    def created(self, about: str) -> bool:
        return about.split("/", 1)[0] in self.made and "/" in about

    def named(self, name: str) -> list[str]:
        """The created threads a name is one of, or that it is the id of."""
        n = verbatim.norm(name)
        return [t for t, names in self.names.items() if t == name or any(verbatim.norm(x) == n for x in names)]

    def on(self, eid: str, about: list[str], day: str) -> list[str]:
        """The threads an entry (or a note) is on: its own, as later placings moved it, every thread joined to one, and
        the threads split from one after its day."""
        out = [a for a in about if self.thread(a)]
        for onto, off in self.placed.get(eid, []):
            out = [a for a in out if a != off] + ([onto] if onto not in out else [])
        todo = list(out)
        while todo:
            a = todo.pop()
            more = list(self.joined.get(a, ()))
            more += [b for f, b, d in self.splits if f == a and (not day or not d or day[:10] <= d)]
            for b in more:
                if b not in out:
                    out.append(b)
                    todo.append(b)
        return out

    def of(self, e) -> list[str]:
        return self.on(e.id, e.about, _day(e))
