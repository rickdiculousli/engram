import json
import subprocess
import sys
import textwrap
import time

import pytest

from conftest import git, make_repo
from engram import config, dates, evalset, frontmatter, lint, search, usage
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


def test_frontmatter_keeps_text():
    fields, body = frontmatter.split("---\nticker: NO\ndate: 2026-10\nprice: 1.50\nflag: yes\nabout: [a/b, c]\n---\nbody\n")
    assert fields == {"ticker": "NO", "date": "2026-10", "price": "1.50", "flag": "yes", "about": ["a/b", "c"]}
    assert body == "body\n"
    again, _ = frontmatter.split(frontmatter.dump(fields) + "x")
    assert again == fields


def test_dates_at_any_precision():
    assert all(dates.valid(v) for v in ("2026", "2026-10", "2026-10-18", "not-sure"))
    assert not any(dates.valid(v) for v in ("~2026-10", "2026-13", "Oct 2026", "2026-10-32", "2026-02-30", "2025-02-29"))
    assert dates.key("2026-02-30") is None
    assert dates.key("2026-10") == "2026-10-01" and dates.key("not-sure") is None


def test_append_only_rejects_edits_and_deletes(tmp_path):
    repo = make_repo(tmp_path / "r", {"events/2026/10/a.md": "a\n", "events/2026/10/b.md": "b\n"})
    (repo / "events/2026/10/c.md").write_text("c\n")
    git(repo, "add", "-A")
    assert lint.staged_event_violations(repo) == []
    git(repo, "commit", "-q", "-m", "add c")
    (repo / "events/2026/10/a.md").write_text("changed\n")
    git(repo, "rm", "-q", "events/2026/10/b.md")
    git(repo, "add", "-A")
    bad = lint.staged_event_violations(repo)
    assert any(b.startswith("M") and b.endswith("a.md") for b in bad)
    assert any(b.startswith("D") and b.endswith("b.md") for b in bad)


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
    example = Path(__file__).resolve().parents[1] / "examples/notes"  # a folder inside engram's own checkout
    env["set_repo"]("outer", outer)
    env["set_repo"]("inner", outer / "inner")
    env["set_repo"]("notes", tmp_path / "elsewhere", remotes=["github.com:example/notes", "example/notes"])
    env["set_repo"]("garden", example)
    doms = config.load()
    assert resolve(outer / "inner/deep", doms) == ["inner"]  # a folder inside another git repo, the deepest match
    assert resolve(outer, doms) == ["outer"]
    assert resolve(example / "garden", doms) == ["garden"]
    assert resolve(clone, doms) == ["notes"]  # by its remote
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


def test_eval_matching_rules():
    assert evalset.matches("logs/a.md#2026-09-12 — x", "logs/a.md#2026-09-12 — x@2")
    assert evalset.matches("logs/a.md#Heading", "logs/a.md#heading~2")
    assert evalset.matches("logs/a.md", "logs/a.md#Anything")
    assert not evalset.matches("logs/a.md#One", "logs/a.md#Two")
    assert evalset.matches("rows.jsonl:3", "rows.jsonl:3") and not evalset.matches("rows.jsonl:3", "rows.jsonl:4")
    assert evalset.matches("session:s1:6", "session:s1:6@10")  # an exchange matches any chunk of it
    assert not evalset.matches("session:s1:6", "session:s1:60") and not evalset.matches("session:s1:6", "session:s1:6:r1")
    assert evalset.matches("session:s1", "session:s1:6@10") and evalset.matches("session:s1", "session:s1:6")
    assert evalset.file_of("session:s1:6@10") == evalset.file_of("session:s1:6") == "session:s1"
    assert evalset.matches("evidence/_staging.md#P-x@2", "evidence/_staging.md#P-x@2")
    assert not evalset.matches("evidence/_staging.md#P-x@2", "evidence/_staging.md#P-x@1")
    assert evalset.matches("ref/note.txt#@1", "ref/note.txt#@1") and not evalset.matches("ref/note.txt#@1", "ref/note.txt#@2")


