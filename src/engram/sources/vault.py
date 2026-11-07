"""An Obsidian vault read as it stands (docs/search.md, "A vault read as it stands"): a folder with `.obsidian/` and no
record of engram's in it. Nothing in it is written. Its own constructs map onto pieces engram already has:
- a `#tag` (inline or in the frontmatter's `tags`, `#a/b` also on `a`) goes in its section's `tags` column, and is a
  thread its sections sit on when the owner says so or the default rule (`_stories`) takes it;
- a daily note (a file named by its date) and a date property date the sections that carry no date of their own;
- a note is a way in: its name and `aliases` name it, and it lights its own sections and every section that links to it;
- a frontmatter key or `key:: [[note]]` field named after one of `RELS` is that typed link, from the note holding it;
- every other `[[wikilink]]`, `![[embed]]` or `[text](note)`, in the text or a frontmatter value, is untyped: a backlink,
  never a link row.

The owner's reading of a vault, its map, lives in engram's config folder (`Reading`, `load_map`), never in the vault."""
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

from engram import dates, frontmatter
from engram.index import Doc
from engram.pack import Link, Way
from engram.paths import record_toml, vault_map

MARK = ".obsidian"
SKIP = (f"{MARK}/", ".trash/")  # the app's settings and its trash
TEMPLATES = (("templates.json", "folder"), ("plugins/templater-obsidian/data.json", "templates_folder"))  # where a vault says its templates are
WIKI = re.compile(r"!?\[\[([^\[\]]+?)\]\]")
MDLINK = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'(][^)]*)?\s*\)")  # `(note)`, `(<a note.md>)`, `(note.md "its title")`
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.I)
ANY_LINK = re.compile(r"!?\[\[[^\[\]]*\]\]|\]\([^)]*\)")  # a heading anchor in one of these isn't a tag
TAG = re.compile(r"(?<![\w/#&:=\"'])#([\w/-]*[^\W\d][\w/-]*)")  # at least one character that isn't a digit; never a colour in markup
FIELD = re.compile(r"^\s*([\w-]+)::\s+(.+)$", re.M)  # a space after it, so `pkg::func()` isn't a field
CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.S)
RELS = {"supersedes": "evidence", "revises": "evidence", "disagrees": "evidence", "led-to": "timeline"}  # rel -> family
# Which tags are threads when the owner hasn't said (docs/technical.md, "A vault's default rule"). A timeline is read
# whole, so a tag or note reaching more sections than it could read is a category; and a tag on a big share of the notes
# says what kind of note they are, not what story they're on.
MOST_ROWS, MOST_SHARE, FLOOR = 90, 0.05, 40
READINGS = {"tags": {"story", "category", "name", "out", "default"}, "folders": {"out", "default"},
            "properties": {"date", "who", "default", *RELS}}


def is_vault(repo: Path | None) -> bool:
    """A record repo is never read as a vault, so a compiled wiki read in Obsidian keeps its index exactly."""
    return bool(repo) and (Path(repo) / MARK).is_dir() and not record_toml(repo).exists()


def _problems(m: dict) -> list[str]:
    """Why a reading map can't be used: only `jobs`, `[read]` and `[lenses]`, weights left unset, and each reading one
    the reader knows."""
    out = [f"[{k}] isn't a table a reading map holds" for k in m if k not in ("jobs", "read", "lenses")]
    if not isinstance(m.get("jobs", []), list):
        out.append("jobs isn't a list")
    read = m.get("read", {})
    for table, entries in read.items() if isinstance(read, dict) else [("read", None)]:
        if table not in READINGS or not isinstance(entries, dict):
            out.append(f"[read.{table}] isn't a table a reading map holds")
            continue
        out += [f"{k} = {v!r} isn't a reading of {table}" for k, v in entries.items() if not isinstance(v, str) or v not in READINGS[table]]
    lenses = m.get("lenses", {})
    for name, lens in lenses.items() if isinstance(lenses, dict) else [("?", None)]:
        weights = lens.get("weights", {}) if isinstance(lens, dict) else None
        if not isinstance(weights, dict) or any(not k.startswith(("tag:", "file:")) or not isinstance(v, (int, float)) or isinstance(v, bool)
                                                or v <= 0 for k, v in weights.items()):
            out.append(f"lens {name} may only lift by tag: or file:")
    return out


