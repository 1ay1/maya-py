# Low-Level API

[← Manual index](index.md)

Below the easy API sits a thin pybind11 layer over maya's runtime element
builders. You rarely need it — but it's there when you want explicit `Style`
and `Color` objects, raw event predicates, or direct `box`/`text` control.

The easy API is built entirely on these primitives, so mixing is fine: any
low-level `Element` can be a child of `col`/`row`/`card`, and vice versa.

## Why a separate layer?

maya's headline feature is a **compile-time, type-state DSL** (`t<"Hello">`,
type-checked style pipes). That cannot cross into Python — template magic
evaporates at the language boundary. So maya-py binds maya's equivalent
**runtime** builders (`box()`, `text()`, `Style`, `Color`). The element trees
produced are identical to what the compile-time DSL would build.

## Elements

### `text(content, style=None, wrap=TextWrap.Wrap)`

A styled text leaf.

```python
import maya_py as maya
maya.text("hello", maya.bold | maya.fg(255, 128, 0))
```

### `box(*children, **opts)`

A flex container. Children may be `Element`s or plain strings (auto-wrapped).
Keyword options: `direction`, `gap`, `padding` (int or 2/4-tuple), `margin`,
`border`, `border_color`, `border_text`, `bg`, `fg`, `grow`, `align`,
`justify`, `width`, `height`.

```python
maya.box(
    maya.text("a"), maya.text("b"),
    direction=maya.Column, border=maya.Round, padding=1, gap=1,
)
```

This is what `col`/`row`/`card` call internally (with friendlier kwargs).

### `vstack(*children, **opts)` / `hstack(*children, **opts)`

`box` with `direction` fixed to `Column` / `Row`.

### `blank()`

A one-row spacer element.

### `styled_text(content, fg=-1, bg=-1, attrs=0, wrap=TextWrap.Wrap)`

The **fast path** the easy API's `T` uses. Builds `Style` + `Element` in one
C++ call from raw scalars:

- `fg`, `bg` — packed `0xRRGGBB` ints, or `-1` for unset.
- `attrs` — a bitmask: `1`=bold, `2`=dim, `4`=italic, `8`=underline,
  `16`=strike, `32`=inverse.

```python
maya._maya.styled_text("hi", 0x64B4FF, -1, 1)   # bold sky-blue "hi"
```

You normally use `T` instead, which manages these scalars for you.

## Styles

### `Style`

An immutable text-style descriptor. Build with fluent `with_*` methods, each
returning a new `Style`:

```python
s = maya.Style().with_bold().with_fg(maya.Color.cyan()).with_underline()
```

| Method | Effect |
|--------|--------|
| `with_fg(Color)` | Foreground color |
| `with_bg(Color)` | Background color |
| `with_bold(v=True)` | Bold |
| `with_dim(v=True)` | Dim |
| `with_italic(v=True)` | Italic |
| `with_underline(v=True)` | Underline |
| `with_strikethrough(v=True)` | Strikethrough |
| `with_inverse(v=True)` | Reverse video |
| `merge(other)` | Overlay `other`'s set properties on top |
| `to_sgr()` | The ANSI SGR escape string |
| `empty()` | `True` if no properties set |

Styles compose with `|` (left is base, right overlays):

```python
heading = maya.bold | maya.fg(100, 180, 255)
```

### Predefined style values

At the package top level, these are ready-made `Style` objects:

```
maya.bold   maya.dim   maya.italic
maya.underline   maya.strikethrough   maya.inverse
```

### Style helper functions

```python
maya.fg(255, 0, 0)       # Style with foreground (also fg((r,g,b)) / fg(0xFF0000))
maya.bg(0, 0, 0)         # Style with background
maya.style(fg=(80,220,120), bold=True, underline=True)   # build from kwargs
```

## Colors

### `Color`

Constructors (all classmethods):

