"""The frozen gate: what one area's retrieval and filer do on fixed inputs, as counts and hashes, so a change that
moves anything that area sees is caught before it lands (docs/evaluation.md, "The frozen gate"). The area is the
config's `[review] gate`; `[review] gate_sets` names its question sets at freeze, the newest last.

usage: uv run python bench/gate.py freeze --pack <repo>@<commit>   # once: pick the sessions, pin the record without their writes, copy the data
       uv run python bench/gate.py record --pack <repo>@<commit>   # once: the real filer over the sessions, replies saved
       uv run python bench/gate.py run <out.json> --pack <repo>@<commit>   # every change: the measures on the frozen inputs
       uv run python bench/gate.py check-pin <out.json>   # before a release: the box's pin for the area is the gated tree
       uv run python bench/gate.py compare <a.json> <b.json>

The gate folder is $ENGRAM_GATE, else the data folder's gate/. Each run works on a fresh copy of its data, with
ENGRAM_FROZEN=1, the clock pinned to the day it was frozen and every model call refused. Nothing it writes holds
record text: refs, prompts, replies and entries are hashed.
"""
import hashlib
import importlib
import json
import os
import pkgutil
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from datetime import date, datetime
from pathlib import Path

from engram import config as _config
from engram.paths import data_dir, data_path

GATE = Path(os.environ.get("ENGRAM_GATE") or data_path("gate")).expanduser()
LIVE = data_dir()
PROJECTS = Path.home() / ".claude/projects"
SESSIONS, WITH_ENTRIES, MAX_BYTES = 10, 5, 1 << 20  # the fixed sessions: those that filed something first, then small ones
D = str(_config.raw().get("review", {}).get("gate") or "")  # the area gated, read before a run swaps the config
DATA_FILES = [f"{D}.sqlite", "capture.sqlite", "sessions-state.sqlite", "theory.sqlite"]
DATA_DIRS = ["moved", f"summaries/{D}", f"record-summaries/{D}"]
# The index rows hashed, by table and column. Timestamps (doc.recorded) and row ids are left out, and a column added
# later is outside the hash until it's listed here, so an additive change leaves the hash alone.
INDEX_COLUMNS = {
    "doc": ["ref", "source", "class", "kind", "date", "date_key", "title", "body", "tags", "author", "superseded",
            "pointer", "parent", "node", "milestone", "stories", "nid"],
    "link": ["from_ref", "to_ref", "family", "rel", "story", "event", "note"],
    "on_story": ["ref", "story", "source"],
    "rec_summary": ["ref", "summary"],
    "way": ["kind", "key", "phrase"],
    "way_ref": ["kind", "key", "ref"],
}
THEN = ["2026-03-01", "2026-08-01"]  # the theory graph as it stood on two fixed days
KINDS = ("facts", "verify", "structure")  # the filer's three asks


def sha(x) -> str:
    return hashlib.sha256((x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)).encode()).hexdigest()[:16]


def index_hash(db: Path, columns: dict[str, list[str]] = INDEX_COLUMNS) -> dict:
    """Per table: its row count and a hash of its rows, sorted, over the listed columns only."""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        have = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        out = {}
        for table, cols in columns.items():
            rows = sorted(json.dumps(r, default=str) for r in c.execute(
                f"SELECT {', '.join(cols)} FROM {table}")) if table in have else []
            out[table] = {"rows": len(rows), "hash": sha("\n".join(rows))}
        return out
    finally:
        c.close()


def flatten(d, at: str = "") -> dict:
    if isinstance(d, dict):
        return {k: v for key, val in d.items() for k, v in flatten(val, f"{at}.{key}" if at else str(key)).items()}
    return {at: d}


