"""What the owner said in a session, as rows on his stories (.engram/README.md, "What he said in a session is a row on its
story"). Each session's stitched summary already picks out the passages that count, every one tied to its line: symptom
reports, other things he reported, his decisions, and changes of mind. Each becomes a record, quoted, dated the day it
was said, and placed on the stories it bears on: a symptom report by its recurring symptom's stories, anything else by
the stories its words find. Only sessions the index already holds are used, so sessions kept out of it stay out."""
import json

from engram import config, dates
from engram.index import Doc, open_index
from engram.paths import data_path, index_path

SOURCE = "said"
KINDS = {"complaints": ("symptom", "{owner_id}"), "reported": ("report", "{owner_id}"), "decisions": ("decision", "{owner_id}"),
         "updates": ("change of mind", "with-claude"), "chronology": ("", "")}
ACTS = {"report": "report", "analysis": "interpretation", "plan": "plan", "finding": "finding", "advice": "plan"}


def _keep(kind: str, item: dict) -> bool:
    """A chronology entry is a row when the owner said it, or when it's a clinician's word he passed on; Claude's own analysis
    and advice stay in the summary."""
    if kind != "chronology":
        return True
    rf = item.get("relayed_from") or ""
    me = config.owner_id()
    return item.get("act") in ACTS and (item.get("speaker") == me and rf in ("own", me) or rf.startswith("clinician:"))
SEEDS, SHARE = 10, 0.6  # a passage sits on the story its top 10 hits mostly sit on, and any other within 60% of its vote


def _items(summary: dict, kind: str) -> list[dict]:
    """A section's items; a recurring symptom's course becomes one item per time he felt it, each with its own line."""
    items = summary.get(kind, [])
    if kind != "complaints":
        return items
    return [{"tag": it.get("tag", ""), **c} for it in items for c in (it.get("course") or [it])]


def _text(kind: str, item: dict) -> str:
    if kind == "complaints":
        tag = item.get("tag", "").split("/", 1)[-1].replace("-", " ")
        return f"{tag}: {item.get('intensity', '')}, {item.get('direction', '')}".strip(", ")
    if kind == "updates":
        return f"{item.get('what', '')}: {item.get('before', '')} → {item.get('after', '')}"
    when = item.get("when_said")
    return item.get("text", "") + (f" ({when})" if when else "")


def _date(data: dict, line: int) -> str | None:
    for s in data.get("segments", []):
        if s.get("first_line", 0) <= line <= s.get("last_line", 10**9) and s.get("start"):
            return s["start"][:10]
    return (data.get("first") or "")[:10] or None


def _stories(db, domain: str, kind: str, item: dict, text: str) -> list[str]:
    from engram import search
    if kind == "complaints":
        slug = item.get("tag", "").split("/", 1)[-1]
        from engram.search import repo_conf
        from engram.sources import waysin
        on = [s for (s,) in db.execute("SELECT story FROM on_story WHERE ref = ?", (waysin.page(repo_conf(domain), slug),))]
        if on:
            return on
    votes: dict[str, float] = {}
    for rank, h in enumerate(search.search(text, [domain], limit=SEEDS, surround=False), 1):
        for (s,) in db.execute("SELECT story FROM on_story WHERE ref = ?", (h["ref"].split("@")[0],)):
            votes[s] = votes.get(s, 0) + 1 / rank
    top = max(votes.values(), default=0)
    return sorted(s for s, v in votes.items() if v >= SHARE * top)


def docs_for(domain: str) -> list[Doc]:
    db = open_index(index_path(domain), readonly=True)
    if db is None:
        return []
    indexed = {src.split(":")[1] for (src,) in db.db.execute("SELECT DISTINCT source FROM doc WHERE source LIKE 'sessions:%:summary'")}
    out = []
    for p in sorted((data_path("summaries") / domain).glob("*.json")):
        if p.stem not in indexed:
            continue
        data = json.loads(p.read_text())
        summary = (data.get("stitch") or {}).get("summary") or {}
        for kind, (node, by) in KINDS.items():
            at: dict[int, int] = {}
            for item in _items(summary, kind):
                line, text = item.get("line"), _text(kind, item)
                if not line or not text or not _keep(kind, item):
                    continue
                at[line] = at.get(line, 0) + 1
                if kind == "chronology":
                    node, by = ACTS[item["act"]], item.get("by") or item["relayed_from"]
                quote = item.get("evidence", "")
                stories = _stories(db.db, domain, kind, item, f"{text} {quote}")
                date = _date(data, line)
                out.append(Doc(ref=f"session:{p.stem}:{line}@said-{kind}-{at[line]}", source=SOURCE, cls="said", kind=node,
                               title=f"said in a session › {text}", body=f"{text}\n\n“{quote}”" if quote else text,
                               pointer=f"session:{p.stem}:{line}", author=config.voice(by), date=date,
                               date_key=dates.key(date), node=node, stories=",".join(stories)))
    db.close()
    return out