def test_single_fact_measure_counts_any_record_code_calls_the_same():
    pairs = {}
    for a, b in [("e1", "logs/a.md#2026-03-27 — Visit")]:
        pairs.setdefault(a, set()).add(b)
        pairs.setdefault(b, set()).add(a)
    assert evalset.in_hand(["e1"], ["logs/a.md#2026-03-27 — Visit@2"], pairs)  # an entry and the section it came from
    assert evalset.in_hand(["logs/a.md#2026-03-27 — Visit"], ["e1"], pairs)
    assert evalset.in_hand(["e1#Findings"], ["logs/a.md#2026-03-27 — Visit"], pairs)  # an entry's section
    rows = {"now:med/x": ({"e2", "e3"}, "- Med X: since 2026-10-15 (dose changed 2026-10-21); 1 puff [e3]")}
    q = {"expect": ["e2"], "points": ["Med X first dose 2026-10-15."]}
    assert evalset.fact_in_hand(q, ["now:med/x"], [], pairs, rows) == "picture"  # its own line states the fact
    q = {"expect": ["e2"], "points": ["Med X first dose 2026-10-14."]}
    assert evalset.fact_in_hand(q, ["now:med/x"], [], pairs, rows) == ""  # on the chain, but the line doesn't say it
    assert evalset.in_hand(["consults/v.md#Findings"], ["consults/v.md"], pairs)  # a whole file holds its sections
    assert not evalset.in_hand(["e2"], ["e3"], pairs)  # two entries on one chain are not the same record
    assert not evalset.in_hand(["consults/v.md#Findings"], ["consults/v.md#Plan"], pairs)
    m = evalset.SOURCE_SECTION.match("reference/treatments/zentrafen.md, Titration History table (clean house)")
    assert (m["path"], m["section"]) == ("reference/treatments/zentrafen.md", "Titration History")  # a table row's entry
    assert evalset.SOURCE_SECTION.match("logs/brace.md, Treatment Plan (migrated)")["section"] == "Treatment Plan"
    assert not evalset.SOURCE_SECTION.match("migrated logs/sore-ankle.md:12")


def test_single_fact_measure_falls_back_to_the_keys_values_strictly():
    assert evalset.key_values("~2026-02-26 (a week after the ZMC visit), 10 mg; Treadmill normal; OrvEx 40 mg; "
                              "Sam and Claude agreed. FluXor 03-22") == ["2026-02-26", "03-22", "10", "40", "ZMC", "OrvEx", "FluXor"]
    assert evalset.states("took 10mg daily", "10") and not evalset.states("took 100 mg", "10")
    assert not evalset.states("2.10 ratio", "10") and evalset.states("on 2026-03-22", "03-22")
    assert evalset.states("orvexa xr", "Orvexa") and not evalset.states("Orvexas", "Orvexa")
    q = {"points": ["Orvexa 40 mg on 2026-10-21.", "Treadmill was normal per Dr. Vale."], "expect": []}
    assert evalset.points_in_hand(q, ["Orvexa 40 mg first dose 2026-10-21", "Vale: treadmill normal (Dr. Vale)"])
    assert not evalset.points_in_hand(q, ["Orvexa 40 mg", "first dose 2026-10-21", "Dr. Vale"])  # one record holds a point
    assert not evalset.points_in_hand({"points": ["it was normal, 2 of them"]}, ["normal 2"])  # nothing strong to pin it
    assert evalset.points_in_hand({"why": "Coach replied after the 2026-10-13 email."}, ["2026-10-13: coach replied"])
    assert [q["id"] for q in evalset.live([{"id": "a"}, {"id": "b", "dropped": "Sam: he knows it"}])] == ["a"]


def test_chain_links_and_grouping():
    q = {"links": [{"step": "visit", "refs": ["logs/a.md#V"]}, {"step": "test", "refs": ["ref/lab.txt", "logs/a.md#Lab"]}]}
    assert evalset.links_found(q, ["logs/a.md#V~2", "ref/lab.txt#Page 1"]) == [True, True]
    assert evalset.links_found(q, ["logs/a.md#V"]) == [True, False]
    rows = [{"kind": "lookup", "stories": ["ankle"], "pass": True, "found": True, "graded": True},
            {"kind": "revision", "stories": ["ankle", "nose"], "pass": False, "found": True, "graded": False}]
    g = evalset.by_group(rows, "stories")
    assert g["ankle"] == {"n": 2, "pass": 1, "found": 2, "graded": 1, "links": 0, "of": 0} and g["nose"]["n"] == 1



