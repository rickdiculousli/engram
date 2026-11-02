import json
import sqlite3
from datetime import datetime, timezone

import pytest

from conftest import make_repo
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
            {"record": "consults/visit.md", "to": "loop/1", "rel": "weakens", "why": "wear"},
            {"record": "consults/visit.md", "to": "discovery/D01", "rel": "strengthens", "why": "cold"},
            {"record": "e1", "to": "loop/1", "rel": "weakens", "why": "knee sore"},  # the pair is linked already
            {"record": "j1", "to": "loop/1", "rel": "strengthens", "why": "x"},  # journals aren't read
            {"record": "e1", "to": "node/A", "rel": "strengthens", "why": "x"},  # a condition isn't a target
            {"record": "e1", "to": "discovery/D01", "rel": "causes", "why": "x"}]}), 0.5

    def confirm(prompt):
        checks.append(prompt)
        return ("Yes." if "Loop 1" in prompt else "no"), 0.1
    out = relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True)
    assert "felt low" not in reads[0] and "Cold stiffens it." in reads[0] and "path: stiffness → knee → ankle → stiffness" in reads[0]
    assert out["proposed"] == 6 and len(out["links"]) == 2 and sorted(d["why"] for d in out["dropped"]) == [
        "already linked", "not a record of this batch", "target node/A isn't a loop or Discovery", "unknown rel causes"]
    assert len(checks) == 2 and all("The knee scan shows mild wear." in c and "wear" not in c.split("<record>")[0] for c in checks)
    assert [(x["from"], x["to"]) for x in out["confirmed"]] == [("consults/visit.md", "loop/1")] and len(out["rejected"]) == 1
    assert round(out["usd"], 2) == 0.7 and not [e for e in store.Store(rec).events(kind="link") if e.fm.get("author") == relink.SWEPT]
    relink.sweep(rec, ask=ask, confirm=confirm)
    [filed] = [e for e in store.Store(rec).events(kind="link") if e.fm.get("author") == relink.SWEPT]
    assert (filed.fm["from"], filed.fm["to"], filed.fm["rel"], filed.fm["by"]) == ("consults/visit.md", "loop/1", "weakens", "claude")
    again = relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True)  # what it filed is held now
    assert [x["to"] for x in again["links"]] == ["discovery/D01"]  # the rejected one is asked again, the filed one isn't
    assert "already linked" in [d["why"] for d in again["dropped"] if d["record"] == "consults/visit.md"]
    capped = relink.sweep(rec, ask=ask, confirm=confirm, dry_run=True, cap=0.5)
    assert capped["stopped"] and not capped["confirmed"]
