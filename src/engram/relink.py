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
import json
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from engram import commitmsg, config, docreg, claude_env, frontmatter, pack, recsum, theory, theorychange
from engram.store import Store
from engram.now import RENEWAL

BUDGET = 90_000  # characters of records per call; a record is never cut, and one bigger than this goes alone
SKIP_FILES = ("AGENTS.md", "CLAUDE.md", "README.md")
RELS = ("strengthens", "weakens")

def _asker(system: str, effort: str = "low"):
    """The re-check's model call, with the pack's `relink_system` words."""
    return lambda prompt: _ask(prompt, system, effort)


def _ask(prompt: str, system: str, effort: str = "low") -> tuple[str, float]:
    cmd = ["claude", "-p", "--model", recsum.MODEL, "--effort", effort, "--output-format", "json", "--setting-sources",
           "project", "--strict-mcp-config", "--no-session-persistence", "--tools", "", "--system-prompt", system]
    with tempfile.TemporaryDirectory(prefix="engram-relink-") as cwd:
        r = subprocess.run(cmd, input=prompt, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=1800)
    out = json.loads(r.stdout)
    if r.returncode or out.get("is_error"):
        raise RuntimeError(str(out.get("result") or f"exit {r.returncode}")[:300])
    return out.get("result") or "", out.get("total_cost_usd", 0) or 0


def records(repo: Path, skip: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """(id, date, text) for every entry and document of the record, each whole: entries by their id, documents by their
    path. The pack's `relink_skip` (theory things, whose links are joins, not evidence; journals; the assistant's own
    files), dot paths and the agents' instructions are left out."""
    st = Store(repo)
    skip_re = re.compile("|".join(f"(?:{x})" for x in (re.escape(st.events_dir + "/"), r"\.", *skip)))
    out = []
    for e in st.events():
        if e.kind in ("link", "status", "capture", RENEWAL):  # a renewal says only "still on it": no evidence
            continue
        body = " ".join(e.body.split())
        out.append((e.id, str(e.date), f"{e.fm.get('title') or e.fm.get('heading', '')}: {body}"))
    for p in sorted([*repo.rglob("*.md"), *repo.rglob("*.txt")]):
        rel = p.relative_to(repo).as_posix()
        if skip_re.match(rel) or rel in SKIP_FILES or "/." in rel or p.name.startswith("_"):
            continue
        out.append((rel, "", " ".join(p.read_text(errors="replace").split())))  # whole: a cut hid what a long one says
    return out


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


def run(change: str, ask=None, dry_run: bool = False, limit: int | None = None, force: bool = False) -> dict:
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
        return _run(change, repo, s, ask, dry_run, limit)
    except Exception as e:
        if not dry_run:
            with theorychange.db() as c:
                c.execute("UPDATE change SET state = 'error', error = ? WHERE id = ?", (f"{type(e).__name__}: {e}"[:300], change))
        raise


def _run(change: str, repo: Path, s: dict, ask, dry_run: bool, limit: int | None) -> dict:
    st = Store(repo)
    g = theory.load(repo)
    tgts, gone = targets(s, g)
    allowed = set(tgts) | set(gone)
    reg = docreg.load(repo)
    rec_of = _rec_of(reg)
    have = {(rec_of(e.fm.get("from")), e.fm.get("to"), e.fm.get("rel")) for e in st.events(kind="link") if e.fm.get("family") == "evidence"}
    held: dict[str, list[str]] = {}  # record -> the targets its evidence points at now, among what changed
    retired_loops = {x["loop"] for x in s.get("retired", []) if x.get("loop")}
    for e in st.events(kind="link"):
        if e.fm.get("family") == "evidence" and (e.fm.get("to") in allowed or e.fm.get("to") in retired_loops):
            held.setdefault(rec_of(e.fm.get("from")), []).append(str(e.fm.get("to")))
    p = pack.for_repo(repo)
    recs = records(repo, p.relink_skip)
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
        _check(reply, {i: d for i, d, _ in b}, allowed, have, out, gone)
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
          "engram-relink")
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
           texts: dict[str, str] | None = None):
    """The code's guards on one batch's reply, into out["links"] and out["dropped"]: the record is in the batch, the
    target is allowed, the rel is strengthens or weakens, a move is off a retired step, the link isn't held already
    (`have`, (record, target, rel), grows with each one kept), and, given the records' `texts`, its passage is the
    record's own words."""
    start = reply.find("{")
    reply_ = json.JSONDecoder().raw_decode(reply[start:])[0] if start >= 0 else {}  # the first object: text may follow it
    for ln in reply_.get("links", []):
        rec, to, rel = str(ln.get("record", "")), str(ln.get("to", "")), str(ln.get("rel", ""))
        why_ = " ".join(str(ln.get("passage" if texts is not None else "why", "")).split())
        moved = str(ln.get("moved_from") or "")
        if rec not in ids:
            out["dropped"].append({"record": rec, "why": "not a record of this batch"})
        elif to not in allowed:
            out["dropped"].append({"record": rec, "why": f"target {to} {off}"})
        elif rel not in RELS:
            out["dropped"].append({"record": rec, "why": f"unknown rel {rel}"})
        elif texts is not None and not (_norm(why_) and _norm(why_) in _norm(texts[rec])):
            out["dropped"].append({"record": rec, "why": "passage not in the record"})
        elif moved and moved not in gone:
            out["dropped"].append({"record": rec, "why": f"moved from {moved}, not a retired step"})
        elif (rec, to, rel) in have:
            out["dropped"].append({"record": rec, "why": "already linked"})
        else:
            have.add((rec, to, rel))
            out["links"].append({"from": rec, "to": to, "rel": rel, "why": why_ if texts is not None else why_[:200],
                                 "moved_from": moved, "date": ids[rec]})