def test_a_usage_limit_leaves_questions_unrun_and_resumable(monkeypatch, tmp_path):
    limit = json.dumps({"type": "result", "is_error": True, "result": "You've hit your weekly limit"})
    monkeypatch.setattr(evalset.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, limit, ""))
    assert evalset._claude("q", {}, None, [])[:2] == ("", "You've hit your weekly limit")
    asked = []

    def one(q):
        asked.append(q["id"])
        if q["id"] == "b":
            return evalset._unrun(q, "limit")
        return {"id": q["id"], "kind": "lookup", "stories": ["ankle"], "hit": True, "file_hit": True, "links": [],
                "found": True, "graded": True, "pass": True, "queries": ["x"]}

    rows = evalset._pool(one, [{"id": i} for i in "abcd"], workers=1)
    assert asked == ["a", "b"] and [bool(r.get("error")) for r in rows] == [False, True, True, True]
    s = evalset.summarize(rows)
    assert s["n"] == 1 and s["unrun"] == 3 and s["pass_rate"] == 1.0
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"rows": rows}))
    done, todo = evalset.resume([{"id": i} for i in "abcde"], prior)
    assert [r["id"] for r in done] == ["a"] and [q["id"] for q in todo] == ["b", "c", "d", "e"]



def test_a_call_reports_its_tokens_and_what_it_read(monkeypatch):
    lines = [{"type": "assistant", "message": {"usage": {"input_tokens": 2, "cache_read_input_tokens": 1000}, "content": [
                 {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/r/logs/a.md"}},
                 {"type": "tool_use", "id": "t2", "name": "Grep", "input": {"pattern": "x", "output_mode": "content"}}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "/r/logs/b.md:3:x here"}]}},
             {"type": "assistant", "message": {"usage": {"input_tokens": 2, "cache_read_input_tokens": 1500}, "content": []}},
             {"type": "result", "result": "the answer", "usage": {"input_tokens": 4, "cache_read_input_tokens": 2500, "output_tokens": 50}}]
    out = "\n".join(json.dumps(l) for l in lines)
    monkeypatch.setattr(evalset.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    text, err, info = evalset._claude("q", {}, None, [])
    assert (text, err) == ("the answer", "") and info["tokens"] == 2554 and (info["base"], info["context"]) == (1002, 1502)
    assert info["reads"] == ["/r/logs/a.md"] and info["greps"] == ["/r/logs/b.md:3:x here"]
    assert evalset._cost(info) == {"tokens": 2554, "context": 1502, "retrieved": 500}
    grep_row = {"id": "a", "kind": "lookup", "stories": ["x"], "links": [], "found": True, "hit": True, "file_hit": True,
                "pass": True, **evalset._cost(info)}  # a grep row has no queries
    assert evalset.summarize([grep_row])["tokens_median"] == 2554


def test_seal_holds_out_a_share_of_each_story_and_kind():
    qs = [{"id": f"q{i}", "stories": ["ankle"], "kind": "lookup"} for i in range(6)]
    qs += [{"id": "t1", "stories": ["nose"], "kind": "revision"}, {"id": "r", "stories": [f"s{i}" for i in range(10)]}, {"id": "g"}]
    tune, held = evalset.seal(qs, "seed")
    assert len([q for q in held if q["stories"] == ["ankle"]]) == 2
    assert {"t1", "r", "g"} <= {q["id"] for q in tune}
    assert evalset.seal(qs, "seed") == (tune, held) and len(tune) + len(held) == len(qs)
    h = [q["id"] for q in held if q["stories"] == ["ankle"]][0]
    t = [q["id"] for q in tune if q.get("stories") == ["ankle"]][0]
    _, held2 = evalset.seal(qs, "seed", together=[[h, t]])
    assert {h, t} <= {q["id"] for q in held2}


def test_seal_by_story_holds_a_third_when_each_kind_has_one_question():
    qs = [{"id": f"q{i}", "stories": ["sol"], "kind": k} for i, k in enumerate(["lookup", "resume", "argument", "lineage", "due", "score"])]
    assert evalset.seal(qs, "seed")[1] == []
    tune, held = evalset.seal(qs, "seed", by_kind=False)
    assert len(held) == 2 and len(tune) == 4 and evalset.seal(qs, "seed", by_kind=False) == (tune, held)


def test_a_session_question_cannot_find_its_own_session(medical, monkeypatch):
    assert evalset.own_source({"origin": "session", "source": "047de7c4 2026-09-23"}) == "sessions:047de7c4"
    assert evalset.own_source({"origin": "synthetic"}) == ""
    refs = [r["ref"] for r in search.search("HbA1c", ["medical"], limit=5)]
    assert refs
    src = open_index(index_path("medical"), readonly=True).db.execute("SELECT source FROM doc WHERE ref = ?", (refs[0],)).fetchone()[0]
    monkeypatch.setenv("ENGRAM_EXCLUDE_SOURCES", src)
    assert refs[0] not in [r["ref"] for r in search.search("HbA1c", ["medical"], limit=5)]


def test_engram_link_joins_two_records_about_the_stories_of_its_ends(tmp_path):
    from engram.cli import main
    from engram.store import Store
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".engram").mkdir(exist_ok=True)
    (repo / ".engram/engram.toml").write_text('schema_version = 1\n[domain]\nname = "medical"\nevents_dir = "events"\ncommit = "none"\n'
                                      '[about]\nprefixes = ["story", "node"]\n[links.evidence]\nrels = ["disagrees"]\n')
    a = Store(repo).add({"title": "x", "date": "2026-01-10", "kind": "plan", "about": ["story/knee", "series/x"]}, "plan started 1/10\n")
    main(["link", a.id, "evidence:disagrees", "reference/brace.md#Notes", "--why", "- plan start: 01-10 against 2026-02", "--repo", str(repo)])
    [link] = Store(repo).events(kind="link")
    assert (link.fm["from"], link.fm["to"], link.fm["rel"], link.fm["author"]) == (a.id, "reference/brace.md#Notes", "disagrees", "claude")
    assert link.about == ["story/knee"]  # an entry end's stories; a document section isn't an about value
    main(["link", a.id, "evidence:disagrees", "node/C", "--why", "-", "--repo", str(repo)])
    assert Store(repo).events(kind="link")[-1].about == ["story/knee", "node/C"]
    with pytest.raises(SystemExit, match="already filed"):  # the same link twice is refused
        main(["link", a.id, "evidence:disagrees", "node/C", "--why", "again", "--repo", str(repo)])


