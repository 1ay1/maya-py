# Getting Started

[← Manual index](index.md)

This is a hands-on tour. By the end you'll have installed maya-py, rendered a
styled static UI, run your first interactive `App`, and built a small live
to-do app from scratch — explaining each new idea exactly when it shows up.

If you'd rather understand *why* maya works the way it does before you type
anything, read **[How It Works](concepts.md)** first. It's the mental model the
rest of the manual (and this page) rests on. Otherwise, come along and we'll
introduce the concepts as we hit them.

---

## 1. Install

maya-py is on PyPI:

```bash
pip install maya-py
```

That's the whole story for most people. maya is a C++26 engine, but you don't
need a compiler: **maya-py ships prebuilt, self-contained binary wheels** (the
native engine is statically linked into the extension), so `pip install` drops
in a ready-to-run package on Linux and macOS. If you want the details — how the
standalone wheels are built and which platforms are covered — see
**[Distribution & Standalone Wheels](distribution.md)**.

Check it imported:

```python
import maya_py
print(maya_py.__version__)   # 0.2.2
```

You write maya UIs with one import line. Everything in this tutorial comes
straight from the top-level package:

```python
from maya_py import card, col, row, T, b, show, App
```

> **Takeaway:** `from maya_py import ...` is the recommended surface. You almost
> never reach below it.

---

## 2. Your first static UI

Before anything interactive, let's just *draw something* once. The two ideas
you need are **elements** and **`show`**.

An **element** is an immutable description of a piece of UI — a box, some text,
a widget. You build a tree of them, then hand it to a renderer. The simplest
renderer is `show(node, width=None)`: it lays the tree out, paints it, and
writes it to your terminal one time.

```python
from maya_py import show, card, b

show(card(b("Hello, maya")))
```

`card(*children, title=None, **opts)` is the everyday container: a bordered,
padded vertical box. `b(s)` makes **bold** text. Run it and you get a rounded
box with bold text inside.

Now the trick that makes maya pleasant — **strings are UI**. Anywhere a child is
expected you can pass a bare `str`, a styled `T`, or a `(text, color)` tuple,
and maya coerces it into an element. So you rarely wrap anything:

```python
from maya_py import show, card, col, row, T, b

show(card(
    b("Account").fg("gold"),
    col(
        row("User:", T("ada").fg("sky"), gap=1),
        row("Plan:", T("Pro").fg("gold"), gap=1),
        row("Tasks:", "7", gap=1),
    ),
    title="profile",
    gap=1,
))
```

What's happening:

- **`col(*children, **opts)`** stacks its children vertically; **`row(*children,
  **opts)`** stacks them horizontally. Both take layout keywords like `gap=`
  (cells between children) — see **[Layout](layout.md)** for the full set.
- **`T(s)`** is a fluent styled-string builder. `T("ada").fg("sky")` sets the
  foreground color; you can chain `.bold`, `.italic`, `.dim`, `.bg(...)`, and
  more. Colors accept friendly names (`"sky"`, `"gold"`, `"red"`), `(r, g, b)`
  tuples, or `"#rrggbb"`. The full palette and styling story is in
  **[Text & Style](text-and-style.md)**.
- The bare strings `"User:"` and `"7"` become plain text leaves automatically.

If you want the rendered frame as a string instead of printing it — handy for
tests or snapshots — use `to_string(node, width=80)`:

```python
from maya_py import to_string, card

frame = to_string(card("snapshot me"), width=40)
assert "snapshot me" in frame
```

> **Takeaway:** A static UI is just *build a tree → `show` it*. `to_string` is
> the same pipeline, returned as text.

---

## 3. Your first interactive App

Static UIs are nice, but a TUI reacts. maya-py's main runtime is the **`App`**
class. The model is small and imperative:

1. **State is a mutable bag.** You seed it, handlers mutate it.
2. **Handlers run on input** and change state.
3. **A view function maps state → an element tree**, and maya re-renders it
   after every handled event.

Here's a complete counter:

