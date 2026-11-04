import json
import os
import plistlib
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import PAGE_MD, REWIRE, git, make_repo
from engram import capture, config, hourly, pack, rewire, setup, store

TOML = """[domain]
name = "medical"
events_dir = "events"
[about]
prefixes = ["series", "story"]
""" + REWIRE


def turn(kind, content, ts="2026-10-18T20:00:00Z", meta=False):
    e = {"type": kind, "timestamp": ts, "cwd": "/x", "message": {"role": kind, "content": content}}
    if meta:
        e["isMeta"] = True
    return json.dumps(e)


def said(text, ts="2026-10-18T20:00:00Z"):
    return turn("user", text, ts)


def reply(text, ts="2026-10-18T20:00:00Z"):
    return turn("assistant", [{"type": "text", "text": text}], ts)


@pytest.fixture
def world(env, monkeypatch):
    tmp = env["tmp"]
    repo = make_repo(tmp / "repos/health_notes", {".engram/engram.toml": TOML, ".engram/README.md": PAGE_MD, ".claude/settings.json": '{\n    "hooks": {}\n}\n'})
    env["set_repo"]("medical", repo)
    st = store.Store(repo)
    with st.transaction() as tx:
        tx.add({"title": "old", "date": "2026-01-01", "kind": "observation", "about": ["series/_observations", "story/ankle"]}, "- old\n")
    root = tmp / "projects"
    monkeypatch.setattr("engram.sources.sessions.ROOT", root)
    path = root / "-Users-x-repos-health-notes" / "s1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join([
        said("how is my knee?"),
        reply("Did you take 10mg of the tablets yesterday?"),
        said("yes"),
        turn("user", "<task-notification>done</task-notification>"),
        turn("user", "Base directory for this skill: ...", meta=True),
        reply("Noted."),
        said("I started Orvexa, 1 tablet 40 mg, on 2026-10-15 and the ache is better"),
        reply("Good."),
    ]) + "\n")
    setup.setup(repo, tmp / "LaunchAgents", load=False)
    return {"repo": repo, "path": path, "tmp": tmp, "payload": {"cwd": str(repo), "session_id": "s1"}}


LATER = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)  # two hours after the session's last message


def fake(facts, calls, verified=None, judge=None):
    def ask(prompt):
        if prompt.startswith(config.voice(pack.load("medical").prompts["verify"])[:40]):  # the repeat check: kept apart, so call counts stay the extractions
            if verified is not None:
                verified.append(prompt)
            return json.dumps({"repeats": judge(prompt) if judge else []}), 0.01
        calls.append(prompt)
        return json.dumps({"facts": facts}), 0.02
    return ask


def run(calls, facts=(), now=LATER, **kw):
    return hourly.run(ask=fake(list(facts), calls), summaries=False, now=now, **kw)


def test_sams_messages_include_short_replies_and_skip_injected_text(world):
    got = capture.owners(capture._parse(world["path"]))
    assert list(got.values()) == ["how is my knee?", "yes", "I started Orvexa, 1 tablet 40 mg, on 2026-10-15 and the ache is better"]


def test_files_checked_facts_from_the_whole_session(world):
    calls = []
    facts = [
        {"line": 7, "text": "Sam started Orvexa, 1 tablet 40 mg, on 2026-10-15.", "quote": "I started Orvexa, 1 tablet 40 mg, on 2026-10-15",
         "date": "2026-10-15", "kind": "observation", "about": ["story/ankle"]},
        {"line": 3, "text": "Sam took 10mg of the tablets.", "quote": "yes", "answering": "Did you take 10mg of the tablets yesterday?",
         "date": "2026-10-17", "kind": "observation", "about": ["series/_observations"]},
        {"line": 3, "text": "Sam took 20mg.", "quote": "yes", "answering": "Did you take 20mg?", "date": "not-sure"},
        {"line": 7, "text": "Sam's ache is gone.", "quote": "the ache is gone", "date": "not-sure"},
        {"line": 7, "text": "Sam took 30 mg.", "quote": "I started Orvexa", "date": "not-sure"},
        {"line": 2, "text": "Sam asked about his knee.", "quote": "Did you take", "date": "not-sure"},
    ]
    out = run(calls, facts)
    assert len(calls) == 1 and out["filed"] == 2
    assert "Did you take 10mg" in calls[0] and "<task-notification>" not in calls[0]  # Claude's words go too, injected text doesn't
    assert sorted(d["why"] for d in out["dropped"]) == ["not one of Sam's new messages", "number 30 not in the record",
                                                       "question not in Claude's words", "quote not in Sam's words"]
    new = [e for e in store.Store(world["repo"]).events() if e.fm.get("author") == "engram-capture"]
    assert {e.fm["by"] for e in new} == {"sam"} and all(e.about[0].startswith("series/") for e in new)
    assert "Sam, answering “Did you take 10mg of the tablets yesterday?”: “yes”" in next(e for e in new if "10mg" in e.body).body
    assert git(world["repo"], "status", "--porcelain", "--", "events", "logs").strip() == ""  # committed
    assert run(calls)["sessions"] == 0 and len(calls) == 1  # filed and unchanged: not read again
    assert any("1 sessions filed" in l or "sessions filed: 1" in l for l in setup.status(world["repo"]))


def test_an_active_session_is_skipped_and_read_once_idle(world):
    calls = []
    assert run(calls, now=LATER - timedelta(minutes=110))["sessions"] == 0 and not calls  # last message 10 minutes ago
    assert run(calls)["sessions"] == 1


def test_a_returning_session_files_only_past_its_mark(world):
    calls = []
    run(calls)
    with world["path"].open("a") as f:
        f.write(reply("Anything else?") + "\n" + said("the tablets make me sleepy today", ts="2026-10-19T09:00:00Z") + "\n")
    assert run(calls)["sessions"] == 0  # the new message is from the future: still going
    old = {"line": 7, "text": "Sam started Orvexa.", "quote": "I started Orvexa", "date": "2026-10-15"}
    new = {"line": 10, "text": "The tablets make me sleepy.", "quote": "the tablets make me sleepy today", "date": "2026-10-19"}
    out = run(calls, [old, new], now=LATER + timedelta(days=1))
    assert len(calls) == 2 and "after line 7" in calls[1] and "Good." in calls[1]  # whole session, read past line 7
    assert out["filed"] == 1 and out["dropped"][0]["why"] == "not one of Sam's new messages"


def test_dry_run_files_nothing_and_keeps_the_mark(world):
    facts = [{"line": 7, "text": "Sam's ache is better.", "quote": "the ache is better", "date": "not-sure"}]
    out = run([], facts, dry_run=True)
    assert len(out["would_file"]) == 1
    assert not [e for e in store.Store(world["repo"]).events() if e.fm.get("author") == "engram-capture"]
    assert run([], facts)["filed"] == 1


def clock(monkeypatch, step):
    """The store's clock, moving `step` seconds at each reading: 0 is two writes in one second, 1 each in its own."""
    class Clock(datetime):
        at = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            cls.at += timedelta(seconds=step)
            return cls.at
    monkeypatch.setattr("engram.store.datetime", Clock)


@pytest.mark.parametrize("step", [0, 1])
def test_the_same_fact_twice_is_filed_once(world, monkeypatch, step):
    clock(monkeypatch, step)
    fact = {"line": 7, "text": "Sam's ache is better.", "quote": "the ache is better", "date": "not-sure"}
    assert len(run([], [fact, dict(fact)], dry_run=True)["would_file"]) == 1
    out = run([], [fact, dict(fact)])
    assert out["filed"] == 1 and not out["dropped"]
    assert len([e for e in store.Store(world["repo"]).events() if e.fm.get("author") == "engram-capture"]) == 1


