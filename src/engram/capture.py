"""Capture (.engram/README.md, "Filing from conversation"): what the owner says in a repo's sessions gets filed without him
doing anything. The hourly job is the only filer of facts from talk; the advisor saves only whole documents he hands it.

One timed job runs every hour (`engram capture run`, `engram.jobs`):
1. It indexes changed sessions. Under "DO NOT STORE GARBAGE" that means their checked summaries, kept current for the
   repos set up; raw transcripts are never indexed.
2. Each session started in a repo set up that has grown since it was last filed, and has been idle an hour (its last
   message at least 60 minutes old), is read whole by Opus at low effort: the owner's messages and Claude's written replies,
   cleaned as for the summaries (no tool calls or output, reminders or hook text). With it go the entries the store
   holds as filed from that session, every entry dated within a month of each of his messages, where every medication and treatment
   stands, and search hits on his words, so a repeat in other words is seen. It files only what's worth keeping, each
   fact with a quote of the owner's words and a full date. A session still going is skipped, never read partly.
3. It checks the install and repairs what's missing.

No duplicates when a session comes back, enforced in code: each session keeps the message it was filed up to, and the
entries filed from it are read from the store by their source. A fact is filed only from the owner's own words: its
quote found word for word in his messages after that point, and every number in it in his words or the question he
answered (found in Claude's turn just before his message); a date may also be the day he said it or follow from his
words ("yesterday", "3 days ago"). A med-change to the status the medication already has is dropped as a repeat.

A repeat check follows (a month's window read at low effort still let repeats through, and documents and complaint
pages were never in it): each checked fact's own text, already in record wording, searches the domain index; its top
hits across entries, documents, complaint pages and where things stand, each shown whole up to a cap, and the entries
dated the same day go with it to one low-effort call per session, which names any record that already states it. A
restatement, or the same detail with a date, is a repeat; a new value, date, change or decision is not.
A new occurrence of a known symptom is always filed; code honours a repeat only for the same occurrence. For an
occurrence kind (symptom, observation, measurement, procedure, visit), the named record's own date, or a full date
written in it (a complaint page listing past occurrences), must fall within 2 days of the candidate's (4 when either is
approximate; a month-only date matches only that month); otherwise the candidate is kept as a new occurrence, whatever
the model said. Interpretations, plans, decisions and beliefs stay repeats on any day.

Theory changes: a theory's status changes, and a loop step or join becomes a theory link, only
when the owner states it or agrees to it in conversation. The model is given the graph's ids and statuses; code files a
status or link only on an id the graph holds, a status or rel the record knows, and the owner's own words (his agreement,
with Claude's proposal, from the turn just before it, as the question answered). A Claude suggestion he hasn't agreed to
never counts.

Emotional and mental-health talk stays out (the record's handle-mental-health rule): it's filed only with his consent,
as a journal page the advisor saves, never by this job and never as a symptom or theory entry.

There is no keyword filter: a word list silently loses whatever isn't on it, and the volume makes it unnecessary.

The SessionStart hook only checks the install and repairs it (it's the only thing that notices a dead job), printing
one line if a repair fails. State lives in the data folder, never in the repo.
"""
import contextlib
import fcntl
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from engram import claude_env, commitmsg, config, daily, dates, pack, recsum, refine, review, store, summarize
from engram import now as now_mod
from engram import theory as theory_mod
from engram.paths import data_path, record_conf, record_toml
from engram.sources import sessions, waysin

IDLE = timedelta(hours=1)  # a session is filed once its last message is this old
STALE = timedelta(hours=3)  # the job runs hourly; three missed runs is a dead job
MAX_CHARS = 600_000  # a session longer than this is read from a little before where it was filed up to
FILED = re.compile(r"\bengram (add|status|link)\b")

SCHEMA = """
CREATE TABLE IF NOT EXISTS filed (session TEXT PRIMARY KEY, domain TEXT, path TEXT, upto INTEGER NOT NULL DEFAULT 0,
  bytes INTEGER NOT NULL DEFAULT 0, entries TEXT NOT NULL DEFAULT '[]', at TEXT);
CREATE TABLE IF NOT EXISTS run (at TEXT, ok INTEGER, sessions INTEGER, filed INTEGER, dropped INTEGER, usd REAL, error TEXT);
CREATE TABLE IF NOT EXISTS repo (domain TEXT PRIMARY KEY, root TEXT NOT NULL, setup TEXT NOT NULL, at TEXT);
"""


def db() -> sqlite3.Connection:
    c = sqlite3.connect(data_path("capture.sqlite"), timeout=30)
    c.executescript(SCHEMA)
    return c


def _now() -> datetime:
    return datetime.now().astimezone()


def repo_of(path: str | Path | None) -> tuple[str, Path] | None:
    """The record repo a folder is in (the nearest with a .engram/engram.toml, up the tree) and its domain name."""
    if not path:
        return None
    p = Path(path).resolve()
    for d in [p, *p.parents]:
        if record_toml(d).exists():
            name = record_conf(d).get("domain", {}).get("name")
            return (name, d) if name else None
    return None


def _parse(path: Path) -> sessions.Session:
    root = sessions.ROOT if sessions.ROOT in path.parents else path.parent.parent
    return sessions.parse(path, root)


def last_message(path: Path) -> datetime:
    """When the session's last message was written: the transcript's last timestamp, else the file's modified time."""
    with path.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 262144))
        tail = f.read().decode(errors="replace").splitlines()
    for line in reversed(tail):
        with contextlib.suppress(json.JSONDecodeError, ValueError, AttributeError, TypeError):
            ts = json.loads(line).get("timestamp")
            if ts:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone()


def _mine(s: sessions.Session, x: sessions.Exchange, me: str) -> list[tuple[int, str]]:
    """The owner's messages in an exchange, each with how many of Claude's replies came before it: what he asked, then
    what he sent while Claude worked. Text a skill, a program or another session wrote isn't his."""
    if x.meta or x.summary:
        return []
    who, words = summarize.speaker(s, x.asked, me)
    return ([(0, words)] if who == me else []) + [(k, q) for k, q in x.queued if summarize.speaker(s, q, me)[0] == me]


def owners(s: sessions.Session, after: int = 0) -> dict[int, str]:
    """line -> the owner's own words in each exchange past `after`, with what he sent while Claude worked. A short reply
    is his, since "yes" to "did you take 10mg?" can be a fact."""
    me, out = config.owner(), {}
    for x in s.exchanges:
        said = _mine(s, x, me) if x.line > after else []
        if said:
            out[x.line] = "\n\n".join(w for _, w in said)
    return out


def turn_before(s: sessions.Session) -> dict[int, str]:
    """line -> Claude's turn just before the owner's words there, where the question he answered must be: all Claude's
    text since his previous message (a skill's turn, a summary or another speaker in between isn't his, so Claude's text
    after one still counts), and, as what he sent while Claude worked joins the line, this turn's text before the last of it."""
    me, out, since = config.owner(), {}, []
    for x in s.exchanges:
        said = _mine(s, x, me)
        if not said:
            since += x.replies
            continue
        k = said[-1][0]
        out[x.line] = "\n".join(since + x.replies[:k])
        since = x.replies[k:]
    return out


THEORY_STATUSES = theory_mod.STATUSES
STRENGTHS = theory_mod.STRENGTHS


def _ask(prompt: str, effort: str = recsum.EFFORT) -> tuple[str, float]:
    cmd = ["claude", "-p", "--model", recsum.MODEL, "--effort", effort, "--output-format", "json", "--setting-sources",
           "project", "--strict-mcp-config", "--no-session-persistence", "--tools", "", "--system-prompt",
           "You file what a person said into their record, carefully and literally."]
    with tempfile.TemporaryDirectory(prefix="engram-capture-") as cwd:
        r = subprocess.run(cmd, input=prompt, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=1800)
    out = json.loads(r.stdout)
    if r.returncode or out.get("is_error"):
        raise RuntimeError(str(out.get("result") or f"exit {r.returncode}")[:300])
    return out.get("result") or "", out.get("total_cost_usd", 0) or 0


def prompt_only(prompt: str) -> tuple[str, float]:
    print(prompt + "\n" + "-" * 80)
    return '{"facts": []}', 0.0


