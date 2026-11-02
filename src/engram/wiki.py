"""The wiki: the map (engram.compile) rendered as pages to read in Obsidian, by code, with no model call
(docs/technical.md, "The compiled wiki"). Every line on a page is a record: a node's line with its checked quote, a
checked summary sentence, an evidence quote, a count. `wiki/` is rebuilt whole after every compile and never committed.

An edge counts only while its quote is still in the current text of the item it cites, so an edge drawn from a cut
paragraph drops out; a superseded node's edges count for the node that superseded it; counts are of distinct backing
items, not edges. A quote from a transcribed source says to check it against the original, at its time in a video."""
import re
from dataclasses import dataclass, field
from pathlib import Path

from engram import config, labels, recsum
from engram.paths import record_conf
from engram.compile import ITEMS, Edge, Item, Map, due, load, parked, state

DIR = "wiki"
FOR, AGAINST = ("supports", "data-for"), ("refutes",)
RIPE = 3  # a theme with this many sparks and no post is ripe
TIME = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")
SPARK_WORDS = 40
STEM = 80  # longest file name, in characters
FOLDER = {"claim": "claims", "theme": "themes", "source": "sources"}  # anything else a post is under posts/


@dataclass
class Claim:
    """What the pages say about one current claim or theme: its live edges, grouped."""
    id: str
    backing: dict[str, list[Edge]] = field(default_factory=dict)  # backing item -> its edges, for
    against: dict[str, list[Edge]] = field(default_factory=dict)
    steelmans: list[str] = field(default_factory=list)  # quoted steelmans' node ids
    own: list[str] = field(default_factory=list)  # Claude's own steelmans
    sparks: list[str] = field(default_factory=list)
    posts: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    of: list[str] = field(default_factory=list)  # the claims a steelman is against
    members: list[str] = field(default_factory=list)  # a theme's claims


def _safe(s: str) -> str:
    return " ".join(str(s).replace("|", "/").replace("[", "(").replace("]", ")").split())


def _stem(s: str) -> str:
    """A page's file name from its title: what Obsidian shows in tabs, the file list and the graph."""
    s = " ".join(re.sub(r'[\\/:*?"<>|#^\[\]]', "", str(s)).split()).strip(" .")
    if len(s) > STEM:
        s = s[:STEM].rsplit(" ", 1)[0].rstrip(" ,;")
    return s or "untitled"


