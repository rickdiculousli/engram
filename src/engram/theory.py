"""The theory graph (.engram/README.md, "How answers are built"): how things work, the second of the two graphs. Its
things are thread files (a condition, a loop, a state a loop passes through), Discoveries, pending patterns and
questions; its links are the theory family: each loop step `feeds` the next, and each join keeps its kind (shared
cause, amplifier…), strength, mechanism, who said it and since when. Loops are allowed. A thing's status is its latest
status event.

A thread file's front matter names it: `id` (`loop/2b`), `kind`, `short` (the label a path is drawn with), `stories`
(the stories it sits on, so a question about them lights it) and `say` (words that name it in a question).

A revision (`engram theory change`, engram.theorychange) never edits a link: a step or join it retires gets a status
event on `link/<its id>` saying "retired", with what replaced it and why. The graph leaves retired links out, and
`load(repo, asof=...)` gives the graph as it stood on a day, so "what did we think back then" still works.

A record may add its own kinds (`[theory.kinds.<kind>]` in its engram.toml): each a folder of thread files, beside the
built-in ones, and for a kind whose change is gradual (an insight) the `stages` it moves through, a second label kept
apart from its status, and `needs_note` (one is added only from a session that has a note). A thing the guide
suggested (`by: claude-suggestion`, its words in `quote`) is shown as the guide's wherever it's printed (`who`)."""
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from engram import config, frontmatter
from engram.paths import record_conf
from engram.store import Store

SUGGESTION = "claude-suggestion"  # who a guide's suggestion is by, as an entry the guide's words hold is
SUGGESTED = "the guide's suggestion"  # how one is labelled wherever it's shown
GONE = ("ruled out", "replaced")  # statuses that take a thing out of the picture a chat starts with


@dataclass
class Thing:
    id: str
    kind: str
    short: str
    file: str = ""
    title: str = ""
    stories: list[str] = field(default_factory=list)
    say: list[str] = field(default_factory=list)
    since: str = ""
    by: str = ""
    quote: str = ""  # a suggestion's: the guide's words


@dataclass
class Kind:
    """One of a record's own theory kinds: where its things live, and for a change made gradually, the stages it
    moves through and whether one must come from a session's note."""
    folder: str
    stages: list[str] = field(default_factory=list)
    needs_note: bool = False


def kinds(repo: Path) -> dict[str, Kind]:
    """The record's own theory kinds, from `[theory.kinds.<kind>]`; none, the theory is the built-in one."""
    conf = (record_conf(repo).get("theory") or {}).get("kinds") or {}
    return {k: Kind(str(v["folder"]).strip("/"), [str(x) for x in v.get("stages") or []], bool(v.get("needs_note")))
            for k, v in conf.items() if isinstance(v, dict) and v.get("folder")}


@dataclass
class Edge:
    id: str
    a: str
    b: str
    rel: str
    note: str
    strength: str = ""
    since: str = ""
    by: str = ""
    loop: str = ""
    step: int = 0
    entry: str = ""


STATUSES = ["proposed", "provisional", "confirmed", "ruled out", "replaced"]
STRENGTHS = ["high", "medium", "low", "open"]
RETIRED = "retired"


@dataclass
class Retired:
    edge: Edge
    date: str
    replaced_by: str
    why: str
    entry: str


