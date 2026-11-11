"""Revising the theory graph (.engram/README.md, "Filing from conversation"): `engram theory change`, used by the advisor
in conversation the moment the owner agrees to a change in the model, and by the hourly job as a backstop.

A change is a list of operations:
- add-node: a condition, or a state a loop passes through: a new thread file under theory/; or a thing of one of the
  record's own kinds, in its kind's folder
- add-loop: a new loop, its path given whole
- insert-step / remove-step: a member added to or taken out of a loop; the step it breaks is retired and the new steps
  take its place
- add-join / retire-join: a join between two things, with its kind, strength and one-line mechanism
- status: a theory's status (proposed, provisional, confirmed, ruled out, replaced)

Nothing is edited: new things are new files, new steps and joins are new links, and a retired step or join gets a
status event on `link/<id>` naming what replaced it and why (theory.load leaves it out; `load(asof=...)` still shows
it). The whole change is checked on the graph it would make before anything is written: every id exists or is made in
the same change, kinds and strengths are the record's, every retirement says what replaced it and why, and a loop that
closed still closes (an open chain stays one path). A structural change (anything but status alone) queues the
re-check of the whole record's evidence (engram.relink)."""
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from engram import commitmsg, config, frontmatter, theory
from engram.paths import data_path
from engram.store import Store

KINDS = ("node", "state", "loop")  # the built-in kinds; a record's own (`[theory.kinds]`) sit beside them
SCHEMA = """
CREATE TABLE IF NOT EXISTS change (
  id TEXT PRIMARY KEY, domain TEXT, repo TEXT, at TEXT, summary TEXT, state TEXT, result TEXT, usd REAL DEFAULT 0,
  shown INTEGER DEFAULT 0, error TEXT
);
"""


class ChangeError(ValueError):
    pass


@dataclass
class Result:
    change: str
    ops: list[dict]
    written: list[str] = field(default_factory=list)
    structural: bool = False
    drawn: dict[str, str] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def db() -> sqlite3.Connection:
    c = sqlite3.connect(data_path("theory.sqlite"), timeout=30)
    c.executescript(SCHEMA)
    return c


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _config(st: Store) -> tuple[list[str], list[str]]:
    conf = st.config.get("links", {}).get("theory", {})
    return list(conf.get("rels") or []), list(conf.get("weights") or theory.STRENGTHS)


