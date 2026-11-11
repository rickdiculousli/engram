"""Where things stand, built from the record and never kept by hand (.engram/README.md, ""Current" is built from the
record"). What it follows is the area's, from its pack (engram.pack.Current).

Each thing has one fixed id, and every change to it points back to it: an entity by its name (every entry of the
pack's entity kind naming it), a thread by its id (every status event about it). Current follows each id's chain to
its latest entry, in the order the record wrote them, so it always matches the record and traces to the entry it came
from. When an earlier-written entry is dated after the latest and says otherwise, both
are shown, never one picked silently. A stopped thing shows for a month, marked stopped, then moves to the stopped
list, with its date and reason, at the end; a stop with no date is already past.

In the printed picture only (the one a session starts with), a thing still going that the owner hasn't mentioned for
over QUIET days reads "last mentioned <month>": a fact about the line, never a to-do. The indexed rows, the standing
lines and the filer's list leave it out, so what the filer reads doesn't move. The owner's last word is the latest date
on its chain or on one of their own dated entries its way in names; summaries, briefs and these rows don't count, so
the advisor repeating a line can't clear it, and so does a renewal: an entry of its own kind, filed after the filer
(capture.renew) when the owner says they're still on a marked thing, which nothing else here reads. A chain with no date
has nothing to measure from.

`engram now` prints it; the session-start hook prints it; it's also indexed (source `current`, one row per thing) so
a question about the present finds it first."""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from engram import config, dates, pack, threads, units
from engram.index import Doc
from engram.store import Store

SOURCE = "current"
SHOW_STOPPED = timedelta(days=30)
QUIET = timedelta(days=90)
RENEWAL = "renewal"  # an entry recording only that the owner said they're still on a thing: it moves `said`, nothing else


@dataclass
class Current:
    thing: str
    name: str
    status: str
    when: str
    detail: str
    entry: str
    group: str
    history: list[str] = field(default_factory=list)
    conflict: list[str] = field(default_factory=list)
    reason: str = ""
    chain: list[str] = field(default_factory=list)  # every entry on the thing's chain, in the order written
    started: str = ""  # when the current run began: an entity's first ongoing date since it last wasn't; a thread's first session
    changed: str = ""  # what the latest entry changed, when it isn't the start ("dose changed")
    said: str = ""  # the day of the owner's last word on a thing that can be marked (QUIET), as of the day asked


REASON = re.compile(r"^\s*[-*]\s*(?:note|reason|why|because)\s*:\s*(.+)$", re.I | re.M)


def reason(e) -> str:
    """Why a change was made, when its entry says: a `reason` field, else a "- note:", "- reason:" or "- why:" line."""
    r = str(e.fm.get("reason") or e.fm.get("why") or "")
    if not r:
        m = REASON.search(e.body)
        r = m.group(1) if m else ""
    r = " ".join(re.sub(r"\*\*", "", r).split())
    return r[:200] + ("…" if len(r) > 200 else "")


def spec(st: Store) -> pack.Current:
    return pack.for_repo(st.root).current


def base(name: str, cur: pack.Current) -> str:
    """An entity's name without its bracket (a medication's generic), unless the pack keeps names whole."""
    return name if cur.whole_names else name.split("(")[0]


def key(entity: str, cur: pack.Current) -> str:
    name = base(entity, cur).strip().lower()
    return f"{cur.entity_prefix}/" + re.sub(r"[^\w]+", "-", name).strip("-")


def chain_id(e, cur: pack.Current) -> str:
    """An entity entry's chain: the `thing` it was filed under (an existing chain its name matched), else its entity's."""
    t = str(e.fm.get("thing") or "")
    return t if t.startswith(f"{cur.entity_prefix}/") else key(str(e.fm.get("entity") or ""), cur)


def name_forms(name: str, cur: pack.Current) -> list[set[str]]:
    """An entity name's forms, strictest first: the pack's, else the name as written."""
    if cur.name_forms:
        return cur.name_forms(name)
    n = " ".join(name.lower().split())
    return [{n}, {n}, {n}]


