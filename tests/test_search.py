import subprocess
import sys
import textwrap
import time

import pytest

from conftest import git, make_repo
from engram import config, evalset, search, usage
from engram.cli import main
from engram.index import open_index
from engram.paths import index_path
from engram.scope import resolve
from engram.sources import sections


RECORD = textwrap.dedent("""\
    # Log

    ## Knee brace
    Knee brace at K5/K6 complete, K2-K3 next.

    ## Supplements
    Zeta-R-XL 600mg daily, zentrafen 20mg at night.

    ## Trade
    ZQXA add on 2026-02-06; ZQX staking yield checked.

    ## Error
    error: ENOENT: no such file or directory, open 'kb.sqlite'

    ## Net A
    the upstream said connection refused by host after retry

    ## Net B
    host refused the connection then retried and said ok

    ## Lab
    HbA1c 5.4% fasting glucose normal
    """)


@pytest.fixture
def medical(env):
    repo = make_repo(env["tmp"] / "med", {"log.md": RECORD, "notes/plan.md": "# Plan\n\nWalk daily.\n",
                                          "rows.jsonl": '{"id": "x1", "date": "2026-07-17", "entity": "Med X"}\n'},
                     origin="git@github.com:example/med.git")
    env["set_repo"]("medical", repo, remotes=["github.com:example/med"])
    main(["ingest", "--domain", "medical"])
    return repo


@pytest.mark.parametrize("query, heading", [
    ("K5", "Knee brace"), ("K5/K6", "Knee brace"), ("20mg", "Supplements"), ("Zeta-R-XL", "Supplements"),
    ("2026-02-06", "Trade"), ("HbA1c", "Lab"), ("ENOENT", "Error"),
])
def test_tokens_find_the_right_section(medical, query, heading):
    top = search.search(query, ["medical"], limit=3)
    assert top and top[0]["ref"] == f"log.md#{heading}"


def test_a_question_reads_the_record_again_only_when_it_changed(medical, monkeypatch, capsys):
    import fcntl
    from datetime import timedelta
    from engram import ingest
    from engram.paths import data_path
    reads, real = [], ingest._record
    monkeypatch.setattr(ingest, "_record", lambda d, derived: reads.append((d, derived)) or real(d, derived))
    main(["search", "HbA1c", "--domain", "medical"])
    assert reads == []  # nothing changed since the ingest
    (medical / "notes/plan.md").write_text("# Plan\n\nWalk daily, and stretch the zygomorph.\n")  # saved, not committed
    capsys.readouterr()
    main(["search", "zygomorph", "--domain", "medical"])
    assert "notes/plan.md" in capsys.readouterr().out and reads == [("medical", False)]  # the files only: nothing built by searching
    main(["search", "zygomorph", "--domain", "medical"])
    assert len(reads) == 1
    monkeypatch.setattr(ingest, "STALE", timedelta(0))  # a pack's own sources aren't in git: those are read again by the clock
    main(["search", "zygomorph", "--domain", "medical"])
    assert len(reads) == 1
    monkeypatch.setattr(ingest, "_own_sources", lambda d: True)
    main(["search", "zygomorph", "--domain", "medical"])
    assert len(reads) == 2
    monkeypatch.setattr(ingest, "PATIENCE", 0.2)
    with open(data_path("{domain}.lock", "medical"), "a") as held:  # a read under way: a question waits a little, then answers
        fcntl.flock(held, fcntl.LOCK_EX)
        main(["search", "zygomorph", "--domain", "medical"])
        assert len(reads) == 2
    main(["search", "zygomorph", "--domain", "medical"])
    assert len(reads) == 3
    monkeypatch.undo()


def test_a_record_in_a_subfolder_of_a_bigger_repo_is_read_again_at_each_edit(env, capsys):
    outer = make_repo(env["tmp"] / "outer", {"notes/plan.md": "# Plan\n\nWalk daily.\n", "other/x.md": "# X\n\nElsewhere.\n"})
    env["set_repo"]("notes", outer / "notes")
    main(["ingest", "--domain", "notes"])
    for word in ("zygomorph", "quixotry"):  # a second edit to a file git already calls changed
        (outer / "notes/plan.md").write_text(f"# Plan\n\nWalk daily, and mind the {word}.\n")
        capsys.readouterr()
        main(["search", word, "--domain", "notes"])
        assert "plan.md" in capsys.readouterr().out, word
    (outer / "notes/plan.md").unlink()  # and a file that's gone
    capsys.readouterr()
    main(["search", "quixotry", "--domain", "notes"])
    assert "plan.md" not in capsys.readouterr().out


