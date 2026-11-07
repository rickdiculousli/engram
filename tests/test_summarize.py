import json
import os
import re
import sqlite3

import pytest

from engram import config, search, summarize
from engram.paths import data_path
from engram.sources import sessions
from test_sessions import turn, world, write_session  # noqa: F401  (world is a fixture)


def reply(text):
    return turn("assistant", [{"type": "text", "text": text}])


def test_segments_overlap_and_hold_still_as_a_session_grows(monkeypatch):
    monkeypatch.setattr(summarize, "SEG_TURNS", 8)
    monkeypatch.setattr(summarize, "SEG_CHARS", 12000)
    turns = [summarize.Turn(i, "2026-10-18T20:00:00", "x" * 1000) for i in range(20)]
    segs = summarize.segments(turns)
    assert all(len(s) <= 8 for s in segs)
    assert [t.line for t in segs[1][:2]] == [t.line for t in segs[0][-2:]]
    assert {t.line for s in segs for t in s} == set(range(20))
    grown = summarize.segments(turns + [summarize.Turn(20, "", "y")])
    assert grown[:len(segs) - 1] == segs[:-1]
    big = [summarize.Turn(1, "", "x" * 13000), summarize.Turn(2, "", "y" * 100)]
    assert [len(s) for s in summarize.segments(big)] == [1, 1]
    # a turn too big to join the overlap still comes in, so no segment sits inside the one before it
    mixed = [summarize.Turn(i, "", "x" * 3000) for i in range(3)] + [summarize.Turn(3, "", "y" * 11000)]
    segs = summarize.segments(mixed)
    assert all(not {t.line for t in b} <= {t.line for t in a} for a, b in zip(segs, segs[1:]))


def test_cleaning_keeps_sams_words_and_names_who_wrote_the_rest(tmp_path):
    root = tmp_path / "p"
    p = write_session(root, "proj", "s1", [
        turn("user", "Base directory for this skill: /x/skills/grilling\n\nLong skill text"), reply("Question one?"),
        turn("user", "my knee is 6/10 since Tuesday"), turn("user", "my knee is 6/10 since Tuesday"), reply("Noted."),
        turn("user", "Another Claude session sent a message: <m>hi</m>"), reply("Thanks."),
        json.dumps({"type": "user", "isMeta": True, "message": {"content": "# Update Config Skill\n\nModify settings."}}),
        turn("user", "This session is being continued from a previous conversation. Summary..."), reply("ok"),
        turn("user", "open a new thread"),
        json.dumps({"type": "assistant", "message": {"stop_reason": "tool_use", "content": [{"type": "text", "text": "Checking the threads."}]}}),
        reply("Opening it."),
        json.dumps({"type": "attachment", "attachment": {"type": "queued_command", "prompt": [{"type": "text", "text": "no, the old thread"}]}}),
        reply("My mistake, the old one."),
    ])
    s = sessions.parse(p, root)
    turns = summarize.clean(s)
    assert [t.text.split(":")[0] for t in turns] == ["Skill loaded", "Sam", "Another Claude session", "Skill loaded", "Sam"]
    assert turns[3].text == "Skill loaded: Update Config Skill"
    assert turns[0].text.startswith("Skill loaded: grilling\n") and "Long skill text" not in turns[0].text
    assert turns[1].text == "Sam: my knee is 6/10 since Tuesday\n\nClaude: Noted."
    assert turns[4].text == ("Sam: open a new thread\n\nClaude: Opening it.\n\nSam (while Claude worked): no, the old thread"
                             "\n\nClaude: My mistake, the old one.")
    q = write_session(root, "proj", "s2", [json.dumps({"type": "user", "entrypoint": "sdk-cli", "message": {"content": "Today is 2026-10-10. Window: ..."}})])
    assert summarize.clean(sessions.parse(q, root)) == []


GOOD = {"topics": ["knee"],
        "claims": [{"line": 10, "text": "Knee pain at 6/10", "relayed_from": "own", "act": "report", "confidence": "unstated",
                    "basis": "his report", "evidence": "my knee is 6/10", "quote": False},
                   {"line": 20, "text": "Ice tonight, and rest", "relayed_from": "own", "act": "advice", "taken_up_at": 30,
                    "uptake_evidence": "I'll ice it tonight",
                    "confidence": "probably",
                    "basis": "inflammation", "evidence": "Ice tonight, and rest", "quote": True}],
        "reported": [{"line": 10, "text": "knee pain began", "when_said": "since Tuesday", "evidence": "6/10 since Tuesday"}],
        "complaints": [{"line": 10, "tag": "new:complaint/knee-pain", "intensity": "6/10", "direction": "worse"}],
        "decisions": [{"line": 30, "text": "Ice it tonight", "why": "not stated", "evidence": "I'll ice it tonight"}],
        "updates": [], "contradictions": [], "filed": [{"line": 30, "what": "knee pain logged", "where": "logs/knee.md"}],
        "open": [], "tenor": {"sam": "worried", "quotes": [{"line": 10, "text": "my knee is 6/10"}]}}
