"""Change 8 of the inner-work spec: a chat starts with where the last session stopped (tests 65-71). A chat that hasn't
been saved yet is named by its id, with the command that prints it (`engram session <id>`)."""
import builtins
import io
import json
import re
import socket
from datetime import datetime, timezone

import pytest

from engram import cli, hourly
from engram import now as now_mod
from engram.sources import sessions
from inner_work import Model, add, chat1_note, chat_id, inner, made, on_day, zone  # noqa: F401  (fixtures)

STOPPED = ["I want to try saying it at sunday dinner.", "Next time we can start from the sentence and the ten-year-old."]
UNSAVED = re.compile(r"(isn't|not been|not) saved yet")


def start(w, chat: int = 9, source: str = "startup") -> str:
    return hourly.session_start({"cwd": str(w.repo), "session_id": chat_id(chat), "source": source})


def noted(w, monkeypatch):
    """The exercise's first session saved as its note; the next evening."""
    w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["about"] = ["theme/going-quiet"]
    w.run(Model(reply))
    on_day(monkeypatch, datetime(2026, 11, 5, 3, tzinfo=timezone.utc))


def test_65_the_next_day_a_chat_opens_with_the_notes_where_you_stopped_and_nothing_else_of_it(inner, monkeypatch):
    w = inner()
    noted(w, monkeypatch)
    out = start(w)
    assert all(words in out for words in STOPPED)
    assert "2026-11-03" in out and "going quiet" in out  # the note's date and themes
    assert "chest. tight." not in out and "my hands stopped shaking" not in out


def test_66_each_thing_saved_since_the_note_is_one_line_and_nothing_older_is(inner, monkeypatch):
    w = inner()
    noted(w, monkeypatch)
    new = ["Told his sister about the sentence", "Slept badly before the dinner"]
    for title in new:
        add(w, {"title": title, "date": "2026-11-04", "kind": "observation", "about": [], "by": "sam"}, f"- {title}\n")
    lines = start(w).splitlines()
    assert [sum(title in l for l in lines) for title in new] == [1, 1]
    assert not [l for l in lines if "Went quiet when his manager criticised the plan" in l]


def test_a_thing_said_before_the_note_and_saved_after_it_is_not_saved_since(inner, monkeypatch):
    """Since is when he said it (`reported`): a row he typed the day before the note, saved in the run that wrote it, or
    an old chat filed late, isn't new to the next chat; what he said after it is."""
    w = inner()
    noted(w, monkeypatch)  # the run that saves the note saves his gym row of 11-02 too
    add(w, {"title": "Said long before the note", "date": "2026-10-01", "reported": "2026-11-01", "kind": "observation",
            "about": [], "by": "sam"}, "- Said long before the note\n")
    add(w, {"title": "Remembered a dinner when he was ten", "date": "2010", "reported": "2026-11-04", "kind": "observation",
            "about": [], "by": "sam"}, "- Remembered a dinner when he was ten\n")
    out = start(w)
    assert "spoke first in the meeting" not in out and "Said long before the note" not in out
    assert "Remembered a dinner when he was ten" in out


def test_67_a_picture_too_long_to_print_is_cut_and_where_you_stopped_is_kept(inner, monkeypatch):
    w = inner()
    noted(w, monkeypatch)
    monkeypatch.setattr(now_mod, "text", lambda *a, **k: "where things stand\n" + "- a long line of the picture\n" * 800)
    out = start(w)
    assert len(out) <= hourly.HOOK_BUDGET and hourly.MORE in out
    assert all(words in out for words in STOPPED)


