"""The index build: each domain's record files, the sources its pack reads, and what's built over them, re-read
before a question is answered when the record has changed since the last read."""
import contextlib
import fcntl
import hashlib
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from engram import config, dates, search, summarize
from engram.index import open_index
from engram.paths import data_dir, data_path, index_path
from engram.sources import events, said, sections, sessions, storygraph, vault, waysin

STALE = timedelta(minutes=15)  # how long a pack's own sources, which git doesn't show changing, go between reads
PATIENCE = 5  # seconds a question waits for a read of its domain already under way


def state(d: config.Domain) -> str:
    """What a read of the record would see, as one hash: the domain's settings, the day (where things stand follows
    the calendar), the commit, and each file git calls changed or new under the record's folder with its size and time,
    so a second edit to a changed file shows. Outside git, every file the index reads. Empty when it can't be told,
    which never counts as read."""
    git = lambda *a: subprocess.run(["git", "--no-optional-locks", "-C", str(d.repo), *a], capture_output=True, text=True)
    try:
        st = git("status", "--porcelain", "-z", "--untracked-files=all", "--", ".")
        if st.returncode:  # a folder outside git
            top, files = d.repo, [(str(f), str(f)) for f in sections.files(d)]
        else:  # git names files from the top of its repo, which a record in a subfolder isn't
            top, files = Path(git("rev-parse", "--show-toplevel").stdout.strip()), [(x, x[3:]) for x in st.stdout.split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = [repr(d), date.today().isoformat(), git("rev-parse", "HEAD").stdout.strip()]
    for line, rel in files:
        try:
            at = (top / rel).stat()
            parts.append(f"{line}:{at.st_size}:{at.st_mtime_ns}")
        except OSError:
            parts.append(line)
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


@contextlib.contextmanager
def _reading(domain: str, patience: float | None = None):
    """One read of a domain at a time (two at once collide on the same rows). Yields whether the lock is held: always
    once it's free, or, given `patience` seconds, False when a read still holds it then."""
    data_dir().mkdir(parents=True, exist_ok=True)
    with open(data_path("{domain}.lock", domain), "a") as fh:
        until = None if patience is None else time.monotonic() + patience
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | (fcntl.LOCK_NB if until is not None else 0))
                break
            except BlockingIOError:
                if time.monotonic() >= until:
                    yield False
                    return
                time.sleep(0.1)
        yield True


def read_pack(idx, domain: str, names: list[str]) -> tuple[list[str], list]:
    """Index the sources the domain's pack reads, by name: their records, and their links with the source's name as
    their family. Gives a line per source, and the ways in they open."""
    from engram import pack
    d, p = config.load()[domain], pack.load(domain)
    out, ways = [], []
    for name in names:
        try:
            src, docs = p.read[name](d.repo), []
            for doc in src.docs:  # a long record is cut into chunks, as a file's section is
                doc.author = config.voice(doc.author)
                doc.date_key = doc.date_key or dates.key(doc.date)
                parts = sections.chunks(doc.body)
                docs += [doc] if len(parts) == 1 else [replace(doc, ref=f"{doc.ref}@{i}", body=part, parent=doc.ref)
                                                       for i, part in enumerate(parts, 1)]
            out.append(f"{name} {idx.sync_source(name, docs)['rows']}")
            if name not in p.on_request:
                with idx.db:
                    idx.db.execute("DELETE FROM link WHERE family = ?", (name,))
                    idx.db.executemany("INSERT INTO link (from_ref, to_ref, family, rel, story, event, note) VALUES (?, ?, ?, ?, '', '', ?)",
                                       [(l.from_ref, l.to_ref, name, l.rel, l.note) for l in src.links])
                ways += src.ways
        except Exception as e:  # recorded so health and every search header show it; the source stays as last read
            idx.record_error(name, f"{type(e).__name__}: {e}")
            out.append(f"{name} failed: {e}")
    return out, ways


def record(domain: str, _files=sections, derived: bool = True) -> str:
    """Read the domain's record: its files, each source its pack reads before every search, and what's built over them,
    once any read of it under way is done. `derived` off leaves out what's built by searching the record itself, a
    search per passage (the threads of what was said in sessions, and of documents on none): a question never waits for
    those, and they stay as last built.
    (`_files` is what older callers pass, a pinned pack's tests among them; the files are always read.)"""
    with _reading(domain):
        return _record(domain, derived)


