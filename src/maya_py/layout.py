"""Responsive layout toolkit — maya's width-aware building blocks.

These re-solve themselves from the width the layout actually hands them,
live on every terminal resize. The whole dashboard idiom is three shapes::

    from maya_py import grid, sidebar, col

    sidebar(grid([cpu, mem, net, disk], min=24), table, width=42)

- :func:`grid` — as many ``min``-wide cells per row as fit; wraps; stacks.
- :func:`sidebar` — fixed-width rail + main pane; stacks when narrow.
- :func:`fit_row` / :func:`fit_col` — drop optional items when tight.
- :func:`pick` — first alternative that fits (semantic zoom).
- :func:`place` — position one child inside its slot (center/corner).
- :func:`clamp_width` — cap content width on ultrawide terminals.
- :func:`adapt` / :func:`fill` — custom width/slot-aware components.
- :func:`measure` — an Element's natural (width, height).
- :func:`rainbow` / :func:`gradient_rule` — pretty text & dividers.
- :func:`hit_id` / :func:`hit_test` / :func:`hit_rect` — paint-time mouse
  hit-testing (tag a box with ``hit=...``, ask who was clicked).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from . import _maya
from ._maya import Element

__all__ = [
    "grid", "sidebar", "place", "pick", "clamp_width",
    "fit_row", "fit_col", "adapt", "fill", "measure",
    "rainbow", "gradient_rule",
    "hit_id", "hit_kind", "hit_index", "hit_test", "hit_rect",
]


def _el(x: Any) -> Any:
    """Coerce strings/T-objects to something the native layer accepts."""
    if isinstance(x, Element) or isinstance(x, str):
        return x
    # T / markup objects expose .element(); duck-type it.
    build = getattr(x, "element", None)
    if callable(build):
        return build()
    return str(x)


def grid(cells: Sequence[Any], min: int = 24, *, max_cols: int = 0,
         gap_x: int = 1, gap_y: int = 0, grow_rows: bool = False) -> Element:
    """Auto-flow grid: as many ``min``-wide cells per row as fit, wrap the
    rest, one column when narrow. "Each cell wants about ``min`` columns"
    is the entire API — re-solved live on every resize.

    >>> grid([cpu, mem, net, disk], 26)
    """
    return _maya.grid([_el(c) for c in cells], min, max_cols, gap_x, gap_y,
                      grow_rows)


def sidebar(rail: Any, main: Any, width: int = 32, *, stack_below: int = 0,
            gap: int = 1, right: bool = False) -> Element:
    """Fixed-``width`` rail beside a main pane that takes the rest; the pair
    stacks vertically (reading order preserved) when the slot is too narrow.
    """
    return _maya.sidebar(_el(rail), _el(main), width, stack_below, gap, right)


def place(child: Any, h: str = "center", v: str = "middle") -> Element:
    """Position one child inside the slot flex gives the wrapper.

    ``h``: ``"left" | "center" | "right"``; ``v``: ``"top" | "middle" |
    "bottom"``. The 9-position grid: ``place(dialog)`` centers, ``place(toast,
    "right", "top")`` puts it in the corner.
    """
    return _maya.place(_el(child), h, v)


def pick(*alternatives: Any) -> Element:
    """Render the FIRST alternative that fits the width; the LAST is the
    fallback (used even when it does not fit). Semantic zoom::

        pick(rich_status_line, medium_status_line, just_the_icon)
    """
    if len(alternatives) == 1 and isinstance(alternatives[0], (list, tuple)):
        alternatives = tuple(alternatives[0])
    return _maya.pick([_el(a) for a in alternatives])


def clamp_width(el: Any, max_width: int, align: str = "center") -> Element:
    """Cap content width on huge terminals and align the clamped column
    (libadwaita's AdwClamp, for terminals). Below ``max_width`` it is a
    transparent wrapper."""
    return _maya.clamp_width(_el(el), max_width, align)


def fit_row(*items: Any, gap: int = 0) -> Element:
    """A row that DROPS optional items when they don't fit.

    Items are Elements/strings (never dropped) or ``(element, keep)`` tuples —
    LOWER ``keep`` ranks drop first, ties drop the rightmost::

        fit_row(logo, (hostname, 5), (kernel, 4), (uptime, 2), (procs, 1))
    """
    if len(items) == 1 and isinstance(items[0], list):
        items = tuple(items[0])
    out = []
    for it in items:
        if isinstance(it, tuple):
            out.append((_el(it[0]), int(it[1])))
        else:
            out.append(_el(it))
    return _maya.fit_row(out, gap)


def fit_col(*items: Any, gap: int = 0) -> Element:
    """The vertical counterpart to :func:`fit_row` — drops items when the
    slot is too SHORT (footers eaten, panels crushed)."""
    if len(items) == 1 and isinstance(items[0], list):
        items = tuple(items[0])
    out = []
    for it in items:
        if isinstance(it, tuple):
            out.append((_el(it[0]), int(it[1])))
        else:
            out.append(_el(it))
    return _maya.fit_col(out, gap)


def adapt(render_fn: Callable[[int], Any]) -> Element:
    """Width-aware component: ``render_fn(width) -> Element | str`` is called
    with the ACTUAL slot width at layout time — the primitive under grid/
    sidebar/pick. Rebuild your UI differently per width::

        adapt(lambda w: compact if w < 60 else full)
    """
    return _maya.adapt(render_fn)


def fill(render_fn: Callable[[int, int], Any], *, min_w: int = 0,
         min_h: int = 1) -> Element:
    """Slot-filling component: ``render_fn(w, h) -> Element | str`` receives
    the slot size flex allocated. Unlike :func:`~maya_py.component` (which
    sizes to CONTENT), ``fill()`` sizes to the SLOT — the right tool for a
    chart that should take the leftover space."""
    return _maya.fill(render_fn, min_w, min_h)


def measure(element: Any, max_width: int = 1 << 14) -> tuple[int, int]:
    """An Element tree's natural ``(width, height)`` under a width cap."""
    e = _el(element)
    if isinstance(e, str):
        e = _maya.text(e)
    return _maya.measure_element(e, max_width)


def rainbow(text: str, *, saturation: float = 0.85, lightness: float = 0.62,
            bold: bool = False) -> Element:
    """Full-spectrum rainbow text (HSL hue sweep across the width)."""
    return _maya.rainbow(str(text), saturation, lightness, bold)


def gradient_rule(*stops: Any, glyph: str = "─") -> Element:
    """A full-width horizontal divider colored from the first stop to the
    last, tiled with ``glyph`` — responsive to the width it is given.

    >>> gradient_rule("#7F5AF0", "#2CB67D")
    """
    # Lazy import: easy.color parses names / "#rrggbb" / tuples / ints,
    # and easy imports after layout in __init__ (avoid a load-time cycle).
    from .easy import color as _to_color
    if len(stops) == 1 and isinstance(stops[0], (list, tuple)):
        stops = tuple(stops[0])
    cols = [_to_color(s) for s in stops]
    if len(cols) == 1:
        cols = cols * 2
    return _maya.gradient_rule(cols, glyph)


# ── Hit registry — paint-time mouse hit-testing ─────────────────────────
# Tag a box as a click target and let the RENDERER record where it painted:
#
#     KIND_TAB = 1
#     stack(..., hit=hit_id(KIND_TAB, i))          # box() kwarg
#
#     @app.on_click()
#     def click(state, x, y):
#         tid = hit_test(x, y)
#         if tid is not None and hit_kind(tid) == KIND_TAB:
#             state.tab = hit_index(tid)
#
# Correct by construction — the rect came from the same layout pass that
# put the pixels on screen. No hand-mirrored layout math.

def hit_id(kind: int, index: int = 0) -> int:
    """Pack a ``(kind, index)`` pair into a 64-bit hit-target id."""
    return _maya.hit_id(kind, index)


def hit_kind(id: int) -> int:
    """The kind half of a packed hit id."""
    return _maya.hit_kind(id)


def hit_index(id: int) -> int:
    """The index half of a packed hit id."""
    return _maya.hit_index(id)


def hit_test(x: int, y: int) -> int | None:
    """Topmost hit-target id painted at cell ``(x, y)`` this frame, or None."""
    return _maya.hit_test(x, y)


def hit_rect(id: int) -> tuple[int, int, int, int] | None:
    """Painted ``(x, y, w, h)`` of the first region under ``id``, or None —
    lets a host anchor a popup/tooltip to a target without knowing where
    layout put it."""
    return _maya.hit_rect(id)