TURNS = {10: "Sam: my knee is 6/10 since Tuesday, worse than 2026-10-01",
         20: "Prompt: what now\n\nClaude: Ice tonight, and rest; it's probably inflamed.",
         30: "Sam: ok I'll ice it tonight\n\nClaude: Good."}
TEXT = "\n\n".join(f"[L{k} · 2026-10-18 20:00]\n{v}" for k, v in TURNS.items())


def bad(**changes):
    out = json.loads(json.dumps(GOOD))
    for path, value in changes.items():
        *keys, last = path.split(".")
        node = out
        for k in keys:
            node = node[int(k)] if k.isdigit() else node[k]
        node[int(last) if last.isdigit() else last] = value
    return summarize.lint(summarize.characterize(out, TURNS), TURNS, TEXT, set())


def test_lint_holds_summaries_to_the_rules():
    assert bad() == []
    assert bad(**{"claims.0.text": 'He said "my knee is 7/10"'})  # a quote that isn't word for word
    assert not bad(**{"claims.0.text": 'He said "my knee is 6/10"'})
    assert bad(**{"claims.0.evidence": "knee pain at six"})  # evidence not in the cited turn
    assert bad(**{"claims.0.line": 30, "claims.0.by": "claude-suggestion"})  # right words, wrong turn
    assert bad(**{"claims.1.taken_up_at": 99})  # taken up in a turn that isn't there
    assert bad(**{"claims.1.taken_up_at": 20})  # ... and that turn must be Sam's
    assert bad(**{"claims.1.uptake_evidence": None})  # ... and quote his words taking it up
    assert bad(**{"claims.1.uptake_evidence": "Good."})  # Claude's words in that turn don't count
    assert bad(**{"claims.0.relayed_from": "the doctor"})  # clinician:<name> (<role>) or other:<source>
    assert not bad(**{"claims.1.relayed_from": "clinician:Dr. Lee (GP)"})  # a relayed finding can be in either's words
    assert bad(**{"claims.1.raised_first_at": 10, "claims.1.raised_first_evidence": "my knee is 6/10"})  # Sam raised it first
    assert not bad(**{"claims.1.raised_first_at": 20, "claims.1.raised_first_evidence": "Ice tonight, and rest"})  # Claude did
    assert bad(**{"claims.1.quote": False})  # advice is quoted exactly
    assert bad(**{"claims.1.relayed_from": "other:drug interaction subagent"})  # Claude's subagent is Claude
    assert bad(**{"decisions.0.text": "commit and push the log"}) and bad(**{"open": [{"line": 20, "text": "add it to the record"}]})
    assert bad(**{"claims.0.act": "decision"}) and bad(**{"claims.0.act": "opinion"})
    assert bad(**{"claims.0.text": "The knee note was filed as noted"})
    assert bad(**{"decisions.0.why": "inflammation"})  # a reason needs Sam's words
    assert bad(**{"decisions.0.why": "inflammation", "decisions.0.why_evidence": "it's probably inflamed"})  # ... not Claude's
    assert not bad(**{"decisions.0.why": "he wants it gone", "decisions.0.why_evidence": "my knee is 6/10"})
    assert bad(**{"open": [{"line": 99, "text": "is it inflamed?", "evidence": "it's probably inflamed"}]})  # a turn that's there
    assert bad(**{"updates": [{"line": 30, "earlier_line": 20, "what": "plan", "before": "rest", "after": "ice"}]})  # no evidence
    assert not bad(**{"updates": [{"line": 30, "earlier_line": 20, "what": "plan", "before": "rest", "after": "ice",
                                   "evidence": "ok I'll ice it tonight"}]})
    assert bad(**{"open": [{"line": 20, "text": "is it inflamed?"}]})  # with words showing it's still open
    assert not bad(**{"open": [{"line": 20, "text": "is it inflamed?", "evidence": "it's probably inflamed"}]})
    asked = {**TURNS, 40: "Sam: should I see someone about it?\n\nClaude: Yes, see your doctor this week."}
    out = json.loads(json.dumps(GOOD))
    out["open"] = [{"line": 40, "text": "whether to see someone", "evidence": "should I see someone about it?"}]
    assert summarize.lint(summarize.characterize(out, asked), asked, TEXT, set())  # his question, answered in the same turn
    out["open"][0]["evidence"] = "should I see someone about it"  # copied without its question mark
    assert summarize.lint(summarize.characterize(out, asked), asked, TEXT, set())
    assert bad(**{"updates": [{"line": 30, "earlier_line": 20, "what": "plan", "before": "", "after": "ice"}]})
    assert bad(**{"decisions.0.line": 20, "decisions.0.evidence": "Ice tonight, and rest"})  # a decision is Sam's
    assert bad(**{"open": [{"line": 20, "text": "the reply was truncated", "evidence": "it's probably inflamed"}]})
    assert bad(**{"claims.0.text": "Claude logged the knee pain in the record"})  # Claude's own record-keeping
    assert bad(**{"claims.0.text": "Knee pain since 2026-10-05"})  # a date the source doesn't have
    assert not bad(**{"claims.0.text": "Worse than on 2026-10-01"})
    assert bad(**{"claims.0.line": 20})  # by sam, on a turn Sam didn't write
    assert bad(**{"claims.0.line": 99})
    assert bad(**{"claims.0.confidence": "fairly confident"})  # not his words, not a status
    assert not bad(**{"claims.0.confidence": "suspected"})
    assert bad(**{"claims.0.basis": ""})
    assert bad(**{"reported.0.when_said": "since Monday"})
    assert bad(**{"complaints.0.tag": "complaint/knee-pain"})  # not in the vocabulary and not marked new
    assert bad(**{"complaints.0.intensity": "7/10"})
    assert bad(**{"tenor.quotes.0.text": "my knee hurts"})
    assert summarize.lint({"topics": []}, TURNS, TEXT, set())


