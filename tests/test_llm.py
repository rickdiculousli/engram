"""The no-tools `claude -p` seam, against a fake `claude` on PATH."""
import json
import sys

import pytest

from engram import capture, llm, recsum, relink, summarize

FAKE = """#!{python}
import json, os, sys, time
stdin = sys.stdin.read()
open(os.environ["FAKE_LOG"], "a").write(json.dumps({{"argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd(),
                                                    "listing": os.listdir("."), "env": dict(os.environ)}}) + "\\n")
mode = os.environ["FAKE_MODE"]
if mode == "ok":
    print(json.dumps({{"result": ' Filed: {{"facts": []}}\\n', "total_cost_usd": 0.5,
                      "usage": {{"input_tokens": 1, "cache_read_input_tokens": 2, "output_tokens": 3}}}}))
elif mode == "is_error":
    print(json.dumps({{"is_error": True, "result": "something went wrong"}}))
elif mode == "limit":
    print(json.dumps({{"is_error": True, "result": "You've hit your usage limit"}})); sys.exit(1)
elif mode == "empty":
    sys.stderr.write("boom\\n"); sys.exit(2)
elif mode == "nonjson":
    print("not json")
elif mode == "timeout":
    time.sleep(5)
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "claude").write_text(FAKE.format(python=sys.executable))
    (bin_ / "claude").chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PATH", f"{bin_}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("CLAUDE_EFFORT", "max")  # a session's own: never passed on
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")

    def calls(mode: str = "ok"):
        monkeypatch.setenv("FAKE_MODE", mode)
        return lambda: [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return calls


@pytest.mark.parametrize("mode,said", [("is_error", "something went wrong"), ("limit", "You've hit your usage limit"),
                                       ("empty", "boom"), ("nonjson", "not json"), ("timeout", "timed out")])
def test_a_failed_call_is_unavailable_with_what_it_said(fake, mode, said):
    fake(mode)
    with pytest.raises(llm.Unavailable, match=said) as e:
        llm.ask("p", "s", model="m", effort="low", timeout=1)
    assert isinstance(e.value, RuntimeError)


RECSUM_ASK = recsum._ask  # the real one: conftest swaps it out so no other test calls a model
BASE = ["-p", "--model", "claude-opus-5-5", "--effort", "{effort}", "--output-format", "json", "--setting-sources", "project",
        "--strict-mcp-config", "--no-session-persistence", "--tools", ""]
SITES = [  # each call site, the system prompt and effort it sends, and what it returns for the fake's reply
    (lambda: capture._ask("P"), "You file what a person said into their record, carefully and literally.", "low",
     (' Filed: {"facts": []}\n', 0.5)),
    (lambda: capture._ask_structure("P"), "You file what a person said into their record, carefully and literally.", "medium",
     (' Filed: {"facts": []}\n', 0.5)),
    (lambda: relink._asker("")("P"), "", "low", (' Filed: {"facts": []}\n', 0.5)),  # a pack with no relink_system words
    (lambda: relink._ask("P", "pack words", "medium"), "pack words", "medium", (' Filed: {"facts": []}\n', 0.5)),
    (lambda: RECSUM_ASK("P"), recsum.SYSTEM, "low", (' Filed: {"facts": []}\n', {"in": 3, "out": 3, "usd": 0.5})),
    (lambda: summarize._claude("P", summarize.SEGMENT_MODEL), summarize.SYSTEM, "low",
     ('Filed: {"facts": []}', {"in": 3, "out": 3, "usd": 0.5})),
    (lambda: llm.ask_json("P"), llm.SYSTEM, "low", ({"facts": []}, {"usd": 0.5})),
]


@pytest.mark.parametrize("call,system,effort,returned", SITES)
def test_each_call_site_sends_its_own_words_from_an_empty_folder(fake, call, system, effort, returned):
    calls = fake("ok")
    assert call() == returned
    [c] = calls()
    assert c["argv"] == [x.format(effort=effort) for x in BASE] + ["--system-prompt", system]
    assert c["stdin"] == "P" and c["listing"] == [] and "engram-llm-" in c["cwd"]
    assert "CLAUDE_EFFORT" not in c["env"] and "CLAUDE_CODE_SESSION_ID" not in c["env"] and c["env"]["FAKE_MODE"] == "ok"


def test_no_system_prompt_sends_no_flag(fake):
    calls = fake("ok")
    llm.ask("P", model="m", effort="low")
    assert "--system-prompt" not in calls()[0]["argv"]