def _entities(st: Store, cur: pack.Current) -> list:
    return [e for e in st.events(kind=cur.entity_kind) if e.fm.get("entity")] if cur.entity_kind else []


def names(st: Store) -> dict[str, list[set[str]]]:
    """chain id -> the forms of every name it goes by: each entity string its entries used, the fields the pack says
    also name it, and any `aliases`."""
    cur = spec(st)
    out: dict[str, list[set[str]]] = {}
    for e in _entities(st, cur):
        al = e.fm.get("aliases") or []
        said = [str(e.fm["entity"]), *(al if isinstance(al, list) else [al]),
                *(str(e.fm[k]) for k in cur.names if e.fm.get(k))]
        forms = out.setdefault(chain_id(e, cur), [set(), set(), set()])
        for n in said:
            for have, add in zip(forms, name_forms(n, cur)):
                have |= add
    return out


def chain_for(st: Store, name: str) -> str | None:
    """The existing chain an entity's name belongs to, matched through its names, entity strings and aliases,
    strictest form first, then a name that starts a longer one ("Zentrafen" for "Zentrafen XR"), then a name of two words
    or more inside a longer one ("serum tears"); None when nothing matches (a new thing). Among several matches at the
    same form, a chain still going beats a finished one, then the chain written to last."""
    cur = spec(st)
    if not name.strip() or not cur.entity_kind:
        return None
    mine = name_forms(name, cur)
    known = names(st)
    last: dict[str, tuple[str, str]] = {}
    for e in _entities(st, cur):
        rec = str(e.fm.get("recorded", ""))
        if rec >= last.get(chain_id(e, cur), ("", ""))[0]:
            last[chain_id(e, cur)] = (rec, str(e.fm.get("status", "")))

    def rank(t: str):
        rec, status = last.get(t, ("", ""))
        return status not in cur.finished, rec
    tiers = [lambda forms, t=t: mine[t] & forms[t] for t in range(3)]
    tiers.append(lambda forms: any(k.startswith(m + " ") for m in mine[2] for k in forms[2]))
    tiers.append(lambda forms: any(len(m.split()) > 1 and f" {m} " in f" {k} " for m in mine[2] for k in forms[2]))
    for match in tiers:
        hits = [t for t, forms in known.items() if match(forms)]
        if hits:
            return max(hits, key=rank)
    return None


def _day(e) -> str:
    return str(e.fm.get("date", "")) if dates.key(str(e.fm.get("date", ""))) else ""


def detail(e, field: str) -> str:
    """An entry's `field`, or its "- <field>:" body line; "" when it gives neither."""
    if not field:
        return ""
    return str(e.fm.get(field) or next((l.split(":", 1)[1].strip() for l in e.body.splitlines() if l.startswith(f"- {field}:")), ""))


def _run_start(evs: list, field: str, cur: pack.Current) -> tuple[str, str]:
    """(when the current run of an entity began, what its latest entry changed) for one still going: the dated entries
    in date order, back from the latest while each is still ongoing; a pause or stop ends the walk, so a restart is a
    new start."""
    dated = sorted((e for e in evs if _day(e)), key=lambda e: dates.key(_day(e)))
    run = []
    for e in reversed(dated):
        if str(e.fm.get("status", "")) not in cur.ongoing:
            break
        run.append(e)
    if len(run) < 2:
        return (_day(run[0]) if run else ""), ""
    first, last, before = _day(run[-1]), run[0], run[1]
    return first, f"{field} changed" if detail(last, field) and detail(last, field) != detail(before, field) else "updated"


def _first_session(st: Store, thing: str, corrected: set[str], start: tuple[str, tuple[str, ...]]) -> str:
    """A thread's first session: the earliest dated session on its series, leaving out any a later entry corrects (a
    start date the owner put right)."""
    series = f"{start[0]}/" + thing.split("/", 1)[1]
    days = [_day(e) for e in st.events() if e.kind in start[1] and series in e.about and _day(e) and e.id not in corrected]
    return min(days, key=dates.key) if days else ""  # as the record wrote it: a month stays a month