def test_who_said_it_comes_from_where_the_evidence_sits_and_record_notes_are_filed():
    out = summarize.characterize(json.loads(json.dumps(GOOD)), TURNS)
    assert [c["by"] for c in out["claims"]] == ["sam", "with-claude"]
    out = json.loads(json.dumps(GOOD))
    out["claims"][1]["taken_up_at"] = None
    out["claims"][0]["relayed_from"] = "clinician:Dr. Lee (GP)"
    out["claims"].append({"line": 30, "text": "knee logged", "act": "record", "evidence": "Good."})
    out["claims"].append({"line": 20, "text": "is it inflamed?", "act": "question", "evidence": "it's probably inflamed"})
    out = summarize.characterize(out, TURNS)
    assert [c["by"] for c in out["claims"]] == ["clinician:Dr. Lee (GP)", "claude-suggestion"]
    out["claims"][1]["relayed_from"] = "sam"  # Claude passing on Sam's own earlier report
    assert summarize.characterize(out, TURNS)["claims"][1]["by"] == "sam"
    assert out["filed"][-1]["what"] == "knee logged"
    assert out["open"] == [{"line": 20, "text": "is it inflamed?", "evidence": "it's probably inflamed"}]


def test_a_session_is_summarized_stored_indexed_and_withdrawn_with_its_session(world, monkeypatch):
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    p = write_session(root, "-Users-x-repos-health-notes", "m1", [
        turn("user", "my knee is 6/10 since Tuesday, worse than 2026-10-01"), reply("Ice tonight."),
    ])
    old = p.stat().st_mtime - 3 * 3600
    os.utime(p, (old, old))
    sessions.ingest(world["doms"], root)
    calls = []

    def fake(prompt, model):
        calls.append(model)
        out = json.loads(json.dumps(GOOD))
        line = int(prompt.split("<<<\n[L")[1].split(" ")[0])
        out["claims"] = out["claims"][:1]
        for item in out["claims"] + out["reported"] + out["complaints"] + out["tenor"]["quotes"]:
            item["line"] = line
        out["decisions"], out["filed"] = [], []
        return json.dumps(out), {"in": 1000, "out": 200, "usd": 0.001}

    monkeypatch.setattr(summarize, "_claude", fake)
    out = summarize.run()
    assert out["summarized"] == 1 and out["flagged"] == 0 and calls == [summarize.SEGMENT_MODEL] * 2  # a read, then the self-check
    assert summarize.run()["current"] == 1 and len(calls) == 2
    assert summarize.index_all() == {"medical": 1, "investments": 0, "general": 0}
    hits = search.search("knee", ["medical"], limit=5)
    assert any(h["class"] == "summary" and h["ref"] == "summary:m1" for h in hits)
    st = sqlite3.connect(data_path("sessions-state.sqlite"))
    with st:
        st.execute("UPDATE file SET domain = 'skipped' WHERE path = ?", (str(p),))
    summarize.index_all()
    assert not any(h["class"] == "summary" for h in search.search("knee", ["medical"], limit=5))
    assert not list(data_path("summaries").glob("*/*.json"))


