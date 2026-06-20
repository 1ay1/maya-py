"""plasma.py — a whole-terminal half-block plasma, built with the mode DSL.

Shows off the fullscreen pixel path with zero boilerplate:

  • `App.fullscreen(...)`  — takes the alt screen, owns every cell.
  • `fullscreen_pixels(draw)` — hands `draw(field, pw, ph)` a PixelField
    already sized to the visible terminal (2 px tall per cell), and renders
    it as half-blocks. No `shutil.get_terminal_size()` dance, no unbounded
    grow-sentinel papercut.
  • the colour comes from the DSL `hsv` hue sweep.

    PYTHONPATH=src python examples/plasma.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, fullscreen_pixels, hsv, wrap  # noqa: E402


app = App.fullscreen("plasma", fps=30, t=0.0, hue=0.0, sat=0.85)


app.quit_on("q", "esc")


@app.on(" ")
def _shift(s):
    s.hue = wrap(s.hue + 0.15, 1.0)


@app.on("d")
def _desat(s):
    s.sat = 0.2 if s.sat > 0.5 else 0.85


@app.on_frame
def _tick(s, dt):
    s.t += dt


@app.view
def view(s):
    t = s.t

    def draw(f, pw, ph):
        # Classic sum-of-sines plasma. One hsv() per pixel — the DSL hue sweep
        # carries the colour so the loop stays a one-liner.
        for y in range(ph):
            fy = y / ph
            for x in range(pw):
                fx = x / pw
                v = (math.sin(fx * 8 + t)
                     + math.sin(fy * 8 - t * 0.7)
                     + math.sin((fx + fy) * 6 + t * 1.3)
                     + math.sin(math.hypot(fx - 0.5, fy - 0.5) * 14 - t * 2))
                h = wrap(v * 0.12 + s.hue, 1.0)
                f.set(x, y, hsv(h, s.sat, 0.55 + 0.45 * math.sin(v + t)))

    return fullscreen_pixels(draw, bg=(4, 4, 10))


if __name__ == "__main__":
    app.run()
