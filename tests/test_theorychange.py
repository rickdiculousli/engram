import json
import sqlite3
from datetime import datetime, timezone

import pytest

from conftest import git, make_repo
from engram import capture, relink, setup, store, theory, theorychange as tc
from engram.paths import data_path

TOML = """[domain]
name = "medical"
events_dir = "events"
commit = "none"
[about]
prefixes = ["series", "story"]
[links.theory]
rels = ["feeds", "shared-cause", "amplifier"]
"""


def node(id_, kind, short, stories=()):
    s = f"stories: [{', '.join(stories)}]\n" if stories else ""
    return f"---\nid: {id_}\nkind: {kind}\nshort: {short}\n{s}since: 2026-01-01\n---\n# {short}\n\nAbout {short}.\n"


def step(a, b, n):
    return {"title": f"Loop 1 {a} feeds {b}", "date": "2026-01-01", "kind": "link", "about": ["loop/1"], "from": a, "to": b,
            "family": "theory", "rel": "feeds", "loop": "loop/1", "step": n, "since": "2026-01-01"}


@pytest.fixture
def rec(env, monkeypatch):
    monkeypatch.setenv("ENGRAM_NO_RELINK", "1")
    repo = make_repo(env["tmp"] / "repos/med", {
        ".engram/engram.toml": TOML, "theory/node-A.md": node("node/A", "node", "stiffness", ["stiffness"]),
        "theory/node-B.md": node("node/B", "node", "knee", ["knee"]), "theory/node-C.md": node("node/C", "node", "ankle", ["ankle"]),
        "theory/loop-1.md": node("loop/1", "loop", "Loop 1"), "consults/visit.md": "# Visit\n\nThe knee scan shows mild wear.\n"})
    env["set_repo"]("medical", repo)
    st = store.Store(repo)
    with st.transaction() as tx:
        for i, (a, b) in enumerate([("node/A", "node/B"), ("node/B", "node/C"), ("node/C", "node/A")], 1):
            tx.add(step(a, b, i), f"step {i}")
        tx.add({"id": "e1", "title": "knee sore after a long walk", "date": "2026-03-01", "kind": "observation",
                "about": ["series/_observations"]}, "- knee sore after a long walk\n")
        tx.add({"title": "strengthens loop/1", "date": "2026-03-01", "kind": "link", "about": ["loop/1"], "from": "e1",
                "to": "loop/1", "family": "evidence", "rel": "strengthens"}, "")
    return repo


INSERT = [{"op": "add-node", "id": "node/X", "title": "Hip tightness", "short": "hip", "stories": ["knee"]},
          {"op": "insert-step", "loop": "loop/1", "after": "node/B", "node": "node/X", "mechanisms": ["knee → hip", "hip → ankle"]}]


def test_inserting_a_member_retires_the_step_it_breaks_and_the_loop_still_closes(rec):
    with pytest.raises(tc.ChangeError, match="unknown theory id node/X"):
        tc.apply(rec, INSERT[1:], why="w")
    with pytest.raises(tc.ChangeError, match="needs why"):
        tc.apply(rec, INSERT)
    r = tc.apply(rec, INSERT, why="hip tightness sits between them", said="yes, add the hip")
    assert r.structural and r.drawn["loop/1"] == "stiffness → knee → hip → ankle → stiffness"
    g = theory.load(rec)
    assert g.closes("loop/1") and g.draw("loop/1") == "stiffness → knee → hip → ankle → stiffness"
    [gone] = g.retired
    assert (gone.edge.a, gone.edge.b, gone.replaced_by, gone.why) == ("node/B", "node/C", "knee → hip → ankle",
                                                                    "hip tightness sits between them")
    assert (rec / "theory/node-x.md").exists() and "Hip tightness" in (rec / "theory/node-x.md").read_text()
    then = theory.load(rec, asof="2026-06-01")  # what we thought back then
    assert then.draw("loop/1") == "stiffness → knee → ankle → stiffness" and "node/X" not in then.things
    assert sum(1 for line in (rec / "events/links.jsonl").read_text().splitlines() if line) == 6  # appended, never edited
    [(state,)] = sqlite3.connect(data_path("theory.sqlite")).execute("SELECT state FROM change").fetchall()
    assert state == "queued"


