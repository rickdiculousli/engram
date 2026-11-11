"""The evidence re-check after a structural theory revision (.engram/README.md, "A theory revision is made in the
conversation"). When a
condition is added, a loop gains or loses a step, or a join is added or retired, the evidence linking the record to the
theory may need to move. Opus at low effort reads every entry and document of the record, in batches, with no search in
front of it (a filter decides silently what the judge never sees), alongside the part of the model that changed, and
says which records bear on what changed:

- a record that bears on a new thing, a revised loop or a new join: an evidence link to it (strengthens or weakens);
- a record that was evidence for a retired step: the new step's member it supports (moved), or a link to the retired
  step saying it was evidence for the old version only.

Code checks every record id and target against the batch and the change, and drops repeats of links already held.
Links are filed by=claude, as placement, never as the owner's claims. The timeline and the stories don't change. Each
change runs once; its outcome is one line in the next session's `engram now` (theorychange.notices)."""
import contextlib
import fcntl
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from engram import commitmsg, config, docreg, frontmatter, llm, notes, pack, recsum, theory, theorychange
from engram.paths import data_path, record_conf
from engram.store import Store
from engram.now import RENEWAL

BUDGET = 90_000  # characters of records per call; a record is never cut, and one bigger than this goes alone
SKIP_FILES = ("AGENTS.md", "CLAUDE.md", "README.md")


@dataclass(frozen=True)
class Rel:
    """One way a record links to a theory thing: its label, what it means (what the confirming call checks a link
    against), the theory kinds it may point at (None: any the job reads against), and whether its passage must be the
    owner's own words."""
    id: str
    label: str
    to: frozenset[str] | None = None
    means: str = ""
    owner_words: bool = False

    def shown(self) -> str:
        return f"{self.label}: {self.means}" if self.means else self.label


@dataclass(frozen=True)
class Kinds:
    """A record's link kinds between its moments and its theory: the links' family and rels, the theory kinds the
    linking job reads against, the records it never reads (by who said them, by kind), whether it runs in the hourly
    job, whether a record bears on a thing one way only (for and against exclude each other), and its commit's
    template."""
    family: str
    rels: dict[str, Rel]
    targets: frozenset[str]
    skip_by: frozenset[str] = frozenset()
    skip_kinds: frozenset[str] = frozenset()
    hourly: bool = False
    one_way: bool = False
    template: str = "moments"

    def text(self) -> str:
        """The kinds as the read's words list them."""
        return "\n".join(f"- {r.id} ({r.label}): {r.means}" + (f"; on a {', '.join(sorted(r.to))}" if r.to else "") +
                         (f"; only on {config.owner()}'s own words" if r.owner_words else "") for r in self.rels.values())


EVIDENCE = Kinds("evidence", {r: Rel(r, r) for r in ("strengthens", "weakens")}, frozenset({"loop", "discovery"}),
                 one_way=True, template="sweep")  # a record that names no link kinds of its own


def kinds(repo: Path | None) -> Kinds:
    """The record's link kinds (`[links.moment]`, each rel a table: `label`, `means`, `to`, `owner_words`), else
    strengthens and weakens on loops and Discoveries. A kind with no `to` points at any target; the job reads against
    every theory kind a kind names, or with none named, the loops and the record's own theory kinds."""
    conf_ = record_conf(repo) if repo else {}
    conf = (conf_.get("links") or {}).get("moment") or {}
    rels = conf.get("rels")
    if not isinstance(rels, dict) or not rels:
        return EVIDENCE
    out = {str(k): Rel(str(k), str(v.get("label") or k), frozenset(str(x) for x in v["to"]) if "to" in v else None,
                       str(v.get("means") or ""), bool(v.get("owner_words"))) for k, v in rels.items() if isinstance(v, dict)}
    named = frozenset(t for r in out.values() for t in r.to or ())
    return Kinds("moment", out, named or frozenset({"loop", *((conf_.get("theory") or {}).get("kinds") or {})}),
                 frozenset(str(x) for x in conf.get("skip_by") or ()), frozenset(str(x) for x in conf.get("skip_kinds") or ()),
                 bool(conf.get("hourly")))

def _asker(system: str, effort: str = "low"):
    """The re-check's model call, with the pack's `relink_system` words."""
    return lambda prompt: _ask(prompt, system, effort)


def _ask(prompt: str, system: str, effort: str = "low") -> tuple[str, float]:
    text, used = llm.ask(prompt, system, model=recsum.MODEL, effort=effort)
    return text, used["usd"] or 0


