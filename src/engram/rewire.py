"""Rewiring's deterministic steps (docs/shape.md, "Rewiring a repo"): the owner's words from their sessions, the facts of
a repo, and the checks on what a model proposes from them. Judgment stays with the model that runs the rewire skill;
whatever it could get wrong silently is checked here."""
import hashlib
import json
import re
import subprocess
import tomllib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from engram import config, dates, pack
from engram.paths import PAGE, RECORD_TOML, record_toml
from engram.sources import sessions
from engram.sources.sections import FENCE, HEADING

PASTE = re.compile(r"<pasted_content[^>]*>(.*?)</pasted_content>", re.S)
THIN_MESSAGES, THIN_DAYS = 40, 14  # fewer, or a shorter span, and the interview opens with one open question


def roots() -> list[Path]:
    """Every folder of Claude Code sessions this box keeps: `[sessions] roots` in config (a mirror among them), else
    Claude Code's own."""
    return [Path(r).expanduser() for r in config.raw().get("sessions", {}).get("roots", [])] or [sessions.ROOT]


def _when(t: str) -> datetime:
    d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    return d if d.tzinfo else d.astimezone()


def turns(repo: Path | None, before: str | None = None, from_roots: list[Path] | None = None,
          also: tuple[str, ...] = ()) -> dict:
    """What the owner typed in the sessions started in a repo, or in every session when it's None, plus the sessions
    whose ids start with one of `also` (a jobs interview held elsewhere, for a repo with few sessions of its own): no
    injected text, subagent, compaction summary or session an agent started (`sessions.by_agent`), and nothing from a
    harness's folders (`sessions_from`). Pastes collapse to their size; a message seen twice (in a mirror and its
    source) counts once."""
    harness = [m for d in config.load().values() for m in d.sessions_from]
    cut = _when(before) if before else None
    seen, out, sessions_used = set(), [], set()
    for root in from_roots or roots():
        for p in sorted(root.rglob("*.jsonl")):
            rel = str(p.relative_to(root))
            if "subagents" in Path(rel).parts or any(m in rel for m in sessions.SKIP_PROJECTS):
                continue
            s = sessions.parse(p, root)
            asked = any(s.stem.startswith(x) for x in also)
            if sessions.by_agent(s) or (repo and not sessions.started_in(s, repo) and not asked) \
                    or any(m in s.project or m in s.cwd for m in harness):
                continue
            for e in s.exchanges:
                if e.meta or e.summary or not e.ts or (cut and _when(e.ts) >= cut):
                    continue
                text = PASTE.sub(lambda m: f"[paste, {len(m.group(1))} chars]", e.asked).strip()
                key = e.uuid or f"{e.ts} {text}"
                if not text or key in seen:
                    continue
                seen.add(key)
                sessions_used.add(s.stem)
                out.append({"ts": e.ts, "session": s.stem[:8], "brief": sessions.brief(text), "text": text})
    out.sort(key=lambda m: m["ts"])
    days = (_when(out[-1]["ts"]) - _when(out[0]["ts"])).days if out else 0
    return {"repo": str(repo or ""), "before": before, "messages": len(out), "briefs": sum(m["brief"] for m in out),
            "sessions": len(sessions_used), "first": out[0]["ts"] if out else None, "last": out[-1]["ts"] if out else None,
            "days": days, "thin": len(out) < THIN_MESSAGES or days < THIN_DAYS, "turns": out}


