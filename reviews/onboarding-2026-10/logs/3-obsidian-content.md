# Persona 3: content Obsidian user, cold read of engram (branch readme-art)

Arrived from an "Obsidian + AI" newsletter link. My vault works fine, about 2,500 notes with daily notes, Templater and Calendar, synced with Obsidian Sync. I'm not using git. Two questions going in: does this replace Obsidian or sit beside it, and will it touch my files?

## 1. Path

1. **Repo page top** (~5 s). GitHub chrome, skipped it and scrolled to the README.
2. **Banner** (~10 s). An orange pixel logo "engram", a brain made of letters with characters raining through it, and "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." I stopped on "Bring your knowledge base". My vault is a knowledge base, so maybe this is for me.
3. **Badges and nav row** (~3 s). "python 3.12+", "index SQLite FTS5", "record plain git", "license MIT". "plain git" was a small alarm.
4. **Intro paragraph and five bullets** (~30 s). Read "engram gets Claude everything your record holds on a question … in fewer tokens than grep." Then skimmed the bullets. "Relational: follows the knowledge graph" made me think of graph view and backlinks. "Plain git: one repo per area of your life" made me think "so it's git, and I need several of them?"
5. **Four jobs list** (~15 s). "Keep: you talk, engram files what matters." "Rewire: fit each repo to the way you actually use it." "Evolve: improve engram and your repos every week." Each one sounds like it changes my stuff.
6. **Session / hourly filer / index diagram** (~15 s). Boxes with "hourly filer", "/[latest].md", "git commit + push". So it writes markdown files and pushes them somewhere, every hour.
7. **Keep section, the "Proposed fact" table and the tomato card** (~25 s). Got that it pulls facts out of Claude chats about my garden(?) and has rules about what gets in. In my capture the four "code guards" boxes on the right were empty, so maybe they animate. Read "Rather file things yourself? Keep your own schema-checked store; engram only reads it." That was the one line that sounded like my question, but I don't know what a "schema-checked store" is. Is my vault one? Probably not.
8. **Find section** (~20 s). A terminal command, `uv run engram timeline …`, and a wall of JSON plus a table. Skimmed past it. Liked "Corrections never erase." The second diagram had two big empty boxes ("in the record" / "one result").
9. **Rewire section** (~25 s). This diagram scared me. "your repo / as it is" with a tangled graph, then an arrow, then "rewired around them": "a page per name", "entries on a thread", "one per category". That reads exactly like "we will restructure your vault." "drift refused at commit" and "pre-commit refuses" came next. Then `ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/`, which I wouldn't type.
10. **Evolve section** (~15 s). Week 1 to week 4 graph cards: "saved by itself", "drop a group you asked for? asks you first". The text says "It never touches your record." But the cards say it regroups things "by itself". Which is it?
11. **What a record is made of** (~15 s). `events/2026/06/[id].md`, one file per fact, "never edited", plus `events/links.jsonl` and `[page].md` "rewritten whole". That isn't how my notes look. My daily notes are one file per day with lots of stuff in them, and I edit them.
12. **Ctrl+F "Obsidian"** (~5 s). 0 results. Ctrl+F "Markdown": 0 results. Ctrl+F "vault": 0.
13. **Architecture and Quickstart** (~15 s). "[your repo]/ your record, plain git" with a `.engram/` folder inserted into it. Quickstart is `git clone`, `uv sync`, a `cat > … <<EOF` config, and "owner = "Sam"". Didn't try it.
14. **Docs list → clicked "shape"** (~40 s), because it says "onboarding a repo" and I wanted to know what happens to *my* files. It opened with "The canon" and a table full of Entry / Document / Link / Thread / Theory / Current / Way in / Lens. "append-only; never edited or deleted once committed." "Moving a file … never breaks a link" sounded nice. I scrolled to "Rewiring a repo": "The proposal, in a scratch clone … lands through migration". That's not reassuring when I don't know what migration does to my notes. Closed the tab.

Total: about 4 minutes.

## 2. First impression (first 10 seconds)

The banner is pretty. The rain-through-the-brain art made it feel like a design-y indie project, not enterprise. "Bring your knowledge base, or start fresh" made me think this is an AI layer you point at your notes, like a smart search over a vault. Then the badges said "plain git" and "SQLite FTS5", and I started to think it's a developer tool for people whose notes live in git.

## 3. Confusions

