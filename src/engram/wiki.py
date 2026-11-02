"""The wiki's pages as data (docs/technical.md, "The compiled wiki"): a concept page and a source page are typed
structures, rendered to Obsidian markdown and parsed back byte for byte. The checker, the splicer, the index and the
health check all read this one model.

A concept page, sections always in this order, an empty one left out:

    ---
    aliases: ["Other name"]
    tags: ["concept", "evolutionary-psychology"]
    pillar: "evolutionary psychology"
    ---

    > [!summary]
    > What the concept means in the owner's thinking, linking [[wiki/concepts/Other|Other]] inline.

    ## What the sources say            each source's words first, then its position in one short sentence
    ## The case against                each steelman a warning callout, from a source (with its quote) or Claude's own,
                                       ending "Answered: <quote> (<link>)" or "Unanswered."
    ## In your writing                 each draft or post that uses it, then the owner's sparks on it, verbatim
    ## Related                         other concepts

A source page: its properties, a summary callout, `## Key quotes`, `## Concepts`, `## Sparks it set off`."""
import json
import re
from dataclasses import dataclass, field, replace

from engram import recsum

DIR = "wiki"
CONCEPTS, SOURCES = f"{DIR}/concepts", f"{DIR}/sources"
STEM = 80  # longest file name, in characters
POSITION_WORDS = 30
LINK = re.compile(r"\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]*))?\]\]")
SENTENCE = re.compile(r"(?<=[.!?])[\"”’)]*\s+(?=[\[\"“A-Z0-9])")
TIME = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")


def stem(s: str) -> str:
    """A page's file name from its name or title: what Obsidian shows in tabs, the file list and the graph."""
    s = " ".join(re.sub(r'[\\/:*?"<>|#^\[\]]', "", str(s)).split()).strip(" .")
    if len(s) > STEM:
        s = s[:STEM].rsplit(" ", 1)[0].rstrip(" ,;")
    return s or "untitled"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def link(target: str, label: str) -> str:
    return f"[[{target}|{label}]]"


def concept_link(name: str) -> str:
    return link(f"{CONCEPTS}/{stem(name)}", stem(name))


def one_line(s: str) -> str:
    return " ".join(str(s).split())


def sentences(s: str) -> list[str]:
    return [x for x in SENTENCE.split(LINK.sub(lambda m: m.group(3) or m.group(1), one_line(s))) if x.strip()]


def transcribed_note(text: str, quote: str) -> str:
    """For a quote from a transcribed source: check it against the original, at the nearest earlier time it gives."""
    body = recsum._norm(text)
    at = TIME.findall(body[:max(body.find(recsum._norm(quote)), 0)])
    return f"(check the original{', at ' + at[-1] if at else ''})"


# the pieces of a page
@dataclass
class Says:
    """One source under "What the sources say": its words first, then its position."""
    source: str  # the source page's link target, `wiki/sources/<stem>`
    quote: str
    position: str
    note: str = ""  # a transcribed source's "(check the original, at 01:30)"


@dataclass
class Answer:
    target: str  # what answers it: a source page or a draft or post, its link target
    label: str
    quote: str


@dataclass
class Steelman:
    argument: str
    source: str = ""  # its source page's link target; "" for Claude's own
    quote: str = ""  # from that source
    note: str = ""
    answer: Answer | None = None


@dataclass
class Use:
    """A draft or post that bears on the concept, and how it uses it."""
    target: str  # the post's file without `.md`
    title: str
    line: str


@dataclass
class Spark:
    date: str
    text: str  # the owner's words, verbatim


@dataclass
class Concept:
    name: str
    pillar: str
    summary: str
    aliases: list[str] = field(default_factory=list)
    sources: list[Says] = field(default_factory=list)
    against: list[Steelman] = field(default_factory=list)
    writing: list[Use] = field(default_factory=list)
    sparks: list[Spark] = field(default_factory=list)
    related: list[str] = field(default_factory=list)  # other concepts' names

    @property
    def path(self) -> str:
        return f"{CONCEPTS}/{stem(self.name)}.md"


