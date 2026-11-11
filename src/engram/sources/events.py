"""A record's dated entries, read straight from its events: once a record
has no rendered log pages, each event is indexed under its own id. Its text is the entry as the log view rendered it,
heading and body, cut at headings and into chunks exactly as a page section was, so ranking and the record summaries
carry over; a heading inside an entry is its own section, `<id>#<heading>`.

A record opts in with `[index] events = true` in its engram.toml."""
import re

from engram import dates
from engram.config import Domain
from engram.index import Doc
from engram.labels import nid
from engram.sources.sections import chunks, md_sections

SOURCE = "events"
SKIP = ("link",)


def enabled(conf: dict) -> bool:
    return bool((conf.get("index") or {}).get("events"))


def heading(e) -> str:
    """The entry's heading as written; an entry filed since migration gets the log template's form, both ends when it
    has two."""
    fm = e.fm
    if fm.get("heading"):
        return fm["heading"]
    note = f" ({fm['date_note']})" if fm.get("date_note") else ""
    title = f" — {fm['title']}" if fm.get("title") else ""
    to = f" to {fm['range_to']}" if fm.get("range_to") else ""  # his two ends: `date` is the first
    return f"{'#' * int(fm.get('level', 3))} {fm.get('date', '')}{to}{note}{title}".rstrip()


def series(e) -> str:
    s = next((a.split("/", 1)[1] for a in e.about if a.startswith("series/")), "")
    if s:
        return s.lstrip("_")
    thing = next((a for a in e.about if not a.startswith(("story/", "complaint/"))), "")
    return thing.split("/", 1)[0] if thing else e.kind  # a status or a join: the kind of thing it's about


def text(e) -> str:
    """The entry as one block: heading, then body; a med-change's fields lead when its body lacks them."""
    body = e.body.rstrip("\n")
    extra = [f"- {k}: {e.fm[k]}" for k in ("entity", "status", "dose", "target") if e.fm.get(k) and str(e.fm[k]) not in body]
    if extra and not e.fm.get("heading"):
        body = "\n".join(extra + ([body] if body.strip() else []))
    return heading(e) + ("\n" + body if body.strip() else "")


POOLED = ("series/meds", "series/_observations")  # series that pool unrelated things: no stories of their own


def inherited(events):
    """The stories an entry with none of its own sits on: a treatment sits on the stories it addressed, so a status row or a medication row filed without a story takes the stories
    of the other entries in its series, or on its medication's chain. A pooled series gives none."""
    by_series: dict[str, dict[str, int]] = {}
    by_entity: dict[str, dict[str, int]] = {}
    for e in events:
        own = [a.split("/", 1)[1] for a in e.about if a.startswith("story/")]
        for a in e.about:
            if a.startswith("series/") and a not in POOLED:
                for s in own:
                    by_series.setdefault(a, {})[s] = by_series.get(a, {}).get(s, 0) + 1
        if e.fm.get("entity"):
            for s in own:
                k = str(e.fm["entity"]).lower()
                by_entity.setdefault(k, {})[s] = by_entity.get(k, {}).get(s, 0) + 1

    def of(e) -> str:
        found: dict[str, int] = {}
        for a in e.about:
            for s, n in by_series.get(a, {}).items():
                found[s] = found.get(s, 0) + n
        for s, n in by_entity.get(str(e.fm.get("entity") or "").lower(), {}).items():
            found[s] = found.get(s, 0) + n
        return ",".join(sorted(found, key=lambda s: -found[s]))
    return of


def docs_for(d: Domain) -> list[Doc]:
    from engram.store import Store
    from engram import threads
    st = Store(d.repo)
    out: list[Doc] = []
    inherit = inherited(st.events())
    on = threads.Threads(st.events(), threads.creatable(st.config))
    for e in st.events():
        if e.kind in SKIP:
            continue
        by = str(e.fm.get("by", "")) or "repo"
        stories = ",".join(map(threads.key, on.of(e))) or inherit(e)
        milestone = int(str(e.fm.get("milestone")).lower() == "true")
        when = str(e.fm.get("date", "")) if dates.valid(str(e.fm.get("date", ""))) else None
        when = when if when and when != "not-sure" else None
        lead = series(e)
        used: dict[str, int] = {}
        for n, (path, body) in enumerate(md_sections(text(e))):
            head = path[-1] if path else ""
            if n == 0:
                base = e.id
            else:
                key = f"{e.id}#{head}"
                used[key] = used.get(key, 0) + 1
                base = key if used[key] == 1 else f"{key}~{used[key]}"
            title = " › ".join(dict.fromkeys([lead, *[x for x in [e.fm.get("section", "")] if x], *path]))
            dt = (when if n == 0 else None) or dates.first_in(head) or None
            parts = chunks(body)
            for i, part in enumerate(parts, 1):
                out.append(Doc(ref=base if len(parts) == 1 else f"{base}@{i}", source=SOURCE, cls="section", kind="entry",
                               title=title, body=part, pointer=f"{d.repo}/{e.path}", date=dt, date_key=dates.key(dt),
                               author=by if n == 0 else "repo", parent=base if len(parts) > 1 else None,
                               node=e.kind if n == 0 else "", milestone=milestone if n == 0 else 0,
                               stories=stories if n == 0 else "", nid=nid(base)))  # a heading inside an entry: as a page section was
    return out


# An entry's id, its date the group: the ref of an entry, `<id>#<heading>` of a section in it.
ID = re.compile(r"^(\d{8})-\d{6}-[\w-]+-[0-9a-f]{4}(?=$|[#@~])")


def is_event_ref(ref: str) -> bool:
    return bool(ID.match(ref))
