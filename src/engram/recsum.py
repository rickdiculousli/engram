"""Two- or three-line summaries of long records, for the timeline's milestones and direct matches (.engram/README.md:
summaries for milestones and direct matches; every other record is a headline, and the full text is one call away).

Opus at low effort reads about 20 records per call. Each summary sentence comes with a quote copied from the record,
and code checks it: the quote must be in the record word for word, every number in the sentence must be in the record,
and a sentence fails if it's over 40 words. A failing sentence is dropped, never kept. Summaries are cached by the
record's text, so an unchanged record isn't summarized twice; the cache lives in the data folder, never in a repo."""
import hashlib
import json
import re
import subprocess
import tempfile

from engram import claude_env, config, dates, pack
from engram.index import open_index
from engram.paths import data_path, index_path

MODEL, EFFORT, BATCH = "claude-opus-5-5", "low", 20
LONG = 600  # characters; a shorter record is cheaper to open whole than to summarize
SYSTEM = "You summarize sections of a person's record for a reader who will open the full record when needed."  # unless
# the domain's pack says what kind of record (`recsum_system`)
PROMPT = """Summarize each record below in one to three short sentences: what happened or what it says, and what came of it.

Rules:
- Use only what the record says. No outside knowledge, no guesses, no advice.
- Keep who said it when the record says (a clinician, {owner}, an analysis worked out with Claude).
- Every number, dose, date or test value you mention must appear in the record exactly as written.
- After each sentence, give a quote: a short phrase (at most 15 words) copied exactly from the record that supports it.
- At most 40 words per sentence.

Reply with JSON only: {{"summaries": [{{"id": "<id>", "sentences": [{{"text": "...", "quote": "..."}}]}}]}}

{records}"""


DASHES = re.compile(r"\s*[-\u2010-\u2015\u2212]\s*")
BROKEN = re.compile(r"(\w)[-\u00ad]\s*\n\s*(\w)")  # a word hyphenated across a line


def _norm(s: str) -> str:
    """Text as a quote is matched: curly quotes straight, a word hyphenated across lines joined, every dash one hyphen
    with no spaces round it, an ellipsis three dots, soft hyphens gone, spaces collapsed, lower case."""
    s = BROKEN.sub(r"\1\2", s.replace("\u00ad", "")).replace("…", "...")
    s = DASHES.sub("-", s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))
    return re.sub(r"\s+", " ", s).strip().lower()


def check(sentence: dict, body: str) -> str | None:
    """Why a summary sentence fails, or None."""
    text, quote = sentence.get("text", ""), sentence.get("quote", "")
    if not text or not quote:
        return "missing text or quote"
    if _norm(quote) not in _norm(body):
        return "quote not in the record"
    if len(text.split()) > 40:
        return "over 40 words"
    have = dates.numbers(body)
    for n in dates.NUMBER.findall(text):
        if n not in have:
            return f"number {n} not in the record"
    return None


def _cache(domain: str):
    d = data_path("record-summaries") / domain
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def wanted(domain: str) -> list[tuple[str, str, str]]:
    """(ref, title, body) for every record long enough to summarize, whole sections with their chunks joined."""
    idx = open_index(index_path(domain), readonly=True)
    if idx is None:  # an area not indexed yet has no records to summarize
        return []
    out = []
    for (ref,) in idx.db.execute("SELECT DISTINCT coalesce(parent, ref) FROM doc WHERE source IN ('repo-sections', 'events')"):
        row = idx.get(ref) or idx.section(ref)
        if row and len(row["body"]) > LONG:
            out.append((ref, row["title"], row["body"]))
    idx.close()
    return out


def _ask(prompt: str, system: str = SYSTEM) -> tuple[str, dict]:
    cmd = ["claude", "-p", "--model", MODEL, "--effort", EFFORT, "--output-format", "json", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--tools", "", "--system-prompt", system]
    with tempfile.TemporaryDirectory(prefix="engram-recsum-") as cwd:
        r = subprocess.run(cmd, input=prompt, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=1800)
    out = json.loads(r.stdout)
    if r.returncode or out.get("is_error"):
        raise RuntimeError(str(out.get("result") or f"exit {r.returncode}")[:300])
    u = out.get("usage") or {}
    return out.get("result") or "", {"in": sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                                     "out": u.get("output_tokens", 0), "usd": out.get("total_cost_usd", 0)}


def run(domain: str, limit: int | None = None) -> dict:
    """Summarize the long records not yet cached, up to `limit`; returns counts, failures and usage."""
    cache = _cache(domain)
    system = pack.load(domain).prompts.get("recsum_system") or SYSTEM
    todo = [w for w in wanted(domain) if not (cache / f"{_key(w[2])}.json").exists()][:limit]
    stats = {"records": len(todo), "kept": 0, "sentences": 0, "dropped": {}, "in": 0, "out": 0, "usd": 0.0}
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        records = "\n\n".join(f"<record id=\"{n}\">\n{title}\n\n{body}\n</record>" for n, (_, title, body) in enumerate(batch))
        reply, used = _ask(config.voice(PROMPT).format(records=records), system)
        for k in ("in", "out", "usd"):
            stats[k] += used[k]
        m = re.search(r"\{.*\}", reply, re.S)
        got = {str(s.get("id")): s.get("sentences", []) for s in (json.loads(m.group(0)).get("summaries", []) if m else [])}
        for n, (ref, _, body) in enumerate(batch):
            keep = []
            for s in got.get(str(n), []):
                why = check(s, body)
                stats["sentences"] += 1
                if why:
                    why = "number not in the record" if why.startswith("number") else why
                    stats["dropped"][why] = stats["dropped"].get(why, 0) + 1
                else:
                    keep.append(s["text"].strip())
            (cache / f"{_key(body)}.json").write_text(json.dumps({"ref": ref, "summary": " ".join(keep)}))
            stats["kept"] += bool(keep)
    return stats


def keep(domain: str, ref: str, body: str, summary: str):
    """A summary written elsewhere (a source's, by the compiler), cached by its record's text as this module's are."""
    (_cache(domain) / f"{_key(body)}.json").write_text(json.dumps({"ref": ref, "summary": summary}))


def cached(domain: str, body: str) -> str:
    """The cached summary of a record's text, or ""."""
    p = _cache(domain) / f"{_key(body)}.json"
    return json.loads(p.read_text()).get("summary", "") if p.exists() else ""


def summaries(domain: str) -> dict[str, str]:
    """ref -> summary for every cached record whose text hasn't changed since."""
    cache = _cache(domain)
    out = {}
    for ref, _, body in wanted(domain):
        p = cache / f"{_key(body)}.json"
        if p.exists() and (s := json.loads(p.read_text()).get("summary")):
            out[ref] = s
    return out


def sync(idx, domain: str) -> int:
    """Copy the cached summaries of unchanged records into the index, for the timeline to print."""
    have = summaries(domain)
    with idx.db:
        idx.db.execute("CREATE TABLE IF NOT EXISTS rec_summary (ref TEXT PRIMARY KEY, summary TEXT NOT NULL)")
        idx.db.execute("DELETE FROM rec_summary")
        idx.db.executemany("INSERT INTO rec_summary (ref, summary) VALUES (?, ?)", have.items())
    return len(have)
