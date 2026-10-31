"""diagrams.py <dir>: writes the README's diagrams, each as <name>-dark.svg and <name>-light.svg.

One source per diagram, both palettes as CSS custom properties on the root; the light file differs only in the
root's class. Every label is true to the README and the docs; a record is a placeholder ([fact], [thing]) or
the made-up garden in examples/notes. Motion is CSS only (GitHub shows an SVG through <img>: no script, no SMIL), and with motion off
each picture is complete, in its final state.
"""
import sys
from pathlib import Path

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
CSS = f"""
svg{{--fg:#e6edf3;--mu:#8b949e;--pf:#161b22;--ps:#30363d;--ed:#4a5260;--or:#ff8a2a;--or2:#ffb35a;--ort:rgba(255,138,42,.13);--ok:#3fb950;--rd:#f85149;--am:#d29922}}
svg.light{{--fg:#1f2328;--mu:#59636e;--pf:#f6f8fa;--ps:#d0d7de;--ed:#afb8c1;--or:#c2410c;--or2:#e8590c;--ort:rgba(232,89,12,.09);--ok:#1a7f37;--rd:#cf222e;--am:#9a6700}}
text{{fill:var(--fg);font-family:{SANS};font-size:14px}}
.m{{font-family:{MONO};font-size:13px}}.s{{font-size:13px}}.t{{font-size:17px;font-weight:600}}.b{{font-weight:600}}
.mu{{fill:var(--mu)}}.or{{fill:var(--or)}}.ok{{fill:var(--ok)}}.rd{{fill:var(--rd)}}.am{{fill:var(--am)}}
.pn{{fill:var(--pf);stroke:var(--ps);stroke-width:1.5}}.po{{fill:var(--ort);stroke:var(--or);stroke-width:1.5}}
.ln{{fill:none;stroke:var(--ed);stroke-width:1.5}}.lo{{fill:none;stroke:var(--or);stroke-width:1.5}}.dash{{stroke-dasharray:4 5}}
.ar{{marker-end:url(#ah)}}.aro{{marker-end:url(#aho)}}#ah path{{fill:var(--ed)}}#aho path{{fill:var(--or)}}
.chip{{fill:var(--pf);stroke:var(--or);stroke-width:1.2}}.hl{{fill:var(--ort)}}
.mv{{opacity:0}}.mv .c{{fill:var(--or)}}.mv .g{{fill:var(--or);opacity:.3}}
.nd{{fill:var(--or)}}.nl{{fill:var(--fg)}}.nb{{fill:var(--ed);stroke:var(--mu);stroke-width:1.5}}.strike{{stroke:var(--rd);stroke-width:1.5}}
@supports not (offset-path:path('M0 0')){{.mv{{display:none}}}}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}
"""
DEFS = ('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0L10 5L0 10z"/></marker><marker id="aho" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def T(x, y, s, cls="", anchor="", raw=False):
    a = f' text-anchor="{anchor}"' if anchor else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x}" y="{y}"{c}{a}>{s if raw else esc(s)}</text>'


