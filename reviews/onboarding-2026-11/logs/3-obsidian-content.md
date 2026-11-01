# Log: persona 3 (content Obsidian user, UX researcher, ~2,500-note vault, uses the Claude app, avoids git)

Arrived from an "Obsidian + AI" newsletter link. Patience about 3–4 minutes. The question I came with: "My vault works. Does this sit beside Obsidian or replace it, and will it touch my files?"

## 1. Path

1. **Repo page top (readme-00), ~3 s.** A wall of GitHub nav. Scrolled straight past it.
2. **Banner (readme-01 top), ~10 s.** A brain made of raining letters, an orange pixel "engram". "Bring your knowledge base, or start fresh." That's me, I have a knowledge base. "Recall every thread and aside, in fewer tokens." Lost me on "tokens". Then `keep  find  rewire  evolve`. "Rewire" made me a bit wary.
3. **Badges and nav row, ~3 s.** python, SQLite FTS5, "record plain git", MIT. "plain git" is the second time it says git and I haven't read a sentence yet.
4. **First two paragraphs, ~30 s.** "engram files what you tell Claude Code into plain git…" Then: "For one person using Claude Code on their own computer… **Not the Claude app or claude.ai.**" I use the Claude app. So this isn't for me as I am today. Kept going only because the newsletter said "Obsidian".
5. **The four bullets and "It does four jobs", ~25 s.** "Plain git: one repo per area of your life." I don't have repos and don't want any. "Rewire: reshape a repo around the questions you bring it." "Evolve: … a weekly pass under a dollar cap you set." A dollar cap? Is this paid on top of Claude?
6. **Loop diagram (animated), ~10 s.** session → keep → hourly filer → `/[latest].md` → git commit + push → index → find. Nice motion, but it's an engineer's diagram. "git commit + push" again.
7. **Ctrl+F "Obsidian", ~5 s.** One hit on the whole page. Jumped there.
8. **"Rewire" section, "Have notes already?" table plus the Obsidian line (readme-03), ~60 s.** This is the only part written to me. Row 1: "A folder of Markdown, in git or not | search by heading, as it stands, read only." Good: that's my vault, no git needed, read only. Then: "On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to." Read it three times. Does "on hold" mean not supported yet? Or that they're held as they are? "Never written to" is what I wanted to hear, but "on hold" in front of it cancels it out. Then the rewire diagram: "your repo, as it is" turns into "a page per name", "one per category". That's exactly what I don't want done to my vault, even if it says "on a scratch copy".
9. **"Evolve" diagram (~10 s, skimmed).** "every week, once you turn it on: tidies your graph", "a record regrouped, saved by itself". "Tidies your graph" by itself, every week? No. I know it says "once you turn it on", but my gut said no.
10. **Clicked "Quickstart" from the table row, ~30 s.** "Needs git, Python 3.12+ and uv." No idea what uv is. A table of launchd jobs, systemd timers, `loginctl enable-linger`. Then `git clone …`, `uv sync`, `export ENGRAM_CONFIG=…`. For my own notes: "add `[domains.<name>]` with `repo = "<a folder of Markdown>"` to your config". I can edit a config file, but which one? I'd have to make it first, and I'd need Claude Code, which I don't have.
11. **Scrolled through Docs list, ~5 s.** "data model", "shape", "migration", "frozen gate". Didn't click any. Closed the tab.

Total: about 3.5 minutes.

## 2. First impression (first 10 seconds)

A good-looking developer tool for "AI memory". The brain banner and "Bring your knowledge base" made me think it might plug into my vault. "Fewer tokens" and the terminal-style font told me it was built by and for coders. I thought it might be an Obsidian plugin or a companion app. It isn't either.

## 3. Confusions

