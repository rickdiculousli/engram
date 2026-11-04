"""Fixed question sets: does the expected section come up in the top five, asked raw and asked through Claude?"""
import json
import re
import subprocess
import tempfile
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from engram import claude_env, config, search, usage
from engram.paths import data_path, record_toml

PROMPT = """You're testing a search tool over {owner}'s {domain} records. {owner} asked:

"{question}"

Find the record section that answers it. Use only the shell command `engram search --domain {domain} --limit 5 "<query>"`, choosing your own query words; run at most 3 searches. You may run `engram show <ref>` to read a result. Don't read files any other way.

Reply with one line only: the ref of the best result exactly as printed after "ref:", or NONE."""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def matches(expect: str, ref: str) -> bool:
    if "#" not in expect and re.search(r":\d+$", expect):
        return ref == expect or ref.startswith(expect + "@")  # an exchange matches any chunk of it
    ep, _, eh = expect.partition("#")
    if "#" not in ref and not re.search(r"[:@]", ref):  # a whole document (a consult as one row) holds every section of it
        return ref == ep
    rp, _, rh = ref.partition("#")
    if not rh:
        rp = re.sub(r"@\d+$", "", rp)
    if re.search(r":\d+$", rp):
        rp = rp.rsplit(":", 1)[0]
    if rp != ep:
        return False
    if not eh:
        return True
    (eb, ec), (rb, rc) = _chunk(eh), _chunk(rh)
    return _norm(eb) == _norm(rb) and (not ec or not rc or ec == rc)  # a whole section (no chunk) holds every chunk


def _chunk(heading: str) -> tuple[str, str]:
    """Split `Heading~2@1` into the heading and its chunk; an expected ref without a chunk matches every chunk."""
    m = re.match(r"^(.*?)(?:~\d+)?(@\d+)?$", heading, re.S)
    return m.group(1), m.group(2) or ""


def file_of(ref: str) -> str:
    p = ref.partition("#")[0]
    return re.sub(r":\d+$", "", re.sub(r"@\d+$", "", p))


def hit(expect: list[str], refs: list[str]) -> bool:
    """An expected record is among the refs. Callers pass every record a result puts in hand (`result_refs`,
    `timeline_refs`), so any version a unit shows hits the unit."""
    return any(matches(e, r) for e in expect for r in refs)


def result_refs(h: dict, surroundings: bool = True) -> list[str]:
    """The records one search result puts in hand: the record, every version its unit shows (a fact and its corrections
    are one result, docs/technical.md), and its surroundings."""
    return [h["ref"], *(h.get("unit") or {}).get("shown", []), *(n["ref"] for n in h.get("surroundings", []) if surroundings)]


def timeline_refs(rows: list[dict]) -> list[str]:
    """The records a timeline puts in hand: each row's record, the versions shown on it, and the theory rows' records."""
    return [x for r in rows for x in ([r["_ref"]] if "_ref" in r else []) + r.get("_unit", []) + r.get("_refs", [])]


def file_hit(expect: list[str], refs: list[str]) -> bool:
    return any(file_of(e) == file_of(r) for e in expect for r in refs)


# The single-fact measure (the owner; docs/evaluation.md, "The bar"): a lookup passes when the fact is in what
# the advisor has after one move, the `engram now` picture it starts every session with plus the top 5 of one search
# (with their surroundings). Any record that states the fact counts, not only the key's named file.

SOURCE_SECTION = re.compile(r"^(?P<path>[\w./-]+\.(?:md|txt)), (?P<section>.+?)(?: table)? \((?:clean house|migrated)\)$")