def test_a_change_that_would_break_a_loop_or_lacks_a_replacement_is_refused(rec):
    with pytest.raises(tc.ChangeError, match="would no longer close"):
        tc.plan(theory.load(rec), [{"op": "add-loop", "id": "loop/2", "path": ["node/A", "node/B", "node/A"]},
                                   {"op": "remove-step", "loop": "loop/2", "node": "node/B"}], ["feeds"], theory.STRENGTHS, "w")
    tc.apply(rec, [{"op": "add-join", "from": "node/B", "to": "node/A", "rel": "amplifier", "strength": "medium",
                    "mechanism": "knee tension raises the urge"}])
    with pytest.raises(tc.ChangeError, match="needs what replaced it"):
        tc.apply(rec, [{"op": "retire-join", "from": "node/B", "to": "node/A", "rel": "amplifier"}], why="w")
    with pytest.raises(tc.ChangeError, match="unknown join kind"):
        tc.apply(rec, [{"op": "add-join", "from": "node/B", "to": "node/A", "rel": "causes", "strength": "high", "mechanism": "m"}])


def test_a_status_alone_is_not_structural_and_queues_no_recheck(rec):
    r = tc.apply(rec, [{"op": "status", "id": "loop/1", "to": "confirmed"}])
    assert not r.structural and theory.load(rec).status["loop/1"][0] == "confirmed"
    with tc.db() as c:
        assert c.execute("SELECT count(*) FROM change").fetchone() == (0,)


def test_the_recheck_reads_every_record_files_checked_links_and_runs_once(rec):
    r = tc.apply(rec, INSERT, why="w")
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return json.dumps({"links": [
            {"record": "consults/visit.md", "to": "node/X", "rel": "strengthens", "why": "wear"},
            {"record": "e1", "to": "node/X", "rel": "strengthens", "why": "knee sore", "moved_from": f"link/{theory.load(rec).retired[0].edge.id}"},
            {"record": "nope", "to": "node/X", "rel": "strengthens", "why": "x"},
            {"record": "e1", "to": "node/Q", "rel": "strengthens", "why": "x"},
            {"record": "e1", "to": "node/X", "rel": "causes", "why": "x"}]}), 0.5
    out = relink.run(r.change, ask=ask)
    assert "consults/visit.md" in prompts[0] and "[e1]" in prompts[0] and "now evidence for: loop/1" in prompts[0]
    assert len(out["links"]) == 2 and sorted(d["why"] for d in out["dropped"]) == [
        "not a record of this batch", "target node/Q isn't part of the change", "unknown rel causes"]
    filed = [e for e in store.Store(rec).events(kind="link") if e.fm.get("author") == "engram-relink"]
    assert {(e.fm["from"], e.fm["to"], e.fm["by"]) for e in filed} == {("consults/visit.md", "node/X", "claude"), ("e1", "node/X", "claude")}
    assert any("moved off the retired step" in e.body for e in filed)
    assert relink.run(r.change, ask=ask) == {"change": r.change, "skipped": "done"} and len(prompts) == 1
    [line] = tc.notices(rec, mark=True)
    assert line.startswith("Loop 1 revised") and "stiffness → knee → hip → ankle → stiffness" in line and "1 moved off the old step" in line
    assert tc.notices(rec) == []  # shown once


def said(text, ts="2026-10-18T20:00:00Z"):
    return json.dumps({"type": "user", "timestamp": ts, "cwd": "/x", "message": {"role": "user", "content": text}})


def test_the_recheck_reads_long_documents_whole_and_an_errored_one_shows_until_rerun(rec):
    tail = "The last line says the hip tightness began with the knee flare."
    (rec / "consults/long.md").write_text("# Long visit\n\n" + "Routine findings. " * 600 + tail + "\n")  # ~10k characters
    r = tc.apply(rec, INSERT, why="w")
    prompts = []

    def broken(prompt):
        raise RuntimeError("usage limit")
    with pytest.raises(RuntimeError):
        relink.run(r.change, ask=broken)
    for _ in range(2):  # every session start, until it's rerun
        [line] = tc.notices(rec, mark=True)
        assert "failed (RuntimeError: usage limit)" in line and f"engram theory relink --change {r.change}" in line

    def ask(prompt):
        prompts.append(prompt)
        return json.dumps({"links": []}), 0.1
    relink.run(r.change, ask=ask)
    assert any(tail in p for p in prompts)  # nothing cut
    assert not any("failed" in l for l in tc.notices(rec, mark=True))
    big = [("a", "", "x" * 60), ("b", "", "y" * 150), ("c", "", "z" * 30)]
    assert [[i for i, _, _ in b] for b in relink.batches(big, budget=100)] == [["a"], ["b"], ["c"]]  # a big one goes alone


