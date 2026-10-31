# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools>=4.47"]
# ///
"""brand.py <dir>: writes banner.svg and logo.svg. Run with `uv run`, which brings fontTools.

The banner's brain is seen from the front, two hemispheres, drawn only in characters: fixed rows of the record's own
characters (short names, dates, link rels) fills the brain's shape, its outline traced from a brain icon. Rain
runs through it right to left, the way code falls in the Matrix: a highlight with a white head and a tail that cools
through orange back to rest, and each character changes as a head passes over it. An engram is the trace a memory leaves in the brain. One
file serves both themes: it's a dark card, like a terminal.

How it moves with CSS alone: each half-row is two texts at the same place, glyph A and glyph B. Its characters are
spaced (textLength) to run exactly from the fissure to the outline rather than snapping to a grid, so the outline's
lobes come through though a character is wider than they are deep. Over a cycle of two passes, A shows from one head
to the next and B from that head to the one after, each lit by the head that brings it in. A cell's delay is its
row's offset plus its place from the right (`nth-last-child`, and for the left half the right half's cells and the
fissure's) times the row's step, so the highlight sweeps right to left across both hemispheres.

The words beside it are traced into shapes, since an <img> SVG can't load a font: the name in Doto, a dot-matrix face,
and the rest in JetBrains Mono, both SIL Open Font License, fetched once from google/fonts at a pinned commit.
"""
import hashlib
import random
import sys
import urllib.request
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

W, H = 960, 280
FONT = 9                    # px
CW, RH = 5.4, 6.9           # px a character takes, about, and per row
CX = 200                    # the midline
TOP, BOTTOM = 14, 266        # the brain's top and bottom
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
FONTS = "https://raw.githubusercontent.com/google/fonts/6c1dbe27dcf7d817d4b62cec033ba77fa8e2a5ec/ofl/"
DOTO = ("doto/Doto%5BROND,wght%5D.ttf", "6f4fe7d37853b91df3698daa84cde2dbe1c9695d88c986e6510134910337d426")
JETBRAINS = ("jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf", "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda")

ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # the short-name alphabet: no 0, o, 1, l or i
WORDS = ["led-to", "revises", "supersedes", "story", "20261012", "kept", "who:me", "north", "events", "now:", "doc-k7f2",
         "2026-04-12", "said", "thread", "keep", "find", "rewire", "evolve"]
HEAD, BRIGHT, WARM = "#fff4e4", "#ffc477", "#ff7a1a"
REST = "#9a4416"                            # a character the rain isn't passing
SPEEDS = [(3.2, .032), (3.9, .038), (4.6, .035), (5.4, .044)]  # (seconds a pass, seconds a column)


# One hemisphere's outline, traced from a reference drawing of a brain icon: (distance from the midline, depth from
# the top) in a drawing 371 px tall. The fissure is the gap the outline leaves at the midline; the other
# hemisphere mirrors this one.
OUTLINE = [(6, 190), (6, 194), (6, 199), (6, 204), (6, 209), (6, 214), (6, 220), (6, 225), (6, 231), (6, 238),
           (6, 245), (6, 253), (6, 262), (6, 272), (6, 284), (6, 298), (6, 314), (6, 336), (11, 352), (19, 362),
           (30, 368), (41, 372), (54, 372), (66, 369), (78, 363), (88, 354), (98, 342), (107, 340), (116, 335),
           (124, 328), (131, 319), (136, 308), (143, 303), (150, 298), (156, 292), (160, 284), (164, 277),
           (167, 269), (169, 260), (169, 251), (169, 243), (167, 234), (165, 226), (168, 221), (170, 215),
           (171, 208), (172, 202), (172, 196), (170, 190), (169, 184), (166, 178), (165, 172), (167, 166),
           (168, 159), (166, 153), (164, 147), (162, 141), (158, 136), (155, 130), (155, 122), (154, 113),
           (151, 106), (146, 100), (141, 94), (135, 90), (132, 79), (129, 65), (124, 54), (116, 46), (107, 40),
           (98, 36), (88, 34), (78, 19), (66, 7), (53, 2), (40, 0), (28, 3), (17, 10), (8, 22), (6, 44), (6, 65),
           (6, 82), (6, 96), (6, 108), (6, 118), (6, 127), (6, 135), (6, 142), (6, 148), (6, 154), (6, 160),
           (6, 165), (6, 171), (6, 176), (6, 180), (6, 185)]
DRAWN_HEIGHT = 371
SCALE = (BOTTOM - TOP) / DRAWN_HEIGHT


def span(y):
    """Where the right hemisphere's row at y runs, in px from the midline: (fissure side, outline side), or None."""
    dy = (y - TOP) / SCALE
    xs = [ax + (dy - ay) * (bx - ax) / (by - ay)
          for (ax, ay), (bx, by) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]) if (ay > dy) != (by > dy)]
    return (min(xs) * SCALE, max(xs) * SCALE) if len(xs) >= 2 else None


