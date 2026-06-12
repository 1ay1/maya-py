"""boids.py — a flocking simulation (Reynolds boids) in the terminal.

A swarm of birds obeys three local rules — separation, alignment, cohesion —
and self-organises into flowing flocks, coloured by heading. Just MOVE the
mouse (no button needed) and the flock follows the cursor; press 'm' to switch
the cursor between an attractor (follow), a predator they scatter from (flee),
or off (free). The field is rendered with half-blocks (`▀`) so it fills the
terminal at double vertical resolution.

  move mouse — lead the flock (cursor follows you with no button held)
  left-click — burst-scatter the flock from that point
  m          — cycle cursor mode: follow · flee · free
  space      — pause / resume
  +/-        — more / fewer boids
  t          — toggle the faint motion trails
  r          — reshuffle    q/esc — quit

    PYTHONPATH=src python examples/boids.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    App, T, b, col, row, card, dim_text, component, badge, grow,
    scroll_state, viewport,
)
from _halfblock import halfblock

# Flock colour by heading (hue wheel) so flocks moving together share a colour.
def hue(h, s=0.7, v=1.0):
    h = (h % (2 * math.pi)) / (2 * math.pi) * 6.0
    i = int(h) % 6
    f = h - int(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t),
               (p, q, v), (t, p, v), (v, p, q)][i]
    return (int(r * 255), int(g * 255), int(b * 255))


class Boid:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy


app = App("boids", inline=False, mouse=True, fps=60)

MODES = ["follow", "flee", "ignore"]

s = app.state(
    boids=[], pw=120, ph=60, target=90,
    mx=60.0, my=30.0, mode=0, trails=True, paused=False,
    scatter=None, scatter_t=0,
    vp=scroll_state(),       # records the field's painted rect for hit-testing
    have_mouse=False,        # only draw the cursor marker once we've seen one
    hover_armed=False,       # has any-motion mouse (1003) been enabled yet?
)


def reshuffle(st):
    st.boids = [
        Boid(random.uniform(0, st.pw), random.uniform(0, st.ph),
             random.uniform(-1, 1), random.uniform(-1, 1))
        for _ in range(st.target)
    ]


reshuffle(s)


def maintain(st):
    n = len(st.boids)
    if n < st.target:
        for _ in range(st.target - n):
            st.boids.append(Boid(random.uniform(0, st.pw), random.uniform(0, st.ph),
                                 random.uniform(-1, 1), random.uniform(-1, 1)))
    elif n > st.target:
        del st.boids[st.target:]


def limit(vx, vy, m):
    sp = math.hypot(vx, vy)
    if sp > m:
        vx, vy = vx / sp * m, vy / sp * m
    return vx, vy


def step(st):
    if st.paused:
        return
    bs = st.boids
    R = 9.0          # neighbour radius
    R2 = R * R
    SEP = 4.5
    SEP2 = SEP * SEP
    maxspeed = 1.8   # px/frame (fps=60 → ~108 px/s, smooth and not too fast)
    w, h = st.pw, st.ph

    # spatial hashing keeps it ~O(n) instead of O(n^2)
    cell = 10
    grid = {}
    for bd in bs:
        key = (int(bd.x) // cell, int(bd.y) // cell)
        grid.setdefault(key, []).append(bd)

    for bd in bs:
        cx, cy = int(bd.x) // cell, int(bd.y) // cell
        sepx = sepy = alx = aly = cohx = cohy = 0.0
        n = 0
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for o in grid.get((gx, gy), ()):
                    if o is bd:
                        continue
                    dx, dy = o.x - bd.x, o.y - bd.y
                    d2 = dx * dx + dy * dy
                    if d2 > R2 or d2 == 0:
                        continue
                    n += 1
                    alx += o.vx; aly += o.vy
                    cohx += o.x;  cohy += o.y
                    if d2 < SEP2:
                        sepx -= dx / d2
                        sepy -= dy / d2
        ax = ay = 0.0
        if n:
            alx /= n; aly /= n
            ax += (alx - bd.vx) * 0.05
            ay += (aly - bd.vy) * 0.05
            cohx = cohx / n - bd.x
            cohy = cohy / n - bd.y
            ax += cohx * 0.0015
            ay += cohy * 0.0015
        ax += sepx * 0.20
        ay += sepy * 0.20

        # cursor influence — distance-weighted so the flock clearly converges
        # on (or flees from) the mouse. Always active when a cursor is tracked.
        mode = MODES[st.mode]
        if mode != "ignore" and st.have_mouse:
            dx, dy = st.mx - bd.x, st.my - bd.y
            dd = math.hypot(dx, dy) + 1e-3
            if mode == "follow":
                # gentle far, firmer near — a smooth lead
                ax += dx / dd * 0.06
                ay += dy / dd * 0.06
            elif mode == "flee" and dd < 36:
                push = (1.0 - dd / 36) * 0.45     # strong close, fades to 0
                ax -= dx / dd * push
                ay -= dy / dd * push

        # transient scatter burst (left-click)
        if st.scatter and st.scatter_t > 0:
            sx, sy = st.scatter
            dx, dy = bd.x - sx, bd.y - sy
            dd = math.hypot(dx, dy) + 1e-3
            if dd < 30:
                ax += dx / dd * 0.6
                ay += dy / dd * 0.6

        bd.vx, bd.vy = limit(bd.vx + ax, bd.vy + ay, maxspeed)
        bd.x = (bd.x + bd.vx) % w
        bd.y = (bd.y + bd.vy) % h

    if st.scatter_t > 0:
        st.scatter_t -= 1


def draw_field(st):
    import shutil
    # Prefer the viewport's real painted height (recorded last frame) so the
    # field is exactly as tall as what's on screen and fully clickable.
    _, _, _, vph = st.vp.viewport_bounds
    if vph > 0:
        cell_h = vph
    else:
        term = shutil.get_terminal_size(fallback=(80, 24))
        cell_h = max(6, term.lines - 8)

    def render(w, h):
        pw = min(600, max(8, w))
        ph = cell_h * 2
        if pw != st.pw or ph != st.ph:
            sx = pw / st.pw if st.pw else 1
            sy = ph / st.ph if st.ph else 1
            for bd in st.boids:
                bd.x *= sx; bd.y *= sy
            st.pw, st.ph = pw, ph

        grid = [[None] * pw for _ in range(ph)]

        # boid body + a short heading-coloured streak behind it (motion blur)
        for bd in st.boids:
            head = math.atan2(bd.vy, bd.vx)
            col = hue(head)
            ix, iy = int(bd.x), int(bd.y)
            if 0 <= ix < pw and 0 <= iy < ph:
                grid[iy][ix] = col
            if st.trails:
                dim = (col[0] // 2, col[1] // 2, col[2] // 2)
                for k in (1, 2, 3):
                    tx = int(bd.x - bd.vx * k * 1.4)
                    ty = int(bd.y - bd.vy * k * 1.4)
                    if 0 <= tx < pw and 0 <= ty < ph and grid[ty][tx] is None:
                        f = 1.0 - k / 4.0
                        grid[ty][tx] = (int(dim[0] * f), int(dim[1] * f), int(dim[2] * f))

        # cursor marker (only once we've actually tracked the mouse over field)
        mode = MODES[st.mode]
        if mode != "ignore" and st.have_mouse:
            mxc = (255, 90, 90) if mode == "flee" else (120, 230, 255)
            for oy in range(-1, 2):
                for ox in range(-1, 2):
                    gx, gy = int(st.mx) + ox, int(st.my) + oy
                    if 0 <= gx < pw and 0 <= gy < ph and (ox == 0 or oy == 0):
                        grid[gy][gx] = mxc

        return halfblock(grid, bg=(10, 12, 20))

    # Wrap in a viewport so its painted rect is recorded for precise hit-test.
    field = component(render, grow=1, height=cell_h)
    return viewport(field, st.vp, grow=1, height=cell_h)


def field_xy(st, col_, row_):
    """Screen cell → field pixel using the viewport's real painted rect.
    Returns None outside the field. No hardcoded offsets."""
    x, y, w, h = st.vp.viewport_bounds
    if w == 0 and h == 0:
        return None
    cx = (col_ - 1) - x
    cy = (row_ - 1) - y
    if not (0 <= cx < w and 0 <= cy < h):
        return None
    return (max(0, min(st.pw - 1, cx)), max(0, min(st.ph - 1, cy * 2 + 1)))


@app.on_mouse
def _mouse(st, ev):
    pos = maya.mouse_pos(ev)
    if pos:
        xy = field_xy(st, pos[0], pos[1])
        if xy is not None:
            st.mx, st.my = xy
            st.have_mouse = True


@app.on_click("left")
def _click(st, c, r):
    xy = field_xy(st, c, r)
    if xy is None:
        return
    st.scatter = xy
    st.scatter_t = 12


@app.on("m")
def _mode(st): st.mode = (st.mode + 1) % len(MODES)


@app.on("t")
def _trails(st): st.trails = not st.trails


@app.on("space")
def _pause(st): st.paused = not st.paused


@app.on("+", "=")
def _more(st): st.target = min(400, st.target + 30); maintain(st)


@app.on("-", "_")
def _fewer(st): st.target = max(10, st.target - 30); maintain(st)


@app.on("r")
def _re(st): reshuffle(st)


@app.on("q", "esc")
def _quit(st): app.stop()


@app.view
def view(st):
    # Enable any-motion mouse tracking (1003) ONCE, after maya's own mouse setup
    # has run (first view frame). maya only enables 1002 = drag-motion, so plain
    # hover would send nothing; 1003 makes moving the mouse lead the flock with
    # no button held. Restored to 1002-only on quit via the finally block below.
    if not st.hover_armed:
        sys.stdout.write("\x1b[?1003h")
        sys.stdout.flush()
        st.hover_armed = True

    step(st)
    mode = MODES[st.mode]
    mode_badge = {
        "follow": badge("follow", kind="success"),
        "flee": badge("flee", kind="error"),
        "ignore": badge("free", kind=""),
    }[mode]

    header = row(
        b("boids").fg("cyan"),
        dim_text(f"{len(st.boids)} birds · {st.pw}×{st.ph}px"),
        mode_badge,
        badge("trails" if st.trails else "no-trails",
              kind="info" if st.trails else ""),
        badge("paused", kind="warning") if st.paused else dim_text("flowing"),
        gap=2, justify="between",
    )

    body = grow(card(draw_field(st), border="round", border_color="slate",
                     pad=0, grow=1))

    return card(
        header,
        body,
        dim_text("move mouse follow · click scatter · m mode · t trails · "
                 "+/- birds · space pause · r reshuffle · q quit"),
        title="flocking", gap=1, height="100%",
    )


if __name__ == "__main__":
    try:
        app.run()
    finally:
        # drop any-motion tracking; maya restores the rest on its own exit path
        sys.stdout.write("\x1b[?1003l")
        sys.stdout.flush()
