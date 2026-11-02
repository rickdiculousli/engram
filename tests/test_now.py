"""Where things stand: the "last mentioned" mark, which only the printed picture carries."""
import json
from datetime import date

import pytest

from conftest import NOTES_PACK, make_repo
from engram import capture, now
from engram.cli import main
from engram.store import Store

CURRENT = """
from engram.pack import Current
pack.current = Current(entity_kind="med-change", entity_prefix="med", detail="dose", statuses=("taking", "stopped"),
                       repeats={"taking": {"taking"}, "stopped": {"stopped"}}, groups={"supplement": "supplements"},
                       group="medications", sections=("medications", "supplements", "stopped"))
"""
TOML = '[domain]\nname = "notes"\nevents_dir = "events"\n[about]\nprefixes = ["series", "story"]\n'


@pytest.fixture
def quiet(env):
    """A supplement started in March and not mentioned since, and a medication started in October."""
    (env["tmp"] / "pack").mkdir()
    (env["tmp"] / "pack/__init__.py").write_text((NOTES_PACK / "__init__.py").read_text() + CURRENT)
    repo = make_repo(env["tmp"] / "notes", {".engram/engram.toml": TOML})
    st = Store(repo)
    n = iter(range(10, 99))

    def add(**fm):
        body = fm.pop("body", "")
        return st.add({"recorded": f"2026-10-01T11:{next(n):02d}:00-07:00", "about": ["series/meds"], **fm}, body)
    add(kind="med-change", entity="Zinc picolinate", group="supplement", status="taking", date="2026-03-01", body="- dose: 30mg")
    add(kind="med-change", entity="Drop X", status="taking", date="2026-10-01", body="- dose: 1 drop")
    env["set_repo"]("notes", repo, pack=env["tmp"] / "pack")
    return {"repo": repo, "add": add}


def _line(repo, name, day):
    return next(l for l in now.text(repo, day).splitlines() if l.startswith(f"- {name}:"))


def test_the_picture_marks_a_thing_not_mentioned_in_90_days(quiet):
    repo, add = quiet["repo"], quiet["add"]
    assert "last mentioned" not in _line(repo, "Zinc picolinate", date(2026, 5, 30))  # 90 days
    assert _line(repo, "Zinc picolinate", date(2026, 5, 31)).startswith("- Zinc picolinate: since 2026-03-01; 30mg; last mentioned 2026-03 [")
    add(kind="observation", title="Asked whether zinc picolinate helps", date="2026-06-10", by="with-claude", body="- idea")
    assert "last mentioned 2026-03" in _line(repo, "Zinc picolinate", date(2026, 8, 1))  # not the owner's words
    add(kind="observation", title="Zinc picolinate upsets their stomach before breakfast", date="2026-06-10", by="sam", body="- said")
    assert "last mentioned" not in _line(repo, "Zinc picolinate", date(2026, 8, 1))  # their own entry its way in names
    assert "last mentioned 2026-06" in _line(repo, "Zinc picolinate", date(2026, 9, 9))
    add(kind="med-change", entity="Zinc picolinate", status="taking", date="2026-09-01", body="- dose: 15mg")
    assert "last mentioned" not in _line(repo, "Zinc picolinate", date(2026, 10, 1))  # a new entry on its chain


def test_search_rows_and_the_filers_input_leave_the_mark_out(quiet, tmp_path):
    repo = quiet["repo"]
    assert "last mentioned 2026-03" in _line(repo, "Zinc picolinate", date(2026, 10, 18))
    rows = {d.ref: d.body for d in now.docs_for(repo, date(2026, 10, 18))}
    assert rows["now:med/zinc-picolinate"] == "Zinc picolinate: taking since 2026-03-01. 30mg\nhistory: taking 2026-03-01"
    main(["ingest", "--domain", "notes"])
    session = tmp_path / "s1.jsonl"
    session.write_text(json.dumps({"type": "user", "timestamp": "2026-10-18T20:00:00Z", "cwd": "/x",
                                   "message": {"role": "user", "content": "the drops are fine"}}) + "\n")
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return '{"facts": [], "theory": []}', 0.0
    capture.file_session("notes", repo, session, ask=ask, dry_run=True)
    assert "Zinc picolinate: taking since 2026-03-01; 30mg\n" in prompts[0] and "last mentioned" not in prompts[0]