def plan(g: theory.Graph, ops: list[dict], rels: list[str], strengths: list[str], why: str = "") -> tuple[theory.Graph, list[tuple], dict]:
    """The graph the change would make, the writes it needs, and what it touched; raises ChangeError on the first
    problem. Writes are ("thing", Thing, description), ("edge", Edge), ("retire", Edge, replaced_by) and
    ("status", id, status)."""
    h = copy.deepcopy(g)
    closed = {l for l in h.loops() if h.closes(l)}
    writes: list[tuple] = []
    touched = {"new": [], "loops": [], "retired": [], "joins": [], "status": []}
    n = 0

    def need(x: str):
        if x not in h.things:
            raise ChangeError(f"unknown theory id {x}")

    def edge(a: str, b: str, rel: str, note: str, strength: str = "", loop: str = "", step: int = 0) -> theory.Edge:
        nonlocal n
        n += 1
        e = theory.Edge(f"new-{n}", a, b, rel, note, strength, loop=loop, step=step)
        h.edges.append(e)
        writes.append(("edge", e))
        return e

    def retire(e: theory.Edge, replaced_by: str):
        if not replaced_by.strip():
            raise ChangeError(f"retiring {e.a} → {e.b} needs what replaced it (--replaced-by)")
        if not why.strip():
            raise ChangeError(f"retiring {e.a} → {e.b} needs why (--why)")
        h.edges.remove(e)
        writes.append(("retire", e, replaced_by))
        touched["retired"].append(e)

    def step_of(loop: str, a: str | None = None, b: str | None = None) -> theory.Edge:
        hit = [e for e in h.edges if e.loop == loop and (a is None or e.a == a) and (b is None or e.b == b)]
        if len(hit) != 1:
            raise ChangeError(f"{loop} has {len(hit)} steps {'from ' + a if a else ''}{' to ' + b if b else ''}; expected one")
        return hit[0]

    for op in ops:
        kind = op.get("op")
        if kind == "add-node":
            tid, k = str(op.get("id", "")), str(op.get("kind") or "node")
            if (k not in KINDS and k not in h.kinds) or not tid.startswith(k + "/") or len(tid) <= len(k) + 1:
                raise ChangeError(f"a new {k} needs an id like {k}/<name>, got {tid!r}")
            if tid in h.things:
                raise ChangeError(f"{tid} already exists")
            if not str(op.get("title", "")).strip():
                raise ChangeError(f"{tid} needs a title")
            t = theory.Thing(tid, k, str(op.get("short") or op["title"]), theory.file_for(h, k, tid),
                             str(op["title"]), [str(s) for s in op.get("stories") or []], [str(s) for s in op.get("say") or []])
            h.things[tid] = t
            writes.append(("thing", t, str(op.get("about") or "")))
            touched["new"].append(tid)
        elif kind == "add-loop":
            lid, path = str(op.get("id", "")), [str(x) for x in op.get("path") or []]
            if not lid.startswith("loop/") or lid in h.things:
                raise ChangeError(f"a new loop needs an unused id like loop/<n>, got {lid!r}")
            if len(path) < 3:
                raise ChangeError(f"{lid} needs a path of at least two steps")
            for x in path:
                need(x)
            h.things[lid] = theory.Thing(lid, "loop", str(op.get("short") or lid.replace("loop/", "Loop ")),
                                         theory.file_for(h, "loop", lid), str(op.get("title") or lid),
                                         [], [str(s) for s in op.get("say") or []])
            writes.append(("thing", h.things[lid], str(op.get("about") or "")))
            notes = list(op.get("mechanisms") or [])
            for i, (a, b) in enumerate(zip(path, path[1:]), 1):
                edge(a, b, "feeds", notes[i - 1] if i <= len(notes) else f"step {i} of {lid}", loop=lid, step=i)
            if path[0] == path[-1]:
                closed.add(lid)
            touched["new"].append(lid)
            touched["loops"].append(lid)
        elif kind == "insert-step":
            loop, after, x = str(op.get("loop", "")), str(op.get("after", "")), str(op.get("node", ""))
            for y in (loop, after, x):
                need(y)
            old = step_of(loop, a=after)
            notes = list(op.get("mechanisms") or [])
            e1 = edge(old.a, x, "feeds", notes[0] if notes else f"step of {loop}", loop=loop, step=old.step)
            e2 = edge(x, old.b, "feeds", notes[1] if len(notes) > 1 else f"step of {loop}", loop=loop, step=old.step)
            retire(old, f"{h.label(e1.a)} → {h.label(x)} → {h.label(e2.b)}")
            touched["loops"].append(loop)
        elif kind == "remove-step":
            loop, x = str(op.get("loop", "")), str(op.get("node", ""))
            for y in (loop, x):
                need(y)
            into, out = step_of(loop, b=x), step_of(loop, a=x)
            e = edge(into.a, out.b, "feeds", str(op.get("mechanism") or f"step of {loop}"), loop=loop, step=into.step)
            retire(into, f"{h.label(e.a)} → {h.label(e.b)}")
            retire(out, f"{h.label(e.a)} → {h.label(e.b)}")
            touched["loops"].append(loop)
        elif kind == "add-join":
            a, b, rel = str(op.get("from", "")), str(op.get("to", "")), str(op.get("rel", ""))
            need(a)
            need(b)
            if rel not in rels or rel == "feeds":
                raise ChangeError(f"unknown join kind {rel!r} (one of: {', '.join(r for r in rels if r != 'feeds')})")
            if str(op.get("strength", "")) not in strengths:
                raise ChangeError(f"unknown strength {op.get('strength')!r} (one of: {', '.join(strengths)})")
            mech = " ".join(str(op.get("mechanism", "")).split())
            if not mech or len(mech.split()) > 40:
                raise ChangeError("a join needs a one-line mechanism (at most 40 words)")
            if any(e.a == a and e.b == b and e.rel == rel for e in h.edges):
                raise ChangeError(f"{a} {rel} {b} is already in the graph")
            touched["joins"].append(edge(a, b, rel, mech, str(op["strength"])))
        elif kind == "retire-join":
            a, b, rel = str(op.get("from", "")), str(op.get("to", "")), str(op.get("rel", ""))
            hit = [e for e in h.edges if e.a == a and e.b == b and e.rel == rel and not e.loop]
            if len(hit) != 1:
                raise ChangeError(f"no join {a} {rel} {b} to retire")
            retire(hit[0], str(op.get("replaced_by", "")))
        elif kind == "status":
            tid, to = str(op.get("id", "")), str(op.get("to", ""))
            need(tid)
            if to not in theory.STATUSES:
                raise ChangeError(f"unknown status {to!r} (one of: {', '.join(theory.STATUSES)})")
            if h.status.get(tid, ("",))[0] == to:
                raise ChangeError(f"{tid} is already {to}")
            h.status[tid] = (to, _today(), "")
            writes.append(("status", tid, to))
            touched["status"].append(tid)
        else:
            raise ChangeError(f"unknown operation {kind!r}")
    for l in h.loops():
        if l in touched["loops"] and sum(1 for e in h.edges if e.loop == l) < 2:
            raise ChangeError(f"{l} would no longer close: it needs at least two steps, and would have {h.draw(l) or 'none'}")
        if l in closed and not h.closes(l):
            raise ChangeError(f"{l} would no longer close: {h.draw(l)}")
        if any(e.loop == l for e in h.edges) and not h.walks(l):
            raise ChangeError(f"{l} would no longer be one path: {h.draw(l)}")
    if not writes:
        raise ChangeError("nothing to change")
    return h, writes, touched


