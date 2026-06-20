"""scroll_styles.py — every built-in scrollbar style preset, side by side.

A compact tile grid; each preset shows its vertical bar next to scrolling
content. All tiles share one ScrollState so they move in lock-step.

  ↑↓ scroll · q quit

    PYTHONPATH=src python examples/scroll_styles.py
"""


import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import (App, col, row, card, b, T, dim_text,
                     scroll_state, viewport, scrollbar)

PRESETS = ["line", "block", "slim", "heavy", "double", "dotted", "dashed",
           "braille", "ascii", "shadow", "minimal", "neon", "retro",
           "danger", "pixel"]

VH = 8


def body():
    return col(*[T(f"line {i:>2}").fg("sky" if i % 2 else "slate")
                 for i in range(40)], gap=0)


def tile(name, s):
    return card(
        T(name).fg("gold"),
        row(viewport(body(), s, height=VH, grow=1),
            scrollbar(s, VH, style=name, thumb_color="sky"),
            gap=1),
        pad=1, border="round", border_color="slate",
    )


app = App.inline("scroll_styles", mouse=True)
s = scroll_state()
app.state(s=s)


app.quit_on("q", "esc")


@app.view
def view(st):
    # 5 tiles per row, 3 rows
    tiles = [tile(p, st.s) for p in PRESETS]
    grid = []
    per = 5
    for i in range(0, len(tiles), per):
        grid.append(row(*tiles[i:i + per], gap=1))
    return card(
        b("scrollbar styles").fg("sky"),
        col(*grid, gap=1),
        dim_text(f"y {st.s.y}/{st.s.max_y} · all share one state · ↑↓ · q quit"),
        title="scroll_styles", gap=1,
    )


if __name__ == "__main__":
    app.run()
