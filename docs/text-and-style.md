# Text & Style

[← Manual index](index.md)

Every glyph maya puts on the screen carries a style: a foreground color, a
background color, and a handful of attribute bits (bold, italic, …). This page
is about producing styled text — fluently, correctly, and fast. By the end you
should know *which* of maya-py's three styling surfaces to reach for, and *why*
they're separate.

Re-read [concepts.md §3](concepts.md) first if you haven't: **strings are
elements.** Anywhere a child is expected — `card(...)`, `row(...)`, `col(...)`,
`show(...)`, `to_string(...)` — a bare `str`, a styled `T`, or a `(text, fg,
…)` tuple is accepted and coerced into a text leaf. Styling text is just a
matter of describing *which* leaf you want.

There are three surfaces, in rough order of how often you'll use them:

1. **`T`** — the fluent styled-string builder, plus the `b`/`i`/`u`/`dim_text`/`c`
   markup shortcuts. The everyday surface; reads beautifully.
2. **Tuple cells** — `(text, fg[, bg[, attrs]])`. The fastest surface; for hot
   per-frame loops (tables, charts, dashboards).
3. **The low-level `Style` / `text(...)` / `styled_text(...)`** primitives. The
   floor everything else is sugar over; reach for it only when the sugar can't
   express what you want.

All three produce byte-identical output. They differ only in ergonomics and
allocation cost.

---

## 1. `T` — the fluent styled string

`T("...")` wraps a string and lets you chain styling onto it. Attribute toggles
are **properties** (no parentheses); colors and options are **methods** (they
take arguments).

```python
from maya_py import T

T("Hello").bold.fg("sky")
T("warn").fg("orange").italic
T("x").bg("red").fg("white")
T("done").dim.strike
```

The constructor signature is `T(s='')`. `s` is coerced to `str`, so
`T(42)` and `T(3.14)` are fine.

### 1.1 Attribute toggles (properties)

| Property | Effect |
|----------|--------|
| `.bold` | Bold |
| `.dim` | Dim / faint |
| `.italic` | Italic |
| `.underline` | Underlined |
| `.strike` | Strikethrough |
| `.inverse` | Reverse video (swap fg/bg) |

Each property OR-s a bit into an internal `_attrs` mask and returns `self`, so
they chain and are order-independent and idempotent:

```python
T("x").bold.italic        # == T("x").italic.bold
T("x").bold.bold          # == T("x").bold  (OR-ing the same bit)
```

### 1.2 Colors — `.fg(color)` / `.bg(color)`

```python
T("ok").fg("green")
T("sel").fg("white").bg("blue")
```