- **"Bring your knowledge base, or start fresh."** (banner). Bring it *how*? As-is? Imported? Converted? It never comes back to this line.
- **"in fewer tokens" / "in fewer tokens than grep"** (banner, intro). I know tokens are an AI cost thing, vaguely. "grep" I've heard of but I don't search my notes with it. It isn't a benefit I'd feel.
- **"your record"** (everywhere). Is my vault "a record"? It reads like medical records or logs, a different thing from notes.
- **"one repo per area of your life"** (intro bullets). I have one vault. Do I have to split it into repos? Does it have to be git?
- **"typed links", "led-to", "revises"** (intro). I have `[[backlinks]]`. Are these the same? Does it understand mine, or ignore them?
- **"files what matters" / "hourly filer"** (Keep). It files where? Into my notes folder? New files every hour that Obsidian Sync then syncs everywhere?
- **"git commit + push"** (diagram). Push to where? I don't have a GitHub for my notes, and I don't want my journal on GitHub.
- **"schema-checked store"** (Keep). No idea. Guessed "a database with strict fields", so not me.
- **"--domain notes"** (Find). Domain like a website domain? I guessed it's a name for one repo.
- **"rewired around them" / "Rewire"** (Rewire diagram). Guessed it means reorganising my folders and notes into its layout: "a page per name", "entries on a thread". That's exactly what I don't want.
- **"drift refused at commit", "pre-commit refuses"** (Rewire). Guessed that after it's set up, if I organise my notes my own way, it blocks me? Scary.
- **"It never touches your record."** (Evolve) vs **"a record regrouped ✓ saved by itself"** (Evolve diagram). These directly contradict each other as I read them.
- **"events/2026/06/[id].md … one fact, never edited"** (record section). Does it want one fact per file? My notes are not like that.
- **"[page].md … rewritten whole"** (record section). Rewritten by whom? By the AI? My notes?
- **"pack", "the area's own words"** (Architecture bullet). Lost.
- **"Not goals: … a web UI."** OK, so there's no app at all. Terminal only?
- **Quickstart `owner = "Sam"`**. Who's Sam? Do I put my name?
- **`ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/`**. "skills" and "~/.claude". I use Claude in the app, not this.
- **Empty diagram boxes** (code guards, "in the record" / "one result"). They looked broken or unfinished to me, but maybe they animate on real GitHub.
- **shape.md: "The canon", "Theory", "Way in", "Lens", "the advisor"**. Too much vocabulary. "Theory … changes only when the owner agrees". What theory?

## 4. The value moment

**Never.** The closest was the banner line "Bring your knowledge base, or start fresh." It promised my story (use what I already have), but nothing after it explained *how* my existing notes come in, or that they stay as they are. The other near-miss was "Corrections never erase." I like that idea, but it's about facts engram files, not my notes.

My story was "My vault works. Why would I change, and will this touch my files?" The README answered the second half with what sounded like "yes: it rewires your repo, files new entries hourly, commits and pushes." It never answered the first half.

## 5. Claims

- **Believed:** "Plain git … readable without engram". I believe the files are just markdown. "Most sessions file nothing", because it's oddly specific. "MIT", and that it's local-ish (config in `~/.config`, index in `~/.local/share`).
- **Doubted:** "It never touches your record" (Evolve). The same README shows it filing entries, committing, pushing, regrouping "by itself", and "rewiring" my repo. "No forms, no upkeep". The Rewire section looks like a lot of setup. "Recall every thread and aside" is a big promise I had no way to check.
- **Didn't understand:** "in fewer tokens than grep", "typed links", "schema-checked store", "drift refused at commit", "pack", "area", "the advisor". And whether it's private at all: "push" suggests something leaves my machine, and the README never says where to.

## 6. Exit

Closed the tab after the shape doc, about 4 minutes in. Didn't star or bookmark. Didn't try installing. The Quickstart starts with `git clone` and a heredoc, and the whole thing assumes my notes live in a git repo, which they don't. My reasons for leaving: (a) nothing mentions Obsidian or a Markdown vault, so I assume it isn't meant for me; (b) the Rewire diagram made me believe it would restructure my notes; (c) I'd need git, which I avoid on purpose.

## 7. In my own words (to a friend)

"Saw this 'engram' thing in the Obsidian AI newsletter. Gorgeous banner, but it's really a git-based tool that turns your Claude chats into little fact files and then 'rewires' your notes repo around them. It never mentions Obsidian once, and I couldn't tell if it would leave my vault alone, so, no thanks. Maybe if you already keep your notes in git and live in the terminal."

## 8. What would have kept / convinced me

- One line near the top saying what it does to an existing Markdown folder: "Point it at your Obsidian vault (or any folder of .md files). It reads them as they are, and never edits, moves or renames your notes." If that's true. If it's not true, tell me up front.
- The word "Obsidian" somewhere, even "works beside Obsidian, doesn't replace it", and a line on whether it understands `[[wikilinks]]`, tags and daily notes.
- A straight answer on git: do I need it? Does it work with Obsidian Sync? Where does "push" push to? Is anything sent anywhere besides to Claude?
- The "rewire" picture shown as something *I* approve first, before/after, with an undo. The doc has "in a scratch clone first" and "after the owner has seen their pages" (I gather), but that reassurance should be on the front page, next to the scary diagram, not buried.
- An example that looks like a notes vault (a daily note, a project note with backlinks), not a garden fact log in JSON.
- A one-sentence "why bother if your vault already works": e.g. "ask Claude about three years of daily notes without pasting them in." That's the itch I actually have. The README never said it in my words.
