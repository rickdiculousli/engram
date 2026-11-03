import json
import subprocess
from datetime import timedelta

import pytest

from conftest import git, make_repo
from engram import capture, llm, review
from test_capture import LATER, TOML, fake, reply, said, turn, world  # noqa: F401

TS = "2026-10-18T20:00:00Z"
DRAFT = review._draft  # the real one; the fixture fakes it


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
    tmp = world["tmp"]
    (world["repo"] / ".engram/engram.toml").write_text(TOML + "[review]\non = true\n")
    origin = tmp / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    rel = make_repo(tmp / "release", {"src/x.py": "x = 1\n"}, origin=str(origin))
    git(rel, "push", "-q", "origin", "main")
    cfg = tmp / "config.toml"
    cfg.write_text(cfg.read_text() + f'[review]\nrelease = "{rel}"\nremote = "{origin}"\n')
    replies, prompts, surfaced, ok = [], [], {"fixed": True}, {"tests": True}
    monkeypatch.setattr(review, "held", lambda d, q, day: "held that day: events/b.md")
    monkeypatch.setattr(review, "_ask", lambda text: (prompts.append(text), ({"findings": replies.pop(0) if replies else []}, 0.25))[1])

    def draft(text, cwd):
        (cwd / "src/x.py").write_text("x = 2\n")
        return "search weighs a title match higher", 0.5

    def check_tests(base, fixed, domain, work):
        return ok["tests"], "tests pass" if ok["tests"] else "tests fail"
    monkeypatch.setattr(review, "_draft", draft)
    monkeypatch.setattr(review, "replay", lambda code, calls, root, day, data: " ".join(f"events/{c}.md" for c in "abcdefghij") if surfaced.get(code.name) else "")
    monkeypatch.setattr(review, "CHECKS", [check_tests])
    monkeypatch.setattr(review.refine, "copy_data", lambda to: None)
    return {**world, "origin": origin, "release": rel, "replies": replies, "prompts": prompts, "surfaced": surfaced, "ok": ok,
            "s2": session(world["path"].parent.parent, "s2")}


def run_review(rv, *found, path=None):
    rv["replies"].append(list(found))
    return review.review(path or rv["s2"], "medical", rv["repo"], "asked")


def branches(repo):
    return git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()


def states():
    with review.db() as c:
        return [s for (s,) in c.execute("SELECT state FROM finding ORDER BY id")]


def test_switch_off_leaves_the_hourly_job_as_it_was(world, monkeypatch):
    monkeypatch.setattr(review, "hourly", lambda *a, **k: pytest.fail("reviewed with the switch off"))
    out = capture.run(ask=fake([], []), summaries=False, now=LATER)
    assert out["sessions"] == 1 and out["error"] is None
    assert not (world["tmp"] / "data/review").exists()
    assert "Open your first reply" not in capture.session_start(world["payload"])


def test_the_hourly_job_reviews_an_idle_session_once_a_day(rv):
    capture.run(ask=fake([], []), summaries=False, now=LATER)
    assert len(rv["prompts"]) == 1 and "c1: engram search knee --domain medical" in rv["prompts"][0]
    assert "held that day: events/b.md" in rv["prompts"][0] and "Your knee is better." in rv["prompts"][0]
    idle = [rv["path"], rv["s2"]]
    assert review.hourly("medical", rv["repo"], idle, LATER) is None  # one a day per repo
    assert review.hourly("medical", rv["repo"], idle, LATER + timedelta(days=1)) is not None
    assert len(rv["prompts"]) == 2  # the next day, the session not yet reviewed


def test_the_reviews_own_runs_are_never_captured_or_reviewed(rv, monkeypatch):
    own = session(rv["path"].parent.parent, "own", first=f"{review.MARK}. Below is one session")
    assert review.review(own, "medical", rv["repo"], "auto")["skipped"] and not rv["prompts"]
    seen = []

    def run(cmd, **kw):
        seen.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": '{"findings": [], "summary": ""}', "total_cost_usd": 0.1}), "")
    monkeypatch.setattr(subprocess, "run", run)
    llm.ask_json("x", cache=None)
    DRAFT("x", rv["tmp"] / "release")
    for cmd, kw in seen:  # no session file is kept, the env is clean, and nothing runs in his repo
        assert "--no-session-persistence" in cmd and not any(k.startswith("CLAUDE_CODE_") for k in kw["env"])
        assert str(rv["repo"]) not in str(kw["cwd"])
    assert "Bash" not in seen[1][0][seen[1][0].index("--tools") + 1]


def test_each_cause_goes_where_it_belongs(rv):
    r = run_review(rv, finding("advisor", "events/a.md"), finding("unrecorded", "x1", rule=True), finding("unrecorded", "x2"),
                   finding("unrecorded", "x3", ask="Should the record keep knee braces by brand? I'd say yes."), finding("tools"))
    assert [f["route"] for f in r["findings"]] == ["proposed", "proposed", "lead", "asked", "proposed"]
    rows = [json.loads(l) for l in (review.state_dir() / "proposals-medical.jsonl").read_text().splitlines()]
    assert [x["kind"] for x in rows] == ["instructions", "filing rule"]
    assert review.leads("medical") == ["a note on the knee (ref x2)"] and review.leads("medical") == []
    assert review.opening("medical").startswith("Should the record") and review.opening("medical").startswith("Should")
    assert r["usd"] == 0.75 and "routed 1 asked, 1 lead, 3 proposed" in review.summary(r)
    assert branches(rv["origin"]) == ["main", "review/fix-5"]


