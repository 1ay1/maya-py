"""fluid.py — a swirling reaction-diffusion / advection fluid, half-block.

A velocity field advects a dye density that decays over time; periodic
emitters inject colour. The result is a continuously churning plasma. Click
to inject dye at the cursor.

  space pause · c palette · r reset · q/esc quit

    PYTHONPATH=src python examples/fluid.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, component
from _halfblock import halfblock

PW, PH = 72, 40

PALETTES = [
    ("aurora", [(10, 20, 40), (20, 120, 160), (60, 220, 180), (200, 255, 220)]),
    ("ember", [(20, 5, 5), (160, 40, 20), (255, 140, 30), (255, 240, 180)]),
    ("violet", [(15, 5, 30), (90, 30, 160), (200, 80, 230), (255, 220, 255)]),
]


def _grad(pal, t):
    t = max(0.0, min(0.999, t))
    seg = t * (len(pal) - 1)
    i = int(seg)
    f = seg - i
    a, bcol = pal[i], pal[i + 1]
    return tuple(int(a[k] + (bcol[k] - a[k]) * f) for k in range(3))


app = App("fluid", inline=True, fps=30, mouse=True)
app.state(dye=[0.0] * (PW * PH), t=0.0, paused=False, pal=0)


def reset(s):
    s.dye = [0.0] * (PW * PH)
    s.t = 0.0


def _vel(x, y, t):
    # smooth curl-noise-ish velocity field
    fx = math.sin(y * 0.18 + t * 0.7) + 0.6 * math.cos(x * 0.12 - t * 0.4)
    fy = math.cos(x * 0.16 - t * 0.5) + 0.6 * math.sin(y * 0.10 + t * 0.6)
    return fx, fy


def step(s):
    s.t += 0.08
    dye = s.dye
    nxt = [0.0] * (PW * PH)
    t = s.t
    for y in range(PH):
        for x in range(PW):
            vx, vy = _vel(x, y, t)
            sx = x - vx
            sy = y - vy
            ix, iy = int(sx) % PW, int(sy) % PH
            nxt[y * PW + x] = dye[iy * PW + ix] * 0.965
    # emitters
    for i in range(3):
        ex = int(PW * (0.3 + 0.2 * i) + 6 * math.sin(t * 0.6 + i))
        ey = int(PH * 0.5 + 8 * math.cos(t * 0.5 + i * 2))
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                xx, yy = (ex + dx) % PW, (ey + dy) % PH
                nxt[yy * PW + xx] = min(1.0, nxt[yy * PW + xx] + 0.5)
    s.dye = nxt


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("c")
def _cycle(s): s.pal = (s.pal + 1) % len(PALETTES)


@app.on("r")
def _reset(s): reset(s)


@app.on("q", "esc")
def _quit(s): app.stop()


def field(s):
    def draw(w, h):
        pal = PALETTES[s.pal][1]
        grid = []
        for y in range(PH):
            crow = []
            for x in range(PW):
                d = s.dye[y * PW + x]
                crow.append(_grad(pal, d) if d > 0.02 else _grad(pal, 0.0))
            grid.append(crow)
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        step(s)
    return card(
        row(b("≈ fluid").fg((60, 220, 180)),
            dim_text(f"{PALETTES[s.pal][0]} · t {s.t:5.1f} · "
                     f"{'paused' if s.paused else 'flowing'}"),
            justify="between"),
        field(s),
        dim_text("space pause · c palette · r reset · q quit"),
        title="advection", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
