"""scroll_2d.py — two-axis scrolling over a wide-and-tall surface.

One ScrollState, one viewport — the renderer applies scroll_x and scroll_y
independently and writes max_x / max_y back after layout so both axes clamp
automatically.

  ↑↓←→ move · PgUp/PgDn page · Home/End jump · wheel vertical · q quit

    PYTHONPATH=src python examples/scroll_2d.py
"""


import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import (App, col, row, card, b, T, dim_text,
                     scroll_state, viewport, scrollbar)

COLS, ROWS = 40, 60


def grid():
    lines = []
    # header row
    header = [T("    ").fg("slate")]
    for c in range(COLS):
        header.append(T(f"c{c:<3}").fg("gold"))
    lines.append(row(*header, gap=0))
    for r in range(ROWS):
        cells = [T(f"r{r:<3}").fg("gold")]
        for c in range(COLS):
            v = (r * c) % 100
            hue = (40 + v * 2, 120, 220 - v)
            cells.append(T(f"{v:>3} ").fg(maya.rgb(*hue)))
        lines.append(row(*cells, gap=0))
    return col(*lines, gap=0)


app = App.inline("scroll_2d", mouse=True)
s = scroll_state()
app.state(s=s)


app.quit_on("q", "esc")


@app.view
def view(st):
    return card(
        b("two-axis scroll").fg("sky"),
        row(
            col(
                viewport(grid(), st.s, width=60, height=16, grow=1),
                scrollbar(st.s, 60, axis="x", style="block", thumb_color="gold"),
                gap=0,
            ),
            scrollbar(st.s, 16, axis="y", style="neon", thumb_color="sky"),
            gap=1,
        ),
        dim_text(f"({st.s.x},{st.s.y}) of ({st.s.max_x},{st.s.max_y}) · "
                 "↑↓←→ scroll · q quit"),
        title="scroll_2d", gap=1,
    )


if __name__ == "__main__":
    app.run()
