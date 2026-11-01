# Persona 5: Record keeper (52, caregiver, health log in a spreadsheet and Google Docs)

Came from a caregiver forum post titled something like "AI for medical history". I use the Claude chat app. I've been burned by it giving me a date for when Mum's dizziness started that I never said. I'm reading this on my laptop, carefully. I'll give it about 10 minutes if it looks trustworthy.

## 1. Path

1. **Repo page top and banner** (~15 s). An orange brain made of random letters, with letters raining through it. Big blocky "engram". "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Then the badges: python, SQLite FTS5, plain git, MIT.
2. **The first paragraph and the "For" line** (~45 s). Read it twice. "Not the Claude app or claude.ai." My heart sank a bit, because that is what I use.
3. **The four bold bullets** (~40 s). "Only what you said" and "Corrections kept" are exactly my problem. I kept reading because of these.
4. **"It does four jobs"** (~20 s). Keep and Find made sense. Rewire and Evolve did not.
5. **The loop diagram** (~30 s, watched it animate). "me: [knowledge]" goes into an "hourly filer", gets three ticks, becomes "/[latest].md", then "git commit + push". Then "index, your records, linked as a graph".
6. **The Keep section: the table and the filer animation** (~2 min). Watched the whole animation twice. This is the best part of the page for me.
7. **Clicked "technical" ("How the filer checks each fact")** (~1 min). A wall of text. Picked out the "Dates never said" bullet and `date: not-sure`. Also hit "(an answered question in Claude's words)", which worried me. Went back.
8. **The Find section: the terminal output and the versions diagram** (~1.5 min). Read row 2, "corrected: July → late June", slowly. The diagram was empty on the first frame. Then a [fact] marked 07 and a [correction] marked 06 appeared, with "nothing erased · every version kept".
9. **Rewire, "Have notes already?"** (~1 min). Looked for "spreadsheet", "Excel" or "Google Docs" and found none of them. Skimmed past "pack", "Obsidian", "rewired", "ln -s".
10. **Evolve** (~45 s). "under a dollar cap you set", "A change lands by itself", "saved by itself". This alarmed me.
11. **"What a record is made of" and Architecture** (~40 s). The files looked readable, which I liked. The architecture box with `~/.config/...` meant nothing to me.
12. **"Where your data goes"** (~1.5 min). This is the paragraph I came for. Read it three times.
13. **Clicked "operations" from that paragraph** (~1 min). Its "Where things live" table talks about "box", "the second box", "ssh host", "daily copy to a second box", "archive's mirror". I closed it more worried than when I opened it.
14. **Quickstart** (~30 s). git, Python 3.12+, uv, launchd, systemd, `loginctl enable-linger`, WSL2. Decided not to try it.
15. **Docs list, clicked "sources" ("what gets indexed")** (~40 s), hoping it would say whether a spreadsheet could come in. Got "The connector contract", "Idempotent", "Watermarks live in `ingest_state`". Nothing about spreadsheets. Left.

Total: about 11 minutes. That's past my patience, but the top of the page earned the extra time.

## 2. First impression (first 10 seconds)

Something for programmers that uses AI. The brain made of letters looks like a hacker movie, not a health tool. "Knowledge base" sounds like a company wiki. "Fewer tokens" means nothing to me. I guessed it was "a way to save notes so an AI can search them", for coders. I nearly left, but the forum post had promised it was about keeping a medical history, so I scrolled.

## 3. Confusions

- **"Recall every thread and aside, in fewer tokens."** (banner) I don't know what tokens are or why I'd care. My guess is it's a cost thing for programmers.
- **"On a real record it finds what grep finds for just over half the tokens"** (first paragraph). "grep" means nothing to me. I skipped the claim.
- **"Not the Claude app or claude.ai."** (For line). This is clear, and it's a blocker. Is Claude Code something I can get? Is it a different subscription? Is it only for programmers? The page doesn't say what I'd need to start.
- **"one repo per area of your life"** (Plain git bullet). I know "repo" from GitHub vaguely. Does each area of my life need its own GitHub thing? Would Mum's health be on GitHub?
- **"Quote, numbers included, isn't in your own words → dropped"** (Keep table). I had to read it three times. I think it means "if the quote, or any number in it, isn't something I actually said, it's thrown out". The comma grammar threw me.
- **"hourly filer", "/[latest].md", "git commit + push"** (loop diagram). I guessed it writes a little file every hour and saves it with git. "Push" to where?
- **"what the owner said"** (filer diagram). Who is "the owner"? I assume me, but it reads as if someone else owns my record.
- **"waits until it settles"** with a "1 hr" clock (filer diagram). I guessed it waits an hour after I stop talking. Fine.
- **The filer animation ran out before I saw the fourth fact.** At about 9 seconds the third row, "Brandywine slow to ripen, date 2026-09-21", still had no verdict. I had to wait for it to loop to see that the date became 2026-09. That narrowing is the most important thing on the page for me, and it comes last.
- **"(an answered question in Claude's words)"** (technical, The filer). Does this mean that if Claude asks me "Did the dizziness start in March?" and I say "yes", the fact gets filed in Claude's words? That's exactly how I've been burned: Claude suggests a date and I half-agree. This needs a plain answer.
- **"`date: not-sure`"** (technical). Reassuring, but it's buried in the technical doc. It should be on the front page.
- **"--domain notes"** (Find). I guessed "domain" means which notebook, here the garden one.
- **"Claude runs these through Bash"** (Find). I don't know what Bash is. Do I type these commands, or does Claude?
- **The versions diagram: "07" and "06"** with no year. I guessed these are months, July and June. On my record the year matters too.
- **"revises" arrow** pointing from the correction up to the fact. I worked it out, but only with row 2 of the table above.
- **"ranked matches, tuned by the repo's own weights"** (Find table). No idea what this means.
- **"Rewire" as a whole.** "pack", "rewired", "Obsidian vault", "`[[links]]`", "drift from it → the repo's pre-commit refuses", "`ln -s ...`". I was lost. What I needed to know was: can my 6 years of spreadsheet come in? The table only says "A folder of Markdown" and "Apple Notes and Keep have to be exported to Markdown". There is nothing about Excel, CSV or Google Docs.
- **"Evolve": "tunes engram and each repo ... every week, under a dollar cap you set"**. Dollars? Does this cost money on top of my subscription? And "a record regrouped, saved by itself": something rearranges Mum's medical record every week without asking me? "One revert undoes it" doesn't help, because I don't know what a revert is.
- **"pushed only to the remote each one names"** (Where your data goes). What is "the remote"? GitHub? Is it private? Does it push by default? Can I say no remote at all?
- **"filing sends each finished session to Claude through your own Claude Code (`claude -p`, your subscription)"**. So the whole conversation goes to Anthropic again, every hour? I guess that's no worse than chatting, but "each finished session" sounds like every session, including ones about other things. The sources doc says a session goes by "the repo it was started in", but in programmer words.
- **"the second box", "ssh host", "daily copy", "the archive"** (operations doc). This sounds like my data gets copied to another computer. Whose? I couldn't tell whether that's optional.
- **"secrets are masked at ingest"** (sources). What counts as a secret? Passwords? Mum's NHS/insurance number?
- **The garden example.** Sungold, Brandywine, basil bolting. I understand the idea, but I had to translate every example into "Mum's meds" in my head.