def write_turns(t: dict, path: Path) -> Path:
    """turns.md: a header of counts and span, then each message under `### <time> <session>`, a brief marked."""
    head = (f"# The owner's words: {t['repo']}\n\n{t['messages']} messages in {t['sessions']} sessions, "
            f"{t['first'] or '-'} to {t['last'] or '-'} ({t['days']} days)"
            + (f", before {t['before']}" if t["before"] else "") + f"; {t['briefs']} marked as briefs, never quoted."
            + ("\nThin: the interview opens with one open question, not a draft." if t["thin"] else "") + "\n")
    body = "".join(f"\n### {m['ts'][:16]} {m['session']}{' brief' if m['brief'] else ''}\n{m['text']}\n" for m in t["turns"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + body)
    return path


# The repo analysis: its natural units, its names, where one update is written in several places, and what's stale.
# Records write dates three ways: 2026-08-27, 08-27 (year implied) and Aug 27; all three are read as written.
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
PARTIAL = re.compile(rf"(?<![\d-])(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?![\d-])|\b({'|'.join(MONTHS)})[a-z]*\.? (\d{{1,2}})\b", re.I)
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
FIELD = re.compile(r"^([\w-]+):\s*(.+)$")
# A name is a capitalised word or a code in mid-sentence; a word that starts a line or a sentence says nothing.
NAME = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*\b")
NOT_NAMES = {m for m in MONTHS} | {"sept", "mon", "tue", "wed", "thu", "fri", "sat", "sun", "monday", "tuesday",
                                   "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
                                   "march", "april", "june", "july", "august", "september", "october", "november", "december"}
NOISE = re.compile(r"`[^`]*`|\]\([^)]*\)|https?://\S+")
COPY_FILES = 3  # one name and one date in this many files is one update written in several places
AS_OF = re.compile(r"^(as[_-]?of|updated|last[_-]updated|reviewed|last[_-]reviewed)$", re.I)
CLOSED = {"dropped", "closed", "archived", "retired", "superseded", "done", "resolved", "exited", "sold", "dead"}
APPEND = 0.1  # a file whose history deletes at most this share of what it adds is written by appending


def date_of(text: str) -> str | None:
    """The first date in a line, as written."""
    return dates.first_in(text) or (m.group(0) if (m := PARTIAL.search(text)) else None)


def day_of(text: str) -> str | None:
    """A date's month and day (MM-DD), however it's written, so a copy is found whether or not it gives the year."""
    if full := dates.first_in(text):
        return full[5:10] if len(full) == 10 else None
    if not (m := PARTIAL.search(text)):
        return None
    if m.group(1):
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return f"{MONTHS.index(m.group(3).lower()[:3]) + 1:02d}-{int(m.group(4)):02d}" if int(m.group(4)) <= 31 else None


def _unit(rel, n, unit, line, path, body=""):
    return {"file": rel, "line": n, "unit": unit, "date": date_of(line), "heading": " > ".join(path),
            "text": line.strip(), "body": body}


def units(rel: str, text: str) -> tuple[list[dict], dict]:
    """A file's dated units (a dated heading with its section, a dated list line, table row or other line, a jsonl
    row) and its frontmatter."""
    out, front, path = [], {}, []
    lines = text.splitlines()
    if rel.endswith(".jsonl"):
        return [_unit(rel, n, "row", line, []) for n, line in enumerate(lines, 1) if line.strip() and date_of(line)], {}
    start = 0
    if lines and lines[0].strip() == "---":
        for n, line in enumerate(lines[1:], 2):
            if line.strip() == "---":
                start = n
                break
            if m := FIELD.match(line):
                front[m.group(1)] = m.group(2).strip()
    heads, fence = [], False
    for n, line in enumerate(lines[start:], start + 1):
        if FENCE.match(line):
            fence = not fence
        if fence or FENCE.match(line):
            continue
        if m := HEADING.match(line):
            level = len(m.group(1))
            path = path[:level - 1] + [m.group(2)]
            heads.append((n, level))
            if date_of(m.group(2)):
                out.append(_unit(rel, n, "heading", line, path))
            continue
        if not date_of(line):
            continue
        kind = "row" if TABLE_ROW.match(line) and not TABLE_RULE.match(line) else "line" if LIST_ITEM.match(line) else "text"
        out.append(_unit(rel, n, kind, line, path))
    for u in out:  # a dated heading's unit is its whole section
        if u["unit"] == "heading":
            level = next(lv for n, lv in heads if n == u["line"])
            end = next((n for n, lv in heads if n > u["line"] and lv <= level), len(lines) + 1)
            u["body"] = "\n".join(lines[u["line"]:end - 1])
    return out, front


def names_in(text: str) -> set[str]:
    out = set()
    for line in NOISE.sub(" ", text).splitlines():
        for m in NAME.finditer(line):
            before = line[:m.start()].rstrip()
            if len(m.group(0)) < 3 or m.group(0).lower() in NOT_NAMES or not before or before[-1] in ".!?:#*>|-+" \
                    or re.fullmatch(r"\s*\d+[.)]", before):
                continue
            out.add(m.group(0))
    return out


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def _tracked(repo: Path, of: str = "") -> dict[str, bytes | None]:
    """Each path git tracks, to its bytes as the working tree has it, as the index does (`of="index"`, what a commit is
    made of) or as a commit does; None for what isn't a regular file, and empty for a commit that doesn't exist. Git's
    environment is kept: inside a hook it names the index being committed."""
    if not of:
        return {r: (repo / r).read_bytes() if (repo / r).is_file() else None
                for r in _git(repo, "ls-files", "-z").split("\0") if r}
    listed = _git(repo, "ls-files", "-s", "-z") if of == "index" else _git(repo, "ls-tree", "-r", "-z", of)
    entries = [e.split("\t", 1) for e in listed.split("\0") if e]
    # "<mode> <sha> <stage>" from the index, "<mode> <type> <sha>" from a commit
    blobs = {rel: meta.split()[1 if of == "index" else 2] for meta, rel in entries if meta.startswith("100")}
    out = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input="\n".join(blobs.values()).encode(),
                         capture_output=True).stdout
    content, at = {}, 0
    for sha in blobs.values():  # each object is "<sha> blob <size>\n<bytes>\n", in the order asked
        head_end = out.index(b"\n", at)
        size = int(out[at:head_end].split()[2])
        content[sha] = out[head_end + 1:head_end + 1 + size]
        at = head_end + 2 + size
    return {rel: content[blobs[rel]] if rel in blobs else None for _, rel in entries}