def compare(a: dict, b: dict) -> list[str]:
    """Each value that differs, by name; `meta` (paths, times) is never compared, and the pack's tree only when the
    baseline has one (one made before packs had none)."""
    skip = {"meta"} | ({"pack_tree"} if not a.get("pack_tree") else set())
    fa, fb = flatten({k: v for k, v in a.items() if k not in skip}), flatten({k: v for k, v in b.items() if k not in skip})
    return [f"{k}: {fa.get(k, '(missing)')} -> {fb.get(k, '(missing)')}" for k in sorted(fa.keys() | fb.keys())
            if fa.get(k, "(missing)") != fb.get(k, "(missing)")]


class Replies:
    """The filer's asks answered from recorded replies, the n-th ask of each kind getting the n-th recorded reply of
    that kind. Every prompt is hashed; an ask past the recording gets an empty reply and is counted."""

    def __init__(self, recorded: list[dict]):
        self.left = {k: [r for r in recorded if r["kind"] == k] for k in KINDS}
        self.prompts, self.unrecorded, self.matched = [], 0, 0

    def ask(self, kind: str):
        def answer(prompt: str) -> tuple[str, float]:
            self.prompts.append(f"{kind}:{sha(prompt)}")
            if not self.left[kind]:
                self.unrecorded += 1
                return "{}", 0.0
            r = self.left[kind].pop(0)
            self.matched += r["prompt"] == sha(prompt)
            return r["reply"], 0.0
        return answer


def filer_result(res: dict, rep: Replies) -> dict:
    """One session's dry run as counts and hashes."""
    return {"prompts": sha(rep.prompts), "asks": len(rep.prompts), "unrecorded": rep.unrecorded,
            "same_prompts_as_recorded": rep.matched,
            "would_file": {"n": len(res["would_file"]), "hash": sha(res["would_file"])},
            "dropped": {"n": len(res["dropped"]), "hash": sha(res["dropped"])},
            "kept": {"n": len(res["kept"]), "hash": sha(res["kept"])}}


# ---- the frozen world a run sees

def _manifest() -> dict:
    return json.loads((GATE / "manifest.json").read_text())


def _record() -> Path:
    return GATE / _manifest()["record"]


def _sets() -> list[str]:
    """The question sets frozen, the newest last; the held-back set is sealed, so the gate never reads it."""
    return _manifest()["sets"]


def _env(data: Path, conf: Path):
    os.environ.update(ENGRAM_DATA=str(data), ENGRAM_CONFIG=str(conf), ENGRAM_FROZEN="1",
                      ENGRAM_SANDBOX="1")
    for k in ("ENGRAM_EXCLUDE_SOURCES", "ENGRAM_AS_OF", "ENGRAM_AS_IT_STOOD", "ENGRAM_TAG", "ENGRAM_FIX"):
        os.environ.pop(k, None)


def _pin_clock(today: date):
    """Every `date.today()` and `datetime.now()` in every engram module loaded, the area's pack's included, read as noon
    on the day the gate was frozen. Every engram module is imported first: one a call imports later would read the real
    clock."""
    import engram
    from engram import pack
    for m in pkgutil.walk_packages(engram.__path__, "engram."):
        importlib.import_module(m.name)
    pack.load(D)
    noon = datetime(today.year, today.month, today.day, 12).astimezone()

    class Day(date):
        @classmethod
        def today(cls):
            return today

    class Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return noon if tz is None else noon.astimezone(tz)

        @classmethod
        def today(cls):
            return noon.replace(tzinfo=None)
    for name, mod in list(sys.modules.items()):
        if name.startswith("engram"):
            if getattr(mod, "date", None) is date:
                mod.date = Day
            if getattr(mod, "datetime", None) is datetime:
                mod.datetime = Now
    from engram import capture
    capture._now = lambda: noon


def _no_models():
    """A run makes no model call: every `claude` it would start raises."""
    real = subprocess.run

    def guarded(cmd, *a, **kw):
        if (cmd[0] if isinstance(cmd, (list, tuple)) else str(cmd).split()[0]) == "claude":
            raise RuntimeError("the gate makes no model calls")
        return real(cmd, *a, **kw)
    subprocess.run = guarded


