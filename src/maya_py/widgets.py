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
from .easy import color as _color, _el as _as_element

_W = _maya._widgets

# enums, re-exported for callers who want them explicitly
GaugeStyle = _W.GaugeStyle
ColumnAlign = _W.ColumnAlign
ButtonVariant = _W.ButtonVariant
TaskStatus = _W.TaskStatus
ToastLevel = _W.ToastLevel
TodoItemStatus = _W.TodoItemStatus
TodoListStatus = _W.TodoListStatus

_ALIGN = {"left": ColumnAlign.Left, "center": ColumnAlign.Center,
          "right": ColumnAlign.Right}

_BUTTON_VARIANT = {"default": ButtonVariant.Default, "primary": ButtonVariant.Primary,
                   "danger": ButtonVariant.Danger, "ghost": ButtonVariant.Ghost}

_TASK_STATUS = {"pending": TaskStatus.Pending, "inprogress": TaskStatus.InProgress,
                "in_progress": TaskStatus.InProgress, "running": TaskStatus.InProgress,
                "completed": TaskStatus.Completed, "done": TaskStatus.Completed}

_TOAST_LEVEL = {"info": ToastLevel.Info, "success": ToastLevel.Success,
                "warning": ToastLevel.Warning, "warn": ToastLevel.Warning,
                "error": ToastLevel.Error}

_TODO_ITEM = {"pending": TodoItemStatus.Pending, "inprogress": TodoItemStatus.InProgress,
              "in_progress": TodoItemStatus.InProgress, "running": TodoItemStatus.InProgress,
              "completed": TodoItemStatus.Completed, "done": TodoItemStatus.Completed}

_TODO_LIST = {"pending": TodoListStatus.Pending, "running": TodoListStatus.Running,
              "done": TodoListStatus.Done, "failed": TodoListStatus.Failed}


def _enum(value, table, default):
    if value is None:
        return default
    if isinstance(value, str):
        return table.get(value.lower().replace(" ", "_"), default)
    return value


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


def checkbox(label: str, checked: bool = False) -> Element:
    """A ``[x] label`` checkbox in its checked/unchecked state."""
    return _W.checkbox(str(label), bool(checked))


def toggle(label: str, on: bool = False) -> Element:
    """An on/off toggle switch (●━━ / ━━◯)."""
    return _W.toggle(str(label), bool(on))


def radio(items: Sequence[str], *, selected: int = 0,
          visible_count: int = 0) -> Element:
    """A radio group; ``selected`` is the chosen index."""
    return _W.radio([str(s) for s in items], int(selected), int(visible_count))


def select(items: Sequence[str], *, cursor: int = 0, indicator: str = "",
           visible_count: int = 0) -> Element:
    """A single-choice list with a ``❯`` cursor on row ``cursor``."""
    return _W.select([str(s) for s in items], int(cursor), indicator,
                     int(visible_count))


def slider(value: float, label: str = "", *, min: float = 0.0, max: float = 1.0,
           step: float = 0.01, width: int = 24, fill: Any = None,
           track: Any = None) -> Element:
    """A horizontal slider filled to ``value`` within ``[min, max]``.

    ``width`` is the track width in columns (a fixed width is required for a
    standalone render)."""
    return _W.slider(float(value), label, float(min), float(max), float(step),
                     int(width), _col(fill), _col(track))


def button(label: str, *, variant: Any = "default") -> Element:
    """A button. ``variant``: default/primary/danger/ghost."""
    return _W.button(str(label),
                     _enum(variant, _BUTTON_VARIANT, ButtonVariant.Default))


def calendar(year: int, month: int, *, today: Any = None) -> Element:
    """A month grid for ``year``/``month`` (1-12). ``today`` is an optional
    ``(y, m, d)`` tuple to highlight the current day."""
    t = tuple(today) if today is not None else None
    return _W.calendar(int(year), int(month), t)


def line_chart(data: Sequence[float], *, height: int = 8, label: str = "",
               color: Any = None) -> Element:
    """A braille line chart with a y-axis."""
    return _W.line_chart([float(x) for x in data], int(height), label,
                         _col(color))