def same_records(domain: str) -> dict[str, set[str]]:
    """ref -> the refs code counts as the same record, both ways: an entry and the document section it came from (its
    `ref:` field, its `source:` naming a section of a document still in the record, and the clean house's moved map).
    A whole file and its sections, and a section and its chunks, are already one record to `matches`. A `now` row and
    the entries on its chain aren't paired here: the row counts only where its own line states the fact (`now_rows`)."""
    from engram import config
    from engram.store import Store
    pairs: dict[str, set[str]] = {}

    def pair(a: str, b: str):
        pairs.setdefault(a, set()).add(b)
        pairs.setdefault(b, set()).add(a)
    moved = data_path("moved") / f"{domain}.json"
    if moved.exists():
        for old, new in json.loads(moved.read_text()).items():
            for n in new:
                pair(old, n)
    d = config.load().get(domain)
    if d and d.repo and record_toml(d.repo).exists():
        for e in Store(d.repo).events():
            if e.fm.get("ref"):
                pair(e.id, str(e.fm["ref"]))
            m = SOURCE_SECTION.match(str(e.fm.get("source", "")))
            if m and (d.repo / m["path"]).exists():  # an entry made from a row of a document's table: that section
                pair(e.id, f"{m['path']}#{m['section']}")
    return pairs


def now_rows(domain: str) -> dict[str, tuple[set[str], str]]:
    """`now:<thing>` -> (the entries on its chain, the line the picture prints for it)."""
    from engram import config, now
    d = config.load().get(domain)
    if not (d and d.repo and record_toml(d.repo).exists()):
        return {}
    lines = now.text(d.repo).splitlines()
    out = {}
    for items in now.build(d.repo).values():
        for c in items:
            line = next((l for l in lines if f"[{c.entry}]" in l), "")
            out[f"now:{c.thing}"] = (set(c.chain), line)
    return out


def picture(domain: str) -> tuple[list[str], str]:
    """What `engram now` puts in hand before any search: its rows (each thing, the upcoming visits and plans) and its
    text. The entry id a row prints isn't in hand: only the line is."""
    from engram import config, now
    d = config.load().get(domain)
    if not (d and d.repo and record_toml(d.repo).exists()):
        return [], ""
    refs = [f"now:{c.thing}" for items in now.build(d.repo).values() for c in items]
    refs += [i for _, _, i in now.upcoming(d.repo)]
    return refs, now.text(d.repo)


def in_hand(expect: list[str], refs: list[str], pairs: dict[str, set[str]]) -> bool:
    """An expected record, or one code counts as the same, is among the refs in hand."""
    wide = set(expect)
    for e in expect:
        wide |= pairs.get(e, set())
        if "/" not in e and "#" in e:  # an entry's section: the entry's own equivalents
            wide |= pairs.get(e.partition("#")[0], set())
    return hit(sorted(wide), refs)


DATE_V = re.compile(r"(?<![\w-])(?:\d{4}-\d\d(?:-\d\d)?|\d\d-\d\d)(?![\w])")
NUM_V = re.compile(r"(?<![\w.,/])\d+(?:[.,/]\d+)*(?![\w.,/]*\w)")
WORD_V = re.compile(r"[A-Za-z][\w'’-]*\w|[A-Z]")
NOT_NAMES = {"claude", "i"}  # and the owner


def key_values(point: str) -> list[str]:
    """A point's key values: its dates, its numbers, and its names (a capitalised word not opening a sentence, or a
    word with a capital inside it, like ZMC or FluXor). The owner and Claude are who said it, not the fact."""
    out = DATE_V.findall(point)
    rest = DATE_V.sub(" ", point)
    out += NUM_V.findall(rest)
    for m in WORD_V.finditer(rest):
        w = re.sub(r"['’]s$", "", m.group(0))
        before = rest[:m.start()].rstrip()
        opens = not before or before[-1] in ".:;!?(\"'“‘—"
        inner = any(c.isupper() for c in w[1:])
        if w.lower() not in NOT_NAMES | {config.owner_id()} and not w.endswith(".md") and (inner or (w[0].isupper() and not opens)):
            out.append(w)
    return list(dict.fromkeys(out))


def states(text: str, value: str) -> bool:
    """A record's text holds a key value: a name as a whole word in any case; a number or date not inside a longer
    one (10 is in "10mg", not in "100" or "2.10")."""
    if value[0].isdigit():
        return bool(re.search(r"(?<![\d.,/])" + re.escape(value) + r"(?![\d]|[.,/]\d)", text))
    return bool(re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text, re.I))


def strong(value: str) -> bool:
    """A key value that can pin a fact on its own: a date, a name, or a number of two digits or more."""
    return not value.isdigit() or len(value) > 1