def test_claudes_window_is_the_projects_setting_then_the_users_then_the_default(tmp_path, monkeypatch):
    from pathlib import Path
    from engram import cli
    proj, home = make_repo(tmp_path / "proj", {"a.md": "x\n"}), tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (proj / ".claude").mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(proj)
    assert cli._window() == cli.WINDOW
    (home / ".claude/settings.json").write_text('{"bashOutputMaxChars": 50000}')
    assert cli._window() == 50000
    (proj / ".claude/settings.json").write_text('{"bashOutputMaxChars": 100000}')
    assert cli._window() == 100000
    (proj / ".claude/settings.json").write_text("{not json")  # one that won't parse says nothing
    assert cli._window() == 50000


def test_exact_phrase_excludes_reordered_words(medical):
    refs = [r["ref"] for r in search.search('"connection refused"', ["medical"])]
    assert refs == ["log.md#Net A"]


def test_jsonl_rows_are_records(medical):
    assert search.search("Med X", ["medical"])[0]["ref"] == "rows.jsonl:1"


def test_ingest_twice_changes_nothing(medical, env):
    idx = open_index(index_path("medical"))
    again = idx.sync_source(sections.SOURCE, sections.docs_for(config.load()["medical"]))
    idx.close()
    assert again["added"] == again["changed"] == again["removed"] == 0


def test_ingest_tracks_edits_and_removals(medical):
    (medical / "log.md").write_text(RECORD.replace("HbA1c 5.4%", "HbA1c 5.6%"))
    (medical / "notes/plan.md").unlink()
    idx = open_index(index_path("medical"))
    s = idx.sync_source(sections.SOURCE, sections.docs_for(config.load()["medical"]))
    idx.close()
    assert (s["changed"], s["removed"]) == (1, 1)
    assert "5.6%" in search.search("HbA1c", ["medical"])[0]["snip"]


def test_a_folder_outside_git_is_searched_and_its_hidden_files_skipped(env, tmp_path):
    notes = tmp_path / "notes"
    (notes / ".obsidian").mkdir(parents=True)
    (notes / ".obsidian/app.md").write_text("# Settings\n\nbasil\n")
    (notes / "beds.md").write_text("# Beds\n\n## South bed\nThe basil bolted.\n")
    env["set_repo"]("notes", notes, pack=None)
    main(["ingest", "--domain", "notes"])
    assert [r["ref"] for r in search.search("basil", ["notes"])] == ["beds.md#South bed"]
    assert resolve(notes, config.load()) == ["notes"]


