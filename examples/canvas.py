"""canvas.py — the PixelCanvas drawing surface: lines, rects, and a live plot.

maya's ``Canvas`` is a half-block drawing surface (``width × height*2`` pixels —
two pixels per terminal cell). You draw imperatively with ``set_pixel`` /
``line`` / ``rect`` / ``fill``, then drop it into a layout. Here we draw a
static logo panel plus a live animated sine/Lissajous plot.

  space pause · q/esc quit

    PYTHONPATH=src python examples/canvas.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, Canvas

CW, CH = 60, 18          # canvas cells → 60 × 36 pixels


def static_art():
    """A one-shot drawing: border, diagonals, and a filled rectangle grid."""
    c = Canvas(40, 12)            # 40 × 24 px
    c.fill((10, 12, 22))
    c.rect(0, 0, 40, 24, "slate")
    # crossing diagonals
    c.line(0, 0, 39, 23, "sky")
    c.line(39, 0, 0, 23, "magenta")
    # a few nested rects
    for i, clr in enumerate([(80, 220, 120), (90, 180, 255), (255, 200, 60)]):
        m = 6 + i * 4
        c.rect(m, m, 40 - m * 2, 24 - m * 2, clr)
    return c.element()


app = App.inline("canvas", fps=30)
app.state(t=0.0, paused=False)


@app.on("space")
def _pause(s): s.paused = not s.paused


app.quit_on("q", "esc")


def plot(s):
    """A live plot drawn fresh each frame with the Canvas drawing API."""
    pw, ph = CW, CH * 2          # pixel resolution
    c = Canvas(CW, CH)
    c.fill((8, 10, 18))
    # zero axis
    c.line(0, ph // 2, pw - 1, ph // 2, (40, 44, 60))
    t = s.t
    # sine wave
    prev = None
    for x in range(pw):
        y = int(ph / 2 + math.sin(x * 0.18 + t) * (ph / 2 - 2))
        if prev is not None:
            c.line(prev[0], prev[1], x, y, "sky")
        prev = (x, y)
    # a Lissajous curve traced as dots
    for i in range(160):
        a = t + i * 0.04
        lx = int(pw / 2 + math.sin(a * 3) * (pw / 2 - 2))
        ly = int(ph / 2 + math.sin(a * 2) * (ph / 2 - 2))
        c.set_pixel(lx, ly, "lime")
    return c.element()


@app.view
def view(s):
    if not s.paused:
        s.t += 0.08
    return card(
        row(b("◧ canvas").fg("sky"),
            dim_text(f"PixelCanvas {CW}×{CH*2}px · "
                     f"{'paused' if s.paused else 'drawing'}"),
            justify="between"),
        row(
            card(static_art(), title="primitives", pad=1),
            card(plot(s), title="live plot", pad=1),
            gap=2,
        ),
        dim_text("space pause · q quit"),
        title="canvas", gap=1,
    )


if __name__ == "__main__":
    app.run()
