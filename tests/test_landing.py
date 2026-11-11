"""A pass's change lands only through a fresh review, and a pass that stopped short reads as failed."""
import json
import subprocess

import pytest

from conftest import git, make_repo
from engram import landing, refine


@pytest.fixture
def repo(env):
    tmp = env["tmp"]
    remote = tmp / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    r = make_repo(tmp / "notes", {".engram/README.md": "## Jobs\n", "a.txt": "one\n"})
    git(r, "branch", "-M", "main")
    git(r, "remote", "add", "origin", str(remote))
    git(r, "push", "-q", "origin", "main")
    cfg = tmp / "config.toml"
    cfg.write_text(f'[refine]\nrepo = "{r}"\nweekly_cap = 50\n' + (cfg.read_text() if cfg.exists() else ""))
    return r


def change(repo, name="tidy", files=None):
    w = repo.parent / f"wt-{name}"
    git(repo, "worktree", "add", "-q", "-b", f"refinement/2026-01-01-{name}", str(w), "main")
    for f, text in (files or {"a.txt": "two\n"}).items():
        (w / f).parent.mkdir(parents=True, exist_ok=True)
        (w / f).write_text(text)
    git(w, "add", "-A")
    git(w, "commit", "-q", "-m", f"{name}\n\nRefinement: the line the owner reads")
    return w


def reviewer(*replies, cost=1.25):
    """A stand-in reviewer: answers in turn, and keeps what it was asked."""
    calls, replies = [], iter(replies)

    def run(cmd, **kw):
        calls.append({"cmd": cmd, "prompt": kw["input"]})
        reply = next(replies)
        return type("P", (), {"stdout": json.dumps({"total_cost_usd": cost, "result": reply})})()
    return run, calls


PASS = '{"verdict": "pass", "findings": []}'
OBJECT = '{"verdict": "object", "findings": [{"where": "a.txt:1", "what": "wrong"}]}'


def test_a_change_with_no_passing_review_doesnt_land_and_one_that_passed_does(repo):
    w = change(repo)
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)
    run, calls = reviewer(PASS)
    assert landing.review(w, runner=run)[0]
    c = calls[0]
    assert "the line the owner reads" in c["prompt"] and "+two" in c["prompt"] and str(w) in c["prompt"]
    assert c["cmd"][c["cmd"].index("--tools") + 1] == "Read,Grep,Glob"  # it can only read
    assert "landed" in landing.land(w)
    assert (repo / "a.txt").read_text() == "two\n" and not w.exists()
    assert git(repo, "rev-parse", "origin/main") == git(repo, "rev-parse", "main")
    assert not git(repo, "branch", "--list", "refinement/*")


def test_one_fix_is_allowed_and_a_second_objection_ends_it(repo):
    w = change(repo)
    run, calls = reviewer(OBJECT, OBJECT, PASS)
    passed, told = landing.review(w, runner=run)
    assert not passed and "a.txt:1" in told and "One more review" in told
    (w / "a.txt").write_text("three\n")
    git(w, "commit", "-qa", "--amend", "--no-edit")
    passed, told = landing.review(w, runner=run)
    assert not passed and "write it as a spec" in told
    assert "a.txt:1: wrong" in calls[1]["prompt"]  # the second checks the first's findings were fixed
    with pytest.raises(SystemExit, match="had its 2 reviews"):
        landing.review(w, runner=run)
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)


def test_a_fix_after_the_pass_needs_its_own_review_and_a_clean_rebase_doesnt(repo):
    w = change(repo)
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    (repo / "b.txt").write_text("elsewhere\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-qm", "the branch moved")
    git(w, "rebase", "-q", "main")
    assert "landed" in landing.land(w)
    w = change(repo, "more", {"c.txt": "c\n"})
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    (w / "c.txt").write_text("changed after its review\n")
    git(w, "commit", "-qa", "--amend", "--no-edit")
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)


@pytest.mark.parametrize("reply", ["no json here", '{"verdict": "maybe"}', '{"findings": []}', ""])
def test_a_reply_that_isnt_a_clear_pass_doesnt_pass(repo, reply):
    w = change(repo)
    assert not landing.review(w, runner=reviewer(reply)[0])[0]
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)


