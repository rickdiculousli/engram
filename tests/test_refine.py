import json
import plistlib
import shlex
import subprocess

import pytest

from conftest import git, make_repo
from engram import refine


@pytest.fixture
def served(env):
    """Engram's own repo and two domains, each with the one page; the config names engram's repo in [refine]."""
    tmp = env["tmp"]
    own = make_repo(tmp / "engram", {".engram/README.md": "## Jobs\n", ".engram/engram.toml": "[refine]\npaused = false\n"})
    med = make_repo(tmp / "med", {".engram/README.md": "## Jobs\n"})
    books = make_repo(tmp / "books", {".engram/README.md": "## Jobs\n", ".engram/engram.toml": "[refine]\npaused = true\n"})
    env["set_repo"]("med", med, pack="")
    env["set_repo"]("books", books, pack="")
    cfg = tmp / "config.toml"
    cfg.write_text(f'[refine]\nrepo = "{own}"\nweekly_cap = 50\npass_cap = 30\n' + cfg.read_text())
    return {**env, "own": own, "med": med, "books": books}


def test_the_pass_serves_engram_then_each_domain_and_skips_a_paused_one(served):
    calls = []
    lines = refine.run(show=True, runner=lambda *a, **k: calls.append(a))
    assert not calls and lines[2] == "books: paused in its rules; skipped"
    work = served["data"] / "scratch/refine"
    for line, name in zip(lines, ("engram", "med")):
        repo = served["own"] if name == "engram" else served["med"]
        assert line.startswith(f"{name}: ") and shlex.split(line.removeprefix(f"{name}: ")) == [
            "claude", "-p", f"Follow {served['own']}/skills/engram-refine/SKILL.md: repo={repo} mode=land worktrees={work}",
            "--output-format", "json", "--max-budget-usd", "30.00", "--permission-mode", "auto", "--model", "opus",
            "--settings", json.dumps({"autoMode": {"allow": ["$defaults", refine.ALLOW]}}),
            "--add-dir", f"{served['own']}/skills/engram-refine", "--add-dir", str(repo), "--add-dir", str(work)]
    assert not (served["data"] / "refine/ledger.jsonl").exists()


def test_a_run_keeps_the_ledger_under_the_weekly_cap_and_skips_a_repo_passed_this_week(served):
    costs = iter([25.0, 20.0])

    def runner(cmd, **kw):
        assert kw["cwd"] == served["data"] / "scratch/refine" and "CLAUDE_EFFORT" not in kw["env"]
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": next(costs), "result": "ok"}),
                              "stderr": ""})()

    assert refine.run(runner=runner)[:2] == ["engram: ok, $25.00; week $25.00 of $50", "med: ok, $20.00; week $45.00 of $50"]
    rows = refine.ledger()
    assert [(r["repo"], r["cost_usd"], r["dry_run"]) for r in rows] == [("engram", 25.0, False), ("med", 20.0, False)]
    assert (served["data"] / f"refine/runs/{refine.week()}/med.md").read_text() == "ok"
    assert refine.run(show=True)[:2] == ["engram: already ran this week", "med: already ran this week"]
    assert "--max-budget-usd 5.00" in refine.run("med", show=True)[0]  # what's left of the week


def writer(html="<!DOCTYPE html><html>page</html>", cost=1.5):
    """A stand-in `claude -p` for the digest: records each call and answers with the page."""
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, kw.get("input")))
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": cost, "result": f"```html\n{html}\n```"}),
                              "stderr": ""})()
    return run, calls


