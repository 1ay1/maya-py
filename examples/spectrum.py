"""spectrum.py — a faux audio spectrum analyzer with peak-hold bars.

Synthesises a moving multi-band spectrum (overlapping sine envelopes) and
renders it as colour-graded vertical bars with falling peak markers — exactly
the kind of dense per-cell colour work maya's renderer eats for breakfast.

  space pause · +/- bands · q/esc quit

    PYTHONPATH=src python examples/spectrum.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component

BARS = 48
HEIGHT = 18                # rows tall
BLOCKS = "▁▂▃▄▅▆▇█"

app = App("spectrum", inline=True, fps=30)
app.state(t=0.0, levels=[], peaks=[], bars_n=48, height=18, paused=False)


def _ensure(s, n, h):
    if n != s.bars_n or not s.levels:
        s.bars_n = n
        s.levels = [0.0] * n
        s.peaks = [0.0] * n
    s.height = h


def step(s):
    s.t += 0.12
    t = s.t
    n = s.bars_n
    for i in range(n):
        f = i / n
        # layered envelopes → spectrum-ish shape, louder in bass
        v = (0.5 * (1 - f) * (0.6 + 0.4 * math.sin(t * 2 + i * 0.4))
             + 0.3 * math.sin(t * 5 + i * 0.9) ** 2
             + 0.2 * random.random() * (1 - f))
        v = max(0.0, min(1.0, v))
        # smooth attack, fast-ish release
        s.levels[i] = max(v, s.levels[i] * 0.82)
        if s.levels[i] >= s.peaks[i]:
            s.peaks[i] = s.levels[i]
        else:
            s.peaks[i] = max(s.levels[i], s.peaks[i] - 0.02)


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("q", "esc")
def _quit(s): app.stop()


def _bar_color(frac):
    # green (low) → yellow → red (high)
    if frac < 0.5:
        return (int(120 * (frac * 2)) + 40, 220, 60)
    return (255, int(220 * (1 - (frac - 0.5) * 2)) + 35, 50)


def bars(s):
    def draw(w, h):
        n = max(8, w // 2)
        hh = max(6, min(h, 30))
        _ensure(s, n, hh)
        if not s.paused:
            step(s)
        lines = []
        for rowi in range(hh):
            segs = []
            for i in range(n):
                lv = s.levels[i]
                pk = s.peaks[i]
                cell_lo = (hh - 1 - rowi) / hh
                cell_hi = (hh - rowi) / hh
                if lv >= cell_hi:
                    segs.append(T("██").fg(maya.rgb(*_bar_color(cell_hi))))
                elif lv > cell_lo:
                    frac = (lv - cell_lo) / (cell_hi - cell_lo)
                    ch = BLOCKS[min(7, int(frac * 7))]
                    segs.append(T(ch + ch).fg(maya.rgb(*_bar_color(lv))))
                elif cell_lo <= pk < cell_hi:
                    segs.append(T("──").fg(maya.rgb(255, 255, 255)))
                else:
                    segs.append(T("  "))
            lines.append(row(*segs, gap=0))
        return col(*lines, gap=0)
    return component(draw, grow=1)


@app.view
def view(s):
    avg = sum(s.levels) / max(1, len(s.levels))
    return card(
        row(b("♫ spectrum").fg((80, 220, 255)),
            dim_text(f"{s.bars_n} bands · level {avg*100:3.0f}% · "
                     f"{'paused' if s.paused else 'live'}"),
            justify="between"),
        bars(s),
        dim_text("space pause · q quit"),
        title="analyzer", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