def R(x, y, w, h, cls="pn", rx=10, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{cls}"{extra}/>'


def P(d, cls="ln ar"):
    return f'<path d="{d}" class="{cls}"/>'


def E(x1, y1, x2, y2, r1=6, r2=6, cls="ln"):
    """An edge between two nodes, stopping at each node's rim rather than running to its centre."""
    dx, dy = x2 - x1, y2 - y1
    d = (dx * dx + dy * dy) ** .5 or 1
    a, b = (r1 + .75) / d, (r2 + .75) / d
    return (f'<line x1="{x1 + dx * a:.1f}" y1="{y1 + dy * a:.1f}" x2="{x2 - dx * b:.1f}" y2="{y2 - dy * b:.1f}" '
            f'class="{cls}"/>')


def chip(cx, cy, s):
    w = len(s) * 8.4 + 20
    return R(cx - w / 2, cy - 12, round(w), 24, "chip", 12) + T(cx, cy + 5, s, "m or b", "middle")


class Anim:
    """Keyframes for one loop of `period` seconds. An element's own style is its shown state; the keyframes only
    hide it before its moment, so with motion off the picture is whole."""

    def __init__(self, period):
        self.T, self.css, self.n = period, [], 0

    def p(self, t):
        return f"{max(0.0, min(100.0, t / self.T * 100)):.2f}%"

    def _name(self):
        self.n += 1
        return f"k{self.n}"

    def appear(self, t0, dim_at=None):
        """Hidden until t0, shown until the loop's end; with dim_at, it settles at half from then (a dropped row)."""
        k, p = self._name(), self.p
        mid = f"{p(t0 + .35)},{p(dim_at)}{{opacity:1}}{p(dim_at + .35)},{p(self.T - .5)}{{opacity:.45}}" if dim_at \
            else f"{p(t0 + .35)},{p(self.T - .5)}{{opacity:1}}"
        self.css.append(f".{k}{{animation:{k} {self.T}s linear infinite}}"
                        f"@keyframes {k}{{0%,{p(t0)}{{opacity:0}}{mid}100%{{opacity:0}}}}")
        return k

    def flash(self, t0, t1):
        """Shown only from t0 to t1; hidden with motion off, so the still picture holds no passing state."""
        k, p = self._name(), self.p
        self.css.append(f".{k}{{opacity:0;animation:{k} {self.T}s linear infinite}}"
                        f"@keyframes {k}{{0%,{p(t0)}{{opacity:0}}{p(t0 + .2)},{p(t1)}{{opacity:1}}{p(t1 + .25)},100%{{opacity:0}}}}")
        return k

    def move(self, d, t0, t1):
        """A dot along the path d from t0 to t1, seen only while it moves."""
        k, p = self._name(), self.p
        self.css.append(f".{k}{{offset-path:path('{d}');offset-rotate:0deg;animation:{k} {self.T}s ease-in-out infinite}}"
                        f"@keyframes {k}{{0%,{p(t0)}{{offset-distance:0%;opacity:0}}{p(t0 + .08)}{{opacity:1}}"
                        f"{p(t1)}{{offset-distance:100%;opacity:1}}{p(t1 + .25)},100%{{offset-distance:100%;opacity:0}}}}")
        return f'<g class="mv {k}"><circle r="9" class="g"/><circle r="4.5" class="c"/></g>'


def svg(name, w, h, label, body, anim=None):
    extra = "".join(anim.css) if anim else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="dark" '
            f'role="img" aria-label="{esc(label)}">\n<title>{esc(name)}</title>\n{DEFS}\n<style>{CSS}{extra}</style>\n'
            + "\n".join(body) + "\n</svg>\n")


def card(x, y, w, h, title, sub="", cls="pn"):
    out = [R(x, y, w, h, cls), T(x + 16, y + 26, title, "t")]
    if sub:
        out.append(T(x + 16, y + 46, sub, "m mu"))
    return out


# --- the loop: keep and find -------------------------------------------------------------------------------------------

