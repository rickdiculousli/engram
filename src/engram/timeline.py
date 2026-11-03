"""A story's or a recurring symptom's whole chain in time order: the frame Claude reads before talking about a complaint,
instead of whole logs across files. It's cleaned deterministically for reading: what
serves only indexing and search (story and series tags, ids, the file path inside every title, a date the ref already
gives, default values) is left out."""
import json
import re
from datetime import date

from engram import config, dates, labels, periods
from engram.index import open_index
from engram.paths import index_path, record_toml
from engram.sources.events import is_event_ref

APART = ("theory/", "now:")  # a theory thread shows in the theory block, and where things stand isn't history



def names(domain: str) -> dict[str, list[str]]:
    """The chains there are: stories, recurring symptoms (complaint pages), and the ways in by kind."""
    idx = open_index(index_path(domain), readonly=True)
    if idx is None:
        return {"stories": [], "symptoms": []}
    from engram.search import repo_conf
    from engram.sources import waysin
    stories = [s for (s,) in idx.db.execute("SELECT DISTINCT story FROM on_story ORDER BY story")]
    folder = (waysin.recurring(repo_conf(domain)) or ("",))[0]
    symptoms = sorted({r[0].split("/", 1)[1].split(".md")[0] for r in idx.db.execute(
        "SELECT ref FROM doc WHERE ref LIKE ?", (f"{folder}/%",))}) if folder else []
    ways: dict[str, list[str]] = {}
    if idx.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'way'").fetchone():
        for kind, key in idx.db.execute("SELECT DISTINCT kind, key FROM way WHERE kind NOT IN ('symptom') ORDER BY kind, key"):
            ways.setdefault(kind, []).append(key)
    idx.close()
    return {"stories": stories, "symptoms": symptoms, **ways}


def _what(title: str, ref: str, date: str | None) -> str:
    """A row's headline, since its short name says nothing: where it sits (a log's name, else the document's title) and
    its heading, the date dropped."""
    path = title.split(" › ")[1:] or [title]
    head = path[-1]
    if date and head.startswith(date):
        head = re.sub(r"^\(approx(imate|\.)?\)\s*", "", head[len(date):].lstrip(" —-:"), flags=re.I)  # the date column says ~
    file = ref.split("#", 1)[0]
    if is_event_ref(ref):  # an entry: its treatment or series, as its log's name once was
        path = title.split(" › ")
        head = path[-1]
        if date and head.startswith(date):
            head = re.sub(r"^\(approx(imate|\.)?\)\s*", "", head[len(date):].lstrip(" —-:"), flags=re.I)
        return " › ".join(x for x in dict.fromkeys((path[0], head)) if x)
    context = file.rsplit("/", 1)[-1].rsplit(".", 1)[0] if file.startswith("logs/") else path[0] if len(path) > 1 else ""
    if not context and not head:
        return file
    return " › ".join(x for x in dict.fromkeys((context, head)) if x)


HEADLINE = 12  # words; the full record is one call away (docs/search.md, "The one-call timeline")
SEEDS, SHARE = 20, 0.4  # a question picks the stories its top 20 hits mostly sit on (each within 40% of the top vote)


def pick(domain: str, about: str, ways: bool = True, votes_out: dict | None = None) -> tuple[list[str], list[str]]:
    """(stories, direct matches) for free text. The search's top hits vote for their stories, a hit's vote shrinking with
    its rank. Each way in the text names (a clinician, a treatment, a test…) adds the records it lights, without a vote:
    voting them in measured slightly worse."""
    from engram import search
    from engram.sources import waysin
    hits = [h["ref"] for h in search.search(about, [domain], limit=SEEDS, surround=False)]
    idx = open_index(index_path(domain), readonly=True)
    db = idx.db
    on = lambda ref: {s for (s,) in db.execute("SELECT story FROM on_story WHERE ref = ?", (ref.split("@")[0],))}
    votes: dict[str, float] = {}
    for rank, ref in enumerate(hits, 1):
        for s in on(ref):
            votes[s] = votes.get(s, 0) + 1 / rank
    lit = []
    for kind, key, _ in (waysin.named(db, about) if ways else []):
        lit += [r for (r,) in db.execute("SELECT ref FROM way_ref WHERE kind = ? AND key = ?", (kind, key))]
    idx.close()
    top = max(votes.values(), default=0)
    if votes_out is not None:  # each story's share of the vote, for the loops the question touches
        votes_out.update({s: v / top for s, v in votes.items()} if top else {})
    return sorted(s for s, v in votes.items() if v >= SHARE * top), list(dict.fromkeys(hits + lit))