def _file(st: Store, g: theory.Graph, reg, links: list[dict], message: str, source: str, author: str) -> None:
    """Files the links as evidence, by=claude, in one transaction: Claude's placement, never the owner's claim."""
    day = datetime.now().astimezone().date().isoformat()
    dom = st.config.get("domain", {}).get("name", "")
    with st.transaction(message=message) as tx:
        for ln in links:
            note = ln["why"] + (f" (moved off the retired step {ln['moved_from']})" if ln["moved_from"] else "") + \
                   (" (evidence for the old version only)" if ln["to"].startswith("link/") else "")
            fm = {"title": f"{ln['rel']} {g.label(ln['to']) if ln['to'] in g.things else ln['to']}",
                  "date": ln["date"] or day, "domain": dom, "kind": "link", "about": [ln["to"]], "by": "claude",
                  "source": source, "author": author, "from": ln["from"], "to": ln["to"], "family": "evidence", "rel": ln["rel"]}
            tx.add(docreg.id_ends(reg, st, fm) if reg else fm, note)  # a document by its stable id, its path the hint


SWEPT, SWEEP_CAP = "engram-sweep", 10.0  # the sweep's author, and what one run may spend
SWEEP_BUDGET, SWEEP_EFFORT = 30_000, "medium"  # the read's batches and effort: denser or lower missed most of what bears