def cells():
    """Rows of (y, inner, outer, n): each row's half from the fissure (inner, px from the midline) to the outline
    (outer), and how many characters fill it, each a little wider or narrower than a column to fit exactly."""
    rows = []
    y = TOP + RH / 2
    while y < BOTTOM:
        if (sp := span(y)) and (n := round((sp[1] - sp[0]) / CW)) >= 1:
            rows.append((y, sp[0], sp[1], n))
        y += RH
    return rows


class Face:
    """A font at one instance, traced: each glyph is a path in <defs> once, and text is <use>s of them."""

    def __init__(self, src, axes, key):
        path, digest = src
        cache = Path.home() / ".cache" / "engram-art" / digest
        if not cache.exists():
            data = urllib.request.urlopen(FONTS + path).read()
            if hashlib.sha256(data).hexdigest() != digest:
                sys.exit(f"brand.py: {path} doesn't match its pinned checksum")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        self.font = instantiateVariableFont(TTFont(cache), axes)
        self.glyphs, self.cmap, self.key, self.defs = self.font.getGlyphSet(), self.font.getBestCmap(), key, {}

    def ink(self, ch):
        pen = BoundsPen(self.glyphs)
        self.glyphs[self.cmap[ord(ch)]].draw(pen)
        return pen.bounds  # (xMin, yMin, xMax, yMax) in font units, or None for a space

    def width(self, text, size):
        return sum(self.glyphs[self.cmap[ord(c)]].width for c in text) * size / self.font["head"].unitsPerEm

    def text(self, text, x, y, size, cls="", whole=False):
        """Text with its first glyph's ink starting at x, on the baseline y. Whole, it's one path in the card's
        coordinates, so a gradient runs across the word rather than restarting in each glyph."""
        k = size / self.font["head"].unitsPerEm
        x -= (self.ink(text[0]) or (0,))[0] * k
        out, pen = [], SVGPathPen(None, ntos=lambda v: f"{v:.1f}".removesuffix(".0"))
        for c in text:
            name = self.cmap[ord(c)]
            if whole:
                self.glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
            elif self.ink(c):
                gid = f"{self.key}{self.font.getGlyphID(name)}"
                if gid not in self.defs:
                    pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
                    self.glyphs[name].draw(pen)
                    self.defs[gid] = f'<path id="{gid}" d="{pen.getCommands()}"/>'
                out.append(f'<use href="#{gid}" transform="matrix({k:.4f} 0 0 {-k:.4f} {x:.1f} {y:.1f})"/>')
            x += self.glyphs[name].width * k
        if whole:
            return f'<path class="{cls}" d="{pen.getCommands()}"/>'
        return f'<g class="{cls}">{"".join(out)}</g>' if cls else "".join(out)


def words():
    """The name, tagline and jobs, traced, beside the brain: (defs, body). The block centres on the card."""
    doto = Face(DOTO, {"wght": 900, "ROND": 0}, "d")
    mono, bold = Face(JETBRAINS, {"wght": 400}, "j"), Face(JETBRAINS, {"wght": 600}, "b")
    x, name = 422, "engram"
    size = 290 / doto.width(name, 1)  # the name 290 px wide
    k = size / doto.font["head"].unitsPerEm
    top, low = max(doto.ink(c)[3] for c in name) * k, -min(doto.ink(c)[1] for c in name) * k  # x-height, the g's tail
    block = top + low + 22 + 28 + 40 + 4  # the name, a gap to the tagline's baseline, its second line, the jobs
    base = H / 2 - block / 2 + top
    t1, t2, jobs = base + low + 22, base + low + 50, base + low + 90
    body = [doto.text(name, x, base, size, "wm", whole=True),
            mono.text("Bring your knowledge base, or start fresh.", x, t1, 17, "tag"),
            mono.text("Recall every thread and aside, in fewer tokens.", x, t2, 17, "tag")]
    for w in ["keep", "find", "rewire", "evolve"]:  # a menu of the four jobs, like a terminal's
        body.append(bold.text("›", x, jobs, 15, "pr"))
        body.append(bold.text(w, x + bold.width("› ", 15), jobs, 15, "job"))
        x += bold.width(f"› {w}", 15) + 22
    defs = "".join(d for f in (doto, mono, bold) for d in f.defs.values())
    gradient = ('<linearGradient id="wm" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffc46b"/>'
                '<stop offset=".5" stop-color="#ff8a2a"/><stop offset="1" stop-color="#e8590c"/></linearGradient>')
    return defs + gradient, "\n".join(body)


