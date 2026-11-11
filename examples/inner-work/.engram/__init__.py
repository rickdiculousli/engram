"""The inner-work area's pack: the words engram's model calls use for one person's sessions with a guide, what "where
things stand" follows (the practices), and a reader for the rows the person's gym app keeps. Every word is made up."""
import json
from datetime import datetime
from pathlib import Path

from engram.pack import Current, Doc, Pack, Source

FILE = """Below is a conversation between {owner} and Claude, his guide in inner work. Each turn starts with its line
number in brackets. File what {owner} says after line {upto} that is worth keeping: what he noticed, what happened, what
he decided or practised. Leave out what Claude says, Claude's guesses about him, and anything already filed.

Go through every line of {owner}'s after line {upto}, one by one. Each is either filed (in a fact, or in the note when
there is one) or given under "left": {{"line", "why"}}, why one of "tools" (only about the app, the notes, engram,
filing, the repo or its settings), "filed before" or "nothing in it". A line that is also about him, his life or how
he feels, even how he feels about the tools, is filed; a short reply ("yeah", "I guess") is filed with what it answers,
a question or not, and is left as "tools" only when what it answers is.

For each fact give "line", "text" (a headline), "quote" ({owner}'s words, copied exactly), "date" (YYYY-MM-DD, YYYY-MM,
YYYY or "not-sure"), "kind" (one of {kinds}), "about" (from {abouts}) and "stories" (from {stories}). When he answers a
question with a few words ("yeah", "mm"), give "answering" (Claude's question, copied exactly) and keep the headline
his answer to that question: never a statement in his voice. When his words say when other than as a plain date, give
"as_said" (those words, copied exactly). When he dates something by a life event or his age, give "landmark": its name
from these ({landmarks}), else a new short one. When he says a note listed below was wrong, give "corrects": its id,
and "text" as it should read.

Threads: "about" takes the threads listed there, each shown with {owner}'s names for it. A thread is one of:
- a person;
- a past event: something that happened once, before the day he says it;
- a theme: something that keeps happening in his life or that he keeps coming back to (a situation, a habit, a worry),
  beside the people and events in it.
When a fact is about a person or a past event none of the listed threads is, give "create": [{{"kind": "person" or
"event", "name": <his own words for it in that message, copied exactly>}}]. For each fact give "again": the ids of
the entries listed below where he brought up the same thing at an earlier time (the same worry, situation, plan or
habit, even if it has moved on since), whatever threads they're on, or [] when this is the first time he brings it up;
a person or event thread holding it doesn't make it new. A fact with "again" is on a theme as well as on its people and
events: a listed theme/... one, or a new one, given as "create" with "kind": "theme" and a name copied from that
message, in words he also used for it before. Facts here about one situation share one theme. A fact with no "again" never starts a theme, and what the theory below
already holds is never one. When he calls a listed thread by a new name, give "names": {{<thread>: <his words>}}. When
he says an entry is on the wrong one, give "moves": [{{"entry": <its id>, "from": <the thread>, "to": <the right
thread, or {{"kind", "name"}}>, "said": <his words saying so, copied exactly>}}]. Never join, split or end a thread.
{theory}
Reply with JSON only: {{"facts": [...], "theory": [], "left": [...]}}.

<conversation>
{conversation}
</conversation>

Already filed from this conversation:
{already}

{record}"""

VERIFY = """These were drawn from what {owner} said in his inner-work sessions. Under each are the records most like it.
Say which ones a record already states.

Reply with only JSON: {{"repeats": [{{"n": <its number>, "ref": "<the record's ref>", "why": "<a few words>"}}]}}.

{candidates}"""

RECORD = """Records dated within {window} days of the days spoken on ({span}){titles}:
{entries}

Where things stand:
{standing}

Search hits:
{hits}"""

THEORY = """
How things work underneath for {owner}: change it only when {owner} says so after line {upto}, in his own words, with a
status (one of: {statuses}), a stage for a thing that has stages ("status": {{"id", "stage"}}: how far along the change
is, apart from how sure it is) or a link (one of: {rels}; strength one of: {strengths}). A belief, part or insight he
names himself that isn't below is "add": {{"kind", "id": <kind>/<a few words, lower case, joined by dashes>, "name":
his words for it, copied exactly}}. A thing marked as the guide's suggestion is Claude's idea, not his.

{graph}
"""

