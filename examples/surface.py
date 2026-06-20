"""surface.py — the Surface drawing DSL: braille charts in a few clean lines.

`Surface` is maya-py's native braille/character drawing grid. It runs entirely
in C++ (set thousands of cells per frame with no Python per-pixel cost) and is
driven by a fluent API:

  • `s.box(...)` / `s.write(...)` / `s.hline(...)`     — cell-space glyphs
  • `s.pen(x, y, w, h)` / `s.panel(...)`              — a braille Pen over a region
  • `pen.curve(fn)` / `pen.fill_between(fn, ...)`     — plot/flood a function
  • `pen.path(pts)` / `pen.points(pts)` / `pen.ring`  — batch primitives
  • `ramp([a, b, c], n)`                              — a colour gradient table

Everything chains and every colour accepts name / (r,g,b) / "#rrggbb".

    PYTHONPATH=src python examples/surface.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, Surface, ramp, col, row, b, dim_text  # noqa: E402

W, H = 58, 11


def draw(w, h, t):
    s = Surface(w, h, bg="#0a0e16")

    # ── a filled, gradient-shaded sine wave ──────────────────────────────
    wave = s.panel(0, 0, w, h, fg="slate", title=" SURFACE DSL ")
    glow = ramp(["#00e5ff", "#0a0e16"], 8)        # accent → bg fade
    wave.fill_between(
        lambda px: 0.5 - 0.42 * math.sin(px / wave.pw * math.tau * 3 + t * 2),
        0.5, ramp_fg=glow,
        line_fg="#00e5ff", thick=2,
    )

    # ── a second phase-shifted line on top (one native polyline) ─────────
    pts = []
    for px in range(0, wave.pw, 2):
        v = 0.5 - 0.30 * math.sin(px / wave.pw * math.tau * 2 - t * 1.3)
        pts += [px, int(v * (wave.ph - 1))]
    wave.path(pts, fg="#ff3d81")

    # ── a little orbiting ring + blip cluster ────────────────────────────
    cx, cy = wave.pw - 18, wave.ph // 2
    wave.ring(cx, cy, 10, 10, fg="#3a4252")
    blips = []
    for k in range(6):
        a = t * 1.5 + k * math.tau / 6
        blips += [int(cx + math.cos(a) * 10), int(cy + math.sin(a) * 10)]
    wave.points(blips, fg="#ffd166")

    return s


app = App("surface", inline=True, fps=30, t=0.0)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _tick(s, dt):
    s.t += dt


@app.view
def view(s):
    return col(
        row(b("Surface"), dim_text("— native braille drawing, fluent DSL"), gap=1),
        draw(W, H, s.t).element(),
        dim_text("q quit"),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
