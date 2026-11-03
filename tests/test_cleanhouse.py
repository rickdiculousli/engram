"""A record with no rendered log pages: entries indexed as themselves, the theory graph, and where things stand."""
from datetime import date

import pytest

from conftest import make_repo
from engram import labels, now, theory, timeline
from engram.cli import main
from engram.index import open_index
from engram.paths import index_path
from engram.store import Store

TOML = """schema_version = 1
[domain]
name = "medical"
events_dir = "events"
commit = "none"
[index]
events = true
[about]
prefixes = ["story", "series", "node", "loop", "state", "discovery", "treatment", "question"]
[links.timeline]
rels = ["led-to"]
[links.evidence]
rels = ["strengthens", "weakens"]
[links.theory]
rels = ["feeds", "shared-cause", "amplifier"]
[nodes]
loop = "theory/loop-{id}.md#*"
node = "theory/node-{id}.md#*"
[ways.theory]
threads = ["theory/loop-*", "theory/node-*"]
"""


def thread(id_, kind, short, stories, say=(), head=""):
    return (f"---\nid: {id_}\nkind: {kind}\nshort: {short}\nstories: [{', '.join(stories)}]\nsay: [{', '.join(say)}]\n"
            f"since: 2026-03-01\nby: with-claude\n---\n# {head or short}\n\nAbout {short}.\n")


@pytest.fixture
def rec(env):
    files = {".engram/engram.toml": TOML,
             "theory/node-A.md": thread("node/A", "node", "stiffness", ["stiffness"], ["morning stiffness"], "Node A — Morning stiffness"),
             "theory/node-B.md": thread("node/B", "node", "knee", ["knee"], [], "Node B — Knee"),
             "theory/node-C.md": thread("node/C", "node", "sore ankle", ["ankle"], ["sore ankle"], "Node C — Sore ankle"),
             "theory/node-F.md": thread("node/F", "node", "cramp", ["calf"], ["cramp"], "Node F — Cramp"),
             "theory/loop-1.md": thread("loop/1", "loop", "Loop 1", [], ["loop 1"], "Loop 1 — Knee cycle"),
             "theory/loop-5.md": thread("loop/5", "loop", "Loop 5", [], ["loop 5"], "Loop 5 — Calf loop"),
             "evidence/D01-x.md": "---\nid: D01\ntitle: Cold mornings stiffen the knee\n---\n# D01\n\nCold.\n"}
    repo = make_repo(env["tmp"] / "med", files)
    st = Store(repo)
    n = iter(range(10, 99))
    rec = lambda: f"2026-10-01T10:{next(n):02d}:00-07:00"

    def add(**fm):
        body = fm.pop("body", "")
        return st.add({"recorded": rec(), **fm}, body)
    for path, loop in ((["node/A", "node/B", "node/C", "node/A"], "loop/1"), (["node/F", "node/A", "node/F"], "loop/5")):
        for k, (a, b) in enumerate(zip(path, path[1:]), 1):
            add(kind="link", family="theory", rel="feeds", **{"from": a, "to": b}, loop=loop, step=k, title="step")
    join = add(kind="interpretation", title="Join: D01 → Loop 1", date="2026-04-01", about=["discovery/D01", "loop/1"],
               by="with-claude", body="- cold exposes the ankle to the knee cycle")
    add(kind="link", family="theory", rel="shared-cause", **{"from": "discovery/D01", "to": "loop/1"}, strength="high",
        entry=join.id, title="join", body="cold exposes the ankle to the knee cycle")
    ankle = add(kind="symptom", title="Ankle achy", heading="### 2026-09-01 — Ankle achy", date="2026-09-01",
              about=["series/sore-ankle", "story/ankle"], by="sam", milestone="true",
              body="- achy all day\n\n### What helped\n- warm compress")
    add(kind="link", family="evidence", rel="strengthens", **{"from": ankle.id, "to": "discovery/D01"}, title="ev")
    add(kind="symptom", title="Knee tight", date="2026-09-02", about=["series/knee", "story/knee"], by="sam", body="- tight")
    add(kind="symptom", title="Cramp flare", date="2026-09-03", about=["series/calf", "story/calf"], by="sam", body="- tight calf")
    add(kind="symptom", title="Stiffness burst", date="2026-09-04", about=["series/stiffness", "story/stiffness"], by="sam", body="- burst")
    add(kind="status", title="D01 Cold mornings stiffen the knee: confirmed", date="2026-05-01", about=["discovery/D01"], status="confirmed")
    # a medication's chain, in the order the record wrote it
    add(kind="med-change", entity="Tablet X (generic 1%)", status="taking", date="2026-07-01", about=["series/meds"], body="- dose: 1 tablet BID")
    add(kind="med-change", entity="Tablet X (generic 1%)", status="paused", date="2026-08-01", about=["series/meds"])
    add(kind="med-change", entity="Tablet X (generic 1%)", status="taking", date="2026-08-15", about=["series/meds"])
    add(kind="med-change", entity="Pill Y", status="stopped", date="2026-10-10", about=["series/meds"], body="- dose: 10mg")
    add(kind="med-change", entity="Cream Z", status="stopped", date="not-sure", about=["series/meds"],
        body="- note: Stung on the face; no change after 2 weeks.")
    add(kind="med-change", entity="Spray W", status="stopped", date="2026-09-20", about=["series/meds"])
    add(kind="med-change", entity="Spray W", status="taking", date="2026-08-01", about=["series/meds"])  # written later, dated earlier
    add(kind="visit", title="Bracing first adjustment", date="2026-02", about=["series/bracing", "story/knee"], body="- first")
    add(kind="med-change", entity="Pill V", status="taking", date="2026-03-02", about=["series/meds"], body="- dose: 5mg")
    add(kind="med-change", entity="Pill V", status="taking", date="2026-09-10", about=["series/meds"], body="- dose: 10mg")
    add(kind="status", title="Bracing: active", date="2026-07-20", about=["treatment/bracing", "series/bracing"], status="active",
        treatment="Bracing", body="- Bracing: Active, 4-week cycles")
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical"])
    return {"repo": repo, "ankle": ankle.id, "join": join.id}


