# Persona 2: notes-app pile (teacher, 41, 1,200+ Apple Notes and Google Keep notes)

I came from a Reddit thread called "second brain with AI". I use the Claude app every week. I don't know git, and I've used Terminal once, for Homebrew.

## 1. Path

1. **Repo page top (3 s).** A lot of GitHub menus. I scroll past them to the picture.
2. **Banner (15 s).** An orange brain made of letters, with "engram" in big blocky orange type. "Bring your knowledge base, or start fresh." My first thought: that's me, my notes are my knowledge base. "Recall every thread and aside, in fewer tokens." I'm not sure what tokens are; I think it's an AI-cost thing. "keep / find / rewire / evolve": I get keep and find. Rewire and evolve sound like a self-help book.
3. **Badges and link row (3 s).** "python 3.12+", "SQLite FTS5", "plain git", "MIT". This is a programmer thing. My heart sinks a little.
4. **Intro line and bullets (40 s).** "engram gets Claude everything your record holds on a question … in fewer tokens than grep." I know Claude. I don't know what "grep" is, or why my notes are now "your record". The bullets: "knowledge graph (threads, `led-to`, `revises`)", "typed links", "one repo per area of your life". I read "Plain git: one repo per area of your life" twice and still couldn't picture it. One folder for recipes and one for the kid's doctor stuff? I gave up on it.
5. **"It does four jobs" (15 s).** "Keep: you talk, engram files what matters. No forms, no upkeep." Nice, but I don't want to talk new things into it. I want the stuff I've *already written* back. "Find: ask a question, get the part of the record it touches." That's my story.
6. **Loop diagram (20 s).** "a session", "hourly filer", "is knowledge", "/[latest].md", "git commit + push", "ingest", "index", "one call". Boxes with code words in them. All I took from it is that something runs every hour and saves stuff.
7. **Clicked "Quickstart" in the link row (30 s).** I jumped there because my real question is *how do I get my notes in*. What I found: "Needs Python 3.12+ and uv", then a block of `git clone`, `uv sync`, `mkdir -p ~/.config/engram`, `cat > … <<EOF`, `owner = "Sam"`, `[domains.notes]`. I could probably paste it if I squinted. But underneath it says `examples/notes/: a made-up garden record`. So the "notes" here are a pretend garden, not mine. Nothing says where *my* notes go. `examples/sessions/: its made-up Claude Code sessions`: is Claude Code the same as my Claude app? I'm not sure. It sounds different.
8. **Scrolled back up to Keep and Find (60 s).** The Keep table, "Proposed fact → Quote, numbers included, isn't in your own words → dropped", read like grading rules. The orange box "picked about 3 kg of Sungold this week, the Brandywine are slow" is the first thing that looked like something I'd actually write. Find, "Ask for a whole history: what happened with the north bed this season?", is exactly the kind of question I'd ask about my house repairs. But the answer is a black terminal box with `{"chain":"north-bed","kind":"story"…`, ids like `p8qdad`, and a column called "versions". You type a command, not ask Claude in the app.
9. **Ctrl+F "Apple" (5 s).** 0 results. **Ctrl+F "Keep" (5 s).** Only the "Keep" job, not Google Keep. **Ctrl+F "import" (5 s).** 0 results. **"Obsidian"** 0. Rewire, Evolve, "What a record is made of" and Architecture got about 10 seconds each on the way down. Lots of diagrams with `[thing]`, `[category]`, `.engram/engram.toml`, "drift refused at commit", `events/links.jsonl`. Skipped.
10. **Docs → "Start here: shape" (30 s).** It said "onboarding a repo", and I hoped onboarding meant getting my stuff in. The first line: "The canon: the shape every record takes in engram, and the lessons learned getting real records there. Rewiring fits it to a repo…" Then a table of Entry / Document / Link / Thread / Theory / Lens. Closed the tab.

About 4.5 minutes in all.

## 2. First impression (first 10 seconds)

A pretty orange brain plus "Bring your knowledge base, or start fresh" made me think this is an AI second-brain app you pour your notes into and then ask questions. Within 3 more seconds the python/SQLite/git badges told me it's a programmer's tool, not an app.

## 3. Confusions

