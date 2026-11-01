# README art

Every SVG in `docs/assets/` is written by a script here: edit the script, never the SVG. `diagrams.py` is Python's standard library only; `brand.py` also needs fontTools, which `uv run` brings.

| Script | Writes | Run |
|---|---|---|
| `brand.py` | `banner.svg` (one dark card for both themes), `logo.svg` | `uv run docs/assets/gen/brand.py docs/assets` |
| `diagrams.py` | `<name>-dark.svg` and `<name>-light.svg` for `loop`, `filer`, `versions`, `rewire`, `evolve`, `record` and `arch` | `python3 docs/assets/gen/diagrams.py docs/assets` |
| `frames.mjs` | PNG frames of an SVG, to check it by eye | `node docs/assets/gen/frames.mjs <svg> <outprefix> [dark\|light] [times] [reduce]` |

- **What GitHub allows:** a README shows an SVG through `<img>`, so no script, no external fonts or files, and no SMIL. Motion is CSS `@keyframes` only; a dot moving along an edge uses `offset-path`.
- **Themes:** an `<img>` SVG can't see GitHub's theme, so each diagram ships as two files switched by `<picture>` in the README. One source holds both palettes as CSS custom properties on the root, and the light file differs only in the root's class.
- **Motion off is a whole picture:** an element's own style is its shown state, and the keyframes only hide it before its moment, so `prefers-reduced-motion` shows everything, final.
- **Words:** plain words, addressed to you, true to the docs. A record is a placeholder (`[fact]`, `[thing]`) unless the example needs real text, and then it's the made-up garden in `examples/notes/`; nothing personal.
- **The banner:** a brain seen from the front, its outline traced from a brain icon (one hemisphere's points in `OUTLINE`, mirrored for the other), drawn only in 9 px characters. Each half-row's characters are spaced (`textLength`) to run exactly from the fissure to the outline, so the outline's lobes show though a character is wider than they are deep. Rain is a highlight sweeping each row right to left across both halves, a white head and a tail cooling to rest, and every character changes as a head passes: each cell is two stacked glyphs that take turns, one per pass, and a cell's delay comes from its place from the right (`nth-last-child`). The words beside it are traced into shapes, since an `<img>` SVG can't load a font: the name in Doto (dot matrix), the rest in JetBrains Mono, both SIL Open Font License, fetched once from google/fonts at a pinned commit and checked against their checksums.
- **Palette:** orange is engram's; green filed, red dropped, amber narrowed.

| role | dark | light |
|---|---|---|
| text | `#e6edf3` | `#1f2328` |
| muted | `#8b949e` | `#59636e` |
| panel | `#161b22` / `#30363d` | `#f6f8fa` / `#d0d7de` |
| orange | `#ff8a2a` | `#c2410c` |
| filed | `#3fb950` | `#1a7f37` |
| dropped | `#f85149` | `#cf222e` |
| narrowed | `#d29922` | `#9a6700` |

Check a change by rendering frames (frames freeze CSS animation at t seconds; `frames.mjs` needs Playwright with a Chromium) in both themes, mid-animation and with `reduce`, and look for overlap and clipping.