def test_a_digest_brings_waiting_specs_and_each_change_once_then_nothing_when_nothing_waits(served):
    med = served["med"]
    (med / ".engram/specs").mkdir()
    for f, status in (("a", "open"), ("b", "approved"), ("c", "deferred"), ("d", "approved\nblocked: it would rewrite the record")):
        (med / f".engram/specs/{f}.md").write_text(f"---\nstatus: {status}\n---\n# Spec {f}\n")
    git(med, "add", "-A")
    git(med, "commit", "-qm", "Shorter rules\n\nRefinement: the advisor's rules are shorter\n\nCo-Authored-By: Claude <noreply@anthropic.com>")  # not git's trailer block
    git(med, "commit", "-q", "--allow-empty", "-m", "not the pass's")
    run, calls = writer()
    cost, line = refine.digest("med", med, 3.0, run)
    page = served["data"] / f"refine/digests/{refine.datetime.now():%Y-%m-%d}-med.html"
    assert cost == 1.5 and line == f"page {page}" and page.read_text() == "<!DOCTYPE html><html>page</html>"
    cmd, prompt = calls[0]
    assert cmd[:2] == ["claude", "-p"] and cmd[cmd.index("--tools") + 1] == "" and "3.00" in cmd
    assert "# Spec a" in prompt and "# Spec d" in prompt and "# Spec b" not in prompt and "# Spec c" not in prompt
    day = git(med, "log", "-1", "--format=%as").strip()
    assert f"- {day}: the advisor's rules are shorter" in prompt and "in med when you want to deal with it" in prompt
    assert calls[1:] == [(["open", str(page)], None)] or refine.sys.platform != "darwin"
    refine.digest("med", med, 3.0, run)
    assert "# Spec a" in calls[-2][1] and "rules are shorter" not in calls[-2][1]  # a change shows once, a spec until answered
    for f in "ad":
        (med / f".engram/specs/{f}.md").write_text("---\nstatus: rejected\n---\n")
    n = len(calls)
    assert refine.digest("med", med, 3.0, run) == (0.0, "") and len(calls) == n  # nothing to discuss: no page


def test_a_digest_that_fails_marks_nothing_shown_and_one_past_the_cap_waits(served):
    med = served["med"]
    git(med, "commit", "-q", "--allow-empty", "-m", "Fold\n\nRefinement: two docs are one")
    run, calls = writer(html="no page here")
    assert refine.digest("med", med, 3.0, run) == (1.5, "no page, the writer's answer wasn't one; its items wait for the next")
    assert refine.digest("med", med, 0.2, run)[1].startswith("no page, the week's cap is spent") and len(calls) == 1
    run, calls = writer()
    refine.digest("med", med, 3.0, run)
    assert "two docs are one" in calls[0][1]


def test_a_pass_leaves_its_page_and_pays_for_it_from_the_week(served):
    med = served["med"]
    (med / ".engram/specs").mkdir()
    (med / ".engram/specs/a.md").write_text("---\nstatus: open\n---\n# Fewer docs\n")
    run, calls = writer()

    def runner(cmd, **kw):
        if "repo=" in " ".join(cmd):
            return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 10.0, "result": "ok"}), "stderr": ""})()
        return run(cmd, **kw)
    lines = refine.run("med", runner=runner, attached=True)
    assert lines[0].startswith("med: ok, $10.00; week $11.50 of $50; page ") and lines[0].endswith("-med.html")
    assert refine.ledger()[-1]["cost_usd"] == 11.5 and "Fewer docs" in calls[0][1]
    assert refine.run("med", runner=runner, dry_run=served["tmp"] / "dry", attached=True)[0].endswith("of $50")  # a dry run: no page


def test_install_writes_the_weekly_job(served, tmp_path):
    plist = plistlib.loads(refine.install(tmp_path / "agents", load=False).read_bytes())
    assert plist["Label"] == "engram.refine" and plist["ProgramArguments"][:2] == ["/usr/bin/caffeinate", "-i"]
    assert plist["ProgramArguments"][-2:] == ["refine", "run"] and plist["StartCalendarInterval"] == refine.SCHEDULE
    assert plist["EnvironmentVariables"]["ENGRAM_DATA"] == str(served["data"])


def test_conversations_read_the_owners_week_in_the_repo_with_the_reply_they_read(served):
    root, med, now = served["tmp"] / "no-sessions", served["med"], refine.datetime.now(refine.timezone.utc)
    ts = lambda days: (now - refine.timedelta(days=days)).isoformat()

    def session(stem, *events, entry="cli"):
        p = root / ("-" + str(med).strip("/").replace("/", "-").replace(".", "-")) / f"{stem}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps({"cwd": str(med), "entrypoint": entry, **e}) + "\n" for e in events))

    user = lambda text, days: {"type": "user", "timestamp": ts(days), "message": {"role": "user", "content": text}}
    reply = lambda text, stop="end_turn": {"type": "assistant", "message": {"stop_reason": stop, "content": [{"type": "text", "text": text}]}}
    session("aaaa1111", user("too old", 9), reply("x"), user("how is my shoulder", 1), reply("checking", "tool_use"),
            reply("Better since Monday."))
    session("bbbb2222", user("filer prompt", 1), entry="sdk-cli")
    session("cccc3333", user("# Brief\n" + "do it. " * 300, 1))
    session("dddd4444", user("Act as the review sub-agent for this task.\n\nReview the shoulder notes", 1),
            user("and the knee", 1), entry="sdk-ts")  # T3's delegate, in the owner's own entrypoint
    out = refine.conversations(med).splitlines()
    assert out[0] == f"# 1 sessions, 1 messages since {now - refine.timedelta(days=7):%Y-%m-%d}"
    assert out[2].startswith("## ") and out[2].endswith("session aaaa1111 (1 messages)")
    assert out[3].endswith(": how is my shoulder") and out[4] == "  - reply: Better since Monday."
    assert refine.conversations(med, cap=10).splitlines()[-1].endswith("session aaaa1111 (1 messages)")  # a cut one is named


