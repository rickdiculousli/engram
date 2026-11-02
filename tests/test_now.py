"""Where things stand: the "last mentioned" mark, which only the printed picture carries, and the renewal that clears it."""
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
pack.prompts["renew"] = "Did {owner} say he's still on these?\\n{things}\\n{exchanges}"
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


def _session(tmp_path, name, turns, ts="2026-10-18T20:00:00Z"):
    path = tmp_path / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps({"type": k, "timestamp": ts, "cwd": "/x", "message": {"role": k, "content": t if k == "user" else [
        {"type": "text", "text": t}]}}) for k, t in turns) + "\n")
    return path


def _asking(renewals, calls):
    def ask(prompt):
        calls.append(prompt)
        return json.dumps({"renewals": renewals}), 0.01
    return ask


def test_a_renewal_clears_the_mark_and_moves_nothing_else_in_the_line(quiet):
    repo = quiet["repo"]
    day = date(2026, 10, 19)
    before, rows = _line(repo, "Zinc picolinate", day), now.docs_for(repo, day)
    Store(repo).add({"kind": now.RENEWAL, "thing": "med/zinc-picolinate", "title": "Zinc picolinate: still on it",
                     "date": "2026-10-18", "by": "sam", "about": ["series/meds"]}, "- still on it\n")
    after = _line(repo, "Zinc picolinate", day)
    assert "last mentioned 2026-03" in before and "last mentioned" not in after
    assert after.split(" [")[0] == before.split("; last mentioned")[0]  # status, dose, since, name: as they were
    assert [vars(d) for d in now.docs_for(repo, day)] == [vars(d) for d in rows]  # search's rows don't move
    assert [c.thing for c in now.build(repo, day)["supplements"]] == ["med/zinc-picolinate"]  # nor its section


def test_the_renewal_step_files_only_his_word_on_a_marked_thing(quiet, tmp_path):
    repo = quiet["repo"]
    calls = []
    quiet_one = _session(tmp_path, "s1", [("user", "the drops are fine"), ("assistant", "Good.")])
    assert not capture.renew("notes", repo, quiet_one, 0, _asking([], calls))["called"] and calls == []  # names no marked thing
    early = _session(tmp_path, "s0", [("user", "hi"), ("assistant", "Still on the zinc?"), ("user", "yes")], ts="2026-05-15T20:00:00Z")
    assert capture.renew("notes", repo, _session(tmp_path, "s9", [("user", "hi"), ("assistant", "Still on the zinc?"), ("user", "yes")]), 0,
                         _asking([], []), dry_run=True)["called"]  # the same words on a day it's marked do call
    assert not capture.renew("notes", repo, early, 0, _asking([], calls))["called"]  # not marked yet that day
    s2 = _session(tmp_path, "s2", [("user", "quick check in"), ("assistant", "Are you still taking the zinc picolinate?"),
                                   ("user", "yes"), ("assistant", "And the drops?"), ("user", "those too")])
    yes = {"thing": "med/zinc-picolinate", "line": 3, "quote": "yes", "answering": "Are you still taking the zinc picolinate?"}
    said = [{**yes, "quote": "yes, every day"},  # not his words
            {"thing": "med/drop-x", "line": 5, "quote": "those too"},  # not marked
            yes, {**yes}]  # one a thing
    res = capture.renew("notes", repo, s2, 0, _asking(said, calls))
    assert res["called"] and len(calls) == 1 and res["renewed"] == 1
    assert "med/zinc-picolinate: Zinc picolinate (last mentioned 2026-03)" in calls[0] and "med/drop-x" not in calls[0]
    assert [d["why"] for d in res["dropped"]] == ["quote not in Sam's words", "not a thing marked as not mentioned for a while",
                                                  "already renewed in this session"]
    renewal = next(e for e in Store(repo).events(kind=now.RENEWAL))
    assert renewal.fm["thing"] == "med/zinc-picolinate" and renewal.fm["date"] == "2026-10-18" and "“yes”" in renewal.body
    assert "last mentioned" not in _line(repo, "Zinc picolinate", date(2026, 10, 19))
    assert not capture.renew("notes", repo, s2, 0, _asking([yes], calls))["called"]  # renewed: no longer marked


def _renewal(repo, date_, source="said in session s0 on 2026-10-18"):
    return Store(repo).add({"kind": now.RENEWAL, "thing": "med/zinc-picolinate", "title": "Zinc picolinate: still on it",
                            "date": date_, "by": "sam", "about": ["series/meds"], "source": source}, "- still on it\n")


def test_a_renewal_is_never_offered_to_the_filer_nor_to_the_evidence_recheck(quiet):
    from engram import relink
    repo = quiet["repo"]
    r = _renewal(repo, "2026-10-18")
    assert now.RENEWAL not in capture.shape(Store(repo))[0]  # the record holds one; the filer's kinds still leave it out
    assert r.id not in [i for i, *_ in relink.records(repo)]


def test_a_refile_never_renews_what_the_session_already_renewed(quiet, tmp_path):
    repo, calls = quiet["repo"], []
    _renewal(repo, "2026-03-15", source="said in session s2 on 2026-03-15")  # old enough that the thing is marked again
    s2 = _session(tmp_path, "s2", [("user", "hi"), ("assistant", "Are you still taking the zinc picolinate?"), ("user", "yes")])
    assert "last mentioned 2026-03" in _line(repo, "Zinc picolinate", date(2026, 10, 19))
    assert not capture.renew("notes", repo, s2, 0, _asking([], calls))["called"] and calls == []
    s3 = _session(tmp_path, "s3", [("user", "hi"), ("assistant", "Are you still taking the zinc picolinate?"), ("user", "yes")])
    assert capture.renew("notes", repo, s3, 0, _asking([], calls))["called"]  # another session's word still counts


def test_a_question_not_in_claudes_message_before_his_is_left_out(quiet, tmp_path):
    repo = quiet["repo"]
    s2 = _session(tmp_path, "s2", [("user", "hi"), ("assistant", "Are you still taking the zinc picolinate?"), ("user", "yes")])
    made_up = {"thing": "med/zinc-picolinate", "line": 3, "quote": "yes", "answering": "Do you still take zinc picolinate daily?"}
    assert capture.renew("notes", repo, s2, 0, _asking([made_up], []))["renewed"] == 1
    renewal = next(e for e in Store(repo).events(kind=now.RENEWAL))
    assert "answering" not in renewal.body and "Do you still take" not in renewal.body and "“yes”" in renewal.body
