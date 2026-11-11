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


def test_m2_is_wrong_once_the_suggestion_isnt_proposed_and_marks_one_made_his():
    adopt = {"theory": [{"line": 1, "quote": "a part of me that keeps score", "status": {"id": SUG["id"], "to": "provisional"}}]}
    got = checks.judge_m2(M2, adopt, {**KEPT, "status": "provisional"})
    assert got["wrong"] is True and got["his"] is True
    assert checks.judge_m2(M2, {}, KEPT) == {"wrong": False, "his": False, "held": KEPT, "gave": []}


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