def test_setup_teardown_round_trip_and_self_repair(world, monkeypatch):
    repo, agents = world["repo"], world["tmp"] / "LaunchAgents"
    ticks = iter(range(60))  # a clock that moves on every read: one run's repairs still show together
    monkeypatch.setattr(setup, "_now", lambda: f"2026-10-29T04:00:{next(ticks):02d}-07:00")
    before = b'{\n    "hooks": {}\n}\n'
    setup.setup(repo, agents, load=False)  # again: idempotent
    conf = json.loads((repo / ".claude/settings.json").read_text())
    assert conf == {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": setup._hook_cmd("capture check")}]}]},
                    "permissions": {"allow": [setup.ALLOW]}, "bashOutputMaxChars": setup.BASH_BUDGET}
    assert git(repo, "config", "core.hooksPath").strip() == ".engram/hooks"
    assert "lint --staged" in (repo / ".engram/hooks/pre-commit").read_text()
    plist = agents / f"{setup.LABEL}.plist"
    assert plistlib.loads(plist.read_bytes())["ProgramArguments"][-2:] == ["capture", "run"]
    assert setup.missing(repo, json.loads(capture.db().execute("SELECT setup FROM repo").fetchone()[0])) == {}

    plist.unlink()
    conf["hooks"].pop("SessionStart")
    (repo / ".claude/settings.json").write_text(json.dumps(conf))
    git(repo, "config", "--unset", "core.hooksPath")
    assert hourly.session_start(world["payload"]) == hourly.READ_WHOLE  # repaired, so nothing more to say
    assert plist.exists() and "SessionStart" in json.loads((repo / ".claude/settings.json").read_text())["hooks"]
    assert git(repo, "config", "core.hooksPath").strip() == ".engram/hooks"
    assert sum("— fixed" in l for l in setup.status(repo)) == 3

    setup.teardown(repo)
    assert (repo / ".claude/settings.json").read_bytes() == before
    assert not plist.exists() and not (repo / ".engram/hooks").exists()
    assert setup._git(repo, "config", "--get", "core.hooksPath").stdout.strip() == ""


def test_an_install_from_before_the_window_gets_it_at_its_next_repair_and_loses_it_at_teardown(world):
    repo, sp = world["repo"], world["repo"] / ".claude/settings.json"
    conf = json.loads(sp.read_text())
    conf.pop("bashOutputMaxChars")
    sp.write_text(json.dumps(conf, indent=2) + "\n")
    with capture.db() as c:  # its manifest has no word of the window
        man = json.loads(c.execute("SELECT setup FROM repo").fetchone()[0])
        man.pop("added_window")
        c.execute("UPDATE repo SET setup = ?", (json.dumps(man),))
    assert setup.missing(repo, man) == {"settings": "Claude's Bash window isn't widened"}
    assert hourly.session_start(world["payload"]) == hourly.READ_WHOLE
    assert json.loads(sp.read_text())["bashOutputMaxChars"] == setup.BASH_BUDGET
    setup.teardown(repo)
    assert sp.read_bytes() == b'{\n    "hooks": {}\n}\n'


def test_a_repos_own_bash_window_is_kept_and_left_at_teardown(world):
    repo, sp = world["repo"], world["repo"] / ".claude/settings.json"
    setup.teardown(repo)
    mine = '{\n  "bashOutputMaxChars": 20000\n}\n'
    sp.write_text(mine)
    setup.setup(repo, world["tmp"] / "LaunchAgents", load=False)
    man = json.loads(capture.db().execute("SELECT setup FROM repo").fetchone()[0])
    assert json.loads(sp.read_text())["bashOutputMaxChars"] == 20000 and not man["added_window"]
    assert setup.missing(repo, man) == {}  # in place at its own value: not rewritten every hour
    assert hourly.READ_WHOLE not in hourly.session_start(world["payload"])  # too narrow to hold engram's output whole
    setup.teardown(repo)
    assert sp.read_text() == mine


@pytest.fixture
def loaded(world, monkeypatch):
    """The world's install as the box's real one: its manifest loaded, launchctl stubbed (the label is the real one,
    so a guard bug must never reach the box's own job), and every piece broken, for a repair to find."""
    repo, ran = world["repo"], []
    monkeypatch.setattr("engram.jobs._run", lambda *a: ran.append(a) or subprocess.CompletedProcess(a, 0, "", ""))
    with capture.db() as c:
        man = json.loads(c.execute("SELECT setup FROM repo").fetchone()[0]) | {"load": True}
        c.execute("UPDATE repo SET setup = ?", (json.dumps(man),))
        c.execute(setup.REPAIR)
    plist = world["tmp"] / "LaunchAgents" / f"{setup.LABEL}.plist"
    plist.unlink()
    sp = repo / ".claude/settings.json"
    sp.write_text('{\n    "hooks": {}\n}\n')
    git(repo, "config", "--unset", "core.hooksPath")
    untouched = lambda: (not plist.exists() and sp.read_text() == '{\n    "hooks": {}\n}\n'
                         and not setup._git(repo, "config", "core.hooksPath").stdout.strip()
                         and not [a for a in ran if a[1] in ("bootout", "bootstrap")]
                         and not capture.db().execute("SELECT count(*) FROM repair").fetchone()[0])
    return {"ran": ran, "plist": plist, "untouched": untouched}


def test_a_scratch_data_folder_leaves_the_real_install_alone(world, loaded, monkeypatch):
    import shutil
    real, scratch = world["tmp"] / "real", world["tmp"] / "data"
    real.mkdir()
    shutil.copy(scratch / "capture.sqlite", real / "capture.sqlite")  # the scratch copy holds the real rows
    monkeypatch.setattr("engram.paths.default_data_dir", lambda: real)
    monkeypatch.setattr("engram.review.release", lambda: world["tmp"] / "no-release")  # the release rule off
    assert setup.repair("medical") == [] and loaded["untouched"]()
    with pytest.raises(SystemExit, match="scratch data folder"):
        setup.setup(world["repo"], world["tmp"] / "LaunchAgents", load=True)
    assert loaded["untouched"]()
    (world["tmp"] / "sub").mkdir()
    monkeypatch.setenv("ENGRAM_DATA", str(world["tmp"] / "sub/../real"))  # the default, named another way
    shutil.copy(scratch / "capture.sqlite", real / "capture.sqlite")
    assert len([d for d in setup.repair("medical") if d["ok"]]) == 3 and loaded["plist"].exists()


def test_only_the_release_repairs_a_loaded_install(world, loaded, monkeypatch):
    rel = world["tmp"] / "data/release"
    rel.mkdir()  # the scratch rule off: the test's data folder is the box's own
    monkeypatch.setattr("engram.paths.default_data_dir", lambda: world["tmp"] / "data")
    assert setup.repair("medical") == [] and loaded["untouched"]()
    with pytest.raises(SystemExit, match="not the release clone"):
        setup.setup(world["repo"], world["tmp"] / "LaunchAgents", load=True)
    assert hourly.session_start(world["payload"]) == "" and loaded["untouched"]()
    monkeypatch.setattr("engram.review.release", lambda: Path(setup.this_code()).parents[1])  # running from the release
    assert len([d for d in setup.repair("medical") if d["ok"]]) == 3 and loaded["plist"].exists()
    assert [a[1] for a in loaded["ran"] if a[1] in ("bootout", "bootstrap")] == ["bootout", "bootstrap"]