def load_map(domain: str) -> tuple[dict, str | None]:
    """(the vault's reading map, why it isn't used). A map engram can't use is ignored, whole: the default rule reads the
    vault, and health says why. Read each time: quotes are checked only when it's saved."""
    p = vault_map(domain)
    try:
        m = tomllib.loads(p.read_text()) if p.exists() else {}
    except (OSError, ValueError) as e:
        return {}, f"it doesn't load: {e}"
    return ({}, "; ".join(why)) if (why := _problems(m)) else (m, None)


class Reading:
    """How the owner said a vault is read. An empty map is the default rule."""

    def __init__(self, m: dict | None = None):
        read = (m or {}).get("read", {})
        self.tags = {k.lstrip("#").lower(): v for k, v in read.get("tags", {}).items() if v != "default"}
        self.out_folders = [k.strip("/") + "/" for k, v in read.get("folders", {}).items() if v == "out"]
        self.props = {k.lower(): v for k, v in read.get("properties", {}).items() if v != "default"}
        self.rels = {**{r: r for r in RELS if r not in self.props}, **{k: v for k, v in self.props.items() if v in RELS}}
        self.date_props = [k for k, v in {"date": "date", **self.props}.items() if v == "date"]
        self.who_props = [k for k, v in self.props.items() if v == "who"]

    def of(self, tag: str) -> str | None:
        """A tag's reading: its own, else the nearest parent's."""
        parts = tag.split("/")
        return next((self.tags[p] for i in range(len(parts), 0, -1) if (p := "/".join(parts[:i])) in self.tags), None)

    def expand(self, written: list[str]) -> list[str]:
        """Tags as written, lower-cased, with every parent they nest under (`a/b` is also on `a`), the left-out ones gone
        along with what they'd bring."""
        out = []
        for t in written:
            parts = t.lower().strip("/").split("/")
            if self.of("/".join(parts)) != "out":
                out += ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
        return list(dict.fromkeys(t for t in out if t and self.of(t) != "out"))


def skip(repo: Path | None, domain: str = "") -> list[str]:
    """What a vault keeps that isn't read: the app's folders, its templates folder and, for a domain named, the folders
    its owner left out."""
    if not is_vault(repo):
        return []
    out = [*SKIP, *(Reading(load_map(domain)[0]).out_folders if domain else [])]
    for conf, key in TEMPLATES:
        try:
            if folder := json.loads((Path(repo) / MARK / conf).read_text()).get(key):
                out.append(folder.strip("/") + "/")
        except (OSError, ValueError, AttributeError):
            pass
    return out


def _list(v, sep: str = r"[,\s]+") -> list[str]:
    """A frontmatter value as a list: `[a, b]`, `a, b` or a single value."""
    items = v if isinstance(v, list) else re.split(sep, v) if isinstance(v, str) else []
    return [str(x).strip().lstrip("#") for x in items if str(x).strip()]


def _note(text: str) -> tuple[dict, str]:
    try:
        fm, body = frontmatter.split(text)
    except Exception:  # a vault's frontmatter isn't checked by anyone; a broken one is read as text
        return {}, text
    return {str(k).lower(): v for k, v in (fm or {}).items()}, body  # Obsidian's property names ignore case


def inline_tags(text: str) -> list[str]:
    return TAG.findall(ANY_LINK.sub(" ", CODE.sub("", re.sub(r"^#{1,6}\s", "", text, flags=re.M))))


def _targets(text: str) -> list[tuple[str, str]]:
    """(name, heading) for each link a text holds, wikilinks and markdown links alike. In a table a wikilink's `|` is `\\|`."""
    out = []
    for m in WIKI.finditer(CODE.sub("", text)):
        name, _, head = re.split(r"\\?\|", m.group(1), maxsplit=1)[0].partition("#")
        out.append((name.strip(), head.split("#")[-1].lstrip("^").strip()))
    for m in MDLINK.finditer(CODE.sub("", text)):
        if not SCHEME.match(to := m.group(1).strip("<>")):
            name, _, head = to.partition("#")
            out.append((unquote(name), unquote(head)))
    return out


