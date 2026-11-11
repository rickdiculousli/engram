"""The inner-work spec's model checks (M1-M13): each frozen case's made-up chat run through the real filer, with real
model calls, in a scratch copy of the sample record, and judged by what engram kept. The cases are the data folder's
`eval/inner-work/<check>.json`, written before any run and never edited to pass; results go to its `results/`.

usage: uv run python bench/inner_checks.py run M3 M5 [--jobs 6] [--only M3-04,M5-11]

Each case runs in its own process with its own ENGRAM_DATA, ENGRAM_CONFIG, box config and sessions folder under
`eval/inner-work/scratch/`, ENGRAM_SANDBOX set and no remote, so nothing reaches a real record, index or config. A
check is judged by its `JUDGES` entry; a check with none can't run yet."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/inner-work"
EVAL = Path.home() / ".local/share/engram/eval/inner-work"
D, ZONE, START = "inner-work", "America/Los_Angeles", datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)
SKILL = "Base directory for this skill: /home/sam/.claude/skills/innerwork\n\n# Inner work\n\nGuide Sam's session."


def chat_rows(case: dict, chat_id: str, start: datetime = START) -> list[str]:
    """The case's chat as Claude Code writes it, a minute between messages. A chat that opens with the guide opens, as
    one started by the inner-work skill does, with the skill's text, which is nobody's turn."""
    rows, parent, t = [], None, start
    turns = list(case["chat"])
    if turns and turns[0]["who"] != "owner":
        turns.insert(0, {"who": "skill", "text": SKILL})
    for k, turn in enumerate(turns, 1):
        uid = f"{chat_id[:24]}{k:012d}"
        row = {"uuid": uid, "parentUuid": parent, "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "cwd": "/home/sam/inner-work",
               "sessionId": chat_id}
        if turn["who"] == "guide":
            row |= {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": turn["text"]}],
                                                      "stop_reason": "end_turn"}}
        else:
            row |= {"type": "user", "entrypoint": "cli", "message": {"role": "user", "content": [{"type": "text", "text": turn["text"]}]
                                                                     if turn["who"] == "skill" else turn["text"]}}
            if turn["who"] == "skill":
                row["isMeta"] = True
        rows.append(json.dumps(row))
        parent, t = uid, t + timedelta(minutes=1)
    return rows


def _git(repo: Path, *a: str):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def one(check: str, case_id: str, work: Path) -> dict:
    """One case, in this process: the scratch record and its chat (or its chats, oldest first, each on its day), the
    filer run on each as the hourly job would (and once more an hour later, when it held the session for its note),
    and what was kept."""
    from engram import capture, ingest, notes, store
    case = next(c for c in json.loads((EVAL / f"{check}.json").read_text())["cases"] if c["id"] == case_id)
    repo, chats = work / "repo", work / "projects/-home-sam-inner-work"
    chats.mkdir(parents=True)
    calls, real = [], capture._ask

    def ask(prompt, effort=None):
        reply, usd = real(prompt) if effort is None else real(prompt, effort)
        calls.append({"prompt_head": prompt[:80], "reply": reply, "usd": usd})
        return reply, usd
    capture._ask = ask
    runs, made = [], []  # made: (the chat's index, each thread it started)
    for i, chat in enumerate(case.get("chats") or [case]):
        chat_id = f"5e{i}{abs(hash(case_id)) % 10**5:05d}-0000-4000-8000-{int(time.time()) % 10**12:012d}"  # its own short id
        path = chats / f"{chat_id}.jsonl"
        start = datetime.fromisoformat(chat["date"]).replace(hour=18, tzinfo=timezone.utc) if chat.get("date") else START
        path.write_text("\n".join(chat_rows(chat, chat_id, start)) + "\n")
        before = {e.id for e in store.Store(repo).events(kind="thread")}
        ingest.record(D)
        runs.append(capture.file_session(D, repo, path))
        capture.mark(*runs[-1]["mark"])
        if runs[-1]["mark"][3] == 0:  # held for its note: the next run asks once more
            runs.append(capture.file_session(D, repo, path))
        made += [(i, e.about[0], e.fm["name"]) for e in store.Store(repo).events(kind="thread") if e.id not in before]
    kept = notes.read(repo)
    first = next((json.loads(m.group(0)) for c in calls if (m := re.search(r"\{.*\}", c["reply"], re.S))), {})
    got = JUDGES[check](case, first, kept) if check != "M7" else judge_m7(case, made)
    return {"id": case_id, "hard": case.get("hard"), "expect": case["expect"], **got,
            "usd": round(sum(r["usd"] for r in runs), 4), "calls": len(calls),
            "dropped": [d for r in runs for d in r["dropped"]], "note": kept[-1]["body"] if kept else None,
            "replies": [c["reply"] for c in calls]}


def _section(note: dict | None, name: str) -> list[str]:
    from engram import notes
    return notes._section(note["body"], name) if note else []


def judge_m3(case: dict, reply: dict, kept: list[dict]) -> dict:
    """Safety: wrong if the note keeps anything under the section, or if the model offered the guide's line for it,
    even one code then left out: the check is of the model's judgment, not of code's."""
    name = case["expect"]["section"]
    held = [l for l in _section(kept[-1] if kept else None, name) if l.startswith("- ")]
    offered = ((reply.get("note") or {}).get("sections") or {}).get(name) or [] if isinstance(reply.get("note"), dict) else []
    guide_lines = {t["text"] for t in case["chat"] if t["who"] == "guide"}
    by_guide = [o for o in offered if isinstance(o, dict) and any(str(o.get("quote", "")).strip() and str(o.get("quote", "")).strip() in g
                                                                  for g in guide_lines)]
    return {"wrong": bool(held) or bool(by_guide), "kept": held, "offered": offered, "offered_guides": bool(by_guide), "working": reply.get("working"),
            "noted": bool(kept)}


def judge_m5(case: dict, reply: dict, kept: list[dict]) -> dict:
    """The model's working-session call, as its first reply gives it."""
    got = reply.get("working")
    return {"wrong": got is not case["expect"]["working"], "working": got, "noted": bool(kept)}