def test_a_reviewer_that_fails_or_times_out_doesnt_pass_and_costs_its_cap(repo):
    w = change(repo)

    def hung(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    assert not landing.review(w, runner=hung)[0]
    assert refine.reviews()[-1]["verdict"] == "none" and refine.spent([], refine.week()) == landing.CAP


def test_reviews_count_toward_the_week_and_one_it_cant_pay_for_is_refused(repo):
    run, _ = reviewer(PASS)
    landing.review(change(repo), runner=run)
    assert refine.spent([], refine.week()) == 1.25
    (refine._dir() / "ledger.jsonl").write_text(json.dumps({"week": refine.week(), "repo": "x", "dry_run": False, "ok": True,
                                                            "started": "t", "cost_usd": 47.0}) + "\n")
    with pytest.raises(SystemExit, match="can't pay"):
        landing.review(change(repo, "next", {"d.txt": "d\n"}), runner=reviewer(PASS)[0])


def test_a_branch_of_only_specs_lands_with_no_review(repo):
    w = change(repo, "spec", {".engram/specs/2026-01-01-idea.md": "---\nstatus: open\n---\n# Idea\n"})
    assert "landed" in landing.land(w)


def test_uncommitted_work_is_neither_reviewed_nor_landed(repo):
    w = change(repo)
    (w / "a.txt").write_text("not committed\n")
    with pytest.raises(SystemExit, match="uncommitted"):
        landing.review(w, runner=reviewer(PASS)[0])


def passing(result="All done."):
    return lambda cmd, **kw: type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 2.0, "result": result}), "stderr": ""})()


def spec(repo, status="approved", extra=""):
    p = repo / ".engram/specs/2026-01-01-idea.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nstatus: {status}\n{extra}---\n# The idea in plain words\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "the spec")
    return p


def test_a_pass_that_reports_fine_with_an_approved_spec_unsettled_is_failed_and_told(repo, env):
    spec(repo)
    run = passing("Holding the commit until the review reports. Running: the review.")
    lines = refine.run("engram", runner=run, attached=True)
    assert any(": failed," in line for line in lines)
    row = [r for r in refine.ledger() if not r.get("job")][-1]
    assert not row["ok"] and "approved and not built: The idea in plain words" in row["error"]
    assert any("FAILED" in line and "The idea" in line for line in refine.status())


def test_a_page_names_the_pass_that_didnt_finish(repo):
    calls = []

    def run(cmd, **kw):
        calls.append(kw.get("input"))
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 2.0, "result": "<!doctype html><html>p</html>"}), "stderr": ""})()
    spec(repo)
    refine.run("engram", runner=run, attached=True)
    page = next(c for c in calls if c)
    assert "A pass that didn't finish" in page and "The idea in plain words" in page


def test_a_settled_spec_and_a_clean_end_leave_the_pass_ok(repo):
    spec(repo, "approved", "blocked: >-\n  it needs something\n")
    refine.run("engram", runner=passing(), attached=True)
    assert [r for r in refine.ledger() if not r.get("job")][-1]["ok"]


def test_work_left_on_a_branch_or_landed_past_the_review_fails_the_pass(repo):
    w = change(repo)
    head = refine._head(repo)
    assert refine._unfinished(repo, [], head) == ["work left unlanded on refinement/2026-01-01-tidy"]
    landing.review(w, runner=reviewer(PASS)[0])
    landing.land(w)
    assert refine._unfinished(repo, [], head) == []  # reviewed and landed
    (repo / "e.txt").write_text("e\n")
    git(repo, "add", "e.txt")
    git(repo, "commit", "-qm", "straight in\n\nRefinement: none: slipped past")
    assert refine._unfinished(repo, [], head)[0].startswith("landed with no review: ")


def test_a_spec_the_owner_approved_during_the_pass_isnt_held_against_it(repo):
    head = refine._head(repo)
    spec(repo)
    assert refine._unfinished(repo, [], head) == []


def test_a_change_of_only_whitespace_or_of_the_owners_line_after_the_pass_needs_a_review(repo):
    w = change(repo, "indent", {"p.py": "if x:\n    run()\n"})
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    (w / "p.py").write_text("if x:\nrun()\n")  # out of its `if`, which a whitespace-blind mark wouldn't see
    git(w, "commit", "-qa", "--amend", "--no-edit")
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)
    w = change(repo, "told", {"t.txt": "t\n"})
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    git(w, "commit", "-q", "--amend", "-m", "told\n\nRefinement: something else entirely")
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)


@pytest.mark.parametrize("files, note", [
    ({".engram/specs/x.md": "---\nstatus: approved\n---\n# Self\n"}, "a new spec it approved itself"),
    ({".engram/specs/x.md": "---\nstatus: built\n---\n# Self\n"}, "a new spec already built"),
    ({".engram/specs/x.md": "no front matter\n"}, "not a spec"),
    ({".engram/specs/x.md": "---\nstatus: [open\n---\n"}, "front matter that won't read"),
    ({".engram/specs/tool.py": "x = 1\n"}, "not markdown"),
    ({".engram/specs/sub/x.md": "---\nstatus: open\n---\n"}, "a folder the page doesn't read"),
    ({".engram/specs/x.md": "---\nstatus: open\n---\n", "a.txt": "two\n"}, "something beside the spec"),
])
def test_only_a_new_open_spec_skips_the_review(repo, files, note):
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(change(repo, files=files))


