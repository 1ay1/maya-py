# Responsive Layout & Mouse Interaction

[← Manual index](index.md)

The [Layout](layout.md) page teaches you to build *one* layout — a fixed
arrangement of boxes. This page teaches layouts that **reshape themselves to
the terminal**: a dashboard that flows from four columns on an ultrawide down
to a single stack on a phone-sized pane, a header that sheds detail as space
runs out, and clickable chrome that knows *where it was actually painted*.

Everything here is new in maya-py **0.3.x** and mirrors maya's own
`element/grid.hpp` and `core/hit.hpp`. If you've never built a maya UI before,
read [Getting Started](getting-started.md) and [Layout](layout.md) first — this
page assumes you know `row`, `col`, `card`, and `grow`.

---

## 1. Why responsive layout?

A terminal is not one size. The same app runs in a 200-column tmux pane, an
80-column SSH session, and a 40-column phone terminal — and it should look
*designed* in all three, not truncated in two of them.

The naive fix is breakpoints: "if width < 80, use the compact view." That
works until a label changes, an icon gains a cell, or a locale widens a word —
and now your hand-picked threshold is wrong and the layout shears mid-cell. The
bug class is real and maddening.

maya's answer is **measurement, not magic numbers**. Every tool on this page
re-solves itself from the width the layout *actually* hands it, using the real
measured size of your content. There are no thresholds to keep in sync with the
UI, because the decisions fall out of the content itself.

> **The one idea:** you describe *what you want at each size*, and maya picks
> the arrangement that fits the width it's given — live, on every resize.

---

## 2. `grid` — the one-number dashboard

The workhorse. You have N cards and you want them tiled: as many per row as
fit, wrapping to new rows, collapsing to a single column when narrow. That's a
`grid`, and it takes **one number** — how wide one cell wants to be:

```python
from maya_py import grid, card, show

cards = [
    card("CPU\n42%",  title="cpu"),
    card("MEM\n6.1G", title="mem"),
    card("NET\n88ms", title="net"),
    card("DISK\n71%", title="disk"),
]

show(grid(cards, 20))     # "each cell wants ~20 columns"
```

Resize your terminal and watch it re-flow:

- **wide** (≥ 4·20 cols): all four cards side by side
- **medium**: two per row, two rows
- **narrow** (< 20 cols): one column, four rows stacked

You never computed a single width. maya divides the slot it's given by your
`min` (plus gaps), clamps to a whole number of cells, and spreads the row width
exactly so the last cell ends flush with the edge.

**Options** (all keyword):

| arg | default | effect |
|-----|---------|--------|
| `min` | 24 | a cell's comfortable minimum width (the one number) |
| `max_cols` | 0 | cap cells per row (0 = as many as fit) |
| `gap_x` | 1 | blank columns between cells |
| `gap_y` | 0 | blank rows between rows |
| `grow_rows` | False | rows share surplus height (needs a definite parent height) |

> **Takeaway:** if you're about to write width math to tile some cards, you
> want `grid(cards, N)` instead. `N` is "how wide does one card need to look
> right?" — a design decision, not a computed value.

---

## 3. `sidebar` — a rail beside a main pane

The other layout every dashboard needs: a fixed-width rail (stats, nav, a
file tree) next to a main pane that takes the rest — and the pair should
**stack vertically** when the terminal is too narrow to show both.

```python
from maya_py import sidebar, card, show

rail = card("Filters\n\n[x] active\n[ ] archived", title="nav")
main = card("… main content …", title="results")

show(sidebar(rail, main, 24))    # rail is 24 cols; main takes the rest
```

When the slot narrows past the point where the main pane would be crushed, the
rail drops *above* the main pane (reading order preserved), so nothing shears.

| arg | default | effect |
|-----|---------|--------|
| `width` | 32 | the rail's fixed width in columns |
| `stack_below` | 0 | stack when slot < this; 0 = auto (2×width) |
| `gap` | 1 | blank columns between rail and main |
| `right` | False | put the rail on the *right* instead of the left |

Compose them: a rail beside a grid is a full three-shape dashboard in two
lines.

```python
show(sidebar(rail, grid(cards, 20), 24))
```

---

