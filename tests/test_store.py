import json
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from engram.store import Store, event_id

LOG = textwrap.dedent("""\
    # Example — Treatment Log

    ## Background
    Why it matters, 2026-01-01 mentioned in prose.

    ## Procedure Log

    ### 2026-03-01 — First session

    - went well
    - mild soreness

    ### 2026-03-01 — Same day, second note
    - written after the first

    ### 2026-02-10 (approx; reported 2026-02-20) — Filed out of order
    - earlier date

    ## Symptom Log

    ### 2026-03-05 — Soreness gone
    - after 4 days
    """)
ENTRIES = [  # the log's dated entries, as written: heading, run, kind, body
    ("### 2026-03-01 — First session", "Procedure Log", "procedure", "\n- went well\n- mild soreness"),
    ("### 2026-03-01 — Same day, second note", "Procedure Log", "procedure", "- written after the first"),
    ("### 2026-02-10 (approx; reported 2026-02-20) — Filed out of order", "Procedure Log", "procedure", "- earlier date"),
    ("### 2026-03-05 — Soreness gone", "Symptom Log", "symptom", "- after 4 days"),
]


def file_log(st: Store) -> list[str]:
    """The example log as a page, and each of its entries as an event; their ids, in the order written."""
    (st.root / "logs/example.md").write_text(LOG)
    out = []
    for n, (heading, run, kind, body) in enumerate(ENTRIES):
        day = heading.split()[1]
        out.append(st.add({"title": heading.split(" — ")[1], "date": day, "heading": heading, "recorded": f"2026-10-21T12:00:0{n}-07:00",
                           "kind": kind, "about": ["series/example"], "run": run, "level": "3", "source": f"migrated logs/example.md:{n + 1}"},
                          body).id)
    return out


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/example.md").write_text(LOG)
    (tmp_path / ".engram").mkdir(exist_ok=True)
    (tmp_path / ".engram/engram.toml").write_text('[domain]\nname = "medical"\ncommit = "none"\n')
    return tmp_path


def test_events_are_append_only_and_ids_are_stable(repo):
    st = Store(repo)
    fm = {"kind": "symptom", "date": "2026-03-05", "recorded": "2026-03-05T10:00:00-07:00", "about": ["story/x"]}
    e = st.add(fm, "- body")
    assert e.id.startswith("20260305-100000-symptom-") and e.path == f"events/2026/03/{e.id}.md"
    with pytest.raises(FileExistsError):
        st.add(fm, "- body")
    assert event_id("2026-03-05T10:00:00-07:00", "symptom", "a") != event_id("2026-03-05T10:00:00-07:00", "symptom", "b")
    assert Store(repo).events(about="story/x")[0].body.strip() == "- body"