def _text(value) -> str:
    """A property's value as text. YAML reads an unquoted `[[Old]]` as a list in a list: it's the link it looks like."""
    if isinstance(value, list):
        return " ".join(f"[[{_text(x[0])}]]" if isinstance(x, list) and len(x) == 1 else _text(x) for x in value)
    return str(value)


def _daily_name(repo: Path) -> re.Pattern | None:
    """The name the daily notes plugin gives a note when its format is all digits (`DD.MM.YYYY`), the default's aside."""
    try:
        last = json.loads((repo / MARK / "daily-notes.json").read_text()).get("format", "").rsplit("/", 1)[-1]
    except (OSError, ValueError, AttributeError):
        return None
    parts = re.split("(YYYY|MM|DD)", last)
    if {"YYYY", "MM", "DD"} - set(parts) or any(re.search(r"[A-Za-z\[]", x) for x in parts[::2]):
        return None
    groups = {"YYYY": r"(?P<y>\d{4})", "MM": r"(?P<m>\d{2})", "DD": r"(?P<d>\d{2})"}
    return re.compile("".join(groups.get(x, re.escape(x)) for x in parts))


class Names:
    """A link's name to the note Obsidian opens for it, in the order its `getLinkpathDest` tries: the only note of that
    name, a path relative to the linking note, an exact path, else the notes whose path ends with it, those under the
    linking note's folder first and the shortest of each first."""

    def __init__(self, notes: list[str]):
        self.by_name: dict[str, list[str]] = {}
        for n in sorted(notes):
            self.by_name.setdefault(n.rsplit("/", 1)[-1].lower(), []).append(n)

    def find(self, name: str, src: str) -> str | None:
        if not name:
            return src  # [[#Heading]]: a heading in the note itself
        n = name.lower()
        last = n.rsplit("/", 1)[-1]
        cands = self.by_name.get(last) if "." in last else None
        if not cands:
            n += ".md"
            last = n.rsplit("/", 1)[-1]
            cands = self.by_name.get(last)
        if not cands:
            return None
        if n == last and len(cands) == 1:
            return cands[0]
        here = src.lower().rpartition("/")[0]
        if n.startswith(("./", "../")):
            n = n.removeprefix("./") if n.startswith("./../") else n
            if n.startswith("./"):
                n = n[2:]
            while n.startswith("../"):
                n, here = n[3:], here.rpartition("/")[0]
            here += "/" if here else ""
            n = here + n
            if hit := next((c for c in cands if c.lower() == n), None):
                return hit  # a relative link that misses goes on as a path, as Obsidian's does
        n = n.removeprefix("/")
        if hit := next((c for c in cands if c.lower() == n), None):
            return hit
        if name.startswith("/"):
            return None
        fit = sorted((c for c in cands if c.lower().endswith(n)), key=lambda c: (not c.lower().startswith(here), len(c)))
        return fit[0] if fit else None


def _named(value) -> str:
    """A person or source a property names: the note's display text when it's a link."""
    text = _text(value)
    m = WIKI.search(text)
    return (m.group(1).split("|")[-1] if m else text).strip()


def _on(d: Doc) -> list[str]:
    return [t for t in d.stories.split(",") if t]