def test_the_cli_takes_a_repo_by_name_and_never_runs_every_repo_for_a_positional_one(served, capsys):
    from engram.cli import main
    for action in ("run", "install"):
        with pytest.raises(SystemExit, match=f"engram refine {action}: takes no repo; run one with `engram refine run --repo NAME`"):
            main(["refine", action, "med"])
    main(["refine", "conversations", "med"])
    assert capsys.readouterr().out.startswith("# 0 sessions")
    with pytest.raises(SystemExit, match="engram refine conversations: medical is neither a folder nor one of engram, med, books"):
        main(["refine", "conversations", "medical"])



def test_a_digest_carries_the_portrait_of_proposed_jobs_until_they_are_confirmed(served):
    med = served["med"]
    page = med / ".engram/README.md"
    portrait = 'You come here for two things: "keep what I tell you" and the plan. #weekly. Is that it?'
    page.write_text(f"---\njobs: proposed\nportrait: >-\n  {portrait}\n---\n# Notes\n\n## Jobs\n")
    run, calls = writer()
    refine.digest("med", med, 3.0, run)
    refine.digest("med", med, 3.0, run)
    assert [portrait in c[1] for c in calls if c[1]] == [True, True]  # every page until answered
    page.write_text(page.read_text().replace("jobs: proposed", "jobs: confirmed"))
    assert refine.digest("med", med, 3.0, run) == (0.0, "")


def test_session_start_shows_only_files_that_wont_parse_and_the_digest_keeps_the_rest(served):
    med, own = served["med"], served["own"]
    (med / ".engram/specs").mkdir(parents=True, exist_ok=True)
    (med / ".engram/specs/a.md").write_text("---\nstatus: approved\nblocked: `engram.toml`: the record\n---\n# A\n")
    (med / ".engram/specs/b.md").write_text("---\nstatus: approved\nblocked: >-\n  it would touch: the record\n---\n# B\n")
    (med / ".engram/README.md").write_text('---\njobs: proposed\nportrait: "You said "keep it": Is that it?"\n---\n')  # what a careless rewiring writes
    git(own, "commit", "-q", "--allow-empty", "-m", "Fold\n\nRefinement: two docs are one")
    out = refine.surface(med)
    assert out.startswith("For you, not the owner") and "specs/a.md:" in out and "README.md:" in out
    assert "B" not in out.replace(str(served["tmp"]), "") and "two docs" not in out
    run, calls = writer()
    refine.digest("med", med, 3.0, run)
    assert "it would touch: the record" in calls[0][1] and "`engram.toml`" not in calls[0][1]
    (med / ".engram/README.md").write_text("---\njobs: confirmed\n---\n")
    (med / ".engram/specs/a.md").unlink()
    assert refine.surface(med) == ""


def test_a_half_written_seen_file_shows_changes_again_instead_of_none(served):
    med = served["med"]
    git(med, "commit", "-q", "--allow-empty", "-m", "Fold\n\nRefinement: two docs are one")
    (served["data"] / "refine").mkdir(parents=True, exist_ok=True)
    (served["data"] / "refine/seen.json").write_text('["abc", ')
    run, calls = writer()
    refine.digest("med", med, 3.0, run)
    assert "two docs are one" in calls[0][1]


def test_a_reverted_refinement_is_never_announced(served):
    med = served["med"]
    (med / "x.md").write_text("x\n")
    git(med, "add", "-A")
    git(med, "commit", "-qm", "Shorter rules\n\nRefinement: the advisor's rules are shorter")
    git(med, "revert", "--no-edit", "HEAD")
    assert refine._landed(med) == []
    git(med, "revert", "--no-edit", "HEAD")  # reapplied: the change is back
    assert [line for _, _, line in refine._landed(med)] == ["the advisor's rules are shorter"]
    git(med, "revert", "--no-edit", "HEAD")  # and undone again
    assert refine._landed(med) == []