def test_any_engram_repairs_a_loaded_install_with_no_release_clone(world, loaded, monkeypatch):
    monkeypatch.setattr("engram.paths.default_data_dir", lambda: world["tmp"] / "data")
    assert len([d for d in setup.repair("medical") if d["ok"]]) == 3 and loaded["plist"].exists()


def test_setup_refuses_a_repo_with_no_current_rewiring(world):
    repo = world["repo"]
    setup.teardown(repo)
    toml = repo / ".engram/engram.toml"
    toml.write_text(toml.read_text().replace(REWIRE, ""))
    git(repo, "commit", "-qam", "unrewired")
    with pytest.raises(SystemExit, match=r"no current rewiring, so it isn't set up: \.engram/engram\.toml has no \[rewire\]"):
        setup.setup(repo, world["tmp"] / "LaunchAgents", load=False)
    assert not (repo / ".engram/hooks/pre-commit").exists()


def test_the_pre_commit_refuses_drift_and_repair_rewrites_a_hook_without_the_check(world):
    repo = world["repo"]
    hook = repo / ".engram/hooks/pre-commit"
    assert re.search(r"(?m)^exec .+ rewire check --drift \"\$\(git rev-parse --show-toplevel\)\"$", hook.read_text())
    page = repo / ".engram/README.md"
    page.write_text(PAGE_MD + '2. **Remind me.** "remind me"\n')
    git(repo, "add", ".engram/README.md")
    r = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "jobs changed"], capture_output=True, text=True)
    assert r.returncode and "engram rewire: .engram/README.md's Jobs section changed since the last rewire" in r.stderr
    git(repo, "checkout", "-q", "HEAD", "--", ".engram/README.md")
    page.write_text(PAGE_MD + "\n## Decisions\n- **Keep it short.**\n")  # the rest of the page isn't the jobs
    git(repo, "add", ".engram/README.md")
    git(repo, "commit", "-qm", "a decision")
    man = json.loads(capture.db().execute("SELECT setup FROM repo").fetchone()[0])
    hook.write_text("\n".join(l for l in hook.read_text().splitlines() if "--drift" not in l) + "\n")  # an older engram's
    assert setup.missing(repo, man) == {"git": "the pre-commit hook is missing, lacks one of its checks or runs an old engram"}
    assert [d["what"] for d in setup.repair("medical") if d["ok"]] == [
        "git: the pre-commit hook is missing, lacks one of its checks or runs an old engram"]
    assert "rewire check --drift" in hook.read_text() and setup.missing(repo, man) == {}


def test_the_pre_commit_refuses_only_drift_the_commit_brings(world):
    repo = world["repo"]
    commit = lambda *a: subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x", *a], capture_output=True, text=True)
    (repo / ".engram/README.md").write_text(PAGE_MD + '2. **Remind me.** "remind me"\n')
    git(repo, "add", ".engram/README.md")
    assert commit("--no-verify").returncode == 0  # drift that reached HEAD past the hook, as a pull brings it
    (repo / "notes.md").write_text("# Notes\nunrelated\n")
    git(repo, "add", "notes.md")
    assert commit().returncode == 0
    with store.Store(repo).transaction() as tx:  # the filer's `git commit --only`
        tx.add({"title": "new", "date": "2026-10-20", "kind": "observation", "about": ["story/ankle"]}, "- new\n")
    assert [f for f in git(repo, "show", "--name-only", "--format=", "HEAD").split() if f.startswith("events/")]
    for rel in ("log", "frost", "beds"):  # one update written in three files, outside every home
        (repo / f"notes/{rel}.md").parent.mkdir(exist_ok=True)
        (repo / f"notes/{rel}.md").write_text("# x\n- 2026-10-12: the Brandywine split\n")
    for rel in ("peppers", "herbs", "compost"):
        (repo / f"notes/{rel}.md").write_text(f"# {rel}\nnothing named here\n")
    git(repo, "add", "notes")
    r = commit()
    assert r.returncode and r.stderr.strip() == ("engram rewire: 1 copies have no home in [rewire.homes]: Brandywine 10-12 in "
                                                 "notes/beds.md, notes/frost.md, notes/log.md")
    assert [d.split(":")[0] for d in rewire.drift(repo)] == [".engram/README.md's Jobs section changed since the last rewire",
                                                            "1 copies have no home in [rewire.homes]"]  # health shows both


def test_teardown_waits_for_a_filing_run_in_progress(world):
    import threading
    done = []
    with hourly.lock() as got:  # a run is filing
        assert got and hourly.run()["skipped"]  # a second run skips
        t = threading.Thread(target=lambda: done.append(setup.teardown(world["repo"])))
        t.start()
        t.join(0.3)
        assert not done and capture.db().execute("SELECT count(*) FROM repo").fetchone()[0] == 1
    t.join(5)
    assert done[0][0] == "waited for the filing run in progress" and "torn down" in done[0][1]
    assert capture.db().execute("SELECT count(*) FROM repo").fetchone()[0] == 0


def test_a_repos_own_pre_commit_keeps_running(world):
    repo = world["repo"]
    setup.teardown(repo)
    (repo / ".engram/hooks").mkdir(parents=True)
    (repo / ".engram/hooks/pre-commit").write_text("#!/bin/sh\necho mine\n")
    setup.setup(repo, world["tmp"] / "LA", load=False)
    assert "pre-commit.before-engram" in (repo / ".engram/hooks/pre-commit").read_text()
    setup.teardown(repo)
    assert (repo / ".engram/hooks/pre-commit").read_text() == "#!/bin/sh\necho mine\n"


def test_dates_from_the_day_he_said_it_and_numbers_from_his_words_and_the_question_he_answered():
    later = {5: "stopped Zentrafen, started Quillmar around then", 7: "my knee felt sore last night", 9: "took it 3 days ago",
             11: "it was the same as she said", 13: "ok, go with that", 15: "pain was 7/10 today"}
    turns = {11: "At the 09-17 visit she measured swelling 4 mm. Was it the same as before?",
             13: "Revenue was 135B, spreads near 1,600bp. Go with that?"}
    fact = lambda line, text, quote, asked="": {"line": line, "text": text, "quote": quote, "answering": asked}
    # the day of the message, and what "last night" or "3 days ago" count back from it
    assert capture.check(fact(5, "Sam stopped Zentrafen and started Quillmar on 2026-09-22.", "stopped Zentrafen, started Quillmar"),
                         later, {}, "2026-09-22") is None
    assert capture.check(fact(7, "Sam's knee felt sore on 2026-09-21.", "my knee felt sore last night"), later, {}, "2026-09-22") is None
    assert capture.check(fact(9, "Sam took it on 09-19.", "took it 3 days ago"), later, {}, "2026-09-22") is None
    assert capture.check(fact(7, "Sam's knee felt sore on 2026-09-15.", "my knee felt sore last night"), later, {}, "2026-09-22") \
        == "number 2026-09-15 not in the record"
    # a date or value in the question he answered
    asked = turns[11]
    assert capture.check(fact(11, "Sam says the 09-17 swelling of 4 mm matched what she said.", "it was the same as she said", asked),
                         later, turns, "2026-09-22") is None
    # any other value still has to be in his words
    assert capture.check(fact(11, "Sam's swelling was 6 mm.", "it was the same as she said", asked), later, turns, "2026-09-22") \
        == "number 6 not in the record"
    # Claude's analysis before his "ok" isn't the question he answered: its numbers aren't his
    assert capture.check(fact(13, "Sam puts spreads near 1,600bp.", "ok, go with that", "Go with that?"), later, turns, "2026-09-22") \
        == "number 1,600 not in the record"
    # a number counts only whole, never as a piece of a longer one; a fraction's parts count
    assert capture.check(fact(13, "Sam puts it at 35.", "ok, go with that", turns[13]), later, turns, "2026-09-22") \
        == "number 35 not in the record"
    assert capture.check(fact(13, "Sam says spreads near 60.", "ok, go with that", turns[13]), later, turns, "2026-09-22") \
        == "number 60 not in the record"
    assert capture.check(fact(15, "Sam's pain was 7 out of 10 on 2026-09-22.", "pain was 7/10 today"), later, {}, "2026-09-22") is None


