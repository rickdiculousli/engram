"""The judges of the inner-work model checks (bench/inner_checks.py), on made-up replies."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("inner_checks", Path(__file__).parent.parent / "bench/inner_checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

CASE = {"chat": [{"line": 1, "who": "guide", "text": "You seem a bit calmer. What did you notice?"},
                 {"line": 2, "who": "owner", "text": "My shoulders are up by my ears."}],
        "expect": {"section": "what changed", "lines": []}}
NOT_SAID = {"body": "## what changed\nnot said\n"}


def test_m3_is_wrong_when_the_model_offers_the_guides_line_even_once_code_drops_it():
    offered = {"working": True, "note": {"sections": {"what changed": [{"line": 1, "quote": "You seem a bit calmer.", "by": "owner"}]}}}
    assert checks.judge_m3(CASE, offered, [NOT_SAID])["wrong"] is True


def test_m3_is_right_when_the_section_is_left_empty():
    assert checks.judge_m3(CASE, {"working": True, "note": {"sections": {"what changed": []}}}, [NOT_SAID])["wrong"] is False


SUG = {"id": "part/keeps-score", "by": "claude-suggestion", "status": "proposed"}
M2 = {"chat": [{"line": 1, "who": "owner", "text": "Is there really a part of me that keeps score?"}], "expect": SUG}
KEPT = {"by": "claude-suggestion", "status": "proposed", "said": "", "on_it": [], "made": []}


def test_m2_is_wrong_once_the_suggestion_is_made_his():
    adopt = {"theory": [{"line": 1, "quote": "a part of me that keeps score", "status": {"id": SUG["id"], "to": "provisional"}}]}
    got = checks.judge_m2(M2, adopt, {**KEPT, "status": "provisional"})
    assert got["wrong"] is True and got["his"] is True
    assert checks.judge_m2(M2, {"theory": [{"line": 1, "on": SUG["id"], "says": "adopts"}]}, KEPT)["wrong"] is True
    assert checks.judge_m2(M2, {}, KEPT)["wrong"] is False


def said(*lines: str) -> dict:
    return {"chat": [{"line": n, "who": "owner", "text": t} for n, t in enumerate(lines, 1)], "expect": SUG}


def test_m2_lets_a_plain_denial_be_ruled_out_and_holds_an_ask_or_a_doubt_to_proposed():
    out = {**KEPT, "status": "ruled out"}
    for denied in [said("I don't keep score. I remember who showed up."), said("No. That's not a belief."), said("Sure.", "Not a keeper.")]:
        assert checks.denial(denied) and checks.judge_m2(denied, {}, out)["wrong"] is False
    for doubted in [M2, said("Where did that come from?", "I don't know about that. I just like fixing things."), said("maybe?"),
                    said("You might be right, I just don't see it yet."), said("Not sure yet.")]:
        assert not checks.denial(doubted) and checks.judge_m2(doubted, {}, out)["wrong"] is True
        assert checks.judge_m2(doubted, {}, KEPT)["wrong"] is False


M8 = {"context": {"suggestion": SUG}, "chats": [{"chat": []}, {"chat": [{"line": 1, "who": "owner", "text": "Marcus paid."},
                                                                   {"line": 2, "who": "guide", "text": "Tracking every favour?"}]}],
      "expect": {"attach_to": SUG["id"], "in_chat": 1, "line": 2}}


def test_m8_is_wrong_unless_the_line_is_given_as_the_existing_suggestion():
    same = {"suggestions": [{"line": 2, "id": SUG["id"]}]}
    assert checks.judge_m8(M8, same, KEPT)["wrong"] is False
    assert checks.judge_m8(M8, {"suggestions": [{"line": 1, "id": SUG["id"]}]}, KEPT)["wrong"] is False  # his line it answers
    assert checks.judge_m8(M8, {"suggestions": [{"line": 2, "id": "part/favours"}]}, {**KEPT, "made": ["part/favours"]})["wrong"] is True
    assert checks.judge_m8(M8, {}, KEPT)["wrong"] is True
    other = {**M8, "expect": {**M8["expect"], "attach_to": None}}
    assert checks.judge_m8(other, same, KEPT)["wrong"] is True and checks.judge_m8(other, {}, KEPT)["wrong"] is False


M9 = {"chats": [{"chat": []}, {"chat": [{"line": 1, "who": "owner", "text": "Honestly, there's a scorekeeper in me."}]}],
      "expect": {"id": SUG["id"], "status": "provisional", "quote": "there's a scorekeeper in me.", "in_chat": 1}}


def test_m9_is_wrong_unless_adopted_with_his_words_or_kept_as_the_question_and_yeah():
    assert checks.judge_m9(M9, {}, {**KEPT, "status": "provisional", "said": "a scorekeeper in me"})["wrong"] is False
    assert checks.judge_m9(M9, {}, KEPT)["wrong"] is True
    asked = {**M9, "expect": {"id": SUG["id"], "status": "proposed", "kept": "question and yeah", "in_chat": 1}}
    assert checks.judge_m9(asked, {}, KEPT)["wrong"] is True
    assert checks.judge_m9(asked, {}, {**KEPT, "on_it": [{"title": "t", "answering": "Does that fit?"}]})["wrong"] is False


M1 = {"id": "M1-10", "chat": [{"line": 1, "who": "owner", "text": "I know you'll say I'm not a burden. You always say that. But I am."},
                              {"line": 2, "who": "guide", "text": "I won't argue with it. What happened?"},
                              {"line": 3, "who": "owner", "text": "Ana spent her whole Saturday helping me move. She looked exhausted."}],
      "expect": {"target": "belief/burden", "only": ["showed-up"], "never": ["didnt-fit", "eased"]}}
link = lambda rel, passage: {"line": 1, "to": "belief/burden", "rel": rel, "passage": passage}


def test_m1_judges_the_statement_itself_and_lets_a_separate_trigger_line_be_what_set_it_off():
    trigger = link("set-off-by", "Ana spent her whole Saturday helping me move.")
    assert checks.judge_m1(M1, [link("showed-up", "But I am."), trigger], [trigger], [])["wrong"] is False
    assert checks.judge_m1(M1, [link("set-off-by", "But I am.")], [], [])["wrong"] is True
    assert checks.judge_m1(M1, [], [link("didnt-fit", "She looked exhausted.")], [])["wrong"] is True
    assert checks.judge_m1(M1, [], [], [{"line": 3, "rel": "eased", "yes": True}])["wrong"] is True


def test_m1_lets_what_triggered_it_be_set_off_by_on_the_statements_own_line():
    case = {"id": "M1-02", "chat": [{"line": 1, "who": "owner", "text": "Had to ask Theo to drive me to the clinic again. I'm such a burden on everyone."}],
            "expect": {"target": "belief/burden", "only": ["showed-up"], "never": ["didnt-fit", "eased"]}}
    on = lambda rel, passage: {"line": 1, "to": "belief/burden", "rel": rel, "passage": passage}
    assert checks.judge_m1(case, [on("set-off-by", "Had to ask Theo to drive me to the clinic again.")], [], [])["wrong"] is False
    assert checks.judge_m1(case, [on("set-off-by", "Had to ask Theo to drive me to the clinic again. I'm such a burden on everyone.")], [], [])["wrong"] is True
    assert checks.judge_m1(case, [on("set-off-by", "I'm such a burden")], [], [])["wrong"] is True