def points_in_hand(q: dict, texts: list[str]) -> bool:
    """Where code can't settle it: every point of the key (its `why` when it has no points) that has a strong key value
    has all its key values in one record's text; a key with no such point can't pass this way."""
    valued = [v for v in (key_values(p) for p in q.get("points") or [q.get("why", "")]) if any(map(strong, v))]
    return bool(valued) and all(any(all(states(t, v) for v in vals) for t in texts) for vals in valued)


def hand(domain: str, question: str, pic: tuple[list[str], str] | None = None,
         surroundings: bool = True) -> tuple[list[str], list[str]]:
    """The refs and texts in hand after one move: the `now` picture plus the top 5 of the question as the search, with
    their surroundings unless left out. A hit's text is its whole record (a unit's: its current version); its other
    versions and its surroundings show only their lines."""
    from engram.index import open_index
    from engram.paths import index_path
    refs, now_text = pic if pic is not None else picture(domain)
    refs, texts = list(refs), [line for line in now_text.splitlines() if line.strip()]  # each row of the picture is its own record
    hits = search.search(question, [domain], limit=5)
    idx = open_index(index_path(domain), readonly=True)
    try:
        for h in hits:
            refs += result_refs(h, surroundings)
            rows = idx.db.execute("SELECT title, body FROM doc WHERE ref = ? OR parent = ? OR (? NOT LIKE '%#%' AND ref LIKE ? || '#%')",
                                  (h["ref"], h["ref"], h["ref"], h["ref"])).fetchall() if idx else []
            texts.append("\n".join(f"{t}\n{b}" for t, b in rows) or h.get("title", ""))
            texts += [*(h.get("unit") or {}).get("text", []), *(n.get("title", "") for n in h.get("surroundings", []) if surroundings)]
    finally:
        if idx:
            idx.close()
    return refs, texts


def fact_in_hand(q: dict, refs: list[str], texts: list[str], pairs: dict[str, set[str]],
                 rows: dict[str, tuple[set[str], str]] | None = None) -> str:
    """How a lookup passes the 2026-10-22 measure: "record" (code settled it), "picture" (a `now` row whose chain holds
    an expected entry, and whose own line states the key's values), "points" (the key's values anywhere), or ""."""
    if in_hand(q.get("expect", []), refs, pairs):
        return "record"
    wide = set(q.get("expect", []))
    for e in list(wide):
        wide |= pairs.get(e, set()) | pairs.get(e.partition("#")[0], set())
    for ref in refs:
        chain, line = (rows or {}).get(ref, (set(), ""))
        if chain & wide and points_in_hand(q, [line]):
            return "picture"
    return "points" if points_in_hand(q, texts) else ""


def live(qs: list[dict]) -> list[dict]:
    """The questions every measure asks: a question marked `dropped` (with the owner's reason) is skipped."""
    return [q for q in qs if not q.get("dropped")]


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def run_direct(qs: list[dict], domain: str) -> list[dict]:
    """The owner's question as the query, top 5. A lookup also reports the single-fact measure (`in_hand`)."""
    out, pairs, pic = [], None, None
    for q in qs:
        hits = search.search(q["question"], [domain], limit=5)
        refs = [x for r in hits for x in result_refs(r, surroundings=False)]
        row = {"id": q["id"], "hit": hit(q["expect"], refs), "file_hit": file_hit(q["expect"], refs), "top": refs}
        if q.get("kind", "lookup") == "lookup":
            if pairs is None:
                pairs, pic, rows = same_records(domain), picture(domain), now_rows(domain)
            row["in_hand"] = fact_in_hand(q, *hand(domain, q["question"], pic), pairs, rows)
        out.append(row)
    return out


