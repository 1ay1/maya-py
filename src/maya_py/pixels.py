"""maya_py.pixels — half-block pixel rendering.

Each terminal cell shows TWO vertical pixels via the upper-half-block glyph
``▀``: its foreground paints the top pixel, its background the bottom pixel.
That doubles vertical resolution — a 64×40 pixel field fits in 64×20 cells.

    from maya_py import halfblock
    grid = [[(r, g, b) or None for x in range(W)] for y in range(H)]  # H even
    element = halfblock(grid)            # rows of run-merged segments
"""

from __future__ import annotations

from ._maya import Color
from .easy import T, col, component, row

UPPER = "▀"  # ▀ upper half block

__all__ = ["halfblock", "upscale", "PixelField", "pixel_canvas"]

# Sane upper bounds for a terminal cell box. maya's fullscreen layout can hand
# a component a HUGE sentinel size during measurement; clamping here keeps a
# grid allocation from exploding to millions of rows.
_MAX_CELLS_W = 400
_MAX_CELLS_H = 200


def target_size(w, h):
    """Clamp a component's (w, h) cell box to sane terminal bounds, returning
    the output *pixel* dimensions ``(out_w, out_h)`` for a half-block field
    (out_h = h*2). Guards against maya's fullscreen layout sentinel."""
    out_w = max(1, min(int(w), _MAX_CELLS_W))
    out_h = max(2, min(int(h) * 2, _MAX_CELLS_H))
    if out_h % 2:
        out_h += 1
    return out_w, out_h


def upscale(small, out_w, out_h):
    """Nearest-neighbour scale a small pixel grid up to ``out_w × out_h`` so a
    cheaply-computed buffer FILLS the whole half-block field (identical layout
    to a native full-resolution render, just lower detail). Returns the scaled
    grid; pass it straight to :func:`halfblock`."""
    sh = len(small)
    sw = len(small[0]) if sh else 0
    if sw == out_w and sh == out_h:
        return small
    if sw == 0 or sh == 0:
        return [[None] * out_w for _ in range(out_h)]
    grid = [None] * out_h
    for oy in range(out_h):
        srow = small[oy * sh // out_h]
        grid[oy] = [srow[ox * sw // out_w] for ox in range(out_w)]
    return grid


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
    return T(UPPER * n).fg(Color.rgb(*fg)).bg(Color.rgb(*bg))


class PixelField:
    """A resize-managing 2-D pixel buffer for half-block rendering.

    Owns a ``w × h`` grid of ``(r,g,b)`` / ``None`` pixels and reallocates only
    when the size changes — so you don't hand-roll the grid + resize-guard that
    every pixel demo otherwise copies. Each terminal cell is 2 pixels tall.

        field = PixelField()
        def draw(w, h):
            field.resize(w, h * 2)      # cell box -> pixel box
            field.clear()
            field.set(x, y, (255, 0, 0))
            return field.render()
        component(draw, grow=1)

    Or skip the wiring entirely with :func:`pixel_canvas`.
    """

    __slots__ = ("w", "h", "bg", "grid")

    def __init__(self, bg=(0, 0, 0)):
        self.w = 0
        self.h = 0
        self.bg = bg
        self.grid: list[list] = []

    def resize(self, w: int, h: int) -> bool:
        """Resize to ``w × h`` pixels, reallocating only on change. Returns True
        if it reallocated."""
        if w != self.w or h != self.h:
            self.w, self.h = w, h
            self.grid = [[None] * w for _ in range(h)]
            return True
        return False

    def clear(self) -> None:
        """Reset every pixel to None (transparent → ``bg``)."""
        for rowp in self.grid:
            for x in range(self.w):
                rowp[x] = None

    def set(self, x: int, y: int, color) -> None:
        """Set pixel (x, y); out-of-bounds is ignored so callers needn't clip."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self.grid[y][x] = color

    def render(self):
        """Render the current grid as a half-block Element."""
        return halfblock(self.grid, bg=self.bg)


def pixel_canvas(draw, *, bg=(0, 0, 0), grow=1, **kw):
    """A size-aware element that hands ``draw(field, w, h)`` a resize-managed
    :class:`PixelField` already sized to the allocated cell box (2 pixels tall
    per cell) and cleared. Mutate the field with ``field.set(...)``; it's
    rendered as half-blocks automatically.

        def draw(f, w, h):
            for x in range(w):
                f.set(x, h - 1, (0, 200, 255))
        pixel_canvas(draw)         # fills its box, animate by re-rendering
    """
    field = PixelField(bg=bg)

    def _inner(w, h):
        field.resize(w, h * 2)
        field.clear()
        draw(field, w, h * 2)
        return field.render()

    return component(_inner, grow=grow, **kw)
