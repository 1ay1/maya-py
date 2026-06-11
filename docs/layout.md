# Layout

[← Manual index](index.md)

maya uses **flexbox** (the Yoga engine) under the hood, so layout is built
from two stack primitives — `col` (vertical) and `row` (horizontal) — plus a
few convenience widgets. Every layout function accepts **bare strings**, `T`
objects, and `Element`s as children, and shares the same keyword options.

## `col(*children, **opts)` — vertical stack

Children stack top to bottom.

```python
from maya_py import col

col("first", "second", "third")
col(b("Title").fg("sky"), "body line 1", "body line 2", gap=1)
```

## `row(*children, **opts)` — horizontal stack

Children sit left to right.

```python
from maya_py import row, c

row(c("OK", "green"), c("WARN", "orange"), c("ERR", "red"), gap=2)
```

## `card(*children, title=None, **opts)` — bordered box

A `col` with a border and padding pre-applied — the everyday container.
Defaults: `pad=1`, `border="round"`. Pass `title=` to label the border.

```python
from maya_py import card

card("hello", title="greeting")
card(col("a", "b"), border="double", pad=(1, 2))
```

## Keyword options

All of `col`, `row`, and `card` accept these (any subset):

| Option | Type | Meaning |
|--------|------|---------|
| `gap` | `int` | Cells between children (default 0). |
| `pad` | `int` or tuple | Padding. `1` = all sides; `(v, h)` = vertical/horizontal; `(t, r, b, l)` = per-side. |
| `border` | `str` or `BorderStyle` | Border style — see below. |
| `border_color` | color | Border line color. |
| `title` | `str` | Text on the top border (implies a round border if none set). |
| `bg` | color | Background fill color. |
| `align` | `str` or `Align` | Cross-axis alignment: `"start"`, `"center"`, `"end"`, `"stretch"`. |
| `justify` | `str` or `Justify` | Main-axis distribution: `"start"`, `"center"`, `"end"`, `"between"`, `"around"`, `"evenly"`. |
| `width` | `int` | Fixed width in cells. |
| `height` | `int` | Fixed height in cells. |
| `grow` | `float` | Flex grow factor (fill available space). |

`color` is anything the [color resolver](text-and-style.md#colors) accepts.

### Border styles

Pass a string (case-insensitive) or a `BorderStyle` enum:

| String | Look |
|--------|------|
| `"round"` | `╭─╮` rounded corners (default for `card`) |
| `"single"` | `┌─┐` standard |
| `"double"` | `╔═╗` double line |
| `"bold"` | `┏━┓` heavy |
| `"classic"` | `+-+` ASCII |
| `"dashed"` | `╭┄╮` dashed edges |
| `"none"` | no border |

### Padding forms

```python
card("x", pad=1)            # 1 cell on all sides
card("x", pad=(1, 2))       # 1 vertical, 2 horizontal
card("x", pad=(0, 1, 0, 1)) # top, right, bottom, left
```

### Alignment & distribution

`align` controls the **cross axis**, `justify` the **main axis**. For a `row`,
the main axis is horizontal; for a `col`, vertical.

```python
# center children horizontally inside a 40-wide column
col("a", "b", align="center", width=40)

# spread a row's children to the edges
row("left", "right", justify="between", width=40)
```

## Convenience widgets

### `field(label, value, *, label_color="slate", value_color=None)`

A `Label: value` row with a dim label. `value` may be a string, `T`, or
`Element`. `value_color` tints a string value.

```python
from maya_py import field

field("Status", "Online", value_color="green")
field("Region", T("us-east-1").fg("gold"))    # pre-styled value
```

Renders as `Status: Online` with `Status:` in slate.

### `hr(width=40, char="─", col="slate")`

A horizontal rule. Returns a styled `Element`.

```python
from maya_py import hr

hr()              # 40-wide slate rule
hr(20, "═", "sky")  # 20-wide double-line in sky blue
```

### `spacer()`

A one-row blank gap. Use between sections when `gap` won't do.

```python
from maya_py import col, spacer

col("top section", spacer(), "bottom section")
```

## Nesting

Layouts nest arbitrarily — the children of any stack can be other stacks:

```python
from maya_py import card, col, row, b, field

card(
    b("Server").fg("sky"),
    row(
        col(field("CPU", "12%"), field("RAM", "4.2G")),
        col(field("Disk", "60%"), field("Net", "1.2M/s")),
        gap=4,
    ),
    title="metrics",
)
```

## Worked example: a status table

```python
from maya_py import card, col, row, b, c, T, hr

services = [("api", "up"), ("db", "up"), ("cache", "down")]

rows = [
    row(
        T(name).fg("sky"),
        c("● " + state, "green" if state == "up" else "red"),
        gap=2,
    )
    for name, state in services
]

ui = card(
    b("Services").fg("gold"),
    hr(24),
    col(*rows),
    title="status",
)
```

## Next

- [Apps](apps.md) — wire layouts to live state.
- [Rendering](rendering.md) — get layouts onto the screen.