def test_links_append_to_one_file_and_lint_allows_only_appends(tmp_path):
    import subprocess
    from engram import lint
    from engram.store import Store
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".engram").mkdir(exist_ok=True)
    (repo / ".engram/engram.toml").write_text('schema_version = 1\n[domain]\nname = "medical"\nevents_dir = "events"\n')
    st = Store(repo)
    a = st.add({"title": "x", "date": "2026-03-01", "kind": "symptom", "about": ["story/knee"]}, "sore\n")
    st.add({"title": "led to", "date": "2026-03-02", "kind": "link", "about": ["story/knee"], "from": a.id, "to": "b",
            "family": "timeline", "rel": "led-to"}, "- worse after")
    assert not list((repo / "events").rglob("*link*.md"))  # no file per link
    links = [e for e in Store(repo).events(kind="link")]
    assert len(links) == 1 and links[0].fm["from"] == a.id and links[0].body == "- worse after"
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
    for c in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "one"]):
        subprocess.run(["git", "-C", str(repo), *c], check=True, env=env)
    Store(repo).add({"title": "led to", "date": "2026-03-03", "kind": "link", "about": [], "from": "b", "to": "c",
                     "family": "timeline", "rel": "led-to"}, "")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    assert lint.staged_event_violations(repo) == []  # an appended line is fine
    p = repo / "events/links.jsonl"
    p.write_text(p.read_text().replace("worse after", "better after"))
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    assert lint.staged_event_violations(repo)  # an edited line isn't


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


def test_grep_reaches_an_entry_by_its_id_when_its_file_was_read_or_grepped(tmp_path, monkeypatch):
    info = {"reads": [str(tmp_path / "events/2026/10/20261022-010221-status-2b2f.md")],
            "greps": [f"{tmp_path}/notes/plan.md:3:Walk daily."], "tokens": 9, "context": 5, "base": 1}
    monkeypatch.setattr(evalset, "_claude", lambda *a, **kw: ("an answer", "", info))
    q = {"id": "q1", "question": "how did it go?", "expect": [],
         "links": [{"refs": ["20261022-010221-status-2b2f"]}, {"refs": ["notes/plan.md#Plan"]}, {"refs": ["20260101-000000-x-0000"]}]}
    row = evalset._grep_one(q, "medical", tmp_path, None)
    assert row["links"] == [True, True, False] and row["grepped"] == ["notes/plan.md"]
