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
from maya_py import halfblock

NSTARS = 320


def _newstar():
    return [random.uniform(-1, 1), random.uniform(-1, 1),
            random.uniform(0.1, 1.0)]   # x, y in [-1,1], z depth


app = App("space", inline=True, fps=30)
app.state(stars=[_newstar() for _ in range(NSTARS)], warp=0.04, paused=False,
          pw=96, ph=56)


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
        h = max(1, min(h, 60))
        s.pw, s.ph = w, h * 2
        if not s.paused:
            step(s)
        pw, ph = s.pw, s.ph
        grid = [[None] * pw for _ in range(ph)]
        cx, cy = pw / 2, ph / 2
        for st in s.stars:
            z = st[2]
            sx = cx + st[0] / z * cx
            sy = cy + st[1] / z * cy
            ix, iy = int(sx), int(sy)
            if 0 <= ix < pw and 0 <= iy < ph:
                bright = max(40, int(255 * (1 - z)))
                c = (bright, bright, min(255, bright + 30))
                grid[iy][ix] = c
                # streak for near stars
                if z < 0.4:
                    px = cx + st[0] / (z + s.warp) * cx
                    py = cy + st[1] / (z + s.warp) * cy
                    jx, jy = int(px), int(py)
                    if 0 <= jx < pw and 0 <= jy < ph:
                        grid[jy][jx] = (bright // 2, bright // 2, bright // 2)
        return halfblock(grid)
    return component(draw, grow=1)


@app.view
def view(s):
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