SWEEP = """How things work underneath for {owner}:
{targets}

The ways a record links to one of these, each saying what happened, never whether a belief is true:
{rels}

For each record that shows one of these at work, give a link for each way above that says what happened to it there:
"record", "to", "rel" and "passage" (the record's own words that show it, copied exactly; inside a note, only
{owner}'s lines).
Reply with JSON only: {{"links": [...]}}

<records>
{records}
</records>"""

SWEEP_CONFIRM = """Does this record show this ({rel})? Reply yes or no alone.

{target}

The passage at issue: {passage}

<record>
{record}
</record>"""

CORRECT_CONFIRM = """Does what {owner} said mean this record was wrong, not that things changed since? Reply with one
word: slip when he misspoke or misremembered, learned when something new showed it wrong, no otherwise.

{entry}

What {owner} said:
{said}"""

NOTE = """The conversation above is one session, lines {first} to {last}. Say whether it was a working session: one
where something was worked through with Claude, such as an exercise, however short. A check-in, small talk, making
plans, or talk about the app, the notes or the tools is not one, even when feelings come up in passing.

Add to your JSON "working": true or false and, for a working session only, "note": {{"sections": {{<section>: [<line>,
...]}}, "about": [<the abouts above it bears on>], "follows": <the id of an earlier note it carries on, if any>}}. Each
line is {{"line": <its line number>, "quote": <words copied exactly from that line>, "by": "{owner}" or "guide"}}.
The sections, and whose words go in each: {sections}.
- what you brought: what {owner} came in with.
- what was done: the exercise or the question as Claude gave it.
- what you found: what {owner} noticed or realised.
- what changed: only a change {owner} says himself, in his own words. Claude saying something seems lighter, calmer or
  softer is never a change, and neither is {owner} going along with it ("yeah", "mm", "maybe"). Without his own words
  for it, leave it empty.
- where you stopped: where {owner} left it, and anything Claude offered that he didn't answer.
A line only about the tools goes in no section. Leave a section empty when nobody said anything for it; never fill
one in.

Earlier notes: {recent}"""

SUGGEST = """Claude's ideas about {owner} that he hasn't taken up (a hunch, "maybe there's a part of you that...", a belief or a
pattern Claude names in him) are kept too, as Claude's. For each such idea Claude offers after line {upto}, new or
said again, give "suggestions": [{{"line": <Claude's line>, "quote": <Claude's words for the idea, copied exactly>,
"kind": one of {kinds}, "id": <kind>/<a few words, lower case, joined by dashes>, "name": <a short name for it>}}]. An
idea the theory above already holds as the guide's suggestion, offered again in any words, takes that thing's own id:
it's the same suggestion, said again. A different idea about the same part or belief is a new one, with a new id.

For each line after {upto} where {owner} speaks of one of the guide's suggestions above, give under "theory":
{{"line": <his line>, "quote": <his words, copied exactly>, "on": <its id>, "says": what he does with it, one of:
- "adopts": he says the idea himself, as his own: in his own words, with his own name for it, even grudgingly;
- "denies": he says it isn't so: no, it isn't him, he doesn't have it;
- "agrees when asked": yes, maybe or could be to Claude's question about it, with "answering": Claude's question, copied
  exactly;
- "doubts": he isn't sure, doesn't know, finds it odd or made up, will see or watch for it;
- "asks": he asks what it is, whether it's real, where it came from.}}
Doubting or asking is not denying. Only "adopts" makes it his, and only "denies" rules it out."""