def test_entries_are_indexed_as_themselves(rec):
    idx = open_index(index_path("medical"), readonly=True)
    row = idx.get(rec["ankle"])
    sub = idx.get(f"{rec['ankle']}#What helped")
    idx.close()
    assert row["source"] == "events" and row["title"].startswith("sore-ankle › ") and row["nid"] == labels.nid(rec["ankle"])
    assert "achy all day" in row["body"] and sub and "warm compress" in sub["body"]
    assert row["stories"] == "ankle" and row["date"] == "2026-09-01"


def test_the_theory_graph_draws_loops_and_keeps_statuses(rec):
    g = theory.load(rec["repo"])
    assert g.draw("loop/1") == "stiffness → knee → sore ankle → stiffness"
    assert [e.rel for e in g.joins()] == ["shared-cause"] and g.joins()[0].entry == rec["join"]
    assert g.status["discovery/D01"][0] == "confirmed"
    assert "loop/1" in g.touched({"knee": 1.0, "ankle": 0.8}) and "loop/5" not in g.touched({"knee": 1.0, "ankle": 0.8})
    assert g.touched({"calf": 1.0}) == ["loop/5"]
    assert "loop/1" in g.touched({"calf": 1.0}, named={"loop/1"})  # a loop the question names always shows
    assert "Loop 1 — Knee cycle\tstiffness → knee → sore ankle → stiffness" in theory.text(g)
    assert "-->|1|" in theory.mermaid(g) and "-.->|shared-cause|" in theory.mermaid(g)