def _world(work: Path, pack: str = "") -> dict:
    """A fresh copy of the gate's data in `work`, engram pointed at it with the area's pack, the record checked at its
    pinned commit. The pack is `<repo>@<commit>`, extracted as live extracts a pin and pinned the same way (the tree it
    measured goes in the result), or a directory while building."""
    m = _manifest()
    head = subprocess.run(["git", "-C", str(_record()), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(_record()), "status", "--porcelain"], capture_output=True, text=True).stdout
    if head != m["commit"] or dirty:
        sys.exit(f"the gate's record moved: HEAD {head[:12]}, {len(dirty.splitlines())} changed paths")
    shutil.copytree(GATE / "data", work / "data")
    conf = work / "config.toml"
    repo, _, pin = pack.rpartition("@")
    pin = pin if repo else pack
    conf.write_text((GATE / "config.toml").read_text().replace(f"[domains.{D}]\n", f"[domains.{D}]\npack = {json.dumps(pin)}\n"))
    _env(work / "data", conf)
    if repo:
        from engram import pack as packs
        packs.extract(D, Path(repo).expanduser(), pin)
        m["pack_tree"] = packs.tree(Path(repo).expanduser(), pin)
    _pin_clock(date.fromisoformat(m["today"]))
    return m


def _session_path(s: dict) -> Path:
    return GATE / "sessions" / s["project"] / f"{s['id']}.jsonl"


# ---- freeze, record, run

WROTE = re.compile(r"^(?:said|agreed) in session (\S{8}) ")  # an entry, renewal or placement link a session filed


def _writes(clone: Path) -> dict[str, list]:
    """Each session's writes in the clone, by the first 8 of its id, as the store reads them: every entry, renewal and
    placement link whose source names the session."""
    from engram import store
    out = {}
    for e in store.Store(clone).events():
        if m := WROTE.match(str(e.fm.get("source", ""))):
            out.setdefault(m[1], []).append(e)
    return out


def _filed(writes: list) -> int:
    """What a session filed, as the filer counts it: its renewals and placement links are bookkeeping."""
    from engram.now import RENEWAL
    return sum(e.kind != RENEWAL and e.fm.get("family") != "timeline" for e in writes)