def test_a_fix_that_passes_lands_as_a_proposal_with_its_entry(rv):
    run_review(rv, finding("tools"))
    log = git(rv["origin"], "log", "-1", "--format=%B", "review/fix-1")
    assert "medical, finding 1" in log
    assert "found it 1 of 1 (before: 0); tests pass." in log and "search weighs a title match higher" in log
    assert git(rv["origin"], "show", "review/fix-1:src/x.py") == "x = 2\n"
    assert git(rv["origin"], "rev-parse", "main") == git(rv["release"], "rev-parse", "HEAD")  # main and the release untouched
    assert review.opening("medical") is None  # Sam hears of it once the lead has merged and released it
    assert review.landed(1) and review.opening("medical").startswith("Engram found a record") and review.opening("medical") is None
    assert "Open your first reply to Sam" not in capture.session_start(rv["payload"])


def test_auto_merges_and_advances_the_release_tag(rv):
    (rv["repo"] / ".engram/engram.toml").write_text(TOML + '[review]\non = true\nlanding = "auto"\n')
    run_review(rv, finding("tools"))
    assert states() == ["released"]
    tag = git(rv["origin"], "tag").strip()
    assert tag.startswith("release-") and git(rv["release"], "describe", "--tags").strip() == tag
    assert git(rv["origin"], "show", "main:src/x.py") == "x = 2\n"
    assert "Open your first reply to Sam with this one line: Engram found" in capture.session_start(rv["payload"])


def test_a_failing_fix_is_dropped_and_two_in_a_row_stop_until_cleared(rv):
    rv["surfaced"].clear()
    run_review(rv, finding("tools", "events/b.md"))
    rv["surfaced"]["fixed"], rv["ok"]["tests"] = True, False
    run_review(rv, finding("tools", "events/c.md"), finding("tools", "events/d.md"))
    assert states() == ["open: dropped, the replay still misses it", "open: dropped, tests fail",
                        "waiting: stopped (2 fixes dropped in a row)"]
    assert branches(rv["origin"]) == ["main"]
    assert review.clear_stop() == 1 and review.stopped() is None


def test_one_attempt_per_cause_and_two_landed_fixes_a_week(rv, monkeypatch):
    monkeypatch.setitem(review.LIMITS, "fixes_a_review", 9)
    run_review(rv, finding("tools", "events/b.md"), finding("tools", "events/b.md"), finding("tools", "events/c.md"),
               finding("tools", "events/d.md"))
    assert states() == ["proposed", "tried", "proposed", "waiting: two fixes landed this week"]


def test_the_held_out_set_every_third_landing_and_a_drop_stops(rv, monkeypatch):
    monkeypatch.setitem(review.LIMITS, "fixes_a_week", 9)
    monkeypatch.setitem(review.LIMITS, "fixes_a_review", 9)
    run_review(rv, *(finding("tools", f"events/{n}.md") for n in "bcd"))
    assert review.stopped() == "no held-out script set"
    review.clear_stop()
    cfg = rv["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text() + 'heldout = ["true"]\n')
    held = iter([{"held": 11, "tokens": 400}, {"held": 10, "tokens": 400}])
    monkeypatch.setattr(review, "measure", lambda cmd, code: next(held))
    run_review(rv, *(finding("tools", f"events/{n}.md") for n in "efgh"))
    assert review.stopped() is None  # the first run is the baseline
    run_review(rv, *(finding("tools", f"events/{n}.md") for n in "ij"))
    assert review.stopped() == "the held-out set dropped"
    run_review(rv, finding("tools", "events/a.md"))
    assert states()[-1] == "waiting: stopped (the held-out set dropped)"


def test_reading_calls_findings_and_measures():
    assert review.engram_args('cd x && uv run engram search "knee" --as-of 2026-10-01 | head') == ["search", "knee", "--as-of", "2026-10-01"]
    assert review.engram_args("engram capture run") is None and review.engram_args("grep engram x") is None
    assert [f["cause"] for f in review.parse({"findings": [finding("tools"), finding("bogus"), {"question": "data"}]})] == ["tools"]
    assert review.worse({"a": {"held": 5, "tokens": 10}}, {"a": {"held": 5, "tokens": 12}}) == ["a.tokens"]
    assert review.worse({"held": 5, "rate": 0.5}, {"held": 6, "rate": 0.5}) == []


def test_a_review_drafts_at_most_two_fixes(rv):
    r = run_review(rv, finding("tools", "events/a.md"), finding("tools", "events/b.md"), finding("tools", "events/c.md"))
    assert [f.get("drafted", False) for f in r["findings"]] == [True, True, False]
    assert r["findings"][2]["route"] == "waiting: the review's fixes are drafted"


def test_a_record_engram_already_surfaces_goes_to_the_advisors_instructions(rv):
    rv["surfaced"]["base"] = True
    r = run_review(rv, finding("tools"))
    assert r["findings"][0]["route"] == "proposed: engram already surfaces it" and not r["findings"][0].get("drafted")
    rows = [json.loads(l) for l in (review.state_dir() / "proposals-medical.jsonl").read_text().splitlines()]
    assert rows[-1]["kind"] == "instructions" and "already surfaces it" in rows[-1]["why"]
    assert branches(rv["origin"]) == ["main"] and r["usd"] == 0.25


def test_a_call_drops_shell_redirections_and_a_loop_variable_cant_be_replayed():
    assert review.engram_args('engram timeline "back spasm" 2>&1 | head') == ["timeline", "back spasm"]
    assert review.engram_args("engram search knee >/dev/null") == ["search", "knee"]
    assert review.engram_args("for i in a b; do engram show $i 2>&1; done") is None


def test_a_gate_with_no_baseline_is_an_error_the_hourly_job_catches(rv):
    cfg = rv["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text().replace("[review]\n", '[review]\ngate = "notes"\n'))
    with pytest.raises(Exception, match="no gate_base") as e:
        review.gate()
    assert not isinstance(e.value, SystemExit)