@dataclass
class Graph:
    things: dict[str, Thing]
    edges: list[Edge]
    status: dict[str, tuple[str, str, str]]  # thing -> (status, date, event id)
    retired: list[Retired] = field(default_factory=list)
    kinds: dict[str, Kind] = field(default_factory=dict)  # the record's own kinds
    stage: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # thing -> (stage, date, event id), apart from status
    word: dict[str, dict] = field(default_factory=dict)  # thing -> the front matter of the event its status is from

    def label(self, thing: str) -> str:
        t = self.things.get(thing)
        return t.short if t else thing.split("/", 1)[-1]

    def loops(self) -> list[str]:
        return [t for t, x in self.things.items() if x.kind == "loop"]

    def path(self, loop: str) -> list[str]:
        """The loop's members in order, back to where it starts: from the first step's start, each next step is the one
        leaving where the last arrived (a step inserted later keeps its neighbours' numbers)."""
        left = sorted((e for e in self.edges if e.loop == loop), key=lambda e: e.step)
        if not left:
            return []
        out = [left[0].a]
        while left:
            nxt = next((e for e in left if e.a == out[-1]), None)
            if nxt is None:
                break
            left.remove(nxt)
            out.append(nxt.b)
        return out

    def walks(self, loop: str) -> bool:
        """Every step of the loop is walked once, as one path."""
        return len(self.path(loop)) - 1 == sum(1 for e in self.edges if e.loop == loop) > 0

    def closes(self, loop: str) -> bool:
        """The loop is one path that ends where it began (an open chain stays one)."""
        p = self.path(loop)
        return self.walks(loop) and p[0] == p[-1]

    def draw(self, loop: str) -> str:
        return " → ".join(self.label(x) for x in self.path(loop))

    def joins(self) -> list[Edge]:
        return [e for e in self.edges if e.rel != "feeds"]

    def stories_of(self, thing: str) -> set[str]:
        t = self.things.get(thing)
        return set(t.stories) if t else set()

    def touched(self, stories: dict[str, float], named: set[str] = frozenset(), share: float = 0.6) -> list[str]:
        """The loops a question touches: how closely what the question is about matches what each loop covers. The
        question weighs each story (1 for one it names, or whose member it names, else the story's share of the
        search's vote); a loop covers the stories its members sit on; a story few loops cover counts for more (tics
        are in every loop). The match is the cosine of the two, so a big loop doesn't win just by covering more. A loop
        shows when it matches at least `share` as well as the best; one the question names always shows. Unrelated
        loops stay out."""
        cover = {l: {s for m in self.path(l) for s in self.stories_of(m)} for l in self.loops()}
        if not cover:
            return []
        rare = {s: math.log(1 + len(cover) / sum(s in c for c in cover.values())) for s in set().union(*cover.values())}
        q = dict(stories)
        for m in named:
            for s in self.stories_of(m):
                q[s] = 1.0
        qn = math.sqrt(sum((v * rare.get(s, 1.0)) ** 2 for s, v in q.items())) or 1.0

        def match(l: str) -> float:
            ln = math.sqrt(sum(rare[s] ** 2 for s in cover[l])) or 1.0
            return sum(q.get(s, 0.0) * rare[s] ** 2 for s in cover[l]) / (qn * ln)
        scores = {l: match(l) for l in self.loops()}
        best = max(scores.values(), default=0)
        shown = [l for l in self.loops() if best and scores[l] >= share * best]
        shown += [l for l in self.loops() if l in named and l not in shown]
        return shown