def test_a_timeline_shows_only_the_loops_it_touches_with_their_path(rec):
    _, rows = timeline.chain("medical", [], "my cramp flare")
    loops = [r for r in rows if r.get("theory", "").startswith("Loop")]
    assert [r["theory"] for r in loops] == ["Loop 5"] and loops[0]["what"].endswith("cramp → stiffness → cramp")
    assert not any(r.get("_ref", "").startswith("theory/") for r in rows)  # a thread file is the theory block's, not a row
    _, rows = timeline.chain("medical", ["loop/1"])
    joins = [r for r in rows if r.get("theory") == "join"]
    assert joins and joins[0]["_refs"] == [rec["join"]] and "D01 → Loop 1, shared-cause" in joins[0]["what"]


def test_a_loop_counts_weakening_records_against_it_not_for_it(rec):
    st = Store(rec["repo"])
    knee = next(e for e in st.events() if e.fm.get("title") == "Knee tight")
    cramp = next(e for e in st.events() if e.fm.get("title") == "Cramp flare")
    st.add({"kind": "link", "family": "evidence", "rel": "strengthens", "from": knee.id, "to": "loop/1", "title": "ev"}, "")
    st.add({"kind": "link", "family": "evidence", "rel": "weakens", "from": cramp.id, "to": "loop/1", "title": "ev"}, "")
    main(["ingest", "--domain", "medical"])
    _, rows = timeline.chain("medical", ["knee", "calf"])
    [loop] = [r for r in rows if r.get("theory") == "Loop 1"]
    n = {r["_ref"]: r["n"] for r in rows if "_ref" in r}
    assert loop["for"] == 1 and loop["against"] == [n[cramp.id]]


def _fix(st, to, title, date, recorded, rel="revises", note="- what changed", about=("series/_observations", "story/calf"), body="- fixed.\n"):
    e = st.add({"kind": "observation", "title": title, "date": date, "recorded": recorded, "about": list(about), "by": "sam"}, body)
    st.add({"kind": "link", "family": "evidence", "rel": rel, "from": e.id, "to": to, "title": "fix",
            "recorded": recorded.replace(":00-07", ":30-07"), "date": date}, note)
    return e


def _unit_of(results, ref):
    return next((r for r in results if r["ref"] == ref or ref in r.get("unit", {}).get("members", [])), None)


def test_a_hit_on_an_old_version_returns_the_unit_with_the_current_version_first(rec):
    from engram import search
    st = Store(rec["repo"])
    fix = _fix(st, rec["ankle"], "Ankle achy only in the evening", "2026-10-21", "2026-10-21T10:00:00-07:00",
               note="- when: all day became evening only", body="- Sam: achy in the evening, not all day.\n")
    main(["ingest", "--domain", "medical"])
    results = search.search("ankle achy all day", ["medical"], limit=5)
    refs = [r["ref"] for r in results]
    assert fix.id in refs and rec["ankle"] not in refs  # one result, at its current version
    u = results[refs.index(fix.id)]["unit"]
    assert u["centre"] == fix.id and [l["ref"] for l in u["lines"]] == [rec["ankle"]]
    assert "corrected: when: all day became evening only" in u["text"][1]
    from engram.cli import render
    assert "other versions (current above):" in render(results)
    _, rows = timeline.chain("medical", [], "ankle achy all day")
    by = {r["_ref"]: r for r in rows if "_ref" in r}
    assert fix.id in by and rec["ankle"] not in by  # the corrected row shows its correction inline, never twice
    assert rec["ankle"] in by[fix.id]["_unit"] and "when: all day became evening only" in by[fix.id]["versions"][0]