def records(repo: Path, skip: tuple[str, ...] = (), kinds_: Kinds = EVIDENCE) -> list[tuple[str, str, str]]:
    """(id, date, text) for every entry and document of the record, each whole: entries by their id, documents by their
    path. The pack's `relink_skip` (theory things, whose links are joins, not evidence; journals; the assistant's own
    files), dot paths, the agents' instructions, the guide's suggestions (never a moment: an idea isn't something that
    happened) and what the link kinds skip, by who said it or by kind, are left out."""
    st, noted = Store(repo), notes.folder(repo)
    skip_re = re.compile("|".join(f"(?:{x})" for x in (re.escape(st.events_dir + "/"), r"\.", *skip)))
    unread = lambda fm: str(fm.get("by", "")) in {theory.SUGGESTION, *kinds_.skip_by} or str(fm.get("kind", "")) in kinds_.skip_kinds
    out = []
    for e in st.events():
        if e.kind in ("link", "status", "capture", RENEWAL) or unread(e.fm):  # a renewal says only "still on it"
            continue
        body = " ".join(e.body.split())
        out.append((e.id, str(e.date), f"{e.fm.get('title') or e.fm.get('heading', '')}: {body}"))
    for p in sorted([*repo.rglob("*.md"), *repo.rglob("*.txt")]):
        rel = p.relative_to(repo).as_posix()
        if skip_re.match(rel) or rel in SKIP_FILES or "/." in rel or p.name.startswith("_"):
            continue
        text = p.read_text(errors="replace")
        try:
            fm = frontmatter.split(text)[0] or {}
        except Exception:  # a page whose front matter doesn't parse is read as it stands
            fm = {}
        if unread(fm):
            continue
        day = str(fm.get("date") or "") if noted and rel.startswith(noted + "/") else ""  # a note is its session's day
        out.append((rel, day, " ".join(text.split())))  # whole: a cut hid what a long one says
    return out


def his_lines(repo: Path, kinds_: Kinds = EVIDENCE) -> tuple[dict[str, list[str]], set[str]]:
    """The owner's own words in each record, line by line, as the lines that name their speaker say (`notes.spoken`:
    a note's lines, an entry's quote of his), for an entry of his and a note: where a record has them, only they can be
    a link's passage; and the notes. Empty where the link kinds need none of his words and the record keeps no notes."""
    folder = notes.folder(repo)
    if not folder and not any(r.owner_words for r in kinds_.rels.values()):
        return {}, set()
    me, st = config.owner(), Store(repo)
    out = {e.id: [q for who, q in notes.spoken(e.body) if who == me] for e in st.events() if str(e.fm.get("by")) == config.owner_id()}
    inside = {n["path"] for n in notes.read(repo)} if folder else set()
    for n in inside:
        out[n] = [q for who, q in notes.spoken((repo / n).read_text(errors="replace")) if who == me]
    return out, inside


def batches(recs: list[tuple[str, str, str]], budget: int = BUDGET) -> list[list[tuple[str, str, str]]]:
    """Records in order, packed into calls of at most `budget` characters each; a record over it is a call alone."""
    out, cur, size = [], [], 0
    for r in recs:
        if cur and size + len(r[2]) > budget:
            out.append(cur)
            cur, size = [], 0
        cur.append(r)
        size += len(r[2])
    return out + ([cur] if cur else [])


def _change_text(s: dict, g: theory.Graph) -> str:
    lines = [f"- new {x['kind']}: {x['id']} ({x['title']})" for x in s.get("new", [])]
    lines += [f"- {x['title'].split(' — ')[0]} was: {x['before'] or '(new)'}; now: {x['after']}" for x in s.get("loops", [])]
    lines += [f"- retired step {x['drawn']} (target id link/{x['id']})" for x in s.get("retired", [])]
    lines += [f"- new join: {g.label(x['from'])} {x['rel']} {g.label(x['to'])}" for x in s.get("joins", [])]
    return "\n".join(lines) or "- (nothing structural)"


def targets(s: dict, g: theory.Graph) -> tuple[list[str], list[str]]:
    """What a link may point at: the new things, the revised loops and their members, a new join's ends; and the
    retired steps (link/<id>)."""
    out = [x["id"] for x in s.get("new", [])]
    for x in s.get("loops", []):
        out += [x["id"], *g.path(x["id"])]
    for x in s.get("joins", []):
        out += [x["from"], x["to"]]
    return [t for t in dict.fromkeys(out) if t in g.things], [f"link/{x['id']}" for x in s.get("retired", [])]


