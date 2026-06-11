"""space3d.py — a rotating 3D wireframe (a spinning cube + an icosahedron),
projected and drawn with Bresenham lines into a half-block field.

Perspective projection, back-to-front depth shading on edges, continuous
rotation on three axes.

  space pause · ←/→ yaw · ↑/↓ pitch · 1/2 shape · q/esc quit

    PYTHONPATH=src python examples/space3d.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, component
from _halfblock import halfblock

PW, PH = 80, 64

# cube vertices + edges
CUBE_V = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
CUBE_E = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6),
          (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]

# icosahedron
_p = (1 + 5 ** 0.5) / 2
ICO_V = [
    (-1, _p, 0), (1, _p, 0), (-1, -_p, 0), (1, -_p, 0),
    (0, -1, _p), (0, 1, _p), (0, -1, -_p), (0, 1, -_p),
    (_p, 0, -1), (_p, 0, 1), (-_p, 0, -1), (-_p, 0, 1),
]
ICO_V = [(x / _p, y / _p, z / _p) for (x, y, z) in ICO_V]
ICO_E = [(0, 11), (0, 5), (0, 1), (0, 7), (0, 10), (1, 5), (5, 11), (11, 10),
         (10, 7), (7, 1), (3, 9), (3, 4), (3, 2), (3, 6), (3, 8), (4, 9),
         (9, 8), (8, 6), (6, 2), (2, 4), (1, 9), (5, 4), (11, 2), (10, 6),
         (7, 8), (4, 11), (2, 10), (6, 7), (8, 1), (9, 5)]

SHAPES = [("cube", CUBE_V, CUBE_E), ("icosahedron", ICO_V, ICO_E)]

app = App("space3d", inline=True, fps=30)
app.state(ax=0.0, ay=0.0, az=0.0, yaw=0.012, pitch=0.009,
          shape=0, paused=False)


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("left")
def _yl(s): s.yaw -= 0.004


@app.on("right")
def _yr(s): s.yaw += 0.004


@app.on("up")
def _pu(s): s.pitch += 0.004


@app.on("down")
def _pd(s): s.pitch -= 0.004


@app.on("1")
def _s1(s): s.shape = 0


@app.on("2")
def _s2(s): s.shape = 1


@app.on("q", "esc")
def _quit(s): app.stop()


def _rot(v, ax, ay, az):
    x, y, z = v
    # X
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    # Y
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    # Z
    x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
    return x, y, z


def _project(v):
    x, y, z = v
    d = 3.2
    f = d / (d + z)
    sx = PW / 2 + x * f * PW * 0.42
    sy = PH / 2 - y * f * PH * 0.42
    return sx, sy, z


def _line(grid, x0, y0, x1, y1, c):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < PW and 0 <= y0 < PH:
            grid[y0][x0] = c
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def render(s):
    def draw(w, h):
        name, verts, edges = SHAPES[s.shape]
        grid = [[None] * PW for _ in range(PH)]
        pv = [_project(_rot(v, s.ax, s.ay, s.az)) for v in verts]
        for (a, bb) in edges:
            za = pv[a][2]
            zb = pv[bb][2]
            zc = (za + zb) / 2
            t = (zc + 1.4) / 2.8
            t = max(0.1, min(1.0, t))
            c = (int(80 + 175 * (1 - t)), int(120 + 100 * (1 - t)), 255)
            _line(grid, pv[a][0], pv[a][1], pv[bb][0], pv[bb][1], c)
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        s.ax += s.pitch
        s.ay += s.yaw
        s.az += 0.004
    name = SHAPES[s.shape][0]
    return card(
        row(b("◈ 3d wireframe").fg((140, 180, 255)),
            dim_text(f"{name} · {'paused' if s.paused else 'spinning'}"),
            justify="between"),
        render(s),
        dim_text("space pause · ←→ yaw · ↑↓ pitch · 1/2 shape · q quit"),
        title="space3d", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
