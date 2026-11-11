"""Change 5 of the inner-work spec: themes, people and past events made from the owner's words (tests 32-42). A thread is
asked for by any of its names or its id (`timeline.chain`); a new one's id is its kind and its name, slugged."""
import json
from datetime import timedelta

import pytest

from engram import now as now_mod
from engram import ingest, search, timeline
from inner_work import D, LATER, Model, add, fact, inner, made, zone  # noqa: F401  (fixtures)

def history(name: str) -> str:
    """Everything one request for a thread returns, as text, after the refresh `engram timeline` makes first."""
    ingest.refresh_if_stale([D])
    return json.dumps(timeline.chain(D, name)[1])


def remark(w, words: str):
    [e] = [e for e in w.mine() if words in e.body]
    return e


@pytest.mark.parametrize("name, ok", [("goes quiet around my dad", False), ("quiet around my dad", True)])
def test_32_a_theme_is_named_only_with_his_words(inner, name, ok):
    w = inner(record=False)
    w.chat(4, upto=2)
    said = "I go quiet around my dad again."
    out = w.run(Model({"facts": [fact(4, said, "Sam goes quiet around his dad again.", create=[{"kind": "theme", "name": name}])]}))
    e = remark(w, said)  # the remark is saved either way
    if ok:
        assert e.id in history("quiet around my dad") and "theme/quiet-around-my-dad" in e.about
    else:
        assert not [x for x in e.about if x.startswith("theme/")]
        assert [d for d in out["dropped"] if "goes" in d["why"]]


def test_33_a_kind_the_repo_doesnt_list_is_not_created_and_the_remark_is_saved(inner):
    w = inner(record=False)
    w.chat(4, upto=8)
    said = "Sam asked me to lead the friday meeting"
    out = w.run(Model({"facts": [fact(4, said, "Sam was asked to lead the friday meeting.",
                                      create=[{"kind": "goal", "name": "lead the friday meeting"}])]}))
    e = remark(w, said)
    assert not [x for x in e.about if x.startswith("goal/")] and e.id not in history("lead the friday meeting")
    assert [d for d in out["dropped"] if "goal" in d["why"]]


def test_34_one_request_for_a_person_returns_what_three_chats_said_in_order_and_now_shows_the_latest(inner):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model({"facts": [fact(1, "that dad would turn on me", "Sam feared his dad would turn on him.",
                                create=[{"kind": "person", "name": "dad"}])]}))
    w.chat(4, upto=2)
    w.run(Model({"facts": [fact(4, "I go quiet around my dad again.", "Sam goes quiet around his dad.", about=["person/dad"])]}),
          now=LATER + timedelta(hours=1))
    w.chat(6, lines=made(6, "2026-11-13T04:00:00", [("O", "my dad called and was kind for once, he asked about my week."),
                                                    ("G", "That sounds different.")]))
    w.run(Model({"facts": [{"line": 1, "quote": "my dad called and was kind for once", "text": "Sam's dad called and was kind.",
                            "date": "not-sure", "kind": "observation", "about": ["person/dad"]}]}), now=LATER + timedelta(hours=2))
    got = history("dad")
    order = [got.find(remark(w, words).id) for words in ("turn on me", "around my dad again", "kind for once")]
    assert -1 not in order and order == sorted(order)
    assert "kind for once" in now_mod.text(w.repo)


def test_35_a_second_name_for_a_person_finds_the_same_person_and_keeps_his_wording(inner):
    w = inner(record=False)
    w.chat(4, upto=2)
    w.run(Model({"facts": [fact(4, "I go quiet around my dad again.", "Sam goes quiet around his dad.",
                                create=[{"kind": "person", "name": "my dad"}])]}))
    w.chat(4, upto=8)
    w.run(Model({"facts": [fact(4, "on the phone with my father yesterday", "Sam's father asked him about money.",
                                about=["person/my-dad"], names={"person/my-dad": "my father"})]}), now=LATER + timedelta(hours=1))
    first, second = remark(w, "around my dad again"), remark(w, "with my father yesterday")
    for name in ("my dad", "my father"):
        got = history(name)
        assert first.id in got and second.id in got
    assert not [e for e in w.events() if any(a.startswith("person/") and a != "person/my-dad" for a in e.about)]


