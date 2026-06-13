# API Reference

[← Manual index](index.md)

Every public symbol in `maya_py`, grouped by purpose. Items marked **easy**
are the recommended high-level surface; **low** items are the thin native
bindings. Both are importable from the top-level `maya_py` package.

```python
import maya_py as maya
from maya_py import T, card, col, row, App, memo   # etc.
```

---

## Text & styling

### Easy

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `T` | `T(s="")` | Fluent styled string. Properties: `.bold .dim .italic .underline .strike .inverse`. Methods: `.fg(color) .bg(color) .element()`. Concat with `+`. |
| `b` | `b(s) -> T` | Bold markup shortcut. |
| `i` | `i(s) -> T` | Italic shortcut. |
| `u` | `u(s) -> T` | Underline shortcut. |
| `dim_text` | `dim_text(s) -> T` | Dim shortcut (named `dim` inside `maya_py.easy`). |
| `c` | `c(s, color) -> T` | Colored shortcut. |
| `color` | `color(value) -> Color` | Resolve name / hex / tuple / int / Color into a `Color`. |

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `Style` | `Style()` | Immutable style; `with_*` builders, `merge`, `to_sgr`, `empty`. `|` composes. |
| `Color` | classmethods | `rgb(r,g,b)`, `hex(int)`, `indexed(i)`, `default_color()`, named (`cyan()`, …). |
| `bold` `dim` `italic` `underline` `strikethrough` `inverse` | `Style` values | Predefined style flags. |
| `fg` | `fg(c, *rest) -> Style` | Foreground style from rgb/tuple/hex. |
| `bg` | `bg(c, *rest) -> Style` | Background style. |
| `rgb` | `rgb(r,g,b) -> Color` | Truecolor. |
| `hex` | `hex(0xRRGGBB) -> Color` | Color from hex int. |
| `style` | `style(*, fg, bg, bold, dim, italic, underline, strikethrough, inverse) -> Style` | Build a Style from kwargs. |

---

## Layout

### Easy

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `col` | `col(*children, **opts) -> Element` | Vertical stack. |
| `when` | `when(cond, then, else_=nothing()) -> node` | Conditional element — `then` if truthy else `else_`; branches may be lazy callables. |
| `row` | `row(*children, **opts) -> Element` | Horizontal stack. |
| `card` | `card(*children, title=None, **opts) -> Element` | Bordered padded box (defaults `pad=1`, round border). |
| `field` | `field(label, value, *, label_color="slate", value_color=None) -> Element` | `Label: value` row. |
| `hr` | `hr(width=40, char="─", col="slate") -> Element` | Horizontal rule. |
| `spacer` | `spacer() -> Element` | One-row blank gap. |