def _said(evs: list, own: list, today: date, cur: pack.Current, renewed: list[str] = ()) -> str:
    """The day of the owner's last word on an entity's chain, up to today: its entries' dates, its renewals' and those
    of the owner's own dated entries its way in names. "" when its chain has no date."""
    from engram.sources import waysin
    if not any(_day(e) for e in evs):
        return ""
    phrases = {p for e in evs for p in waysin.entity_phrases(str(e.fm["entity"]), cur.whole_names)}
    names = re.compile(r"\b(" + "|".join(sorted(map(re.escape, phrases), key=len, reverse=True)) + r")\b", re.I) if phrases else None
    chain = {e.id for e in evs}
    days = [_day(e) for e in evs if _day(e)] + list(renewed)
    days += [_day(e) for e in own if names and e.id not in chain and names.search(f"{e.fm.get('title', '')}\n{e.body}")]
    return max((dates.key(d) for d in days if dates.key(d) <= today.isoformat()), default="")


def mark(c: Current, today: date, cur: pack.Current) -> str:
    """"last mentioned 2026-06" for a thing still going whose owner last mentioned it over QUIET ago; "" otherwise."""
    if c.status not in cur.ongoing or not c.said or date.fromisoformat(c.said) >= today - QUIET:
        return ""
    return f"last mentioned {c.said[:7]}"


def his_words(body: str) -> str:
    """The owner's words, quoted, in an entry the filer wrote (`capture.entry`): its line `- <owner>: “<his words>”`, or
    `- <owner>, answering “<the question>”: “<his words>”`, read from its last `: “`, so the question he answered is
    never taken for his words; empty when it has no such line."""
    me = config.owner()
    for line in reversed(body.splitlines()):
        line = line.rstrip()
        head, sep, words = line.removesuffix("”").rpartition(": “")
        if sep and line.endswith("”") and (head == f"- {me}" or head.startswith(f"- {me}, ")):
            return f"“{words}”"
    return ""


def _chain(st: Store, today: date | None = None) -> list[Current]:
    today = today or date.today()
    cur = spec(st)
    chains: dict[str, list] = {}
    corrected = units.corrected(st)
    narrowed = {e.fm.get("supersedes") for e in st.events() if e.fm.get("narrowed_by")}  # its copy holds its place
    for e in _entities(st, cur):
        if e.id not in narrowed:
            chains.setdefault(chain_id(e, cur), []).append(e)
    made = threads.creatable(st.config)
    for e in st.events(kind="status") if cur.threads else []:
        for a in e.about if e.id not in narrowed else []:
            if a.split("/")[0] in cur.threads and a.split("/")[0] not in made:
                chains.setdefault(a, []).append(e)
    tt = threads.Threads(st.events(), made) if made and set(made) & set(cur.threads) else None
    for e in st.events() if tt else []:  # a thread the filer makes stands where the latest thing said on it does
        for a in tt.of(e) if e.kind not in ("link", threads.KIND) and e.id not in narrowed else []:
            if a.split("/")[0] in cur.threads and tt.created(a):
                chains.setdefault(a, []).append(e)
    own = [e for e in st.events() if e.kind != "link" and str(e.fm.get("by", "")) == config.owner_id() and _day(e)]
    renewed: dict[str, list[str]] = {}
    for e in st.events(kind=RENEWAL):
        if _day(e):
            renewed.setdefault(str(e.fm.get("thing", "")), []).append(_day(e))
    out = []
    for thing, evs in chains.items():
        evs.sort(key=lambda e: str(e.fm.get("recorded", "")))
        if tt and tt.created(thing):  # filed in one second, the later said is the later
            evs.sort(key=lambda e: (str(e.fm.get("recorded", "")), dates.key(_day(e)) or ""))
        last = evs[-1]
        status = str(last.fm.get("status", ""))
        when = _day(last)
        conflict = [e.id for e in evs[:-1] if _day(e) and when and dates.key(_day(e)) > dates.key(when)
                    and str(e.fm.get("status", "")) != status]
        said = ""
        if last.kind == cur.entity_kind:
            name = str(last.fm["entity"])
            shown = detail(last, cur.detail)
            if not shown and status in cur.ongoing:  # the latest entry only changed the status: the detail before it
                shown = next((d for e in reversed(evs[:-1]) if (d := detail(e, cur.detail))), "")
            group = cur.groups.get(str(last.fm.get("group", "")), cur.group)
            started, changed = _run_start(evs, cur.detail, cur) if status in cur.ongoing else ("", "")
            said = _said(evs, own, today, cur, renewed.get(thing, []))
        else:
            prefix = thing.split("/")[0]
            name = str(last.fm.get(prefix) or thing.split("/", 1)[1].replace("-", " "))
            first = next((l.lstrip("- ").strip() for l in last.body.splitlines() if l.strip()), "")
            shown = re.sub(r"\*\*", "", first.split(": ", 1)[1] if first.startswith(name + ":") else first)
            if tt and tt.created(thing):  # his own words on it, as said
                name = tt.names[thing][0]
                shown = his_words(last.body) or shown
            group = cur.threads[prefix]
            started, changed = (_first_session(st, thing, corrected, cur.starts[prefix]) if prefix in cur.starts else ""), ""
        history = [f"{e.fm.get('status', '')} {_day(e) or 'date not sure'}" for e in evs]
        out.append(Current(thing, name, status, when, shown, last.id, group, history, conflict,
                           reason(last) if status in cur.finished else "", [e.id for e in evs], started, changed, said))
    return out