def test_a_failed_pass_is_told_in_health_and_only_a_free_failure_is_retried(served):
    def runner(cmd, **kw):
        if "repo=" + str(served["own"]) in cmd[2]:
            raise subprocess.TimeoutExpired(cmd, kw["timeout"])
        raise FileNotFoundError(2, "No such file or directory", "claude")

    assert refine.run(runner=runner)[:2] == ["engram: failed, $30.00; week $30.00 of $50",
                                             "med: failed, $0.00; week $30.00 of $50"]  # never started: nothing spent
    assert [(r["repo"], r["ok"], r["error"]) for r in refine.ledger()] == [
        ("engram", False, "timed out after 4 hours"),
        ("med", False, "didn't start: FileNotFoundError: [Errno 2] No such file or directory: 'claude'")]
    again = refine.run(show=True)
    assert again[0] == "engram: already ran this week, and failed" and again[1].startswith("med: claude -p")  # a free failure retries
    assert refine.status()[:2] == ["weekly pass on engram: FAILED (timed out after 4 hours), $30.00",
                                   "weekly pass on med: FAILED (didn't start: FileNotFoundError: [Errno 2] No such file or "
                                   "directory: 'claude'), $0.00"]


def test_a_pass_stopped_mid_run_keeps_its_cap_spent_and_is_never_rerun_for_free(served):
    def runner(cmd, **kw):
        raise KeyboardInterrupt  # the process is stopped before the pass ends
    with pytest.raises(KeyboardInterrupt):
        refine.run(only="med", runner=runner)
    row = refine.ledger()[-1]
    assert (row["repo"], row["running"], row["cost_usd"]) == ("med", True, 30.0)
    assert "med: already ran this week, stopped mid-run" in refine.run(show=True)
    assert "stopped mid-run" in refine.status()[1]  # no pass holds the lock


def test_a_pass_cut_by_its_budget_says_so(served):
    class Proc:
        returncode, stderr = 1, ""
        stdout = json.dumps({"is_error": True, "subtype": "error_max_budget_usd", "total_cost_usd": 30.0, "result": ""})
    refine.run(only="med", runner=lambda cmd, **kw: Proc())
    assert refine.ledger()[-1]["error"] == "error max budget usd"



def test_a_pass_on_request_starts_on_its_own_and_health_survives_a_hand_edited_ledger(served, monkeypatch):
    started = []
    monkeypatch.setattr(refine.subprocess, "Popen", lambda cmd, **kw: started.append((cmd, kw)))
    assert "started on its own" in refine.start("med")
    cmd, kw = started[0]
    assert cmd[-3:] == ["--repo", "med", "--attached"] and kw["start_new_session"] is True
    (served["data"] / "refine").mkdir(parents=True, exist_ok=True)
    (served["data"] / "refine/ledger.jsonl").write_text(json.dumps({"week": refine.week(), "repo": "med", "dry_run": False}) + "\n")
    assert refine.status()[0].startswith("weekly pass: the ledger doesn't read")