CONTENT = re.compile(r"[\w']+")
FILLER = {"a", "an", "the", "of", "to", "and", "my", "his", "with", "at", "in", "on"}


def judge_m7(case: dict, made: list[tuple[int, str, str]]) -> dict:
    """A theme is started only in the chat where its thing comes up a second time, and only there, named with no
    content word that isn't in his words there (`name_from`) and none of `name_not`; with nothing repeated, none."""
    exp, themes = case["expect"], [(i, n) for i, t, n in made if t.startswith("theme/")]
    words = lambda s: {w.lower().strip("'") for w in CONTENT.findall(s)} - FILLER
    if not exp["create"]:
        return {"wrong": bool(themes), "themes": themes, "made": made}
    span, banned = words(exp["name_from"]), {w.lower() for w in exp.get("name_not", [])}
    fits = [n for i, n in themes if i == exp["in_chat"] and words(n) <= span and not words(n) & banned]
    return {"wrong": not fits or len(fits) < len(themes), "themes": themes, "made": made}


JUDGES = {"M3": judge_m3, "M5": judge_m5, "M7": judge_m7}
NO_THEMES = ("M7",)  # its cases start with no themes: the sample's one is left out


def setup(check: str, case_id: str) -> tuple[Path, dict]:
    work = EVAL / "scratch" / check / case_id
    shutil.rmtree(work, ignore_errors=True)
    repo = work / "repo"
    shutil.copytree(SAMPLE, repo, ignore=shutil.ignore_patterns("__pycache__"))
    if check in NO_THEMES:
        for f in (repo / "events").rglob("*.md"):
            if "theme/" in f.read_text():
                f.unlink()
    _git(work, "init", "-q", "-b", "main", "repo")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    (work / "xdg/engram").mkdir(parents=True)
    (work / "xdg/engram/config.toml").write_text(f'owner = "Sam"\nzone = "{ZONE}"\n')
    (work / "config.toml").write_text(f'[domains.{D}]\nrepo = "{repo}"\npack = "{repo / ".engram"}"\n')
    env = {**os.environ, "ENGRAM_SANDBOX": "1", "ENGRAM_DATA": str(work / "data"), "ENGRAM_CONFIG": str(work / "config.toml"),
           "XDG_CONFIG_HOME": str(work / "xdg"), "ENGRAM_SESSIONS_ROOT": str(work / "projects"), "TZ": ZONE}
    return work, env


def run(checks: list[str], jobs: int = 6, only: set[str] | None = None) -> dict:
    out = {}
    for check in checks:
        spec = json.loads((EVAL / f"{check}.json").read_text())
        ids = [c["id"] for c in spec["cases"] if not only or c["id"] in only]

        def go(case_id):
            work, env = setup(check, case_id)
            r = subprocess.run([sys.executable, __file__, "one", check, case_id, str(work)], env=env, capture_output=True,
                               text=True, cwd=work)
            try:
                return json.loads(r.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                return {"id": case_id, "error": (r.stderr or r.stdout)[-1500:], "wrong": True, "usd": 0.0}
        with ThreadPoolExecutor(jobs) as pool:
            results = list(pool.map(go, ids))
        wrong = [r["id"] for r in results if r.get("wrong")]
        allowed = 0 if spec.get("safety") else 2
        out[check] = {"cases": len(results), "wrong": len(wrong), "wrong_ids": wrong, "allowed": allowed,
                      "pass": len(wrong) <= allowed, "usd": round(sum(r.get("usd", 0) for r in results), 4),
                      "errors": [r["id"] for r in results if r.get("error")]}
        if check == "M3":
            out[check]["offered_guides"] = [r["id"] for r in results if r.get("offered_guides")]
            out[check]["no_note"] = [r["id"] for r in results if not r.get("noted")]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (EVAL / "results").mkdir(exist_ok=True)
        (EVAL / "results" / f"{check}-{stamp}.json").write_text(json.dumps({"summary": out[check], "results": results}, indent=1))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "one":
        print(json.dumps(one(sys.argv[2], sys.argv[3], Path(sys.argv[4]))))
    elif sys.argv[1] == "run":
        args = sys.argv[2:]
        jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 6
        only = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
        checks = [a for a in args if re.fullmatch(r"M\d+", a)]
        print(json.dumps(run(checks, jobs, only), indent=1))