def test_36_a_remark_on_the_wrong_sam_moves_when_he_says_different_sam_and_nothing_is_lost(inner):
    w = inner(record=False)
    w.chat(4, upto=8)
    w.run(Model({"facts": [
        fact(4, "I called my brother Sam after", "Sam called his brother Sam.", create=[{"kind": "person", "name": "my brother Sam"}]),
        fact(4, "Sam asked me to lead the friday meeting", "Sam was asked to lead the friday meeting.",
             about=["person/my-brother-sam"])]}))
    brother, meeting = remark(w, "called my brother Sam"), remark(w, "lead the friday meeting")
    w.chat(4)
    w.run(Model({"facts": [fact(4, "no, different Sam.", "The meeting was Sam from work's idea, not his brother's.",
                                moves=[{"entry": meeting.id, "from": "person/my-brother-sam",
                                        "to": {"kind": "person", "name": "Sam from work"}, "said": "no, different Sam"}])]}),
          now=LATER + timedelta(hours=1))
    assert brother.id in history("my brother Sam") and meeting.id not in history("my brother Sam")
    assert meeting.id in history("Sam from work") and brother.id not in history("Sam from work")
    assert {brother.id, meeting.id} <= {e.id for e in w.events()}


def test_37_a_remark_attached_to_nothing_is_saved_and_searchable(inner):
    """True today."""
    w = inner(record=False)
    w.chat(4, upto=8)
    w.run(Model({"facts": [fact(4, "he asked about money and I just said fine", "Sam's father asked about money.")]}))
    e = remark(w, "about money")
    assert any(r["ref"] == e.id for r in search.search("asked about money", [D]))


def test_38_a_remark_attaches_to_the_least_used_of_more_than_eighty_themes(inner):
    w = inner()
    entries = [({"title": f"remark {n}{x}", "date": "2026-10-01", "kind": "observation", "about": [f"theme/t-{n}"], "by": "sam"},
                f"- remark {n}\n") for n in range(1, 85) for x in "ab"]
    entries.append(({"title": "joined the climbing group", "date": "2026-10-02", "kind": "observation",
                     "about": ["theme/the-climbing-group"], "by": "sam"}, "- joined the climbing group\n"))
    from engram import store
    st = store.Store(w.repo)
    with st.transaction() as tx:
        for k, (fm, body) in enumerate(entries):  # a second apart: in one second, two ids' 4-hex hashes can meet
            tx.add({"domain": D, "recorded": f"2026-10-01T09:{k // 60:02d}:{k % 60:02d}-07:00", **fm}, body)
    w.chat(5)
    said = "they asked me to come again next week, the climbing group."
    w.run(Model({"facts": [fact(5, said, "The climbing group asked Sam to come again.", about=["theme/the-climbing-group"])]}))
    assert "theme/the-climbing-group" in remark(w, said).about


def test_39_a_join_returns_both_histories_and_a_split_keeps_what_came_before(inner):
    w = inner()
    at_work = [add(w, {"title": f"quiet in standup {d}", "date": f"2026-10-0{d}", "kind": "observation",
                       "about": ["theme/quiet-at-work"], "by": "sam"}, "- quiet in standup\n") for d in (1, 5)]
    [old] = [e.id for e in w.events(kind="observation") if "theme/going-quiet" in e.about]
    add(w, {"title": "quiet at work joined into going quiet", "date": "2026-11-01", "kind": "link", "family": "timeline",
            "rel": "joined-into", "from": "theme/quiet-at-work", "to": "theme/going-quiet", "about": ["theme/going-quiet"],
            "by": "sam"}, "Sam: “it's the same thing, the quiet”")
    for theme in ("theme/quiet-at-work", "theme/going-quiet"):
        got = history(theme)
        assert old in got and all(e in got for e in at_work)
    add(w, {"title": "going quiet split", "date": "2026-11-05", "kind": "link", "family": "timeline", "rel": "split-into",
            "from": "theme/going-quiet", "to": "theme/quiet-with-dad", "about": ["theme/going-quiet"], "by": "sam"},
        "Sam: “with dad it's its own thing”")
    later = add(w, {"title": "quiet at the dinner table", "date": "2026-11-06", "kind": "observation",
                    "about": ["theme/quiet-with-dad"], "by": "sam"}, "- quiet at dinner\n")
    got = history("theme/quiet-with-dad")
    assert later in got and old in got