def freeze(pack: str):
    """The record is cloned at HEAD, the sessions picked from it, then their writes are taken out of the clone in one
    commit and the index rebuilt from it, so the filer reads each session for the first time: nothing of its own in the
    record, the record-window search or the repeat check."""
    from engram import config
    from engram.paths import index_path
    if (GATE / "manifest.json").exists():
        sys.exit(f"{GATE} is already frozen")
    if subprocess.run(["pgrep", "-f", "capture run"], capture_output=True).stdout.strip():
        sys.exit("the hourly job is running; freeze when it's done")
    GATE.mkdir(parents=True, exist_ok=True)
    sets = list(_config.raw().get("review", {}).get("gate_sets") or [f"{D}.toml"])
    clone = GATE / config.load()[D].repo.name
    subprocess.run(["git", "clone", "-q", str(config.load()[D].repo), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "remove", "origin"], check=True)  # nothing here can push
    data = GATE / "data"
    data.mkdir()
    for f in DATA_FILES:
        if (LIVE / f).exists():
            src, dst = sqlite3.connect(f"file:{LIVE / f}?mode=ro", uri=True), sqlite3.connect(data / f)
            src.backup(dst)
            src.close(), dst.close()
    for d in DATA_DIRS:
        if (LIVE / d).exists():
            shutil.copytree(LIVE / d, data / d)
    if (LIVE / "summaries/vocabulary.txt").exists():
        shutil.copy2(LIVE / "summaries/vocabulary.txt", data / "summaries/vocabulary.txt")
    (data / "eval").mkdir()
    for f in sets:
        shutil.copy2(LIVE / "eval" / f, data / "eval" / f)
    (GATE / "config.toml").write_text(f'[domains.{D}]\nrepo = "{clone}"\n'  # every other area emptied
                                      + "".join(f'[domains.{n}]\nrepo = ""\n' for n in config.load() if n != D))
    writes = _writes(clone)
    c = sqlite3.connect(data / "capture.sqlite")
    rows = [r for r in c.execute("SELECT session, path FROM filed WHERE domain = ? ORDER BY session", (D,))
            if Path(r[1]).exists() and "/subagents/" not in r[1]]
    chosen = [r for r in rows if _filed(writes.get(r[0][:8], []))][:WITH_ENTRIES]
    chosen += [r for r in rows if not writes.get(r[0][:8]) and Path(r[1]).stat().st_size <= MAX_BYTES][:SESSIONS - len(chosen)]
    picked, gone = [], []
    for sid, path in chosen:
        src = Path(path)
        s = {"id": sid, "project": src.relative_to(PROJECTS).parts[0], "filed_before": _filed(writes.get(sid[:8], []))}
        gone += writes.get(sid[:8], [])
        dst = _session_path(s)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        s |= {"bytes": dst.stat().st_size, "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
        picked.append(s)
        # read whole, as `capture refile` would, with nothing shown as already filed
        c.execute("UPDATE filed SET upto = 0, bytes = 0, entries = '[]', path = ? WHERE session = ?", (str(dst), sid))
    c.execute("UPDATE repo SET root = ? WHERE domain = ?", (str(clone), D))
    c.commit()
    c.close()
    lines = {}  # a link is a line of the links file, `<file>:<n>`; every other write is a file of its own
    for e in gone:
        f, _, n = e.path.partition(":")
        if n:
            lines.setdefault(f, set()).add(int(n))
        else:
            (clone / f).unlink()
    for f, ns in lines.items():
        (clone / f).write_text("".join(l for n, l in enumerate((clone / f).read_text().splitlines(keepends=True), 1) if n not in ns))
    git = ["git", "-C", str(clone)]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", f"gate: the {len(picked)} picked sessions' {len(gone)} writes taken out"], check=True)
    commit = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    m = {"commit": commit, "record": clone.name, "sets": sets, "today": date.today().isoformat(), "frozen": datetime.now().astimezone().isoformat(timespec="seconds"),
         "sessions": picked}
    (GATE / "manifest.json").write_text(json.dumps(m, indent=1))
    with tempfile.TemporaryDirectory(prefix="gate-") as work:  # the index re-read from the trimmed clone, as a run reads it
        from engram import cli
        from engram.sources import sections
        _world(Path(work), pack)
        cli._ingest(D, sections)
        src, dst = sqlite3.connect(index_path(D)), sqlite3.connect(data / f"{D}.sqlite")
        src.backup(dst)
        src.close(), dst.close()
    print(f"frozen at {commit[:12]}: {len(picked)} sessions, {sum(s['filed_before'] > 0 for s in picked)} that filed something, "
          f"{len(gone)} of their writes taken out")


def record(pack: str):
    """The real filer, once, over the fixed sessions: each raw reply saved, nothing filed."""
    from engram import capture
    out = GATE / "replies"
    if out.exists():
        sys.exit(f"{out} already holds the recorded replies")
    with tempfile.TemporaryDirectory(prefix="gate-") as work:
        m = _world(Path(work), pack)
        out.mkdir()
        calls, usd = 0, 0.0
        for s in m["sessions"]:
            got = []

            def saving(kind, real):
                def ask(prompt):
                    reply, cost = real(prompt)
                    got.append({"kind": kind, "prompt": sha(prompt), "reply": reply, "usd": cost})
                    return reply, cost
                return ask
            try:
                capture.file_session(D, _record(), _session_path(s), dry_run=True,
                                     ask=saving("facts", capture._ask), ask_verify=saving("verify", capture._ask_verify),
                                     ask_structure=saving("structure", capture._ask_structure))
                error = None
            except Exception as e:
                error = type(e).__name__
            (out / f"{s['id']}.json").write_text(json.dumps(got))
            calls += len(got)
            usd += sum(r["usd"] for r in got)
            print(f"{s['id'][:8]}: {len(got)} calls{', ' + error if error else ''}")
        m["recorded"] = {"calls": calls, "usd": round(usd, 4), "at": datetime.now().astimezone().isoformat(timespec="seconds")}
        (GATE / "manifest.json").write_text(json.dumps(m, indent=1))
        print(f"{calls} model calls, ${usd:.2f}")


def measure16(qs: list[dict]) -> dict:
    """On the newest tuning set only: frame questions (records in one
    timeline call, tokens per call), single facts both ways, waxing occurrences. Counts, miss ids and a row hash."""
    import statistics
    from engram import evalset, search, timeline
    qs = evalset.live(qs)
    pairs, pic, nrows = evalset.same_records(D), evalset.picture(D), evalset.now_rows(D)
    syms = timeline.names(D)["symptoms"]
    chains = {s: evalset.timeline_refs([r for r in timeline.chain(D, s)[1] if r.get("_ref")]) for s in syms}
    o = {"frame": {}, "facts": {}, "new": {}, "wax": {}, "tokens": []}
    for q in qs:
        if q.get("kind") == "lookup" or not q.get("links"):
            continue
        h, rows = timeline.chain(D, [], q["question"])
        own = evalset.own_source(q).replace("sessions:", "session:")
        rows = [r for r in rows if own == "" or not r.get("_ref", "").startswith(own)]
        refs = evalset.timeline_refs(rows)
        o["frame"][q["id"]] = [bool(evalset.hit(l["refs"], refs)) for l in q["links"]]
        o["tokens"].append(len(timeline.render(h, rows, "tsv")) // 4)
    for q in [q for q in qs if q.get("kind") == "lookup"]:
        refs = []
        for hh in search.search(q["question"], [D], limit=5):
            refs += evalset.result_refs(hh)
        o["facts"][q["id"]] = bool(evalset.hit(q["expect"], refs))
        o["new"][q["id"]] = evalset.fact_in_hand(q, *evalset.hand(D, q["question"], pic), pairs, nrows)
    for q in [q for q in qs if q.get("waxing")]:
        best = max(syms, key=lambda s: sum(evalset.hit([e], chains[s]) for e in q["expect"]))
        o["wax"][q["id"]] = [bool(evalset.hit([e], chains[best])) for e in q["expect"]]
    fr, nw = o["frame"].values(), o["new"]
    return {"frame_complete": f"{sum(all(v) for v in fr)}/{len(fr)}", "frame_records": f"{sum(map(sum, fr))}/{sum(map(len, fr))}",
            "tokens_median": int(statistics.median(o["tokens"])) if o["tokens"] else 0, "tokens_total": sum(o["tokens"]),
            "facts_strict": f"{sum(o['facts'].values())}/{len(o['facts'])}",
            "facts_in_hand": f"{sum(map(bool, nw.values()))}/{len(nw)}",
            "in_hand_by": {k: sum(v == k for v in nw.values()) for k in ("record", "picture", "points")},
            "waxing": f"{sum(map(sum, o['wax'].values()))}/{sum(map(len, o['wax'].values()))}",
            "misses": {"frame": sorted(k for k, v in o["frame"].items() if not all(v)),
                       "facts_strict": sorted(k for k, v in o["facts"].items() if not v),
                       "facts_in_hand": sorted(k for k, v in nw.items() if not v)},
            "rows": sha(o)}


# ---- what the moved code does on fixed inputs: the picture, the theory graph, a revision and its re-check, a synthetic
# session that repeats a medication and agrees to a structural change, every search as printed, every timeline whole

PROBE_SAID = "yes, change the model that way"


def _probe_ops(g) -> list[dict]:
    """A fixed structural change on the frozen graph, from its shape alone: a new node put into the first loop after
    its first member, and a join between the first two conditions."""
    loop = g.loops()[0]
    nodes = [t for t, x in g.things.items() if x.kind == "node"]
    return [{"op": "add-node", "id": "node/gate-probe", "kind": "node", "title": "Gate probe", "short": "probe",
             "stories": [], "say": [], "about": "a fixed change the gate makes"},
            {"op": "insert-step", "loop": loop, "after": g.path(loop)[0], "node": "node/gate-probe",
             "mechanisms": ["into the probe", "out of the probe"]},
            {"op": "add-join", "from": nodes[0], "to": nodes[1], "rel": "amplifier", "strength": "low",
             "mechanism": "a fixed join the gate makes"}]


def _probe_session(work: Path, project: str, med: str, proposal: str) -> Path:
    def turn(kind, content, ts):
        return json.dumps({"type": kind, "timestamp": ts, "cwd": "/gate", "message": {"role": kind, "content": content}})
    path = work / "projects" / project / "gate-probe.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join([
        turn("user", f"I'm still taking {med} and a brief knee twinge came back this morning", "2026-10-26T17:00:00Z"),
        turn("assistant", [{"type": "text", "text": f"Noted. {proposal}"}], "2026-10-26T17:01:00Z"),
        turn("user", PROBE_SAID, "2026-10-26T17:02:00Z"),
        turn("assistant", [{"type": "text", "text": "Done."}], "2026-10-26T17:03:00Z"),
    ]) + "\n")
    return path