- **"Bring your knowledge base" (banner).** Nothing after the banner ever says how to bring it, or what counts. I guessed my notes count. The rest of the page only talks about *new* things from talking to Claude.
- **"in fewer tokens" (banner) / "in fewer tokens than grep" (intro).** I guessed tokens are what AI charges for. I had no idea what grep is; maybe a competitor?
- **"your record" (intro and everywhere).** Like a medical record? A school record? I guessed it means "all your stuff".
- **"knowledge graph (threads, `led-to`, `revises`)" (bullets).** No idea. Threads like email threads?
- **"Plain git: one repo per area of your life" (bullets).** The biggest wall. I know git as "version history" and I don't know "repo". Is it a folder? Do I have to sort my 1,200 notes into areas first?
- **"you talk, engram files what matters" (Keep).** Talk where? In the Claude app on my phone? It later says "Claude Code sessions", so maybe not.
- **"hourly filer", "/[latest].md", "git commit + push", "ingest" (loop diagram).** Meaningless to me.
- **"A model proposes facts; code decides what gets in" plus the table "Has a day you never said → narrowed to the month or year you did say" (Keep).** I sort of got it: it won't make things up. But it read like a rulebook.
- **"Rather file things yourself? Keep your own schema-checked store; engram only reads it."** This might be the closest thing to "bring your existing stuff", but "schema-checked store" means nothing to me.
- **The Find output (`{"chain":"north-bed",…}`, `p8qdad`, "versions 2026-07 me:").** It's a terminal answer, not a chat answer.
- **"--domain notes".** I hoped "notes" meant notes. It's the name of a made-up garden.
- **"Rewire … your own words → your jobs → the kinds of question each job brings".** Jobs? I'm a teacher; I have one job.
- **"Evolve … engram refine (skill: skills/engram-refine/) tunes engram and each repo … within a budget."** A money budget?
- **"ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/".** No idea.
- **"Needs Python 3.12+ and uv".** What is uv?
- **`cat > ~/.config/engram/config.toml <<EOF … EOF`.** I'd paste it and pray.
- **"Claude Code sessions" (Quickstart).** Is this my Claude app or something else? It never says.
- **The shape doc's "The canon".** Canon like Star Wars canon?

## 4. The value moment

Almost. The closest was **"Ask for a whole history: `what happened with the north bed this season?`"** in Find. That *is* my story: "I've written it all down somewhere; I want to just ask and get it back." But the answer comes back as a terminal table about a fake garden, and nothing shows that my Apple Notes could be what's searched. So: **never, for me.** The banner's "Bring your knowledge base" promised it, and the page never paid it off.

## 5. Claims

- **Believed:** "Corrections never erase … engram keeps both". Fine, and comforting, though I wouldn't have asked for it. "No forms, no upkeep" sounds lovely, and I believed they mean it.
- **Doubted:** "Bring your knowledge base". Nothing on the page shows how, so I stopped believing it was for someone like me. "Just talk to Claude" too, because the Quickstart is all typed commands, not talking.
- **Didn't understand:** "fewer tokens than grep", "Relational … tangents grep never reaches", "Filed to be found … typed links", "one repo per area of your life", all of Rewire and Evolve, and the Architecture box.

## 6. Exit

I closed the tab after the first lines of the "shape" doc, about 4.5 minutes in. I didn't star it and didn't install. My reasons:

- Searching the page for "Apple" found nothing.
- The setup needs git, Python and something called uv.
- The only "notes" in it are a made-up garden.

Installing would mean a Terminal session that ends with a pretend garden, not my notes. I'd have needed to see "Apple Notes" or "import" somewhere before risking that.

## 7. In your own words

"Saw this 'second brain' thing on Reddit and the banner literally says 'bring your knowledge base', so I got excited. But it's a coder tool: git, Python, terminal commands. As far as I can tell it remembers what you *tell Claude* from now on, not the notes you already have. Nothing about Apple Notes or Keep, so not for me, but maybe for your techy brother-in-law."

## 8. What would have kept / convinced you

- One sentence near the top saying "Already have notes in Apple Notes / Google Keep / Obsidian? Here's how to bring them in", with steps, or an honest "not yet, export them as text files first".
- An example made of things like mine (a recipe, a note about my kid's ear infection, the plumber's number) instead of tomatoes, so I can see *my* kind of question coming back.
- Showing the answer the way I'd see it: Claude replying in the chat, not a black box of ids.
- A plain line on whether this works with the regular Claude app or only with "Claude Code", and what that is.
- Telling me what "repo per area of your life" means for me. For example: "you'd have one for the house, one for the kids' health, one for school ideas, and engram can set them up for you."
- A "you'll need to be comfortable in Terminal" warning up front, so I'd know in 5 seconds instead of 4 minutes.
