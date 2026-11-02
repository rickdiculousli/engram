import json

import pytest

from conftest import git, make_repo
from engram import fix, setup
from engram.store import Store

WRONG = "---\nid: {id}\ntitle: Earlier cramp\ndate: 2026-10-07\nkind: observation\n---\n- Earlier cramp\n"


@pytest.fixture
def rec(tmp_path, env):
    a, b = "20261024-124456-observation-87c0", "20261024-194408-observation-49b6"
    link = {"id": "20261024-194411-link-379f", "kind": "link", "from": b, "to": a, "family": "evidence", "rel": "revises"}
    keep = {"id": "20261024-194412-link-aaaa", "kind": "link", "from": a, "to": "notes/x.md", "family": "evidence", "rel": "strengthens"}
    repo = make_repo(tmp_path / "rec", {".engram/engram.toml": '[domain]\nname = "medical"\n',
                                        f"events/2026/10/{a}.md": WRONG.format(id=a),
                                        f"events/2026/10/{b}.md": WRONG.format(id=b).replace("2026-10-07", "not-sure"),
                                        "events/links.jsonl": json.dumps(link) + "\n" + json.dumps(keep) + "\n"})
    git(repo, "config", "core.hooksPath", ".engram/hooks")
    (repo / ".engram/hooks").mkdir(parents=True)
    (repo / ".engram/hooks/pre-commit").write_text(f"#!/bin/sh\nexec {setup.engram_cmd()[0]} lint --staged --repo \"$(git rev-parse --show-toplevel)\"\n")
    (repo / ".engram/hooks/pre-commit").chmod(0o755)
    git(repo, "add", ".engram/hooks")
    git(repo, "commit", "-qm", "hooks")
    return repo, f"events/2026/10/{a}.md", f"events/2026/10/{b}.md", link["id"]


def test_a_fix_edits_and_deletes_listed_events_in_one_commit_the_lint_lets_through(rec):
    repo, wrong, extra, link = rec
    (repo / wrong).write_text((repo / wrong).read_text().replace("date: 2026-10-07", "date: not-sure"))
    (repo / extra).unlink()
    git(repo, "add", "-A")  # an ordinary commit of the same change is refused
    assert git(repo, "diff", "--cached", "--name-only") and \
        __import__("subprocess").run(["git", "-C", str(repo), "commit", "-qm", "x"], capture_output=True).returncode
    git(repo, "reset", "-q")
    with pytest.raises(fix.Refused, match="point at a deleted event"):
        fix.apply(Store(repo), [wrong, extra], "a date never said")
    done = fix.apply(Store(repo), [wrong, extra], "a date never said", [link])
    assert set(done) == {wrong, extra, "events/links.jsonl"}
    assert git(repo, "status", "--porcelain").strip() == ""
    assert "Engram-Fix: a date never said" in git(repo, "log", "-1", "--format=%B")
    assert [json.loads(l)["id"] for l in (repo / "events/links.jsonl").read_text().splitlines()] == ["20261024-194412-link-aaaa"]
    assert [e.fm["date"] for e in Store(repo).events() if e.kind != "link"] == ["not-sure"]


def test_a_fix_refuses_what_it_was_not_given(rec):
    repo, wrong, extra, link = rec
    with pytest.raises(fix.Refused, match="unchanged"):
        fix.apply(Store(repo), [wrong], "x")
    (repo / wrong).write_text((repo / wrong).read_text().replace("date: 2026-10-07", "date: not-sure"))
    (repo / extra).write_text((repo / extra).read_text() + "- more\n")
    with pytest.raises(fix.Refused, match="other event files are changed"):
        fix.apply(Store(repo), [wrong], "x")
    git(repo, "checkout", "--", extra)
    (repo / wrong).write_text((repo / wrong).read_text().replace("id: 20261024", "id: 20991024"))
    with pytest.raises(fix.Refused, match="its own id"):
        fix.apply(Store(repo), [wrong], "x")
    (repo / wrong).write_text((repo / wrong).read_text().replace("id: 20991024", "id: 20261024"))
    with pytest.raises(fix.Refused, match="no such link"):
        fix.apply(Store(repo), [wrong], "x", ["nope"])
    assert "Engram-Fix" not in git(repo, "log", "-1", "--format=%B")


def test_a_link_drops_without_paths_and_a_sweep_run_drops_whole_and_leaves_the_weekly_page(rec):
    from engram import refine
    repo, _, _, link = rec
    done = fix.apply(Store(repo), [], "a link the machinery got wrong", [link])
    assert done == ["events/links.jsonl"] and link not in (repo / "events/links.jsonl").read_text()
    swept = [{"id": f"20261101-0900{i:02d}-link-s{i}", "kind": "link", "from": "notes/x.md", "to": "loop/1", "family": "evidence",
              "rel": "strengthens", "by": "claude", "author": "engram-sweep"} for i in range(3)]
    with open(repo / "events/links.jsonl", "a") as fh:
        fh.writelines(json.dumps(x) + "\n" for x in swept)
    git(repo, "add", "events/links.jsonl")
    git(repo, "commit", "-qm", "engram: evidence swept\n\nRefinement: 3 records now show for or against the theory")
    run = git(repo, "rev-parse", "HEAD").strip()
    assert [line for _, _, line in refine._landed(repo)] == ["3 records now show for or against the theory"]
    with pytest.raises(fix.Refused, match="filed no sweep link"):
        fix.apply(Store(repo), [], "x", drop_run="HEAD~1")
    fix.apply(Store(repo), [], "x", [swept[0]["id"]])  # one already dropped by hand: the run drops what's left
    fix.apply(Store(repo), [], "the sweep linked the wrong loop", drop_run=run[:8])
    assert [json.loads(l)["id"] for l in (repo / "events/links.jsonl").read_text().splitlines()] == ["20261024-194412-link-aaaa"]
    assert f"This reverts commit {run}." in git(repo, "log", "-1", "--format=%B") and refine._landed(repo) == []
    with pytest.raises(fix.Refused, match="name event files"):
        fix.apply(Store(repo), [], "x")


def test_one_fix_drops_several_sweep_runs_and_the_weekly_page_loses_both_lines(rec):
    from engram import refine
    repo = rec[0]
    runs = []
    for k in range(2):
        with open(repo / "events/links.jsonl", "a") as fh:
            fh.write(json.dumps({"id": f"20261101-0900{k:02d}-link-r{k}", "kind": "link", "from": "notes/x.md", "to": "loop/1",
                                 "family": "evidence", "rel": "strengthens", "by": "claude", "author": "engram-sweep"}) + "\n")
        git(repo, "add", "events/links.jsonl")
        git(repo, "commit", "-qm", f"engram: evidence swept\n\nRefinement: run {k}")
        runs.append(git(repo, "rev-parse", "HEAD").strip())
    assert len(refine._landed(repo)) == 2
    fix.apply(Store(repo), [], "the backlog was wrong", drop_run=runs)
    assert "engram-sweep" not in (repo / "events/links.jsonl").read_text() and refine._landed(repo) == []