class Wiki:
    def __init__(self, m: Map, domain: str):
        self.m, self.domain = m, domain
        self.items = {it.id: it for it in m.items.values() if it.id}
        self.live = [e for e in m.edges if m.live(e)]
        self.by: dict[str, Claim] = {n: Claim(n) for n in m.nodes if m.is_current(n)}
        for e in self.live:
            a, rel, b = m.key(e)
            backer = e.item or a
            if b in self.by:
                c = self.by[b]
                if rel in FOR:
                    c.backing.setdefault(backer, []).append(e)
                elif rel in AGAINST:
                    c.against.setdefault(backer, []).append(e)
                elif rel == "steelman-of" and a in self.by:
                    (c.own if m.nodes[a].fm.get("by") == "claude-suggestion" else c.steelmans).append(a)
                    self.by[a].of.append(b)
                elif rel == "part-of" and a in self.by:
                    c.members.append(a)
                    self.by[a].themes.append(b)
                elif rel == "relates-to" and a in self.by:
                    c.related.append(a)
                    self.by[a].related.append(b)
            if a in self.by and rel == "argued-in" and b in self.items:
                self.by[a].posts.append(b)
            for end in (a, b, e.item):
                if self.items.get(end) and self.items[end].kind == "spark":
                    for n in (a, b):
                        if n in self.by:
                            self.by[n].sparks.append(end)
        for c in self.by.values():
            for k in ("steelmans", "own", "sparks", "posts", "related", "themes", "of", "members"):
                setattr(c, k, sorted(set(getattr(c, k)) - {c.id}))
        self.page: dict[str, str] = {}  # ref -> its page's path in wiki/, without .md
        refs = [(n, self.m.nodes[n].kind, self.line(n)) for n in self.by]
        refs += [(it.id, it.kind if it.kind == "source" else "post", it.title) for it in self.items.values() if it.kind != "spark"]
        taken: set[str] = set()
        for ref, kind, title in sorted(refs):
            name = f"{FOLDER.get(kind, 'posts')}/{_stem(title)}"
            if name.lower() in taken:
                name = f"{name} ({ref[-4:]})"
            taken.add(name.lower())
            self.page[ref] = name

    # pieces
    def line(self, n: str) -> str:
        return _safe(self.m.nodes[n].fm.get("title", ""))

    def link(self, ref: str) -> str:
        if ref in self.by:
            return f"[[{DIR}/{self.page[ref]}|{self.line(ref)}]]"
        it = self.items.get(ref)
        if it and it.kind == "spark":
            return f"a spark ({it.id})"
        return f"[[{DIR}/{self.page[ref]}|{_safe(it.title)}]]" if it else ref

    def quote(self, q: str, item: str, here: bool = False) -> str:
        """A quote with where it's from (unless it's from the page's own item); a transcribed source's says to check it
        against the original."""
        it = self.items.get(item)
        out = f"“{' '.join(q.split())}”" + ("" if here else f" ({self.link(item)})")
        if it and it.transcribed_by:
            body = recsum._norm(it.text)
            at = TIME.findall(body[:max(body.find(recsum._norm(q)), 0)])
            out += f" (check against the original{', at ' + at[-1] if at else ''})"
        return out

    def answered(self, s: str) -> bool:
        return any(self.m.key(e)[1:] == ("answers", s) for e in self.live)

    def counts(self, c: Claim) -> str:
        """Only what there is: backing from outside sources apart from the owner's own writing, then against, then
        steelmans, Claude's own apart; a claim with none of it says so."""
        outside = sum(1 for b in c.backing if (it := self.items.get(b)) and it.kind == "source")
        parts = [f"{outside} for from sources"] if outside else []
        if len(c.backing) > outside:
            parts.append(f"{len(c.backing) - outside} for from your own writing")
        if c.against:
            parts.append(f"{len(c.against)} against")
        for ss, who in ((c.steelmans, ""), (c.own, " by Claude")):
            if ss:
                parts.append(f"{len(ss)} steelman{'s' if len(ss) > 1 else ''}{who} "
                             f"({sum(not self.answered(s) for s in ss)} unanswered)")
        return ", ".join(parts) or "nothing behind it yet"

    def spark(self, ref: str) -> str:
        it = self.items[ref]
        words = it.text.split()
        return f"“{' '.join(words[:SPARK_WORDS])}{'…' if len(words) > SPARK_WORDS else ''}” ({it.id})"

    def evidence(self, edges: dict[str, list[Edge]]) -> list[str]:
        out = []
        for backer in sorted(edges):
            for e in sorted(edges[backer], key=lambda e: e.id):
                out.append(f"- {e.rel}: {self.quote(e.quote, e.item) if e.quote else self.link(backer)}")
        return out

    def steelman_lines(self, c: Claim) -> list[str]:
        out = []
        for s in c.steelmans + c.own:
            mine = " (Claude's own, not from a source)" if s in c.own else ""
            out.append(f"- {self.link(s)}{mine}")
            answers = [e for e in self.live if self.m.key(e)[1:] == ("answers", s)]
            for e in sorted(answers, key=lambda e: e.id):
                out.append(f"  - answered: {self.quote(e.quote, e.item) if e.quote else self.link(self.m.key(e)[0])}")
            if not answers:
                out.append("  - unanswered")
        return out

    # pages
    def claim_page(self, n: str) -> str:
        c, node = self.by[n], self.m.nodes[n]
        src = str(node.fm.get("quoted_from") or "")
        out = [f"# {self.line(n)}", ""]
        if node.fm.get("quote"):
            out += [f"> {self.quote(str(node.fm['quote']), src)}", ""]
        elif node.fm.get("by") == "claude-suggestion":
            out += ["Claude's own, not from a source.", ""]
        for x in c.of:
            answers = [e for e in self.live if self.m.key(e)[1:] == ("answers", n)]
            out += [f"A steelman of {self.link(x)}: {'answered' if answers else 'unanswered'}.", ""]
        out += [self.counts(c), ""]
        sections = [("Answered by", [f"- {self.quote(e.quote, e.item) if e.quote else self.link(self.m.key(e)[0])}"
                                     for e in sorted(self.live, key=lambda e: e.id) if self.m.key(e)[1:] == ("answers", n)]),
                    ("Backed by", self.evidence(c.backing)), ("Against", self.evidence(c.against)),
                    ("Steelmans", self.steelman_lines(c)), ("Sparks", [f"- {self.spark(s)}" for s in c.sparks]),
                    ("Argued in", [f"- {self.link(p)}" for p in c.posts]),
                    ("Themes", [f"- {self.link(t)}" for t in c.themes]),
                    ("Related", [f"- {self.link(r)}" for r in c.related])]
        for head, rows in sections:
            if rows:
                out += [f"## {head}", "", *rows, ""]
        return "\n".join(out)

    def theme_sparks(self, c: Claim) -> list[str]:
        return sorted(set(c.sparks) | {s for m in c.members for s in self.by[m].sparks})

    def ripe(self, c: Claim) -> bool:
        return len(self.theme_sparks(c)) >= RIPE and not (c.posts or any(self.by[m].posts for m in c.members))

    def theme_page(self, n: str) -> str:
        c = self.by[n]
        out = [f"# {self.line(n)}", ""]
        if self.ripe(c):
            out += [f"Ripe: {len(self.theme_sparks(c))} sparks and no post yet.", ""]
        if c.members:
            out += ["## Claims", "", *[f"- {self.link(x)}: {self.counts(self.by[x])}" for x in c.members], ""]
        if sparks := self.theme_sparks(c):
            out += ["## Sparks", "", *[f"- {self.spark(s)}" for s in sparks], ""]
        return "\n".join(out)

    def source_page(self, it: Item) -> str:
        who = labels.who(it.by, labels.people(record_conf(self.m.root))).rstrip("?") if it.by else "unknown"
        out = [f"# {_safe(it.title)}", ""]
        out += [f"- who: {who}"]
        out += [f"- where: {it.url}"] if it.url else []
        out += [f"- file: {it.file}"] if it.file else []
        out += [f"- read by: {it.transcribed_by}; check quotes against the original"] if it.transcribed_by else []
        out.append("")
        if summary := recsum.cached(self.domain, it.text):
            out += ["## Summary", "", summary, ""]
        used = sorted({(str(n.fm.get("quote")), n.id) for n in self.m.nodes.values() if n.fm.get("quoted_from") == it.id
                       and self.m.is_current(n.id)} | {(e.quote, self.m.key(e)[2]) for e in self.live if e.item == it.id})
        if used:
            out += ["## Quotes used", "", *[f"- {self.quote(q, it.id, here=True)}: {self.link(n)}" for q, n in used], ""]
        backs = sorted({(self.m.key(e)[1], self.m.key(e)[2]) for e in self.live if e.item == it.id and e.rel != "sparked-by"})
        if backs:
            out += ["## What it bears on", "", *[f"- {rel} {self.link(n)}" for rel, n in backs], ""]
        set_off = sorted({self.m.key(e)[0] for e in self.live if e.rel == "sparked-by" and self.m.key(e)[2] == it.id})
        if set_off:
            out += ["## Sparks it set off", "", *[f"- {self.spark(s)}" for s in set_off if s in self.items], ""]
        return "\n".join(out)

    def post_page(self, it: Item) -> str:
        argued = sorted(c.id for c in self.by.values() if it.id in c.posts)
        out = [f"# {_safe(it.title)}", "", f"{'Published' if it.kind == 'published' else 'Draft'}: {it.path}", ""]
        for n in argued:
            c = self.by[n]
            out += [f"## {self.line(n)}", "", f"{self.counts(c)} ([[{DIR}/{self.page[n]}|the claim]])", ""]
            for head, rows in (("For", self.evidence(c.backing)), ("Against", self.evidence(c.against)),
                               ("Steelmans", self.steelman_lines(c))):
                if rows:
                    out += [f"### {head}", "", *rows, ""]
        mine = set(argued) | {t for n in argued for t in self.by[n].themes}
        reading = sorted(p.id for p in self.items.values() if p.kind == "published" and p.id != it.id and
                         mine & {x for c in self.by.values() if p.id in c.posts for x in [c.id, *c.themes]})
        if reading:
            out += ["## Further reading", "", *[f"- {self.link(p)}" for p in reading], ""]
        return "\n".join(out)

    def index(self) -> str:
        themes = sorted((n for n, c in self.by.items() if self.m.nodes[n].kind == "theme"), key=self.line)
        claims = [n for n, c in self.by.items() if self.m.nodes[n].kind == "claim"]
        out = ["# The map", ""]
        for t in themes:
            c = self.by[t]
            out += [f"## {self.link(t)}{' (ripe)' if self.ripe(c) else ''}", ""]
            out += [f"- {self.link(x)}: {self.counts(self.by[x])}" for x in sorted(c.members, key=self.line)] + [""]
        loose = sorted((n for n in claims if not self.by[n].themes and not self.by[n].of), key=self.line)
        if loose:
            out += ["## Not under a theme yet", "", *[f"- {self.link(x)}: {self.counts(self.by[x])}" for x in loose], ""]
        posts = sorted((it for it in self.items.values() if it.kind not in ITEMS), key=lambda it: (it.kind, it.title))
        if posts:
            out += ["## Posts", "", *[f"- {self.link(p.id)} ({p.kind})" for p in posts], ""]
        sources = sorted((it for it in self.items.values() if it.kind == "source"), key=lambda it: it.title)
        if sources:
            out += ["## Sources", "", *[f"- {self.link(s.id)}" for s in sources], ""]
        return "\n".join(out)

    def open(self) -> str:
        """What the health check finds: what couldn't be compiled or hasn't been, claims with nothing behind them,
        steelmans not answered, and gaps worth looking up, which wait for the owner's go."""
        s = state(self.domain)
        rows = [("Couldn't be compiled (tried twice; tried again when it changes)",
                 [f"- {self.link(it.id) if it.id else it.path}" for it in parked(self.domain, self.m)]),
                ("Not compiled yet", [f"- {self.link(r) if r in self.items else r}" for r in due(self.domain, self.m)]),
                ("Claims with nothing behind them",
                 [f"- {self.link(n)}" for n in sorted(self.by, key=self.line) if self.m.nodes[n].kind == "claim"
                  and not self.by[n].backing and self.m.nodes[n].fm.get("by") != "claude-suggestion"]),
                ("Steelmans not answered",
                 [f"- {self.link(x)} (against {self.link(c.id)})" for c in sorted(self.by.values(), key=lambda c: c.id)
                  for x in c.steelmans + c.own if not self.answered(x)]),
                ("Worth looking up (nothing is fetched until you say go)", [f"- {_safe(g)}" for g in s.get("gaps", [])])]
        out = ["# Open", ""]
        for head, lines in rows:
            if lines:
                out += [f"## {head}", "", *lines, ""]
        return "\n".join(out if len(out) > 2 else out + ["Nothing open.", ""])

    def pages(self) -> dict[str, str]:
        out = {"index.md": self.index(), "open.md": self.open()}
        for n in self.by:
            out[f"{self.page[n]}.md"] = self.theme_page(n) if self.m.nodes[n].kind == "theme" else self.claim_page(n)
        for it in self.items.values():
            if it.kind == "source":
                out[f"{self.page[it.id]}.md"] = self.source_page(it)
            elif it.kind not in ITEMS:
                out[f"{self.page[it.id]}.md"] = self.post_page(it)
        return {k: v.rstrip("\n") + "\n" for k, v in out.items()}


def render(domain: str) -> Path:
    """Rebuild `wiki/` in the domain's repo: every page written, any page no longer made removed."""
    root = config.load()[domain].repo
    pages = Wiki(load(root), domain).pages()
    d = Path(root) / DIR
    d.mkdir(exist_ok=True)
    for p in d.rglob("*.md"):
        if p.relative_to(d).as_posix() not in pages:
            p.unlink()
    for name, text in pages.items():
        p = d / name
        p.parent.mkdir(exist_ok=True)
        if not p.exists() or p.read_text() != text:
            p.write_text(text)
    for sub in d.iterdir():
        if sub.is_dir() and not any(sub.iterdir()):
            sub.rmdir()
    return d