## 4. `fit_row` / `fit_col` — shed detail, never shear

A status header is the classic responsive-bug magnet: logo, hostname, kernel,
uptime, a battery chip, process counts — all fine at 120 columns, a sheared
mess at 60. `fit_row` fixes the whole class declaratively. You list the items
once, tag the optional ones with a **keep rank**, and the row drops items —
lowest keep first, ties dropping the rightmost — until what remains fits:

```python
from maya_py import fit_row, T, show

def status_header(host, kernel, uptime, procs):
    return fit_row(
        T("● maya").fg("sky").bold,       # essential — never dropped
        (T(host).fg("gold"), 5),          # (element, keep): 5 = important
        (T(kernel).dim, 4),
        (T(f"up {uptime}"), 2),
        (T(f"{procs} procs").dim, 1),     # first to go when tight
        gap=2,
    )

show(status_header("web-01", "6.9.3", "14d", 214))
```

Widths come from **measuring the real styled fragments** — no hand-summed cell
counts to drift out of sync with the content. Notes:

- An item is **atomic**: group an icon + label + value into one element
  (`row(...)`) so it appears or disappears as a unit.
- An item with no `(el, keep)` tuple has keep = *always* — it never drops.
- `fit_col` is the vertical twin, for the axis everyone forgets: a footer or a
  side panel that should drop rows when the pane is too *short* rather than
  overflow off-screen.

> **Takeaway:** never write "if narrow, hide the uptime chip." Tag it with a
> keep rank and let the row decide, at every width, from measured sizes.

---

## 5. `pick` — semantic zoom

