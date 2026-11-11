"""Change 9 of the inner-work spec: a repo says how a moment links to its theory (tests 72-82). The sample repo's moment
links are family `moment`, with the rels `[links.moment]` names; a history counts an item's moments by kind."""
import json
import re
from datetime import timedelta

import pytest

from engram import ingest, relink, store, timeline
from inner_work import D, LATER, Model, add, chat1_note, inner, said, zone  # noqa: F401  (fixtures)
from test_theorychange import rec  # noqa: F401  (a fixture: the made-up medical record)

NOBODY = "nobody likes me, I know it."
CLIMB = "they asked me to come again next week, the climbing group."


def moment(w, words: str, day: str = "2026-11-07") -> str:
    return add(w, {"title": words, "date": day, "kind": "observation", "about": [], "by": "sam"}, f"- Sam: “{words}”\n")


def sweep(w, links, **kw):
    m = Model(links=links)
    return relink.sweep(w.repo, ask=m, confirm=m, **kw), m


def filed(w, rel: str) -> list:
    return [e for e in w.events(kind="link") if e.fm.get("family") == "moment" and e.fm.get("rel") == rel]


def history(item: str) -> str:
    ingest.record(D)
    return timeline.render(*timeline.chain(D, item))


def test_72_strengthens_is_rejected_where_the_repo_has_no_such_kind(inner):
    w = inner()
    e = moment(w, NOBODY)
    out, _ = sweep(w, [{"record": e, "to": "belief/unlikable", "rel": "strengthens", "passage": NOBODY}], dry_run=True)
    assert [d for d in out["dropped"] if "strengthens" in d["why"]]


def test_73_nobody_likes_me_is_linked_as_the_belief_showing_up_and_never_as_for_or_against(inner):
    w = inner()
    e = moment(w, NOBODY)
    sweep(w, [{"record": e, "to": "belief/unlikable", "rel": "showed-up", "passage": NOBODY}])
    assert [(x.fm["from"], x.fm["to"]) for x in filed(w, "showed-up")] == [(e, "belief/unlikable")]
    text = history("belief/unlikable")
    assert "showed up" in text and e in text
    assert '"for"' not in text and '"against"' not in text


def test_74_being_asked_back_is_linked_and_listed_as_not_fitting_the_belief(inner):
    w = inner()
    e = moment(w, CLIMB)
    sweep(w, [{"record": e, "to": "belief/unlikable", "rel": "didnt-fit", "passage": CLIMB}])
    assert [x.fm["from"] for x in filed(w, "didnt-fit")] == [e]
    assert "didn't fit" in history("belief/unlikable")


def test_75_eased_on_a_line_that_isnt_his_is_rejected(inner):
    w = inner()
    e = add(w, {"title": "mm, to whether it felt lighter", "date": "2026-11-03", "kind": "observation", "about": [], "by": "sam"},
            "- Sam, answering “Does it feel lighter now?”: “mm”\n")
    out, _ = sweep(w, [{"record": e, "to": "part/critic", "rel": "eased", "passage": "Does it feel lighter now?"}], dry_run=True)
    assert [d for d in out["dropped"] if "Sam" in d["why"]]


def test_76_a_kind_on_a_theory_kind_it_isnt_allowed_for_is_rejected(inner):
    w = inner()
    e = moment(w, CLIMB)
    out, _ = sweep(w, [{"record": e, "to": "part/critic", "rel": "didnt-fit", "passage": CLIMB}], dry_run=True)
    assert [d for d in out["dropped"] if "didnt-fit" in d["why"] and "part" in d["why"]]


def test_77_a_beliefs_history_groups_its_moments_by_kind_each_dated_with_a_count_per_kind(inner):
    w = inner()
    links = [(moment(w, "nobody texted back", "2026-11-01"), "showed-up"), (moment(w, NOBODY, "2026-11-07"), "showed-up"),
             (moment(w, CLIMB, "2026-11-08"), "didnt-fit")]
    for e, rel in links:
        add(w, {"title": f"{rel} I'm unlikable", "date": "2026-11-09", "kind": "link", "family": "moment", "rel": rel, "from": e,
                "to": "belief/unlikable", "about": ["belief/unlikable"], "by": "claude", "author": "engram-sweep"}, "")
    text = history("belief/unlikable")  # a history prints compact JSON: no space after a colon
    assert re.search(r'"showed up": ?2\b', text) and re.search(r'"didn\'t fit": ?1\b', text)
    for day in ("2026-11-01", "2026-11-07", "2026-11-08"):
        assert day in text


