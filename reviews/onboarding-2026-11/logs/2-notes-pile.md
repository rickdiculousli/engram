# Persona 2: notes-app pile (41, teacher, 1,200+ Apple Notes + Keep notes, Claude app weekly)

## 1. Path

1. **Repo page top** (~5 s). A wall of GitHub menu stuff I scroll straight past. Not why I'm here.
2. **Banner** (~15 s). Orange brain made of letters, raining. "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." First line is exactly my Reddit thread. Second line: "tokens"? Then `keep · find · rewire · evolve` in orange. Keep and find, yes please.
3. **Badges + first paragraph** (~20 s). Skip the badges (python, SQLite, git: nope). "engram files what you tell Claude Code into plain git, and hands Claude the whole story when you ask." I tell Claude things... but what's "Claude Code"? "On a real record it finds what grep finds for just over half the tokens." No idea what grep is.
4. **"For" line** (~15 s, re-read twice). "For one person using Claude Code on their own computer: macOS, Linux, or Windows through WSL2*... Not the Claude app or claude.ai." That's the thing I pay for. My stomach drops a bit. I don't click the Claude Code link yet because I want to know if my notes count first, and the banner promised that.
5. **Four bullets + "It does four jobs"** (~25 s). "one repo per area of your life" — still no idea what that means for me. "you talk → engram files the facts... No forms." Nice. "you ask → Claude gets the whole story". That's the dream. "Rewire: reshape a repo around the questions you bring it" — lost. "Evolve: ... a weekly pass under a dollar cap you set" — wait, it costs money on top?
6. **Loop diagram** (~15 s, watched it animate). "a session", "me: [knowledge]", "hourly filer", "/[latest].md", "git commit + push", "index". Boxes and arrows. I get "you say something, later you ask and it comes back." The rest is for programmers.
7. **Keep section + filer animation** (~30 s). The tomato example is the first thing that feels human: "picked about 3 kg of Sungold this week, the Brandywine are slow." I like that it crossed out "5 kg" because I never said 5. That's a nice touch. But this is all about *talking* to it going forward. Where's my existing pile?
8. **Find section** (~10 s). A black terminal block with "$ uv run engram timeline ..." and a table of ids like "p8qdad". Scrolled past fast. The corrections animation I half get ("nothing erased · every version kept").
9. **Rewire: "Have notes already?"** (~40 s). THIS is my question. Read the table three times. "A folder of Markdown, in git or not → search by heading, as it stands, read only". "Your own tool and its store → a pack reads it in". Then: **"Apple Notes and Keep have to be exported to Markdown."** OK so it does mention my apps by name. But how? Apple Notes doesn't have an export-to-Markdown button that I know of. No link, no steps.
10. **Clicked "pack"** (~20 s) because "Your own tool and its store" sounds like Apple Notes is "my own tool." Landed in docs/shape.md "A pack": "the record's data (kinds, link families, nodes, lenses, ways in, people)... the filer, the repeat check, the theory revision and the evidence re-check". Back button immediately.
11. **Clicked "Quickstart"** from the "Have notes already?" row (~40 s). "Needs git, Python 3.12+ and uv." Table of "launchd jobs", "systemd user timers", "loginctl enable-linger". Then a code block that sets up a made-up garden, not my notes. "Your own notes: add `[domains.<name>]` with `repo = "<a folder of Markdown>"` to your config". What config? Where? This is not a hand-holding guide.
12. **Glanced at Docs list** (~10 s). "data model", "FTS5", "migration", "frozen gate". Closed the tab.

Total: about 4 minutes.

## 2. First impression (first 10 seconds)

Pretty orange brain art and "Bring your knowledge base." I thought: oh, this might be one of those "chat with all your notes" tools from the Reddit thread, maybe something that plugs into Claude. Then the badges said python/SQLite/git and I thought "uh-oh, this is a programmer's thing."

## 3. Confusions