def _relink_reply(prompt: str) -> tuple[str, float]:
    """A fixed reply to each re-check batch, from the prompt alone: the batch's first record strengthens the first
    target, its second was evidence for the first retired step only, and two links code must drop."""
    ids = re.findall(r"^\[(.+?)\] date ", prompt.split("<records>", 1)[1], re.M)
    tgts = prompt.split("- \"to\": one of these targets: ", 1)[1].split("\n", 1)[0].split(", ")
    gone = [t for t in tgts if t.startswith("link/")]
    links = [{"record": ids[0], "to": tgts[0], "rel": "strengthens", "why": "fixed"}] if ids else []
    if len(ids) > 1 and gone:
        links.append({"record": ids[1], "to": gone[0], "rel": "strengthens", "why": "fixed"})
    links += [{"record": "no-such-record", "to": tgts[0], "rel": "strengthens"},
              {"record": ids[0] if ids else "", "to": "node/nowhere", "rel": "weakens"}]
    return json.dumps({"links": links}), 0.0


def probes(work: Path, m: dict) -> dict:
    from engram import capture, now, relink, theory, theorychange
    repo, today = _record(), date.fromisoformat(m["today"])
    out = {"now": {"text": sha(now.text(repo, today)), "standing": sha(sorted(now.standing(repo).items())),
                   "rows": sha([vars(d) for d in now.docs_for(repo, today)])}}
    g = theory.load(repo)
    if not g.loops():  # an area with no theory graph: nothing more to probe
        return out
    out["theory"] = {"now": {"text": sha(theory.text(g)), "mermaid": sha(theory.mermaid(g))}}
    for day in THEN:
        h = theory.load(repo, asof=day)
        out["theory"][day] = {"text": sha(theory.text(h)), "mermaid": sha(theory.mermaid(h)),
                              "files": sha(theory.files_then(repo, h, day))}
    ops = _probe_ops(g)

    def attempt(change: list[dict]):
        try:
            r = theorychange.apply(repo, change, why="a fixed change", dry_run=True)
            return {"structural": r.structural, "drawn": sha(r.drawn)}
        except theorychange.ChangeError as e:
            return {"refused": sha(str(e))}
    disc = next(t for t, x in g.things.items() if x.kind == "discovery")
    out["change"] = {"ops": attempt(ops), "status": attempt([{"op": "status", "id": disc, "to": "provisional"}]),
                     "bad": attempt([{**ops[1], "after": "node/nowhere"}])}
    loop = g.loops()[0]
    step = next(e for e in g.edges if e.loop == loop)
    summary = {"date": m["today"], "why": "a fixed change", "new": [],
               "loops": [{"id": loop, "title": g.things[loop].title, "before": g.draw(loop), "after": g.draw(loop)}],
               "retired": [{"id": step.id, "drawn": f"{g.label(step.a)} → {g.label(step.b)}", "loop": loop}],
               "joins": [{"from": ops[2]["from"], "to": ops[2]["to"], "rel": "amplifier"}]}
    asked = []
    rl = relink._run("gate-probe", repo, summary, lambda p: (asked.append(sha(p)), _relink_reply(p))[1], True, None)
    out["relink"] = {"prompts": sha(asked), "batches": rl["batches"], "links": sha(rl["links"]),
                     "dropped": sha(rl["dropped"]), "result": rl["result"]}
    med = next((c.name for c in now.build(repo, today).get("medications", []) if c.status == "taking"), None)
    if med is None:  # the synthetic session repeats a tracked thing the area has
        return out
    proposal = "Shall I add a probe condition into the first loop?"
    path = _probe_session(work, m["sessions"][0]["project"], med, proposal)
    facts = {"facts": [
        {"line": 1, "text": f"Still taking {med}", "quote": f"still taking {med}", "date": "not-sure", "kind": "med-change",
         "entity": med, "status": "taking", "about": [], "stories": []},
        {"line": 1, "text": "A brief knee twinge came back", "quote": "a brief knee twinge came back this morning",
         "date": "2026-10-26", "kind": "symptom", "about": [], "stories": []}],
        "theory": [{"line": 3, "quote": PROBE_SAID, "answering": proposal,
                    "status": {"id": ops[2]["from"], "to": "confirmed"}}], "structural": 3}
    structural = {"line": 3, "quote": PROBE_SAID, "answering": proposal, "why": "a fixed change", "ops": ops}
    asked = []

    def fixed(kind, reply):
        def ask(prompt):
            asked.append(f"{kind}:{sha(prompt)}")
            return json.dumps(reply), 0.0
        return ask
    res = capture.file_session(D, repo, path, dry_run=True, ask=fixed("facts", facts),
                               ask_verify=fixed("verify", {"repeats": []}), ask_structure=fixed("structure", structural))
    out["synthetic"] = {"prompts": sha(asked), "asks": len(asked), "would_file": sha(res["would_file"]),
                        "dropped": sha(res["dropped"]), "kept": sha(res["kept"]),
                        "why": [d["why"].split(":")[0][:12] for d in res["dropped"]],
                        "n": [len(res["would_file"]), len(res["dropped"]), len(res["kept"])]}
    return out


