"""Stable ids for the record's documents and for the headings links point at (docs/technical.md, "Stable document ids").

`events/docs.jsonl`, appended to and never edited like links.jsonl, holds one fact per line; the latest line about a
document (or about one of its anchors) wins:

    {"doc": "doc-k7f2qa", "path": "plans/x.md"}                 registered at a path, or moved there
    {"doc": "doc-k7f2qa", "anchor": "h3kq", "heading": "Why"}   a heading given an anchor, or the heading renamed
    {"doc": "doc-k7f2qa", "to": "doc-m4r8vd"}                   the document went into another one
    {"doc": "doc-k7f2qa", "anchor": "h3kq", "to": "doc-m4r8vd#p2xa"}   the section went elsewhere

A path row may carry `thing` (`discovery/D09`), the theory thing the file is, so a renamed thing file still resolves.
A link end is `doc-…` (a whole document) or `doc-…#anchor` (one section). An older end, `path#Heading`, resolves
through every path and heading the registry has held, so links.jsonl is never rewritten."""
import difflib
import fcntl
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engram import commitmsg

REG = "docs.jsonl"
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0, o, 1, l or i, as short names
TEXT_EXT = {".md", ".txt", ".csv"}
ID = re.compile(r"doc-[a-z2-9]{6}")


def _hash(key: str, n: int) -> str:
    x = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    out = ""
    for _ in range(n):
        x, r = divmod(x, len(ALPHABET))
        out += ALPHABET[r]
    return out


def headings(text: str, suffix: str = ".md") -> list[str]:
    """A document's headings as the index names its sections: levels 1–3, a repeated one as `Heading~2`."""
    if suffix != ".md":
        return []
    from engram.sources.sections import md_sections
    used: dict[str, int] = {}
    out = []
    for path, _ in md_sections(text):
        h = path[-1] if path else ""
        if not h:
            continue
        used[h] = used.get(h, 0) + 1
        out.append(h if used[h] == 1 else f"{h}~{used[h]}")
    return out


@dataclass
class Where:
    """Where an end stands now: a document's path, and a heading or None for the whole document."""
    doc: str
    path: str
    heading: str | None

    @property
    def ref(self) -> str:
        return f"{self.path}#{self.heading or ''}"