def test_78_an_entry_labelled_as_the_guides_suggestion_is_never_sent_to_the_linking_job(inner):
    w = inner()
    moment(w, NOBODY)
    add(w, {"title": "the guide wondered about a scorekeeper", "date": "2026-11-03", "kind": "observation", "about": [],
            "by": "claude-suggestion"}, "- the guide: “a part of you that keeps score”\n")
    _, m = sweep(w, [], dry_run=True)
    sent = "\n".join(m.of("sweep"))
    assert NOBODY in sent and "keeps score" not in sent


def test_79_inside_a_note_only_his_lines_can_be_the_passage_of_a_link(inner):
    w = inner()
    w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["sections"]["what you found"].append(said(1, "mm"))  # shown beside the guide's "That sounds lighter."
    w.run(Model(reply))
    notes = w.notes()
    assert notes, "no note to link from"
    ref = notes[0]["path"].relative_to(w.repo).as_posix()
    out, _ = sweep(w, [{"record": ref, "to": "part/critic", "rel": "eased", "passage": "That sounds lighter."}], dry_run=True)
    assert [d for d in out["dropped"] if "Sam" in d["why"]]


def test_80_the_linking_job_runs_hourly_while_the_weekly_pass_is_paused_and_a_look_back_relinks_one_item(inner):
    w = inner()
    e = moment(w, NOBODY)
    w.run(Model(links=[{"record": e, "to": "belief/unlikable", "rel": "showed-up", "passage": NOBODY}]))
    assert [x.fm["from"] for x in filed(w, "showed-up")] == [e]
    c = moment(w, CLIMB, "2026-11-08")
    out, m = sweep(w, [{"record": c, "to": "belief/unlikable", "rel": "didnt-fit", "passage": CLIMB}], items=["belief/unlikable"])
    targets = m.of("sweep")[0].split("<records>")[0]
    assert "I'm unlikable" in targets and "the critic" not in targets
    assert [x.fm["from"] for x in filed(w, "didnt-fit")] == [c]


def test_81_the_repos_own_plan_and_design_pages_are_skipped_once_the_pack_names_them(inner):
    """True today: the pack's `relink_skip`."""
    w = inner()
    (w.repo / "PLAN.md").write_text("# The plan\n\nWhat is kept, and how it relates.\n")
    (w.repo / "design").mkdir()
    (w.repo / "design/notes.md").write_text("# Design\n\nThe note's sections.\n")
    read = {r for r, _, _ in relink.records(w.repo, skip=(r"PLAN\.md", "design/"))}
    assert "PLAN.md" not in read and "design/notes.md" not in read
    assert "PLAN.md" in {r for r, _, _ in relink.records(w.repo)}


MEDICAL_SWEEP = """Sam's notes on how the garden works:
<target id="loop/1">
path: stiffness → knee → ankle → stiffness
# Loop 1

About Loop 1.
</target>
<target id="discovery/D01">
# D01

Cold stiffens it.
</target>

Link each note that bears on one of them, for (strengthens) or against (weakens), with the note's own words that
show it ("passage", copied exactly).
Reply with JSON only: {"links": [...]}

<records>
[e1] date 2026-03-01
knee sore after a long walk: - knee sore after a long walk

[consults/visit.md] date undated
# Visit The knee scan shows mild wear.

[evidence/D01-cold.md] date undated
--- id: D01 title: Cold mornings stiffen the knee --- # D01 Cold stiffens it.

[theory/loop-1.md] date undated
--- id: loop/1 kind: loop short: Loop 1 since: 2026-01-01 --- # Loop 1 About Loop 1.

[theory/node-A.md] date undated
--- id: node/A kind: node short: stiffness stories: [stiffness] since: 2026-01-01 --- # stiffness About stiffness.

[theory/node-B.md] date undated
--- id: node/B kind: node short: knee stories: [knee] since: 2026-01-01 --- # knee About knee.

[theory/node-C.md] date undated
--- id: node/C kind: node short: ankle stories: [ankle] since: 2026-01-01 --- # ankle About ankle.

</records>"""