def chain(domain: str, names: str | list[str], about: str | None = None) -> tuple[dict, list[dict]]:
    """(header, rows) for stories and recurring symptoms merged into one timeline, rows in time order, undated standing
    sections after. Free text (`about`) adds the stories its search hits sit on, the hits themselves, and one step out:
    records a led-to link joins to a row from another story, so interleaving complaints arrive in the same call."""
    names = [names] if isinstance(names, str) else list(names)
    asked = list(names)  # the chains the caller named, before the search adds its picks
    hits: list[str] = []
    within = None
    if not about and len(names) == 1:  # a recurring symptom by name: its listed occurrences, plus what its words pick
        about = _symptom_words(domain, names[0])
    votes: dict[str, float] = {}
    if about:
        picked, hits = pick(domain, about, votes_out=votes)
        names += [s for s in picked if s not in names]
        within = periods.period(about, dated=lambda phrase: _first_date(domain, phrase))
    idx = open_index(index_path(domain), readonly=True)
    if idx is None:
        return {}, []
    db = idx.db
    from engram.search import repo_conf
    from engram.sources import waysin
    conf = repo_conf(domain)
    known = labels.people(conf)
    folder = (waysin.recurring(conf) or ("",))[0]
    on: dict[str, list[str]] = {}  # ref -> the chains here it's on
    kinds = []
    for name in names:
        page = waysin.page(conf, name)
        if folder and db.execute("SELECT 1 FROM doc WHERE ref = ? OR parent = ?", (page, page)).fetchone():
            refs = [r[0] for r in db.execute("SELECT to_ref FROM link WHERE rel = 'occurrence' AND from_ref = ?", (page,))]
            kinds.append("symptom")
        elif refs := [r[0] for r in db.execute("SELECT ref FROM on_story WHERE story = ?", (name,))]:
            kinds.append("story")
        else:  # a clinician, treatment, test or theory node, by its key or a phrase naming it
            refs = list(dict.fromkeys(r[0] for r in db.execute(
                "SELECT r.ref FROM way w JOIN way_ref r ON r.kind = w.kind AND r.key = w.key WHERE w.key = ? OR w.phrase = ?",
                (name.lower(), name.lower()))))
            if any(r.startswith("theory/") for r in refs):  # a loop or condition: the records that bear on it
                refs += [f for r in refs if r.startswith("theory/") for (f,) in db.execute(
                    "SELECT from_ref FROM link WHERE to_ref = ? AND family = 'evidence'", (r,))]
            kinds.append(next((k for (k,) in db.execute("SELECT kind FROM way WHERE key = ? OR phrase = ?", (name.lower(), name.lower()))), "story"))
        for ref in refs:
            on.setdefault(ref, []).append(name)
    if about:
        for ref in hits:
            on.setdefault(ref, [])
        for ref in list(on):
            for (b,) in db.execute("SELECT to_ref FROM link WHERE rel = 'led-to' AND from_ref = ? UNION "
                                   "SELECT from_ref FROM link WHERE rel = 'led-to' AND to_ref = ?", (ref, ref)):
                on.setdefault(b, [])
    from engram import units
    from engram.search import _excluded, now_lines
    then = str(within[1]) if within and within[1] < date.today() else None  # a question about the past: theory as it stood
    when, hide = then, False
    if day := units.session_day(db):
        when, hide = day, True  # as things stood for a question taken from a session: nothing said after it
    g, now_of = units.graph(db), now_lines(domain)
    cache: dict[str, object] = {}

    def unit_of(ref: str):
        if ref not in cache:
            cache[ref] = units.build(db, g, ref, when, hide, known, _excluded, now_of)
        return cache[ref]
    for ref in list(on):  # a fact's current version comes with it, wherever it's filed (the owner); the row it
        if (u := unit_of(ref)) and u.centre != units.norm(ref):  # corrects folds into it
            on.setdefault(u.centre, [])
            on[u.centre] = list(dict.fromkeys(on[u.centre] + on[ref]))
    rows = []
    for ref, chains in on.items():
        if ref.startswith(APART):
            continue
        src = db.execute("SELECT source FROM doc WHERE ref = ? OR parent = ? LIMIT 1", (ref, ref)).fetchone()
        if src and _excluded(src[0], ref):  # a session-origin question never sees its own session (eval runner)
            continue
        d = db.execute("SELECT title, date, date_key, author, node, milestone, stories, nid FROM doc WHERE ref = ? OR parent = ? LIMIT 1",
                       (ref, ref)).fetchone()
        if d:
            rows.append({"ref": ref, "title": d[0], "date": d[1], "key": d[2], "who": labels.who(d[3], known), "kind": d[4], "m": d[5],
                         "on": chains or [s for s in (d[6] or "").split(",") if s] or ["search match"], "nid": d[7]})
    rows = _whole(db, rows, repo_conf(domain).get("timeline", {}).get("whole", []), known)
    rows.sort(key=lambda r: (r["key"] is None, r["key"] or "", r["date"] or ""))
    direct = set(hits)
    direct |= {r["ref"] for r in rows if direct & set(r.get("parts", []))}
    rows, folded = _units(rows, unit_of, direct)
    num = {r["ref"]: i for i, r in enumerate(rows, 1)}
    num |= {p: num[r["ref"]] for r in rows for p in r.get("parts", [])}  # a link to a consult's section points at its row
    num |= {m: num[r] for m, r in folded.items()}  # a version shown on its unit's row points at that row
    has_sum = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'rec_summary'").fetchone()

    def summary(r: dict) -> str:  # direct matches carry one; every other row is its headline (the owner)
        if not has_sum or r["ref"] not in direct:
            return ""
        for ref in [x for x in r.get("parts", []) if x in hits] or [r["ref"]]:  # a whole consult: the matched section's
            if s := db.execute("SELECT summary FROM rec_summary WHERE ref = ?", (ref,)).fetchone():
                return s[0]
        return ""

    def at(ref: str) -> str:  # a row number here, else the record's short name
        if ref in num:
            return str(num[ref])
        n = db.execute("SELECT nid FROM doc WHERE ref = ? OR parent = ? LIMIT 1", (ref, ref)).fetchone()
        return n[0] if n else ref
    merged = len(names) > 1 or about
    out, said_now = [], set()
    for i, r in enumerate(rows, 1):
        row = {"n": i, "_ref": r["ref"], **({"_parts": r["parts"]} if r.get("parts") else {})}
        if r["date"]:
            approx = re.search(re.escape(r["date"]) + r"\s*\(approx", r["title"], re.I)
            row["date"] = ("~" if approx else "") + r["date"]
        if merged:
            row["on"] = ", ".join(r["on"])  # which complaints a row belongs to: one marks a lane, two or more an interleaving
        if r["who"]:
            row["who"] = r["who"]
        if r["kind"]:
            row["kind"] = r["kind"]
        if r["m"]:
            row["milestone"] = 1
        if folder and r["ref"].startswith(f"{folder}/"):  # a recurring symptom on this story: its own chain holds the occurrences
            row["what"] = f"recurring symptom: engram timeline {r['ref'].split('/', 1)[1].split('.md')[0]}"
        else:
            words = _what(r["title"], r["ref"], r["date"]).split()
            row["what"] = " ".join(words[:HEADLINE]) + ("…" if len(words) > HEADLINE else "")
        if s := summary(r):
            row["summary"] = s
        row["id"] = r["nid"]
        ends = r.get("parts") or [r["ref"]]
        after = sorted({num[a] for e in ends for (a,) in db.execute("SELECT from_ref FROM link WHERE rel = 'led-to' AND to_ref = ?", (e,))
                        if a in num and num[a] != i})
        if after:
            row["after"] = after  # the rows it follows on; two or more is a join, and a row followed twice is a split
        for u in r.get("units", []):  # its other versions inline, one line each, and where its thing stands
            if u.lines or u.more:
                row.setdefault("versions", []).extend(
                    (("beside it: " if l["side"] else "") + units.line(l) for l in u.lines))
                if u.more:
                    row["versions"].append(f"{u.more} more versions")
            if u.now and u.now not in said_now:
                row["now"] = u.now
                said_now.add(u.now)
        if r.get("of"):
            row["version of"] = at(r["of"])
        if r.get("_versions"):
            row["_unit"] = r["_versions"]
        out.append(row)
    theory = _theory(db, num, domain, then, asked, about, votes)
    idx.close()
    dated = sum(1 for r in rows if r["key"])
    header = {"chain": ", ".join(names), "kind": kinds[0] if len(set(kinds)) == 1 and len(kinds) == 1 else "merged",
              "picked from": f"search for {about!r}" if about else None,
              "period": f"{within[0]} to {within[1]} (the question's; nothing is cut)" if within else None, "records": len(out),
              "from": next((r["date"] for r in rows if r["key"]), None), "to": rows[dated - 1]["date"] if dated else None,
              "undated after": dated if dated < len(out) else None,
              "theory": len(theory) or None,
              "versions": "a fact's other versions, one line each (date who: what changed [id]); beside it: disagrees, "
                          "none is the answer" if any("versions" in r for r in out) else None,
              "read a record": "engram show <id>" + (f" (as it stood: --as-of {then})" if then else ""),
              "key": config.voice(labels.KEY)}
    return {k: v for k, v in header.items() if v is not None}, out + theory