def with_a_tool_call(lines: list[str]) -> list[str]:
    """The chat with a tool call of the guide's and its output after its first message, as Claude Code writes them."""
    first = json.loads(lines[0])
    call = {**first, "type": "assistant", "uuid": "5e110000-0000-4000-8000-0003aaaaaaaa", "message": {
        "role": "assistant", "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "engram now --secret-call"}}]}}
    result = {**first, "uuid": "5e110000-0000-4000-8000-0003bbbbbbbb", "message": {
        "role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "TOOL OUTPUT NOBODY SAID"}]}}
    out = [first, call, result, *map(json.loads, lines[1:])]
    for a, b in zip(out, out[1:]):
        b["parentUuid"] = a["uuid"]
    return [json.dumps(r) for r in out]


def test_68_ten_minutes_after_the_last_chat_one_line_says_it_isnt_saved_and_a_command_prints_it(inner, monkeypatch, capsys):
    w = inner()
    w.chat(3, lines=with_a_tool_call(w.chat(3).read_text().splitlines()))
    on_day(monkeypatch, datetime(2026, 11, 9, 16, 12, tzinfo=timezone.utc))  # ten minutes after its last message
    out = start(w)
    said = [l for l in out.splitlines() if UNSAVED.search(l)]
    assert len(said) == 1 and chat_id(3) in said[0]
    capsys.readouterr()
    cli.main(["session", chat_id(3)])
    printed = capsys.readouterr().out
    assert "quick check-in: I did the breathing this morning." in printed and "Have a good day." in printed
    assert "secret-call" not in printed and "TOOL OUTPUT" not in printed


@pytest.mark.parametrize("source", ["resume", "compact"])
def test_69_the_chat_being_resumed_or_compacted_is_never_the_unsaved_last_session(inner, monkeypatch, source):
    w = inner(2, 3)
    on_day(monkeypatch, datetime(2026, 11, 9, 16, 12, tzinfo=timezone.utc))
    said = [l for l in start(w, chat=3, source=source).splitlines() if UNSAVED.search(l)]
    assert len(said) == 1 and chat_id(2) in said[0] and chat_id(3) not in said[0]


def test_70_chat_start_calls_no_model_and_no_network_and_reads_only_the_latest_earlier_chat(inner, monkeypatch):
    w = inner(2, 3)
    on_day(monkeypatch, datetime(2026, 11, 9, 16, 12, tzinfo=timezone.utc))

    def no(*a, **k):
        raise AssertionError("chat start reached past this box")
    for target in ("engram.capture._ask", "engram.summarize._claude", "engram.relink._ask", "engram.recsum._ask"):
        monkeypatch.setattr(target, no)
    monkeypatch.setattr(socket, "socket", no)
    read, real = [], io.open

    def spy(file, *a, **k):
        if str(file).startswith(str(w["chats"])):
            read.append(str(file))
        return real(file, *a, **k)
    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    parsed, parse = [], sessions.parse
    monkeypatch.setattr(sessions, "parse", lambda path, *a, **k: parsed.append(str(path)) or parse(path, *a, **k))
    out = start(w)
    assert [l for l in out.splitlines() if UNSAVED.search(l) and chat_id(3) in l]
    assert set(read + parsed) == {str(w["chats"] / f"{chat_id(3)}.jsonl")}


@pytest.mark.parametrize("opener", ["Act as the reviewer sub-agent for this task. Review the last commit.",
                                    "You are executor inner-work/fix-1 in buildermesh. Build the piece."])
def test_an_agents_chat_in_a_worktree_of_the_record_is_never_the_unsaved_last_session(inner, monkeypatch, opener):
    """A delegate or an executor at work in the record, or in one of its worktrees, is no session of his."""
    w = inner(3)
    on_day(monkeypatch, datetime(2026, 11, 9, 16, 12, tzinfo=timezone.utc))
    tree = w["tmp"] / "projects/-home-sam--bmesh-worktrees-inner-work-fix-1"
    tree.mkdir()
    (tree / f"{chat_id(20)}.jsonl").write_text("\n".join(made(20, "2026-11-09T16:05:00", [("O", opener), ("G", "Done.")])) + "\n")
    assert not [l for l in start(w).splitlines() if UNSAVED.search(l)]


def test_a_chat_marked_skipped_is_never_the_unsaved_last_session(inner, monkeypatch):
    w = inner(3)
    on_day(monkeypatch, datetime(2026, 11, 9, 16, 12, tzinfo=timezone.utc))
    path = w["chats"] / f"{chat_id(3)}.jsonl"
    with sessions._state() as st:
        st.execute("INSERT INTO file (path, bytes, mtime_ns, domain, exchanges, docs, seen) VALUES (?, ?, ?, 'skipped', 0, 0, '')",
                   (str(path), path.stat().st_size, path.stat().st_mtime_ns))
    assert not [l for l in start(w).splitlines() if UNSAVED.search(l)]


def test_71_in_a_repo_with_no_notes_the_start_text_is_unchanged(inner):
    """True today: chat start prints the Bash window's line and `engram now`."""
    w = inner()
    assert start(w) == hourly.READ_WHOLE + "\n\n" + now_mod.text(w.repo)