def test_the_question_he_answered_is_in_claudes_turn_just_before_his_words(env):
    path = env["tmp"] / "projects" / "-Users-x-repos-notes" / "s.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join([
        said("how is my knee?"),
        turn("assistant", [{"type": "text", "text": "Did you take 10mg of the tablets?"},
                           {"type": "text", "text": "I'll check the notes either way."}]),
        said("yes"),
        reply("How many tablets a day?"),
        json.dumps({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "two"}}),
        reply("Thanks, noted."),
        turn("user", "Base directory for this skill: ...", meta=True),
        reply("Shall I log the swelling as 4 mm?"),
        said("sure"),
    ]) + "\n")
    s = capture._parse(path)
    later, turns = capture.owners(s), capture.turn_before(s)
    why = lambda line, quote, asked, text: capture.check({"line": line, "quote": quote, "answering": asked, "text": text},
                                                         later, turns, "2026-10-18")
    assert why(3, "yes", "Did you take 10mg of the tablets?", "Sam took 10mg of the tablets.") is None  # not the turn's last block
    assert why(3, "two", "How many tablets a day?", "Sam takes two tablets a day.") is None  # sent while Claude worked: same line
    assert why(9, "sure", "Shall I log the swelling as 4 mm?", "Sam's swelling was 4 mm.") is None  # asked after a skill's turn
    assert why(9, "sure", "Did you take 10mg of the tablets?", "Sam took 10mg.") == "question not in Claude's words"  # two turns back


THEORY_TOML = TOML + """[links.theory]
rels = ["feeds", "shared-cause", "amplifier"]
"""


def node(id_, kind, short):
    return f"---\nid: {id_}\nkind: {kind}\nshort: {short}\n---\n# {short}\n\nAbout {short}.\n"


@pytest.fixture
def graph(env, monkeypatch):
    """A record with a theory graph, and a session where Claude proposes things and Sam agrees to some."""
    tmp = env["tmp"]
    repo = make_repo(tmp / "repos/med", {".engram/engram.toml": THEORY_TOML, ".engram/README.md": PAGE_MD, "theory/node-A.md": node("node/A", "node", "stiffness"),
                                         "theory/node-B.md": node("node/B", "node", "knee"),
                                         "theory/loop-1.md": node("loop/1", "loop", "Loop 1"),
                                         "evidence/staging/P-01.md": "# P-01 Cold and the knee\n"})
    env["set_repo"]("medical", repo)
    st = store.Store(repo)
    with st.transaction() as tx:
        tx.add({"title": "old", "date": "2026-01-01", "kind": "observation", "about": ["series/_observations"]}, "- old\n")
        tx.add({"title": "P-01: proposed", "date": "2026-02-01", "kind": "status", "about": ["pattern/P-01"], "status": "proposed",
                "recorded": "2026-02-01T10:00:00-07:00"}, "")
    root = tmp / "projects"
    monkeypatch.setattr("engram.sources.sessions.ROOT", root)
    path = root / "-Users-x-repos-med" / "s2.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join([
        said("the cold days line up with the achy knee again"),
        reply("Should we mark P-01 as provisional now?"),
        said("yes, mark it provisional"),
        reply("I think the knee tension amplifies the stiffness."),
        said("ok"),
        reply("Maybe the cold pattern is confirmed, too."),
        said("I feel pretty hopeless about all of this, nothing ever gets better"),
        reply("That sounds hard."),
        said("I'm discouraged but my knee is stiff today"),
        reply("Noted."),
    ]) + "\n")
    setup.setup(repo, tmp / "LaunchAgents", load=False)
    return {"repo": repo}


def captured(repo, kind=None):
    return [e for e in store.Store(repo).events(kind=kind) if e.fm.get("author") == "engram-capture"]


def ask_theory(theory, facts=(), calls=None):
    def ask(prompt):
        if calls is not None:
            calls.append(prompt)
        return json.dumps({"facts": list(facts), "theory": theory}), 0.0
    return ask


def test_a_status_sam_agrees_to_is_filed_and_one_only_claude_proposed_is_not(graph):
    calls = []
    agreed = {"line": 3, "quote": "yes, mark it provisional", "answering": "Should we mark P-01 as provisional now?",
              "status": {"id": "pattern/P-01", "to": "provisional"}}
    claudes = {"line": 5, "quote": "Maybe the cold pattern is confirmed", "status": {"id": "pattern/P-01", "to": "confirmed"}}
    unknown = {"line": 3, "quote": "yes", "answering": "Should we mark P-01 as provisional now?",
               "status": {"id": "pattern/P-99", "to": "provisional"}}
    odd = {"line": 3, "quote": "yes", "status": {"id": "pattern/P-01", "to": "probably"}}
    out = hourly.run(ask=ask_theory([agreed, claudes, unknown, odd], calls=calls), summaries=False, now=LATER)
    assert "pattern/P-01\tpattern\tproposed" in calls[0] and "loop/1" in calls[0]  # real ids and statuses go to the model
    assert out["filed"] == 1
    assert sorted(d["why"] for d in out["dropped"]) == ["quote not in Sam's words", "unknown status probably",
                                                       "unknown theory id pattern/P-99"]
    [st] = captured(graph["repo"], "status")
    assert st.about == ["pattern/P-01"] and st.fm["status"] == "provisional" and st.fm["by"] == "sam"
    assert "agreeing to “Should we mark P-01 as provisional now?”" in st.body
    from engram import theory
    assert theory.load(graph["repo"]).status["pattern/P-01"][0] == "provisional"  # the latest status event wins


def test_a_link_sam_agrees_to_is_a_theory_link_in_links_jsonl(graph):
    link = {"from": "node/B", "to": "node/A", "rel": "amplifier", "mechanism": "knee tension raises the urge to rest",
            "strength": "medium"}
    ok = {"line": 5, "quote": "ok", "answering": "I think the knee tension amplifies the stiffness.", "link": link}
    bad_rel = {**ok, "link": {**link, "rel": "causes"}}
    bad_id = {**ok, "link": {**link, "to": "node/Z"}}
    out = hourly.run(ask=ask_theory([ok, bad_rel, bad_id]), summaries=False, now=LATER)
    assert out["filed"] == 1 and sorted(d["why"] for d in out["dropped"]) == ["unknown rel causes", "unknown theory id node/Z"]
    [e] = captured(graph["repo"], "link")
    assert e.path.startswith("events/links.jsonl:")
    assert git(graph["repo"], "status", "--porcelain", "--", "events").strip() == ""  # appended and committed through the store
    assert (e.fm["family"], e.fm["rel"], e.fm["from"], e.fm["to"], e.fm["strength"], e.fm["by"]) == \
        ("theory", "amplifier", "node/B", "node/A", "medium", "sam")
    from engram import theory
    [edge] = theory.load(graph["repo"]).joins()
    assert edge.note.startswith("knee tension raises the urge to rest") and edge.since == "2026-10-18"


