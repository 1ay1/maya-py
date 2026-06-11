"""_halfblock.py — shared half-block pixel rendering helper for the demos.

Each terminal cell shows TWO vertical pixels via the upper-half-block glyph
``▀``: its foreground paints the top pixel, its background the bottom pixel.
That doubles vertical resolution — a 64×40 pixel field fits in 64×20 cells.

    from _halfblock import halfblock
    grid = [[(r, g, b) or None for x in range(W)] for y in range(H)]  # H even
    element = halfblock(grid)            # one row of run-merged segments / line
"""

from __future__ import annotations

import maya_py as maya
from maya_py import T, col, row

UPPER = "\u2580"  # ▀ upper half block


def halfblock(grid, *, bg=(0, 0, 0)):
    """Render a 2-D pixel grid (rows of (r,g,b) tuples or None) as half-blocks.

    ``grid`` height must be even. None means "use ``bg``". Adjacent cells with
    the same (top,bottom) colour merge into one styled segment, so a line is a
    handful of ``T`` runs rather than one per pixel.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    lines = []
    for cy in range(0, h, 2):
        top = grid[cy]
        bot = grid[cy + 1] if cy + 1 < h else [None] * w
        segs = []
        run_n = 0
        run_fg = run_bg = None
        for x in range(w):
            tp = top[x] or bg
            bp = bot[x] or bg
            if (tp, bp) != (run_fg, run_bg):
                if run_n:
                    segs.append(_seg(run_n, run_fg, run_bg))
                run_fg, run_bg, run_n = tp, bp, 0
            run_n += 1
        if run_n:
            segs.append(_seg(run_n, run_fg, run_bg))
        lines.append(row(*segs, gap=0))
    return col(*lines, gap=0)


def _seg(n, fg, bg):
    return T(UPPER * n).fg(maya.rgb(*fg)).bg(maya.rgb(*bg))