def test_engram_add_commits_one_event(repo, monkeypatch, capsys):
    import io
    import subprocess
    from engram.cli import main
    from conftest import git
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@x")
    git(repo, "config", "user.name", "t")
    (repo / ".engram").mkdir(exist_ok=True)
    (repo / ".engram/engram.toml").write_text('[domain]\nname = "medical"\ncommit = "per-write"\n[about]\nprefixes = ["series", "story"]\n')
    file_log(Store(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "migrated")
    monkeypatch.setattr("sys.stdin", io.StringIO("- woke locked, ~30° left rotation\n"))
    main(["add", "--kind", "symptom", "--date", "2026-03-06", "--reported", "2026-03-07", "--about", "series/example,story/knee",
          "--by", "sam", "--title", "Knee locked", "--repo", str(repo)])
    assert "added" in capsys.readouterr().out
    log = git(repo, "log", "--name-only", "--format=%s", "-1")
    assert log.startswith("engram: symptom 2026-03-06") and "events/2026/" in log
    assert git(repo, "status", "--porcelain").strip() == ""
    with pytest.raises(SystemExit):
        main(["add", "--kind", "symptom", "--date", "March", "--repo", str(repo)])
    with pytest.raises(SystemExit):
        main(["add", "--kind", "symptom", "--date", "2026-03-06", "--about", "nowhere/x", "--repo", str(repo)])


def test_a_malformed_entry_or_link_line_names_itself(repo):
    st = Store(repo)
    st.add({"title": "fine", "date": "2026-03-01", "kind": "symptom"}, "")
    bad = repo / "events/2026/03/20260301-000000-symptom-0000.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    for text in ("---\ntitle: [unclosed\n---\n", "---\ntitle: caf\xe9\n---\n"):  # bad YAML, or not UTF-8
        bad.write_bytes(text.encode("latin-1"))
        with pytest.raises(ValueError, match="events/2026/03/20260301-000000-symptom-0000.md: "):
            Store(repo).events()
    bad.unlink()
    for line in ("{not json", '{"kind": "link"}', "[1]"):  # not JSON, no id, not an object
        (repo / "events/links.jsonl").write_text('{"id": "a", "kind": "link"}\n' + line + "\n")
        with pytest.raises(ValueError, match="events/links.jsonl:2: "):
            Store(repo).events()


def test_a_hit_arrives_with_its_story_neighbours(repo, env):
    from engram import config, search
    from engram.cli import main
    first, _, _, gone = file_log(Store(repo))
    st = Store(repo)
    for e in st.events():
        e.fm["ref"] = {first: "logs/example.md#2026-03-01 — First session",
                       gone: "logs/example.md#2026-03-05 — Soreness gone"}.get(e.id, "")
    st.add({"title": "led to", "date": "2026-03-05", "recorded": "2026-10-21T12:00:01-07:00", "kind": "link",
            "about": ["story/ankle"], "from": first, "to": gone, "family": "timeline", "rel": "led-to"}, "")
    from engram.store import render_event
    for e in st.events():
        if e.fm.get("ref"):
            (repo / e.path).write_text(render_event(e.fm, e.body))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    hits = search.search("First session", ["medical"], limit=3)
    top = next(h for h in hits if h["ref"] == "logs/example.md#2026-03-01 — First session")
    assert top["surroundings"][0]["ref"] == "logs/example.md#2026-03-05 — Soreness gone"
    assert top["surroundings"][0]["rel"] == "led to" and top["surroundings"][0]["story"] == "ankle"


def test_a_search_naming_an_impossible_day_reads_it_as_no_date(repo, env):
    from engram import search
    from engram.cli import main
    file_log(Store(repo))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    assert search.search("soreness gone on 2026-02-30", ["medical"], limit=3)


def test_links_reach_theory_sections_and_the_query_picks_among_them(repo, env, capsys):
    from engram import search
    from engram.cli import main
    (repo / "evidence").mkdir()
    (repo / "evidence/D01-soreness.md").write_text("# D01 — Soreness\n\n## Observation\nSoreness after every session.\n\n"
                                                  "## Mechanism\nJoint guarding after the fitting, settling in days.\n")
    (repo / ".engram/engram.toml").write_text((repo / ".engram/engram.toml").read_text() + '[nodes]\ndiscovery = "evidence/{id}-*"\n')
    first = file_log(Store(repo))[0]
    st = Store(repo)
    for e in st.events():
        if e.id == first:
            e.fm["ref"] = "logs/example.md#2026-03-01 — First session"
            from engram.store import render_event
            (repo / e.path).write_text(render_event(e.fm, e.body))
    st = Store(repo)
    st.add({"title": "strengthens", "date": "2026-03-01", "recorded": "2026-10-21T12:00:01-07:00", "kind": "link",
            "about": ["discovery/D01"], "from": first, "to": "discovery/D01", "family": "evidence", "rel": "strengthens"}, "")
    st.add({"title": "outdates", "date": "2026-03-01", "recorded": "2026-10-21T12:00:02-07:00", "kind": "link", "about": [],
            "from": first, "to": "evidence/D01-soreness.md#Observation", "family": "evidence", "rel": "supersedes"}, "- note")
    st.add({"title": "disagrees", "date": "2026-03-05", "recorded": "2026-10-21T12:00:03-07:00", "kind": "link", "about": [],
            "from": "logs/example.md#2026-03-05 — Soreness gone", "to": "evidence/D01-soreness.md#Mechanism", "family": "evidence",
            "rel": "disagrees"}, "- how long it lasted: “after 4 days” against “settling in days”")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    from engram.paths import index_path
    for a, b in [("logs/example.md#2026-03-05 — Soreness gone", "evidence/D01-soreness.md#Mechanism"),
                 ("evidence/D01-soreness.md#Mechanism", "logs/example.md#2026-03-05 — Soreness gone")]:
        side = {"ref": a}
        search._surround(index_path("medical"), [side], "anything")
        assert side["surroundings"][0]["rel"] == "disagrees with" and side["surroundings"][0]["ref"] == b  # at both ends
        assert "against" in side["surroundings"][0]["title"]
    flagged = {"ref": "evidence/D01-soreness.md#Observation"}
    search._surround(index_path("medical"), [flagged], "anything")
    assert flagged["surroundings"][0]["rel"] == "outdated by"  # a flag always shows, first
    assert flagged["surroundings"][0]["ref"] == "logs/example.md#2026-03-01 — First session"
    top = {"ref": "logs/example.md#2026-03-01 — First session"}
    search._surround(index_path("medical"), [top], "why the guarding")
    assert [n["rel"] for n in top["surroundings"]][:2] == ["outdates", "bears on"]  # the flag shows at its other end too
    assert top["surroundings"][1] == {"rel": "bears on", "ref": "evidence/D01-soreness.md#Mechanism", "story": "",
                                      "title": "evidence/D01-soreness.md › D01 — Soreness › Mechanism", "lead": ""}
    assert search._lead("## Mechanism\nJoint guarding after the fitting.", 240) == "Joint guarding after the fitting."  # verbatim, heading dropped
    capsys.readouterr()
    main(["show", "../evidence/D01-soreness.md#mechanism"])  # a page's link: relative, with GitHub's anchor
    assert "Joint guarding" in capsys.readouterr().out
    main(["show", "evidence/D01-soreness.md"])
    assert "ref: evidence/D01-soreness.md#Observation" in capsys.readouterr().out


def test_a_whole_section_matches_any_of_its_chunks():
    from engram.evalset import matches
    assert matches("evidence/_staging.md#P-x@2", "evidence/_staging.md#P-x")
    assert not matches("evidence/_staging.md#P-x@2", "evidence/_staging.md#P-x@1")


def test_a_lens_weighs_records_by_kind(repo, env, capsys):
    from engram import search
    from engram.cli import main
    (repo / ".engram/engram.toml").write_text((repo / ".engram/engram.toml").read_text() + '[lenses.milestones]\nabout = "turning points"\n'
                                      'for = "how it went"\n[lenses.milestones.weights]\nday-to-day = 0.1\n"node:story" = 2.0\n'
                                      '"by:clinician" = 3.0\n"file:logs/*" = 0.5\n')
    env["set_repo"]("medical", repo)
    w = search.lenses("medical")["milestones"]["weights"]
    f = search.lens_factor
    assert f({"ref": "logs/a.md#x", "node": "symptom", "milestone": 0}, w) == 0.1 * 0.5
    assert f({"ref": "stories/a.md#x", "node": "story", "milestone": 1}, w) == 2.0
    assert f({"ref": "consults/a.md#x", "node": "visit", "milestone": 1, "author": "clinician:x (doctor)"}, w) == 3.0
    assert f({"ref": "reference/a.md#x"}, w) == 1.0  # a record on no story isn't day-to-day
    main(["lenses", "--domain", "medical"])
    assert "milestones [medical]: turning points" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["search", "soreness", "--domain", "medical", "--lens", "nowhere"])


def test_a_timeline_is_a_storys_records_in_time_order_cleaned_for_reading(repo, env, capsys, monkeypatch):
    import json as _json
    from engram import timeline, usage
    from engram.cli import main
    (repo / "events").mkdir(exist_ok=True)
    rows = [{"ref": "logs/example.md#2026-03-05 — Soreness gone", "node": "symptom", "by": "sam", "stories": ["ankle"]},
            {"ref": "logs/example.md#2026-03-01 — First session", "node": "procedure", "milestone": True, "by": "clinician:Dr. A (PT)",
             "stories": ["ankle"]},
            {"ref": "logs/example.md#Background", "node": "interpretation", "by": "with-claude", "stories": ["ankle"]}]
    (repo / "events/_nodes.jsonl").write_text("".join(_json.dumps(r) + "\n" for r in rows))
    Store(repo).add({"title": "led to", "date": "2026-03-05", "recorded": "2026-10-21T12:00:01-07:00", "kind": "link",
                     "about": ["story/ankle"], "from": rows[1]["ref"], "to": rows[0]["ref"], "family": "timeline", "rel": "led-to"}, "")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    assert timeline.names("medical")["stories"] == ["ankle"]
    header, chain = timeline.chain("medical", "ankle")
    assert [r["_ref"] for r in chain] == [rows[1]["ref"], rows[0]["ref"], rows[2]["ref"]]  # dated first, the standing analysis after
    first = chain[0]
    assert {k: first[k] for k in ("n", "date", "who", "kind", "milestone", "what")} == {
        "n": 1, "date": "2026-03-01", "who": "Dr. A (PT)?", "kind": "procedure", "milestone": 1, "what": "example › First session"}
    assert re.fullmatch(r"[a-z2-9]{6}", first["id"])  # a short name, not the file path and heading
    assert chain[1]["after"] == [1] and chain[1]["who"] == "me"
    assert header["records"] == 3 and header["undated after"] == 2 and "me = Sam" in header["key"]
    capsys.readouterr()
    main(["show", first["id"], "--domain", "medical"])
    assert "First session" in capsys.readouterr().out
    monkeypatch.setenv("ENGRAM_TAG", "tl-test")
    main(["timeline", "ankle", "--domain", "medical", "--format", "tsv"])
    out = capsys.readouterr().out.splitlines()
    assert out[1].startswith("n\tdate\twho") and "_ref" not in out[1] and len(out) == 5
    assert {r["ref"] for s in usage.searches("medical", "tl-test") for r in s["results"]} == {r["ref"] for r in rows}
    (repo / ".engram/engram.toml").write_text((repo / ".engram/engram.toml").read_text() + '[people.a]\nname = "Dr. A"\naliases = ["Dr. A (PT)"]\n')
    assert timeline.chain("medical", "ankle")[1][0]["who"] == "Dr. A"  # on the people list: one name everywhere
    from engram import labels
    assert labels.who("clinician:Dr. A (sports medicine)", labels.people({"people": {"a": {"name": "Dr. A", "say": ["Dr. A"]}}})) == "Dr. A"
    header, merged = timeline.chain("medical", [], "soreness after the first session")  # free text picks the story
    assert header["chain"] == "ankle" and "picked from" in header
    lane = [r for r in merged if r["on"] == "ankle"]
    assert [r["_ref"] for r in lane] == [r["_ref"] for r in chain] and lane[1]["after"] == [lane[0]["n"]]
    assert {r["on"] for r in merged} - {"ankle"} <= {"search match"}  # the search's own hits off the story, marked
    main(["timeline", "why", "is", "my", "ankle", "sore", "--domain", "medical", "--format", "tsv"])
    assert "\ton\t" in capsys.readouterr().out.splitlines()[1]


def test_a_timeline_across_domains_answers_from_each_with_stories_under_its_name(env, tmp_path, capsys, monkeypatch):
    from engram.cli import main

    def record(name: str, story_on: str | None) -> Path:
        root = tmp_path / name
        (root / "logs").mkdir(parents=True)
        (root / "logs/example.md").write_text(LOG)
        (root / ".engram").mkdir()
        (root / ".engram/engram.toml").write_text(f'[domain]\nname = "{name}"\ncommit = "none"\n')
        if story_on:
            (root / "events").mkdir()
            (root / "events/_nodes.jsonl").write_text(json.dumps(
                {"ref": f"logs/example.md#{story_on}", "node": "symptom", "by": "sam", "stories": ["ankle"]}) + "\n")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        env["set_repo"](name, root)
        main(["ingest", "--domain", name])
        return root

    record("medical", "2026-03-01 — First session")
    record("clinic", "2026-03-05 — Soreness gone")
    monkeypatch.chdir(record("blog", None))
    capsys.readouterr()
    for scope in ("blog,medical", "medical,blog"):  # the one with stories answers, in either order
        main(["timeline", "ankle", "--domain", scope])
        out = capsys.readouterr().out
        assert out.startswith('{"domain":"medical",') and "First session" in out and '"blog"' not in out
    main(["timeline", "ankle", "--domain", "medical,clinic"])  # both with stories: both answer, each under its name
    out = capsys.readouterr().out
    assert out.index('{"domain":"medical",') < out.index("First session") < out.index('{"domain":"clinic",') < out.index("Soreness gone")
    main(["timeline", "ankle", "--domain", "medical,clinic", "--format", "jsonl"])  # still JSON lines, every one
    assert all(json.loads(l) for l in capsys.readouterr().out.splitlines())
    with pytest.raises(SystemExit, match="no stories here"):
        main(["timeline", "ankle", "--domain", "blog"])


def test_a_way_in_lights_its_records_and_names_a_chain(repo, env):
    import json as _json
    from engram import timeline
    from engram.cli import main
    from engram.index import open_index
    from engram.paths import index_path
    from engram.sources import waysin
    (repo / "state-events.jsonl").write_text(_json.dumps({"entity": "Zentrafen (zentrazole 0.05%)", "kind": "med"}) + "\n")
    (repo / "logs/example.md").write_text((repo / "logs/example.md").read_text() + "\n## 2026-03-09 — Zentrafen started\nOne tablet twice a day.\n")
    (repo / ".engram/engram.toml").write_text((repo / ".engram/engram.toml").read_text() + '[ways.treatment]\nlists = ["state-events.jsonl"]\n'
                                      '[people.a]\nname = "Dr. A"\naliases = ["Dr. A (PT)"]\nsay = ["Dr. A"]\n')
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    db = open_index(index_path("medical"), readonly=True).db
    assert waysin.named(db, "how did zentrazole go") == [("treatment", "zentrafen", "zentrazole")]  # the generic names it too
    assert waysin.named(db, "a topical cream") == []  # a dosage form names nothing
    lit = {r for (r,) in db.execute("SELECT ref FROM way_ref WHERE key = 'zentrafen'")}
    assert "logs/example.md#2026-03-09 — Zentrafen started" in lit and "state-events.jsonl:1" in lit
    header, rows = timeline.chain("medical", "zentrafen")
    assert header["kind"] == "treatment" and "logs/example.md#2026-03-09 — Zentrafen started" in {r["_ref"] for r in rows}
    from datetime import date
    assert timeline._first_date("medical", "since zentrafen") == date(2026, 3, 9)  # the day it started, not 1 January


def test_what_sam_said_in_a_session_is_a_row_on_its_story(repo, env):
    import json as _json
    from engram.index import Doc, open_index
    from engram.paths import data_path, index_path
    from engram.sources import said
    (repo / "events").mkdir(exist_ok=True)
    (repo / "events/_nodes.jsonl").write_text(_json.dumps({"ref": "logs/example.md#2026-03-01 — First session", "node": "procedure",
                                                          "stories": ["ankle"]}) + "\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    from engram.cli import main
    main(["ingest", "--domain", "medical"])
    idx = open_index(index_path("medical"))
    idx.sync_source("sessions:s1:summary", [Doc(ref="summary:s1", source="sessions:s1:summary", cls="summary", kind="summary",
                                                 title="s1", body="summary", pointer="s1")])
    idx.close()
    (data_path("summaries") / "medical").mkdir(parents=True, exist_ok=True)
    chron = [{"line": 9, "text": "Sam's ankle soreness came back after the first session.", "relayed_from": "own", "act": "report",
              "speaker": "sam", "by": "sam", "evidence": "sore again"},
             {"line": 9, "text": "Claude: likely guarding.", "relayed_from": "own", "act": "analysis", "speaker": "claude", "by": "with-claude"}]
    (data_path("summaries") / "medical/s1.json").write_text(_json.dumps({"segments": [{"first_line": 1, "last_line": 20, "start": "2026-03-06T10:00:00-08:00"}],
                                                                     "stitch": {"summary": {"chronology": chron, "complaints": [
        {"tag": "new:complaint/ankle-ache", "course": [{"line": 4, "intensity": "dull", "direction": "worse"},
                                                         {"line": 12, "intensity": "gone by evening", "direction": "better"}]}]}}}))
    (data_path("summaries") / "medical/s2.json").write_text(_json.dumps({"stitch": {"summary": {"chronology": chron}}}))  # not indexed
    rows = said.docs_for("medical")
    assert [d.ref for d in rows] == ["session:s1:4@said-complaints-1", "session:s1:12@said-complaints-1",
                                     "session:s1:9@said-chronology-1"]  # each time he felt it; his report; not Claude's analysis
    assert rows[1].kind == "symptom" and rows[1].body == "ankle ache: gone by evening, better"
    d = rows[2]
    assert d.author == "sam" and d.kind == "report" and d.date == "2026-03-06" and "“sore again”" in d.body
    assert d.stories == "ankle"  # placed by the stories its words find


def test_a_question_about_a_period_keeps_what_led_in_and_what_changed_it():
    from datetime import date
    from engram import periods
    today = date(2026, 10, 21)
    assert periods.period("how was my ankle last spring", today) == (date(2026, 3, 1), date(2026, 5, 31))
    assert periods.period("what did we think in may", today) == (date(2026, 5, 1), date(2026, 5, 31))
    assert periods.period("may I ask about the brace", today) is None  # the verb
    assert periods.period("like the june brace gave relief", today) is None  # a month alone isn't a period
    assert periods.period("since the brace", today, dated=lambda w: date(2026, 6, 4)) == (date(2026, 6, 4), today)
    assert periods.period("soreness after the session", today, dated=lambda w: date(2026, 6, 4)) is None  # a cause
    assert periods.period("before August", today)[1] == date(2026, 8, 1)
    a, b = periods.span("2024-03 (approx.)", today)
    assert a < date(2024, 3, 1) and b > date(2024, 3, 31)  # a fuzzy date widens, more the further back


def test_a_record_as_it_stood_comes_from_git(tmp_path):
    import os
    from engram import asof
    repo = tmp_path / "r"
    (repo / "evidence").mkdir(parents=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for day, text in (("2026-04-25", "## Mechanism\nGuarding.\n"), ("2026-07-20", "## Mechanism\nNerve, not guarding.\n")):
        (repo / "evidence/D01-x.md").write_text(text)
        stamp = {**env, "GIT_AUTHOR_DATE": f"{day}T12:00:00", "GIT_COMMITTER_DATE": f"{day}T12:00:00"}
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=stamp)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", day], check=True, env=stamp)
    assert asof.revised(repo, "evidence/D01-x.md") == ["2026-04-25", "2026-07-20"]
    assert asof.section(repo, "evidence/D01-x.md", "Mechanism", "2026-05-01") == ("2026-04-25", "## Mechanism\nGuarding.")
    assert asof.section(repo, "evidence/D01-x.md", "Mechanism", "2026-03-01") is None  # the file didn't exist yet



def test_as_of_follows_a_deleted_or_moved_file_to_its_old_home(tmp_path, monkeypatch):
    import os
    from engram import asof, theory
    monkeypatch.setenv("ENGRAM_DATA", str(tmp_path / "data"))
    repo = tmp_path / "r"
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    def commit(day):
        stamp = {**env, "GIT_AUTHOR_DATE": f"{day}T12:00:00", "GIT_COMMITTER_DATE": f"{day}T12:00:00"}
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=stamp)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", day], check=True, env=stamp)
    (repo / "logs").mkdir(parents=True)
    (repo / ".engram").mkdir(exist_ok=True)
    (repo / ".engram/engram.toml").write_text('[domain]\nname = "medical"\n')
    (repo / "logs/knee.md").write_text("# Knee\n\n### 2026-03-01 — Stiff\n- stiff, then better\n")
    (repo / "architecture.md").write_text("# Model\n\n## Core nodes\n- A: stiffness\n")
    commit("2026-03-02")
    (repo / "logs/knee.md").write_text("# Knee\n\n### 2026-03-01 — Stiff\n- stiff, then much better\n")
    commit("2026-05-01")
    # the clean house: the log becomes an entry naming its old section, architecture.md a theory file
    (repo / "logs/knee.md").unlink()
    (repo / "architecture.md").unlink()
    (repo / "events/2026/10").mkdir(parents=True)
    eid = "20261022-010000-symptom-abcd"
    (repo / f"events/2026/10/{eid}.md").write_text(
        f"---\nid: {eid}\ntitle: Stiff\ndate: 2026-03-01\nkind: symptom\nref: \"logs/knee.md#2026-03-01 — Stiff\"\n---\n- stiff, then much better\n")
    (repo / "theory").mkdir()
    (repo / "theory/node-A.md").write_text("---\nid: node/A\nkind: node\nshort: stiffness\n---\n# Node A — Stiffness\n\nStiffness.\n")
    commit("2026-10-22")
    (tmp_path / "data/moved").mkdir(parents=True)
    (tmp_path / "data/moved/medical.json").write_text(json.dumps({"architecture.md#Core nodes": ["theory/node-A.md#Node A — Stiffness"]}))

    assert asof.stood(repo, eid, "2026-04-01") == ("2026-03-02", "### 2026-03-01 — Stiff\n- stiff, then better", "logs/knee.md#2026-03-01 — Stiff")
    assert asof.stood(repo, eid, "2026-06-01")[1].endswith("then much better")  # the commit current that day
    assert asof.stood(repo, eid, "2026-10-23")[2] == eid  # once the entry exists, the entry itself
    assert asof.stood(repo, "theory/node-A.md#Node A — Stiffness", "2026-04-01") == ("2026-03-02", "## Core nodes\n- A: stiffness", "architecture.md#Core nodes")
    assert asof.stood(repo, eid, "2026-01-01") is None  # neither existed yet
    g = theory.load(repo, asof="2026-04-01")
    assert "stiffness\tin architecture.md#Core nodes (committed 2026-03-02); its own file began 2026-10-22" in theory.files_then(repo, g, "2026-04-01")
    assert "stiffness\ttheory/node-A.md: as now" in theory.files_then(repo, g, "2026-10-23")

def test_a_summary_sentence_must_quote_the_record_and_keep_its_numbers():
    from engram.recsum import check
    body = "2026-04-27 evening — Dose reduced 20mg → 10mg after the dizzy spell."
    assert check({"text": "The dose was cut from 20mg to 10mg.", "quote": "Dose reduced 20mg → 10mg"}, body) is None
    assert check({"text": "The dose was cut to 5mg.", "quote": "Dose reduced"}, body) == "number 5 not in the record"
    assert check({"text": "The dose was cut.", "quote": "dose halved"}, body) == "quote not in the record"
    assert check({"text": "The dose was cut to 0mg.", "quote": "Dose reduced"}, body) == "number 0 not in the record"


def test_record_summaries_count_each_dropped_sentence_by_why(env, monkeypatch):
    from engram import recsum
    body = "2026-04-27 evening: dose reduced 20mg to 10mg after the dizzy spell, and the spell did not come back. " * 8
    monkeypatch.setattr(recsum, "wanted", lambda domain: [("log.md#Dose", "Dose", body)])
    said = [{"text": "The dose went to 5mg.", "quote": "dose reduced"}, {"text": "The dose went to 7mg.", "quote": "dose reduced"},
            {"text": "Then 5mg again.", "quote": "dose reduced"}, {"text": "It was halved.", "quote": "dose halved"},
            {"text": "The dose went from 20mg to 10mg.", "quote": "dose reduced 20mg to 10mg"}]
    reply = json.dumps({"summaries": [{"id": "0", "sentences": said}]})
    monkeypatch.setattr(recsum, "_ask", lambda prompt, system: (reply, {"in": 1, "out": 1, "usd": 0.01}))
    stats = recsum.run("notes")
    assert stats["dropped"] == {"number not in the record": 3, "quote not in the record": 1}
    assert stats["sentences"] == 5 and stats["kept"] == 1


def test_a_consult_is_one_row_opened_whole(repo, env, capsys):
    import json as _json
    from engram import timeline
    from engram.cli import main
    from engram.evalset import matches
    (repo / "consults/past").mkdir(parents=True)
    (repo / "consults/past/pt-2026-03-04.md").write_text("# Consult: PT — 2026-03-04\n\n## Background\nAnkle sore since February.\n\n"
                                                         "## Visit Outcome\nMild sprain; exercises.\n")
    (repo / "events").mkdir(exist_ok=True)
    rows = [{"ref": "consults/past/pt-2026-03-04.md#Background", "node": "interpretation", "by": "sam", "stories": ["ankle"]},
            {"ref": "consults/past/pt-2026-03-04.md#Visit Outcome", "node": "visit", "milestone": True, "by": "clinician:PT (PT)",
             "stories": ["ankle"]}]
    (repo / "events/_nodes.jsonl").write_text("".join(_json.dumps(r) + "\n" for r in rows))
    (repo / ".engram/engram.toml").write_text((repo / ".engram/engram.toml").read_text() + '[timeline]\nwhole = ["consults/*"]\n')
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    header, chain = timeline.chain("medical", "ankle")
    assert len(chain) == 1  # one visit, one row
    row = chain[0]
    assert row["_ref"] == "consults/past/pt-2026-03-04.md" and row["date"] == "2026-03-04" and row["kind"] == "visit"
    assert row["who"] == "PT?" and row["milestone"] == 1
    assert matches("consults/past/pt-2026-03-04.md#Background", row["_ref"])  # the whole file holds each section
    capsys.readouterr()
    main(["show", row["id"], "--domain", "medical"])
    out = capsys.readouterr().out
    assert "Ankle sore since February" in out and "Mild sprain" in out
    assert "[ref: consults/past/pt-2026-03-04.md#Visit Outcome]" in out  # each part's ref, so it can be cited
    main(["show", "consults/past/pt-2026-03-04.md#Visit", "--domain", "medical"])  # a heading cut short
    assert "Mild sprain" in capsys.readouterr().out



def test_a_hidden_session_stays_hidden_in_its_story_rows(monkeypatch):
    from engram.search import _excluded
    monkeypatch.setenv("ENGRAM_EXCLUDE_SOURCES", "sessions:abc")
    assert _excluded("sessions:abc", "session:abc:12")
    assert _excluded("said", "session:abc:12@said-reported-1")  # his passage from that session, filed on a story
    assert not _excluded("said", "session:xyz:12@said-reported-1")


def test_dead_node_rows_are_pruned_in_one_commit_the_lint_allows_and_a_path_can_be_excluded(tmp_path, env):
    from conftest import git, make_repo
    from engram import lint, setup
    from engram.cli import main
    from engram.sources import sections
    rows = [{"ref": "notes/a.md#A", "node": "interpretation"}, {"ref": "logs/gone.md#B", "node": "symptom"}]
    repo = make_repo(tmp_path / "rec", {".engram/engram.toml": '[domain]\nname = "medical"\n[index]\nevents = false\n',
                                        "notes/a.md": "# A\n\nkept\n", "data/readings.csv": "t,pm25\n1,3\n",
                                        "events/_nodes.jsonl": "".join(json.dumps(r) + "\n" for r in rows)})
    git(repo, "config", "core.hooksPath", ".engram/hooks")
    (repo / ".engram/hooks").mkdir(parents=True)
    (repo / ".engram/hooks/pre-commit").write_text(f"#!/bin/sh\nexec {setup.engram_cmd()[0]} lint --staged --repo \"$(git rev-parse --show-toplevel)\"\n")
    (repo / ".engram/hooks/pre-commit").chmod(0o755)
    git(repo, "add", ".engram/hooks")
    git(repo, "commit", "-qm", "hooks")
    assert [json.loads(l)["ref"] for l in sections.prune_nodes(repo)] == ["logs/gone.md#B"]
    assert (repo / "events/_nodes.jsonl").read_text() == json.dumps(rows[0]) + "\n"
    assert git(repo, "status", "--porcelain").strip() == "" and "node list drops 1 rows" in git(repo, "log", "-1", "--format=%s")
    (repo / "events/_nodes.jsonl").write_text(json.dumps({**rows[0], "node": "symptom"}) + "\n")  # an edit, not a drop
    git(repo, "add", "-A")
    assert lint.staged_event_violations(repo) == ["M\tevents/_nodes.jsonl"]
    git(repo, "reset", "-q", "--hard")
    env["set_repo"]("medical", repo)
    assert "data/readings.csv" in [p.as_posix() for p in sections.files(config_domain())]
    assert setup.exclude(Store(repo), "data/readings.csv") and not setup.exclude(Store(repo), "data/readings.csv")
    assert "data/readings.csv" not in [p.as_posix() for p in sections.files(config_domain())]
    assert git(repo, "status", "--porcelain").strip() == "" and "stays out of the index" in git(repo, "log", "-1", "--format=%s")
    assert 'exclude = ["data/readings.csv"]' in (repo / ".engram/engram.toml").read_text()


def config_domain():
    from engram import config
    return config.load()["medical"]


def _searchable(tmp_path, env, toml: str, files: dict[str, str], entries: list[tuple[dict, str]] = ()):
    """A record with an engram.toml, plain files and entries, indexed."""
    from engram.cli import main
    repo = tmp_path / "rec"
    repo.mkdir()
    (repo / ".engram").mkdir(exist_ok=True)
    (repo / ".engram/engram.toml").write_text('[domain]\nname = "medical"\ncommit = "none"\nevents_dir = "events"\n[index]\nevents = true\n' + toml)
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    st = Store(repo)
    with st.transaction() as tx:
        for fm, body in entries:
            tx.add({"domain": "medical", **fm}, body)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    env["set_repo"]("medical", repo, exclude=["events/"])  # entries are indexed as themselves
    main(["ingest", "--domain", "medical"])
    return repo


def test_a_role_word_is_a_way_in_to_that_clinicians_records(tmp_path, env):
    from engram import search
    from engram.index import open_index
    from engram.paths import index_path
    from engram.sources import waysin
    _searchable(tmp_path, env, '[people.bw]\nname = "fascial bodyworker"\nsay = ["bodyworker"]\nroles = ["massage therapist"]\n'
                'aliases = ["bodyworker (bodyworker)"]\n',
                {"notes/breathing.md": "# Breathing\n\n## Drills\nDiaphragm drills, diaphragm breathing drills, loose diaphragm.\n",
                 "notes/coach.md": "# Coach\n\n## Ask\nAsk the coach whether a massage therapist could help.\n"},
                [({"title": "Session", "date": "2026-03-27", "kind": "visit", "by": "clinician:bodyworker (bodyworker)"},
                  "### Findings\nDiaphragm tight and tender, right more than left.\n")])
    db = open_index(index_path("medical"), readonly=True).db
    assert waysin.named(db, "did the massage therapist say so") == [("person", "bw", "massage therapist")]
    lit = {r for (r,) in db.execute("SELECT ref FROM way_ref WHERE key = 'bw'")}
    assert not any(r.startswith("notes/coach.md") for r in lit)  # a role in a record's text isn't a mention of them
    def visit(q):
        return next(h for h in search.search(q, ["medical"], limit=5, surround=False) if "-visit-" in h["ref"])
    named, plain = visit("did the massage therapist find my diaphragm tight"), visit("did they find my diaphragm tight")
    assert named["factors"]["person"] == search.PERSON and "person" not in plain["factors"]  # naming nobody weighs nobody


def test_an_entrys_sections_are_one_hit_under_its_id(tmp_path, env):
    from engram import search
    _searchable(tmp_path, env, "", {"notes/a.md": "# A\n\n## Other\nunrelated words here\n"},
                [({"title": "Visit", "date": "2026-03-27", "kind": "visit", "by": "clinician:x (y)"},
                  "### Findings\nDiaphragm tight.\n\n### Response\nDiaphragm looser after.\n\n### Flags\nDiaphragm first.\n")])
    refs = [h["ref"] for h in search.search("diaphragm", ["medical"], limit=5, surround=False)]
    assert len(refs) == 1 and "-visit-" in refs[0] and "#" not in refs[0]


def test_one_documents_sections_take_at_most_two_places(tmp_path, env):
    from engram import search
    _searchable(tmp_path, env, "", {"consults/brief.md": "# Brief\n\n" + "".join(f"## Part {i}\nNasal valve surgery, part {i}.\n\n" for i in range(5)),
                                    **{f"notes/n{i}.md": f"# Note {i}\n\n## Day\nNasal spray, day {i}.\n" for i in range(4)}})
    refs = [h["ref"] for h in search.search("nasal valve surgery", ["medical"], limit=5, surround=False)]
    assert sum(r.startswith("consults/brief.md#") for r in refs) == search.PER_FILE and len(refs) == 5  # the rest fill in


def test_a_link_filed_twice_is_one_link_in_the_index(tmp_path, env):
    from engram.index import open_index
    from engram.paths import index_path
    link = {"title": "disagrees", "date": "2026-01-28", "kind": "link", "about": ["story/knee"], "from": "notes/a.md#One",
            "to": "notes/b.md#Two", "family": "evidence", "rel": "disagrees"}
    _searchable(tmp_path, env, "", {"notes/a.md": "# A\n\n## One\nstarted 01-28\n", "notes/b.md": "# B\n\n## Two\nstarted 03\n"},
                [(link, "- start: 01-28 against 03"), (link, "- start again")])
    rows = open_index(index_path("medical"), readonly=True).db.execute("SELECT note FROM link WHERE rel = 'disagrees'").fetchall()
    assert [r[0] for r in rows] == ["start: 01-28 against 03"]


def test_a_folder_word_lifts_that_folders_records_without_filtering(tmp_path, env):
    from engram import search
    _searchable(tmp_path, env, '[folders]\nboost = 1.5\n[folders.words]\njournal = "diary/"\nlab = ["reference/labs/"]\n',
                {"diary/2026-03-29.md": "# Slow going\n\n## On stairs\nKnee aches when I climb stairs feel slow.\n",
                 "consults/brief.md": "# Brief\n\n## Ask\nKnee aches when I climb stairs at work.\n",
                 **{f"notes/n{i}.md": f"# Note {i}\n\n## Day\nWalked {i} miles, slept well.\n" for i in range(8)}})
    q = "whats in my journal about knee aches when i climb stairs"
    assert search.folders_named(search.repo_conf("medical"), q) == ["diary/"]
    assert search.folders_named(search.repo_conf("medical"), "my labs from june") == ["reference/labs/"]  # a plural too
    assert search.folders_named(search.repo_conf("medical"), "a journaling habit") == []  # whole words only
    plain = {h["ref"]: h for h in search.search("knee aches when i climb stairs", ["medical"], limit=5, surround=False)}
    named = search.search(q, ["medical"], limit=5, surround=False)
    assert named[0]["ref"].startswith("diary/") and named[0]["factors"]["folder"] == 1.5
    assert "folder" not in plain[named[0]["ref"]]["factors"]
    assert any(h["ref"].startswith("consults/") for h in named)  # a boost, never a filter


def test_what_a_question_asks_for_weighs_kinds_of_record(tmp_path, env):
    from engram import search
    _searchable(tmp_path, env, '[asks.findings]\nwords = ["find", "found"]\n[asks.findings.weights]\n"ref:*-visit-*" = 1.3\n'
                '"node:measurement" = 1.3\n"file:reference/*" = 1.3\n"file:consults/upcoming/*" = 0.7\n',
                {"consults/upcoming/knee.md": "# Knee brief\n\n## Questions to ask\nWhat will the knee consult find?\n",
                 **{f"notes/n{i}.md": f"# Note {i}\n\n## Day\nWalked {i} miles, slept well.\n" for i in range(8)}},
                [({"title": "Knee consult", "date": "2026-10-20", "kind": "visit", "by": "clinician:x (y)"}, "Treadmill normal.\n")])
    conf = search.repo_conf("medical")
    assert search.asks(conf, "what did the knee consult find?") and not search.asks(conf, "when is the knee consult")
    top = search.search("what did the knee consult find?", ["medical"], limit=5, surround=False)
    brief = next(h for h in top if h["ref"].startswith("consults/"))
    visit = next(h for h in top if "-visit-" in h["ref"])
    assert visit["factors"]["ask"] == 1.3 and brief["factors"]["ask"] == 0.7
    assert "ask" not in search.search("when is the knee consult", ["medical"], limit=1, surround=False)[0]["factors"]