def shape(st: store.Store, kinds: tuple[str, ...] = ()) -> tuple[list[str], list[str], str]:
    """The kinds the filer may write, the record's about values by use, and its home prefix: the one most events name
    first, which decides the page an entry renders into (series/<log>). The kinds are the pack's; a pack that names
    none offers the kinds the record already holds, most used first."""
    evs = [e for e in st.events() if e.kind != "link"]
    if not kinds:
        kinds = [k for k, _ in Counter(e.kind for e in evs).most_common()
                 if k not in ("status", "capture", now_mod.RENEWAL)] or ["observation"]
    abouts = [a for a, _ in Counter(a for e in evs for a in e.about).most_common(80)]
    home = Counter(e.about[0].split("/")[0] for e in evs if e.about).most_common(1)
    return list(kinds), abouts, home[0][0] if home else ""


def on_record(domain: str, said: list[str], per: int = 5) -> list[str]:
    """The record's current entries on what the owner talked about (a search per message), so repeats are skipped."""
    from engram import search
    seen, out = set(), []
    for words in said:
        for r in search.search(words[:500], [domain], limit=per, surround=False):
            if r["ref"] not in seen:
                seen.add(r["ref"])
                out.append(f"[{r.get('date') or 'undated'}] {r['title']}: {' '.join(str(r.get('snip') or '').split())[:300]}")
    return out


WINDOW = 31  # days either side of each of the owner's messages whose entries all go to the model
WINDOW_FULL = 250  # past this many entries in the window, titles only
WINDOW_MAX = 600  # and past this many, the ones nearest his messages


def _span(value: str) -> tuple[date, date] | None:
    """The days a record date covers: a day or a month (a year or no date is too vague to place)."""
    k = dates.key(value)
    if not k or len(value) < 7:
        return None
    start = date.fromisoformat(k)
    if len(value) == 7:
        return start, (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return start, start


def near(st: store.Store, days: set[str], span: int = WINDOW) -> list[store.Event]:
    """Every entry dated within `span` days either side of any of the days, nearest first: what the record already
    holds around when he spoke, whatever words it used."""
    centres = [date.fromisoformat(d) for d in days if d and len(d) == 10 and dates.valid(d)]
    out = []
    for e in st.events():
        sp = None if e.kind == "link" else _span(str(e.fm.get("date") or ""))
        if not sp or not centres:
            continue
        gap = min(max((sp[0] - c).days, (c - sp[1]).days, 0) for c in centres)
        if gap <= span:
            out.append((gap, e))
    out.sort(key=lambda x: x[0])
    return [e for _, e in out[:WINDOW_MAX]]


def _first_line(body: str) -> str:
    return next((" ".join(l.strip().lstrip("-* ").split()) for l in body.splitlines() if l.strip().lstrip("-* ")), "")


def listing(evs: list[store.Event]) -> list[str]:
    """Each entry as its date, title and first body line, oldest first; titles only when there are many."""
    full = len(evs) <= WINDOW_FULL
    out = []
    for e in sorted(evs, key=lambda e: (dates.key(str(e.fm.get("date") or "")) or "", str(e.fm.get("recorded", "")))):
        title = " ".join(str(e.fm.get("title") or e.fm.get("heading") or "").split())
        first = _first_line(e.body)[:200] if full else ""
        out.append(f"[{e.fm.get('date')}] {title}" + (f" | {first}" if first and first != title else "") + f" (id {e.id})")
    return out


def _n(s: str) -> str:
    return " ".join(str(s).lower().replace("’", "'").split())


def standing(st: store.Store) -> list[tuple["now_mod.Current", set[str]]]:
    """Where every thing the pack follows stands (each id's chain followed to its latest entry), with the names it goes
    by: every entity string its entries used, the fields that also name it, any aliases the entries list, a thread's name."""
    names = {t: forms[0] for t, forms in now_mod.names(st).items()}
    out = []
    for c in now_mod._chain(st):
        out.append((c, names.get(c.thing, set()) | {_n(c.name), _n(c.name.split("(")[0]),
                                                    _n(c.thing.split("/", 1)[-1].replace("-", " "))}))
    return out


def entity_repeat(fact: dict, stands: list, cur: pack.Current, thing: str | None = None) -> str | None:
    """Why an entity entry is a repeat, or None: its thing (its chain, matched through its names, entity strings and
    aliases by now.chain_for) already stands at that status in the record, with the same detail if he gave one."""
    ent, status = str(fact.get("entity") or ""), str(fact.get("status") or "")
    if not ent or status not in cur.repeats:
        return None
    k, names = thing or now_mod.key(ent, cur), {_n(ent), _n(ent.split("(")[0])}
    for c, al in stands:
        if c.thing != k and not names & al:
            continue
        shown = _n(fact.get(cur.detail) or "") if cur.detail else ""
        if c.status in cur.repeats[status] and (not shown or status not in now_mod.ONGOING or shown in _n(c.detail)):
            return f"repeat: {c.name} is already {c.status} in the record"
    return None


def record_context(domain: str, st: store.Store, later: dict[int, str], when: dict[int, str], stands: list, words: str) -> str:
    """What the record already holds, put to the model so a repeat can't slip through on different wording: every
    entry within WINDOW days of each of the owner's new messages, where every thing the pack follows stands, and the
    search hits on his words, in the pack's `record` words."""
    days = {when[l] for l in later if when.get(l)}
    win = listing(near(st, days))
    now_lines = [f"{c.name}: {c.status}" + (f" since {c.when}" if c.when else "") + (f"; {c.detail}" if c.detail else "")
                 for c, _ in sorted(stands, key=lambda x: x[0].name.lower())]
    hits = on_record(domain, list(later.values()))
    return words.format(window=WINDOW, span=", ".join(sorted(days)) or "unknown",
                        titles=", titles only (there are many)" if len(win) > WINDOW_FULL else "", entries="\n".join(win) or "none",
                        standing="\n".join(now_lines) or "none", hits="\n".join(hits) or "nothing found")


def conversation(s: sessions.Session, upto: int) -> str:
    turns = summarize.clean(s)
    text = summarize.render_turns(turns)
    if len(text) > MAX_CHARS:  # start a few turns before the new part
        i = next((n for n, t in enumerate(turns) if t.line > upto), len(turns))
        text = summarize.render_turns(turns[max(0, i - 4):])
    return text


DATEISH = re.compile(r"^(\d{4}-\d{1,2}(-\d{1,2})?|\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?)$")
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "couple": 2,
         "a couple": 2, "couple of": 2, "a couple of": 2, "few": 3, "a few": 3}
_N = r"(\d+|a couple(?: of)?|couple(?: of)?|a few|few|an?|one|two|three|four|five|six|seven)"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HEDGE = re.compile(r"\b(about|around|roughly|approximately|maybe|or so|ish)\b|~", re.I)
# (pattern, days back or a function of the match and the day, estimated?)
RELATIVE = [
    (re.compile(r"\b(today|this morning|this afternoon|this evening|tonight|just now)\b", re.I), lambda m, d: 0, False),
    (re.compile(r"\b(yesterday|last night)\b", re.I), lambda m, d: 1, False),
    (re.compile(_N + r"\s+days?\s+ago\b", re.I), lambda m, d: WORDS.get(m.group(1).lower(), 0) or int(m.group(1)), None),
    (re.compile(_N + r"\s+weeks?\s+ago\b", re.I), lambda m, d: 7 * (WORDS.get(m.group(1).lower(), 0) or int(m.group(1))), True),
    (re.compile(r"\bsince (?:last )?(" + "|".join(WEEKDAYS) + r")\b", re.I),
     lambda m, d: (d.weekday() - WEEKDAYS.index(m.group(1).lower())) % 7 or 7, False),
    (re.compile(r"\bthis week\b", re.I), lambda m, d: d.weekday(), True),
    (re.compile(r"\blast week\b", re.I), lambda m, d: 7, True),
]


def relative_days(words: str, said_on: str | None) -> list[tuple[str, bool]]:
    """The days a message's relative date words name, counted back from the day it was sent, each with whether it's
    an estimate: "about 2 days ago" on 2026-09-23 is (2026-09-21, True); "since Monday", the latest Monday before."""
    if not said_on or len(said_on) != 10 or not dates.valid(said_on):
        return []
    day = datetime.fromisoformat(said_on).date()
    out = []
    for pat, back, est in RELATIVE:
        for m in pat.finditer(words):
            n = back(m, day)
            hedged = est if est is not None else bool(HEDGE.search(words[max(0, m.start() - 12):m.start()])) or \
                m.group(1).lower() in ("couple", "couple of", "a couple", "a couple of", "few", "a few")
            out.append(((day - timedelta(days=n)).isoformat(), bool(hedged)))
    return out


