import json
from pathlib import Path

import pytest

from conftest import make_repo
from engram import config, search
from engram.index import Doc, open_index
from engram.paths import index_path
from engram.sources import sessions


def turn(kind, content, ts="2026-10-18T20:00:00Z", cwd="/tmp/x"):
    return json.dumps({"type": kind, "timestamp": ts, "cwd": cwd, "message": {"role": kind, "content": content}})


def write_session(root, project, stem, lines):
    p = root / project / f"{stem}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")
    return p


def sources_in(domain):
    idx = open_index(index_path(domain), readonly=True)
    if idx is None:
        return set()
    out = {r[0] for r in idx.db.execute("SELECT DISTINCT source FROM doc")}
    idx.close()
    return out


def filed(domain):
    """The sessions filed into a domain (by stem)."""
    st = sessions._state()
    out = {Path(p).stem for (p,) in st.execute("SELECT path FROM file WHERE domain = ?", (domain,))}
    st.close()
    return out


@pytest.fixture
def world(env):
    tmp = env["tmp"]
    med = make_repo(tmp / "repos/medical_history", {
        "state-events.jsonl": json.dumps({"entity": "Fakezine 10mg", "status": "taking"}) + "\n",
        "logs/fakelog.md": "# Fakelog\n",
    })
    inv = make_repo(tmp / "repos/investments", {"pins.md": "# Pins\n"})
    env["set_repo"]("medical", med)
    env["set_repo"]("investments", inv, sessions_from=["-T-desk-", "/T/desk-"])
    return {"root": tmp / "projects", "doms": config.load()}


def test_a_session_belongs_where_it_was_started(world):
    root = world["root"]
    write_session(root, "-Users-x-repos-medical-history", "m1", [turn("user", "how is the ankle?"), turn("assistant", [{"type": "text", "text": "Better."}])])
    write_session(root, "-Users-x-scratch-a", "t1", [
        turn("user", "check the ledger"),
        turn("assistant", [{"type": "tool_use", "name": "Read", "input": {"file_path": "/Users/x/repos/medical_history/state.md"}}]),
        turn("user", [{"type": "tool_result", "content": "/Users/x/repos/medical_history/state.md"}]),
    ])
    write_session(root, "-Users-x-scratch-b", "w1", [turn("user", "fakezine made me drowsy after the fakelog visit")])
    write_session(root, "-Users-x-repos-investments", "i1", [turn("user", "where does the copper pin stand?")])
    write_session(root, "-Users-x-repos-gametrainer", "g1", [turn("user", "fix the build")])
    out = sessions.ingest(world["doms"], root)
    assert out["read"] == 5
    assert filed("medical") == {"m1"}  # touching its files (t1) or naming its words (w1) doesn't count
    assert filed("investments") == {"i1"} and filed("general") == {"g1", "t1", "w1"}
    assert sessions.ingest(world["doms"], root)["read"] == 0


def test_nothing_of_a_session_is_indexed_and_old_raw_rows_go(world, monkeypatch):
    root = world["root"]
    idx = open_index(index_path("medical"))
    idx.sync_source("sessions:old", [Doc(ref="session:old:1", source="sessions:old", cls="session", kind="exchange", title="t", body="raw turn", pointer="x")])
    idx.sync_source("memory:proj", [Doc(ref="memory:proj/a.md#", source="memory:proj", cls="model", kind="memory", title="t", body="note", pointer="x")])
    idx.sync_source("sessions:old:summary", [Doc(ref="summary:old", source="sessions:old:summary", cls="summary", kind="session-summary", title="t", body="checked", pointer="x")])
    idx.close()
    write_session(root, "-Users-x-repos-medical-history", "m1", [turn("user", "how is the ankle?")])
    (root / "-Users-x-repos-medical-history" / "memory").mkdir()
    (root / "-Users-x-repos-medical-history" / "memory" / "a.md").write_text("# note\nClaude's note")
    out = sessions.ingest(world["doms"], root)
    assert out["removed"] == 2
    assert sources_in("medical") == {"sessions:old:summary"}  # only the checked summary stays