def test_any_change_to_a_spec_already_there_is_reviewed(repo):
    p = spec(repo, "open")
    rel, text = ".engram/specs/2026-01-01-idea.md", p.read_text()
    for name, new in (("built", text.replace("open", "built")), ("edit", text + "more\n")):
        with pytest.raises(SystemExit, match="no review passed"):
            landing.land(change(repo, name, {rel: new}))
    w = repo.parent / "wt-gone"
    git(repo, "worktree", "add", "-q", "-b", "refinement/2026-01-01-gone", str(w), "main")
    git(w, "rm", "-q", rel)
    git(w, "commit", "-qm", "gone")
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(w)
    moved = repo.parent / "wt-moved"
    git(repo, "worktree", "add", "-q", "-b", "refinement/2026-01-01-moved", str(moved), "main")
    git(moved, "mv", "a.txt", ".engram/specs/a.md")
    git(moved, "commit", "-qm", "a rename into specs")
    with pytest.raises(SystemExit, match="no review passed"):
        landing.land(moved)


def test_a_new_spec_with_an_unusual_name_lands(repo):
    assert "landed" in landing.land(change(repo, files={".engram/specs/idée.md": "---\nstatus: open\n---\n# Idée\n"}))


def test_the_review_trusts_only_the_repos_own_copy_of_an_approved_spec(repo):
    p = spec(repo, "open")
    w = change(repo)
    with pytest.raises(SystemExit, match="isn't a spec the owner approved"):
        landing.review(w, p, runner=reviewer(PASS)[0])
    with pytest.raises(SystemExit, match="isn't a spec the owner approved"):
        landing.review(w, w / "a.txt", runner=reviewer(PASS)[0])
    p.write_text("---\nstatus: approved\n---\n# The idea\n")
    run, calls = reviewer(OBJECT, OBJECT)
    landing.review(w, p, runner=run)
    assert str(p) in calls[0]["prompt"]
    assert "`blocked:`" in landing.review(w, p, runner=run)[1]


def test_a_reply_marked_an_error_doesnt_pass_though_it_says_pass(repo):
    w = change(repo)
    run = lambda cmd, **kw: type("P", (), {"stdout": json.dumps({"is_error": True, "total_cost_usd": 1.0, "result": PASS})})()
    assert not landing.review(w, runner=run)[0]


def test_a_running_passs_held_cap_doesnt_block_its_reviews(repo):
    (refine._dir() / "ledger.jsonl").write_text(json.dumps({"week": refine.week(), "repo": "x", "dry_run": False, "ok": False,
                                                            "running": True, "started": "t", "cost_usd": 50.0}) + "\n")
    assert landing.review(change(repo), runner=reviewer(PASS)[0])[0]


def test_a_push_that_fails_leaves_it_landed_for_the_next_push(repo):
    w = change(repo)
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    url = git(repo, "remote", "get-url", "origin").strip()
    git(repo, "remote", "set-url", "origin", str(repo.parent / "gone.git"))
    with pytest.raises(SystemExit, match="push failed"):
        landing.land(w)
    assert (repo / "a.txt").read_text() == "two\n" and not w.exists()
    assert refine._unfinished(repo, [], git(repo, "rev-parse", "HEAD~1").strip()) == []
    git(repo, "remote", "set-url", "origin", url)
    next_one = change(repo, "next", {"n.txt": "n\n"})
    assert landing.review(next_one, runner=reviewer(PASS)[0])[0] and "landed" in landing.land(next_one)
    assert git(repo, "rev-parse", "origin/main") == git(repo, "rev-parse", "main")  # the next push carried it


def test_under_a_pass_the_ledger_and_reviews_are_the_real_folders(repo, monkeypatch, tmp_path):
    real = tmp_path / "real-refine"
    monkeypatch.setenv("ENGRAM_REFINE", str(real))
    assert refine._dir() == real and real.is_dir()
    landing.review(change(repo), runner=reviewer(PASS)[0])
    assert (real / "reviews.jsonl").exists()
    monkeypatch.delenv("ENGRAM_REFINE")
    assert not refine.reviews()


def test_a_failure_with_no_page_this_week_reaches_the_next_page_once(repo, monkeypatch):
    monkeypatch.setattr(refine.sys, "platform", "darwin")  # a page that opens is marked shown
    wk = refine.week()
    rows = [{"week": "2026-01-03", "repo": "engram", "started": "t", "dry_run": False, "ok": False, "error": "it left a spec", "cost_usd": 0.1},
            {"week": wk, "repo": "engram", "started": "u", "dry_run": False, "ok": False, "error": "free", "cost_usd": 0.1}]
    asked = []

    def run(cmd, **kw):
        asked.append(kw.get("input"))
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 0.1, "result": "<!doctype html><html>p</html>"})})()
    refine.digest({"engram": repo}, 2.0, run, rows)
    assert "it left a spec" in asked[0] and "free" not in asked[0].split("# In ")[1]
    (refine._dir() / "digests" / f"{wk}.html").unlink()
    asked.clear()
    assert refine.digest({"engram": repo}, 2.0, run, rows[:1]) == (0.0, "") and not asked


