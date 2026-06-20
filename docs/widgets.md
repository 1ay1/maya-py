# Widgets

[← Manual index](index.md)

A **widget** in maya-py is a function that returns an `Element` — the same
immutable node a `card(...)` or `row(...)` produces. Each one wraps a native
maya C++ renderer (see the pipeline in [concepts.md §2](concepts.md)), so the
work happens once at the pybind11 boundary and the result drops straight into
any layout:

```python
from maya_py import col, sparkline, gauge, table, show

show(col(
    sparkline([3, 1, 4, 1, 5, 9, 2, 6], label="req/s", show_last=True),
    gauge(0.72, "load"),
    table(["Name", "Score"], [["Ada", "99"], ["Bob", "7"]], bordered=True),
))
```

Two things hold across the whole catalog:

- **Widgets are values, not commands.** They return a description of pixels;
  you compose them, you don't "draw" them. Re-read [concepts.md §1](concepts.md).
- **Colours are friendly everywhere.** Any `color=` / `fill=` / `track=`
  argument accepts a name (`"sky"`, `"red"`), an `(r, g, b)` tuple, a
  `"#rrggbb"` string, or a maya `Color`. `None` means "use the widget default."

Every example below is runnable as-is — wrap it in `show(...)` (or `to_string`)
to see it, as in the snippet above. Full gallery:
[examples/widgets_gallery.py](https://github.com/1ay1/maya-py/blob/master/examples/widgets_gallery.py)
and [examples/dashboard.py](https://github.com/1ay1/maya-py/blob/master/examples/dashboard.py).

---

## The count: 77 native renderers

The catalog covers **77 native renderers**, every one a thin wrapper over a
maya C++ widget. Counted from `widgets.py`'s `__all__`:

| Category | Renderers | n |
|----------|-----------|---|
| charts & meters | sparkline, gauge, progress, bar_chart, line_chart, heatmap, flame_chart, waterfall, activity_indicator | 9 |
| controls | checkbox, toggle, radio, select, slider, button | 6 |
| text & labels | badge, divider, spinner, callout, status_banner, system_banner, breadcrumb, tabs, gradient, link, title_chip, model_badge, file_ref, markdown, html, phase_chip, phase_accent | 17 |
| structure & nav | table, tree, list_view, menu, disclosure, key_help, calendar, timeline, picker, popup, overlay, modal, command_palette, log_viewer | 14 |
| agent UI | thinking, todo_list, toast, inline_diff, tool_call, plan_view, context_window, context_gauge, diff_view, git_graph, git_status, user_message, assistant_message, shortcut_row, activity_bar, file_changes, api_usage, cost_tracker, checkpoint_divider, turn_divider, streaming_cursor, token_stream, token_stream_sparkline, search_result, changes_strip, welcome_screen | 26 |
| graphics | image, canvas | 2 |
| scrolling | viewport, scrollbar | 2 |
| color helpers | gradient *(listed under text)* | — |
| **Total** | | **77** |

(The category buckets are presentational; the `__all__` total is what binds.)

What is **not** counted as a renderer: the `Canvas`/`Surface` classes are
imperative *drawing surfaces*, not presentational renderers (they ultimately
emit the same half-block / braille paint as `canvas(...)`); `scroll_state()` /
`scroll_handle(...)` are *state helpers* that produce/route a `ScrollState`;
and `rgb_lerp(...)` / `ramp(...)` are *colour* helpers (they return tuples /
int LUTs, not an `Element`). The widget enums (`GaugeStyle`, `ColumnAlign`,
`ButtonVariant`, `TaskStatus`, `ToastLevel`, `TodoItemStatus`,
`TodoListStatus`, `PopupStyle`, `BannerLevel`, `ToolCallStatus`,
`ToolCallKind`, `FileChangeKind`, `TurnRole`, `CursorStyle`, `SearchKind`,
`SearchStatus`, `ScrollbarStyle`) are option types.
Layout primitives (`card`, `row`, `col`, `tcol`/`trow`, …) live in
[layout.md](layout.md), not here.

---

## Input-shape flexibility

Several widgets accept *loose* inputs and normalise them for you. Worth
internalising before the reference:

- **List items** (`list_view`, `menu`) accept a bare `str`, a
  `(label, description, icon)` tuple, or a `dict`.
- **Timeline & todo statuses** accept either a **string**
  (`"pending"`, `"in_progress"`, `"completed"`, `"done"`, `"running"`,
  `"failed"`) or the exported enum (`TaskStatus`, `TodoItemStatus`,
  `TodoListStatus`). Strings are lower-cased and spaces become underscores, so
  `"In Progress"` works.
- **Chart series** (`bar_chart`, `flame_chart`, `waterfall`) take tuples where
  trailing fields (colour, depth, …) are optional.
- **Cells** in `table` are stringified for you — pass numbers directly.

---

## Charts & meters

### `sparkline`

```python
sparkline(data: Sequence[float], *, label: str = "", color=None,
          show_min_max: bool = False, show_last: bool = False) -> Element
```

An inline mini bar chart from a sequence of numbers.

```python
from maya_py import sparkline, show
show(sparkline([3, 1, 4, 1, 5, 9, 2, 6, 5, 3], label="req/s",
               color="sky", show_last=True))
```

Notable: `show_min_max` appends the range; `show_last` appends the most recent
value. Both are off by default for a clean one-line glyph.

### `gauge`

```python
gauge(value: float, label: str = "", *, color=None, style="arc") -> Element
```

A meter over `0..1`. `style` is `"arc"` (default) or `"bar"`, or a `GaugeStyle`
member.

```python
from maya_py import gauge, show
show(gauge(0.72, "CPU", color="lime", style="arc"))
```

### `progress`

```python
progress(value: float, label: str = "", *, width: int = 0, fill=None,
         track=None, show_track: bool = True,
         show_percentage: bool = True) -> Element
```

A horizontal progress bar over `0..1`. `width=0` fills the available space.

```python
from maya_py import progress, show
show(progress(0.4, "downloading", fill="sky", width=30))
```

Notable: set `show_track=False` for a bar with no background groove, or
`show_percentage=False` to drop the trailing `%`.

### `bar_chart`

```python
bar_chart(bars: Sequence[Any], *, max_value: float = 0.0, color=None) -> Element
```

Horizontal bars. Each `bars` entry is `(label, value)` or
`(label, value, color)`. `max_value=0` auto-scales to the largest bar; `color`
is the default for bars without their own.

```python
from maya_py import bar_chart, show
show(bar_chart([("Mon", 30), ("Tue", 80, "lime"), ("Wed", 55)], color="sky"))
```

### `line_chart`

```python
line_chart(data: Sequence[float], *, height: int = 8, label: str = "",
           color=None) -> Element
```

A braille line chart with a y-axis. `height` is the plot height in cells.

```python
from maya_py import line_chart, show
show(line_chart([1, 3, 2, 5, 4, 7, 6, 9, 8], height=6, label="latency"))
```

### `heatmap`

```python
heatmap(grid: Sequence[Sequence[float]], *, low=None, high=None,
        x_labels: Sequence[str] = (), y_labels: Sequence[str] = ()) -> Element
```

A 2-D heatmap. `grid` is rows of floats; each cell colour-interpolates from
`low` to `high`. Optional axis labels.

```python
from maya_py import heatmap, show
show(heatmap([[0, 2, 4], [1, 3, 5], [6, 4, 2]],
             low="#1e3a8a", high="orange",   # color: name / "#rrggbb" / (r,g,b)
             x_labels=["a", "b", "c"], y_labels=["x", "y", "z"]))
```

### `flame_chart`

```python
flame_chart(spans: Sequence[Any], *, time_scale: float = 0.0, width: int = 60,
            show_times: bool = True) -> Element
```

A flamegraph. Each span is `(label, start, duration, depth, color)` — `depth`
and `color` are optional trailing fields. `time_scale=0` auto-scales; `width`
is the chart width in columns.

```python
from maya_py import flame_chart, show
show(flame_chart([
    ("main", 0.0, 10.0, 0),
    ("parse", 1.0, 4.0, 1, "sky"),
    ("eval", 5.0, 4.0, 1, "lime"),
]))
```

### `waterfall`

```python
waterfall(entries: Sequence[Any], *, time_scale: float = 0.0, bar_width: int = 30,
          show_labels: bool = True, frame: int = 0) -> Element
```

A request waterfall (think browser network tab). Each entry is
`(label, start, duration, color)` — `color` optional. `frame` advances any
in-flight animation; `bar_width` is the track width in columns.

```python
from maya_py import waterfall, show
show(waterfall([
    ("DNS",      0.0,  20.0, "slate"),
    ("connect",  20.0, 40.0, "sky"),
    ("download", 60.0, 120.0, "lime"),
]))
```

---

## Controls

These render an interactive *control in a given state* — maya draws the visual,
you own the state (toggle the bool, move the cursor) in your update logic. None
of them capture keys on their own; see [apps.md](apps.md) for wiring them up.

### `checkbox`

```python
checkbox(label: str, checked: bool = False) -> Element
```

A `[x] label` box in its checked/unchecked state.

```python
from maya_py import checkbox, col, show
show(col(checkbox("Accept terms", True), checkbox("Subscribe", False)))
```

### `toggle`

```python
toggle(label: str, on: bool = False) -> Element
```

An on/off switch (`●━━` / `━━◯`).

```python
from maya_py import toggle, show
show(toggle("Dark mode", on=True))
```

### `radio`

```python
radio(items: Sequence[str], *, selected: int = 0, visible_count: int = 0) -> Element
```

A radio group; `selected` is the chosen index. `visible_count>0` windows a long
list to that many rows.

```python
from maya_py import radio, show
show(radio(["Small", "Medium", "Large"], selected=1))
```

### `select`

```python
select(items: Sequence[str], *, cursor: int = 0, indicator: str = "",
       visible_count: int = 0) -> Element
```

A single-choice list with a `❯` cursor on row `cursor`. `indicator` overrides
the cursor glyph; `visible_count>0` windows the list.

```python
from maya_py import select, show
show(select(["main.py", "utils.py", "test.py"], cursor=1))
```

### `slider`

```python
slider(value: float, label: str = "", *, min: float = 0.0, max: float = 1.0,
       step: float = 0.01, width: int = 24, fill=None, track=None) -> Element
```

A horizontal slider filled to `value` within `[min, max]`. `width` is the track
width in columns — a fixed width is required for a standalone render.

```python
from maya_py import slider, show
show(slider(60, "volume", min=0, max=100, step=5, width=30, fill="sky"))
```

### `button`

```python
button(label: str, *, variant="default") -> Element
```

A button. `variant` is `"default"` / `"primary"` / `"danger"` / `"ghost"`, or a
`ButtonVariant` member.

```python
from maya_py import button, row, show
show(row(button("Save", variant="primary"), button("Delete", variant="danger")))
```

---

## Text & labels

### `badge`

```python
badge(label: str, *, kind: str = "", style=None) -> Element
```

A bracketed tag. `kind` colours it: `""` (neutral), `"success"`, `"error"`,
`"warning"`, `"info"`, `"tool"`. `style` is an explicit maya `Style` override.

```python
from maya_py import badge, row, show
show(row(badge("NEW", kind="success"), badge("DEPRECATED", kind="warning")))
```

### `divider`

```python
divider(label: str = "", *, line=None, color=None) -> Element
```

A horizontal rule with an optional centered label. `line` is a `BorderStyle`
member or its name (`"single"`, `"double"`, `"dashed"`, …; defaults to single).

```python
from maya_py import divider, show
show(divider("Section", line="double", color="slate"))
```

### `spinner`

```python
spinner(*, style=None) -> Element
```

A single animated spinner *frame*. It does not animate itself — advance it per
frame from a continuous loop (`@app.on_frame`, `animate`, or `fps>0`); see
[examples/live_spinner.py](https://github.com/1ay1/maya-py/blob/master/examples/live_spinner.py).

```python
from maya_py import spinner, row, show
show(row(spinner(), " working…"))
```

### `callout`

```python
callout(title: str, body: str = "", *, kind: str = "info") -> Element
```

A severity box with a title and body. `kind`: `"info"` / `"success"` /
`"warning"` / `"error"`.

```python
from maya_py import callout, show
show(callout("Heads up", "Disk is 90% full.", kind="warning"))
```

### `status_banner`

```python
status_banner(text: str, *, kind: str = "info") -> Element
```

A one-line full-width status strip. `kind`: `"info"` / `"warning"` / `"error"`.

```python
from maya_py import status_banner, show
show(status_banner("Build passed in 4.2s", kind="info"))
```

### `breadcrumb`

```python
breadcrumb(segments: Sequence[str]) -> Element
```

A `home › projects › file` path trail.

```python
from maya_py import breadcrumb, show
show(breadcrumb(["home", "projects", "maya-py", "widgets.md"]))
```

### `tabs`

```python
tabs(labels: Sequence[str], active: int = 0) -> Element
```

A tab bar with one active tab highlighted.

```python
from maya_py import tabs, show
show(tabs(["Code", "Issues", "Pull Requests"], active=0))
```

### `gradient`

```python
gradient(text: str, start, end) -> Element
```

Text with a per-character colour gradient from `start` to `end`. Both endpoints
are required colours.

```python
from maya_py import gradient, show
show(gradient("maya-py", "magenta", "cyan"))
```

> Note ([concepts.md §7](concepts.md)): a static gradient is fine, but an
> *animated* one that emits a fresh shade per cell per frame grows maya's style
> pool — quantize to a fixed palette in hot loops.

### `link`

```python
link(text: str, url: str = "", *, show_icon: bool = False, color=None) -> Element
```

An OSC-8 hyperlink (clickable in supporting terminals). `show_icon` prepends a
link glyph.

```python
from maya_py import link, show
show(link("maya-py on GitHub", "https://github.com/1ay1/maya-py", show_icon=True))
```

### `title_chip`

```python
title_chip(title: str, *, edge_color=None, text_color=None, max_chars: int = 0) -> Element
```

A rounded title chip (the agent-header style). `max_chars>0` truncates.

```python
from maya_py import title_chip, show
show(title_chip("Refactor auth module", edge_color="magenta"))
```

### `model_badge`

```python
model_badge(model: str, *, compact: bool = False) -> Element
```

A model-name badge (e.g. `✦ Opus 4`). `compact` shortens it.

```python
from maya_py import model_badge, show
show(model_badge("Claude Opus 4"))
```

### `file_ref`

```python
file_ref(path: str, *, line: int = 0, show_icon: bool = True) -> Element
```

A `📄 path:line` file reference. `line=0` omits the line number; `show_icon`
toggles the leading glyph.

```python
from maya_py import file_ref, show
show(file_ref("src/maya_py/widgets.py", line=429))
```

### `markdown`

```python
markdown(source: str) -> Element
```

Renders GFM markdown (headings, lists, tables, code, emphasis) to an Element —
the same renderer maya uses for agent output.

```python
from maya_py import markdown, show
show(markdown("# Title\n\n- **bold** item\n- `code` item\n\n> a quote"))
```

### `html`

```python
html(source: str, *, theme: str = "dark") -> Element
```

Renders a subset of HTML to an Element — the same engine maya's markdown widget
uses for inline tags. `theme` is `dark` / `light` / `dark_ansi` / `light_ansi`.

```python
from maya_py import html, show
show(html("<b>bold</b> and <i>italic</i> and <code>mono</code>"))
```

### `error_block`

```python
error_block(error_type: str, message: str = "", *, detail: str = "", hint: str = "",
            severity: str = "error", trace: Sequence[str] = ()) -> Element
```

A structured error card: a typed header, a message, optional `detail` / `hint`
lines, and a `trace` stack. `severity` is `error` / `warning` / `info`.

```python
from maya_py import error_block, show
show(error_block("TypeError", "cannot add int and str",
                 hint="cast with str() or int()",
                 trace=["file.py:12 in add()", "main.py:3 in <module>"]))
```

### `activity_indicator`

```python
activity_indicator(detail: str = "", *, color=None) -> Element
```

The animated "working…" ticker (a rotating word pool + sweep). Pass an optional
trailing token like an elapsed time as `detail`.

```python
from maya_py import activity_indicator, show
show(activity_indicator("3.4s", color="cyan"))
```

---

## Structure & navigation

### `table`

```python
table(columns: Sequence[Any], rows: Sequence[Sequence[Any]], *, stripe: bool = True,
      bordered: bool = False, title: str = "", cell_padding: int = 1) -> Element
```

A data table. `columns` is a list of header strings, or `(header, width, align)`
tuples where `align` is `"left"` / `"center"` / `"right"` (or a `ColumnAlign`
member; `width=0` auto-sizes). `rows` is a list of row-lists; cells are
stringified for you.

```python
from maya_py import table, show
show(table(
    [("Name", 0, "left"), ("Score", 8, "right")],
    [["Ada", 99], ["Bob", 7], ["Cy", 42]],
    bordered=True, stripe=True, title="Leaderboard",
))
```

Notable: `stripe` zebra-stripes rows; `bordered` draws box borders;
`cell_padding` is the horizontal padding inside each cell. For per-frame hot
tables, pass tuple cells into layout instead (see [concepts.md §7](concepts.md)).

### `tree`

```python
tree(root: dict) -> Element
```

A collapsible tree. `root` is a nested dict
`{label, expanded, selected, children: [...]}`.

```python
from maya_py import tree, show
show(tree({
    "label": "src", "expanded": True, "children": [
        {"label": "maya_py", "expanded": True, "children": [
            {"label": "widgets.py", "selected": True},
            {"label": "easy.py"},
        ]},
        {"label": "tests"},
    ],
}))
```

### `list_view`

```python
list_view(items: Sequence[Any], *, cursor: int = 0, filterable: bool = False,
          visible_count: int = 0) -> Element
```

A scrollable item list with a highlighted `cursor` row. Items are strings,
`(label, description, icon)` tuples, or dicts. `filterable` shows a filter
affordance; `visible_count>0` windows the list.

```python
from maya_py import list_view, show
show(list_view([
    "Plain item",
    ("Deploy", "push to prod", "🚀"),
    {"label": "Settings", "description": "preferences", "icon": "⚙"},
], cursor=1))
```

### `menu`

```python
menu(items: Sequence[Any], *, cursor: int = 0) -> Element
```

A dropdown menu. Items are strings, dicts, or
`(label, shortcut, enabled, separator)` tuples.

```python
from maya_py import menu, show
show(menu([
    ("Open", "⌘O", True, False),
    ("Save", "⌘S", True, False),
    ("", "", False, True),          # separator row
    ("Quit", "⌘Q", True, False),
], cursor=0))
```

### `disclosure`

```python
disclosure(label: str, *, open: bool = False, content: Element | None = None) -> Element
```

A collapsible section. When `open` and `content` is given, the content renders
beneath the header.

```python
from maya_py import disclosure, col, show
show(disclosure("Details", open=True, content=col("line one", "line two")))
```

### `key_help`

```python
key_help(bindings: Sequence[Any], *, title: str = "") -> Element
```

A keyboard-shortcut cheat sheet. Each binding is `(key, description)` or
`(key, description, group)`.

```python
from maya_py import key_help, show
show(key_help([
    ("q", "quit", "general"),
    ("↑/↓", "move", "nav"),
    ("enter", "select", "nav"),
], title="Shortcuts"))
```

### `calendar`

```python
calendar(year: int, month: int, *, today=None) -> Element
```

A month grid for `year`/`month` (1-12). `today` is an optional `(y, m, d)` tuple
to highlight the current day.

```python
from maya_py import calendar, show
show(calendar(2026, 6, today=(2026, 6, 15)))
```

### `timeline`

```python
timeline(events: Sequence[Any], *, show_connector: bool = True, compact: bool = False,
         frame: int = 0, track_width: int = 40) -> Element
```

A vertical event timeline. Each event is a dict
`{label, detail, duration, status, bar_width}` or a tuple
`(label, detail, duration, status, bar_width)`. `status` accepts a string
(`"pending"` / `"in_progress"` / `"completed"`) or a `TaskStatus` member.
`frame` advances any in-flight bar animation.

```python
from maya_py import timeline, TaskStatus, show
show(timeline([
    {"label": "Fetch", "detail": "GET /api", "duration": "0.4s", "status": "completed"},
    {"label": "Parse", "duration": "0.1s", "status": TaskStatus.InProgress},
    {"label": "Render", "status": "pending"},
]))
```

### `picker`

```python
picker(rows: Sequence[Any] = (), *, title: str = "", accent=None, selected: int | None = None,
       header: Sequence[Element] = (), footer: Sequence[Element] = (),
       items: Sequence[Element] = (), min_width: int = 50, viewport_h: int = 14,
       cursor_color=None, active_color=None) -> Element
```

A bordered command-palette / fuzzy-picker panel (Zed / VS Code style). Each
`rows` entry is a string, a `(leading, trailing, selected, active)` tuple, or a
dict with those keys (plus optional `leading_style` / `trailing_style`). The
selected row gets the cursor edge-bar + bold; an `active` row gets the magenta
"current" bar. `selected` is the 0-based cursor index (auto-derived from the
first row flagged `selected` if omitted).

`header` / `footer` are pre-built Elements painted above/below the list (a
search line, a `↑↓ move` hint). For full layout control, pass raw `items`
Elements instead of `rows` (no auto-styling).

```python
from maya_py import picker, show
show(picker(
    rows=[
        ("Go to File", "⌘P"),
        ("Go to Symbol", "⌘O"),
        ("Command Palette", "⌘⇧P"),
    ],
    title="Quick Open", selected=0, accent="magenta",
))
```

### `modal`

```python
modal(title: str, *, content=None, buttons: Sequence[Any] = (), focused: int = 0) -> Element
```

A centered dialog: a title bar, a body, and a footer of action buttons.
`content` is text or an Element; `buttons` is a list of labels or
`(label, variant)` tuples where `variant` is `default` / `primary` / `danger`;
`focused` highlights that button index. Pair it with `overlay(base, modal(...))`
to float it over your UI.

```python
from maya_py import modal, show
show(modal("Delete file?", content="This cannot be undone.",
           buttons=[("Cancel", "default"), ("Delete", "danger")], focused=1))
```

### `command_palette`

```python
command_palette(commands: Sequence[Any], *, cursor: int = 0) -> Element
```

A fuzzy command menu (the `Ctrl-K` palette). Each command is a name, a
`(name, description, shortcut)` tuple, or a dict with those keys. `cursor` is
the highlighted row.

```python
from maya_py import command_palette, show
show(command_palette([("Open File", "", "^O"),
                      ("Save", "write the buffer", "^S")], cursor=0))
```

### `log_viewer`

```python
log_viewer(entries: Sequence[Any], *, visible: int = 0, scroll: int = 0) -> Element
```

A scrolling log panel. Each entry is a `(timestamp, message, level)` tuple or a
dict `{timestamp, message, level}`; `level` is `debug` / `info` / `warn` /
`error`. `visible>0` windows the rows; `scroll` is the top offset.

```python
from maya_py import log_viewer, show
show(log_viewer([("12:00:01", "Started", "info"),
                 ("12:00:02", "Disk full", "error")], visible=10))
```

---

## Agent UI

These match the visual language of a coding agent — thinking traces, task
lists, tool calls, message bubbles, git status, context budgets. See
[examples/agent.py](https://github.com/1ay1/maya-py/blob/master/examples/agent.py)
and [examples/widgets_gallery.py](https://github.com/1ay1/maya-py/blob/master/examples/widgets_gallery.py).

### `thinking`

```python
thinking(content: str = "", *, active: bool = False, expanded: bool = True,
         max_lines: int = 0) -> Element
```

A collapsible "thinking" block (an agent reasoning trace). `active` shows the
live in-progress treatment; `expanded` shows the body; `max_lines>0` caps the
visible lines.

```python
from maya_py import thinking, show
show(thinking("Let me check the config, then run the tests…",
              active=True, max_lines=3))
```

### `todo_list`

```python
todo_list(items: Sequence[Any], *, description: str = "", status="pending",
          elapsed: float = 0.0, expanded: bool = True) -> Element
```

An agent-style todo card. Items are strings or `(content, status)` tuples,
where the *item* status is `"pending"` / `"in_progress"` / `"completed"` (or a
`TodoItemStatus` member). The *card* `status` is `"pending"` / `"running"` /
`"done"` / `"failed"` (or a `TodoListStatus` member). `elapsed` shows a timer.

```python
from maya_py import todo_list, TodoItemStatus, show
show(todo_list([
    ("Read the source", "completed"),
    ("Write the docs", TodoItemStatus.InProgress),
    ("Verify the count", "pending"),
], description="Documenting widgets", status="running", elapsed=12.5))
```

### `toast`

```python
toast(messages: Sequence[Any]) -> Element
```

A stack of toast notifications. Each is a string or `(message, level)` tuple;
`level` is `"info"` / `"success"` / `"warning"` / `"error"` (or a `ToastLevel`
member).

```python
from maya_py import toast, ToastLevel, show
show(toast([
    ("Saved", "success"),
    ("Low memory", ToastLevel.Warning),
    "Plain info toast",
]))
```

### `inline_diff`

```python
inline_diff(before: str, after: str, *, label: str = "", show_header: bool = True) -> Element
```

A word-level inline diff between `before` and `after`. `label` titles the block;
`show_header` toggles the header row.

```python
from maya_py import inline_diff, show
show(inline_diff("the quick brown fox",
                 "the slow brown dog",
                 label="edit"))
```

### `tool_call`

```python
tool_call(name: str, *, kind="other", description: str = "", status="pending",
          elapsed: float = 0.0, expanded: bool = False, content=None) -> Element
```

An agent tool-call card. `kind` is `read` / `edit` / `execute` / `search` /
`delete` / `move` / `fetch` / `think` / `agent` / `other` (or a `ToolCallKind`);
`status` is `pending` / `running` / `completed` / `failed` / `confirmation` (or
a `ToolCallStatus`). `content` is an optional Element shown when `expanded`.

```python
from maya_py import tool_call, show
show(tool_call("Read", kind="read", description="src/auth.py",
               status="completed", elapsed=1.2))
```

### `plan_view`

```python
plan_view(tasks: Sequence[Any]) -> Element
```

A task checklist. Each task is a string (pending) or a `(label, status)` tuple;
status is `pending` / `in_progress` / `completed` (or a `TaskStatus`).

```python
from maya_py import plan_view, show
show(plan_view([("Audit widgets", "completed"),
                ("Write docs", "in_progress"),
                "Ship it"]))
```

### `phase_chip`

```python
phase_chip(verb: str, *, glyph: str = "", color=None, breathing: bool = False,
           frame: int = 0, verb_width: int = 10, elapsed: float = -1.0) -> Element
```

A status chip for the current agent phase ("Thinking", "Running", …). `breathing`
+ `frame` animate a pulse; `elapsed >= 0` appends a timer.

### `context_gauge`

```python
context_gauge(used: int, max: int, *, cells: int = 10, show_bar: bool = True) -> Element
```

A compact token-budget meter (`used/max`) with a threshold-coloured bar.

### `context_window`

```python
context_window(segments: Sequence[Any], *, max_tokens: int = 200000, width: int = 0,
               show_labels: bool = True, show_percent: bool = True) -> Element
```

A segmented context-budget bar. Each segment is a `(label, tokens)` /
`(label, tokens, color)` tuple or a dict; segments fill toward `max_tokens`.

### `diff_view`

```python
diff_view(path: str, diff: str, *, show_border: bool = True,
          show_line_numbers: bool = True) -> Element
```

Renders a unified-diff string (`@@ … @@` hunks, `+`/`-` lines) with syntax
colouring under a `path` header.

### `git_graph`

```python
git_graph(commits: Sequence[Any], *, max_branches: int = 0, show_hash: bool = True,
          show_author: bool = False, show_time: bool = True) -> Element
```

An ASCII commit graph. Each commit is a dict
`{hash, message, author, time, branch, is_merge, is_head}` or the matching tuple.

### `git_status`

```python
git_status(*, branch: str = "", ahead: int = 0, behind: int = 0, modified: int = 0,
           staged: int = 0, untracked: int = 0, deleted: int = 0, conflicts: int = 0,
           compact: bool = True, changed_files: Sequence[str] = ()) -> Element
```

A git-status summary (branch, ahead/behind, dirty counts). `compact` renders a
single line; otherwise an expanded list including `changed_files`.

### `activity_bar`

```python
activity_bar(*, model: str = "", input_tokens: int = 0, output_tokens: int = 0,
             cost: float = 0.0, context_pct: int = 0, status: str = "") -> Element
```

A single-line model/usage status strip (the Claude Code / Zed activity bar):
`model · ↑in ↓out · $cost · ctx%`. Omitted fields drop out.

```python
from maya_py import activity_bar, show
show(activity_bar(model="claude-opus-4", input_tokens=12000, output_tokens=3400,
                  cost=0.21, context_pct=42, status="streaming"))
```

### `file_changes`

```python
file_changes(changes: Sequence[Any], *, compact: bool = False) -> Element
```

A session file-change summary with `+`/`~`/`-` status icons and ±line counts.
Each change is a dict `{path, kind, added, removed}` or a tuple
`(path, kind, added, removed)`; `kind` is `created` / `modified` / `deleted` /
`renamed` (or a `FileChangeKind`).

```python
from maya_py import file_changes, show
show(file_changes([
    ("src/auth.py", "modified", 18, 4),
    ("src/new.py", "created", 60, 0),
    ("old.py", "deleted", 0, 120),
]))
```

### `api_usage`

```python
api_usage(*, requests: int = 0, request_limit: int = 0, tokens: int = 0,
          token_limit: int = 0, latency_ms: int = 0, errors: int = 0,
          compact: bool = False) -> Element
```

An API rate-limit / usage panel: request + token mini-bars that shade
green → yellow → red as they approach their limits, plus latency and error
count. A limit of `0` hides that row.

### `cost_tracker`

```python
cost_tracker(turns: Sequence[Any], *, compact: bool = False) -> Element
```

A per-turn + cumulative token/cost breakdown. Each turn is a dict with keys
`input` / `output` / `cache_read` / `cache_write` / `cost` / `latency_ms`, or a
tuple `(input, output, cost)`.

### `token_stream`

```python
token_stream(*, total_tokens: int = 0, tokens_per_sec: float = 0.0,
             peak_rate: float = 0.0, elapsed: float = 0.0,
             history: Sequence[float] = (), color=None, compact: bool = False) -> Element
```

A live token-generation visualiser: a sparkline of `history` plus
rate / total / peak / elapsed stats. `compact` collapses it to one line.

### `token_stream_sparkline`

```python
token_stream_sparkline(*, rate: float = 0.0, total: int = 0,
                       history: Sequence[float] = (), color=None,
                       live: bool = False) -> Element
```

A fixed-width `⚡ 23.4 t/s ▁▂▃▄▅▆▇█ 1234` streaming status slot. Every segment
is a stable display width, so neighbouring chips don't shift as numbers tick.
`live=False` dims it (frozen).

### `streaming_cursor`

```python
streaming_cursor(label: str = "", *, style=None, active: bool = True,
                 frame: int = 0) -> Element
```

An animated typing/streaming indicator. `style` is `block` / `dots` / `bar` /
`pulse` (or a `CursorStyle`); `frame` advances the animation; `active=False`
freezes it.

### `checkpoint_divider`

```python
checkpoint_divider(label: str = "", *, color=None) -> Element
```

A full-width `↺ Restore checkpoint` rule marking a snapshot point.

### `turn_divider`

```python
turn_divider(role=None, *, turn_number: int = 0, show_role: bool = True) -> Element
```

A conversation-turn separator (`─── ✦ Claude #3 ───`). `role` is `user` /
`assistant` / `system` / `tool` (or a `TurnRole`); `turn_number` numbers it.

### `phase_accent`

```python
phase_accent(*, color=None, position: str = "top") -> Element
```

A soft-shelf full-width rule (a row of `▁`/`▔` half-blocks) in a phase colour.
`position` is `top` or `bottom` — pair it above/below a phase block.

### `search_result`

```python
search_result(groups: Sequence[Any], *, kind=None, pattern: str = "",
              status=None, elapsed: float = 0.0, expanded: bool = True,
              max_matches_per_file: int = 0) -> Element
```

A Grep/Glob search-results panel (bordered file groups + matches). `groups` is
a list of dicts `{file_path, matches}` or tuples `(file_path, matches)`; each
match is `(line, content)`, a string, or `{line, content}`. `kind` is `grep` /
`glob` (or a `SearchKind`); `status` is `pending` / `searching` / `done` /
`failed` (or a `SearchStatus`).

```python
from maya_py import search_result, show
show(search_result([
    ("src/auth.py", [(12, "def login(user):"), (88, "    return token")]),
    ("src/api.py", [(4, "import auth")]),
], kind="grep", pattern="auth", status="done", elapsed=0.03))
```

### `changes_strip`

```python
changes_strip(changes: Sequence[Any], *, border_color=None, text_color=None,
              accept_color=None, reject_color=None) -> Element
```

A bordered "session has pending changes" banner over a file list — the same
change shape as `file_changes`. Empty `changes` renders to an empty Element, so
you can drop it into a stack unconditionally.

### `welcome_screen`

```python
welcome_screen(*, tagline: str = "", model_badge: Element | None = None,
               profile_label: str = "", profile_color=None,
               starters_title: str = "", starters: Sequence[str] = (),
               hint_intro: str = "", hints: Sequence[Any] = (),
               sigil_color=None, accent_color=None,
               sigil_draw_ms: int = 0, max_rows: int = 0) -> Element
```

An empty-thread brand splash: a pixel-art wordmark, `tagline`, a model +
profile chip row, an optional `starters` card, and a hint footer. `model_badge`
is a built Element (e.g. `model_badge("Opus 4")`); `hints` is a list of
`(key, label)` or `(key, label, color)` tuples. `sigil_draw_ms=0` renders the
completed mark statically; raise it for the cascade-in intro inside an app loop.

```python
from maya_py import welcome_screen, model_badge, show
show(welcome_screen(
    tagline="your terminal coding agent",
    model_badge=model_badge("Opus 4"),
    profile_label="default",
    starters_title="Try",
    starters=["Explain this repo", "Fix the failing test"],
    hints=[("q", "quit"), ("?", "help")],
))
```

### `user_message` / `assistant_message`

```python
user_message(content) -> Element
assistant_message(content) -> Element
```

Chat bubbles: `user_message` is a bordered user turn, `assistant_message` a
padded reply block. `content` is text or an Element.

### `system_banner`

```python
system_banner(message: str, *, level="info", dismissable: bool = False) -> Element
```

A full-width system notice rule. `level` is `info` / `success` / `warning` /
`error` (or a `BannerLevel`).

### `shortcut_row`

```python
shortcut_row(bindings: Sequence[Any], *, color=None) -> Element
```

A width-adaptive keybinding hint row. `bindings` is a list of `(key, label)` or
`(key, label, key_color, priority)` tuples; lower-priority bindings degrade or
drop first when space runs out.

```python
from maya_py import shortcut_row, show
show(shortcut_row([("q", "quit"), ("/", "search"), ("?", "help")]))
```

### `popup` / `overlay`

```python
popup(content: str, *, style="info") -> Element
overlay(base, over, *, present: bool = True) -> Element
```

`popup` is a floating notice box (`style`: `info` / `warning` / `error`, or a
`PopupStyle`). `overlay` z-stacks `over` on top of `base` for a modal layer;
with `present=False` only `base` renders — the toggle you flip to show/hide a
modal.

---

## Graphics

### `image`

```python
image(pixels: Sequence[Sequence[Any]], *, color=None) -> Element
```

A 1-bit braille image. `pixels` is a 2-D grid of truthy/falsy values (on/off
dots), packed into braille cells (denser than the cell grid). `color` tints the
dots.

```python
from maya_py import image, show
grid = [[1 if (x + y) % 2 == 0 else 0 for x in range(16)] for y in range(8)]
show(image(grid, color="sky"))
```

### `canvas`

```python
canvas(pixels: Sequence[Sequence[Any]]) -> Element
```

A colour half-block canvas from a *static* grid. `pixels` is a 2-D grid of
colours (name / `(r,g,b)` / `"#rrggbb"` / `Color`), or `None` for a blank cell.
For an imperative drawing surface, use the `Canvas` class below.

```python
from maya_py import canvas, show
red, blu = "red", "sky"
show(canvas([
    [red, red, None, blu, blu],
    [red, None, None, None, blu],
    [None, None, "lime", None, None],
]))
```

### The `Canvas` class — imperative drawing

```python
Canvas(width: int, height: int)
```

A stateful half-block drawing surface (maya's `PixelCanvas`). The resolution is
`width × (height*2)` **pixels** — each terminal cell stacks two vertical pixels,
so a 40×10 canvas is 40×20 pixels. Draw imperatively, then drop `.element()`
(or feed it through `col(...)`) into a layout. The drawing methods return
`self`, so they chain.

**Properties**

| Property | Returns |
|----------|---------|
| `width` | cell width (= pixel width) |
| `height` | cell height |
| `pixel_height` | pixel height (`= height * 2`) |

**Methods**

| Method | Effect |
|--------|--------|
| `set_pixel(x, y, color)` | set the pixel at `(x, y)`, `y ∈ [0, height*2)` |
| `line(x1, y1, x2, y2, color)` | Bresenham line |
| `rect(x, y, w, h, color)` | outline rectangle, `w×h` pixels |
| `fill(color)` | flood the whole canvas |
| `clear()` | reset every pixel to the clear colour (black) |
| `element()` | build the current drawing into an `Element` |

```python
from maya_py import Canvas, col, show

c = Canvas(40, 10)              # 40×20 pixels
c.fill("black")
c.line(0, 0, 39, 19, "sky")
c.rect(5, 4, 12, 8, "lime")
c.set_pixel(20, 10, "red")
show(col("drawing:", c.element()))
```

See [examples/paint.py](https://github.com/1ay1/maya-py/blob/master/examples/paint.py)
and [examples/canvas.py](https://github.com/1ay1/maya-py/blob/master/examples/canvas.py).
For a *size-aware* drawing that fills its box every frame, prefer the
`pixel_canvas` / `halfblock` helpers (they get the live measure pass — see the
note in [concepts.md §8](concepts.md)).

---

## Scrolling

Scrolling composes from a `ScrollState` (held in your app state) dropped into a
`viewport` (which clips content) and an optional `scrollbar` (which visualises
position). The big payoff: **scroll states auto-dispatch** — the run loop
forwards arrows / PgUp / PgDn / Home / End and (with `mouse=True`) the wheel and
scrollbar drag to every on-screen scroll state with **no handler code**. The
full story is [concepts.md §6](concepts.md); the API:

### `scroll_state` *(state helper, not a renderer)*

```python
scroll_state() -> ScrollState
```

A fresh scroll position (x/y offsets + max bounds). `auto_dispatch` is on by
default. Set `state.auto_dispatch = False` only if you route events yourself
with `scroll_handle` (doing both double-scrolls).

### `viewport`

```python
viewport(content: Element, state: ScrollState, *, width: int = 0, height: int = 0,
         grow: float = 0.0) -> Element
```

Clips `content` to a `width`×`height` window scrolled by `state`. `0` on an axis
means "fill available space"; `grow=1` expands the window to fill its row/column
(pushing a sibling scrollbar to the edge). The renderer writes the max scroll
bounds back into `state` each frame.

### `scrollbar`

```python
scrollbar(state: ScrollState, viewport_size: int, *, axis: str = "y", style=None,
          thumb_color=None, track_color=None) -> Element
```

A scrollbar reflecting `state` over a `viewport_size`-cell track. `axis` is
`"y"` (vertical) or `"x"` (horizontal). `style` is a preset *name* (see
`ScrollbarStyle` below) or a `ScrollbarStyle`; `thumb_color` / `track_color`
override colours.

### `scroll_handle` *(state helper, not a renderer)*

```python
scroll_handle(state: ScrollState, ev: Any) -> bool
```

Manually route an App event to `state` (arrows / PgUp / PgDn / Home / End +
wheel + drag). Returns `True` if consumed. Only needed when driving the
low-level `run` loop yourself or with `auto_dispatch = False`.

**Putting it together**

```python
from maya_py import App, scroll_state, viewport, scrollbar, row, col

app = App("log", quit_keys=("q",), sc=scroll_state())

@app.view
def view(s):
    body = col(*[f"line {i}" for i in range(200)])
    return row(
        viewport(body, s.sc, grow=1, height=20),
        scrollbar(s.sc, 20, style="neon"),
    )

# app.run()   # arrows / PgUp / wheel scroll with no handler code
```

Examples: [examples/scroll.py](https://github.com/1ay1/maya-py/blob/master/examples/scroll.py),
[examples/scroll_styles.py](https://github.com/1ay1/maya-py/blob/master/examples/scroll_styles.py).

---

## The enums

Every option that takes a string also accepts the corresponding enum member,
re-exported from the top-level package (`from maya_py import GaugeStyle`, …).
Values copied from source:

| Enum | Members | Used by |
|------|---------|---------|
| `GaugeStyle` | `Arc`, `Bar` | `gauge(style=)` |
| `ColumnAlign` | `Left`, `Center`, `Right` | `table` column tuples |
| `ButtonVariant` | `Default`, `Primary`, `Danger`, `Ghost` | `button(variant=)` |
| `TaskStatus` | `Pending`, `InProgress`, `Completed` | `timeline` event status |
| `ToastLevel` | `Info`, `Success`, `Warning`, `Error` | `toast` message level |
| `TodoItemStatus` | `Pending`, `InProgress`, `Completed` | `todo_list` item status |
| `TodoListStatus` | `Pending`, `Running`, `Done`, `Failed` | `todo_list` card status |
| `PopupStyle` | `Info`, `Warning`, `Error` | `popup(style=)` |
| `BannerLevel` | `Info`, `Success`, `Warning`, `Error` | `system_banner(level=)` |
| `ToolCallStatus` | `Pending`, `Running`, `Completed`, `Failed`, `Confirmation` | `tool_call(status=)` |
| `ToolCallKind` | `Read`, `Edit`, `Execute`, `Search`, `Delete`, `Move`, `Fetch`, `Think`, `Agent`, `Other` | `tool_call(kind=)` |
| `FileChangeKind` | `Created`, `Modified`, `Deleted`, `Renamed` | `file_changes` / `changes_strip` kind |
| `TurnRole` | `User`, `Assistant`, `System`, `Tool` | `turn_divider(role=)` |
| `CursorStyle` | `Block`, `Dots`, `Bar`, `Pulse` | `streaming_cursor(style=)` |
| `SearchKind` | `Grep`, `Glob` | `search_result(kind=)` |
| `SearchStatus` | `Pending`, `Searching`, `Done`, `Failed` | `search_result(status=)` |
| `ScrollbarStyle` | `line`, `block`, `slim`, `heavy`, `double_line`, `dotted`, `dashed`, `braille`, `ascii`, `shadow`, `minimal`, `neon`, `retro`, `danger`, `pixel` | `scrollbar(style=)` |

`ScrollbarStyle` members are factory functions returning a configured style
object (with settable `.thumb_color` / `.track_color`). The names accepted by
`scrollbar(style="...")` are those member names, plus the alias `"double"` for
`double_line`.

```python
from maya_py import button, ButtonVariant, scrollbar, scroll_state, ScrollbarStyle
button("Ship it", variant=ButtonVariant.Primary)

st = ScrollbarStyle.neon()
# override the preset's thumb color via the scrollbar() kwarg, which resolves
# name / "#rrggbb" / (r,g,b). (Setting st.thumb_color directly needs a Color
# object, e.g. maya_py.Color.rgb(...), so prefer the kwarg.)
scrollbar(scroll_state(), 20, style=st, thumb_color="magenta")
```

---

## Where to go next

- **[concepts.md](concepts.md)** — the mental model (why widgets are values, the
  performance lever of `memo`, the auto-dispatch scroll model in §6).
- **[layout.md](layout.md)** — `card` / `row` / `col` / `grow` / `tcol` and how
  widgets flow inside them.
- **[apps.md](apps.md)** — wiring controls and scroll states into an interactive
  loop.
