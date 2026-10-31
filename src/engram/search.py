"""Keyword search: FTS5 BM25 inside each domain's file, weighted by kind, lens and the question, rank fusion across files."""
import math
import os
import re
from dataclasses import asdict
from datetime import date
from fnmatch import fnmatchcase

from engram import config
from engram.index import open_index
from engram.paths import index_path, record_conf, record_toml

TERM = re.compile(r"[\w][\w./+%:-]*[\w%]|[\w]", re.UNICODE)
NOW = re.compile(r"\b(now|current|currently|these days|lately|right now|still|am i (on|taking|using)|what am i|who is my|who's my)\b", re.I)
RRF_K = 60
ENTRY = re.compile(r"^\d{8}-\d{6}-[\w-]+-[0-9a-f]{4}(?=$|#)")
PERSON = 1.3  # a record lit by a person the question names, by name or role ("did the massage therapist say…")


RAW = 0.5  # raw text: the lowest weight that keeps it from crowding records out
SUPERSEDED = 0.5


def fts_query(q: str) -> str | None:
    q = q.strip()
    if len(q) > 1 and q.startswith('"') and q.endswith('"') and '"' not in q[1:-1]:
        return q if q[1:-1].strip() else None
    terms = [t for t in TERM.findall(q)]
    if not terms:
        return None
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in dict.fromkeys(terms))


def _factors(row: dict) -> dict:
    return {"class": RAW if row["class"] == "raw" else 1.0, "superseded": SUPERSEDED if row["superseded"] else 1.0}


def repo_conf(domain: str) -> dict:
    d = config.load().get(domain)
    return record_conf(d.repo) if d and d.repo else {}


def lenses(domain: str) -> dict[str, dict]:
    """A domain's lenses, from `[lenses.<name>]` in its repo's engram.toml: name → {about, for, weights}."""
    return repo_conf(domain).get("lenses", {})


def lens_factor(row: dict, weights: dict) -> float:
    """The product of a lens's weights that fit a record. Keys: `milestone`, `day-to-day` (a record on a story that
    isn't a milestone), `node:<kind>`, `by:<whose claim, prefix>`, `file:<glob>`, `ref:<glob>` (a section), `class:<class>`."""
    f = 1.0
    node, ms, file = row.get("node") or "", row.get("milestone") or 0, row["ref"].partition("#")[0]
    for k, w in weights.items():
        key, _, val = k.partition(":")
        if ((k == "milestone" and ms) or (k == "day-to-day" and node and not ms) or (key == "node" and node == val)
                or (key == "by" and (row.get("author") or "").startswith(val)) or (key == "file" and fnmatchcase(file, val))
                or (key == "ref" and fnmatchcase(row["ref"], val))
                or (key == "class" and row.get("class") == val)):
            f *= w
    return f


