"""Change 10 of the inner-work spec: what the owner types into his own app is saved as his words (tests 83-89). The
sample pack's `gym` reader passes his own rows as records of class `said` with his id as author, the row's practice in
`stories`; the app's coach's rows as plain rows; and a practice's rows with no text as a count."""
import json

import pytest

from engram import pack, relink
from inner_work import D, LATER, Model, inner, zone  # noqa: F401  (fixtures)

NOT_YET = "change 10: engram reads an app's rows but never saves from them"
SPOKE = "spoke first in the meeting, hands shaking"


def from_app(w) -> list:
    return [e for e in w.events() if "gym" in str(e.fm.get("source", ""))]


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_83_his_row_on_a_practice_is_saved_once_as_his_dated_in_his_zone_on_that_practice(inner):
    w = inner()
    w.run(Model())
    saved = from_app(w)
    assert [e.body.count(SPOKE) for e in saved] == [1]
    e = saved[0]
    assert e.fm["by"] == "sam" and str(e.fm["date"]) == "2026-11-02"  # 03:10 UTC on the 3rd is the evening of the 2nd
    assert "practice/speak-first-in-meetings" in e.about


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_84_the_same_row_passed_again_is_not_saved_twice(inner):
    w = inner()
    w.run(Model())
    w.run(Model(), now=LATER.replace(hour=13))
    assert len([e for e in from_app(w) if SPOKE in e.body]) == 1


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_85_a_row_the_apps_own_assistant_wrote_is_never_saved(inner):
    w = inner()
    w.run(Model())
    assert [e for e in from_app(w) if SPOKE in e.body]
    assert not [e for e in w.events() if "That took courage" in e.body]


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_86_a_row_with_no_text_is_never_saved_and_the_reader_still_counts_them(inner):
    w = inner()
    w.run(Model())
    assert [e.body.count(SPOKE) for e in from_app(w)] == [1]  # his one row with words, and nothing for the two without
    counts = [d.body for d in pack.load(D).read["gym"](w.repo) if d.kind == "app-count"]
    assert counts == ["2 check-ins with no words"]


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_87_a_row_changed_later_keeps_the_first_entry_and_saves_the_change_as_its_revision(inner):
    w = inner()
    w.run(Model())
    saved = from_app(w)
    assert len(saved) == 1
    first, was = saved[0], saved[0].path
    rows = w.repo / "gym/rows.jsonl"
    rows.write_text(rows.read_text().replace(SPOKE, SPOKE + ", then steadier"))
    w.run(Model(), now=LATER.replace(hour=13))
    saved = from_app(w)
    assert len(saved) == 2 and (w.repo / was).read_text().count("then steadier") == 0
    [later] = [e for e in saved if e.id != first.id]
    revises = [e for e in w.events(kind="link") if e.fm.get("from") == later.id and e.fm.get("to") == first.id]
    assert later.fm.get("supersedes") == first.id or revises


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_88_the_linking_job_reads_an_entry_saved_from_the_app_like_any_of_his(inner):
    w = inner()
    w.run(Model())
    saved = from_app(w)
    assert len(saved) == 1
    e, m = saved[0], Model()
    relink.sweep(w.repo, ask=m, confirm=m, dry_run=True)
    assert f"[{e.id}] date 2026-11-02" in "\n".join(m.of("sweep"))


def test_89_a_reader_that_passes_none_of_his_words_saves_nothing(inner):
    """True today: nothing is ever saved from a reader."""
    w = inner()
    rows = w.repo / "gym/rows.jsonl"
    rows.write_text("".join(json.dumps({**json.loads(l), "by": "coach"}) + "\n" for l in rows.read_text().splitlines()))
    w.run(Model())
    assert not from_app(w) and not [e for e in w.events() if SPOKE in e.body]