def test_a_failed_call_stops_the_run(world, monkeypatch):
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    for i in range(3):
        p = write_session(root, "-Users-x-repos-health-notes", f"m{i}", [turn("user", "hello"), reply("hi")])
        os.utime(p, (p.stat().st_mtime - 3 * 3600,) * 2)
    sessions.ingest(world["doms"], root)

    def limit(prompt, model):
        raise summarize.Unavailable("You've hit your weekly limit")

    monkeypatch.setattr(summarize, "_claude", limit)
    out = summarize.run(workers=1)
    assert out["stopped"] == "You've hit your weekly limit" and out["summarized"] == 0


def test_a_long_session_is_stitched_in_groups_then_once_more(world, monkeypatch):
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    monkeypatch.setattr(summarize, "GROUP", 3)
    for name, value in {"SEG_TURNS": 8, "SEG_CHARS": 12000, "SECOND_PASS": True, "SEGMENT_MODEL": "segment-model",
                        "STITCH_MODEL": "stitch-model"}.items():
        monkeypatch.setattr(summarize, name, value)
    lines = []
    for i in range(30):
        lines += [turn("user", f"a question about the same topic {i}"), reply(f"answer {i}")]
    p = write_session(root, "-Users-x-repos-health-notes", "long", lines)
    os.utime(p, (p.stat().st_mtime - 3 * 3600,) * 2)
    sessions.ingest(world["doms"], root)
    calls, prompts = [], []

    def fake(prompt, model):
        calls.append(model)
        prompts.append(prompt)
        claim = {"text": "x", "relayed_from": "own", "act": "report", "confidence": "unstated", "basis": "y", "evidence": "a question about the",
                 "quote": False}
        if model == summarize.SEGMENT_MODEL:
            line = int(prompt.split("<<<\n[L")[1].split(" ")[0])
            return json.dumps({"topics": [], "claims": [{**claim, "line": line}], "reported": [], "complaints": [],
                               "decisions": [], "updates": [], "contradictions": [], "filed": [], "open": [],
                               "tenor": {"sam": "calm", "quotes": []}}), {"usd": 0.01}
        line = int(prompt.split('"first_line": ')[1].split(",")[0])
        return json.dumps({"topics": [], "chronology": [{**claim, "line": line}], "reported": [], "complaints": [],
                           "decisions": [], "updates": [], "contradictions": [], "filed": [], "open": [],
                           "tenor": {"arc": "calm", "quotes": []}}), {"usd": 0.1}

    monkeypatch.setattr(summarize, "_claude", fake)
    assert summarize.run()["flagged"] == 0
    data = json.loads((summarize.store_dir("medical") / "long.json").read_text())
    assert len(data["segments"]) == 5 and data["stitch"]["parts"] == 2
    assert calls.count(summarize.STITCH_MODEL) == 3 and calls.count(summarize.SEGMENT_MODEL) == 10
    assert all(g["pass"] == "second" for g in data["segments"])
    second = [p for p in prompts if "this segment, first reading: " in p]
    assert len(second) == 5 and "after: " in second[0] and "before: " not in second[0] and "before: " in second[-1]


def test_a_long_one_segment_session_keeps_its_segments_cap(world, monkeypatch):
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    lines = []
    for i in range(70):
        lines += [turn("user", f"a question about the same topic {i} " + "x" * 600), reply(f"answer {i}")]
    p = write_session(root, "-Users-x-repos-health-notes", "one", lines)
    os.utime(p, (p.stat().st_mtime - 3 * 3600,) * 2)
    sessions.ingest(world["doms"], root)

    def fake(prompt, model):
        lines = sorted({int(x) for x in re.findall(r"^\[L(\d+) ", prompt.split("<<<\n", 1)[1], re.M)})
        claims = [{"line": n, "text": "x", "relayed_from": "own", "act": "report", "confidence": "unstated", "basis": "y",
                   "evidence": "a question about the", "quote": False} for n in lines[:65]]
        return json.dumps({"topics": [], "claims": claims, "reported": [], "complaints": [], "decisions": [], "updates": [],
                           "contradictions": [], "filed": [], "open": [], "tenor": {"sam": "calm", "quotes": []}}), {"usd": 0.01}

    monkeypatch.setattr(summarize, "_claude", fake)
    assert summarize.run()["flagged"] == 0
    data = json.loads((summarize.store_dir("medical") / "one.json").read_text())
    assert len(data["segments"]) == 1 and len(data["stitch"]["summary"]["chronology"]) == 65 and not data["stitch"]["lint"]


