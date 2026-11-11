"""Session summaries (docs/summaries.md): cleaned segments, a Haiku pass per segment, a lint in code, Opus stitching,
stored as JSON per session and indexed as class summary.

A turn is one exchange: the owner's words, any messages he sent while Claude worked, and Claude's replies, cited by the
line of his turn in the session file.
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from engram import config, daily, dates, llm, pack
from engram.index import Doc, now, open_index
from engram.paths import data_path, index_path
from engram.sources import sessions
from engram.sources.sections import chunks

SEGMENT_VERSION, STITCH_VERSION = "16", "17"  # a new version re-summarizes only after QA shows it does better


def rules(domain: str) -> tuple[str, str, str] | None:
    """The domain's own rules, from its pack: (version, what the segment prompt adds, what the second pass adds)."""
    return pack.load(domain).summary_rules


def segment_version(domain: str) -> str:
    """A domain with rules of its own versions its segment prompt apart, so the base one stays as it is."""
    return SEGMENT_VERSION + r[0] if (r := rules(domain)) else SEGMENT_VERSION
# Measured 2026-10-20, blind review of four variants on three sessions: Opus at low effort reading the whole
# session had the fewest unfaithful items (10 against 15 to 22) and cost less than Haiku segments with Opus stitching.
SEGMENT_MODEL = STITCH_MODEL = "claude-opus-5-5"
SEGMENT_EFFORT = STITCH_EFFORT = "low"
# A re-read of each part against its own first reading. Blind review, four sessions, 2026-10-20: 12 unfaithful
# items against 18 for one pass, 6 missed points against 23, ranked best in every session; about 3 times the cost.
SECOND_PASS = True
SEG_TURNS, SEG_CHARS, OVERLAP = 100000, 200000, 2  # a whole session is one part unless it's longer than this
GROUP = 8  # one stitch reads at most this many summaries; a longer session is stitched in overlapping groups, then once more
CLIP = 20000  # either side of a turn longer than this keeps its head and tail
IDLE = timedelta(hours=2)  # a session written to more recently than this may still be going
SYSTEM = "You turn conversation transcripts into strict JSON summaries. Reply with JSON only."
RELAYED = r"^(own|{owner_id}|clinician:.+|other:.+)$"
CLAIM_ACTS = {"report", "finding", "analysis", "advice", "plan"}  # record and question items are moved out by characterize()
NOT_STATED = "not stated"
STATUSES = {"confirmed", "suspected", "ruled out", "considering", "adopted", "dropped", "planned", "established",
            "working hypothesis", "resolved", "open"}
DIRECTIONS = {"better", "worse", "same", "new", "back", "gone", "unclear"}
TAG = re.compile(r"^(new:)?complaint/[a-z0-9]+(-[a-z0-9]+)*$")
QUOTED = re.compile(r'"([^"]{3,}?)"|“([^”]{3,}?)”')
CUT = re.compile(r"characters cut|truncat", re.I)
BOOKKEEPING = re.compile(r"^(Claude|The assistant) (filed|logged|saved|committed|pushed|updated|wrote|drafted|revised|added|"
                         r"corrected|recorded|copied|cleared|created|edited|moved|appended|noted that it)\b"
                         r"|\b(filed|logged) (as|under|in the|to the)\b|\bnot watching\b|\b(medication|med)[- ]list (write|update|entry)"
                         r"|\bpending (write|update|filing)\b|\bgit (commit|push)\b|\bcommit(ted|s)? and push|\bpushed (to|the)\b"
                         r"|\b(add|log|file|record|note) (it|this|that|them|the \w+) (to|in) (the|your) (record|log|history|chart|notes)\b", re.I)
# Claude's own subagents, checks and tools are Claude, never an outside source.
CLAUDE_TOOLING = re.compile(r"\b(subagent|sub-agent|agent|auditor|audit|check|claude)\b", re.I)
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
DATE = re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b"
                  rf"|\b(?:{MONTHS})[a-z]*\.? \d{{1,2}}(?:st|nd|rd|th)?\b|\b\d{{1,2}}(?:st|nd|rd|th)? (?:{MONTHS})[a-z]*\b", re.I)
TEXT_CAP, CLAIMS_CAP, CHRONOLOGY_CAP = 400, 25, 60
# Sessions a program started: headless `claude -p` runs, SDK runs from the system temp folder, and a domain's
# `sessions_from` folders (a harness's own runs).
LAUNCHED = ("-private-var-folders-",)
# Turns a program, a skill or another session wrote, though they arrive as user turns. Only the rest are the owner's words.
AUTOMATED = [(re.compile(p, re.S | re.M), label) for p, label in [
    (r"^Base directory for this skill: \S*?([\w-]+)\s", "Skill loaded"),
    (r"^Another Claude session sent a message:", "Another Claude session"),
    (r"^(=== QUEUED CONVERSATION SPANS|You generate concise git branch names|Review the change at this commit"
     r"|(TODAY IS|Today is) \d{4}-\d{2}-\d{2}(\.(\s|$)| for this \w+\.)|# Scout packet|Build what's accepted in"
     r"|Please analyze this codebase|You are executor \S+ in |YOUR PREVIOUS ANSWER WAS REJECTED)", "Prompt"),
    (r"^You are the [^\n]*\n.*^#{1,6} ", "Prompt")]]  # a role a program hands out heads a brief with sections


Unavailable = llm.Unavailable  # a call failed instead of answering: run() stops on it and keeps done sessions; tests raise it


@dataclass
class Turn:
    line: int
    ts: str
    text: str


def _clip(s: str) -> str:
    s = s.strip()
    if len(s) <= CLIP:
        return s
    return f"{s[:CLIP * 2 // 3]}\n[… {len(s) - CLIP} characters cut …]\n{s[-CLIP // 3:]}"


