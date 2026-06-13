"""gravity.py — an interactive, RESPONSIVE gravity-well sandbox.

A live n-body toy that grows to fill the terminal. Two gravity wells pull a
swarm of glowing particles around the field; particles shift colour by speed
(cool blue when drifting, hot white/orange when whipping past a well). The
play-field auto-sizes to whatever the terminal gives it and re-flows on resize.

  click  — drop a burst of particles where you click
  space  — toggle the second (orbiting) well on/off
  g      — cycle gravity strength (weak · normal · strong · chaos)
  +/-    — more / fewer particles
  r      — reset the swarm
  c      — clear all particles
  q/esc  — quit

Rendering uses the shared half-block helper (`▀`): each terminal cell shows two
vertical pixels, so a W×H-cell box becomes a W×(2H)-pixel field.

Run:  PYTHONPATH=src python examples/gravity.py
"""

from __future__ import annotations

import math
import random
import shutil
import sys

import maya_py as maya
from maya_py import (
    App, T, b, col, row, card, dim_text, component, badge, grow,
    scroll_state, viewport,
)
from maya_py import halfblock

# The field fills the WHOLE terminal in fullscreen mode. Each half-block cell
# is 2 pixels tall, so an H-cell box becomes a (2H)-pixel field. These are
# only first-frame fallbacks before the layout has measured the real size.
FALLBACK_W, FALLBACK_CELLS_H = 80, 20

# gravity presets: (label, G constant, soften radius)
GRAVITY = [
    ("weak",   28.0, 6.0),
    ("normal", 70.0, 5.0),
    ("strong", 150.0, 4.0),
    ("chaos",  300.0, 3.0),
]

# speed → colour ramp (slow → fast): deep blue, sky, lime, gold, white-hot
RAMP = [
    (40, 70, 160),
    (80, 150, 255),
    (120, 230, 140),
    (255, 200, 80),
    (255, 245, 230),
]


def ramp(t: float):
    """t in [0,1] → an (r,g,b) tuple along the speed ramp."""
    t = max(0.0, min(0.999, t))
    pos = t * (len(RAMP) - 1)
    i = int(pos)
    f = pos - i
    a, bb = RAMP[i], RAMP[i + 1]
    return tuple(int(a[k] + (bb[k] - a[k]) * f) for k in range(3))


class Particle:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy


def spawn_ring(n, cx, cy, r, spin):
    """A ring of `n` particles around (cx,cy) given a tangential spin speed."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n + random.uniform(-0.1, 0.1)
        rr = r * random.uniform(0.7, 1.15)
        px, py = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        # tangential velocity (perpendicular to the radius) → orbits, not falls
        tx, ty = -math.sin(a), math.cos(a)
        out.append(Particle(px, py, tx * spin, ty * spin))
    return out


app = App("gravity", inline=False, mouse=True, fps=30)


def field_scale(st):
    """Characteristic field size (px) used to make the sim scale-invariant."""
    return min(st.fw, st.fh)


def orbital_spin(st):
    """Initial tangential speed (px/frame) tuned so a body at the spawn ring
    roughly orbits — grows with the field so orbits look the same at any size."""
    return field_scale(st) * 0.06


def fresh(st):
    """Re-seed the swarm centred in the CURRENT field."""
    r = min(st.fw, st.fh) * 0.32
    st.parts = spawn_ring(st.target, st.fw / 2, st.fh / 2, r, orbital_spin(st))
    st.frame = 0


s = app.state(
    parts=[], frame=0,
    fw=FALLBACK_W, fh=FALLBACK_CELLS_H * 2,   # live field size in PIXELS
    target=160,                               # desired particle count
    grav=1,                                   # index into GRAVITY
    second=True,                              # second orbiting well on?
    last_click=None,
    vp=scroll_state(),                        # records the field's painted rect
    hover=None,                               # last mouse pos in pixel space
    hover_armed=False,                        # any-motion mouse (1003) enabled?
)
fresh(s)


def field_xy(st, col_, row_):
    """Map a 1-based screen click to FIELD PIXEL coords using the viewport's
    real painted rect — no hardcoded offsets. Returns None if outside the field.
    Half-blocks are 2px tall per cell, so y is doubled (and we resolve which of
    the two stacked pixels the click landed on isn't knowable, so centre it)."""
    x, y, w, h = st.vp.viewport_bounds
    if w == 0 and h == 0:
        return None
    cx = (col_ - 1) - x          # cell offset into the field
    cy = (row_ - 1) - y
    if not (0 <= cx < w and 0 <= cy < h):
        return None
    px = cx                       # field is 1 px per cell horizontally
    py = cy * 2 + 1               # centre of the 2-px cell vertically
    return (max(0, min(st.fw - 1, px)), max(0, min(st.fh - 1, py)))


def wells(st):
    """Current gravity wells in pixel space: (x, y, mass)."""
    cx, cy = st.fw / 2, st.fh / 2
    out = [(cx, cy, 1.0)]
    if st.second:
        a = st.frame * 0.045
        orbit = field_scale(st) * 0.28
        out.append((cx + math.cos(a) * orbit, cy + math.sin(a) * orbit, 0.7))
    return out


def step(st):
    _, G, soft = GRAVITY[st.grav]
    ws = wells(st)
    # Scale gravity by field size: acceleration ∝ G_strength * scale, so a body
    # halfway across the field feels the same relative pull at 60px or 400px.
    scale = field_scale(st)
    g_eff = G * scale * scale * 0.0008
    soft_px = soft / 64.0 * scale            # soften radius scales too
    soft2 = soft_px * soft_px
    w, h = st.fw, st.fh
    for p in st.parts:
        ax = ay = 0.0
        for wx, wy, wm in ws:
            dx, dy = wx - p.x, wy - p.y
            d2 = dx * dx + dy * dy + soft2
            inv = wm * g_eff / (d2 * math.sqrt(d2))
            ax += dx * inv
            ay += dy * inv
        p.vx = (p.vx + ax * 0.016) * 0.9995    # tiny drag keeps it bounded
        p.vy = (p.vy + ay * 0.016) * 0.9995
        p.x += p.vx * 0.5
        p.y += p.vy * 0.5
        # wrap at the edges so the swarm never fully escapes the field
        if p.x < 0: p.x += w
        elif p.x >= w: p.x -= w
        if p.y < 0: p.y += h
        elif p.y >= h: p.y -= h


def on_resize(st, new_w, new_h):
    """The terminal (and thus the field) changed size — rescale particle
    positions AND velocities in place so the swarm keeps its shape and orbital
    energy instead of snapping to a corner or stalling."""
    if new_w == st.fw and new_h == st.fh:
        return
    sx = new_w / st.fw if st.fw else 1.0
    sy = new_h / st.fh if st.fh else 1.0
    sv = (sx + sy) * 0.5          # uniform velocity rescale
    for p in st.parts:
        p.x *= sx
        p.y *= sy
        p.vx *= sv
        p.vy *= sv
    st.fw, st.fh = new_w, new_h


def maintain_count(st):
    """Grow/shrink the swarm toward st.target (after +/- or a big resize)."""
    n = len(st.parts)
    if n < st.target:
        st.parts.extend(
            spawn_ring(st.target - n, st.fw / 2, st.fh / 2,
                       field_scale(st) * 0.3, orbital_spin(st)))
    elif n > st.target:
        del st.parts[st.target:]


def draw_field(st):
    # Height: prefer the viewport's REAL painted height (recorded last frame);
    # fall back to a terminal-rows estimate on the very first frame. This keeps
    # the pixel field exactly as tall as what's on screen, so the whole field
    # is visible AND clickable (no off-fold rows).
    _, _, _, vph = st.vp.viewport_bounds
    if vph > 0:
        cell_h = vph
    else:
        term = shutil.get_terminal_size(fallback=(80, 24))
        cell_h = max(6, term.lines - 8)

    def render(w, h):
        # w is CELLS wide (real). Half-blocks pack 2 pixels per cell vertically;
        # cell_h is the field's fixed cell height for this frame.
        pw = min(600, max(8, w))
        ph = cell_h * 2
        on_resize(st, pw, ph)

        grid = [[None] * pw for _ in range(ph)]

        # particles first, coloured by speed; additive brighten on overlap
        for p in st.parts:
            ix, iy = int(p.x), int(p.y)
            if 0 <= ix < pw and 0 <= iy < ph:
                spd = math.hypot(p.vx, p.vy)
                r, g, bl = ramp(spd / 9.0)
                cur = grid[iy][ix]
                if cur is None:
                    grid[iy][ix] = (r, g, bl)
                else:
                    grid[iy][ix] = (min(255, cur[0] + r // 2),
                                    min(255, cur[1] + g // 2),
                                    min(255, cur[2] + bl // 2))

        # gravity wells LAST so they're never buried under the swarm. A pulsing
        # golden-white core with a soft radial halo, sized to the field.
        pulse = 0.75 + 0.25 * math.sin(st.frame * 0.18)
        rad = max(4, int(field_scale(st) * 0.05))    # halo radius in pixels
        for wx, wy, wm in wells(st):
            ix, iy = int(wx), int(wy)
            for oy in range(-rad, rad + 1):
                for ox in range(-rad, rad + 1):
                    gx, gy = ix + ox, iy + oy
                    if not (0 <= gx < pw and 0 <= gy < ph):
                        continue
                    d = math.hypot(ox, oy)
                    if d > rad:
                        continue
                    # falloff 1.0 at centre → 0 at the halo edge
                    fall = (1.0 - d / (rad + 1)) ** 2 * pulse * wm
                    add_r = int(255 * fall)
                    add_g = int(225 * fall)
                    add_b = int(140 * fall)
                    cur = grid[gy][gx] or (8, 8, 14)
                    grid[gy][gx] = (min(255, cur[0] + add_r),
                                    min(255, cur[1] + add_g),
                                    min(255, cur[2] + add_b))
            # blazing white centre pixel on top
            if 0 <= ix < pw and 0 <= iy < ph:
                grid[iy][ix] = (255, 250, 235)

        # hover crosshair — shows exactly where a click will spawn (precision)
        if st.hover is not None:
            hx, hy = int(st.hover[0]), int(st.hover[1])
            ring = (120, 230, 255)
            for ox in range(-3, 4):
                gx = hx + ox
                if 0 <= gx < pw and 0 <= hy < ph and abs(ox) > 1:
                    grid[hy][gx] = ring
            for oy in range(-3, 4):
                gy = hy + oy
                if 0 <= hx < pw and 0 <= gy < ph and abs(oy) > 1:
                    grid[gy][hx] = ring

        return halfblock(grid, bg=(8, 8, 14))

    # Wrap the field in a viewport so its painted rect is recorded into st.vp
    # each frame — the click handler hit-tests against that exact rect. grow=1
    # fills the row WIDTH; height is set explicitly (the box `h` maya reports
    # under fullscreen grow is the unbounded sentinel, not usable).
    field = component(render, grow=1, height=cell_h)
    return viewport(field, st.vp, grow=1, height=cell_h)


@app.on_mouse
def _hover(st, ev):
    pos = maya.mouse_pos(ev)
    if pos:
        st.hover = field_xy(st, pos[0], pos[1])


@app.on_click("left")
def _click(st, col_, row_):
    xy = field_xy(st, col_, row_)
    if xy is None:                 # clicked outside the field — ignore
        return
    px, py = xy
    burst = max(24, st.target // 6)
    st.parts.extend(spawn_ring(burst, px, py, 4, random.uniform(2.5, 4.5)))
    st.target = len(st.parts)
    st.last_click = (int(px), int(py))
    if len(st.parts) > 1400:        # hard cap
        del st.parts[:len(st.parts) - 1400]
        st.target = len(st.parts)


@app.on("space")
def _toggle(st): st.second = not st.second


@app.on("g")
def _grav(st): st.grav = (st.grav + 1) % len(GRAVITY)


@app.on("+", "=")
def _more(st):
    st.target = min(1400, st.target + 60)
    maintain_count(st)


@app.on("-", "_")
def _fewer(st):
    st.target = max(20, st.target - 60)
    maintain_count(st)


@app.on("r")
def _reset(st): fresh(st)


@app.on("c")
def _clear(st):
    st.parts = []
    st.target = 0


@app.on("q", "esc")
def _quit(st): app.stop()


@app.view
def view(st):
    # Enable any-motion mouse (1003) once so the hover crosshair tracks the
    # mouse with no button held (maya only enables 1002 = drag-motion).
    if not st.hover_armed:
        sys.stdout.write("\x1b[?1003h")
        sys.stdout.flush()
        st.hover_armed = True

    st.frame += 1
    step(st)

    gname, _, _ = GRAVITY[st.grav]
    well_badge = (badge("2 wells", kind="success") if st.second
                  else badge("1 well", kind="warning"))

    header = row(
        b("gravity").fg("sky"),
        dim_text(f"{len(st.parts)} bodies · {st.fw}×{st.fh}px"),
        well_badge,
        badge(gname, kind="info"),
        gap=2, justify="between",
    )

    legend = row(
        T("slow ").fg(maya.rgb(*RAMP[0])),
        T("▀▀▀").fg(maya.rgb(*RAMP[1])),
        T("▀▀▀").fg(maya.rgb(*RAMP[2])),
        T("▀▀▀").fg(maya.rgb(*RAMP[3])),
        T(" fast").fg(maya.rgb(*RAMP[4])),
        dim_text("  speed → colour"),
        gap=0,
    )

    # The field card grows to fill ALL remaining space (both axes) between the
    # header and footer, so the sandbox is truly fullscreen.
    body = grow(card(draw_field(st), border="round", border_color="slate",
                     pad=0, grow=1))

    return card(
        header,
        body,
        legend,
        dim_text("click spawn · space 2nd-well · g gravity · +/- bodies · r reset · c clear · q quit"),
        title="n-body sandbox", gap=1, height="100%",
    )


if __name__ == "__main__":
    try:
        app.run()
    finally:
        sys.stdout.write("\x1b[?1003l")   # drop any-motion tracking
        sys.stdout.flush()
