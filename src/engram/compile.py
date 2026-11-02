"""The compiler that keeps an area's wiki (docs/technical.md, "The compiled wiki").

Its **items** are what was handed over or written: a `source` or a `spark` entry, and each post (a `.md` file under a
folder `[wiki] posts` names, a draft or published), read as HEAD holds it. Which items were compiled at which text is
the data folder's (`compile/<domain>.json`): a source or spark is compiled once; a draft once its text has stood a day
unchanged in git, a post at once when it's published; an item that fails twice at the same text is parked until it
changes. One run at a time per area (`lock`)."""
import contextlib
import copy
import fcntl
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from engram import commitmsg, config, llm, pack, recsum, store, wiki
from engram.paths import data_path

ENTRIES = ("source", "spark")
TRIES = 2  # an item that fails this many times at the same text is parked until it changes
SETTLE = 24 * 3600  # a draft compiles once its text has stood this long unchanged in git
MAX_CONCEPTS = 5  # a source or post bears on at most this many concepts
EFFORT = "low"


@dataclass
class Item:
    key: str  # an entry's id, or a post's document id ("" until its first compile gives it one)
    kind: str  # source, spark, draft or published
    title: str
    text: str
    path: str = ""  # a post's file
    fm: dict = field(default_factory=dict)  # an entry's front matter
    since: float = 0.0  # a post: when its file last changed in git

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]

    @property
    def ref(self) -> str:
        return self.key or self.path


def posts(st: store.Store) -> dict[str, str]:
    """Each folder of posts and what its posts are (`[wiki] posts`: "drafts/" = "draft")."""
    return dict((st.config.get("wiki") or {}).get("posts") or {})


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def at_head(root: Path, path: str) -> str | None:
    """A file as HEAD holds it, or None."""
    r = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def post_title(text: str, path: str) -> str:
    """A post's title: its header's `title:` line, else its file name."""
    for line in text.splitlines()[:20]:
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return Path(path).stem


def items(root: Path) -> dict[str, Item]:
    """Every item by its ref: the entries from the record, the posts from HEAD."""
    from engram import docreg
    st = store.Store(root)
    out = {}
    for e in st.events():
        if e.kind in ENTRIES:
            out[e.id] = Item(e.id, e.kind, str(e.fm.get("title", "")), e.body, fm=dict(e.fm))
    reg = docreg.load(root)
    for folder, what in sorted(posts(st).items()):
        for rel in sorted(_git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", folder).splitlines()):
            if not rel.endswith(".md"):
                continue
            text = at_head(root, rel) or ""
            since = float(_git(root, "log", "-1", "--format=%ct", "--", rel).strip() or 0)
            it = Item(reg.owner(rel) or "", what, post_title(text, rel), text, path=rel, since=since)
            out[it.ref] = it
    return out


# what was compiled, at which text
def _state_path(domain: str) -> Path:
    return data_path("compile") / f"{domain}.json"


def state(domain: str) -> dict:
    p = _state_path(domain)
    return json.loads(p.read_text()) if p.exists() else {"items": {}, "parked": [], "found": {}}


def save(domain: str, s: dict):
    p = _state_path(domain)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1, ensure_ascii=False, sort_keys=True))
    tmp.replace(p)


def parked(domain: str, its: dict[str, Item]) -> list[Item]:
    """Items that failed twice at their current text."""
    got = state(domain)["items"]
    return [it for k, it in sorted(its.items()) if (s := got.get(k)) and s["hash"] == it.hash and not s["ok"]
            and s["fails"] >= TRIES]


def due(domain: str, its: dict[str, Item], now: float | None = None) -> list[str]:
    """The items to compile: a source or spark never compiled; a post whose text changed since, once it has stood a day
    or at once when it was published at a new path; never one parked. Entries first."""
    now = time.time() if now is None else now
    got = state(domain)["items"]
    out = []
    for k, it in sorted(its.items(), key=lambda x: (x[1].kind not in ENTRIES, x[0])):
        s = got.get(k)
        if s and s["hash"] == it.hash and (s["ok"] or s["fails"] >= TRIES):
            continue
        if s and s["ok"] and it.kind in ENTRIES:  # an entry never changes; compiled once
            continue
        published = it.kind == "published" and (not s or s.get("path") != it.path)
        if it.kind not in ENTRIES and not published and now - it.since < SETTLE:
            continue
        out.append(k)
    return out