def _local(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return ts


def _launched() -> tuple[str, ...]:
    return LAUNCHED + tuple(m for d in config.load().values() for m in d.sessions_from)


def speaker(s: sessions.Session, said: str, owner: str) -> tuple[str, str]:
    """Who wrote a user turn, and the words to show for it: the owner's (labelled `owner`) verbatim, a skill by name only."""
    if sessions.by_agent(s) or any(m in s.project for m in _launched()):
        return "Prompt", said
    for pat, label in AUTOMATED:
        m = pat.match(said)
        if m:
            return label, m.group(1) if label == "Skill loaded" else said
    return owner, said


def _owner_turn(owner: str) -> str:
    """A turn's opening label when the owner wrote it."""
    return rf"^{re.escape(owner)}( \(while Claude worked\))?: "


def clean(s: sessions.Session) -> list[Turn]:
    """The owner's words verbatim, the messages he sent while Claude worked in their place, and Claude's replies; tool
    calls, tool output, reminders and compaction summaries dropped, and so is Claude's narration between commands
    when a final reply follows it, since its statuses go stale within the turn. A turn sent again with nothing said between is a retry, and only
    the later one is kept. A session with no turn of his (a headless run, a launcher's prompt) has nothing to summarize."""
    owner = config.owner()
    xs = [x for x in s.exchanges if not x.summary]
    out = []
    for i, x in enumerate(xs):
        if i + 1 < len(xs) and xs[i + 1].asked.strip() == x.asked.strip() and not (x.replies or x.queued):
            continue
        who, words = ("Skill loaded", x.asked.lstrip("# ").splitlines()[0][:80]) if x.meta else speaker(s, x.asked, owner)
        parts = [f"{who}: {_clip(words)}"]
        finals = [i for i in range(len(x.replies)) if i not in x.narration]
        keep = set(finals or range(len(x.replies))[-1:])
        start = 0
        for at, said in x.queued + [(len(x.replies), None)]:
            run = [x.replies[i] for i in range(start, at) if i in keep]
            if run:
                parts.append(f"Claude: {_clip(chr(10).join(run))}")
            start = at
            if said is not None:
                label, said = speaker(s, said, f"{owner} (while Claude worked)")
                parts.append(f"{label}: {_clip(said)}")
        out.append(Turn(x.line, _local(x.ts), "\n\n".join(parts)))
    return out if any(re.search(_owner_turn(owner), t.text, re.M) for t in out) else []


def segments(turns: list[Turn]) -> list[list[Turn]]:
    """About 8 turns or 12,000 characters each, overlapping the next by 2 turns, and always holding at least one turn
    the last segment didn't. Boundaries depend only on the turns before them, so a session that grows changes only
    its last segments."""
    out, i, new = [], 0, 0
    while i < len(turns):
        seg, size, j = [], 0, i
        while j < len(turns) and (not seg or j == new or (len(seg) < SEG_TURNS and size + len(turns[j].text) <= SEG_CHARS)):
            seg.append(turns[j])
            size += len(turns[j].text)
            j += 1
        out.append(seg)
        if j >= len(turns):
            break
        i, new = max(i + 1, j - OVERLAP), j
    return out


def render_turns(turns: list[Turn]) -> str:
    return "\n\n".join(f"[L{t.line} · {t.ts[:16].replace('T', ' ')}]\n{t.text}" for t in turns)


def _n(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


def _within(part: str, whole: str) -> bool:
    return _n(part).lower() in _n(whole).lower()


def _part_end() -> str:
    return rf"(?=\n\n(?:Claude|{re.escape(config.owner())}|Prompt|Skill loaded|Another Claude session)[^\n]*: |\Z)"


def _owner_words(src: str) -> str:
    return "\n".join(m.group(2) for m in re.finditer(_owner_turn(config.owner()) + "(.*?)" + _part_end(), src, re.M | re.S))


def _claude_words(src: str) -> str:
    return "\n".join(m.group(1) for m in re.finditer(r"^Claude: (.*?)" + _part_end(), src, re.M | re.S))


def _asks(phrase: str, words: str) -> bool:
    """The phrase sits in a sentence of these words that ends in a question mark."""
    t, e = _n(words).lower(), _n(phrase).lower()
    i = t.find(e) if e else -1
    if i < 0:
        return False
    end = min([j for j in (t.find(c, i) for c in ".?!\n") if j >= 0] or [len(t)])
    return end < len(t) and t[end] == "?"


def said_by(item: dict, turns: dict[int, str]) -> str | None:
    """Whose words an item's evidence is, in the turn it cites: the owner's id, "claude", or None when it's in neither's."""
    src = turns.get(item.get("line")) or ""
    ev = str(item.get("evidence", "")).strip('"“” ')
    return (config.owner_id() if ev and _within(ev, _owner_words(src)) else
            "claude" if ev and _within(ev, _claude_words(src)) else None)


def _speakers(summary, turns: dict[int, str]):
    """Each update's speaker, by where its evidence sits: a change the owner stated is his; an analysis Claude
    corrected is Claude's."""
    for u in (summary.get("updates") or []) if isinstance(summary, dict) else []:
        if isinstance(u, dict):
            u["speaker"] = said_by(u, turns)


def characterize(out, turns: dict[int, str], stitched: bool = False):
    """Works out what the model is asked only to describe. Who said each claim, and each update, comes from where its
    evidence sits; whose claim it is follows from that and `relayed_from`; a record note goes to `filed` and an open
    question to `open`, never standing as claims."""
    key = "chronology" if stitched else "claims"
    if not isinstance(out, dict) or not isinstance(out.get(key), list):
        return out
    me = config.owner_id()
    _speakers(out, turns)
    keep = []
    for c in out[key]:
        if not isinstance(c, dict):
            keep.append(c)
            continue
        act = c.get("act")
        if act == "record" and isinstance(out.get("filed"), list):
            out["filed"].append({"line": c.get("line"), "what": c.get("text"), "where": ""})
            continue
        if act == "question" and isinstance(out.get("open"), list):
            out["open"].append({"line": c.get("line"), "text": c.get("text"), "evidence": c.get("evidence")})
            continue
        c["speaker"] = said_by(c, turns)
        rel = str(c.get("relayed_from") or "own").strip()
        if rel.lower() == me:
            c["by"] = me
        elif rel.lower() != "own":
            c["by"] = rel
        elif c["speaker"] == me:
            c["by"] = me
        elif c["speaker"] == "claude":
            c["by"] = "with-claude" if c.get("taken_up_at") else "claude-suggestion"
        else:
            c["by"] = ""
        keep.append(c)
    out[key] = keep
    return out


def lint(out, turns: dict[int, str], text: str, vocab: set[str], stitched: bool = False, cap: int | None = None,
         reach: dict[int, str] | None = None) -> list[str]:
    """Every rule docs/summaries.md puts on a summary that code can check. An empty list passes. `reach` is the turns
    a with-claude claim's `taken_up_at` may cite, when the owner may take an idea up after the text summarized."""
    if not isinstance(out, dict):
        return ["the reply is not a JSON object"]
    errs: list[str] = []
    claims_key = "chronology" if stitched else "claims"
    shape = {"topics": list, claims_key: list, "reported": list, "complaints": list, "decisions": list,
             "updates": list, "contradictions": list, "filed": list, "open": list, "tenor": dict}
    for k, t in shape.items():
        if not isinstance(out.get(k), t):
            errs.append(f"`{k}` is missing or not a {t.__name__}")
    if errs:
        return errs

    def at(item, where, key="line", among=None) -> str | None:
        among = among or turns
        line = item.get(key) if isinstance(item, dict) else None
        if not isinstance(line, int) or line not in among:
            errs.append(f"{where}: `{key}` {line!r} is not a turn in this text")
            return None
        return among[line]

    def words(s, src, where):
        if not isinstance(s, str):
            errs.append(f"{where}: not text")
            return
        if len(s) > TEXT_CAP:
            errs.append(f"{where}: over {TEXT_CAP} characters")
        if CUT.search(s):
            errs.append(f"{where}: mentions cut text; leave it out")
        for m in QUOTED.finditer(s):
            q = m.group(1) or m.group(2)
            if src is not None and not _within(q, src):
                errs.append(f'{where}: "{q[:60]}" is in quotation marks but is not word for word in the cited turn')
        for d in DATE.findall(s):
            if not _within(d, text):
                errs.append(f"{where}: the date {d!r} is not in the source")

    def exact(s, src, field, where):
        if s and src is not None and not _within(s, src):
            errs.append(f"{where}: `{field}` {s[:60]!r} is not word for word in the cited turn")

    def evidence(item, src, where):
        ev = str(item.get("evidence", "")).strip('"“” ')
        if len(ev.split()) < 3:
            errs.append(f"{where}: `evidence` must be a phrase of at least 3 words copied from the cited turn")
        else:
            exact(ev, src, "evidence", where)

    owner, me = config.owner(), config.owner_id()
    owner_words, claude_words = _owner_words, _claude_words

    def spoken_by(item, src, where, who):
        """The evidence sits in the words of the speaker the item credits: the owner's part of the turn, or Claude's."""
        ev = str(item.get("evidence", "")).strip('"“” ')
        if src is None or len(ev.split()) < 3 or not _within(ev, src):
            return
        part = owner_words(src) if who == me else claude_words(src)
        if not _within(ev, part):
            errs.append(f"{where}: the evidence isn't in {owner if who == me else 'Claude'}'s words, but the item credits "
                        f"{'him' if who == me else 'Claude'}")

    def owners(src, line, where, what):
        if src is not None and not re.search(_owner_turn(owner), src, re.M):
            errs.append(f"{where}: {what}, but {owner} didn't write turn {line}")

    claims = out[claims_key]
    if len(claims) > (cap or (CHRONOLOGY_CAP if stitched else CLAIMS_CAP)):
        errs.append(f"`{claims_key}` has {len(claims)} items, over the cap")
    for i, c in enumerate(claims):
        where = f"{claims_key}[{i}]"
        src = at(c, where)
        if not isinstance(c, dict):
            continue
        words(c.get("text", ""), src, where)
        evidence(c, src, where)
        if BOOKKEEPING.search(str(c.get("text", ""))):
            errs.append(f"{where}: Claude's own filing or record-keeping is not a claim; label it act \"record\"")
        if c.get("act") == "decision":
            errs.append(f"{where}: a decision goes in `decisions`")
        elif c.get("act") not in CLAIM_ACTS:
            errs.append(f"{where}: `act` {c.get('act')!r} is not report, finding, analysis, advice, plan, question or record")
        rel = str(c.get("relayed_from") or "")
        if not re.match(RELAYED.replace("{owner_id}", re.escape(me)), rel):
            errs.append(f"{where}: `relayed_from` is \"own\", \"{me}\", \"clinician:<name> (<role>)\" or \"other:<source>\"")
        elif rel.startswith("other:") and CLAUDE_TOOLING.search(rel):
            errs.append(f"{where}: Claude's own subagents, checks and tools are Claude: relayed_from \"own\"")
        if c.get("act") == "advice" and not c.get("quote"):
            errs.append(f"{where}: advice is quoted exactly, the whole instruction with its conditions: set quote true")
        if src is not None and "speaker" in c and c["speaker"] is None and _within(str(c.get("evidence", "")).strip('"“” '), src):
            errs.append(f"{where}: the evidence must be {owner}'s or Claude's own words in that turn")
        by = str(c.get("by", ""))
        first, raised = c.get("raised_first_at"), str(c.get("raised_first_evidence") or "").strip('"“” ')
        first_turn = (reach or turns).get(first, "") if isinstance(first, int) else ""
        if by in ("claude-suggestion", "with-claude") and first_turn and len(raised.split()) >= 2 and _within(raised, owner_words(first_turn)):
            errs.append(f"{where}: {owner} raised this first (L{first}: \"{raised[:60]}\"), so the idea is his: credit it to him at his "
                        f"turn, with his words as evidence; what Claude added is a separate claim")
        if by == "with-claude":
            took = at(c, where, "taken_up_at", reach)
            owners(took, c.get("taken_up_at"), where, f"`taken_up_at` must be a turn of {owner}'s")
            up = str(c.get("uptake_evidence", "")).strip('"“” ')
            if took is not None and (len(up.split()) < 2 or not _within(up, owner_words(took))):
                errs.append(f"{where}: `uptake_evidence` must copy {owner}'s own words from turn {c.get('taken_up_at')} that take it up")
            if took is not None and isinstance(c.get("line"), int) and c["taken_up_at"] < c["line"]:
                errs.append(f"{where}: `taken_up_at` comes before the claim")
        if not str(c.get("basis", "")).strip():
            errs.append(f"{where}: no `basis`")
        conf = str(c.get("confidence", "")).strip()
        if conf.lower() not in {"", "unstated"} | STATUSES:
            exact(conf, src, "confidence", where)
        if c.get("quote"):
            exact(str(c.get("text", "")).strip('"“” '), src, "text", where)
    for i, r in enumerate(out["reported"]):
        where = f"reported[{i}]"
        src = at(r, where)
        if isinstance(r, dict):
            words(r.get("text", ""), src, where)
            exact(str(r.get("when_said", "")), src, "when_said", where)
            evidence(r, src, where)
            spoken_by(r, src, where, me)
    for i, c in enumerate(out["complaints"]):
        where = f"complaints[{i}]"
        if not isinstance(c, dict):
            errs.append(f"{where}: not an object")
            continue
        tag = str(c.get("tag", ""))
        if not TAG.match(tag):
            errs.append(f"{where}: tag {tag!r} is not complaint/<kebab-name> or new:complaint/<kebab-name>")
        elif not tag.startswith("new:") and tag not in vocab:
            errs.append(f"{where}: tag {tag!r} is not in the vocabulary; mark it new:")
        for j, step in enumerate(c.get("course", []) if stitched else [c]):
            w = f"{where}.course[{j}]" if stitched else where
            src = at(step, w)
            if isinstance(step, dict):
                exact(str(step.get("intensity", "")), src, "intensity", w)
                if step.get("direction") not in DIRECTIONS:
                    errs.append(f"{w}: direction {step.get('direction')!r} is not one of {', '.join(sorted(DIRECTIONS))}")
    for i, d in enumerate(out["decisions"]):
        where = f"decisions[{i}]"
        src = at(d, where)
        if isinstance(d, dict):
            owners(src, d.get("line"), where, f"a decision is {owner}'s")
            if BOOKKEEPING.search(str(d.get("text", ""))):
                errs.append(f"{where}: telling Claude to file, commit or push is record work: it goes in `filed`")
            words(d.get("text", ""), src, where)
            words(d.get("why", ""), src, where + ".why")
            words(d.get("claude_reason") or "", text, where + ".claude_reason")
            evidence(d, src, where)
            spoken_by(d, src, where, me)
            why = str(d.get("why", "")).strip()
            said = str(d.get("why_evidence") or "").strip('"“” ')
            if why.lower() != NOT_STATED and (len(said.split()) < 3 or not any(_within(said, owner_words(t)) for t in turns.values())):
                errs.append(f'{where}: `why` is {owner}\'s stated reason, with his words in `why_evidence`, or "{NOT_STATED}"')
    for i, u in enumerate(out["updates"]):
        where = f"updates[{i}]"
        src = at(u, where)
        if isinstance(u, dict):
            for k in ("what", "before", "after"):
                words(u.get(k, ""), src, f"{where}.{k}")
            if not str(u.get("before", "")).strip() or not str(u.get("after", "")).strip():
                errs.append(f"{where}: an update gives `before` and `after`")
            evidence(u, src, where)
            if BOOKKEEPING.search(" ".join(str(u.get(k, "")) for k in ("what", "before", "after"))):
                errs.append(f"{where}: a change to {owner}'s record is record work: it goes in `filed`")
    for i, f in enumerate(out["filed"]):
        where = f"filed[{i}]"
        at(f, where)
        if isinstance(f, dict):
            words(f.get("what", ""), text, where)
    for i, c in enumerate(out["contradictions"]):
        where = f"contradictions[{i}]"
        lines = c.get("lines") if isinstance(c, dict) else None
        if not isinstance(lines, list) or len(lines) < 2 or any(x not in turns for x in lines):
            errs.append(f"{where}: `lines` must name two or more turns in this text")
        elif c.get("later") not in lines:
            errs.append(f"{where}: `later` must be one of its lines")
        if isinstance(c, dict):
            words(c.get("text", ""), text, where)
    for i, t in enumerate(out["topics"]):
        words(t, text, f"topics[{i}]")
    for i, o in enumerate(out["open"]):
        where = f"open[{i}]"
        at(o, where)
        if isinstance(o, dict):
            words(o.get("text", ""), text, where)
            src = turns.get(o.get("line")) if isinstance(o.get("line"), int) else None
            evidence(o, src, where)
            ev = str(o.get("evidence", "")).strip('"“” ')
            if src and claude_words(src) and _asks(ev, owner_words(src)):
                errs.append(f"{where}: {owner}'s question was met by Claude's reply in the same turn; an open item quotes words "
                            f"saying it is still unresolved (Claude's, or {owner}'s in a later turn), or it isn't open")
            if BOOKKEEPING.search(str(o.get("text", ""))):
                errs.append(f"{where}: an open item about {owner}'s record is record work: it goes in `filed`")
    tenor = out["tenor"]
    words(tenor.get("arc" if stitched else me, ""), text, "tenor")
    for i, q in enumerate(tenor.get("quotes", []) or []):
        src = at(q, f"tenor.quotes[{i}]")
        if isinstance(q, dict):
            exact(str(q.get("text", "")).strip('"“” '), src, "text", f"tenor.quotes[{i}]")
    return errs


BY_RULES = """Who each claim is from. Code works out who said it in the conversation, from where its evidence sits. You give:
- `relayed_from`: "own" when the speaker says it as their own ({owner}'s report or view; Claude's analysis or advice). "{owner_id}" when Claude passes on {owner}'s own earlier report, from his brief, his record or an earlier session (his symptoms, triggers, observations): it's {owner}'s, as Claude relays it. Or the source the speaker is passing on: "clinician:<name> (<role>)" for what a clinician said, found or set, including findings in an exam, test or visit note (by role alone, like "clinician:ENT", when no one is named); "other:<source>" for anything else, such as an article, a newsletter or a person. Test and lab results are findings: credit the clinician who ordered or read them, by role when unnamed ("clinician:allergist", "clinician:lab"). Claude's own subagents, checks and tools are part of Claude: what they found or advised, relayed by Claude, is relayed_from "own".
- `act`, what kind of statement it is: "report" (something that happened, or that {owner} feels), "finding" (a test or exam result), "analysis" (an interpretation or explanation), "advice" (what someone should do), "plan" (what will happen), "question" (still unanswered), or "record" (record work, see below). A decision of {owner}'s goes in `decisions`.
- Advice is quoted exactly: set "quote": true and copy the whole instruction, with its conditions ("more than a few days, especially with a fever").
- Record work is everything about keeping {owner}'s record: Claude filing, logging, noting, editing, committing or pushing; Claude offering to add something or asking for a detail so it can log it; {owner} asking Claude to file, commit or push, or approving an entry. Record work goes only in `filed`, in a few words; it is never a claim, a decision, an update or an open item.
- For Claude's analysis or advice that {owner} took up in a later turn (he agreed with it, acted on it, or built on it): `taken_up_at`, that turn's line, and `uptake_evidence`, his own words there. "ok", asking for an explanation, not objecting, reporting something he had already done, or asking for a draft he hasn't used is not taking it up.
- `raised_first_at` and `raised_first_evidence`: the line where the idea first came up, and the words there that raised it. When {owner} raised it first, even as a question in the same turn Claude answered, the idea is his: credit it to him with his words as evidence; what Claude added is a separate claim.
A claim that mixes words from different sources becomes separate claims.

Examples, in pairs: each second line looks like the first but is labelled differently.
- {owner}: "the allergist said to take it at night" → relayed_from "clinician:allergist", act "advice".
  {owner}: "I take it at night" → relayed_from "own", act "report".
- Claude: "Logged: started the drops today." → act "record" (it goes to `filed`).
  Claude: "The drops take about two weeks to work." → relayed_from "own", act "analysis".
- Claude: "Noted in your log, not a pattern yet." → act "record".
  Claude: "Want me to add the visit outcome to your record?" or "Tell me the day you move it and I'll split the readings in the log" → record work, in `filed`.
  Claude: "Move it to the desk for a week to compare" → advice, quoted.
  {owner}: "commit and push" → record work, in `filed`; not a decision.
  Claude: "One flare after the run isn't a pattern yet." → relayed_from "own", act "analysis", confidence "isn't a pattern yet".
- Claude, reading back {owner}'s brief: "the itch comes with heat, scented detergent and the carpeted corner" → relayed_from "{owner_id}", act "report".
  Claude: "heat as the clearest trigger points toward an irritant reflex" → relayed_from "own", act "analysis".
- Claude, relaying its drug-check subagent: "the interaction check says to stop it" → relayed_from "own" (the subagent is Claude).
  Claude, relaying the visit note: "the optometrist noted dry eye" → relayed_from "clinician:optometrist".
- Claude, reading the visit note: "IOP 19 right eye." → relayed_from "clinician:optometrist" (the exam's clinician, by role), act "finding".
  Claude: "19 is high-normal and could explain the pressure feeling." → relayed_from "own", act "analysis", confidence "could".
- Claude: "Start once daily, as the consult said." {owner}: "ok once daily" → a decision with why "not stated" and claude_reason "as the consult said". His "ok" doesn't take up the reasoning.
  {owner}: "once daily, twice made my throat sore" → a decision with why "twice made my throat sore", his words in why_evidence.
- {owner} (L10): "maybe I should ask support first". Claude (L12): "asking support first usually gets a faster answer" → {owner}'s idea: the claim cites L10 with his words; raised_first_at 10, raised_first_evidence "maybe I should ask support first".
  {owner} (L40): "should I just go to a private place?" Claude, same turn: "Yes, go private" → the idea is {owner}'s (raised_first_at 40, raised_first_evidence "should I just go to a private place"); Claude's how-to is a separate claim.
  Claude (L12): "ask support first". {owner} (L14): "good call, sending it now" → Claude's advice, taken_up_at 14, uptake_evidence "good call, sending it now".
- Claude (L50): "start with your allergist". {owner} (L60): "prep a consult with my allergist" → taken up: he acted on it.
  Claude (L50): "put the sensor at the desk". {owner} (L60): "not the desk yet, a few weeks here first" → not taken up: he deferred it with his own plan.
  Claude (L50) describes how an urge feels. {owner} (L60): "great description of how it feels to me" → taken up: he agreed with it.
- Claude (L30): "stop the old drops once the new ones start". {owner} (L34): "i stopped the old drops" (he already had) → his report, act "report"; Claude's advice is not taken up.
  Claude (L30): "stop the old drops tonight". {owner} (L34): "ok, stopping them tonight" → taken_up_at 34, uptake_evidence "ok, stopping them tonight".
- {owner}: "had my trigger point visit at the pain clinic; the nerve block is on hold" (no one said who put it on hold) → the hold is {owner}'s report, not the clinic's decision.
  {owner}: "the pain clinic doctor said to hold the nerve block" → relayed_from "clinician:pain clinic doctor".
- Claude (L20): "try 1–2 puffs twice a day". {owner} (L24): "they said once a day" → an update: before "1–2 puffs twice a day", after "once a day"; and a claim relayed_from "clinician:asthma clinic". Not a contradiction.
  An exam note says "no reflux" while the ENT says "reflux likely", both standing → a contradiction.
- Claude: "you could try a 30-second head-tilt test" → relayed_from "own", act "advice".
  {owner}: "I'll do the head-tilt test tomorrow" → relayed_from "own", act "plan", his words as evidence."""

SEGMENT_PROMPT = """You summarize one segment of a conversation between {owner} and Claude, his {domain} advisor, so it can be searched later. The summary stands in for the conversation, so it must be faithful: say what the turns say, no more and no less.

{place}

Each turn is headed [L<line> · <date time>] and opens with who wrote it: "{owner}" (his own words), "{owner} (while Claude worked)" (a message he sent mid-turn), "Prompt" (a program or launcher wrote it, not {owner}), "Skill loaded" (instructions Claude loaded) or "Another Claude session". Claude's replies follow "Claude:". Cite every item by its turn's line number.

{by_rules}

Every claim, report and decision carries `evidence`: a phrase of 4 to 20 words, copied exactly from the cited turn, in the words of the person the item credits: the words the item rests on, including any qualifier in them ("would suggest", "kind of", "if ..."). It is shown beside the item, so the speaker's own nuance travels with it.

`confidence` is the claimant's own words for how sure they are, copied exactly from anywhere in that turn (like "Established.", "my hunch is" or "I'd hold both fairly firmly"). Words for a choice ("I'd pick") aren't confidence. Use "unstated" only when the turn has none.

Faithfulness:
- Keep every hedge, condition and direction: "perhaps", "roughly", "would suggest", "if it was properly anesthetized", which way a number moved, which risk is called the real one. When a detail matters, quote it.
- When Claude advises {owner} to do something, the item keeps the advice itself ("Keep taking it"), not only the topic.
- {owner}'s short messages say only what they say. Quote them rather than interpret them.
- When a later turn changes a status (a task finished, a plan dropped), keep only the latest status.
- Quotation marks mean word for word. Set "quote": true only when the whole claim text is copied exactly. Otherwise the claim is a paraphrase, and it has quotation marks only around words copied exactly.
- The date on a turn is when something was said; say when something happened only when the turn says so ("10-08: reported tight calves after the weekend's hike").
- Never write a date that isn't written in the segment. Keep fuzzy times in the speaker's words in `reported`, with `when_said` copied exactly.
- Never mention that text was cut.
- Read abbreviations and shorthand in context ("OD" can mean the right eye or an optometrist); when unsure, quote them as written.
- When {owner} answers a numbered list, keep what each number refers to.

What to keep:
- Each fact once: merge repeats.
- Findings, reports, decisions, open questions, and how {owner} felt. Drop Claude's process, even when it runs over several turns: what it is checking or about to do, waiting, retries, its own tool or permission trouble. What Claude's receipts say it filed ("Committed: logged a possible nerve link") is record work, not a claim made in the session.
- `filed`: what Claude wrote to {owner}'s record in these turns (its receipts: "Added to your derm history: ...", "Filed: ...", a med-list write, a commit), each with what and where. These are never claims; what they record is a claim only from its own source.
- `decisions`: only what {owner} decided, cited at his turn. `why` is the reason {owner} gave, in this turn or an earlier one, with his own words in `why_evidence`; when he gave none anywhere, `why` is "not stated". A reason Claude gave goes in `claude_reason`, never in `why`. Claude's plans and labels are claims.
- `updates`: something that changed within these turns: a plan, an estimate, a dose, a date corrected, advice revised, an analysis of Claude's that a later turn corrected. Give `before` and `after`, cite the later turn with `evidence` copied from it, and name the earlier one in `earlier_line`. Only the latest version stands in claims and `open`.
- `open`: questions still unresolved at the end. Each cites the latest turn that bears on it, and its `evidence` quotes words there showing it is still unresolved ("we'll know after the test", "haven't booked it yet", "not sure yet"). A question answered in the same turn it was asked, or in any later turn, has no such words: it isn't open. {owner}'s question itself is never the evidence when Claude replied to it. What someone should or will do is a claim (act "advice" or "plan") at its own turn, not an open item.
- `contradictions`: two statements that can't both be true of the same thing at the same time, such as something Claude recorded and {owner}'s later report, Claude reversing itself, or two sources disagreeing. Give both lines and which is later. A change over time (a plan changed, a task got done, a later reading on a later day) is not a contradiction: keep the latest status.
- `complaints`: each symptom {owner} reports. `tag` is "new:complaint/<short-kebab-name>"{vocab}. `intensity` is copied exactly from his words, or "". `direction` is better, worse, same, new (the first time ever), back (returned after a gap), gone or unclear, and unclear unless his words say which. One entry per symptom per turn: don't split one sensation into several tags.
- `tenor`: how {owner} came across and how that changed over these turns, in a sentence or two (where he started, where he ended), plus up to 3 short quotes of his, copied exactly. Read his words as they are: don't soften anger or invent calm.
- At most {claims_cap} claims, each under 300 characters. Any list can be empty.

Reply with JSON only, in this shape:
{"topics": ["..."],
 "claims": [{"line": 0, "text": "...", "relayed_from": "own", "act": "report|finding|analysis|plan", "taken_up_at": null, "uptake_evidence": null, "raised_first_at": null, "raised_first_evidence": null, "confidence": "...", "basis": "...", "evidence": "...", "quote": false},
            {"line": 0, "text": "<the advice, copied exactly with its conditions>", "relayed_from": "own", "act": "advice", "taken_up_at": null, "uptake_evidence": null, "raised_first_at": null, "raised_first_evidence": null, "confidence": "...", "basis": "...", "evidence": "<the same words>", "quote": true}],
 "reported": [{"line": 0, "text": "...", "when_said": "...", "evidence": "..."}],
 "complaints": [{"line": 0, "tag": "...", "intensity": "...", "direction": "..."}],
 "decisions": [{"line": 0, "text": "...", "why": "...", "why_evidence": "...", "claude_reason": null, "evidence": "..."}],
 "updates": [{"line": 0, "earlier_line": 0, "what": "...", "before": "...", "after": "...", "evidence": "..."}],
 "contradictions": [{"lines": [0, 0], "text": "...", "later": 0}],
 "filed": [{"line": 0, "what": "...", "where": "..."}],
 "open": [{"line": 0, "text": "...", "evidence": "..."}],
 "tenor": {"{owner_id}": "...", "quotes": [{"line": 0, "text": "..."}]}}

The segment:
<<<
"""

STITCH_PROMPT = """You join the summaries of consecutive parts of one conversation between {owner} and Claude, his {domain} advisor, into one summary of the whole. Consecutive parts overlap, and the raw text of the overlapping turns is given so you can merge repeats.

{by_rules}

Each part summary saw only its own turns. So a part may leave untaken a suggestion of Claude's that a later part shows {owner} took up: then set `taken_up_at` and `uptake_evidence` to his turn. And a part may list as open something a later part settles: then it leaves `open`.

Rules:
- Merge repeats. Keep each item's line, relayed_from, act, taken_up_at, uptake_evidence, raised_first_at, confidence, basis, evidence and quote exactly as the parts give them.
- When two parts label the same claim differently, decide from the raw overlapping turns, using the rules above.
- Add no claim the parts don't make, and no reason they don't give.
- When a later part changes a status (a task finished, a plan dropped), keep only the latest status, in `chronology` and in `open`.
- `contradictions`: keep the ones the parts record, and add any between parts: something recorded earlier that a later turn contradicts. A change over time (a plan changed, a task got done) is not a contradiction.
- `filed` and `updates` merge across parts like the rest; an update between parts goes in `updates`. An open item a later part settles leaves `open`.
- `chronology`: the claims in order. Drop intermediate steps.
- `complaints`: one entry per complaint tag, with its course in order.
- `tenor`: the arc of how {owner} came across over the whole, plus up to 5 quotes taken from the part summaries.
- Quotation marks mean word for word. Write no date that isn't in the input. At most {cap} chronology items, each under 300 characters.

Reply with JSON only, in this shape:
{"topics": ["..."],
 "chronology": [{"line": 0, "text": "...", "relayed_from": "own", "act": "report|finding|analysis|plan", "taken_up_at": null, "uptake_evidence": null, "raised_first_at": null, "raised_first_evidence": null, "confidence": "...", "basis": "...", "evidence": "...", "quote": false},
                {"line": 0, "text": "<the advice, copied exactly with its conditions>", "relayed_from": "own", "act": "advice", "taken_up_at": null, "uptake_evidence": null, "raised_first_at": null, "raised_first_evidence": null, "confidence": "...", "basis": "...", "evidence": "<the same words>", "quote": true}],
 "reported": [{"line": 0, "text": "...", "when_said": "...", "evidence": "..."}],
 "complaints": [{"tag": "...", "course": [{"line": 0, "intensity": "...", "direction": "..."}]}],
 "decisions": [{"line": 0, "text": "...", "why": "...", "why_evidence": "...", "claude_reason": null, "evidence": "..."}],
 "updates": [{"line": 0, "earlier_line": 0, "what": "...", "before": "...", "after": "...", "evidence": "..."}],
 "contradictions": [{"lines": [0, 0], "text": "...", "later": 0}],
 "filed": [{"line": 0, "what": "...", "where": "..."}],
 "open": [{"line": 0, "text": "...", "evidence": "..."}],
 "tenor": {"arc": "...", "quotes": [{"line": 0, "text": "..."}]}}

"""


def _claude(prompt: str, model: str) -> tuple[str, dict]:
    effort = STITCH_EFFORT if model == STITCH_MODEL and model != SEGMENT_MODEL else SEGMENT_EFFORT
    text, used = llm.ask(prompt, SYSTEM, model=model, effort=effort)
    return text.strip(), used


def _add(a: dict, b: dict) -> dict:
    return {k: round(a.get(k, 0) + b.get(k, 0), 6) for k in ("in", "out", "usd")}


FAILED_ITEM = re.compile(r"^(claims|chronology|reported|complaints|decisions|updates|contradictions|filed|open|topics)\[(\d+)\]"
                         r"|^tenor\.quotes\[(\d+)\]")


def _drop_failing(out: dict, errs: list[str]) -> tuple[dict, list]:
    """After the retry, the items lint still names are dropped, so one bad item doesn't cost the whole summary."""
    drop: dict[tuple, set[int]] = {}
    for e in errs:
        m = FAILED_ITEM.match(e)
        if not m:
            continue
        if m.group(1):
            drop.setdefault((m.group(1),), set()).add(int(m.group(2)))
        else:
            drop.setdefault(("tenor", "quotes"), set()).add(int(m.group(3)))
    dropped = []
    for path, idx in drop.items():
        parent = out if len(path) == 1 else out.get(path[0], {})
        items = parent.get(path[-1], [])
        dropped += [items[i] for i in sorted(idx) if i < len(items)]
        parent[path[-1]] = [x for i, x in enumerate(items) if i not in idx]
    return out, dropped


def _ask(prompt: str, model: str, turns: dict[int, str], text: str, vocab: set[str], stitched: bool, cap: int | None = None,
         reach: dict[int, str] | None = None) -> dict:
    """One call, linted; a failure is retried once with its errors; a second failure flags it."""
    reply, used = _claude(prompt, model)
    out = characterize(llm.parse(reply), turns, stitched)
    errs = lint(out, turns, text, vocab, stitched, cap, reach) if out is not None else ["the reply is not JSON"]
    tries = 1
    if errs:
        retry = (prompt + "\n\nYour previous reply failed these checks. Reply again with the whole JSON, fixed:\n- "
                 + "\n- ".join(errs[:40]) + "\n\nYour previous reply:\n" + reply[:20000])
        reply2, used2 = _claude(retry, model)
        used = _add(used, used2)
        out2 = characterize(llm.parse(reply2), turns, stitched)
        errs2 = lint(out2, turns, text, vocab, stitched, cap, reach) if out2 is not None else ["the reply is not JSON"]
        tries = 2
        if out2 is not None or out is None:
            out, errs = out2, errs2
    dropped = []
    if errs and isinstance(out, dict):
        out, dropped = _drop_failing(out, errs)
        errs = lint(out, turns, text, vocab, stitched, cap, reach)
    return {"summary": out, "lint": errs, "flagged": bool(errs), "tries": tries, "usage": used, "dropped": dropped}


def vocabulary() -> set[str]:
    p = data_path("summaries") / "vocabulary.txt"
    return {l.strip() for l in p.read_text().splitlines() if l.strip()} if p.exists() else set()


REFINE = """

That was the segment. Below is a first reading of it, and, when there are any, first readings of the segments just before and after it, made separately. Audit the first reading of this segment against the turns above, and fix what fails:
- Every item: do the turns say it, no more? Put back dropped hedges and confidence words; add what the turns hold that the first reading missed.
- Every analysis or guess of Claude's: does a later turn correct it, by {owner}'s answer or Claude's own revision? Then the later stands, and the change goes in `updates`.
- Every open item and every claim about how something stands (waiting, unresponsive, not booked, still burning): read the last turns again; if any later turn answers, settles, drops or changes it, it isn't open, and the change goes in `updates`.
- Every claim or decision whose status the turns later change (an estimate corrected, a plan set aside, a task done): only the latest stands; the change goes in `updates`.
- Every advice or analysis of Claude's: read {owner}'s later turns. If he acted on it or agreed with it, it is taken up (`taken_up_at`, `uptake_evidence`); if he deferred it, set his own plan, or didn't respond, it isn't. Reporting something he had already done ("i stopped it") is not taking it up.
- Every idea credited to Claude: did {owner} raise it first, in an earlier turn? Then it's his, at his turn.
- Every finding from an exam, test or visit note: credited to the clinician, by role when unnamed, never to Claude or "the record".
- Every named clinician or clinic: does the turn tie this statement to them? If not, don't name them.
- Any record work (filing, logging, committing, offers or requests to log, {owner} approving an entry) in claims, decisions, updates or open: move it to `filed`.
- Every advice item: quoted exactly, the whole instruction with its conditions.
- Every finding or advice from Claude's own subagent or check: relayed_from "own".
- Use the neighbouring readings only to judge what came before and after: whether {owner} took an idea up later (then the claim is with-claude, with `taken_up_at` at his turn, which may be in the next segment), whether a status changed, whether something was already decided. They may hold mistakes.
- Every item must still be about these turns and cite one of them, with `evidence` copied from it. Never move an item in from a neighbouring segment.

Reply with the revised JSON only, in the same shape.
"""




def _place(n: int, total: int, title: str, day: str) -> str:
    """Tells the segment model it sees a window of a session, so it doesn't treat the window as the whole story."""
    session = f'one session ("{title}", from {day})' if title else f"one session, from {day}"
    if total == 1:
        return (f"This segment is the whole of {session}. `open` holds only what is still open at its end: drop a question "
                "a later turn answered.")
    where = [f"This is segment {n} of {total} from {session}."]
    where.append("It starts the session." if n == 1 else "Its first turns repeat the end of the segment before it.")
    where.append("It ends the session." if n == total else "The session goes on after it.")
    return " ".join(where) + """ You see only these turns, so:
- What looks settled here may have been decided earlier or reversed later. Report statuses as of these turns, and call nothing final or resolved unless the turns do.
- Don't conclude that something wasn't said or done because it isn't here.
- An analysis of Claude's that {owner} hasn't taken up within these turns is a claude-suggestion. A later segment may show him taking it up; the next step judges that.
- `open` holds what is still open at the end of these turns: drop a question a later turn answered."""


def _refine_prompt(domain: str, text: str, vocab: set[str], place: str, near: list) -> str:
    """The second pass: the segment again, with the first readings of its neighbours and its own."""
    ctx = zip(("before", "this segment, first reading", "after"), near)
    refine = REFINE
    if r := rules(domain):
        refine = refine.replace("\nReply with the revised JSON only", r[2] + "\nReply with the revised JSON only")
    return (_segment_prompt(domain, text, vocab, place) + config.voice(refine)
            + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in ctx if v))


def claims_cap(text: str) -> int:
    """25 claims per 12,000 characters, so a larger chunk may hold more."""
    return CLAIMS_CAP * max(1, -(-len(text) // 12000))


def _segment_prompt(domain: str, text: str, vocab: set[str], place: str) -> str:
    known = f', or one of these without "new:": {", ".join(sorted(vocab))}' if vocab else ""
    prompt = SEGMENT_PROMPT
    if r := rules(domain):
        prompt = prompt.replace("\nReply with JSON only, in this shape:", r[1] + "\nReply with JSON only, in this shape:")
    return config.voice(prompt.replace("{domain}", domain).replace("{place}", place).replace("{by_rules}", BY_RULES)
                        .replace("{vocab}", known).replace("{claims_cap}", str(claims_cap(text)))) + text + "\n>>>"


def _stitch_prompt(domain: str, parts: list[dict], overlaps: list[Turn], cap: int) -> str:
    body = "Part summaries, in order:\n" + "\n".join(
        json.dumps({"part": i, "first_line": s["first_line"], "last_line": s["last_line"], **(s["summary"] or {})}, ensure_ascii=False)
        for i, s in enumerate(parts, 1))
    body += "\n\nOverlapping turns, raw:\n<<<\n" + render_turns(overlaps) + "\n>>>"
    return config.voice(STITCH_PROMPT.replace("{domain}", domain).replace("{by_rules}", BY_RULES).replace("{cap}", str(cap))) + body


def chronology_cap(segments_: int) -> int:
    return max(CHRONOLOGY_CAP, 6 * segments_)


def _overlaps(groups: list[list[Turn]]) -> list[Turn]:
    seen, out = set(), []
    for g in groups:
        for t in g:
            if t.line in seen and t not in out:
                out.append(t)
            seen.add(t.line)
    return out


def _stitch(domain: str, segs: list[dict], seg_turns: list[list[Turn]], vocab: set[str]) -> dict:
    """Up to GROUP segment summaries in one Opus call. A longer session is stitched in groups of GROUP that share a
    segment, and the group summaries are stitched once more, so no call reads a whole long session at once."""
    def lines_of(groups):
        turns = {t.line: t for g in groups for t in g}
        return {k: t.text for k, t in turns.items()}, render_turns(sorted(turns.values(), key=lambda t: t.line))

    if len(segs) <= GROUP:
        lines, text = lines_of(seg_turns)
        cap = chronology_cap(len(segs))
        return _ask(_stitch_prompt(domain, segs, _overlaps(seg_turns), cap), STITCH_MODEL, lines, text, vocab, True, cap)
    parts, used, shared = [], {}, []
    for k in range(0, len(segs), GROUP - 1):
        part = _stitch(domain, segs[k:k + GROUP], seg_turns[k:k + GROUP], vocab)
        used = _add(used, part["usage"])
        parts.append({"first_line": seg_turns[k][0].line, "last_line": seg_turns[min(k + GROUP, len(segs)) - 1][-1].line,
                      "summary": as_part(part["summary"] or {})})
        if k + GROUP >= len(segs):
            break
        shared += seg_turns[k + GROUP - 1]
    lines, text = lines_of(seg_turns)
    cap = chronology_cap(len(segs))
    final = _ask(_stitch_prompt(domain, parts, shared, cap), STITCH_MODEL, lines, text, vocab, True, cap)
    return {**final, "parts": len(parts), "usage": _add(final["usage"], used)}


def as_session(seg: dict) -> dict:
    """A one-segment session needs no stitching: its segment summary, in the session shape."""
    return {"topics": seg.get("topics", []), "chronology": seg.get("claims", []), "reported": seg.get("reported", []),
            "complaints": [{"tag": c.get("tag"), "course": [{k: c.get(k) for k in ("line", "intensity", "direction")}]}
                           for c in seg.get("complaints", [])],
            "decisions": seg.get("decisions", []), "contradictions": seg.get("contradictions", []), "open": seg.get("open", []),
            **{k: seg.get(k, []) for k in ("updates", "filed")},
            "tenor": {"arc": seg.get("tenor", {}).get(config.owner_id(), ""), "quotes": seg.get("tenor", {}).get("quotes", [])}}


def as_part(st: dict) -> dict:
    """A group's stitched summary, in the shape the final stitch reads."""
    return {"topics": st.get("topics", []), "claims": st.get("chronology", []), "reported": st.get("reported", []),
            "complaints": [{"tag": c.get("tag"), **step} for c in st.get("complaints", []) for step in c.get("course", [])],
            "decisions": st.get("decisions", []), "contradictions": st.get("contradictions", []), "open": st.get("open", []),
            **{k: st.get(k, []) for k in ("updates", "filed")},
            "tenor": {config.owner_id(): st.get("tenor", {}).get("arc", ""), "quotes": st.get("tenor", {}).get("quotes", [])}}


def _versions(stored: dict | None) -> dict:
    v = (stored or {}).get("prompt_version")
    return v if isinstance(v, dict) else {"segment": v, "stitch": v}


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def store_dir(domain: str) -> Path:
    return data_path("summaries") / domain


def _write(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(p)


def _load_session(path: Path) -> sessions.Session | None:
    """The session file, or the second box's mirror copy of one Claude Code has since cleaned up."""
    root = sessions.ROOT
    if path.exists():
        return sessions.parse(path, root)
    if not (host := daily.box()):
        return None
    rel = path.relative_to(root)
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", host, f"cat '{daily.SESSIONS}{rel}'"], capture_output=True, timeout=300)
    if r.returncode:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / rel
        local.parent.mkdir(parents=True)
        local.write_bytes(r.stdout)
        s = sessions.parse(local, Path(tmp))
    s.path = path
    return s


def _settled(path: Path, domain: str) -> bool:
    """A session cleaned up from this box can't grow, so it's fetched from the mirror again only if a prompt moved or
    its summary was lost; one a program started has no turn of the owner's to summarize. Keeps the hourly job off the
    network for sessions nothing can change, which matters once a harness's thousands of runs age out."""
    if any(m in path.parent.name for m in _launched()):
        return True
    p = store_dir(domain) / f"{path.stem}.json"
    return p.exists() and "days" in (stored := json.loads(p.read_text())) and \
        _versions(stored) == {"segment": segment_version(domain), "stitch": STITCH_VERSION}


def known_sessions(domain: str | None = None, stems: list[str] | None = None) -> list[tuple[Path, str]]:
    """Main sessions filed into a domain; subagents are skipped, since their outcome is in the parent session. Naming
    a session reads it whatever its state."""
    st = sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)
    doms = list(config.load())
    rows = st.execute(f"SELECT path, domain, gone FROM file WHERE domain IN ({', '.join('?' * len(doms))}) "
                      "AND path NOT LIKE '%/subagents/%' ORDER BY path", doms).fetchall()
    st.close()
    out = []
    for path, dom, gone in rows:
        p = Path(path)
        if domain and dom != domain or stems and p.stem not in stems:
            continue
        if not gone and p.exists() and datetime.now().timestamp() - p.stat().st_mtime < IDLE.total_seconds():
            continue
        if not stems and not p.exists() and _settled(p, dom):
            continue
        out.append((p, dom))
    return out


def plan(path: Path, domain: str) -> dict | None:
    """What summarizing a session would take, and whether its stored summary is current. None when the session can't
    be read; `empty` when it has no turn of the owner's."""
    s = _load_session(path)
    if s is None:
        return None
    turns = clean(sessions.from_start(s, (d := config.load().get(domain)) and d.repo))
    if not turns:
        return {"path": path, "domain": domain, "empty": True}
    segs = segments(turns)
    texts = [render_turns(seg) for seg in segs]
    # the last segment is told the session ends there, so it's redone once the session grows past it
    shas = [_sha(segment_version(domain) + ("|last" if i == len(texts) - 1 else "") + t) for i, t in enumerate(texts)]
    stored_p = store_dir(domain) / f"{path.stem}.json"
    stored = json.loads(stored_p.read_text()) if stored_p.exists() else None
    current = (bool(stored) and _versions(stored) == {"segment": segment_version(domain), "stitch": STITCH_VERSION}
               and [g["sha"] for g in stored["segments"]] == shas)
    return {"path": path, "domain": domain, "session": s, "turns": turns, "segs": segs, "texts": texts, "shas": shas,
            "stored": stored, "current": current, "chars": sum(len(t) for t in texts)}


def _days(turns: list[Turn]) -> dict[str, str]:
    """The day each turn was said, by its line."""
    return {str(t.line): t.ts[:10] for t in turns}


def complete(pl: dict) -> bool:
    """A current summary made before each turn's day and each update's speaker were kept gets them from its session,
    with no model call: in the stitched summary and in every segment's, which a later stitch is rebuilt from. One
    cleaned up from this box is fetched from the mirror for it (`_settled`) until it has them; while it can't be read,
    it stays as it was."""
    data = pl["stored"]
    if "days" in data:
        return False
    lines = {t.line: t.text for t in pl["turns"]}
    for summary in [(data.get("stitch") or {}).get("summary"), *(g.get("summary") for g in data.get("segments") or [])]:
        _speakers(summary, lines)
    _write(store_dir(pl["domain"]) / f"{pl['path'].stem}.json", {**data, "days": _days(pl["turns"])})
    return True


def summarize_session(pl: dict, vocab: set[str]) -> tuple[dict, dict]:
    """The session's summary, stored, and what this call spent; the stored usage is the session's running total."""
    s, domain, turns, segs = pl["session"], pl["domain"], pl["turns"], pl["segs"]
    old = {g["sha"]: g for g in (pl["stored"] or {}).get("segments", []) if _versions(pl["stored"])["segment"] == segment_version(domain)}
    out_segs, used, fresh = [], {}, False
    all_lines = {t.line: t.text for t in turns}
    places = [_place(i, len(segs), s.title, turns[0].ts[:10]) for i in range(1, len(segs) + 1)]
    for i, (seg, text, sha) in enumerate(zip(segs, pl["texts"], pl["shas"])):
        if sha in old:
            g = {**old[sha], "segment": i + 1}
        else:
            fresh = True
            g = {"segment": i + 1, "first_line": seg[0].line, "last_line": seg[-1].line, "start": seg[0].ts, "end": seg[-1].ts,
                 "sha": sha, "first": _ask(_segment_prompt(domain, text, vocab, places[i]), SEGMENT_MODEL,
                                           {t.line: t.text for t in seg}, text, vocab, False, claims_cap(text))}
            used = _add(used, g["first"]["usage"])
        out_segs.append(g)
    # The second pass re-reads each segment with its neighbours' first readings, and is redone when any of them changes.
    # It stands unless it fails lint where the first reading passed.
    for i, (seg, text, g) in enumerate(zip(segs, pl["texts"], out_segs)):
        near = [out_segs[j]["first"]["summary"] if 0 <= j < len(out_segs) else None for j in (i - 1, i, i + 1)]
        ctx = _sha(json.dumps(near, sort_keys=True)) if SECOND_PASS else "one pass"
        if g.get("context") == ctx and "summary" in g:
            continue
        fresh = True
        second, pick = None, g["first"]
        if SECOND_PASS and g["first"]["summary"] is not None:
            second = _ask(_refine_prompt(domain, text, vocab, places[i], near), SEGMENT_MODEL, {t.line: t.text for t in seg},
                          text, vocab, False, claims_cap(text), reach=all_lines)
            used = _add(used, second["usage"])
            if not second["flagged"] or g["first"]["flagged"]:
                pick = second
        g.update({"summary": pick["summary"], "lint": pick["lint"], "flagged": pick["flagged"], "context": ctx,
                  "pass": "second" if pick is second else "first",
                  "second": second and {k: second[k] for k in ("lint", "flagged", "tries", "usage")}})
    full = render_turns(turns)
    prev = pl["stored"] or {}
    if len(out_segs) == 1:
        session = as_session(out_segs[0]["summary"] or {})
        # its chronology is the segment's claims, so a long segment's own cap holds
        cap = max(chronology_cap(1), claims_cap(full))
        stitch = {"summary": session, "lint": lint(session, all_lines, full, vocab, True, cap), "tries": 0, "usage": {}}
        stitch["flagged"] = bool(stitch["lint"])
        stitch_model = None
    elif not fresh and prev.get("stitch") and _versions(prev)["stitch"] == STITCH_VERSION:
        stitch, stitch_model = prev["stitch"], prev["models"].get("stitch")
    else:
        stitch = _stitch(domain, out_segs, segs, vocab)
        used = _add(used, stitch["usage"])
        stitch_model = STITCH_MODEL
    data = {"stem": s.stem, "domain": domain, "path": str(pl["path"]), "title": s.title, "project": s.project,
            "prompt_version": {"segment": segment_version(domain), "stitch": STITCH_VERSION}, "models": {"segment": SEGMENT_MODEL, "stitch": stitch_model}, "made": now(),
            "turns": len(turns), "first": turns[0].ts, "last": turns[-1].ts, "days": _days(turns),
            "segments": out_segs, "stitch": stitch,
            "flagged": [g["segment"] for g in out_segs if g["flagged"]] + (["stitch"] if stitch["flagged"] else []),
            "usage": _add(prev.get("usage", {}) if pl["stored"] else {}, used)}
    _write(store_dir(domain) / f"{s.stem}.json", data)
    for other in config.load():
        if other != domain:
            (store_dir(other) / f"{s.stem}.json").unlink(missing_ok=True)
    return data, used


def run(domain: str | None = None, stems: list[str] | None = None, limit: int | None = None, workers: int = 4,
        sample: int | None = None, seed: str = "") -> dict:
    """Summarize every session whose stored summary is missing or out of date. A failed call stops the run;
    the sessions finished before it are kept, and the next run picks up the rest."""
    vocab = vocabulary()
    broken = {d for d in config.load() if pack.problem(d)}  # without its pack a domain's rules are missing: its sessions wait
    todo = [x for x in known_sessions(domain, stems) if x[1] not in broken]
    if sample:
        todo = sorted(todo, key=lambda x: _sha(seed + x[0].stem))
    counts = {"summarized": 0, "current": 0, "flagged": 0, "usage": {}, "stopped": None}
    stop = threading.Event()
    lock = threading.Lock()
    picked = 0

    cap = limit or sample

    def one(item):
        nonlocal picked
        if stop.is_set() or (cap and picked >= cap):
            return
        pl = plan(*item)
        if pl is None:
            return
        if pl.get("empty"):  # a summary made before its session was known to be a program's run
            (store_dir(pl["domain"]) / f"{pl['path'].stem}.json").unlink(missing_ok=True)
            return
        with lock:
            if pl["current"]:
                complete(pl)
                counts["current"] += 1
                return
            if cap and picked >= cap:
                return
            picked += 1
        try:
            data, spent = summarize_session(pl, vocab)
        except Unavailable as e:
            stop.set()
            counts["stopped"] = str(e)
            return
        with lock:
            counts["summarized"] += 1
            counts["flagged"] += bool(data["flagged"])
            counts["usage"] = _add(counts["usage"], spent)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    return counts


def estimate(domain: str | None = None) -> dict:
    """Calls and list-price dollars a full run would take, before anything is spent, from what summaries already made
    cost: a Haiku call per segment, and Opus stitching that grows with the segments it reads. A session over GROUP
    segments is priced at 1.5 times, for its group stitches and the final one."""
    made = [json.loads(p.read_text()) for p in (data_path("summaries")).glob("*/*.json")]
    seg_calls = [{"usage": _add((g.get("first") or g).get("usage") or {}, (g.get("second") or {}).get("usage") or {})}
                 for d in made for g in d["segments"] if (g.get("first") or g).get("usage")]
    stitched = [d for d in made if d["stitch"].get("usage")]
    per_seg = sum(g["usage"]["usd"] for g in seg_calls) / len(seg_calls) if seg_calls else None
    per_stitched_seg = (sum(d["stitch"]["usage"]["usd"] for d in stitched) / sum(len(d["segments"]) for d in stitched)
                        if stitched else None)
    out: dict = {}
    for path, dom in known_sessions(domain):
        pl = plan(path, dom)
        if pl is None or pl.get("empty"):
            continue
        o = out.setdefault(dom, {"sessions": 0, "current": 0, "segments": 0, "stitched_sessions": 0, "stitched_segments": 0,
                                 "chars": 0, "usd_list": 0.0})
        if pl["current"]:
            o["current"] += 1
            continue
        n = len(pl["segs"])
        o["sessions"] += 1
        o["segments"] += n
        o["chars"] += pl["chars"]
        if per_seg is not None:
            o["usd_list"] += n * per_seg
        if n > 1:
            o["stitched_sessions"] += 1
            o["stitched_segments"] += n
            if per_stitched_seg is not None:
                o["usd_list"] += n * per_stitched_seg * (1.5 if n > GROUP else 1)
    for o in out.values():
        o["usd_list"] = round(o["usd_list"], 2)
    return {"by_domain": out, "usd_list": round(sum(o["usd_list"] for o in out.values()), 2),
            "measured_from": {"segments": len(seg_calls), "stitched_sessions": len(stitched)},
            "usd_per_segment": per_seg and round(per_seg, 4), "usd_per_stitched_segment": per_stitched_seg and round(per_stitched_seg, 4)}


def _who(by: str) -> str:
    return {config.owner_id(): config.owner(), "with-claude": "worked out with Claude", "claude-suggestion": "Claude's suggestion"}.get(
        by, by.split(":", 1)[-1])


def render(data: dict) -> str:
    s = data["stitch"]["summary"] or {}
    out = []
    if s.get("topics"):
        out.append("Topics: " + "; ".join(s["topics"]))
    for c in s.get("chronology", []):
        how = c.get("confidence") or "unstated"
        relayed = str(c.get("relayed_from") or "own") != "own" and c.get("speaker") and c.get("speaker") != str(c.get("by"))
        who = (_who(str(c.get("by", ""))) + (f", as {config.owner() if c.get('speaker') == config.owner_id() else 'Claude'} relayed" if relayed else "")
               + (f", taken up at L{c['taken_up_at']}" if c.get("taken_up_at") else ""))
        said = f'"{str(c.get("text")).strip(chr(34))}"' if c.get("quote") else f"{c.get('text')} (paraphrase)"
        words = f' “{c["evidence"]}”' if c.get("evidence") and not c.get("quote") else ""
        out.append(f"[L{c.get('line')}] {said} ({who}; how sure: {how}; basis: {c.get('basis')}){words}")
    for r in s.get("reported", []):
        out.append(f"[L{r.get('line')}] {r.get('text')} (said: {r.get('when_said')})" + (f' “{r["evidence"]}”' if r.get("evidence") else ""))
    for c in s.get("complaints", []):
        out.append(f"Complaint {c.get('tag')}: " + "; ".join(
            f"L{x.get('line')} {x.get('intensity') or ''} ({x.get('direction')})".replace("  ", " ") for x in c.get("course", [])))
    for d in s.get("decisions", []):
        why = (f' Why ({config.owner()}): “{d["why_evidence"]}”' if d.get("why_evidence") and str(d.get("why")).lower() != NOT_STATED
               else f" Why: not stated by {config.owner()}.")
        why += f" Claude's reasoning: {d['claude_reason']}." if d.get("claude_reason") else ""
        out.append(f"[L{d.get('line')}] Decided: {d.get('text')}.{why}" + (f' “{d["evidence"]}”' if d.get("evidence") else ""))
    for u in s.get("updates", []):
        out.append(f"[L{u.get('earlier_line')} → L{u.get('line')}] Changed: {u.get('what')}: {u.get('before')} → {u.get('after')}")
    for c in s.get("contradictions", []):
        out.append(f"[{' vs '.join(f'L{x}' for x in c.get('lines', []))}] Contradiction: {c.get('text')} (later: L{c.get('later')})")
    for o in s.get("open", []):
        out.append(f"[L{o.get('line')}] Open: {o.get('text')}" if isinstance(o, dict) else f"Open: {o}")
    for f in s.get("filed", []):
        out.append(f"[L{f.get('line')}] Filed to the record: {f.get('what')} ({f.get('where')})")
    t = s.get("tenor") or {}
    if t.get("arc"):
        out.append(f"Tenor: {t['arc']}" + "".join(f' "{q.get("text")}" (L{q.get("line")})' for q in t.get("quotes", [])))
    return "\n".join(out)


def docs_for(data: dict) -> list[Doc]:
    first, last = dates.key((data.get("first") or "")[:10]), dates.key((data.get("last") or "")[:10])
    span = first if not last or last == first else f"{first} to {last}"
    head = data.get("title") or data["project"].replace(str(Path.home()).replace("/", "-") + "-", "~/").replace("-", "/")
    base = f"summary:{data['stem']}"
    parts = chunks(render(data))
    return [Doc(ref=base if len(parts) == 1 else f"{base}@{i}", source=f"sessions:{data['stem']}:summary", cls="summary",
                kind="session-summary", title=f"{head} · {span or ''} · session summary", body=part,
                pointer=str(store_dir(data["domain"]) / f"{data['stem']}.json"), author="summary", date=first, date_key=first,
                tags=data["project"], parent=base if len(parts) > 1 else None)
            for i, part in enumerate(parts, 1)]


def index_all() -> dict:
    """Index every stored summary whose stitched summary passed lint, in its session's domain. A summary follows its
    session when the session is refiled, and is deleted when the session stops being indexed (eval work holds answer keys)."""
    st = sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)
    filed = {Path(p).stem: d for p, d in st.execute("SELECT path, domain FROM file WHERE path NOT LIKE '%/subagents/%'")}
    st.close()
    want: dict[str, dict[str, dict]] = {d: {} for d in config.load()}
    for p in sorted((data_path("summaries")).glob("*/*.json")):
        dom = filed.get(p.stem)
        if dom == "skipped":
            p.unlink()
            continue
        if dom not in want:
            continue
        data = json.loads(p.read_text())
        if dom != p.parent.name:
            data["domain"] = dom
            _write(store_dir(dom) / p.name, data)
            p.unlink()
        if data["stitch"].get("summary") and not data["stitch"]["flagged"]:
            want[dom][p.stem] = data
    counts = {}
    for dom, items in want.items():
        idx = open_index(index_path(dom))
        try:
            have = {r[0] for r in idx.db.execute("SELECT DISTINCT source FROM doc WHERE source LIKE 'sessions:%:summary'")}
            for stem, data in items.items():
                idx.sync_source(f"sessions:{stem}:summary", docs_for(data))
            for src in have - {f"sessions:{s}:summary" for s in items}:
                idx.sync_source(src, [])
                idx.db.execute("DELETE FROM ingest_state WHERE source = ?", (src,))
                idx.db.commit()
        finally:
            idx.close()
        counts[dom] = len(items)
    return counts


def status() -> dict:
    """For engram health: summaries per domain, and the flagged ones."""
    out = {}
    for p in sorted((data_path("summaries")).glob("*/*.json")):
        d = json.loads(p.read_text())
        o = out.setdefault(p.parent.name, {"sessions": 0, "flagged": []})
        o["sessions"] += 1
        if d.get("flagged"):
            o["flagged"].append(f"{p.stem[:8]} ({', '.join(map(str, d['flagged']))})")
    return out
