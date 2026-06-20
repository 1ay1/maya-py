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
PopupStyle = _W.PopupStyle
BannerLevel = _W.BannerLevel
ToolCallStatus = _W.ToolCallStatus
ToolCallKind = _W.ToolCallKind

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

_POPUP_STYLE = {"info": PopupStyle.Info, "warning": PopupStyle.Warning,
                "warn": PopupStyle.Warning, "error": PopupStyle.Error}

_BANNER_LEVEL = {"info": BannerLevel.Info, "success": BannerLevel.Success,
                 "warning": BannerLevel.Warning, "warn": BannerLevel.Warning,
                 "error": BannerLevel.Error}

_TOOL_STATUS = {"pending": ToolCallStatus.Pending, "running": ToolCallStatus.Running,
                "completed": ToolCallStatus.Completed, "done": ToolCallStatus.Completed,
                "failed": ToolCallStatus.Failed, "error": ToolCallStatus.Failed,
                "confirmation": ToolCallStatus.Confirmation,
                "confirm": ToolCallStatus.Confirmation}

_TOOL_KIND = {"read": ToolCallKind.Read, "edit": ToolCallKind.Edit,
              "execute": ToolCallKind.Execute, "exec": ToolCallKind.Execute,
              "run": ToolCallKind.Execute, "search": ToolCallKind.Search,
              "delete": ToolCallKind.Delete, "move": ToolCallKind.Move,
              "fetch": ToolCallKind.Fetch, "think": ToolCallKind.Think,
              "agent": ToolCallKind.Agent, "other": ToolCallKind.Other}


def _enum(value, table, default):
    if value is None:
        return default
    if isinstance(value, str):
        return table.get(value.lower().replace(" ", "_"), default)
    return value


def _col(c: Any) -> Color | None:
    return None if c is None else _color(c)


def sparkline(data: Sequence[float], *, label: str = "", color: Any = None,
              show_min_max: bool = False, show_last: bool = False,
              range_min: float | None = None,
              range_max: float | None = None) -> Element:
    """An inline mini bar chart from a sequence of numbers. ``range_min`` /
    ``range_max`` pin the value axis (otherwise it auto-scales to the data)."""
    return _W.sparkline([float(x) for x in data], label, _col(color),
                        show_min_max, show_last, range_min, range_max)


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


def error_block(error_type: str, message: str = "", *, detail: str = "",
                hint: str = "", severity: str = "error",
                trace: Sequence[str] = ()) -> Element:
    """A boxed error panel: a severity icon + ``error_type`` + ``message``,
    with optional ``detail`` / ``hint`` lines and a stack ``trace``.
    ``severity``: error/warning/info.

        error_block("RateLimitError", "429 Too Many Requests",
                    detail="Retry after 30 seconds",
                    hint="Batch your requests or lower the rate")
    """
    return _W.error_block(str(error_type), str(message), str(detail), str(hint),
                          str(severity), [str(t) for t in trace])


def modal(title: str, *, content: Any = None, buttons: Sequence[Any] = (),
          focused: int = 0) -> Element:
    """A centered dialog: a title bar, a body, and a footer of action buttons.

    ``content`` is text or an Element. ``buttons`` is a list of labels or
    ``(label, variant)`` tuples where variant is default/primary/danger.
    ``focused`` highlights that button index.

        modal("Delete file?", content="This cannot be undone.",
              buttons=[("Cancel", "default"), ("Delete", "danger")], focused=1)
    """
    body = None if content is None else (
        content if isinstance(content, Element) else _as_element(content))
    btns = []
    for b in buttons:
        btns.append(b if isinstance(b, str) else tuple(b))
    return _W.modal(str(title), body, btns, int(focused))


def log_viewer(entries: Sequence[Any], *, visible: int = 0,
               scroll: int = 0) -> Element:
    """A scrolling log panel. Each entry is a
    ``(timestamp, message, level)`` tuple or a dict
    ``{timestamp, message, level}``; ``level``: debug/info/warn/error.

        log_viewer([("12:00:01", "Started", "info"),
                    ("12:00:02", "Disk full", "error")], visible=10)
    """
    out = []
    for e in entries:
        out.append(e if isinstance(e, dict) else tuple(str(x) for x in e))
    return _W.log_viewer(out, int(visible), int(scroll))