def _stories(by_file: dict[str, list[Doc]], reading: Reading, links_of: dict[int, list[str]], daily: set[str]) -> None:
    """Which tags are threads. The owner's say first; a tag they didn't mention goes by the default rule (docs/technical.md,
    "A vault's default rule"). A dated section with no thread of its own, a daily note's line, sits on the most specific
    threads of the notes it links to, as far as each has room."""
    every = [d for secs in by_file.values() for d in secs]
    of = {id(d): f for f, secs in by_file.items() for d in secs}
    notes: dict[str, set[str]] = {}
    rows: dict[str, set[str]] = {}
    for d in every:
        for t in _on(d):
            notes.setdefault(t, set()).add(of[id(d)])
            rows.setdefault(t, set()).add(d.parent or d.ref)
    room = max(FLOOR, MOST_SHARE * len(by_file))
    told = lambda t: reading.of(t) == "story"
    drop = {t for t in notes if not told(t) and (len(notes[t]) > room or len(rows[t]) > MOST_ROWS)}
    for d in every:
        d.stories = ",".join(t for t in _on(d) if t not in drop)
    of_note = {f: {t for d in secs for t in _on(d)} for f, secs in by_file.items()}
    specific = {f: sorted(t for t in ts if not any(o.startswith(t + "/") for o in ts)) for f, ts in of_note.items()}
    borrow = {id(d): list(dict.fromkeys(t for to in links_of.get(id(d), []) if to not in daily for t in specific[to]))
              for d in every if not d.stories and d.date}
    for d in every:
        for t in borrow.get(id(d), ()):
            notes.setdefault(t, set()).add(of[id(d)])
            rows.setdefault(t, set()).add(d.parent or d.ref)
    full = {t for t in rows if not told(t) and len(rows[t]) > MOST_ROWS}
    alone = {t for t in rows if not told(t) and len(notes[t]) < 2}  # a thread joins notes; one note is reached by its name
    for d in every:
        d.stories = d.stories or ",".join(t for t in borrow.get(id(d), ()) if t not in full)
        d.stories = ",".join(t for t in _on(d) if t not in alone)


