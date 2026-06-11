"""particles.py — a half-block particle fountain with gravity and colour decay.

Particles spawn at the bottom centre, arc up under gravity, and fade through a
fire-to-smoke palette as they age. Click (mouse) to burst particles at the
cursor; the fountain runs continuously.

  space pause · +/- rate · c color cycle · q/esc quit · click to burst

    PYTHONPATH=src python examples/particles.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, component
from _halfblock import halfblock

PW, PH = 90, 48
GRAV = 0.06
MAX_P = 600

PALETTES = [
    ("fire", [(255, 240, 180), (255, 180, 60), (255, 90, 30), (150, 40, 20)]),
    ("ice", [(220, 245, 255), (130, 200, 255), (60, 120, 230), (30, 50, 120)]),
    ("toxic", [(220, 255, 180), (140, 240, 90), (60, 180, 50), (20, 90, 30)]),
]


def _grad(pal, t):
    t = max(0.0, min(0.999, t))
    seg = t * (len(pal) - 1)
    i = int(seg)
    f = seg - i
    a, b = pal[i], pal[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


app = App("particles", inline=True, fps=30, mouse=True)
# particle: [x, y, vx, vy, life, maxlife]
app.state(parts=[], paused=False, rate=6, pal=0, frame=0, bounds=None)


def _spawn(s, x, y, vx0=0.0, vy0=-1.0, spread=0.5, n=1):
    for _ in range(n):
        if len(s.parts) >= MAX_P:
            return
        ang = random.uniform(-spread, spread)
        speed = random.uniform(0.7, 1.4)
        vx = vx0 + math.sin(ang) * speed
        vy = vy0 - math.cos(ang) * speed * random.uniform(0.8, 1.3)
        life = random.randint(28, 56)
        s.parts.append([x, y, vx, vy, life, life])


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("+", "=")
def _up(s): s.rate = min(20, s.rate + 1)


@app.on("-")
def _dn(s): s.rate = max(1, s.rate - 1)


@app.on("c")
def _cycle(s): s.pal = (s.pal + 1) % len(PALETTES)


@app.on("q", "esc")
def _quit(s): app.stop()


@app.on_click("left")
def _burst(s, col_, row_):
    b = s.bounds
    if not b:
        return
    bx, by, bw, bh = b
    # map screen cell → pixel coords
    px = int((col_ - bx) / max(1, bw) * PW)
    py = int((row_ - by) / max(1, bh) * PH)
    _spawn(s, px, py, vy0=0.0, spread=math.pi, n=40)


def step(s):
    s.frame += 1
    # continuous fountain
    _spawn(s, PW / 2, PH - 1, vy0=1.6, spread=0.45, n=s.rate)
    alive = []
    for p in s.parts:
        p[2] *= 0.99
        p[3] += GRAV
        p[0] += p[2]
        p[1] += p[3]
        p[4] -= 1
        if p[4] > 0 and 0 <= p[1] < PH and -2 <= p[0] < PW + 2:
            alive.append(p)
    s.parts = alive


def field(s):
    def draw(w, h):
        s.bounds = None  # set after first layout below
        grid = [[None] * PW for _ in range(PH)]
        pal = PALETTES[s.pal][1]
        for p in s.parts:
            x, y = int(p[0]), int(p[1])
            if 0 <= x < PW and 0 <= y < PH:
                age_t = 1.0 - p[4] / p[5]
                grid[y][x] = _grad(pal, age_t)
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        step(s)
    name = PALETTES[s.pal][0]
    return card(
        row(b("✦ particles").fg((255, 200, 120)),
            dim_text(f"{name} · {len(s.parts)} alive · rate {s.rate} · "
                     f"{'paused' if s.paused else 'flowing'}"),
            justify="between"),
        field(s),
        dim_text("space pause · +/- rate · c color · click burst · q quit"),
        title="fountain", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