def loop():
    a = Anim(14)
    b = []

    def bubble(x, y, w, who, what, cls, t):
        k = a.appear(t)
        return (f'<g class="{k}">' + R(x, y, w, 34, cls, 10) + T(x + 12, y + 22, f'<tspan class="mu">{who}</tspan> {what}',
                "s", raw=True) + "</g>")

    # a session: you tell it things, and later ask
    b += card(16, 20, 262, 300, "a session")
    b.append(bubble(32, 68, 230, "me:", "[knowledge]", "po", 0.3))
    b.append(T(147, 170, "· · ·  later  · · ·", "s mu", "middle"))
    b.append(bubble(32, 229, 230, "me:", "[question]", "po", 6.2))
    b.append(bubble(32, 272, 230, "claude:", "[answer]", "pn", 11.0))
    # the hourly filer: checks, then writes and pushes the entry
    b += card(350, 20, 594, 130, "hourly filer")
    b.append(T(366, 94, "is knowledge", "s"))
    for i, t in enumerate((2.1, 2.5, 2.9)):
        x = 462 + 24 * i
        b.append(R(x, 80, 18, 18, "pn", 4))
        b.append(T(x + 9, 94, "✓", f"ok b {a.appear(t)}", "middle"))
    b.append(P("M538 89 H580"))
    k = a.appear(3.4)
    b.append(R(586, 74, 130, 30, "pn", 6) + f'<g class="{k}">' + R(586, 74, 130, 30, "po", 6) + "</g>"
             + T(651, 94, "/[latest].md", "m", "middle"))
    b.append(P("M722 89 H764"))
    b.append(T(772, 94, "git commit + push", "s"))
    b.append(T(366, 128, "most sessions file nothing", "s mu"))
    # the index: your records as a graph, the new entry joining it
    b += card(682, 190, 262, 130, "index")
    b.append(T(698, 236, "your records, linked as a graph", "s mu"))
    nodes = {1: (716, 266), 2: (762, 256), 3: (812, 282), 4: (756, 304), 5: (862, 260), 6: (910, 292), 7: (866, 306)}
    for u, v in ((1, 2), (2, 3), (1, 4), (4, 3), (3, 5), (5, 6)):
        b.append(E(*nodes[u], *nodes[v]))
    k = a.appear(5.1)
    b.append(f'<g class="{k}">{E(812, 282, 866, 306)}</g>')
    b += [f'<circle cx="{x}" cy="{y}" r="6" class="pn{f" {k}" if n == 7 else ""}"/>' for n, (x, y) in nodes.items()]
    # the new entry flashes orange as it joins, then is a record like the rest
    b.append(f'<g class="{a.flash(5.1, 5.4)}">{E(812, 282, 866, 306, cls="lo")}'
             f'<circle cx="866" cy="306" r="6" class="po"/></g>')
    # a question lights its match, then what links to it
    b.append(f'<circle cx="812" cy="282" r="6" class="nd {a.appear(8.4)}"/>')
    k = a.appear(8.8)
    b.append(f'<g class="{k}">' + "".join(f'<circle cx="{nodes[n][0]}" cy="{nodes[n][1]}" r="4" class="nl"/>'
                                          for n in (2, 4, 5, 7)) + "</g>")
    # the one call: the match and its links, in time order
    b += card(350, 190, 262, 130, "one call")
    b.append(T(366, 236, "the match + what links to it", "s mu"))
    k = a.appear(9.6)
    rows = (("04", "[linked]", "m"), ("06", "[match]", "m or b"), ("09", "[linked]", "m"), ("10", "[latest]", "m"))
    b.append(f'<g class="{k}">' + "".join(T(366, 257 + 17 * i, d, "m mu") + T(394, 257 + 17 * i, w, c)
                                         for i, (d, w, c) in enumerate(rows))
             + T(596, 285, "time order ↓", "s mu", "end") + "</g>")
    # edges
    e1, e3 = "M278 85 H346", "M813 150 V186"
    e4, ask, ans = "M682 255 H616", "M278 246 H346", "M350 289 H282"
    b += [P(e1), P(e3), P(e4), P(ask), P(ans)]
    b.append(T(823, 173, "ingest", "m mu"))
    b.append(chip(314, 62, "keep"))
    b.append(chip(314, 316, "find"))
    b += [a.move(e1, 1.0, 1.8), a.move(e3, 4.3, 4.9), a.move(ask, 6.8, 7.6),
          a.move("M616 255 H682", 7.8, 8.4), a.move(e4, 9.0, 9.6), a.move(ans, 10.2, 10.9)]
    return svg("engram: keep and find", 960, 340,
               "The loop. Keep: you tell Claude something in a session; the hourly filer checks it is knowledge, "
               "three checks, then writes it as the latest entry and commits and pushes it. The index, your records "
               "linked as a graph, takes it in. Find: you ask a question; one call lights its match in the graph and "
               "what links to it, returns them in time order, and Claude answers from them.", b, a)


# --- the filer's guards ------------------------------------------------------------------------------------------------

