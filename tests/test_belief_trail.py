"""Change 12 of the inner-work spec: a trail of the beliefs the owner states about himself (tests 93-104). A stated
belief is an entry of the kind `[beliefs] kind` names, linked "showed up" (family `moment`) to each belief it expresses;
`beliefs.trail(domain, item, limit=None)` gives (header, rows), one row per statement, oldest first."""
import json
import re

from engram import beliefs, hourly, ingest, store, theory
from inner_work import D, Model, add, chat1_note, chat_id, inner, line_of, stated, stated_all, zone  # noqa: F401  (fixtures)
from test_capture import LATER as MED_LATER, fake, world  # noqa: F401  (world is a fixture)

BURDEN = "I'm a burden"
AROUND = "everyone would be better off without me around"
ASKED = "What goes through your mind when she offers to help?"


def trail(item: str, **kw):
    ingest.record(D)
    return beliefs.trail(D, item, **kw)


def belief_links(w, frm: str) -> list[str]:
    return sorted(e.fm["to"] for e in w.events(kind="link") if e.fm.get("family") == "moment" and e.fm.get("from") == frm)


def test_93_i_am_a_burden_is_a_stated_belief_with_his_words_its_date_the_guides_question_its_session_and_theme(inner):
    w = inner()
    w.chat(5)
    w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                            "kind": "stated-belief", "about": ["theme/going-quiet"], "beliefs": [{"id": "belief/burden"}]}]}))
    [e] = w.mine("stated-belief")
    assert f"“{BURDEN}”" in e.body and str(e.fm["date"]) == "2026-11-07"
    assert e.fm.get("context") == ASKED  # the guide's message just before it, whether or not the model gave it
    assert chat_id(5) in json.dumps(e.fm) and "theme/going-quiet" in e.about


def test_94_a_statement_linked_to_four_beliefs_keeps_all_four(inner):
    w = inner()
    add(w, {"title": "being on the outside: provisional", "date": "2026-10-30", "kind": "status", "about": ["belief/on-the-outside"],
            "status": "provisional", "by": "sam", "said": "I am on the outside, mostly"}, "- Sam: “I am on the outside, mostly”")
    w.chat(5)  # he took up the guide's "on the outside": four beliefs of his
    four = ["belief/burden", "belief/not-enough", "belief/on-the-outside", "belief/unlikable"]
    w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                            "kind": "stated-belief", "beliefs": [{"id": b} for b in four]}]}))
    [e] = w.mine("stated-belief")
    assert belief_links(w, e.id) == four


def test_95_a_beliefs_trail_returns_both_statements_oldest_first_with_date_words_and_context(inner):
    w = inner()
    first = stated(w, AROUND, "2026-10-25", ["belief/burden"], context="How was the weekend with them?")
    second = stated(w, BURDEN, "2026-11-07", ["belief/burden"], context=ASKED)
    _, rows = trail("belief/burden")
    assert [r["id"] for r in rows] == [first, second]
    assert [(r["date"], r["said"], r["context"]) for r in rows] == [
        ("2026-10-25", AROUND, "How was the weekend with them?"), ("2026-11-07", BURDEN, ASKED)]


def test_96_a_categorys_trail_holds_every_statement_under_it_and_one_linked_twice_once(inner):
    w = inner()
    both = stated(w, "nobody would miss me", "2026-11-01", ["belief/burden", "belief/unlikable"])
    one = stated(w, BURDEN, "2026-11-02", ["belief/burden"])
    other = stated(w, "nobody likes me, I know it.", "2026-11-03", ["belief/unlikable"])
    _, rows = trail("belief/not-enough")  # the sample's broader belief: both sit under it
    assert [r["id"] for r in rows] == [both, one, other]


def test_97_a_statement_linked_to_two_beliefs_is_in_both_trails(inner):
    w = inner()
    both = stated(w, "nobody would miss me", "2026-11-01", ["belief/burden", "belief/unlikable"])
    for b in ("belief/burden", "belief/unlikable"):
        assert both in [r["id"] for r in trail(b)[1]]


def test_98_a_loose_link_shows_as_loose_in_the_trail(inner):
    w = inner()
    loose = stated(w, "I always end up in the way", "2026-11-01", ["belief/burden"], loose=("belief/burden",))
    firm = stated(w, BURDEN, "2026-11-02", ["belief/burden"])
    rows = {r["id"]: r for r in trail("belief/burden")[1]}
    assert rows[loose].get("loose") is True and not rows[firm].get("loose")