def test_reading_a_repos_files_from_elsewhere_stays_general(world):
    root = world["root"]
    p = write_session(root, "-Users-x-scratch-c", "c1", [turn("user", "plan the week")])
    sessions.ingest(world["doms"], root)
    with p.open("a") as f:
        f.write(turn("assistant", [{"type": "tool_use", "name": "Read", "input": {"file_path": "/Users/x/repos/medical_history/state.md"}}]) + "\n")
    sessions.ingest(world["doms"], root)
    assert filed("general") == {"c1"} and filed("medical") == set()


def test_a_worktree_or_subfolder_of_the_repo_counts(world):
    root = world["root"]
    write_session(root, "-Users-x--t3-worktrees-medical-history-t3code-1a2b", "wt", [turn("user", "how is the ankle?")])
    write_session(root, "-Users-x-elsewhere", "sub", [turn("user", "how is the knee?", cwd=str(world["doms"]["medical"].repo / "logs"))])
    write_session(root, "-Users-x-repos-medical-history-logs", "logs", [turn("user", "hm")])
    sessions.ingest(world["doms"], root)
    assert filed("medical") == {"wt", "sub", "logs"}


def test_a_rewritten_session_is_read_again(world):
    root = world["root"]
    p = write_session(root, "-Users-x-scratch-d", "d1", [turn("user", "first question"), turn("user", "second question")])
    sessions.ingest(world["doms"], root)
    p.write_text(turn("user", "compacted summary") + "\n")
    out = sessions.ingest(world["doms"], root)
    assert (out["read"], out["rewritten"]) == (1, 1)


def test_system_reminders_notifications_and_summaries_are_not_sams_turns(world):
    root = world["root"]
    p = write_session(root, "-Users-x-scratch-e", "e1", [
        turn("user", "<system-reminder>hook text</system-reminder>"),
        turn("user", "<task-notification>done</task-notification>"),
        turn("user", "real question <system-reminder>noise</system-reminder>"),
        turn("user", sessions.SUMMARY + " earlier we tuned the zygomorph setting"),
    ])
    xs = sessions.parse(p, root).exchanges
    assert [(x.line, x.asked, x.summary) for x in xs][:1] == [(3, "real question", False)] and xs[1].summary


def test_desk_seats_are_investments_and_title_generators_are_skipped(world):
    root = world["root"]
    write_session(root, "-private-var-folders-ab-cd-T-desk-9tltwo6d", "s1",
                  [turn("user", "argue the bear case", cwd="/private/var/folders/ab/cd/T/desk-9tltwo6d")])
    write_session(root, "-private-var-folders-ab-cd-T-t3code-claude-title-AbC123", "t1", [turn("user", "title this thread")])
    sessions.ingest(world["doms"], root)
    assert filed("investments") == {"s1"} and filed("skipped") == {"t1"}


def test_eval_work_and_its_subagents_are_skipped(world):
    root = world["root"]
    write_session(root, "-Users-x-scratch-e", "e1", [
        turn("user", "build the question set"),
        turn("assistant", [{"type": "tool_use", "name": "Read", "input": {"file_path": "/Users/x/.local/share/engram/eval/medical.toml"}}]),
    ])
    write_session(root, "-Users-x-scratch-e/e1/subagents", "agent-1", [turn("user", "check the key")])
    sessions.ingest(world["doms"], root)
    assert filed("skipped") == {"e1", "agent-1"}


def test_a_classifier_change_refiles_known_sessions(world, monkeypatch):
    root = world["root"]
    write_session(root, "-Users-x-scratch-g", "g2", [turn("user", "fix the build")])
    sessions.ingest(world["doms"], root)
    assert filed("general") == {"g2"}
    monkeypatch.setattr(sessions, "CLASSIFY_VERSION", "test-next")
    monkeypatch.setattr(sessions, "classify", lambda s, doms: "investments")
    out = sessions.ingest(world["doms"], root)
    assert out["read"] == 1 and filed("investments") == {"g2"} and filed("general") == set()