class Registry:
    def __init__(self, root: Path, text: str | None = None, events_dir: str = "events"):
        self.root = Path(root)
        self.file = self.root / events_dir / REG
        self.rel = f"{events_dir}/{REG}"
        if text is None:
            text = self.file.read_text() if self.file.exists() else ""
        self.rows = [json.loads(l) for l in text.splitlines() if l.strip()]
        self._build()

    @classmethod
    def at(cls, root: Path, rev: str) -> "Registry":
        """The registry as a git revision holds it: `HEAD`, or `` (empty) for what is staged."""
        r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:events/{REG}"], capture_output=True, text=True)
        return cls(root, r.stdout if r.returncode == 0 else "")

    def __bool__(self) -> bool:
        return bool(self.rows)

    def _build(self):
        self.path: dict[str, str] = {}  # doc -> its path now
        self.ever: dict[str, str] = {}  # every path a document has stood at -> the latest to stand there
        self.into: dict[str, str] = {}  # doc -> the document it went into
        self.heading: dict[tuple[str, str], str] = {}  # (doc, anchor) -> its heading now
        self.named: dict[tuple[str, str], str] = {}  # (doc, any heading an anchor has had) -> the latest such anchor
        self.fwd: dict[tuple[str, str], str] = {}  # (doc, anchor) -> where the section went
        self.thing: dict[str, str] = {}
        for r in self.rows:
            self._apply(r)

    def _apply(self, r: dict):
        d = r["doc"]
        if r.get("anchor"):
            k = (d, r["anchor"])
            if r.get("to"):
                self.fwd[k] = r["to"]
            elif r.get("heading") is not None:
                self.heading[k] = r["heading"]
                self.named[(d, r["heading"])] = r["anchor"]
                self.fwd.pop(k, None)
        elif r.get("to"):
            self.into[d] = r["to"]
        elif r.get("path"):
            self.path[d] = r["path"]
            self.ever[r["path"]] = d
            self.into.pop(d, None)
            if r.get("thing"):
                self.thing[r["thing"]] = d

    # reading
    def owner(self, path: str) -> str | None:
        """The document at a path now, else the last one that stood there."""
        now = [d for d, p in self.path.items() if p == path and d not in self.into]
        return now[-1] if now else self.ever.get(path)

    def current(self, doc: str, heading: str) -> str | None:
        """The anchor a document's heading has now."""
        a = self.named.get((doc, heading))
        return a if a and self.heading.get((doc, a)) == heading and (doc, a) not in self.fwd else None

    def resolve(self, end: str) -> Where | None:
        """Where an end stands now: `doc-…`, `doc-…#anchor`, or an old `path#Heading` / `path#` / `path`. None when the
        registry can't place it (an unknown id, or a path it never held)."""
        if ID.match(end):
            doc, _, anc = end.partition("#")
            return self._follow(doc, anc or None, None)
        path, _, heading = end.partition("#")
        doc = self.owner(path)
        if doc is None:
            return None
        if not heading:
            return self._follow(doc, None, None)
        return self._follow(doc, self.named.get((doc, heading)), heading)

    def _follow(self, doc: str, anc: str | None, heading: str | None, depth: int = 0) -> Where | None:
        if depth > 20:
            return None
        if anc and (doc, anc) in self.fwd:
            d2, _, a2 = self.fwd[(doc, anc)].partition("#")
            return self._follow(d2, a2 or None, None, depth + 1)
        if anc:
            heading = self.heading.get((doc, anc), heading)
            if heading is None:
                return None
        if doc in self.into:  # a merged document's section keeps its heading in the one it went into
            d2, _, a2 = self.into[doc].partition("#")
            if a2:
                return self._follow(d2, a2, None, depth + 1)
            return self._follow(d2, self.named.get((d2, heading)) if heading else None, heading, depth + 1)
        if doc not in self.path:
            return None
        return Where(doc, self.path[doc], heading)

    def is_end(self, end: str) -> bool:
        return bool(ID.match(end))

    # writing (each fact appended at once; a store transaction takes the lines back if its commit fails)
    def _append(self, row: dict):
        row = {**row, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
        self.file.parent.mkdir(parents=True, exist_ok=True)
        with self.file.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.rows.append(row)
        self._apply(row)

    def doc_id(self, path: str, thing: str | None = None) -> str:
        """The document's id, given it now if it has none."""
        now = [d for d, p in self.path.items() if p == path and d not in self.into]
        if now:
            return now[-1]
        taken = set(self.path) | set(self.into)
        salt, d = 0, ""
        while not d or d in taken:
            d = "doc-" + _hash(f"{path}\0{salt}", 6)
            salt += 1
        self._append({"doc": d, "path": path, **({"thing": thing} if thing else {})})
        return d

    def anchor(self, doc: str, heading: str) -> str:
        """The heading's anchor, given it now if it has none."""
        if a := self.current(doc, heading):
            return a
        taken = {a for (d, a) in self.heading if d == doc} | {a for (d, a) in self.fwd if d == doc}
        salt, a = 0, ""
        while not a or a in taken:
            a = _hash(f"{doc}\0{heading}\0{salt}", 4)
            salt += 1
        self._append({"doc": doc, "anchor": a, "heading": heading})
        return a

    def end(self, path: str, heading: str | None = None, thing: str | None = None) -> str:
        d = self.doc_id(path, thing)
        return f"{d}#{self.anchor(d, heading)}" if heading else d

    def rename(self, doc: str, old: str, new: str):
        """A heading of a document renamed in place: its anchor carries the new text."""
        self._append({"doc": doc, "anchor": self.current(doc, old) or self.named.get((doc, old)) or self.anchor(doc, old),
                      "heading": new})

    def move(self, doc: str, path: str):
        self._append({"doc": doc, "path": path})


def load(root: Path) -> Registry:
    from engram.store import Store
    return Registry(root, events_dir=Store(root).events_dir)


def thing_of(path: str, patterns: dict) -> str | None:
    """The theory thing a file is, from engram.toml's [nodes] patterns (`discovery = "evidence/{id}-*"`)."""
    for kind, pats in patterns.items():
        for pat in pats if isinstance(pats, list) else [pats]:
            pat = pat.split("#", 1)[0]
            rx = re.escape(pat).replace(re.escape("{id}"), r"(?P<id>[^/]+?)").replace(r"\*", r"[^/]*")
            if m := re.fullmatch(rx, path):
                return f"{kind}/{m.group('id')}"
    return None


def documents(root: Path) -> list[str]:
    """The record's indexed documents (markdown and text files the section source reads), as paths."""
    from engram import config
    from engram.sources import sections
    root = Path(root).resolve()
    d = next((d for d in config.load().values() if d.repo and Path(d.repo).resolve() == root), None)
    if d is None:
        d = config.Domain("record", root, exclude=["events/"])
    return [p.as_posix() for p in sections.files(d) if p.suffix in TEXT_EXT]


def text_at(root: Path, rev: str, path: str) -> str | None:
    """A file as a revision holds it (`HEAD`, `` for staged, None for the working tree); None when it isn't there."""
    if rev is None:
        p = Path(root) / path
        return p.read_text(errors="replace") if p.is_file() else None
    r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


# what links point at
SKIP = ("session:", "link/")


def ends(root: Path, links_text: str | None = None) -> list[tuple[str, str, str]]:
    """(link id, from|to, end) for every link of the record."""
    p = Path(root) / "events" / "links.jsonl"
    text = links_text if links_text is not None else (p.read_text() if p.exists() else "")
    out = []
    for line in text.splitlines():
        if line.strip():
            row = json.loads(line)
            for k in ("from", "to"):
                if row.get(k):
                    out.append((row["id"], k, str(row[k])))
    return out


def classify(end: str, entries: set[str], patterns: dict) -> str:
    base = end.split("#", 1)[0]
    if base in entries:
        return "entry"
    if end.startswith("session:"):
        return "session"
    if end.startswith("link/"):
        return "link"
    if ID.match(end):
        return "id-section" if "#" in end else "id-doc"
    if "#" in end and end.split("#", 1)[1]:
        return "section"
    if "/" in base and Path(base).suffix in TEXT_EXT:
        return "doc"
    if "/" in end and end.split("/", 1)[0] in patterns:
        return "thing"
    return "other"


def target(reg: Registry, end: str, kind: str, root: Path, patterns: dict, rev: str | None = None) -> tuple[str, str | None] | None:
    """(path, heading or None) a document end stands at now, or None when it can't be placed. A thing resolves to its
    file through the registry, else the [nodes] patterns."""
    if kind == "thing":
        if end in reg.thing and (w := reg._follow(reg.thing[end], None, None)):
            return w.path, None
        kind_, _, nid = end.partition("/")
        for pat in patterns.get(kind_) if isinstance(patterns.get(kind_), list) else [patterns.get(kind_)]:
            if not pat:
                continue
            from fnmatch import fnmatchcase
            want = pat.split("#", 1)[0].format(id=nid)
            hit = [p for p in _files(root, rev) if fnmatchcase(p, want)]
            if hit:
                return hit[0], None
        return None
    w = reg.resolve(end)
    if w:
        return w.path, w.heading
    path, _, heading = end.partition("#")
    return (path, heading or None) if kind in ("section", "doc") else None


_FILES: dict = {}


def _files(root: Path, rev: str | None) -> list[str]:
    key = (str(root), rev)
    if key not in _FILES:
        if rev is None:
            args = ["ls-files", "--cached", "--others", "--exclude-standard"]
        elif rev == "":
            args = ["ls-files", "--cached"]
        else:
            args = ["ls-tree", "-r", "--name-only", rev]
        _FILES[key] = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True).stdout.split("\n")
    return _FILES[key]