def search_domain(domain: str, q: str, limit: int, after: str | None = None,
                  kind: str | None = None, cls: str | None = None, today: date | None = None, lens: str | None = None,
                  surround: bool = True, as_of: str | None = None, as_it_stood: bool = False) -> list[dict]:
    idx = open_index(index_path(domain), readonly=True)
    expr = fts_query(q)
    if idx is None or expr is None:
        return []
    today = today or date.today()
    where, args = ["doc_fts MATCH ?"], [expr]
    if after:
        where.append("d.date_key >= ?"); args.append(after)
    if kind:
        where.append("d.kind = ?"); args.append(kind)
    if cls:
        where.append("d.class = ?"); args.append(cls)
    # Set by the eval runner: a question taken from a session must not find that session, which holds the question itself.
    for src in filter(None, os.environ.get("ENGRAM_EXCLUDE_SOURCES", "").split(",")):
        where.append("d.source NOT LIKE ?"); args.append(src + "%")
        if src.startswith("sessions:"):  # what he said there, as rows on his stories, is that session too
            where.append("d.ref NOT LIKE ?"); args.append("session:" + src.split(":")[1] + ":%")
    conf = repo_conf(domain)
    # every search weighs records by kind ([weights], beside its `about` line); a lens weighs again on top
    base = {k: v for k, v in conf.get("weights", {}).items() if isinstance(v, (int, float))}
    weights = conf.get("lenses", {}).get(lens, {}).get("weights", {}) if lens else {}
    sql = (f"SELECT d.ref, d.parent, d.class, d.kind, d.date, d.date_key, d.title, d.author, d.superseded, d.pointer, "
           f"d.node, d.milestone, bm25(doc_fts, 2.0, 1.0, 1.0) AS bm,snippet(doc_fts, 1, '[', ']', '…', {SNIP}) AS snip "
           f"FROM doc_fts JOIN doc d ON d.id = doc_fts.rowid WHERE {' AND '.join(where)} ORDER BY bm LIMIT ?")
    rows = [dict(r) for r in idx.db.execute(sql, args + [max(limit * 20, 200)])]
    for alt, syn_w in synonyms(repo_conf(domain), q):  # query expansion: a synonym's match adds to a record's score,
        mine = {r["ref"]: r for r in rows}  # at its weight, and never filters
        for r in idx.db.execute(sql, [alt] + args[1:] + [max(limit * 20, 200)]):
            r = dict(r)
            if r["ref"] in mine:
                mine[r["ref"]]["bm"] += syn_w * r["bm"]
            else:
                rows.append({**r, "bm": syn_w * r["bm"]})
    people = person_lit(idx.db, q)
    present = bool(NOW.search(q))
    folders = folders_named(conf, q)
    asked = asks(conf, q)
    out = []
    for r in rows:
        f = _factors(r)
        if r["class"] == "current":  # where things stand: first for a question about the present, else below history
            f["current"] = 1.5 if present else 0.7
        if base:
            f["node"] = round(lens_factor(r, base), 4)
        if people and ({r["ref"], r["ref"].partition("#")[0], r["parent"]} & people):  # a section of their record too
            f["person"] = PERSON
        if asked:  # the strongest favour that fits, not stacked, times every disfavour; a weight, never a filter
            fit = [w for k, w in asked.items() if w and lens_factor(r, {k: w}) != 1.0]
            f["ask"] = round(max([w for w in fit if w > 1], default=1.0) * math.prod(w for w in fit if w < 1), 4)
        if folders and r["ref"].startswith(tuple(folders)):
            f["folder"] = float(conf["folders"].get("boost", 1.5))
        if weights:
            f["lens"] = round(lens_factor(r, weights), 4)
            if not f["lens"]:  # a weight of 0 keeps a kind of record out of the lens
                continue
        score = -r["bm"]
        for v in f.values():
            score *= v
        out.append({**r, "domain": domain, "score": round(score, 4), "factors": {"bm25": round(-r["bm"], 4), **f}})
    out.sort(key=lambda r: -r["score"])
    # A section cut into chunks is one hit, under the section's own ref (`engram show` reads it whole): its chunks
    # don't take several of the top places.
    # One document's sections take at most PER_FILE of the places; the next results fill the rest.
    seen, kept, per_file = set(), [], {}
    for r in out:
        key = r.pop("parent") or r["ref"]
        if ENTRY.match(key):  # an entry is one item (one visit, one test): its sections are one hit under its id
            key = key.partition("#")[0]
        if key in seen:
            continue
        seen.add(key)
        doc = key.partition("#")[0] if "#" in key and "/" in key.partition("#")[0] else None
        if doc and per_file.get(doc, 0) >= PER_FILE:
            continue
        if doc:
            per_file[doc] = per_file.get(doc, 0) + 1
        kept.append({**r, "ref": key})
    try:
        out = gathered(idx.db, domain, q, expr, kept, limit, today, as_of, as_it_stood) if surround else kept[:limit]
    finally:
        idx.close()
    if surround:  # a caller wanting only the ranking (story picking, placing a passage) skips the neighbours
        _surround(idx_path_of(domain), out, q, weights={k: base.get(k, 1.0) * weights.get(k, 1.0) for k in base.keys() | weights.keys()})
    return out