def _then(domain: str, key: str, then: str) -> str:
    """How a theory file stood on a date, as git shows it: begun later, as it is now, or revised since (with the days);
    `engram show <id> --as-of <date>` reads the old text."""
    from engram import asof, config
    repo = config.load()[domain].repo
    rel = key.split("#", 1)[0]
    days = asof.revised(repo, rel) if repo and (repo / rel).exists() else []
    if not days:
        return ""
    if days[0] > then:  # the idea may be older, written elsewhere before it had its own file
        home = asof.then_home(repo, rel, then)
        return f"then in {home[0].split('#')[0]} (committed {home[1]})" if home else f"file began {days[0]}"
    later = [x for x in days if x > then]
    return f"revised since: {', '.join(later)}" if later else "as now"


def _units(rows: list[dict], unit_of, direct: set[str]) -> tuple[list[dict], dict[str, str]]:
    """Each fact once, with its versions (docs/search.md, "A fact and its corrections"): a row carries its unit (a
    whole document, those of its sections that are hits). A unit shows on one row, the current version's when it's
    here, else the earliest version's; a single record among the versions that row lists folds into it, and one past
    the cap stays a row of its own, pointing at it ("version of"), so nothing is printed twice. Returns the rows and
    {folded record: the row it folded into}."""
    from engram import units
    for r in rows:
        ends = r.get("parts") or [r["ref"]]
        r["units"] = [u for e in (ends if len(ends) == 1 else [e for e in ends if e in direct]) if (u := unit_of(e))]
    single = {units.norm(r["ref"]): r for r in rows if not r.get("parts")}
    folded: dict[str, str] = {}
    done: set[str] = set()
    for r in rows:
        if r.get("parts") or not r["units"] or r["ref"] in done:
            continue
        rep = single.get(r["units"][0].centre) or r  # rows come in time order: r is the earliest version here
        if rep["ref"] in done:
            continue
        done.add(rep["ref"])
        u = rep["units"][0] if rep["units"] else r["units"][0]
        listed = {l["ref"] for l in u.lines}
        for m in u.members:
            if m in single and single[m] is not rep and single[m]["ref"] not in done:
                done.add(single[m]["ref"])
                if m in listed:
                    folded[single[m]["ref"]] = rep["ref"]
                else:
                    single[m]["of"], single[m]["units"] = rep["ref"], []
    out = [r for r in rows if r["ref"] not in folded]
    for r in out:  # the versions in hand on the row that shows them
        r["_versions"] = list(dict.fromkeys(x for u in r["units"] for x in u.shown))
    return out, folded