def link(text: str, url: str = "", *, show_icon: bool = False,
         color: Any = None) -> Element:
    """An OSC-8 hyperlink (clickable in supporting terminals)."""
    return _W.link(str(text), str(url), bool(show_icon), _col(color))


def key_help(bindings: Sequence[Any], *, title: str = "") -> Element:
    """A keyboard-shortcut cheat sheet.

    ``bindings`` is a list of ``(key, description)`` or
    ``(key, description, group)`` tuples.
    """
    out = []
    for b in bindings:
        out.append((b,) if isinstance(b, str) else tuple(str(x) for x in b))
    return _W.key_help(out, title)


def timeline(events: Sequence[Any], *, show_connector: bool = True,
             compact: bool = False, frame: int = 0,
             track_width: int = 40) -> Element:
    """A vertical event timeline.

    Each event is a dict ``{label, detail, duration, status, bar_width}`` or a
    tuple ``(label, detail, duration, status, bar_width)``. ``status`` is
    pending/in_progress/completed.
    """
    out = []
    for e in events:
        if isinstance(e, dict):
            d = dict(e)
            if "status" in d:
                d["status"] = _enum(d["status"], _TASK_STATUS, TaskStatus.Pending)
            out.append(d)
        else:
            e = list(e)
            if len(e) > 3:
                e[3] = _enum(e[3], _TASK_STATUS, TaskStatus.Pending)
            out.append(tuple(e))
    return _W.timeline(out, bool(show_connector), bool(compact), int(frame),
                       int(track_width))


def tree(root: dict) -> Element:
    """A collapsible tree. ``root`` is a nested dict
    ``{label, expanded, selected, children: [...]}``."""
    return _W.tree(root)


def list_view(items: Sequence[Any], *, cursor: int = 0, filterable: bool = False,
              visible_count: int = 0) -> Element:
    """A scrollable item list with a highlighted ``cursor`` row.

    Items are strings, ``(label, description, icon)`` tuples, or dicts.
    """
    out = []
    for it in items:
        out.append(it if isinstance(it, (str, dict)) else tuple(str(x) for x in it))
    return _W.list_view(out, int(cursor), bool(filterable), int(visible_count))


def menu(items: Sequence[Any], *, cursor: int = 0) -> Element:
    """A dropdown menu. Items are strings, dicts, or
    ``(label, shortcut, enabled, separator)`` tuples."""
    out = [it if isinstance(it, (str, dict)) else tuple(it) for it in items]
    return _W.menu(out, int(cursor))


def disclosure(label: str, *, open: bool = False,
               content: Element | None = None) -> Element:
    """A collapsible section. When ``open`` and ``content`` is given, the
    content renders beneath the header."""
    return _W.disclosure(str(label), bool(open), content)


def toast(messages: Sequence[Any]) -> Element:
    """A stack of toast notifications. Each is a string or
    ``(message, level)`` tuple; level is info/success/warning/error."""
    out = []
    for m in messages:
        if isinstance(m, str):
            out.append(m)
        else:
            m = list(m)
            if len(m) > 1:
                m[1] = _enum(m[1], _TOAST_LEVEL, ToastLevel.Info)
            out.append(tuple(m))
    return _W.toast(out)


def todo_list(items: Sequence[Any], *, description: str = "",
              status: Any = "pending", elapsed: float = 0.0,
              expanded: bool = True) -> Element:
    """An agent-style todo card. Items are strings or ``(content, status)``
    tuples (status: pending/in_progress/completed). The card ``status`` is
    pending/running/done/failed."""
    out = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
        else:
            it = list(it)
            if len(it) > 1:
                it[1] = _enum(it[1], _TODO_ITEM, TodoItemStatus.Pending)
            out.append(tuple(it))
    return _W.todo_list(out, description,
                        _enum(status, _TODO_LIST, TodoListStatus.Pending),
                        float(elapsed), bool(expanded))