def load(repo: Path, asof: str | None = None) -> Graph:
    """The graph as the record holds it; with `asof` (YYYY-MM-DD), as it stood that day: things, links and statuses
    from later are left out, and a link retired later is still in."""
    st = Store(repo)

    def later(day: str) -> bool:
        return bool(asof and day and str(day)[:10] > asof)
    things: dict[str, Thing] = {}
    own = kinds(repo)
    for folder, kind in [("theory", ""), *((k.folder, name) for name, k in own.items())]:
        for p in sorted((repo / folder).glob("*.md")) if (repo / folder).exists() else []:
            fm, body = frontmatter.split(p.read_text())
            if not fm or not fm.get("id"):
                continue
            head = next((l.lstrip("# ").strip() for l in body.splitlines() if l.startswith("# ")), fm["id"])
            if later(str(fm.get("since", ""))):
                continue
            things[fm["id"]] = Thing(fm["id"], fm.get("kind") or kind, str(fm.get("short") or head), p.relative_to(repo).as_posix(),
                                     head, [str(s) for s in fm.get("stories") or []], [str(s) for s in fm.get("say") or []],
                                     str(fm.get("since", "")), str(fm.get("by", "")), str(fm.get("quote") or ""))
    for p in sorted((repo / "evidence").glob("D[0-9]*-*.md")) if (repo / "evidence").exists() else []:
        fm, _ = frontmatter.split(p.read_text())
        did = str((fm or {}).get("id") or p.name.split("-", 1)[0])
        things[f"discovery/{did}"] = Thing(f"discovery/{did}", "discovery", did, p.relative_to(repo).as_posix(),
                                           str((fm or {}).get("title", did)))
    for folder, kind in (("evidence/staging", "pattern"), ("questions", "question")):
        for p in sorted((repo / folder).glob("*.md")) if (repo / folder).exists() else []:
            fm, body = frontmatter.split(p.read_text())
            head = next((l.lstrip("# ").strip() for l in (body or p.read_text()).splitlines() if l.startswith("# ")), p.stem)
            things[f"{kind}/{p.stem}"] = Thing(f"{kind}/{p.stem}", kind, p.stem, p.relative_to(repo).as_posix(), head)
    edges, status, retired, stage, word = [], {}, {}, {}, {}
    for e in st.events():
        if e.kind == "link" and e.fm.get("family") == "theory" and not later(str(e.fm.get("since") or e.date)):
            edges.append(Edge(e.id, e.fm.get("from", ""), e.fm.get("to", ""), e.fm.get("rel", ""), e.body.strip(),
                              str(e.fm.get("strength", "")), str(e.fm.get("since", "")), str(e.fm.get("by", "")),
                              str(e.fm.get("loop", "")), int(e.fm.get("step") or 0), str(e.fm.get("entry", ""))))
    # a guide's suggestion is where its thing's history starts: in the same second, it comes before what's said of it
    for e in sorted(st.events(kind="status"), key=lambda e: (str(e.fm.get("recorded", "")), e.fm.get("by") != SUGGESTION)):
        if later(str(e.date)):
            continue
        for a in e.about:
            if a.startswith("link/") and e.fm.get("status") == RETIRED:
                retired[a[5:]] = e
            elif "/" in a and not a.startswith(("story/", "series/")):
                if "status" in e.fm or not e.fm.get("stage"):  # a stage alone leaves the status as it was
                    status[a] = (str(e.fm.get("status", "")), str(e.date), e.id)
                    word[a] = e.fm
                if e.fm.get("stage"):
                    stage[a] = (str(e.fm["stage"]), str(e.date), e.id)
    gone = [Retired(x, str(retired[x.id].date), str(retired[x.id].fm.get("replaced_by", "")), str(retired[x.id].fm.get("why", "")),
                    retired[x.id].id) for x in edges if x.id in retired]
    return Graph(things, [x for x in edges if x.id not in retired], status, gone, own, stage, word)


def file_for(g: Graph, kind: str, tid: str) -> str:
    """Where a new thing's file goes: its kind's folder, for a kind of the record's own, else theory/<kind>-<name>.md."""
    name = re.sub(r"[^\w]+", "-", tid.split("/", 1)[-1].lower()).strip("-")
    return f"{g.kinds[kind].folder}/{name}.md" if kind in g.kinds else f"theory/{kind}-{name}.md"


def unanswered(g: Graph, thing: str) -> bool:
    """A guide's suggestion the owner hasn't said anything of yet: its status is still the guide's own."""
    t = g.things.get(thing)
    return bool(t) and t.by == SUGGESTION and (g.word.get(thing) or {}).get("by", SUGGESTION) == SUGGESTION


def who(g: Graph, thing: str) -> str:
    """Whose a thing is, for a guide's suggestion: the guide's words while it's proposed, and once the owner has said
    something of it, his words beside them ("raised by the guide, adopted by <owner>"). Empty for any other thing."""
    t = g.things.get(thing)
    if not t or t.by != SUGGESTION:
        return ""
    fm, status = g.word.get(thing) or {}, g.status.get(thing, ("",))[0]
    if unanswered(g, thing):
        return f"{SUGGESTED}: “{t.quote}”" if t.quote else SUGGESTED
    said = f"“{' '.join(str(fm.get('said') or '').split())}”"
    if fm.get("answering"):
        said = f"asked “{' '.join(str(fm['answering']).split())}”, {said}"
    verb = "adopted" if status in ("provisional", "confirmed") else status
    return f"raised by the guide, {verb} by {config.owner()}: {said}"


def node_doc(g: Graph, thing: str, refs: list[str]) -> str | None:
    """The indexed section a thing's file opens with."""
    t = g.things.get(thing)
    if not t or not t.file:
        return None
    mine = [r for r in refs if r.split("#", 1)[0] == t.file]
    return next((r for r in mine if r.split("#", 1)[1]), mine[0] if mine else None)  # its heading, not the front matter