def filer():
    a = Anim(17)
    b = []
    b += card(16, 20, 226, 280, "what the owner said", "")
    b.append(R(30, 60, 198, 66, "po", 10))
    b += [T(42, 81, "picked about 3 kg of", "s"), T(42, 98, "Sungold this week, the", "s"),
          T(42, 115, "Brandywine are slow", "s"), T(30, 146, "said on 2026-09-28", "m mu")]
    # a one-hour timer: the filer waits for the session to settle before reading it
    k = a._name()
    a.css.append(f".{k}{{stroke-dasharray:100;animation:{k} {a.T}s linear infinite}}@keyframes {k}{{0%,{a.p(.2)}"
                 f"{{stroke-dashoffset:100}}{a.p(1.8)},{a.p(a.T - .5)}{{stroke-dashoffset:0}}100%{{stroke-dashoffset:100}}}}")
    b += [R(124, 180, 10, 6, "pn", 2), '<circle cx="129" cy="214" r="26" class="ln"/>',
          f'<circle cx="129" cy="214" r="26" pathLength="100" class="lo {k}" style="stroke-width:3" '
          'transform="rotate(-90 129 214)"/>', T(129, 219, "1 hr", "s b", "middle"),
          T(129, 264, "waits until it settles", "s mu", "middle")]
    b.append(T(268, 40, "what the model proposes", "s mu"))
    b.append(T(685, 26, "code guards", "s mu", "middle"))
    cols = (598, 656, 714, 772)
    for x, s in zip(cols, ("quote", "numbers", "date", "repeat")):
        b.append(T(x, 46, s, "s b", "middle"))
    b.append(T(812, 46, "outcome", "s b"))
    rows = [  # text, date, marks (✓, ✗, ~ narrowed, · nothing to check), outcome, its class, dropped
        ("About 3 kg of Sungold picked this week", "2026-09-28", "✓✓✓✓", "filed", "ok", False),
        ("5 kg of Sungold picked", "2026-09-28", "✓✗", "dropped", "rd", True),
        ("Brandywine slow to ripen", "2026-09-21", "✓·~✓", "filed, 2026-09", "am", False),
        ("Brandywine and Sungold in the north bed", "2026-09-28", "✓·✓✗", "dropped:", "rd", True),
    ]
    for i, (s, d, marks, out, oc, dropped) in enumerate(rows):
        y, t0 = 62 + 62 * i, 2.0 + 3.4 * i
        end = t0 + 0.5 + 0.4 * len(marks) + 0.4
        k = a.appear(t0, dim_at=end + .3 if dropped else None)
        g = [R(258, y, 312, 50, "pn", 8), T(272, y + 21, s, "s"), T(272, y + 40, f"date {d}", "m mu")]
        if dropped:
            g.append(f'<path d="M270 {y + 17} H{272 + len(s) * 6.6:.0f}" class="strike"/>')
        b.append(f'<g class="{k}">' + "".join(g) + "</g>")
        b.append(R(576, y, 368, 50, "pn", 8, ' style="fill:none"'))
        for j, m in enumerate(marks):
            cls = {"✓": "ok", "✗": "rd", "~": "am", "·": "mu"}[m]
            k = a.appear(t0 + 0.5 + 0.4 * j)
            b.append(T(cols[j], y + 31, m, f"b {cls} {k}", "middle").replace("<text", '<text style="font-size:18px"'))
        k = a.appear(end)
        b.append(f'<g class="{k}">' + T(812, y + 22, out, f"s b {oc}")
                 + (T(812, y + 40, "repeats p8qdad", "m mu") if out == "dropped:" else
                    T(812, y + 40, "not in their words", "s mu") if dropped else
                    T(812, y + 40, "a day nobody said", "s mu") if oc == "am" else T(812, y + 40, "committed, pushed", "s mu"))
                 + "</g>")
    return svg("engram: the filer's guards", 960, 320,
               "The hourly filer waits an hour for a session to settle, then files from one message, 'picked about 3 kg of Sungold this week, the Brandywine "
               "are slow', said on 2026-09-28. The model proposes four facts and code checks each: the quote is in the "
               "owner's words, every number is theirs, the date is one they gave, and it isn't a repeat. 'About 3 kg of "
               "Sungold picked this week' passes and is filed. '5 kg of Sungold picked' is dropped: 5 isn't in their "
               "words. 'Brandywine slow to ripen' dated 2026-09-21 is filed with its date narrowed to 2026-09. "
               "'Brandywine and Sungold in the north bed' is dropped as a repeat of an entry already filed.", b, a)


# --- a fact and its corrections ----------------------------------------------------------------------------------------

def N(x, y, r=5, cls="pn"):
    return f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" class="{cls}"/>'


def G(k, *parts):
    """Parts shown together from one keyframe."""
    return f'<g class="{k}">' + "".join(parts) + "</g>"