def synonyms(conf: dict, q: str) -> list[tuple[str, float]]:
    """[(an FTS expression of alternatives to the question's words that it doesn't use itself, their weight)] from
    `[synonyms]` in the record's engram.toml: `same` maps a short form to the words it stands for ("pt" to "physical
    therapy"), or a word to a form of it the stemmer doesn't join ("surgery", "surgical"), at full weight; `words` maps a word to near-synonyms ("restart" to "renew", "resume") at `weight`, lower.
    One way, so "drops" for eye drops never reads as "stopped". A word matches whole, a plural or -ed/-ing allowed (stopped)."""
    sy = conf.get("synonyms") or {}
    used = {t.lower() for t in TERM.findall(q)}
    out = []
    for table, w in (("same", 1.0), ("words", float(sy.get("weight", 0.5)))):
        alt = [a for k, alts in (sy.get(table) or {}).items()
               if cued(q, [k]) or any(re.fullmatch(re.escape(k) + f"{re.escape(k[-1])}?(ed|d|ing)", u) for u in used)
               for a in alts if a.lower() not in used]
        if alt:
            out.append((" OR ".join('"' + a.replace('"', '""') + '"' for a in dict.fromkeys(alt)), w))
    return out


def reading_date(db, q: str, today: date, as_of: str | None = None, as_it_stood: bool = False) -> tuple[str | None, bool]:
    """(the date the record is read as of, whether later versions are hidden): `--as-of` and `--as-it-stood`, else the
    day of a session the eval runner hides (as things stood: hidden), else the end of a past period the question names
    (later versions shown as changed later)."""
    from engram import periods, units
    when, hide = as_of, as_it_stood
    if not when and (day := units.session_day(db)):
        return day, True
    if not when and (p := periods.period(q, today)) and p[1] < today:
        when = p[1].isoformat()
    return when, hide


def now_lines(domain: str):
    """ref -> where its thing stands now, for an entry on a `now` chain that isn't its latest (units carry it)."""
    from engram import now
    d = config.load().get(domain)
    if not (d and d.repo and record_toml(d.repo).exists()):
        return None
    try:
        lines = now.standing(d.repo)
    except Exception:  # the line is a help; it mustn't break a search
        return None
    return lambda ref: lines.get(ref, "")  # None: the thing's latest entry


def gathered(db, domain: str, q: str, expr: str, kept: list[dict], limit: int, today: date, as_of: str | None = None,
             as_it_stood: bool = False) -> list[dict]:
    """The top `limit` units (docs/search.md, "A fact and its corrections"): a record and every version of it along
    revises, supersedes and disagrees links are one result, shown at its current version (as of the reading date), so
    another version never takes a second place. A result with no other version stays as it was."""
    from engram import units
    g = units.graph(db)
    when, hide = reading_date(db, q, today, as_of, as_it_stood)
    known = labels_people(domain)
    now_of = now_lines(domain)
    out, claimed, said_now = [], set(), set()
    for r in kept:
        if len(out) >= limit:
            break
        if units.norm(r["ref"]) in claimed:
            continue
        u = units.build(db, g, r["ref"], when, hide, known, _excluded, now_of)
        if u is None:
            out.append(r)
            claimed.add(units.norm(r["ref"]))
            continue
        claimed |= set(u.members) | set(u.hidden)
        if u.now in said_now:  # where a thing stands, once per search
            u.now = ""
        said_now.add(u.now)
        if u.centre != units.norm(r["ref"]):
            r = centre_row(db, u.centre, expr, r)
        out.append({**r, "unit": {**asdict(u), "size": u.size, "shown": u.shown, "text": units.text_lines(u)}})
    return out