def run(change: str, ask=None, dry_run: bool = False, limit: int | None = None, force: bool = False, confirm=None) -> dict:
    """Re-check one change; returns counts (and, for a dry run, the links it would file). Runs once per change; `force`
    restarts one left running by a crash."""
    with theorychange.db() as c:
        row = c.execute("SELECT repo, summary, state FROM change WHERE id = ?", (change,)).fetchone()
        if not row:
            raise SystemExit(f"engram: no theory change {change}")
        if (row[2] == "done" or (row[2] == "running" and not force)) and not dry_run:
            return {"change": change, "skipped": row[2]}
        if not dry_run:
            c.execute("UPDATE change SET state = 'running' WHERE id = ?", (change,))
    repo, s = Path(row[0]), json.loads(row[1])
    words = pack.for_repo(repo).prompts
    if not words.get("relink"):
        raise SystemExit(f"engram: {repo}'s pack has no `relink` words; its evidence isn't re-checked")
    ask = ask or _asker(words.get("relink_system", ""))
    try:
        return _run(change, repo, s, ask, dry_run, limit, confirm)
    except Exception as e:
        if not dry_run:
            with theorychange.db() as c:
                c.execute("UPDATE change SET state = 'error', error = ? WHERE id = ?", (f"{type(e).__name__}: {e}"[:300], change))
        raise


def _run(change: str, repo: Path, s: dict, ask, dry_run: bool, limit: int | None, confirm=None) -> dict:
    loops = [x["id"] for x in s.get("loops", [])]
    if loops and not dry_run:  # what engram placed on a revised loop is read again against its new path
        recheck(repo, loops, confirm, why=f"theory change {change}")
    st = Store(repo)
    g = theory.load(repo)
    tgts, gone = targets(s, g)
    allowed = set(tgts) | set(gone)
    reg = docreg.load(repo)
    rec_of = _rec_of(reg)
    k = kinds(repo)
    have = {(rec_of(e.fm.get("from")), e.fm.get("to"), e.fm.get("rel")) for e in st.events(kind="link") if e.fm.get("family") == k.family}
    held: dict[str, list[str]] = {}  # record -> the targets its evidence points at now, among what changed
    retired_loops = {x["loop"] for x in s.get("retired", []) if x.get("loop")}
    for e in st.events(kind="link"):
        if e.fm.get("family") == k.family and (e.fm.get("to") in allowed or e.fm.get("to") in retired_loops):
            held.setdefault(rec_of(e.fm.get("from")), []).append(str(e.fm.get("to")))
    p = pack.for_repo(repo)
    recs = records(repo, p.relink_skip, k)
    refused = _refused(st, repo, g, reg, k)
    owner_of = _entry_of(recs, st)
    things = "\n".join(f"{t.id}\t{t.title}" for t in g.things.values() if t.kind in ("node", "state", "loop"))
    why = f"; why: {s['why']}" if s.get("why") else ""
    out = {"change": change, "batches": 0, "records": len(recs), "links": [], "dropped": [], "usd": 0.0}
    for b in batches(recs)[:limit]:
        text = "\n".join(f"[{i}] date {d or 'undated'}" + (f" (now evidence for: {', '.join(held[i])})" if i in held else "") + f"\n{t}\n"
                         for i, d, t in b)
        reply, usd = ask(config.voice(p.prompts["relink"]).format(date=s.get("date", ""), why=why, change=_change_text(s, g), things=things,
                                       targets=", ".join(tgts + gone), retired_ids=", ".join(gone) or "none", records=text))
        out["usd"] += usd
        out["batches"] += 1
        _check(reply, {i: d for i, d, _ in b}, allowed, have, out, gone, refused=refused, owner_of=owner_of, kinds_=k,
               kind_of={t: x.kind for t, x in g.things.items()})
    bear: dict[str, int] = {}
    for ln in out["links"]:
        if not ln["to"].startswith("link/") and not ln["moved_from"]:
            bear[g.label(ln["to"])] = bear.get(g.label(ln["to"]), 0) + 1
    result = {"bear": bear, "moved": sum(1 for x in out["links"] if x["moved_from"]),
              "old_only": sum(1 for x in out["links"] if x["to"].startswith("link/")), "filed": len(out["links"]),
              "dropped": len(out["dropped"]), "records": len(recs)}
    out["result"] = result
    if dry_run:
        return out
    _file(st, g, reg, out["links"], commitmsg.message("relink", change=change), f"re-check after theory change {change}",
          "engram-relink", k)
    with theorychange.db() as c:
        c.execute("UPDATE change SET state = 'done', result = ?, usd = ? WHERE id = ?", (json.dumps(result), out["usd"], change))
    return out


def _rec_of(reg):
    """A document's link end (its id, or an old path) as the record list names it: its path now."""
    def rec_of(x) -> str:
        w = reg.resolve(str(x)) if reg else None
        return w.path if w and w.heading is None else str(x)
    return rec_of


def _norm(text: str) -> str:
    return " ".join(text.lower().split()).strip(" \"'“”.…")