def test_search_works_while_an_ingest_holds_a_write(medical, env, tmp_path):
    flag = tmp_path / "locked"
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import sqlite3, time, pathlib
        db = sqlite3.connect({str(index_path('medical'))!r}, isolation_level=None)
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE doc SET body = body || ' x' WHERE ref = 'log.md#Lab'")
        pathlib.Path({str(flag)!r}).write_text("1")
        time.sleep(5)
        db.execute("ROLLBACK")
    """)])
    for _ in range(100):
        if flag.exists():
            break
        time.sleep(0.05)
    assert flag.exists()
    assert search.search("HbA1c", ["medical"])[0]["ref"] == "log.md#Lab"
    holder.kill()


def test_scope_follows_the_repo_including_worktrees(medical, env, tmp_path):
    doms = config.load()
    assert resolve(medical, doms) == ["medical"]
    wt = tmp_path / "wt"
    git(medical, "worktree", "add", "-q", str(wt), "-b", "side")
    assert resolve(wt, doms) == ["medical"]
    with pytest.raises(SystemExit, match="not in a repo engram serves; known: medical, general; pass --domain"):
        resolve(tmp_path, doms)
    assert resolve(tmp_path, doms, "all") == list(config.load())
    assert resolve(medical, doms, "medical,general") == ["medical", "general"]


def test_scope_is_the_deepest_configured_folder_holding_cwd_then_the_repo_then_the_remote(env, tmp_path):
    from pathlib import Path
    outer = make_repo(tmp_path / "outer", {"inner/a.md": "# A\n", "inner/deep/b.md": "# B\n"})
    other = make_repo(tmp_path / "other", {"a.md": "# A\n"}, origin="git@github.com:example/notes-archive.git")
    clone = make_repo(tmp_path / "clone", {"a.md": "# A\n"}, origin="git@github.com:example/notes.git")
    theirs = make_repo(tmp_path / "theirs", {"a.md": "# A\n"}, origin="https://github.com/myexample/notes")
    hosted = make_repo(tmp_path / "hosted", {"a.md": "# A\n"}, origin="ssh://box/srv/git/papers.git")
    example = Path(__file__).resolve().parents[1] / "examples/notes"  # a folder inside engram's own checkout
    env["set_repo"]("outer", outer)
    env["set_repo"]("inner", outer / "inner")
    env["set_repo"]("notes", tmp_path / "elsewhere", remotes=["github.com:example/notes", "example/notes"])
    env["set_repo"]("garden", example)
    env["set_repo"]("papers", tmp_path / "away", remotes=["/srv/git/papers.git"])
    doms = config.load()
    assert resolve(outer / "inner/deep", doms) == ["inner"]  # a folder inside another git repo, the deepest match
    assert resolve(outer, doms) == ["outer"]
    assert resolve(example / "garden", doms) == ["garden"]
    assert resolve(clone, doms) == ["notes"]  # by its remote
    assert resolve(hosted, doms) == ["papers"]  # a remote that starts at a slash
    with pytest.raises(SystemExit):
        resolve(other, doms)  # notes-archive isn't notes
    with pytest.raises(SystemExit):
        resolve(theirs, doms)  # myexample/notes isn't example/notes


@pytest.mark.parametrize("call", [["search", "HbA1c"], ["timeline"], ["now"], ["theory"], ["lenses"]])
def test_outside_every_repo_a_scope_wide_read_says_so(medical, tmp_path, monkeypatch, capsys, call):
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    with pytest.raises(SystemExit, match="not in a repo engram serves; known: medical, general; pass --domain"):
        main(call)


def test_outside_every_repo_general_is_asked_for_by_name_and_a_ref_still_opens(medical, tmp_path, monkeypatch, capsys):
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    main(["search", "HbA1c", "--domain", "general"])
    assert "HbA1c" not in capsys.readouterr().out  # the general pile, not the medical record
    main(["show", "log.md#Lab"])
    assert "HbA1c 5.4%" in capsys.readouterr().out


def test_show_opens_its_own_repos_record_first_and_anothers_when_only_there(medical, env, tmp_path, monkeypatch, capsys):
    blog = make_repo(tmp_path / "blog", {"log.md": "# Log\n\n## Lab\nA post about the lab visit.\n"})
    env["set_repo"]("blog", blog)  # listed after medical
    main(["ingest", "--domain", "blog"])
    monkeypatch.chdir(blog)
    main(["show", "log.md#Lab"])
    assert "A post about the lab visit" in capsys.readouterr().out
    main(["show", "log.md#Supplements"])  # only in the medical record, which the blog draws on
    assert "Zeta-R-XL" in capsys.readouterr().out
    main(["show", "log.md#Lab", "--domain", "medical"])
    assert "HbA1c 5.4%" in capsys.readouterr().out


def test_search_and_open_are_logged(medical, monkeypatch, capsys):
    monkeypatch.setenv("ENGRAM_TAG", "t1")
    main(["search", "HbA1c", "--domain", "medical"])
    main(["show", "log.md#Lab", "--domain", "medical"])
    runs = usage.searches("medical", "t1")
    assert runs and runs[0]["results"][0]["ref"] == "log.md#Lab"
    assert "HbA1c 5.4%" in capsys.readouterr().out


def test_a_session_question_cannot_find_its_own_session(medical, monkeypatch):
    assert evalset.own_source({"origin": "session", "source": "047de7c4 2026-09-23"}) == "sessions:047de7c4"
    assert evalset.own_source({"origin": "synthetic"}) == ""
    refs = [r["ref"] for r in search.search("HbA1c", ["medical"], limit=5)]
    assert refs
    src = open_index(index_path("medical"), readonly=True).db.execute("SELECT source FROM doc WHERE ref = ?", (refs[0],)).fetchone()[0]
    monkeypatch.setenv("ENGRAM_EXCLUDE_SOURCES", src)
    assert refs[0] not in [r["ref"] for r in search.search("HbA1c", ["medical"], limit=5)]


def test_synonyms_expand_one_way_and_skip_words_the_question_uses():
    conf = {"synonyms": {"weight": 0.5, "same": {"pt": ["physical therapy"]},
                         "words": {"restart": ["renew", "resume"], "stop": ["quit", "drop"]}}}
    assert search.synonyms(conf, "when did i restart pt") == [('"physical therapy"', 1.0), ('"renew" OR "resume"', 0.5)]
    assert search.synonyms(conf, "which drops am i on") == []  # one way: "drops" never reads as "stop"
    assert search.synonyms(conf, "when was it stopped, or did i quit") == [('"drop"', 0.5)]  # -ed allowed; quit already asked
    assert search.synonyms({}, "restart") == []


def test_a_synonym_adds_to_the_score_and_never_filters(medical, env):
    (medical / ".engram").mkdir(exist_ok=True)
    (medical / ".engram/engram.toml").write_text('schema_version = 1\n[domain]\nname = "medical"\n[synonyms]\nweight = 0.5\n'
                                         '[synonyms.words]\nwalking = ["walk"]\n')
    refs = [r["ref"] for r in search.search("walking plan", ["medical"])]
    assert refs[0] == "notes/plan.md#Plan"  # "Walk daily." found through the synonym; "plan" alone found it before too
    assert search.search("glucose", ["medical"])[0]["ref"] == "log.md#Lab"
