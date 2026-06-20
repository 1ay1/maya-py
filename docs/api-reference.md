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
| `T` | `T(s="")` | Fluent styled string. Properties: `.bold .dim .italic .underline .strike .inverse`. Methods: `.fg(color) .bg(color) .opt(**flags) .element()`. `.opt` applies attributes conditionally (`.opt(dim=done, strike=done)`); `.fg`/`.bg` accept `None` to no-op. Concat with `+`. |
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
| `BOLD` `DIM` `ITALIC` `UNDERLINE` `STRIKE` `INVERSE` | `int` bitflags | Attribute bits for `styled_text(..., attrs=…)`; OR them together (e.g. `BOLD | UNDERLINE`). |

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
| `center` | `center(*children, **opts) -> Element` | Center children on both axes. |
| `tcol` | `tcol(*specs, gap=-1, grow=-1.0) -> Element` | Table-like column with aligned cells. |
| `trow` | `trow(*specs, gap=-1, grow=-1.0) -> Element` | Table-like row with aligned cells. |
| `component` | `component(render_fn, *, grow=None, width=None, height=None) -> Element` | Size-aware element; `render_fn(w, h)` runs with the resolved cell box. |
| `pct` | `pct(value) -> Dimension` | Percentage dimension for `width`/`height` (e.g. `width=pct(50)`). |