def run_replay(qs: list[dict], domain: str, prior: Path, lens: str | None = None) -> list[dict]:
    """Rerun the queries Claude wrote in an earlier run, so an engine change is measured without Claude's variance.
    Each query keeps the lens Claude gave it, unless `lens` names one for every query, is `none`, or is `auto`: the
    lens whose `kinds` lists the question's kind. A hit's surroundings count, as in answer mode."""
    prior_rows = {r["id"]: r for r in json.loads(prior.read_text())["rows"] if not r.get("error")}
    by_kind = {k: name for name, l in search.lenses(domain).items() for k in l.get("kinds", [])}
    out = []
    for q in qs:
        r = prior_rows.get(q["id"], {})
        queries = r.get("queries", [])
        refs, chars = [], 0
        for qq, logged in zip(queries, r.get("lenses") or [None] * len(queries)):
            use = by_kind.get(q.get("kind", "lookup")) if lens == "auto" else None if lens == "none" else lens or logged
            hits = search.search(qq, [domain], limit=5, lens=use)
            chars += len(search.render(hits))
            for h in hits:
                refs += result_refs(h)
        links = links_found(q, refs)
        out.append({"id": q["id"], "stories": q.get("stories", []), "kind": q.get("kind", "lookup"), "queries": queries,
                    "hit": hit(q["expect"], refs), "file_hit": file_hit(q["expect"], refs), "links": links,
                    "found": all(links) if links else hit(q["expect"], refs), "chars": chars})
    return out


def _agent_one(q: dict, domain: str, tag: str, model: str | None) -> dict:
    env = claude_env.clean(ENGRAM_TAG=tag, ENGRAM_EXCLUDE_SOURCES=own_source(q))
    text, err, _ = _claude(config.voice(PROMPT).format(domain=domain, question=q["question"]), env, model,
                        ["Bash(engram search:*)", "Bash(engram show:*)"])
    if err:
        return _unrun(q, err)
    answer = text.splitlines()[-1].strip() if text else ""
    if answer.startswith("ref:"):
        answer = answer[4:].strip()
    runs = usage.searches(domain, tag)
    refs = [res["ref"] for s in runs for res in s["results"] if res["rank"] <= 5]
    return {"id": q["id"], "queries": [s["query"] for s in runs], "hit": hit(q["expect"], refs),
            "file_hit": file_hit(q["expect"], refs), "answer": answer,
            "answer_hit": bool(answer) and hit(q["expect"], [answer])}


def run_agent(qs: list[dict], domain: str, workers: int = 4, model: str | None = None) -> list[dict]:
    run = datetime.now().strftime("%Y%m%d%H%M%S")
    return _pool(lambda q: _agent_one(q, domain, f"eval-{run}-{q['id']}", model), qs, workers)


def _unrun(q: dict, error: str) -> dict:
    """A question Claude couldn't be asked (a usage limit, most often). It counts toward no rate, and a resumed run asks it again."""
    return {"id": q["id"], "stories": q.get("stories", []), "kind": q.get("kind", "lookup"), "error": error}


def _pool(one, qs: list[dict], workers: int) -> list[dict]:
    """Ask each question; after the first failed call to Claude, the questions not yet started are left unrun rather than failed."""
    stop = threading.Event()

    def guarded(q):
        if stop.is_set():
            return _unrun(q, "not run: an earlier call to Claude failed")
        row = one(q)
        if row.get("error"):
            stop.set()
        return row

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(guarded, qs))


def resume(qs: list[dict], prior: Path) -> tuple[list[dict], list[dict]]:
    """The rows an earlier run got answers for, and the questions it left unrun or never reached."""
    done = [r for r in json.loads(prior.read_text())["rows"] if not r.get("error")]
    have = {r["id"] for r in done}
    return done, [q for q in qs if q["id"] not in have]


CHAIN = {"through-line", "crossing", "revision", "whole-picture"}

ANSWER_PROMPT = """{owner} asked, about their {domain} records:

"{question}"

Answer them from their records. Use only the shell commands `engram search --domain {domain} --limit 5 "<query>"` (your own query words; at most {cap} searches) and `engram show <ref>`. Don't read files any other way.
{lenses}{timelines}
How answers must read:
- Lead with the arc, not a list of every day-to-day report.
- After each claim, say who it came from (a clinician by name and role, {owner} themselves, an analysis they worked out with Claude, or a Claude suggestion they're considering), as the record says it, and cite the record's id or full ref in [brackets], copied exactly as engram printed it, never shortened or paraphrased.
- Quote doses, test numbers, dates and clinicians' words from the record; put only exact words in quotation marks.
- If the record disagrees with itself, give each version with its date and source.
- Keep approximate or remembered dates as approximate, in the record's words; never sharpen them.
- If something isn't recorded, say so."""