def _whole(db, rows: list[dict], patterns: list[str], known: dict | None = None) -> list[dict]:
    """Rows from a file the record names as one item (a consult: one visit) merged into one row for the file: its first
    heading as the headline, its earliest date, any milestone, every story its sections are on. Its sections stay
    searchable on their own; `engram show <id>` opens the whole file."""
    from fnmatch import fnmatchcase
    out, groups = [], {}
    for r in rows:
        file = r["ref"].split("#", 1)[0]
        if "#" in r["ref"] and any(fnmatchcase(file, p) for p in patterns):
            groups.setdefault(file, []).append(r)
        else:
            out.append(r)
    for file, parts in groups.items():
        first = db.execute("SELECT title, date, date_key, author FROM doc WHERE ref LIKE ? ORDER BY rowid LIMIT 1",
                           (file.replace("%", r"\%") + "#%",)).fetchone()
        dated = sorted((p for p in parts if p["key"]), key=lambda p: p["key"])
        lead = dated[0] if dated else parts[0]
        file_rows = db.execute("SELECT node, author, milestone FROM doc WHERE ref LIKE ? ORDER BY rowid", (file.replace("%", r"\%") + "#%",)).fetchall()
        visit = next(({"who": labels.who(a, known or {}), "kind": n} for n, a, _ in file_rows if n == "visit"), None)  # the whole file's, not just the parts here
        when = re.search(r"20\d\d-\d\d(-\d\d)?", first[0]) if first else None  # the visit's own date, from its heading
        date = when.group(0) if when else lead["date"]
        out.append({**lead, "ref": file, "title": first[0] if first else lead["title"], "nid": labels.nid(file),
                    "date": date, "key": dates.key(date) if when else lead["key"],
                    "who": (visit or {}).get("who") or next((p["who"] for p in parts if p["who"]), ""),
                    "m": int(any(p["m"] for p in parts) or any(m for *_, m in file_rows)), "kind": "visit" if visit else lead["kind"],
                    "on": sorted({s for p in parts for s in p["on"]}), "parts": [p["ref"] for p in parts]})
    return out