def command_palette(commands: Sequence[Any], *, cursor: int = 0) -> Element:
    """A fuzzy command menu (the ``Ctrl-K`` palette). Each command is a name,
    a ``(name, description, shortcut)`` tuple, or a dict with those keys.
    ``cursor`` is the highlighted row.

        command_palette([("Open File", "", "^O"),
                         ("Save", "write the buffer", "^S")], cursor=0)
    """
    out = []
    for c in commands:
        out.append(c if isinstance(c, (str, dict)) else tuple(str(x) for x in c))
    return _W.command_palette(out, int(cursor))


def activity_indicator(detail: str = "", *, color: Any = None) -> Element:
    """The animated “working…” ticker (a rotating word pool + sweep). Pass an
    optional trailing token like an elapsed time as ``detail``.

        activity_indicator("3.4s", color="cyan")
    """
    return _W.activity_indicator(str(detail), _col(color))


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
          visible_count: int = 0, on_indicator: str = "",
          off_indicator: str = "") -> Element:
    """A radio group; ``selected`` is the chosen index. ``on_indicator`` /
    ``off_indicator`` override the default ``●`` / ``○`` bullets."""
    return _W.radio([str(s) for s in items], int(selected), int(visible_count),
                    str(on_indicator), str(off_indicator))


def select(items: Sequence[str], *, cursor: int = 0, indicator: str = "",
           visible_count: int = 0, inactive_prefix: str = "") -> Element:
    """A single-choice list with a ``❯`` cursor on row ``cursor``.
    ``indicator`` overrides the cursor glyph; ``inactive_prefix`` is the lead-in
    for non-cursor rows."""
    return _W.select([str(s) for s in items], int(cursor), indicator,
                     int(visible_count), str(inactive_prefix))


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


def tree(root: dict, *, expanded_icon: str = "", collapsed_icon: str = "",
         leaf_prefix: str = "", indent_width: int = 0) -> Element:
    """A collapsible tree. ``root`` is a nested dict
    ``{label, expanded, selected, children: [...]}``. The icon / prefix /
    ``indent_width`` kwargs override the default ``▾`` / ``▸`` glyphs and 2-space
    indent."""
    return _W.tree(root, str(expanded_icon), str(collapsed_icon),
                   str(leaf_prefix), int(indent_width))


def list_view(items: Sequence[Any], *, cursor: int = 0, filterable: bool = False,
              visible_count: int = 0, indicator: str = "",
              inactive_prefix: str = "") -> Element:
    """A scrollable item list with a highlighted ``cursor`` row.

    Items are strings, ``(label, description, icon)`` tuples, or dicts.
    ``indicator`` overrides the cursor glyph; ``inactive_prefix`` is the lead-in
    for non-cursor rows.
    """
    out = []
    for it in items:
        out.append(it if isinstance(it, (str, dict)) else tuple(str(x) for x in it))
    return _W.list_view(out, int(cursor), bool(filterable), int(visible_count),
                        str(indicator), str(inactive_prefix))


def menu(items: Sequence[Any], *, cursor: int = 0) -> Element:
    """A dropdown menu. Items are strings, dicts, or
    ``(label, shortcut, enabled, separator)`` tuples."""
    out = [it if isinstance(it, (str, dict)) else tuple(it) for it in items]
    return _W.menu(out, int(cursor))


def disclosure(label: str, *, open: bool = False,
               content: Element | None = None, open_icon: str = "",
               closed_icon: str = "") -> Element:
    """A collapsible section. When ``open`` and ``content`` is given, the
    content renders beneath the header. ``open_icon`` / ``closed_icon`` override
    the default ``▼`` / ``▶`` triangles."""
    return _W.disclosure(str(label), bool(open), content,
                         str(open_icon), str(closed_icon))


def toast(messages: Sequence[Any], *, duration: float = 3.0,
          fade_time: float = 0.5, max_visible: int = 0) -> Element:
    """A stack of toast notifications. Each is a string or
    ``(message, level)`` tuple; level is info/success/warning/error.
    ``duration`` / ``fade_time`` / ``max_visible`` tune the manager."""
    out = []
    for m in messages:
        if isinstance(m, str):
            out.append(m)
        else:
            m = list(m)
            if len(m) > 1:
                m[1] = _enum(m[1], _TOAST_LEVEL, ToastLevel.Info)
            out.append(tuple(m))
    return _W.toast(out, float(duration), float(fade_time), int(max_visible))


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
                width: int = 60, show_times: bool = True,
                max_depth: int = 0) -> Element:
    """A flamegraph. Spans are ``(label, start, duration, depth, color)``
    tuples (depth/color optional). ``max_depth`` caps the stack rows shown."""
    out = []
    for s in spans:
        s = list(s)
        if len(s) > 4:
            s[4] = _col(s[4])
        out.append(tuple(s))
    return _W.flame_chart(out, float(time_scale), int(width), bool(show_times),
                          int(max_depth))