def check(root: Path) -> dict:
    """Every link end of the record by kind, and those that point at nothing in today's files: a section whose heading
    the file no longer has, a document or thing whose file is gone."""
    from engram.store import Store
    st = Store(root)
    reg = Registry(root, events_dir=st.events_dir)
    patterns = st.config.get("nodes", {})
    entries = {p.stem for p in (Path(root) / st.events_dir).rglob("*.md")}
    _FILES.clear()
    kinds: dict[str, int] = {}
    dangling: dict[str, list] = {}
    heads: dict[str, list[str] | None] = {}
    for lid, side, end in ends(root):
        k = classify(end, entries, patterns)
        kinds[k] = kinds.get(k, 0) + 1
        if k in ("entry", "session", "link", "other"):
            continue
        t = target(reg, end, k, root, patterns)
        ok = False
        if t:
            path, heading = t
            if path not in heads:
                txt = text_at(root, None, path)
                heads[path] = None if txt is None else headings(txt, Path(path).suffix)
            ok = heads[path] is not None and (heading is None or heading in heads[path])
        if not ok:
            dangling.setdefault(k, []).append((lid, side, end))
    return {"kinds": kinds, "dangling": dangling}


def sync(root: Path, dry_run: bool = False) -> dict:
    """Give every indexed document an id and every linked section an anchor, in one store commit (pushed when the
    record pushes). Run at migration and by the hourly job, so a document gets its id when first indexed."""
    from engram.store import Store
    st = Store(root)
    reg = Registry(root, events_dir=st.events_dir)
    patterns = st.config.get("nodes", {})
    entries = {p.stem for p in (Path(root) / st.events_dir).rglob("*.md")}
    docs = [p for p in documents(root) if not p.startswith(st.events_dir + "/")]
    new_docs = [p for p in docs if not any(q == p and d not in reg.into for d, q in reg.path.items())]
    want: list[tuple[str, str]] = []
    heads: dict[str, list[str]] = {}
    for _, _, end in ends(root):
        if classify(end, entries, patterns) != "section":
            continue
        w = reg.resolve(end)
        path, heading = (w.path, w.heading) if w else end.split("#", 1)
        if w and reg.current(w.doc, heading):
            continue
        if path not in heads:
            txt = text_at(root, None, path)
            heads[path] = headings(txt, Path(path).suffix) if txt is not None else []
        if heading in heads[path] and (path, heading) not in want:
            want.append((path, heading))
    out = {"documents": len(new_docs), "anchors": len(want)}
    if dry_run or not (new_docs or want):
        return out
    with st.transaction(message=commitmsg.message("ids", docs=len(new_docs), headings=len(want))) as tx:
        for p in new_docs:
            reg.doc_id(p, thing_of(p, patterns))
        for path, heading in want:
            reg.anchor(reg.doc_id(path, thing_of(path, patterns)), heading)
        tx.extra.append(reg.rel)
    return out


