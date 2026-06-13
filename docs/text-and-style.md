# Text & Style

[← Manual index](index.md)

All on-screen text is styled through one class — **`T`** — plus a handful of
markup shortcuts and a flexible color resolver.

## `T` — a fluent styled string

`T("...")` wraps a string and lets you chain styling. Attribute toggles are
**properties** (no parentheses); colors are **methods** (take an argument).

```python
from maya_py import T

T("Hello").bold.fg("sky")
T("warn").fg("orange").italic
T("x").bg("red").fg("white")
T("done").dim.strike
```

### Attribute toggles (properties)

| Property | Effect |
|----------|--------|
| `.bold` | Bold |
| `.dim` | Dim / faint |
| `.italic` | Italic |
| `.underline` | Underlined |
| `.strike` | Strikethrough |
| `.inverse` | Reverse video (swap fg/bg) |

They're chainable and order-independent: `T("x").bold.italic` == `T("x").italic.bold`.

### Colors (methods)

| Method | Effect |
|--------|--------|
| `.fg(color)` | Foreground color |
| `.bg(color)` | Background color |

`color` is anything the [color resolver](#colors) accepts (a name, hex, tuple,
int, or `Color`). **`None` is a no-op**, so conditional colour reads cleanly:
`T(x).fg("sky" if focused else None)`.

### Conditional attributes — `.opt(**flags)`

Apply attributes conditionally — only the truthy ones take effect — so a dynamic
label styles itself in one declarative chain instead of reassigning through `if`
branches:

```python
T(text).fg("sky" if focused else None).opt(dim=done, strike=done, bold=focused)
```

`.opt(bold=, dim=, italic=, underline=, strike=, inverse=)`.

### Concatenation

`+` appends text and **keeps the left operand's style** for the whole result:

```python
b("ERROR ") + "connection refused"   # both parts bold
"status: " + T("ok").fg("green")     # right style wins via __radd__
```

> Note: concatenation produces a single styled run; you can't mix two
> different styles in one `T`. For mixed styling, put separate `T`s in a
> `row(...)` instead.

### `.element()`

Turns the `T` into a maya `Element`. You rarely call this directly — layout
functions and `show`/`to_string` call it for you. It is **cached**: the first
call builds the element (one boundary crossing), subsequent calls return the
same object. Mutating the `T` (any `.bold`/`.fg`/…) invalidates the cache.

## Markup shortcuts

For the common one-off case, these are shorter than `T(...).x`:

```python
from maya_py import b, i, u, dim_text, c

b("bold")            # T("bold").bold
i("italic")          # T("italic").italic
u("underline")       # T("underline").underline
dim_text("faint")    # T("faint").dim
c("colored", "red")  # T("colored").fg("red")
```

Each returns a `T`, so you can keep chaining:

```python
b("important").fg("gold").underline
```

> Why `dim_text` and not `dim`? At the package top level, `maya.dim` is a
> reusable **Style** object (for the low-level API). The markup helper that
> wraps a string is exported as `dim_text` to avoid the clash. Inside
> `maya_py.easy` the markup helper is named `dim`.

## Colors

Anywhere a color is expected (`.fg`, `.bg`, `c(...)`, `border_color=`,
`bg=`, …), maya-py accepts **any** of these forms:

| Form | Example |
|------|---------|
| Palette name | `"red"`, `"sky"`, `"gold"` |
| Hex string | `"#ff8800"`, `"#f80"` (short form expands) |
| `(r, g, b)` tuple | `(255, 128, 0)` |
| Packed int | `0xFF8800` |
| A `Color` object | `maya.Color.cyan()` |

### Built-in palette

```
black   white   red     green   blue
yellow  magenta cyan    gray    grey
orange  purple  pink    teal    lime
sky     gold    slate
```

These are tuned for readable truecolor terminals (e.g. `sky` is a soft blue,
`slate` is a muted gray-blue used for dim labels).

### `color(value)`

If you need an actual `Color` object (for the low-level API), call:

```python
from maya_py import color

color("sky")          # -> Color
color("#ff8800")      # -> Color
color((255, 128, 0))  # -> Color
```

Unknown names raise `ValueError`; unsupported types raise `TypeError`.

## How styling stays fast

`T("x").bold.fg("sky")` does **zero** work in C++ until the element is built.
Each `.bold` / `.fg` just flips a bit or stores a packed int in pure Python.
At `.element()` time, a single `styled_text(content, fg, bg, attrs)` call
crosses into C++ and builds the `Style` + `Element` in one shot.

This is why the fluent API is cheap: ~one boundary crossing per styled string,
not one per `.bold`/`.fg`. See [Performance](performance.md) for the numbers.

## Next

- [Layout](layout.md) — arrange styled text into stacks and cards.
