"""A domain's story graph, from its link events: for each timeline link, the two record sections it joins, so a search
hit can arrive with the steps before and after it on each story.

A link's ends are events or record sections named by ref. An evidence link may point at a theory node (`discovery/D08`);
engram.toml's `[nodes]` patterns name the sections each node lives in, and the link joins the entry to every one of
them, so search can pick the section that fits the query."""
from fnmatch import fnmatchcase
from pathlib import Path

from engram import notes
from engram.config import Domain
from engram.paths import record_toml
from engram.store import Store

FAMILIES = ("timeline", "evidence")


def ref_of(e, store: Store) -> str | None:
    """The record an event is indexed as: its own id once entries are read straight from events, else the page section
    it shows up in, set at migration or worked out for an entry filed since."""
    if (store.config.get("index") or {}).get("events"):
        return e.id
    if e.fm.get("ref"):
        return e.fm["ref"]
    series = next((a.split("/", 1)[1] for a in e.about if a.startswith("series/")), None)
    if series and (store.root / f"logs/{series}.md").exists():
        note = f" ({e.fm['date_note']})" if e.fm.get("date_note") else ""
        title = f" — {e.fm['title']}" if e.fm.get("title") else ""
        return f"logs/{series}.md#{e.date}{note}{title}"
    return None


def node_refs(node: str, patterns: dict[str, str], refs: list[str]) -> list[str]:
    """The sections a theory node lives in: `discovery/D08` with `discovery = "evidence/{id}-*"` is every section of
    evidence/D08-….md."""
    kind, _, nid = node.partition("/")
    pat = patterns.get(kind)
    return [r for r in refs if fnmatchcase(r, pat.format(id=nid))] if pat else []


def links(d: Domain, refs: list[str] = (), first: dict[str, str] | None = None) -> list[tuple]:
    """(from_ref, to_ref, family, rel, story, link id, note) for every timeline and evidence link; the note is the
    first line of the link's body, which a flag (`supersedes`) uses to say what changed.

    A document end goes through the registry (engram.docreg) to where it stands now: `doc-…#anchor`, or an old
    `path#Heading` whose file moved or heading was renamed. A whole document (`path#`) is its opening section when
    the file has no text before its first heading (`first`: file → the section it opens with)."""
    if not d.repo or not record_toml(d.repo).exists():
        return []
    from engram.docreg import Registry
    st = Store(d.repo)
    reg = Registry(Path(d.repo), events_dir=st.events_dir)
    patterns = st.config.get("nodes", {})
    by_id = {e.id: e for e in st.events()}
    noted = notes.refs(d.repo)
    have = set(refs)
    first = first or {}

    def ends(x) -> list[str]:
        if not x:
            return []
        if x in by_id:
            r = ref_of(by_id[x], st)
            return [r] if r else []
        if x in noted:
            return [noted[x]]
        if x.startswith(("session:", "link/")):
            return [x]
        if reg and (reg.is_end(x) or "#" in x or "." in x.rsplit("/", 1)[-1]) and (w := reg.resolve(x)):
            x = w.ref
        if "#" in x or ":" in x:
            if x.endswith("#") and x not in have and x[:-1] in first:
                return [first[x[:-1]]]
            return [x]
        if (out := node_refs(x, patterns, refs)) or not reg or x not in reg.thing:
            return out or [x]
        w = reg.resolve(reg.thing[x])  # a thing whose file was renamed: every section of where it went
        return [r for r in refs if w and r.split("#", 1)[0] == w.path] or [x]

    out, seen = [], set()
    for link in st.events(kind="link"):
        fam = link.fm.get("family")
        if fam not in FAMILIES:
            continue
        story = next((x.split("/", 1)[1] for x in link.about if x.startswith("story/")), "")
        note = next((l.removeprefix("- ").strip() for l in link.body.splitlines() if l.strip()), "")
        for fa in ends(link.fm.get("from")):
            for fb in ends(link.fm.get("to")):
                if (fa, fb, fam, link.fm.get("rel", "")) in seen:  # the same link filed twice is one link, the first kept
                    continue
                seen.add((fa, fb, fam, link.fm.get("rel", "")))
                out.append((fa, fb, fam, link.fm.get("rel", ""), story, link.id, note))
    return out


def sync(idx, d: Domain) -> int:
    refs = [r[0] for r in idx.db.execute("SELECT DISTINCT coalesce(parent, ref) FROM doc WHERE class = 'section'")]
    first = {}
    for (r,) in idx.db.execute("SELECT coalesce(parent, ref) FROM doc WHERE class = 'section' ORDER BY rowid"):
        first.setdefault(r.split("#", 1)[0], r)
    rows = links(d, refs, first)
    with idx.db:
        idx.db.execute("DELETE FROM link WHERE family IN ('timeline', 'evidence')")
        idx.db.executemany("INSERT INTO link (from_ref, to_ref, family, rel, story, event, note) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)