def test_the_sweep_files_only_what_the_guards_keep_and_the_second_call_confirms(rec):
    (rec / "evidence").mkdir()
    (rec / "evidence/D01-cold.md").write_text("---\nid: D01\ntitle: Cold mornings stiffen the knee\n---\n# D01\n\nCold stiffens it.\n")
    store.Store(rec).add({"id": "j1", "title": "a low week", "date": "2026-03-02", "kind": "journal", "about": ["series/_journal"]},
                         "- felt low\n")
    reads, checks = [], []

    def ask(prompt):
        reads.append(prompt)
        return json.dumps({"links": [
            {"record": "consults/visit.md", "to": "loop/1", "rel": "weakens", "passage": "the knee scan shows mild wear",
             "why": "a reason the second call never sees"},
            {"record": "consults/visit.md", "to": "discovery/D01", "rel": "strengthens", "passage": "\"The knee scan shows\""},
            {"record": "e1", "to": "loop/1", "rel": "weakens", "passage": "knee sore"},  # the pair is linked already
            {"record": "j1", "to": "loop/1", "rel": "strengthens", "passage": "x"},  # journals aren't read
            {"record": "e1", "to": "node/A", "rel": "strengthens", "passage": "x"},  # a condition isn't a target
            {"record": "e1", "to": "discovery/D01", "rel": "causes", "passage": "x"},
            {"record": "e1", "to": "discovery/D01", "rel": "strengthens", "passage": "sore after a short run"}]}) + "\nDone.", 0.5

    def confirm(prompt):
        checks.append(prompt)
        return ("Yes." if "Loop 1" in prompt else "no"), 0.1
    out = relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True)
    assert "felt low" not in reads[0] and "Cold stiffens it." in reads[0] and "path: stiffness → knee → ankle → stiffness" in reads[0]
    assert out["proposed"] == 7 and len(out["links"]) == 2 and sorted(d["why"] for d in out["dropped"]) == [
        "already linked", "not a record of this batch", "passage not in the record", "target node/A isn't a loop or Discovery",
        "unknown rel causes"]
    assert len(checks) == 2 and all("The knee scan shows mild wear." in c and "never sees" not in c for c in checks)
    assert "The passage at issue: the knee scan shows mild wear" in checks[0]
    assert [(x["from"], x["to"]) for x in out["confirmed"]] == [("consults/visit.md", "loop/1")] and len(out["rejected"]) == 1
    assert round(out["usd"], 2) == 0.7 and out["left"] == {"unread": 0, "pending": 0}
    assert not [e for e in store.Store(rec).events(kind="link") if e.fm.get("author") == relink.SWEPT]
    assert relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True)["batches"] == 0  # a dry run picks up where the last stopped
    capped = relink.sweep(rec, ask=ask, confirm=confirm, cap=0.5)  # a real run keeps its own progress: it reads, then stops
    assert capped["stopped"] and capped["batches"] == 1 and not capped["confirmed"] and capped["left"] == {"unread": 0, "pending": 2}
    done = relink.sweep(rec, ask=ask, confirm=confirm)  # the next confirms what waits, reading nothing again
    assert done["batches"] == 0 and len(done["confirmed"]) == 1 and len(reads) == 2
    [filed] = [e for e in store.Store(rec).events(kind="link") if e.fm.get("author") == relink.SWEPT]
    assert (filed.fm["from"], filed.fm["to"], filed.fm["rel"], filed.fm["by"]) == ("consults/visit.md", "loop/1", "weakens", "claude")
    (rec / "consults/visit.md").write_text("# Visit\n\nThe knee scan shows mild wear, worse than last year.\n")
    again = relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True)  # only a changed record is read again
    assert again["unread"] == 1 and "already linked" in [d["why"] for d in again["dropped"] if d["record"] == "consults/visit.md"]