def test_two_disagreeing_records_come_back_side_by_side(rec):
    from engram import search
    st = Store(rec["repo"])
    other = _fix(st, rec["ankle"], "Ankle achy mornings per the physiotherapist", "2026-09-01", "2026-10-02T10:00:00-07:00",
                 rel="disagrees", note="- when achy: all day against mornings", body="- achy all day? mornings.\n")
    main(["ingest", "--domain", "medical"])
    results = search.search("ankle achy all day", ["medical"], limit=5)
    r = _unit_of(results, rec["ankle"])
    u = r["unit"]
    assert u["disagree"] and {r["ref"], *(l["ref"] for l in u["lines"])} == {rec["ankle"], other.id}
    assert all(l["side"] for l in u["lines"]) and "none is the answer" in u["text"][0]
    assert sum(1 for x in results if x["ref"] in (rec["ankle"], other.id)) == 1


def test_an_as_of_question_centres_on_the_version_current_then(rec):
    from engram import search
    st = Store(rec["repo"])
    old = st.add({"kind": "observation", "title": "Knee clicks when climbing", "date": "2026-05-03", "recorded": "2026-05-03T09:00:00-07:00",
                  "about": ["series/_observations", "story/knee"], "by": "sam"}, "- knee clicks on stairs\n")
    new = _fix(st, old.id, "Knee clicks only on the left", "2026-08-02", "2026-08-02T09:00:00-07:00", about=("series/_observations", "story/knee"),
               note="- side: both knees became the left only", body="- left knee clicks on stairs.\n")
    main(["ingest", "--domain", "medical"])
    then = _unit_of(search.search("did my knee click on stairs in June 2026", ["medical"], limit=5), old.id)
    assert then["ref"] == old.id and then["unit"]["lines"][0]["later"]  # the question's past date
    assert then["unit"]["text"][1].startswith("changed later, 2026-08-02")
    assert _unit_of(search.search("knee clicks on stairs", ["medical"], limit=5), old.id)["ref"] == new.id  # today
    stood = _unit_of(search.search("knee clicks on stairs", ["medical"], limit=5, as_of="2026-06-01", as_it_stood=True), old.id)
    assert stood["ref"] == old.id and not stood["unit"]["lines"] and stood["unit"]["hidden"] == [new.id]


def test_a_past_date_before_every_version_centres_on_the_current_one_unless_read_as_it_stood(rec):
    from engram import search
    st = Store(rec["repo"])
    old = st.add({"kind": "observation", "title": "Knee clicks when climbing", "date": "2026-05-03", "recorded": "2026-08-02T09:00:00-07:00",
                  "about": ["series/_observations", "story/knee"], "by": "sam"}, "- knee clicks on stairs\n")
    new = _fix(st, old.id, "Only the left one", "2026-05-03", "2026-09-05T09:00:00-07:00", about=("series/_observations", "story/knee"),
               note="- side: both knees became the left only", body="- the left only.\n")
    main(["ingest", "--domain", "medical"])
    then = _unit_of(search.search("did my knee click on stairs in June 2026", ["medical"], limit=5), old.id)
    assert then["ref"] == new.id  # every version came after June: none stood then, so the current one
    stood = _unit_of(search.search("knee clicks on stairs", ["medical"], limit=5, as_of="2026-06-01", as_it_stood=True), old.id)
    assert stood["ref"] == old.id and stood["unit"]["hidden"] == [new.id]  # nothing said later shows in full


def test_a_chain_longer_than_six_is_capped(rec):
    from engram import search
    st = Store(rec["repo"])
    fixes, to = [], rec["ankle"]
    for k in range(8):  # one line through time: each revises the one before
        fixes.append(_fix(st, to, f"Ankle achy revision {k}", f"2026-10-{k + 10}", f"2026-10-{k + 10}T10:00:00-07:00",
                          rel="supersedes" if k % 2 else "revises", note=f"- revision {k}"))
        to = fixes[-1].id
    main(["ingest", "--domain", "medical"])
    results = search.search("ankle achy all day", ["medical"], limit=5)
    r = _unit_of(results, rec["ankle"])
    u = r["unit"]
    assert len(u["members"]) == 9 and len(u["lines"]) == 5 and u["more"] == 3
    assert "3 more versions" in u["text"]
    assert rec["ankle"] in [l["ref"] for l in u["lines"]]  # the hit is always shown
    assert not {x["ref"] for x in results if x is not r} & ({f.id for f in fixes} | {rec["ankle"]})


