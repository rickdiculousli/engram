# Log, persona 1: curious newcomer (event planner, Claude app on phone and laptop, never opened a terminal)

## 1. Path

1. **Repo page top (readme-00), ~3 s.** A long list of GitHub menu stuff: "Products", "Copilot", "CI/CD", "Code Security". Not for me, it's GitHub's own menu. I scroll down to find the actual thing my friend sent.
2. **Banner (readme-01, top), ~10 s.** An orange brain made of letters with stuff raining through it, big pixel "engram", and "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Then "› keep › find › rewire › evolve". Looks cool and techy. "Start fresh" is me, I guess. "Recall every thread and aside" sounds like remembering my chats. Promising.
3. **Badges row, ~2 s.** "python 3.12+", "index SQLite FTS5", "record plain git", "license MIT". Little coloured code stickers. Uh-oh, this is a programmer thing.
4. **First sentence + five bullets, ~15 s.** "engram gets Claude everything your record holds on a question, related records included, in fewer tokens than grep." I don't know what grep is or what "my record" is. Bullets: "Thorough", "Relational: follows the knowledge graph (threads, `led-to`, `revises`)", "Lean", "Filed to be found ... with typed links", "Plain git: one repo per area of your life". I skim; I get "one per area of your life" (health, trips, money? nice) and nothing else.
5. **"It does four jobs", ~10 s.** "**Keep:** you talk, engram files what matters. No forms, no upkeep." THAT is what I want. Read it twice. "Find: ask a question, get the part of the record it touches" ok-ish. "Rewire: fit each repo..." lost me. "Evolve: improve engram and your repos every week" lost me.
6. **Big diagram (a session / hourly filer / index / one call), ~10 s.** Big dark boxes, "a session" box is mostly empty with "· · · later · · ·". "is knowledge", "/[latest].md", "git commit + push", "ingest", "your records, linked as a graph". The "a session" and later the "code guards" and "in the record / one result" boxes look empty in what I saw (probably they animate on real GitHub, but at a skim they read as blank). I don't get it, but "hourly filer" sounds like it does stuff on its own, which is good.
7. **Clicked "Keep" mentally / kept scrolling into Keep section, ~15 s.** "Just talk to Claude. Every hour, engram reads your finished sessions and files what a good advisor would note. Most sessions file nothing." This is the bit I'd screenshot for myself. Then a table "A model proposes facts; code decides what gets in" with "dropped / narrowed to the month or year you did say / dropped as a repeat". The tomato example ("picked about 3 kg of Sungold this week") is cute and human. But: is "Claude" here the Claude I use? On my phone? It doesn't say.
8. **Scrolled fast past Find, ~10 s.** `$ uv run engram timeline "what happened with the north bed this season?" --domain notes` and a wall of monospace table with ids like "p8qdad". That's code. So asking is done by typing commands, not by just asking Claude? Confused.
9. **Clicked "Quickstart" in the top link row, ~10 s.** "Needs Python 3.12+ and uv." Then `git clone ...`, `uv sync`, `mkdir -p ~/.config/engram`, `cat > ... <<EOF`. This is a terminal. I'd never do this. Saw "made-up Claude Code sessions" at the bottom: "Claude Code"? Is that different from Claude? Probably a programmer version.
10. **Closed the tab.** Total about 1.5 minutes.

Did not click any docs (shape, technical, data model, etc.). Names like "migration: phases, gates, deletions, risks" and "evaluation: question sets, the bar, the frozen gate" would not tempt me. Did not try installing.

## 2. First impression (first 10 seconds)

A pretty, nerdy brain logo for some coding tool. The tagline half-spoke to me ("start fresh", "recall every thread") but "knowledge base" and "fewer tokens" told me it's aimed at techy people who already have some organised notes system. By the badges (python, SQLite, git) I was 80% sure it's not for me.

## 3. Confusions

