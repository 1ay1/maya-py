"""maya_py.pixels — half-block pixel rendering.

Each terminal cell shows TWO vertical pixels via the upper-half-block glyph
``▀``: its foreground paints the top pixel, its background the bottom pixel.
That doubles vertical resolution — a 64×40 pixel field fits in 64×20 cells.

There is exactly ONE rendering path: the native ``_maya._widgets.halfblock``
C++ builder. It takes a FLAT buffer of packed ``0xRRGGBB`` ints (one per pixel,
``-1`` = transparent → bg) and run-merges + builds the whole Element tree in
C++. Python does no per-pixel work.

    from maya_py import halfblock
    grid = [[(r, g, b) or None for x in range(W)] for y in range(H)]  # H even
    element = halfblock(grid)            # built entirely in C++

For the hot loop, use :class:`PixelField`, which owns a flat packed-int buffer
so even the per-pixel writes never allocate a tuple.
"""

from __future__ import annotations

from ._maya import _widgets as _W
from .easy import component

__all__ = ["halfblock", "upscale", "PixelField", "pixel_canvas", "HalfBlockField"]

_native_halfblock = _W.halfblock
HalfBlockField = _W.HalfBlockField   # native stateful pixel surface (C++)

# Sane upper bounds for a terminal cell box. maya's fullscreen layout can hand
# a component a HUGE sentinel size during measurement; clamping here keeps a
# buffer allocation from exploding to millions of pixels.
_MAX_CELLS_W = 400
_MAX_CELLS_H = 200


def _pack(c):
    """(r,g,b) | packed-int | None → packed 0xRRGGBB int, or -1 for None."""
    if c is None:
        return -1
    if type(c) is int:
        return c
    return ((c[0] & 0xFF) << 16) | ((c[1] & 0xFF) << 8) | (c[2] & 0xFF)


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
    cheaply-computed buffer FILLS the whole half-block field. Returns the scaled
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
    """Render a 2-D pixel grid as half-blocks, entirely in C++.

    ``grid`` is rows of ``(r,g,b)`` tuples / packed ints / ``None`` (height
    must be even). The grid is flattened to a packed-int buffer and handed to
    the native ``halfblock`` builder which does all run-merging + Element
    construction. None means "use ``bg``".
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if w == 0 or h == 0:
        return _native_halfblock([], 0, 0, -1)
    pack = _pack
    flat = [pack(c) for rowp in grid for c in rowp]
    bg_pk = ((bg[0] & 0xFF) << 16) | ((bg[1] & 0xFF) << 8) | (bg[2] & 0xFF)
    return _native_halfblock(flat, w, h, bg_pk)


class PixelField:
    """A resize-managing half-block pixel buffer (flat, packed ints).

    Owns a single flat list of ``w*h`` packed ``0xRRGGBB`` ints (``-1`` =
    transparent → bg). Writes go straight into the flat buffer — no per-pixel
    tuple, no nested grid. ``render()`` hands the buffer to the native C++
    half-block builder. Each terminal cell is 2 pixels tall.

        field = PixelField()
        def draw(w, h):
            field.resize(w, h * 2)
            field.clear()
            field.set(x, y, (255, 0, 0))     # or a packed int
            return field.render()
        component(draw, grow=1)
    """

    __slots__ = ("w", "h", "bg", "buf")

    def __init__(self, bg=(0, 0, 0)):
        self.w = 0
        self.h = 0
        self.bg = ((bg[0] & 0xFF) << 16) | ((bg[1] & 0xFF) << 8) | (bg[2] & 0xFF)
        self.buf: list[int] = []

    def resize(self, w: int, h: int) -> bool:
        """Resize to ``w × h`` pixels, reallocating only on change. Returns True
        if it reallocated."""
        if w != self.w or h != self.h:
            self.w, self.h = w, h
            self.buf = [-1] * (w * h)
            return True
        return False

    def clear(self) -> None:
        """Reset every pixel to transparent (-1 → ``bg``)."""
        # Slice-assign a fresh fill in ONE C-level memcpy rather than a
        # per-pixel Python loop. CPython lays the list backing store out
        # contiguously, so this is a bulk overwrite, not n bound checks.
        self.buf[:] = (-1,) * (self.w * self.h)

    def set(self, x: int, y: int, color) -> None:
        """Set pixel (x, y) to a packed int or (r,g,b); out-of-bounds ignored."""
        if 0 <= x < self.w and 0 <= y < self.h:
            if type(color) is not int:
                color = ((color[0] & 0xFF) << 16) | ((color[1] & 0xFF) << 8) | (color[2] & 0xFF)
            self.buf[y * self.w + x] = color

    def render(self):
        """Build the buffer into a half-block Element (native, in C++)."""
        return _native_halfblock(self.buf, self.w, self.h, self.bg)


def pixel_canvas(draw, *, bg=(0, 0, 0), grow=1, **kw):
    """A size-aware element that hands ``draw(field, w, h)`` a resize-managed
    :class:`PixelField` already sized to the allocated cell box (2 pixels tall
    per cell) and cleared. Mutate the field with ``field.set(...)``; it's
    rendered as half-blocks automatically.
    """
    field = PixelField(bg=bg)

    def _inner(w, h):
        field.resize(w, h * 2)
        field.clear()
        draw(field, w, h * 2)
        return field.render()

    return component(_inner, grow=grow, **kw)
