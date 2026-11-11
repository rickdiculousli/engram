"""The word-for-word check every quote of the owner's goes through: a quote counts when its text, read as a quote is
matched, is inside what it cites as whole words."""
import re

DASHES = re.compile(r"\s*[-‐-―−]\s*")
BROKEN = re.compile(r"(\w)[-­]\s*\n\s*(\w)")  # a word hyphenated across a line
UNSPACED = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f\U00020000-\U0003ffff]")  # Han and kana: no spaces between words


def norm(s: str) -> str:
    """Text as a quote is matched: curly quotes straight, a word hyphenated across lines joined, every dash one hyphen
    with no spaces round it, an ellipsis three dots, soft hyphens gone, spaces collapsed, lower case."""
    s = BROKEN.sub(r"\1\2", s.replace("­", "")).replace("…", "...")
    s = DASHES.sub("-", s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))
    return re.sub(r"\s+", " ", s).strip().lower()


def found(quote: str, text: str) -> bool:
    """The quote is in the text word for word, as `norm` reads both."""
    return inside(norm(quote), norm(text))


def _joined(a: str, b: str) -> bool:
    """Two letters or digits side by side are one word, unless either is of a script written without word spaces."""
    return a.isalnum() and b.isalnum() and not (UNSPACED.match(a) or UNSPACED.match(b))


def inside(part: str, whole: str) -> bool:
    """`part` is in `whole` as whole words: where it starts or ends with a letter or digit, the text beside it there
    isn't one of the same word. Why: "no" is no quote of "I know", nor "mm" of "summer"; in Chinese or Japanese,
    written without spaces, any run of characters can be a quote."""
    i = whole.find(part)
    while i >= 0:
        j = i + len(part)
        if not (part and i and _joined(whole[i - 1], part[0])) and not (part and j < len(whole) and _joined(part[-1], whole[j])):
            return True
        i = whole.find(part, i + 1)
    return False


def span(quote: str, text: str) -> str:
    """The words of `text` a quote `found` there matches, as they were typed there (its capitals, its spacing); the
    quote itself where only `norm` tells them apart."""
    words = quote.split()
    pat = (r"(?<!\w)" if words and words[0][0].isalnum() else "") + r"\s+".join(map(re.escape, words)) + \
        (r"(?!\w)" if words and words[-1][-1].isalnum() else "")
    m = re.search(pat, text, re.I) if words else None
    return m[0] if m else quote