```python
maya.Color.rgb(255, 128, 0)     # truecolor
maya.Color.hex(0xFF8800)        # from a hex int
maya.Color.indexed(202)         # 256-color palette index
maya.Color.default_color()      # terminal default
```

Named colors:

```
black red green yellow blue magenta cyan white
bright_black bright_red bright_green bright_yellow
bright_blue bright_magenta bright_cyan bright_white
gray grey
```

```python
maya.Color.cyan()
maya.Color.bright_magenta()
```

### Helper functions

```python
maya.rgb(255, 128, 0)    # -> Color
maya.hex(0xFF8800)       # -> Color
```

The easy API's `color(...)` is more flexible (accepts names, hex strings,
tuples) — see [Text & Style](text-and-style.md#colors).

## Events

Inside a low-level `run`'s `event_fn`, you get an opaque `Event` object. Match
it with these predicates:

| Predicate | Matches |
|-----------|---------|
| `key(ev, "q")` | a printable char key |
| `key_special(ev, SpecialKey.Up)` | a named special key |
| `ctrl(ev, "c")` | Ctrl + letter |
| `alt(ev, "x")` | Alt + char |
| `any_key(ev)` | any key event |
| `resized(ev)` | a terminal resize |

```python
def on_event(ev):
    if maya.key(ev, "q"):
        return False
    if maya.key_special(ev, maya.SpecialKey.Up):
        scroll_up()
    return True
```

The `App` class wraps all of this — its string key names (`"up"`, `"ctrl+c"`)
map onto these predicates for you.

## Enums

| Enum | Values |
|------|--------|
| `FlexDirection` | `Row`, `Column`, `RowReverse`, `ColumnReverse` |
| `Align` | `Start`, `Center`, `End`, `Stretch`, `Baseline` |
| `Justify` | `Start`, `Center`, `End`, `SpaceBetween`, `SpaceAround`, `SpaceEvenly` |
| `BorderStyle` | `None_`, `Single`, `Double`, `Round`, `Bold`, `SingleDouble`, `DoubleSingle`, `Classic`, `Arrow`, `Dashed` |
| `TextWrap` | `Wrap`, `TruncateEnd`, `TruncateMiddle`, `TruncateStart`, `NoWrap` |
| `SpecialKey` | `Up`, `Down`, `Left`, `Right`, `Home`, `End`, `PageUp`, `PageDown`, `Tab`, `BackTab`, `Backspace`, `Delete`, `Insert`, `Enter`, `Escape`, `F1`–`F12` |

### Top-level enum shortcuts

For convenience, the package re-exports some enum values bare:

```
maya.Round = BorderStyle.Round       maya.Single = BorderStyle.Single
maya.Double = BorderStyle.Double     maya.BoldBorder = BorderStyle.Bold
maya.Classic = BorderStyle.Classic   maya.Dashed = BorderStyle.Dashed
maya.Row = FlexDirection.Row         maya.Column = FlexDirection.Column
```

## Renderers (low-level names)

| Function | Notes |
|----------|-------|
| `print(element, *, width=None)` | render an Element to stdout (falls through to builtin `print` for non-Elements; `show` wraps it) |
| `render_to_string(element, width=80)` | raw string render (`to_string` wraps it) |
| `live(render_fn, fps=30, max_width=0, cursor=False)` | raw animation loop (`animate` wraps it) |
| `run(event_fn, render_fn, ...)` | the interactive loop (`App` wraps it) |
| `quit()` | stop the current loop |

These live on the package and on `maya_py._maya` (the extension module).

## The native extension module

`maya_py._maya` is the compiled pybind11 module. Everything documented here is
defined there; the Python package re-exports and wraps it. You can reach it
directly as `maya_py._maya` if you ever need the unwrapped surface.

## Next

- [API Reference](api-reference.md) — every symbol in one place.
- [Text & Style](text-and-style.md) — the easy styling layer over `Style`/`Color`.
