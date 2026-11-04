"""The index build: each domain's record files, the sources its pack reads, and what's built over them, re-read
before a search when the last read is stale."""
import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta

from engram import config, dates, search, summarize
from engram.index import open_index
from engram.paths import data_dir, data_path, index_path
from engram.sources import events, said, sections, sessions, storygraph, waysin

STALE = timedelta(minutes=15)


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


def record(domain: str, _files=sections) -> str:
    """Read the domain's record: its files, each source its pack reads before every search, and what's built over them.
    (`_files` is what older callers pass, a pinned pack's tests among them; the files are always read.)"""
    from engram import pack
    d = config.load()[domain]
    idx = open_index(index_path(domain))
    try:
        out = f"{domain}: {sections.SOURCE} {idx.sync_source(sections.SOURCE, sections.docs_for(d))}"
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
        out += f"; story links {storygraph.sync(idx, d)}; ways in {waysin.sync(idx, d, conf, ways)}"
        out += f"; said in sessions {idx.sync_source(said.SOURCE, said.docs_for(domain))['rows']}"
        from engram.sources import place
        out += f"; documents placed by their words {place.sync(idx, domain)}"
        from engram import recsum
        out += f"; summaries {recsum.sync(idx, domain)}"
        return out
    except Exception as e:  # recorded so health and every search header show it
        idx.record_error(sections.SOURCE, f"{type(e).__name__}: {e}")
        return f"{domain}: {sections.SOURCE} failed: {e}"
    finally:
        idx.close()


def refresh_if_stale(domains: list[str]):
    """Re-read today's record files when the last read is over 15 minutes old; it takes a fraction of a second. A scratch
    iteration's index stays frozen (ENGRAM_FROZEN, or a data folder under scratch/), so a comparison isn't moved by new
    sessions arriving mid-run."""
    if os.environ.get("ENGRAM_FROZEN") or "/scratch/" in str(data_dir()):
        return
    doms = config.load()
    for name in domains:
        if not doms[name].repo:
            continue
        idx = open_index(index_path(name), readonly=True)
        last = next((s["last_ok"] for s in idx.sources() if s["source"] == sections.SOURCE), None) if idx else None
        if idx:
            idx.close()
        if not last or datetime.now().astimezone() - datetime.fromisoformat(last) > STALE:
            record(name)
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