def sweep(repo: Path, ask=None, confirm=None, dry_run: bool = False, limit: int | None = None, cap: float = SWEEP_CAP) -> dict:
    """The evidence sweep: every entry but journals and every document the re-check reads, in its batches, against the
    theory's loops and Discoveries, with the pack's `sweep` words. The re-check's guards hold, with a pair already
    linked by any evidence rel counting as held, and the read must cite the record's own words that bear on it (its
    `passage`, checked word for word); then each surviving link goes to a second call (`sweep_confirm`), which sees
    only the record, that passage, the target and the rel, never the read's reasoning, and only a yes is filed,
    by=claude. It stops calling once a run
    has spent `cap`. Returns counts and the links, for a dry run too, which files nothing."""
    p = pack.for_repo(repo)
    if not (p.prompts.get("sweep") and p.prompts.get("sweep_confirm")):
        raise SystemExit(f"engram: {repo}'s pack has no `sweep` and `sweep_confirm` words; its evidence isn't swept")
    confirm = confirm or _asker(p.prompts.get("relink_system", ""))
    ask = ask or _asker(p.prompts.get("relink_system", ""), SWEEP_EFFORT)
    st, g, reg = Store(repo), theory.load(repo), docreg.load(repo)
    rec_of = _rec_of(reg)
    tg = {t.id: t for t in g.things.values() if t.kind in ("loop", "discovery")}
    by_file = {t.file: t.id for t in tg.values()}

    def thing_of(x) -> str | None:  # a link's target as a loop or Discovery: its id, its file, a section or its doc id
        if str(x) in tg:
            return str(x)
        w = reg.resolve(str(x)) if reg else None
        return by_file.get(w.path if w else str(x).split("#", 1)[0])
    have = {(rec_of(e.fm.get("from")), t, rel) for e in st.events(kind="link")
            if e.fm.get("family") == "evidence" and (t := thing_of(e.fm.get("to"))) for rel in RELS}

    def about(t) -> str:
        body = frontmatter.split((repo / t.file).read_text())[1].strip() if t.file and (repo / t.file).exists() else ""
        status = g.status.get(t.id, ("",))[0]
        return f"<target id=\"{t.id}\"{f' status=\"{status}\"' if status else ''}>\n" + \
               (f"path: {g.draw(t.id)}\n" if t.kind == "loop" else "") + f"{body}\n</target>"
    journal = {e.id for e in st.events(kind="journal")}
    recs = [r for r in records(repo, p.relink_skip) if r[0] not in journal]
    text_of = {i: (d, t) for i, d, t in recs}
    targets_text = "\n".join(about(t) for t in tg.values())
    out = {"records": len(recs), "targets": len(tg), "batches": 0, "proposed": 0, "links": [], "dropped": [], "confirmed": [],
           "rejected": [], "usd": 0.0, "read_usd": 0.0, "stopped": False}
    for b in batches(recs, SWEEP_BUDGET)[:limit]:
        if out["usd"] >= cap:
            out["stopped"] = True
            break
        text = "\n".join(f"[{i}] date {d or 'undated'}\n{t}\n" for i, d, t in b)
        reply, usd = ask(config.voice(p.prompts["sweep"]).format(targets=targets_text, records=text))
        out["usd"] += usd
        out["batches"] += 1
        _check(reply, {i: d for i, d, _ in b}, set(tg), have, out, off="isn't a loop or Discovery", texts={i: t for i, _, t in b})
    out["read_usd"] = out["usd"]
    out["proposed"] = len(out["links"]) + len(out["dropped"])
    for ln in out["links"]:
        if out["usd"] >= cap:
            out["stopped"] = True
            break
        d, t = text_of[ln["from"]]
        reply, usd = confirm(config.voice(p.prompts["sweep_confirm"]).format(
            record=f"[{ln['from']}] date {d or 'undated'}\n{t}", passage=ln["why"], target=about(tg[ln["to"]]), rel=ln["rel"]))
        out["usd"] += usd
        (out["confirmed"] if re.match(r"\W*yes\b", reply, re.I) else out["rejected"]).append(ln)
    if out["confirmed"] and not dry_run:
        _file(st, g, reg, out["confirmed"], commitmsg.message("sweep", n=len(out["confirmed"])), "evidence sweep", SWEPT)
    return out


def pending(older_than_minutes: int = 10) -> list[str]:
    """Changes still queued (the background start didn't run) or left running for over three hours by a crash, for the
    hourly job to run. One that errored waits for `engram theory relink --change <id>`: a retry spends money."""
    with theorychange.db() as c:
        rows = c.execute("SELECT id, at, state FROM change WHERE state IN ('queued', 'running')").fetchall()
    now = datetime.now().astimezone()
    age = {i: (now - datetime.fromisoformat(at)).total_seconds() for i, at, _ in rows}
    return [i for i, _, state in rows if age[i] > (3 * 3600 if state == "running" else older_than_minutes * 60)]
