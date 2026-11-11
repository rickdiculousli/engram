"""The ways into a record besides matching words (.engram/README.md, "How answers are built"): a clinician, a
treatment or medication, a test, a theory node, the owner's words for a symptom. Each way in is a key with the phrases that
name it and the records it lights: records it wrote or that mention it, the series or file it has, the theory links on
it. A question naming one of the phrases lights those records directly.

The record's engram.toml declares where each kind comes from (`[ways.<kind>]`); people come from `[people]`, each with
`say`, the words that name them in text, and `roles`, what the owner calls them ("massage therapist" for the bodyworker): a
role names the person in a question, but a record using the word isn't counted as mentioning them, since a role is
often shared."""
import json
import re
from fnmatch import fnmatchcase

from engram import threads
from engram.config import Domain

SCHEMA = """
CREATE TABLE IF NOT EXISTS way (kind TEXT NOT NULL, key TEXT NOT NULL, phrase TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS way_phrase ON way(phrase);
CREATE TABLE IF NOT EXISTS way_ref (kind TEXT NOT NULL, key TEXT NOT NULL, ref TEXT NOT NULL, PRIMARY KEY (kind, key, ref));
"""
MAX_WORDS = 4  # a longer phrase (a quoted sentence) never turns up whole in a question, so it doesn't name a way in
LINKED = ("note", "tag", "thread")  # a vault's, and a thread the filer made: they light what links to them or carries
# them, never mere mentions (their names are everyday words: "dad", "work")
FORMS = {"topical", "oral", "cream", "ointment", "solution", "drops", "spray", "gel", "foam", "shampoo", "tablet", "capsule"}


def recurring(conf: dict) -> tuple[str, str] | None:
    """Where a record keeps its recurring symptoms, from `[ways.symptom] pages` ("complaints/*#Occurrences"): the
    folder of their pages and the section listing each one's occurrences; None when it keeps none."""
    pat = next(iter((conf.get("ways") or {}).get("symptom", {}).get("pages", [])), "")
    folder, _, section = pat.partition("/*")
    return (folder, section.removeprefix(".md").lstrip("#")) if folder and section else None


def page(conf: dict, slug: str) -> str:
    """A recurring symptom's occurrences section, by its slug."""
    folder, section = recurring(conf) or ("", "")
    return f"{folder}/{slug}.md#{section}"


def _phrases(*names: str) -> list[str]:
    out = []
    for n in names:
        n = re.sub(r"\s+", " ", re.sub(r"[\d.]+\s*(%|mg|mcg)|[()]", " ", n)).strip(" ,;-").lower()
        if n and len(n) > 2 and len(n.split()) <= MAX_WORDS and n not in FORMS:
            out.append(n)
    return list(dict.fromkeys(out))


def entity_phrases(entity: str, whole: bool = False) -> list[str]:
    """What names a medication in text: its brand, its generic (the bracket's first part), and the first word of a long
    brand ("olopatadine" of a long name). A name kept whole (the pack's `whole_names`) is named by itself alone, at any
    length: a practice is said by its whole name, and four words of it name something else."""
    if whole:
        n = " ".join(entity.lower().split())
        return [n] if len(n) > 2 else []
    brand, _, generic = entity.partition("(")
    first = brand.split()[0] if len(brand.split()) > 1 and len(brand.split()[0]) >= 6 else ""
    return _phrases(brand, generic.split(",")[0], first)