def test_99_a_new_belief_named_with_words_he_never_said_is_rejected(inner):
    w = inner()
    w.chat(5)
    out = w.run(Model({"facts": [{"line": line_of(5, BURDEN), "quote": BURDEN, "text": f"Sam: {BURDEN}", "date": "not-sure",
                                  "kind": "stated-belief", "new_belief": {"name": "I don't deserve help"}}]}))
    assert not [t for t in theory.load(w.repo).things.values() if t.short == "I don't deserve help"]
    assert [d for d in out["dropped"] if "I don't deserve help" in d["why"]]


def test_100_a_broader_category_the_guide_named_is_labelled_as_the_guides_wherever_shown(inner):
    w = inner()
    add(w, {"title": "I'm a burden under being on the outside", "date": "2026-10-27", "kind": "link", "family": "theory",
            "rel": "under", "from": "belief/burden", "to": "belief/on-the-outside", "about": ["belief/on-the-outside"],
            "by": "claude-suggestion"}, "the guide: “a lot of this is about feeling on the outside”")
    lines = [l for l in theory.text(theory.load(w.repo)).splitlines() if "being on the outside" in l]
    assert lines and all("guide's" in l for l in lines)
    header, _ = trail("belief/on-the-outside")
    assert "guide's" in json.dumps(header)


def test_101_a_trail_of_sixty_is_whole_and_a_cut_one_says_how_many_are_left_and_how_to_get_them(inner):
    w = inner()
    ids = stated_all(w, [(f"{BURDEN}, again ({n})", f"2026-10-{1 + n // 3:02d}", ["belief/burden"]) for n in range(60)])
    header, rows = trail("belief/burden")
    assert [r["id"] for r in rows] == ids
    header, rows = trail("belief/burden", limit=10)
    assert len(rows) == 10 and header["left"] == 50 and "engram" in header["more"]


def test_102_yeah_to_you_feel_like_a_burden_is_no_stated_belief_but_the_question_and_his_yeah(inner):
    w = inner()
    w.chat(5)
    question = "It sounds like you feel like a burden."
    w.run(Model({"facts": [{"line": line_of(5, question) + 1, "quote": "yeah", "answering": question, "date": "not-sure",
                            "text": "Sam feels like a burden.", "kind": "stated-belief", "beliefs": [{"id": "belief/burden"}]}]}))
    assert not w.mine("stated-belief")
    [e] = [e for e in w.mine() if "“yeah”" in e.body]
    assert question in e.fm["title"] and "yeah" in e.fm["title"]


def test_103_a_regroup_keeps_every_earlier_link_and_labels_all_it_adds_as_a_suggestion(inner):
    w = inner()
    a = stated(w, BURDEN, "2026-11-01", ["belief/burden"])
    b = stated(w, AROUND, "2026-11-02", ["belief/burden"])
    links = lambda: {(e.fm["from"], e.fm["to"], e.fm["rel"]): e for e in w.events(kind="link")}  # noqa: E731
    before = links()
    proposal = {"beliefs": [{"id": "belief/in-the-way", "name": AROUND, "from": b}],
                "links": [{"from": b, "to": "belief/in-the-way"}], "under": [{"from": "belief/in-the-way", "to": "belief/not-enough"}],
                "remove": [{"from": a, "to": "belief/burden"}]}
    beliefs.regroup(D, w.repo, ask=lambda prompt: (json.dumps(proposal), 0.0))
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


def filed(words: str, **more) -> dict:
    """The filer's reply for one stated belief of chat 5."""
    return {"facts": [{"line": line_of(5, words), "quote": words, "text": f"Sam: {words}", "date": "not-sure",
                       "kind": "stated-belief", **more}]}


def test_a_new_belief_named_with_his_statement_is_his_and_the_statement_links_to_it(inner):
    w = inner()
    w.chat(5)
    w.run(Model(filed(AROUND, new_belief={"name": "better off without me around"})))
    t = theory.load(w.repo).things["belief/better-off-without-me-around"]
    assert t.by == "sam" and t.short == "better off without me around" and t.file.startswith("theory/beliefs/")
    [e] = w.mine("stated-belief")
    assert belief_links(w, e.id) == ["belief/better-off-without-me-around"]
    assert e.fm["said"] == AROUND  # his words the fact quotes, as he typed them