@pytest.mark.parametrize("step", [0, 1])
def test_the_same_theory_link_twice_is_filed_once(graph, monkeypatch, step):
    clock(monkeypatch, step)
    link = {"from": "node/B", "to": "node/A", "rel": "amplifier", "mechanism": "knee tension raises the urge to rest",
            "strength": "medium"}
    ok = {"line": 5, "quote": "ok", "answering": "I think the knee tension amplifies the stiffness.", "link": link}
    out = hourly.run(ask=ask_theory([ok, dict(ok)]), summaries=False, now=LATER)
    assert out["filed"] == 1 and len(captured(graph["repo"], "link")) == 1


def test_an_agreement_counts_only_for_claudes_turn_just_before_it(graph):
    link = {"from": "node/B", "to": "node/A", "rel": "amplifier", "mechanism": "knee tension raises the urge to rest",
            "strength": "medium"}
    near = {"line": 5, "quote": "ok", "answering": "I think the knee tension amplifies the stiffness.", "link": link}
    far = {"line": 5, "quote": "ok", "answering": "Should we mark P-01 as provisional now?",
           "status": {"id": "pattern/P-01", "to": "provisional"}}
    out = hourly.run(ask=ask_theory([near, far]), summaries=False, now=LATER)
    assert out["filed"] == 1 and [d["why"] for d in out["dropped"]] == ["question not in Claude's words"]
    assert len(captured(graph["repo"], "link")) == 1 and not captured(graph["repo"], "status")


def add_session(world, name, lines, ts):
    path = world["path"].parent / f"{name}.jsonl"
    path.write_text("\n".join(said(t, ts) if i % 2 == 0 else reply(t, ts) for i, t in enumerate(lines)) + "\n")
    return path


@pytest.fixture
def knee(world):
    """The record already holds a week of knee-tablet entries; a later session repeats them in other words."""
    st = store.Store(world["repo"])
    with st.transaction() as tx:
        tx.add({"title": "Quillmar started; Zentrafen stopped", "date": "2026-09-21", "kind": "observation",
                "about": ["series/_observations"]}, "- switched tablets\n")
        tx.add({"title": "Knee a bit stiffer over first 2 days of Quillmar; stair climbing induced soreness",
                "date": "2026-09-23", "kind": "observation", "about": ["series/_observations"]}, "- noticed both\n")
        tx.add({"title": "Long ago", "date": "2026-06-01", "kind": "observation", "about": ["series/_observations"]}, "- far\n")
        tx.add({"title": "Torvanex stopped", "date": "2026-09-01", "kind": "med-change", "about": ["series/_observations"],
                "entity": "Torvanex (torvanexide)", "status": "stopped", "aliases": ["TVX tablets"]}, "- stopped\n")
        tx.add({"title": "Brevonal prescribed, never started", "date": "2026-08-01", "kind": "med-change",
                "about": ["series/_observations"], "entity": "Brevonal", "status": "prescribed-not-started"}, "- never\n")
    world["path"].unlink()  # only the new session is due
    path = add_session(world, "s3", ["my knee is a bit stiffer in the 2 days since Quillmar, and the stairs made it sore",
                                     "Noted.", "torvanex quietly stopped, and I never used brevonal", "Ok.",
                                     "I started it about 2 days ago", "Ok.", "back in August the swelling began", "Ok."],
                       "2026-09-23T20:00:00Z")
    return path


def test_a_relative_day_is_counted_from_when_he_said_it_and_a_bare_month_stays(knee):
    facts = [{"line": 5, "text": "Sam started Quillmar", "quote": "I started it about 2 days ago", "date": "2026-09",
              "kind": "observation"},
             {"line": 7, "text": "\"Swelling began\"", "quote": "back in August the swelling began", "date": "2026-08",
              "kind": "observation"}]
    out = run([], facts, now=datetime(2026, 9, 23, 23, 0, tzinfo=timezone.utc), dry_run=True)
    started, swelling = out["would_file"]
    assert (started["title"], started["date"], started["date_note"], started["approx"]) == ("Started Quillmar", "2026-09-21", "approx", "true")
    assert (swelling["title"], swelling["date"]) == ("Swelling began", "2026-08") and "approx" not in swelling
    assert "“I started it about 2 days ago”" in started["body"]  # the verbatim quote stays in the body


def test_relative_phrases():
    days = lambda w: capture.relative_days(w, "2026-09-23")  # a Wednesday
    assert days("about 2 days ago") == [("2026-09-21", True)]
    assert days("3 days ago") == [("2026-09-20", False)]
    assert days("last night") == [("2026-09-22", False)]
    assert days("since Monday") == [("2026-09-21", False)]
    assert days("since Wednesday") == [("2026-09-16", False)]
    assert days("this week") == [("2026-09-21", True)]
    assert days("a few days ago") == [("2026-09-20", True)]


def test_a_date_he_never_gave_is_not_sure_and_a_named_month_is_kept():
    said = "2026-10-24"  # a Saturday
    last_time = {"date": "2026-10-07", "quote": "Last time I was going to sleep"}
    assert capture.full_date(last_time, said, "Last time I was going to sleep and my back got tweaked") == ("never-said", False)
    assert capture.full_date({"date": "2026-10-07"}, said, "it was sometime in October") == ("2026-10", False)
    for day, words in [("2026-10-24", "my back is tight"), ("2026-10-23", "yesterday it hurt"), ("2026-10-07", "on Oct 7th"),
                       ("2026-10-07", "on 10/7"), ("2026-10-07", "7 October"), ("2026-10-20", "on Tuesday it flared"),
                       ("2026-10-18", "last weekend"), ("2026-10-10", "a couple of weeks ago")]:
        assert capture.said_date(day, words, said), (day, words)
    assert not capture.said_date("2026-05", "I may have", said) and capture.said_date("2026-05", "since may", said)
    assert capture.said_date("2026-09", "last month", said) and not capture.said_date("2026-08", "last month", said)
    fm, _ = capture.entry({"text": "Prior back cramp came lying flat", "quote": "Last time I was going to sleep", **last_time},
                          said, "s1", ["observation"], [], "", "Last time I was going to sleep")
    assert (fm["date"], fm["date_note"], fm["reported"]) == ("not-sure", "reported; when it happened wasn't said", said)


def test_an_impossible_day_is_never_filed():
    assert capture.full_date({"date": "2026-02-30"}, "2026-03-02") == ("not-sure", False)
    fm, _ = capture.entry({"text": "Knee ached", "quote": "knee ached", "date": "2026-02-30"},
                          "2026-03-02", "s1", ["observation"], [], "", "knee ached")
    assert fm["date"] != "2026-02-30"


def test_a_past_episode_dated_the_day_he_said_it_is_not_sure_and_a_month_is_the_latest_one():
    said, words = "2026-10-24", "Last time I was going to sleep and my back got tweaked"
    assert capture.full_date({"date": said, "quote": words}, said, words) == ("never-said", False)
    assert capture.full_date({"date": said, "quote": "it hurts again today"}, said, "it hurts again today") == (said, False)
    assert capture.said_date("2026-10", "in October", said) and capture.said_date("2025-11", "in November", said)
    assert not capture.said_date("2025-10", "in October", said) and not capture.said_date("2026-11", "in November", said)


