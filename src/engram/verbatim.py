"""The word-for-word check every quote of the owner's goes through: a quote counts when its text, read as a quote is
matched, is inside what it cites as whole words."""
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
    return inside(norm(quote), norm(text))


def inside(part: str, whole: str) -> bool:
    """`part` is in `whole` as whole words: where it starts or ends with a letter or digit, the text beside it there
    isn't one. Why: "no" is no quote of "I know", nor "mm" of "summer"."""
    i = whole.find(part)
    while i >= 0:
        j = i + len(part)
        if not (part[:1].isalnum() and i and whole[i - 1].isalnum()) and \
                not (part[-1:].isalnum() and j < len(whole) and whole[j].isalnum()):
            return True
        i = whole.find(part, i + 1)
    return False