COMMITTED = TOML.replace('commit = "none"\n', "")


@pytest.fixture
def placed(env, monkeypatch):
    """A record whose links are committed: on Loop 1, one link the sweep placed and one the owner made; on D01, one the
    re-check placed."""
    monkeypatch.setenv("ENGRAM_NO_RELINK", "1")
    repo = make_repo(env["tmp"] / "repos/med", {
        ".engram/engram.toml": COMMITTED, "theory/node-A.md": node("node/A", "node", "stiffness", ["stiffness"]),
        "theory/node-B.md": node("node/B", "node", "knee", ["knee"]), "theory/node-C.md": node("node/C", "node", "ankle", ["ankle"]),
        "theory/loop-1.md": node("loop/1", "loop", "Loop 1"),
        "evidence/D01-cold.md": "---\nid: D01\ntitle: Cold mornings stiffen the knee\n---\n# D01\n\nCold stiffens it.\n",
        "consults/visit.md": "# Visit\n\nThe knee scan shows mild wear.\n", "consults/walk.md": "# Walk\n\nThe ankle ached after the cold walk.\n"})
    env["set_repo"]("medical", repo)
    ev = {"date": "2026-03-01", "kind": "link", "family": "evidence"}
    with store.Store(repo).transaction() as tx:
        for i, (a, b) in enumerate([("node/A", "node/B"), ("node/B", "node/C"), ("node/C", "node/A")], 1):
            tx.add(step(a, b, i), f"step {i}")
        tx.add({**ev, "title": "weakens Loop 1", "about": ["loop/1"], "from": "consults/visit.md", "to": "loop/1", "rel": "weakens",
                "by": "claude", "author": "engram-sweep"}, "the knee scan shows mild wear")
        tx.add({**ev, "title": "strengthens Loop 1", "about": ["loop/1"], "from": "consults/walk.md", "to": "loop/1",
                "rel": "strengthens", "by": "sam"}, "")
        tx.add({**ev, "title": "strengthens D01", "about": ["discovery/D01"], "from": "consults/walk.md", "to": "discovery/D01",
                "rel": "strengthens", "by": "claude", "author": "engram-relink"}, "the cold walk")
    return repo


def _no_to_wear(asked):
    def confirm(prompt):
        asked.append(prompt)
        return ("no" if "mild wear" in prompt.split("<record>")[1] else "yes"), 0.1
    return confirm


def test_a_recheck_reads_only_what_engram_placed_drops_a_no_for_the_weekly_page_and_remembers_it(placed, monkeypatch):
    from engram import refine
    from engram.cli import main
    asked = []
    monkeypatch.setattr(relink, "_asker", lambda system, effort="low": _no_to_wear(asked))
    main(["theory", "recheck", "loop/1", "--domain", "medical"])  # on request
    assert len(asked) == 1 and "Cold stiffens it." not in asked[0]  # only engram's link to Loop 1; never the owner's
    links = [e for e in store.Store(placed).events(kind="link") if e.fm.get("family") == "evidence"]
    assert {(e.fm["from"], e.fm["to"]) for e in links} == {("consults/walk.md", "loop/1"), ("consults/walk.md", "discovery/D01")}
    assert "Engram-Fix:" in git(placed, "log", "-1", "--format=%B") and len(refine._landed(placed)) == 1
    asked.clear()
    relink.recheck(placed, ["discovery/D01"], confirm=_no_to_wear(asked))
    assert len(asked) == 1 and len(store.Store(placed).events(kind="link")) == 5  # a yes keeps it

    def ask(prompt):
        return json.dumps({"links": [{"record": "consults/visit.md", "to": "loop/1", "rel": "weakens",
                                      "passage": "the knee scan shows mild wear"}]}), 0.5
    out = relink.sweep(placed, ask=ask, confirm=lambda p: ("yes", 0.1), dry_run=True)
    assert not out["links"] and [d["why"] for d in out["dropped"]] == ["dropped on re-reading; its target hasn't changed since"]
    (placed / "theory/loop-1.md").write_text((placed / "theory/loop-1.md").read_text() + "\nThe knee wears first.\n")
    relink._progress(store.Store(placed), True).unlink()  # read the record afresh against the changed loop
    assert [x["from"] for x in relink.sweep(placed, ask=ask, confirm=lambda p: ("yes", 0.1), dry_run=True)["links"]] == ["consults/visit.md"]


