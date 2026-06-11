"""doom_fire.py — the classic Doom PSX fire effect, half-block rendered.

The fire-propagation algorithm: a hot row of "embers" along the bottom, each
pixel cooled and nudged sideways as it rises. Three palettes, adjustable wind
and intensity.

  space pause · ←/→ wind · +/- intensity · 1/2/3 palette · q/esc quit

    PYTHONPATH=src python examples/doom_fire.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component
from _halfblock import halfblock

PW, PH = 80, 44          # pixel field (PH even → PH/2 cell rows)
LEVELS = 37              # fire heat levels (0 = cold)


def _classic(h):
    u = h / LEVELS
    if u < 0.33:
        return (int(u * 3 * 180), 0, 0)
    if u < 0.66:
        v = (u - 0.33) * 3
        return (180 + int(v * 75), int(v * 100), 0)
    v = (u - 0.66) * 3
    return (255, 100 + int(v * 155), int(v * 255 * 0.4))


def _inferno(h):
    u = h / LEVELS
    return (int(40 + u * 120), int(u * u * 60), int(120 + u * 135))


def _toxic(h):
    u = h / LEVELS
    return (int(u * u * 120), int(40 + u * 215), int(u * 60))


PALETTES = [("classic", _classic), ("inferno", _inferno), ("toxic", _toxic)]

app = App("doom_fire", inline=True, fps=30)
app.state(fire=[0] * (PW * PH), paused=False, wind=0, intensity=LEVELS, pal=0)


def _seed(s):
    base = (PH - 1) * PW
    for x in range(PW):
        s.fire[base + x] = s.intensity


_seed(app.s)


def step(s):
    f = s.fire
    for x in range(PW):
        for y in range(1, PH):
            src = y * PW + x
            heat = f[src]
            decay = random.randint(0, 2)
            nx = x + s.wind + (random.randint(0, 2) - 1)
            nx = max(0, min(PW - 1, nx))
            dst = (y - 1) * PW + nx
            f[dst] = max(0, heat - decay)
    base = (PH - 1) * PW
    for x in range(PW):
        f[base + x] = s.intensity


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("left")
def _wl(s): s.wind = max(-2, s.wind - 1)


@app.on("right")
def _wr(s): s.wind = min(2, s.wind + 1)


@app.on("+", "=")
def _up(s): s.intensity = min(LEVELS, s.intensity + 2); _seed(s)


@app.on("-")
def _dn(s): s.intensity = max(4, s.intensity - 2); _seed(s)


@app.on("1")
def _p1(s): s.pal = 0


@app.on("2")
def _p2(s): s.pal = 1


@app.on("3")
def _p3(s): s.pal = 2


@app.on("q", "esc")
def _quit(s): app.stop()


def flame(s):
    def draw(w, h):
        name, fn = PALETTES[s.pal]
        grid = []
        for y in range(PH):
            crow = []
            for x in range(PW):
                hv = s.fire[y * PW + x]
                crow.append(fn(hv) if hv > 0 else None)
            grid.append(crow)
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        step(s)
    name = PALETTES[s.pal][0]
    return card(
        row(b("🔥 doom fire").fg((255, 140, 40)),
            dim_text(f"{name} · wind {s.wind:+d} · {'paused' if s.paused else 'burning'}"),
            justify="between"),
        flame(s),
        dim_text("space pause · ←→ wind · +/- intensity · 1/2/3 palette · q quit"),
        title="fire", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