def keyframes(k, period, step, a):
    """One glyph of a cell over a cycle of two passes: the head at 0% (B's) or 50% (A's), then the tail cooling to
    rest, hidden while the other glyph shows."""
    C = 2 * period
    p = lambda t, base=0.0: f"{base + t / C * 100:.2f}%"
    base = 50.0 if a else 0.0
    # in steps: one cell of white head, a few bright, then the tail cooling over about fifteen cells
    lit = (f"{p(0, base)}{{fill:{HEAD}}}{p(step, base)}{{fill:{HEAD}}}{p(2 * step, base)}{{fill:{BRIGHT}}}"
           f"{p(5 * step, base)}{{fill:{WARM}}}")
    if a:
        return f"@keyframes {k}{{0%,49.99%{{fill:transparent}}{lit}{p(17 * step, base)},100%{{fill:{REST}}}}}"
    return f"@keyframes {k}{{{lit}{p(17 * step)},49.99%{{fill:{REST}}}50%,100%{{fill:transparent}}}}"


def banner():
    rng = random.Random(1012)
    rows = cells()
    css = []
    for s, (period, step) in enumerate(SPEEDS):
        for g in "ab":
            css.append(keyframes(f"{g}{s}", period, step, g == "a"))
            css.append(f".{g}{s}{{--s:{step}s}}.{g}{s} a{{animation:{g}{s} {2 * period}s linear infinite}}")
    css.append("".join(f".g a:nth-last-child({i + 1}){{--c:{i}}}" for i in range(max(n for *_, n in rows))))
    body = []
    for y, inner, outer, n in rows:
        s = rng.randrange(len(SPEEDS))
        period, step = SPEEDS[s]
        off = -rng.uniform(0, 2 * period) - 2 * period
        stream, a_glyphs = "", []
        for _ in range(2 * n):  # the record's words run through the rows now and then, like a strand of code
            if not stream:
                stream = rng.choice(WORDS) if rng.random() < 0.08 else rng.choice(ALPHABET)
            a_glyphs.append(stream[0])
            stream = stream[1:]
        b_glyphs = [rng.choice(ALPHABET) for _ in range(2 * n)]
        width, ty = outer - inner, y + FONT * 0.36
        # the left half lights after the right half's cells and the fissure's width have passed
        halves = ((CX - outer, off + (n + 2 * inner / (width / n)) * step, slice(0, n)), (CX + inner, off, slice(n, 2 * n)))
        for x, o, part in halves:
            for g, glyphs in (("a", a_glyphs), ("b", b_glyphs)):
                runs = "".join(f"<a>{ch}</a>" for ch in glyphs[part])  # a text run, the shortest one SVG has
                body.append(f'<text x="{x:.1f}" y="{ty:.1f}" textLength="{width:.1f}" lengthAdjust="spacing" '
                            f'class="{g}{s}" style="--o:{o:.2f}s">{runs}</text>')
    defs, words_body = words()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="engram: Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens. A brain seen from the front, two hemispheres drawn in orange characters, with rain running through them right to left.">
<title>engram</title>
<defs>
<radialGradient id="bg" cx=".2" cy=".5" r=".85"><stop offset="0" stop-color="#1c1109"/><stop offset=".6" stop-color="#100d0c"/><stop offset="1" stop-color="#0d1117"/></radialGradient>
{defs}
</defs>
<style>
.g text{{font:700 {FONT}px {MONO};white-space:pre}}
.g [class^=a] a{{fill:{REST}}}.g [class^=b] a{{fill:transparent}}
{"".join(css)}
.g text a{{animation-delay:calc(var(--o) + var(--c) * var(--s))}}
.wm{{fill:url(#wm)}}.tag{{fill:#f0e6dc}}.pr{{fill:#7a4a26}}.job{{fill:#ffb35a}}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}
</style>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="url(#bg)"/>
<g class="g">
{chr(10).join(body)}
</g>
{words_body}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="#3a2a20" stroke-width="1.5"/>
</svg>
'''


def logo():
    """The mark: the two hemispheres as a grid of dots, a few lit as heads of the rain."""
    rng = random.Random(4)
    s, mid, dots = 42 / (BOTTOM - TOP), (TOP + BOTTOM) / 2, []
    for y in (TOP + 11.5 + 27.6 * k for k in range(9)):  # its own rows, whatever the banner's font
        outer = span(y)[1]
        d = 3.4  # the first dot's distance from the midline, in the mark's px, so the fissure shows
        while d <= outer * s + 0.6:
            for x in (30 + d, 30 - d):
                fill = HEAD if rng.random() < 0.08 else WARM
                dots.append(f'<circle cx="{x:.1f}" cy="{(y - mid) * s + 22:.1f}" r="1.5" fill="{fill}"/>')
            d += 4.6
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 44" width="60" height="44" role="img" '
            f'aria-label="engram">{"".join(dots)}</svg>\n')


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
    (out / "banner.svg").write_text(banner())
    (out / "logo.svg").write_text(logo())
