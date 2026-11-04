"""Stable document ids and heading anchors (engram.docreg): links survive a renamed heading and a moved file, and the
pre-commit refuses a removed linked heading with the command that fixes it."""
import json
import subprocess
import sys

import pytest

from conftest import git, make_repo
from engram import docreg
from engram.store import Store

TOML = '[domain]\nname = "medical"\nevents_dir = "events"\ncommit = "per-write"\n[index]\nevents = true\n' \
       '[links.evidence]\nrels = ["strengthens", "revises"]\n[ways.symptom]\npages = ["complaints/*#Occurrences"]\n'
PLAN = "# Rehab plan\n\nIntro.\n\n## Why\nTendon load.\n\n## Phase 1 — Isometrics\nHold 45 seconds.\n\n## Success markers\nNo pain.\n"


def _link(st, frm, to, rel="strengthens"):
    with st.transaction(message="a link") as tx:
        return tx.add({"title": rel, "date": "2026-10-01", "kind": "link", "about": ["story/arm"], "from": frm, "to": to,
                       "family": "evidence", "rel": rel}, "").id


@pytest.fixture
def rec(tmp_path, env):
    """A record with a plan, a note and an entry; one old-style link into the plan's Phase 1 heading and one into the
    whole note; stable ids given by `engram docs sync`."""
    repo = make_repo(tmp_path / "rec", {".engram/engram.toml": TOML, "plans/rehab.md": PLAN, "notes/visit.txt": "Seen 2026-09-30.\n"})
    env["set_repo"]("medical", repo, exclude=["events/"])
    st = Store(repo)
    with st.transaction(message="an entry") as tx:
        eid = tx.add({"title": "Elbow better", "date": "2026-10-02", "kind": "observation", "about": ["story/arm"]},
                     "Isometrics helped.\n").id
    _link(st, eid, "plans/rehab.md#Phase 1 — Isometrics")
    _link(st, eid, "notes/visit.txt#", "revises")
    out = docreg.sync(repo)
    assert out == {"documents": 2, "anchors": 1}
    assert git(repo, "status", "--porcelain").strip() == ""  # one commit
    return {"repo": repo, "entry": eid}


def _lint(repo, capsys):
    from engram.cli import main
    try:
        main(["lint", "--staged", "--repo", str(repo)])
        code = 0
    except SystemExit as e:
        code = e.code
    return code, capsys.readouterr().err


def _index_links(entry):
    from engram import ingest
    from engram.index import open_index
    from engram.paths import index_path
    ingest.record("medical")
    db = open_index(index_path("medical"), readonly=True).db
    return sorted(r[0] for r in db.execute("SELECT to_ref FROM link WHERE from_ref = ?", (entry,)))


def test_old_path_heading_ends_resolve_through_the_registry(rec):
    reg = docreg.load(rec["repo"])
    w = reg.resolve("plans/rehab.md#Phase 1 — Isometrics")
    assert w.ref == "plans/rehab.md#Phase 1 — Isometrics" and w.doc.startswith("doc-")
    assert reg.resolve(f"{w.doc}#{reg.current(w.doc, 'Phase 1 — Isometrics')}").ref == w.ref
    assert reg.resolve("notes/visit.txt#").ref == "notes/visit.txt#"
    assert _index_links(rec["entry"]) == ["notes/visit.txt#", "plans/rehab.md#Phase 1 — Isometrics"]
    assert docreg.check(rec["repo"])["dangling"] == {}


def test_a_renamed_heading_keeps_its_links(rec, capsys):
    repo = rec["repo"]
    (repo / "plans/rehab.md").write_text(PLAN.replace("## Phase 1 — Isometrics", "## Phase 1 — Isometric holds"))
    git(repo, "add", "-A")
    code, err = _lint(repo, capsys)
    assert code == 0 and "one-to-one rename" in err  # recorded on its own and staged with the commit
    git(repo, "commit", "-qm", "reword a heading")
    assert git(repo, "status", "--porcelain").strip() == ""
    assert _index_links(rec["entry"]) == ["notes/visit.txt#", "plans/rehab.md#Phase 1 — Isometric holds"]
    assert docreg.check(repo)["dangling"] == {}


def test_a_moved_file_keeps_its_links(rec, capsys):
    repo = rec["repo"]
    git(repo, "mv", "plans/rehab.md", "plans/forearm-rehab.md")
    git(repo, "mv", "notes/visit.txt", "notes/visit-2026-09-30.txt")
    code, err = _lint(repo, capsys)
    assert code == 0 and err.count("a pure move") == 2
    git(repo, "commit", "-qm", "rename files")
    assert _index_links(rec["entry"]) == ["notes/visit-2026-09-30.txt#", "plans/forearm-rehab.md#Phase 1 — Isometrics"]
    reg = docreg.load(repo)
    assert reg.resolve("plans/rehab.md#Phase 1 — Isometrics").ref == "plans/forearm-rehab.md#Phase 1 — Isometrics"