def versions():
    a = Anim(8)
    b = []
    b += card(16, 20, 420, 210, "in the record")
    b.append(G(a.appear(0.3), R(40, 66, 372, 44, "pn", 8), T(56, 93, "[fact]", "s"), T(396, 93, "07", "m mu", "end")))
    b.append(G(a.appear(1.0), R(40, 162, 372, 44, "po", 8), T(56, 189, "[correction]", "s"), T(396, 189, "06", "m or", "end"),
               P("M96 160 V114", "lo aro"), T(108, 142, "revises", "m or")))
    search = "M440 125 H500"
    b += [P(search), T(470, 115, "search", "s mu", "middle"), a.move(search, 1.7, 2.3)]
    b += card(504, 20, 440, 210, "one result")
    b.append(T(520, 66, 'engram search "[question]"', "m mu"))
    b.append(G(a.appear(2.5), R(520, 86, 408, 44, "po", 8), T(536, 113, "[correction]", "s b"),
               T(912, 113, "06", "m or", "end")))
    b.append(G(a.appear(2.9), T(536, 158, "07", "m mu"), T(564, 158, "[fact]", "m mu"), T(624, 158, "→ corrected", "s mu")))
    b.append(G(a.appear(3.3), T(520, 206, "nothing erased · every version kept", "s mu")))
    return svg("engram: a fact and its corrections", 960, 250,
               "In the record: a fact dated July, and a correction dated June with a revises link to it. One search "
               "returns them as one result: the correction in full, and the July version on one line marked corrected. "
               "Nothing is erased; every version is kept.", b, a)


# --- rewire ------------------------------------------------------------------------------------------------------------

def rewire():
    import random
    b = []
    # the repo as it is: a tangle
    b += card(16, 20, 220, 260, "your repo", "as it is")
    rng = random.Random(7)
    pts = [(40 + rng.random() * 170, 90 + rng.random() * 170) for _ in range(13)]
    for _ in range(14):
        (x1, y1), (x2, y2) = rng.sample(pts, 2)
        b.append(E(x1, y1, x2, y2, 5, 5))
    b += [N(x, y) for x, y in pts]
    b.append(P("M236 150 H268"))
    # what you want it to do, and the shape that does it
    b.append(T(276, 40, "what you want this repo to do", "s mu"))
    b.append(T(560, 40, "rewired around them", "s mu"))
    shapes = []
    # follow each [thing]: a page per name, spokes to its records
    y = 87
    shapes.append([E(nx, ny, ex, y, 5, 0) for nx, ny, ex in ((584, y - 18, 612), (584, y + 18, 612), (696, y - 18, 668),
                                                             (696, y + 18, 668))]
                  + [R(612, y - 12, 56, 24, "pn", 12), R(612, y - 12, 56, 24, "po", 12), T(640, y + 5, "[thing]", "m or", "middle")]
                  + [N(584, y - 18), N(584, y + 18), N(696, y - 18), N(696, y + 18)]
                  + [T(928, y + 5, "a page per name", "s", "end")])
    # keep what happened: entries on a thread
    y = 167
    shapes.append([E(584 + 32 * k, y, 616 + 32 * k, y, 5, 5) for k in range(5)] + [N(584 + 32 * k, y) for k in range(6)]
                  + [P(f"M750 {y} H770", "lo aro"), T(928, y + 5, "entries on a thread", "s", "end")])
    # sort by [category]: a group per category
    y = 247
    g = []
    for gx in (576, 692):
        g += [f'<rect x="{gx}" y="{y - 20}" width="104" height="44" rx="10" class="ln dash"/>',
              R(gx + 4, y - 30, 96, 20, "pn", 10), R(gx + 4, y - 30, 96, 20, "po", 10),
              T(gx + 52, y - 16, "[category]", "m or", "middle")]
        g += [N(gx + 28 + 24 * k, y + 8) for k in range(3)]
    shapes.append(g + [T(928, y + 5, "one per category", "s", "end")])
    for i, (job, parts) in enumerate(zip(("follow each [thing]", "keep what happened", "sort by [category]"), shapes)):
        y = 58 + 80 * i
        b += [R(276, y, 230, 44, "pn", 10), T(292, y + 27, job, "s b"), P(f"M506 {y + 22} H552"),
              R(560, y - 4, 384, 66, "pn", 10), *parts]
    b.append(T(560, 306, "kept in .engram/engram.toml · drift refused at commit", "s mu"))
    return svg("engram: rewiring a repo", 960, 320,
               "Rewiring: a repo starts as a tangle of records. What you want it to do decides its shape: follow each "
               "thing becomes a page per name with spokes to its records; keep what happened becomes entries on a "
               "thread; sort by category becomes a group per category. The shape is kept in .engram/engram.toml, and "
               "a commit that drifts from it is refused.", b)


