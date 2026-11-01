import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

from conftest import git, make_repo
from engram import rewire

NOTES = Path(__file__).resolve().parents[1] / "examples/notes"


def said(text, ts="2026-10-01T10:00:00Z", uuid="", entry="cli", meta=False, cwd="/home/sam/notes"):
    e = {"type": "user", "timestamp": ts, "cwd": cwd, "entrypoint": entry, "message": {"role": "user", "content": text}}
    return json.dumps({**e, "uuid": uuid, "isMeta": meta})


def session(root, project, stem, lines):
    p = root / project / f"{stem}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")


def test_turns_keep_only_what_the_owner_typed_in_the_repo(tmp_path):
    root, repo = tmp_path / "projects", Path("/home/sam/notes")
    brief = "# Task\n\n" + "do the thing. " * 199 + "do the thing."
    session(root, "-home-sam-notes", "a", [
        said("the basil bolted", uuid="u1"),
        said("injected skill text", meta=True),
        said("This session is being continued from a previous conversation that ran out of context."),
        said("<task-notification>done</task-notification>"),
        said("here it is <pasted_content id=1>long log text</pasted_content> what now", ts="2026-10-02T10:00:00Z"),
        said(brief, ts="2026-10-03T10:00:00Z"),
        said("too late", ts="2026-11-01T10:00:00Z")])
    session(root, "-home-sam-notes", "b", [said("filer prompt", entry="sdk-cli")])  # a headless run, the filer's own
    session(root, "-home-sam-notes", "t", [said("Act as the review sub-agent for this task.\n\nReview the beds",
                                                entry="sdk-ts"), said("and the herbs", entry="sdk-ts")])  # T3's delegate
    session(root, "-home-sam-notes", "c", [said("from the app", entry="sdk-ts", ts="2026-10-04T10:00:00Z")])
    session(root, "-home-sam-notes/a/subagents", "s", [said("a subagent's prompt")])
    session(root, "-home-sam-elsewhere", "d", [said("not this repo", cwd="/home/sam/elsewhere")])
    mirror = tmp_path / "mirror"
    session(mirror, "-home-sam-notes", "a", [said("the basil bolted", uuid="u1")])  # the same message, mirrored

    t = rewire.turns(repo, before="2026-10-20T00:00:00Z", from_roots=[root, mirror])

    assert [m["text"] for m in t["turns"]] == ["the basil bolted", "here it is [paste, 13 chars] what now", brief,
                                              "from the app"]
    assert [m["brief"] for m in t["turns"]] == [False, False, True, False]
    assert (t["messages"], t["briefs"], t["sessions"], t["days"], t["thin"]) == (4, 1, 2, 3, True)
    out = rewire.write_turns(t, tmp_path / "turns.md").read_text()
    assert "### 2026-10-03T10:00 a brief\n" in out and "Thin:" in out


def test_units_read_every_dated_unit_as_the_record_writes_it():
    text = textwrap.dedent("""\
        # Tomatoes
        ## Background
        - planted around 04-12, sunny
        - no date here
        ## 2026-05-01 (Staked)
        Notes.
        ### 2026-05-05 follow-up
        | date | note |
        |---|---|
        | 2026-05-06 | wilted |
        ```
        ## 2026-06-01 inside a fence
        ```
        Picked on Aug 9.
        """)
    us, _ = rewire.units("garden/tomatoes.md", text)
    got = [(u["unit"], u["date"]) for u in us]
    assert got == [("line", "04-12"), ("heading", "2026-05-01"), ("heading", "2026-05-05"), ("row", "2026-05-06"),
                   ("text", "Aug 9")]
    assert "2026-05-06" in us[1]["body"] and "Aug 9" in us[1]["body"]  # a dated heading's unit is its section
    assert [rewire.day_of(u["text"]) for u in us] == ["04-12", "05-01", "05-05", "05-06", "08-09"]


def test_analyse_finds_one_update_written_in_several_places(tmp_path):
    notes = {str(p.relative_to(NOTES)): p.read_text() for p in NOTES.rglob("*") if p.is_file() and ".engram" not in p.parts}
    repo = make_repo(tmp_path / "notes", notes)
    assert rewire.analyse(repo)["copies"] == []
    planted = {"garden/log.md": "# Log\n- 2026-10-14: the Brandywine tomatoes split after rain\n",
               "garden/beds.md": notes["garden/beds.md"] + "\nOct 14: lost two Brandywine fruit to splitting.\n",
               "garden/tomatoes.md": "---\nstatus: growing\nas_of: 2026-09-01\n---\n# Tomatoes\n## 2026-10-14 split\n"
                                     "The Brandywine plants split.\n",
               **{f"garden/{bed}.md": f"# {bed}\nnothing named here\n" for bed in ("peppers", "herbs", "compost")}}
    for rel, text in planted.items():
        (repo / rel).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plant")
    a = rewire.analyse(repo)
    assert a["copies"] == [{"name": "Brandywine", "date": "10-14",
                            "files": ["garden/beds.md", "garden/log.md", "garden/tomatoes.md"]}]
    assert a["stale"] == [{"file": "garden/tomatoes.md", "as_of": "2026-09-01", "newest_entry": "2026-10-14"}]
    assert a["folders"]["events/*/*"]["frontmatter"]["kind"] == len(list((NOTES / "events").rglob("*.md")))  # every entry has one


