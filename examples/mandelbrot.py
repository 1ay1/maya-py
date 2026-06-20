"""mandelbrot.py — Mandelbrot fractal explorer.

A faithful port of maya's `examples/mandelbrot.cpp`. A real-time Mandelbrot
renderer with smooth iteration colouring, auto-zoom toward Seahorse Valley, six
switchable palettes, and half-block pixels for 2x vertical resolution, rendered
through maya's native half-block surface.

The C++ original threads the per-pixel escape-time loop across every CPU core.
This port keeps the math faithful but runs it in pure Python, so it renders a
small CAPPED buffer (bounded frame time) — a low-resolution explorer rather
than a 30fps one. Raise MAX_PW/MAX_PH for more detail at lower framerate.

  Keys: arrows pan · +/- zoom · space toggle auto-zoom · 1-6 palette
        r reset · q/Esc quit

    PYTHONPATH=src python examples/mandelbrot.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, box, col, component, halfblock, row, upscale, target_size  # noqa: E402

MAX_PW = 60
MAX_PH = 36
MAX_ITER = 512
TAU = 6.28318530

TARGET_X = -0.7463
TARGET_Y = 0.1102
ZOOM_SPEED = 0.015
PAN_SPEED = 0.02

PAL_NAMES = ["ultra", "fire", "ocean", "neon", "gray", "rainbow"]


def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def clampi(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class World:
    def __init__(self):
        self.cx = -0.5
        self.cy = 0.0
        self.zoom = 1.0
        self.palette = 0
        self.auto = True
        self.frame = 0
        self.elapsed = 0.0
        self.iter_count = MAX_ITER


W = World()


# ── Color math ───────────────────────────────────────────────────────────────

def hsv(h, s, v):
    h = math.fmod(h, 1.0)
    if h < 0:
        h += 1.0
    c = v * s
    x = c * (1.0 - abs(math.fmod(h * 6.0, 2.0) - 1.0))
    m = v - c
    if h < 1 / 6:
        r, g, b = c, x, 0
    elif h < 2 / 6:
        r, g, b = x, c, 0
    elif h < 3 / 6:
        r, g, b = 0, c, x
    elif h < 4 / 6:
        r, g, b = 0, x, c
    elif h < 5 / 6:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (r + m, g + m, b + m)


def cosine_palette(t, a, b, c, d):
    return (
        clampf(a[0] + b[0] * math.cos(TAU * (c[0] * t + d[0])), 0, 1),
        clampf(a[1] + b[1] * math.cos(TAU * (c[1] * t + d[1])), 0, 1),
        clampf(a[2] + b[2] * math.cos(TAU * (c[2] * t + d[2])), 0, 1),
    )


def palette_ultra(t):
    return cosine_palette(t, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5),
                          (1.0, 1.0, 1.0), (0.0, 0.10, 0.20))


def palette_fire(t):
    if t < 0.33:
        s = t / 0.33
        return (s, s * 0.15, 0.0)
    if t < 0.66:
        s = (t - 0.33) / 0.33
        return (1.0, 0.15 + s * 0.65, 0.0)
    s = (t - 0.66) / 0.34
    return (1.0, 0.8 + s * 0.2, s)


def palette_ocean(t):
    if t < 0.5:
        s = t / 0.5
        return (0.0, s * 0.4, 0.15 + s * 0.55)
    s = (t - 0.5) / 0.5
    return (s * 0.7, 0.4 + s * 0.6, 0.7 + s * 0.3)


def palette_neon(t):
    return cosine_palette(t, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5),
                          (1.0, 1.0, 0.5), (0.80, 0.20, 0.50))


def palette_gray_bands(t):
    gray = t
    band = math.sin(t * 40.0)
    if band > 0.85:
        return (0.2 + gray * 0.6, 0.1 + gray * 0.3, 0.05)
    if band < -0.85:
        return (0.05, 0.1 + gray * 0.3, 0.2 + gray * 0.6)
    return (gray, gray, gray)


def palette_rainbow(t):
    return hsv(t, 0.85, 0.9)


PALETTES = [palette_ultra, palette_fire, palette_ocean, palette_neon,
            palette_gray_bands, palette_rainbow]


def get_color(smooth_iter):
    if smooth_iter < 0:
        return (0, 0, 0)
    t = math.fmod(smooth_iter / 64.0, 1.0)
    r, g, b = PALETTES[W.palette](t)
    return (int(r * 255), int(g * 255), int(b * 255))


# ── Mandelbrot ───────────────────────────────────────────────────────────────

def mandelbrot(cr, ci):
    q = (cr - 0.25) * (cr - 0.25) + ci * ci
    if q * (q + (cr - 0.25)) <= 0.25 * ci * ci:
        return -1.0
    if (cr + 1.0) * (cr + 1.0) + ci * ci <= 0.0625:
        return -1.0
    zr = zi = zr2 = zi2 = 0.0
    iters = W.iter_count
    it = 0
    while it < iters and zr2 + zi2 <= 256.0:
        zi = 2.0 * zr * zi + ci
        zr = zr2 - zi2 + cr
        zr2 = zr * zr
        zi2 = zi * zi
        it += 1
    if it >= iters:
        return -1.0
    abs_z = math.sqrt(zr2 + zi2)
    return it + 1.0 - math.log2(math.log2(abs_z))


def tick(dt):
    w = W
    w.frame += 1
    w.elapsed += dt
    if w.auto:
        w.cx += (TARGET_X - w.cx) * PAN_SPEED
        w.cy += (TARGET_Y - w.cy) * PAN_SPEED
        w.zoom *= (1.0 - ZOOM_SPEED)
        if w.zoom < 1e-13:
            w.cx, w.cy, w.zoom = -0.5, 0.0, 1.0
    w.iter_count = clampi(int(256 + 40 * math.log2(1.0 / w.zoom)), 256, MAX_ITER)


def _field(w, h):
    # Compute a small CAPPED buffer (bounded frame time), then upscale to fill
    # the whole half-block field so the fractal fills the screen exactly like
    # the threaded C++ original. The aspect uses the OUTPUT dims so the framing
    # matches; raise MAX_PW/MAX_PH to trade fps for detail.
    out_w, out_h = target_size(w, h)
    pw = max(1, min(MAX_PW, out_w))
    ph = max(2, min(MAX_PH, out_h))
    if ph % 2:
        ph += 1
    aspect = out_w / out_h
    grid = [[None] * pw for _ in range(ph)]
    for py in range(ph):
        v = (2.0 * (py + 0.5) / ph - 1.0)
        ci = W.cy + v * W.zoom
        rowg = grid[py]
        for px in range(pw):
            u = (2.0 * (px + 0.5) / pw - 1.0) * aspect
            cr = W.cx + u * W.zoom
            rowg[px] = get_color(mandelbrot(cr, ci))
    return halfblock(upscale(grid, out_w, out_h))


# ── App ──────────────────────────────────────────────────────────────────────

app = App("MANDELBROT", inline=False, fps=30)
app.state(_t=0.0)


for _p in range(1, 7):
    def _mk(p):
        def _pal(s):
            W.palette = p - 1
        return _pal
    app.on(str(_p))(_mk(_p))


@app.on("+", "=")
def _zoomin(s):
    W.zoom *= 0.8


@app.on("-")
def _zoomout(s):
    W.zoom *= 1.25


@app.on("left")
def _left(s):
    W.cx -= W.zoom * 0.1


@app.on("right")
def _right(s):
    W.cx += W.zoom * 0.1


@app.on("up")
def _up(s):
    W.cy -= W.zoom * 0.1


@app.on("down")
def _down(s):
    W.cy += W.zoom * 0.1


@app.on("space")
def _auto(s):
    W.auto = not W.auto


@app.on("r")
def _reset(s):
    W.cx, W.cy, W.zoom, W.auto = -0.5, 0.0, 1.0, True


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 30.0)


@app.view
def view(s):
    status = row(
        T(f" MANDELBROT │ {W.cx:.4e} + {W.cy:.4e}i │ "
          f"zoom:{1.0 / W.zoom:.2e} │ iter:{W.iter_count} │ "
          f"{PAL_NAMES[W.palette]}{' [auto]' if W.auto else ''}").fg((80, 180, 255)).bold,
        T("   [1-6] pal [+-] zoom [spc] auto [r] reset [q] quit").fg((70, 70, 70)),
        gap=0,
    )
    return col(box(component(_field, grow=1)), status, gap=0)


if __name__ == "__main__":
    app.run()