# --- evolve ------------------------------------------------------------------------------------------------------------

def evolve():
    b = []
    hubs = {"A": (66, 76), "B": (164, 76)}
    spokes = {"A": [(30, 52), (34, 112), (96, 120)], "B": [(134, 46), (200, 54), (196, 118)]}
    sx, sy = 128, 128  # a record, filed with A, that belongs with B
    W = 220
    caps = (("as rewired", ""), ("a record regrouped", "✓ saved by itself"),
            ("new ingested knowledge, linked", "✓ saved by itself"), ("drop a group you asked for?", "? asks you first"))
    b.append(T(16, 34, "⟳ every week, on its own: tidies your graph", "s b"))
    for i in range(4):
        ox, oy = 16 + 236 * i, 52
        base, change = [], []
        for h, (hx, hy) in hubs.items():
            dropped = i == 3 and h == "A"
            (change if dropped else base).extend(E(ox + hx, oy + hy, ox + x, oy + y, 8, 5, "lo dash" if dropped else "ln")
                                                 for x, y in spokes[h])
        if i == 0:
            base.append(E(ox + 66, oy + 76, ox + sx, oy + sy, 8, 5))
        elif i == 1:
            base.append(E(ox + 66, oy + 76, ox + sx, oy + sy, 8, 5, "ln dash"))
            change.append(E(ox + 164, oy + 76, ox + sx, oy + sy, 8, 5, "lo"))
        else:
            base.append(E(ox + 164, oy + 76, ox + sx, oy + sy, 8, 5))
        if i >= 2:  # new knowledge, linked to what it bears on
            (change if i == 2 else base).extend(E(ox + 110, oy + 150, ox + x, oy + y, 6, 5, "lo" if i == 2 else "ln")
                                                for x, y in ((96, 120), (sx, sy)))
        for h, (hx, hy) in hubs.items():
            if i == 3 and h == "A":
                change += [f'<circle cx="{ox + hx}" cy="{oy + hy}" r="8" class="po" style="stroke-dasharray:3 3"/>',
                           T(ox + hx, oy + 60, "?", "s b or", "middle")]
            else:
                base.append(N(ox + hx, oy + hy, 8))
            base += [N(ox + x, oy + y) for x, y in spokes[h]]
        (change if i == 1 else base).append(N(ox + sx, oy + sy, 5, "po" if i == 1 else "pn"))
        if i >= 2:
            (change if i == 2 else base).append(N(ox + 110, oy + 150, 6, "po" if i == 2 else "pn"))
        c1, c2 = caps[i]
        cap = [T(ox + 2, 248, c1, "s b or" if i == 3 else "s b" if i else "s mu")]
        if c2:
            cap.append(T(ox + 2, 268, c2, "s b or" if i == 3 else "s b ok"))
        b += [R(ox, oy, W, 170, "po" if i == 3 else "pn", 10), T(ox + 14, oy + 24, f"week {i + 1}", "s b"), *base,
              *change, *cap]
        if i < 3:
            b.append(P(f"M{ox + W + 1} 137 H{ox + 235}", "ln"))
    b.append(T(16, 304, "small and undoable → saves itself · bigger, or losing anything you asked for → asks you "
                        "at your next session", "s mu"))
    return svg("engram: the weekly pass", 960, 320,
               "Every week, on its own, engram tidies your graph. Week 1: as rewired. Week 2: a record regrouped, saved "
               "by itself. Week 3: new ingested knowledge, linked, saved by itself. Week 4: dropping a group you asked "
               "for is a bigger change, so it asks you first. Small and undoable changes save themselves; bigger ones, "
               "or losing anything you asked for, are asked at your next session.", b)


# --- what a record is made of ------------------------------------------------------------------------------------------

def NB(x, y, r=6):
    return f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" class="nb"/>'