def dates_said(words: str, said_on: str | None) -> set[str]:
    """The days a message's date words can mean: the day it was sent, and what "yesterday", "last night" or "3 days
    ago" count back from it."""
    if not said_on or not dates.valid(said_on) or len(said_on) != 10:
        return set()
    return {said_on} | {d for d, _ in relative_days(words, said_on)}


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH = (r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?")
MONTH_DAY = re.compile(_MONTH + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b|\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MONTH, re.I)
MONTH_NAME = re.compile(_MONTH, re.I)
DATE_TOKEN = re.compile(r"\b\d{1,4}(?:[-/]\d{1,2}){1,2}(?:[-/]\d{2,4})?\b")
PAST = re.compile(r"\b(last time|the time before|before that|the other day|once|previously|back then|used to)\b", re.I)
WEEKDAY = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b", re.I)


def said_date(value: str, words: str, said_on: str | None) -> bool:
    """Whether a date rests on what was said: the day he said it, a day his relative words count back to ("yesterday",
    "3 days ago"), a weekday he named in the fortnight before, a day of a weekend he named, or a date written out ("2026-10-07", "10/7", "Oct 7");
    a month by its name, number or "this/last month"; a year by its digits or "this/last year"."""
    if not said_on or len(said_on) != 10 or not dates.valid(said_on) or not dates.valid(value) or value == "not-sure":
        return False
    day, low = date.fromisoformat(said_on), words.lower()
    if len(value) == 10:
        if value in dates_said(words, said_on) or any(_date_fits(t, {value}) for t in DATE_TOKEN.findall(words)):
            return True
        when = date.fromisoformat(value)
        for m in MONTH_DAY.finditer(words):
            name, n = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            if MONTHS.index(name.lower()[:3]) + 1 == when.month and int(n) == when.day:
                return True
        back = (day - when).days
        return 0 < back <= 14 and any(WEEKDAYS.index(w.lower()) == when.weekday() for w in WEEKDAY.findall(words)) or \
            0 < back <= 13 and when.weekday() >= 5 and "weekend" in low
    if len(value) == 7:
        y, m = int(value[:4]), int(value[5:])
        last = day.replace(day=1) - timedelta(days=1)
        named = {MONTHS.index(x.lower()[:3]) + 1 for x in MONTH_NAME.findall(words) if x.lower() != "may"}
        if re.search(r"\b(in|since|of|early|mid|late|last|this) may\b", low):  # bare "may" is mostly the verb
            named.add(5)
        named = named if y in (day.year, day.year - 1) and (y, m) <= (day.year, day.month) and \
            (y == day.year or m > day.month) else set()  # "October" is the latest October up to now
        return value in words or m in named or ("this month" in low and (y, m) == (day.year, day.month)) or \
            ("last month" in low and (y, m) == (last.year, last.month))
    return value in words or ("this year" in low and int(value) == day.year) or \
        ("last year" in low and int(value) == day.year - 1)


def full_date(fact: dict, said_on: str, words: str | None = None) -> tuple[str, bool]:
    """The fact's date and whether it's an estimate. The model gives a full day; when it gave only a month (or no
    date) and the quote or text has a relative phrase, code counts the day back from when he said it. Given what he
    said (`words`: his message and what he was answering), a date that doesn't rest on it narrows to the month or year
    that does, else "never-said": the model counted a day he never gave (a "last time" placed on a date, or on the
    day he said it)."""
    date, approx = str(fact.get("date") or "not-sure"), fact.get("approx") in (True, "true", "yes")
    if not dates.valid(date):
        date = "not-sure"
    if date == "not-sure" or len(date) == 7:
        for said in (str(fact.get("quote", "")), str(fact.get("text", ""))):
            found = relative_days(said, said_on)
            if found and (date == "not-sure" or found[0][0].startswith(date)):
                return found[0][0], approx or found[0][1]
    quote = str(fact.get("quote", ""))
    if words is not None and date == said_on and PAST.search(quote) and not relative_days(quote, said_on):
        return "never-said", False  # "last time" dated the day he said it
    if words is None or date == "not-sure" or said_date(date, words, said_on):
        return date, approx
    for part in (date[:7], date[:4]):
        if len(part) < len(date) and said_date(part, words, said_on):
            return part, approx
    return "never-said", False


WRAPPED = re.compile(r"^[\"'“”‘’«»](.*)[\"'“”‘’«»]\.?$", re.S)


def headline(text: str) -> str:
    """A plain headline: no wrapping quote marks, no "<owner> ..." at the start (it's his record)."""
    t = " ".join(str(text).split())
    while WRAPPED.match(t):
        t = WRAPPED.match(t).group(1).strip()
    me = re.escape(config.owner())
    t = re.sub(rf"^{me}(?:'s|’s)\s+", "", t)
    t = re.sub(rf"^{me}\s+(?:says|said|reports|reported|notes|noted|mentions|mentioned)\s+(?:that\s+)?(?:he\s+)?", "", t, flags=re.I)
    t = re.sub(rf"^{me}\s+(?:is|was)\s+", "", t)
    t = re.sub(r"^(?:his|he)\s+", "", re.sub(rf"^{me}\s+", "", t), flags=re.I)
    return t[:1].upper() + t[1:] if t else t


def _date_fits(token: str, days: set[str]) -> bool:
    """A date in the fact (2026-09-22, 09-22, 9/22) that names one of the days."""
    if not DATEISH.match(token):
        return False
    parts = [int(x) for x in re.split(r"[-/]", token)]
    for d in days:
        y, m, dd = (int(x) for x in d.split("-"))
        if parts in ([y, m, dd], [y, m], [m, dd], [m, dd, y], [m, dd, y % 100]):
            return True
    return False


def _his(item: dict, later: dict[int, str], turns: dict[int, str]) -> str | None:
    """Why an item isn't in the owner's own new words, or None: its quote in one of his messages past the mark, word for word,
    and the question he answered (or the proposal he agreed to) in Claude's turn just before his words (`turn_before`)."""
    try:
        line = int(item.get("line"))
    except (TypeError, ValueError):
        line = None
    words = later.get(line)
    quote, asked = str(item.get("quote", "")), str(item.get("answering", ""))
    if words is None:
        return f"not one of {config.owner()}'s new messages"
    if not quote.strip() or recsum._norm(quote) not in recsum._norm(words):
        return f"quote not in {config.owner()}'s words"
    if asked and recsum._norm(asked) not in recsum._norm(turns.get(line, "")):
        return "question not in Claude's words"
    return None


def check(fact: dict, later: dict[int, str], turns: dict[int, str], said_on: str | None = None) -> str | None:
    """Why a fact can't be filed as the owner's, or None. A fact is filed only from the owner's own words: its quote
    found word for word in his messages after the filed-up-to point, and every number in it in his words or the question
    he answered, found in Claude's turn just before his; a date may also be the day he said it or follow from his words
    ("yesterday", "3 days ago"). At most 40 words."""
    why = _his(fact, later, turns)
    if why:
        return why
    words, asked, text = later[int(fact["line"])], str(fact.get("answering", "")), str(fact.get("text", ""))
    if not text.strip():
        return "missing text or quote"
    if len(text.split()) > 40:
        return "over 40 words"
    context = dates.numbers("\n".join([words, asked]))
    days = dates_said(words, said_on)
    for n in dates.NUMBER.findall(text):
        if n not in context and not _date_fits(n, days):
            return f"number {n} not in the record"
    return None


def cut_title(text: str, limit: int = 120) -> str:
    """A headline cut at the last whole word within the limit, marked with an ellipsis; the body keeps it whole."""
    if len(text) <= limit:
        return text
    return text[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "…"


def entry(fact: dict, said_on: str, stem: str, kinds: list[str], abouts: list[str], home: str,
          words: str | None = None, cur: pack.Current = pack.NONE.current, other: str = "observation") -> tuple[dict, str]:
    """The event front matter and body for a checked fact, in one of the kinds offered, else `other`. A date he never
    gave is filed as not sure, never guessed."""
    date, approx = full_date(fact, said_on, words)
    kind = fact.get("kind") if fact.get("kind") in kinds else other
    if kind == cur.entity_kind and (not fact.get("entity") or fact.get("status") not in cur.statuses):
        kind = other
    about = [a for a in fact.get("about") or [] if a in abouts][:3]
    if home and not any(a.startswith(home + "/") for a in about):
        homes = [a for a in abouts if a.startswith(home + "/")]
        if homes:  # the fact still needs a page to render into: the most used one
            about.insert(0, homes[0])
    text = headline(fact["text"])
    fm = {"title": cut_title(text), "date": date, "reported": said_on, "kind": kind,
          "about": about, "by": config.owner_id(), "source": f"said in session {stem[:8]} on {said_on}", "author": "engram-capture"}
    if date == "not-sure":
        fm["date"], fm["date_note"] = said_on, "reported"
    elif date == "never-said":
        fm["date"], fm["date_note"] = "not-sure", "reported; when it happened wasn't said"
    elif approx:
        fm["date_note"], fm["approx"] = "approx", "true"
    if kind == cur.entity_kind:
        fm.update(entity=fact["entity"], status=fact["status"], **({cur.detail: fact.get(cur.detail) or ""} if cur.detail else {}),
                  reason=" ".join(str(fact.get("reason") or "").split())[:200])
    who = f"{config.owner()}, answering “{' '.join(fact['answering'].split())}”" if fact.get("answering") else config.owner()
    return fm, f"- {text}\n- {who}: “{' '.join(str(fact['quote']).split())}”\n"


def theory_shape(st: store.Store, words: str):
    """The theory graph, its link kinds and strengths, and the graph as the model reads it in the pack's `theory`
    words: each thing's id, kind, status and name, each loop's path, and the joins already held. None when the record
    has no theory graph, or its pack no words for one."""
    from engram import theory
    g = theory.load(st.root)
    if not g.things or not words:
        return None
    conf = st.config.get("links", {}).get("theory", {})
    rels, strengths = list(conf.get("rels") or []), list(conf.get("weights") or STRENGTHS)
    lines = ["id\tkind\tstatus\tname"]
    for t in g.things.values():
        lines.append(f"{t.id}\t{t.kind}\t{g.status.get(t.id, ('none',))[0] or 'none'}\t{t.title}")
    lines += [f"{l} path: {' → '.join(g.path(l))}" for l in g.loops() if g.path(l)]
    lines += [f"join: {e.a} {e.rel} {e.b} ({e.strength or 'no strength'})" for e in g.joins()]
    graph = "\n".join(lines)
    text = config.voice(words).format(statuses=", ".join(THEORY_STATUSES), rels=", ".join(rels) or "none (no links can be filed)",
                                      strengths=", ".join(strengths), graph=graph, upto="{upto}")
    return g, rels, strengths, text, graph


def check_theory(item: dict, later: dict[int, str], turns: dict[int, str], g, rels: list[str], strengths: list[str]) -> str | None:
    """Why a theory change can't be filed, or None: it must be in the owner's own words (his agreement when he agreed to
    Claude's proposal in the turn just before), on ids the graph holds, with a status or rel the record knows."""
    why = _his(item, later, turns)
    if why:
        return why
    st, ln = item.get("status"), item.get("link")
    if isinstance(st, dict):
        tid, to = str(st.get("id", "")), str(st.get("to", ""))
        if tid not in g.things:
            return f"unknown theory id {tid}"
        if to not in THEORY_STATUSES:
            return f"unknown status {to}"
        if g.status.get(tid, ("",))[0] == to:
            return f"{tid} is already {to}"
        return None
    if isinstance(ln, dict):
        a, b, rel = str(ln.get("from", "")), str(ln.get("to", "")), str(ln.get("rel", ""))
        for x in (a, b):
            if x not in g.things:
                return f"unknown theory id {x}"
        if rel not in rels:
            return f"unknown rel {rel}"
        if str(ln.get("strength", "")) not in strengths:
            return f"unknown strength {ln.get('strength')}"
        mech = " ".join(str(ln.get("mechanism", "")).split())
        if not mech or len(mech.split()) > 40:
            return "mechanism missing or over 40 words"
        loop = str(ln.get("loop") or "")
        if loop and (rel != "feeds" or loop not in g.loops()):
            return f"unknown loop {loop}"
        if any(e.a == a and e.b == b and e.rel == rel for e in g.edges):
            return "link already in the record"
        return None
    return "neither a status nor a link"


def theory_entry(item: dict, said_on: str, stem: str, g) -> tuple[dict, str]:
    """A checked theory change as the store writes it: a status event on the theory, or a theory link (appended to
    links.jsonl by the store), by the owner, since the day he said it."""
    who = f"{config.owner()}, agreeing to “{' '.join(item['answering'].split())}”" if item.get("answering") else config.owner()
    said = f"{who}: “{' '.join(str(item['quote']).split())}”"
    base = {"date": said_on, "reported": said_on, "by": config.owner_id(), "source": f"said in session {stem[:8]} on {said_on}",
            "author": "engram-capture"}
    if isinstance(item.get("status"), dict):
        tid, to = item["status"]["id"], item["status"]["to"]
        return {**base, "title": f"{g.label(tid)}: {to}", "kind": "status", "about": [tid], "status": to}, f"- {said}\n"
    ln = item["link"]
    a, b, rel = ln["from"], ln["to"], ln["rel"]
    fm = {**base, "title": f"{g.label(a)} {rel} {g.label(b)}", "kind": "link", "about": [a, b], "from": a, "to": b,
          "family": "theory", "rel": rel, "strength": ln["strength"], "since": said_on}
    if ln.get("loop"):
        fm.update(loop=ln["loop"], step=max([e.step for e in g.edges if e.loop == ln["loop"]], default=0) + 1)
    return fm, f"{' '.join(str(ln['mechanism']).split())} ({said})"


def _ask_structure(prompt: str) -> tuple[str, float]:
    return _ask(prompt, effort="medium")  # a revision of the model takes more judgment than drawing out facts


def structure(domain: str, st: store.Store, s: sessions.Session, line: int, later: dict[int, str], turns: dict[int, str], th,
              ask, words: str) -> tuple[dict | None, str | None, float]:
    """The backstop for a structural theory revision the owner agreed to but the conversation didn't make: one call at
    medium effort writes it as operations; his agreement is checked word for word and the change on the graph it would
    make. Returns (item, why it can't be filed, cost)."""
    from engram import theorychange
    ran = [r[:300] for x in s.exchanges for r in x.ran if "engram theory change" in r]
    g, rels, strengths = th[0], th[1], th[2]
    stories = sorted({a.split("/", 1)[1] for e in st.events() for a in e.about if a.startswith("story/")})
    reply, usd = ask(config.voice(words).format(domain=domain, line=line, rels=", ".join(r for r in rels if r != "feeds"),
                                             strengths=", ".join(strengths), statuses=", ".join(THEORY_STATUSES),
                                             stories=", ".join(stories), graph=th[4].strip(),
                                             ran="\n".join(ran) or "none", conversation=conversation(s, 0)))
    m = re.search(r"\{.*\}", reply, re.S)
    item = json.loads(m.group(0)) if m else {}
    if not item.get("ops"):
        return None, "on a closer read, no structural change was agreed", usd
    why = _his(item, later, turns)
    if why:
        return None, why, usd
    try:
        theorychange.plan(g, item["ops"], rels, strengths, str(item.get("why", "")))
    except theorychange.ChangeError as e:
        return None, str(e), usd
    return item, None, usd


def placement_shape(st: store.Store) -> tuple[list[str], dict[str, tuple[str, list[str]]]]:
    """The record's stories (every story an entry or complaint page sits on) and its recurring symptoms: slug ->
    (name, its stories), from the complaint pages' title and "Stories:" line ([ways.symptom] pages says where)."""
    stories = {a.split("/", 1)[1] for e in st.events() for a in e.about if a.startswith("story/")}
    complaints = {}
    where = st.root / waysin.recurring(st.config)[0] if waysin.recurring(st.config) else None
    for p in sorted(where.glob("*.md")) if where and where.exists() else []:
        text = p.read_text(errors="replace")
        name = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem)
        line = next((l.split(":", 1)[1] for l in text.splitlines() if l.lower().startswith("stories:")), "")
        mine = [x.strip() for x in line.split(",") if x.strip()]
        complaints[p.stem] = (name, mine)
        stories |= set(mine)
    return sorted(stories), complaints


def place(fact: dict, fm: dict, st: store.Store, stories: list[str], complaints: dict, rels: list[str],
          occurrence: frozenset[str] = frozenset()) -> dict:
    """Claude's placement of one filed fact, checked by code: stories from the record's list; an occurrence of a known
    recurring symptom (an occurrence kind only) onto its complaint page, whose stories it also takes; a led-to from an
    entry the record holds. Returns {"stories": [...], "occurrence": slug|None, "led_from": id|None}; anything unknown
    is left out."""
    picked = [x for x in (fact.get("stories") or []) if isinstance(x, str) and x in stories][:3]
    occ = str(fact.get("occurrence_of") or "").removeprefix("complaint/")
    occ = occ if occ in complaints and fm.get("kind") in occurrence and "occurrence" in rels else None
    if occ:
        picked += [x for x in complaints[occ][1] if x in stories and x not in picked]
    led = str(fact.get("led_from") or "")
    led = led if led and "led-to" in rels and any(e.id == led and e.kind != "link" for e in st.events()) else None
    return {"stories": list(dict.fromkeys(picked)), "occurrence": occ, "led_from": led}


def placed(fm: dict, where: dict) -> dict:
    """The entry's front matter with its stories and recurring symptom in `about`."""
    about = list(fm.get("about") or [])
    about += [f"story/{x}" for x in where["stories"] if f"story/{x}" not in about]
    if where["occurrence"] and f"complaint/{where['occurrence']}" not in about:
        about.append(f"complaint/{where['occurrence']}")
    return {**fm, "about": about}


def links_for(eid: str, fm: dict, where: dict, quote: str, source: str, st: store.Store) -> list[tuple[dict, str]]:
    """The placement links of a filed entry, as the store writes them: by=claude, never the owner's claim. Inside the
    store's transaction, the complaint page's occurrences section is written as its stable id (engram.docreg), once the
    record keeps a registry."""
    base = {"date": fm.get("date"), "kind": "link", "family": "timeline", "by": "claude", "author": "engram-capture",
            "source": source}
    stories = [f"story/{x}" for x in where["stories"]]
    out = []
    if where["occurrence"]:
        slug = where["occurrence"]
        out.append(({**base, "title": f"occurrence of {slug}", "about": [f"complaint/{slug}", *stories],
                     "from": waysin.page(st.config, slug), "to": eid, "rel": "occurrence"}, quote[:120]))
    if where["led_from"]:
        out.append(({**base, "title": "led to", "about": stories, "from": where["led_from"], "to": eid, "rel": "led-to"}, ""))
    from engram import docreg
    reg = docreg.load(st.root)
    if reg:
        def ided(lfm):
            try:
                return docreg.id_ends(reg, st, lfm)
            except docreg.MoveError:  # a page without the section: filed as named, the rename check guards it
                return lfm
        out = [(ided(lfm), note) for lfm, note in out]
    return out


VERIFY_HITS, VERIFY_CHARS = 8, 1500  # search hits shown per candidate, and each record's characters
NOT_RECORD = ("said", "summary", "raw")  # index classes that are talk, not the record: the session itself would match

def _ask_verify(prompt: str) -> tuple[str, float]:
    return _ask(prompt, effort="low")


FULL_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
SAME_DAYS, SAME_DAYS_APPROX = 2, 4  # how far apart two dates of one occurrence can be, exact or approximate


def _record_text(idx, ref: str) -> str:
    """A record's whole text, title first."""
    rows = idx.db.execute("SELECT title, body FROM doc WHERE ref = ? OR parent = ? ORDER BY id", (ref, ref)).fetchall()
    if not rows:
        return ""
    body = " ".join(" ".join(str(b or "").split()) for _, b in rows)
    return f"{rows[0][0]}: {body}"


def _approx(fm: dict) -> bool:
    return str(fm.get("approx")).lower() == "true" or fm.get("date_note") in ("approx", "reported")


def record_dates(own: str, approx: bool, text: str) -> list[tuple[str, bool]]:
    """The dates a record is about, each with whether it's approximate: its own date, and every full date written in
    its text (a complaint page's list of past occurrences)."""
    out = [(own, approx)] if own and dates.valid(own) and own != "not-sure" else []
    return out + [(d, False) for d in FULL_DATE.findall(text) if dates.valid(d)]


def same_occurrence(fm: dict, held: list[tuple[str, bool]]) -> bool:
    """Whether a record with these dates can be about the candidate's own occurrence: a date within SAME_DAYS of the
    candidate's (SAME_DAYS_APPROX when either is approximate). A month-only date matches only a date in that month."""
    when = str(fm.get("date") or "")
    if not dates.valid(when) or when == "not-sure":
        return False
    for d, approx in held:
        if len(when) < 10 or len(d) < 10:
            if d.startswith(when) or (when.startswith(d) and len(d) >= 7):
                return True
            continue
        gap = abs((date.fromisoformat(when) - date.fromisoformat(d)).days)
        if gap <= (SAME_DAYS_APPROX if approx or _approx(fm) else SAME_DAYS):
            return True
    return False


def repeat_hits(domain: str, st: store.Store, fm: dict, body: str) -> list[tuple[str, str, list[tuple[str, bool]]]]:
    """The records a candidate could repeat, as (ref, text, the dates it's about): the top search hits on its own title
    and body (record wording finds the record far better than his raw words), then every entry dated the same day."""
    from engram import search
    from engram.index import open_index
    from engram.paths import index_path
    hits = [r for r in search.search_domain(domain, f"{fm.get('title', '')} {body}"[:2000], VERIFY_HITS * 5,
                                            surround=False) if r.get("class") not in NOT_RECORD]
    out, seen = [], set()
    evs = {e.id: e for e in st.events() if e.kind != "link"}
    idx = open_index(index_path(domain), readonly=True)
    try:
        for r in hits[:VERIFY_HITS]:
            text = _record_text(idx, r["ref"]) if idx else ""
            if text:
                seen.add(r["ref"])
                e = evs.get(r["ref"])
                own = str(e.fm.get("date") or "") if e else str(r.get("date") or "")
                held = record_dates(own, bool(e) and _approx(e.fm), text)
                out.append((r["ref"], f"[{r.get('date') or 'undated'}] {text}"[:VERIFY_CHARS], held))
    finally:
        if idx:
            idx.close()
    day = str(fm.get("date") or "")
    for e in evs.values():
        if e.id not in seen and str(e.fm.get("date") or "") == day:
            title = " ".join(str(e.fm.get("title") or "").split())
            text = f"{title}: {' '.join(e.body.split())}"
            out.append((e.id, f"[{day}] {text}"[:VERIFY_CHARS], record_dates(day, _approx(e.fm), text)))
    return out


def verify(domain: str, st: store.Store, entries: list[tuple[dict, str]], ask, p: pack.Pack = pack.NONE) -> tuple[dict[int, str], dict[int, str], float]:
    """Which checked candidates (fm, body) the record already holds, in one call: {index: the ref that states it}; the
    ones the model called repeats that code keeps as new occurrences, {index: ref}; and the cost. A repeat must name a
    record that was shown under it, and for a dated occurrence kind a record about the same occurrence (same_occurrence);
    with no date to tell occurrences apart, the model's verdict stands."""
    if not entries:
        return {}, {}, 0.0
    shown = [repeat_hits(domain, st, fm, body) for fm, body in entries]
    blocks = []
    for n, ((fm, body), recs) in enumerate(zip(entries, shown), 1):
        lines = "\n".join(f"  - [ref {ref}] {text}" for ref, text, _ in recs) or "  (nothing found)"
        blocks.append(f"Candidate {n} [{fm.get('date')}]: {fm.get('title')}\n{body.strip()}\nRecords:\n{lines}")
    reply, usd = ask(config.voice(p.prompts["verify"]).format(domain=domain, candidates="\n\n".join(blocks)))
    said = reply_json(reply).get("repeats", [])
    hit, kept = {}, {}
    for r in said if isinstance(said, list) else []:
        try:
            n = int(r.get("n"))
        except (TypeError, ValueError, AttributeError):
            continue
        held = {ref: d for ref, _, d in shown[n - 1]} if 1 <= n <= len(entries) else {}
        ref = str(r.get("ref"))
        if ref not in held or n - 1 in hit:
            continue
        fm = entries[n - 1][0]
        if fm.get("kind") in p.occurrence_kinds and fm.get("date") != "not-sure" and not same_occurrence(fm, held[ref]):
            kept.setdefault(n - 1, ref)
        else:
            hit[n - 1] = ref
            kept.pop(n - 1, None)
    return hit, kept, usd


class ReplyError(RuntimeError):
    """The model's reply held no JSON object to read: an error, never "nothing to file"."""


def reply_json(reply: str) -> dict:
    """The JSON object in a reply. A reply with none, or one that doesn't parse, raises ReplyError, so the session's
    mark stays and the run's error says why; only an explicit empty list means nothing new."""
    found = re.search(r"\{.*\}", reply or "", re.S)
    if not found:
        raise ReplyError(f"the reply held no JSON: {' '.join(str(reply).split())[:120]!r}")
    try:
        out = json.loads(found.group(0))
    except json.JSONDecodeError as e:
        raise ReplyError(f"the reply's JSON didn't parse ({e})") from None
    if not isinstance(out, dict):
        raise ReplyError("the reply's JSON isn't an object")
    return out


def filed_from(st: store.Store, stem: str) -> list:
    """The entries filed from a session, read from the store by their source: facts, theory statuses and links, and
    structural records; not the placement links filed with its facts, nor its renewals."""
    mine = (f"said in session {stem[:8]} ", f"agreed in session {stem[:8]} ")
    return [e for e in st.events() if str(e.fm.get("source", "")).startswith(mine)
            and e.fm.get("family") != "timeline" and e.kind != now_mod.RENEWAL]


def file_session(domain: str, root: Path, path: Path, ask=None, dry_run: bool = False, ask_structure=None,
                 ask_verify=None) -> dict:
    """Read one session whole and file what's new since it was last filed; returns counts, the session's new mark
    (`mark`), which the caller writes once all its steps on the session have succeeded, and, for a dry run, what it
    would file. The domain's pack says what's worth writing down; with no `file` words in it, nothing is filed."""
    p = pack.load(domain)
    if not p.prompts.get("file"):
        raise RuntimeError(f"engram files only for an area whose pack says what to write down; {domain}'s has no `file` words")
    cur = p.current
    ask_structure = ask_structure or (ask if ask else _ask_structure)
    ask_verify = ask_verify or (ask if ask else _ask_verify)
    ask = ask or _ask
    with contextlib.closing(db()) as c:
        upto = (c.execute("SELECT upto FROM filed WHERE session = ?", (path.stem,)).fetchone() or (0,))[0]
    size = path.stat().st_size
    s = _parse(path)
    later = owners(s, upto)
    res = {"session": path.stem[:8], "filed": 0, "dropped": [], "kept": [], "would_file": [], "usd": 0.0,
           "mark": (domain, path, max([upto, *later]), size)}
    if later:
        st = store.Store(root)
        kinds, abouts, home = shape(st, p.kinds)
        th = theory_shape(st, p.prompts.get("theory", ""))
        mine = filed_from(st, path.stem)
        already = [f"{e.date} {e.fm.get('title', '')}: {' '.join(e.body.split())[:200]}" for e in mine]
        already += [r[:300] for x in s.exchanges for r in x.ran if r.startswith("Bash:") and FILED.search(r)]
        when = {x.line: sessions._local_date(x.ts) or _now().date().isoformat() for x in s.exchanges}
        stands = standing(st)
        stories, complaints = placement_shape(st)
        rels = list(st.config.get("links", {}).get("timeline", {}).get("rels") or [])
        reply, res["usd"] = ask(config.voice(p.prompts["file"]).format(domain=domain, upto=upto, kinds=", ".join(kinds), abouts=", ".join(abouts),
                                              stories=", ".join(stories) or "none",
                                              complaints="; ".join(f"{k} ({v[0]})" for k, v in complaints.items()) or "none",
                                              conversation=conversation(s, upto), window=WINDOW,
                                              theory=th[3].replace("{upto}", str(upto)) if th else "", already="\n".join(already) or "nothing",
                                              record=record_context(domain, st, later, when, stands, p.prompts.get("record", ""))))
        parsed = reply_json(reply)
        turns = turn_before(s)
        entries, lines, places = [], [], []
        for f in parsed.get("facts") or []:
            try:
                line = int(f.get("line"))
            except (TypeError, ValueError):
                line = -1
            why = check(f, later, turns, when.get(line))
            thing = now_mod.chain_for(st, str(f.get("entity") or "")) if cur.entity_kind and f.get("kind") == cur.entity_kind else None
            if not why and cur.entity_kind and f.get("kind") == cur.entity_kind:
                why = entity_repeat(f, stands, cur, thing)
            if why:
                res["dropped"].append({"session": path.stem[:8], "line": f.get("line"), "why": why, "text": str(f.get("text", ""))[:120]})
            else:
                fm, body = entry(f, when[int(f["line"])], path.stem, kinds, abouts, home,
                                 "\n".join([later[line], str(f.get("answering", ""))]), cur,
                                 p.kinds[0] if p.kinds else "observation")
                if thing and fm["kind"] == cur.entity_kind:  # an existing chain: "Pataday" joins "Pataday 0.7%"
                    fm["thing"] = thing
                where = place(f, fm, st, stories, complaints, rels, p.occurrence_kinds)
                entries.append((placed(fm, where), body))
                lines.append(line)
                places.append((where, " ".join(str(f.get("quote", "")).split())))
        repeats, kept, usd = verify(domain, st, entries, ask_verify, p)
        res["usd"] += usd
        for i, ref in kept.items():
            if i not in repeats:
                res["kept"].append({"session": path.stem[:8], "line": lines[i],
                                    "why": f"kept: a new occurrence of something the record has ({ref})",
                                    "text": entries[i][0]["title"]})
        for i, ref in repeats.items():
            res["dropped"].append({"session": path.stem[:8], "line": lines[i], "why": f"already in {ref}",
                                   "text": entries[i][0]["title"]})
        entries = [x for i, x in enumerate(entries) if i not in repeats]
        places = [x for i, x in enumerate(places) if i not in repeats]
        for t in parsed.get("theory") or []:
            if not isinstance(t, dict):
                continue
            why = check_theory(t, later, turns, *th[:3]) if th else "the record has no theory graph"
            if why:
                res["dropped"].append({"session": path.stem[:8], "line": t.get("line"), "why": why, "text": str(t.get("quote", ""))[:120]})
            else:
                entries.append(theory_entry(t, when[int(t["line"])], path.stem, th[0]))
        revision = None
        try:
            line = int(parsed.get("structural"))
        except (TypeError, ValueError):
            line = None
        if th and line in later and p.prompts.get("structure"):
            revision, why, usd = structure(domain, st, s, line, later, turns, th, ask_structure, p.prompts.get("structure", ""))
            res["usd"] += usd
            if why:
                res["dropped"].append({"session": path.stem[:8], "line": line, "why": why, "text": "a structural theory change"})
        places += [None] * (len(entries) - len(places))  # theory changes carry no placement
        once = {}  # the same fact twice is filed once: in one second the two would share an id and the store refuse it
        for x, w in zip(entries, places):
            once.setdefault(json.dumps(x, sort_keys=True, default=str), (x, w))
        entries, places = [x for x, _ in once.values()], [w for _, w in once.values()]
        if dry_run:
            res["would_file"] = [{"session": path.stem[:8], **fm, "body": body,
                                  **({"placement": w[0]} if w and (w[0]["occurrence"] or w[0]["led_from"]) else {})}
                                 for (fm, body), w in zip(entries, places)]
            if revision:
                res["would_file"].append({"session": path.stem[:8], "kind": "theory-change", "ops": revision["ops"]})
            return res
        if revision:
            from engram import theorychange
            said = (f"{revision['quote']} (agreeing to “{' '.join(str(revision['answering']).split())}”)"
                    if revision.get("answering") else str(revision["quote"]))
            r = theorychange.apply(root, revision["ops"], by=config.owner_id() if not revision.get("answering") else "with-claude",
                                   why=str(revision.get("why", "")), said=said, date=when.get(line),
                                   source=f"agreed in session {path.stem[:8]} on {when.get(line)}")
            res["filed"] += len(r.written)
        if entries:
            with st.transaction(message=commitmsg.message("facts", n=len(entries), session=path.stem[:8])) as tx:
                dom = st.config.get("domain", {}).get("name", "")
                for (fm, body), w in zip(entries, places):
                    eid = tx.add({**fm, "domain": dom}, body).id
                    for lfm, note in links_for(eid, fm, w[0], w[1], fm.get("source", ""), st) if w else []:
                        tx.add({**lfm, "domain": dom}, note)
        res["filed"] += len(entries)
    return res


def mark(domain: str, path: Path, upto: int, size: int):
    """Move a session's filed mark: the next run reads it only once it has grown past `size`, from message `upto`."""
    with contextlib.closing(db()) as c, c:
        c.execute("INSERT INTO filed (session, domain, path, upto, bytes, at) VALUES (?, ?, ?, ?, ?, ?) "
                  "ON CONFLICT(session) DO UPDATE SET upto = excluded.upto, bytes = excluded.bytes, "
                  "at = excluded.at, path = excluded.path",
                  (path.stem, domain, str(path), upto, size, _now().isoformat(timespec="seconds")))


def answered(s: sessions.Session) -> dict[int, str]:
    """line -> Claude's message just before each of the owner's: the context he was answering."""
    before, last = {}, ""
    for x in s.exchanges:
        before[x.line] = last
        last = x.replies[-1] if x.replies else last
    return before


RENEW_CONTEXT = 4000  # the end of Claude's message before his that the renewal call sees: where a question sits


def _naming(names: list[set[str]], name: str) -> re.Pattern | None:
    """What names a thing in talk, generously: every form of every name it goes by, and each word of four letters or
    more in their barest forms. The call and the quote check do the deciding."""
    from engram.sources import waysin
    words = {f for forms in names for f in forms} | {w for f in names[-1] for w in f.split() if len(w) >= 4}
    words = {w for w in words | set(waysin.entity_phrases(name)) if len(w) >= 3}
    return re.compile(r"\b(" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) + r")\b", re.I) if words else None