def build(repo: Path, today: date | None = None) -> dict[str, list[Current]]:
    """Sections of where things stand, as the pack names them, then stopped."""
    today = today or date.today()
    st = Store(repo)
    cur = spec(st)
    sections: dict[str, list[Current]] = {}
    for c in _chain(st, today):
        finished = c.status in cur.finished
        recent = finished and c.when and dates.key(c.when) and date.fromisoformat(dates.key(c.when)) >= today - SHOW_STOPPED
        if c.group in cur.hidden and finished:
            continue
        sections.setdefault("stopped" if finished and not recent else c.group, []).append(c)
    for v in sections.values():
        v.sort(key=lambda c: (dates.key(c.when) or "0000", c.name), reverse=True)
    return sections


def upcoming(repo: Path, today: date | None = None) -> list[tuple[str, str, str]]:
    """(date, what, id) for each entry of a kind the pack names dated ahead of today, by the entry's date or a date in
    its title, and each document in its folder named by a date ahead."""
    today = (today or date.today()).isoformat()
    st = Store(repo)
    cur = spec(st)
    out = []
    for e in st.events() if cur.ahead else []:
        if e.kind not in cur.ahead:
            continue
        ahead = [d for d in dates.FIND.findall(f"{e.fm.get('title', '')} {e.fm.get('date', '')}") if dates.key(d) and dates.key(d) > today]
        if ahead:
            out.append((min(ahead), str(e.fm.get("title") or e.fm.get("heading", "")).lstrip("# "), e.id))
    folder = repo / cur.ahead_dir if cur.ahead_dir else None
    for p in sorted(folder.glob("*.md")) if folder and folder.exists() else []:
        ahead = [d for d in dates.FIND.findall(p.stem) if dates.key(d) and dates.key(d) > today]
        if ahead:
            out.append((ahead[0], p.stem, p.relative_to(repo).as_posix()))
    return sorted(out)


def care_team(repo: Path, today: date | None = None) -> list[tuple[str, str]]:
    """(name, last seen) for each person the owner sees (the pack's `team`) on the people list with a record in the
    last year, from the entries they wrote and the documents they wrote (by the index, when there is one)."""
    from engram import labels
    today = today or date.today()
    st = Store(repo)
    team = spec(st).team[0]
    if not team:
        return []
    known = labels.people(st.config)
    last: dict[str, str] = {}

    def seen(by: str, day: str | None):
        k = dates.key(day or "")
        who = labels.who(by, known) if by.startswith(f"{team}:") else ""
        if k and who and not who.endswith("?"):
            last[who] = max(last.get(who, ""), k)
    for e in st.events():
        if e.kind != "link":
            seen(str(e.fm.get("by", "")), str(e.fm.get("date", "")))
    try:
        from engram.index import open_index
        from engram.paths import index_path
        idx = open_index(index_path(str(st.config.get("domain", {}).get("name", ""))), readonly=True)
        if idx:
            for by, day in idx.db.execute("SELECT author, max(date_key) FROM doc WHERE author LIKE ? GROUP BY author", (f"{team}:%",)):
                seen(by, day)
            idx.close()
    except Exception:
        pass
    cut = (today - timedelta(days=365)).isoformat()
    return sorted(((n, d) for n, d in last.items() if d >= cut), key=lambda x: x[1], reverse=True)