GRADE_PROMPT = """You grade an answer against a written key. You can't see the records; judge only against the key.

Question: {question}
Kind: {kind}
Marks: {marks}

Key, the points a correct answer must make{ordered}:
{points}

The answer:
<<<
{answer}
>>>

Fail the answer if any of these hold: it misses or contradicts a key point; it gets the order or the cause and effect wrong where the key gives them; it guesses a step the key doesn't support; it buries the arc under day-to-day detail; it turns an approximate date into a precise one; it picks one side of a conflict the key says to show; it claims something the key says isn't recorded.

Reply with JSON only:
{{"pass": true|false, "points": [{{"point": 1, "met": true|false, "note": "..."}}], "problems": ["..."]}}"""


def links_found(q: dict, refs: list[str]) -> list[bool]:
    return [hit(link["refs"], refs) for link in q.get("links", [])]


EFFORT = "medium"  # the owner's own default, never the calling session's


def _claude(prompt: str, env: dict, model: str | None, tools: list[str], cwd: Path | None = None) -> tuple[str, str, dict]:
    """Claude's reply, or an error when the call failed instead of answering; and what the call cost and read:
    `tokens` processed in all (each turn rereads its context), `context` at its largest and `base` at the first turn
    (the fixed part: system prompt, tools, the repo's instructions), the files it Read, and Grep's matching lines."""
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--permission-mode", "dontAsk", "--effort", EFFORT]
    if tools:
        cmd += ["--allowedTools", *tools]
    if model:
        cmd += ["--model", model]
    try:
        with tempfile.TemporaryDirectory(prefix="engram-eval-") as tmp:
            r = subprocess.run(cmd, cwd=cwd or tmp, env=env, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return "", "timed out", {}
    info, final, grep_ids = {"reads": [], "greps": [], "contexts": []}, None, set()
    for line in r.stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant":
            u = e["message"].get("usage") or {}
            info["contexts"].append(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
            for b in e["message"].get("content") or []:
                if b.get("type") == "tool_use" and b.get("name") == "Read":
                    info["reads"].append(b["input"].get("file_path", ""))
                if b.get("type") == "tool_use" and b.get("name") == "Grep" and b["input"].get("output_mode") == "content":
                    grep_ids.add(b.get("id"))
        elif e.get("type") == "user":
            for b in e["message"].get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in grep_ids:
                    c = b.get("content")
                    info["greps"].append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict)))
        elif e.get("type") == "result":
            final = e
    if final is None:
        return "", (r.stderr or r.stdout).strip()[:300] or f"exit {r.returncode}", {}
    u = final.get("usage") or {}
    ctx = info.pop("contexts")
    info.update(tokens=sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")),
                context=max(ctx, default=0), base=ctx[0] if ctx else 0)
    text = (final.get("result") or "").strip()
    if r.returncode or final.get("is_error"):
        return "", text[:300] or f"exit {r.returncode}", info
    return text, "", info


def _grade(q: dict, answer: str, env: dict, model: str) -> dict:
    points = q.get("points") or [q.get("why", "")]
    prompt = GRADE_PROMPT.format(question=q["question"], kind=q.get("kind", "lookup"), marks=", ".join(q.get("marks", [])) or "none",
                                 ordered=" (in order)" if q.get("kind") in CHAIN else "",
                                 points="\n".join(f"{i}. {p}" for i, p in enumerate(points, 1)), answer=answer or "(no answer)")
    text, err, _ = _claude(prompt, env, model, [])
    if err:
        return {"pass": False, "error": err}
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {"pass": False, "problems": ["grader gave no JSON"]}
    except json.JSONDecodeError:
        return {"pass": False, "problems": ["grader gave bad JSON"]}


def lens_lines(domain: str) -> str:
    """The prompt's paragraph on lenses, from the domain's config; empty for a domain with none, so a record built
    before lenses is asked exactly as before."""
    ls = search.lenses(domain)
    if not ls:
        return ""
    default = search.repo_conf(domain).get("weights", {}).get("about")
    return ("\nA search can add `--lens <name>`, which puts one kind of record first" + (f"; without one, {default}" if default else "")
            + ". Pick the lens that fits what that search looks for:\n"
            + "\n".join(f"- `{name}`, for {l.get('for', '')}: {l.get('about', '')}" for name, l in ls.items()) + "\n")


