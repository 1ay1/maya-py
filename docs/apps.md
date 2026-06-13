# Apps

[← Manual index](index.md)

`App` is the high-level way to build an interactive terminal program. It owns
the event loop, the state, and the render schedule — you just declare key
bindings and a view.

## The shape of an app

```python
from maya_py import App, card, b

app = App("counter", inline=True)   # 1. create
app.state(n=0)                      # 2. seed state

@app.on("+", "=")                   # 3. bind keys
def inc(s):
    s.n += 1

@app.on("q", "esc")
def quit_(s):
    app.stop()

@app.view                           # 4. declare the view
def view(s):
    return card(b(f"Count: {s.n}"))

app.run()                           # 5. go
```

## `App(title="", *, inline=True, mouse=False, fps=0, quit_on_ctrl_c=True, quit_keys=(), **state)`

| Argument | Default | Meaning |
|----------|---------|---------|
| `title` | `""` | Terminal window title (OSC 0). |
| `inline` | `True` | `True` = inline mode (lives in scrollback, Claude-Code style). `False` = fullscreen alt-screen. |
| `mouse` | `False` | Enable mouse event reporting. |
| `fps` | `0` | `0` = event-driven (render only after input). `>0` = continuous render at N fps. A frame handler (`@app.on_frame`) bumps this to 30 automatically. |
| `quit_on_ctrl_c` | `True` | Ctrl-C quits unless you bind it yourself. |
| `quit_keys` | `()` | Keys that auto-quit, e.g. `quit_keys=("q", "esc")` — saves writing the quit handler. |
| `model` | `None` | Use your own object as the state — handlers mutate it and call its methods (instead of the attribute bag). |
| `keys` | `None` | Declarative `{key: fn(state)}` map, an alternative to `@app.on` decorators. |
| `**state` | — | Initial state, folded straight in: `App("counter", n=0)`. |

A model + declarative keys keeps a whole app declarative — state is a normal
class, bindings call its methods:

```python
class Todo:
    items = [("Buy milk", False), ("Ship it", False)]
    cursor = 0
    def move(self, d): self.cursor = (self.cursor + d) % len(self.items)
    def toggle(self):
        t, done = self.items[self.cursor]; self.items[self.cursor] = (t, not done)

app = App("todo", quit_keys=("q", "esc"), model=Todo(), keys={
    "up":    lambda s: s.move(-1),
    "down":  lambda s: s.move(+1),
    "space": lambda s: s.toggle(),
})
```

## State

### Constructor / `app.state(**kw)`

Seed initial state either in the constructor or with `app.state(...)` (both
return the state object). The constructor form is shortest:

```python
app = App("todo", items=["a", "b"], cursor=0)   # state in the constructor
# — or —
app.state(count=0, items=["a", "b"], cursor=0)
```

State is a plain attribute bag. Handlers mutate it directly:

```python
@app.on("down")
def down(s):
    s.cursor = (s.cursor + 1) % len(s.items)
```

### `app.s`

The live state object, if you need it outside a handler (e.g. in tests):

```python
app.s.count          # read
app.s.count = 5      # write
```

## Key bindings

### `@app.on(*keys)`

Decorator that binds one or more keys to a handler `fn(state)`. The handler
receives the state object and returns nothing (mutate `state` in place). If
multiple keys are given, any of them triggers the handler.

```python
@app.on("+", "=")        # either key
def inc(s):
    s.n += 1

@app.on("q", "esc")      # char + named key
def quit_(s):
    app.stop()
```

Only the **first** matching binding fires per event.

### Key names

| Kind | Accepted forms |
|------|----------------|
| Printable char | `"q"`, `"+"`, `"A"`, `" "` (case-sensitive) |
| Named special | `"up"`, `"down"`, `"left"`, `"right"`, `"enter"` (or `"return"`), `"esc"` (or `"escape"`), `"tab"`, `"backtab"`, `"space"`, `"backspace"`, `"delete"`, `"home"`, `"end"`, `"pageup"`, `"pagedown"` |
| Ctrl combo | `"ctrl+c"`, `"ctrl+a"`, … (lowercase letter) |
| Alt combo | `"alt+x"`, … |

Named keys are case-insensitive; single printable chars keep their case so
`"+"`, `"="`, `"A"` all work.

### `@app.on_key`

Decorator for a catch-all handler `fn(state, event)` called for **every** key
event, before the bound handlers. Use it for text input or logging.