```python
from maya_py import App, card, b, dim_text

# State goes straight in the constructor as keyword args. quit_keys auto-binds
# q and Esc to quit, so you don't hand-write a quit handler.
app = App("counter", n=0, quit_keys=("q", "esc"))

@app.on("+", "=")
def inc(s):
    s.n += 1

@app.on("-")
def dec(s):
    s.n -= 1

@app.on("r")
def reset(s):
    s.n = 0

@app.view
def view(s):
    return card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("+/- change   r reset   q quit"),
        title="counter",
    )

app.run()
```

Save it as `counter.py`, run `python counter.py`, and press `+`, `-`, `r`, `q`.

Walk through the new pieces:

- **`App(title="", *, inline=True, mouse=False, fps=0, quit_on_ctrl_c=True,
  quit_keys=(), model=None, keys=None, **state)`** — the constructor. Any extra
  keyword (`n=0`) seeds the state bag, reachable as `app.s` and passed to every
  handler as `s`. `quit_keys=("q", "esc")` binds those keys to quit for free.
- **`@app.on(*keys)`** — bind one or more keys to a handler `fn(state)`. Keys are
  characters (`"+"`, `"="`, `"r"`) or names (`"up"`, `"enter"`, `"esc"`,
  `"space"`, `"ctrl+c"`, ...). The handler mutates state in place.
- **`@app.view`** — register the view: a pure function `state -> node`. You
  never return a new view from a handler; the view is simply re-evaluated.
- **`app.run()`** — start the event loop (blocks until quit). There's also
  `app.stop()` to request exit from inside a handler.

By default `App(inline=True)` renders **in place** in your scrollback — like a
rich prompt — instead of taking over the whole screen, and `fps=0` means
**"redraw only when something changes"**. No input, no work. The full set of
`App` members and behaviors lives in **[Apps](apps.md)**.

> **Takeaway:** `App` = a state bag + key handlers that mutate it + a `view(s)`
> that re-renders from it. That's the 90% path for interactive apps.

---

## 4. Building a real app: a live to-do list

Let's build something with moving parts: a to-do list you navigate with the
arrow keys and toggle with space. We'll add concepts one at a time.

### 4a. State as an object

For anything beyond a counter, a plain object with methods reads better than a
flat bag. `App` supports this directly: pass `model=` and that object *becomes*
the state — handlers receive it as `s` and call its methods.

```python
class Todo:
    def __init__(self):
        self.items = [("Buy milk", False), ("Write docs", True),
                      ("Ship it", False)]
        self.cursor = 0

    def move(self, d):
        self.cursor = (self.cursor + d) % len(self.items)

    def toggle(self):
        text, done = self.items[self.cursor]
        self.items[self.cursor] = (text, not done)
```

### 4b. Declarative key bindings

Instead of a decorator per key, you can hand `App` a `keys={...}` map — a
key-name → `fn(state)` dict. It's the same binding mechanism as `@app.on`, just
written inline, which pairs naturally with a model whose methods *are* the
actions:

```python
from maya_py import App

app = App(
    "todo", quit_keys=("q", "esc"), model=Todo(),
    keys={
        "up":    lambda s: s.move(-1),
        "down":  lambda s: s.move(+1),
        "space": lambda s: s.toggle(),
        "enter": lambda s: s.toggle(),
    },
)
```

### 4c. The view, with conditional styling

Now the view. Two new ideas:

- **`(text, color)` tuple cells.** Inside `row`/`col` you can pass a
  `(text, fg)` (or `(text, fg, bg)`) tuple instead of a `T`. It's the leanest
  way to emit a styled cell — no intermediate object.
- **Conditional style on `T`.** `.fg(c)` treats `None` as a no-op, so
  `T(x).fg("sky" if focused else None)` reads cleanly. And `.opt(bold=...,
  dim=..., strike=..., ...)` applies attributes only where the flag is truthy —
  perfect for "dim and strike through done items."

