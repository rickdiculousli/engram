# Log: persona 5, the record keeper

52, operations manager, caregiver. I keep Mum's health log in a spreadsheet plus Google Docs. Came here from a caregiver forum post on "AI for medical history". I've been burned by Claude making up dates. I use the Claude chat app, not anything in a terminal.

## 1. Path

1. **The repo page above the README** (5 s). GitHub's menus, then a file list. Didn't take much in. Scrolled.
2. **The banner** (10 s). An orange brain made of letters with text raining through it, then "engram", "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." and `keep · find · rewire · evolve`. Looks like a hacker thing. "Knowledge base" maybe means my notes? "Tokens" means nothing to me.
3. **The badges** (3 s). "python 3.12+", "SQLite FTS5", "plain git", "MIT". "Plain git" worried me straight away: git is the GitHub thing, and GitHub is public.
4. **The opening paragraph and bullets** (40 s). "gets Claude everything your record holds on a question, related records included, in fewer tokens than grep." I don't know what grep is. The bullets mean little to me: "knowledge graph", "`led-to`, `revises`", "typed links", "the shape that retrieval runs on". The only one I took in: "**Plain git:** one repo per area of your life, readable without engram". One per area sounds like how I already split health, money and school.
5. **"It does four jobs"** (20 s). "Keep: you talk, engram files what matters. No forms, no upkeep." Interested. "Evolve: improve engram and your repos every week, without losing anything." Who improves what, every week, on its own? Made me a bit nervous.
6. **The loop diagram** (30 s). A session, an "hourly filer", "is knowledge", "/[latest].md", "git commit + push", "ingest", "index", "one call", "find". I read it as: I talk, every hour something takes the important bits, saves them and **pushes** them somewhere, and later I ask. "Push" to where?
7. **Keep section, first line** (30 s). "Just talk to Claude. Every hour, engram reads your finished sessions and files what a good advisor would note." My first reaction was "reads *what*?" Which sessions? My chat app conversations? Everything? Who is "a good advisor"?
8. **The filer rules table** (1 min 30 s). This is the part I came for. Read it twice.
   - "Quote, numbers included, isn't in your own words → dropped": good, that's exactly my problem with dates and doses.
   - "Has a day you never said → narrowed to the month or year you did say": **yes.** That's the dates thing I'm burned on.
   - "Already in the record → dropped as a repeat"
   - "Passes all three → filed as an entry, committed and pushed"
   The table heads are "Proposed fact | →". The arrow as a heading looked like a mistake.
