"""maya_py.widgets — friendly wrappers over maya's native widget renderers.

Each function builds a real maya widget (the same renderer maya C++ uses) and
returns an Element you drop straight into a layout:

    from maya_py import col, sparkline, gauge, table

    col(
        sparkline([3, 1, 4, 1, 5, 9, 2, 6], label="req/s", show_last=True),
        gauge(0.72, "load"),
        table(["Name", "Score"], [["Ada", "99"], ["Bob", "7"]], bordered=True),
    )

Colors accept the same friendly values as the rest of maya_py: names
("sky", "red"), (r, g, b) tuples, "#rrggbb", or a maya Color.
"""

from __future__ import annotations

from typing import Any, Sequence

from . import _maya
from ._maya import Element, Color
from .easy import color as _color

_W = _maya._widgets

# enums, re-exported for callers who want them explicitly
GaugeStyle = _W.GaugeStyle
ColumnAlign = _W.ColumnAlign

_ALIGN = {"left": ColumnAlign.Left, "center": ColumnAlign.Center,
          "right": ColumnAlign.Right}


def _col(c: Any) -> Color | None:
    return None if c is None else _color(c)


def sparkline(data: Sequence[float], *, label: str = "", color: Any = None,
              show_min_max: bool = False, show_last: bool = False) -> Element:
    """An inline mini bar chart from a sequence of numbers."""
    return _W.sparkline([float(x) for x in data], label, _col(color),
                        show_min_max, show_last)


def gauge(value: float, label: str = "", *, color: Any = None,
          style: Any = "arc") -> Element:
    """A meter (0..1). ``style`` is ``"arc"`` or ``"bar"``."""
    gs = style if not isinstance(style, str) else (
        GaugeStyle.Bar if style.lower() == "bar" else GaugeStyle.Arc)
    return _W.gauge(float(value), label, _col(color), gs)


def progress(value: float, label: str = "", *, width: int = 0, fill: Any = None,
             track: Any = None, show_track: bool = True,
             show_percentage: bool = True) -> Element:
    """A progress bar (0..1). ``width=0`` fills the available space."""
    return _W.progress(float(value), label, width, _col(fill), _col(track),
                       show_track, show_percentage)


def badge(label: str, *, kind: str = "", style: Any = None) -> Element:
    """A bracketed tag. ``kind``: ""/success/error/warning/info/tool."""
    return _W.badge(label, style, kind)


def divider(label: str = "", *, line: Any = None, color: Any = None) -> Element:
    """A horizontal rule with an optional centered label."""
    ls = line if line is not None else _maya.BorderStyle.Single
    if isinstance(ls, str):
        ls = getattr(_maya.BorderStyle, ls.capitalize(), _maya.BorderStyle.Single)
    return _W.divider(label, ls, _col(color))


def spinner(*, style: Any = None) -> Element:
    """A single animated spinner frame (advance it yourself per frame)."""
    return _W.spinner(style)


def table(columns: Sequence[Any], rows: Sequence[Sequence[Any]], *,
          stripe: bool = True, bordered: bool = False, title: str = "",
          cell_padding: int = 1) -> Element:
    """A data table.

    ``columns`` is a list of header strings, or ``(header, width, align)``
    tuples where align is ``"left"``/``"center"``/``"right"``. ``rows`` is a
    list of row-lists; cells are stringified.
    """
    cols = []
    for c in columns:
        if isinstance(c, str):
            cols.append(c)
        else:
            header = c[0]
            width = c[1] if len(c) > 1 else 0
            align = c[2] if len(c) > 2 else ColumnAlign.Left
            if isinstance(align, str):
                align = _ALIGN.get(align.lower(), ColumnAlign.Left)
            cols.append((header, width, align))
    srows = [[str(cell) for cell in row] for row in rows]
    return _W.table(cols, srows, stripe, bordered, title, cell_padding)


def callout(title: str, body: str = "", *, kind: str = "info") -> Element:
    """A severity box. ``kind``: info/success/warning/error."""
    return _W.callout(title, body, kind)


def status_banner(text: str, *, kind: str = "info") -> Element:
    """A one-line status strip. ``kind``: info/warning/error."""
    return _W.status_banner(text, kind)


def breadcrumb(segments: Sequence[str]) -> Element:
    """A ``home › projects › file`` path trail."""
    return _W.breadcrumb([str(s) for s in segments])


def tabs(labels: Sequence[str], active: int = 0) -> Element:
    """A tab bar with one active tab highlighted."""
    return _W.tabs([str(s) for s in labels], active)


def bar_chart(bars: Sequence[Any], *, max_value: float = 0.0,
              color: Any = None) -> Element:
    """A horizontal bar chart.

    ``bars`` is a list of ``(label, value)`` or ``(label, value, color)``
    tuples. ``max_value=0`` auto-scales to the largest bar.
    """
    out = []
    for b in bars:
        label, value = b[0], float(b[1])
        bc = _col(b[2]) if len(b) > 2 else None
        out.append((str(label), value, bc))
    return _W.bar_chart(out, float(max_value), _col(color))


def gradient(text: str, start: Any, end: Any) -> Element:
    """Text with a per-character color gradient from ``start`` to ``end``."""
    return _W.gradient(text, _color(start), _color(end))


def heatmap(grid: Sequence[Sequence[float]], *, low: Any = None, high: Any = None,
            x_labels: Sequence[str] = (), y_labels: Sequence[str] = ()) -> Element:
    """A 2-D heatmap. ``grid`` is rows of floats; cells colour-interpolate
    from ``low`` to ``high``."""
    g = [[float(v) for v in row] for row in grid]
    return _W.heatmap(g, _col(low), _col(high),
                      [str(x) for x in x_labels], [str(y) for y in y_labels])


__all__ = [
    "GaugeStyle", "ColumnAlign",
    "sparkline", "gauge", "progress", "badge", "divider", "spinner",
    "table", "callout", "status_banner", "breadcrumb", "tabs",
    "bar_chart", "gradient", "heatmap",
]