@contextlib.contextmanager
def lock(domain: str):
    """One compile run per area at a time; a second finds the lock taken and yields False."""
    p = data_path("compile") / f"{domain}.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# the wiki as HEAD holds it
@dataclass
class Book:
    """Every page of the wiki as HEAD holds it, and the vault its pages are checked against."""
    root: Path
    its: dict[str, Item]
    concepts: dict[str, wiki.Concept]  # by name
    sources: dict[str, wiki.Source]  # by page name
    titles: dict[str, str]  # a source item's id -> its page's name
    files: set[str]
    pillars: list[str]

    def concept(self, name: str) -> wiki.Concept | None:
        """A concept by its name or one of its aliases, in any case."""
        k = wiki.stem(name).lower()
        return next((c for c in self.concepts.values() if k == c.name.lower() or k in map(str.lower, c.aliases)), None)

    def vault(self, extra: set[str] = frozenset()) -> wiki.Vault:
        texts = {f"{wiki.SOURCES}/{t}.md": self.its[i].text for i, t in self.titles.items()}
        texts |= {it.path: it.text for it in self.its.values() if it.path}
        return wiki.Vault(self.files | set(extra), texts, [it.text for it in self.its.values() if it.kind == "spark"],
                          self.pillars)


def titles(its: dict[str, Item]) -> dict[str, str]:
    """Each source's page name, from its title; a later source with a taken name gets its id's tail."""
    out, taken = {}, set()
    for k, it in sorted(its.items()):
        if it.kind == "source":
            name = wiki.stem(it.title)
            if name.lower() in taken:
                name = f"{name} ({k[-4:]})"
            taken.add(name.lower())
            out[k] = name
    return out


def book(root: Path) -> Book:
    st = store.Store(root)
    its = items(root)
    files = {f for f in _git(root, "ls-tree", "-r", "--name-only", "HEAD").splitlines() if f.endswith(".md")}
    concepts, sources = {}, {}
    for f in sorted(files):
        name = Path(f).stem
        if f.startswith(wiki.CONCEPTS + "/"):
            concepts[name] = wiki.parse_concept(name, at_head(root, f) or "")
        elif f.startswith(wiki.SOURCES + "/"):
            sources[name] = wiki.parse_source(name, at_head(root, f) or "")
    return Book(Path(root), its, concepts, sources, titles(its), files,
                list((st.config.get("wiki") or {}).get("pillars") or []))


# what the model is shown
def listing(b: Book) -> str:
    """Each concept with its pillar, aliases, first sentence and steelmans, numbered so an answer can name one."""
    out = []
    for c in sorted(b.concepts.values(), key=lambda c: c.name):
        first = (wiki.sentences(c.summary) or [""])[0]
        aka = f"; also {', '.join(c.aliases)}" if c.aliases else ""
        out.append(f"- {c.name} ({c.pillar}{aka}): {first}")
        for n, s in enumerate(c.against, 1):
            out.append(f"  S{n} [{'answered' if b.vault().answered(s) else 'unanswered'}] {s.argument}")
    return "\n".join(out) or "none yet"


def _ask(prompt: str) -> tuple[dict | None, float]:
    out, used = llm.ask_json(prompt, effort=EFFORT)
    return out, used.get("usd", 0.0)


def _concept_link(b: Book, new: dict[str, wiki.Concept]):
    """`[[Name]]` the model wrote for a concept, as the concept's link; anything else is left for the checker."""
    def sub(m):
        if "/" in m.group(1):
            return m.group(0)
        c = b.concept(m.group(1)) or new.get(wiki.stem(m.group(1)))
        return wiki.concept_link(c.name) if c else m.group(0)
    return sub