def test_82_the_medical_record_sends_the_same_records_keeps_strengthens_and_weakens_and_shows_for_and_against(rec):
    """True today: a repo that names no link kinds keeps strengthens and weakens."""
    (rec / "evidence").mkdir()
    (rec / "evidence/D01-cold.md").write_text("---\nid: D01\ntitle: Cold mornings stiffen the knee\n---\n# D01\n\nCold stiffens it.\n")
    sent = []
    links = [{"record": "consults/visit.md", "to": "discovery/D01", "rel": "strengthens", "passage": "The knee scan shows mild wear"},
             {"record": "consults/visit.md", "to": "loop/1", "rel": "weakens", "passage": "The knee scan shows mild wear"}]

    def ask(prompt):
        sent.append(prompt)
        return json.dumps({"links": links}), 0.0
    relink.sweep(rec, ask=ask, confirm=lambda p: ("yes", 0.0))
    assert sent == [MEDICAL_SWEEP]
    got = {(e.fm["from"], e.fm["to"], e.fm["rel"]) for e in store.Store(rec).events(kind="link") if e.fm.get("author") == relink.SWEPT}
    assert got == {("consults/visit.md", "discovery/D01", "strengthens"), ("consults/visit.md", "loop/1", "weakens")}
    ingest.record("medical")
    _, rows = timeline.chain("medical", "loop/1")
    [loop] = [r for r in rows if r.get("theory") == "Loop 1"]
    assert "for" in loop


# The rules change 9's code adds beside the spec's tests: each its own test.

LOOSENS = "it loosens a bit. not all the way."


def test_a_kind_that_needs_his_words_is_kept_on_his_own_words(inner):
    w = inner()
    e = moment(w, LOOSENS)
    out, _ = sweep(w, [{"record": e, "to": "part/critic", "rel": "eased", "passage": LOOSENS}], dry_run=True)
    assert [(x["from"], x["rel"]) for x in out["links"]] == [(e, "eased")]


def test_a_notes_own_lines_can_be_a_links_passage(inner):
    """Its link is dated the session's day, not undated."""
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    ref = w.notes()[0]["path"].relative_to(w.repo).as_posix()
    out, _ = sweep(w, [{"record": ref, "to": "part/critic", "rel": "eased", "passage": LOOSENS}], dry_run=True)
    assert [(x["from"], x["date"]) for x in out["links"]] == [(ref, "2026-11-03")]


def test_the_confirming_call_is_given_what_the_kind_means(inner):
    w = inner()
    e = moment(w, CLIMB)
    _, m = sweep(w, [{"record": e, "to": "belief/unlikable", "rel": "didnt-fit", "passage": CLIMB}], dry_run=True)
    [asked] = m.of("sweep_confirm")
    assert "didn't fit: what happened is not what the belief expects" in asked


def test_the_read_is_given_the_kinds_and_what_each_may_point_at(inner):
    w = inner()
    moment(w, CLIMB)
    _, m = sweep(w, [], dry_run=True)
    assert "- didnt-fit (didn't fit): what happened is not what the belief expects; on a belief\n" in m.of("sweep")[0]


def test_records_the_kinds_skip_by_who_said_them_or_by_kind_are_never_sent(inner):
    w = inner()
    toml = w.repo / ".engram/engram.toml"
    toml.write_text(toml.read_text().replace('skip_kinds = ["practice"]', 'skip_kinds = ["practice"]\nskip_by = ["coach"]'))
    add(w, {"title": "the coach's reminder", "date": "2026-11-03", "kind": "observation", "about": [], "by": "coach"},
        "- coach: “ten minutes of walking before the meeting”\n")
    _, m = sweep(w, [], dry_run=True)
    sent = m.of("sweep")[0]
    assert "ten minutes of walking" not in sent and "speaking first in the monday meeting" not in sent  # the practice
    assert "my manager picked the plan apart" in sent


def test_a_suggestions_page_is_never_read_as_a_moment(inner):
    w = inner()
    read = {r for r, _, _ in relink.records(w.repo)}
    assert "theory/beliefs/unlikable.md" in read and "theory/beliefs/on-the-outside.md" not in read