def _check(reply: str, ids: dict[str, str], allowed: set[str], have: set, out: dict, gone=(), off="isn't part of the change",
           texts: dict[str, str] | None = None, refused: set = frozenset(), owner_of=None, kinds_: Kinds = EVIDENCE,
           kind_of: dict[str, str] | None = None, his: tuple[dict[str, list[str]], set[str]] = ({}, set())):
    """The code's guards on one batch's reply, into out["links"] and out["dropped"]: the record is in the batch, the
    target is allowed, the rel is one of the record's kinds (`kinds_`) and may point at the target's theory kind
    (`kind_of`), a move is off a retired step, given the records' `texts` its passage is the record's own words, and the
    owner's own (`his`: each record's lines of his, and the notes) in a record that has lines of his, inside a note
    and for a kind that needs his words, a
    document's passage that restates one entry is that entry's evidence (`owner_of`; out["moved"]), it wasn't dropped on
    re-reading against the target as it stands (`refused`), and it isn't held already (`have`, (record, target, rel),
    grows with each one kept)."""
    lines, inside = his
    start = reply.find("{")
    reply_ = json.JSONDecoder().raw_decode(reply[start:])[0] if start >= 0 else {}  # the first object: text may follow it
    for ln in reply_.get("links", []):
        rec, to, rel = str(ln.get("record", "")), str(ln.get("to", "")), str(ln.get("rel", ""))
        why_ = " ".join(str(ln.get("passage" if texts is not None else "why", "")).split())
        moved = str(ln.get("moved_from") or "")
        drop = lambda why: out["dropped"].append({"record": rec, "why": why})
        if rec not in ids:
            drop("not a record of this batch")
            continue
        if to not in allowed:
            drop(f"target {to} {off}")
            continue
        if rel not in kinds_.rels:
            drop(f"unknown rel {rel}")
            continue
        if kinds_.rels[rel].to is not None and (kind_of or {}).get(to) not in kinds_.rels[rel].to:
            drop(f"{rel} doesn't point at a {(kind_of or {}).get(to)}")
            continue
        if texts is not None and (rec in inside or lines.get(rec) or kinds_.rels[rel].owner_words):
            if not (_norm(why_) and any(_norm(why_) in _norm(l) for l in lines.get(rec, []))):
                drop(f"the passage isn't {config.owner()}'s own words" + (f", which {kinds_.rels[rel].label} needs"
                     if kinds_.rels[rel].owner_words else ": only his lines are a moment"))
                continue
        elif texts is not None and not (_norm(why_) and _norm(why_) in _norm(texts[rec])):
            drop("passage not in the record")
            continue
        if moved and moved not in gone:
            drop(f"moved from {moved}, not a retired step")
            continue
        date = ids[rec]
        if owner_of and (entry := owner_of(rec, why_)):
            out.setdefault("moved", []).append({"record": rec, "entry": entry[0], "to": to})
            rec, date = entry
        if (rec, to, rel) in refused:
            drop("dropped on re-reading; its target hasn't changed since")
        elif (rec, to, rel) in have:
            drop("already linked")
        else:
            have.add((rec, to, rel))
            out["links"].append({"from": rec, "to": to, "rel": rel, "why": why_ if texts is not None else why_[:200],
                                 "moved_from": moved, "date": date})


DATED_ROW = re.compile(r"^\W*(\d{4}-\d{2}-\d{2})\s*[—–-]+\s*(.+)$")  # an index row: a date, a dash, a headline