def apply(repo: Path, ops: list[dict], by: str = "with-claude", why: str = "", said: str = "", date: str | None = None,
          source: str = "", dry_run: bool = False, relink: bool = True) -> Result:
    """Checks the whole change, then writes it in one transaction; prints nothing. A structural change is queued for
    the evidence re-check, which starts in the background unless `relink` is off (the hourly job runs it otherwise)."""
    st = Store(repo)
    g = theory.load(repo)
    rels, strengths = _config(st)
    h, writes, touched = plan(g, ops, rels, strengths, why)
    day = date or _today()
    structural = any(w[0] != "status" for w in writes)
    res = Result(change="", ops=ops, structural=structural)
    loops = list(dict.fromkeys(touched["loops"] + [l for l in h.loops() if any(x in h.path(l) for x in touched["new"])]))
    res.drawn = {l: h.draw(l) for l in loops}
    if dry_run:
        return res
    dom = st.config.get("domain", {}).get("name", "")
    base = {"date": day, "reported": day, "by": by, "domain": dom, "source": source or f"theory revision, {day}",
            "author": "engram-theory"}
    words = f"\n- {config.owner()}: “{' '.join(said.split())}”" if said.strip() else ""
    ids: dict[str, str] = {}
    with st.transaction(message=commitmsg.message("theory", day=day)) as tx:
        for w in writes:
            if w[0] == "thing":
                t, about = w[1], w[2]
                p = repo / t.file
                if p.exists():
                    raise ChangeError(f"{t.file} exists")
                p.parent.mkdir(parents=True, exist_ok=True)
                fm = {"id": t.id, "kind": t.kind, "short": t.short, "stories": t.stories, "say": t.say, "since": day, "by": by}
                text = about.strip() or f"{t.title}. Part of the working model; its loops and connections: `engram theory`."
                p.write_text(frontmatter.dump({k: v for k, v in fm.items() if v not in (None, "", [])}) +
                             f"# {t.title}\n\n{text}\n" + (f"\nWhy it was added: {why.strip()}\n" if why.strip() else ""))
                tx.extra.append(t.file)
                res.written.append(t.file)
            elif w[0] == "edge":
                e = w[1]
                where = f"{h.things[e.loop].title.split(' — ')[0]} " if e.loop in h.things else ""
                fm = {**base, "title": f"{where}{h.label(e.a)} {e.rel} {h.label(e.b)}".strip(), "kind": "link",
                      "about": [e.loop] if e.loop else [e.a, e.b], "from": e.a, "to": e.b, "family": "theory", "rel": e.rel,
                      "since": day}
                if e.strength:
                    fm["strength"] = e.strength
                if e.loop:
                    fm.update(loop=e.loop, step=e.step)
                ev = tx.add(fm, f"{e.note}{words}" if words else e.note)
                ids[e.id] = ev.id
                res.written.append(ev.id)
            elif w[0] == "retire":
                e, replaced = w[1], w[2]
                where = f" ({g.things[e.loop].title.split(' — ')[0]})" if e.loop in g.things else ""
                ev = tx.add({**base, "title": f"retired: {g.label(e.a)} → {g.label(e.b)}{where}", "kind": "status",
                             "about": [f"link/{e.id}"], "status": theory.RETIRED, "replaced_by": replaced, "why": why.strip()},
                            f"- retired: {g.label(e.a)} {e.rel} {g.label(e.b)}{where}\n- replaced by: {replaced}\n- why: {why.strip()}{words}\n")
                res.written.append(ev.id)
            elif w[0] == "status":
                tid, to = w[1], w[2]
                ev = tx.add({**base, "title": f"{g.label(tid)}: {to}", "kind": "status", "about": [tid], "status": to},
                            f"- {g.label(tid)} is now {to}." + (f"\n- why: {why.strip()}" if why.strip() else "") + f"{words}\n")
                res.written.append(ev.id)
    res.change = f"{day}-{hashlib.sha256(' '.join(res.written).encode()).hexdigest()[:6]}"
    res.summary = {
        "date": day, "why": why.strip(),
        "new": [{"id": x, "title": h.things[x].title, "kind": h.things[x].kind} for x in touched["new"]],
        "loops": [{"id": l, "title": h.things[l].title, "before": g.draw(l) if l in g.things else "", "after": h.draw(l)} for l in loops],
        "retired": [{"id": e.id, "drawn": f"{g.label(e.a)} → {g.label(e.b)}", "loop": e.loop} for e in touched["retired"]],
        "joins": [{"from": e.a, "to": e.b, "rel": e.rel, "id": ids.get(e.id, "")} for e in touched["joins"]],
        "status": touched["status"],
    }
    if structural:
        with db() as c:
            c.execute("INSERT OR REPLACE INTO change (id, domain, repo, at, summary, state) VALUES (?, ?, ?, ?, ?, 'queued')",
                      (res.change, dom, str(repo), datetime.now().astimezone().isoformat(timespec="seconds"), json.dumps(res.summary)))
        if relink and not os.environ.get("ENGRAM_NO_RELINK"):
            log = data_path("relink.log")
            subprocess.Popen([sys.executable, "-m", "engram.cli", "theory", "relink", "--change", res.change],
                             stdout=log.open("a"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                             cwd=str(repo))
    return res


def ops_from_args(a) -> list[dict]:
    """The operations one `engram theory change` names with flags, in a sensible order (a new node before the step that
    uses it); --ops gives a list of them as JSON for a compound change."""
    if a.ops:
        text = sys.stdin.read() if a.ops == "-" else Path(a.ops).read_text()
        ops = json.loads(text)
        return ops if isinstance(ops, list) else [ops]
    ops = []
    if a.add_node:
        kind = a.add_node.split("/", 1)[0]
        ops.append({"op": "add-node", "id": a.add_node, "kind": kind, "title": a.title or "", "short": a.short or "",
                    "stories": _list(a.stories), "say": _list(a.say), "about": a.about or ""})
    if a.insert:
        ops.append({"op": "insert-step", "loop": a.insert, "after": a.after, "node": a.node,
                    "mechanisms": [m for m in (a.mechanism, a.mechanism_next) if m]})
    if a.remove:
        ops.append({"op": "remove-step", "loop": a.remove, "node": a.node, "mechanism": a.mechanism or ""})
    if a.join:
        ops.append({"op": "add-join", "from": a.join[0], "to": a.join[1], "rel": a.rel, "strength": a.strength,
                    "mechanism": a.mechanism or ""})
    if a.retire_join:
        ops.append({"op": "retire-join", "from": a.retire_join[0], "to": a.retire_join[1], "rel": a.rel,
                    "replaced_by": a.replaced_by or ""})
    if a.status:
        ops.append({"op": "status", "id": a.status, "to": a.to})
    return ops


def _list(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def notices(repo: Path, mark: bool = False) -> list[str]:
    """One line per finished re-check not yet shown: what changed and how the evidence moved. Shown once (mark). A
    re-check that errored shows one line every time until it's rerun, since only a hand rerun spends the money."""
    with db() as c:
        failed = [f"the evidence re-check after the theory change of {json.loads(summary).get('date', '?')} failed "
                  f"({(error or 'no reason recorded')[:120]}); rerun it: engram theory relink --change {cid}"
                  for cid, summary, error in c.execute("SELECT id, summary, error FROM change WHERE repo = ? AND state = 'error' "
                                                       "ORDER BY at", (str(repo),))]
        rows = c.execute("SELECT id, summary, result FROM change WHERE repo = ? AND state = 'done' AND shown = 0 ORDER BY at",
                         (str(repo),)).fetchall()
        out = []
        for cid, summary, result in rows:
            s, r = json.loads(summary), json.loads(result or "{}")
            what = "; ".join(f"{x['title'].split(' — ')[0]} revised {s['date']}: {x['after']}" for x in s.get("loops", [])) or \
                   "; ".join(f"{x['title']} added {s['date']}" for x in s.get("new", [])) or f"theory revised {s['date']}"
            bits = [f"{n} records now bear on {t}" for t, n in (r.get("bear") or {}).items() if n]
            if r.get("moved"):
                bits.append(f"{r['moved']} moved off the old step")
            if r.get("old_only"):
                bits.append(f"{r['old_only']} were evidence for the old version only")
            out.append(f"{what}" + (f" — {', '.join(bits)}" if bits else " — no records needed new links"))
            if mark:
                c.execute("UPDATE change SET shown = 1 WHERE id = ?", (cid,))
    return failed + out