def _steelman_at(c: wiki.Concept, ref) -> int | None:
    n = str(ref or "").strip().upper().lstrip("S")
    return int(n) - 1 if n.isdigit() and 0 < int(n) <= len(c.against) else None


# one item's edits, spliced into pages
@dataclass
class Edits:
    """What one reply changes: each concept's page, the source's page, and what code dropped."""
    concepts: dict[str, wiki.Concept] = field(default_factory=dict)
    old: dict[str, wiki.Concept | None] = field(default_factory=dict)
    source: wiki.Source | None = None
    sentences: list[dict] = field(default_factory=list)
    sources: dict[str, wiki.Source] = field(default_factory=dict)  # source pages a spark lands on


def splice(b: Book, it: Item, reply: dict) -> Edits:
    """A reply's edits applied to copies of the pages they touch. A source adds its entry, steelmans, answers and
    related links to each concept it names (at most five), and its own page; a post sets its line under "In your
    writing", and may revise a summary, answer a steelman or bring a new concept; a spark goes under the concept it
    bears on, verbatim, and on the page of the source that set it off."""
    e = Edits()
    names = {}
    rows = [r for r in reply.get("concepts") or [] if isinstance(r, dict) and str(r.get("name") or "").strip()]
    if it.kind == "spark":
        rows = [{"name": reply["concept"], "summary": reply.get("summary")}] if reply.get("concept") else []
    rows = rows[:MAX_CONCEPTS]
    for r in rows:  # every concept the reply names, so links among them resolve
        old = b.concept(str(r["name"]))
        if old:
            names[old.name] = copy.deepcopy(old)
            e.old[old.name] = old
        elif it.kind != "spark":
            name = wiki.stem(r["name"])
            names[name] = wiki.Concept(name, str(r.get("pillar") or ""), str(r.get("summary") or ""),
                                       [wiki.stem(a) for a in r.get("aliases") or [] if str(a).strip()])
            e.old[name] = None
    link = _concept_link(b, names)
    title = b.titles.get(it.key, "")
    target = f"{wiki.SOURCES}/{title}" if it.kind == "source" else it.path.removesuffix(".md")
    note = (lambda q: wiki.transcribed_note(it.text, q)) if it.fm.get("transcribed_by") else (lambda q: "")
    for r in rows:
        held = b.concept(str(r["name"]))
        c = names.get(held.name if held else wiki.stem(r["name"]))
        if c is None:
            continue
        if (e.old[c.name] is None or it.kind != "source") and r.get("summary"):
            c.summary = wiki.LINK.sub(link, wiki.one_line(r["summary"]))
        if it.kind == "source":
            c.sources.append(wiki.Says(target, wiki.one_line(r.get("quote", "")), wiki.one_line(r.get("position", "")),
                                       note(str(r.get("quote", "")))))
            for s in r.get("steelmans") or []:
                q = wiki.one_line(s.get("quote") or "") if isinstance(s, dict) else ""
                c.against.append(wiki.Steelman(wiki.one_line(s.get("argument", "")) if isinstance(s, dict) else str(s),
                                               target if q else "", q, note(q) if q else ""))
        elif it.kind == "spark":
            c.sparks.append(wiki.Spark(it.fm.get("date", ""), it.text.strip("\n")))
        else:
            use = wiki.Use(target, it.title, wiki.one_line(r.get("line", "")))
            at = next((n for n, u in enumerate(c.writing) if u.target == target), len(c.writing))
            c.writing[at:at + 1] = [use]
        for a in r.get("answers") or []:
            n = _steelman_at(c, a.get("steelman") if isinstance(a, dict) else None)
            if n is not None:
                c.against[n].answer = wiki.Answer(target, title or it.title, wiki.one_line(a.get("quote", "")))
        for x in r.get("related") or []:
            o = b.concept(str(x)) or names.get(wiki.stem(str(x)))
            if o and o.name != c.name and o.name not in c.related:
                c.related.append(o.name)
        e.concepts[c.name] = c
    if it.kind == "source":
        e.sentences = [x for x in reply.get("summary") or [] if isinstance(x, dict)][:3]
        quotes = [wiki.one_line(q) for q in reply.get("key_quotes") or [] if str(q).strip()]
        e.source = wiki.Source(title, str(it.fm.get("by", "")).removeprefix("other:"), str(it.fm.get("form", "")),
                               str(it.fm.get("date", "")), str(it.fm.get("url", "")),
                               " ".join(wiki.one_line(x.get("text", "")) for x in e.sentences),
                               [(q, note(q)) for q in quotes], list(e.concepts))
    if it.kind == "spark" and (src := b.titles.get(str(it.fm.get("sparked_by") or ""))) and src in b.sources:
        page = copy.deepcopy(b.sources[src])
        page.sparks.append(wiki.Spark(it.fm.get("date", ""), it.text.strip("\n")))
        e.sources[src] = page
    return e