def _entry_of(recs: list[tuple[str, str, str]], st: Store | None = None):
    """For a document's passage, the one entry it restates, as (id, date): the one entry whose own words it is (an
    index row, a table line), or, for a dated index row (a date, a dash, a headline), the entry its row links to, else
    the one entry titled with its headline (that day's, when several are). None for an entry's own link, a passage that
    isn't the document's own words (the re-check's reasons aren't checked), or when no one entry fits."""
    entries = [(i, d, _norm(t)) for i, d, t in recs if d]
    date_of = {i: d for i, d, _ in entries}
    docs = {i: _norm(t) for i, d, t in recs if not d}
    titles = [(e.id, str(e.date), _norm(str(e.fm.get("title", "")))) for e in (st.events() if st else [])
              if e.id in date_of and e.fm.get("title")]

    def owner_of(rec: str, passage: str):
        n = _norm(passage)
        if not n or rec not in docs or n not in docs[rec]:
            return None
        hits = [(i, d) for i, d, t in entries if n in t]
        if len(hits) == 1:
            return hits[0]
        if hits or not (m := DATED_ROW.match(passage.strip())) or not st:
            return None
        rows = [l for l in (st.root / rec).read_text(errors="replace").splitlines() if n in _norm(l)]
        linked = {i for l in rows for i in date_of if re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", l)}
        if len(linked) == 1:
            i = linked.pop()
            return i, date_of[i]
        named = [(i, d) for i, d, t in titles if t == _norm(m.group(2))]
        named = named if len(named) == 1 else [(i, d) for i, d in named if d == m.group(1)]
        return named[0] if len(named) == 1 else None
    return owner_of

def _file(st: Store, g: theory.Graph, reg, links: list[dict], message: str, source: str, author: str,
          kinds_: Kinds = EVIDENCE) -> None:
    """Files the links in the record's family, by=claude, in one transaction: Claude's placement, never the owner's
    claim."""
    day = datetime.now().astimezone().date().isoformat()
    dom = st.config.get("domain", {}).get("name", "")
    with st.transaction(message=message) as tx:
        for ln in links:
            note = ln["why"] + (f" (moved off the retired step {ln['moved_from']})" if ln["moved_from"] else "") + \
                   (" (evidence for the old version only)" if ln["to"].startswith("link/") else "")
            label = kinds_.rels[ln["rel"]].label if ln["rel"] in kinds_.rels else ln["rel"]
            fm = {"title": f"{label} {g.label(ln['to']) if ln['to'] in g.things else ln['to']}",
                  "date": ln["date"] or day, "domain": dom, "kind": "link", "about": [ln["to"]], "by": "claude",
                  "source": source, "author": author, "from": ln["from"], "to": ln["to"], "family": kinds_.family, "rel": ln["rel"]}
            tx.add(docreg.id_ends(reg, st, fm) if reg else fm, note)  # a document by its stable id, its path the hint


PLACED = ("engram-sweep", "engram-relink")  # the authors of the links engram places, by=claude: the only ones read again


def _about(repo: Path, g: theory.Graph, t: theory.Thing) -> str:
    """A target as the sweep's calls see it: its status, a loop's path, whose it is when it's the guide's suggestion,
    its text. Its hash is its version."""
    body = frontmatter.split((repo / t.file).read_text())[1].strip() if t.file and (repo / t.file).exists() else ""
    status, who = g.status.get(t.id, ("",))[0], theory.who(g, t.id)
    return f"<target id=\"{t.id}\"{f' status=\"{status}\"' if status else ''}>\n" + \
           (f"path: {g.draw(t.id)}\n" if t.kind == "loop" else "") + (f"{who}\n" if who else "") + f"{body}\n</target>"


def _version(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _targets(g: theory.Graph, reg, kinds_: Kinds = EVIDENCE):
    """The things the record's links point at (the loops and Discoveries, unless it names its own kinds), and a link
    end's target among them: its id, its file, a section or its doc id."""
    tg = {t.id: t for t in g.things.values() if t.kind in kinds_.targets}
    by_file = {t.file: t.id for t in tg.values()}

    def thing_of(x) -> str | None:
        if str(x) in tg:
            return str(x)
        w = reg.resolve(str(x)) if reg else None
        return by_file.get(w.path if w else str(x).split("#", 1)[0])
    return tg, thing_of


def _dropped(st: Store) -> Path:
    """Links dropped on re-reading, each with the version of its target it was dropped against."""
    return data_path("sweep") / f"{st.config.get('domain', {}).get('name', 'domain')}.dropped.json"


def _refused(st: Store, repo: Path, g: theory.Graph, reg, kinds_: Kinds = EVIDENCE) -> set:
    """(record, target, rel) of each link dropped on re-reading whose target hasn't changed since."""
    path = _dropped(st)
    if not path.exists():
        return set()
    tg, _ = _targets(g, reg, kinds_)
    now = {t: _version(_about(repo, g, tg[t])) for t in tg}
    return {(x["from"], x["to"], x["rel"]) for x in json.loads(path.read_text()) if now.get(x["to"]) == x["version"]}


def recheck(repo: Path, targets: list[str], confirm=None, cap: float = 10.0, dry_run: bool = False,
            why: str = "") -> dict:
    """Reads again each link engram placed (`PLACED`, by=claude) on these loops and Discoveries, never the owner's, with
    the confirming call (`sweep_confirm`) against the target as it stands now. A no drops it through `engram fix`, in
    one commit whose `Refinement:` line is the weekly page's, and remembers it against that version of its target, so
    neither the sweep nor the re-check files it again until the target changes. Never starts a call past `cap`."""
    from engram import fix
    p = pack.for_repo(repo)
    out = {"read": 0, "kept": 0, "dropped": 0, "usd": 0.0, "stopped": False}
    if not p.prompts.get("sweep_confirm"):
        return out
    st, g, reg, k = Store(repo), theory.load(repo), docreg.load(repo), kinds(repo)
    rec_of = _rec_of(reg)
    tg, thing_of = _targets(g, reg, k)
    links = [(e, t) for e in st.events(kind="link") if e.fm.get("family") == k.family and e.fm.get("by") == "claude"
             and e.fm.get("author") in PLACED and e.fm.get("rel") in k.rels and (t := thing_of(e.fm.get("to"))) in targets]
    if not links:
        return out
    confirm = confirm or _asker(p.prompts.get("relink_system", ""))
    text_of = {i: (d, t) for i, d, t in records(repo, p.relink_skip, k)}
    about = {t: _about(repo, g, tg[t]) for t in {t for _, t in links}}
    drop, biggest = [], 0.0
    for e, t in links:
        rec = rec_of(e.fm.get("from"))
        if rec not in text_of:
            continue
        if out["usd"] + biggest > cap:
            out["stopped"] = True
            break
        d, text = text_of[rec]
        reply, usd = confirm(config.voice(p.prompts["sweep_confirm"]).format(
            record=f"[{rec}] date {d or 'undated'}\n{text}", passage=" ".join(e.body.split()), target=about[t],
            rel=k.rels[e.fm["rel"]].shown()))
        out["usd"] += usd
        biggest = max(biggest, usd)
        out["read"] += 1
        if re.match(r"\W*yes\b", reply, re.I):
            out["kept"] += 1
        else:
            drop.append((e, rec, t))
    out["dropped"] = len(drop)
    if drop and not dry_run:
        names = ", ".join(sorted({g.label(t) for _, _, t in drop}))
        fix.apply(st, [], f"engram's placement on {names} didn't hold on re-reading" + (f" after {why}" if why else ""),
                  [e.id for e, _, _ in drop], line=f"{len(drop)} {'link' if len(drop) == 1 else 'links'} engram placed on {names} "
                  "no longer held on re-reading and dropped")
        path = _dropped(st)
        old = json.loads(path.read_text()) if path.exists() else []
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(old + [{"from": rec, "to": t, "rel": e.fm["rel"], "version": _version(about[t])}
                                          for e, rec, t in drop], ensure_ascii=False))
    return out


SWEPT, SWEEP_CAP = "engram-sweep", 10.0  # the sweep's author, and what one run may spend
SWEEP_BUDGET, SWEEP_EFFORT = 30_000, "medium"  # the read's batches and effort: denser or lower missed most of what bears


def _progress(st: Store, dry_run: bool) -> Path:
    """The sweep's progress for a record: each record read, at which text, and the links still to confirm or file. A
    dry run keeps its own, so dry runs chain without touching a real one's."""
    return data_path("sweep") / f"{st.config.get('domain', {}).get('name', 'domain')}{'.dry' if dry_run else ''}.json"


def sweep(repo: Path, ask=None, confirm=None, dry_run: bool = False, limit: int | None = None, cap: float = SWEEP_CAP,
          replay: dict | None = None, items: list[str] | None = None) -> dict:
    """The linking job: every entry but journals and every document the re-check reads, against the theory things the
    record's link kinds point at (`kinds`: loops and Discoveries, strengthens or weakens, unless it names its own), with
    the pack's `sweep` words and the kinds listed (`{rels}`). The re-check's guards hold, with a pair already linked
    counting as held (by any rel where for and against exclude each other, else by that rel), and the read must cite
    the record's own words that bear on it (its `passage`, checked word for word; his own, inside a note or for a kind
    that needs them). Each surviving link then goes to a second call (`sweep_confirm`), which sees only the record, that
    passage, the target and the kind with what it means, never the read's reasoning; only a yes is filed, by=claude.

    A run never starts a call that could take it past `cap`, and picks up where the last one stopped: it confirms the
    links still waiting first, then reads only records not read at their present text, against every target, and the
    records read already against a target added since, against it alone (`adding`, merged once read). Returns this run's counts and links, and what's left; a dry run files nothing. `items` (a look-back's
    request) reads every record against those things alone, apart from the progress.

    `replay` lands an approved set with no model calls: its "proposals" (record, to, rel, passage) answer each read for
    the records in that batch, and a link is confirmed only when its (passage, target, rel) is in its "approved"; every
    guard runs against the record as it stands. One record's runs take turns (`lock`): the hourly job's, a look-back's
    and the weekly pass's would otherwise read the same links as unfiled and file them twice."""
    with lock(repo):
        return _sweep(repo, ask, confirm, dry_run, limit, cap, replay, items)


@contextlib.contextmanager
def lock(repo: Path):
    """The linking job's turn on a record: a run waits for one already running on it."""
    path = data_path("sweep") / f"{Store(repo).config.get('domain', {}).get('name', 'domain')}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _sweep(repo: Path, ask, confirm, dry_run: bool, limit: int | None, cap: float, replay: dict | None,
           items: list[str] | None) -> dict:
    p = pack.for_repo(repo)
    if not (p.prompts.get("sweep") and p.prompts.get("sweep_confirm")):
        raise SystemExit(f"engram: {repo}'s pack has no `sweep` and `sweep_confirm` words; its evidence isn't swept")
    confirm = confirm or _asker(p.prompts.get("relink_system", ""))
    ask = ask or _asker(p.prompts.get("relink_system", ""), SWEEP_EFFORT)
    st, g, reg, k = Store(repo), theory.load(repo), docreg.load(repo), kinds(repo)
    tg, _ = _targets(g, reg, k)
    if items and (off := [t for t in items if t not in tg]):
        raise SystemExit(f"engram: {', '.join(off)} isn't a theory thing the record's links point at")
    path = None if items else _progress(st, dry_run)
    state = json.loads(path.read_text()) if path and path.exists() else {}
    versions = {t: _version(_about(repo, g, tg[t])) for t in tg}
    seen = state.get("versions", {})
    changed = [t for t, v in seen.items() if t in versions and versions[t] != v]
    recheck_out = recheck(repo, changed, confirm, cap, dry_run, why="its text changed") if changed else None
    if recheck_out and recheck_out["dropped"] and not dry_run:
        st, g, reg = Store(repo), theory.load(repo), docreg.load(repo)
    rec_of = _rec_of(reg)
    tg, thing_of = _targets(g, reg, k)
    if items:
        tg = {t: tg[t] for t in items}
    about = lambda t: _about(repo, g, t)
    held_as = lambda rel: k.rels if k.one_way else (rel,)
    have = {(rec_of(e.fm.get("from")), t, rel) for e in st.events(kind="link")
            if e.fm.get("family") == k.family and (t := thing_of(e.fm.get("to"))) for rel in held_as(e.fm.get("rel"))}
    refused = _refused(st, repo, g, reg, k)
    journal = {e.id for e in st.events(kind="journal")}
    recs = [r for r in records(repo, p.relink_skip, k) if r[0] not in journal]
    text_of = {i: (d, t) for i, d, t in recs}
    owner_of = _entry_of(recs, st)
    his = his_lines(repo, k)
    approved = {(_norm(a), b, c) for a, b, c in (replay or {}).get("approved", [])}
    sig = lambda t: hashlib.sha1(t.encode()).hexdigest()[:16]
    if "targets" not in state:  # nothing read yet: every record against every target
        state = {"targets": sorted(tg), "read": {}, "pending": state.get("pending", []), "confirmed": state.get("confirmed", [])}
    state["targets"] = sorted(set(state["targets"]) & set(tg))  # one that goes needs nothing read again
    added = sorted(set(tg) - set(state["targets"]))  # one that's added: the records read already, against it alone
    if (state.get("adding") or {}).get("targets") != added:
        state["adding"] = {"targets": added, "read": {}}
    adding = state["adding"]
    have |= {(x["from"], x["to"], rel) for x in state["pending"] + state["confirmed"] for rel in held_as(x["rel"])}
    unread = [r for r in recs if state["read"].get(r[0]) != sig(r[2])]
    unread_added = [r for r in recs if added and state["read"].get(r[0]) == sig(r[2]) and adding["read"].get(r[0]) != sig(r[2])]
    work = ([(b, list(tg)) for b in batches(unread, SWEEP_BUDGET)] +
            [(b, [t for t in tg if t in added]) for b in batches(unread_added, SWEEP_BUDGET)])[:limit]
    # the record's own kinds are shown with the theory they belong to; links are made only to what the kinds point at
    own = [] if items else [t for t in g.things.values() if t.kind in g.kinds and t.id not in tg]
    targets_text = {tuple(a): "\n".join(about(t) for t in [*(tg[x] for x in a), *(own if len(a) == len(tg) else [])])
                    for a in {tuple(a) for _, a in work}}
    out = {"records": len(recs), "unread": len(unread) + len(unread_added), "targets": len(tg), "batches": 0, "proposed": 0, "links": [],
           "dropped": [], "moved": [], "confirmed": [], "rejected": [], "usd": 0.0, "read_usd": 0.0, "stopped": False}
    if recheck_out:
        out["recheck"], out["usd"], out["stopped"] = recheck_out, recheck_out["usd"], recheck_out["stopped"]
    state["versions"] = {**versions, **({t: seen[t] for t in changed} if out["stopped"] else {})}  # unfinished: next run
    biggest = 0.0  # the dearest call so far: no call starts unless the run could pay that much more

    def call(fn, prompt):
        nonlocal biggest
        reply, usd = fn(prompt)
        out["usd"] += usd
        biggest = max(biggest, usd)
        return reply, usd

    def save():
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, ensure_ascii=False))
    while (state["pending"] or work) and not out["stopped"]:
        if out["usd"] + biggest > cap:
            out["stopped"] = True
            break
        if state["pending"]:
            ln = state["pending"][0]
            if ln["from"] not in text_of or ln["to"] not in tg or ln["rel"] not in k.rels:  # the record, target or kind is gone
                state["pending"].pop(0)
                save()
                continue
            d, t = text_of[ln["from"]]
            prompt = config.voice(p.prompts["sweep_confirm"]).format(
                record=f"[{ln['from']}] date {d or 'undated'}\n{t}", passage=ln["why"], target=about(tg[ln["to"]]),
                rel=k.rels[ln["rel"]].shown())
            yes = (_norm(ln["why"]), ln["to"], ln["rel"]) in approved if replay else \
                bool(re.match(r"\W*yes\b", call(confirm, prompt)[0], re.I))
            state["pending"].pop(0)
            (state["confirmed"] if yes else out["rejected"]).append(ln)
            if yes:
                out["confirmed"].append(ln)
        else:
            b, against = work.pop(0)
            text = "\n".join(f"[{i}] date {d or 'undated'}\n{t}\n" for i, d, t in b)
            ids = {i for i, _, _ in b}
            reply, usd = (json.dumps({"links": [x for x in replay["proposals"] if x["record"] in ids]}), 0.0) if replay else \
                call(ask, config.voice(p.prompts["sweep"]).format(targets=targets_text[tuple(against)], records=text, rels=k.text()))
            out["read_usd"] += usd
            out["batches"] += 1
            got = {"links": [], "dropped": out["dropped"], "moved": out["moved"]}
            _check(reply, {i: d for i, d, _ in b}, set(against), have, got, off="isn't a theory thing these links point at"
                   if k is not EVIDENCE else "isn't a loop or Discovery", texts={i: t for i, _, t in b}, refused=refused,
                   owner_of=owner_of, kinds_=k, kind_of={t: tg[t].kind for t in against}, his=his)
            out["links"] += got["links"]
            state["pending"] += got["links"]
            if added:
                adding["read"].update({i: sig(t) for i, _, t in b})
            if len(against) == len(tg):
                state["read"].update({i: sig(t) for i, _, t in b})
        save()
    if added and all(adding["read"].get(i) == sig(t) for i, _, t in recs if state["read"].get(i) == sig(t)):
        state["targets"], state["adding"] = sorted(tg), {"targets": [], "read": {}}  # read against it: one of the rest
    out["proposed"] = len(out["links"]) + len(out["dropped"])
    out["left"] = {"unread": sum(len(b) for b in work), "pending": len(state["pending"])}
    if state["confirmed"] and not dry_run:
        _file(st, g, reg, state["confirmed"], commitmsg.message(k.template, n=len(state["confirmed"]),
              records="record" if len(state["confirmed"]) == 1 else "records"), "evidence sweep", SWEPT, k)
    state["confirmed"] = []
    save()
    return out