def test_the_weekly_sweep_rereads_what_engram_placed_on_a_target_that_changed(placed):
    quiet = lambda prompt: (json.dumps({"links": []}), 0.5)
    asked = []
    first = relink.sweep(placed, ask=quiet, confirm=_no_to_wear(asked))
    assert first["batches"] == 1 and not asked  # nothing changed yet: nothing re-read
    (placed / "theory/loop-1.md").write_text((placed / "theory/loop-1.md").read_text() + "\nThe knee wears first.\n")
    git(placed, "commit", "-qam", "loop 1 sharpened")
    out = relink.sweep(placed, ask=quiet, confirm=_no_to_wear(asked))
    assert len(asked) == 1 and "The knee wears first." in asked[0] and out["recheck"]["dropped"] == 1
    asked.clear()
    assert relink.sweep(placed, ask=quiet, confirm=_no_to_wear(asked))["batches"] == 0 and not asked  # read once per change


def test_a_structural_change_rereads_what_engram_placed_on_the_loop_against_its_new_path(placed):
    r = tc.apply(placed, INSERT, why="hip tightness sits between them")
    asked = []
    relink.run(r.change, ask=lambda p: (json.dumps({"links": []}), 0.1), confirm=_no_to_wear(asked))
    assert len(asked) == 1 and "stiffness → knee → hip → ankle → stiffness" in asked[0]
    assert ("consults/visit.md", "loop/1") not in {(e.fm["from"], e.fm["to"]) for e in store.Store(placed).events(kind="link")}


def test_a_page_row_restating_an_entry_counts_as_that_entry_not_again(rec):
    st = store.Store(rec)
    st.add({"id": "e2", "title": "knee locks on the stairs", "date": "2026-03-05", "kind": "observation",
            "about": ["series/_observations"]}, "- knee locks on the stairs, worse going down\n")
    st.add({"id": "e3", "title": "ankle swells after the long drive", "date": "2026-03-06", "kind": "observation",
            "about": ["series/_observations"]}, "- ankle swells after the long drive\n")
    (rec / "complaints").mkdir()
    (rec / "complaints/knee.md").write_text("# Knee\n\n| date | what | entry |\n|---|---|---|\n"
                                            "| 2026-03-05 | knee locks on the stairs | [e2](../events/e2.md) |\n"
                                            "| 2026-03-06 | ankle swells after the long drive | [e3](../events/e3.md) |\n"
                                            "| 2026-03-07 | knee sore | |\n")

    def ask(prompt):
        return json.dumps({"links": [
            {"record": "e2", "to": "loop/1", "rel": "strengthens", "passage": "knee locks on the stairs"},
            {"record": "complaints/knee.md", "to": "loop/1", "rel": "strengthens", "passage": "knee locks on the stairs"},  # a repeat of e2
            {"record": "complaints/knee.md", "to": "loop/1", "rel": "weakens", "passage": "ankle swells after the long drive"},  # e3's
            {"record": "complaints/knee.md", "to": "loop/1", "rel": "weakens", "passage": "Knee"}]}), 0.5  # in e1 and e2: unclear
    out = relink.sweep(rec, ask=ask, confirm=lambda p: ("yes", 0.1), dry_run=True)
    assert [(m["record"], m["entry"]) for m in out["moved"]] == [("complaints/knee.md", "e2"), ("complaints/knee.md", "e3")]
    assert [d["why"] for d in out["dropped"]] == ["already linked"]
    assert sorted((x["from"], x["rel"], x["date"]) for x in out["confirmed"]) == [
        ("complaints/knee.md", "weakens", ""), ("e2", "strengthens", "2026-03-05"), ("e3", "weakens", "2026-03-06")]
    owner_of = relink._entry_of(relink.records(rec))
    assert owner_of("complaints/knee.md", "after the long drive") == ("e3", "2026-03-06")
    assert owner_of("consults/visit.md", "after the long drive") is None  # a reason that isn't the document's own words