def problems(b: Book, it: Item, e: Edits, drop: set[str] = frozenset()) -> tuple[dict[str, list[str]], list[str]]:
    """Each concept page's problems, and the source page's, checked against the vault with the pages this item writes;
    a concept in `drop` (one that failed) isn't there to link to."""
    made = {c.path for n, c in e.concepts.items() if n not in drop}
    if e.source:
        made.add(e.source.path)
    v = b.vault(made)
    out = {}
    for n, c in e.concepts.items():
        if n in drop:
            continue
        rewrites = it.path.removesuffix(".md") if it.path else ""
        out[n] = wiki.check_concept(c, v) + wiki.kept(e.old[n], c, it.kind != "source", rewrites)
    src = []
    if e.source:
        page = replace(e.source, concepts=[x for x in e.source.concepts if x not in drop])
        src = wiki.check_source(page, v, e.sentences) + ([] if e.sentences else ["no summary"])
    return out, src


def _retry(prompt: str, why: dict[str, list[str]], src: list[str]) -> str:
    lines = [f"- {n}: {'; '.join(w)}" for n, w in why.items() if w] + ([f"- the source page: {'; '.join(src)}"] if src else [])
    return prompt + "\n\nYour last reply had these problems. Reply again in full, the same JSON, fixing them:\n" + "\n".join(lines)


@contextlib.contextmanager
def _compiler_commit():
    """The pre-commit lets only the compiler change `wiki/` (lint.WIKI_ENV)."""
    from engram import lint
    before = os.environ.get(lint.WIKI_ENV)
    os.environ[lint.WIKI_ENV] = "1"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(lint.WIKI_ENV, None)
        else:
            os.environ[lint.WIKI_ENV] = before


def write(root: Path, pages: dict[str, str], message: str, register: str = "") -> list[str]:
    """Pages written under `wiki/` and committed in one transaction, with the post's id given it now if it has none.
    Nothing outside `wiki/` is ever written here."""
    from engram import docreg
    bad = [p for p in pages if not p.startswith(wiki.DIR + "/") or ".." in Path(p).parts]
    if bad:
        raise ValueError(f"the compiler writes only under {wiki.DIR}/: {bad}")
    st = store.Store(root)
    with _compiler_commit(), st.transaction(message=message) as tx:
        if register:
            docreg.load(root).doc_id(register)
        for rel, text in pages.items():
            p = Path(root) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            tx.extra.append(rel)
    return sorted(pages)


PROMPTS = {"source": "compile", "draft": "compile_post", "published": "compile_post", "spark": "compile_spark"}