HOURLY_WAIT = timedelta(days=1)  # after a run that stopped at its cap, the hourly linking job waits this long


def _stopped_at(st: Store) -> Path:
    return data_path("sweep") / f"{st.config.get('domain', {}).get('name', 'domain')}.stopped"


def hourly(repo: Path, ask=None, now: datetime | None = None) -> dict | None:
    """The linking job in the hourly run, for a record whose link kinds say `hourly` (whether or not its weekly pass is
    paused): `sweep` with its own progress as its mark, so a run with nothing new or waiting makes no call. A run that
    stops at its cap waits a day before the next, so a backlog costs at most one cap a day. None when it doesn't run."""
    if not kinds(repo).hourly:
        return None
    now = now or datetime.now().astimezone()
    mark = _stopped_at(Store(repo))
    if mark.exists() and now - datetime.fromisoformat(mark.read_text().strip()) < HOURLY_WAIT:
        return None
    res = sweep(repo, ask=ask, confirm=ask)
    if res["stopped"]:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(now.isoformat(timespec="seconds"))
    elif mark.exists():
        mark.unlink()
    return res


def pending(older_than_minutes: int = 10) -> list[str]:
    """Changes still queued (the background start didn't run) or left running for over three hours by a crash, for the
    hourly job to run. One that errored waits for `engram theory relink --change <id>`: a retry spends money."""
    with theorychange.db() as c:
        rows = c.execute("SELECT id, at, state FROM change WHERE state IN ('queued', 'running')").fetchall()
    now = datetime.now().astimezone()
    age = {i: (now - datetime.fromisoformat(at)).total_seconds() for i, at, _ in rows}
    return [i for i, _, state in rows if age[i] > (3 * 3600 if state == "running" else older_than_minutes * 60)]