def id_ends(reg: Registry, st, fm: dict) -> dict:
    """A link's front matter with its document ends as ids and their hints (`from_hint`, `to_hint`). Call inside the
    store transaction that adds the link, so the registry lines commit with it."""
    fm = dict(fm)
    for k in ("from", "to"):
        end, hint = as_end(reg, st.root, str(fm.get(k) or ""), st.config.get("nodes", {}))
        if hint:
            fm[k], fm[f"{k}_hint"] = end, hint
    return fm


# moves and renames
class MoveError(ValueError):
    pass


def as_end(reg: Registry, root: Path, x: str, patterns: dict | None = None) -> tuple[str, str | None]:
    """A link end as a new link writes it, with its display hint: a document or one of its sections (`path`, `path#`,
    `path#Heading`) becomes `doc-…` or `doc-…#anchor`, given an id and anchor now if it has none, with the path and
    heading as the hint; anything else (an entry, a thing, a session line, an id end) is kept as it is."""
    if not x or ID.match(x) or x.startswith(SKIP):
        return x, None
    path, _, heading = x.partition("#")
    if Path(path).suffix not in TEXT_EXT:
        return x, None
    txt = text_at(root, None, path)
    if txt is None:
        w = reg.resolve(x)  # an old end whose file moved: the id of where it went
        if not w:
            raise MoveError(f"{path} isn't in the record")
        path, heading, txt = w.path, w.heading or "", text_at(root, None, w.path) or ""
    if heading and heading not in headings(txt, Path(path).suffix):
        raise MoveError(f"{path} has no heading {heading!r}; its headings: {', '.join(headings(txt, Path(path).suffix)) or 'none'}")
    return reg.end(path, heading or None, thing_of(path, patterns or {})), f"{path}#{heading}" if heading else path


