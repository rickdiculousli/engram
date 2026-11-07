import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import PAGE_MD, NOTES_PACK, REWIRE, git, make_repo
from engram import config, hourly, pack, search, setup
from engram.cli import main


def notes_repo(path, name="notes"):
    """A record whose `.engram/` is the notes pack, committed."""
    repo = make_repo(path, {".engram/engram.toml": f'[domain]\nname = "{name}"\nevents_dir = "events"\n' + REWIRE,
                            ".engram/README.md": PAGE_MD, ".engram/__init__.py": (NOTES_PACK / "__init__.py").read_text()})
    return repo, git(repo, "rev-parse", "HEAD").strip()


def test_a_pinned_commit_loads_read_only_and_the_working_tree_never_runs(env):
    repo, sha = notes_repo(env["tmp"] / "notes")
    (repo / ".engram/__init__.py").write_text("raise SystemExit('the working tree ran')\n")  # inert until committed and pinned
    env["set_repo"]("notes", repo, pack=sha)
    p = pack.load("notes")
    assert p.prompts["file"].startswith("Below is a conversation") and pack.problem("notes") is None
    dest = env["data"] / "packs/notes" / sha
    assert (dest / "__init__.py").exists() and not (dest / "__init__.py").stat().st_mode & stat.S_IWUSR
    assert pack.extract("notes", repo, sha) == dest  # extracted once


def test_the_pack_tree_covers_the_packs_own_files_and_nothing_else_in_engram(env):
    repo, sha = notes_repo(env["tmp"] / "notes")
    own = subprocess.run(["git", "-C", str(repo), "mktree"], input=f"100644 blob {git(repo, 'rev-parse', f'{sha}:.engram/__init__.py').strip()}\t__init__.py\n",
                         capture_output=True, text=True, check=True).stdout.strip()
    assert pack.tree(repo, sha) == own  # git's own id for the pack's files alone
    for rel, text in {".engram/README.md": "## Jobs\n1. **New.** \"x\"\n", ".engram/specs/a.md": "---\nstatus: open\n---\n# A\n",
                      ".engram/engram.toml": "[index]\nexclude = [\"x\"]\n", ".engram/hooks/pre-commit": "#!/bin/sh\n"}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
        git(repo, "add", rel)
        git(repo, "commit", "-qm", rel)
        assert pack.tree(repo, "HEAD") == own, rel
    (repo / ".engram/tests").mkdir()
    (repo / ".engram/tests/test_x.py").write_text("def test_x():\n    pass\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a test")
    assert pack.tree(repo, "HEAD") != own  # the pack's tests are its own



def test_a_pin_extracts_inside_another_repos_git_hook(env, monkeypatch):
    repo, sha = notes_repo(env["tmp"] / "notes")
    other = make_repo(env["tmp"] / "other", {"a.txt": "a\n"})
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))  # what git sets while a hook of `other` runs
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git/index"))
    env["set_repo"]("notes", repo, pack=sha)
    assert pack.load("notes").prompts["file"] and pack.problem("notes") is None

def test_a_broken_pack_is_its_domains_alone_and_says_why(env, tmp_path):
    good, sha = notes_repo(tmp_path / "good")
    bad = tmp_path / "bad-pack"
    shutil.copytree(NOTES_PACK, bad)
    (bad / "__init__.py").write_text((bad / "__init__.py").read_text().replace("from engram.pack import Pack",
                                                                            "from engram.pack import Pack\nfrom engram import capture"))
    env["set_repo"]("notes", good, pack=sha)
    env["set_repo"]("other", make_repo(tmp_path / "other", {".engram/engram.toml": '[domain]\nname = "other"\n'}), pack=bad)
    assert pack.load("other") is pack.NONE and "engram.capture" in pack.problem("other")
    assert pack.load("notes").prompts["file"] and pack.problem("notes") is None


