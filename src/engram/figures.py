"""The number matcher (docs/technical.md, "Building without touching what runs"; build group 6a). A figure is a whole number
in a text, read with its money, magnitude, percent or share-count marks, so "$1.5k", "1,500" and "1.5k USD" are one
value. A range, fraction or time counts by its parts ("80-81" is 80 and 81; "$1-2M" is 1M and 2M), never as a whole,
and never as a piece of a longer number: "35" isn't in "135" or "3.35". Dates, cite ids, paths, links and hex ids
aren't figures.

`amounts` finds the money and share counts the commit check keeps out of commit messages."""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CUR = r"(?:US\$|C\$|A\$|\$|€|£|¥)"
NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+"
SEP = r"\s?[-–—/:]\s?"
WORDS = {"thousand": 3, "million": 6, "billion": 9, "trillion": 12}
SUFFIX = {"k": 3, "K": 3, "mm": 6, "MM": 6, "M": 6, "bn": 9, "BN": 9, "B": 9}
WITH_CURRENCY = {"m": 6, "b": 9, "tn": 12, "T": 12}  # too ambiguous alone ("5m" may be minutes)
FIGURE = re.compile(
    rf"(?<![A-Za-z0-9_.])(?:(?P<cur>{CUR})\s?)?(?P<num>(?:{NUM})(?:{SEP}{CUR}?(?:{NUM}))*)"
    r"(?:(?P<suf>mm|MM|bn|BN|tn|[kKmMbBT])(?![A-Za-z])|\s(?P<word>thousand|million|billion|trillion)\b)?"
    r"(?:\s?(?P<pct>%|percent\b|pct\b|bps?\b)|\s?(?P<code>USD|EUR|GBP|dollars?)\b|\s(?P<sh>shares?\b|sh\b))?")
PART = re.compile(NUM)

NOT_FIGURES = [re.compile(p) for p in (
    r"https?://\S+",
    r"\S*(?:_harness|reports|ledger|journal|threads|cache|runs|store|record|judgment|intel|pages|sessions)/\S*",  # paths, a ledger row's ref
    r"\S+\.(?:md|jsonl?|txt|csv|py|toml)\b\S*",
    r"\d{4}-(?:0[1-9]|1[0-2])-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?",  # ISO dates and stamps
    r"(?<!\d)\d{4}-(?:0[1-9]|1[0-2])(?![\d-])",  # "2025-26" is a range, not a month
    r"\b(?:p?TH\d\d|[PRH]\d{1,3})\b",  # thesis, page and hit ids
    r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{6,}\b",  # run, session and commit ids
)]


@dataclass(frozen=True)
class Figure:
    raw: str        # the whole match, "$1-2M"
    part: str       # this part as written, "2"
    value: Decimal  # scaled, 2000000
    kind: str       # "money", "scaled" ("1.5M", no currency), "percent", "shares" or "number"
    span: tuple[int, int]


def clean(text: str) -> str:
    """The text with what isn't a figure blanked out, same length, so spans still point into the original."""
    for p in NOT_FIGURES:
        text = p.sub(lambda m: " " * len(m.group(0)), text)
    return text


def figures(text: str) -> list[Figure]:
    """Every figure in a text, a range or fraction as one per part."""
    out = []
    for m in FIGURE.finditer(clean(text)):
        suf, word, cur = m.group("suf"), m.group("word"), m.group("cur")
        scale = WORDS.get(word or "", 0) or SUFFIX.get(suf or "", 0) or (WITH_CURRENCY.get(suf or "", 0) if cur else 0)
        if suf and not scale:  # "5m" alone: the letter isn't a magnitude, and this is a plain 5
            suf = None
        kind = ("money" if cur or m.group("code") else "scaled" if scale else "percent" if m.group("pct")
                else "shares" if m.group("sh") else "number")
        raw = text[m.start():m.end()].strip()
        for p in PART.finditer(m.group("num")):
            try:
                v = Decimal(p.group(0).replace(",", "")).scaleb(scale)
            except InvalidOperation:
                continue
            out.append(Figure(raw, p.group(0), v, kind, (m.start(), m.end())))
    return out


AMOUNT = ("money", "shares")  # a bare "6M" is as often months or tokens: one record's log has five


def amounts(text: str) -> list[Figure]:
    """The money and share counts in a text: what no commit message may carry."""
    return [f for f in figures(text) if f.kind in AMOUNT]


def strip(text: str) -> str:
    """The text with every amount taken out, for the hourly path, which must never fail on one."""
    spans = sorted({f.span for f in amounts(text)}, reverse=True)
    for a, b in spans:
        text = text[:a] + "[amount]" + text[b:]
    return text
