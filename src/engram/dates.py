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
THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")


def plain(n: str) -> str:
    """A number by its value, however its thousands are written: "2,000" is 2000."""
    return THOUSANDS.sub(lambda m: m[0].replace(",", ""), n)


def numbers(text: str) -> set[str]:
    """The whole numbers in a text, each by its value (`plain`), plus each part of a fraction, range, time or date
    ("7/10" gives 7 and 10 too); never a piece of a longer number, so "35" isn't in "135B" and "60" isn't in "1,600"."""
    out = set()
    for n in map(plain, NUMBER.findall(text)):
        out |= {n, *filter(None, re.split(r"[/:-]", n))}
    return out


def printed(value: str, title: str) -> str:
    """A row's date as printed, read from the heading the index built: "~<from> to <to>" for the owner's two ends,
    "~<date>" for an approximate date, else the date."""
    m = re.search(re.escape(value) + r"( to [\d-]+)?\s*\(approx", title, re.I)
    return f"~{value}{m[1] or ''}" if m else value
