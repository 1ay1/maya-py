"""fluid.py — FLUID: 2D Navier-Stokes smoke simulation.

A faithful port of maya's `examples/fluid.cpp`. A real-time, real-fluid
solver — Jos Stam's "Stable Fluids" (Gauss-Seidel diffuse + semi-Lagrangian
advect + Helmholtz pressure projection, 10 iterations each) — rendered with
half-block characters for 2x vertical resolution through maya's native
`halfblock` surface. Five palettes (FIRE / OCEAN / NEON / SMOKE / RAINBOW),
adjustable viscosity, and mouse-drag injection of density + velocity.

The C++ original runs the solver on a full-terminal grid at 30fps. Pure-Python
per-cell loops over a 10-iteration Gauss-Seidel solver are far slower, so this
port CAPS the simulation grid with a fixed N×M (module constants below) so the
frame time stays bounded regardless of terminal size. The solver MATH is
byte-for-byte faithful — only the resolution is bounded.

Mouse: real left-drag injects density + velocity (wired via @app.on_mouse).
When no drag is happening, an auto "stir" source is injected each frame so the
simulation is always visibly alive (this auto-source is an addition over the
C++, noted in `_auto_stir`); drag to take over.

  Keys: 1-5 palette · +/- viscosity · space pause · r reset · q/Esc quit

    PYTHONPATH=src python examples/fluid.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya  # noqa: E402
from maya_py import App, T, col, component, halfblock, row  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────

DT = 0.1
ITER = 10

# The solver runs a 10-iteration Gauss-Seidel sweep over every interior cell,
# four times per frame — O(N*M*ITER) per frame in pure Python. We CAP the grid
# at a fixed size (independent of terminal size) so frame time stays bounded;
# the half-block field is emitted at this size. Raise these for more detail at
# lower framerate. (The C++ uses the full terminal grid.)
GRID_N = 60   # grid width  (cells)
GRID_M = 40   # grid height (cells, = display rows * 2 for half-blocks)


# ── Palettes ─────────────────────────────────────────────────────────────────
# Each palette maps density 0..4 to five color stops (byte-faithful to C++).

PALETTES = [
    ("FIRE",    [(0, 0, 0), (140, 20, 0), (220, 100, 0), (255, 220, 50), (255, 255, 255)]),
    ("OCEAN",   [(0, 0, 0), (0, 20, 100), (0, 80, 140), (0, 200, 220), (255, 255, 255)]),
    ("NEON",    [(0, 0, 0), (80, 0, 120), (180, 0, 180), (255, 80, 200), (255, 255, 255)]),
    ("SMOKE",   [(0, 0, 0), (40, 40, 40), (100, 100, 100), (180, 180, 180), (255, 255, 255)]),
    ("RAINBOW", [(0, 0, 0), (255, 0, 80), (0, 200, 100), (80, 120, 255), (255, 255, 255)]),
]


def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp_rgb(a, b, t):
    t = clampf(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def density_to_color(d, palette):
    stops = PALETTES[palette][1]
    d = clampf(d, 0.0, 5.0)
    t = d / 5.0 * 4.0           # map [0,5] -> [0,4]
    seg = min(int(t), 3)
    frac = t - seg
    return lerp_rgb(stops[seg], stops[seg + 1], frac)


# ── State ────────────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.N = 0
        self.M = 0
        self.palette = 0
        self.paused = False
        self.visc = 0.0001
        self.diff = 0.0001
        self.dens = []
        self.dens0 = []
        self.vx = []
        self.vy = []
        self.vx0 = []
        self.vy0 = []
        # Mouse state
        self.mouse_down = False
        self.mouse_x = -1
        self.mouse_y = -1
        self.prev_mx = -1
        self.prev_my = -1
        # Auto-stir phase (addition over C++ so the sim is alive without input)
        self.t = 0.0


G = World()


def IX(x, y):
    return y * G.N + x


# ── Fluid solver (Jos Stam "Stable Fluids") ──────────────────────────────────

def set_bnd(b, x):
    N, M = G.N, G.M
    for i in range(1, N - 1):
        x[IX(i, 0)] = -x[IX(i, 1)] if b == 2 else x[IX(i, 1)]
        x[IX(i, M - 1)] = -x[IX(i, M - 2)] if b == 2 else x[IX(i, M - 2)]
    for j in range(1, M - 1):
        x[IX(0, j)] = -x[IX(1, j)] if b == 1 else x[IX(1, j)]
        x[IX(N - 1, j)] = -x[IX(N - 2, j)] if b == 1 else x[IX(N - 2, j)]
    x[IX(0, 0)] = 0.5 * (x[IX(1, 0)] + x[IX(0, 1)])
    x[IX(0, M - 1)] = 0.5 * (x[IX(1, M - 1)] + x[IX(0, M - 2)])
    x[IX(N - 1, 0)] = 0.5 * (x[IX(N - 2, 0)] + x[IX(N - 1, 1)])
    x[IX(N - 1, M - 1)] = 0.5 * (x[IX(N - 2, M - 1)] + x[IX(N - 1, M - 2)])


def diffuse(b, x, x0, diff):
    N, M = G.N, G.M
    a = DT * diff * (N - 2) * (M - 2)
    c = 1.0 + 4.0 * a
    inv_c = 1.0 / c
    for _ in range(ITER):
        for j in range(1, M - 1):
            base = j * N
            up = base - N
            dn = base + N
            for i in range(1, N - 1):
                x[base + i] = (x0[base + i] + a * (
                    x[base + i - 1] + x[base + i + 1] +
                    x[up + i] + x[dn + i])) * inv_c
        set_bnd(b, x)


def advect(b, d, d0, vx, vy):
    N, M = G.N, G.M
    dt0x = DT * (N - 2)
    dt0y = DT * (M - 2)
    for j in range(1, M - 1):
        base = j * N
        for i in range(1, N - 1):
            x = i - dt0x * vx[base + i]
            y = j - dt0y * vy[base + i]
            x = clampf(x, 0.5, N - 1.5)
            y = clampf(y, 0.5, M - 1.5)
            i0 = int(x)
            j0 = int(y)
            i1 = i0 + 1
            j1 = j0 + 1
            s1 = x - i0
            s0 = 1.0 - s1
            t1 = y - j0
            t0 = 1.0 - t1
            d[base + i] = (s0 * (t0 * d0[j0 * N + i0] + t1 * d0[j1 * N + i0])
                           + s1 * (t0 * d0[j0 * N + i1] + t1 * d0[j1 * N + i1]))
    set_bnd(b, d)


def project(vx, vy, p, div):
    N, M = G.N, G.M
    hx = 1.0 / (N - 2)
    hy = 1.0 / (M - 2)
    for j in range(1, M - 1):
        base = j * N
        up = base - N
        dn = base + N
        for i in range(1, N - 1):
            div[base + i] = -0.5 * (
                hx * (vx[base + i + 1] - vx[base + i - 1]) +
                hy * (vy[dn + i] - vy[up + i]))
            p[base + i] = 0.0
    set_bnd(0, div)
    set_bnd(0, p)

    for _ in range(ITER):
        for j in range(1, M - 1):
            base = j * N
            up = base - N
            dn = base + N
            for i in range(1, N - 1):
                p[base + i] = (div[base + i] +
                               p[base + i - 1] + p[base + i + 1] +
                               p[up + i] + p[dn + i]) / 4.0
        set_bnd(0, p)

    for j in range(1, M - 1):
        base = j * N
        up = base - N
        dn = base + N
        for i in range(1, N - 1):
            vx[base + i] -= 0.5 * (p[base + i + 1] - p[base + i - 1]) * (N - 2)
            vy[base + i] -= 0.5 * (p[dn + i] - p[up + i]) * (M - 2)
    set_bnd(1, vx)
    set_bnd(2, vy)


def step():
    # Velocity step
    G.vx, G.vx0 = G.vx0, G.vx
    diffuse(1, G.vx, G.vx0, G.visc)
    G.vy, G.vy0 = G.vy0, G.vy
    diffuse(2, G.vy, G.vy0, G.visc)
    project(G.vx, G.vy, G.vx0, G.vy0)

    G.vx, G.vx0 = G.vx0, G.vx
    G.vy, G.vy0 = G.vy0, G.vy
    advect(1, G.vx, G.vx0, G.vx0, G.vy0)
    advect(2, G.vy, G.vy0, G.vx0, G.vy0)
    project(G.vx, G.vy, G.vx0, G.vy0)

    # Density step
    G.dens, G.dens0 = G.dens0, G.dens
    diffuse(0, G.dens, G.dens0, G.diff)
    G.dens, G.dens0 = G.dens0, G.dens
    advect(0, G.dens, G.dens0, G.vx, G.vy)

    # Clamp density
    dens = G.dens
    for k in range(len(dens)):
        dens[k] = clampf(dens[k], 0.0, 5.0)


# ── Add sources from mouse ──────────────────────────────────────────────────

def add_source():
    if not G.mouse_down or G.mouse_x < 0:
        return
    cx = G.mouse_x
    cy = G.mouse_y
    if cx < 1 or cx >= G.N - 1 or cy < 1 or cy >= G.M - 1:
        return

    # Density burst
    radius = 3
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx = cx + dx
            ny = cy + dy
            if nx < 1 or nx >= G.N - 1 or ny < 1 or ny >= G.M - 1:
                continue
            dist = math.sqrt(float(dx * dx + dy * dy))
            if dist > radius:
                continue
            strength = (1.0 - dist / radius) * 2.0
            G.dens[IX(nx, ny)] += strength

    # Velocity from drag direction
    if G.prev_mx >= 0:
        dvx = float(cx - G.prev_mx) * 5.0
        dvy = float(cy - G.prev_my) * 5.0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx = cx + dx
                ny = cy + dy
                if nx < 1 or nx >= G.N - 1 or ny < 1 or ny >= G.M - 1:
                    continue
                G.vx[IX(nx, ny)] += dvx
                G.vy[IX(nx, ny)] += dvy
    G.prev_mx = cx
    G.prev_my = cy


def _auto_stir():
    # ADDITION over the C++: when nobody is dragging, inject a moving source so
    # the sim is visibly alive. Mimics a mouse drag through `add_source`'s
    # injection math (same radius/strength), driven by a Lissajous path.
    if G.mouse_down:
        return
    G.t += DT
    cx = int(G.N * 0.5 + (G.N * 0.30) * math.sin(G.t * 0.7))
    cy = int(G.M * 0.5 + (G.M * 0.30) * math.cos(G.t * 0.5))
    if cx < 1 or cx >= G.N - 1 or cy < 1 or cy >= G.M - 1:
        return
    radius = 3
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx = cx + dx
            ny = cy + dy
            if nx < 1 or nx >= G.N - 1 or ny < 1 or ny >= G.M - 1:
                continue
            dist = math.sqrt(float(dx * dx + dy * dy))
            if dist > radius:
                continue
            strength = (1.0 - dist / radius) * 2.0
            G.dens[IX(nx, ny)] += strength
    # Velocity along the tangent of the path
    dvx = math.cos(G.t * 0.7) * 4.0
    dvy = -math.sin(G.t * 0.5) * 4.0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx = cx + dx
            ny = cy + dy
            if nx < 1 or nx >= G.N - 1 or ny < 1 or ny >= G.M - 1:
                continue
            G.vx[IX(nx, ny)] += dvx
            G.vy[IX(nx, ny)] += dvy


# ── Resize / reset ──────────────────────────────────────────────────────────

def resize_grid(N, M):
    G.N = max(4, N)
    G.M = max(4, M)
    sz = G.N * G.M
    G.dens = [0.0] * sz
    G.dens0 = [0.0] * sz
    G.vx = [0.0] * sz
    G.vy = [0.0] * sz
    G.vx0 = [0.0] * sz
    G.vy0 = [0.0] * sz


resize_grid(GRID_N, GRID_M)


# ── App ──────────────────────────────────────────────────────────────────────

app = App("fluid", inline=False, fps=30, mouse=True)
app.state(_t=0.0)


@app.on("space")
def _pause(s):
    G.paused = not G.paused


@app.on("r")
def _reset(s):
    resize_grid(G.N, G.M)


@app.on("+", "=")
def _visc_up(s):
    G.visc = min(G.visc * 2.0, 0.01)


@app.on("-")
def _visc_dn(s):
    G.visc = max(G.visc * 0.5, 0.00001)


def _mk_pal(idx):
    def _pal(s):
        G.palette = idx
    return _pal


for _i in range(5):
    app.on(str(_i + 1))(_mk_pal(_i))


@app.on("q", "esc")
def _quit(s):
    app.stop()


# Mouse: real left-drag injects density + velocity. The fluid grid is fixed
# size (GRID_N x GRID_M); the display box is fixed too, so we map the reported
# cell to grid coords by scaling, with row*2 for the half-block vertical res.
@app.on_mouse
def _mouse(s, ev):
    pos = maya.mouse_pos(ev)
    if maya.mouse_clicked(ev):
        G.mouse_down = True
        if pos:
            G.mouse_x = pos[0]
            G.mouse_y = pos[1] * 2
            G.prev_mx = G.mouse_x
            G.prev_my = G.mouse_y
    elif maya.mouse_released(ev):
        G.mouse_down = False
        G.prev_mx = -1
        G.prev_my = -1
    elif maya.mouse_moved(ev) and G.mouse_down:
        if pos:
            G.mouse_x = pos[0]
            G.mouse_y = pos[1] * 2


@app.on_frame
def _frame(s, dt):
    if not G.paused:
        add_source()
        _auto_stir()
        step()


def _field(w, h):
    # The grid is a FIXED GRID_N x GRID_M (bounded frame time); emit it as
    # half-blocks at its natural size — each display row = 2 fluid rows.
    pal = G.palette
    fluid_rows = G.M // 2
    grid = [[None] * G.N for _ in range(fluid_rows)]
    dens = G.dens
    for ty in range(fluid_rows):
        fy_top = ty * 2
        fy_bot = ty * 2 + 1
        rowg = grid[ty]
        base_top = fy_top * G.N
        base_bot = fy_bot * G.N
        for x in range(G.N):
            d_top = dens[base_top + x]
            d_bot = dens[base_bot + x] if fy_bot < G.M else 0.0
            rowg[x] = density_to_color(d_top, pal) if d_top > 0.02 else (0, 0, 0)
            # halfblock takes a single grid; encode top/bot via two rows.
    # Build a full M-row color grid (top + bottom interleaved) so halfblock
    # pairs them correctly into ▀ glyphs.
    full = [[None] * G.N for _ in range(G.M)]
    for fy in range(G.M):
        base = fy * G.N
        fr = full[fy]
        for x in range(G.N):
            d = dens[base + x]
            fr[x] = density_to_color(d, pal) if d > 0.02 else (0, 0, 0)
    return halfblock(full)


@app.view
def view(s):
    pal_name = PALETTES[G.palette][0]
    status = row(
        T(f" FLUID │ drag=add │ [1-5] palette │ [r] reset │ "
          f"[+/-] visc:{G.visc:.5f} │ [spc] "
          f"{'paused' if G.paused else 'run'} ").fg((180, 180, 180)).bold,
        T(f"  {pal_name}  ").fg((120, 200, 255)).bold,
        T("[q] quit").fg((90, 90, 90)),
        gap=0,
    )
    return col(component(_field, grow=1), status, gap=0)


if __name__ == "__main__":
    app.run()