def _symptom_words(domain: str, name: str) -> str | None:
    """A recurring symptom's name and the owner's words for it, from its page; None for anything else. Its listed occurrences
    held 38 of the 56 the waxing questions expect; picking by its words as well held all 56."""
    from engram.search import repo_conf
    from engram.sources import waysin
    folder = (waysin.recurring(repo_conf(domain)) or ("",))[0]
    idx = open_index(index_path(domain), readonly=True) if folder else None
    row = idx.db.execute("SELECT body FROM doc WHERE ref LIKE ? ORDER BY rowid LIMIT 1", (f"{folder}/{name}.md#%",)).fetchone() if idx else None
    if idx:
        idx.close()
    if not row:
        return None
    words = re.search(re.escape(config.owner()) + r"'s words:\s*“([^”]+)”", row[0])
    return f"{name.replace('-', ' ')} {words.group(1) if words else ''}".strip()


def _first_date(domain: str, phrase: str):
    """The first date the record has for a thing a question names ("since the PRF"): the earliest dated record of a way
    in the phrase names, else of the phrase's top search hits."""
    from engram import search
    from engram.sources import waysin
    idx = open_index(index_path(domain), readonly=True)
    refs = [r for kind, key, _ in waysin.named(idx.db, phrase)
            for (r,) in idx.db.execute("SELECT ref FROM way_ref WHERE kind = ? AND key = ?", (kind, key))]
    refs = refs or [h["ref"] for h in search.search(phrase, [domain], limit=3, surround=False)]
    keys = sorted(k for r in refs for (k,) in idx.db.execute(
        "SELECT date_key FROM doc WHERE (ref = ? OR parent = ?) AND date_key IS NOT NULL", (r, r)))
    idx.close()
    return periods.span(keys[0])[0] if keys else None


JOIN_FOCUS = 5  # joins are shown on the loops shown, what the question names, and the five theories cited most


def lit_of(g, weight: dict[str, float]) -> set[str]:
    """The conditions and states on the stories a question is about."""
    return {t for t, x in g.things.items() if x.kind in ("node", "state") and set(x.stories) & set(weight)}