**Shared `opts`** for `col`/`row`/`card`: `gap`, `pad`, `border`,
`border_color`, `title`, `bg`, `align`, `justify`, `width`, `height`, `grow`.
See [Layout](layout.md#keyword-options).

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `box` | `box(*children, **opts) -> Element` | Flex container (raw kwargs). |
| `vstack` | `vstack(*children, **opts) -> Element` | `box` with `direction=Column`. |
| `hstack` | `hstack(*children, **opts) -> Element` | `box` with `direction=Row`. |
| `text` | `text(content, style=None, wrap=TextWrap.Wrap) -> Element` | Styled text leaf. |
| `styled_text` | `styled_text(content, fg=-1, bg=-1, attrs=0, wrap=…) -> Element` | Fast styled text from raw scalars. |
| `blank` | `blank() -> Element` | One-row spacer element. |

---

## Apps

### Easy

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `App` | `App(title="", *, inline=True, mouse=False, fps=0, quit_on_ctrl_c=True, quit_keys=(), model=None, keys=None, **state)` | Interactive app. `model=` uses your object as state; `keys={k: fn}` binds keys declaratively; `**state`/`quit_keys` as before. |
| `App.state` | `app.state(**kw) -> state` | Seed state; returns the state bag. |
| `App.s` | property | The live state bag. |
| `App.on` | `@app.on(*keys)` | Bind keys to `fn(state)`. |
| `App.on_key` | `@app.on_key` | Catch-all `fn(state, event)`. |
| `App.on_frame` | `@app.on_frame` | Per-frame tick `fn(state, dt)` before view (enables redraw). |
| `App.on_paste` | `@app.on_paste` | `fn(state, text)` on bracketed paste. |
| `App.on_resize` | `@app.on_resize` | `fn(state, cols, rows)` on terminal resize. |
| `App.focus` | `app.focus(*widgets)` | Register interactive widgets; focused one gets keys, Tab cycles. |
| `App.view` | `@app.view` | Register `fn(state) -> node`. |
| `App.run` | `app.run()` | Start the loop (blocks). |
| `App.stop` | `app.stop()` | Request exit. |
| `text_input` | `text_input(placeholder="", *, password=False, multiline=False)` | Interactive text field (a hosted maya `Input`). `.value`, `.clear()`, `.on_submit(fn)`, `.on_change(fn)`. |
| `textarea` | `textarea(placeholder="")` | Multi-line `text_input`. |

**Key names** for `on`: chars (`"q"`, `"+"`); names (`"up"`, `"down"`,
`"left"`, `"right"`, `"enter"`/`"return"`, `"esc"`/`"escape"`, `"tab"`,
`"backtab"`, `"space"`, `"backspace"`, `"delete"`, `"home"`, `"end"`,
`"pageup"`, `"pagedown"`); combos (`"ctrl+c"`, `"alt+x"`).

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `run` | `run(event_fn, render_fn, *, title="", inline_mode=False, mouse=False, fps=0)` | Interactive loop. `event_fn(ev)->bool`. |

---

## Widgets

Native maya widget renderers (return the same `Element` maya's C++ produces).
Full docs + examples in [Widgets](widgets.md). Colours accept name / hex /
tuple / `Color` everywhere.

**Charts & meters:** `sparkline` `gauge` `progress` `bar_chart` `line_chart`
`heatmap` `flame_chart` `waterfall`

**Controls:** `checkbox` `toggle` `radio` `select` `slider` `button`

**Text & labels:** `badge` `divider` `spinner` `callout` `status_banner`
`breadcrumb` `tabs` `gradient` `link` `title_chip` `model_badge` `file_ref`
`markdown`

**Structure & nav:** `table` `tree` `list_view` `menu` `disclosure` `key_help`
`calendar` `timeline` `picker`

**Agent UI:** `thinking` `todo_list` `toast` `inline_diff`

**Graphics:** `image` `canvas` `Canvas` (imperative drawing surface)

**Widget enums:** `GaugeStyle` `ColumnAlign` `ButtonVariant` `TaskStatus`
`ToastLevel` `TodoItemStatus` `TodoListStatus`

## Scrolling

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `scroll_state` | `scroll_state() -> ScrollState` | A fresh scroll position (auto-dispatch on). |
| `viewport` | `viewport(content, state, *, width=0, height=0, grow=0.0) -> Element` | Clip content to a scrolled window (0 = fill that axis). |
| `scrollbar` | `scrollbar(state, viewport_size, *, axis="y", style=None, thumb_color=None, track_color=None) -> Element` | A scrollbar reflecting `state`. |
| `scroll_handle` | `scroll_handle(state, ev) -> bool` | Manually route an event to a scroll state. |
| `ScrollState` | class | Holds `x`/`y`/`max_x`/`max_y`, `scroll_*`, `at_*`, `viewport_bounds`. |
| `ScrollbarStyle` | class | 15 presets (`.line()`, `.neon()`, `.braille()`, …). |

---

## Rendering

### Easy

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `show` | `show(node, width=None)` | Render once to stdout. |
| `to_string` | `to_string(node, width=80) -> str` | Render to a string. |
| `animate` | `animate(render_fn, *, fps=30)` | Inline animation; `render_fn(dt)->node`. |

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `print` | `print(element, *, width=None)` | Render Element; falls through to builtin print for non-Elements. |
| `print_element` | `print_element(element, width=None)` | Raw render-to-stdout. |
| `render_to_string` | `render_to_string(element, width=80) -> str` | Raw string render. |
| `live` | `live(render_fn, fps=30, max_width=0, cursor=False)` | Raw animation loop; `render_fn(dt)->Element`. |
| `quit` | `quit()` | Stop the current loop. |

---

## Events (low)

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `key` | `key(ev, "c") -> bool` | Printable char key. |
| `key_special` | `key_special(ev, SpecialKey) -> bool` | Named special key. |
| `ctrl` | `ctrl(ev, "c") -> bool` | Ctrl + letter. |
| `alt` | `alt(ev, "x") -> bool` | Alt + char. |
| `any_key` | `any_key(ev) -> bool` | Any key event. |
| `resized` | `resized(ev) -> bool` | Terminal resize. |
| `event_char` | `event_char(ev) -> str \| None` | The typed character (printable, no Ctrl/Alt), else `None`. |
| `pasted` | `pasted(ev) -> str \| None` | Bracketed-paste text, else `None`. |
| `resize_size` | `resize_size(ev) -> (cols, rows) \| None` | New terminal size on a resize event. |
| `Event` | class | Opaque event object. |

---

## Utilities

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `string_width` | `string_width(s) -> int` | Display width in terminal columns (CJK/emoji = 2). |
| `gradient_at` | `gradient_at(stops, t) -> (r,g,b)` | Interpolate a color across evenly-spaced `(r,g,b)` stops at `t` ∈ [0,1]. |
| `fmt_duration` | `fmt_duration(seconds, *, centis=False) -> str` | Format `M:SS` / `H:MM:SS` (`.CC` with `centis`). |
| `halfblock` | `halfblock(grid, *, bg=(0,0,0)) -> Element` | Render a 2-D pixel grid as upper-half-block (`▀`) cells (2 px tall each). |
| `PixelField` | `PixelField(bg=(0,0,0))` | Resize-managing pixel buffer: `.resize(w,h)`, `.clear()`, `.set(x,y,color)`, `.render()`. |
| `pixel_canvas` | `pixel_canvas(draw, *, bg=(0,0,0), grow=1)` | Size-aware element handing `draw(field, w, h)` a sized `PixelField`. |

---

## Performance

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `memo` | `@memo` | Cache a builder by positional args; returns the same Element until args change. |

See [Performance](performance.md).

---

## Enums (low)

| Enum | Values |
|------|--------|
| `FlexDirection` | `Row` `Column` `RowReverse` `ColumnReverse` |
| `Align` | `Start` `Center` `End` `Stretch` `Baseline` |
| `Justify` | `Start` `Center` `End` `SpaceBetween` `SpaceAround` `SpaceEvenly` |
| `BorderStyle` | `None_` `Single` `Double` `Round` `Bold` `SingleDouble` `DoubleSingle` `Classic` `Arrow` `Dashed` |
| `TextWrap` | `Wrap` `TruncateEnd` `TruncateMiddle` `TruncateStart` `NoWrap` |
| `SpecialKey` | `Up` `Down` `Left` `Right` `Home` `End` `PageUp` `PageDown` `Tab` `BackTab` `Backspace` `Delete` `Insert` `Enter` `Escape` `F1`–`F12` |
| `GaugeStyle` | `Arc` `Bar` |
| `ColumnAlign` | `Left` `Center` `Right` |
| `ButtonVariant` | `Default` `Primary` `Danger` `Ghost` |
| `TaskStatus` | `Pending` `InProgress` `Completed` |
| `ToastLevel` | `Info` `Success` `Warning` `Error` |
| `TodoItemStatus` | `Pending` `InProgress` `Completed` |
| `TodoListStatus` | `Pending` `Running` `Done` `Failed` |

### Enum shortcuts (top-level)

| Shortcut | Equals |
|----------|--------|
| `Round` | `BorderStyle.Round` |
| `Single` | `BorderStyle.Single` |
| `Double` | `BorderStyle.Double` |
| `BoldBorder` | `BorderStyle.Bold` |
| `Classic` | `BorderStyle.Classic` |
| `Dashed` | `BorderStyle.Dashed` |
| `Row` | `FlexDirection.Row` |
| `Column` | `FlexDirection.Column` |

---

## Types (low)

| Symbol | Description |
|--------|-------------|
| `Element` | An opaque element tree node. Returned by builders; consumed by renderers. |
| `Style` | Text style descriptor (see [styling](#text--styling)). |
| `Color` | A color value (see [styling](#text--styling)). |
| `Event` | An input event (see [events](#events-low)). |

---

## Color palette names

Accepted anywhere a color is expected in the easy API:

```
black  white  red   green  blue   yellow magenta cyan
gray   grey   orange purple pink   teal   lime    sky
gold   slate
```

Plus `"#RRGGBB"` / `"#RGB"` hex strings, `(r, g, b)` tuples, `0xRRGGBB` ints,
and `Color` objects.

## Module metadata

| Symbol | Value |
|--------|-------|
| `maya_py.__version__` | the installed version (from package metadata) |
| `maya_py._maya` | the compiled pybind11 extension module |
