"""The data folder's one table: every caller asks it, and health names what's there that it doesn't list."""
import re
from pathlib import Path

import pytest

from engram import cli, paths

SRC = Path(__file__).resolve().parents[1]


def test_every_entry_code_asks_for_is_in_the_table():
    asked = {m for f in [*(SRC / "src").rglob("*.py"), *(SRC / "bench").rglob("*.py")]
             for m in re.findall(r'data_path\("([^"]+)"', f.read_text())}
    assert asked and asked <= paths.DATA.keys()
    with pytest.raises(KeyError):
        paths.data_path("medical.sqlite.pre-3a")


def test_health_names_each_stray_and_nothing_else(env, capsys):
    env["set_repo"]("medical", env["tmp"] / "medical")
    env["data"].mkdir()
    for f in ["medical.sqlite-wal", "usage-medical.sqlite", "capture.log", "releases.jsonl",
              "old.sqlite", "medical.sqlite.pre-3a"]:
        (env["data"] / f).write_text("")
    for d in ["packs", "summaries", "work", "clones"]:
        (env["data"] / d).mkdir()
    assert paths.strays(["medical"]) == ["clones/", "medical.sqlite.pre-3a", "old.sqlite"]  # work/ is listed
    cli.main(["health"])
    out = [l for l in capsys.readouterr().out.splitlines() if l.startswith("data folder:")]
    assert out == [f"data folder: {s} isn't one of engram's (paths.DATA)" for s in ["clones/", "medical.sqlite.pre-3a", "old.sqlite"]]
    for s in ["clones", "medical.sqlite.pre-3a", "old.sqlite"]:
        p = env["data"] / s
        p.rmdir() if p.is_dir() else p.unlink()
    cli.main(["health"])
    assert "data folder:" not in capsys.readouterr().out