def title_chip(title: str, *, edge_color: Any = None, text_color: Any = None,
               max_chars: int = 0) -> Element:
    """A rounded title chip (the agent header style)."""
    return _W.title_chip(str(title), _col(edge_color), _col(text_color),
                         int(max_chars))


def model_badge(model: str, *, compact: bool = False) -> Element:
    """A model-name badge (e.g. ``✦ Opus 4``)."""
    return _W.model_badge(str(model), bool(compact))


def file_ref(path: str, *, line: int = 0, show_icon: bool = True) -> Element:
    """A ``📄 path:line`` file reference."""
    return _W.file_ref(str(path), int(line), bool(show_icon))


def inline_diff(before: str, after: str, *, label: str = "",
                show_header: bool = True) -> Element:
    """A word-level inline diff between ``before`` and ``after``."""
    return _W.inline_diff(str(before), str(after), label, bool(show_header))


def flame_chart(spans: Sequence[Any], *, time_scale: float = 0.0,
                width: int = 60, show_times: bool = True) -> Element:
    """A flamegraph. Spans are ``(label, start, duration, depth, color)``
    tuples (depth/color optional)."""
    out = []
    for s in spans:
        s = list(s)
        if len(s) > 4:
            s[4] = _col(s[4])
        out.append(tuple(s))
    return _W.flame_chart(out, float(time_scale), int(width), bool(show_times))


def waterfall(entries: Sequence[Any], *, time_scale: float = 0.0,
              bar_width: int = 30, show_labels: bool = True,
              frame: int = 0) -> Element:
    """A request waterfall. Entries are ``(label, start, duration, color)``
    tuples (color optional)."""
    out = []
    for e in entries:
        e = list(e)
        if len(e) > 3:
            e[3] = _col(e[3])
        out.append(tuple(e))
    return _W.waterfall(out, float(time_scale), int(bar_width),
                        bool(show_labels), int(frame))


def thinking(content: str = "", *, active: bool = False, expanded: bool = True,
             max_lines: int = 0) -> Element:
    """A collapsible 'thinking' block (agent reasoning trace)."""
    return _W.thinking(str(content), bool(active), bool(expanded),
                       int(max_lines))


def markdown(source: str) -> Element:
    """Render GFM markdown (headings, lists, tables, code, emphasis) to an
    Element — the same renderer maya uses for agent output."""
    return _W.markdown(str(source))


def image(pixels: Sequence[Sequence[Any]], *, color: Any = None) -> Element:
    """A 1-bit braille image. ``pixels`` is a 2-D grid of truthy/falsy values
    (on/off dots)."""
    grid = [[1 if v else 0 for v in row] for row in pixels]
    return _W.image(grid, _col(color))


def canvas(pixels: Sequence[Sequence[Any]]) -> Element:
    """A color half-block canvas from a static grid. ``pixels`` is a 2-D grid
    of colors (name, (r,g,b), "#rrggbb", maya Color) or ``None`` for a blank
    cell. For an imperative drawing surface (set_pixel/line/rect), use the
    :class:`Canvas` class instead."""
    grid = [[_col(v) for v in row] for row in pixels]
    return _W.canvas(grid)


