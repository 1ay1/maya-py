"""fps.py — a Wolfenstein-style raycaster: walk a textured dungeon in first
person, half-block rendered, with a minimap.

DDA raycasting against a tile map; walls are shaded by distance and side
(N/S vs E/W) with a brick-mortar pattern, plus a lit floor/ceiling gradient.

  WASD / arrows move · ,/. turn · m minimap · q/esc quit

    PYTHONPATH=src python examples/fps.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component
from _halfblock import halfblock

MAP = [
    "################",
    "#..............#",
    "#..##....####..#",
    "#..#........#..#",
    "#..#..####..#..#",
    "#.....#..#.....#",
    "#..#..#..#..#..#",
    "#..#........#..#",
    "#..####..####..#",
    "#..............#",
    "#..##..##..##..#",
    "#..............#",
    "################",
]
MH = len(MAP)
MW = len(MAP[0])

PW, PH = 96, 56          # mutated per-frame to the real terminal size
FOV = math.pi / 3
MAX_PW = 140             # column ceiling so the cast loop stays smooth

app = App("fps", inline=True, fps=24)
app.state(px=2.5, py=2.5, ang=0.4, show_map=True)


def _wall(x, y):
    if 0 <= int(y) < MH and 0 <= int(x) < MW:
        return MAP[int(y)][int(x)] == "#"
    return True


def _move(s, fwd, strafe):
    spd = 0.18
    nx = s.px + math.cos(s.ang) * fwd * spd - math.sin(s.ang) * strafe * spd
    ny = s.py + math.sin(s.ang) * fwd * spd + math.cos(s.ang) * strafe * spd
    if not _wall(nx, s.py):
        s.px = nx
    if not _wall(s.px, ny):
        s.py = ny


@app.on("w", "up")
def _fwd(s): _move(s, 1, 0)


@app.on("s", "down")
def _back(s): _move(s, -1, 0)


@app.on("a")
def _sl(s): _move(s, 0, -1)


@app.on("d")
def _sr(s): _move(s, 0, 1)


@app.on(",", "left")
def _tl(s): s.ang -= 0.12


@app.on(".", "right")
def _tr(s): s.ang += 0.12


@app.on("m")
def _map(s): s.show_map = not s.show_map


@app.on("q", "esc")
def _quit(s): app.stop()


def _cast(s, col_frac):
    ray = s.ang - FOV / 2 + col_frac * FOV
    sin, cos = math.sin(ray), math.cos(ray)
    dist = 0.0
    while dist < 20:
        dist += 0.04
        tx = s.px + cos * dist
        ty = s.py + sin * dist
        if _wall(tx, ty):
            # which side? use fractional part nearest to integer
            fx = tx - int(tx)
            fy = ty - int(ty)
            side = 0 if min(fx, 1 - fx) < min(fy, 1 - fy) else 1
            hit_u = fy if side == 0 else fx
            return dist * math.cos(ray - s.ang), side, hit_u
    return 20.0, 0, 0.0


def world(s):
    def draw(w, h):
        global PW, PH
        h = max(1, min(h, 60))
        PW = min(w, MAX_PW)
        PH = h * 2
        grid = [[None] * PW for _ in range(PH)]
        for sx in range(PW):
            d, side, hu = _cast(s, sx / PW)
            wall_h = min(PH, int(PH / (d + 0.0001)))
            top = (PH - wall_h) // 2
            shade = max(0.15, 1.0 - d / 12)
            if side == 1:
                shade *= 0.7
            for sy in range(PH):
                if sy < top:
                    # ceiling gradient
                    f = sy / max(1, top)
                    grid[sy][sx] = (int(20 + 30 * f), int(20 + 25 * f), int(40 + 40 * f))
                elif sy < top + wall_h:
                    # brick: mortar lines on a grid
                    vy = (sy - top) / max(1, wall_h)
                    mortar = (abs(hu - 0.5) > 0.46) or (abs((vy * 4) % 1 - 0.5) > 0.44)
                    base = (180, 90, 60) if not mortar else (90, 80, 75)
                    grid[sy][sx] = tuple(int(c * shade) for c in base)
                else:
                    f = (sy - (top + wall_h)) / max(1, PH - (top + wall_h))
                    g = int(50 * (1 - f) + 15)
                    grid[sy][sx] = (g, g, int(g * 0.8))
        return halfblock(grid)
    return component(draw, grow=1)


def minimap(s):
    rows = []
    for y in range(MH):
        segs = []
        for x in range(MW):
            if int(s.px) == x and int(s.py) == y:
                segs.append(T("◉").fg("lime"))
            elif MAP[y][x] == "#":
                segs.append(T("█").fg("slate"))
            else:
                segs.append(T("·").fg((40, 40, 50)))
        rows.append(row(*segs, gap=0))
    return col(*rows, gap=0)


@app.view
def view(s):
    body = world(s)
    panes = [body]
    if s.show_map:
        panes = row(body, card(minimap(s), title="map", pad=1,
                               align_self="start"), gap=1)
    else:
        panes = body
    return card(
        row(b("▣ dungeon").fg((200, 120, 80)),
            dim_text(f"pos ({s.px:.1f},{s.py:.1f}) · {math.degrees(s.ang)%360:3.0f}°"),
            justify="between"),
        panes,
        dim_text("wasd/↑↓ move · ,/. or ←→ turn · m minimap · q quit"),
        title="fps", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
