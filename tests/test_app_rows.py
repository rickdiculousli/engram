"""Change 10 of the inner-work spec: what the owner types into his own app is saved as his words (tests 83-89). The
sample pack's `gym` reader passes his own rows as records of class `said` with his id as author, the row's practice in
`stories`; the app's coach's rows as plain rows; and a practice's rows with no text as a count."""
import json

import pytest

from engram import pack, relink
from inner_work import D, LATER, SAMPLE, Model, add, inner, zone  # noqa: F401  (fixtures)

SPOKE = "spoke first in the meeting, hands shaking"


def from_app(w) -> list:
    return [e for e in w.events() if "gym" in str(e.fm.get("source", ""))]


def test_83_his_row_on_a_practice_is_saved_once_as_his_dated_in_his_zone_on_that_practice(inner):
    w = inner()
    w.run(Model())
    saved = from_app(w)
    assert [e.body.count(SPOKE) for e in saved] == [1]
    e = saved[0]
    assert e.fm["by"] == "sam" and str(e.fm["date"]) == "2026-11-02"  # 03:10 UTC on the 3rd is the evening of the 2nd
    assert "practice/speak-first-in-meetings" in e.about


def test_84_the_same_row_passed_again_is_not_saved_twice(inner):
    w = inner()
    w.run(Model())
    w.run(Model(), now=LATER.replace(hour=13))
    assert len([e for e in from_app(w) if SPOKE in e.body]) == 1


def test_85_a_row_the_apps_own_assistant_wrote_is_never_saved(inner):
    w = inner()
    w.run(Model())
    assert [e for e in from_app(w) if SPOKE in e.body]
    assert not [e for e in w.events() if "That took courage" in e.body]


def test_86_a_row_with_no_text_is_never_saved_and_the_reader_still_counts_them(inner):
    w = inner()
    w.run(Model())
    assert [e.body.count(SPOKE) for e in from_app(w)] == [1]  # his one row with words, and nothing for the two without
    counts = [d.body for d in pack.load(D).read["gym"](w.repo).docs if d.kind == "app-count"]
    assert counts == ["2 check-ins with no words"]


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


def reader(**doc) -> str:
    """Pack code adding a reader `notes` that passes one record, the given fields over one of the owner's own rows."""
    row = {"ref": "notes#n1", "source": "notes", "cls": "said", "kind": "app-row", "title": "a note", "body": "walked home slowly",
           "pointer": "notes", "author": "{owner_id}", "date": "2026-11-02", "stories": "practice/speak-first-in-meetings", **doc}
    return f"pack.read['notes'] = lambda repo: Source([Doc(**{row!r})])"


def test_a_row_of_his_from_any_reader_is_saved(inner):
    w = inner(pack_tail=reader())
    w.run(Model())
    assert [e.body.count("walked home slowly") for e in w.events() if "notes" in str(e.fm.get("source", ""))] == [1]


@pytest.mark.parametrize("doc", [{"author": "coach"}, {"cls": "row"}, {"body": "  \n"}, {"date": None}],
                         ids=["by-anyone-else", "not-said", "no-words", "undated"])
def test_a_row_that_isnt_his_own_dated_words_is_never_saved(inner, doc):
    """Only a record of class `said`, by him, with words and a date, is his to keep."""
    w = inner(pack_tail=reader(**doc))
    w.run(Model())
    assert not [e for e in w.events() if "notes" in str(e.fm.get("source", ""))]


def test_a_repo_that_names_no_app_kind_saves_nothing_from_its_readers(inner):
    toml = (SAMPLE / ".engram/engram.toml").read_text()
    w = inner(toml=toml[:toml.index("[app]")])
    w.run(Model())
    assert not from_app(w) and not [e for e in w.events() if SPOKE in e.body]


def test_a_row_changed_twice_revises_the_latest_entry(inner):
    w = inner()
    w.run(Model())
    rows = w.repo / "gym/rows.jsonl"
    rows.write_text(rows.read_text().replace(SPOKE, SPOKE + ", then steadier"))
    w.run(Model(), now=LATER.replace(hour=13))
    rows.write_text(rows.read_text().replace(", then steadier", ", then calm"))
    w.run(Model(), now=LATER.replace(hour=14))
    saved = from_app(w)
    by = {e.fm.get("supersedes"): e for e in saved}
    [first] = [e for e in saved if not e.fm.get("supersedes")]
    assert len(saved) == 3 and "then calm" in by[by[first.id].id].body
    w.run(Model(), now=LATER.replace(hour=15))
    assert len(from_app(w)) == 3


def test_a_row_entry_he_corrected_in_a_chat_is_not_saved_again(inner):
    """Only the row's own entries say which words it was last saved with: a correction filed from a chat leaves it saved."""
    w = inner()
    w.run(Model())
    [first] = from_app(w)
    add(w, {"title": "spoke second, not first", "date": "2026-11-02", "kind": "observation", "about": [], "by": "sam",
            "supersedes": first.id, "source": "said in session 5e110000 on 2026-11-04"}, "- Sam: “I spoke second”\n")
    w.run(Model(), now=LATER.replace(hour=13))
    assert from_app(w) == [first]


def test_a_reader_that_fails_is_the_runs_error(inner):
    """Its record of the run says so; nothing is saved from any reader that run, and the run goes on to its other steps."""
    w = inner(pack_tail="def _broken(repo):\n    raise OSError('the app is away')\npack.read['notes'] = _broken")
    out = w.run(Model())
    assert "app rows inner-work: OSError: the app is away" in out["error"] and not from_app(w)