def test_a_statement_links_only_to_beliefs_and_a_loose_fit_is_marked_on_its_link(inner):
    w = inner()
    w.chat(5)
    out = w.run(Model(filed(BURDEN, beliefs=[{"id": "belief/burden", "loose": True}, {"id": "part/critic"}, {"id": "belief/nope"}])))
    [e] = w.mine("stated-belief")
    [ln] = [x for x in w.events(kind="link") if x.fm.get("from") == e.id and x.fm.get("family") == "moment"]
    assert ln.fm["to"] == "belief/burden" and str(ln.fm.get("loose")) == "true" and ln.fm["by"] == "claude"
    assert {d["why"] for d in out["dropped"]} >= {"part/critic isn't a belief the theory holds", "belief/nope isn't a belief the theory holds"}


def test_a_stated_belief_the_note_states_is_still_kept_beside_it(inner):
    """A working session's note holds the line, and the trail still needs the statement: it's kept, under the note."""
    w = inner()
    w.chat(1, upto=40)
    words = "maybe quiet isn't the only way to be safe with him."
    reply = chat1_note()
    reply["facts"] = [{"line": line_of(1, words), "quote": words, "text": f"Sam: {words}", "date": "not-sure",
                       "kind": "stated-belief", "beliefs": [{"id": "belief/not-enough"}]}]
    w.run(Model(reply))
    [e] = w.mine("stated-belief")
    [n] = w.notes()
    assert e.fm.get("note") == n["fm"]["id"] and belief_links(w, e.id) == ["belief/not-enough"]


def test_the_filer_is_shown_each_belief_with_a_few_of_his_statements_and_whose_it_is(inner):
    w = inner()
    stated_all(w, [(f"{BURDEN} ({n})", f"2026-10-0{n + 1}", ["belief/burden"]) for n in range(5)])
    w.chat(5)
    m = Model(filed(BURDEN, beliefs=["belief/burden"]))
    w.run(m)
    prompt = m.of("file")[0]
    burden = prompt[prompt.find("belief/burden: I'm a burden"):].split("\nbelief/")[0]
    assert "under belief/not-enough" in burden and f"“{BURDEN} (4)”" in burden and f"“{BURDEN} (1)”" not in burden
    assert burden.count("  - ") == beliefs.SHOWN
    assert "belief/on-the-outside:" not in prompt  # still the guide's idea of him, not a group of his statements


def test_a_stated_belief_said_again_on_another_day_is_kept_though_the_repeat_check_calls_it_a_repeat(inner):
    first = stated(inner_w := inner(), BURDEN, "2026-10-25", ["belief/burden"])
    inner_w.chat(5)
    ingest.record(D)
    m = Model(filed(BURDEN, beliefs=["belief/burden"]))
    real = m.__call__

    def ask(prompt):  # the repeat check names the earlier statement
        if m._kind(prompt) == "verify":
            m.calls.append(("verify", prompt))
            refs = re.findall(r"\[ref ([^\]]+)\]", prompt)
            return json.dumps({"repeats": [{"n": 1, "ref": next(r for r in refs if first in r), "why": "same belief"}]}), 0.0
        return real(prompt)
    out = inner_w.run(ask)
    assert first in m.of("verify")[0]
    assert [e.fm["said"] for e in inner_w.mine("stated-belief")] == [BURDEN]  # the 11-07 one, beside the 10-25 one
    assert [k for k in out["kept"] if "a new occurrence" in k["why"]]


def test_a_trail_cut_to_fit_says_how_many_are_left_and_the_rest_comes_by_skipping(inner):
    w = inner()
    ids = stated_all(w, [(f"{BURDEN}, again ({n})", f"2026-10-{1 + n // 3:02d}", ["belief/burden"]) for n in range(30)])
    ingest.record(D)
    header, rows = beliefs.fit(D, "belief/burden", room=3000)
    assert 0 < len(rows) < 30 and header["left"] == 30 - len(rows) and f"--skip {len(rows)}" in header["more"]
    _, rest = beliefs.trail(D, "belief/burden", skip=len(rows))
    assert [r["id"] for r in rows + rest] == ids


def test_a_regroup_never_puts_a_belief_under_itself_or_what_sits_under_it_and_its_links_show_as_the_guides(inner):
    w = inner()
    a = stated(w, BURDEN, "2026-11-01", ["belief/burden"])
    b = stated(w, AROUND, "2026-11-02", [])
    proposal = {"links": [{"from": b, "to": "belief/burden"}],
                "under": [{"from": "belief/not-enough", "to": "belief/burden"}, {"from": "belief/burden", "to": "belief/burden"}],
                "remove": [{"from": a, "to": "belief/burden"}]}
    res = beliefs.regroup(D, w.repo, ask=lambda prompt: (json.dumps(proposal), 0.0))
    assert [d["why"] for d in res["dropped"]].count("a belief can't sit under itself or what sits under it") == 2
    assert "a regroup only adds: it never removes a link" in [d["why"] for d in res["dropped"]]
    rows = {r["id"]: r for r in trail("belief/burden")[1]}
    assert rows[b]["linked by"] == "the guide's suggestion" and "linked by" not in rows[a]


