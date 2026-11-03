import json
import subprocess
from datetime import timedelta

import pytest

from conftest import make_repo
from engram import capture, llm, refine, review
from test_capture import LATER, TOML, fake, reply, said, turn, world  # noqa: F401

TS = "2026-10-18T20:00:00Z"


def session(root, stem, first="how is my knee?"):
    p = root / "-Users-x-repos-health-notes" / f"{stem}.jsonl"
    call = {"type": "assistant", "timestamp": TS, "cwd": "/x", "message": {"role": "assistant", "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "name": "Bash", "input": {"command": 'engram search "knee" --domain medical | head'}}]}}
    p.write_text("\n".join([said(first), json.dumps(call), turn("user", [{"type": "tool_result", "content": "1. drops\n   ref: events/a.md"}]),
                            reply("Your knee is better.")]) + "\n")
    return p


def finding(cause, ref="events/b.md", **kw):
    return {"question": "data", "cause": cause, "ref": ref, "call": "c1", "what": "a note on the knee", **kw}


@pytest.fixture
def rv(world, monkeypatch):
    (world["repo"] / ".engram/engram.toml").write_text(TOML + "[review]\non = true\n")
    replies, prompts = [], []
    monkeypatch.setattr(review, "held", lambda d, q, day: "held that day: events/b.md")
    monkeypatch.setattr(review, "_ask", lambda text: (prompts.append(text), ({"findings": replies.pop(0) if replies else []}, 0.25))[1])
    return {**world, "replies": replies, "prompts": prompts, "s2": session(world["path"].parent.parent, "s2")}


def run_review(rv, *found):
    rv["replies"].append(list(found))
    return review.review(rv["s2"], "medical", "asked")


def test_switch_off_leaves_the_hourly_job_as_it_was(world, monkeypatch):
    monkeypatch.setattr(review, "hourly", lambda *a, **k: pytest.fail("reviewed with the switch off"))
    out = capture.run(ask=fake([], []), summaries=False, now=LATER)
    assert out["sessions"] == 1 and out["error"] is None
    assert not (world["tmp"] / "data/review").exists()


def test_the_hourly_job_reviews_an_idle_session_once_a_day(rv):
    rv["replies"].append([finding("tools")])
    capture.run(ask=fake([], []), summaries=False, now=LATER)
    assert len(rv["prompts"]) == 1 and "c1: engram search knee --domain medical" in rv["prompts"][0]
    assert "held that day: events/b.md" in rv["prompts"][0] and "Your knee is better." in rv["prompts"][0]
    idle = [rv["path"], rv["s2"]]
    assert review.hourly("medical", rv["repo"], idle, LATER) is None  # one a day per repo
    assert review.hourly("medical", rv["repo"], idle, LATER + timedelta(days=1)) is not None
    assert len(rv["prompts"]) == 2  # the next day, the session not yet reviewed
    assert "review" not in capture.session_start(rv["payload"])  # its news never comes at session start


def test_the_reviews_own_runs_are_never_captured_or_reviewed(rv, monkeypatch):
    own = session(rv["path"].parent.parent, "own", first=f"{review.MARK}. Below is one session")
    assert review.review(own, "medical", "auto")["skipped"] and not rv["prompts"]
    seen = []

    def run(cmd, **kw):
        seen.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": '{"findings": []}', "total_cost_usd": 0.1}), "")
    monkeypatch.setattr(subprocess, "run", run)
    llm.ask_json("x", cache=None)
    cmd, kw = seen[0]  # no session file is kept, the env is clean, and nothing runs in his repo
    assert "--no-session-persistence" in cmd and not any(k.startswith("CLAUDE_CODE_") for k in kw["env"])
    assert str(rv["repo"]) not in str(kw.get("cwd"))


def test_every_finding_is_recorded_with_its_cause_and_the_call_written_out(rv):
    r = run_review(rv, finding("advisor", "events/a.md"), finding("unrecorded", "x1"), finding("tools"))
    with review.db() as c:
        rows = c.execute("SELECT session, day, cause, ref, call FROM finding ORDER BY id").fetchall()
    assert rows == [("s2", "2026-10-18", "advisor", "events/a.md", "engram search knee --domain medical"),
                    ("s2", "2026-10-18", "unrecorded", "x1", "engram search knee --domain medical"),
                    ("s2", "2026-10-18", "tools", "events/b.md", "engram search knee --domain medical")]
    assert review.summary(r) == "engram review: 3 findings; by question 3 data; by cause 1 advisor, 1 tools, 1 unrecorded; $0.25"
    assert not list(review.state_dir().glob("*.jsonl"))  # no proposals, asks or leads: the weekly pass reads the record


def test_a_tools_finding_reaches_the_pass_on_engrams_own_repo(rv, monkeypatch):
    own = make_repo(rv["tmp"] / "engram", {".engram/README.md": "## Jobs\n"})
    cfg = rv["tmp"] / "config.toml"
    cfg.write_text(f'[refine]\nrepo = "{own}"\n' + cfg.read_text())
    run_review(rv, finding("advisor", "events/a.md", what="the advisor left out the brace"), finding("tools"))
    monkeypatch.setenv("ENGRAM_DATA", refine.fenced("engram", own, refine.week())["ENGRAM_DATA"])  # the pass's copy
    out = refine.conversations(own).splitlines()
    assert out[-2].startswith("# 1 value review findings on engram's tools since ")
    assert out[-1] == "- 2026-10-18 medical, the right data: a note on the knee (ref events/b.md; engram search knee --domain medical)"
    assert "value review" not in refine.conversations(rv["repo"])  # a record repo's pass reads its conversations only


def test_reading_calls_and_findings():
    assert review.engram_args('cd x && uv run engram search "knee" --as-of 2026-10-01 | head') == ["search", "knee", "--as-of", "2026-10-01"]
    assert review.engram_args("engram capture run") is None and review.engram_args("grep engram x") is None
    assert review.engram_args('engram timeline "back spasm" 2>&1 | head') == ["timeline", "back spasm"]
    assert [f["cause"] for f in review.parse({"findings": [finding("tools"), finding("bogus"), {"question": "data"}]})] == ["tools"]


def test_a_gate_with_no_baseline_is_an_error_the_release_reports(world):
    cfg = world["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text() + '[review]\ngate = "notes"\n')
    with pytest.raises(Exception, match="no gate_base") as e:
        review.gate()
    assert not isinstance(e.value, SystemExit)