- **"Bring your knowledge base"** (banner). I assumed "knowledge base" = my notes. The page never says plainly whether a pile of Apple Notes counts until way down in Rewire, and then only as "have to be exported to Markdown."
- **"in fewer tokens"** (banner). Something about AI cost? Meant nothing to me.
- **"Claude Code"** (first paragraph). Is that a different product from my Claude? A setting in the app? Guessed it's a developer version.
- **"Not the Claude app or claude.ai."** (For line). Clear, and it rules me out. But it's sitting next to "Bring your knowledge base", which made me think it was for me.
- **"grep"** (first paragraph, "finds what grep finds"). No idea. Guessed it's another search program.
- **"plain git" / "one repo per area of your life, readable without engram"** (bullet). Repo = folder? Area of my life = recipes vs. school vs. kid's medical? Not explained for a normal person.
- **"WSL2*"** (For line). Don't know, I'm on a Mac anyway.
- **"Rewire: reshape a repo around the questions you bring it, on a copy first"**. Lost. Is that the part that imports my notes? Turns out it's where "Have notes already?" lives, which I would never have guessed from the word "Rewire."
- **"a weekly pass under a dollar cap you set"** (Evolve bullet). Does this cost extra money on top of my Claude subscription? Not answered where I'd look.
- **"/[latest].md", "git commit + push", "index... linked as a graph"** (loop diagram). Programmer words.
- **"$ uv run engram timeline ... --domain notes"** and the id column "p8qdad" (Find). I'd never type that. Does Claude type it for me? It says "Claude runs these through Bash." Bash?
- **"search by heading, as it stands, read only"** (Have notes already? table). My notes don't have headings. Does that mean it only finds titles?
- **"A git repo of it, rewired → stories, timelines, corrections and hourly filing"**. So the good stuff needs my notes to be "a git repo... rewired." No idea how.
- **"Your own tool and its store → a pack reads it in"**. Thought Apple Notes was "my own tool." The pack page was unreadable ("link families, nodes, lenses, ways in").
- **"Apple Notes and Keep have to be exported to Markdown."** No how-to. What is Markdown, exactly — a file type? Is there an Apple Notes button for that?
- **"On hold: an Obsidian vault's tags..."** "On hold" — is Obsidian not working yet? I'd heard Obsidian was the thing to try.
- **Quickstart "Needs git, Python 3.12+ and uv."** I have Homebrew from one tutorial. Nothing here says "on a Mac, paste this."
- **"add `[domains.<name>]` with `repo = ...` to your config"**. Which file, opened with what? `~/.config/engram/config.toml` — that path is hidden on a Mac, isn't it?
- **"launchd jobs", "loginctl enable-linger"**. No idea.

## 4. The value moment

Almost, twice, but never fully.
- First near-hit: banner "Bring your knowledge base, or start fresh." That's my story, but it's a slogan, not a promise I can check.
- Second near-hit: the tomato animation ("picked about 3 kg of Sungold... the Brandywine are slow" → filed). Felt like "it remembers what I actually said." But that's about new things I *say* to Claude Code, not getting back the 1,200 notes I already wrote.
- Then "Apple Notes and Keep have to be exported to Markdown" told me my pile is a do-it-yourself project before anything works, with only "search by heading" as the payoff.

So: **never** for my story ("I want to just ask, and get the note back"). The value it shows is for people who will talk to Claude Code from now on, not for people with an existing pile.

## 5. Claims

- **Believed:** "Not the Claude app or claude.ai." Very clear, and the reason I left.
- **Believed:** "Most sessions file nothing" and the crossed-out "5 kg". The example made the "only your own words" idea feel real and careful.
- **Believed, but scared me:** "Apple Notes and Keep have to be exported to Markdown." Honest, but no path.
- **Doubted:** "Bring your knowledge base." The banner implies my notes come in; the body says only Markdown folders, read only, by heading. The banner over-promised for me.
- **Didn't understand:** "finds what grep finds for just over half the tokens, and more of the story (measured)." Sounds like a benchmark for programmers.
- **Didn't understand:** "a weekly pass under a dollar cap you set" — not sure if this is optional, or what it costs.
- **Didn't understand:** "one repo per area of your life."

## 6. Exit

Closed the tab after the Quickstart, about 4 minutes in. Two reasons, in order: it isn't for the Claude app I use ("Not the Claude app or claude.ai"), and my Apple Notes/Keep pile needs an export to Markdown that the page doesn't explain, after which I'd only get "search by heading." Didn't install: the Quickstart needs git, Python, uv and a config file I'd have to hand-edit, and it starts with a made-up garden instead of my notes. No star, no bookmark. Might mention it back on the Reddit thread as "looks cool but it's for coders."

## 7. In my own words

"Someone on Reddit linked this 'second brain' thing with a gorgeous brain banner that says 'bring your knowledge base,' so I thought finally, my notes. But it's for Claude Code, not the normal Claude app, and Apple Notes has to be exported to some Markdown format first, which they don't explain. It looks really careful about only saving what you actually said, but it's built for programmers who talk to Claude in a terminal all day."

## 8. What would have kept / convinced me

- Right under the banner: one honest sentence like "You'll need Claude Code (a free/paid add-on, here's what it is) and a Mac/Linux terminal. If you only use the Claude app, this isn't for you yet." I'd rather know in 10 seconds than in 4 minutes.
- If "Bring your knowledge base" stays, a short "Got Apple Notes or Google Keep?" box near the top with the actual steps: how to get my notes out as Markdown (which app or button, Google Takeout for Keep), where to put the folder, the exact command, and what I'd get back. Not "add `[domains.<name>]`".
- An example with notes like mine: "ask 'what was that lasagna recipe from Mum?' → it shows the note." The garden is cute but it's about logging new things, not finding old ones.
- Say plainly what "search by heading" means for notes without headings: will it find my words inside the note, or just the titles?
- Tell me whether this costs anything beyond my Claude subscription ("dollar cap" spooked me).
- A step-by-step Mac install that assumes I have Homebrew and nothing else, with "paste this, you should see this."