def test_a_summary_is_withdrawn_once_its_session_turns_out_to_be_a_programs_run(world, monkeypatch):
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    p = write_session(root, "-private-var-folders-x-T-seat-abc", "d1", [turn("user", "# Scout packet, week to 2026-10-10"), reply("ok")])
    os.utime(p, (p.stat().st_mtime - 3 * 3600,) * 2)
    sessions.ingest(world["doms"], root)
    dom = sqlite3.connect(data_path("sessions-state.sqlite")).execute("SELECT domain FROM file").fetchone()[0]
    stale = summarize.store_dir(dom) / "d1.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    summarize.run()
    assert not stale.exists()


def test_a_child_claude_never_inherits_the_calling_sessions_effort(monkeypatch):
    from engram import claude_env
    monkeypatch.setenv("CLAUDE_EFFORT", "xhigh")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/x")
    env = claude_env.clean(ENGRAM_TAG="t")
    assert "CLAUDE_EFFORT" not in env and "CLAUDE_CODE_SESSION_ID" not in env
    assert env["CLAUDE_CONFIG_DIR"] == "/x" and env["ENGRAM_TAG"] == "t"


def test_items_that_still_fail_after_the_retry_are_dropped_and_the_rest_stands(monkeypatch):
    out = json.loads(json.dumps(GOOD))
    out["claims"].append({**GOOD["claims"][0], "evidence": "words that are not there"})
    replies = iter([json.dumps(out), json.dumps(out)])
    monkeypatch.setattr(summarize, "_claude", lambda prompt, model: (next(replies), {}))
    got = summarize._ask("p", summarize.SEGMENT_MODEL, TURNS, TEXT, set(), False)
    assert got["tries"] == 2 and not got["flagged"] and len(got["dropped"]) == 1
    assert len(got["summary"]["claims"]) == 2


def test_a_delegated_agents_session_is_never_the_owners_words(tmp_path):
    ex = lambda text: sessions.Exchange(line=1, ts="2026-10-01T10:00:00Z", asked=text)
    agent = sessions.Session(path=tmp_path / "a.jsonl", stem="a", project="-home-sam-notes", entrypoint="sdk-ts",
                             exchanges=[ex("Act as the review sub-agent for this task.\n\nReview the beds"), ex("and the log")])
    mine = sessions.Session(path=tmp_path / "b.jsonl", stem="b", project="-home-sam-notes", entrypoint="sdk-ts",
                            exchanges=[ex("which bed for the tomatoes?")])
    assert summarize.speaker(agent, "and the log", "Sam") == ("Prompt", "and the log")
    assert summarize.speaker(mine, "which bed for the tomatoes?", "Sam") == ("Sam", "which bed for the tomatoes?")


def test_a_session_cleaned_up_here_is_fetched_again_only_if_something_could_have_changed(world, env, monkeypatch):
    monkeypatch.setattr(summarize, "LAUNCHED", ("-T-desk-",))
    root = sessions.ROOT
    sql = sqlite3.connect(data_path("sessions-state.sqlite"))
    sql.execute("CREATE TABLE IF NOT EXISTS file (path TEXT PRIMARY KEY, bytes INTEGER, mtime_ns INTEGER, head_sha TEXT, "
                "domain TEXT, exchanges INTEGER, docs INTEGER, rewrites INTEGER DEFAULT 0, seen TEXT, gone TEXT)")
    gone = {n: root / folder / f"{n}.jsonl" for n, folder in
            [("kept", "proj"), ("old", "proj"), ("lost", "proj"), ("seat", "x-T-desk-1")]}
    for p in gone.values():
        sql.execute("INSERT OR REPLACE INTO file (path, domain, gone) VALUES (?, 'medical', 'now')", (str(p),))
    sql.commit()
    sql.close()
    now = {"segment": summarize.segment_version("medical"), "stitch": summarize.STITCH_VERSION}
    d = summarize.store_dir("medical")
    d.mkdir(parents=True, exist_ok=True)
    (d / "kept.json").write_text(json.dumps({"prompt_version": now}))
    (d / "old.json").write_text(json.dumps({"prompt_version": {**now, "stitch": "older"}}))
    assert sorted(p.stem for p, _ in summarize.known_sessions("medical")) == ["lost", "old"]
    assert [p.stem for p, _ in summarize.known_sessions("medical", ["kept"])] == ["kept"]  # asked for by name
