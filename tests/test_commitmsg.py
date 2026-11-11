"""The commit check on synthetic fixtures: the number matcher's money forms, every commit template,
strip on the hourly path and refuse elsewhere, medical's messages unchanged."""
from decimal import Decimal

import pytest

from conftest import git, make_repo
from engram import commitmsg, figures, fix
from engram.store import Store

MONEY = [  # each form, and the value it reads as
    ("$1.5k", "1500", "money"), ("1,500", "1500", "number"), ("1.5k USD", "1500", "money"), ("$1,500", "1500", "money"),
    ("1.5 thousand dollars", "1500", "money"), ("$1.5M", "1500000", "money"), ("1.5 million", "1500000", "scaled"),
    ("$1,500,000", "1500000", "money"), ("€20", "20", "money"), ("US$ 3bn", "3000000000", "money"),
    ("2.5MM", "2500000", "scaled"), ("135B", "135000000000", "scaled"), ("$5m", "5000000", "money"),
    ("5m", "5", "number"), ("35%", "35", "percent"), ("35 percent", "35", "percent"), ("60bp", "60", "percent"),
    ("1,200 shares", "1200", "shares"), ("10 sh", "10", "shares"),
]


@pytest.mark.parametrize("text,value,kind", MONEY)
def test_a_money_form_reads_as_its_value(text, value, kind):
    (f,) = figures.figures(text)
    assert f.value == Decimal(value) and f.kind == kind


def test_a_range_counts_by_its_parts_and_ids_are_not_figures():
    assert [(f.part, f.value) for f in figures.figures("$1-2M")] == [("1", Decimal("1E+6")), ("2", Decimal("2E+6"))]
    assert figures.figures("Q3 and FY26") == []  # a label, not a figure
    assert figures.figures("2026-10-27T09:00:00-07:00 [P012] pTH03 R4 _harness/runs/2026-09-26/scout-week-1c21ea "
                           "ideas.jsonl:12 https://x.example/a/123 commit 9b1975c0") == []


def test_amounts_are_money_and_share_counts_only():
    assert [f.kind for f in figures.amounts("sold 40 shares for $1,200 at 3% of a 6M plan, 3 facts")] == ["shares", "money"]
    assert figures.strip("engram: 3 facts about $1,200 and 40 shares") == "engram: 3 facts about [amount] and [amount]"


# --- commit messages

TODAY = [  # medical's messages as engram wrote them before the templates, byte for byte
    ("write", dict(kind="symptom", date="2026-10-01"), "engram: symptom 2026-10-01"),
    ("facts", dict(n=3, session="ab12cd34"), "engram: 3 facts Sam said in session ab12cd34"),
    ("theory", dict(day="2026-10-02"), "engram: theory revision 2026-10-02"),
    ("relink", dict(change="tc-20261002-ab12"), "engram: evidence re-checked after theory change tc-20261002-ab12"),
    ("exclude", dict(path="reference/x.csv"), "engram: reference/x.csv stays out of the index"),
    ("nodes", dict(n=4), "engram: the node list drops 4 rows for files that are gone"),
    ("ids", dict(docs=2, headings=5), "engram: stable ids for 2 documents and 5 linked headings"),
    ("moved", dict(old="a.md", new="b.md"), "engram: a.md moved to b.md"),
    ("fix", dict(why="a date never said"), "engram fix: a date never said\n\nEngram-Fix: a date never said"),
]


SWEEP = [("sweep", dict(n=4, records="records"), "engram: evidence swept, 4 records linked to the theory\n\n"
                               "Refinement: the theory's loops and Discoveries gained evidence from 4 more records"),
          ("sweep", dict(n=1, records="record"), "engram: evidence swept, 1 record linked to the theory\n\n"
                               "Refinement: the theory's loops and Discoveries gained evidence from 1 more record")]
WIKI = [("wiki", dict(item="doc-k7f2qa", n=3), "engram: the wiki from doc-k7f2qa, 3 pages"),
        ("wiki_index", {}, "engram: the wiki's index and open list"),
        ("wiki_merge", dict(n=1), "engram: the wiki's health check merged concepts (1), their links repointed"),
        ("wiki_moved", dict(n=1), "engram: links repointed to moved posts (1)")]
RENEWALS = [("renewals", dict(n=2, session="ab12cd34"), "engram: Sam still on 2 things, said in session ab12cd34"),
            ("narrow", dict(n=2), "engram: 2 dates narrowed by dated documents"),
            ("note", dict(n=1, session="ab12cd34"), "engram: the note of Sam's session ab12cd34, and 1 facts"),
            ("moments", dict(n=2, records="records"), "engram: 2 records linked to the theory by what happened"),
            ("regroup", dict(n=3), "engram: Sam's stated beliefs regrouped, 3 suggestions"),
            ("rows", dict(n=2), "engram: 2 rows Sam typed in an app")]


def test_each_template_writes_medicals_message_byte_for_byte():
    assert {name for name, *_ in TODAY + SWEEP + WIKI + RENEWALS} == set(commitmsg.TEMPLATES)
    for name, fields, want in TODAY + SWEEP + WIKI + RENEWALS:
        assert commitmsg.message(name, **fields) == want
    assert commitmsg.message("write", "rec: {kind} on {date}", kind="lab", date="2026-10-03") == "rec: lab on 2026-10-03"


def test_an_amount_is_stripped_on_the_hourly_path_and_refused_elsewhere():
    assert commitmsg.message("facts", n="$1,200", session="ab12cd34") == "engram: [amount] facts Sam said in session ab12cd34"
    with pytest.raises(commitmsg.AmountInMessage):
        commitmsg.message("fix", why="sold 40 shares")
    with pytest.raises(commitmsg.AmountInMessage):
        commitmsg.message("moved", old="the $5k plan", new="b")


@pytest.fixture
def rec(tmp_path, env):
    return make_repo(tmp_path / "rec", {".engram/engram.toml": '[domain]\nname = "medical"\ncommit_message = "engram: {kind} {date} for $1,200"\n'})


FM = {"kind": "symptom", "date": "2026-10-01", "recorded": "2026-10-01T10:00:00-07:00"}


def test_the_store_strips_its_own_message_and_refuses_a_given_one_before_writing(rec):
    st = Store(rec)
    with st.transaction() as tx:
        tx.add(FM, "- a cramp")
    assert git(rec, "log", "-1", "--format=%s").strip() == "engram: symptom 2026-10-01 for [amount]"
    with pytest.raises(commitmsg.AmountInMessage):
        with st.transaction(message="engram: paid $40") as tx:
            tx.add({**FM, "recorded": "2026-10-01T11:00:00-07:00"}, "- another")
    assert len(Store(rec).events()) == 1 and not git(rec, "status", "--porcelain")


def test_a_fix_with_an_amount_in_its_why_is_refused_and_changes_nothing(rec):
    st = Store(rec)
    with st.transaction() as tx:
        e = tx.add(FM, "- a cramp")
    (rec / e.path).write_text((rec / e.path).read_text().replace("2026-10-01\n", "not-sure\n", 1))
    with pytest.raises(fix.Refused, match="amount"):
        fix.apply(Store(rec), [e.path], "the $40 was never said")
    assert git(rec, "log", "--format=%s").count("\n") == 2  # init and the entry; the edit is still only in the tree
