"""paint.py — a mouse-driven pixel painter. Click to paint, scroll to pick a
color, right-click to erase. Demonstrates maya-py mouse support.

  click   paint a cell            scroll   change brush color
  right   erase a cell            c        clear      q/Esc  quit

    PYTHONPATH=src python examples/paint.py

(Requires a terminal with mouse reporting — most do: xterm, kitty, iTerm2,
Windows Terminal, tmux with `set -g mouse on`.)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T

# the canvas is drawn starting at this screen offset (col, row), 1-based to
# match maya's mouse coordinates. The card border + title shift content down.
GRID_W, GRID_H = 28, 14
ORIGIN_COL = 2   # inside the outer card's left border + padding
ORIGIN_ROW = 4   # below title + top border + header row

PALETTE = ["red", "orange", "gold", "lime", "sky", "magenta", "white"]

app = App("paint", inline=True)
app.state(
    cells={},          # (cx, cy) -> color name
    brush=0,           # index into PALETTE
    last=None,         # last painted cell (for the status line)
)


def _cell_at(col_, row_):
    """Map a 1-based screen (col, row) to a grid cell, or None if outside."""
    cx = col_ - ORIGIN_COL
    cy = row_ - ORIGIN_ROW
    if 0 <= cx < GRID_W and 0 <= cy < GRID_H:
        return (cx, cy)
    return None


@app.on_click("left")
def paint(s, col_, row_):
    cell = _cell_at(col_, row_)
    if cell:
        s.cells[cell] = PALETTE[s.brush]
        s.last = cell


@app.on_click("right")
def erase(s, col_, row_):
    cell = _cell_at(col_, row_)
    if cell and cell in s.cells:
        del s.cells[cell]
        s.last = cell


@app.on_scroll
def pick(s, direction):
    s.brush = (s.brush + direction) % len(PALETTE)


@app.on("c")
def clear(s):
    s.cells.clear()


@app.on("q", "esc")
def quit_(s):
    app.stop()


def canvas(s):
    rows = []
    for cy in range(GRID_H):
        parts = []
        for cx in range(GRID_W):
            color = s.cells.get((cx, cy))
            if color:
                parts.append(T("██").fg(color))
            else:
                parts.append(T("··").fg(maya.rgb(45, 49, 58)))
        rows.append(row(*parts, gap=0))
    return col(*rows)


@app.view
def view(s):
    swatches = []
    for i, name in enumerate(PALETTE):
        chip = T("██").fg(name)
        if i == s.brush:
            swatches.append(row(T("[").fg("white"), chip, T("]").fg("white"), gap=0))
        else:
            swatches.append(row(" ", chip, " ", gap=0))
    return card(
        row(b("✎ paint").fg("sky"),
            dim_text(f"{len(s.cells)} cells"),
            row(dim_text("brush:"), *swatches, gap=0),
            justify="between"),
        canvas(s),
        dim_text("click paint · right erase · scroll color · c clear · q quit"),
        title="paint", gap=1,
    )


if __name__ == "__main__":
    app.run()
