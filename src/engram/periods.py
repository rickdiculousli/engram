"""A period a question names, and the dates a row spans (.engram/README.md: a period is named in the answer's header,
never cut to). Deterministic: month and season names, years, "last month" and the like, and "since/after/before
<something>", where the something is a date or a thing the record dates (its first dated record)."""
import re
from datetime import date, timedelta

from engram import dates

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


def span(value: str | None) -> tuple[date, date] | None:
    """The dates a written date covers: its day, month or year; None for anything else or a day that doesn't exist."""
    m = dates.DATE.match(value or "")
    if not m or not dates.valid(value):
        return None
    y, mo, d = int(m.group(1)), m.group(2) and int(m.group(2)), m.group(3) and int(m.group(3))
    start = date(y, mo or 1, d or 1)
    return start, start if d else _month_end(y, mo) if mo else date(y, 12, 31)


FLOOR, SHARE = 7, 0.3  # a fuzzy date widens by 0.3 of how far back it reaches, at least a week (docs/search.md)
PAD = 30  # a memory a landmark pins widens by about a month each way, however long ago


def of(fm: dict, written: str) -> tuple[date, date] | None:
    """An entry's date range: his own ends; else its date's span, widened both ways when approximate by a share of the
    days from when it was said (`reported`, else `written`, its id day), or by PAD when a landmark pins it, and a
    recollection never ends after that."""
    if (a := span(fm.get("range_from"))) and (b := span(fm.get("range_to"))):
        return a[0], b[1]
    if not (s := span(fm.get("date"))) or str(fm.get("approx")).lower() not in ("true", "yes"):
        return s
    said = (span(fm.get("reported")) or span(written))[1]
    pad = timedelta(days=PAD if fm.get("landmark") else max(FLOOR, round(SHARE * abs((said - s[0]).days))))
    return s[0] - pad, min(s[1] + pad, said) if s[0] <= said else s[1] + pad


def mark(r: tuple[date, date] | None, p: tuple[date, date]) -> str | None:
    """How much of a date range falls inside a period: in (all of it), probably (more than half), possibly (any)."""
    if not r:
        return None
    inside = (min(r[1], p[1]) - max(r[0], p[0])).days + 1
    share = inside / ((r[1] - r[0]).days + 1)
    return "in" if share >= 1 else "probably" if share > 0.5 else "possibly" if inside > 0 else None


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
        return span(m.group(0))
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