def renew(domain: str, root: Path, path: Path, upto: int, ask=None, dry_run: bool = False) -> dict:
    """The renewal step, after the filer and apart from it: when the owner, or Claude's message he's answering, names a
    thing marked "last mentioned" (engram.now) as of that day, one call asks whether he said he's still on it. Code files
    a renewal only for a thing marked that day, on an exchange that names it, with his quote word for word; one a thing,
    and none for a thing this session already renewed (a refile rereads it). The question he answered is kept only when
    it's word for word in Claude's message before his. A session naming no marked thing makes no call."""
    p = pack.load(domain)
    res = {"session": path.stem[:8], "called": False, "renewed": 0, "would_renew": [], "dropped": [], "usd": 0.0}
    if not p.prompts.get("renew"):
        return res
    s = _parse(path)
    later = owners(s, upto)
    if not later:
        return res
    when = {x.line: sessions._local_date(x.ts) or _now().date().isoformat() for x in s.exchanges}
    before = answered(s)
    st = store.Store(root)
    day = date.fromisoformat(max([when[l] for l in later if l in when] or [_now().date().isoformat()]))
    forms = now_mod.names(st)
    marked = {c.thing: c for c in now_mod._chain(st, day) if now_mod.mark(c, day)}
    naming = {t: _naming(forms.get(t, [set(), set(), set()]), c.name) for t, c in marked.items()}
    named = {t: [l for l, words in later.items() if rx and rx.search(f"{before.get(l, '')}\n{words}")
                 and now_mod.mark(marked[t], date.fromisoformat(when.get(l, day.isoformat())))]
             for t, rx in naming.items()}
    mine = f"said in session {path.stem[:8]} "  # a refile rereads the session: what it renewed stays renewed
    done = {str(e.fm.get("thing")) for e in st.events(kind=now_mod.RENEWAL) if str(e.fm.get("source", "")).startswith(mine)}
    named = {t: ls for t, ls in named.items() if ls and t not in done}
    if not named:
        return res
    lines = sorted({l for ls in named.values() for l in ls})
    me = config.owner()
    exchanges = "\n\n".join(f"[line {l}]\nClaude: {' '.join(before.get(l, '').split())[-RENEW_CONTEXT:] or '(nothing)'}\n{me}: {later[l]}"
                             for l in lines)
    things = "\n".join(f"- {t}: {marked[t].name} ({now_mod.mark(marked[t], day)})" for t in named)
    reply, res["usd"] = (ask or _ask)(config.voice(p.prompts["renew"]).format(domain=domain, things=things, exchanges=exchanges))
    res["called"] = True
    turns, out = turn_before(s), []
    said = reply_json(reply).get("renewals", [])
    for r in said if isinstance(said, list) else []:
        t = str(r.get("thing")) if isinstance(r, dict) else ""
        try:
            line = int(r.get("line"))
        except (TypeError, ValueError, AttributeError):
            line = -1
        if isinstance(r, dict) and r.get("answering") and recsum._norm(str(r["answering"])) not in recsum._norm(before.get(line, "")):
            r = {k: v for k, v in r.items() if k != "answering"}  # a question not in Claude's message before his isn't kept
        why = ("not a thing marked as not mentioned for a while" if t not in named else
               "not an exchange that names it" if line not in named[t] else
               "already renewed in this session" if t in {fm["thing"] for fm, _ in out} else _his(r, later, turns))
        if why:
            res["dropped"].append({"session": path.stem[:8], "line": r.get("line") if isinstance(r, dict) else None, "why": why})
            continue
        c, said_on = marked[t], when.get(line, day.isoformat())
        title = f"{c.name}: still on it"
        about = next((e.about for e in st.events() if e.id == c.entry), [])
        who = f"{me}, answering “{' '.join(str(r['answering']).split())}”" if r.get("answering") else me
        out.append(({"title": title, "date": said_on, "reported": said_on, "kind": now_mod.RENEWAL, "thing": t, "about": about,
                     "by": config.owner_id(), "source": f"said in session {path.stem[:8]} on {said_on}", "author": "engram-capture"},
                    f"- {title}\n- {who}: “{' '.join(str(r['quote']).split())}”\n"))
    if dry_run:
        res["would_renew"] = [{"session": path.stem[:8], **fm, "body": body} for fm, body in out]
        return res
    if out:
        with st.transaction(message=commitmsg.message("renewals", n=len(out), session=path.stem[:8])) as tx:
            dom = st.config.get("domain", {}).get("name", "")
            for fm, body in out:
                tx.add({**fm, "domain": dom}, body)
    res["renewed"] = len(out)
    return res