def shown(qs: list[dict]) -> dict:
    """Every question's search as `engram search` prints it, and every timeline whole: each chain by name, and each
    question's own."""
    from engram import cli, search, timeline
    out = {"search": sha([cli.render(search.search(q["question"], [D], limit=5)) for q in qs])}
    have = timeline.names(D)
    out["timeline"] = {kind: sha([timeline.render(*timeline.chain(D, n), "tsv") for n in names])
                       for kind, names in sorted(have.items())}
    out["timeline"]["questions"] = sha([timeline.render(*timeline.chain(D, [], q["question"]), "tsv") for q in qs])
    return out


def run(out: Path, pack: str = ""):
    from engram import capture, cli, evalset
    from engram.paths import index_path
    from engram.sources import sections
    with tempfile.TemporaryDirectory(prefix="gate-") as work:
        m = _world(Path(work), pack)
        _no_models()
        result = {"pack_tree": m.get("pack_tree"),
                  "meta": {"gate": str(GATE), "code": str(Path(capture.__file__).parent), "pack": pack, "commit": m["commit"],
                           "today": m["today"], "at": datetime.now().astimezone().isoformat(timespec="seconds")}}
        result["filer"] = {}  # first, on the frozen index the replies were recorded against
        for s in m["sessions"]:
            rec = GATE / "replies" / f"{s['id']}.json"
            rep = Replies(json.loads(rec.read_text()) if rec.exists() else [])
            try:
                res = capture.file_session(D, _record(), _session_path(s), dry_run=True,
                                           ask=rep.ask("facts"), ask_verify=rep.ask("verify"), ask_structure=rep.ask("structure"))
                result["filer"][s["id"][:8]] = filer_result(res, rep)
            except Exception as e:
                result["filer"][s["id"][:8]] = {"error": type(e).__name__, "prompts": sha(rep.prompts)}
        cli._ingest(D, sections)  # then the record re-read by this code, as the 15-minute refresh would
        result["index"] = index_hash(index_path(D))
        result["direct"] = {}
        for f in _sets():
            rows = evalset.run_direct(evalset.live(evalset.load(Path(work) / "data/eval" / f)["q"]), D)
            result["direct"][f] = {**evalset.summarize(rows), "rows": sha(rows)}
        result["measure16"] = measure16(evalset.load(Path(work) / "data/eval" / _sets()[-1])["q"])
        qs = [q for f in _sets() for q in evalset.live(evalset.load(Path(work) / "data/eval" / f)["q"])]
        result["shown"] = shown(qs)
        result["probes"] = probes(Path(work), m)
    out.write_text(json.dumps(result, indent=1, sort_keys=True))
    f = result["filer"].values()
    print(f"index {result['index']['doc']['rows']} rows | direct " +
          ", ".join(f"{k} {v['recall_at_5']}" for k, v in result["direct"].items()) +
          f" | frame {result['measure16']['frame_complete']} | filer {len(f)} sessions, "
          f"{sum(x.get('asks', 0) for x in f)} asks ({sum(x.get('same_prompts_as_recorded', 0) for x in f)} as recorded), {sum(x.get('would_file', {}).get('n', 0) for x in f)} would file, "
          f"{sum(x.get('unrecorded', 0) for x in f)} unrecorded | saved {out}")