def theories(repo: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(id, status, title) for each Discovery and pattern, and the open questions."""
    from engram import theory
    g = theory.load(repo)
    ths = [(t.short, g.status.get(t.id, ("",))[0], t.title) for t in g.things.values() if t.kind in ("discovery", "pattern")]
    qs = [t.title for t in g.things.values() if t.kind == "question" and g.status.get(t.id, ("",))[0] == "open"]
    return ths, qs


def own_theory(repo: Path, today: date) -> list[str]:
    """The record's own kinds of theory (`[theory.kinds]`), one line each: its status, its stage and whose it is. Left
    out: what's ruled out or replaced, and a guide's suggestion still proposed that the owner hasn't spoken of (an
    entry of his on it) for `[suggestions] quiet_days`, counted from when it was made; moments linked to it and the
    guide saying it again don't count. `engram theory` prints them all. None for a record without such kinds."""
    from engram import theory
    from engram.paths import record_conf
    g = theory.load(repo)
    if not g.kinds:
        return []
    quiet = (record_conf(repo).get("suggestions") or {}).get("quiet_days")
    cut = (today - timedelta(days=int(quiet))).isoformat() if quiet else ""
    me, last = config.owner_id(), {}
    for e in Store(repo).events() if cut else []:
        if e.kind != "link" and str(e.fm.get("by", "")) == me and _day(e):
            for a in e.about:
                last[a] = max(last.get(a, ""), dates.key(_day(e)))
    out = []
    for t in g.things.values():
        status = g.status.get(t.id, ("",))[0]
        if t.kind not in g.kinds or status in theory.GONE:
            continue
        unanswered = t.by == theory.SUGGESTION and (g.word.get(t.id) or {}).get("by", theory.SUGGESTION) == theory.SUGGESTION
        if cut and unanswered and max(last.get(t.id, ""), dates.key(t.since) or "") < cut:
            continue
        bits = [b for b in (status, g.stage.get(t.id, ("",))[0], theory.who(g, t.id)) if b]
        out.append(f"- {t.short} ({t.kind})" + (f": {'; '.join(bits)}" if bits else ""))
    return out


def text(repo: Path, today: date | None = None, mark_shown: bool = False) -> str:
    """Where things stand, what a session needs first at the top, since the session start cuts it from its end:
    upcoming, the theories and open questions, the pack's sections in its order, the team, and last what stopped over a
    month ago. A theory revision whose evidence re-check finished shows one line at the very top, once (the
    session-start hook marks it shown)."""
    today = today or date.today()
    cur = pack.for_repo(repo).current
    secs = build(repo, today)
    lines = [f"where things stand, as of {today.isoformat()} (from the record; `engram show <id>` opens an entry)"]
    try:
        from engram import theorychange
        lines += [f"theory: {n}" for n in theorychange.notices(repo, mark=mark_shown)]
    except Exception:  # the notice is a help; it mustn't block the picture
        pass
    up = upcoming(repo, today)
    if up:
        lines.append("\nupcoming:")
        lines += [f"- {d}: {w} [{i}]" for d, w, i in up]
    ths, qs = theories(repo)
    if ths:
        lines.append("\ntheories: " + "; ".join(f"{i} {s}" for i, s, _ in ths if s))
    if qs:
        lines.append(f"\nopen questions ({len(qs)}):")
        lines += [f"- {q}" for q in qs]
    if own := own_theory(repo, today):
        lines.append("\nthe theory (`engram theory` prints all of it):")
        lines += own

    def section(name: str):
        items = secs.get(name, [])
        if not items:
            return
        lines.append(f"\n{name}:")
        for c in items:
            label = c.status if c.status not in ("taking", "active") else ""
            if c.status in cur.finished:
                since = c.when or "date not sure"
            elif name in cur.threads.values():  # a status line written that day, and when the thread began
                since = "; ".join(b for b in (f"as of {c.when}" if c.when else "", f"first session {c.started}" if c.started else "") if b)
            else:
                since = since_text(c)
            why = f"why: {c.reason}" if c.reason and c.reason not in c.detail else ""
            bits = [b for b in (label, since, c.detail, why, mark(c, today, cur)) if b]
            line = f"- {c.name}: {'; '.join(bits)} [{c.entry}]"
            if c.conflict:
                line += f" — the record disagrees: also {', '.join(c.conflict)}"
            lines.append(line)
    for name in cur.sections:
        if name != "stopped":
            section(name)
    team = care_team(repo, today)
    if team:
        lines.append(f"\n{cur.team[1]} (seen in the last year):")
        lines += [f"- {n}: last {d}" for n, d in team]
    if "stopped" in cur.sections:
        section("stopped")
    return "\n".join(lines)