def test_the_job_files_a_date_never_said_as_not_sure_and_an_undated_repeat_stays_dropped(world):
    with world["path"].open("a") as f:
        f.write(said("last time my back got tweaked going to sleep, and the bicycle knee is sore again", ts="2026-10-18T20:05:00Z") + "\n")
    back = {"line": 9, "text": "The earlier back cramp came going to sleep.", "quote": "last time my back got tweaked going to sleep",
            "date": "2026-10-07", "kind": "observation"}
    knee = {"line": 9, "text": "Bicycle knee is sore.", "quote": "the bicycle knee is sore again", "date": "2026-10-01",
            "kind": "observation"}
    from engram import ingest
    doc = world["repo"] / "reference/knee.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Knee\n\nThe bicycle knee gets sore again now and then.\n")
    git(world["repo"], "add", "-A")
    git(world["repo"], "commit", "-qm", "doc")
    ingest.record("medical")
    calls, verified = [], []
    out = hourly.run(ask=fake([back, knee], calls, verified, stating("bicycle")), summaries=False,
                      now=LATER + timedelta(minutes=5), dry_run=True)
    filed = out["would_file"]
    assert [(f["title"], f["date"], f["date_note"]) for f in filed] == \
        [("The earlier back cramp came going to sleep.", "not-sure", "reported; when it happened wasn't said")]
    assert [d["text"] for d in out["dropped"] if d["why"].startswith("already in")] == ["Bicycle knee is sore."]


def test_a_long_title_is_cut_at_a_word():
    text = "Left mid-trap cramp (centre line to scapula) plus a little left lat; came on at rest, sitting at the computer after waking up"
    assert capture.cut_title(text) == "Left mid-trap cramp (centre line to scapula) plus a little left lat; came on at rest, sitting at the computer after…"
    assert capture.cut_title("Short") == "Short"
    assert capture.cut_title("a" * 119 + " b", 120) == "a" * 119 + "…" and capture.cut_title("abc def", 3) == "abc…"


def test_refile_clears_the_mark_and_keeps_the_entries(world):
    calls = []
    fact = {"line": 7, "text": "Ache is better", "quote": "the ache is better", "date": "2026-10-18"}
    assert run(calls, [fact])["filed"] == 1 and run(calls)["sessions"] == 0
    assert capture.refile(["nomatch"]) == {"nomatch": []}
    assert capture.refile(["s"]) == {"s": ["s1"]}
    with capture.db() as c:
        assert c.execute("SELECT upto FROM filed").fetchone() == (0,)
    run(calls, [])
    assert len(calls) == 2 and "after line 0" in calls[1] and "Ache is better" in calls[1]  # read again, its entries shown
    assert len(captured(world["repo"])) == 1  # nothing deleted


def stating(phrase):
    """A stand-in for the repeat check's judgment: a candidate holding the phrase repeats the first record shown under
    it that holds it too."""
    def judge(prompt):
        out = []
        for block in re.split(r"\n(?=Candidate \d+ )", prompt)[1:]:
            m = re.match(r"Candidate (\d+) ", block)
            head, recs = block.split("Records:")
            for ref, text in re.findall(r"  - \[ref (.+?)\] (.*)", recs):
                if phrase in head.lower() and phrase in text.lower():
                    out.append({"n": int(m.group(1)), "ref": ref, "why": "same"})
                    break
        return out
    return judge


@pytest.fixture
def ankle(world):
    from engram import ingest
    doc = world["repo"] / "reference/treatments/ankle.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Ankle brace\n\nThe ankle injury dates from a bicycle fall on 2019-06-02, landing on the right side.\n")
    git(world["repo"], "add", "-A")
    git(world["repo"], "commit", "-qm", "doc")
    ingest.record("medical")
    with world["path"].open("a") as f:
        f.write(said("my ankle started when I slid off my bicycle, and ice helped tonight", ts="2026-10-18T20:05:00Z") + "\n")
    return world


SLID = {"line": 9, "text": "The ankle injury began when Sam slid off his bicycle.", "quote": "my ankle started when I slid off my bicycle",
        "date": "2019-06-02", "kind": "observation"}
ICE = {"line": 9, "text": "Ice helped the ankle tonight.", "quote": "ice helped tonight", "date": "2026-10-18", "kind": "observation"}


def test_a_fact_already_in_a_document_is_dropped_and_a_new_detail_kept(ankle):
    calls, verified = [], []
    out = hourly.run(ask=fake([SLID, ICE], calls, verified, stating("bicycle")), summaries=False, now=LATER + timedelta(minutes=5))
    assert out["filed"] == 1 and [e.fm["title"] for e in captured(ankle["repo"])] == ["Ice helped the ankle tonight."]
    drop = [d for d in out["dropped"] if d["why"].startswith("already in")]
    assert drop == [{"session": "s1", "line": 9, "why": "already in reference/treatments/ankle.md#Ankle brace",
                     "text": "The ankle injury began when Sam slid off his bicycle."}]
    assert len(calls) == 1 and len(verified) == 1  # one repeat check per session, beside the one extraction


def test_the_repeat_check_is_shown_the_search_hits_on_the_candidates_own_text(ankle):
    calls, verified = [], []
    hourly.run(ask=fake([SLID], calls, verified), summaries=False, now=LATER + timedelta(minutes=5))
    prompt = verified[0]
    assert "Candidate 1 [" in prompt and "slid off his bicycle" in prompt
    hits = prompt.split("Records:")[1]
    assert "[ref reference/treatments/ankle.md#Ankle brace] " in hits and "dates from a bicycle fall on 2019-06-02" in hits


def test_a_repeat_naming_a_record_not_shown_is_kept(ankle):
    calls = []
    made_up = lambda prompt: [{"n": 1, "ref": "reference/elsewhere.md#X", "why": "same"}]
    out = hourly.run(ask=fake([ICE], calls, judge=made_up), summaries=False, now=LATER + timedelta(minutes=5))
    assert out["filed"] == 1


def naming(where):
    """A model that calls every candidate a repeat of the first record shown under it whose ref holds `where`."""
    def judge(prompt):
        out = []
        for block in re.split(r"\n(?=Candidate \d+ )", prompt)[1:]:
            n = int(re.match(r"Candidate (\d+) ", block).group(1))
            refs = [ref for ref in re.findall(r"  - \[ref (.+?)\] ", block.split("Records:")[1]) if where in ref]
            if refs:
                out.append({"n": n, "ref": refs[0], "why": "same"})
        return out
    return judge


@pytest.fixture
def tension(world):
    """Knee stiffness is in the record on 2026-10-13, as an entry and on its complaint page; a session on
    2026-11-05 says it's back."""
    from engram import ingest
    st = store.Store(world["repo"])
    with st.transaction() as tx:
        tx.add({"title": "Knee stiffness behind the kneecap", "date": "2026-10-13", "kind": "symptom",
                "about": ["series/_observations"]}, "- knee stiffness, eased with heat\n")
        tx.add({"title": "Knee stiffness comes from desk posture", "date": "2026-10-13", "kind": "interpretation",
                "about": ["series/_observations"]}, "- knee stiffness blamed on posture\n")
    doc = world["repo"] / "complaints/knee-stiffness.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Knee stiffness\n\nPast occurrences of knee stiffness:\n- 2026-10-13: knee stiffness, eased with heat\n")
    git(world["repo"], "add", "-A")
    git(world["repo"], "commit", "-qm", "tension")
    ingest.record("medical")
    world["path"].unlink()
    add_session(world, "s4", ["knee stiffness is back, and it comes from my desk posture", "Noted."], "2026-11-05T20:00:00Z")
    return world


NOV5 = datetime(2026, 11, 5, 23, 0, tzinfo=timezone.utc)


def back(date, kind="symptom", approx=False):
    f = {"line": 1, "text": "Knee stiffness is back", "quote": "knee stiffness is back", "date": date, "kind": kind}
    return {**f, "approx": True} if approx else f