def timeline_lines(domain: str) -> str:
    """The prompt's paragraph on timelines; empty for a record without them, so it's asked as before."""
    from engram import timeline
    if not timeline.names(domain)["stories"]:
        return ""
    return (f"\nFor a single fact (a dose, a date, a result, who said something), search: it's cheaper. "
            f"For a question about how something went, or to set the frame around a complaint, `engram timeline --domain {domain} "
            f"<the question in your words>` prints, in one call, the whole chains it bears on merged into one timeline in time "
            f"order: one record per row with its ref, the complaints each row is on, and which rows it follows on (branches and "
            f"joins). Naming stories or recurring symptoms instead (`engram timeline --domain {domain} neck eyes`) merges just those, and "
            f"naming a treatment, clinician, test or theory node gives its history; `engram timeline --domain {domain}` lists them all. Timelines don't count against the search limit. Read the timeline, "
            f"then open what you need with `engram show <ref>`.\n")


def own_source(q: dict) -> str:
    """The session a session-origin question was taken from, as a source prefix to hide from its own run."""
    if q.get("origin") != "session" or not q.get("source"):
        return ""
    return "sessions:" + q["source"].split()[0]


def _answer_one(q: dict, domain: str, tag: str, model: str | None, grader: str | None) -> dict:
    env = claude_env.clean(ENGRAM_TAG=tag, ENGRAM_EXCLUDE_SOURCES=own_source(q))
    cap = 6 if q.get("kind") in CHAIN else 3
    answer, err, info = _claude(config.voice(ANSWER_PROMPT).format(domain=domain, question=q["question"], cap=cap, lenses=lens_lines(domain),
                                                     timelines=timeline_lines(domain)), env, model,
                                ["Bash(engram search:*)", "Bash(engram show:*)", "Bash(engram timeline:*)"])
    if err:
        return _unrun(q, err)
    runs = usage.searches(domain, tag)
    refs = [res["ref"] for s in runs for res in s["results"] if res["rank"] <= 5]
    links = links_found(q, refs)
    found = all(links) if links else hit(q["expect"], refs)
    # a diagnostic beside the bar: links reached by opening what a page or a hit pointed to, not only in a top 5
    reached = links_found(q, refs + usage.opens(domain, tag)) if q.get("links") else [hit(q["expect"], refs + usage.opens(domain, tag))]
    row = {"id": q["id"], "stories": q.get("stories", []), "kind": q.get("kind", "lookup"), "queries": [s["query"] for s in runs],
           "lenses": [s.get("lens") for s in runs], "hit": hit(q["expect"], refs), "file_hit": file_hit(q["expect"], refs),
           "links": links, "found": found, "reached": all(reached), "pass": found, "answer": answer, **_cost(info)}
    if grader:  # a diagnostic: how Claude wrote the answer isn't engram's gate (docs/evaluation.md, "The bar")
        grade = _grade(q, answer, claude_env.clean(), grader)
        if grade.get("error"):
            return _unrun(q, "grader: " + grade["error"])
        row.update(graded=bool(grade.get("pass")), grade=grade)
    return row


def _cost(info: dict) -> dict:
    """What answering cost: tokens processed, the largest context, and what retrieval added to the fixed first turn."""
    return {"tokens": info.get("tokens", 0), "context": info.get("context", 0), "retrieved": info.get("context", 0) - info.get("base", 0)}


def run_answer(qs: list[dict], domain: str, workers: int = 4, model: str | None = None, grader: str | None = None) -> list[dict]:
    """Claude answers in full; a question passes when every link (or, for a lookup, an answering ref) was in a top 5.
    With a grader, an independent model also checks the answer against the key, as a diagnostic."""
    run = datetime.now().strftime("%Y%m%d%H%M%S")
    return _pool(lambda q: _answer_one(q, domain, f"eval-{run}-{q['id']}", model, grader), qs, workers)