STATED = """What {owner} says he believes about himself, about who or what he is or how he is with people, is kept as a
trail. Give each such statement as a fact of kind {kind}, its quote his words that say it, copied exactly, and under
"beliefs" every belief below that it expresses: [{{"id": <its id>}}], with "loose": true where it fits only in part.
Judge by what the statement says about him, never by the words it shares with a belief or with his other statements:
two statements with no word in common can say the same thing about him, and two that share words can say different
things, or one of them nothing about him at all. Give the narrowest belief that fits, and every one that does; a
broader belief already holds what sits under it. When none below fits, give "new_belief": {{"name": his statement, or
the words of it that say the belief, copied exactly}}, and nothing for it under "theory".

A statement is his own, about himself. Not one: what he says about another person, a group, people or the world, even
when it echoes a belief of his; what someone else thinks of him, or of themselves, which he reports; a remark about a
day, a thing or a task that happens to share a belief's words; what only Claude said, or what he only agreed to. Keep
those, if they're worth keeping, as facts of another kind.

The beliefs, each with what it sits under and a few of his statements:
{beliefs}"""

REGROUP = """Below is every statement {owner} has made about himself, each with the beliefs it is linked to, and the beliefs,
each with what it sits under. Read them all at once and propose, by what each statement means, not by shared words:
- "links": a statement to a belief it expresses that it isn't linked to yet, {{"from": <the statement's id>, "to": <a
  belief's id>, "loose": true where it fits only in part}};
- "beliefs": a new belief for statements that say the same thing and fit none below, {{"id": "belief/<a few words,
  lower case, joined by dashes>", "name": <one of his statements, or the words of it that say the belief, copied
  exactly>, "from": <that statement's id>}}, with a link from each statement that expresses it;
- "under": a belief that sits under a broader one, {{"from": <the narrower>, "to": <the broader>}}; a broader one may
  be new, named in your words.
Never remove a link or a belief. Reply with JSON only: {{"beliefs": [...], "links": [...], "under": [...]}}.

Statements:
{statements}

Beliefs:
{beliefs}"""


def read_gym(repo: Path) -> Source:
    """The gym app's rows: each of the owner's own dated words on a practice, for engram to keep as his (change 10);
    the app's coach's rows are read for search only; and a practice's rows with no text are only counted."""
    docs, empty = [], {}
    for n, line in enumerate((repo / "gym/rows.jsonl").read_text().splitlines(), 1):
        row = json.loads(line)
        day = datetime.fromisoformat(row["at"].replace("Z", "+00:00")).astimezone().date().isoformat()
        if not row["text"].strip():
            empty[row["practice"]] = empty.get(row["practice"], 0) + 1
            continue
        mine = row["by"] == "owner"
        docs.append(Doc(ref=f"gym/rows.jsonl#{row['id']}", source="gym", cls="said" if mine else "row", kind="app-row",
                        title=f"gym app: {row['text'][:60]}", body=row["text"], pointer=f"{repo}/gym/rows.jsonl:{n}",
                        author="{owner_id}" if mine else "coach", date=day, stories=row["practice"]))
    for practice, count in empty.items():
        docs.append(Doc(ref=f"gym/rows.jsonl#count-{practice}", source="gym", cls="row", kind="app-count",
                        title=f"{practice}: {count} check-ins with no words", body=f"{count} check-ins with no words",
                        pointer=f"{repo}/gym/rows.jsonl", author="repo"))
    return Source(docs)


pack = Pack(
    prompts={"file": FILE, "verify": VERIFY, "record": RECORD, "theory": THEORY, "sweep": SWEEP, "sweep_confirm": SWEEP_CONFIRM,
             "relink_system": "You link moments in an inner-work record to the patterns underneath.",
             "correct_confirm": CORRECT_CONFIRM,
             "note": NOTE, "suggest": SUGGEST, "stated": STATED, "regroup": REGROUP},
    kinds=("observation", "practice", "stated-belief", "plan"),
    current=Current(entity_kind="practice", entity_prefix="practice", detail="routine",
                    statuses=("started", "carried", "paused", "retired"), group="practices", threads={"person": "people"},
                    sections=("practices", "people", "stopped"), ongoing=frozenset({"started", "carried"}),
                    finished=frozenset({"retired"}), whole_names=True, origin="insight"),
    read={"gym": read_gym},
    relink_skip=("theory/",),  # the theory's own pages: what a moment links to, never a moment
)