class Canvas:
    """A stateful half-block drawing surface (maya's ``PixelCanvas``).

    Resolution is ``width × (height*2)`` pixels — each terminal cell holds two
    vertical pixels, so a 40×10 canvas is 40×20 pixels. Draw imperatively, then
    drop ``.element()`` (or the Canvas itself) into a layout:

        c = Canvas(40, 10)
        c.fill("black")
        c.line(0, 0, 39, 19, "sky")
        c.rect(5, 4, 12, 8, "lime")
        c.set_pixel(20, 10, "red")
        col("drawing:", c.element())

    All colours accept name / (r,g,b) / "#rrggbb" / Color, same as everywhere.
    """

    __slots__ = ("_c",)

    def __init__(self, width: int, height: int):
        self._c = _W.PixelCanvas(int(width), int(height))

    @property
    def width(self) -> int:
        return self._c.width

    @property
    def height(self) -> int:
        return self._c.height

    @property
    def pixel_height(self) -> int:
        """Pixel height (= ``height * 2``)."""
        return self._c.pixel_height

    def set_pixel(self, x: int, y: int, color: Any) -> "Canvas":
        """Set the pixel at ``(x, y)`` where ``y`` is in ``[0, height*2)``."""
        self._c.set_pixel(int(x), int(y), _color(color))
        return self

    def line(self, x1: int, y1: int, x2: int, y2: int, color: Any) -> "Canvas":
        """Draw a Bresenham line from ``(x1, y1)`` to ``(x2, y2)``."""
        self._c.line(int(x1), int(y1), int(x2), int(y2), _color(color))
        return self

    def rect(self, x: int, y: int, w: int, h: int, color: Any) -> "Canvas":
        """Draw an outline rectangle at ``(x, y)`` of size ``w×h`` pixels."""
        self._c.rect(int(x), int(y), int(w), int(h), _color(color))
        return self

    def fill(self, color: Any) -> "Canvas":
        """Flood the whole canvas with ``color``."""
        self._c.fill(_color(color))
        return self

    def clear(self) -> "Canvas":
        """Reset every pixel to the clear colour (black)."""
        self._c.clear()
        return self

    def element(self) -> Element:
        """Build the current drawing into an Element."""
        return self._c.element()


def picker(rows: Sequence[Any] = (), *, title: str = "", accent: Any = None,
           selected: int | None = None, header: Sequence[Element] = (),
           footer: Sequence[Element] = (), items: Sequence[Element] = (),
           min_width: int = 50, viewport_h: int = 14,
           cursor_color: Any = None, active_color: Any = None) -> Element:
    """A bordered command-palette / fuzzy-picker panel (Zed/VS Code style).

    ``rows`` is a list of entries the widget styles itself — a string, a
    ``(leading, trailing, selected, active)`` tuple, or a dict with those keys
    (plus optional ``leading_style`` / ``trailing_style``). The selected row
    gets the cursor edge-bar + bold; an ``active`` row gets the magenta
    "current" bar. ``selected`` is the 0-based cursor index (auto-derived from
    the first row flagged ``selected`` if omitted).

    ``header`` / ``footer`` are pre-built Elements painted above/below the list
    (e.g. a search line, a ``↑↓ move`` hint). For full layout control pass raw
    ``items`` Elements instead of ``rows`` (no auto-styling).
    """
    norm = []
    auto_sel = -1
    for i, r in enumerate(rows):
        if isinstance(r, str):
            norm.append(r)
        elif isinstance(r, dict):
            norm.append(dict(r))
            if r.get("selected"):
                auto_sel = i
        else:
            r = list(r)
            norm.append(r)
            if len(r) > 2 and r[2]:
                auto_sel = i
    sel = auto_sel if selected is None else int(selected)
    # When the caller gives a bare `selected` index (not per-row flags), mark
    # that row so the cursor edge-bar + bold styling actually appears.
    if selected is not None and 0 <= sel < len(norm):
        r = norm[sel]
        if isinstance(r, str):
            norm[sel] = {"leading": r, "selected": True}
        elif isinstance(r, dict):
            r["selected"] = True
        else:  # list form
            while len(r) < 3:
                r.append("" if len(r) < 2 else False)
            r[2] = True
    return _W.picker(norm, title, _col(accent), sel,
                     [_as_element(h) for h in header],
                     [_as_element(f) for f in footer],
                     list(items), int(min_width), int(viewport_h),
                     _col(cursor_color), _col(active_color))


# ── scrolling ───────────────────────────────────────
ScrollState = _W.ScrollState
ScrollbarStyle = _W.ScrollbarStyle

# scrollbar style presets by name
_SCROLL_STYLES = {
    "line": ScrollbarStyle.line, "block": ScrollbarStyle.block,
    "slim": ScrollbarStyle.slim, "heavy": ScrollbarStyle.heavy,
    "double": ScrollbarStyle.double_line, "double_line": ScrollbarStyle.double_line,
    "dotted": ScrollbarStyle.dotted, "dashed": ScrollbarStyle.dashed,
    "braille": ScrollbarStyle.braille, "ascii": ScrollbarStyle.ascii,
    "shadow": ScrollbarStyle.shadow, "minimal": ScrollbarStyle.minimal,
    "neon": ScrollbarStyle.neon, "retro": ScrollbarStyle.retro,
    "danger": ScrollbarStyle.danger, "pixel": ScrollbarStyle.pixel,
}