def _keys(d: Domain, conf: dict, docs: list[tuple]) -> dict[tuple[str, str], dict]:
    """(kind, key) -> {phrases, refs}: what names each way in, and the records it lights before mentions."""
    from engram import pack
    repo, ways, out = d.repo, conf.get("ways") or {}, {}
    refs = [r for r, *_ in docs]
    whole = pack.load(d.name).current.whole_names
    called = lambda entity: entity.strip().lower() if whole else entity.partition("(")[0].strip().lower()

    def add(kind, key, phrases, lit=(), roles=()):
        w = out.setdefault((kind, key), {"phrases": [], "refs": set(), "roles": []})
        w["phrases"] += [p for p in phrases if p not in w["phrases"]]
        w["roles"] += [p for p in roles if p not in w["roles"] and p not in w["phrases"]]
        w["refs"] |= set(lit)

    for pid, p in (conf.get("people") or {}).items():
        aliases = {a.lower() for a in p.get("aliases", [])}
        add("person", pid, _phrases(*p.get("say", [])),
            [r for r, _, author in docs if (author.split(":", 1)[1] if ":" in author else author).lower() in aliases],
            _phrases(*p.get("roles", [])))
    if t := ways.get("treatment"):
        for f in t.get("lists", []):
            for n, line in enumerate((repo / f).read_text().splitlines() if (repo / f).exists() else [], 1):
                if line.strip():
                    entity = json.loads(line).get("entity", "")
                    add("treatment", called(entity), entity_phrases(entity, whole), [f"{f}:{n}"])
        if t.get("entities"):  # entries naming a medication (a med-change's entity), once log pages are gone
            from engram.store import Store
            for e in Store(repo).events(kind=t["entities"]):
                entity = str(e.fm.get("entity", ""))
                if entity:
                    add("treatment", called(entity), entity_phrases(entity, whole), [e.id])
        if t.get("series_about"):  # a treatment series: every entry about it
            from engram.store import Store
            for e in Store(repo).events():
                for a in e.about:
                    if a.startswith("series/") and not a.split("/", 1)[1].startswith("_") and a != "series/meds" and e.kind != "link":
                        name = a.split("/", 1)[1].replace("-", " ")
                        add("treatment", name, _phrases(name), [e.id])
        for pat in t.get("series_docs", []):  # a treatment's own document
            for r in refs:
                if fnmatchcase(r, pat):
                    stem = r.split("#", 1)[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    add("treatment", stem.replace("-", " "), _phrases(stem.replace("-", " ")), [r])
        for pat in t.get("series", []):
            for r in refs:
                if fnmatchcase(r, pat) and not r.rsplit("/", 1)[-1].startswith("_"):
                    stem = r.split("#", 1)[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    add("treatment", stem.replace("-", " "), _phrases(stem.replace("-", " ")), [r])
    for pat in (ways.get("theory") or {}).get("threads", []):  # a loop or condition by its name: its own file
        from engram import frontmatter
        for f in sorted(repo.glob(pat + ".md")) if repo else []:
            fm, _ = frontmatter.split(f.read_text())
            if fm and fm.get("id"):
                rel = f.relative_to(repo).as_posix()
                add("theory", fm["id"], _phrases(*[str(s) for s in fm.get("say") or []]), [r for r in refs if r.split("#", 1)[0] == rel])
    for pat in (ways.get("test") or {}).get("files", []):
        for r in refs:
            if fnmatchcase(r.split("#", 1)[0], pat):
                stem = r.split("#", 1)[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                name = re.sub(r"[-_]?\d{4}(-\d\d)?(-\d\d)?.*$", "", stem).replace("-", " ").replace("_", " ")
                add("test", name, _phrases(name), [r])
    for pat in (ways.get("symptom") or {}).get("pages", []):
        for r in refs:
            if fnmatchcase(r, pat):
                slug = r.split("#", 1)[0].rsplit("/", 1)[-1].removesuffix(".md")
                add("symptom", slug, _phrases(slug.replace("-", " ")), [r])
    return out


def sync(idx, d: Domain, conf: dict, more: list = ()) -> int:
    """Rebuild the ways in: their phrases, and every record each lights, mentions included. `more` are the ways a pack's
    readers open (engram.pack.Way)."""
    db = idx.db
    db.executescript(SCHEMA)
    docs = [(r, t, a) for r, t, a in db.execute("SELECT DISTINCT coalesce(parent, ref), title, author FROM doc")]
    keys = _keys(d, conf, docs)
    for w in more:
        k = keys.setdefault((w.kind, w.key), {"phrases": [], "refs": set(), "roles": []})
        said = [p.lower() for p in w.phrases] if w.kind == "tag" else _phrases(*w.phrases)  # a tag the owner asks by, however short
        k["phrases"] += [p for p in said if p not in k["phrases"]]
        k["refs"] |= set(w.refs)
    if made := threads.creatable(conf):  # a created thread by any of its names, however long: what's on it
        from engram.store import Store
        for t, said in threads.Threads(Store(d.repo).events(), made).names.items():
            k = keys.setdefault(("thread", t), {"phrases": [], "refs": set(), "roles": []})
            k["phrases"] += [p for p in dict.fromkeys(" ".join(x.lower().split()) for x in said) if p not in k["phrases"]]
            k["refs"] |= {r for (r,) in db.execute("SELECT ref FROM on_story WHERE story = ?", (t,))}
    if (conf.get("ways") or {}).get("theory"):  # a discovery file (evidence/D03-cervicogenic-eye.md) and what bears on it
        for (to,) in db.execute("SELECT DISTINCT to_ref FROM link WHERE family = 'evidence' AND rel IN ('strengthens', 'weakens')"):
            if m := re.match(r".*/(D\d+)-([\w-]+)\.md$", to.split("#", 1)[0]):
                w = keys.setdefault(("theory", m.group(1)), {"phrases": _phrases(m.group(1), m.group(2).replace("-", " ")), "refs": set(), "roles": []})
                w["refs"] |= {to} | {f for (f,) in db.execute("SELECT from_ref FROM link WHERE to_ref = ? AND family = 'evidence'", (to,))}
    names = {}
    for (kind, key), w in keys.items():
        for p in w["phrases"] if kind not in LINKED else ():
            names.setdefault(p, []).append((kind, key))
    if names:
        pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b", re.I)
        for ref, title, body in db.execute("SELECT coalesce(parent, ref), title, body FROM doc"):
            for m in set(x.lower() for x in pattern.findall(f"{title}\n{body}")):
                for k in names.get(m, []):
                    keys[k]["refs"].add(ref)
    with db:
        db.execute("DELETE FROM way")
        db.execute("DELETE FROM way_ref")
        db.executemany("INSERT INTO way (kind, key, phrase) VALUES (?, ?, ?)",
                       [(k, key, p) for (k, key), w in keys.items() for p in w["phrases"] + w["roles"]])
        db.executemany("INSERT OR IGNORE INTO way_ref (kind, key, ref) VALUES (?, ?, ?)",
                       [(k, key, r) for (k, key), w in keys.items() for r in w["refs"]])
    return len(keys)


def named(db, text: str) -> list[tuple[str, str, str]]:
    """(kind, key, phrase) for each way in a question names, longest phrase first; nothing for a record without them."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'way'").fetchone():
        return []
    low, out, taken = text.lower(), [], []
    for kind, key, phrase in sorted(db.execute("SELECT kind, key, phrase FROM way"), key=lambda r: -len(r[2])):
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", low):
            # "cervical mri" wins over "mri"; two notes sharing a name are both named by it
            if not any(a <= m.start() < b and not (kind in LINKED and low[a:b] == phrase) for a, b in taken):
                taken.append((m.start(), m.end()))
                out.append((kind, key, phrase))
                break
    return out
