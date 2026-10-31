"""A period a question names, and the dates a row spans (.engram/README.md: a question about a period is cut to it, plus
what led into it; fuzzy dates are ranges that widen the further back they reach). Deterministic: month and season
names, years, "last month" and the like, and "since/after/before <something>", where the something is a date or a
thing the record dates (its first dated record)."""
import re
from datetime import date, timedelta

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], 1)}
MONTHS |= {m[:3]: i for m, i in list(MONTHS.items())} | {"sept": 9}
SEASONS = {"spring": (3, 5), "summer": (6, 8), "fall": (9, 11), "autumn": (9, 11), "winter": (12, 2)}
YEAR = r"(20\d\d)"


def _month_end(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def _season(y: int, name: str) -> tuple[date, date]:
    """A season of year y; winter is December of the year before through February."""
    a, b = SEASONS[name]
    return (date(y - 1, 12, 1), _month_end(y, 2)) if a > b else (date(y, a, 1), _month_end(y, b))


def _past(y: int | None, m: int, today: date) -> int:
    """The year of the most recent such month, when none is given."""
    return y or (today.year if m <= today.month else today.year - 1)


def span(text: str | None, today: date | None = None) -> tuple[date, date] | None:
    """The dates a written date covers: a day, a month, a year; `~`, "approx" or "around" widen it by a month, and a
    further month for each year before today."""
    if not text:
        return None
    today = today or date.today()
    m = re.search(r"(20\d\d)(?:-(\d\d)(?:-(\d\d))?)?", text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), m.group(2) and int(m.group(2)), m.group(3) and int(m.group(3))
    start = date(y, mo or 1, d or 1)
    end = date(y, mo, d) if d else _month_end(y, mo) if mo else date(y, 12, 31)
    if re.search(r"~|approx|around|about|early|mid|late", text, re.I):
        pad = timedelta(days=30 * (1 + max(0, (today - start).days // 365)))
        start, end = start - pad, end + pad
    return start, end


def _when(phrase: str, today: date, bare: bool = False) -> tuple[date, date] | None:
    """A date-like phrase: a month (with or without its year), a season, a year, or a relative period."""
    p = phrase.lower()
    if m := re.search(r"\b(last|this|past)\s+(spring|summer|fall|autumn|winter)\b", p):
        for y in range(today.year + 1, today.year - 3, -1):  # the latest one ended (last) or begun (this) by today
            a, b = _season(y, m.group(2))
            if (b < today) if m.group(1) in ("last", "past") else (a <= today):
                return a, b
    if m := re.search(r"\b(spring|summer|fall|autumn|winter)\s+(?:of\s+)?" + YEAR, p):
        return _season(int(m.group(2)), m.group(1))
    names = "|".join(sorted(MONTHS, key=len, reverse=True))
    if m := re.search(r"(?:\b(in|during|since|by|after|before|until|through|of|back in|early|mid|late)\s+)?\b(" + names
                      + r")\b\.?,?\s*(?:of\s+)?" + YEAR + "?", p):
        if m.group(1) or m.group(3) or bare:  # a month alone is a period only after "in", "since"… ("like the june PRF" isn't)
            mo = MONTHS[m.group(2)]
            y = _past(int(m.group(3)) if m.group(3) else None, mo, today)
            return date(y, mo, 1), _month_end(y, mo)
    if m := re.search(r"\b(20\d\d)-(\d\d)(?:-(\d\d))?\b", p):
        return span(m.group(0), today)
    if m := re.search(r"\b(?:in|during|since|after|before|until|throughout)\s+" + YEAR + r"\b", p):
        y = int(m.group(1))
        return date(y, 1, 1), date(y, 12, 31)
    if re.search(r"\blast month\b", p):
        first = today.replace(day=1) - timedelta(days=1)
        return first.replace(day=1), first
    if m := re.search(r"\b(?:past|last)\s+(\d+|few|couple of)\s+(week|month)s?\b", p):
        n = {"few": 3, "couple of": 2}.get(m.group(1)) or int(m.group(1))
        return today - timedelta(days=n * (7 if m.group(2) == "week" else 30)), today
    if re.search(r"\b(lately|recently|these days)\b", p):
        return today - timedelta(days=60), today
    if re.search(r"\blast year\b", p):
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if re.search(r"\bthis year\b", p):
        return date(today.year, 1, 1), today
    return None


def period(text: str, today: date | None = None, dated=None) -> tuple[date, date] | None:
    """The period a question names, or None. `dated(phrase)` gives the first date the record has for a thing it names
    ("since the PRF"), for "since/after/before <thing>"."""
    today = today or date.today()
    p = text.lower()
    if m := re.search(r"\b(since|after|following|before|until|prior to)\s+(?:the\s+|my\s+|starting\s+|i\s+started\s+)?([\w\-/ ]{2,40}?)(?=[?.,;!]|\s+(?:and|but|did|has|have|was|is|how|what|when|why)\b|$)", p):
        word, what = m.group(1), m.group(2).strip()
        at = _when(what, today, bare=True)
        anchor = at and (at[1] if word == "until" else at[0])  # since or before August: its first day; until August: its last
        if anchor is None and dated and word not in ("after", "following"):  # "soreness after the session" is a cause, not a period
            anchor = dated(what)
        if anchor:
            return (anchor, today) if word in ("since", "after", "following") else (date(2000, 1, 1), anchor)
    return _when(p, today)