def compile_item(domain: str, ref: str, ask=None) -> dict:
    """Compile one item: one call (and one more for what failed), its pages checked and committed together; a concept
    page that still fails is parked as (item, concept) and the rest land. A source page that fails fails the item."""
    d = config.load()[domain]
    root = Path(d.repo)
    b = book(root)
    it = b.its[ref]
    p = pack.load(domain)
    words = config.voice(p.prompts[PROMPTS[it.kind]])
    prompt = words.format(title=it.title, by=str(it.fm.get("by", "")).removeprefix("other:"), kind=it.fm.get("form", it.kind),
                          path=it.path, text=it.text, concepts=listing(b), pillars=", ".join(b.pillars))
    s = state(domain)
    rec = s["items"].get(ref) if s["items"].get(ref, {}).get("hash") == it.hash else None
    res = {"item": ref, "pages": [], "parked": [], "usd": 0.0, "ok": False}
    ask = ask or _ask

    def call(text):
        try:
            reply, usd = ask(text)
        except llm.Unavailable as err:
            reply, usd, res["error"] = None, 0.0, str(err)
        res["usd"] += usd
        return reply if isinstance(reply, dict) else None

    reply = call(prompt)
    e = splice(b, it, reply) if reply is not None else None
    if e is not None:
        why, src = problems(b, it, e)
        if any(why.values()) or src:
            again = call(_retry(prompt, why, src))
            if again is not None:
                e2 = splice(b, it, again)
                for n in [n for n, w in why.items() if w]:  # only what failed is taken from the second reply
                    if n in e2.concepts:
                        e.concepts[n], e.old[n] = e2.concepts[n], e2.old[n]
                    else:
                        e.concepts.pop(n)
                if src:
                    e.source, e.sentences = e2.source, e2.sentences
        failed: dict[str, list[str]] = {}
        while True:  # a page left linking to a parked page fails with it
            why, src = problems(b, it, e, set(failed))
            failing = {n: w for n, w in why.items() if w}
            if not failing:
                break
            failed |= failing
        drop = set(failed)
        if src:
            e = None
            res["error"] = "; ".join(src)
    if e is None:
        s["items"][ref] = {"hash": it.hash, "ok": False, "fails": (rec or {}).get("fails", 0) + 1, "path": it.path}
        res.setdefault("error", "no JSON reply")
        save(domain, s)
        return res
    pages = {c.path: wiki.render_concept(c) for n, c in e.concepts.items() if n not in drop}
    if e.source:
        e.source.concepts = [x for x in e.source.concepts if x not in drop]
        pages[e.source.path] = wiki.render_source(e.source)
        recsum.keep(domain, it.key, it.text, e.source.summary)
    pages |= {pg.path: wiki.render_source(pg) for pg in e.sources.values()}
    register = it.path if it.path and not it.key else ""
    if pages or register:
        res["pages"] = write(root, pages, commitmsg.message("wiki", item=it.key or "a new post", n=len(pages)), register)
    key = it.key or (docreg_owner(root, it.path) if register else ref)
    s = state(domain)
    s["items"].pop(ref, None)
    s["items"][key] = {"hash": it.hash, "ok": True, "fails": 0, "path": it.path}
    s["parked"] = [x for x in s["parked"] if x["item"] != key]
    s["parked"] += [{"item": key, "concept": n, "why": failed[n]} for n in sorted(drop)]
    save(domain, s)
    res.update(item=key, parked=sorted(drop), ok=True)
    return res


def docreg_owner(root: Path, path: str) -> str:
    from engram import docreg
    return docreg.load(root).owner(path) or path


def run(domain: str, ask=None, only: list[str] | None = None) -> dict:
    """Compile every due item (or just `only`), one area's run at a time."""
    out = {"compiled": [], "failed": [], "usd": 0.0, "skipped": False}
    with lock(domain) as got:
        if not got:
            out["skipped"] = True
            return out
        root = Path(config.load()[domain].repo)
        for ref in only if only is not None else due(domain, items(root)):
            r = compile_item(domain, ref, ask)
            out["usd"] += r["usd"]
            out["compiled" if r["ok"] else "failed"].append(r)
    return out


def health(domain: str, ask=None) -> dict:
    """The wiki's health check. It arrives with the index."""
    return {"usd": 0.0}


def domain_of(root: Path) -> str | None:
    """The configured domain whose record is `root`."""
    root = Path(root).expanduser().resolve()
    return next((n for n, d in config.load().items() if d.repo and Path(d.repo).expanduser().resolve() == root), None)