```python
from maya_py import card, col, row, T

@app.view
def view(s):
    rows = []
    for i, (text, done) in enumerate(s.items):
        focused = (i == s.cursor)
        rows.append(row(
            T("›" if focused else " ").fg("sky"),
            T("[x]" if done else "[ ]").fg("green" if done else "slate"),
            T(text).fg("sky" if focused else None).opt(dim=done, strike=done),
            gap=1,
        ))
    return card(
        T("Todo").bold.fg("gold"),
        col(*rows),
        T("↑/↓ move · space toggle · q quit").dim,
        title="todo",
        gap=1,
    )

app.run()
```

That's a complete, working app. Navigate with ↑/↓, toggle with space, quit with
`q`. The view is one declarative expression: no cursor moves, no screen clears —
you describe what the screen should look like *now*, and maya computes the
minimal update.

### 4d. Make redraws cheap with `memo`

Our view rebuilds every row on every keypress. For three items that's nothing,
but the habit that separates a snappy maya app from a sluggish one is **don't
rebuild what didn't change.** That's what **`memo`** is for.

`@memo` caches a built sub-tree keyed by its positional arguments. If the args
are identical to last frame, it returns the *same* element object — zero Python
work — and maya's diff sees an unchanged subtree. The rule: pass small
*comparable* values, never the whole mutable state.

```python
from maya_py import memo, row, T

@memo
def todo_row(text, done, focused):
    return row(
        T("›" if focused else " ").fg("sky"),
        T("[x]" if done else "[ ]").fg("green" if done else "slate"),
        T(text).fg("sky" if focused else None).opt(dim=done, strike=done),
        gap=1,
    )
```

Then the view body becomes:

```python
col(*[todo_row(text, done, i == s.cursor)
      for i, (text, done) in enumerate(s.items)])
```

Now when you move the cursor, only the two rows whose `focused` argument changed
get rebuilt; the rest are served from cache. This single technique is the
biggest lever for a live app — read the full performance model in
**[Performance](performance.md)** and §7 of [concepts](concepts.md).