## 4. The value moment

The four bullets near the top:

> **Only what you said:** a fact gets in only in your words and numbers; a day you never gave → the month you did
> **Corrections kept:** fix a fact → both versions come back as one result, the newest in full

Then the filer animation confirmed it, when "5 kg of Sungold picked" got struck through with "dropped, not in their words". The table row "Has a day you never said → narrowed to the month or year you did say" is my exact story. That's "nothing invented" and "the dates I actually said". It matches what I want almost word for word. Row 2 of the timeline output ("corrected: July → late June") is "corrections kept", shown for real.

## 5. Claims

- **Believed: "a day you never gave → the month you did".** The animation shows it, and the technical doc says code checks it, not the AI. That "code decides" line matters to me: "Claude ... proposes facts; code decides what gets in". I trust a rule more than the AI.
- **Believed: "Corrections never erase."** It's saved in git, which I understand keeps history. Row 2 shows both versions.
- **Believed: "readable without engram".** The "on disk: plain files" box looked like something I could open in Notepad. That's reassuring if this project dies.
- **Doubted: "Only what you said".** It checks quotes and numbers. But the technical doc says an answer to Claude's question can be filed in Claude's words. My worst case is Claude suggesting a date and me saying "yeah, around then".
- **Doubted: "Where your data goes".** It's honest that sessions go to Claude, but "remote", "push" and, in the linked doc, "second box" and "ssh host" left me unsure whether anything leaves my laptop besides that. For a medical record, "unsure" is a no.
- **Doubted, and it alarmed me: Evolve "saved by itself".** Something changing my record weekly, by itself, for dollars, is the opposite of what I want from a medical log. I did notice "once you turn it on", and I'd want it off forever.
- **Didn't understand: "just over half the tokens", "SQLite FTS5", "grep", "tuned by the repo's own weights".**
- **Didn't understand whether my existing history can come in.** It says nothing about spreadsheets or Google Docs. "Export to Markdown" is all I got, and I don't know how to turn a 6-year spreadsheet into Markdown in a useful way.

## 6. Exit

Left from the "sources" doc at about the 11-minute mark, after I failed to find anything about spreadsheets. It was getting too technical, with no answer on the two things I need: can my history come in, and does my data go anywhere besides Anthropic. I didn't install it. To start I'd need Claude Code (which I don't have and isn't my chat app), then uv and Python 3.12, and maybe WSL2 on my laptop. Doing all that blind, for my mother's medical data, from a project with no sign of who runs it, is too much. I bookmarked it and wrote down "ask Dev (colleague who writes scripts) about Claude Code". No star, because I don't really know what starring does.

## 7. In your own words

"Found a thing that does exactly what I've been wanting: it only saves dates you actually said, and if you correct something it keeps both versions instead of making stuff up. But it's really for programmers. You need Claude Code, not the normal Claude app, plus a bunch of installing. I couldn't tell if my spreadsheet could go in, or where 'push' sends everything. I've bookmarked it and I'll ask Dev to look at it with me."

## 8. What would have kept / convinced me

- One example that's like my life, not a garden: "Mum's dizziness started in March, I said 'early spring' → filed as 2024, not-sure month", or "I corrected the metoprolol dose → both versions come back". Made up is fine.
- A plain "Your data" box near the top, in yes/no form. Leaves your computer: only to Anthropic, the same as any Claude chat. GitHub: only if you set it up, and it's off by default. Second computer: no, unless you set it up. Costs: your Claude subscription only.
- A straight answer on what happens when Claude suggests the date and I agree. Is that "my words" or not?
- "Bring your spreadsheet: here's how". Even "save as CSV, then run this one command", or "not supported yet". Don't make me hunt through the docs for it.
- Tell me what I'd need before I start: "You need Claude Code (what it is, what it costs, link)". Put that next to "Not the Claude app", not in the Quickstart.
- Say that "Evolve" is off unless I turn it on, and that I can leave it off forever, in words a non-programmer reads as "nothing changes your record without you".
- Show the year on the corrections picture ("Jul 2024 → Jun 2024"), and say who "the owner" is ("you").
