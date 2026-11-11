"""The inner-work area's pack: the words engram's model calls use for one person's sessions with a guide, what "where
things stand" follows (the practices), and a reader for the rows the person's gym app keeps. Every word is made up.

The words under "Not yet read by engram" are the inner-work changes' (docs/technical.md, "The inner-work settings"):
`note`, `suggest`, `stated` and `regroup`. Today engram reads only the rest."""
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

When a fact is about a theme, a person or a past event the record doesn't hold yet, give "create": [{{"kind": "theme",
"person" or "event", "name": <a few of his own words, copied exactly>}}]. Never join, split or end one.
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
How things work underneath for {owner}, as he has agreed it: change it only when {owner} says so after line {upto},
with a status (one of: {statuses}) or a link (one of: {rels}; strength one of: {strengths}).

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

# ---- Not yet read by engram: the inner-work changes' words ----

NOTE = """Say whether lines {first} to {last} were a working session: something worked through, such as an exercise. A
check-in, small talk or talk about the tools is not one. If it was, give "note": for each of these sections, its lines
({sections}), each with "line" and "quote", copied exactly from that line, and "by" ({owner} or the guide). Leave a
section empty when nobody said anything for it; never fill one in. Name the earlier note it continues, if any
({recent})."""

SUGGEST = """The guide's ideas about {owner} that he hasn't agreed to are kept too, as the guide's: for each one the guide
offered after line {upto}, give "suggestions": [{{"line": <the guide's line>, "quote": <the guide's words, copied
exactly>, "kind" (one of {kinds}) and "name", or "link"}}]. When {owner} later says one in his own words, says yes when
asked, or says no, give it under "theory" with his words."""

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
    current=Current(entity_kind="practice", entity_prefix="practice", detail="note",
                    statuses=("started", "carried", "paused", "retired"), group="practices", sections=("practices", "stopped")),
    read={"gym": read_gym},
)