def test_40_the_filer_on_its_own_never_joins_splits_or_ends_a_thread(inner):
    w = inner()
    w.chat(4, upto=8)
    ops = [{"op": "join", "from": "theme/going-quiet", "into": "theme/quiet-with-dad"},
           {"op": "split", "from": "theme/going-quiet", "into": ["theme/a", "theme/b"]},
           {"op": "end", "id": "theme/going-quiet"}]
    out = w.run(Model({"facts": [fact(4, "I go quiet around my dad again.", "Sam goes quiet around his dad.",
                                      about=["theme/going-quiet"])], "thread_ops": ops}))
    assert not [e for e in w.events(kind="link") if e.fm.get("rel") in ("joined-into", "split-into", "ended")]
    assert sorted(next(op for op in ("join", "split", "end") if op in d["why"]) for d in out["dropped"]
                  if any(op in d["why"] for op in ("join", "split", "end"))) == ["end", "join", "split"]


ABOUT_TEN = {"line": 3, "quote": "like when I was about ten and he shouted about the bills",
             "text": "When Sam was about ten his father shouted about the bills.", "date": "not-sure",
             "as_said": "when I was about ten", "kind": "observation",
             "create": [{"kind": "event", "name": "he shouted about the bills"}]}


def test_41_about_ten_keeps_his_wording_and_runs_from_his_ninth_birthday_to_the_day_before_his_twelfth(inner):
    w = inner()
    add(w, {"title": "Sam was born", "date": "1990-05-14", "kind": "observation", "landmark": "birth", "about": [], "by": "sam"},
        "- born\n")
    w.chat(4, upto=8)
    w.run(Model({"facts": [ABOUT_TEN]}))
    e = remark(w, "when I was about ten")
    assert (e.fm.get("as_said"), e.fm.get("range_from"), e.fm.get("range_to")) == \
        ("when I was about ten", "1999-05-14", "2002-05-13")


def test_41_with_no_birth_year_about_ten_keeps_his_wording_and_no_date(inner):
    """True today: with no birth in the record, an age is filed not sure, his words kept."""
    w = inner()
    w.chat(4, upto=8)
    w.run(Model({"facts": [ABOUT_TEN]}))
    e = remark(w, "when I was about ten")
    assert e.fm.get("as_said") == "when I was about ten" and not e.fm.get("range_from")
    assert e.fm.get("date_note") and "reported" in e.fm["date_note"]


def test_42_two_later_sessions_that_return_to_a_past_event_attach_to_the_same_one(inner):
    w = inner()
    w.chat(4, upto=8)
    w.run(Model({"facts": [ABOUT_TEN]}))
    event = "event/he-shouted-about-the-bills"
    w.chat(1, upto=40)
    w.run(Model({"facts": [fact(1, "it's the kitchen in the old house", "The feeling goes back to the old kitchen.", about=[event])]}),
          now=LATER + timedelta(hours=1))
    w.chat(6, lines=made(6, "2026-11-13T04:00:00", [("O", "the bills thing came up again, the night he shouted."),
                                                    ("G", "The same night as before?")]))
    w.run(Model({"facts": [{"line": 1, "quote": "the bills thing came up again", "text": "The bills night came up again.",
                            "date": "not-sure", "kind": "observation", "about": [event]}]}), now=LATER + timedelta(hours=2))
    got = history(event)
    assert all(remark(w, words).id in got for words in ("when I was about ten", "the old house", "the bills thing"))


def test_now_shows_his_words_on_a_thread_never_the_question_he_answered(inner):
    w = inner(record=False)
    w.chat(4, upto=8)
    w.run(Model({"facts": [fact(4, "on the phone with my father yesterday", "Sam's father asked him about money.",
                                answering="When did you notice it this time?", create=[{"kind": "person", "name": "my father"}])]}))
    [line] = [l for l in now_mod.text(w.repo).splitlines() if "my father" in l]
    assert "on the phone with my father yesterday" in line and "notice it this time" not in line


