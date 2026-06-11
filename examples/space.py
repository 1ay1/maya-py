"""space.py — a warp-speed starfield flying toward the viewer.

Stars stream outward from a vanishing point; closer stars are bigger and
brighter, with motion-blur streaks at high warp. Pure projection math drawn
into a half-block field.

  space pause · +/- warp · q/esc quit

    PYTHONPATH=src python examples/space.py
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

PW, PH = 96, 56
NSTARS = 220


def _newstar():
    return [random.uniform(-1, 1), random.uniform(-1, 1),
            random.uniform(0.1, 1.0)]   # x, y in [-1,1], z depth


app = App("space", inline=True, fps=30)
app.state(stars=[_newstar() for _ in range(NSTARS)], warp=0.04, paused=False)


def step(s):
    for st in s.stars:
        st[2] -= s.warp
        if st[2] <= 0.02:
            st[0] = random.uniform(-1, 1)
            st[1] = random.uniform(-1, 1)
            st[2] = 1.0


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("+", "=")
def _up(s): s.warp = min(0.18, s.warp + 0.01)


@app.on("-")
def _dn(s): s.warp = max(0.01, s.warp - 0.01)


@app.on("q", "esc")
def _quit(s): app.stop()


def field(s):
    def draw(w, h):
        grid = [[None] * PW for _ in range(PH)]
        cx, cy = PW / 2, PH / 2
        for st in s.stars:
            z = st[2]
            sx = cx + st[0] / z * cx
            sy = cy + st[1] / z * cy
            ix, iy = int(sx), int(sy)
            if 0 <= ix < PW and 0 <= iy < PH:
                bright = int(255 * (1 - z))
                bright = max(40, bright)
                c = (bright, bright, min(255, bright + 30))
                grid[iy][ix] = c
                # streak for near stars
                if z < 0.4:
                    px = cx + st[0] / (z + s.warp) * cx
                    py = cy + st[1] / (z + s.warp) * cy
                    jx, jy = int(px), int(py)
                    if 0 <= jx < PW and 0 <= jy < PH:
                        dim = (bright // 2, bright // 2, bright // 2)
                        grid[jy][jx] = dim
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        step(s)
    return card(
        row(b("✦ warp speed").fg((180, 200, 255)),
            dim_text(f"warp {s.warp:.2f} · {NSTARS} stars · "
                     f"{'paused' if s.paused else 'flying'}"),
            justify="between"),
        field(s),
        dim_text("space pause · +/- warp · q quit"),
        title="starfield", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