def waterfall(entries: Sequence[Any], *, time_scale: float = 0.0,
              bar_width: int = 30, show_labels: bool = True,
              frame: int = 0, show_times: bool = True) -> Element:
    """A request waterfall. Entries are ``(label, start, duration, color)``
    tuples (color optional). ``show_times`` appends the per-row duration."""
    out = []
    for e in entries:
        e = list(e)
        if len(e) > 3:
            e[3] = _col(e[3])
        out.append(tuple(e))
    return _W.waterfall(out, float(time_scale), int(bar_width),
                        bool(show_labels), int(frame), bool(show_times))


def token_stream(*, total_tokens: int = 0, tokens_per_sec: float = 0.0,
                 peak_rate: float = 0.0, elapsed: float = 0.0,
                 history: Sequence[float] = (), color: Any = None,
                 compact: bool = False) -> Element:
    """Live token-generation rate visualizer: a sparkline of ``history`` plus
    rate/total/peak/elapsed stats. ``compact`` collapses it to one line."""
    return _W.token_stream(int(total_tokens), float(tokens_per_sec),
                           float(peak_rate), float(elapsed),
                           [float(x) for x in history], _col(color),
                           bool(compact))


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


def popup(content: str, *, style: Any = "info") -> Element:
    """A floating tooltip/notice box. ``style``: info/warning/error."""
    return _W.popup(str(content), _enum(style, _POPUP_STYLE, PopupStyle.Info))


def overlay(base: Any, over: Any, *, present: bool = True) -> Element:
    """Composite ``over`` on top of ``base`` (a modal/popup layer). When
    ``present`` is False, only ``base`` renders."""
    return _W.overlay(_as_element(base), _as_element(over), bool(present))


def user_message(content: Any) -> Element:
    """A bordered user-message bubble. ``content`` is text or an Element."""
    return _W.user_message(content if isinstance(content, str)
                           else _as_element(content))


def assistant_message(content: Any) -> Element:
    """A padded assistant-message block. ``content`` is text or an Element."""
    return _W.assistant_message(_as_element(content))


def system_banner(message: str, *, level: Any = "info",
                  dismissable: bool = False) -> Element:
    """A full-width system notice rule. ``level``: info/success/warning/error."""
    return _W.system_banner(str(message),
                            _enum(level, _BANNER_LEVEL, BannerLevel.Info),
                            bool(dismissable))


def phase_chip(verb: str, *, glyph: str = "", color: Any = None,
               breathing: bool = False, frame: int = 0, verb_width: int = 10,
               elapsed: float = -1.0) -> Element:
    """A rounded status chip (``✷ Thinking  4.2s``). ``elapsed < 0`` omits the
    time tail; ``verb_width=0`` drops the verb. ``frame`` drives the breathing
    animation when ``breathing`` is on."""
    return _W.phase_chip(str(verb), str(glyph), _col(color), bool(breathing),
                         int(frame), int(verb_width), float(elapsed))


def context_gauge(used: int, max: int, *, cells: int = 10,
                  show_bar: bool = True) -> Element:
    """A compact token-budget meter (``used/max``) with a threshold-coloured
    bar. Renders blank when ``max <= 0``."""
    return _W.context_gauge(int(used), int(max), int(cells), bool(show_bar))


def context_window(segments: Sequence[Any], *, max_tokens: int = 200000,
                   width: int = 0, show_labels: bool = True,
                   show_percent: bool = True) -> Element:
    """A segmented context-window bar. ``segments`` is a list of
    ``(label, tokens)`` or ``(label, tokens, color)`` tuples; the bar fills to
    the sum of segment tokens out of ``max_tokens``."""
    out = []
    for s in segments:
        s = list(s)
        if len(s) > 2:
            s[2] = _col(s[2])
        out.append(tuple(s))
    return _W.context_window(out, int(max_tokens), int(width),
                             bool(show_labels), bool(show_percent))


