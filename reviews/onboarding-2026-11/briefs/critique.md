# Phase 2 brief (shared by the three critic agents)

Seven persona agents each walked the GitHub repo `rickdiculousli/engram` cold, in character,
and logged it. Your job: pick apart the repo's **structure, order and presentation of value**
for those seven people, through one lens (given in your prompt).

## Inputs
- Persona logs: `<run>/log-1.md` … `<run>/log-7.md`. Read all seven first. Personas:
  1 curious newcomer (no KB, no terminal, Claude app) · 2 notes-app pile (Apple Notes/Keep,
  can paste a command) · 3 content Obsidian user (light tech, avoids git) · 4 Obsidian power
  user (dev, Claude Code daily, wants numbers vs grep) · 5 record keeper (health/finance
  history, privacy, mid tech) · 6 custom-KB builder (staff engineer, RAG, reads docs deeply) ·
  7 agent-memory evaluator (ML engineer comparing mem0/Letta/Zep).
- README as GitHub renders it: `<run>/readme-00-repo-top.png`, `<run>/readme-01.png`…`<run>/readme-05.png`
  (the serif font is a capture artifact; ignore it).
- **Animated diagrams:** the loop, filer and versions diagrams animate on GitHub; the screenshots
  caught empty first frames. Several personas reported "empty boxes": that's capture timing, not
  the real view. Frames over time: `<run>/frames/{loop,filer,ver}-{0,2,4,6,9}.png` (seconds). Judge the diagrams from those. (It's still fair to
  note what a reader sees in the first second, but not to call the diagrams broken.)
- The repo itself at `<repo>` (README.md, docs/, examples/, skills/, bench/, src/).
  Read-only. Ignore `.engram/`, `local/`, `__pycache__`.

## Ground rules
- The persona logs are evidence, not verdicts. A persona agent may have misread something the
  repo does say; check the repo before blaming it, and say when a persona was wrong.
  Equally, look past the logs: walk the README and the docs it links yourself.
- Not every persona is the audience. Say which personas engram *should* win, which it should
  just *route quickly* (a clear "not for you yet" is a success), and judge against that.
  engram is honest about being one person's Claude Code tool with plain-git records; don't
  recommend turning it into a web app or multi-user product (those are stated non-goals).
- The owner's style for README prose: active, casual, addresses "you"; cut before adding;
  fragments over full sentences; lists, tables, arrows; value to the reader, not step-by-step
  mechanics (except in a how-it-works section); no heavy nominalization; no punchy shorthand
  that confuses a newcomer. Diagrams: placeholders not example text, show don't tell.
  Repo rule: every change removes at least as much as it adds, or says why not.
- Concrete beats general. Every finding names the exact line/section/file, quotes it, and
  proposes the specific change (a rewrite, a move, a cut, a link), with what it removes.

## Write to `<run>/critic-<lens>.md`
- **Verdict (3–5 lines):** how well the repo serves its should-win personas through your lens.
- **Findings, ranked by impact:** for each: title · personas hurt (numbers) · evidence (quotes
  from logs and repo, with locations) · proposed change (exact) · what it cuts · confidence.
- **Persona errors:** places a persona misjudged the repo.
- **Keep:** what already works and must not be lost in a revision.

Final reply: the path and your top 5 findings in one line each.

## This is round 2
The first round ran on an earlier README; the owner has since made fixes. Its summary is
`<repo>/reviews/onboarding-2026-10/README.md` (ranked findings 1–8) and its critiques are in
`<repo>/reviews/onboarding-2026-10/critiques/`. Read the summary and the round-1 critique for
your lens after the new logs. Add a section **Round 1 → now** to your file: for each round-1 finding
your lens covers, say *fixed / partly / not / regressed*, with evidence from the new logs and the repo.
Then call out anything the fixes introduced (new claims to check, new jargon, new length: the repo
rule is that every change removes at least as much as it adds). Rank new findings as before.

---

## The three lenses, round 2 (each critic got this brief, then one block; trimmed)

- **Structure and order:** does section order, and order inside each section, match what each should-win persona needs and when? The top of the page now (opening line → For line → bullets → jobs); the four-job spine and where "Have notes already?", Obsidian, privacy and setup cost sit (round-2 personas found the notes answer under "Rewire"); the lower half and Docs. End with an outline, compared with round 1's.
- **Value and wording:** jargon that lost a round-2 persona; the measured grep claim against its source's caveats, "Bring your knowledge base" vs what a plain vault gets, the Evolve rule, the "On hold" Obsidian line, and the output snags personas hit, each verified; value moments in the reader's terms; one-person or medical leaks left in public docs and help, with file:line. End with rewrites of the opening line, For line, bullets and job lines.
- **Paths and drop-offs:** where each journey ended vs round 1, and the smallest fix; a true, kind next step for readers routed out; every README link walked; the Quickstart run, then the README's "your own notes" path on a folder outside git and on a small git repo, "drop `--domain`" included; the missing paths (Apple Notes/Keep/spreadsheets, Obsidian, where data goes, the numbers, use from an agent), each answered from the repo or named a product gap.
