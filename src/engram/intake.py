"""What the owner hands over, kept as saved (docs/data-model.md, "Sources and sparks"): a web page, a video, an image,
a scribble or a quote is an entry of kind `source`, its body the text (code fetches a page itself; for a video or an
image the advisor passes the text it got, marked `transcribed_by`); the owner's own thought is a `spark`, with
`sparked_by` the source that set it off without being its point. A file handed over is kept beside it under
`events/files/<sha256>.<ext>`, append-only like every event file. One transaction."""
import hashlib
import html.parser
import re
import urllib.request
from datetime import date
from pathlib import Path

from engram import config, store

FORMS = ("page", "video", "image", "note", "quote")  # a source's form; `spark` is the owner's own
FILES = "files"
SKIP = {"script", "style", "noscript", "template", "svg", "head", "nav", "footer", "form"}
BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "pre", "section",
         "article", "header", "figcaption", "dd", "dt", "hr", "table"}


class _Text(html.parser.HTMLParser):
    """A page's title and readable text: no markup, scripts, styles or navigation; a block is its own paragraph."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.parts, self.skip, self.in_title = "", [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def page_text(markup: str) -> tuple[str, str]:
    """(title, text) of an HTML page."""
    p = _Text()
    p.feed(markup)
    paras = [" ".join(x.split()) for x in re.split(r"\n\s*\n", "".join(p.parts))]
    return " ".join(p.title.split()), "\n\n".join(x for x in paras if x)


def fetch(url: str) -> tuple[str, str]:
    """A page's title and text, fetched with the standard library."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (engram)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        markup = r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    return page_text(markup)


def keep(st: store.Store, path: Path) -> str:
    """Copy a handed-over file into `events/files/`, named by its content, and return its path in the repo."""
    data = Path(path).expanduser().read_bytes()
    rel = f"{st.events_dir}/{FILES}/{hashlib.sha256(data).hexdigest()}{Path(path).suffix.lower()}"
    dest = st.root / rel
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return rel


def add(st: store.Store, kind: str, text: str, title: str = "", by: str = "", url: str = "", file: Path | None = None,
        transcribed_by: str = "", sparked_by: str = "") -> store.Event:
    """One source or spark in one commit, with its file."""
    if kind != "spark" and kind not in FORMS:
        raise ValueError(f"a source is one of {', '.join(FORMS)}, or a spark")
    if kind == "page" and url and not text.strip():
        got, text = fetch(url)
        title = title or got
    if not text.strip() and not file:
        raise ValueError("nothing to keep: give the text on stdin, a --url to fetch or a --file")
    today = date.today().isoformat()
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    fm = {"title": title or first[:120] or Path(file).name, "date": today, "author": "claude",
          "domain": st.config.get("domain", {}).get("name", "")}
    if kind == "spark":
        fm.update(kind="spark", by=config.owner_id(), sparked_by=sparked_by)
    else:
        fm.update(kind="source", form=kind, by=f"other:{by}" if by else "", url=url, transcribed_by=transcribed_by)
    with st.transaction() as tx:
        if file:
            fm["file"] = keep(st, file)
            tx.extra.append(fm["file"])
        e = tx.add(fm, text.strip() + "\n")
    return e
