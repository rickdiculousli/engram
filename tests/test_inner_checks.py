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