def since_text(c: Current) -> str:
    """"since 2026-03-02 (dose changed 2026-09-10)": when the run began, and the latest change when it's later."""
    start = c.started or c.when
    if not start:
        return "since: date not sure"
    later = c.when and c.changed and dates.key(c.when) != dates.key(start)
    return f"since {start}" + (f" ({c.changed} {c.when})" if later else "")


def _begun(cur: pack.Current) -> set[str]:
    """The sections of threads that begin at their first session: their line gives that, not how long they've run."""
    return {cur.threads[p] for p in cur.starts if p in cur.threads}


def line(c: Current, begun: set[str], cur: pack.Current) -> str:
    """Where one thing stands, in one line: its name, status, since when, its detail and why it stopped."""
    why = f" Why: {c.reason}" if c.reason else ""
    when = since_text(c) if c.status in cur.ongoing and c.group not in begun else f"{c.when or ''}" + (
        f", first session {c.started}" if c.started else "")
    return " ".join(f"{c.name}: {' '.join(b for b in (c.status, when) if b)}. {c.detail}{why}".split())


_STANDING: dict = {}


def standing(repo: Path) -> dict[str, str | None]:
    """entry id -> where its thing stands now (`line`), for every entry on a thing's chain, None for the latest (it is
    where the thing stands): a unit holding an older dose step carries this instead of the step being a correction
    (docs/search.md, "A fact and its corrections"). Cached per process while the events folder is unchanged."""
    ev = repo / "events"
    stamp = (str(repo), ev.stat().st_mtime_ns if ev.exists() else 0)
    if _STANDING.get("stamp") != stamp:
        out = {}
        cur = pack.for_repo(repo).current
        begun = _begun(cur)
        for items in build(repo).values():
            for c in items:
                for e in c.chain:
                    out[e] = None if e == c.entry else line(c, begun, cur)
        _STANDING.clear()
        _STANDING.update(stamp=stamp, lines=out)
    return _STANDING["lines"]


def docs_for(repo: Path, today: date | None = None) -> list[Doc]:
    """One row per thing, so a search about the present finds where it stands."""
    out = []
    cur = pack.for_repo(repo).current
    begun = _begun(cur)
    for section, items in build(repo, today).items():
        for c in items:
            why = f" Why: {c.reason}" if c.reason else ""
            when = since_text(c) if c.status in cur.ongoing and c.group not in begun else f"{c.when or ''}" + (
                f", first session {c.started}" if c.started else "")
            body = f"{c.name}: {c.status} {when}. {c.detail}{why}\nhistory: {'; '.join(c.history)}".strip()
            out.append(Doc(ref=f"now:{c.thing}", source=SOURCE, cls="current", kind=section, title=f"now › {section} › {c.name}",
                           body=body, pointer=f"{repo}/events", date=c.when or None, date_key=dates.key(c.when) if c.when else None,
                           author="repo"))
    return out