def labels_people(domain: str) -> dict:
    from engram import labels
    return labels.people(repo_conf(domain))


def centre_row(db, ref: str, expr: str, hit: dict) -> dict:
    """A unit's current version as a result, in the detail a hit has: its title, date, kind, whose claim, an excerpt
    (the question's words where it has them, else its opening words), keeping the hit's score."""
    row = db.execute("SELECT id, ref, class, kind, date, date_key, title, author, superseded, pointer, node, milestone, body "
                     "FROM doc WHERE ref = ? OR parent = ? OR (? GLOB '[0-9]*' AND ref LIKE ? || '#%') ORDER BY rowid LIMIT 1",
                     (ref, ref, ref, ref)).fetchone()
    if row is None:
        return hit
    snip = db.execute(f"SELECT snippet(doc_fts, 1, '[', ']', '…', {SNIP}) FROM doc_fts WHERE doc_fts MATCH ? AND rowid = ?",
                      (expr, row[0])).fetchone()
    words = " ".join(l for l in row[12].splitlines() if l.strip() and not l.lstrip().startswith("#")).split()
    text = snip[0] if snip else " ".join(words[:SNIP]) + ("…" if len(words) > SNIP else "")
    keys = ("class", "kind", "date", "date_key", "title", "author", "superseded", "pointer", "node", "milestone")
    return {**hit, **dict(zip(keys, row[2:12])), "ref": ref, "snip": text}


def cued(q: str, words) -> bool:
    """The question uses one of the words or phrases, whole, a plural `s` allowed."""
    return any(re.search(r"\b" + re.escape(w.lower()) + r"s?\b", q.lower()) for w in words)


def folders_named(conf: dict, q: str) -> list[str]:
    """The folders a question's words point at, from `[folders.words]` in the record's engram.toml ("journal" →
    mental-health/): their records rank higher by `[folders] boost`, never only them."""
    words = (conf.get("folders") or {}).get("words") or {}
    return [f for w, fs in words.items() if cued(q, [w]) for f in ([fs] if isinstance(fs, str) else fs)]


def asks(conf: dict, q: str) -> dict[str, float]:
    """The kind weights of what a question asks for: each `[asks.<name>]` in the record's engram.toml whose `words` the
    question uses applies its `weights` (lens keys), beside every search's own ("what did the consult find?" favours
    visits and results over the brief written before it)."""
    out: dict[str, float] = {}
    for a in (conf.get("asks") or {}).values():
        if cued(q, a.get("words", [])):
            for k, w in (a.get("weights") or {}).items():
                out[k] = out.get(k, 1.0) * w
    return out


def person_lit(db, q: str) -> set[str]:
    """The records lit by each person the question names, by a name they go by or a role the owner uses for them (a way in,
    .engram/README.md): what they wrote and what mentions them by name."""
    from engram.sources import waysin
    keys = [key for kind, key, _ in waysin.named(db, q) if kind == "person"]
    if not keys:
        return set()
    return {r for (r,) in db.execute(f"SELECT ref FROM way_ref WHERE kind = 'person' AND key IN ({','.join('?' * len(keys))})", keys)}


def idx_path_of(domain: str):
    return index_path(domain)


# Neighbours shown per hit beside the listed and fixed ones, and how many steps out they're drawn from. Measured in
# replay as records found against characters printed: a second step took every link
# found from 45 to 52 of 75 questions; neighbours' opening words cost 40% of the output and found nothing more, which
# paid for 8 neighbours instead of 5 (53 → 58, a third less printed); past 8 the gains flatten, and a third step adds none.
PER_HIT, DEPTH = 8, 2
PER_FILE = 2  # sections of one document among a search's results
LEAD, SNIP, ARC_MAX = 0, 14, 0  # a neighbour's opening characters (0: none), a hit's excerpt in words, arc steps listed (0: all)
STEP_RELS = ("led-to", "strengthens", "weakens")  # what a second step follows: story steps and theory, not page lists
REL = {("timeline", "out"): "led to", ("timeline", "in"): "led from", ("evidence", "out"): "bears on",
       ("evidence", "in"): "evidence for it"}
