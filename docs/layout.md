# Layout

[← Manual index](index.md)

maya lays out every UI with a **flexbox** solver (Yoga — the same engine behind
React Native). You never compute coordinates. You describe *boxes inside boxes*,
declare how they should grow, align, and space themselves, and the solver
resolves an exact `(x, y, w, h)` for every node before maya paints it (see the
pipeline in [concepts.md](concepts.md)).

This page makes the solver predictable. Once the main/cross-axis model clicks,
you can look at a tree of `row`/`col`/`card` calls and know what the screen will
do — no guessing, no trial-and-error.

---

## 1. The flexbox mental model

Every container has a **flex direction** that defines two perpendicular axes:

| Direction | Main axis (children laid along) | Cross axis (perpendicular) |
|-----------|----------------------------------|-----------------------------|
| `row` (`FlexDirection.Row`) | horizontal → | vertical ↓ |
| `col` (`FlexDirection.Column`) | vertical ↓ | horizontal → |

This is the **one fact everything else hangs off of.** `justify` works on the
main axis; `align` works on the cross axis; `grow`/`shrink`/`basis` resize along
the main axis. Flip the direction and every one of those swaps meaning.

```
row(...)                              col(...)
┌──── main axis (justify) ────►       ┌─ cross axis (align) ─►
│ ┌────┐ ┌────┐ ┌────┐                │ ┌──────────────┐
│ │ a  │ │ b  │ │ c  │                │ │      a       │   main axis (justify)
│ └────┘ └────┘ └────┘                │ └──────────────┘        │
▼ cross axis (align)                  │ ┌──────────────┐        ▼
                                      │ │      b       │
                                      │ └──────────────┘
```

### Sizing: the three-step solve

For each container the solver does, conceptually:

1. **Basis** — give every child its starting main-axis size. This is `basis=` if
   set, otherwise its `width`/`height` (for the main axis), otherwise its
   *content* size (`"auto"`).
2. **Distribute free space** — measure the leftover main-axis space (container
   size minus the sum of bases minus `gap`s). If positive, hand it out in
   proportion to each child's **`grow`** factor. If negative (children overflow),
   take it back in proportion to each child's **`shrink`** factor.
3. **Align on the cross axis** — size and position each child across the axis per
   the container's **`align`** (and per-child `align_self`).

The container's main-axis *packing* of whatever space is still free after
step 2 — i.e. when no child grows — is governed by **`justify`**.

### `justify` — main-axis packing

Set on the container; affects how children sit along the main axis when there's
slack. Accepts a `Justify` enum or a friendly string:

| String | `Justify` | Behavior |
|--------|-----------|----------|
| `"start"` | `Start` | pack at the start (default) |
| `"center"` | `Center` | pack centered |
| `"end"` | `End` | pack at the end |
| `"between"` | `SpaceBetween` | first/last flush to edges, equal gaps between |
| `"around"` | `SpaceAround` | equal space around each child (half-gaps at edges) |
| `"evenly"` | `SpaceEvenly` | equal space between and at both edges |

### `align` — cross-axis alignment

Set on the container; positions each child across the axis. Accepts an `Align`
enum or a string:

| String | `Align` | Behavior |
|--------|---------|----------|
| `"stretch"` | `Stretch` | fill the cross axis (default when no cross size set) |
| `"start"` | `Start` | pin to the cross-axis start |
| `"center"` | `Center` | center across the axis |
| `"end"` | `End` | pin to the cross-axis end |
| `"baseline"` | `Baseline` | align text baselines |

A single child can override its container with `align_self="center"` (same value
set).

### `grow` / `shrink` / `basis` — the per-child main-axis levers