def _record(domain: str, derived: bool) -> str:
    from engram import pack
    d = config.load()[domain]
    seen = state(d)  # before the read, so a change that lands during it is read next time
    idx = open_index(index_path(domain))
    try:
        docs = sections.docs_for(d)
        is_vault = vault.is_vault(d.repo)
        docs, vlinks, vways, vstats = vault.read(d.repo, docs, vault.Reading(vault.load_map(domain)[0])) if is_vault else (docs, [], [], None)
        out = f"{domain}: {sections.SOURCE} {idx.sync_source(sections.SOURCE, docs)}"
        conf = search.repo_conf(domain)
        if events.enabled(conf):  # a record without rendered log pages: its entries straight from their events
            out += f"; entries {idx.sync_source(events.SOURCE, events.docs_for(d))['rows']}"
            from engram import now
            if why := pack.problem(domain):  # the picture as last indexed stays until the pack loads again
                out += f"; where things stand kept as last indexed (its pack didn't load: {why})"
            else:
                out += f"; where things stand {idx.sync_source(now.SOURCE, now.docs_for(d.repo))['rows']}"
        elif idx.db.execute("SELECT 1 FROM doc WHERE source = ? LIMIT 1", (events.SOURCE,)).fetchone():
            idx.sync_source(events.SOURCE, [])
        p = pack.load(domain)
        lines, ways = read_pack(idx, domain, [n for n in p.read if n not in p.on_request])
        out += "".join(f"; {l}" for l in lines)
        out += f"; story links {storygraph.sync(idx, d)}"
        if is_vault:
            vault.sync_links(idx, vlinks)
            out += f"; vault {vstats}"
        out += f"; ways in {waysin.sync(idx, d, conf, ways + vways)}"
        if derived:
            out += f"; said in sessions {idx.sync_source(said.SOURCE, said.docs_for(domain))['rows']}"
            from engram.sources import place
            out += f"; documents placed by their words {place.sync(idx, domain)}"
        from engram import recsum
        out += f"; summaries {recsum.sync(idx, domain)}"
        with idx.db:
            idx.db.execute("UPDATE ingest_state SET watermark = ? WHERE source = ? AND key = ''", (seen, sections.SOURCE))
        return out
    except Exception as e:  # recorded so health and every search header show it
        idx.record_error(sections.SOURCE, f"{type(e).__name__}: {e}")
        return f"{domain}: {sections.SOURCE} failed: {e}"
    finally:
        idx.close()


def _own_sources(domain: str) -> bool:
    """Whether the domain's pack reads sources of its own before every search: rows a tool keeps, outside what git shows."""
    from engram import pack
    if pack.problem(domain):
        return False
    p = pack.load(domain)
    return any(n not in p.on_request for n in p.read)


def _frozen() -> bool:
    """A scratch iteration's index stays as it is (ENGRAM_FROZEN, or a data folder under scratch/), so a comparison
    isn't moved by a read or by new sessions arriving mid-run."""
    return bool(os.environ.get("ENGRAM_FROZEN")) or "/scratch/" in str(data_dir())


def _behind(domain: str, d: config.Domain) -> bool:
    """Whether the index is behind the record: never read, its files changed since (`state`), or, where its pack reads
    sources of its own, that read over 15 minutes old."""
    idx = open_index(index_path(domain), readonly=True)
    row = idx.db.execute("SELECT watermark, last_ok FROM ingest_state WHERE source = ? AND key = ''",
                         (sections.SOURCE,)).fetchone() if idx else None
    if idx:
        idx.close()
    if not row or not row["last_ok"] or not (now := state(d)) or row["watermark"] != now:
        return True
    return datetime.now().astimezone() - datetime.fromisoformat(row["last_ok"]) > STALE and _own_sources(domain)


def refresh_if_stale(domains: list[str]):
    """Re-read a domain's record before a question is answered when the index is behind it (`_behind`), so what was
    just filed or saved is there. Only the files and the pack's sources: what's built by searching the record waits
    for the hourly job or `engram ingest`. A read already under way is waited for a few seconds, then left to finish,
    and whoever waited reads only if the index is still behind."""
    if _frozen():
        return
    doms = config.load()
    for name in domains:
        if doms[name].repo and _behind(name, doms[name]):
            with _reading(name, PATIENCE) as mine:
                if mine and _behind(name, doms[name]):
                    _record(name, derived=False)


def refresh_sessions():
    """File new sessions and index their summaries when that was last done over 15 minutes ago."""
    if _frozen():
        return
    doms = config.load()
    stamp = data_path("sessions-last.txt")
    last_s = stamp.read_text().strip() if stamp.exists() else ""
    if not last_s or datetime.now().astimezone() - datetime.fromisoformat(last_s) > STALE:
        try:
            sessions.ingest(doms)
            summarize.index_all()
            stamp.write_text(datetime.now().astimezone().isoformat(timespec="seconds"))
        except Exception as e:  # a failed refresh never blocks a search; health reports the age
            print(f"engram: sessions refresh failed: {e}", file=sys.stderr)


def asked(domain: str, names: list[str]) -> list[str]:
    """Sources the domain's pack reads only on request."""
    idx = open_index(index_path(domain))
    try:
        return [f"{domain}: {line}" for line in read_pack(idx, domain, names)[0]]
    finally:
        idx.close()
