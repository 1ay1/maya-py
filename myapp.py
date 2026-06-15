"""An animated plasma field with a live status panel floating on top.

Ctrl+C to quit. Everything is time-driven (uses dt), so it runs at a
constant real-world speed regardless of fps.

  • a plasma field painted per-frame as half-blocks (2 px per cell row)
  • a status card centered over it via zstack + center
  • a braille spinner + cycling phase + elapsed clock
  • a gradient progress bar that loops, and a bouncing equalizer
"""
import math

import maya_py as maya
from maya_py import (
    animate, card, col, row, b, c, dim_text, zstack,
    progress, bar_chart, halfblock, gradient_at, fmt_duration,
)

SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
ACCENT = [(80, 200, 255), (130, 120, 255), (255, 120, 200)]      # sky→violet→pink
PLASMA = [(15, 25, 70), (120, 40, 160), (255, 90, 140), (70, 210, 230)]
PHASES = ["connecting", "fetching", "building", "finalizing"]

PW, PHPX = 72, 44        # plasma size: 72 cols × 44 px (= 22 cells tall)
PANEL_W = 40             # status card width (narrower, so plasma shows around it)
t = 0.0


def _g(x):                                      # gradient_at-safe: [0, 1)
    return 0.0 if x < 0 else 0.999999 if x >= 1 else x


# maya's StylePool interns every *distinct* color for the whole run and never
# evicts (canvas.hpp), so feeding it a fresh shade per cell per frame grows
# memory ~unbounded. We quantize each gradient to a small fixed palette and
# cache it, so the pool only ever sees `LEVELS` colors per gradient.
LEVELS = 48
_palettes = {}


def grad(stops, x):
    key = id(stops)
    lut = _palettes.get(key)
    if lut is None:
        lut = [gradient_at(stops, _g(i / LEVELS)) for i in range(LEVELS)]
        _palettes[key] = lut
    return lut[int(_g(x) * LEVELS)]


def plasma_grid():                              # 2-D grid of (r, g, b) pixels
    cx, cy = PW / 2, PHPX / 2
    grid = []
    for y in range(PHPX):
        rowpx = []
        for x in range(PW):
            v = (math.sin(x * 0.15 + t)
                 + math.sin(y * 0.15 + t * 1.1)
                 + math.sin((x + y) * 0.08 + t * 0.7)
                 + math.sin(math.hypot(x - cx, y - cy) * 0.15 - t * 1.3))
            rowpx.append(grad(PLASMA, (v + 4) / 8))
        grid.append(rowpx)
    return grid


def render(dt):
    global t
    t += dt

    spin = SPIN[int(t * 12) % len(SPIN)]
    p = (t % 5.0) / 5.0                          # 0→1 every 5s, then loop
    accent = grad(ACCENT, p)
    phase = PHASES[min(int(p * len(PHASES)), len(PHASES) - 1)]

    bands = [
        (" ", 0.5 + 0.5 * math.sin(t * (2.2 + i * 0.7) + i), grad(ACCENT, i / 6))
        for i in range(6)
    ]

    panel = card(
        col(
            row(c(spin, accent).bold, b(f" {phase}…"),
                dim_text(f"   {fmt_duration(t)}")),
            progress(p, "load", fill=accent, width=22),
            bar_chart(bands, max_value=1.0),
            dim_text("Ctrl+C to quit"),
            gap=1,
        ),
        title="status",
        width=PANEL_W,
        bg=(8, 10, 24),
        border_color=accent,
    )

    # zstack's first layer sets the size; the second fills it and centers the
    # card. Center with main-axis justify on both axes (row=horizontal,
    # col=vertical) — that's the reliable centering primitive here.
    return zstack(
        halfblock(plasma_grid()),
        row(col(panel, justify="center"),
            justify="center", width=PW, height=PHPX // 2),
    )


if __name__ == "__main__":
    animate(render, fps=30)  # maya.quit() to stop