@pytest.mark.parametrize("name", ["quiet around my dad", "going quiet"])
def test_a_theme_gathers_earlier_tellings_only_when_it_starts_and_only_those_on_no_theme(inner, name):
    """A new theme gathers the earlier tellings on no theme; one he already has (`going quiet`) gathers none, since
    putting what's on one thread onto another is a join, and joins are made in conversation."""
    w = inner()
    loose = add(w, {"title": "quiet with dad at lunch", "date": "2026-10-02", "kind": "observation", "about": [], "by": "sam"},
                "- Sam: “I went quiet with dad at lunch”\n")
    elsewhere = add(w, {"title": "quiet in standup", "date": "2026-10-03", "kind": "observation", "about": ["theme/quiet-at-work"],
                        "by": "sam"}, "- Sam: “quiet in standup again”\n")
    w.chat(4, upto=2)
    w.run(Model({"facts": [fact(4, "I go quiet around my dad again.", "Sam goes quiet around his dad again.",
                                create=[{"kind": "theme", "name": name}], again=[loose, elsewhere])]}))
    gathered = {e.fm["from"] for e in w.events(kind="link") if e.fm.get("rel") == "placed-on"}
    assert gathered == ({loose} if name == "quiet around my dad" else set())


def test_a_past_event_is_refused_when_the_date_his_words_give_is_after_the_day_he_said_it(inner):
    w = inner(record=False)
    said = "the Leeds trip on 2026-11-28 is all I can think about."
    w.chat(6, lines=made(6, "2026-11-13T04:00:00", [("O", said), ("G", "What about it?")]))
    out = w.run(Model({"facts": [{"line": 1, "quote": said, "text": "Sam keeps thinking about the Leeds trip.", "date": "2026-11",
                                  "kind": "observation", "create": [{"kind": "event", "name": "the Leeds trip"}]}]}))
    assert not [e for e in w.events() if any(a.startswith("event/") for a in e.about)]
    assert [d for d in out["dropped"] if "hasn't happened" in d["why"]]


def test_a_move_without_his_words_saying_it_was_wrong_is_refused(inner):
    w = inner(record=False)
    w.chat(4, upto=8)
    w.run(Model({"facts": [
        fact(4, "I called my brother Sam after", "Sam called his brother Sam.", create=[{"kind": "person", "name": "my brother Sam"}]),
        fact(4, "Sam asked me to lead the friday meeting", "Sam was asked to lead the friday meeting.",
             about=["person/my-brother-sam"])]}))
    meeting = remark(w, "lead the friday meeting")
    w.chat(4)
    out = w.run(Model({"facts": [fact(4, "the friday meeting went ok.", "The friday meeting went ok.",
                                      moves=[{"entry": meeting.id, "from": "person/my-brother-sam", "to": "person/my-brother-sam"},
                                             {"entry": meeting.id, "from": "person/my-brother-sam",
                                              "to": {"kind": "person", "name": "the friday meeting"}}])]}),
                now=LATER + timedelta(hours=1))
    assert meeting.id in history("my brother Sam") and not [e for e in w.events(kind="link") if e.fm.get("rel") == "placed-on"]
    assert [d for d in out["dropped"] if "wrong" in d["why"]]


def test_a_thread_is_named_as_he_typed_it(inner):
    w = inner(record=False)
    w.chat(4, upto=2)
    w.run(Model({"facts": [fact(4, "I go quiet around my dad again.", "Sam goes quiet around his dad.",
                                create=[{"kind": "person", "name": "My Dad"}])]}))
    assert [e.fm["name"] for e in w.events(kind="thread")] == ["my dad"]


def test_a_record_that_creates_no_threads_reads_no_thread_links():
    """Off by default: a join or a move in a record without `[threads] create` changes no history."""
    from engram import store, threads
    link = lambda rel, a, b: store.Event(f"l-{rel}", "", {"kind": "link", "rel": rel, "from": a, "to": b, "date": "2026-11-01"}, "")
    events = [link("joined-into", "story/ankle", "story/knee"), link("split-into", "story/ankle", "story/heel"),
              link("placed-on", "e1", "story/knee")]
    assert threads.Threads(events, ()).on("e1", ["story/ankle"], "2026-10-01") == ["story/ankle"]