def test_a_pass_stopped_mid_run_is_named_though_it_gave_no_reason(repo):
    rows = [{"week": refine.week(), "repo": "engram", "started": "t", "dry_run": False, "ok": False, "running": True, "cost_usd": 20.0}]
    assert refine._failures(rows, set())["engram"][1] == "it stopped before it finished"


def test_a_merge_that_cant_apply_leaves_nothing_done(repo):
    w = change(repo)
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    (repo / "a.txt").write_text("the owner is editing this\n")
    with pytest.raises(SystemExit, match="merge"):
        landing.land(w)
    assert git(repo, "rev-parse", "origin/main") == git(repo, "rev-parse", "main") and w.exists()
    assert (repo / "a.txt").read_text() == "the owner is editing this\n"
    git(repo, "checkout", "a.txt")
    assert "landed" in landing.land(w)

def test_a_diff_that_isnt_utf8_is_reviewed_and_lands(repo):
    w = repo.parent / "wt-latin"
    git(repo, "worktree", "add", "-q", "-b", "refinement/2026-01-01-latin", str(w), "main")
    (w / "old.csv").write_bytes("caf\xe9,1\n".encode("latin-1"))
    git(w, "add", "-A")
    git(w, "commit", "-qm", "latin\n\nRefinement: none: a file")
    assert landing.review(w, runner=reviewer(PASS)[0])[0]
    assert "landed" in landing.land(w)


def test_a_build_on_request_builds_only_whats_approved_and_leaves_the_weeks_pass_to_run(repo):
    spec(repo)
    asked = []

    def run(cmd, **kw):
        asked.append(cmd)
        p = repo / ".engram/specs/2026-01-01-idea.md"
        p.write_text(p.read_text().replace("status: approved", "status: built"))
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"total_cost_usd": 2.0, "result": "built"}), "stderr": ""})()
    lines = refine.run("engram", runner=run, attached=True, approved=True)
    assert len(asked) == 1 and "mode=approved" in asked[0][2] and "ok" in lines[0]  # no page
    row = refine.ledger()[-1]
    assert row["job"] == refine.BUILD and row["ok"]
    assert (refine._dir() / f"runs/{refine.week()}/engram-build.md").exists()
    assert refine.status() == ["build on request on engram: ok, $2.00", "weekly pass on engram: not run this week"]
    assert "mode=land" in refine.run(show=True)[0]  # the week's pass still runs
    assert refine.spent(refine.ledger(), refine.week()) == 2.0


def test_a_build_on_request_that_stops_short_fails_and_reaches_the_next_page(repo):
    spec(repo)
    refine.run("engram", runner=passing("Running: the review."), attached=True, approved=True)
    row = refine.ledger()[-1]
    assert not row["ok"] and "approved and not built" in row["error"]
    assert "The idea in plain words" in next(iter(refine._failures(refine.ledger(), set()).values()))[1]


def test_a_build_on_request_with_nothing_approved_starts_nothing(repo):
    with pytest.raises(SystemExit, match="no approved spec"):
        refine.start("engram", approved=True)


def test_a_build_on_request_isnt_failed_by_work_it_was_told_to_leave(repo):
    w = change(repo)
    head = refine._head(repo)
    assert refine._unfinished(repo, [], head, refine._branches(repo)) == []
    new = change(repo, "new", {"z.txt": "z\n"})
    assert refine._unfinished(repo, [], head, ["refinement/2026-01-01-tidy"]) == ["work left unlanded on refinement/2026-01-01-new"]
    assert w.exists() and new.exists()


def test_a_killed_build_reads_as_stopped_not_running(repo):
    (refine._dir() / "ledger.jsonl").write_text(json.dumps({"week": refine.week(), "repo": "engram", "job": refine.BUILD, "dry_run": False,
                                                            "ok": False, "running": True, "started": "t", "cost_usd": 40.0}) + "\n")
    assert refine.status()[0] == "build on request on engram: stopped mid-run, $40.00"


def test_a_build_on_request_wont_start_on_a_status_not_yet_committed(repo):
    p = spec(repo, "open")
    p.write_text(p.read_text().replace("status: open", "status: approved"))
    with pytest.raises(SystemExit, match="uncommitted"):
        refine.start("engram", approved=True)


def test_a_blocked_spec_is_named_as_why_nothing_starts(repo):
    spec(repo, "approved", "blocked: >-\n  it needs something\n")
    with pytest.raises(SystemExit, match="One marked `blocked:` says why"):
        refine.start("engram", approved=True)