GREP_PROMPT = """{owner} asked, about their {domain} records:

"{question}"

Answer them from their records, the files in this folder. Use only the Read, Grep and Glob tools and your skills; don't look anywhere else.

How answers must read:""" + ANSWER_PROMPT.split("How answers must read:", 1)[1]


def _grep_one(q: dict, domain: str, repo: Path, model: str | None) -> dict:
    env = claude_env.clean()
    answer, err, info = _claude(config.voice(GREP_PROMPT).format(domain=domain, question=q["question"]), env, model,
                                ["Read", "Grep", "Glob", "Skill"], cwd=repo)
    if err:
        return _unrun(q, err)
    root = str(repo.resolve()) + "/"
    read = {p.removeprefix(root).removeprefix(str(repo) + "/") for p in info.get("reads", [])}
    grepped = {line.split(":", 1)[0].removeprefix(root) for out in info.get("greps", []) for line in out.splitlines() if ":" in line}
    seen = read | grepped
    names = {Path(f).stem for f in seen}  # an entry is named by its id, the stem of its file

    def reached(refs):  # a link counts when its file was read, or a matching line from it was printed
        return any(re.split(r"[#:]", r, maxsplit=1)[0] in seen or r in names for r in refs)
    links = [reached(l["refs"]) for l in q.get("links", [])]
    return {"id": q["id"], "stories": q.get("stories", []), "kind": q.get("kind", "lookup"), "links": links,
            "found": all(links) if links else reached(q["expect"]), "hit": reached(q["expect"]), "file_hit": reached(q["expect"]),
            "pass": all(links) if links else reached(q["expect"]),
            "reads": sorted(read), "grepped": sorted(grepped), "answer": answer, **_cost(info)}


def run_grep(qs: list[dict], domain: str, repo: Path, workers: int = 4, model: str | None = None) -> list[dict]:
    """The original approach, for comparison: Claude answers by grepping and reading a copy of the record as it was,
    with the repo's own instructions. A link counts as reached when its file was read or grepped (file level, so more
    generous than engram's top 5); the point is the tokens it took."""
    return _pool(lambda q: _grep_one(q, domain, repo, model), qs, workers)


