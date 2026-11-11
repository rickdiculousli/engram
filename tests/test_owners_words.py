"""What the owner typed is the owner's: a message sent again after Claude answered isn't a retry, and words that only
open the way a program's prompt does aren't one."""
import json
import os

import pytest

from engram import capture, summarize
from engram.sources import sessions
from test_sessions import turn, world, write_session  # noqa: F401  (world is a fixture)
from test_zone import server  # noqa: F401  (a fixture)

LEAD = ("You are the lead of spec 12, which the operator picked in `garden` (`/home/x/repos/garden`), dispatched 2026-11-01. "
        "You are in a fresh worktree on your own branch. Follow the `lead` skill.\n\n## This repo\n\n"
        + "The beds, the log and the seed list. " * 60 + "\n\n## The spec\n\n" + "Plant the tomatoes in bed two. " * 20)
SHAS = ['721808750d5fe9be']  # the segment ids this session had before the change
DELEGATE = "Act as the review sub-agent for this task.\n\n# The job\n\nReview the beds and say what's wrong with each."


def reply(text):
    return turn("assistant", [{"type": "text", "text": text}])


def read(root, lines, stem="s1", project="-home-sam-notes"):
    return sessions.parse(write_session(root, project, stem, lines), root)


def sams(s):
    """What the filer takes as Sam's, and what the summarizer shows as his."""
    return list(capture.owners(s).values()), [t.text for t in summarize.clean(s) if t.text.startswith("Sam: ")]


def test_the_same_short_answer_to_two_questions_is_two_answers(tmp_path):  # test 10
    s = read(tmp_path, [turn("user", "can we go through the week?"), reply("Did you sleep?"), turn("user", "yeah"),
                        reply("And did you eat?"), turn("user", "yeah"), reply("Good.")])
    text = summarize.render_turns(summarize.clean(s))
    assert text.index("Did you sleep?") < text.index("Sam: yeah") < text.index("And did you eat?") < text.rindex("Sam: yeah")
    assert text.count("Sam: yeah") == 2 and capture.conversation(s, 0) == text
    assert capture.turn_before(s) == {1: "", 3: "Did you sleep?", 5: "And did you eat?"}


def test_a_message_sent_again_with_nothing_between_keeps_only_the_second(tmp_path):  # test 11, true today
    s = read(tmp_path, [turn("user", "my knee is 6/10"), turn("user", "my knee is 6/10"), reply("Noted.")])
    assert [t.line for t in summarize.clean(s)] == [2]


@pytest.mark.parametrize("words", ["You are the one who always says I'm lazy.",  # test 12
                                   "Today is 2026-11-11 and I can't get up"])  # test 13
def test_words_that_open_like_a_programs_prompt_mid_chat_are_his(tmp_path, words):
    s = read(tmp_path, [turn("user", "can we talk?"), reply("Of course."), turn("user", words), reply("I hear you.")])
    filed, shown = sams(s)
    assert words in filed and f"Sam: {words}\n\nClaude: I hear you." in shown


def test_a_chat_he_opens_with_act_as_the_is_his(tmp_path):  # test 14
    words = "Act as the father I needed for a minute."
    s = read(tmp_path, [turn("user", words), reply("I'm here."), turn("user", "thank you"), reply("Any time.")])
    assert not sessions.by_agent(s)
    assert sams(s)[0] == [words, "thank you"]


def test_a_delegates_brief_a_leads_brief_and_the_launchers_prompts_are_still_a_programs(tmp_path):  # test 15, true today
    delegated = read(tmp_path, [turn("user", DELEGATE), reply("Done.")], "d1")
    assert sessions.by_agent(delegated) and sams(delegated) == ([], [])
    lead = read(tmp_path, [turn("user", LEAD), reply("Starting.")], "l1")
    assert summarize.speaker(lead, LEAD, "Sam")[0] == "Prompt" and sams(lead) == ([], [])
    executor = read(tmp_path, [turn("user", "You are executor garden/beds in buildermesh. Work only in /tmp/w."), reply("ok")], "e1")
    assert sessions.by_agent(executor)
    for words in ["Today is 2026-10-10. Window: the last week", "TODAY IS 2026-10-10 for this debate. Each seat speaks",
                  "=== QUEUED CONVERSATION SPANS ===", "You generate concise git branch names", "# Scout packet, week to 2026-10-10",
                  "Review the change at this commit", "YOUR PREVIOUS ANSWER WAS REJECTED"]:
        s = read(tmp_path, [turn("user", "can we talk?"), reply("Of course."), turn("user", words), reply("ok")], "p1")
        assert summarize.speaker(s, words, "Sam")[0] == "Prompt", words
    headless = read(tmp_path, [json.dumps({"type": "user", "entrypoint": "sdk-cli", "message": {"content": "Today is 2026-10-10. Window: ..."}})], "h1")
    assert summarize.clean(headless) == []


def test_stored_summaries_stay_current_with_no_call(world, monkeypatch, server):  # test 16, true today
    server("UTC")  # a turn's time is in what its segment's id is made from
    root = world["root"]
    monkeypatch.setattr(sessions, "ROOT", root)
    p = write_session(root, "-Users-x-repos-health-notes", "m1", [
        turn("user", "my knee is 6/10 since Tuesday"), turn("user", "my knee is 6/10 since Tuesday"), reply("Ice tonight."),
        turn("user", "Base directory for this skill: /x/skills/grilling\n\nLong skill text"), reply("Question one?"),
        turn("user", "ok I'll ice it tonight"), reply("Good.")])
    os.utime(p, (p.stat().st_mtime - 3 * 3600,) * 2)
    sessions.ingest(world["doms"], root)
    made = summarize.plan(p, "medical")
    stored = {"prompt_version": {"segment": summarize.segment_version("medical"), "stitch": summarize.STITCH_VERSION},
              "segments": [{"sha": sha} for sha in made["shas"]], "days": {}, "stitch": {"summary": None, "flagged": True}}
    (summarize.store_dir("medical")).mkdir(parents=True)
    (summarize.store_dir("medical") / "m1.json").write_text(json.dumps(stored))
    monkeypatch.setattr(summarize, "_claude", lambda *a: pytest.fail("a call was made"))
    out = summarize.run()
    assert (out["current"], out["summarized"]) == (1, 0)
    assert made["shas"] == SHAS
