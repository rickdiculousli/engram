import importlib.util
import json
import sqlite3
from pathlib import Path

from test_capture import TOML, reply, said  # noqa: F401  (the capture world's fixture and session helpers)
from test_capture import world  # noqa: F401
from engram import capture

spec = importlib.util.spec_from_file_location("medical_gate", Path(__file__).parent.parent / "bench/medical_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_compare_names_each_difference_and_ignores_meta():
    a = {"meta": {"at": "1"}, "index": {"doc": {"rows": 3, "hash": "x"}}, "filer": {"s1": {"asks": 1}}}
    b = {"meta": {"at": "2"}, "index": {"doc": {"rows": 3, "hash": "y"}}, "filer": {"s1": {"asks": 1}, "s2": {"asks": 0}}}
    assert gate.compare(a, a | {"meta": {"at": "9"}}) == []
    assert gate.compare(a, b) == ["filer.s2.asks: (missing) -> 0", "index.doc.hash: x -> y"]


def test_index_hash_ignores_row_order_timestamps_and_new_columns(tmp_path):
    cols = {"doc": ["ref", "title"]}

    def build(p, rows, extra=False):
        c = sqlite3.connect(p)
        c.execute("CREATE TABLE doc (id INTEGER PRIMARY KEY, ref TEXT, title TEXT, recorded TEXT)")
        c.executemany("INSERT INTO doc (ref, title, recorded) VALUES (?, ?, ?)", rows)
        if extra:
            c.execute("ALTER TABLE doc ADD COLUMN lens TEXT")
        c.commit()
        c.close()
        return gate.index_hash(p, cols)
    one = build(tmp_path / "a.sqlite", [("r1", "a", "t1"), ("r2", "b", "t1")])
    assert one == build(tmp_path / "b.sqlite", [("r2", "b", "t9"), ("r1", "a", "t8")], extra=True)
    assert one != build(tmp_path / "c.sqlite", [("r1", "a", "t1"), ("r2", "B", "t1")])
    assert gate.index_hash(tmp_path / "a.sqlite", {"missing": ["x"]}) == {"missing": {"rows": 0, "hash": gate.sha("")}}


def test_replies_answer_by_kind_and_count_what_was_not_recorded():
    rep = gate.Replies([{"kind": "facts", "prompt": gate.sha("p1"), "reply": "F"},
                        {"kind": "verify", "prompt": gate.sha("other"), "reply": "V"}])
    assert rep.ask("verify")("v1") == ("V", 0.0)
    assert rep.ask("facts")("p1") == ("F", 0.0)
    assert rep.ask("facts")("p2") == ("{}", 0.0)
    assert (rep.unrecorded, rep.matched, len(rep.prompts)) == (1, 1, 3)


def test_a_replayed_session_is_stable_and_a_changed_reply_shows(world):
    facts = [{"line": 7, "text": "Sam started Orvexa, 1 tablet 40 mg, on 2026-10-15.", "quote": "I started Orvexa, 1 tablet 40 mg, on 2026-10-15",
              "date": "2026-10-15", "kind": "observation", "about": ["story/ankle"]}]

    def replay(recorded):
        rep = gate.Replies(recorded)
        res = capture.file_session("medical", world["repo"], world["path"], dry_run=True,
                                   ask=rep.ask("facts"), ask_verify=rep.ask("verify"), ask_structure=rep.ask("structure"))
        return gate.filer_result(res, rep)
    recorded = [{"kind": "facts", "prompt": "", "reply": json.dumps({"facts": facts})},
                {"kind": "verify", "prompt": "", "reply": json.dumps({"repeats": []})}]
    one = replay(recorded)
    assert one == replay(recorded) and one["would_file"]["n"] == 1 and one["asks"] == 2 and one["unrecorded"] == 0
    other = replay([{**recorded[0], "reply": json.dumps({"facts": [{**facts[0], "date": "2026-10-14"}]})}, recorded[1]])
    changed = [d.split(":")[0] for d in gate.compare({"filer": one}, {"filer": other})]
    assert changed == ["filer.prompts", "filer.would_file.hash"]  # the verify prompt shows the date; the entry holds it