def check_pin(result: dict) -> str | None:
    """Why the box's pin for the area isn't the pack this run measured, or None: its pack's tree must be the gated one."""
    from engram import config, pack
    d = config.load().get(D)
    if not d or not d.repo or not pack.SHA.match(d.pack):
        return f"the box's config pins no {D or 'gated'} pack commit"
    if not result.get("pack_tree"):
        return "this run measured no pinned pack (run it with --pack <repo>@<commit>)"
    have = pack.tree(d.repo, d.pack)
    return None if have == result["pack_tree"] else f"the pin's pack tree {have[:12]} isn't the gated {result['pack_tree'][:12]}"


def main(argv: list[str]):
    if os.environ.get("PYTHONHASHSEED") != "0":  # set order reaches prompts and ranking ties: pin it
        os.execve(sys.executable, [sys.executable, *sys.argv], {**os.environ, "PYTHONHASHSEED": "0"})
    cmd = argv[0] if argv else ""
    if cmd in ("freeze", "record", "run", "check-pin") and not D:
        sys.exit("no gate set: name the area in the config's [review] gate")
    if cmd in ("freeze", "record") and (len(argv) != 3 or argv[1] != "--pack"):
        sys.exit(__doc__)
    if cmd == "freeze":
        freeze(argv[2])
    elif cmd == "record":
        record(argv[2])
    elif cmd == "run" and len(argv) in (2, 4) and (len(argv) == 2 or argv[2] == "--pack"):
        run(Path(argv[1]).expanduser(), argv[3] if len(argv) == 4 else "")
    elif cmd == "check-pin" and len(argv) == 2:
        why = check_pin(json.loads(Path(argv[1]).expanduser().read_text()))
        print(why or "the pin is the gated pack")
        sys.exit(1 if why else 0)
    elif cmd == "compare" and len(argv) == 3:
        diff = compare(*(json.loads(Path(p).expanduser().read_text()) for p in argv[1:]))
        print("same" if not diff else "\n".join(diff))
        sys.exit(1 if diff else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