def test_the_same_occurrence_is_still_a_repeat(tension):
    cases = [(back("2026-10-13"), "symptom"),  # a same-day restatement
             (back("2026-10-16", approx=True), "symptom"),  # an approximate date within 4 days
             (back("2026-10-14"), "complaints/"),  # the complaint page lists the candidate's own occurrence
             ({**back("2026-11-05", kind="interpretation"), "text": "Knee stiffness comes from desk posture",
               "quote": "it comes from my desk posture"}, "interpretation")]  # an interpretation, on any day
    for fact, where in cases:
        out = hourly.run(ask=fake([fact], [], None, naming(where)), summaries=False, now=NOV5, dry_run=True)
        assert out["would_file"] == [] and not out["kept"], (fact, where)
        assert [d["why"].startswith("already in") and where in d["why"] for d in out["dropped"]] == [True], (fact, where)


def test_same_occurrence_dates():
    same = capture.same_occurrence
    assert same({"date": "2026-11-05"}, [("2026-11-03", False)]) and not same({"date": "2026-11-05"}, [("2026-11-02", False)])
    assert same({"date": "2026-11-05", "approx": "true"}, [("2026-11-01", False)])
    assert same({"date": "2026-11-05"}, [("2026-11-01", True)]) and not same({"date": "2026-11-05"}, [("2026-10-31", True)])
    assert same({"date": "2026-11"}, [("2026-11-20", False)]) and not same({"date": "2026-11"}, [("2026-10-31", False)])
    assert same({"date": "2026-11-05"}, [("2026-11", False)]) and not same({"date": "2026-11-05"}, [])


ACHE = [{"line": 7, "text": "The ache is better.", "quote": "the ache is better", "date": "not-sure"}]


def test_a_reply_without_json_is_an_error_and_the_mark_stays(world):
    out = hourly.run(ask=lambda p: ("I looked and there is nothing to file.", 0.01), summaries=False, now=LATER)
    assert out["sessions"] == 0 and "held no JSON" in out["error"]
    with capture.db() as c:
        assert c.execute("SELECT count(*) FROM filed").fetchone() == (0,)
        assert c.execute("SELECT ok, error FROM run ORDER BY rowid DESC LIMIT 1").fetchone()[0] == 0
    assert any("held no JSON" in l for l in setup.status(world["repo"]))
    assert run([], ACHE)["filed"] == 1  # the next run reads it again


def test_a_failed_commit_takes_back_its_entry_files(world):
    repo = world["repo"]
    links = repo / "events" / store.LINKS
    (repo / ".engram/hooks/pre-commit").write_text("#!/bin/sh\nexit 1\n")  # a pre-commit that refuses
    st = store.Store(repo)
    before = len(st.events())
    with pytest.raises(RuntimeError, match="commit failed"):
        with st.transaction() as tx:
            tx.add({"title": "x", "date": "2026-10-18", "kind": "observation", "about": ["series/_observations"]}, "- x\n")
            tx.add({"title": "l", "date": "2026-10-18", "kind": "link", "from": "a", "to": "b", "family": "timeline", "rel": "led-to"}, "")
    assert git(repo, "status", "--porcelain", "--untracked-files=all", "--", "events").strip() == ""
    assert not links.exists() and len(store.Store(repo).events()) == before
    with pytest.raises(Exception):
        capture.file_session("medical", repo, world["path"], ask=fake(ACHE, []))
    assert git(repo, "status", "--porcelain", "--untracked-files=all", "--", "events").strip() == ""
    with capture.db() as c:
        assert c.execute("SELECT count(*) FROM filed").fetchone() == (0,)  # the mark stays: the next run files it once
    (repo / "events/2026").mkdir(parents=True, exist_ok=True)
    (repo / "events/2026/stray.md").write_text("---\nid: stray\n---\n")
    assert any("1 entry files aren't committed: events/2026/stray.md" in l for l in setup.status(repo))


def test_a_failed_push_is_recorded_shown_and_retried(world):
    repo, bare = world["repo"], world["tmp"] / "hub.git"
    (repo / ".engram/engram.toml").write_text(TOML.replace('events_dir = "events"', 'events_dir = "events"\npush = true'))
    git(repo, "commit", "-qam", "push")
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "config", "branch.main.remote", "origin")
    git(repo, "config", "branch.main.merge", "refs/heads/main")
    run([], ACHE)  # the hub isn't there: the push fails
    assert store.push_failure(repo)
    assert any("last push failed" in l for l in hourly.problems("medical"))
    assert "last push failed" in hourly.session_start(world["payload"])
    assert any("last push failed" in l for l in setup.status(repo))
    git(bare.parent, "init", "-q", "--bare", str(bare))
    out = hourly.run(ask=fake([], []), summaries=False, now=LATER)  # the next hourly run retries
    assert store.push_failure(repo) is None and out["error"] is None
    assert hourly.unpushed(repo)[0] == 0 and hourly.session_start(world["payload"]) == hourly.READ_WHOLE


def test_a_push_that_hangs_is_a_failed_push_and_retried(world, monkeypatch):
    repo, bare = world["repo"], world["tmp"] / "hub.git"
    git(bare.parent, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "config", "branch.main.remote", "origin")
    git(repo, "config", "branch.main.merge", "refs/heads/main")
    hook = repo / ".engram/hooks/pre-push"  # a push that never answers, as a dead ssh link
    hook.write_text("#!/bin/sh\nsleep 30\n")
    hook.chmod(0o755)
    monkeypatch.setattr(store, "PUSH_TIMEOUT", 1)
    assert store.Store(repo).push() is False
    assert "timed out" in store.push_failure(repo)[1]
    hook.unlink()
    (repo / ".engram/engram.toml").write_text(TOML.replace('events_dir = "events"', 'events_dir = "events"\npush = true'))
    out = {"error": None}
    hourly.retry_push(repo, out)  # the hourly retry
    assert store.push_failure(repo) is None and out["error"] is None


def test_a_summaries_run_that_stops_is_the_runs_error(world, monkeypatch):
    monkeypatch.setattr(hourly.summarize, "run", lambda d: {"summarized": 0, "stopped": "out of quota"})
    out = hourly.run(ask=fake([], []), now=LATER)
    assert "out of quota" in out["error"]
    assert any("out of quota" in l for l in hourly.problems("medical"))


def test_the_hourly_run_summarizes_the_records_of_an_area_it_files_for(world, monkeypatch):
    got = []
    monkeypatch.setattr(hourly.recsum, "run", lambda d: got.append(d) or {"usd": 0.5})
    assert run([], dry_run=True)["error"] is None and got == []  # a dry run spends nothing
    out = run([])
    assert got == ["medical"] and out["error"] is None and out["usd"] >= 0.5
    monkeypatch.setattr(hourly.pack, "load", lambda d: pack.NONE)  # its pack says nothing to write down: not filed for
    run([], now=LATER + timedelta(days=1))
    assert got == ["medical"]


def test_a_record_summaries_failure_is_the_runs_error(world, monkeypatch):
    def fail(d):
        raise RuntimeError("usage limit")
    monkeypatch.setattr(hourly.recsum, "run", fail)
    assert "record summaries medical: RuntimeError: usage limit" in run([])["error"]


def test_a_daily_copy_that_failed_or_went_quiet_is_its_own_line(world):
    cfg, daily_json = world["tmp"] / "config.toml", world["tmp"] / "data/daily.json"
    def last(ok, ago):
        at = (datetime.now().astimezone() - ago).isoformat(timespec="seconds")
        daily_json.write_text(json.dumps({"started": at, "ok": ok, "finished": at} | ({} if ok else {"failed_step": "pull backups"})))
        return hourly.session_start(world["payload"])
    assert last(False, timedelta(hours=1)) == hourly.READ_WHOLE  # no daily copy configured: nothing to say
    cfg.write_text(cfg.read_text() + '[daily]\nbox = "spare"\n')
    failed = last(False, timedelta(hours=1))
    assert failed.startswith("engram's daily copy") and "pull backups" in failed and "capture" not in failed
    quiet = last(True, timedelta(days=3))
    assert quiet.startswith("engram's daily copy") and "capture" not in quiet
    assert last(True, timedelta(hours=20)) == hourly.READ_WHOLE