`color` is anything the [color resolver](#3-the-color-system) accepts: a palette
name, a hex string, an `(r,g,b)` tuple, a packed `0xRRGGBB` int, or a `Color`
object. Two things worth internalizing:

- **`None` is a no-op.** This is deliberate, so conditional color reads cleanly
  without an `if`:

  ```python
  T(label).fg("sky" if focused else None)   # unfocused → no fg set
  ```

- **Names resolve in pure Python.** A palette name is a single dict hit; only a
  real `Color` object defers any work to the C++ side (see §1.6).

### 1.3 Conditional attributes — `.opt(**flags)`

`.opt()` applies attributes conditionally — only the truthy keywords take
effect — so a dynamic label can express its whole style in one declarative chain
instead of branching through reassignment:

```python
# a to-do item: dim + struck through once done, highlighted while focused
T(item.text).fg("sky" if focused else None).opt(dim=item.done, strike=item.done)
```

Full signature:

```python
.opt(*, bold=False, dim=False, italic=False,
        underline=False, strike=False, inverse=False) -> T
```

It only invalidates the cache (§1.6) if the attribute mask actually changed, so
an all-`False` `.opt()` is genuinely free.

### 1.4 `+` concatenation

`+` appends text and **keeps the left operand's style** for the entire result:

```python
b("ERROR ") + "connection refused"    # whole thing bold (left style wins)
"status: " + T("ok").fg("green")      # whole thing green (via __radd__)
```

The mechanics: `T.__add__(other)` builds a *new* `T` whose string is
`self._s + str(other)` (if `other` is a `T`, its *text* is taken but its *style
is discarded*), then copies `self`'s fg/bg/attrs onto it. `__radd__` is the
mirror image for `"literal" + T(...)` — there the *right* operand's style is
copied.

> **The key limitation:** a single `T` carries exactly one style. Concatenation
> produces one styled run — you cannot mix two styles inside one `T`. For *mixed*
> styling, put separate styled leaves side by side in a `row(...)`:
>
> ```python
> row(b("ERROR "), T("connection refused").fg("red"))
> ```

### 1.5 `.element()`

`.element()` turns the `T` into a maya `Element`. You rarely call it yourself —
the layout functions and `show`/`to_string` call it for you when they coerce
children. It's there for when you need an `Element` directly:

```python
hr_line = T("─" * 40).fg("slate").element()
```

It is **cached**: the first call builds the element and stashes it; later calls
return the same object. Any mutation (`.bold`, `.fg`, `.opt`, …) clears the
cache so the next `.element()` rebuilds.

### 1.6 How `T` crosses the boundary (the performance story)

This is what makes the fluent API cheap. Re-read
[concepts.md §3 and §7](concepts.md): **building the tree in Python is the
expensive part; maya's native render is cheap.** `T` is engineered so that all
the chaining is pure Python and the C++ boundary is crossed exactly once.

- `T("x")` stores the string and three scalars: `_fg = -1`, `_bg = -1`,
  `_attrs = 0` (`-1` = "unset").
- `.bold` / `.fg("sky")` / `.opt(...)` mutate those scalars **in place** and
  return `self`. No allocation, no boundary crossing, per step.
- The first `.element()` (or the first time a layout function coerces the `T`)
  makes a **single** call across pybind:
  - **Hot path** — both `_fg` and `_bg` are plain ints (or `-1`): one
    `_maya.styled_text(s, fg, bg, attrs)` call builds the `Style` + `Element`
    in one shot, no `Style` assembly in Python.
  - **Slow path** — a raw `Color` object was passed to `.fg`/`.bg`: a `Style`
    is assembled with `.with_fg(...)`/`.with_bold()`/… and handed to
    `_maya.text(s, style)`.
- The built `Element` is **cached on the `T`**; subsequent uses are free.

So `T("x").bold.fg("sky")` costs ~one C++ crossing, not five. (When a `T` flows
directly into `row`/`col`, maya can flatten it even further — see §2.2.)

---

## 2. Markup shortcuts & tuple cells

### 2.1 Markup shortcuts

For the common one-off case these are shorter than `T(...).x`. Real signatures:

```python
from maya_py import b, i, u, dim_text, c

b(s)          # -> T(s).bold
i(s)          # -> T(s).italic
u(s)          # -> T(s).underline
dim_text(s)   # -> T(s).dim
c(s, col)     # -> T(s).fg(col)
```

| Helper | Signature | Equivalent |
|--------|-----------|------------|
| `b` | `b(s: Any) -> T` | `T(s).bold` |
| `i` | `i(s: Any) -> T` | `T(s).italic` |
| `u` | `u(s: Any) -> T` | `T(s).underline` |
| `dim_text` | `dim_text(s: Any) -> T` | `T(s).dim` |
| `c` | `c(s: Any, col: Any) -> T` | `T(s).fg(col)` |

Each returns a `T`, so you keep chaining:

```python
b("important").fg("gold").underline
c("hint", "slate").italic
```

> **Why `dim_text` and not `dim`?** At the package top level, `maya.dim` is a
> reusable **`Style`** object for the low-level API (see §4). The markup helper
> that wraps a string would clash with it, so it's exported as `dim_text`.
> Inside `maya_py.easy` the same helper is just named `dim`.

### 2.2 Tuple cells — `(text, fg[, bg[, attrs]])`

`row(...)` and `col(...)` accept **tuple (or list) cells** as children. A cell is
a tuple whose first element is a `str`:

```python
from maya_py import row, col, BOLD, DIM

row(("OK", "green"))                       # fg only
row(("sel", "white", "blue"))              # fg + bg
row(("title", "gold", None, BOLD))         # fg + attrs (bg unset via None)
col(("Name:", "slate"), ("Ada", "white"))
```

The slots are positional: `text`, then optional `fg`, `bg`, and `attrs` (an
integer bitmask — see §2.3). Each color slot accepts the same forms as
`.fg`/`.bg`, and `None`/omitted means "unset". A tuple cell builds **no `T`
object at all** — it goes straight to `_maya.styled_text(text, fg, bg, attrs)`.

This matters because of how `row`/`col` build. When *every* child is flattenable
— a tuple cell, a fresh `T` with plain-int colors, or a bare `str` — maya fuses
them into **one** `styled_text_row` crossing for the entire stack (no per-cell
`Element`, no per-cell boundary crossing). The moment any child is a built
`Element`, a nested box, or a `Color`-object `T`, it falls back to the
per-child path. Tuple cells are the surest way to stay on the fused fast path.

> **`T` vs tuple cells — the expert's rule** (see [concepts.md §3 and §7](concepts.md)):
> reach for `T`/markup for one-off UI — it reads well and the single-crossing
> cache makes it cheap enough. Reach for tuple cells in **hot per-frame loops**
> that emit many styled cells (tables, charts, per-frame grids), where even a
> throwaway `T` per cell adds up. Both produce byte-identical output.

`trow(*specs, gap=-1, grow=-1.0)` and `tcol(*specs, gap=-1, grow=-1.0)` are
back-compat aliases for `row`/`col` over tuple specs — new code can just use
`row`/`col`, which take the same specs at identical speed.

### 2.3 The attribute bitflags

For the `attrs` slot of a tuple cell (and for low-level `styled_text`), use the
exported integer constants, OR-ed together:

```python
from maya_py import BOLD, DIM, ITALIC, UNDERLINE, STRIKE, INVERSE

row(("HEADER", "gold", None, BOLD | UNDERLINE))
```

| Constant | Value | Effect |
|----------|-------|--------|
| `BOLD` | `1` | Bold |
| `DIM` | `2` | Dim / faint |
| `ITALIC` | `4` | Italic |
| `UNDERLINE` | `8` | Underlined |
| `STRIKE` | `16` | Strikethrough |
| `INVERSE` | `32` | Reverse video |

These are exactly the bits that `T`'s attribute properties set internally, so
`("x", "red", None, BOLD)` and `T("x").fg("red").bold` are equivalent.

---

## 3. The color system

A "color" in the easy API is wonderfully permissive: every color-accepting
argument (`.fg`, `.bg`, the `c(...)` helper, tuple-cell color slots,
`border_color=`, `bg=`, `fg=` on boxes, widget `color=` kwargs, …) runs through
the same resolver. It accepts **all** of:

| Form | Example | Notes |
|------|---------|-------|
| Palette name | `"red"`, `"sky"`, `"gold"` | 18 built-in names (§3.1) |
| Hex string | `"#ff8800"`, `"#f80"` | 3-digit short form expands (`#f80` → `#ff8800`) |
| `(r, g, b)` tuple | `(255, 128, 0)` | also a 3-element list |
| Packed int | `0xFF8800` | `0xRRGGBB`; masked to 24 bits |
| `Color` object | `Color.cyan()` | the low-level type (§3.3) |

In the hot path these resolve to a packed `0xRRGGBB` int in **pure Python** — no
boundary crossing — which is why styling stays cheap. A repeated `#hex` literal
is memoised into the palette dict after its first use, so it costs one dict
lookup on every later frame. Only a real `Color` object defers to C++.

### 3.1 The built-in palette

Eighteen names, tuned for readable truecolor terminals:

```
black   white   red     green   blue
yellow  magenta cyan    gray    grey
orange  purple  pink    teal    lime
sky     gold    slate
```

(`gray` and `grey` are the same color.) `sky` is a soft blue, `slate` a muted
gray-blue commonly used for dim labels (it's the default `label_color` for
`field(...)` and the default rule color for `hr(...)`).

### 3.2 `color(value)` — the resolver

When you need an actual `Color` object — for the low-level `Style` API, or for a
widget that takes one — call `color(value)`. It accepts every form in the table
above and returns a `Color`:

```python
from maya_py import color

color("sky")          # -> Color
color("#ff8800")      # -> Color
color((255, 128, 0))  # -> Color
color(0xFF8800)       # -> Color
```

Unknown palette names raise `ValueError`; types it can't interpret raise
`TypeError`.

### 3.3 The low-level `Color` type

`Color` is the native truecolor type. Build one with its classmethods:

```python
from maya_py import Color

Color.rgb(255, 128, 0)   # rgb(r: int, g: int, b: int) -> Color
Color.hex(0xFF8800)      # hex(rgb: int) -> Color  (packed 0xRRGGBB)
Color.indexed(196)       # indexed(idx: int) -> Color  (256-color palette index)
```

It also exposes named constructors: `Color.black()`, `Color.white()`,
`Color.red()`, `Color.green()`, `Color.blue()`, `Color.yellow()`,
`Color.magenta()`, `Color.cyan()`, `Color.gray()` / `Color.grey()`, the
`Color.bright_*()` variants (`bright_black`, `bright_red`, `bright_green`,
`bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`,
`bright_white`), and `Color.default_color()` (the terminal's default).

### 3.4 Top-level color/style helpers

For the low-level API, the package exposes a few convenience constructors:

```python
from maya_py import rgb, hex, fg, bg, style

rgb(255, 128, 0)         # rgb(r, g, b) -> Color
hex(0xFF8800)            # hex(value) -> Color
fg(255, 0, 0)            # fg(c, *rest) -> Style  (foreground-only Style)
bg(0x202020)             # bg(c, *rest) -> Style  (background-only Style)
```

`fg(...)` / `bg(...)` are flexible: `fg(255, 0, 0)`, `fg((r, g, b))`, and
`fg(0xFF0000)` all work, each returning a `Style`. `style(...)` builds a full
`Style` in one keyword call:

```python
style(*, fg=None, bg=None, bold=False, dim=False, italic=False,
         underline=False, strikethrough=False, inverse=False) -> Style
```

(Note the keyword is `strikethrough` here, mirroring the `Style` method —
whereas `T`'s property is `.strike`.)

---

## 4. The low-level `Style` / `text` / `styled_text` / `TextWrap`

Everything above is sugar over these four primitives. You can build text leaves
directly when you need to.

### 4.1 `Style`

A `Style` is an immutable bundle of color + attributes. You compose one with
chained `with_*` methods (each returns a new `Style`):

```python
from maya_py import Style, color

st = (Style()
      .with_fg(color("sky"))
      .with_bg(color("#202020"))
      .with_bold()
      .with_underline())
```

Methods: `with_fg(Color)`, `with_bg(Color)`, `with_bold()`, `with_dim()`,
`with_italic()`, `with_underline()`, `with_strikethrough()`, `with_inverse()`,
plus `merge(other)` (overlay another `Style`), `empty()`, and `to_sgr()` (the
raw ANSI SGR string). The module also exports ready-made single-attribute
`Style` values — `bold`, `dim`, `italic`, `underline`, `strikethrough`,
`inverse` — which you can OR together with `|`:

```python
from maya_py import text, bold, underline, fg

text("Heading", bold | underline | fg(100, 180, 255))
```

### 4.2 `text(...)` and `styled_text(...)`

```python
text(content: str, style: Style | None = None, wrap: TextWrap = TextWrap.Wrap) -> Element
styled_text(content: str, fg: int = -1, bg: int = -1, attrs: int = 0,
            wrap: TextWrap = TextWrap.Wrap) -> Element
```

- `text(content, style)` builds a text leaf from a `Style` object. This is the
  slow path `T` falls back to when handed a raw `Color`.
- `styled_text(content, fg, bg, attrs)` is the *scalar* fast path: `fg`/`bg` are
  packed `0xRRGGBB` ints (or `-1` for unset) and `attrs` is the bitmask from
  §2.3. This is the single call `T` makes on its hot path, and what every tuple
  cell compiles to. Unlike `text`, it is **not** re-exported at the top level —
  it lives on the native extension module, `maya_py._maya.styled_text`. You
  rarely call it directly; prefer tuple cells (§2.3), which use it for you.

```python
import maya_py as maya
from maya_py import BOLD

maya._maya.styled_text("OK", 0x50DC78, -1, BOLD)   # green bold, no bg
```

### 4.3 `TextWrap`

The `wrap` argument controls how text behaves when it's wider than its box:

| Value | Behavior |
|-------|----------|
| `TextWrap.Wrap` | Wrap onto multiple lines (the default) |
| `TextWrap.NoWrap` | Keep on one line (overflow clipped by the box) |
| `TextWrap.TruncateEnd` | One line; cut the end, append an ellipsis |
| `TextWrap.TruncateMiddle` | One line; cut the middle |
| `TextWrap.TruncateStart` | One line; cut the start |

```python
from maya_py import text, TextWrap, fg

text("a very long single-line status that should be elided",
     fg(150, 150, 150), TextWrap.TruncateEnd)
```

The `T` builder always uses the default `Wrap`; reach for `text(...)`/
`styled_text(...)` directly when you need a different wrap mode.

---

## 5. Gradients & color interpolation

Two helpers cover the two common gradient needs.

### 5.1 `gradient(text, start, end)` — a finished widget

`gradient(text: str, start, end) -> Element` builds a text element where each
character is interpolated from `start` to `end`. Both endpoints accept any color
form from §3:

```python
from maya_py import gradient, show

show(gradient("maya makes terminals beautiful", "sky", "magenta"))
```

It returns a ready `Element`, so drop it straight into a layout.

### 5.2 `gradient_at(stops, t)` — interpolate one color

```python
gradient_at(stops, t: float) -> tuple[int, int, int]
```

`gradient_at` interpolates a single `(r, g, b)` color across a list of
evenly-spaced `(r, g, b)` `stops` at position `t`. Use it to *drive* a color
from a scalar — a heat value, an animation phase, a progress fraction:

```python
from maya_py import T, gradient_at

WARM = [(20, 20, 60), (200, 60, 40), (255, 220, 120)]
T("x").fg(gradient_at(WARM, heat))        # heat in [0, 1)
```

The returned tuple plugs straight into `.fg()` / `.bg()`, a tuple cell, or
`halfblock`.

> **Important gotcha — keep `t` in `[0, 1)`.** Internally `gradient_at` clamps:
> `t < 0` becomes `0`, and `t > 1.0` is clamped to `0.999999`. But **exactly
> `1.0` is unsafe** — at `t == 1.0` the segment index lands on the last stop and
> the code reads `stops[i + 1]`, which is out of range and raises `IndexError`.
> Always pass `t` in the half-open interval `[0, 1)`. If you have a fraction
> that can hit `1.0`, nudge it: `gradient_at(stops, min(t, 0.999999))`.

> **Animation note** (see [concepts.md §7](concepts.md)): a gradient that emits a
> *fresh shade per cell per frame* keeps growing maya's never-evicted
> `StylePool`. For continuous animation, **quantize** — precompute N color steps
> with `gradient_at` and index into them — so the pool stays bounded.

---

## 6. Cheat sheet

```python
from maya_py import T, b, i, u, dim_text, c, color, row, col, BOLD, UNDERLINE

# fluent
T("Hello").bold.fg("sky")
T(label).fg("sky" if focused else None).opt(dim=done, strike=done)

# markup
b("error") ; i("note") ; u("link") ; dim_text("muted") ; c("ok", "green")

# concatenation (left style wins)
b("ERROR ") + "connection refused"

# tuple cells (fastest; hot loops)
row(("OK", "green"), ("warn", "orange", None, BOLD))

# colors — every form
color("sky") ; color("#f80") ; color((255, 128, 0)) ; color(0xFF8800)
```

---

## See also

- [concepts.md](concepts.md) — §3 (strings are elements; `T` vs tuple cells) and
  §7 (the performance model: build cost, the `StylePool`, quantizing colors).
- [layout.md](layout.md) — arranging styled text into rows, columns, and cards.
- [api-reference.md](api-reference.md) — the complete symbol list and signatures.

Example programs that lean on styling:
[dashboard.py](https://github.com/1ay1/maya-py/blob/master/examples/dashboard.py),
[doom_fire.py](https://github.com/1ay1/maya-py/blob/master/examples/doom_fire.py)
(quantized `gradient_at`).