@dataclass
class Source:
    title: str  # the page's name
    by: str
    kind: str
    date: str
    url: str = ""
    summary: str = ""
    quotes: list[tuple[str, str]] = field(default_factory=list)  # (quote, note)
    concepts: list[str] = field(default_factory=list)
    sparks: list[Spark] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{SOURCES}/{self.title}.md"

    @property
    def target(self) -> str:
        return f"{SOURCES}/{self.title}"


# rendering
def _props(rows: list[tuple[str, object]]) -> list[str]:
    return ["---", *[f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in rows], "---", ""]


def _callout(kind: str, title: str, lines: list[str], depth: int = 1) -> list[str]:
    p = "> " * depth
    return [f"{p}[!{kind}]{' ' + title if title else ''}", *[(p + l).rstrip() for l in lines]]


def _text_lines(text: str) -> list[str]:
    return text.strip("\n").splitlines() or [""]


def _spark(s: Spark) -> list[str]:
    return _callout("quote", f"Spark, {s.date}" if s.date else "Spark", _text_lines(s.text))


def _quote_lines(quote: str, note: str) -> list[str]:
    return [one_line(quote)] + ([note] if note else [])


def render_concept(c: Concept) -> str:
    out = _props([("aliases", c.aliases), ("tags", ["concept", slug(c.pillar)]), ("pillar", c.pillar)])
    out += _callout("summary", "", [one_line(c.summary)]) + [""]
    blocks: list[tuple[str, list[list[str]]]] = [
        ("What the sources say", [_callout("quote", link(s.source, s.source.rsplit("/", 1)[-1]), _quote_lines(s.quote, s.note))
                                  + ["", one_line(s.position)] for s in c.sources]),
        ("The case against", [_steelman(s) for s in c.against]),
        ("In your writing", ([[f"- {link(u.target, u.title)}: {one_line(u.line)}" for u in c.writing]] if c.writing else [])
         + [_spark(s) for s in c.sparks]),
        ("Related", [[f"- {concept_link(r)}" for r in c.related]] if c.related else []),
    ]
    for head, bs in blocks:
        if bs:
            out += [f"## {head}", ""]
            for b in bs:
                out += b + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def _steelman(s: Steelman) -> list[str]:
    title = f"Steelman ({link(s.source, s.source.rsplit('/', 1)[-1])})" if s.source else "Steelman (Claude's own)"
    lines = [one_line(s.argument)]
    if s.quote:
        lines += _callout("quote", "", _quote_lines(s.quote, s.note))
    lines += ["", f"Answered: “{one_line(s.answer.quote)}” ({link(s.answer.target, s.answer.label)})" if s.answer else "Unanswered."]
    return _callout("warning", title, lines)


def render_source(s: Source) -> str:
    out = _props([("by", s.by), ("url", s.url), ("kind", s.kind), ("date", s.date), ("tags", ["source"])])
    out += _callout("summary", "", [one_line(s.summary)]) + [""]
    blocks = [("Key quotes", [_callout("quote", "", _quote_lines(q, n)) for q, n in s.quotes]),
              ("Concepts", [[f"- {concept_link(c)}" for c in s.concepts]] if s.concepts else []),
              ("Sparks it set off", [_spark(x) for x in s.sparks])]
    for head, bs in blocks:
        if bs:
            out += [f"## {head}", ""]
            for b in bs:
                out += b + [""]
    return "\n".join(out).rstrip("\n") + "\n"


# parsing: the inverse of rendering
class Unreadable(ValueError):
    pass


