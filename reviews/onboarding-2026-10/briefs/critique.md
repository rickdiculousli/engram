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
  the real view. Mid-animation frames: `<run>/frames/loop-{0,2,4,6,9}.png`,
  `filer-{0,3}.png`, `ver-{0,3}.png` (seconds). Judge the diagrams from those. (It's still fair to
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

---

## The three lenses (each critic got this brief, then one block; examples from this run trimmed)

### Structure and order (file: critic-structure.md)
Question to answer: does the README's section order, and the order inside each section, match what each should-win persona needs and when they need it? Cover:
- the top of the page (banner → badges → nav → opening line → bullets → four jobs → loop diagram): what each persona needs in their first 10 seconds and whether they get it, including who-it's-for and which Claude (Claude Code vs the app);
- the four-job spine (Keep / Find / Rewire / Evolve): does it carry the value, or is it the builder's mental model? Where do "bring your knowledge base" (existing notes or vault), privacy and data location, and setup cost belong?
- the lower half (What a record is made of, Architecture, Not goals, Quickstart, Docs): order, and what's redundant or misplaced;
- the Docs list: is "Start here" pointing at the right docs, in the right order?
End with a proposed section outline for the README (headings with a one-line purpose each), noting what moves, merges or goes.

### Value and wording (file: critic-value.md)
Question to answer: is the win stated in each should-win persona's own terms, and do the claims land? Cover:
- **Jargon audit:** every README term that lost at least one persona (record, repo/area/domain, knowledge graph, threads, typed links, `led-to`/`revises`, tokens, grep, pack, schema-checked store, rewire, refine, ingest, filer…). For each: who it lost, whether it's needed at that spot, and a plain replacement or a cut. Respect the owner's style (fragments, arrows, "you"; no punchy shorthand that confuses newcomers).
- **Claims:** "fewer tokens than grep", "thorough", "relational", "never touches your record" vs the Evolve diagram's "saved by itself", "Bring your knowledge base". Which are backed, unbacked, or contradicted by the repo itself? For an unbacked claim, propose either evidence that exists in the repo (find it) or softer, true wording. Check the product behaviour personas 4, 6 and 7 hit when running the Quickstart (a plain Markdown vault gets only search; the stale "basil bolted in July" document row under its correction; example sessions ingesting 0) and say how the README should state what's true.
- **The value moments** that worked (the filer table, corrections kept, the versions diagram): how to bring them earlier or say them in the reader's terms, without adding length.
- **Leaks that make it read as one person's medical tool** (persona 6's list). Verify each in the repo, quote it with file:line, and say whether it also breaks the repo rule "the owner is never named, and areas appear only generically".
End with rewritten text for: the opening line + bullets, and the four job lines (fit the owner's style; say what each rewrite removes).

### Paths and drop-offs (file: critic-paths.md)
Question to answer: for each persona, where exactly did the journey end, and what is the smallest change (a link, a line, a reorder, a cut) that would have either kept them or routed them out fast and kindly? Cover:
- a drop-off table: persona → last thing seen → why they left → should-win or route-out → smallest fix;
- **the README → docs handoff:** walk every link in the README yourself (anchors included) and check it lands where its label promises. Check what each linked doc's opening screen says to a newcomer;
- **the Quickstart path:** run it yourself in a scratch clone (with `XDG_CONFIG_HOME` and `ENGRAM_DATA` inside that dir). Note friction and the gap between demo and "now do it with your own notes": is there a next step after the demo?
- **the missing paths personas went looking for:** existing notes or vault → engram; "which Claude does this need"; "where does my data go"; "show me the numbers". For each, does an answer exist anywhere in the repo? If so, where, and how should the README point to it in one line? If not, say so plainly (that's a product gap, not a README fix).