# Links that list a page's records: the page brings every one, oldest first, and each record names the page it's on.
LISTED = {"occurrence": ("occurrence", "on the timeline of"), "arc-step": ("arc step", "on the arc of")}
# What the record says against itself: shown first at both ends (in, out), with the link's note.
FIXED = {"supersedes": ("outdated by", "outdates"), "revises": ("revised by", "revises"),
         "disagrees": ("disagrees with", "disagrees with")}


def _excluded(source: str, ref: str = "") -> bool:
    """Hidden by the eval runner: a source prefix, and for a session also its passages filed as story rows."""
    for x in filter(None, os.environ.get("ENGRAM_EXCLUDE_SOURCES", "").split(",")):
        if source.startswith(x) or (x.startswith("sessions:") and ref.startswith("session:" + x.split(":")[1] + ":")):
            return True
    return False


def _lead(body: str, width: int | None = None) -> str:
    """A record's opening words, verbatim: the level of detail a neighbour arrives at, so a step can be read without opening it. Exact values still come from the record itself."""
    width = LEAD if width is None else width
    if not width:
        return ""
    lines = body.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):  # the heading is already the title
        lines.pop(0)
    text = " ".join(" ".join(lines).split())
    return text if len(text) <= width else text[:width].rsplit(" ", 1)[0] + " …"


