"""doom_fire.py — the classic Doom PSX fire effect (faithful port of doom_fire.cpp).

A hot source row of MAX_HEAT embers along the bottom; each pixel is cooled by a
random decay and nudged sideways by wind as it propagates upward. Ember
particles spawn from the high-heat core and drift up with buoyancy. Three
palettes (CLASSIC / INFERNO / TOXIC), wind ±5, intensity 1-5. The field fills
the whole terminal (last row reserved for the status bar) — no border, exactly
like the C++ original.

  q/Esc quit · space toggle source · ←/→ wind · +/- heat · 1/2/3 palette

    PYTHONPATH=src python examples/doom_fire.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, component, halfblock  # noqa: E402

MAX_HEAT = 48
NUM_PALETTES = 3
# Cap the simulated fire field height: the fullscreen layout hands the field
# component an unbounded-height sentinel, so without a cap we'd simulate a
# 200-row fire (400 px rows) every frame regardless of the real terminal —
# that was the source of the lag. Simulate at most MAX_CH cells tall (covers
# any normal terminal; taller ones clip harmlessly) and let maya clip.
MAX_CH = 50

_rng = random.Random(42)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ── Palettes (heat 0..MAX_HEAT → (r,g,b)), byte-faithful to doom_fire.cpp ─────

def classic_color(h):
    h = _clamp(h, 0, MAX_HEAT)
    t = h / MAX_HEAT
    if t < 0.15:
        u = t / 0.15
        return (int(u * 180), 0, 0)
    if t < 0.4:
        u = (t - 0.15) / 0.25
        return (int(180 + u * 75), int(u * 100), 0)
    if t < 0.7:
        u = (t - 0.4) / 0.3
        return (255, int(100 + u * 155), 0)
    u = (t - 0.7) / 0.3
    return (255, 255, int(u * 255))


def inferno_color(h):
    h = _clamp(h, 0, MAX_HEAT)
    t = h / MAX_HEAT
    if t < 0.2:
        u = t / 0.2
        return (int(u * 60), 0, int(u * 100))
    if t < 0.45:
        u = (t - 0.2) / 0.25
        return (int(60 + u * 160), 0, int(100 + u * 60))
    if t < 0.7:
        u = (t - 0.45) / 0.25
        return (int(220 + u * 35), int(u * 140), int(160 - u * 160))
    u = (t - 0.7) / 0.3
    return (255, int(140 + u * 115), int(u * 200))


def toxic_color(h):
    h = _clamp(h, 0, MAX_HEAT)
    t = h / MAX_HEAT
    if t < 0.2:
        u = t / 0.2
        return (0, int(u * 60), 0)
    if t < 0.5:
        u = (t - 0.2) / 0.3
        return (0, int(60 + u * 195), int(u * 30))
    if t < 0.75:
        u = (t - 0.5) / 0.25
        return (int(u * 200), 255, int(30 - u * 30))
    u = (t - 0.75) / 0.25
    return (int(200 + u * 55), 255, int(u * 255))


PALETTES = [("CLASSIC", classic_color), ("INFERNO", inferno_color),
            ("TOXIC", toxic_color)]

# Precompute a heat→colour lookup table per palette (heat 0..MAX_HEAT). The
# render loop touches every pixel each frame; a list index is ~10× cheaper
# than recomputing the gradient, which is what keeps 60fps achievable.
_BLACK = (0, 0, 0)
PALETTE_LUTS = [[fn(hh) if hh > 0 else _BLACK for hh in range(MAX_HEAT + 1)]
                for _name, fn in PALETTES]


# ── State ────────────────────────────────────────────────────────────────────

# A pure-Python fire sim at 60fps over a full terminal is too heavy (the per
# pixel propagation does several RNG draws each frame); 30fps runs smoothly
# with headroom and looks just as fluid. The C++ original is native at 60.
app = App("doom_fire", inline=False, fps=30)
app.state(fire=[], w=0, h=0, source=True, wind=0, palette=0, intensity=3,
          embers=[])  # ember: [x, y, vx, vy, heat, life]


def rebuild(s, w, h):
    s.w, s.h = w, h
    fire_h = h * 2
    s.fire = [0] * (w * fire_h)
    if s.source:
        base = (fire_h - 1) * w
        for x in range(w):
            s.fire[base + x] = MAX_HEAT


def step(s):
    w, h = s.w, s.h
    if w == 0 or h == 0:
        return
    fire_h = h * 2
    f = s.fire
    wind = s.wind
    aw = abs(wind)
    decay_hi = 6 - s.intensity
    ri = _rng.randint
    wmax = w - 1
    # Propagate upward. Hoist the wind branch out of the inner loop and fold
    # the horizontal jitter (±1) into a single random span so we do two RNG
    # draws per cell instead of three.
    if wind == 0:
        lo, hi = -1, 1
    elif wind > 0:
        lo, hi = -1, aw + 1
    else:
        lo, hi = -aw - 1, 1
    for y in range(fire_h - 1):
        rowbase = y * w
        srcbase = (y + 1) * w
        for x in range(w):
            src_x = x + ri(lo, hi)
            if src_x < 0:
                src_x = 0
            elif src_x > wmax:
                src_x = wmax
            heat = f[srcbase + src_x] - ri(0, decay_hi)
            f[rowbase + x] = heat if heat > 0 else 0
    # Maintain the source row.
    if s.source:
        base = (fire_h - 1) * w
        for x in range(w):
            f[base + x] = MAX_HEAT
    # Spawn ember particles from the high-heat core.
    if s.source and _rng.randint(0, 2) == 0:
        ex = _rng.randrange(w)
        ey_row = fire_h // 3 + _rng.randrange(fire_h // 3)
        heat = f[ey_row * w + ex]
        if heat > MAX_HEAT // 2:
            vx = (_rng.randrange(100) - 50) / 200.0 + s.wind * 0.05
            vy = -(_rng.randrange(100) + 30) / 200.0
            s.embers.append([float(ex), ey_row / 2.0, vx, vy, heat, 1.0])
    # Update embers (buoyancy + cooling + fade).
    for e in s.embers:
        e[0] += e[2]
        e[1] += e[3]
        e[3] -= 0.003
        e[5] -= 0.02
        e[4] = int(e[4] * 0.97)
    s.embers = [e for e in s.embers if e[5] > 0.0 and e[4] > 1]


# ── Events ─────────────────────────────────────────────────────────────────

@app.on("space")
def _toggle(s):
    s.source = not s.source
    if s.w and s.h:
        fire_h = s.h * 2
        base = (fire_h - 1) * s.w
        v = MAX_HEAT if s.source else 0
        for x in range(s.w):
            s.fire[base + x] = v


@app.on("right")
def _wr(s):
    s.wind = min(s.wind + 1, 5)


@app.on("left")
def _wl(s):
    s.wind = max(s.wind - 1, -5)


@app.on("+", "=")
def _up(s):
    s.intensity = min(s.intensity + 1, 5)


@app.on("-")
def _dn(s):
    s.intensity = max(s.intensity - 1, 1)


@app.on("1")
def _p1(s):
    s.palette = 0


@app.on("2")
def _p2(s):
    s.palette = 1


@app.on("3")
def _p3(s):
    s.palette = 2


@app.on("q", "esc")
def _quit(s):
    app.stop()


# ── Render ───────────────────────────────────────────────────────────────────

def _field(w, h):
    # The fullscreen layout passes an unbounded-height sentinel for h. We can't
    # learn the real terminal height, so simulate a fixed, bounded field that
    # comfortably covers a normal terminal and let maya clip the overflow.
    # (Capping here is what keeps the 60fps sim cheap.)
    w = max(1, min(int(w), 400))
    canvas_h = MAX_CH if h > MAX_CH else max(1, int(h))
    s = app.s
    if w != s.w or canvas_h != s.h:
        rebuild(s, w, canvas_h)
    step(s)
    lut = PALETTE_LUTS[s.palette]
    f = s.fire
    fw = s.w
    # Build the half-block pixel grid by mapping each fire row through the LUT.
    # A per-row list comprehension over a slice is far faster than a nested
    # per-pixel Python loop with a function call.
    grid = [None] * (canvas_h * 2)
    pr = 0
    base = 0
    for _cy in range(canvas_h * 2):
        rowf = f[base:base + fw]
        grid[pr] = [lut[hv] for hv in rowf]
        base += fw
        pr += 1
    # Embers on top (a bright dot in the upper pixel of its cell).
    for e in s.embers:
        ex = int(e[0])
        ey = int(e[1])
        if 0 <= ex < fw and 0 <= ey < canvas_h:
            grid[ey * 2][ex] = lut[_clamp(int(e[4]), 0, MAX_HEAT)]
    return halfblock(grid)


_BAR = ("DOOM FIRE \u2502 [1-3] palette \u2502 [+/-] heat \u2502 "
        "[\u2190\u2192] wind \u2502 [space] toggle \u2502 [q] quit")
_BAR_BG = (20, 20, 20)


def _status(w, h):
    s = app.s
    name = PALETTES[s.palette][0]
    right = f"{name} h:{s.intensity} w:{s.wind:+d} e:{len(s.embers)}"
    w = max(1, min(int(w), 400))
    # Compose a fixed-width line of (char, accent?) the way the C++ canvas does:
    # write the dim bar at col 1, accent "DOOM FIRE" over it, then overlay the
    # accented right stats at (w - len(right) - 1) — the bar tail is overwritten.
    bar = _BAR
    chars = [" "] * w
    accent = [False] * w  # True => accent colour (orange+bold), else dim
    # dim bar starting at column 1
    for i, ch in enumerate(bar):
        c = 1 + i
        if c < w:
            chars[c] = ch
    # accent "DOOM FIRE"
    for i, ch in enumerate("DOOM FIRE"):
        c = 1 + i
        if c < w:
            chars[c] = ch
            accent[c] = True
    # right stats overlay
    rlen = len(right)
    if w > rlen + 2:
        start = w - rlen - 1
        for i, ch in enumerate(right):
            c = start + i
            if 0 <= c < w:
                chars[c] = ch
                accent[c] = True
    # Merge into runs of (text, accent) to keep the segment count low.
    cells = []
    i = 0
    while i < w:
        a = accent[i]
        j = i
        while j < w and accent[j] == a:
            j += 1
        text = "".join(chars[i:j])
        if a:
            cells.append((text, (255, 140, 40), _BAR_BG, 1))
        else:
            cells.append((text, (100, 100, 110), _BAR_BG))
        i = j
    return row(*cells, gap=0)


@app.view
def view(s):
    return col(
        component(_field, grow=1),
        component(_status, height=1),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