def test_a_removed_linked_heading_is_refused_with_the_command_that_fixes_it(rec, capsys):
    repo = rec["repo"]
    text = PLAN.replace("## Phase 1 — Isometrics\nHold 45 seconds.\n\n", "").replace("## Why\nTendon load.\n",
                                                                                      "## Why\nTendon load. Hold 45 seconds.\n")
    (repo / "plans/rehab.md").write_text(text)
    git(repo, "add", "-A")
    code, err = _lint(repo, capsys)
    assert code == 1 and "no longer has the heading “Phase 1 — Isometrics”" in err
    cmd = next(l.strip() for l in err.splitlines() if l.strip().startswith("engram moved"))
    assert cmd.startswith("engram moved 'plans/rehab.md#Phase 1 — Isometrics' 'plans/rehab.md#")
    from engram.cli import main
    import shlex
    main([*shlex.split(cmd)[1:], "--repo", str(repo)])  # what the advisor runs: staged beside the change
    assert _lint(repo, capsys)[0] == 0
    git(repo, "commit", "-qm", "fold phase 1 into why")
    assert docreg.check(repo)["dangling"] == {}
    to = _index_links(rec["entry"])
    assert "plans/rehab.md#Phase 1 — Isometrics" not in to and len(to) == 2


def test_a_deleted_linked_document_is_refused_until_its_new_home_is_recorded(rec, capsys):
    repo = rec["repo"]
    git(repo, "rm", "-q", "notes/visit.txt")
    code, err = _lint(repo, capsys)
    assert code == 1 and "notes/visit.txt is deleted" in err and "engram moved 'notes/visit.txt'" in err
    (repo / "consults").mkdir()
    (repo / "consults/visit-2026-09-30.md").write_text("# Visit 2026-09-30\n\nSeen.\n")
    git(repo, "add", "-A")
    assert "engram moved 'notes/visit.txt' 'consults/visit-2026-09-30.md'" in _lint(repo, capsys)[1]
    from engram.cli import main
    main(["moved", "notes/visit.txt", "consults/visit-2026-09-30.md", "--repo", str(repo)])
    assert _lint(repo, capsys)[0] == 0


def test_new_links_write_stable_ids_with_a_readable_hint(rec, capsys):
    from engram.cli import main
    repo = rec["repo"]
    main(["link", rec["entry"], "evidence:strengthens", "plans/rehab.md#Why", "--why", "load", "--repo", str(repo)])
    row = json.loads((repo / "events/links.jsonl").read_text().splitlines()[-1])
    assert docreg.ID.match(row["to"]) and "#" in row["to"] and row["to_hint"] == "plans/rehab.md#Why"
    assert git(repo, "status", "--porcelain").strip() == ""  # the new anchor's line committed with the link
    with pytest.raises(SystemExit):  # the same link again, named the old way, is the same link
        main(["link", rec["entry"], "evidence:strengthens", "plans/rehab.md#Why", "--why", "again", "--repo", str(repo)])
    assert "plans/rehab.md#Why" in _index_links(rec["entry"])


def test_the_pre_commit_hook_stages_a_pure_move_into_the_commit(rec):
    repo = rec["repo"]
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text(f"#!/bin/sh\nexec {sys.executable} -c 'from engram.cli import main; main([\"lint\", \"--staged\", \"--repo\", \".\"])'\n")
    hook.chmod(0o755)
    git(repo, "mv", "plans/rehab.md", "plans/forearm-rehab.md")
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "move"], check=True, capture_output=True)
    assert git(repo, "status", "--porcelain").strip() == ""
    assert "events/docs.jsonl" in git(repo, "show", "--name-only", "--format=", "HEAD")


def test_capture_places_an_occurrence_on_the_complaint_pages_stable_id(rec):
    from engram import capture
    repo = rec["repo"]
    (repo / "complaints").mkdir()
    (repo / "complaints/elbow-ache.md").write_text("# Elbow ache\n\nStories: arm\n\n## Occurrences\n\n| Date | |\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a complaint page")
    st = Store(repo)
    where = {"stories": ["arm"], "occurrence": "elbow-ache", "led_from": None}
    with st.transaction(message="placed") as tx:
        [(lfm, _)] = capture.links_for(rec["entry"], {"date": "2026-10-03"}, where, "ache again", "s1", st)
        tx.add(lfm, "")
    assert docreg.ID.match(lfm["from"]) and lfm["from_hint"] == "complaints/elbow-ache.md#Occurrences"
    assert git(repo, "status", "--porcelain").strip() == ""
    assert docreg.load(repo).resolve(lfm["from"]).ref == "complaints/elbow-ache.md#Occurrences"


def test_a_document_by_id_opens_whole(rec, capsys):
    from engram import ingest
    from engram.cli import main
    ingest.record("medical")
    doc = docreg.load(rec["repo"]).owner("plans/rehab.md")
    capsys.readouterr()
    main(["show", doc, "--domain", "medical"])
    out = capsys.readouterr().out
    assert out.startswith("plans/rehab.md\nref: plans/rehab.md\n")
    for heading, text in [("Rehab plan", "Intro."), ("Why", "Tendon load."), ("Phase 1 — Isometrics", "Hold 45 seconds."),
                          ("Success markers", "No pain.")]:
        assert f"[ref: plans/rehab.md#{heading}]\n" in out and text in out