def read(repo: Path, docs: list[Doc], reading: Reading | None = None) -> tuple[list[Doc], list[Link], list[Way], dict]:
    """The vault's sections as `sections.docs_for` cut them, filled with what the vault says (threads and tags, dates, who
    said it, aliases as search terms, the frontmatter left out of the text), with the typed links and ways in among them."""
    reading = reading or Reading()
    by_file: dict[str, list[Doc]] = {}
    for d in docs:
        if d.cls == "section" and d.ref.split("#", 1)[0].endswith(".md"):
            by_file.setdefault(d.ref.split("#", 1)[0], []).append(d)
    names = Names(list(by_file))
    daily_name = _daily_name(repo)
    meta: dict[str, dict] = {}
    named_tags: dict[str, list[str]] = {}
    for f, secs in by_file.items():
        text = (repo / f).read_text(errors="replace")
        fm, body = _note(text)
        if fm and secs[0].body.startswith("---\n"):  # the frontmatter is read below, not searched as text
            secs[0].body = secs[0].body[len(text) - len(body):]
        stem = Path(f).stem
        named = daily_name.fullmatch(stem) if daily_name else None
        day = f"{named['y']}-{named['m']}-{named['d']}" if named else None
        day = (day if day and dates.valid(day) else None) or (dates.first_in(stem) if re.match(r"\d{4}-\d{2}", stem) else None)  # named by its date, as a daily note is
        when = day or next((str(fm[k])[:10] for k in reading.date_props if dates.valid(str(fm.get(k, ""))[:10])), None)
        who = next((_named(fm[k]) for k in reading.who_props if fm.get(k)), "")
        own = _list(fm.get("tags") or fm.get("tag") or [])
        aliases = _list(fm.get("aliases") or fm.get("alias") or [], r"\s*,\s*")
        meta[f] = {"fm": fm, "aliases": aliases, "daily": bool(named or dates.DATE.match(stem)), "text": text}
        inline_of: dict[str, list[str]] = {}  # a section cut into chunks carries each tag on all of them
        for d in secs:
            inline_of.setdefault(d.parent or d.ref, []).extend(inline_tags(d.body))
        for d in secs:
            if when and not d.date:
                d.date, d.date_key = when, dates.key(when)
            if who:
                d.author = who
            inline = inline_of[d.parent or d.ref]
            tags = reading.expand([*own, *inline])
            d.stories = ",".join(t for t in tags if reading.of(t) in (None, "story"))
            d.tags = " ".join([stem, *aliases, *(f"#{t}" for t in tags)])
            for t in inline:  # left out means left out: its words aren't there to search or read, heading included
                if reading.of(t.lower().strip("/")) == "out":
                    gone = rf"\s*(?<![\w/#&])#{re.escape(t)}(?![\w/-])"
                    d.body = re.sub(gone, "", d.body)
                    for o in secs:  # a section's title carries the headings above it
                        o.title = re.sub(gone, "", o.title)
                    file, _, head = d.ref.partition("#")
                    clean = f"{file}#{re.sub(gone, '', head)}"
                    if clean not in {x.ref for x in secs}:  # a heading of that name beside it keeps its address
                        d.ref, d.parent = clean, d.parent and f"{file}#{re.sub(gone, '', d.parent.partition('#')[2])}"
            for t in tags:
                if reading.of(t) == "name":
                    named_tags.setdefault(t, []).append(d.parent or d.ref)
    by_file = {f: [d for d in secs if d.body.strip()] or secs[:1] for f, secs in by_file.items()}
    first = {f: (secs[0].parent or secs[0].ref) for f, secs in by_file.items()}

    def ends(f: str, head: str) -> list[str]:
        if head:
            hit = [r for r in dict.fromkeys(d.parent or d.ref for d in by_file[f]) if r.split("#", 1)[1].split("~")[0].lower() == head.lower()]
            if hit:
                return hit[:1]
        return [first[f]]

    links, backlinks, unresolved, typed = [], {f: set() for f in by_file}, 0, 0
    superseded: set[str] = set()
    links_of: dict[int, list[str]] = {}
    for f, secs in by_file.items():
        fm = meta[f]["fm"]
        fields = [*fm.items(), *((k.lower(), v) for k, v in FIELD.findall(CODE.sub("", meta[f]["text"])))]
        for prop, value in fields:
            rel = reading.rels.get(prop)
            for name, head in _targets(_text(value)):
                if not (to := names.find(name, f)) or to == f:
                    continue
                if rel is None:
                    if prop in fm:  # the text isn't searched for it, as a `key::` field's is
                        backlinks[to].add(first[f])
                    continue
                typed += 1
                olds = [d.parent or d.ref for d in by_file[to]] if not head else ends(to, head)
                links += [Link(first[f], o, rel) for o in dict.fromkeys(olds)]
                if rel == "supersedes":
                    superseded |= set(olds)
        for d in secs:
            linked = []
            for name, head in _targets(d.body):
                to = names.find(name, f)
                if to is None:
                    unresolved += 1
                elif to != f:
                    backlinks[to].add(d.parent or d.ref)
                    linked.append(to)
            links_of[id(d)] = linked
    _stories(by_file, reading, links_of, {f for f in by_file if meta[f]["daily"]})
    for secs in by_file.values():
        for d in secs:
            d.superseded = int((d.parent or d.ref) in superseded) or d.superseded
    ways = [Way("note", f.removesuffix(".md").lower(), [Path(f).stem, *meta[f]["aliases"]],  # by path: two notes may share a name
                [d.parent or d.ref for d in by_file[f]] + (sorted(backlinks[f]) if len(backlinks[f]) <= MOST_ROWS else []))
            for f in by_file if not meta[f]["daily"]]
    ways += [Way("tag", t, [re.sub(r"[-_]", " ", t.rsplit("/", 1)[-1])], list(dict.fromkeys(refs))) for t, refs in named_tags.items()]  # by its last word
    kept = {id(d) for secs in by_file.values() for d in secs}
    docs = [d for d in docs if id(d) in kept or not (d.cls == "section" and d.ref.split("#", 1)[0].endswith(".md"))]
    return docs, links, ways, {"notes": len(by_file), "typed links": typed, "backlinks": sum(map(len, backlinks.values())), "unresolved": unresolved}


def sync_links(idx, links: list[Link]) -> None:
    """The vault's typed links, after the story graph, which rebuilds the two families they sit in."""
    with idx.db:
        idx.db.executemany("INSERT INTO link (from_ref, to_ref, family, rel, story, event, note) VALUES (?, ?, ?, ?, '', '', ?)",
                           [(l.from_ref, l.to_ref, RELS[l.rel], l.rel, l.note) for l in links])