def record_move(reg: Registry, root: Path, old: str, new: str, patterns: dict | None = None) -> list[dict]:
    """Record where a document or heading went: `old.md new.md`, `old.md#Heading new.md#Heading` or
    `old.md#Heading new.md` (the section folded into a whole document). Returns the rows appended."""
    patterns = patterns or {}
    before = len(reg.rows)
    opath, _, ohead = old.partition("#")
    npath, _, nhead = new.partition("#")
    ntext = text_at(root, None, npath)
    if ntext is None:
        raise MoveError(f"{npath} isn't in the record")
    if nhead and nhead not in headings(ntext, Path(npath).suffix):
        raise MoveError(f"{npath} has no heading {nhead!r}; its headings: {', '.join(headings(ntext, Path(npath).suffix)) or 'none'}")
    doc = reg.owner(opath) or reg.doc_id(opath, thing_of(opath, patterns))
    if not ohead:
        if nhead:
            raise MoveError("a whole document goes to a document, not a heading")
        other = reg.owner(npath)
        if other and other != doc and reg.path.get(other) == npath and other not in reg.into:
            reg._append({"doc": doc, "to": other})
        elif reg.path.get(doc) != npath:
            reg.move(doc, npath)
        return reg.rows[before:]
    anc = reg.current(doc, ohead) or reg.named.get((doc, ohead)) or reg.anchor(doc, ohead)
    owner = reg.owner(npath)
    d2 = owner if owner and reg.path.get(owner) == npath else reg.doc_id(npath, thing_of(npath, patterns))
    if d2 == doc and nhead:
        if reg.heading.get((doc, anc)) != nhead or (doc, anc) in reg.fwd:
            reg._append({"doc": doc, "anchor": anc, "heading": nhead})
    elif nhead:
        reg._append({"doc": doc, "anchor": anc, "to": f"{d2}#{reg.anchor(d2, nhead)}"})
    else:
        reg._append({"doc": doc, "anchor": anc, "to": d2})
    return reg.rows[before:]


def moved(root: Path, old: str, new: str) -> str:
    """`engram moved`: record it. With other changes staged it is staged beside them, for that commit; otherwise it is
    committed (and pushed) on its own."""
    from engram.store import Store
    st = Store(root)
    staged = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"]).returncode != 0
    reg = Registry(root, events_dir=st.events_dir)
    if staged:
        rows = record_move(reg, root, old, new, st.config.get("nodes", {}))
        if rows:
            subprocess.run(["git", "-C", str(root), "add", "--", reg.rel], check=True)
        return f"recorded {old} → {new} ({len(rows)} line{'s' * (len(rows) != 1)}), staged with your change"
    with st.transaction(message=commitmsg.message("moved", old=old, new=new)) as tx:
        rows = record_move(reg, root, old, new, st.config.get("nodes", {}))
        tx.extra.append(reg.rel)
    return f"recorded {old} → {new} ({len(rows)} line{'s' * (len(rows) != 1)}), committed"