**Shared `opts`** for `col`/`row`/`card`: `gap`, `pad`, `border`,
`border_color`, `title`, `bg`, `align`, `justify`, `width`, `height`, `grow`.
See [Layout](layout.md#keyword-options).

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `box` | `box(*children, **opts) -> Element` | Flex container (raw kwargs). |
| `vstack` | `vstack(*children, **opts) -> Element` | `box` with `direction=Column`. |
| `hstack` | `hstack(*children, **opts) -> Element` | `box` with `direction=Row`. |
| `zstack` | `zstack(*layers) -> Element` | Overlay layers on the same cell box (later layers on top). |
| `sides` | `sides(*, top=True, right=True, bottom=True, left=True) -> BorderSides` | Pick which border sides to draw. |
| `text` | `text(content, style=None, wrap=TextWrap.Wrap) -> Element` | Styled text leaf. |
| `styled_text` | `styled_text(content, fg=-1, bg=-1, attrs=0, wrap=…) -> Element` | Fast styled text from raw scalars. Native-only: call as `maya_py._maya.styled_text` (not re-exported at the top level). |
| `blank` | `blank() -> Element` | One-row spacer element. |

---

## Apps

### Easy

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `App` | `App(title="", *, inline=True, mouse=False, fps=0, quit_on_ctrl_c=True, quit_keys=(), model=None, keys=None, **state)` | Interactive app. `model=` uses your object as state; `keys={k: fn}` binds keys declaratively; `**state`/`quit_keys` as before. |
| `App.inline` | `App.inline(title="", **kw) -> App` | Inline app (draws in place, keeps scrollback). Reads as intent; same as `inline=True`. |
| `App.fullscreen` | `App.fullscreen(title="", **kw) -> App` | Fullscreen app (alt screen, owns every cell, restores on exit). Same as `inline=False`. Pair with `fullscreen_pixels`. |
| `App.state` | `app.state(**kw) -> state` | Seed state; returns the state bag. |
| `App.s` | property | The live state bag. |
| `App.on` | `@app.on(*keys)` | Bind keys to `fn(state)`. |
| `App.on_key` | `@app.on_key` | Catch-all `fn(state, event)`. |
| `App.on_frame` | `@app.on_frame` | Per-frame tick `fn(state, dt)` before view (enables redraw). |
| `App.on_paste` | `@app.on_paste` | `fn(state, text)` on bracketed paste. |
| `App.on_resize` | `@app.on_resize` | `fn(state, cols, rows)` on terminal resize. |
| `App.focus` | `app.focus(*widgets)` | Register interactive widgets; focused one gets keys, Tab cycles. |
| `App.set_mouse` | `app.set_mouse(on)` | Toggle mouse capture at runtime (call from a handler). Off → native terminal scroll; on → clicks captured. See [Apps](apps.md). |
| `App.mouse_active` | `bool` | Current mouse-capture state. |
| `App.view` | `@app.view` | Register `fn(state) -> node`. |
| `App.run` | `app.run()` | Start the loop (blocks). |
| `App.stop` | `app.stop()` | Request exit. |
| `text_input` | `text_input(placeholder="", *, password=False, multiline=False)` | Interactive text field (a hosted maya `Input`). `.value`, `.clear()`, `.on_submit(fn)`, `.on_change(fn)`. |
| `textarea` | `textarea(placeholder="")` | Multi-line `text_input`. |
| `Program` | `Program(init, update, view, subscribe=None)` | Elm-style MVU app (alternative to `App`). See [Program](program.md). |
| `run_program` | `run_program(init, update, view, subscribe=None, *, title="", inline=False, mouse=False, fps=0)` | Run an MVU program from plain functions. See [Program](program.md). |

**Key names** for `on`: chars (`"q"`, `"+"`); names (`"up"`, `"down"`,
`"left"`, `"right"`, `"enter"`/`"return"`, `"esc"`/`"escape"`, `"tab"`,
`"backtab"`, `"space"`, `"backspace"`, `"delete"`, `"home"`, `"end"`,
`"pageup"`, `"pagedown"`); combos (`"ctrl+c"`, `"alt+x"`).

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `run` | `run(event_fn, render_fn, *, title="", inline_mode=False, mouse=False, fps=0)` | Interactive loop. `event_fn(ev)->bool`. |
| `Cmd` | class | MVU command (side effect) returned from `update`. Constructors: `none`, `quit`, `batch`, `after`, `task`, `set_title`, `write_clipboard`, … See [Program](program.md). |
| `Sub` | class | MVU subscription (input source). Constructors: `none`, `batch`, `on_key`, `on_mouse`, `every`, `on_animation_frame`, … See [Program](program.md). |

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
`calendar` `timeline` `picker` `popup` `overlay`

**Agent UI:** `thinking` `todo_list` `toast` `inline_diff` `tool_call`
`plan_view` `phase_chip` `context_window` `context_gauge` `diff_view`
`git_graph` `git_status` `user_message` `assistant_message` `system_banner`
`shortcut_row`

**Graphics:** `image` `canvas` `Canvas` (imperative drawing surface)

**Widget enums:** `GaugeStyle` `ColumnAlign` `ButtonVariant` `TaskStatus`
`ToastLevel` `TodoItemStatus` `TodoListStatus` `PopupStyle` `BannerLevel`
`ToolCallStatus` `ToolCallKind`

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
| `term_size` | `term_size(fallback=(80,24)) -> (cols, rows)` | Terminal size in cells. The `shutil.get_terminal_size` dance, once. |
| `term_cols` | `term_cols(fallback=80) -> int` | Terminal width in cells. |
| `term_rows` | `term_rows(fallback=24) -> int` | Terminal height in cells. |
| `fullscreen_pixels` | `fullscreen_pixels(draw, *, bg=(0,0,0), reserve=0, max_pw=600, grid=False)` | Whole-terminal half-block canvas for a fullscreen app. Hands `draw(field, pw, ph)` a `PixelField` sized to the visible terminal (2 px/cell) and renders it — no grow-sentinel / `shutil` boilerplate. `grid=True` hands a `[[None]*pw …]` list instead. |

### Low

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `print` | `print(element, *, width=None)` | Render Element; falls through to builtin print for non-Elements. |
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
| `is_mouse` | `is_mouse(ev) -> bool` | Any mouse event (move / press / release / wheel). |
| `mouse_clicked` | `mouse_clicked(ev) -> bool` | A mouse button press. |
| `mouse_released` | `mouse_released(ev) -> bool` | A mouse button release. |
| `mouse_moved` | `mouse_moved(ev) -> bool` | Pointer movement. |
| `scrolled_up` | `scrolled_up(ev) -> bool` | Wheel scrolled up. |
| `scrolled_down` | `scrolled_down(ev) -> bool` | Wheel scrolled down. |
| `mouse_pos` | `mouse_pos(ev) -> (col, row) \| None` | 1-based cell position (top-left is `(1, 1)`), else `None`. |
| `mouse_button` | `mouse_button(ev) -> MouseButton \| None` | Button involved, else `None`. |
| `mouse_kind` | `mouse_kind(ev) -> MouseEventKind \| None` | `Press` / `Release` / `Move`, else `None`. |
| `Event` | class | Opaque event object. |

---

## DSL helpers

The vocabulary every live / visual terminal app reaches for, so you never
redefine `clamp` or hand-roll a sparkline again. All top-level imports. See
`examples/dsl.py` for an animated tour.

### Numeric

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `clamp` | `clamp(x, lo=0, hi=1) -> x` | Clamp into `[lo, hi]`. Preserves `int` for `int` input (drop-in for an integer-index clamp). |
| `saturate` | `saturate(x) -> float` | Clamp into `[0, 1]` (the shader `saturate`). |
| `lerp` | `lerp(a, b, t) -> float` | Linear interpolate `a→b` by `t` (unclamped). |
| `norm` | `norm(x, lo, hi) -> float` | Inverse-lerp: where `x` falls in `[lo, hi]` as a 0..1 fraction. |
| `remap` | `remap(x, a, b, c, d) -> float` | Map `x` from `[a, b]` into `[c, d]` (unclamped). |
| `remapc` | `remapc(x, a, b, c, d) -> float` | `remap`, clamped to `[c, d]`. |
| `smoothstep` | `smoothstep(t) -> float` | Hermite ease of a 0..1 `t`. |
| `wrap` | `wrap(x, hi, lo=0) -> float` | Wrap `x` into `[lo, hi)`. |
| `sign` | `sign(x) -> -1\|0\|1` | Sign of `x`. |
| `approach` | `approach(cur, target, rate) -> float` | Move `cur` toward `target` by at most `rate`. |

### Animation

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `oscillate` | `oscillate(t, lo=0, hi=1, period=1) -> float` | Sine sweep in `[lo, hi]` with `period` seconds. |
| `pulse` | `pulse(t, period=1, duty=0.5) -> bool` | Square wave: `True` for the first `duty` fraction of each period. |
| `ease` | `ease(t, kind="smooth") -> float` | Ease a 0..1 `t`. `kind`: `linear` `in` `out` `inout` `smooth` `cubic` `expo` `bounce`. |

### Colour

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `hsv` | `hsv(h, s=1, v=1) -> (r,g,b)` | HSV → rgb. `h` in turns (0..1, wraps). The ergonomic hue sweep. |
| `mix` | `mix(a, b, t) -> (r,g,b)` | Blend two colour specs at `t`. |
| `lighten` | `lighten(c, amount=0.2) -> (r,g,b)` | Blend `c` toward white. |
| `darken` | `darken(c, amount=0.2) -> (r,g,b)` | Blend `c` toward black. |
| `alpha` | `alpha(fg, bg, a) -> (r,g,b)` | Composite `fg` over `bg` at opacity `a` (fake translucency). |
| `ramp` | `ramp(stops, n) -> [int,…]` | Pack a list of colour stops into an `n`-entry gradient LUT (packed `0xRRGGBB`). |
| `rgb_lerp` | `rgb_lerp(a, b, t) -> (r,g,b)` | Interpolate two `(r,g,b)` tuples. |

### Data → text

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `spark` | `spark(data, width=0, *, lo=None, hi=None) -> str` | Unicode block sparkline. `width=0` = one cell per sample; `lo`/`hi` pin the axis. |
| `bar` | `bar(value, width=10, *, lo=0, hi=1, fill="█", track="░") -> str` | Horizontal fill bar; sub-cell precise with the default block glyphs. |
| `fixed` | `fixed(text, width, align="left") -> str` | Pad / clip to exactly `width` cells (`left`/`right`/`center`) — column alignment. |
| `human` | `human(n, *, prec=1) -> str` | Compact magnitude format: `1234 → 1.2k`, `5.6M`. |
| `percent` | `percent(value, *, prec=0, sign=False) -> str` | Format a 0..1 fraction as `62%`; `sign=True` prefixes `+` on deltas. |

### Random & spinners

The tiny helpers every live demo used to hand-roll.

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `randf` | `randf(lo=0.0, hi=1.0) -> float` | Uniform random float in `[lo, hi]` — `random.uniform` with defaults. |
| `randi` | `randi(lo, hi) -> int` | Random integer in `[lo, hi]` inclusive — `random.randint`. |
| `spin` | `spin(frame, kind="dots") -> str` | One glyph from a looping spinner, indexed by `frame`. `kind`: `dots` / `line` / `bar` / `arc` / `circle`. |

### Theme

Named colour roles instead of `THEMES[i][TH_ACCENT]` index constants. Every
role normalises to an `(r,g,b)` tuple, so it flows into `.fg()` / `ramp()` /
`mix()`.

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `Theme` | `Theme(name, **roles)` | Immutable named-colour-role bag. Read by attribute (`th.accent`) or item (`th["accent"]`). |
| `Theme.with_` | `.with_(**overrides) -> Theme` | Derive a variant with some roles replaced / added. |
| `Theme.shade` | `.shade(role, amount) -> (r,g,b)` | Lighten (`amount > 0`) or darken (`< 0`) a role on the fly. |
| `Theme.get` / `.roles` / `.name` | — | `get(role, default)`, the role names, the theme name. |
| `ThemeSet` | `ThemeSet(*themes, index=0)` | Cyclable collection; proxies attribute access to the active theme (`themes.accent`). |
| `ThemeSet.next` / `.prev` / `.set` | `.next(step=1)` / `.prev()` / `.set(i)` | Cycle / jump (wraps); returns the now-active `Theme`. |
| `ThemeSet.current` / `.index` / `.names` | — | The active `Theme`, its index, every theme name. |
| `ThemeSet.from_rows` | `from_rows(fields, rows, *, name_field="name") -> ThemeSet` | Build from a legacy positional `THEMES = [...]` table in one line. |

```python
themes = ThemeSet(
    Theme("CYBER", accent=(0, 255, 200), bg="#050a0f", hot=(255, 0, 100)),
    Theme("EMBER", accent=(255, 120, 0), bg=(15, 8, 5), hot=(255, 40, 40)),
)
T("x").fg(themes.accent)      # active theme's accent
ramp([themes.bg, themes.hot], 8)
themes.next()                 # cycle (wraps)
```

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
| `FlexWrap` | `NoWrap` `Wrap` `WrapReverse` |
| `Overflow` | `Visible` `Hidden` `Scroll` |
| `Align` | `Start` `Center` `End` `Stretch` `Baseline` |
| `Justify` | `Start` `Center` `End` `SpaceBetween` `SpaceAround` `SpaceEvenly` |
| `BorderStyle` | `None_` `Single` `Double` `Round` `Bold` `SingleDouble` `DoubleSingle` `Classic` `Arrow` `Dashed` |
| `BorderTextPos` | `Top` `Bottom` |
| `BorderTextAlign` | `Start` `Center` `End` |
| `TextWrap` | `Wrap` `TruncateEnd` `TruncateMiddle` `TruncateStart` `NoWrap` |
| `SpecialKey` | `Up` `Down` `Left` `Right` `Home` `End` `PageUp` `PageDown` `Tab` `BackTab` `Backspace` `Delete` `Insert` `Enter` `Escape` `F1`–`F12` |
| `MouseButton` | `None_` `Left` `Middle` `Right` `ScrollUp` `ScrollDown` `ScrollLeft` `ScrollRight` |
| `MouseEventKind` | `Press` `Release` `Move` |
| `GaugeStyle` | `Arc` `Bar` |
| `ColumnAlign` | `Left` `Center` `Right` |
| `ButtonVariant` | `Default` `Primary` `Danger` `Ghost` |
| `TaskStatus` | `Pending` `InProgress` `Completed` |
| `ToastLevel` | `Info` `Success` `Warning` `Error` |
| `TodoItemStatus` | `Pending` `InProgress` `Completed` |
| `TodoListStatus` | `Pending` `Running` `Done` `Failed` |
| `PopupStyle` | `Info` `Warning` `Error` |
| `BannerLevel` | `Info` `Success` `Warning` `Error` |
| `ToolCallStatus` | `Pending` `Running` `Completed` `Failed` `Confirmation` |
| `ToolCallKind` | `Read` `Edit` `Execute` `Search` `Delete` `Move` `Fetch` `Think` `Agent` `Other` |

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
| `Dimension` | A size value (`auto` / fixed / percent). Build percents with `pct(…)`; pass to `width`/`height`. |
| `BorderSides` | Which border sides to draw. Build with `sides(…)` or use `BorderSides.all` / `.none` / `.horizontal` / `.vertical` / `.top` / `.right` / `.bottom` / `.left`. |

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