def _theory(db, num: dict[str, int], domain: str | None = None, then: str | None = None, names: list[str] = (),
            about: str | None = None, votes: dict[str, float] | None = None) -> list[dict]:
    """The theory the rows bear on (.engram/README.md, "The theory comes with the history"): each diagnosis or mechanism
    a row strengthens or weakens, with its status, how many rows support it and which weaken it, most-cited first;
    `engram timeline <node>` gives a node's own history. A discovery or pattern file is one node; any other target
    section is its own. Then the loops the question touches, each with its path drawn (unrelated loops stay out), and
    the joins among what's shown; `engram theory` prints the whole graph."""
    from engram import config, theory as th
    repo = config.load()[domain].repo if domain else None
    g = th.load(repo) if repo and record_toml(repo).exists() else th.Graph({}, [], {})
    by_file = {t.file: t for t in g.things.values() if t.file}
    nodes: dict[str, dict] = {}
    loop_ev: dict[str, dict[str, set]] = {}
    for ref, n in num.items():
        for to, rel in db.execute("SELECT to_ref, rel FROM link WHERE from_ref = ? AND rel IN ('strengthens', 'weakens')", (ref,)):
            file = to.split("#", 1)[0]
            thing = by_file.get(file)
            if thing and thing.kind in ("loop", "node", "state", "treatment"):  # a loop shows below, with its path
                loop_ev.setdefault(thing.id, {"for": set(), "against": set()})["for" if rel == "strengthens" else "against"].add(n)
                continue
            key = file if re.search(r"/D\d+-", file) or file.startswith(("evidence/staging/", "questions/")) else to
            node = nodes.setdefault(key, {"for": set(), "against": set(), "refs": set()})
            node["for" if rel == "strengthens" else "against"].add(n)
            node["refs"].add(to)
    out, shown, cited_order = [], set(), []
    for key, node in sorted(nodes.items(), key=lambda kv: -len(kv[1]["for"] | kv[1]["against"])):
        head = db.execute("SELECT title, body, nid FROM doc WHERE ref = ? OR ref = ? OR parent = ? ORDER BY rowid LIMIT 1",
                          (key + "#", key, key)).fetchone()
        if not head:
            continue
        thing = by_file.get(key)
        title = re.search(r"^title:\s*(.+)$", head[1], re.M)
        status = g.status.get(thing.id, ("",))[0] if thing else ""
        if not status and (m := re.search(r"^status:\s*(\S+)", head[1], re.M)):
            status = m.group(1)
        m = re.search(r"/(D\d+)-", key)
        row = {"theory": m.group(1) if m else thing.short if thing else head[0].split(" › ")[-1],
               "status": status,
               "what": title.group(1).strip().strip('"') if title else thing.title if thing else head[0].split(" › ")[-1],
               "then": _then(domain, key, then) if then else "",
               "for": len(node["for"]), "against": sorted(node["against"]) if len(node["against"]) <= 10 else len(node["against"]),
               "id": head[2], "_refs": sorted(node["refs"])}  # rows for, counted; rows against, listed while few
        if thing:
            shown.add(thing.id)
            cited_order.append(thing.id)
        out.append({k: v for k, v in row.items() if v or k in ("theory", "id")})
    every = {s for (s,) in db.execute("SELECT DISTINCT story FROM on_story")}
    weight = {s: v for s, v in (votes or {}).items() if s in every}
    words = set(re.findall(r"[a-z]+", (about or "").lower()))
    for s in every:  # a story the question names outright ("neck", "the skin"), or a chain named by the caller
        if s in names or any(p in words or p + "s" in words or p.rstrip("s") in words for p in s.split("-") if len(p) > 2):
            weight[s] = 1.0
    from engram.sources import waysin
    ways = waysin.named(db, about) if about else []
    ways += [(k, key, n) for n in names for k, key in db.execute(
        "SELECT DISTINCT kind, key FROM way WHERE key = ? OR phrase = ?", (n, n.lower()))] if db.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'way'").fetchone() else []
    named = {n for n in names if n in g.things}  # a theory thing the question or the caller names: by its key, or a
    for kind, key, _ in ways:                    # treatment by its own name
        thing = key if kind == "theory" else f"treatment/{key.replace(' ', '-')}" if kind == "treatment" else ""
        if thing in g.things or (kind == "theory" and f"discovery/{key}" in g.things):
            named.add(thing if thing in g.things else f"discovery/{key}")
    refs_of = lambda t: [r for (r,) in db.execute("SELECT DISTINCT coalesce(parent, ref) FROM doc WHERE ref LIKE ?",
                                                  ((g.things[t].file if t in g.things else "-") + "#%",))]
    loops = g.touched(weight, named)
    for l in loops:
        doc = th.node_doc(g, l, refs_of(l))
        nid = db.execute("SELECT nid FROM doc WHERE ref = ? OR parent = ? LIMIT 1", (doc, doc)).fetchone() if doc else None
        ev = loop_ev.get(l, {"for": set(), "against": set()})
        row = {"theory": g.things[l].short, "status": g.status.get(l, ("",))[0],
               "what": f"{g.things[l].title.split(' — ', 1)[-1]}: {g.draw(l)}", "for": len(ev["for"]),
               "against": sorted(ev["against"]) if len(ev["against"]) <= 10 else len(ev["against"]),
               "id": nid[0] if nid else "", "_refs": [doc] if doc else []}
        out.append({k: v for k, v in row.items() if v != [] or k == "_refs"})
        shown |= {l, *g.path(l)}
    cited = [t for t in cited_order if t.startswith(("discovery/", "pattern/"))]
    focus = set(loops) | named | set(cited[:JOIN_FOCUS])  # the joins on what the answer leans on most
    near = shown | lit_of(g, weight) | named
    rows: dict[str, dict] = {}  # one row per join, even when it reaches several loops (SNS → all loops)
    for e in g.joins():
        if not ({e.a, e.b} & named or ({e.a, e.b} & focus and {e.a, e.b} <= near | focus)):
            continue  # every join on a thing the question names; otherwise only among what's shown
        key = e.entry or e.id
        r = rows.setdefault(key, {"a": e.a, "b": [], "e": e})
        r["b"].append(e.b)
    for key, r in rows.items():
        e, ends = r["e"], r["b"]
        to = "all loops" if len(ends) == len(g.loops()) and all(b in g.loops() for b in ends) else ", ".join(g.label(b) for b in ends)
        nid = db.execute("SELECT nid FROM doc WHERE ref = ? LIMIT 1", (e.entry,)).fetchone() if e.entry else None
        out.append({"theory": "join", "status": e.strength, "what": f"{g.label(e.a)} → {to}, {e.rel}: {e.note}",
                    "id": nid[0] if nid else "", "_refs": [e.entry] if e.entry else []})
    return out