def record():
    def file_card(x, y, w, h, path):
        return [R(x, y, w, h, "pn", 8), T(x + 14, y + 22, path, "m mu"), f'<path d="M{x} {y + 32} H{x + w}" class="ln"/>']

    b = [T(16, 34, "on disk: plain files", "s b"), T(520, 34, "what engram builds from them", "s b")]
    # an entry, a link, a document
    b += file_card(16, 48, 456, 132, "events/2026/06/[id].md")
    for i, (l, r) in enumerate((("date: 2026-06", "when it happened"), ("about: [thread]", "the story it's on"),
                                ("by: me", "who said it"), ("[the fact]", "one fact, never edited"))):
        b += [T(30, 104 + 21 * i, l, "m"), T(456, 104 + 21 * i, r, "s mu", "end")]
    b += file_card(16, 192, 456, 58, "events/links.jsonl")
    b += [T(30, 240, '{"from": B, "to": A, "rel": "revises"}', "m"), T(456, 240, "one line each", "s mu", "end")]
    b += file_card(16, 262, 456, 58, "[page].md")
    b += [T(30, 310, "# [where things stand]", "m"), T(456, 310, "rewritten whole", "s mu", "end")]
    b.append(P("M480 186 H514"))
    # the graph: threads as lines through their entries, links as arrows
    b.append(R(520, 48, 424, 272, "pn", 10))
    nodes = {(600, 110), (740, 110), (840, 110), (680, 180), (780, 180), (880, 250)}
    for y in (110, 180, 250):
        b.append(T(536, y - 14, "[thread]", "m mu"))
        xs = [544] + sorted(x for x, ny in nodes if ny == y) + [928]
        b += [E(x1, y, x2, y, 0 if x1 == 544 else 6, 0 if x2 == 928 else 6) for x1, x2 in zip(xs, xs[1:])]
    b += [P("M771 173 C750 150 712 150 689 173", "lo aro"), T(730, 146, "revises", "m or", "middle"),
          P("M846 116 C880 150 880 200 878 242", "lo aro"), T(862, 216, "led to", "m or", "end")]
    b += [NB(x, y) for x, y in nodes]
    b += [T(680, 206, "A", "m mu", "middle"), T(780, 206, "B", "m mu", "middle"),
          T(536, 306, "entries in time, on their threads, with typed links", "s mu")]
    return svg("engram: what a record is made of", 960, 336,
               "On disk, a record is plain files: an entry file per fact (its date, the thread it's about, who said "
               "it, and the fact, never edited), one line of events/links.jsonl per link (B revises A), and documents "
               "rewritten whole. From them engram builds a graph: entries in time on their threads, with typed links "
               "such as revises and led to.", b)


# --- where things live ----------------------------------------------------------------------------------------------------

def arch():
    def tree(x, y, rows):
        return [T(x + 18 * depth, y + 22 * k, name, f"m {cls}".strip()) for k, (depth, name, cls) in enumerate(rows)]

    b = card(16, 20, 452, 180, "engram/", "this repo")
    b += tree(32, 96, [(0, "src/engram/", ""), (0, "skills/", ""), (1, "engram-rewire/", ""), (1, "engram-refine/", ""),
                       (0, "docs/", "")])
    b += card(492, 20, 452, 180, "[your repo]/", "your record, plain git")
    b += [R(500, 80, 436, 24, "po", 6), T(928, 96, "engram's folder", "s mu", "end")]
    b += tree(508, 96, [(0, ".engram/", "or b"), (0, "events/…/[id].md", ""), (0, "events/links.jsonl", ""),
                        (0, "[page].md", "")])
    b.append(P("M468 110 H488"))
    b += card(16, 216, 928, 76, "your machine")
    b += [T(32, 276, "~/.config/engram/config.toml", "m"), T(278, 276, "which repos", "s mu"),
          T(500, 276, "~/.local/share/engram/", "m"), T(690, 276, "the index", "s mu")]
    return svg("engram: where things live", 960, 306,
               "Where things live: engram's own repo holds the code and skills. Your repo is your record, plain git, "
               "with engram's folder .engram/ inside it beside your entries, links and documents. On your machine, "
               "~/.config/engram/config.toml names which repos engram serves, and ~/.local/share/engram/ holds the "
               "index.", b)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
    for name, fn in (("loop", loop), ("filer", filer), ("versions", versions), ("rewire", rewire), ("evolve", evolve),
                     ("record", record), ("arch", arch)):
        dark = fn()
        (out / f"{name}-dark.svg").write_text(dark)
        (out / f"{name}-light.svg").write_text(dark.replace('class="dark"', 'class="light"', 1))
