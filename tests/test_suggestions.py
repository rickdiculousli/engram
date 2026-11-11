"""Change 6 of the inner-work spec: the theory holds the guide's suggestions, labelled as the guide's, and the repo's own
kinds (tests 43-58). A suggestion's `by` is `claude-suggestion`, as an entry's is."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_repo
from engram import hourly, relink, search, store, theory, theorychange, timeline
from inner_work import D, LATER, Model, add, answering, inner, line_of, made, on_day, zone  # noqa: F401
from test_capture import LATER as MED_LATER, graph  # noqa: F401  (graph is a fixture)

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


def test_43_a_hunch_he_answered_past_is_a_proposed_part_labelled_as_the_guides_and_nowhere_his(inner):
    w = inner()
    suggested(w)
    g = theory.load(w.repo)
    assert "part/keeps-score" in g.things
    assert g.things["part/keeps-score"].by == "claude-suggestion" and g.status["part/keeps-score"][0] == "proposed"
    assert not [e for e in w.events() if e.fm.get("by") == "sam" and "keeps score" in e.body + str(e.fm.get("title"))]
    assert not [t for t in g.things.values() if t.by == "sam" and "keeps score" in t.title]


def test_44_of_two_suggestions_a_word_apart_only_the_guides_exact_words_are_kept(inner):
    w = inner()
    off = {**KEEPS, "id": "part/keeps-scores", "quote": "there's a part of you that keeps scores"}
    out = suggested(w, off)
    g = theory.load(w.repo)
    assert "part/keeps-score" in g.things and "part/keeps-scores" not in g.things
    assert [d for d in out["dropped"] if "guide" in d["why"] and d.get("line") == KEEPS["line"]]


def test_45_adding_a_suggestion_starts_no_model_pass_over_the_whole_record(inner):
    w = inner()
    suggested(w)
    assert "part/keeps-score" in theory.load(w.repo).things
    with theorychange.db() as c:
        assert not c.execute("SELECT id FROM change").fetchall()
    assert not relink.pending(older_than_minutes=0)


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
def test_48_49_a_yeah_is_saved_as_the_question_and_his_yeah_never_as_a_statement_in_his_voice(inner, question, rewrite):
    w = inner()
    w.chat(5)
    w.run(Model({"facts": [{**yeah_after(question), "text": rewrite}]}))
    [e] = [e for e in w.mine() if "“yeah”" in e.body]  # still saved
    assert question in e.fm["title"] and "yeah" in e.fm["title"]
    assert question in e.body
    assert rewrite.removeprefix("Sam ").rstrip(".") not in e.fm["title"] + e.body


EARN = "there's a belief that you have to earn your place"


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


def test_51_a_suggestion_that_would_add_a_step_to_his_loop_is_rejected_and_the_loop_stays(inner):
    w = inner()
    path = theory.load(w.repo).path("loop/quiet")
    step = {"line": KEEPS["line"], "quote": HUNCH,
            "link": {"op": "insert-step", "loop": "loop/quiet", "after": "state/quiet", "node": "part/keeps-score"}}
    out = suggested(w, step)
    assert [d for d in out["dropped"] if "loop/quiet" in d["why"]]
    assert theory.load(w.repo).path("loop/quiet") == path


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


def test_53_the_same_suggestion_twice_with_the_same_id_is_one_item(inner):
    w = inner()
    suggested(w, dict(KEEPS))
    g = theory.load(w.repo)
    assert [t for t in g.things if "keeps-score" in t] == ["part/keeps-score"]
    assert len(store.Store(w.repo).events(kind="status", about="part/keeps-score")) == 1


INSIGHT = "insight/quiet-kept-me-safe"


def insight_line(w) -> str:
    return naming(theory.text(theory.load(w.repo)), "going quiet kept me safe")


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


def test_55_a_how_far_along_label_with_none_of_his_words_behind_it_is_rejected(inner):
    w = inner()
    w.chat(1, upto=40)
    guess = "That's a big thing to notice."
    out = w.run(Model({"suggestions": [{"line": line_of(1, guess), "quote": guess, "stage": {"id": INSIGHT, "to": "living it"}}]}))
    assert [d for d in out["dropped"] if "stage" in d["why"]]
    assert "noticed" in insight_line(w)


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


# The rules the code adds besides the spec's tests: each red before it was built.

def test_a_suggested_join_is_the_guides_and_a_suggestion_never_sets_a_status(inner):
    w = inner()
    join = {"line": KEEPS["line"], "quote": HUNCH, "link": {"from": "part/critic", "to": "belief/not-enough", "rel": "under"}}
    status = {"line": KEEPS["line"], "quote": HUNCH, "status": {"id": "part/critic", "to": "ruled out"}}
    out = suggested(w, join, status)
    g = theory.load(w.repo)
    [e] = [e for e in g.edges if e.a == "part/critic" and e.b == "belief/not-enough"]
    assert e.by == "claude-suggestion" and HUNCH in e.note
    assert "the guide's suggestion" in naming(theory.text(g), "the critic → I'm not enough")
    assert [d for d in out["dropped"] if "status" in d["why"]] and g.status.get("part/critic", ("",))[0] == ""


BURDEN = "It sounds like you feel like a burden."


def test_a_yeah_to_a_suggestion_keeps_the_question_and_his_yeah_on_it_and_it_stays_the_guides(inner):
    w = inner()
    w.chat(5)
    yes = {"line": line_of(5, BURDEN) + 1, "quote": "yeah", "status": {"id": "belief/on-the-outside", "to": "provisional"}}
    out = w.run(Model({"theory": [{**yes, "answering": BURDEN}]}))
    g = theory.load(w.repo)
    assert g.status["belief/on-the-outside"][0] == "proposed" and "the guide's suggestion" in theory.who(g, "belief/on-the-outside")
    [e] = w.events(about="belief/on-the-outside")[-1:]
    assert e.kind != "status" and e.fm["answering"] == BURDEN and BURDEN in e.fm["title"] and "“yeah”" in e.fm["title"]
    assert [k for k in out["kept"] if "belief/on-the-outside" in k["why"]]


def test_a_yeah_with_no_question_adopts_nothing_and_is_dropped(inner):
    w = inner()
    w.chat(5)
    out = w.run(Model({"theory": [{"line": line_of(5, BURDEN) + 1, "quote": "yeah",
                                   "status": {"id": "belief/on-the-outside", "to": "provisional"}}]}))
    assert theory.load(w.repo).status["belief/on-the-outside"][0] == "proposed"
    assert [d for d in out["dropped"] if "never makes the guide's suggestion" in d["why"]]


FOUND = "maybe quiet isn't the only way to be safe with him."


def test_a_thing_he_names_is_his_named_with_his_words_and_an_insight_names_its_note(inner):
    from inner_work import chat1_note
    w = inner()
    w.chat(1, upto=40)
    mine = {"line": line_of(1, FOUND), "quote": FOUND,
            "add": {"kind": "insight", "id": "insight/not-the-only-way", "name": "quiet isn't the only way to be safe"}}
    other = {**mine, "add": {"kind": "belief", "id": "belief/safe-is-quiet", "name": "being quiet is safe"}}
    out = w.run(Model({**chat1_note(), "theory": [mine, other]}))
    g = theory.load(w.repo)
    t = g.things["insight/not-the-only-way"]
    assert t.by == "sam" and t.file == "theory/insights/not-the-only-way.md" and t.short == "quiet isn't the only way to be safe"
    [n] = w.notes()
    assert f"note: {n['fm']['id']}" in (w.repo / t.file).read_text()
    assert "belief/safe-is-quiet" not in g.things and [d for d in out["dropped"] if "Sam's words" in d["why"]]


def test_his_word_on_a_suggestion_keeps_it_in_the_start_text_past_the_set_time(inner, monkeypatch):
    w = inner()
    suggested(w)
    add(w, {"title": "the scorekeeper again", "date": "2027-01-10", "kind": "observation", "about": ["part/keeps-score"], "by": "sam"},
        "- Sam: “the scorekeeper again”\n")
    on_day(monkeypatch, datetime(2027, 1, 15, 4, tzinfo=timezone.utc))
    assert labelled(hourly.session_start(payload(w)))


def test_in_one_second_the_guides_suggestion_comes_before_his_word_on_it(inner):
    w = inner()
    at = "2026-11-20T10:00:00-08:00"
    for by, status in (("sam", "ruled out"), ("claude-suggestion", "proposed")):
        add(w, {"title": f"on the outside: {status}", "date": "2026-11-20", "recorded": at, "kind": "status",
                "about": ["belief/on-the-outside"], "status": status, "by": by}, "")
    assert theory.load(w.repo).status["belief/on-the-outside"][0] == "ruled out"


def test_a_change_in_conversation_adds_a_thing_of_the_records_own_kind_in_its_folder(inner):
    w = inner()
    theorychange.apply(w.repo, [{"op": "add-node", "id": "belief/too-much", "kind": "belief", "title": "I'm too much"}], relink=False)
    t = theory.load(w.repo).things["belief/too-much"]
    assert t.kind == "belief" and t.file == "theory/beliefs/too-much.md" and (w.repo / t.file).exists()


def test_a_hedged_yes_when_asked_is_kept_on_the_suggestion_as_the_question_and_his_words(inner):
    w = inner()
    w.chat(5)
    hedged = {"line": line_of(5, BURDEN) + 1, "quote": "yeah", "answering": BURDEN, "agrees": "belief/on-the-outside"}
    mine = {**hedged, "agrees": "belief/burden"}
    out = w.run(Model({"theory": [hedged, mine]}))
    assert theory.load(w.repo).status["belief/on-the-outside"][0] == "proposed"
    [e] = w.events(about="belief/on-the-outside")[-1:]
    assert e.fm["answering"] == BURDEN and "“yeah”" in e.fm["title"]
    assert [d for d in out["dropped"] if "belief/burden isn't one of the guide's suggestions" in d["why"]]


def test_a_suggestion_may_name_the_line_of_the_message_the_guide_answered(inner):
    w = inner()
    suggested(w, {**KEEPS, "id": "part/adds-it-up", "name": "adds it up", "line": KEEPS["line"] - 1,
                  "quote": "adding up every time you didn't speak"})
    assert theory.load(w.repo).things["part/adds-it-up"].by == "claude-suggestion"


def test_what_he_says_of_a_suggestion_decides_and_a_doubt_rules_nothing_out(inner):
    w = inner()
    w.chat(5)
    words = "no, that's not it."
    doubt = {"line": line_of(5, words), "quote": words, "on": "belief/on-the-outside", "says": "doubts",
             "status": {"id": "belief/on-the-outside", "to": "ruled out"}}  # the reply's status doesn't stand against its doubt
    out = w.run(Model({"theory": [doubt]}))
    assert theory.load(w.repo).status["belief/on-the-outside"][0] == "proposed"
    assert [d for d in out["dropped"] if "doubts of belief/on-the-outside" in d["why"]]
    w.chat(7, lines=made(7, "2026-11-14T04:00:00", [("O", "I'm not on the outside, that isn't it."), ("G", "Ok.")]))
    w.run(Model({"theory": [{"line": 1, "quote": "I'm not on the outside, that isn't it.", "on": "belief/on-the-outside",
                             "says": "denies"}]}), now=LATER + timedelta(hours=1))
    g = theory.load(w.repo)
    assert g.status["belief/on-the-outside"][0] == "ruled out" and "ruled out by Sam" in theory.who(g, "belief/on-the-outside")


# The step's review.

def test_a_yeah_with_no_question_is_headlined_as_his_word_alone_never_a_statement_in_his_voice(inner):
    w = inner()
    w.chat(5)
    w.run(Model({"facts": [{**yeah_after("Is that shame?"), "answering": "", "text": "Sam feels shame."}]}))
    [e] = [e for e in w.mine() if "“yeah”" in e.body]
    assert "shame" not in e.fm["title"] + e.body and e.fm["title"] == "“yeah”"


def test_a_suggestion_is_adopted_in_conversation_only_with_his_words_and_shows_them(inner):
    w = inner()
    with pytest.raises(theorychange.ChangeError, match="his words"):
        theorychange.apply(w.repo, [{"op": "status", "id": "belief/on-the-outside", "to": "provisional"}], relink=False)
    theorychange.apply(w.repo, [{"op": "status", "id": "belief/on-the-outside", "to": "provisional"}], relink=False,
                       said="I am on the outside a lot")
    g = theory.load(w.repo)
    assert theory.who(g, "belief/on-the-outside") == "raised by the guide, adopted by Sam: “I am on the outside a lot”"


def test_the_theory_is_read_only_where_its_words_or_kinds_are(env, monkeypatch):
    """A record with no theory words and no kinds of its own files and prints where things stand without reading the
    theory more than `engram now`'s one read of its Discoveries."""
    from test_now import CURRENT, TOML  # noqa: F401
    from conftest import NOTES_PACK
    reads = []
    real = theory.load
    monkeypatch.setattr(theory, "load", lambda *a, **k: reads.append(1) or real(*a, **k))
    (env["tmp"] / "pack").mkdir()
    (env["tmp"] / "pack/__init__.py").write_text((NOTES_PACK / "__init__.py").read_text() + CURRENT)
    repo = make_repo(env["tmp"] / "notes", {".engram/engram.toml": TOML})
    env["set_repo"]("notes", repo, pack=env["tmp"] / "pack")
    from engram import now
    now.text(repo)
    assert len(reads) == 1