def _history(repo: Path) -> dict[str, tuple[int, int]]:
    """Lines each path's history added and deleted."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for line in _git(repo, "log", "--numstat", "--format=", "--no-renames").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            out[parts[2]][0] += int(parts[0])
            out[parts[2]][1] += int(parts[1])
    return {k: (a, d) for k, (a, d) in out.items()}


def _folder(rel: str) -> str:
    parts = Path(rel).parts[:-1]
    return "/".join("*" if re.fullmatch(r"\d{2,4}", p) else p for p in parts) or "."


def analyse(repo: Path) -> dict:
    """The facts of a repo a rewiring starts from, with no model call: each folder's files, units, frontmatter keys,
    row fields and whether its files are appended to or revised in place; the names the most files mention (the
    spine's candidates); every name and date found in COPY_FILES or more files; and each live item whose stated
    date is older than its newest entry."""
    if _git(repo, "rev-parse", "--show-toplevel").strip() != str(repo.resolve()):
        raise ValueError(f"{repo} isn't the top of a git repo: analyse reads what git tracks, so clone or init it")
    tracked = {r: b for r, b in _tracked(repo).items() if not r.startswith(f"{pack.DIR}/")}
    hist = _history(repo)
    folders: dict[str, dict] = {}
    all_units, file_names, stale = [], {}, []
    for rel, raw in tracked.items():
        p = Path(rel)
        f = folders.setdefault(_folder(rel), {"files": 0, "bytes": 0, "suffixes": Counter(), "dated_units": 0,
                                              "most_units": 0, "frontmatter": Counter(), "row_fields": Counter(),
                                              "appended": 0, "revised": 0})
        f["files"] += 1
        f["suffixes"][p.suffix or "(none)"] += 1
        if raw is None:
            continue
        f["bytes"] += len(raw)
        if rel in hist and hist[rel][0]:
            f["appended" if hist[rel][1] <= APPEND * hist[rel][0] else "revised"] += 1
        if not _is_text(rel):
            continue
        text = raw.decode(errors="replace")
        us, front = units(rel, text)
        f["dated_units"] += len(us)
        f["most_units"] = max(f["most_units"], len(us))
        f["frontmatter"].update(front.keys())
        if p.suffix == ".jsonl":
            for line in text.splitlines()[:200]:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    f["row_fields"].update(row.keys())
        all_units += us
        file_names[rel] = names_in(text)
        as_of = next((v for k, v in front.items() if AS_OF.match(k) and dates.first_in(v)), None)
        newest = max((d for u in us if (u["unit"] == "heading" or LIST_ITEM.match(u["text"]) and
                                        date_of(" ".join(LIST_ITEM.sub("", u["text"]).split()[:3])))
                      and (d := dates.first_in(u["text"])) and len(d) == 10), default=None)
        if as_of and newest and front.get("status", "").lower() not in CLOSED and newest > dates.first_in(as_of):
            stale.append({"file": rel, "as_of": dates.first_in(as_of), "newest_entry": newest})
    df, copies = _copies(all_units, file_names)
    names = {n for n, c in df.items() if 2 <= c <= len(file_names) / 2}
    for f in folders.values():
        for k in ("suffixes", "frontmatter", "row_fields"):
            f[k] = dict(f[k].most_common(12))
    return {"repo": str(repo), "commit": _git(repo, "rev-parse", "HEAD").strip(), "files": len(tracked),
            "dated_units": len(all_units), "folders": dict(sorted(folders.items())),
            "names": [{"name": n, "files": df[n]} for n in sorted(names, key=lambda n: (-df[n], n))[:30]],
            "copies": copies, "stale": stale}


def _is_text(rel: str) -> bool:
    """A file analyse reads: text the record writes, outside engram's own folder."""
    return Path(rel).suffix in (".md", ".jsonl", ".txt") and not rel.startswith(f"{pack.DIR}/")


def _copies(all_units: list[dict], file_names: dict[str, set[str]]) -> tuple[Counter, list[dict]]:
    """How many files mention each name, and every name and date found in COPY_FILES or more files. A name in more
    than half the files, or in one, is no item's."""
    df = Counter(n for ns in file_names.values() for n in ns)
    names = {n for n, c in df.items() if 2 <= c <= len(file_names) / 2}
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for u in all_units:
        if day := day_of(u["text"]):
            for n in names_in(u["text"] + "\n" + u["body"]) & names:
                groups[(n, day)].add(u["file"])
    return df, sorted(({"name": n, "date": d, "files": sorted(fs)} for (n, d), fs in groups.items() if len(fs) >= COPY_FILES),
                      key=lambda g: (-len(g["files"]), g["name"], g["date"]))


def summary(a: dict) -> dict:
    return {"files": a["files"], "dated_units": a["dated_units"], "folders": len(a["folders"]),
            "spine_candidates": [n["name"] for n in a["names"][:8]], "copy_groups": len(a["copies"]),
            "widest_copy": (f"{a['copies'][0]['name']} {a['copies'][0]['date']} in {len(a['copies'][0]['files'])} files"
                            if a["copies"] else None), "stale": len(a["stale"])}


# The checks on a proposal, and the two signs that a rewired repo has drifted.
CANON = Path(__file__).resolve().parents[2] / "docs/shape.md"
AXES = {"entity", "category", "time", "owner", "lifecycle", "aggregate"}
ANCHOR = re.compile(r"^\s*(?:[-*]|\|)\s*\*\*(.+?)\*\*", re.M)
QUOTE = re.compile(r'"([^"\n]+)"|\u201c([^\u201d\n]+)\u201d')
ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\*\*(.+?)\*\*(.*)$", re.M)
ASK_TURNS = 3  # each kind of ask cites this many of the owner's messages


def anchor_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def anchors(canon: Path = CANON) -> set[str]:
    """The canon's anchors: each bold lead phrase of a bullet or table row in shape.md."""
    return {anchor_key(m.group(1)) for m in ANCHOR.finditer(canon.read_text())}


def _flat(text: str) -> str:
    return " ".join(text.lower().replace("\u2019", "'").replace("\u2018", "'").split())


def found(quote: str, corpus: str) -> bool:
    """A quote is found when every part of it (split at an ellipsis) is in the corpus word for word."""
    parts = [p.strip(" ,.;") for p in re.split(r"\.\.\.|\u2026", _flat(quote))]
    return all(p in corpus for p in parts if p)


def owner_words(run: Path) -> tuple[str, str | None]:
    """turns.md's messages that aren't briefs, flattened for matching, and the time it was cut at."""
    text = (run / "turns.md").read_text()
    kept = [m.group(2) for m in re.finditer(r"^### \S+ \S+( brief)?\n(.*?)(?=^### |\Z)", text, re.S | re.M) if not m.group(1)]
    cut = re.search(r"\), before (.+?); \d+ marked as briefs", text.split("\n### ", 1)[0])
    return _flat("\n".join(kept)), cut.group(1) if cut else None


JOBS = f"{PAGE}'s Jobs section"
JOBS_HEADING = re.compile(r"^## Jobs\b.*$", re.M)


def jobs_section(page: bytes | None) -> bytes | None:
    """A repo page's Jobs section, from its heading to the next heading of its level or above: the jobs and failures a
    rewiring answers to, which `[rewire] at` names. An edit elsewhere on the page isn't drift."""
    text = page.decode() if page else ""
    if not (m := JOBS_HEADING.search(text)):
        return None
    end = re.search(r"^#{1,2} ", text[m.end():], re.M)
    return (text[m.start():m.end() + end.start() if end else len(text)].strip() + "\n").encode()


def jobs_of(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """A Jobs section's jobs, then its failures (the items under a "Failures" heading): each numbered or bulleted bold
    item, with the quotes it carries."""
    m = re.search(r"^#+\s*Failures", text, re.M | re.I)
    parts = (text[:m.start()], text[m.start():]) if m else (text, "")
    return tuple({anchor_key(i.group(1)): [a or b for a, b in QUOTE.findall(i.group(0))] for i in ITEM.finditer(part)}
                 for part in parts)


def said_anywhere(quote: str, words: str, before: str | None, everywhere: list[str]) -> bool:
    """Whether the owner typed a quote before the run's cut: in the repo's turns, else in any session of theirs. A job
    or a departure may quote the owner wherever they said it; a kind of ask cites the repo's own turns."""
    if found(quote, words):
        return True
    if not everywhere:  # read once per check, and only when a quote isn't in the repo's own turns
        everywhere.append(_flat("\n".join(m["text"] for m in turns(None, before)["turns"] if not m["brief"])))
    return found(quote, everywhere[0])


def check(repo: Path, run: Path, canon: Path = CANON) -> dict:
    """What a rewiring must hold before it lands, and whether a rewired repo has drifted (docs/shape.md, "Rewiring a
    repo"). Problems are listed in plain words; none means it passes."""
    problems = []
    words, before = owner_words(run) if (run / "turns.md").exists() else (None, None)
    everywhere: list[str] = []
    if words is None:
        problems.append(f"no turns.md in {run}: run `engram rewire turns` first")
    jobs_raw = jobs_section((repo / PAGE).read_bytes() if (repo / PAGE).exists() else None)
    jobs_text = jobs_raw.decode() if jobs_raw else ""
    jobs, failures = jobs_of(jobs_text)
    if not jobs:
        problems.append(f"{JOBS} names no jobs (numbered or bulleted bold items)")
    for job, quotes in {**jobs, **failures}.items():
        if not quotes:
            problems.append(f"job '{job}' quotes none of the owner's words")
        for q in quotes:
            if words is not None and not said_anywhere(q, words, before, everywhere):
                problems.append(f"job '{job}': \"{q}\" isn't in the owner's messages word for word (briefs don't count)")
    try:
        toml = tomllib.loads(record_toml(repo).read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {"ok": False, "problems": problems + [f"{RECORD_TOML} doesn't load: {e}"], "drift": []}
    if (repo / pack.DIR / "__init__.py").exists():
        try:
            pack.load_dir("rewire_check", repo / pack.DIR)
        except Exception as e:  # any failure to import is the pack's
            problems.append(f"{pack.DIR}/ doesn't load as a pack: {e}")
    canon_anchors = anchors(canon)
    rw = toml.get("rewire") or {}
    served = set()
    for ask in rw.get("asks") or []:
        name = ask.get("kind", "?")
        if ask.get("axis") not in AXES:
            problems.append(f"kind of ask '{name}': axis '{ask.get('axis')}' is none of {sorted(AXES)}")
        if anchor_key(str(ask.get("piece", ""))) not in canon_anchors:
            problems.append(f"kind of ask '{name}': piece '{ask.get('piece')}' is no anchor in the canon")
        cited = [t for t in ask.get("turns") or [] if words is not None and found(t, words)]
        if len(set(cited)) < ASK_TURNS:
            problems.append(f"kind of ask '{name}' cites {len(set(cited))} of the owner's messages word for word, "
                            f"not {ASK_TURNS}")
        for j in ask.get("jobs") or []:
            if anchor_key(j) not in jobs:
                problems.append(f"kind of ask '{name}' serves '{j}', which {JOBS} doesn't name")
            served.add(anchor_key(j))
    for job in sorted(jobs.keys() - served):
        problems.append(f"job '{job}' is served by no kind of ask")
    try:
        copies = analyse(repo)["copies"]
    except ValueError as e:
        problems.append(str(e))
        copies = []
    unhomed = _unhomed(copies, rw.get("homes") or {}, lambda h: (repo / h).is_file())
    for g in unhomed[:10]:
        problems.append(f"copy {g['name']} {g['date']} in {len(g['files'])} files has no home in [rewire.homes]")
    if len(unhomed) > 10:
        problems.append(f"... and {len(unhomed) - 10} more copies with no home")
    for anchor, why in (toml.get("departures") or {}).items():
        if anchor_key(anchor) not in canon_anchors:
            problems.append(f"departure '{anchor}' names no anchor in the canon")
        quotes = [a or b for a, b in QUOTE.findall(str(why))]
        if not any(found(q, _flat(jobs_text)) or (words is not None and said_anywhere(q, words, before, everywhere)) for q in quotes):
            problems.append(f"departure '{anchor}' quotes no job, failure or message of the owner's")
    return {"ok": not problems, "problems": problems, "drift": _say(_signs(rw, jobs_raw, unhomed))}


def jobs_id(section: bytes) -> str:
    """The id `[rewire] at` holds: of the Jobs section's jobs and failures (each bold name with its quotes, `jobs_of`),
    so prose around them isn't drift."""
    return hashlib.sha1(json.dumps(jobs_of(section.decode()), ensure_ascii=False).encode()).hexdigest()


def _unhomed(copies: list[dict], homes: dict, is_file) -> list[dict]:
    """The copies none of whose files is under a home (a folder or a file, keyed as analyse names its paths)."""
    hs = [h if is_file(h) else h.rstrip("/") + "/" for h in homes]
    return [g for g in copies if not any(f == h or f.startswith(h) for f in g["files"] for h in hs)]


def _signs(rw: dict, jobs: bytes | None, unhomed: list[dict]) -> dict:
    """The two signs a rewired repo has drifted: its jobs aren't the ones `[rewire] at` names (`jobs_id` of the Jobs
    section it was rewired at), or a copy has no home. Keyed so one sign in two trees is one key: `rewire`, `jobs`, and
    each unhomed copy's name and date."""
    if not rw:
        return {"rewire": f"{RECORD_TOML} has no [rewire]: the repo has no rewiring on record (the engram-rewire skill)"}
    out: dict = {}
    if jobs is None:
        out["jobs"] = f"there's no {JOBS}: a rewiring answers to the owner's jobs"
    elif rw.get("at") != (now := jobs_id(jobs)):
        out["jobs"] = (f"{JOBS} changed since the last rewire: set [rewire] at = \"{now}\", or rewire against it first if "
                       f"a job was added, dropped or renamed")
    return out | {("copy", g["name"], g["date"]): g for g in unhomed}


def _say(signs: dict) -> list[str]:
    """The signs in plain words, the copies on one line."""
    out = [v for v in signs.values() if isinstance(v, str)]
    if gs := [v for v in signs.values() if isinstance(v, dict)]:
        out.append(f"{len(gs)} copies have no home in [rewire.homes]: " + "; ".join(
            f"{g['name']} {g['date']} in {', '.join(g['files'])}" for g in gs[:3]) + ("; ..." if len(gs) > 3 else ""))
    return out


def _signs_in(files: dict[str, bytes | None]) -> dict:
    try:
        rw = tomllib.loads((files.get(RECORD_TOML) or b"").decode()).get("rewire") or {}
    except tomllib.TOMLDecodeError as e:
        return {"toml": f"{RECORD_TOML} doesn't load: {e}"}
    all_units, names = [], {}
    for rel, raw in files.items():
        if raw is not None and _is_text(rel):
            text = raw.decode(errors="replace")
            all_units += units(rel, text)[0]
            names[rel] = names_in(text)
    return _signs(rw, jobs_section(files.get(PAGE)), _unhomed(_copies(all_units, names)[1], rw.get("homes") or {}, lambda h: h in files))


def drift(repo: Path, introduced: bool = False) -> list[str]:
    """Drift in what's being committed (the index), with no run folder: health's check. `introduced` keeps only the
    signs HEAD doesn't already have, nor the tree a conflicted merge brings in (MERGE_HEAD): the pre-commit's check, so
    drift that reached HEAD another way (a pull, a `--no-verify` commit, a release that finds more copies) is health's to
    report and never blocks a commit, the filer's included."""
    signs = _signs_in(_tracked(repo, "index"))
    for of in ("HEAD", "MERGE_HEAD") if introduced else ():
        if tree := _tracked(repo, of):
            signs = {k: v for k, v in signs.items() if k not in _signs_in(tree)}
    return _say(signs)
