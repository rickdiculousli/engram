"""A hedged date narrows when a dated document turns up (.engram/README.md, the Dates section): the hourly job's step after
filing, for an area whose pack has `narrow` and `narrow_confirm` words (docs/technical.md, "The filer"). The first run
marks the record's head and asks nothing, so what the record already holds is never narrowed in bulk."""
import contextlib
import json
import re
import subprocess
from collections import Counter
from datetime import date, datetime
from fnmatch import fnmatchcase
from pathlib import Path

from engram import capture, commitmsg, config, ingest, pack, periods, relink, store, units, verbatim
from engram.index import open_index
from engram.paths import index_path
from engram.sources import sections

COUNTS = ("documents", "undated", "unindexed", "failed", "asks", "narrowed", "disagree", "reset")
NOT_CARRIED = ("id", "heading", "date", "approx", "date_note", "range_from", "range_to", "as_said", "reported", "landmark", "source")


def _line(e: store.Event) -> str:
    a, b = periods.of(e.fm, units.said_on(e.id, None))
    return f"[{e.id}] {e.fm.get('title')} (some day from {a} to {b})\n{e.body.strip()}"


def candidates(st: store.Store, day: str) -> list[store.Event]:
    """The entries a document dated `day` could narrow: dated roughly (`approx`, or two ends), heading their chains
    (nothing revises or supersedes them), their range holding the day."""
    gone, (a, b) = units.corrected(st), periods.span(day)
    return [e for e in st.events() if e.kind != "link" and e.id not in gone
            and (str(e.fm.get("approx")).lower() in ("true", "yes") or e.fm.get("range_to"))
            and (r := periods.of(e.fm, units.said_on(e.id, None))) and r[0] <= a and b <= r[1]]


def dated(domain: str, files: list[str]) -> dict[str, str | None]:
    """Each file the index holds once refreshed, with the earliest date the index gives it; None when it gives none. A
    file it doesn't hold is left out. A refresh that recorded an error raises."""
    ingest.record(domain)
    out = {}
    with contextlib.closing(open_index(index_path(domain), readonly=True)) as idx:
        if err := next((s["last_error"] for s in idx.sources() if s["source"] == sections.SOURCE and s["last_error"]), None):
            raise RuntimeError(f"the index's refresh failed: {err}")
        for f in files:
            if rows := idx.db.execute("SELECT date_key, date FROM doc WHERE substr(ref, 1, ?) = ?", (len(f) + 1, f + "#")).fetchall():
                out[f] = min(((k, d) for k, d in rows if k and periods.span(d)), default=(None, None))[1]
    return out


def run(domain: str, root: Path, ask=None, dry_run: bool = False) -> dict:
    """Narrow what the documents under `[timeline] whole` the record gained since its mark (git) date, and return the
    counts (`COUNTS`), the cost, for a dry run each document's candidates, and an `error`: anything raised, a model's
    error among them, stops the run with nothing written and the mark where it was, so the next run tries again."""
    out = dict.fromkeys(COUNTS, 0) | {"usd": 0.0, "would_ask": [], "error": None}
    try:
        _pass(domain, root, ask or capture._ask, dry_run, out)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _call(ask, out: dict, prompt: str) -> str:
    reply, usd = ask(prompt)
    out["usd"], out["asks"] = out["usd"] + usd, out["asks"] + 1
    return reply


def _pass(domain: str, root: Path, ask, dry_run: bool, out: dict):
    """One call per dated document with candidates asks which it records as happening on its own date, and each yes goes
    to a second call. A reply with no readable answer fails that document, once: the entry stays a range. A candidate
    confirmed on one date gets a new entry there that supersedes it; on two dates, none. The mark moves to the head it
    read after the commit, never past a document the refresh could still read; a document absent from a clean refresh
    never will be read, and is counted and passed. A mark gone from history is reset to the head, asking nothing."""
    p, st = pack.load(domain), store.Store(root)
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout
    head = git("rev-parse", "HEAD").strip()
    with contextlib.closing(capture.db()) as c:
        since, before = c.execute("SELECT mark, counts FROM narrow WHERE domain = ?", (domain,)).fetchone() or (None, "{}")
    if since and subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", since, head], capture_output=True).returncode:
        since, out["reset"] = None, 1
    whole = st.config.get("timeline", {}).get("whole", [])
    new = [f for f in (git("diff", "-z", "--name-only", "-M", "--diff-filter=A", since, head).split("\0") if since else [])
           if f and any(fnmatchcase(f, w) for w in whole)]
    docs = dated(domain, new) if new else {}
    out["unindexed"] = len(new) - len(docs)
    found = {}  # candidate -> {date: document}
    for f, day in docs.items():
        out["documents" if day else "undated"] += 1
        if not day or not (cands := {e.id: e for e in candidates(st, day)}):
            continue
        if dry_run:
            out["would_ask"].append({"document": f, "date": day, "candidates": sorted(cands)})
            continue
        fields = {"document": f, "date": day, "text": (root / f).read_text(errors="replace")[:relink.SWEEP_BUDGET]}
        try:
            said = capture.reply_json(_call(ask, out, config.voice(p.prompts["narrow"]).format(
                **fields, entries="\n\n".join(map(_line, cands.values()))))).get("narrows")
            for r in said if isinstance(said, list) else []:
                r = r if isinstance(r, dict) else {}
                e, passage = cands.get(str(r.get("id"))), str(r.get("passage") or "")
                if not e or not passage.strip() or not verbatim.found(passage, fields["text"]):
                    continue
                yes = _call(ask, out, config.voice(p.prompts["narrow_confirm"]).format(**fields, entry=_line(e), passage=passage))
                if re.match(r"\W*yes\b", yes, re.I):
                    found.setdefault(e.id, {}).setdefault(day, f)
                elif not re.match(r"\W*no\b", yes, re.I):
                    raise capture.ReplyError("the confirm said neither yes nor no")
        except capture.ReplyError:
            out["failed"] += 1
    sure = {i: next(iter(d.items())) for i, d in found.items() if len(d) == 1}
    out["disagree"] = len(found) - len(sure)
    if dry_run:
        return
    if sure:
        evs, dom = {e.id: e for e in st.events()}, st.config.get("domain", {}).get("name", "")
        with st.transaction(message=commitmsg.message("narrow", n=len(sure))) as tx:
            for i, (day, f) in sure.items():
                e = evs[i]
                fm = {**{k: v for k, v in e.fm.items() if k not in NOT_CARRIED}, "date": day, "supersedes": i,
                      "narrowed_by": f, "author": "engram-capture", "domain": dom}
                # `recorded` keeps its place in `now`'s chain; the id is when it was filed, which as-it-stood reads go by
                fm["id"] = store.event_id(datetime.now().astimezone().isoformat(), e.kind, store.render_event(fm, e.body))
                to = tx.add(fm, e.body).id
                tx.add({"title": f"{to} supersedes {i}", "date": date.today().isoformat(), "kind": "link", "about": e.about,
                        "from": to, "to": i, "family": "evidence", "rel": "supersedes", "author": "engram-capture",
                        "domain": dom}, f"narrowed by {f}")
    out["narrowed"] = len(sure)
    total = Counter(json.loads(before)) + Counter({k: out[k] for k in COUNTS})
    with contextlib.closing(capture.db()) as c, c:
        c.execute("INSERT OR REPLACE INTO narrow VALUES (?, ?, ?)", (domain, head, json.dumps(total)))