def text(g: Graph) -> str:
    """The whole graph in one read: conditions, loops with their paths, joins, and every theory's status."""
    out = ["conditions: " + "; ".join(f"{t.id.split('/')[1]} {t.title.split(' — ', 1)[-1]}" for t in g.things.values() if t.kind == "node")]
    out.append("")
    out.append("loop\tpath\tsince")
    for l in g.loops():
        out.append(f"{g.things[l].title}\t{g.draw(l)}\t{g.things[l].since}")
    out.append("")
    out.append("join\tkind\tstrength\tsince\tby\tmechanism")
    for e in g.joins():
        out.append(f"{g.label(e.a)} → {g.label(e.b)}\t{e.rel}\t{e.strength}\t{e.since}\t"
                   f"{SUGGESTED if e.by == SUGGESTION else e.by}\t{e.note}")
    out.append("")
    out.append("theory\tstatus\tsince\twhat")
    for t in g.things.values():
        if t.kind in ("discovery", "pattern"):
            s, d, _ = g.status.get(t.id, ("", "", ""))
            out.append(f"{t.short}\t{s}\t{d}\t{t.title}")
    if g.kinds:  # the record's own kinds: each thing's status, its stage where its kind has them, and whose it is
        out.append("")
        out.append("item\tkind\tstatus\tstage\tsince\twho")
        for t in g.things.values():
            if t.kind in g.kinds:
                out.append(f"{t.short}\t{t.kind}\t{g.status.get(t.id, ('',))[0]}\t{g.stage.get(t.id, ('',))[0]}\t{t.since}\t"
                           f"{who(g, t.id) or t.by}")
    if g.retired:
        out.append("")
        out.append("retired\twhen\treplaced by\twhy")
        for r in g.retired:
            where = f" ({g.things[r.edge.loop].title.split(' — ')[0]})" if r.edge.loop in g.things else ""
            out.append(f"{g.label(r.edge.a)} → {g.label(r.edge.b)}{where}\t{r.date}\t{r.replaced_by}\t{r.why}")
    qs = [(t, g.status.get(t.id, ("", "", ""))) for t in g.things.values() if t.kind == "question"]
    out.append("")
    out.append(f"questions: {sum(1 for _, s in qs if s[0] == 'open')} open, " + ", ".join(
        f"{n} {k}" for k, n in sorted({s[0]: sum(1 for _, x in qs if x[0] == s[0]) for _, s in qs}.items()) if k != "open"))
    for t, s in qs:
        if s[0] == "open":
            out.append(f"  open: {t.title}")
    return "\n".join(out)


def files_then(repo: Path, g: Graph, when: str) -> str:
    """Where each theory thing's text stood on a date, from git: its own file as committed then, or, for a file begun
    later (the clean house split architecture.md into theory files), the old home it moved from. `engram show <ref>
    --as-of <date>` reads the text."""
    from engram import asof
    out = [f"\nas it stood in git on {when} (engram show <ref> --as-of {when} reads it)", "thing\tthen"]
    for t in g.things.values():
        if not t.file:
            continue
        days = asof.revised(repo, t.file)
        if days and days[0] <= when:
            later = [d for d in days if d > when]
            out.append(f"{t.short}\t{t.file}: " + (f"revised since: {', '.join(later)}" if later else "as now"))
        elif home := asof.then_home(repo, t.file, when):
            out.append(f"{t.short}\tin {home[0]} (committed {home[1]}); its own file began {days[0] if days else 'later'}")
        else:
            out.append(f"{t.short}\tnot in git yet")
    return "\n".join(out)


def mermaid(g: Graph) -> str:
    """The graph as a Mermaid diagram (GitHub draws it): loop steps solid, joins dotted with their kind."""
    ids = {}

    def n(thing: str) -> str:
        if thing not in ids:
            ids[thing] = f"n{len(ids)}"
        return ids[thing]
    lines = ["graph LR"]
    for e in g.edges:
        if e.rel == "feeds":
            lines.append(f"  {n(e.a)} -->|{e.loop.split('/')[1]}| {n(e.b)}")
        else:
            lines.append(f"  {n(e.a)} -.->|{e.rel}| {n(e.b)}")
    lines += [f'  {v}["{re.sub(chr(34), chr(39), g.label(k))}"]' for k, v in ids.items()]
    return "\n".join(lines)