def diff_view(path: str, diff: str, *, show_border: bool = True,
              show_line_numbers: bool = True) -> Element:
    """Render a unified-diff string (``@@ ... @@`` hunks, ``+``/``-`` lines)
    with syntax colours and line numbers."""
    return _W.diff_view(str(path), str(diff), bool(show_border),
                        bool(show_line_numbers))


def tool_call(name: str, *, kind: Any = "other", description: str = "",
              status: Any = "pending", elapsed: float = 0.0,
              expanded: bool = False, content: Element | None = None) -> Element:
    """An agent tool-call card. ``kind``:
    read/edit/execute/search/delete/move/fetch/think/agent/other.
    ``status``: pending/running/completed/failed/confirmation. ``content`` is an
    optional Element shown when ``expanded``."""
    return _W.tool_call(str(name), _enum(kind, _TOOL_KIND, ToolCallKind.Other),
                        str(description),
                        _enum(status, _TOOL_STATUS, ToolCallStatus.Pending),
                        float(elapsed), bool(expanded),
                        None if content is None else _as_element(content))


def git_graph(commits: Sequence[Any], *, max_branches: int = 0,
              show_hash: bool = True, show_author: bool = False,
              show_time: bool = True) -> Element:
    """An ASCII commit graph. Each commit is a dict
    ``{hash, message, author, time, branch, is_merge, is_head}`` or a tuple
    ``(hash, message, author, time, branch, is_merge, is_head)``."""
    out = [c if isinstance(c, dict) else tuple(c) for c in commits]
    return _W.git_graph(out, int(max_branches), bool(show_hash),
                        bool(show_author), bool(show_time))


def git_status(*, branch: str = "", ahead: int = 0, behind: int = 0,
               modified: int = 0, staged: int = 0, untracked: int = 0,
               deleted: int = 0, conflicts: int = 0, compact: bool = True,
               changed_files: Sequence[str] = ()) -> Element:
    """A git-status summary (branch, ahead/behind, dirty counts). ``compact``
    renders a single line; otherwise an expanded list with ``changed_files``."""
    return _W.git_status(str(branch), int(ahead), int(behind), int(modified),
                         int(staged), int(untracked), int(deleted),
                         int(conflicts), bool(compact),
                         [str(f) for f in changed_files])


def shortcut_row(bindings: Sequence[Any], *, color: Any = None) -> Element:
    """A width-adaptive keybinding hint row. ``bindings`` is a list of
    ``(key, label)`` or ``(key, label, key_color, priority)`` tuples; lower
    priority bindings degrade/drop first when space runs out."""
    out = []
    for b in bindings:
        b = list(b)
        if len(b) > 2:
            b[2] = _col(b[2])
        out.append(tuple(b))
    return _W.shortcut_row(out, _col(color))


def plan_view(tasks: Sequence[Any]) -> Element:
    """A task checklist. Each task is a string (pending) or a
    ``(label, status)`` tuple; status is pending/in_progress/completed."""
    out = []
    for t in tasks:
        if isinstance(t, str):
            out.append(t)
        else:
            t = list(t)
            if len(t) > 1:
                t[1] = _enum(t[1], _TASK_STATUS, TaskStatus.Pending)
            out.append(tuple(t))
    return _W.plan_view(out)


# ── scrolling ──────────────────────────────────
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
    "PopupStyle", "BannerLevel", "ToolCallStatus", "ToolCallKind",
    "sparkline", "gauge", "progress", "badge", "divider", "spinner",
    "table", "callout", "status_banner", "breadcrumb", "tabs",
    "error_block", "modal", "log_viewer", "command_palette", "activity_indicator",
    "bar_chart", "gradient", "heatmap",
    "checkbox", "toggle", "radio", "select", "slider", "button", "calendar",
    "line_chart", "link", "key_help", "timeline", "tree", "list_view", "menu",
    "disclosure", "toast", "todo_list", "title_chip", "model_badge",
    "file_ref", "inline_diff", "flame_chart", "waterfall", "token_stream",
    "thinking",
    "markdown", "image", "canvas", "Canvas", "picker",
    "popup", "overlay", "user_message", "assistant_message", "system_banner",
    "phase_chip", "context_gauge", "context_window", "diff_view", "tool_call",
    "git_graph", "git_status", "shortcut_row", "plan_view",
    "scroll_state", "viewport", "scrollbar", "scroll_handle",
]
