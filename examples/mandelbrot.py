"""mandelbrot.py — a colored ASCII Mandelbrot set that zooms, via component().

The fractal is rendered to fit whatever box maya allocates. Auto-stops after
~18s; Ctrl-C to quit early.

    PYTHONPATH=src python examples/mandelbrot.py
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import component, col, row, card, T, dim_text

start = time.time()
RAMP = " .:-=+*#%@"
CX, CY = -0.745, 0.115   # an interesting point to zoom toward
ROWS = 22
COLS = 64


def _color(it, maxit):
    if it >= maxit:
        return T(" ")
    f = it / maxit
    # hue sweep blue -> magenta -> orange
    r = int(80 + 175 * f)
    g = int(40 + 120 * (1 - abs(0.5 - f) * 2))
    bch = int(180 * (1 - f))
    ch = RAMP[min(len(RAMP) - 1, int(f * (len(RAMP) - 1)) + 1)]
    return T(ch).fg(maya.rgb(r, g, bch))


def fractal(zoom):
    def draw(w, h):
        w = min(w, COLS)
        h = ROWS
        maxit = 40 + int(zoom * 6)
        scale = 1.6 / (1.3 ** zoom)
        rows = []
        for sy in range(h):
            parts = []
            for sx in range(w):
                x0 = CX + (sx / w - 0.5) * scale * 2 * (w / h) * 0.5
                y0 = CY + (sy / h - 0.5) * scale * 2
                x = y = 0.0
                it = 0
                while x * x + y * y <= 4 and it < maxit:
                    x, y = x * x - y * y + x0, 2 * x * y + y0
                    it += 1
                parts.append(_color(it, maxit))
            rows.append(row(*parts, gap=0))
        return col(*rows)
    return component(draw, height=ROWS)


def render(dt):
    t = time.time() - start
    if t > 18:
        maya.quit()
    zoom = t * 0.8
    return card(
        fractal(zoom),
        dim_text(f"mandelbrot · zoom {zoom:4.1f}× · Ctrl-C to quit"),
        title="fractal", pad=0,
    )


if __name__ == "__main__":
    maya.animate(render, fps=12)
