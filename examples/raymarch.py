"""raymarch.py — a real-time raymarched scene (a glowing sphere over a plane),
rendered with signed-distance fields into a half-block field.

Per-pixel sphere-tracing with Lambert + soft shadow + a pulsing emissive
sphere. It's heavy math per frame but the field is small (64×40), so it stays
smooth. Drag the light with ←/→/↑/↓.

  space pause · ←→↑↓ move light · q/esc quit

    PYTHONPATH=src python examples/raymarch.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, component
from _halfblock import halfblock

PW, PH = 64, 40
MAX_STEPS = 40
MAX_DIST = 12.0
EPS = 0.02


def _sd_sphere(p, c, r):
    return math.sqrt((p[0]-c[0])**2 + (p[1]-c[1])**2 + (p[2]-c[2])**2) - r


def _length(v):
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])


app = App("raymarch", inline=True, fps=20)
app.state(t=0.0, lx=2.5, ly=3.0, paused=False)


def _scene(p, t):
    # ground plane at y = -1, plus a bobbing sphere
    plane = p[1] + 1.0
    sy = 0.3 * math.sin(t)
    sph = _sd_sphere(p, (0, sy, 0), 1.0)
    return min(plane, sph), (0 if plane < sph else 1)


def _normal(p, t):
    d, _ = _scene(p, t)
    nx = _scene((p[0]+EPS, p[1], p[2]), t)[0] - d
    ny = _scene((p[0], p[1]+EPS, p[2]), t)[0] - d
    nz = _scene((p[0], p[1], p[2]+EPS), t)[0] - d
    l = math.sqrt(nx*nx + ny*ny + nz*nz) or 1
    return (nx/l, ny/l, nz/l)


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("left")
def _l(s): s.lx -= 0.4


@app.on("right")
def _r(s): s.lx += 0.4


@app.on("up")
def _u(s): s.ly += 0.4


@app.on("down")
def _d(s): s.ly -= 0.4


@app.on("q", "esc")
def _quit(s): app.stop()


def render(s):
    def draw(w, h):
        t = s.t
        ro = (0.0, 0.6, -4.0)          # ray origin (camera)
        light = (s.lx, s.ly, -1.5)
        grid = [[(8, 10, 22)] * PW for _ in range(PH)]
        for py in range(PH):
            for px in range(PW):
                u = (px / PW - 0.5) * 2 * (PW / PH) * 0.5
                v = -(py / PH - 0.5) * 2 * 0.5
                rd = (u, v, 1.0)
                rl = _length(rd)
                rd = (rd[0]/rl, rd[1]/rl, rd[2]/rl)
                dist = 0.0
                hit = False
                mat = 0
                for _ in range(MAX_STEPS):
                    p = (ro[0]+rd[0]*dist, ro[1]+rd[1]*dist, ro[2]+rd[2]*dist)
                    d, mat = _scene(p, t)
                    if d < EPS:
                        hit = True
                        break
                    dist += d
                    if dist > MAX_DIST:
                        break
                if hit:
                    p = (ro[0]+rd[0]*dist, ro[1]+rd[1]*dist, ro[2]+rd[2]*dist)
                    n = _normal(p, t)
                    ld = (light[0]-p[0], light[1]-p[1], light[2]-p[2])
                    ll = _length(ld) or 1
                    ld = (ld[0]/ll, ld[1]/ll, ld[2]/ll)
                    diff = max(0.0, n[0]*ld[0] + n[1]*ld[1] + n[2]*ld[2])
                    if mat == 1:
                        glow = 0.5 + 0.5 * math.sin(t * 2)
                        base = (255, int(120 + 100*glow), 60)
                    else:
                        chk = (int(p[0]) + int(p[2])) % 2
                        base = (200, 200, 210) if chk else (60, 70, 90)
                    sh = 0.25 + 0.75 * diff
                    grid[py][px] = tuple(min(255, int(c * sh)) for c in base)
        return halfblock(grid)
    return component(draw, height=PH // 2, width=PW)


@app.view
def view(s):
    if not s.paused:
        s.t += 0.1
    return card(
        row(b("◐ raymarch").fg((255, 160, 80)),
            dim_text(f"sdf · light ({s.lx:.1f},{s.ly:.1f}) · "
                     f"{'paused' if s.paused else 'live'}"),
            justify="between"),
        render(s),
        dim_text("space pause · ←→↑↓ move light · q quit"),
        title="raymarch", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