def _resolve_style(style, thumb_color, track_color):
    if style is None:
        st = ScrollbarStyle()
    elif isinstance(style, str):
        maker = _SCROLL_STYLES.get(style.lower())
        if maker is None:
            opts = ", ".join(sorted(_SCROLL_STYLES))
            raise ValueError(f"unknown scrollbar style {style!r}; valid: {opts}")
        st = maker()
    else:
        st = style
    if thumb_color is not None:
        st.thumb_color = _color(thumb_color)
    if track_color is not None:
        st.track_color = _color(track_color)
    return st


def scroll_state() -> "ScrollState":
    """A fresh scroll position (x/y offsets + max bounds). Hold one in your
    app state and drop it into ``viewport`` + ``scrollbar``.

    Scrolling "just works" with NO handler code: like maya, ``auto_dispatch``
    is on, so the run loop forwards arrow keys / PgUp / PgDn / Home / End and
    the mouse wheel + scrollbar drag to every on-screen scroll state
    automatically. Only set ``auto_dispatch = False`` and call
    ``scroll_handle`` yourself if you need custom routing (e.g. several
    independent scroll regions). Don't do both — that double-scrolls.
    """
    return ScrollState()


def viewport(content: Element, state: "ScrollState", *, width: int = 0,
             height: int = 0, grow: float = 0.0) -> Element:
    """Clip ``content`` to a ``width``×``height`` window scrolled by ``state``.
    0 on an axis means "fill available space". Pass ``grow=1`` so the window
    expands to fill its row/column (pushing a sibling scrollbar to the edge).
    The renderer writes the max scroll bounds back into ``state`` each frame.
    """
    return _W.viewport(content, state, width, height, grow)


def scrollbar(state: "ScrollState", viewport_size: int, *, axis: str = "y",
              style: Any = None, thumb_color: Any = None,
              track_color: Any = None) -> Element:
    """A scrollbar reflecting ``state`` over a ``viewport_size``-cell track.

    ``axis`` is "y" (vertical) or "x" (horizontal). ``style`` is a preset
    name ("line", "block", "slim", "neon", "braille", "ascii", ...) or a
    ``ScrollbarStyle``; ``thumb_color`` / ``track_color`` override colors.
    """
    st = _resolve_style(style, thumb_color, track_color)
    if axis == "x":
        return _W.scrollbar_x(state, viewport_size, st)
    return _W.scrollbar_y(state, viewport_size, st)


def scroll_handle(state: "ScrollState", ev: Any) -> bool:
    """Route an App event to ``state``: arrow keys / PgUp / PgDn / Home / End
    and mouse wheel + scrollbar drag. Returns True if consumed. Use inside
    ``@app.on_key`` / ``@app.on_mouse`` handlers (set ``state.auto_dispatch``
    off if you route manually)."""
    return _maya.scroll_handle(state, ev)


__all__ = [
    "GaugeStyle", "ColumnAlign", "ButtonVariant", "TaskStatus", "ToastLevel",
    "TodoItemStatus", "TodoListStatus", "ScrollState", "ScrollbarStyle",
    "sparkline", "gauge", "progress", "badge", "divider", "spinner",
    "table", "callout", "status_banner", "breadcrumb", "tabs",
    "bar_chart", "gradient", "heatmap",
    "checkbox", "toggle", "radio", "select", "slider", "button", "calendar",
    "line_chart", "link", "key_help", "timeline", "tree", "list_view", "menu",
    "disclosure", "toast", "todo_list", "title_chip", "model_badge",
    "file_ref", "inline_diff", "flame_chart", "waterfall", "thinking",
    "markdown", "image", "canvas", "Canvas", "picker",
    "scroll_state", "viewport", "scrollbar", "scroll_handle",
]