```python
@app.on_key
def log(s, ev):
    s.last_event = ev
```

You get the raw `Event` object; match it with the
[event predicates](low-level.md#events) (`key`, `ctrl`, etc.) if needed. The
typed character is available with `maya.event_char(ev)` (returns the printable
character, or `None` for special/modified keys).

### `@app.on_frame`

Decorator for a per-frame tick `fn(state, dt)`, called **before** the view
renders, where `dt` is seconds since the previous frame. Put your animation or
simulation step here so `view(state)` stays a pure function of state. Adding a
frame handler turns on continuous redraw (defaults `fps` to 30 if it was 0).

```python
@app.on_frame
def tick(s, dt):
    s.t += dt
    s.particles = step(s.particles, dt)
```

### `@app.on_paste` / `@app.on_resize`

```python
@app.on_paste
def paste(s, text):        # bracketed paste; a focused text widget also gets it
    s.buffer += text

@app.on_resize
def resize(s, cols, rows): # terminal size changed
    s.cols = cols
```

## Text input & focus

Real maya `Input` widgets, hosted in Python. Create one with `text_input()`
(or `textarea()`), register it with `app.focus(...)` so it receives keystrokes,
read `.value`, and drop it straight into a view — it renders itself (box +
cursor).

```python
from maya_py import App, text_input, col

app = App("search")
query = text_input("type to filter…")
app.focus(query)                 # focused widget gets keys; Tab cycles fields

@query.on_submit                 # Enter
def go(text): app.s.results = search(text)

@app.view
def view(s):
    return col(query, results_list(s))   # query.value is the live text
```

| Call | Meaning |
|------|---------|
| `text_input(placeholder="", *, password=False, multiline=False)` | A single-line field (or password / multiline). |
| `textarea(placeholder="")` | Multi-line input (Enter = newline, Ctrl/Shift-Enter = submit). |
| `app.focus(*widgets)` | Register interactive widgets; the focused one gets keys, **Tab** / **Shift-Tab** cycle. Keys a widget ignores fall through to your `@app.on` bindings. |
| `inp.value` | Read/write the text. |
| `inp.clear()` | Empty it. |
| `inp.on_submit(fn)` / `inp.on_change(fn)` | Callbacks `fn(text)` on Enter / every edit. |

These are the same `Input` widgets maya uses in C++ — their cursor/editing
state lives on the C++ side; only `value` / `handle` / the rendered element
cross into Python. See [`examples/login.py`](../examples/login.py).

## Mouse

Decorate mouse handlers — registering any of them auto-enables mouse reporting
(no `mouse=True` needed). Coordinates are 1-based screen cells.

```python
@app.on_click("left")          # "left" / "right" / "middle" / "any"
def click(s, col, row):
    s.hits += 1
    s.pos = (col, row)

@app.on_scroll              # wheel
def scroll(s, direction):      # -1 up, +1 down
    s.offset += direction

@app.on_mouse               # every mouse event (press/release/move/scroll)
def any_mouse(s, ev):
    ...
```

Mouse needs a terminal that reports it (xterm, kitty, iTerm2, Windows
Terminal, or tmux with `set -g mouse on`). Low-level predicates
(`mouse_clicked`, `mouse_pos`, `scrolled_up/down`, …) are in the
[low-level docs](low-level.md#events).

## Using widgets in an app

All the [native widgets](widgets.md) are plain functions that return an
`Element`, so they drop straight into a view. Render the widget in the state
your `App` holds, and mutate that state in key handlers — the widget shows the
right appearance every frame:

```python
from maya_py import App, col, gauge, progress, select

app = App("panel", inline=True, fps=10)
app.state(load=0.4, cursor=0)

@app.on("down")
def down(s): s.cursor = (s.cursor + 1) % 3

@app.view
def view(s):
    return col(
        gauge(s.load, "load"),
        progress(s.load, "mem", width=24),
        select(["Build", "Test", "Ship"], cursor=s.cursor),
    )
```

For scrollable content, hold a `scroll_state()` in your state and pair
`viewport()` with a `scrollbar()` — scrolling works with no handler code (see
[Widgets → Scrolling](widgets.md#scrolling)).

### Fixed-width panes (sidebars)

To pin a pane to an exact width inside a `row` (an IDE-style sidebar), use
`basis=N, grow=0, shrink=0` — **not** `width=N`. In a flex row the bare `width`
kwarg gets overridden by a `grow=1` sibling, so the fixed pane collapses; the
`basis` + `shrink=0` triple holds the width across every layout context:

```python
row(
    card(tree(FILES), title="explorer", basis=26, grow=0, shrink=0),  # 26 cols
    card(editor, grow=1, basis=0),                                    # fills rest
    col(outline, problems, basis=30, grow=0, shrink=0),               # 30 cols
    gap=1,
)
```

Keep widget content within the pane's usable width (border + padding eat ~4
cols) — plain `T(...)` rows don't auto-wrap, so stack long lines (e.g. a
diagnostic's badge on one row, its message on the next) rather than letting one
wide row overflow the border. See `examples/ide.py`.

### Full-screen effects with `component`

For a pixel field that **fills and grows with the terminal** (games, sims),
use `component(draw, grow=1)` — the `draw(w, h)` callback receives the real
allocated `(width, height)` each frame. Size your grid from those args and
reallocate only when they change:

```python
from maya_py import App, card, component

app = App("fx", inline=True, fps=30)
app.state(grid=[], pw=0, ph=0)

def field(s):
    def draw(w, h):
        h = max(1, min(h, 60))          # clamp the headless path
        if (w, h * 2) != (s.pw, s.ph):  # resized -> reallocate
            s.pw, s.ph = w, h * 2
            s.grid = [[None] * s.pw for _ in range(s.ph)]
        # ... advance + draw into s.grid ...
        return render(s.grid)
    return component(draw, grow=1)

@app.view
def view(s):
    return card(field(s), pad=0)
```

The `examples/_halfblock.py` helper renders such a grid as half-blocks (two
pixels per cell). See `examples/doom_fire.py`, `life.py`, `fluid.py`, and
`fps.py`.

## The view

### `@app.view`

Registers the render function `fn(state) -> node`. It runs **every frame** and
returns the current UI computed from state. Return a `str`, `T`, or `Element`.

```python
@app.view
def view(s):
    return card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("press q to quit"),
        title="counter",
    )
```

You never return a "new state" or trigger redraws manually — the view is pure
and re-evaluated automatically after each event. (If `fps>0`, it also re-runs
on the frame clock.)

## Lifecycle

### `app.run()`

Starts the event loop. **Blocks** until a handler calls `app.stop()`. Sets up
raw mode, installs the render pipeline, and cleans up the terminal on exit.

### `app.stop()`

Requests a clean exit. Typically called from a quit binding:

```python
@app.on("q", "esc", "ctrl+c")
def quit_(s):
    app.stop()
```

## A complete app: arrow-key menu

```python
from maya_py import App, card, col, row, T, b, dim_text, c

app = App("todo", inline=True)
app.state(
    items=["Buy milk", "Write code", "Ship it"],
    done=[False, True, False],
    cursor=0,
)


@app.on("up")
def up(s):
    s.cursor = (s.cursor - 1) % len(s.items)


@app.on("down")
def down(s):
    s.cursor = (s.cursor + 1) % len(s.items)


@app.on("space", "enter")
def toggle(s):
    s.done[s.cursor] = not s.done[s.cursor]


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    rows = []
    for idx, (text, done) in enumerate(zip(s.items, s.done)):
        mark = c("[x]", "green") if done else dim_text("[ ]")
        label = T(text).dim.strike if done else T(text)
        if idx == s.cursor:
            label = T(text).fg("sky").bold
            rows.append(row(c("›", "sky"), mark, label, gap=1))
        else:
            rows.append(row(" ", mark, label, gap=1))
    return card(
        b("Todo").fg("gold"),
        col(*rows),
        dim_text("↑/↓ move   space toggle   q quit"),
        title="todo",
    )


app.run()
```

## Testing apps headlessly

Because the view is pure and bindings are plain functions, you can test
without a terminal:

```python
app = App("t")
app.state(n=0)

@app.on("+")
def inc(s): s.n += 1

@app.view
def v(s): return card(f"n={s.n}")

inc(app.s); inc(app.s)
assert app.s.n == 2
assert "n=2" in maya.to_string(app._render(), 20)   # _render() builds the view
```

## Performance note

In a live app the view runs every frame. If parts of your UI rarely change,
wrap their builders in [`memo`](performance.md#memo) so the hot frame skips
Python tree construction entirely.

## Next

- [Rendering](rendering.md) — `animate` and the lower-level `live`/`run`.
- [Performance](performance.md) — `memo` and fast-frame patterns.