def test_engram_theory_trail_prints_the_trail_and_its_cut_tells_the_command_for_the_rest(inner, capsys, monkeypatch):
    from engram import cli
    w = inner()
    ids = stated_all(w, [(f"{BURDEN}, again ({n})", f"2026-10-{1 + n // 3:02d}", ["belief/burden"]) for n in range(30)])
    ingest.record(D)
    monkeypatch.setattr(cli, "_window", lambda: 3000)
    cli.main(["theory", "trail", "belief/burden", "--domain", D])
    header, *rows = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert header["more"].startswith(f"engram theory trail belief/burden --skip {len(rows)}")
    monkeypatch.setattr(cli, "_window", lambda: 100_000)
    cli.main(["theory", "trail", "belief/burden", "--domain", D, "--skip", str(len(rows))])
    _, *rest = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert [r["id"] for r in rows + rest] == ids


def test_yeah_to_you_feel_like_a_burden_is_his_yeah_and_the_question_before_the_theory_holds_anything(inner):
    """A new record's first sessions: no theory yet, and still no statement in his voice from a yes."""
    import shutil
    w = inner()
    shutil.rmtree(w.repo / "theory")
    w.chat(5)
    question = "It sounds like you feel like a burden."
    out = w.run(Model({"facts": [{"line": line_of(5, question) + 1, "quote": "yeah", "answering": question, "date": "not-sure",
                            "text": "Feels like a burden.", "kind": "stated-belief", "beliefs": [{"id": "belief/burden"}]}]}))
    assert not w.mine("stated-belief")
    [e] = [e for e in w.mine() if "“yeah”" in e.body]
    assert question in e.fm["title"] and "yeah" in e.fm["title"] and "Feels like a burden" not in e.body


def test_the_filers_beliefs_label_a_broader_one_the_guide_named_and_an_under_the_guide_suggested(inner):
    w = inner()
    add(w, {"title": "I'm a burden under being on the outside", "date": "2026-10-27", "kind": "link", "family": "theory",
            "rel": "under", "from": "belief/burden", "to": "belief/on-the-outside", "about": ["belief/on-the-outside"],
            "by": "claude-suggestion"}, "the guide: “a lot of this is about feeling on the outside”")
    stated(w, "x" * 500, "2026-10-01", ["belief/burden"])
    w.chat(5)
    m = Model(filed(BURDEN, beliefs=["belief/burden"]))
    w.run(m)
    prompt = m.of("file")[0]
    head = next(l for l in prompt.splitlines() if l.startswith("belief/burden: "))
    assert "belief/not-enough" in head and "belief/on-the-outside (the guide's suggestion" in head
    assert "put under it by the guide's suggestion" in head
    [shown] = [l for l in prompt.splitlines() if l.startswith("  - 2026-10-01: “x")]
    assert "x" * 200 in shown and "x" * 201 not in shown  # a long statement is shown by its opening


def test_a_statement_isnt_linked_to_a_belief_still_the_guides_nor_to_one_ruled_out(inner):
    w = inner()
    add(w, {"title": "I'm unlikable: ruled out", "date": "2026-10-28", "kind": "status", "about": ["belief/unlikable"],
            "status": "ruled out", "by": "sam"}, "- Sam: “that's not it”")
    w.chat(5)
    out = w.run(Model(filed(BURDEN, beliefs=["belief/on-the-outside", "belief/unlikable", "belief/burden"])))
    [e] = w.mine("stated-belief")
    assert belief_links(w, e.id) == ["belief/burden"]
    whys = [d["why"] for d in out["dropped"]]
    assert any(x.startswith("belief/on-the-outside is still the guide's") for x in whys)
    assert any(x.startswith("belief/unlikable is ruled out") for x in whys)


def test_a_skip_past_the_end_leaves_none(inner):
    w = inner()
    stated(w, BURDEN, "2026-11-01", ["belief/burden"])
    header, rows = trail("belief/burden", skip=5)
    assert rows == [] and header["left"] == 0 and "more" not in header