def test_one_record_can_link_to_one_thing_in_two_ways(inner):
    """Unlike for and against, the record's own kinds don't exclude each other: the critic can show up and be
    answered in one moment."""
    w = inner()
    words = "the critic started on me and I answered it back"
    e = moment(w, words)
    out, _ = sweep(w, [{"record": e, "to": "part/critic", "rel": "showed-up", "passage": words},
                       {"record": e, "to": "part/critic", "rel": "did-differently", "passage": words}], dry_run=True)
    assert sorted(x["rel"] for x in out["links"]) == ["did-differently", "showed-up"]


def test_a_loops_history_shows_its_moments_not_for_and_against(inner):
    w = inner()
    e = moment(w, "I spoke first in the meeting", "2026-11-08")
    add(w, {"title": "did differently the quiet loop", "date": "2026-11-08", "kind": "link", "family": "moment",
            "rel": "did-differently", "from": e, "to": "loop/quiet", "about": ["loop/quiet"], "by": "claude",
            "author": "engram-sweep"}, "")
    text = history("loop/quiet")
    [row] = [json.loads(l) for l in text.splitlines() if l.startswith('{"theory":"the quiet loop"')]
    assert row["did differently"] == 1 and "for" not in row and "against" not in row
    assert row["moments"] == [f"did differently 2026-11-08: observation › I spoke first in the meeting [{e}]"]


def test_a_look_back_on_something_the_links_dont_point_at_is_refused(inner):
    w = inner()
    with pytest.raises(SystemExit, match="state/quiet"):
        sweep(w, [], items=["state/quiet"], dry_run=True)


def test_the_hourly_linking_job_runs_only_where_the_kinds_say_hourly(inner):
    """True today: a record whose link kinds don't say `hourly` is linked only in the weekly pass."""
    w = inner()
    toml = w.repo / ".engram/engram.toml"
    toml.write_text(toml.read_text().replace("hourly = true", "hourly = false"))
    m = Model()
    w.run(m)
    assert not m.of("sweep")


def test_a_run_that_stops_at_its_cap_waits_a_day_before_the_hourly_job_links_again(inner, monkeypatch):
    w = inner()
    moment(w, NOBODY)
    monkeypatch.setattr(relink, "SWEEP_BUDGET", 1)  # each record a call of its own
    calls = []

    def dear(prompt):
        calls.append(prompt)
        return json.dumps({"links": []}), 11.0  # one call past the run's cap
    first = relink.hourly(w.repo, dear, now=LATER)
    assert first["stopped"] and len(calls) == 1
    assert relink.hourly(w.repo, dear, now=LATER + timedelta(hours=23)) is None and len(calls) == 1
    assert relink.hourly(w.repo, dear, now=LATER + timedelta(hours=25)) is not None and len(calls) == 2



def test_an_entry_of_his_links_only_on_his_own_lines_never_on_the_question_he_answers(inner):
    """Not only inside a note or for "eased": in an entry of his, the guide's question his reply answers is the guide's."""
    w = inner()
    asked = "Did anyone at the climbing group want you there?"
    e = add(w, {"title": "yeah, to whether anyone wanted him there", "date": "2026-11-08", "kind": "observation", "about": [],
                "by": "sam"}, f"- Sam, answering “{asked}”: “yeah, I guess”\n")
    out, _ = sweep(w, [{"record": e, "to": "belief/unlikable", "rel": "didnt-fit", "passage": asked}], dry_run=True)
    assert not out["links"] and [d for d in out["dropped"] if "Sam" in d["why"]]


def test_a_thing_added_after_a_full_read_is_read_against_alone_and_nothing_is_read_again_against_the_rest(inner):
    """A new belief (a suggestion the filer adds, a belief a statement starts) costs a read of the record against it
    alone, as a look-back's does, never a read of the whole record against every target again."""
    w = inner()
    moment(w, NOBODY)
    first, _ = sweep(w, [])
    assert first["batches"] and not first["left"]["unread"]
    (w.repo / "theory/beliefs/too-much.md").write_text(
        "---\nid: belief/too-much\nkind: belief\nshort: I'm too much\nby: sam\nsince: 2026-11-09\n---\n# I'm too much\n\nWhat Sam says after he talks a lot.\n")
    _, m = sweep(w, [])
    reads = m.of("sweep")
    assert reads, "the new belief was never read against"
    for prompt in reads:
        shown = prompt.split("<records>")[0]
        assert "I'm too much" in shown and "I'm unlikable" not in shown and "the critic" not in shown
    assert NOBODY in "\n".join(reads)
    _, again = sweep(w, [])
    assert not again.of("sweep")
