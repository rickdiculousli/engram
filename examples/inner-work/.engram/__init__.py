"""The inner-work area's pack: the words engram's model calls use for one person's sessions with a guide, what "where
things stand" follows (the practices), and a reader for the rows the person's gym app keeps. Every word is made up.

The words under "Not yet read by engram" are the inner-work changes' (docs/technical.md, "The inner-work settings"):
`stated` and `regroup`. Today engram reads only the rest."""
import json
from datetime import datetime
from pathlib import Path

from engram.pack import Current, Doc, Pack, Source

FILE = """Below is a conversation between {owner} and Claude, his guide in inner work. Each turn starts with its line
number in brackets. File what {owner} says after line {upto} that is worth keeping: what he noticed, what happened, what
he decided or practised. Leave out what Claude says, Claude's guesses about him, and anything already filed.

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
Reply with JSON only: {{"facts": [...], "theory": []}}.

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

For each record that shows one of these at work, give the link: "record", "to", "rel" (what happened, never whether the
belief is true) and "passage" (the record's own words that show it, copied exactly; inside a note, only {owner}'s lines).
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
Leave a section empty when nobody said anything for it; never fill one in.

Earlier notes: {recent}"""

# ---- Not yet read by engram: the inner-work changes' words ----

SUGGEST = """Claude's ideas about {owner} that he hasn't taken up (a hunch, "maybe there's a part of you that...", a belief or a
pattern Claude names in him) are kept too, as Claude's. For each such idea Claude offers after line {upto}, new or
said again, give "suggestions": [{{"line": <Claude's line>, "quote": <Claude's words for the idea, copied exactly>,
"kind": one of {kinds}, "id": <kind>/<a few words, lower case, joined by dashes>, "name": <a short name for it>}}]. An
idea the theory above already holds as the guide's suggestion, offered again in any words, takes that thing's own id:
it's the same suggestion, said again. A different idea about the same part or belief is a new one, with a new id.

What {owner} says after line {upto} about one of the guide's suggestions above goes under "theory", with his line and
his words:
- he says the idea himself, as his own (in his words, with his own name for it, even grudgingly): "status":
  {{"id": <its id>, "to": "provisional"}}, his words that say it as "quote";
- he says no to it, or that it isn't him: "status": {{"id": <its id>, "to": "ruled out"}};
- he says yes, maybe or could be when Claude asks about it ("yeah", "I guess", "could be"): "agrees": <its id>, with
  "answering": Claude's question, copied exactly. That isn't his own words for it.
Asking about one, wondering, being unsure, or planning to watch for it changes nothing: give nothing for it."""

STATED = """When {owner} says something about himself ("I'm a burden"), give it as a fact of kind {kind} and, under
"beliefs", every belief below it expresses, by meaning, not by shared words ("loose": true when the fit is partial). If
none fits, give "new_belief" with his statement, copied exactly. Never give one said only by the guide, or one he
only agreed to.

{beliefs}"""

REGROUP = """Here is every statement {owner} has made about himself, with the beliefs each is linked to. Propose new
beliefs, new links and broader groupings. Never remove a link.

{statements}"""


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
)