- **"knowledge base"** (banner): some organised notes app? I don't have one. "or start fresh" saved it for a second.
- **"in fewer tokens"** (banner, and "fewer tokens than grep" in first sentence): tokens = something AI-cost-related? Coins? No idea why I'd care.
- **"python 3.12+", "SQLite FTS5", "plain git"** (badges): programmer labels. Told me "not for you".
- **"your record" / "everything your record holds"** (first sentence): my medical record? My chat history? Unclear what "record" means here; it's used everywhere.
- **"grep"**: no idea. Guessed some other search tool.
- **"knowledge graph (threads, `led-to`, `revises`)"**: lost.
- **"typed links", "the shape that retrieval runs on"**: lost.
- **"one repo per area of your life"**: liked "area of your life", but "repo" is vague; a GitHub folder? Do I need a GitHub account?
- **"Rewire: fit each repo to the way you actually use it"** and **"Evolve: improve engram and your repos every week"**: sounds like homework or like something messing with my stuff.
- **Diagram labels "/[latest].md", "git commit + push", "ingest"**: meaningless to me.
- **Empty-looking boxes** in the loop diagram ("a session"), the Keep diagram ("code guards" rows), and the Find diagram ("in the record", "one result"): looked blank at a skim; I assumed it was broken or loading.
- **"Every hour, engram reads your finished sessions"**: which sessions? My phone chats? Where does it read them from?
- **"A model proposes facts; code decides what gets in"**: kind of reassuring, but "model" and "code" are abstract.
- **`$ uv run engram timeline ... --domain notes`** (Find): so I have to type commands to get things back? I thought Claude would just remember.
- **"Needs Python 3.12+ and uv."** (Quickstart): hard stop.
- **"made-up Claude Code sessions"** (Quickstart bullets): only place the README names which Claude it works with, and it's "Claude Code", which I've never heard of. Is that not the app I use?

## 4. The value moment

Line: **"Keep: you talk, engram files what matters. No forms, no upkeep."** and then **"Just talk to Claude. Every hour, engram reads your finished sessions and files what a good advisor would note."**

It matches my story exactly ("I want it to just remember, without me doing homework"). But it was undone within 20 seconds: the very next section shows remembering things back requires typing `uv run engram ...` commands, and the Quickstart is all terminal. And nothing ever says whether it works with the Claude app on my phone. So: a value moment that promised my story, then took it back.

## 5. Claims

- **Believed:** "No forms, no upkeep" (as an intention). "Most sessions file nothing" actually made me trust it more: it isn't going to hoard every random thing I say. The "dropped / narrowed to the month you did say" table made it sound careful about not making stuff up, which matters for my health worry.
- **Doubted:** "Just talk to Claude" — doubted once I saw the commands. Doubted "Evolve ... without losing anything" because something rewriting my stuff weekly on its own sounds risky, and I can't tell what it touches.
- **Didn't understand:** "fewer tokens than grep", "Relational: follows the knowledge graph", "Filed to be found", "Plain git", all of Rewire, the Architecture section, "Not goals: embeddings ... a web UI" (a web UI I would have wanted, apparently it's a non-goal).

## 6. Exit

Closed the tab at the Quickstart, about 1.5 minutes in, at "Needs Python 3.12+ and uv." followed by a block of terminal commands. Did not star, bookmark or install. Would reply to my friend "is this for coders?".

## 7. In my own words

"It's a cool-looking thing that's supposed to make Claude remember your stuff by saving notes from your chats every hour, which is exactly what I want. But it's a programmer tool: you install it in a terminal, it talks about git and Python, and I couldn't even tell if it works with the normal Claude app. Not for me, unless you set it up for me."

## 8. What would have kept / convinced me

- Tell me in the first two lines **who this is for**: "This is for people who use Claude Code (a programmer's version of Claude) and are comfortable in a terminal." Then I'd have left in 10 seconds without feeling dumb, or known to ask my techy friend.
- Say plainly **whether it works with the Claude app on my phone / claude.ai**. That was my main question and it's never answered.
- Show me a **before/after of a normal chat**: "Monday you tell Claude about your knee. Two weeks later, in a new chat, you ask 'what did the doctor say about my knee?' and Claude knows." In chat bubbles, not a terminal table.
- Put the friendly "Just talk to Claude... Most sessions file nothing" bit at the very top instead of "fewer tokens than grep".
- Drop words like grep, tokens, FTS5, knowledge graph from the top part, or explain them in five words each.
- If there's no way for someone like me to use it, just say "not yet for non-programmers" so I'm not left guessing.