def _split(text: str) -> tuple[dict, str, dict[str, list[list[str]]]]:
    """(properties, the summary, each section's blocks of lines, split at blank lines)."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise Unreadable("no properties")
    end = lines.index("---", 1)
    props = {}
    for l in lines[1:end]:
        k, _, v = l.partition(": ")
        props[k] = json.loads(v)
    body = lines[end + 1:]
    heads = [i for i, l in enumerate(body) if l.startswith("## ")]
    top = body[:heads[0]] if heads else body
    summary = " ".join(l[2:] for l in top if l.startswith("> ") and not l.startswith("> [!summary]"))
    sections = {}
    for n, i in enumerate(heads):
        chunk = body[i + 1:heads[n + 1] if n + 1 < len(heads) else len(body)]
        blocks, cur = [], []
        for l in chunk + [""]:
            if l == "":
                if cur:
                    blocks.append(cur)
                cur = []
            else:
                cur.append(l)
        sections[body[i][3:]] = blocks
    return props, summary, sections


def _unquote(lines: list[str], depth: int = 1) -> list[str]:
    p = ">" * depth
    return [l[len(p) + 1:] if l.startswith(p + " ") else "" for l in lines]


def _link_of(s: str) -> tuple[str, str]:
    m = LINK.search(s)
    if not m:
        raise Unreadable(f"no link in {s!r}")
    return m.group(1), m.group(3) or m.group(1)


def _quote_of(lines: list[str]) -> tuple[str, str]:
    q = [l for l in lines if l]
    note = q[-1] if len(q) > 1 and q[-1].startswith("(check the original") else ""
    return " ".join(q[:-1] if note else q), note


def _spark_of(block: list[str]) -> Spark:
    head = block[0]
    date = head.split("Spark, ", 1)[1] if "Spark, " in head else ""
    return Spark(date, "\n".join(_unquote(block[1:])))


def parse_concept(name: str, text: str) -> Concept:
    props, summary, secs = _split(text)
    c = Concept(name, props.get("pillar", ""), summary, list(props.get("aliases") or []))
    for b in secs.get("What the sources say", []):
        if b[0].startswith("> [!quote]"):
            q, note = _quote_of(_unquote(b[1:]))
            c.sources.append(Says(_link_of(b[0])[0], q, "", note))
        elif c.sources:
            c.sources[-1].position = " ".join(b)
    for b in secs.get("The case against", []):
        src = "" if "Claude's own" in b[0] else _link_of(b[0])[0]
        inner = _unquote(b[1:])
        s = Steelman(inner[0], src)
        nested = [l for l in inner if l.startswith(">")]
        if nested:
            s.quote, s.note = _quote_of(_unquote(nested[1:]))
        last = inner[-1]
        if last.startswith("Answered: "):
            m = re.match(r"Answered: “(.*)” \((\[\[.*\]\])\)$", last)
            if not m:
                raise Unreadable(f"an answer that doesn't read: {last!r}")
            s.answer = Answer(*_link_of(m.group(2)), m.group(1))
        c.against.append(s)
    for b in secs.get("In your writing", []):
        if b[0].startswith("> [!quote]"):
            c.sparks.append(_spark_of(b))
            continue
        for l in b:
            m = re.match(r"- (\[\[.*?\]\]): (.*)$", l)
            if not m:
                raise Unreadable(f"a writing line that doesn't read: {l!r}")
            c.writing.append(Use(*_link_of(m.group(1)), m.group(2)))
    for b in secs.get("Related", []):
        c.related += [_link_of(l)[1] for l in b]
    return c


def parse_source(title: str, text: str) -> Source:
    props, summary, secs = _split(text)
    s = Source(title, props.get("by", ""), props.get("kind", ""), props.get("date", ""), props.get("url", ""), summary)
    s.quotes = [_quote_of(_unquote(b[1:])) for b in secs.get("Key quotes", [])]
    s.concepts = [_link_of(l)[1] for b in secs.get("Concepts", []) for l in b]
    s.sparks = [_spark_of(b) for b in secs.get("Sparks it set off", [])]
    return s


# the vault, as the checker sees it
@dataclass
class Vault:
    """What a page is checked against: every `.md` file in the repo, the text each quotable file stands for (a source
    page stands for its source's text, a draft or post for itself), every spark's words, the pillars."""
    files: set[str]
    texts: dict[str, str] = field(default_factory=dict)  # a file's path -> the text its quotes are checked against
    sparks: list[str] = field(default_factory=list)
    pillars: list[str] = field(default_factory=list)

    def resolve(self, target: str) -> str | None:
        """A link's file as Obsidian resolves it, against `.md` files only: the path from the vault's root, else the
        one file whose path ends with it."""
        t = target.strip()
        t = t if t.endswith(".md") else t + ".md"
        if t in self.files:
            return t
        ends = sorted(f for f in self.files if f.endswith("/" + t))
        return ends[0] if ends else None

    def quoted(self, quote: str, target: str) -> bool:
        path = self.resolve(target)
        return bool(path and quote.strip() and path in self.texts and recsum._norm(quote) in recsum._norm(self.texts[path]))

    def answered(self, s: Steelman) -> bool:
        """A steelman counts as answered only while its answer's quote checks against what it links."""
        return bool(s.answer and self.quoted(s.answer.quote, s.answer.target))


def _links(text: str) -> list[str]:
    return [m.group(1) for m in LINK.finditer(text)]


def check_concept(c: Concept, v: Vault) -> list[str]:
    """Why a concept page can't be written, or nothing: its properties and sections, every quote verbatim in what it
    cites, every link resolving, every steelman owned by a source whose words it quotes or by Claude."""
    out = []
    if c.pillar not in v.pillars:
        out.append(f"pillar {c.pillar!r} isn't one of {', '.join(v.pillars)}")
    if not 2 <= len(sentences(c.summary)) <= 4:
        out.append(f"the summary has {len(sentences(c.summary))} sentences, not two to four")
    for s in c.sources:
        label = s.source.rsplit("/", 1)[-1]
        if not s.source.startswith(SOURCES + "/") or not v.resolve(s.source):
            out.append(f"{label}: a source entry links no source page")
        elif not v.quoted(s.quote, s.source):
            out.append(f"{label}: its quote isn't in the source word for word")
        if len(sentences(s.position)) != 1 or len(s.position.split()) > POSITION_WORDS:
            out.append(f"{label}: its position isn't one short sentence")
    for s in c.against:
        if not s.source and s.quote:
            out.append("a steelman of Claude's own quotes nothing")
        if s.source and not v.quoted(s.quote, s.source):
            out.append(f"the steelman from {s.source.rsplit('/', 1)[-1]} doesn't quote it word for word")
        if s.answer and not v.answered(s):
            out.append(f"an answer's quote isn't in {s.answer.label} word for word")
    for sp in c.sparks:
        if not any(recsum._norm(sp.text) in recsum._norm(x) for x in v.sparks if sp.text.strip()):
            out.append("a spark isn't the owner's words")
    for t in _links(render_concept(c)):
        if not v.resolve(t):
            out.append(f"the link {t!r} goes nowhere")
    return sorted(set(out), key=out.index)


def check_source(s: Source, v: Vault, sentences_checked: list[dict] = ()) -> list[str]:
    """Why a source page can't be written: every key quote in the source, every summary sentence quoting it (as
    recsum checks a summary), every link resolving."""
    out = []
    text = v.texts.get(s.path, "")
    for q, _ in s.quotes:
        if not v.quoted(q, s.target):
            out.append(f"a key quote isn't in the source word for word: {q[:60]!r}")
    for x in sentences_checked:
        if why := recsum.check(x, text):
            out.append(f"a summary sentence: {why}")
    for sp in s.sparks:
        if not any(recsum._norm(sp.text) in recsum._norm(x) for x in v.sparks if sp.text.strip()):
            out.append("a spark isn't the owner's words")
    for t in _links(render_source(s)):
        if not v.resolve(t):
            out.append(f"the link {t!r} goes nowhere")
    return out


def kept(old: Concept | None, new: Concept, summary_may_change: bool, rewrites: str = "") -> list[str]:
    """Whether a splice left everything outside its edits as it was: every source entry, steelman, writing line, spark
    and related link of the old page is on the new one, unchanged, in its order. A steelman may gain or change its
    answer but never lose it; the writing line of the post being compiled (`rewrites`) may be rewritten; the summary
    changes only where it may."""
    if old is None:
        return []
    out = []
    if not summary_may_change and old.summary != new.summary:
        out.append("the summary changed on a source's compile")
    if new.sources[:len(old.sources)] != old.sources:
        out.append("an old source entry changed")
    pairs = list(zip(old.against, new.against))
    if len(new.against) < len(old.against) or any(replace(a, answer=None) != replace(b, answer=None)
                                                  or (a.answer and not b.answer) for a, b in pairs):
        out.append("an old steelman changed")
    if len(new.writing) < len(old.writing) or any(a != b and not (a.target == b.target == rewrites)
                                                  for a, b in zip(old.writing, new.writing)):
        out.append("an old writing line changed")
    if new.sparks[:len(old.sparks)] != old.sparks or new.related[:len(old.related)] != old.related:
        out.append("an old spark or related link changed")
    if (new.pillar, new.aliases[:len(old.aliases)]) != (old.pillar, old.aliases):
        out.append("the pillar or an alias changed")
    return out