def render(header: dict, rows: list[dict], fmt: str = "jsonl") -> str:
    """JSON lines, or a table with the columns named once (`tsv`), whichever reads in fewer tokens."""
    if fmt == "tsv":
        theory = [r for r in rows if "theory" in r]
        rows = [r for r in rows if "theory" not in r]
        lead = [c for c in ("n", "date", "on", "who", "kind", "milestone", "what", "summary", "id", "after")
                if c not in ("on", "summary") or any(c in r for r in rows)]
        cols = lead + sorted({k for r in rows for k in r if not k.startswith("_")} - set(lead))
        cell = lambda v: re.sub(r"\s+", " ", "; ".join(map(str, v)) if isinstance(v, list) else str(v))
        lines = [json.dumps(header, ensure_ascii=False, separators=(",", ":")), "\t".join(cols)]
        lines += ["\t".join(cell(r.get(c, "")) for c in cols) for r in rows]
        if theory:
            tcols = ["theory", "status"] + (["then"] if any("then" in r for r in theory) else []) + ["what", "for", "against", "id"]
            lines += ["", "\t".join(tcols)] + ["\t".join(cell(r.get(c, "")) for c in tcols) for r in theory]
        return "\n".join(lines)
    return "\n".join(json.dumps({k: v for k, v in x.items() if not k.startswith("_")}, ensure_ascii=False, separators=(",", ":"))
                     for x in [header, *rows])