def test_a_pin_the_repo_lacks_stops_only_filing_and_shows_at_session_start(env, monkeypatch):
    repo, sha = notes_repo(env["tmp"] / "repos/notes")
    env["set_repo"]("notes", repo, pack=sha)
    monkeypatch.setattr("engram.capture.repo_of", lambda cwd: ("notes", repo))
    setup.setup(repo, env["tmp"] / "LaunchAgents", load=False)
    cfg = env["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text().replace(sha, "0" * 40))
    assert pack.load("notes") is pack.NONE and "no .engram/" in pack.problem("notes")
    assert "its pack didn't load" in hourly.session_start({"cwd": str(repo)})


def test_a_release_moves_the_tag_and_logs_the_pins_and_refuses_a_pack_the_gate_didnt_measure(env, tmp_path):
    import json
    import pytest
    from engram import review
    repo, sha = notes_repo(tmp_path / "notes")
    env["set_repo"]("notes", repo, pack=sha)
    code = make_repo(tmp_path / "engram", {"README.md": "x\n"})
    git(code, "tag", "release-x")
    rel = tmp_path / "release"
    git(tmp_path, "clone", "-q", str(code), str(rel))
    cfg = env["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text() + f'[review]\nrelease = "{rel}"\ngate = "notes"\ngate_base = "{tmp_path / "base.json"}"\n')
    with pytest.raises(SystemExit):
        review.advance("release-x", code, {"pack_tree": "0" * 40})
    assert review.advance("release-x", code, {"pack_tree": pack.tree(repo, sha)}) == "release-x"
    [logged] = [json.loads(l) for l in (env["data"] / "releases.jsonl").read_text().splitlines()]
    assert logged["tag"] == "release-x" and logged["pins"] == {"notes": sha}


ROWS_PACK = '''from engram.pack import Doc, Link, Pack, Source, Way


def rows(repo):
    a = Doc(ref="views.jsonl#a1", source="views", cls="row", kind="view", title="beds: first view", body="tomatoes need shade",
            pointer=f"{repo}/views.jsonl:1", author="{owner_id}", date="2026-10-01", stories="beds")
    b = Doc(ref="views.jsonl#a2", source="views", cls="row", kind="view", title="beds: second view", body="tomatoes need sun",
            pointer=f"{repo}/views.jsonl:2", author="{owner_id}", date="2026-10-05", stories="beds")
    return Source([a, b], [Link(b.ref, a.ref, "revises", "sun, not shade")], [Way("bed", "beds", ["raised beds", "B1"], [a.ref])])


def loose(repo):
    return Source([Doc(ref="loose:1", source="loose", cls="raw", kind="text", title="loose", body="a loose note on compost " * 400,
                       pointer=str(repo))])


pack = Pack(read={"views": rows, "loose": loose}, on_request=frozenset({"loose"}), summary_rules=("g1", "\\nRULES {owner}\\n", "AUDIT\\n"),
            health=lambda repo: "rows newer than this pack" if (repo / "NEWER").exists() else None)
'''


def test_a_pack_reads_what_core_cant_and_core_indexes_it_like_any_source(env, tmp_path, capsys):
    from engram import cli, search, summarize
    from engram.index import open_index
    from engram.paths import index_path
    repo = make_repo(tmp_path / "garden", {".engram/engram.toml": '[domain]\nname = "garden"\n[index]\nspines = ["beds/"]\n',
                                           "beds/beds/plan.md": "# Plan\nWhere the beds go.\n"})
    (tmp_path / "rows-pack").mkdir()
    (tmp_path / "rows-pack/__init__.py").write_text(ROWS_PACK)
    env["set_repo"]("garden", repo, pack=tmp_path / "rows-pack")
    cli.main(["ingest", "--domain", "garden"])
    idx = open_index(index_path("garden"), readonly=True)
    db = idx.db
    assert tuple(db.execute("SELECT author, date_key FROM doc WHERE ref = 'views.jsonl#a1'").fetchone()) == ("sam", "2026-10-01")
    assert {r for (r,) in db.execute("SELECT ref FROM on_story WHERE story = 'beds'")} == {
        "views.jsonl#a1", "views.jsonl#a2", "beds/beds/plan.md#Plan"}  # a file under a spine folder sits on that spine
    assert [tuple(r) for r in db.execute("SELECT family, rel FROM link")] == [("views", "revises")]
    assert {p for (p,) in db.execute("SELECT phrase FROM way WHERE key = 'beds'")} == {"raised beds"}  # too short to name it: B1
    assert not db.execute("SELECT 1 FROM doc WHERE source = 'loose'").fetchone()  # read on request only
    idx.close()
    [hit] = [h for h in search.search("tomatoes", ["garden"], limit=5) if h["ref"].startswith("views")]
    assert hit["ref"] == "views.jsonl#a2" and hit["unit"]["size"] == 2  # the revision and what it revised: one result
    cli.main(["ingest", "--domain", "garden", "--source", "loose"])
    assert "loose 3" in capsys.readouterr().out  # a long record is cut into chunks
    assert summarize.segment_version("garden") == summarize.SEGMENT_VERSION + "g1"
    assert "\nRULES Sam\n" in summarize._segment_prompt("garden", "turns", set(), "")
    (repo / "NEWER").write_text("")
    cli.main(["health"])
    out = capsys.readouterr().out
    assert "garden: rows newer than this pack" in out
    assert "garden: rewiring .engram/engram.toml has no [rewire]" in out  # every domain's drift, a repo engram only reads too
    with pytest.raises(SystemExit, match="doesn't say what to write down"):
        setup.setup(repo, env["tmp"] / "LaunchAgents", load=False)  # a pack that only reads is never filed for
    with pytest.raises(SystemExit, match="no pack reads a source called nothing"):
        cli.main(["ingest", "--source", "nothing"])


def test_the_example_shop_is_read_through_its_pack_and_never_filed_for(env, tmp_path, capsys):
    shop = tmp_path / "shop"
    shutil.copytree(Path(__file__).resolve().parents[1] / "examples/shop", shop)
    make_repo(shop, {})
    env["set_repo"]("shop", shop, pack=shop / ".engram", summaries=True)
    assert not pack.load("shop").prompts.get("file") and config.load()["shop"].summaries
    main(["ingest", "--domain", "shop"])
    hits = search.search("what's happening with the Hendersons", ["shop"], limit=3)
    assert hits and hits[0]["ref"] == "jobs.jsonl#oak-table"
    with pytest.raises(SystemExit, match="can't file"):
        setup.setup(shop)