def _surround(path, rows: list[dict], q: str = "", per_hit: int | None = None, weights: dict | None = None):
    """Each hit's neighbours on its stories: what it led from and led to, and the theory it bears on or that rests on
    it. When a hit has more than `per_hit`, the ones sharing the most words with the query come first, scaled by the
    lens's weight for each, steps before theory; a neighbour already on the page isn't repeated. A recurring symptom's
    timeline brings every occurrence it holds, oldest first (docs/evaluation.md, "Waxing and waning")."""
    from engram.units import norm
    idx = open_index(path, readonly=True)
    if idx is None:
        return
    per_hit = per_hit or PER_HIT
    words = {t.lower() for t in TERM.findall(q) if len(t) > 2}
    shown = {r["ref"] for r in rows}
    shown |= {m for r in rows for m in (r.get("unit") or {}).get("members", []) + (r.get("unit") or {}).get("hidden", [])}  # a unit carries its versions
    try:
        for r in rows:
            hit = (idx.db.execute("SELECT parent FROM doc WHERE ref = ?", (r["ref"],)).fetchone() or [None])[0] or r["ref"]
            near = [(fam, rel, "out", x, story, n, ev) for fam, rel, x, story, n, ev in idx.db.execute(
                "SELECT family, rel, to_ref, story, note, event FROM link WHERE family IN ('timeline', 'evidence') AND from_ref = ?", (hit,))]
            near += [(fam, rel, "in", x, story, n, ev) for fam, rel, x, story, n, ev in idx.db.execute(
                "SELECT family, rel, from_ref, story, note, event FROM link WHERE family IN ('timeline', 'evidence') AND to_ref = ?", (hit,))]
            if DEPTH > 1:  # a second step out along story steps and theory, ranked below the first
                first = {x for _, rel, _, x, *_ in near if rel in STEP_RELS}
                for x in first:
                    near += [(fam, rel, "far", y, story, n, ev) for fam, rel, y, story, n, ev in idx.db.execute(
                        f"SELECT family, rel, to_ref, story, note, event FROM link WHERE rel IN {STEP_RELS} AND from_ref = ?", (x,))]
                    near += [(fam, rel, "far", y, story, n, ev) for fam, rel, y, story, n, ev in idx.db.execute(
                        f"SELECT family, rel, from_ref, story, note, event FROM link WHERE rel IN {STEP_RELS} AND to_ref = ?", (x,))]
            seen, scored, timeline, fixed = set(), [], [], []  # fixed: flags and the pages a record is on, outside the cap
            near.sort(key=lambda x: x[1] not in FIXED)  # a neighbour that's also a flag shows as the flag
            for fam, rel, way, ref, story, why, ev in near:
                if ref in seen or ref == hit:
                    continue
                seen.add(ref)
                rows_ = idx.db.execute("SELECT title, body, source, date_key, class, author, node, milestone FROM doc WHERE ref = ? OR parent = ?", (ref, ref)).fetchall()
                if any(_excluded(x[2], ref) for x in rows_):
                    continue
                title = rows_[0][0] if rows_ else ref
                lead = _lead(rows_[0][1]) if rows_ else ""
                if rel in FIXED:  # a flag shows first at both ends: on what was outdated, and on what outdated it
                    fixed.insert(0, {"rel": FIXED[rel][way != "in"], "ref": ref, "story": story,
                                     "title": f"{title} — {why}" if why else title, "lead": lead})
                    continue
                if rel in LISTED:
                    n = {"rel": LISTED[rel][way == "in"], "ref": ref, "story": story, "title": title}
                    if way == "out":  # an arc lists its steps in its own order, by headline; occurrences go by date
                        if rel == "arc-step":
                            timeline.append((ev or "", {**n, "title": why or title}))
                        else:
                            timeline.append(((rows_[0][3] if rows_ else None) or "9999", {**n, "lead": lead}))
                        continue
                    fixed.append(n)  # a listed record always shows the page it's on
                    continue
                if ref in shown:
                    continue
                text = " ".join(f"{t} {b}" for t, b, *_ in rows_).lower()
                overlap = sum(1 for w in words if w in text)
                if weights:
                    typed_row = {"ref": ref, **dict(zip(("class", "author", "node", "milestone"), rows_[0][4:] if rows_ else ()))}
                    overlap = (overlap + 1) * lens_factor(typed_row, weights)
                if way == "far":
                    overlap *= 0.5
                scored.append((-overlap, fam != "timeline", {"rel": "two steps on" if way == "far" else REL[(fam, way)], "ref": ref,
                                                             "story": story, "title": title, "lead": lead}))
            scored.sort(key=lambda x: (x[0], x[1]))
            fixed.sort(key=lambda n: n["rel"] not in {x for v in FIXED.values() for x in v})
            listed = sorted(timeline, key=lambda x: x[0])
            if ARC_MAX and len(listed) > ARC_MAX:  # the steps sharing the most words with the query, kept in order
                keep = sorted(range(len(listed)), key=lambda i: -sum(w in listed[i][1]["title"].lower() for w in words))[:ARC_MAX]
                listed = [listed[i] for i in sorted(keep)]
            pick = fixed + [n for _, n in listed] + [n for *_, n in scored[:per_hit]]
            pick = [n for n in pick if (n["ref"] not in shown and norm(n["ref"]) not in shown) or n["rel"] in {v[0] for v in LISTED.values()}]
            shown |= {n["ref"] for n in pick}
            if pick:
                r["surroundings"] = pick
    finally:
        idx.close()


def search(q: str, domains: list[str], limit: int = 10, **filters) -> list[dict]:
    lists = [search_domain(d, q, limit, **filters) for d in domains]
    lists = [l for l in lists if l]
    if len(lists) <= 1:
        merged = lists[0] if lists else []
    else:
        fused = {}
        for l in lists:
            for rank, r in enumerate(l, 1):
                key = (r["domain"], r["ref"])
                fused.setdefault(key, {**r, "rrf": 0.0})["rrf"] += 1.0 / (RRF_K + rank)
        merged = sorted(fused.values(), key=lambda r: -r["rrf"])
        for r in merged:
            r["factors"]["rrf"] = round(r.pop("rrf"), 5)
    merged = merged[:limit]
    for i, r in enumerate(merged, 1):
        r["rank"] = i
    return merged