These live on the **child** box (passed as that box's own kwargs), not the
parent:

- **`grow`** (float, default 0) — share of *extra* main-axis space. `grow=1` on
  one child makes it eat all the slack; two children with `grow=1` split it
  50/50; `grow=2` vs `grow=1` splits it 2:1.
- **`shrink`** (float, default 1) — share of the *deficit* when children overflow.
  `shrink=0` means "never shrink me," so this box keeps its size and pushes the
  overflow onto its siblings.
- **`basis`** (size) — the main-axis starting size before grow/shrink. Think of
  it as `width` for a `row` child or `height` for a `col` child, but
  flex-specific. `basis="auto"` (the default) uses content size.

> **Predicting a layout, in one breath:** read the container's direction → that
> fixes which axis `justify`/`grow` act on and which `align` acts on. Then: do
> any children `grow`? If yes, they absorb the slack (justify is moot). If no,
> `justify` packs them. Cross-axis size comes from `align`.

---

## 2. The containers

All of these come from the friendly API: `from maya_py import col, row, card, …`.
Strings, `T`s, tuple cells, and nested elements are all valid children (see
[concepts.md §3](concepts.md) and [text-and-style.md](text-and-style.md)).

### `col` and `row` — the workhorses

```python
col(*children, **opts) -> Element     # vertical stack  (main axis ↓)
row(*children, **opts) -> Element      # horizontal stack (main axis →)
```

Everything in [§3](#3-the-shared-options) is a valid `**opt`. A bare `col("a",
"b")` with no options takes a fused fast path; the options just configure the
same box.

```python
from maya_py import row, col, b

col(
    b("Title"),
    row("left", "right", gap=2),
    "footer",
    gap=1,
)
```

### `card` — bordered, padded `col`

```python
card(*children, title=None, **opts) -> Element
```

`card` is exactly `col(...)` with two defaults applied: `pad=1` and
`border=BorderStyle.Round`. It's the everyday panel. `title=` is sugar for a
centered border caption (see `title` in [§3](#3-the-shared-options)).

```python
from maya_py import card, field
card(field("Status", "online"), field("Region", "us-east"), title="Server")
```

### `center` — center on both axes

```python
center(*children, **opts) -> Element
```

Defaults `align="center"`, `justify="center"`, `direction=Column`. Give it a
size (or `grow=1`) so there's space to center *within*:

```python
from maya_py import center, card
center(card("Ready"), height=20, grow=1)   # vertically + horizontally centered
```

### `stack` — z-layering (overlay)

```python
stack(*layers) -> Element
```

A z-stack: layers paint on top of each other. **The first layer sets the size;**
later layers overlay it (clipped to that box). Use it for badges, overlays, and
modals.

```python
from maya_py import stack, card, T
stack(card("body", height=10), T("NEW").fg("red"))
```

> `stack` is the friendly wrapper over the native `zstack`. The low-level
> `zstack`, `vstack`, and `hstack` are also exported from `maya_py` (they take
> already-built `Element`s and map to overlay / `Column` / `Row` boxes); in
> day-to-day code prefer `col`, `row`, and `stack`, which coerce strings and
> tuples for you.

### `box` — the raw container

`box` is the native flex container that `col`/`row`/`card` are built on. It takes
already-built children and the full kwarg surface directly:

```python
import maya_py as maya
maya.box(maya.text("hi"), border=maya.Round, padding=1, gap=1)
```

You rarely need it from the friendly API — `col`/`row` forward the same options
and accept bare strings — but it's there when you're working at the low level.

### Leaves

| Function | Signature | What it is |
|----------|-----------|------------|
| `field` | `field(label, value, *, label_color="slate", value_color=None)` | a `Label: value` row with a dim label |
| `hr` | `hr(width=40, char="─", col="slate")` | a horizontal rule (a styled line of `char`) |
| `spacer` | `spacer()` | a **one-row** blank gap |
| `blank` | `blank()` | the native empty leaf (`spacer` is built on it) |
| `divider` | `divider(label="", *, line=None, color=None)` | a full-width labeled separator (a [widget](widgets.md)) |
| `nothing` | `nothing()` | a **zero-row** fragment — consumes no space (vs `spacer`'s one row) |

```python
from maya_py import col, field, hr, spacer, divider, nothing, when
col(
    field("Name", "Ayush"),
    hr(30),
    divider("Section"),
    when(False, "hidden", else_=nothing()),   # occupies no rows
    spacer(),                                   # one blank row
    "end",
)
```

`when(cond, then, else_=None)` keeps conditionals inside the tree, defaulting the
un-taken branch to `nothing()` — handy for "show this only if…".

---

## 3. The shared options

These keyword options apply to `col`, `row`, `card`, and the underlying `box`
(and `center`, which is a `box`). They are forwarded to maya's box builder; the
friendly API resolves string aliases and color-ish values for you.

### Spacing & decoration

| Option | Accepts | Effect |
|--------|---------|--------|
| `gap` | int (cells) | space *between* children along the main axis |
| `pad` | int, or per-side spec | inner padding (alias for the native `padding`) |
| `margin` | int, or per-side spec | outer margin |
| `bg` | color-ish | background fill color |
| `fg` | color-ish | default foreground for text inside |

### Borders

| Option | Accepts | Effect |
|--------|---------|--------|
| `border` | `BorderStyle` or a name string | draw a border; setting it adds a 1-cell frame |
| `border_color` | color-ish | border line color |
| `border_sides` | `BorderSides` (use `sides(...)`) | which edges to draw |
| `title` | str | centered caption in the top border (implies a Round border) |
| `border_text` | str | caption text in the border (top, start-aligned by default) |
| `border_text_end` | str | a second caption anchored at the *end* of the border |

Border style names (case-insensitive strings) map to `BorderStyle`:

| String | `BorderStyle` | Look |
|--------|---------------|------|
| `"round"` | `Round` | `╭─╮` rounded corners (the `card` default) |
| `"single"` | `Single` | `┌─┐` square single line |
| `"double"` | `Double` | `╔═╗` double line |
| `"bold"` | `Bold` | `┏━┓` heavy line |
| `"classic"` | `Classic` | `+--+` ASCII |
| `"dashed"` | `Dashed` | dashed line |
| `"none"` | `None_` | no visible border (reserves no frame) |

> `BorderStyle` also has `SingleDouble`, `DoubleSingle`, and `Arrow`. The module
> re-exports the common ones unprefixed: `Round`, `Single`, `Double`,
> `BoldBorder`, `Classic`, `Dashed`, `SingleDouble`, `DoubleSingle`, `Arrow`.

`sides(...)` builds the per-edge mask:

```python
sides(*, top=True, right=True, bottom=True, left=True) -> BorderSides
```

```python
from maya_py import card, sides
card("body", border_sides=sides(top=False, bottom=False))   # left+right only
```

`BorderSides` also exposes presets as constructors: `BorderSides.all()`,
`BorderSides.none()`, `BorderSides.horizontal()`, `BorderSides.vertical()`, and
single-edge `top()` / `right()` / `bottom()` / `left()`.

### Alignment

| Option | Accepts | Axis |
|--------|---------|------|
| `justify` | `Justify` or name (`"start"`/`"center"`/`"end"`/`"between"`/`"around"`/`"evenly"`) | main |
| `align` | `Align` or name (`"start"`/`"center"`/`"end"`/`"stretch"`/`"baseline"`) | cross |
| `align_self` | `Align` or name | this box's own cross-axis override |

### Sizing

| Option | Effect |
|--------|--------|
| `width` / `height` | fixed/explicit box size |
| `min_width` / `max_width` | clamp the resolved width |
| `min_height` / `max_height` | clamp the resolved height |
| `grow` | main-axis grow factor (float; see [§1](#1-the-flexbox-mental-model)) |
| `shrink` | main-axis shrink factor (float) |
| `basis` | main-axis starting size before grow/shrink |

**Accepted value forms** for every size option (`width`, `height`, the
`min_`/`max_` clamps, and `basis`):

| Form | Meaning | Example |
|------|---------|---------|
| `int` | fixed number of cells | `width=20` |
| `"50%"` | percent of the parent's inner size | `width="50%"` |
| `float` in (0, 1] | fraction of parent (e.g. `0.5` = 50%) | `width=0.5` |
| `"auto"` | content-driven / fill parent | `width="auto"` |
| `cells(n)` | explicit fixed `Dimension` | `width=cells(20)` |
| `pct(n)` | explicit percent `Dimension` | `width=pct(50)` |
| `auto()` | explicit auto `Dimension` | `width=auto()` |

The bare forms (`20`, `"50%"`, `0.5`, `"auto"`) are coerced for you. The helpers
build an explicit `Dimension` when you want to be unambiguous:

```python
pct(value)   -> Dimension      # Dimension.percent(value)
cells(value) -> Dimension      # Dimension.fixed(value)
auto()       -> Dimension      # Dimension.auto()
```

`Dimension` objects (the native type) also expose `is_fixed`, `is_percent`,
`is_auto` predicates if you ever need to inspect one.

### Wrap & overflow

| Option | Accepts | Effect |
|--------|---------|--------|
| `wrap` | `FlexWrap` or name (`"nowrap"`/`"wrap"`/`"reverse"`) | let children flow onto new main-axis lines |
| `overflow` | `Overflow` or name (`"visible"`/`"hidden"`/`"scroll"`) | how content past the box edge is handled |

`wrap="wrap"` is what turns a `row` of cards into a **responsive grid** — see
[§6](#6-worked-layouts).

---

## 4. `grow(...)` and size-aware `component(...)`

### `grow(child, factor=1.0, **opts)`

A convenience wrapper that puts one child in its own box with a grow factor — so
you don't have to set `grow=` on the child's own container:

```python
grow(child: Any, factor: float = 1.0, **opts) -> Element
```

```python
from maya_py import row, grow
row(sidebar, grow(main_content))         # main_content fills the rest
row(grow(a, 2), grow(b, 1))              # a gets twice b's slack
```

`grow(x)` is equivalent to giving `x`'s wrapper `grow=1`; passing a `factor`
changes the share. Extra `**opts` apply to the wrapper box.

### `component(render_fn, *, grow=None, width=None, height=None)`

A **size-aware** leaf. `render_fn(w, h)` is called *after* layout has allocated
this node a width and height, and returns the element to fill that space. Use it
to draw anything that needs to know its own box — progress fills, ASCII bars,
charts, anything width-dependent:

```python
component(render_fn: Callable[[int, int], Any], *,
          grow: float | None = None, width=None, height=None) -> Element
```

```python
from maya_py import col, component, T

def bar(w, h):
    filled = int(w * 0.6)
    return T("█" * filled + "░" * (w - filled)).fg("green")

col("Loading", component(bar, height=1, grow=1))
```

> **Pitfall (from [concepts.md §8](concepts.md)):** `component` needs the live
> renderer's *measure pass* to learn its `(w, h)`. It will **not** render through
> `to_string` / `show`, which run a single static pass with no allocation step.
> Drive a `component` via `App.run`, `run_program`, `animate`, or `live`. For
> static output that needs pixels, use `halfblock` with a pre-built grid instead.

---

## 5. The relevant enums

All exported from `maya_py`. You can pass either the enum member or, in the
friendly API, the lowercase string alias shown in [§3](#3-the-shared-options).

| Enum | Members |
|------|---------|
| `FlexDirection` | `Row`, `Column`, `RowReverse`, `ColumnReverse` (re-exported as `Row`, `Column`, `RowReverse`, `ColumnReverse`) |
| `Align` | `Start`, `Center`, `End`, `Stretch`, `Baseline` |
| `Justify` | `Start`, `Center`, `End`, `SpaceBetween`, `SpaceAround`, `SpaceEvenly` |
| `BorderStyle` | `Round`, `Single`, `Double`, `Bold`, `Classic`, `Dashed`, `SingleDouble`, `DoubleSingle`, `Arrow`, `None_` |
| `FlexWrap` | `NoWrap`, `Wrap`, `WrapReverse` |
| `Overflow` | `Visible`, `Hidden`, `Scroll` |
| `Dimension` | constructors `fixed(n)`, `percent(n)`, `auto()`; predicates `is_fixed`, `is_percent`, `is_auto` |
| `BorderSides` | constructors `all()`, `none()`, `horizontal()`, `vertical()`, `top()`, `right()`, `bottom()`, `left()` (or build via `sides(...)`) |
| `BorderTextAlign` | `Start`, `Center`, `End` |
| `BorderTextPos` | `Top`, `Bottom` |

`BorderTextAlign` / `BorderTextPos` describe where a border caption sits; the
friendly `title=` shortcut uses a centered top caption, while `border_text` /
`border_text_end` give you start- and end-anchored captions.

---

## 6. Worked layouts

Each of these runs as-is. Wrap a tree in `show(...)` (or `to_string`) for a
one-shot static render, or return it from a view as in [apps.md](apps.md). (The
size-aware `component` examples need a live runtime — see
[§4](#4-grow-and-size-aware-component).)

### Sidebar + main content (grow)

The classic app shell: a fixed-width sidebar, the rest filled by the main pane.

```python
from maya_py import row, col, card, grow, b, field, show

sidebar = card(
    b("Menu"),
    "Dashboard", "Servers", "Logs", "Settings",
    width=20,            # fixed
    gap=0,
)

main = card(
    b("Dashboard"),
    field("Uptime", "13d 4h"),
    field("Requests", "1.2M"),
    title="us-east-1",
)

show(row(sidebar, grow(main), gap=1, height=14))
```

`sidebar` keeps its 20 cells (no grow); `grow(main)` absorbs all remaining
horizontal space. The `height=14` gives the row a cross-axis size so both panes
stretch to full height.

### Centered modal (z-stack + center)

An overlay centered in a region:

```python
from maya_py import stack, center, card, b, show

backdrop = card("", width=60, height=16, border="none", bg="black")

modal = card(
    b("Delete file?"),
    "This cannot be undone.",
    "",
    "[ Cancel ]   [ Delete ]",
    title="Confirm",
    border="double",
    border_color="red",
)

# First layer sets the size; center the modal on top of it.
show(stack(backdrop, center(modal, width=60, height=16)))
```

`center` fills the 60×16 region and centers the `modal` on both axes; `stack`
paints it over the backdrop.

### Responsive card grid (wrap)

A `row` with `wrap="wrap"` flows its children onto new lines when they run out of
horizontal room — a fluid grid that reflows with the terminal width:

```python
from maya_py import row, card, b, field, show

def tile(name, val):
    return card(b(name), field("value", val), width=18, height=4)

grid = row(
    tile("CPU", "62%"),
    tile("Memory", "3.1 GB"),
    tile("Disk", "240 GB"),
    tile("Net", "12 Mbps"),
    tile("Load", "0.74"),
    tile("Temp", "51C"),
    wrap="wrap",
    gap=1,
)

show(grid, width=64)     # try different widths to see it reflow
```

Each tile is a fixed 18×4; `wrap="wrap"` packs as many as fit per row, then wraps.
Narrow the `width` and the same tree lays out fewer per line.

### A status bar pinned across the bottom (grow as spacer)

```python
from maya_py import col, row, card, grow, b, dim_text, show

body = grow(card(b("Editor"), "…your content…"))

status = row(
    dim_text(" main* "),
    grow(row()),                 # an empty growing spacer pushes the rest right
    dim_text(" UTF-8 "),
    dim_text(" Ln 12, Col 4 "),
    bg="slate",
)

show(col(body, status, height=12))
```

The empty `grow(row())` in the status bar eats the slack, pushing the trailing
indicators flush right — `justify="between"` would do the same for evenly-split
ends.

---

## 7. Where to go next

- **[Text & Style](text-and-style.md)** — `T`, markup helpers, colors, tuple
  cells (the leaves you put *inside* these containers).
- **[Widgets](widgets.md)** — the native renderers (`table`, `gauge`, `divider`,
  `viewport`, `scrollbar`, …) that drop into any layout.
- **[concepts.md](concepts.md)** — the render pipeline, `memo`, and the
  performance model behind why building less matters.

More runnable layouts live in the examples directory, e.g.
[dashboard.py](https://github.com/1ay1/maya-py/blob/master/examples/dashboard.py)
and [ide.py](https://github.com/1ay1/maya-py/blob/master/examples/ide.py).
