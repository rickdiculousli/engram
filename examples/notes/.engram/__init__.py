"""The notes area's pack: the words engram's model calls use for a garden notebook. It sets only words, so it shows
the least a pack can be."""
from engram.pack import Pack

FILE = """Below is a conversation between {owner} and Claude about {owner}'s {domain}. Each turn starts with its line
number in brackets. File each new fact about the garden that {owner} states after line {upto}: what was planted,
picked, watered or lost, and when. Leave out questions, plans and anything already filed or already in the notes.

For each fact give "line", "text" (a headline), "quote" ({owner}'s words, copied exactly), "date" (YYYY-MM-DD,
YYYY-MM, YYYY or "not-sure"), "kind" (one of {kinds}), "about" (from {abouts}) and "stories" (from {stories}).
{theory}
Reply with JSON only: {{"facts": [...], "theory": []}}.

<conversation>
{conversation}
</conversation>

Already filed from this conversation:
{already}

{record}"""

VERIFY = """These facts were drawn from what {owner} said about the {domain}. Under each are the notes most like it.
Say which ones a note already states.

Reply with only JSON: {{"repeats": [{{"n": <fact number>, "ref": "<the note's ref>", "why": "<a few words>"}}]}}.

{candidates}"""

RECORD = """Notes dated within {window} days of the days spoken on ({span}){titles}:
{entries}

Where things stand:
{standing}

Search hits:
{hits}"""

THEORY = """
How things in the garden affect each other: change it only when {owner} says so after line {upto}, with a status
(one of: {statuses}) or a link (one of: {rels}; strength one of: {strengths}).

{graph}
"""

STRUCTURE = """{owner} agreed at line {line} to change how the garden's things affect each other. Write the change as
operations (rels: {rels}; strengths: {strengths}; statuses: {statuses}; stories: {stories}).

{graph}

Already run: {ran}

<conversation>
{conversation}
</conversation>"""

RELINK = """{owner}'s notes on how the garden works just changed ({date}{why}):
{change}

Things: {things}
Link each note that bears on it to one of: {targets} (retired: {retired_ids}).
Reply with JSON only: {{"links": [...]}}

<records>
{records}
</records>"""

SWEEP = """{owner}'s notes on how the garden works:
{targets}

Link each note that bears on one of them, for (strengthens) or against (weakens), with the note's own words that
show it ("passage", copied exactly).
Reply with JSON only: {{"links": [...]}}

<records>
{records}
</records>"""

SWEEP_CONFIRM = """Does this note {rel} this idea about the garden? Reply yes or no alone.

{target}

The passage at issue: {passage}

<record>
{record}
</record>"""

pack = Pack(prompts={"file": FILE, "verify": VERIFY, "record": RECORD, "theory": THEORY, "structure": STRUCTURE,
                     "relink": RELINK, "relink_system": "You link garden notes to how the garden works.",
                     "sweep": SWEEP, "sweep_confirm": SWEEP_CONFIRM})