9. **The filer animation** (40 s, watched it play through once). "picked about 3 kg of Sungold this week, the Brandywine are slow" goes in, four proposed facts come out, ticks and crosses, "5 kg … dropped, not in their words", "Brandywine slow to ripen, date 2026-09-21 → filed, 2026-09, a day nobody said". This sold me more than any sentence. I could see a made-up 5 kg get crossed out. I'd want the same with a dose or a "started on" date. Tomatoes are fine as an example, but I had to translate it to medicine myself.
10. **Find section, the terminal output** (40 s). `$ uv run engram timeline …`, then a block of JSON, then a table. I'm an Excel person, so I can read a table. Row 2: "Basil bolted in late June" and "2026-07 me: corrected: July → late June". I got that: the old answer is kept next to the new one. The line `{"chain":"north-bed","kind":"story",...}` above the table means nothing to me.
11. **"Corrections never erase." and the versions diagram** (40 s). "[fact] 07", "[correction] 06", "revises", then "one result" with the correction on top, "07 [fact] → corrected", "nothing erased · every version kept". **This is what I want for Mum's meds.** When a doctor changed a dose, I want both. This and the filer were the two things that made me stay.
12. **Command table, "Each repo searches only itself unless you ask"** (15 s). Good for privacy: the health record doesn't leak into the school record. I liked that line.
13. **Rewire and Evolve** (1 min, skimmed). "pre-commit refuses", "drift", "`ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/`", "within a budget", "tidies your graph", "a record regrouped, saved by itself". I didn't follow it. What I did take: something rearranges my record weekly **on its own**, and it only asks for "bigger" changes. That cuts against "nothing erased" for me. The diagram says "small and undoable → saves itself". Fine, but what counts as small?
14. **"What a record is made of" and Architecture** (40 s). "events/2026/06/[id].md … date, about, by: me, [the fact] — one fact, never edited". That reassured me: a plain file per fact that I could open. Architecture: `~/.config/engram/config.toml` and `~/.local/share/engram/` "the index" on "your machine". So the index is on my computer. But does anything go anywhere else? Not answered here.
15. **Quickstart** (30 s). `git clone`, `uv sync`, `cat > … <<EOF`. I've run a colleague's Python script, but never with "uv", and the `<<EOF` block is beyond me. Then "`examples/sessions/`: its made-up **Claude Code** sessions". **That's when it clicked: this is for Claude Code, not the Claude app I use.** Also "`engram setup <repo>` → turns on hourly filing … (once its pack has filing words and it's rewired)": no idea what a pack or filing words are.
16. **Clicked "technical" from "More in technical"** under the filer, looking for privacy (1 min). Very dense. "Routing", "`dates.numbers`", "`now` chains", "one low-effort call per session (`verify`)". I picked out "Dates he never gave: code checks the model's date against the message … else `date: not-sure`". I like `not-sure`. But it never says *which* model or *where* it runs. Who is "he"?
17. **Back to Docs list, clicked "summaries: who-said-what rules"** (1 min), because "who said what" is my exact worry with doctors vs. me. Found "**No invented dates.** Fuzzy dates stay in the source's words." and "Quotation marks mean word for word." Great. Then: "Opus at low effort (`claude -p`, the owner's subscription)". Reading between the lines, the conversations do go to Claude (Anthropic's servers) using my own subscription. That's no worse than what I already do in the app. But I had to dig two pages deep to work it out, and I'm not 100% sure I read it right.
18. **Clicked "example" from Architecture** (40 s). Opened `examples/notes/.engram/README.md` and then one entry file. The entry file is readable: `title: Six tomato plants in the north bed`, `date: 2026-04-12`, `reported: 2026-09-14`, `by: sam`. I liked that it keeps "reported" separately from "date": that's the difference between "when it started" and "when I mentioned it". The README part ("How bold", "two-way doors", "Refinement: trailer") lost me.
19. **Stopped** (around 11 minutes total, a little over my patience, kept going only because the filer and corrections parts looked trustworthy).

## 2. First impression (first 10 seconds)

A developer's toy: a glowing brain made of code characters, "knowledge base", "tokens". It looked like something for programmers who use AI to code, not for a caregiver with a spreadsheet. It took me until the Keep table to think it might be for me at all.

## 3. Confusions

- **"in fewer tokens"** (banner) and **"in fewer tokens than grep"** (first line): don't know tokens or grep. Guessed "cheaper/faster than some search tool". Doesn't matter to me. Accuracy matters to me, not tokens.
- **"Bring your knowledge base, or start fresh."** (banner): hoped it meant "bring your existing spreadsheet/doc history". **Nothing in the README tells me how.** The closest was the "migration" doc title: "phases, gates, deletions, risks". "Deletions" and "risks" put me off clicking it for my mother's records.
- **"plain git"** badge, **"git commit + push"** in the loop diagram, **"filed as an entry, committed and pushed"** in the table: pushed *where*? GitHub? Is my mother's medical history going to a public website? The README never says the repo can or should be private, or that pushing can be off.
- **"Every hour, engram reads your finished sessions"** (Keep): which sessions? I assumed my Claude chats at first. Only learned from "made-up Claude Code sessions" in Quickstart (and `~/.claude/projects/` in sources) that it means Claude Code on my computer. It also doesn't say it reads *only* sessions started in that record's folder; I found that in technical ("a session belongs to the repo it was started in").
- **"A model proposes facts"**: which model? Running where? On my computer or sent off? Answered only in summaries.md ("Opus … `claude -p`, the owner's subscription"), and only if you know what that means.
- **"files what a good advisor would note"**: who decides what a good advisor would note? For a medical log I'd want *everything* about a symptom or dose kept, not an advisor's pick.
- **"Most sessions file nothing."**: reassuring on privacy, worrying on completeness. If I mention a new symptom in passing, does it get dropped?
- **Table heading "Proposed fact | →"**: the arrow column heading looked like a typo; I'd want "What happens".
- **"Relational: follows the knowledge graph (threads, `led-to`, `revises`) out to the tangents grep never reaches"**: lost.
- **"Filed to be found: … with typed links, the shape that retrieval runs on"**: lost.
- **The JSON line** `{"chain":"north-bed","kind":"story","records":6,…}` above the timeline table: noise to me.
- **"5 search match" / "6 search match"** rows with no date: what are they, and why are they in a timeline?
- **"Evolve … improve engram and your repos every week, without losing anything"** and **"tidies your graph"**, **"a record regrouped, saved by itself"**: something changes my record without asking me. The README says Evolve "never touches your record", but the diagram says "a record regrouped, saved by itself". Those read as contradicting each other.
- **"Rewire"**, **"drift refused at commit"**, **"pre-commit"**, **`ln -s …`**: didn't understand.
- **"pack", "filing words", "rewired"** (Quickstart last bullet): no idea.
- **"launchd"**, **"second box"**, **"ssh host"** (operations doc, glanced): is this Mac-only? What second box? Am I meant to have two computers?
- **"Dates he never gave"** (technical): who is "he"?
- **"the owner"** everywhere in the docs: I guessed it means me.

## 4. The value moment

The filer animation, at the frame where "5 kg of Sungold picked" is struck out with "dropped, not in their words", and "Brandywine slow to ripen, date 2026-09-21" becomes "filed, 2026-09, a day nobody said". The table line behind it: **"Has a day you never said → narrowed to the month or year you did say"**. Then the second half, at **"Corrections never erase. Fix a fact → engram keeps both and links them"** and the "nothing erased · every version kept" diagram.

That matches my story almost exactly: "the dates I actually said, corrections kept, nothing invented". It's the first tool I've seen that *checks* the AI's dates against my words rather than asking it nicely. But the moment is all about *keeping new things from talk*. My story starts with **years of existing history**, and nothing showed me that history coming in.

## 5. Claims

- **Believed:** "Has a day you never said → narrowed to the month or year you did say". The animation shows the mechanism, and technical.md backs it with "else `date: not-sure`". Also believed "Corrections never erase", since row 2 of the example output shows both versions.
- **Believed:** "Each repo searches only itself unless you ask." Plain statement, and it's what I'd want.
- **Believed, with relief:** the entry files are plain text I can open ("readable without engram"). I opened one, and it was.
- **Doubted:** "No forms, no upkeep." Quickstart needs a config file written by hand and something called rewiring before filing even turns on. That's upkeep for me.
- **Doubted:** "without losing anything" (Evolve) next to "a record regrouped, saved by itself". I'd need to see what "regrouped" does to Mum's file.
- **Doubted / couldn't check:** privacy overall. Nowhere in the README says plainly "your data stays on your computer, except X goes to Claude". I had to infer it.
- **Didn't understand:** "fewer tokens than grep", "knowledge graph", "typed links", "Rewire".
- **Didn't understand whether it applies:** "Bring your knowledge base". Can my spreadsheet and Google Docs come in, and how?

## 6. Exit

Did not install. I stopped after the summaries doc and the example entry, at about 11 minutes. Reasons, in order:
1. It reads **Claude Code** sessions. I use the Claude app; I'd have to start using a terminal tool to talk about my mother's health.
2. I couldn't find, in plain words, where my data goes. "Committed and pushed" with no "to a private place you choose" scared me.
3. Nothing showed how my years of spreadsheet and Google Docs history would come in. The migration doc's title ("deletions, risks") made me not want to try it on real records.
4. Quickstart's `uv` and `<<EOF` block is past what I'd attempt alone.

Bookmarked it to show my colleague (the one who wrote my Python scripts) and asked myself to come back if there's a "for non-programmers" page. No star: I don't really use GitHub.

## 7. In my own words

"Found a tool on GitHub that does the one thing I want from AI with Mum's records: it won't let Claude put down a date or a number I never said, and when I correct something it keeps the old version next to the new one. But it's built for programmers using Claude Code in a terminal, it saves everything with git and 'pushes' it somewhere it never really explains, and I couldn't see how my years of spreadsheet history would get in. I've bookmarked it to ask Dan about, but I'm not putting medical data in it until someone tells me where it goes."

## 8. What would have kept / convinced me

- **One plain "Where your data goes" box near the top.** Something like: "Your records stay in folders on your computer. The index stays on your computer. To file, engram sends a finished conversation to Claude using your own Claude subscription, the same as chatting. Pushing is to a git remote *you* choose. Make it private, or don't push at all." If that's true, say it on page one. I shouldn't have to find `claude -p` in a summaries doc.
- **Tell me up front it's for Claude Code**, not the Claude app, and what that means for someone like me. Is there a way to use it with the app, or by pasting?
- **"Bring your existing history" shown, not just promised.** Show a spreadsheet of symptoms and doses becoming dated entries, with the same "date nobody said" checks applied to my old rows. Tell me it works on a copy first. (I gather from migration.md that it does, in "scratch clones", but the title "deletions, risks" scared me off.)
- **A health or caregiving example next to the garden one.** "Mum said the dizziness started 'around Easter'" filed as "2026-04, her words", and a dose correction kept with the old dose on one line. Then I wouldn't have to translate tomatoes into medicine.
- **Say plainly what "Evolve" can and can't change in my record.** "Never edits or deletes a fact you said; only regroups how they're listed" would let me sleep.
- **"Most sessions file nothing" needs its other half for me:** how do I make sure a symptom I mention in passing *does* get kept? Can I say "keep this"?
- **Drop the words I can't use** from the top (tokens, grep, knowledge graph, typed links) or move them lower. Lead with "the dates you actually said, corrections kept, nothing invented". That's the thing it does, and it's what brought me here.
