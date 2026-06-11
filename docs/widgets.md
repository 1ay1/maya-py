# Widgets

[← Manual index](index.md)

maya ships a library of ~90 ready-made widgets. maya-py wraps the
**presentational** ones — every widget that renders from data + a config into
an `Element` — and returns the *same Element maya's own C++ renderers produce*.
You drop them straight into any layout:

```python
from maya_py import col, row, sparkline, gauge, table

col(
    sparkline([3, 1, 4, 1, 5, 9, 2, 6], label="req/s", show_last=True),
    gauge(0.72, "load"),
    table(["Name", "Score"], [["Ada", "99"], ["Bob", "7"]], bordered=True),
)
```

Every colour argument accepts the same friendly values as the rest of maya-py:
a name (`"sky"`, `"red"`), an `(r, g, b)` tuple, `"#rrggbb"`, or a `Color`.
See [Text & Style](text-and-style.md#colors).

> **Interactive vs. presentational.** These functions render a widget's
> *appearance* in whatever state you pass (`checked=`, `selected=`, `cursor=`).
> They don't capture keyboard focus — controls that need maya's `Program`
> runtime + signals (full `Input`/`TextArea` editing, live `List`/`Tree`
> navigation) aren't wrapped. Drive interactivity from the [`App`](apps.md)
> class instead: render the widget in the right state, mutate state in your key
> handlers.

---

## Charts & meters

| Function | Signature | Renders |
|----------|-----------|---------|
| `sparkline` | `sparkline(data, *, label="", color=None, show_min_max=False, show_last=False)` | An inline mini bar chart from a sequence of numbers. |
| `gauge` | `gauge(value, label="", *, color=None, style="arc")` | A 0..1 meter; `style` is `"arc"` or `"bar"`. |
| `progress` | `progress(value, label="", *, width=0, fill=None, track=None, show_track=True, show_percentage=True)` | A 0..1 progress bar; `width=0` fills available space. |
| `bar_chart` | `bar_chart(bars, *, max_value=0.0, color=None)` | Horizontal bars; `bars` are `(label, value)` or `(label, value, color)`. `max_value=0` auto-scales. |
| `line_chart` | `line_chart(data, *, height=8, label="", color=None)` | A braille line chart with a y-axis. |
| `heatmap` | `heatmap(grid, *, low=None, high=None, x_labels=(), y_labels=())` | A 2-D heatmap; cells interpolate `low`→`high`. |
| `flame_chart` | `flame_chart(spans, *, time_scale=0.0, width=60, show_times=True)` | A flamegraph; spans are `(label, start, duration, depth, color)`. |
| `waterfall` | `waterfall(entries, *, time_scale=0.0, bar_width=30, show_labels=True, frame=0)` | A request waterfall; entries are `(label, start, duration, color)`. |

```python
from maya_py import col, sparkline, line_chart, gauge, bar_chart, heatmap

col(
    sparkline([3, 1, 4, 1, 5, 9, 2, 6], label="rps", color="sky", show_last=True),
    line_chart([2, 5, 3, 8, 6, 9, 4, 7], height=6, color="lime"),
    gauge(0.72, "load", style="bar", color="green"),
    bar_chart([("jan", 4), ("feb", 9), ("mar", 6)]),
    heatmap([[0.1, 0.9], [0.5, 0.3]], low="slate", high="lime"),
)
```

---

## Controls

Rendered in whatever state you pass — no focus required.

| Function | Signature | Renders |
|----------|-----------|---------|
| `checkbox` | `checkbox(label, checked=False)` | A `[x] label` checkbox. |
| `toggle` | `toggle(label, on=False)` | An on/off switch (`●━━` / `━━◯`). |
| `radio` | `radio(items, *, selected=0, visible_count=0)` | A radio group; `selected` is the chosen index. |
| `select` | `select(items, *, cursor=0, indicator="", visible_count=0)` | A single-choice list with a `❯` cursor on row `cursor`. |
| `slider` | `slider(value, label="", *, min=0.0, max=1.0, step=0.01, width=24, fill=None, track=None)` | A filled slider; `width` is the track in columns. |
| `button` | `button(label, *, variant="default")` | A button; `variant` is `default`/`primary`/`danger`/`ghost`. |

```python
from maya_py import col, row, checkbox, toggle, radio, slider, button

col(
    checkbox("Ship it", checked=True),
    toggle("Dark mode", on=True),
    radio(["Small", "Medium", "Large"], selected=1),
    slider(0.6, "volume", width=24, fill="sky"),
    row(button("Save", variant="primary"), button("Delete", variant="danger")),
)
```

---

## Text & labels

| Function | Signature | Renders |
|----------|-----------|---------|
| `badge` | `badge(label, *, kind="", style=None)` | A bracketed tag; `kind` is ``""``/`success`/`error`/`warning`/`info`/`tool`. |
| `divider` | `divider(label="", *, line=None, color=None)` | A horizontal rule with an optional centered label. |
| `spinner` | `spinner(*, style=None)` | One animated spinner frame (advance per frame). |
| `callout` | `callout(title, body="", *, kind="info")` | A severity box; `kind` is `info`/`success`/`warning`/`error`. |
| `status_banner` | `status_banner(text, *, kind="info")` | A one-line status strip. |
| `breadcrumb` | `breadcrumb(segments)` | A `home › projects › file` trail. |
| `tabs` | `tabs(labels, active=0)` | A tab bar with one tab highlighted. |
| `gradient` | `gradient(text, start, end)` | Text with a per-character colour gradient. |
| `link` | `link(text, url="", *, show_icon=False, color=None)` | An OSC-8 hyperlink (clickable in supporting terminals). |
| `title_chip` | `title_chip(title, *, edge_color=None, text_color=None, max_chars=0)` | A rounded title chip (agent header style). |
| `model_badge` | `model_badge(model, *, compact=False)` | A model-name badge (e.g. `✦ Opus 4`). |
| `file_ref` | `file_ref(path, *, line=0, show_icon=True)` | A `📄 path:line` file reference. |
| `markdown` | `markdown(source)` | Full GFM render (headings, lists, tables, code, emphasis). |

```python
from maya_py import row, badge, gradient, model_badge, file_ref, markdown

row(badge("PASS", kind="success"), badge("WARN", kind="warning"))
gradient("maya-py", "sky", "magenta")
model_badge("Opus 4.8", compact=True)
file_ref("src/main.py", line=42)
markdown("## Hello\nThis is **bold**, *italic*, and `code`.")
```

---

## Structure & navigation

| Function | Signature | Renders |
|----------|-----------|---------|
| `table` | `table(columns, rows, *, stripe=True, bordered=False, title="", cell_padding=1)` | A data table; `columns` are headers or `(header, width, align)`. |
| `tree` | `tree(root)` | A collapsible tree; `root` is a nested dict (below). |
| `list_view` | `list_view(items, *, cursor=0, filterable=False, visible_count=0)` | A scrollable list; items are str, `(label, description, icon)`, or dicts. |
| `menu` | `menu(items, *, cursor=0)` | A dropdown menu; items are str, dicts, or `(label, shortcut, enabled, separator)`. |
| `disclosure` | `disclosure(label, *, open=False, content=None)` | A collapsible section; when `open`, `content` renders beneath. |
| `key_help` | `key_help(bindings, *, title="")` | A shortcut cheat sheet; bindings are `(key, desc)` or `(key, desc, group)`. |
| `calendar` | `calendar(year, month, *, today=None)` | A month grid; `today` is an optional `(y, m, d)` tuple. |
| `timeline` | `timeline(events, *, show_connector=True, compact=False, frame=0, track_width=40)` | A vertical event timeline (below). |
| `picker` | `picker(rows, *, title="", accent=None, selected=None, header=(), footer=(), …)` | A bordered command-palette panel (below). |

**`tree(root)`** — `root` is a nested dict:

```python
tree({
    "label": "src", "expanded": True,
    "children": [
        {"label": "main.py", "selected": True},
        {"label": "widget", "expanded": True,
         "children": [{"label": "table.hpp"}, {"label": "tree.hpp"}]},
    ],
})
```

The root dict is the implicit container — its `children` are the visible
top-level rows.

**`timeline(events)`** — each event is a dict
`{label, detail, duration, status, bar_width}` or a tuple
`(label, detail, duration, status, bar_width)`. `status` is
`"pending"` / `"in_progress"` / `"completed"` (or a `TaskStatus` enum).

```python
timeline([
    ("clone",   "", "0.4s", "completed"),
    ("compile", "", "2.1s", "completed"),
    ("link",    "", "",     "in_progress", 8),
])
```

**`picker(rows, …)`** — a bordered command-palette / fuzzy-picker panel.
`rows` are strings, `(leading, trailing, selected, active)` tuples, or dicts.
The selected row gets a cursor edge-bar + bold; an `active` row gets a magenta
"current" bar. `header` / `footer` are Elements (or strings / `T`) painted
above / below the list.

```python
from maya_py import picker, dim_text

picker(
    [
        ("Opus 4.8", "anthropic", True),     # selected
        ("Sonnet 4", "anthropic"),
        {"leading": "GPT-5", "trailing": "openai", "active": True},
    ],
    title="Models", accent="cyan",
    header=[dim_text("  search: opus_")],
    footer=[dim_text("  ↑↓ move · enter select · esc cancel")],
)
```

A bare `selected=N` index marks that row even when rows are plain strings.

---

## Agent UI

The widgets behind a Claude-Code-style session (see `examples/agent.py`).

| Function | Signature | Renders |
|----------|-----------|---------|
| `thinking` | `thinking(content="", *, active=False, expanded=True, max_lines=0)` | A collapsible reasoning trace. |
| `todo_list` | `todo_list(items, *, description="", status="pending", elapsed=0.0, expanded=True)` | An agent todo card. |
| `toast` | `toast(messages)` | A stack of notifications; each is a str or `(message, level)`. |
| `inline_diff` | `inline_diff(before, after, *, label="", show_header=True)` | A word-level inline diff. |

```python
from maya_py import col, thinking, todo_list, inline_diff, toast

col(
    thinking("The export lives in export.py…", active=True, max_lines=3),
    todo_list(
        [("design API", "completed"), ("implement", "in_progress"), "write tests"],
        description="sprint", status="running", elapsed=42.0,
    ),
    inline_diff("const x = 1", "const x = 42", label="app.ts"),
    toast([("Build succeeded", "success"), ("3 warnings", "warning")]),
)
```

`todo_list` item statuses are `"pending"`/`"in_progress"`/`"completed"`; the
card `status` is `"pending"`/`"running"`/`"done"`/`"failed"`. `toast` levels
are `"info"`/`"success"`/`"warning"`/`"error"`. Strings or the exported enums
(`TaskStatus`, `TodoItemStatus`, `TodoListStatus`, `ToastLevel`,
`ButtonVariant`) both work.

---

## Graphics

| Function | Signature | Renders |
|----------|-----------|---------|
| `image` | `image(pixels, *, color=None)` | A 1-bit braille image; `pixels` is a 2-D grid of truthy/falsy values. |
| `canvas` | `canvas(pixels)` | A colour half-block canvas from a static grid; `pixels` is a 2-D grid of colours or `None`. |

```python
from maya_py import image, canvas

image([[1, 0, 1], [0, 1, 0]], color="magenta")
canvas([["red", "blue", None], [None, "green", "yellow"]])
```

### `Canvas` — an imperative drawing surface

For freeform drawing, use the **`Canvas`** class (maya's `PixelCanvas`). It's a
half-block surface of `width × height*2` pixels — each terminal cell holds two
vertical pixels, so a `Canvas(40, 10)` is 40×20 pixels. Draw imperatively, then
drop it (or `.element()`) into a layout:

```python
from maya_py import Canvas, col

c = Canvas(40, 10)            # 40 × 20 px
c.fill("black")
c.line(0, 0, 39, 19, "sky")        # Bresenham line
c.rect(5, 4, 14, 10, "lime")       # outline rectangle (px coords)
c.set_pixel(20, 10, "red")         # y is 0..height*2
col("drawing:", c)                 # a Canvas is renderable directly
```

| Method | Description |
|--------|-------------|
| `Canvas(width, height)` | A `width × height*2`-pixel surface. |
| `set_pixel(x, y, color)` | Set one pixel (`y` in `0..height*2`). |
| `line(x1, y1, x2, y2, color)` | A Bresenham line. |
| `rect(x, y, w, h, color)` | An outline rectangle. |
| `fill(color)` / `clear()` | Flood / reset to black. |
| `element()` | Build the current drawing into an `Element`. |
| `width` / `height` / `pixel_height` | Dimensions (read-only). |

Drawing methods chain (each returns the canvas), and colours accept the usual
name / `(r,g,b)` / `"#rrggbb"` / `Color`. See `examples/canvas.py` for a static
logo plus a live animated plot.

For full-screen pixel effects driven by a render loop, see the half-block
helper in `examples/_halfblock.py` and the `doom_fire` / `life` / `fluid` /
`particles` examples.

---

## Scrolling

Clip tall/wide content to a window and pair it with a live scrollbar.
Scrolling **just works with no handler code** — like maya, the run loop
auto-forwards ↑↓ / PgUp / PgDn / Home / End and the mouse wheel + scrollbar
drag to every on-screen scroll state.

| Function | Signature | Description |
|----------|-----------|-------------|
| `scroll_state` | `scroll_state() -> ScrollState` | A fresh scroll position (auto-dispatch on). |
| `viewport` | `viewport(content, state, *, width=0, height=0, grow=0.0)` | Clip `content` to a window scrolled by `state`. 0 = fill that axis. |
| `scrollbar` | `scrollbar(state, viewport_size, *, axis="y", style=None, thumb_color=None, track_color=None)` | A scrollbar reflecting `state`. |
| `scroll_handle` | `scroll_handle(state, ev) -> bool` | Route an event to `state` manually (when `auto_dispatch=False`). |

```python
from maya_py import App, row, scroll_state, viewport, scrollbar

app = App("log", mouse=True)
s = scroll_state()
app.state(s=s)

@app.view
def view(st):
    return row(
        viewport(content, st.s, height=14, grow=1),
        scrollbar(st.s, 14, style="neon", thumb_color="sky"),
        gap=1,
    )
```

`style` is a preset name: `line`, `block`, `slim`, `heavy`, `double`,
`dotted`, `dashed`, `braille`, `ascii`, `shadow`, `minimal`, `neon`, `retro`,
`danger`, `pixel` — or a `ScrollbarStyle`. The `ScrollState` exposes
`x`/`y`/`max_x`/`max_y`, `scroll_by`, `scroll_to`, `scroll_to_top/bottom`,
`at_top()`/`at_bottom()`, and `viewport_bounds` (the painted rect, for click
hit-testing). For independent regions set `state.auto_dispatch = False` and
call `scroll_handle(state, ev)` yourself — don't do both (it double-scrolls).

See the `scroll_clip`, `scroll_2d`, `scroll_slice`, and `scroll_styles`
examples for the full set of patterns.

---

## Enums

Exported for callers who want them explicitly (strings work everywhere too):

| Enum | Values |
|------|--------|
| `GaugeStyle` | `Arc` `Bar` |
| `ColumnAlign` | `Left` `Center` `Right` |
| `ButtonVariant` | `Default` `Primary` `Danger` `Ghost` |
| `TaskStatus` | `Pending` `InProgress` `Completed` |
| `ToastLevel` | `Info` `Success` `Warning` `Error` |
| `TodoItemStatus` | `Pending` `InProgress` `Completed` |
| `TodoListStatus` | `Pending` `Running` `Done` `Failed` |
| `ScrollbarStyle` | 15 presets via `.line()`, `.neon()`, … |

---

See the live gallery (`examples/widgets_gallery.py`) and the one-shot showcase
(`examples/widgets.py`) for everything on one screen.
