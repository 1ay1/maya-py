"""maya — Python bindings for the maya C++26 TUI framework.

A thin, pythonic layer over the native ``_maya`` extension. Build styled
terminal UIs with flexbox layout, render them inline or fullscreen, and
drive interactive apps from Python callbacks.

Quick start::

    import maya_py as maya

    ui = maya.box(
        maya.text("Hello World", maya.bold | maya.fg(100, 180, 255)),
        maya.box(
            maya.text("Status:", maya.dim),
            maya.text("Online", maya.bold | maya.fg(80, 220, 120)),
            gap=1,
        ),
        border=maya.Round, padding=1,
    )
    maya.print(ui)
"""

from __future__ import annotations

from . import _maya
from ._maya import (
    Element,
    Style,
    Color,
    Event,
    # enums
    FlexDirection,
    Align,
    Justify,
    BorderStyle,
    TextWrap,
    SpecialKey,
    # element factories
    text,
    box,
    vstack,
    hstack,
    blank,
    # rendering
    render_to_string,
    live,
    run,
    quit,
    # event predicates
    key,
    key_special,
    ctrl,
    alt,
    any_key,
    resized,
)

# ── Border style shortcuts (BorderStyle.* without the prefix) ───────────────
Round = BorderStyle.Round
Single = BorderStyle.Single
Double = BorderStyle.Double
BoldBorder = BorderStyle.Bold
Classic = BorderStyle.Classic
Dashed = BorderStyle.Dashed

# ── Direction / align / justify shortcuts ───────────────────────────────────
Row = FlexDirection.Row
Column = FlexDirection.Column

__all__ = [
    "Element", "Style", "Color", "Event",
    "FlexDirection", "Align", "Justify", "BorderStyle", "TextWrap", "SpecialKey",
    "text", "box", "vstack", "hstack", "blank",
    "print", "render_to_string", "live", "run", "quit",
    "key", "key_special", "ctrl", "alt", "any_key", "resized",
    "Round", "Single", "Double", "BoldBorder", "Classic", "Dashed",
    "Row", "Column",
    # style helpers
    "fg", "bg", "rgb", "hex", "bold", "dim", "italic", "underline",
    "strikethrough", "inverse", "style",
]


# ── Style helpers ───────────────────────────────────────────────────────────
# These mirror maya's predefined constexpr styles (Bold, Dim, Fg<...>) as
# composable Python values, joinable with `|`.

bold = Style().with_bold()
dim = Style().with_dim()
italic = Style().with_italic()
underline = Style().with_underline()
strikethrough = Style().with_strikethrough()
inverse = Style().with_inverse()


def _to_color(c, *rest) -> Color:
    """Coerce flexible color args into a maya Color.

    Accepts: a Color, an (r, g, b) tuple, three ints, or a single int hex
    (0xRRGGBB).
    """
    if isinstance(c, Color):
        return c
    if rest:
        return Color.rgb(int(c), int(rest[0]), int(rest[1]))
    if isinstance(c, (tuple, list)):
        return Color.rgb(int(c[0]), int(c[1]), int(c[2]))
    # single int -> hex
    return Color.hex(int(c))


def fg(c, *rest) -> Style:
    """Foreground color style. ``fg(255, 0, 0)``, ``fg((r,g,b))``, ``fg(0xFF0000)``."""
    return Style().with_fg(_to_color(c, *rest))


def bg(c, *rest) -> Style:
    """Background color style."""
    return Style().with_bg(_to_color(c, *rest))


def rgb(r: int, g: int, b: int) -> Color:
    """A 24-bit truecolor Color."""
    return Color.rgb(r, g, b)


def hex(value: int) -> Color:
    """A Color from a hex literal, e.g. ``hex(0xFF8800)``."""
    return Color.hex(value)


def style(
    *,
    fg=None,
    bg=None,
    bold: bool = False,
    dim: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    inverse: bool = False,
) -> Style:
    """Build a Style from keyword flags in one call."""
    s = Style()
    if fg is not None:
        s = s.with_fg(_to_color(fg))
    if bg is not None:
        s = s.with_bg(_to_color(bg))
    if bold:
        s = s.with_bold()
    if dim:
        s = s.with_dim()
    if italic:
        s = s.with_italic()
    if underline:
        s = s.with_underline()
    if strikethrough:
        s = s.with_strikethrough()
    if inverse:
        s = s.with_inverse()
    return s


# ── print ───────────────────────────────────────────────────────────────────
# Shadow the builtin within this package's namespace so `maya.print(ui)`
# renders an Element, but plain strings fall through to builtins.print.
_builtin_print = print


def print(element, *args, width: int | None = None, **kwargs):  # noqa: A001
    """Render a maya Element to stdout. Falls back to builtin print otherwise."""
    if isinstance(element, Element):
        _maya.print_element(element, width)
        return None
    return _builtin_print(element, *args, **kwargs)


__version__ = "0.1.0"