def test_a_pass_on_request_that_cant_run_says_why_and_starts_nothing(served, monkeypatch):
    started = []
    monkeypatch.setattr(refine.subprocess, "Popen", lambda cmd, **kw: started.append(cmd))
    (served["data"] / "refine").mkdir(parents=True, exist_ok=True)
    rows = [{"week": refine.week(), "repo": "engram", "dry_run": False, "ok": False, "running": True, "cost_usd": 50.0,
             "started": "x"}]
    (served["data"] / "refine/ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with open(served["data"] / "refine/lock", "w") as fh:
        refine.fcntl.flock(fh, refine.fcntl.LOCK_EX)
        with pytest.raises(SystemExit, match="a pass is running now"):  # not "spent": the running pass holds its cap
            refine.start("med")
        assert "running since" in refine.status()[0]
    rows = [{"week": refine.week(), "repo": "engram", "dry_run": False, "ok": True, "cost_usd": 50.0, "started": "x"}]
    (served["data"] / "refine/ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(SystemExit, match="is spent"):
        refine.start("med")
    with pytest.raises(SystemExit, match="paused"):
        refine.start("books")
    assert started == []


def test_a_long_revert_chain_is_walked_without_recursion(served):
    med = served["med"]
    tree = git(med, "write-tree").strip()
    head = git(med, "commit-tree", tree, "-p", "HEAD", "-m", "Shorter\n\nRefinement: shorter").strip()
    first = head
    for _ in range(1201):  # past Python's recursion limit
        head = git(med, "commit-tree", tree, "-p", head, "-m", f"Revert\n\nThis reverts commit {head}.").strip()
    git(med, "reset", "-q", "--hard", head)
    assert refine._landed(med) == []  # an odd number of reverts: undone
    assert first


def test_a_commit_that_reverts_a_change_and_its_revert_settles_both(served):
    med = served["med"]
    tree = git(med, "write-tree").strip()
    c0 = git(med, "commit-tree", tree, "-p", "HEAD", "-m", "A\n\nRefinement: a").strip()
    c1 = git(med, "commit-tree", tree, "-p", c0, "-m", f"B\n\nRefinement: b\n\nThis reverts commit {c0}.").strip()
    c2 = git(med, "commit-tree", tree, "-p", c1, "-m", f"C\n\nThis reverts commit {c1}.").strip()
    c3 = git(med, "commit-tree", tree, "-p", c2, "-m", f"D\n\nRefinement: d\n\nThis reverts commit {c2}.\nThis reverts commit {c0}.").strip()
    git(med, "reset", "-q", "--hard", c3)
    assert [line for _, _, line in refine._landed(med)] == ["b", "d"]  # d stands, so c2 is undone, so b stands, and a is undone



def test_the_detached_pass_inherits_the_lock_and_runs_without_taking_it(served, monkeypatch):
    seen = {}
    monkeypatch.setattr(refine.subprocess, "Popen", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))
    refine.start("med")
    assert seen["cmd"][:2] == ["/usr/bin/caffeinate", "-i"] and seen["cmd"][-1] == "--attached" and seen["kw"]["pass_fds"]
    calls = []
    monkeypatch.setattr(refine, "_lock", lambda **kw: (_ for _ in ()).throw(AssertionError("took the lock")))
    refine.run(only="med", show=True, attached=True)


def _sweeps_med(served):
    """med takes the made-up area's pack, whose words include `sweep`."""
    from conftest import NOTES_PACK
    cfg, head = served["tmp"] / "config.toml", f'[domains.med]\nrepo = "{served["med"]}"\n'
    cfg.write_text(cfg.read_text().replace(head, head + f'pack = "{NOTES_PACK}"\n'))


def test_the_evidence_sweep_runs_before_the_passes_once_a_week_and_is_told_in_health(served, monkeypatch):
    from engram import relink
    _sweeps_med(served)
    swept, order = [], []
    results = iter([{"usd": 4.0, "confirmed": [1, 2], "stopped": True}])

    def sweep(repo, cap):
        swept.append((repo, cap))
        order.append("sweep")
        return next(results)
    monkeypatch.setattr(relink, "sweep", sweep)

    def runner(cmd, **kw):
        order.append("pass")
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 10.0, "result": "ok"}), "stderr": ""})()
    assert refine.run(dry_run=served["tmp"] / "plans", show=True)[0] == "med: would sweep the evidence, up to $10.00"
    assert not swept and not (served["data"] / "refine/ledger.jsonl").exists()  # a dry run runs and writes nothing
    lines = refine.run(runner=runner)
    assert order[0] == "sweep" and swept == [(served["med"], relink.SWEEP_CAP)]
    assert lines[0] == "med: evidence sweep stopped at its cap, 2 filed, $4.00; the next run picks up"
    assert lines[2] == "med: ok, $10.00; week $24.00 of $50"  # the money left counts the sweep; its row isn't the pass's
    rows = refine.ledger()
    assert [(r["repo"], r.get("job"), r["cost_usd"]) for r in rows] == [("med", "sweep", 4.0), ("engram", None, 10.0), ("med", None, 10.0)]
    assert "evidence sweep on med: stopped at its $10 cap, $4.00; the next run picks up" in refine.status()
    assert "weekly pass on med: ok, $10.00" in refine.status()
    refine.run("med", show=True)
    assert len(swept) == 1  # its own weekly mark: a --repo run or a catch-up doesn't repeat it
    (served["med"] / ".engram/engram.toml").write_text("[refine]\npaused = true\n")
    assert refine.run(show=True)[0] == "med: evidence sweep paused with the repo; skipped"


def test_a_failed_sweep_is_told_in_health_and_counts_its_cap(served, monkeypatch):
    from engram import relink
    _sweeps_med(served)

    def sweep(repo, cap):
        raise RuntimeError("usage limit")
    monkeypatch.setattr(relink, "sweep", sweep)
    refine.run(runner=lambda cmd, **kw: type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 1.0}), "stderr": ""})())
    assert "evidence sweep on med: FAILED (RuntimeError: usage limit), $10.00" in refine.status()