def by_group(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        for g in (r[key] if isinstance(r[key], list) else [r[key]]):
            groups.setdefault(g, []).append(r)
    return {g: {"n": len(rs), "pass": sum(r.get("pass", 0) for r in rs), "found": sum(r["found"] for r in rs),
                "graded": sum(r.get("graded", 0) for r in rs), "links": sum(sum(r.get("links", [])) for r in rs),
                "of": sum(len(r.get("links", [])) for r in rs)} for g, rs in sorted(groups.items())}


def seal(qs: list[dict], seed: str, together: list[list[str]] = (), by_kind: bool = True) -> tuple[list[dict], list[dict]]:
    """Split a frozen set into tuning and held-out: a third of each story, spread over its kinds, chosen by a seeded hash
    so the split is reproducible without anyone picking. A question goes with its first story; roll-ups stay in tuning.
    Questions in a `together` group share an answer, so they land on the side of the group's first member. By default a
    third of each story and kind is held; with `by_kind` off, a third of each story, taken in kind order,
    for a set whose stories hold one or two questions of a kind, where the default would hold almost none."""
    import hashlib
    groups: dict[tuple, list[dict]] = {}
    for q in qs:
        stories = q.get("stories", [])
        if not stories or len(stories) >= 5:  # five or more stories is a roll-up
            groups.setdefault(("", ""), []).append(q)
            continue
        groups.setdefault((stories[0], q.get("kind", "lookup") if by_kind else ""), []).append(q)
    held = set()
    for key, group in groups.items():
        if key == ("", ""):
            continue
        order = sorted(group, key=lambda q: (q.get("kind", "lookup"), hashlib.sha256(f"{seed}:{q['id']}".encode()).hexdigest()))
        held.update(q["id"] for i, q in enumerate(order) if i % 3 == 1)
    for group in together:
        side = group[0] in held
        held.difference_update(group)
        if side:
            held.update(group)
    return [q for q in qs if q["id"] not in held], [q for q in qs if q["id"] in held]


def summarize(rows: list[dict]) -> dict:
    """Rates over the questions that were asked; unrun ones are counted apart and never scored as misses."""
    unrun = [r["id"] for r in rows if r.get("error")]
    rows = [r for r in rows if not r.get("error")]
    n = len(rows) or 1
    s = {"n": len(rows), "unrun": len(unrun), "recall_at_5": round(sum(r["hit"] for r in rows) / n, 3),
         "file_recall_at_5": round(sum(r["file_hit"] for r in rows) / n, 3)}
    if any("in_hand" in r for r in rows):
        looked = [r for r in rows if "in_hand" in r]
        s["facts_in_hand"] = f"{sum(bool(r['in_hand']) for r in looked)}/{len(looked)}"
    if rows and "held" in rows[0]:  # the same-record rule, on: the owner's own questions and those that need more apart
        main = [r for r in rows if not r.get("needs")]
        s.update(held_summary(main))
        s["owners"] = held_summary([r for r in main if r["owners"]])
        needs: dict[str, list[dict]] = {}
        for r in rows:
            if r.get("needs"):
                needs.setdefault(r["needs"], []).append(r)
        if needs:
            s["needs"] = {k: held_summary(v) for k, v in sorted(needs.items())}
    if rows and "answer_hit" in rows[0]:
        s["answer_accuracy"] = round(sum(r["answer_hit"] for r in rows) / n, 3)
        s["searches_per_question"] = round(sum(len(r.get("queries", [])) for r in rows) / n, 2)
    if rows and "found" in rows[0]:
        s["found_rate"] = round(sum(r["found"] for r in rows) / n, 3)
        s["links_found"] = f"{sum(sum(r['links']) for r in rows)}/{sum(len(r['links']) for r in rows)}"
        s["by_kind"] = by_group(rows, "kind")
    if rows and "chars" in rows[0]:  # replay: what the searches printed, about 4 characters a token
        s["search_chars_median"] = sorted(r["chars"] for r in rows)[len(rows) // 2]
    if rows and "tokens" in rows[0]:
        for k in ("tokens", "context", "retrieved"):
            v = sorted(r.get(k, 0) for r in rows)
            s[f"{k}_median"] = v[len(v) // 2]
    if rows and "pass" in rows[0]:
        s["pass_rate"] = round(sum(r["pass"] for r in rows) / n, 3)
        s["found_rate"] = round(sum(r["found"] for r in rows) / n, 3)
        if "graded" in rows[0]:
            s["graded_rate"] = round(sum(r.get("graded", False) for r in rows) / n, 3)
        if "reached" in rows[0]:
            s["reached_rate"] = round(sum(r["reached"] for r in rows) / n, 3)
        s["searches_per_question"] = round(sum(len(r.get("queries", [])) for r in rows) / n, 2)
        s["by_kind"] = by_group(rows, "kind")
        s["by_story"] = by_group(rows, "stories")
    return s


def held_summary(rows: list[dict]) -> dict:
    """The same-record rule's counts: refs held and questions passed three ways (a lookup by `in_hand`, any other
    question by every ref held), each call's precision on average, and owners shown on the key records in hand."""
    s = {"questions": len(rows)}
    for k in ("", "_strict", "_top5"):
        s[f"refs_held{k}"] = f"{sum(sum(r['held' + k]) for r in rows)}/{sum(len(r['held' + k]) for r in rows)}"
        s[f"passes{k}"] = f"{sum(bool(r['in_hand' + k]) if 'in_hand' in r else all(r['held' + k]) for r in rows)}/{len(rows)}"
    p = [r["precision"] for r in rows if r["precision"] is not None]
    s["precision"] = round(sum(p) / len(p), 3) if p else None
    if owned := [r["owner"] for r in rows if "owner" in r]:
        s["owner_shown"] = f"{sum(a for a, _ in owned)}/{sum(b for _, b in owned)}"
    return s


def save(domain: str, mode: str, rows: list[dict]) -> Path:
    d = data_path("eval") / "results"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{domain}-{mode}-{datetime.now():%Y%m%d-%H%M%S}.json"
    p.write_text(json.dumps({"rows": rows}, indent=1))  # the answers first: a run can't be rerun for free
    p.write_text(json.dumps({"summary": summarize(rows), "rows": rows}, indent=1))
    return p