def test_the_session_start_cuts_only_the_picture_at_a_line_to_fit_the_hooks_window(world, monkeypatch):
    toml = world["repo"] / ".engram/engram.toml"
    toml.write_text(TOML + "[index]\nevents = true\n")
    picture = "\n".join(f"- thing {n}: taking since 2026-01-01; 10mg [{n:04d}]" for n in range(400))
    monkeypatch.setattr(hourly.now_mod, "text", lambda repo, mark_shown=False: picture)
    monkeypatch.setattr(hourly, "problems", lambda d: ["the hourly job hasn't run since 2026-10-01 00:00"])
    surface = "For you, not the owner: " + "x" * 1500
    monkeypatch.setattr(hourly.refine, "surface", lambda root: surface)
    out = hourly.session_start(world["payload"])
    parts = out.split("\n\n")
    assert hourly.HOOK_BUDGET - 100 < len(out) <= hourly.HOOK_BUDGET
    assert parts[0].startswith("engram capture needs fixing") and parts[1] == hourly.READ_WHOLE and parts[3] == surface
    shown = parts[2].splitlines()
    assert shown[-1] == hourly.MORE and shown[:-1] == picture.splitlines()[:len(shown) - 1]
    monkeypatch.setattr(hourly.now_mod, "text", lambda repo, mark_shown=False: "- one thing: taking")
    assert hourly.session_start(world["payload"]).split("\n\n")[2] == "- one thing: taking"  # it fits: whole


def test_a_launcher_at_another_path_running_the_same_code_is_not_old(world):
    repo, tmp = world["repo"], world["tmp"]
    other = tmp / "bin/engram"  # another install of the same checkout, as ~/.local/bin/engram is
    other.parent.mkdir()
    other.write_text(Path(setup.engram_cmd()[0]).read_text())
    other.chmod(0o755)
    here = setup.engram_cmd()[0]
    sp = repo / ".claude/settings.json"
    sp.write_text(sp.read_text().replace(here, str(other)))
    hook = repo / ".engram/hooks/pre-commit"
    hook.write_text(hook.read_text().replace(here, str(other)))
    plist = tmp / "LaunchAgents" / f"{setup.LABEL}.plist"
    conf = plistlib.loads(plist.read_bytes())
    conf["ProgramArguments"][0] = str(other)
    plist.write_bytes(plistlib.dumps(conf))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "installed from elsewhere")
    man = json.loads(capture.db().execute("SELECT setup FROM repo").fetchone()[0])
    assert setup.missing(repo, man) == {}
    assert hourly.session_start(world["payload"]) == hourly.READ_WHOLE
    assert git(repo, "status", "--porcelain").strip() == ""  # nothing rewritten
    stale = tmp / "gone/engram"
    sp.write_text(sp.read_text().replace(str(other), str(stale)))
    assert setup.missing(repo, man) == {"settings": "the SessionStart hook runs an old engram"}


@pytest.fixture
def flare(world):
    """Knee stiffness is a recurring symptom with its own page; the record holds a long drive on 2026-11-04."""
    from engram import ingest
    repo = world["repo"]
    (repo / ".engram/engram.toml").write_text(TOML + '[index]\nevents = true\n[links.timeline]\nrels = ["led-to", "occurrence"]\n')
    (repo / "complaints").mkdir()
    (repo / "complaints/knee-stiffness.md").write_text(
        "# Knee stiffness\n\nSam's words: “tight behind my kneecap”\n\nStories: knee, leg\n\n## Occurrences\n\n"
        "| Date | How it felt |\n|---|---|\n| 2026-10-13 | tight behind my kneecap |\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a complaint page")
    st = store.Store(repo)
    with st.transaction() as tx:
        drive = tx.add({"title": "Four-hour drive to Tahoe", "date": "2026-11-04", "kind": "observation",
                        "about": ["series/_observations", "story/knee"]}, "- long drive\n").id
    ingest.record("medical")
    world["path"].unlink()
    add_session(world, "s6", ["knee stiffness is back today, it started after the long drive yesterday", "Noted."],
                "2026-11-05T20:00:00Z")
    return {**world, "drive": drive}


def test_placement_with_unknown_ids_files_the_fact_unplaced(flare):
    fact = {"line": 1, "text": "Knee stiffness is back", "quote": "knee stiffness is back today", "date": "2026-11-05",
            "kind": "symptom", "stories": ["nonsense"], "occurrence_of": "no-such-symptom", "led_from": "20990101-000000-x-0000"}
    assert hourly.run(ask=fake([fact], []), summaries=False, now=NOV5)["filed"] == 1
    st = store.Store(flare["repo"])
    assert not [l for l in st.events(kind="link") if l.fm.get("author") == "engram-capture"]
    interp = {**fact, "kind": "interpretation", "occurrence_of": "knee-stiffness"}  # not an occurrence kind
    assert capture.place(interp, {"kind": "interpretation"}, st, ["knee"], {"knee-stiffness": ("x", ["knee"])},
                         ["occurrence"])["occurrence"] is None


def test_a_refiled_session_sees_its_facts_as_already_filed_from_the_store(flare):
    fact = {"line": 1, "text": "Knee stiffness is back", "quote": "knee stiffness is back today", "date": "2026-11-05",
            "kind": "symptom", "led_from": flare["drive"]}
    assert hourly.run(ask=fake([fact], []), summaries=False, now=NOV5)["filed"] == 1
    st = store.Store(flare["repo"])
    assert [l.fm["family"] for l in st.events(kind="link") if l.fm.get("author") == "engram-capture"] == ["timeline"]
    with st.transaction() as tx:  # a renewal from the same session shares its source
        tx.add({"title": "Orvexa: still on it", "date": "2026-11-05", "kind": "renewal", "thing": "orvexa",
                "source": "said in session s6 on 2026-11-05", "author": "engram-capture"}, "- still on it\n")
    with capture.db() as c, c:
        c.execute("UPDATE filed SET entries = '[]'")  # nothing kept per session: the store is what's filed
    assert capture.refile(["s6"]) == {"s6": ["s6"]}
    calls = []
    hourly.run(ask=fake([], calls), summaries=False, now=NOV5)
    assert "2026-11-05 Knee stiffness is back:" in calls[0]
    assert "2026-11-05 led to:" not in calls[0] and "2026-11-05 Orvexa: still on it:" not in calls[0]


def test_a_failed_renewal_leaves_the_mark_so_the_next_run_reads_the_session_again(world, monkeypatch):
    renew = capture.renew

    def broken(*a, **k):
        raise RuntimeError("renew broke")
    monkeypatch.setattr(capture, "renew", broken)
    calls = []
    out = run(calls, ACHE)
    assert out["filed"] == 1 and "renew broke" in out["error"]
    with capture.db() as c:
        assert c.execute("SELECT count(*) FROM filed").fetchone() == (0,)  # the mark didn't move
    monkeypatch.setattr(capture, "renew", renew)
    assert run(calls)["sessions"] == 1 and len(calls) == 2  # read again
    with capture.db() as c:
        assert c.execute("SELECT upto FROM filed").fetchone() == (7,)
