"""Event dates at the precision they were known: a year, a month, a day, or not sure."""
import re
from datetime import date

DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
FIND = re.compile(r"(?<!\d)(\d{4}-\d{2}(?:-\d{2})?)(?!\d)")


def valid(value: str) -> bool:
    if value == "not-sure":
        return True
    m = DATE.match(value)
    if not m:
        return False
    y, mo, d = m.groups()
    try:  # a day that exists: no 2026-02-30
        date.fromisoformat(f"{y}-{mo or '01'}-{d or '01'}")
    except ValueError:
        return False
    return True


def key(value: str | None) -> str | None:
    """Sortable YYYY-MM-DD; an imprecise date sorts at the start of its period."""
    if not value or value == "not-sure" or not valid(value):
        return None
    y, m, d = DATE.match(value).groups()
    return f"{y}-{m or '01'}-{d or '01'}"


def first_in(text: str) -> str | None:
    m = FIND.search(text)
    return m.group(1) if m and valid(m.group(1)) else None


NUMBER = re.compile(r"\d+(?:[.,/:-]\d+)*")


def numbers(text: str) -> set[str]:
    """The whole numbers in a text, plus each part of a fraction, range, time or date ("7/10" gives 7 and 10 too); never
    a piece of a longer number, so "35" isn't in "135B" and "60" isn't in "1,600"."""
    out = set()
    for n in NUMBER.findall(text):
        out |= {n, *filter(None, re.split(r"[/:-]", n))}
    return out
