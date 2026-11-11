"""Change 12 of the inner-work spec: a trail of the beliefs the owner states about himself (tests 93-104). A stated
belief is an entry of the kind `[beliefs] kind` names, linked "showed up" (family `moment`) to each belief it expresses;
`timeline.trail(domain, item, limit=None)` gives (header, rows), one row per statement, oldest first."""
import json

import pytest

from engram import capture, hourly, ingest, store, theory, timeline
from inner_work import D, Model, add, chat_id, inner, line_of, stated, stated_all, zone  # noqa: F401  (fixtures)
from test_capture import LATER as MED_LATER, fake, world  # noqa: F401  (world is a fixture)

BURDEN = "I'm a burden"
AROUND = "everyone would be better off without me around"
ASKED = "What goes through your mind when she offers to help?"


def trail(item: str, **kw):
    ingest.record(D)
    return timeline.trail(D, item, **kw)


def belief_links(w, frm: str) -> list[str]:
    return sorted(e.fm["to"] for e in w.events(kind="link") if e.fm.get("family") == "moment" and e.fm.get("from") == frm)


@pytest.mark.xfail(strict=True, reason="change 12: an entry keeps no context but the question the model says it answered")
def test_93_i_am_a_burden_is_a_stated_belief_with_his_words_its_date_the_guides_question_its_session_and_theme(inner):
    w = inner()
    w.chat(5)
    w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                            "kind": "stated-belief", "about": ["theme/going-quiet"], "beliefs": [{"id": "belief/burden"}]}]}))
    [e] = w.mine("stated-belief")
    assert f"“{BURDEN}”" in e.body and str(e.fm["date"]) == "2026-11-07"
    assert e.fm.get("context") == ASKED  # the guide's message just before it, whether or not the model gave it
    assert chat_id(5) in json.dumps(e.fm) and "theme/going-quiet" in e.about


@pytest.mark.xfail(strict=True, reason="change 12: a stated belief links to no belief")
def test_94_a_statement_linked_to_four_beliefs_keeps_all_four(inner):
    w = inner()
    w.chat(5)
    four = ["belief/burden", "belief/not-enough", "belief/on-the-outside", "belief/unlikable"]
    w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                            "kind": "stated-belief", "beliefs": [{"id": b} for b in four]}]}))
    [e] = w.mine("stated-belief")
    assert belief_links(w, e.id) == four


NO_TRAIL = "change 12: there's no trail command (timeline.trail)"


@pytest.mark.xfail(strict=True, reason=NO_TRAIL)
def test_95_a_beliefs_trail_returns_both_statements_oldest_first_with_date_words_and_context(inner):
    w = inner()
    first = stated(w, AROUND, "2026-10-25", ["belief/burden"], context="How was the weekend with them?")
    second = stated(w, BURDEN, "2026-11-07", ["belief/burden"], context=ASKED)
    _, rows = trail("belief/burden")
    assert [r["id"] for r in rows] == [first, second]
    assert [(r["date"], r["said"], r["context"]) for r in rows] == [
        ("2026-10-25", AROUND, "How was the weekend with them?"), ("2026-11-07", BURDEN, ASKED)]


@pytest.mark.xfail(strict=True, reason=NO_TRAIL)
def test_96_a_categorys_trail_holds_every_statement_under_it_and_one_linked_twice_once(inner):
    w = inner()
    both = stated(w, "nobody would miss me", "2026-11-01", ["belief/burden", "belief/unlikable"])
    one = stated(w, BURDEN, "2026-11-02", ["belief/burden"])
    other = stated(w, "nobody likes me, I know it.", "2026-11-03", ["belief/unlikable"])
    _, rows = trail("belief/not-enough")  # the sample's broader belief: both sit under it
    assert [r["id"] for r in rows] == [both, one, other]


@pytest.mark.xfail(strict=True, reason=NO_TRAIL)
def test_97_a_statement_linked_to_two_beliefs_is_in_both_trails(inner):
    w = inner()
    both = stated(w, "nobody would miss me", "2026-11-01", ["belief/burden", "belief/unlikable"])
    for b in ("belief/burden", "belief/unlikable"):
        assert both in [r["id"] for r in trail(b)[1]]


@pytest.mark.xfail(strict=True, reason=NO_TRAIL)
def test_98_a_loose_link_shows_as_loose_in_the_trail(inner):
    w = inner()
    loose = stated(w, "I always end up in the way", "2026-11-01", ["belief/burden"], loose=("belief/burden",))
    firm = stated(w, BURDEN, "2026-11-02", ["belief/burden"])
    rows = {r["id"]: r for r in trail("belief/burden")[1]}
    assert rows[loose].get("loose") is True and not rows[firm].get("loose")