def refile(prefixes: list[str]) -> dict[str, list[str]]:
    """Clear the filed mark of the sessions whose ids start with each prefix, so the next run reads them whole again.
    Nothing is deleted: the entries already filed from them are shown to the model as already filed."""
    out = {}
    with contextlib.closing(db()) as c, c:
        for pre in prefixes:
            hits = [r for (r,) in c.execute("SELECT session FROM filed WHERE session LIKE ? ESCAPE '\\' ORDER BY session",
                                            (pre.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",))]
            c.executemany("UPDATE filed SET upto = 0, bytes = 0 WHERE session = ?", [(h,) for h in hits])
            out[pre] = hits
    return out


def due(domain: str, now: datetime | None = None) -> list[Path]:
    """The domain's main sessions that grew since they were last filed and have been idle an hour."""
    now = now or _now()
    with contextlib.closing(sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)) as st:
        has = st.execute("SELECT 1 FROM sqlite_master WHERE name = 'file'").fetchone()
        paths = [Path(p) for (p,) in st.execute("SELECT path FROM file WHERE domain = ? AND gone IS NULL "
                                                "AND path NOT LIKE '%/subagents/%'", (domain,))] if has else []
    with contextlib.closing(db()) as c:
        done = dict(c.execute("SELECT session, bytes FROM filed WHERE domain = ?", (domain,)).fetchall())
    return [p for p in paths if p.exists() and p.stat().st_size > done.get(p.stem, 0) and now - last_message(p) >= IDLE]


@contextlib.contextmanager
def lock(wait: bool = False):
    """One run at a time; a second one finds the lock taken and skips. Teardown waits for it instead, so a run that
    started before can't file into a repo after it's torn down; it yields whether it had to wait."""
    with open(data_path("capture.lock"), "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            got = True
        except BlockingIOError:
            if not wait:
                yield False
                return
            fcntl.flock(fh, fcntl.LOCK_EX)
            got = "waited"
        yield got
        fcntl.flock(fh, fcntl.LOCK_UN)


def run(ask=None, dry_run: bool = False, summaries: bool = True, now: datetime | None = None) -> dict:
    """The hourly job: index changed sessions, file every due session of each repo set up, repair the install. A dry
    run files nothing and moves no mark; with `ask` set to `prompt_only` it also spends nothing."""
    out = {"sessions": 0, "filed": 0, "renewed": 0, "dropped": [], "kept": [], "would_file": [], "usd": 0.0, "skipped": False, "error": None, "repairs": []}
    with lock() as got:
        if not got:
            out["skipped"] = True
            return out
        from engram import config, setup
        with contextlib.closing(db()) as c:
            repos = {d: Path(r) for d, r in c.execute("SELECT domain, root FROM repo")}
        try:
            sessions.ingest(config.load())
            if summaries and not dry_run:
                for d in repos:  # without raw transcripts in the index, a session is searchable through its summary
                    if stopped := summarize.run(d)["stopped"]:
                        _error(out, f"summaries {d} stopped: {stopped}")
            summarize.index_all()
        except Exception as e:
            _error(out, f"indexing: {type(e).__name__}: {e}")
        for d, root in repos.items():
            idle = due(d, now)
            for p in idle:
                with contextlib.closing(db()) as c:
                    upto = (c.execute("SELECT upto FROM filed WHERE session = ?", (p.stem,)).fetchone() or (0,))[0]
                try:
                    r = file_session(d, root, p, ask, dry_run)
                except Exception as e:  # recorded; the session's mark stays, so the next run tries again
                    _error(out, f"{p.stem[:8]}: {type(e).__name__}: {e}")
                    continue
                try:  # after the filer and apart from it
                    rn = renew(d, root, p, upto, ask, dry_run)
                    out["renewed"] += rn["renewed"]
                    out["usd"] += rn["usd"]
                except Exception as e:  # recorded; the mark stays, so the next run reads the session again
                    _error(out, f"renew {p.stem[:8]}: {type(e).__name__}: {e}")
                else:
                    if not dry_run:
                        mark(*r["mark"])
                out["sessions"] += 1
                out["filed"] += r["filed"]
                out["dropped"] += r["dropped"]
                out["kept"] += r["kept"]
                out["would_file"] += r["would_file"]
                out["usd"] += r["usd"]
            if not dry_run and pack.load(d).prompts.get("compile"):  # what was handed over or filed, onto the map
                from engram import compile as compile_mod
                try:
                    out["usd"] += compile_mod.run(d)["usd"]
                except Exception as e:
                    _error(out, f"compile {d}: {type(e).__name__}: {e}")
            if not dry_run and pack.load(d).prompts.get("file"):  # an area engram files for: its long records summarized
                try:  # a failed call stops it, as it stops the session summaries; what's summarized before it is kept
                    out["usd"] += recsum.run(d)["usd"]
                except Exception as e:
                    _error(out, f"record summaries {d}: {type(e).__name__}: {e}")
            if not dry_run and review.on(root):  # the value review, behind its switch; off leaves the job as it was
                try:
                    out["usd"] += (review.hourly(d, root, idle, now) or {}).get("usd", 0.0)
                except Exception as e:
                    _error(out, f"review {d}: {type(e).__name__}: {e}")
        if not dry_run:
            from engram import relink
            for cid in relink.pending():  # a theory change whose background re-check never ran
                try:
                    out["usd"] += relink.run(cid, force=True).get("usd", 0.0)
                except Exception as e:
                    _error(out, f"relink {cid}: {type(e).__name__}: {e}")
            from engram import docreg
            for d, root in repos.items():
                try:  # a document gets its stable id when first indexed; a new link's heading its anchor
                    if docreg.load(root):
                        docreg.sync(root)
                except Exception as e:
                    _error(out, f"docs sync {d}: {type(e).__name__}: {e}")
                out["repairs"] += setup.repair(d)
                retry_push(root, out)
            with contextlib.closing(db()) as c, c:
                c.execute("INSERT INTO run VALUES (?, ?, ?, ?, ?, ?, ?)", (_now().isoformat(timespec="seconds"),
                          int(out["error"] is None), out["sessions"], out["filed"], len(out["dropped"]), out["usd"], out["error"]))
    return out


def _error(out: dict, msg: str):
    """Add one error to a run's record, keeping every one (not only the last)."""
    out["error"] = (f"{out['error']}; " if out.get("error") else "") + msg[:300]


def _git(root: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def unpushed(root: Path) -> tuple[int, list[str]]:
    """(commits ahead of the upstream, the entry files they hold); (0, []) when there's no upstream."""
    if not _git(root, "rev-parse", "--abbrev-ref", "@{u}").strip():
        return 0, []
    n = int(_git(root, "rev-list", "--count", "@{u}..HEAD").strip() or 0)
    files = [f for f in _git(root, "diff", "--name-only", "@{u}..HEAD", "--", store.Store(root).events_dir).split("\n") if f]
    return n, files


def retry_push(root: Path, out: dict):
    """The hourly retry: a repo that pushes and whose last push failed, or that is ahead of its upstream, is pushed."""
    st = store.Store(root)
    if not st.config.get("domain", {}).get("push") or os.environ.get("ENGRAM_SANDBOX"):
        return
    if store.push_failure(root) or unpushed(root)[0]:
        if not st.push():
            _error(out, f"push {root.name}: {(store.push_failure(root) or ('', ''))[1]}")


def record_state(root: Path) -> list[str]:
    """What's off in the repo: entry files written but not committed (a failed transaction's leftovers), commits not
    pushed, and a failing push. Empty when all is committed and pushed."""
    st = store.Store(root)
    out = []
    loose = [l[3:] for l in _git(root, "status", "--porcelain", "--untracked-files=all", "--", st.events_dir).splitlines() if l.strip()]
    if loose:
        out.append(f"{len(loose)} entry files aren't committed: " + ", ".join(loose[:5]) + (" …" if len(loose) > 5 else ""))
    n, files = unpushed(root)
    if n:
        out.append(f"{n} commits aren't pushed ({len(files)} entry files)")
    failed = store.push_failure(root)
    if failed:
        out.append(f"the last push failed (since {failed[0]}): {failed[1]}")
    return out


def problems(domain: str) -> list[str]:
    """What's wrong with capture for a repo set up for it, after repairing what can be; empty when healthy."""
    from engram import setup
    out = [f"couldn't repair {r['what']} ({r['error']})" for r in setup.repair(domain) if not r["ok"]]
    with contextlib.closing(db()) as c:
        row = c.execute("SELECT at FROM repo WHERE domain = ?", (domain,)).fetchone()
        if not row:
            return out
        last = c.execute("SELECT at, ok, error FROM run ORDER BY rowid DESC LIMIT 1").fetchone()
        last_ok = c.execute("SELECT at FROM run WHERE ok = 1 ORDER BY rowid DESC LIMIT 1").fetchone()
    since = datetime.fromisoformat(last_ok[0]) if last_ok else datetime.fromisoformat(row[0]) if row[0] else None
    if since and _now() - since > STALE:
        out.append(f"the hourly job hasn't run since {since:%Y-%m-%d %H:%M}")
    if last and not last[1]:
        out.append(f"the last run failed: {last[2]}")
    root = row and _root(domain)
    failed = store.push_failure(root) if root else None
    if failed:
        out.append(f"the record's last push failed (since {failed[0]}): {failed[1][:120]}")
    return out


def _root(domain: str) -> Path | None:
    with contextlib.closing(db()) as c:
        row = c.execute("SELECT root FROM repo WHERE domain = ?", (domain,)).fetchone()
    return Path(row[0]) if row else None


def session_start(payload: dict) -> str:
    """The SessionStart hook: check the install and repair it, saying one line only if something couldn't be fixed;
    then, for a record whose entries are read straight from events, where things stand (`engram now`); then, for the
    agent, any weekly-refinement file that won't parse (`engram refine surface`)."""
    found = repo_of(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR"))
    if not found:
        return ""
    bad = problems(found[0])
    if why := pack.problem(found[0]):
        bad.append(f"its pack didn't load, so nothing is filed: {why}")
    out = [f"engram capture needs fixing ({'; '.join(bad)}): run `engram capture status` and tell {config.owner()} in one line."] if bad else []
    if copy := daily.stalled():  # not capture's: its own line, so it never reads as capture broken
        out.append(f"engram's daily copy {copy}: run `engram health` and tell {config.owner()} in one line.")
    conf = record_conf(found[1])
    if (conf.get("index") or {}).get("events"):
        with contextlib.suppress(Exception):  # the picture is a help; a broken record mustn't block the session
            out.append(now_mod.text(found[1], mark_shown=True))
    with contextlib.suppress(Exception):
        out += [t] if (t := refine.surface(found[1])) else []
    return "\n\n".join(out)