Sometimes you don't want to *drop* pieces — you want a **different rendering**
of the same thing at each size. A host chip might be `🖥 web-01 · linux 6.9` when
there's room, `🖥 web-01` when there's less, and just `🖥` when there's almost
none. That's `pick`: give it alternatives richest-first; it renders the first
one that fits, and the **last** is the guaranteed fallback (used even if it
doesn't fit — something must render).

```python
from maya_py import pick, row, T, show

def host_chip(host, os_):
    return pick(
        row(T("🖥 ").fg("sky"), T(host), T(" · "), T(os_).dim),  # rich
        row(T("🖥 ").fg("sky"), T(host)),                         # medium
        T("🖥").fg("sky"),                                        # fallback
    )

show(host_chip("web-01", "linux 6.9"))
```

`pick` measures each alternative at its natural width and picks the first that
fits the slot — the terminal equivalent of responsive images' `srcset`.

---

## 6. `place` and `clamp_width` — positioning & max width

Two smaller tools you'll reach for constantly:

**`place(child, h, v)`** — position one child inside the slot flex gives the
wrapper. The 9-position grid: `h` is `"left" | "center" | "right"`, `v` is
`"top" | "middle" | "bottom"`.

```python
from maya_py import place

place(dialog)                       # dead center — modals, empty states
place(toast, "right", "top")        # corner-anchored — toasts, notifications
place(spinner, "center", "middle")  # centered loading
```

**`clamp_width(el, max_width, align)`** — cap content width on huge terminals
and align the clamped column. Full-width prose on a 300-column ultrawide is
unreadable (the eye loses the line on the way back); `clamp_width` is
libadwaita's `AdwClamp` for terminals. Below `max_width` it's a transparent
wrapper — the child gets the whole slot.

```python
from maya_py import clamp_width

clamp_width(article, 100)              # never wider than 100 cells, centered
clamp_width(toast, 60, "right")        # corner-anchored popup
```

---

## 7. `adapt` and `fill` — build your own responsive component

`grid`, `sidebar`, and `pick` are all built on one primitive: a component that
receives the width it's given and returns a tree. When the built-ins don't fit
your case, drop to that primitive directly.

**`adapt(fn)`** calls `fn(width) -> element | str` with the **actual slot
width** at layout time. Rebuild your UI however you like per width:

```python
from maya_py import adapt, col, row

def responsive_form(fields):
    # two columns when wide, one when narrow — measured, not guessed
    return adapt(lambda w: (
        row(*fields, gap=2) if w >= 60 else col(*fields, gap=1)
    ))
```

**`fill(fn)`** calls `fn(w, h) -> element | str` with the slot **size** flex
allocated. The crucial difference from a plain component: `fill` sizes to its
SLOT (it sets `grow=1` with a tiny basis), so it *claims* leftover space
instead of collapsing to its content's natural size. This is exactly what a
chart wants — take whatever's left after the fixed meters. Give the parent a
definite `height=` so there's slack for the fill to grow into:

```python
from maya_py import fill, col, gauge, sparkline

dashboard = col(
    gauge(0.72, "load"),                         # fixed height
    gauge(0.41, "mem"),                          # fixed height
    fill(lambda w, h: sparkline(series[-w:],     # fills the rest
                                label="req/s")),
    height=20,                                    # definite parent → slack to fill
)
```

> **Rule of thumb:** use `adapt` when you want to *switch layouts* by width;
> use `fill` when you want a single child to *absorb leftover space*.

**`measure(el, max_width=…) -> (w, h)`** returns any element's natural size
under a width cap — the primitive the whole toolkit measures with. Reach for it
when you need to make your own fit decision.

```python
from maya_py import measure

w, h = measure(some_widget, max_width=80)
```

---

## 8. Pretty text — `rainbow` and `gradient_rule`

Two flourishes that read as "designed" for near-zero cost, both responsive to
the width they're given:

```python
from maya_py import rainbow, gradient_rule, show, col

show(col(
    rainbow("maya-py"),                       # HSL hue sweep across the text
    gradient_rule("#7F5AF0", "#2CB67D"),      # full-width gradient divider
))
```

`rainbow(text)` colors each character by its horizontal position (one
`TextElement`, so it still wraps and measures like plain text).
`gradient_rule(*stops, glyph="─")` tiles a glyph across the *full width it's
allotted* and colors it from the first stop to the last — a hero underline or
section divider that always spans the pane, at any terminal size. Colours
accept the usual names / `"#rrggbb"` / `(r,g,b)` / `Color`.

---

## 9. Mouse interaction — the hit registry

Responsive chrome is only half the story: clickable chrome needs to know
*where it was painted*. Historically a fullscreen app had to reverse-engineer
the layout math by hand — leading offsets, per-tab label widths, gap
accounting — and keep that mirror in lockstep with the widget forever. Every
restyle silently broke it.

maya's **hit registry** lets the renderer record where things landed. You tag a
box with an id; the painter appends its **absolute painted rect** to a
per-frame registry; you ask "what's at (x, y)?" and the answer is correct *by
construction* — it came from the same layout pass that drew the pixels.

### The three moves

**1. Tag a box** with `hit=hit_id(kind, index)` — any `box`/`row`/`col`/`card`
takes the kwarg. `hit_id` packs a *kind* (which family of target) and an
*index* (which one) into a single 64-bit id:

```python
from maya_py import row, hit_id

KIND_TAB = 1
tabs = row(*[
    row(f" {label} ", hit=hit_id(KIND_TAB, i))
    for i, label in enumerate(("Files", "Search", "Git"))
], gap=1)
```

**2. Ask who was clicked** with `hit_test(x, y)` — it returns the topmost id
painted at that cell this frame, or `None`. An `@app.on_click` handler receives
the click as `(state, col, row)`, so pass those straight in; unpack the id with
`hit_kind` / `hit_index`:

```python
from maya_py import hit_test, hit_kind, hit_index

@app.on_click()
def click(state, col, row):
    tid = hit_test(col, row)
    if tid is not None and hit_kind(tid) == KIND_TAB:
        state.active_tab = hit_index(tid)
```

**3. (Optional) anchor to a target** with `hit_rect(id)`, which returns the
painted `(x, y, w, h)` of a target — so you can float a tooltip or popup at a
button without knowing where layout put it:

```python
from maya_py import hit_rect

rect = hit_rect(hit_id(KIND_TAB, state.active_tab))
if rect is not None:
    x, y, w, h = rect
    # draw an underline / popup anchored under that tab
```

### A complete clickable-tabs app

```python
from maya_py import (App, col, row, card, hit_id, hit_test,
                     hit_kind, hit_index, T)

KIND_TAB = 1
TABS = ("Files", "Search", "Git")

app = App.fullscreen("tabs", mouse=True)   # mouse=True enables click reporting
s = app.state(active=0)                     # app.state(...) RETURNS the state
app.quit_on("q")                             # bind q -> stop, in one line

@app.on_click()
def click(st, col_, row_):
    tid = hit_test(col_, row_)
    if tid is not None and hit_kind(tid) == KIND_TAB:
        st.active = hit_index(tid)

@app.view
def view(st):
    tabbar = row(*[
        row(f" {label} ",
            bg="indigo" if i == st.active else None,
            hit=hit_id(KIND_TAB, i))
        for i, label in enumerate(TABS)
    ], gap=1)
    return card(tabbar, T(f"\n{TABS[st.active]} panel"), title="editor")

app.run()
```

Click a tab and it activates — with no layout math anywhere in your code. When
you restyle the tab bar (add a pad cell, swap a glyph), the click targets move
with it automatically, because they *are* the painted rects.

> **Why kinds?** One app has many clickable families — tabs, table rows, footer
> buttons. Packing a `kind` into the id lets one `hit_test` result tell you both
> *what* was clicked and *which one*, with a single switch on `hit_kind`.

### Hover highlights

For hover effects (highlight the row under the cursor), enable **hover motion**
so bare no-button movement reaches your handlers, and use `on_mouse` (which
sees *every* mouse event) with the `mouse_moved` / `mouse_pos` predicates:

```python
import maya_py as maya

app = App.fullscreen("browser", mouse=True, hover_motion=True)
s = app.state(hovered=-1)

@app.on_mouse
def mouse(st, ev):
    if maya.mouse_moved(ev):
        pos = maya.mouse_pos(ev)
        tid = hit_test(*pos) if pos else None
        st.hovered = hit_index(tid) if tid and hit_kind(tid) == KIND_ROW else -1
```

`hover_motion` is off by default because mode 1003 floods move events; turn it
on only when you actually paint a hover state.

---

## 10. Putting it together

A responsive, clickable dashboard is now a short function — no thresholds, no
layout math:

```python
from maya_py import (App, sidebar, grid, fit_row, card, col, T,
                     hit_id, hit_test, hit_kind, hit_index)

KIND_CARD = 1

app = App.fullscreen("ops", mouse=True)
s = app.state(selected=-1,
              metrics=[("cpu", 42), ("mem", 61), ("net", 88), ("disk", 71)])
app.quit_on("q")

@app.on_click()
def click(st, col_, row_):
    tid = hit_test(col_, row_)
    if tid is not None and hit_kind(tid) == KIND_CARD:
        st.selected = hit_index(tid)

@app.view
def view(st):
    header = fit_row(
        T("● ops").fg("sky").bold,
        (T("region us-east-1").dim, 3),
        (T("14d uptime").dim, 1),
        gap=2,
    )
    cards = [
        card(f"{name.upper()}\n{val}%",
             title=name,
             bg="indigo" if i == st.selected else None,
             hit=hit_id(KIND_CARD, i))
        for i, (name, val) in enumerate(st.metrics)
    ]
    rail = card("\n".join(n for n, _ in st.metrics), title="services")
    return col(header, sidebar(rail, grid(cards, 18), 18))

app.run()
```

Resize it: the grid re-flows, the header sheds chips, the sidebar stacks.
Click a card: it highlights — the hit rect follows the card wherever the grid
placed it this frame.

---

## Where to go next

- **[Layout](layout.md)** — the flexbox fundamentals (`row`/`col`/`grow`/
  `align`/`justify`) these tools compose over.
- **[Apps](apps.md)** — `@app.on_click` / `@app.on_move`, mouse plumbing, and
  the full event model.
- **[Widgets → table](widgets.md#table)** — the data table's own responsive
  weighted columns and its `row_hit_kind` / `header_hit_kind` integration with
  this hit registry.
- **[API Reference → Responsive toolkit](api-reference.md#responsive-toolkit)**
  — every signature in one table.

Runnable versions live in
[examples/dashboard.py](https://github.com/1ay1/maya-py/blob/master/examples/dashboard.py)
and [examples/ide.py](https://github.com/1ay1/maya-py/blob/master/examples/ide.py).
