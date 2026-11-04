import json
import subprocess

from engram import evalset


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


def test_grep_reaches_an_entry_by_its_id_when_its_file_was_read_or_grepped(tmp_path, monkeypatch):
    info = {"reads": [str(tmp_path / "events/2026/10/20261022-010221-status-2b2f.md")],
            "greps": [f"{tmp_path}/notes/plan.md:3:Walk daily."], "tokens": 9, "context": 5, "base": 1}
    monkeypatch.setattr(evalset, "_claude", lambda *a, **kw: ("an answer", "", info))
    q = {"id": "q1", "question": "how did it go?", "expect": [],
         "links": [{"refs": ["20261022-010221-status-2b2f"]}, {"refs": ["notes/plan.md#Plan"]}, {"refs": ["20260101-000000-x-0000"]}]}
    row = evalset._grep_one(q, "medical", tmp_path, None)
    assert row["links"] == [True, True, False] and row["grepped"] == ["notes/plan.md"]