The finished version of this app is in the repo:
[examples/todo.py](https://github.com/1ay1/maya-py/blob/master/examples/todo.py).

> **Takeaway:** Build the view as a pure function of state; reach for `memo` on
> the stable sub-trees, passing comparable summaries (not the state object).

---

## 5. Going live: animation and widgets

So far we redraw only on input. Some UIs need to redraw *continuously* — clocks,
spinners, dashboards. maya-py gives you a per-frame hook: **`@app.on_frame`**.

`@app.on_frame` registers `fn(state, dt)`, called once per frame *before* the
view renders, where `dt` is seconds since the last frame. Registering one turns
on continuous redraw (if `fps` was left at 0, it defaults to 30). Put your
"clock advances / simulation steps" logic here so the view stays a pure function
of state.

Here's a mini dashboard that animates a request sparkline. It also introduces
**widgets** — native renderers you drop straight into a layout. We'll use three:

- **`gauge(value, label="", *, color=None, style="arc")`** — a meter from 0..1.
- **`progress(value, label="", *, ...)`** — a progress bar from 0..1.
- **`sparkline(data, *, label="", color=None, show_last=False, ...)`** — an
  inline mini bar chart from a sequence of numbers.

```python
import math
from maya_py import App, card, col, row, divider, gauge, progress, sparkline

app = App("dashboard", t=0.0, history=[0.5] * 24)

@app.on_frame
def tick(s, dt):
    s.t += dt
    # push a new fake "req/s" sample, keep the last 24
    sample = 0.5 + 0.45 * math.sin(s.t * 2.0)
    s.history = (s.history + [sample])[-24:]

@app.on("q", "esc")
def quit(s):
    app.stop()

@app.view
def view(s):
    load = s.history[-1]
    return card(
        row("System Status", gap=1),
        divider("metrics"),
        sparkline(s.history, label="req/s", show_last=True),
        gauge(load, "load"),
        progress(load, "cpu"),
        col(("q quit", "slate")),
        title="dashboard",
        gap=1,
    )

app.run()
```

Run it and watch the sparkline, gauge, and bar breathe in real time. Note that
`("q quit", "slate")` is a tuple cell — a styled string with no `T` allocation.

maya ships a large catalog of these native widgets — tables, charts, trees,
calendars, toasts, key-help panels, and more. Browse them in
**[Widgets](widgets.md)**. A worked dashboard example is at
[examples/dashboard.py](https://github.com/1ay1/maya-py/blob/master/examples/dashboard.py),
and a live clock is at
[examples/clock.py](https://github.com/1ay1/maya-py/blob/master/examples/clock.py).

> **Takeaway:** `@app.on_frame` is how you get continuous motion; leave `fps=0`
> for everything else so a static UI costs nothing.

---

## 6. Hosting a real input field

One more building block you'll want: a real text field. **`text_input(placeholder="",
*, password=False, multiline=False)`** returns an interactive widget (cursor,
UTF-8 editing, history, masking). To make it receive keystrokes, register it
with **`app.focus(*widgets)`** — the focused widget gets keys first, and Tab
cycles between several. Read `.value` in your view.

```python
from maya_py import App, card, col, text_input

name = text_input("type your name…")

app = App("hello", quit_keys=("esc",))
app.focus(name)               # this field now receives keystrokes

@app.view
def view(s):
    greeting = f"Hello, {name.value}!" if name.value else "(waiting…)"
    return card(
        col("Name:", name, greeting, gap=1),
        title="input",
    )

app.run()
```

Type and watch the greeting update; press Esc to quit. (`textarea(placeholder="")`
is the multi-line variant.) The focus model — how keys route to widgets vs your
`@app.on` bindings — is covered in **[Apps](apps.md)**.

> **Takeaway:** Interactive widgets are objects you register with `app.focus`;
> the run loop routes keys to the focused one automatically.

---

## 7. The other runtime: `Program` (MVU)

`App` is imperative and covers almost everything. maya-py also offers a second
runtime, **`Program`**, which follows the Elm Architecture (Model-View-Update):
state is *immutable*, `update(model, msg)` is a *pure* function returning a new
model plus a `Cmd` (effects you return as data rather than perform inline), and
inputs arrive through `Sub`scriptions. The two runtimes compile to the same
render pipeline; you pick one per program.

Reach for `Program` when you want testable update logic (assert on
`update(model, msg)` with no terminal) or explicit, data-described effects and
concurrency. The full treatment — `Cmd`, `Sub`, `run_program` — is in
**[Program (MVU)](program.md)**, and the tradeoff is summarized in §4 of
[concepts](concepts.md). A side-by-side counter lives at
[examples/counter_program.py](https://github.com/1ay1/maya-py/blob/master/examples/counter_program.py).

---

## 8. Where to go next

You can now build a real interactive terminal app. To go deeper:

- **[How It Works](concepts.md)** — the mental model: the render pipeline, why
  build cost (not render) is the floor, and the performance levers.
- **[Text & Style](text-and-style.md)** — `T`, the color palette, markup
  helpers (`b`/`i`/`u`/`dim_text`/`c`), tuple cells.
- **[Layout](layout.md)** — `row`/`col`/`card`/`center`/`stack`/`grow`, gaps,
  borders, sizing with `pct`/`cells`/`auto`.
- **[Apps](apps.md)** — the complete `App` surface: every handler, focus, mouse,
  paste, resize, and inline vs alternate-screen.
- **[Widgets](widgets.md)** — the full native widget catalog.
- **[Program (MVU)](program.md)** — the immutable runtime, `Cmd`, and `Sub`.
- **[Performance](performance.md)** — benchmarks and the techniques behind
  `memo` and tuple cells.
- **[Distribution & Standalone Wheels](distribution.md)** — shipping your app.

And the [examples directory](https://github.com/1ay1/maya-py/blob/master/examples/counter.py)
is full of runnable programs — counters, a to-do, dashboards, clocks, games —
that show every API in context.