- **"in fewer tokens"** (banner tagline): I don't think in tokens. I guessed it's about cost or speed for the AI.
- **"Not the Claude app or claude.ai."** (second paragraph): clear, but it's a dealbreaker that comes before any reason to care. I didn't know Claude Code was a separate thing from the app I use.
- **"Plain git: one repo per area of your life"** (bullets): I don't know what a "repo per area" would mean for one vault. Would I have to split my vault into several git repos?
- **"engram files what you tell Claude Code into plain git"**: files where? Into my vault? A new folder? This is the "will it touch my files" question, and the top of the page doesn't answer it.
- **"Rewire" / "reshape a repo around the questions you bring it"**: sounds like it restructures my notes. The diagram (tangle → "a page per name", "one per category") looks like it does.
- **"On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to."** (under "Have notes already?"): the most important sentence for me, and I can't parse it. Is Obsidian support "on hold" (not working yet)? Or does "on hold" mean my tags and links are held as they are? I guessed it's not supported yet, which makes "never written to" a promise about a feature that doesn't exist.
- **"search by heading, as it stands, read only"**: "read only" is great. "Search by heading" I don't get: does it only search my headings, not the text under them? Most of my daily notes barely have headings.
- **"a dollar cap you set"** (Evolve): paid how? Is this an extra subscription? Later "your subscription" in "Where your data goes" suggests it uses my Claude plan, but that's down at the bottom.
- **"tidies your graph… saved by itself"** (Evolve diagram): "graph" to me means Obsidian's graph view. It sounded like it rearranges my notes weekly without asking.
- **"hourly filer", "/[latest].md", "git commit + push"** (loop diagram): the `[latest].md` with brackets looked like a placeholder I was supposed to understand.
- **"`pack`", "`.engram/engram.toml`", "pre-commit refuses", "drift"** (Rewire bullets): no idea.
- **"Needs git, Python 3.12+ and uv"** (Quickstart): what's uv?
- **`[domains.<name>]`**: "domain" makes me think of websites.
- **The terminal example in Find** (`uv run engram timeline … --domain notes` followed by a JSON line and a table with ids like `p8qdad`): it showed me what Claude would get back. I wanted to see what *I* would see.

## 4. The value moment

Almost, but no. The nearest was the "Have notes already?" table:

> "A folder of Markdown, in git or not | search by heading, as it stands, read only"

For a second that matched my story: it reads my vault as it is, doesn't need git, and doesn't write. Then the next line ("On hold: an Obsidian vault's…") made me doubt whether my vault counts. And everything else on the page (Keep, Rewire, Evolve) is about the opposite: git repos that it writes, reshapes and tidies. The read-only path also only gets "search by heading". All the impressive stuff (stories, timelines, corrections) is for "A git repo of it, rewired". So the value is behind the two things I don't want: git and rewiring.

## 5. Claims

- **Believed:** "read only" / "never written to" for a plain Markdown folder. It's said plainly and twice. "Records stay in your repos": local and private, mostly. I believed that it reshapes on a copy first and shows me before and after. It's the kind of thing a careful person writes.
- **Doubted:** "Bring your knowledge base". Technically yes, but only as headings-only search unless I turn it into a git repo and "rewire" it. That's not really bringing it. Also "Recall every thread and aside": from my vault, or only from Claude Code chats?
- **Didn't understand:** "finds what grep finds for just over half the tokens" (don't know grep beyond the name, don't care about tokens). "corrections kept, both versions come back as one result". Sounds smart, but I don't correct facts in my vault, I just edit notes. "Each repo searches only itself unless you ask."
- **Privacy:** "filing sends each finished session to Claude through your own Claude Code". Fine, I already paste notes into Claude. But it's at the very bottom, under "Architecture", where I almost didn't scroll.

## 6. Exit

Closed the tab at the Quickstart, about 3.5 minutes in. I didn't star it or install it. Reasons, in order:
1. It's for Claude Code, not the Claude app I use (said in paragraph two).
2. Install needs git, Python, "uv", terminal exports and background jobs. Way past "edit a config file".
3. The one sentence about Obsidian says "On hold", which I read as "not yet".
4. "Rewire" and "Evolve tidies your graph" made me nervous about my files, even with the copy-first promises.

I didn't try installing.

## 7. In my own words

"Saw this engram thing from the Obsidian newsletter. It's not an Obsidian plugin. It's a memory system for Claude Code that keeps your stuff in git repos and reorganizes them. It can apparently search a Markdown folder read-only, but Obsidian support says 'on hold', and you need Claude Code and a terminal setup to try it. Pretty diagrams, not for me."

## 8. What would have kept / convinced me

- Say near the top, in one line, what it means for an Obsidian vault: "Point it at your vault. It reads it, never edits it, no git needed. Obsidian stays your editor." If that's true, put it in the first screen, not under "Rewire".
- Replace "On hold:" with plain words. If Obsidian isn't supported yet, say "Not yet: Obsidian tags, daily notes and [[links]]" and when. If it is, drop "on hold".
- Tell me what I'd get with my vault as it is: one example question against daily notes, and the answer as I'd see it in a chat, not a JSON line and an id table.
- Explain "Claude Code" vs. the Claude app before I hit "Not the Claude app". One line on what Claude Code is and whether my Claude subscription covers it.
- Make it obvious that Rewire and Evolve are opt-in and only apply to repos engram owns, never my vault. Put "your existing notes are never touched" next to the scary diagrams.
- An easier install path for someone who doesn't use git: even "one command, then point it at a folder".
- Don't use "graph" for something other than what Obsidian people mean by graph, or say what it means.
