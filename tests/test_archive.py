import os
import sqlite3

from engram import archive


def write(p, text, mtime=None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if mtime:
        os.utime(p, (mtime, mtime))


def test_archive_keeps_new_lines_and_every_version(tmp_path):
    m, db = tmp_path / "mirror", tmp_path / "a.sqlite"
    store = m / "_harness/store/price/yahoo.jsonl"
    page = m / "_harness/runtime/away.md"
    write(store, '{"k": 1}\n{"k": 2}\n', 1_000_000)
    write(page, "# Away\nday one\n", 1_000_000)
    write(m / "_harness/cache/voice-packets/x/frame.jpg", "\xff\xd8binary", 1_000_000)
    first = archive.ingest(m, db)
    assert (first["new_records"], first["new_artifacts"]) == (2, 2)

    again = archive.ingest(m, db)
    assert again["changed"] == 0 and again["new_records"] == again["new_artifacts"] == 0

    write(store, '{"k": 1}\n{"k": 2}\n{"k": 3}\n', 2_000_000)
    write(page, "# Away\nday two\n", 2_000_000)
    grown = archive.ingest(m, db)
    assert (grown["new_records"], grown["new_artifacts"]) == (1, 1)

    c = sqlite3.connect(db)
    assert c.execute("SELECT count(*) FROM artifact_path WHERE path LIKE '%away.md'").fetchone()[0] == 2
    assert c.execute("SELECT blob IS NOT NULL FROM artifact WHERE kind = 'cache/voice-packets'").fetchone()[0] == 1
    assert archive.verify(m, db) == {"files": 3, "missing_store_lines": 0, "missing_files": 0}

    write(m / "_harness/runs/new.md", "not ingested yet\n")
    assert archive.verify(m, db)["missing_files"] == 1


def test_backup_keeps_the_newest(tmp_path):
    db = tmp_path / "a.sqlite"
    archive.connect(db).close()
    out = tmp_path / "backups"
    for day in range(1, 10):
        (out / f"archive-202610{day:02d}.sqlite").parent.mkdir(parents=True, exist_ok=True)
        (out / f"archive-202610{day:02d}.sqlite").write_text("")
    made = archive.backup(db, out, keep=3)
    kept = sorted(p.name for p in out.glob("archive-*.sqlite"))
    assert made.name in kept and len(kept) == 3
    assert sqlite3.connect(made).execute("SELECT count(*) FROM record").fetchone()[0] == 0