BRIEF = "\n### 2026-10-05T10:00 b brief\n# Brief\na long brief that quotes a secret\n"


def proposal(tmp_path):
    """examples/notes as its rewiring left it, committed, and a run folder with its owner's words and a brief."""
    notes = {str(p.relative_to(NOTES)): p.read_text() for p in NOTES.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    repo = make_repo(tmp_path / "notes", notes)
    run = tmp_path / "run"
    turns = rewire.write_turns(rewire.turns(repo, from_roots=[NOTES.parent / "sessions"]), run / "turns.md")
    turns.write_text(turns.read_text() + BRIEF)
    return repo, run


def test_check_passes_a_sound_proposal_and_fails_each_planted_defect(tmp_path):
    repo, run = proposal(tmp_path)
    assert rewire.check(repo, run) == {"ok": True, "problems": [], "drift": []}

    def problems_after(rel, old, new):
        p = repo / rel
        text = p.read_text()
        assert old in text
        p.write_text(text.replace(old, new))
        try:
            return rewire.check(repo, run)["problems"]
        finally:
            p.write_text(text)

    assert problems_after(".engram/README.md", "what I picked and when", "everything I ever picked") == \
        ["""job 'keep the harvest log': "Mostly I want to know everything I ever picked, so next year I can plan better" isn't in the owner's messages word for word (briefs don't count)"""]
    assert problems_after(".engram/README.md", '"which bed gets the tomatoes next year? I don\'t want them in the same spot twice"', "") == \
        ["job 'plan the beds' quotes none of the owner's words"]
    assert problems_after(".engram/README.md", "what I picked and when", "quotes a secret")[0].startswith("job 'keep")
    assert problems_after(".engram/engram.toml", "[rewire]", "[rewire")[0].startswith(".engram/engram.toml doesn't load")
    assert problems_after(".engram/__init__.py", "pack = Pack(", "pack = None and Pack(") == \
        [".engram/ doesn't load as a pack: .engram/__init__.py sets no `pack = Pack(...)`".replace(".engram/__init__.py", str(repo / ".engram/__init__.py"))]
    assert problems_after(".engram/engram.toml", '"aggregate"', '"vibes"')[0].startswith("kind of ask 'harvest so far': axis 'vibes'")
    assert problems_after(".engram/engram.toml", 'piece = "Current"', 'piece = "Dashboard"') == \
        ["kind of ask 'harvest so far': piece 'Dashboard' is no anchor in the canon"]
    assert problems_after(".engram/engram.toml", '"picked about 3 kg of Sungold this week", ', "") == \
        ["kind of ask 'harvest so far' cites 2 of the owner's messages word for word, not 3"]
    assert problems_after(".engram/engram.toml", 'jobs = ["Plan the beds"]', 'jobs = ["Sell seeds"]') == \
        ["kind of ask 'where things grow' serves 'Sell seeds', which .engram/README.md's Jobs section doesn't name",
         "job 'plan the beds' is served by no kind of ask"]
    END = 'have it kept"]\n'  # the toml's last line
    departs = "\n[departures]\n\"Theory\" = 'no theory: \"which bed gets the tomatoes next year\" is all the planning there is'\n"
    assert problems_after(".engram/engram.toml", END, END + departs) == []
    assert problems_after(".engram/engram.toml", END, END + departs.replace('"Theory"', '"Mood board"')) == \
        ["departure 'Mood board' names no anchor in the canon"]
    assert problems_after(".engram/engram.toml", END, END + departs.replace('"which bed gets the tomatoes next year"', "planning")) == \
        ["departure 'Theory' quotes no job, failure or message of the owner's"]



def test_a_job_may_quote_the_owner_from_any_session_but_an_ask_cites_the_repos_own(tmp_path, monkeypatch):
    repo, run = proposal(tmp_path)
    page = repo / ".engram/README.md"
    page.write_text(page.read_text().replace("what I picked and when", "the garden as a whole"))
    assert rewire.check(repo, run)["problems"][0].startswith("job 'keep the harvest log'")
    elsewhere = tmp_path / "elsewhere"  # said while working on another repo
    session(elsewhere, "-home-sam-engram", "e", [said(
        "Mostly I want to know the garden as a whole, so next year I can plan better", cwd="/home/sam/engram")])
    monkeypatch.setattr("engram.sources.sessions.ROOT", elsewhere)
    assert rewire.check(repo, run)["problems"] == []
    turns = run / "turns.md"
    turns.write_text(turns.read_text().replace(" days); ", " days), before 2026-10-01; ", 1))  # said after the run's cut
    assert rewire.check(repo, run)["problems"][0].startswith("job 'keep the harvest log'")
    turns.write_text(turns.read_text().replace("before 2026-10-01;", "before 2026-11-01;"))
    shutil.rmtree(elsewhere)
    session(elsewhere, "-home-sam-engram", "e", [said(  # a brief carrying the quote isn't the owner's words
        "Act as the design sub-agent for this task. The job: Mostly I want to know the garden as a whole, so next year I "
        "can plan better", entry="sdk-ts", cwd="/home/sam/engram")])
    assert rewire.check(repo, run)["problems"][0].startswith("job 'keep the harvest log'")
    shutil.rmtree(elsewhere)
    session(elsewhere, "-home-sam-engram", "e", [said(
        "Mostly I want to know the garden as a whole, so next year I can plan better", cwd="/home/sam/engram")])
    toml = repo / ".engram/engram.toml"
    toml.write_text(toml.read_text().replace('"picked about 3 kg of Sungold this week"', '"the garden as a whole"'))
    assert rewire.check(repo, run)["problems"] == \
        ["kind of ask 'harvest so far' cites 2 of the owner's messages word for word, not 3"]

def jobs_id(page):
    return rewire.jobs_id(rewire.jobs_section(page.read_bytes()))


def test_the_jobs_section_runs_to_the_next_heading_of_its_level():
    page = b"---\njobs: confirmed\n---\n# Garden\nintro\n\n## Jobs\n1. **Keep.** \"x\"\n\n### Failures\n- **Forms.** \"y\"\n\n## Decisions\n- **Z.**\n"
    assert rewire.jobs_section(page) == b"## Jobs\n1. **Keep.** \"x\"\n\n### Failures\n- **Forms.** \"y\"\n"
    assert rewire.jobs_of(rewire.jobs_section(page).decode()) == ({"keep": ["x"]}, {"forms": ["y"]})
    assert rewire.jobs_section(b"# Garden\n## Decisions\n") is None and rewire.jobs_section(None) is None


def plant_copy(repo):
    """One update written in three files outside every home, among others that don't name it."""
    (repo / "notes").mkdir()
    for rel in ("log", "frost", "beds"):
        (repo / f"notes/{rel}.md").write_text("# x\n- 2026-10-12: the Brandywine split\n")
    for rel in ("peppers", "herbs", "compost"):
        (repo / f"notes/{rel}.md").write_text(f"# {rel}\nnothing named here\n")


def test_check_finds_an_unhomed_copy_and_drift_since_the_last_rewire(tmp_path):
    repo, run = proposal(tmp_path)
    page = repo / ".engram/README.md"
    page.write_text(page.read_text().replace("### Failures", "4. **Save seed.** \"I want to know what I picked and when\"\n\n### Failures"))
    plant_copy(repo)
    git(repo, "add", "-A")
    res = rewire.check(repo, run)
    assert res["drift"] == [
        f".engram/README.md's Jobs section changed since the last rewire: set [rewire] at = \"{jobs_id(page)}\", or rewire "
        "against it first if a job was added, dropped or renamed",
        "1 copies have no home in [rewire.homes]: Brandywine 10-12 in notes/beds.md, notes/frost.md, notes/log.md"]
    assert "copy Brandywine 10-12 in 3 files has no home in [rewire.homes]" in res["problems"]


def test_drift_judges_what_is_being_committed(tmp_path):
    repo, _ = proposal(tmp_path)
    assert rewire.drift(repo) == []
    toml = repo / ".engram/engram.toml"
    page = repo / ".engram/README.md"
    page.write_text(page.read_text() + "\n## Decisions\n- **Beds rotate yearly.**\n\n## Design\nOne file per bed.\n")
    git(repo, "add", ".engram/README.md")
    assert rewire.drift(repo) == []  # the rest of the page isn't the jobs
    page.write_text(page.read_text().replace("\n## Decisions", "- **Lost seed packets.** \"I lose track\"\n\n## Decisions"))
    assert rewire.drift(repo) == []  # the working tree isn't what's committed
    git(repo, "add", ".engram/README.md")
    assert rewire.drift(repo) == [f".engram/README.md's Jobs section changed since the last rewire: set [rewire] at = "
                                  f"\"{jobs_id(page)}\", or rewire against it first if a job was added, dropped or renamed"]
    toml.write_text(re.sub(r'(?m)^at = ".*"$', f'at = "{jobs_id(page)}"', toml.read_text()))
    git(repo, "add", ".engram/engram.toml")
    assert rewire.drift(repo) == []  # rewired: at moved with the jobs
    git(repo, "commit", "-qm", "rewired")
    plant_copy(repo)
    git(repo, "add", "-A")
    assert rewire.drift(repo) == ["1 copies have no home in [rewire.homes]: Brandywine 10-12 in notes/beds.md, "
                                  "notes/frost.md, notes/log.md"]
    git(repo, "rm", "-q", "--cached", ".engram/engram.toml")
    assert rewire.drift(repo)[0] == ".engram/engram.toml has no [rewire]: the repo has no rewiring on record (the engram-rewire skill)"


def test_a_folder_git_doesnt_track_fails_check_instead_of_passing_empty(tmp_path):
    repo, run = proposal(tmp_path)
    plain = tmp_path / "copied"
    shutil.copytree(repo, plain, ignore=shutil.ignore_patterns(".git"))
    assert rewire.check(plain, run)["problems"] == [
        f"{plain} isn't the top of a git repo: analyse reads what git tracks, so clone or init it"]


def test_a_page_started_from_the_template_has_every_section_engram_and_the_pass_read():
    for page in (Path(__file__).resolve().parents[1] / "skills/engram-rewire/page.md", NOTES / ".engram/README.md"):
        text = page.read_text()
        assert text.startswith("---\njobs: ") and rewire.jobs_section(text.encode())
        assert [h for h in re.findall(r"^## (.+)$", text, re.M)] == \
            ["Jobs", "Decisions", "How the weekly pass may change this repo"]


def test_a_session_the_owner_opens_with_a_long_paste_is_still_theirs(tmp_path):
    root, repo = tmp_path / "projects", Path("/home/sam/notes")
    paste = "# My notes\n\n" + "the beds this spring. " * 120
    session(root, "-home-sam-notes", "p", [said(paste), said("which bed for the tomatoes?", ts="2026-10-02T10:00:00Z")])
    t = rewire.turns(repo, from_roots=[root])
    assert [(m["brief"], m["text"][:9]) for m in t["turns"]] == [(True, "# My note"), (False, "which bed")]


def test_an_agents_report_is_never_the_owners_turn(tmp_path):
    root, repo = tmp_path / "projects", Path("/home/sam/notes")
    session(root, "-home-sam-notes", "r", [said("Delegated task node:x (build) [completed]: all done, merge it"),
                                           said('<agent-message from="worker">done</agent-message>'),
                                           said("thanks, which bed next?", ts="2026-10-02T10:00:00Z")])
    assert [m["text"] for m in rewire.turns(repo, from_roots=[root])["turns"]] == ["thanks, which bed next?"]


def test_prose_around_the_jobs_isnt_drift_but_a_quote_is(tmp_path):
    repo, _ = proposal(tmp_path)
    page = repo / ".engram/README.md"
    text = page.read_text()
    page.write_text(text.replace("so next year's plan rests on it", "for next year").replace("### Failures", "Said once.\n\n### Failures"))
    git(repo, "add", "-A")
    assert rewire.drift(repo) == []
    page.write_text(text.replace('"don\'t make me fill in forms"', '"no forms"'))
    git(repo, "add", "-A")
    assert rewire.drift(repo)[0].startswith(".engram/README.md's Jobs section changed since the last rewire")


def test_a_conflicted_merge_isnt_refused_for_drift_the_merged_in_side_brings(tmp_path):
    repo, _ = proposal(tmp_path)
    git(repo, "checkout", "-qb", "other")
    page = repo / ".engram/README.md"
    page.write_text(page.read_text().replace("### Failures", '4. **Save seed.** "save seed"\n\n### Failures'))
    (repo / "x.md").write_text("theirs\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "edited where no hook runs")
    git(repo, "checkout", "-q", "main")
    (repo / "x.md").write_text("ours\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "ours")
    assert subprocess.run(["git", "-C", str(repo), "merge", "-q", "other"], capture_output=True).returncode
    (repo / "x.md").write_text("both\n")
    git(repo, "add", "x.md")
    assert rewire.drift(repo, introduced=True) == [] and rewire.drift(repo)  # health still shows it
