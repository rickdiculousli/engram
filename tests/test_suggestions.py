"""Change 6 of the inner-work spec: the theory holds the guide's suggestions, labelled as the guide's, and the repo's own
kinds (tests 43-58). A suggestion's `by` is `claude-suggestion`, as an entry's is."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_repo
from engram import hourly, relink, search, store, theory, theorychange, timeline
from inner_work import D, LATER, Model, add, answering, inner, line_of, made, on_day, zone  # noqa: F401
from test_capture import LATER as MED_LATER, graph  # noqa: F401  (graph is a fixture)

NOT_YET = "change 6: the filer never adds the guide's suggestion to the theory, and the repo's kinds aren't read"
HUNCH = "there's a part of you that keeps score"
KEEPS = {"id": "part/keeps-score", "kind": "part", "name": "keeps score", "line": line_of(1, HUNCH), "quote": HUNCH}


def suggested(w, *more, now=LATER):
    w.chat(1, upto=40)
    return w.run(Model({"suggestions": [KEEPS, *more]}), now=now)


def payload(w, n=9):
    return {"cwd": str(w.repo), "session_id": f"5e110000-0000-4000-8000-{n:012d}", "source": "startup"}


def naming(text: str, name: str) -> str:
    """The one line of the text that names the item."""
    lines = [l for l in text.splitlines() if name in l]
    assert len(lines) == 1, f"{name!r} is on {len(lines)} lines"
    return lines[0]


def labelled(text: str, name: str = "keeps score") -> bool:
    """Every line naming the item says it's the guide's, and there is one."""
    lines = [l for l in text.splitlines() if name in l]
    return bool(lines) and all("guide's" in l for l in lines)


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_43_a_hunch_he_answered_past_is_a_proposed_part_labelled_as_the_guides_and_nowhere_his(inner):
    w = inner()
    suggested(w)
    g = theory.load(w.repo)
    assert "part/keeps-score" in g.things
    assert g.things["part/keeps-score"].by == "claude-suggestion" and g.status["part/keeps-score"][0] == "proposed"
    assert not [e for e in w.events() if e.fm.get("by") == "sam" and "keeps score" in e.body + str(e.fm.get("title"))]
    assert not [t for t in g.things.values() if t.by == "sam" and "keeps score" in t.title]


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_44_of_two_suggestions_a_word_apart_only_the_guides_exact_words_are_kept(inner):
    w = inner()
    off = {**KEEPS, "id": "part/keeps-scores", "quote": "there's a part of you that keeps scores"}
    out = suggested(w, off)
    g = theory.load(w.repo)
    assert "part/keeps-score" in g.things and "part/keeps-scores" not in g.things
    assert [d for d in out["dropped"] if "guide" in d["why"] and d.get("line") == KEEPS["line"]]


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_45_adding_a_suggestion_starts_no_model_pass_over_the_whole_record(inner):
    w = inner()
    suggested(w)
    assert "part/keeps-score" in theory.load(w.repo).things
    with theorychange.db() as c:
        assert not c.execute("SELECT id FROM change").fetchall()
    assert not relink.pending(older_than_minutes=0)


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_46_a_suggestion_is_labelled_as_the_guides_everywhere_it_appears(inner, monkeypatch):
    w = inner()
    suggested(w)
    assert labelled(theory.text(theory.load(w.repo)))  # the full theory
    on_day(monkeypatch, LATER)
    assert labelled(hourly.session_start(payload(w)))  # the chat start text
    assert labelled(timeline.render(*timeline.chain(D, "part/keeps-score")))  # the theory block of a history
    pages = [r for r in search.search("keeps score", [D]) if r["ref"].startswith("theory/")]
    assert pages and all("guide's" in json.dumps(r) for r in pages)  # a search result for its page
    w.chat(5)
    filer = Model()
    w.run(filer, now=LATER + timedelta(hours=1))
    assert labelled(filer.of("file")[-1].split("<conversation>")[0])  # what the filer is given
    sweep = Model()
    relink.sweep(w.repo, ask=sweep, confirm=sweep, dry_run=True)
    assert labelled(sweep.of("sweep")[0].split("<records>")[0])  # what the linking job is given


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_47_said_later_in_his_own_words_it_is_provisional_raised_by_the_guide_and_adopted_by_him(inner):
    w = inner()
    suggested(w)
    w.chat(5)
    words = "that scorekeeper part was loud today"
    w.run(Model({"theory": [{"line": line_of(5, words), "quote": words, "status": {"id": "part/keeps-score", "to": "provisional"}}]}),
          now=LATER + timedelta(hours=1))
    g = theory.load(w.repo)
    assert g.status.get("part/keeps-score", ("",))[0] == "provisional"
    line = naming(theory.text(g), "keeps score")
    assert "guide" in line and "adopted" in line and words in theory.text(g)


def yeah_after(question: str) -> dict:
    return {"line": line_of(5, question) + 1, "quote": "yeah", "answering": question, "date": "not-sure", "kind": "observation"}


@pytest.mark.parametrize("question, rewrite", [("Is that shame?", "Sam feels shame."),
                                               ("Did you do it this morning?", "Sam did the breathing practice this morning.")])
@pytest.mark.xfail(strict=True, reason="change 6: a short reply is saved under the model's rewrite of it, in his voice")
def test_48_49_a_yeah_is_saved_as_the_question_and_his_yeah_never_as_a_statement_in_his_voice(inner, question, rewrite):
    w = inner()
    w.chat(5)
    w.run(Model({"facts": [{**yeah_after(question), "text": rewrite}]}))
    [e] = [e for e in w.mine() if "“yeah”" in e.body]  # still saved
    assert question in e.fm["title"] and "yeah" in e.fm["title"]
    assert question in e.body
    assert rewrite.removeprefix("Sam ").rstrip(".") not in e.fm["title"] + e.body


EARN = "there's a belief that you have to earn your place"


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_50_no_thats_not_it_rules_it_out_with_his_words_kept_in_the_theory_and_out_of_the_start_text(inner, monkeypatch):
    w = inner()
    w.chat(5)
    asked = answering(5, "no, that's not it.")
    w.run(Model({"suggestions": [{"id": "belief/earn-my-place", "kind": "belief", "name": "earn your place",
                                  "line": line_of(5, EARN), "quote": EARN}],
                 "theory": [{"line": line_of(5, "no, that's not it."), "quote": "no, that's not it.", "answering": asked,
                             "status": {"id": "belief/earn-my-place", "to": "ruled out"}}]}))
    g = theory.load(w.repo)
    assert g.status.get("belief/earn-my-place", ("",))[0] == "ruled out"
    assert "no, that's not it." in store.Store(w.repo).events(about="belief/earn-my-place")[-1].body
    assert "earn your place" in theory.text(g)
    on_day(monkeypatch, LATER)
    assert "earn your place" not in hourly.session_start(payload(w))


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_51_a_suggestion_that_would_add_a_step_to_his_loop_is_rejected_and_the_loop_stays(inner):
    w = inner()
    path = theory.load(w.repo).path("loop/quiet")
    step = {"line": KEEPS["line"], "quote": HUNCH,
            "link": {"op": "insert-step", "loop": "loop/quiet", "after": "state/quiet", "node": "part/keeps-score"}}
    out = suggested(w, step)
    assert [d for d in out["dropped"] if "loop/quiet" in d["why"]]
    assert theory.load(w.repo).path("loop/quiet") == path


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_52_one_he_never_mentions_leaves_the_start_text_after_the_set_time_and_stays_in_the_theory(inner, monkeypatch):
    w = inner()
    suggested(w)
    moment = add(w, {"title": "kept quiet in the meeting", "date": "2026-11-21", "kind": "observation", "about": [], "by": "sam"},
                 "- Sam: “kept quiet again”\n")
    add(w, {"title": "showed up keeps score", "date": "2026-11-21", "kind": "link", "family": "moment", "rel": "showed-up",
            "from": moment, "to": "part/keeps-score", "about": ["part/keeps-score"], "by": "claude"}, "kept quiet again")
    w.chat(7, lines=made(7, "2026-12-01T04:00:00", [("O", "work was fine today."),
                                                    ("G", "Maybe that part of you that keeps score was quieter today.")]))
    w.run(Model({"suggestions": [{**KEEPS, "line": 2, "quote": "that part of you that keeps score"}]}),
          now=datetime(2026, 12, 2, tzinfo=timezone.utc))
    assert "keeps score" in theory.text(theory.load(w.repo))
    on_day(monkeypatch, datetime(2027, 1, 15, 4, tzinfo=timezone.utc))
    assert "keeps score" not in hourly.session_start(payload(w))


@pytest.mark.xfail(strict=True, reason=NOT_YET)
def test_53_the_same_suggestion_twice_with_the_same_id_is_one_item(inner):
    w = inner()
    suggested(w, dict(KEEPS))
    g = theory.load(w.repo)
    assert [t for t in g.things if "keeps-score" in t] == ["part/keeps-score"]
    assert len(store.Store(w.repo).events(kind="status", about="part/keeps-score")) == 1


INSIGHT = "insight/quiet-kept-me-safe"


def insight_line(w) -> str:
    return naming(theory.text(theory.load(w.repo)), "going quiet kept me safe")


@pytest.mark.xfail(strict=True, reason="change 6: an insight has one label, and the repo's kinds aren't read")
def test_54_an_insight_shows_how_sure_and_how_far_along_and_each_changes_alone(inner):
    w = inner()
    w.chat(1, upto=40)
    found = "maybe quiet isn't the only way to be safe with him."
    w.run(Model({"theory": [{"line": line_of(1, found), "quote": found, "status": {"id": INSIGHT, "stage": "trying"}}]}))
    line = insight_line(w)
    assert "provisional" in line and "trying" in line and "noticed" not in line
    w.chat(6, lines=made(6, "2026-11-13T04:00:00", [("O", "I'm sure now the quiet was how I kept safe back then."),
                                                    ("G", "That sounds settled.")]))
    w.run(Model({"theory": [{"line": 1, "quote": "I'm sure now the quiet was how I kept safe back then.",
                             "status": {"id": INSIGHT, "to": "confirmed"}}]}), now=LATER + timedelta(hours=1))
    line = insight_line(w)
    assert "confirmed" in line and "trying" in line


@pytest.mark.xfail(strict=True, reason="change 6: no stage label exists to be checked")
def test_55_a_how_far_along_label_with_none_of_his_words_behind_it_is_rejected(inner):
    w = inner()
    w.chat(1, upto=40)
    guess = "That's a big thing to notice."
    out = w.run(Model({"suggestions": [{"line": line_of(1, guess), "quote": guess, "stage": {"id": INSIGHT, "to": "living it"}}]}))
    assert [d for d in out["dropped"] if "stage" in d["why"]]
    assert "noticed" in insight_line(w)


@pytest.mark.xfail(strict=True, reason="change 6: the theory can't hold an insight, nor require its note")
def test_56_an_insight_that_names_no_note_is_rejected_where_the_repo_requires_one(inner):
    w = inner()
    w.chat(1, upto=40)
    found = "maybe quiet isn't the only way to be safe with him."
    out = w.run(Model({"theory": [{"line": line_of(1, found), "quote": found,
                                   "add": {"kind": "insight", "id": "insight/quiet-isnt-the-only-way",
                                           "name": "quiet isn't the only way to be safe"}}]}))
    assert "insight/quiet-isnt-the-only-way" not in theory.load(w.repo).things
    assert [d for d in out["dropped"] if "note" in d["why"]]


def test_57_linking_a_moment_never_changes_a_status(env):
    """True today: links are placed, statuses are the owner's."""
    repo = make_repo(env["tmp"] / "repos/med", {
        ".engram/engram.toml": '[domain]\nname = "medical"\nevents_dir = "events"\ncommit = "none"\n',
        "evidence/D01-cold.md": "---\nid: D01\ntitle: Cold mornings stiffen the knee\n---\n# D01\n\nCold stiffens it.\n"})
    env["set_repo"]("medical", repo)
    st = store.Store(repo)
    st.add({"id": "e1", "title": "stiff on a cold morning", "date": "2026-03-01", "kind": "observation", "about": []},
           "- stiff on a cold morning\n")
    st.add({"title": "D01: provisional", "date": "2026-02-01", "kind": "status", "about": ["discovery/D01"],
            "status": "provisional"}, "")
    links = [{"record": "e1", "to": "discovery/D01", "rel": "strengthens", "passage": "stiff on a cold morning"}]
    out = relink.sweep(repo, ask=lambda p: (json.dumps({"links": links}), 0.0), confirm=lambda p: ("yes", 0.0))
    assert len(out["confirmed"]) == 1
    assert theory.load(repo).status["discovery/D01"][0] == "provisional"


def test_58_the_medical_test_record_takes_no_suggestion_and_prints_the_same_theory(graph):
    """True today: the made-up medical record has no suggestion words and no kinds of its own."""
    before = theory.text(theory.load(graph["repo"]))
    things = set(theory.load(graph["repo"]).things)
    guess = {"id": "node/C", "kind": "node", "name": "cold", "line": 4, "quote": "I think the knee tension amplifies the stiffness."}

    def ask(prompt):
        return json.dumps({"facts": [], "theory": [], "suggestions": [guess]}), 0.0
    hourly.run(ask=ask, summaries=False, now=MED_LATER)
    assert set(theory.load(graph["repo"]).things) == things
    assert theory.text(theory.load(graph["repo"])) == before