def test_two_siblings_correcting_one_record_stay_separate_units_sharing_it(rec):
    from engram import search
    st = Store(rec["repo"])
    a = _fix(st, rec["ankle"], "Ankle achy only in the evening", "2026-10-20", "2026-10-20T10:00:00-07:00", note="- when: evening",
             body="- evening grit.\n")
    b = _fix(st, rec["ankle"], "Warm compress stopped helping", "2026-10-21", "2026-10-21T10:00:00-07:00", note="- compress: no longer helps",
             body="- compress no longer helps.\n")
    main(["ingest", "--domain", "medical"])
    ua = _unit_of(search.search("evening grit", ["medical"], limit=5), a.id)["unit"]
    ub = _unit_of(search.search("compress no longer helps", ["medical"], limit=5), b.id)["unit"]
    assert set(ua["members"]) == {a.id, rec["ankle"]} and set(ub["members"]) == {b.id, rec["ankle"]}
    assert [l["ref"] for l in ua["lines"]] == [rec["ankle"]] == [l["ref"] for l in ub["lines"]]


def test_a_unit_takes_one_top_five_place(rec):
    from engram import search
    st = Store(rec["repo"])
    to = rec["ankle"]
    for k in range(3):  # a chain of three corrections, each of the one before
        to = _fix(st, to, f"Ankle achy all day, take {k}", "2026-10-2" + str(k), f"2026-10-2{k}T10:00:00-07:00", note=f"- take {k}",
                  body="- ankle achy all day.\n").id
    for k in range(5):
        st.add({"kind": "symptom", "title": f"Ankle achy again {k}", "date": f"2026-09-1{k}", "recorded": f"2026-10-0{k + 2}T11:00:00-07:00",
                "about": ["series/sore-ankle", "story/ankle"], "by": "sam"}, "- ankle achy\n")
    main(["ingest", "--domain", "medical"])
    results = search.search("ankle achy all day", ["medical"], limit=5)
    r = _unit_of(results, rec["ankle"])
    members = set(r["unit"]["members"])
    assert len(members) == 4 and len(results) == 5
    assert sum(1 for x in results if x["ref"] in members) == 1  # the other places go to other records


def test_an_entry_with_no_story_takes_its_series_or_chain_stories():
    from types import SimpleNamespace as E
    from engram.sources.events import inherited
    evs = [E(about=["series/bracing", "story/knee"], fm={}), E(about=["series/bracing", "story/knee", "story/ankle"], fm={}),
           E(about=["series/meds", "story/calf"], fm={"entity": "Cream Z"}), E(about=["series/meds", "story/ankle"], fm={"entity": "Tablet X"})]
    of = inherited(evs)
    assert of(E(about=["treatment/bracing", "series/bracing"], fm={})) == "knee,ankle"  # most entries first
    assert of(E(about=["series/meds"], fm={"entity": "cream z"})) == "calf"  # its medication's chain, not the pooled series
    assert of(E(about=["series/meds"], fm={})) == ""


def test_an_unplaced_question_sits_on_the_stories_its_words_find(rec):
    (rec["repo"] / "questions").mkdir()
    (rec["repo"] / "questions/Q-achy.md").write_text("---\nid: question/Q-achy\n---\n# Why is the ankle achy all day\n\n- open\n")
    main(["ingest", "--domain", "medical"])
    idx = open_index(index_path("medical"), readonly=True)
    on = {s for (s,) in idx.db.execute("SELECT story FROM on_story WHERE ref LIKE 'questions/Q-achy.md#%'")}
    idx.close()
    assert on == {"ankle"}
