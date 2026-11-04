"""The filer's word-for-word check: a quote counts when its text, read as a quote is matched, is inside what it cites."""
import re

DASHES = re.compile(r"\s*[-‐-―−]\s*")
BROKEN = re.compile(r"(\w)[-­]\s*\n\s*(\w)")  # a word hyphenated across a line


def norm(s: str) -> str:
    """Text as a quote is matched: curly quotes straight, a word hyphenated across lines joined, every dash one hyphen
    with no spaces round it, an ellipsis three dots, soft hyphens gone, spaces collapsed, lower case."""
    s = BROKEN.sub(r"\1\2", s.replace("­", "")).replace("…", "...")
    s = DASHES.sub("-", s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))
    return re.sub(r"\s+", " ", s).strip().lower()


def found(quote: str, text: str) -> bool:
    """The quote is in the text word for word, as `norm` reads both."""
    return norm(quote) in norm(text)