def _ends(n: int) -> str:
    return f"{n} link end{'s' * (n != 1)} point{'s' * (n == 1)}"


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def staged_problems(root: Path) -> tuple[list[str], list[str]]:
    """The pre-commit's rename and move check: (problems, what was recorded on its own). A staged change that deletes or
    moves a document a link points at, or renames or removes a heading one points at, is refused unless the staged
    registry says where it went. A pure `git mv`, any move git sees of a document with an id that no link points at (a
    draft published), and a one-to-one heading rename (the only heading gone and the only one new, in the same place,
    alike) are recorded and staged here. Each problem names the command that fixes it."""
    root = Path(root)
    head, staged = Registry.at(root, "HEAD"), Registry.at(root, "")
    if not head and not staged:
        return [], []  # a record without stable ids yet
    from engram.store import Store
    st = Store(root)
    patterns = st.config.get("nodes", {})
    out = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-status", "-M", "--diff-filter=DRM"],
                         capture_output=True, text=True, check=True).stdout
    changes = [l.split("\t") for l in out.splitlines() if l.strip()]
    changes = [c for c in changes if any(Path(p).suffix in TEXT_EXT and not p.startswith(st.events_dir + "/") for p in c[1:])]
    if not changes:
        return [], []
    links_text = text_at(root, "", f"{st.events_dir}/links.jsonl") or ""
    entries = {Path(p).stem for p in _files_fresh(root, "") if p.startswith(st.events_dir + "/") and p.endswith(".md")}
    _FILES.clear()
    # what the links point at, as HEAD stood
    whole: dict[str, int] = {}
    secs: dict[tuple[str, str], int] = {}
    for _, _, end in ends(root, links_text):
        k = classify(end, entries, patterns)
        if k in ("entry", "session", "link", "other"):
            continue
        t = target(head, end, k, root, patterns, "HEAD")
        if not t:
            continue
        whole[t[0]] = whole.get(t[0], 0) + 1
        if t[1]:
            secs[(t[0], t[1])] = secs.get((t[0], t[1]), 0) + 1
    can_fix = Path(os.environ.get("GIT_INDEX_FILE", "index")).name in ("index", "index.lock")
    work = Registry(root, events_dir=st.events_dir)
    problems, fixed = [], []

    def lands(reg: Registry, end: str) -> bool:
        w = reg.resolve(end)
        if not w:
            return False
        txt = text_at(root, "", w.path)
        return txt is not None and (w.heading is None or w.heading in headings(txt, Path(w.path).suffix))

    added = [l.split("\t")[1] for l in subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-status", "-M",
                                                       "--diff-filter=A"], capture_output=True, text=True).stdout.splitlines() if l]
    for c in changes:
        status, old = c[0], c[1]
        new = c[2] if len(c) == 3 else (None if status == "D" else old)
        n = whole.get(old, 0)
        if new and new != old and not n and status.startswith("R") and can_fix and head.owner(old) \
                and not lands(staged, f"{old}#"):  # a document with an id moved, though no link points at it yet
            record_move(work, root, old, new, patterns)
            fixed.append(f"{old} → {new} (a move)")
            staged = Registry(root, work.file.read_text())
        if new != old and n:  # deleted or moved
            if not lands(staged, f"{old}#"):
                if new and status == "R100" and can_fix:
                    record_move(work, root, old, new, patterns)
                    fixed.append(f"{old} → {new} (a pure move)")
                    staged = Registry(root, work.file.read_text())
                elif new:
                    problems.append(f"{old} moved to {new}, and {_ends(n)} at it. Record it:\n"
                                    f"    engram moved {_q(old)} {_q(new)}")
                else:
                    cands = sorted(added, key=lambda p: -difflib.SequenceMatcher(None, old, p).ratio())[:3]
                    cmd = "\n".join(f"    engram moved {_q(old)} {_q(p)}" for p in cands) or \
                        f"    engram moved {_q(old)} '<the file it went into>'"
                    problems.append(f"{old} is deleted, and {_ends(n)} at it. Record where it went:\n{cmd}")
        if new is None:
            continue
        before_t, after_t = text_at(root, "HEAD", old), text_at(root, "", new)
        if before_t is None or after_t is None:
            continue
        hb, ha = headings(before_t, Path(old).suffix), headings(after_t, Path(new).suffix)
        gone = [h for h in hb if h not in ha]
        fresh = [h for h in ha if h not in hb]
        for h in gone:
            m = secs.get((old, h), 0)
            if not m or lands(staged, f"{old}#{h}"):
                continue
            one = len(gone) == 1 and len(fresh) == 1 and hb.index(h) == ha.index(fresh[0]) \
                and difflib.SequenceMatcher(None, h.lower(), fresh[0].lower()).ratio() >= 0.5
            if one and can_fix and (new == old or lands(staged, f"{old}#")):
                record_move(work, root, f"{old}#{h}", f"{new}#{fresh[0]}", patterns)
                fixed.append(f"{new}: “{h}” → “{fresh[0]}” (a one-to-one rename)")
                staged = Registry(root, work.file.read_text())
                continue
            prev = next((x for x in reversed(hb[:hb.index(h)]) if x in ha), None)  # the section that took its text
            cands = list(dict.fromkeys([*sorted(fresh, key=lambda x: -difflib.SequenceMatcher(None, h.lower(), x.lower()).ratio())[:2],
                                        *([prev] if prev else [])]))
            cmd = "\n".join(f"    engram moved {_q(old + '#' + h)} {_q(new + '#' + x)}" for x in cands) or \
                f"    engram moved {_q(old + '#' + h)} {_q(new)}"
            problems.append(f"{new} no longer has the heading “{h}”, and {_ends(m)} at it. "
                            f"Record where it went (or into the whole file, `engram moved {_q(old + '#' + h)} {_q(new)}`):\n{cmd}")
    if fixed:
        subprocess.run(["git", "-C", str(root), "add", "--", work.rel], check=True)
    return problems, fixed


def _files_fresh(root: Path, rev: str) -> list[str]:
    _FILES.pop((str(root), rev), None)
    return _files(root, rev)
