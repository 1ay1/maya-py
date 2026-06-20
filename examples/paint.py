"""paint.py — a mouse-driven pixel painter. Click to paint, scroll to pick a
color, right-click to erase. Demonstrates maya-py mouse support.

  click   paint a cell            scroll   change brush color
  right   erase a cell            c        clear      q/Esc  quit

    PYTHONPATH=src python examples/paint.py

Requires a terminal with mouse reporting (xterm, kitty, iTerm2, Windows
Terminal, tmux with `set -g mouse on`). Runs FULLSCREEN so mouse clicks map
to an exact, fixed coordinate origin; the canvas is wrapped in a maya viewport
whose painted rect is reported back each frame, so clicks hit-test against the
REAL on-screen position — never a hardcoded offset.
"""


import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import (
    App, col, row, card, b, dim_text, T,
    scroll_state, viewport, scroll_handle,
)

GRID_W, GRID_H = 60, 18
PALETTE = ["red", "orange", "gold", "lime", "sky", "magenta", "white"]

app = App.fullscreen("paint", mouse=True)   # fullscreen: clean coord origin
vp = scroll_state()          # records the canvas's painted bounds each frame
app.state(cells={}, brush=0, last=None, vp=vp)


def _cell_at(s, click_col, click_row):
    """Map a 1-based screen click to a grid cell using the canvas's REAL
    painted rect (viewport_bounds), so no offset is ever hardcoded."""
    x, y, w, h = s.vp.viewport_bounds
    if w == 0 and h == 0:        # not painted yet (first frame)
        return None
    # mouse coords are 1-based; bounds are 0-based canvas coords.
    cx = (click_col - 1) - x
    cy = (click_row - 1) - y
    if 0 <= cx < GRID_W and 0 <= cy < GRID_H:
        return (cx, cy)
    return None


@app.on_click("left")
def paint(s, col_, row_):
    cell = _cell_at(s, col_, row_)
    if cell:
        s.cells[cell] = PALETTE[s.brush]
        s.last = cell


@app.on_click("right")
def erase(s, col_, row_):
    cell = _cell_at(s, col_, row_)
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
    # one cell = ONE column (a single block glyph), so screen col ↔ grid col
    # is a clean 1:1 map after subtracting the painted origin.
    rows = []
    for cy in range(GRID_H):
        line = []
        for cx in range(GRID_W):
            color = s.cells.get((cx, cy))
            if color:
                line.append(T("█").fg(color))
            else:
                line.append(T("·").fg(maya.rgb(50, 54, 64)))
        rows.append(row(*line, gap=0))
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
            dim_text(f"{len(s.cells)} cells  ·  {s.last or ''}"),
            row(dim_text("brush:"), *swatches, gap=0),
            justify="between"),
        # the viewport records its painted rect into vp.viewport_bounds so the
        # click handler can hit-test exactly; size it to the grid (no clip).
        viewport(canvas(s), s.vp, width=GRID_W, height=GRID_H),
        dim_text("click paint · right erase · scroll color · c clear · q quit"),
        title="paint", gap=1,
    )


if __name__ == "__main__":
    app.run()