@pytest.mark.xfail(strict=True, reason="change 12: a new belief can't be made from a statement, so none is checked")
def test_99_a_new_belief_named_with_words_he_never_said_is_rejected(inner):
    w = inner()
    w.chat(5)
    out = w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                                  "kind": "stated-belief", "new_belief": {"name": "I don't deserve help"}}]}))
    assert not [t for t in theory.load(w.repo).things.values() if t.short == "I don't deserve help"]
    assert [d for d in out["dropped"] if "I don't deserve help" in d["why"]]


@pytest.mark.xfail(strict=True, reason="change 12: the theory doesn't show a belief, nor who named it")
def test_100_a_broader_category_the_guide_named_is_labelled_as_the_guides_wherever_shown(inner):
    w = inner()
    add(w, {"title": "I'm a burden under being on the outside", "date": "2026-10-27", "kind": "link", "family": "theory",
            "rel": "under", "from": "belief/burden", "to": "belief/on-the-outside", "about": ["belief/on-the-outside"],
            "by": "claude-suggestion"}, "the guide: “a lot of this is about feeling on the outside”")
    lines = [l for l in theory.text(theory.load(w.repo)).splitlines() if "being on the outside" in l]
    assert lines and all("guide's" in l for l in lines)
    header, _ = trail("belief/on-the-outside")
    assert "guide's" in json.dumps(header)


@pytest.mark.xfail(strict=True, reason=NO_TRAIL)
def test_101_a_trail_of_sixty_is_whole_and_a_cut_one_says_how_many_are_left_and_how_to_get_them(inner):
    w = inner()
    ids = stated_all(w, [(f"{BURDEN}, again ({n})", f"2026-10-{1 + n // 3:02d}", ["belief/burden"]) for n in range(60)])
    header, rows = trail("belief/burden")
    assert [r["id"] for r in rows] == ids
    header, rows = trail("belief/burden", limit=10)
    assert len(rows) == 10 and header["left"] == 50 and "engram" in header["more"]


@pytest.mark.xfail(strict=True, reason="change 12: a stated belief from a yeah is saved in his voice")
def test_102_yeah_to_you_feel_like_a_burden_is_no_stated_belief_but_the_question_and_his_yeah(inner):
    w = inner()
    w.chat(5)
    question = "It sounds like you feel like a burden."
    w.run(Model({"facts": [{"line": line_of(5, question) + 1, "quote": "yeah", "answering": question, "date": "not-sure",
                            "text": "Sam feels like a burden.", "kind": "stated-belief", "beliefs": [{"id": "belief/burden"}]}]}))
    assert not w.mine("stated-belief")
    [e] = [e for e in w.mine() if "“yeah”" in e.body]
    assert question in e.fm["title"] and "yeah" in e.fm["title"]


@pytest.mark.xfail(strict=True, reason="change 12: there's no regroup (capture.regroup)")
def test_103_a_regroup_keeps_every_earlier_link_and_labels_all_it_adds_as_a_suggestion(inner):
    w = inner()
    a = stated(w, BURDEN, "2026-11-01", ["belief/burden"])
    b = stated(w, AROUND, "2026-11-02", ["belief/burden"])
    links = lambda: {(e.fm["from"], e.fm["to"], e.fm["rel"]): e for e in w.events(kind="link")}  # noqa: E731
    before = links()
    proposal = {"beliefs": [{"id": "belief/in-the-way", "name": AROUND, "from": b}],
                "links": [{"from": b, "to": "belief/in-the-way"}], "under": [{"from": "belief/in-the-way", "to": "belief/not-enough"}],
                "remove": [{"from": a, "to": "belief/burden"}]}
    capture.regroup(D, w.repo, ask=lambda prompt: (json.dumps(proposal), 0.0))
    after = links()
    assert set(before) <= set(after)
    added = [e for k, e in after.items() if k not in before]
    assert added and all(e.fm.get("by") == "claude-suggestion" for e in added)
    assert theory.load(w.repo).things["belief/in-the-way"].by == "claude-suggestion"


def test_104_a_repo_that_names_no_stated_belief_kind_saves_such_a_fact_as_it_always_did(world):
    """True today: the made-up medical record has no such kind, so the fact is an observation like any other."""
    facts = [{"line": 7, "text": "Sam's ache is better.", "quote": "the ache is better", "date": "not-sure", "kind": "stated-belief",
              "beliefs": [{"id": "belief/x"}]}]
    hourly.run(ask=fake(facts, []), summaries=False, now=MED_LATER)
    [e] = [e for e in store.Store(world["repo"]).events() if e.fm.get("author") == "engram-capture"]
    assert e.kind == "observation" and "context" not in e.fm and "beliefs" not in e.fm
    assert e.body == "- Ache is better.\n- Sam: “the ache is better”\n"
