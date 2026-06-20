# Apps

[← Manual index](index.md)

`App` is the high-level, imperative way to build an interactive terminal
program in maya-py. It owns the event loop, your state, and the render
schedule; you just declare *what's in state*, *how keys change it*, and *what
the screen looks like*. This is the 90% path — reach for the Elm-style
[`Program` (MVU)](program.md) only when you need pure, testable update logic
or explicitly-managed effects.

Before reading on, internalise the mental model in
[concepts.md §4](concepts.md#4-two-runtimes-app-and-program) (the two runtimes),
[§5](concepts.md#5-the-frame-lifecycle) (the frame lifecycle) and
[§6](concepts.md#6-the-event--input-model) (the event & input model). This page
is the depth-first tour of everything those sections summarise.

---

## 1. The state → view loop

An `App` is built on one idea (see
[concepts.md §1](concepts.md#1-the-one-sentence-model)):

> **State is a mutable bag. Handlers mutate it. The view is a pure function
> from that state to an element tree, re-evaluated after every handled event.**

You never imperatively touch the screen. You don't "redraw line 3" or "clear
the field." You mutate state, and maya re-runs your `view(state)`, lays it out,
paints it, diffs it against the previous frame, and writes only the changed
cells.

```python
from maya_py import App, card, b

app = App("counter", n=0, quit_keys=("q", "esc"))   # 1. construct + seed state

@app.on("+", "=")                                    # 2. bind keys → mutate state
def inc(s):
    s.n += 1

@app.view                                            # 3. state → element tree
def view(s):
    return card(b(f"Count: {s.n}"))

app.run()                                            # 4. block until stop()
```

Every runnable snippet on this page imports only from `maya_py`.

### The frame lifecycle, concretely

When you press a key (full detail in
[concepts.md §5](concepts.md#5-the-frame-lifecycle)):

1. **Input** is decoded into an `Event`.
2. The runtime **routes** it (in this exact order — see §6 below): Ctrl-C
   guard → mouse handlers → paste → resize → focused widget → `@app.on_key`
   catch-alls → the first matching `@app.on(...)` binding.
3. `@app.on_frame` handlers (if any) run, then your **view** is called for a
   fresh tree.
4. The tree is **laid out, painted, diffed**, and the changed cells are
   written.
5. The loop **waits** — for the next input, or, if a frame rate is set, until
   the next frame deadline.

> Handlers return nothing meaningful. You don't return a new view — the view is
> re-evaluated from state every frame, so just mutate `s` and let the loop do
> the rest.

---

## 2. Construction

```python
App(title="", *, inline=True, mouse=False, fps=0,
    quit_on_ctrl_c=True, quit_keys=(), model=None, keys=None, **state)
```

| Argument | Default | Meaning |
|----------|---------|---------|
| `title` | `""` | Terminal/window title while running. |
| `inline` | `True` | Render in place in scrollback vs. take over the alternate screen. |
| `mouse` | `False` | Enable mouse reporting. Auto-enabled if you register any mouse handler. |
| `fps` | `0` | `0` = redraw only on change; `>0` = continuous redraw at that rate. |
| `quit_on_ctrl_c` | `True` | Ctrl-C always quits, even from a frozen handler — unless you bind `ctrl+c` yourself, or set this `False`. |
| `quit_keys` | `()` | Keys auto-bound to `stop()` (e.g. `("q", "esc")`). |
| `model` | `None` | Use your own object as state instead of the attribute bag. |
| `keys` | `None` | Declarative `{key: fn(state)}` map, an alternative to `@app.on`. |
| `**state` | — | Seed the attribute bag: `App("c", n=0, name="x")`. Ignored when `model=` is given. |

### The three state styles

You pick exactly one of these per app. They're mutually exclusive in practice:
`**state` kwargs are *ignored* when you pass a `model`.

**(a) kwargs — the attribute bag.** Fast to write. Each kwarg becomes an
attribute on `app.s`:

```python
app = App("counter", n=0, name="world")

@app.on("+")
def inc(s):
    s.n += 1          # s is the bag; attributes are your kwargs
```

**(b) `model=` — your own object.** State *is* an instance of your class;
handlers mutate it and call its methods. This keeps logic with data and is the
cleanest style for anything non-trivial:

```python
class Counter:
    def __init__(self):
        self.n = 0
    def bump(self, d):
        self.n += d

app = App("counter", model=Counter())

@app.on("+")
def inc(s):
    s.bump(+1)        # s is your Counter instance
```

**(c) `keys=` — declarative bindings.** A `{key_name: fn(state)}` map, evaluated
at construction. Pairs beautifully with `model=` so the whole app is data:

```python
app = App(
    "counter", model=Counter(),
    keys={
        "+": lambda s: s.bump(+1),
        "-": lambda s: s.bump(-1),
    },
)
```

`keys=` and `@app.on` can coexist; both append to the same binding list.

### `inline` vs. alternate screen

`inline=True` (the default) renders *in place* in your scrollback, like a rich
prompt — output above the app is preserved, and the app cleans up to a few
stable rows on exit. This is what makes maya feel native in a normal shell
session. `inline=False` takes over the whole terminal (alternate screen),
which suits full-screen dashboards and games. See
[concepts.md §5](concepts.md#5-the-frame-lifecycle).

Two classmethod constructors read as intent instead of a boolean flag:

```python
app = App.inline("counter", fps=30)          # == App("counter", inline=True, fps=30)
app = App.fullscreen("boids", mouse=True)    # == App("boids", inline=False, mouse=True)
```

**Fullscreen pixel canvas.** A fullscreen half-block app used to hand-roll a
`shutil.get_terminal_size()` fallback, because a `grow=1` component under the
alternate screen receives an *unbounded* height sentinel, not the real cell
height. `fullscreen_pixels(draw)` does that for you — it hands `draw(field,
pw, ph)` a `PixelField` already sized to the visible terminal (2 pixels tall
per cell) and renders it as half-blocks:

```python
from maya_py import App, fullscreen_pixels, hsv, wrap

app = App.fullscreen("plasma", fps=30, t=0.0)

@app.on_frame
def tick(s, dt): s.t += dt

@app.view
def view(s):
    def draw(f, pw, ph):
        for y in range(ph):
            for x in range(pw):
                f.set(x, y, hsv(wrap(x / pw + s.t * 0.1, 1.0)))
    return fullscreen_pixels(draw, bg=(4, 4, 10))
```

Need raw cell dimensions yourself? `term_size() -> (cols, rows)`,
`term_cols()`, `term_rows()` wrap the size lookup with a sane fallback.

### `fps=0` vs. `fps>0`

- **`fps=0` (default): event-driven.** The loop sleeps until input arrives,
  then redraws. Zero CPU when idle. Correct for almost every UI.
- **`fps>0`: continuous redraw** at that rate — for clocks, spinners, games,
  progress bars. Registering an `@app.on_frame` handler automatically bumps a
  `0` fps up to `30`. Don't set `fps>0` for a static UI; it burns CPU
  re-rendering identical frames.

### Quit handling

- `quit_on_ctrl_c=True` (default) — Ctrl-C arrives as a key event (raw mode
  disables tty signals) and always stops the app, so a frozen handler can still
  be killed. Binding `ctrl+c` yourself (`@app.on("ctrl+c")`) takes over and
  disables this guard.
- `quit_keys=("q", "esc")` — auto-binds those keys to `stop()`, so you don't
  hand-write a quit handler in every app.

---

## 3. State access

```python
app.state(**kw) -> state    # seed/update fields; returns the state object
app.s                       # the live state object (read/write)
```

`app.state(n=0)` is the imperative twin of the `n=0` constructor kwarg — useful
when you want to construct the app, attach handlers, then seed state:

```python
app = App("counter")
app.state(n=0, history=[])
app.s.n += 1                 # direct mutation works anywhere you hold `app`
```

When you pass `model=`, `app.s` *is* your object and `app.state(**kw)` writes
attributes onto it (so prefer constructing your model with its own fields).

---

## 4. Handlers

All handlers are registered with decorators on the `app`. The complete set is
exactly: `on`, `on_key`, `on_frame`, `on_paste`, `on_resize`, `on_click`,
`on_scroll`, `on_mouse`.

### `@app.on(*keys)` — `fn(state)`

Bind one or more key *names* (see §5) to a handler that receives state. The
**first** matching binding for an event runs, then routing stops:

```python
@app.on("+", "=")           # several keys → one handler
def inc(s):
    s.n += 1

@app.on("r")
def reset(s):
    s.n = 0
```

### `@app.on_key` — `fn(state, event)` (catch-all)

Runs for **every** key event, before the `@app.on` bindings, and receives the
raw `Event`. Use the low-level predicates to inspect it
(`key`, `key_special`, `ctrl`, `alt`, `event_char`, `any_key` — see
[low-level.md](low-level.md)). Multiple `on_key` handlers all run.

```python
from maya_py import App, event_char, card

app = App("typer", buf="")

@app.on_key
def feed(s, ev):
    ch = event_char(ev)     # the typed character, or None
    if ch is not None:
        s.buf += ch

@app.view
def view(s):
    return card(s.buf or "(type something)")
```

### `@app.on_frame` — `fn(state, dt)` (animation)

Called once per frame **before** the view renders, with `dt` = seconds since
the previous frame. Put your simulation/animation step here so `view(state)`
stays a pure function of state. Registering a frame handler turns on continuous
redraw: if `fps` was `0`, it becomes `30`.

```python
from maya_py import App, card, b

app = App("clock", t=0.0)

@app.on_frame
def tick(s, dt):
    s.t += dt

@app.view
def view(s):
    return card(b(f"{s.t:5.1f}s elapsed"))

app.run()
```

### `@app.on_paste` — `fn(state, text)`

Bracketed-paste text arrives in **one shot** — never reconstruct it
keystroke-by-keystroke. If a focused text widget exists it also receives the
paste automatically.

```python
@app.on_paste
def on_paste(s, text):
    s.buf += text
```

### `@app.on_resize` — `fn(state, cols, rows)`

Fires on terminal resize with the new dimensions.

```python
@app.on_resize
def on_resize(s, cols, rows):
    s.size = (cols, rows)
```

### Mouse handlers (need `mouse=True`)

Registering **any** of these auto-sets `mouse=True`, so you don't strictly have
to pass it — but being explicit is fine.

| Decorator | Signature | Fires on |
|-----------|-----------|----------|
| `@app.on_click(button="left")` | `fn(state, col, row)` | a button *press*; `button` is `"left"`/`"right"`/`"middle"`/`"any"`. `col`/`row` are 1-based. |
| `@app.on_scroll` | `fn(state, direction)` | wheel; `direction` is `-1` (up) or `+1` (down). |
| `@app.on_mouse` | `fn(state, event)` | **every** mouse event (press, release, move, scroll); inspect with `mouse_*` predicates. |

```python
from maya_py import App, card

app = App("pointer", last=None)

@app.on_click("left")
def click(s, col, row):
    s.last = (col, row)

@app.on_scroll
def scroll(s, direction):
    s.last = f"scroll {direction:+d}"

@app.view
def view(s):
    return card(f"last: {s.last}")

app.run()
```

`@app.on_click` is a decorator *factory* (note the call: `@app.on_click("left")`
or `@app.on_click()`), whereas `@app.on_scroll` / `@app.on_mouse` are bare
decorators.

#### Coordinates are frame-relative — even inline

`mouse_pos(ev)` and the `col`/`row` passed to `on_click` are **relative to your
UI's top-left**, not the terminal's. In `inline=True` mode your app is drawn
partway down the terminal, but maya translates the raw (absolute) mouse position
into frame-relative coordinates for you (it learns the frame's top row via a
one-time cursor-position query at startup). So a click on the first cell of your
view reports `(1, 1)` whether the app is at the top of the screen or 20 rows
down — exactly like fullscreen mode.

Clicks and scrolls that land **outside** your frame (in the surrounding
scrollback) are dropped — your handlers only fire for events on the rendered UI.

#### Mouse capture vs. native terminal scroll: `set_mouse()`

There's one unavoidable trade-off: **while mouse reporting is on, the terminal
hands the scroll wheel to your app instead of scrolling its own scrollback.**
That's how terminal mouse protocols work (the wheel is reported as a mouse
button) — it's not specific to maya, and it can't be worked around while capture
is on. So in inline mode, an app with mouse enabled means the user can't scroll
the terminal's history until the app exits (capture is always released on exit).

When that matters, toggle capture at runtime:

| Member | Role |
|--------|------|
| `app.set_mouse(on)` | Turn mouse capture on/off **while running** (call from a handler). Off → the wheel goes back to the terminal (native scrollback works); on → clicks/drag/wheel are captured again. |
| `app.mouse_active` | `bool` — the current capture state. |

```python
from maya_py import App, card, col, b

app = App("toggle", mouse=True, quit_keys=("q",))

@app.on("m")
def toggle(s):
    app.set_mouse(not app.mouse_active)   # flip between clicks and terminal scroll

@app.view
def view(s):
    state = "ON (clicks)" if app.mouse_active else "OFF (terminal scroll)"
    return col(b(f"mouse: {state}"), card("m = toggle · q = quit"))

app.run()
```

If your app simply doesn't need the mouse, **don't enable it** (the default is
`mouse=False`) and native terminal scroll just works. `set_mouse()` is the
runtime escape hatch for apps that want both, on demand. Full example:
[examples/mouse.py](https://github.com/1ay1/maya-py/blob/master/examples/mouse.py).

---

## 5. Key name syntax

`@app.on(...)`, `quit_keys=`, and `keys=` all use the same key-name vocabulary:

- **Characters** — the literal char, case-sensitive enough that `"+"`, `"="`,
  `"G"`, `"g"` all work: `@app.on("q", "+", "G")`.
- **Special keys** (case-insensitive names):
  `"up"`, `"down"`, `"left"`, `"right"`, `"enter"` (alias `"return"`),
  `"esc"` (alias `"escape"`), `"tab"`, `"backtab"`, `"space"`,
  `"backspace"`, `"delete"`, `"home"`, `"end"`, `"pageup"`, `"pagedown"`.
- **Combos** — `"ctrl+<char>"` and `"alt+<char>"`, e.g. `"ctrl+s"`, `"alt+x"`.
  (These match a single modifier + single character.)

```python
@app.on("up", "k")            def up(s):    s.cursor -= 1
@app.on("down", "j")          def down(s):  s.cursor += 1
@app.on("space", "enter")     def go(s):    s.toggle()
@app.on("ctrl+s")             def save(s):  s.save()
@app.on("pageup")             def pg(s):    s.cursor -= 10
```

For anything the name vocabulary can't express, drop to `@app.on_key` and the
low-level predicates ([low-level.md](low-level.md)).

---

## 6. Event routing order

When an event arrives, `App` routes it in this fixed order — understanding it
explains why, e.g., a focused text field "eats" your `j`/`k` bindings:

1. **Ctrl-C guard** — if `quit_on_ctrl_c` and you didn't bind `ctrl+c`, stop.
2. **Mouse events** → `on_mouse`, then `on_scroll` *or* `on_click`. Mouse
   events never reach key bindings.
3. **Paste** → focused widget (if any), then `on_paste` handlers.
4. **Resize** → `on_resize` handlers.
5. **Focused widget** (if `app.focus(...)` was called) — Tab/Shift-Tab cycle
   focus; the focused widget consumes the key first. Keys it *doesn't* consume
   fall through to:
6. **`@app.on_key`** catch-alls (all of them run), then
7. The **first matching `@app.on(...)`** binding (then routing stops).

[Scroll states](#9-automatic-scrolling) get their refusal *inside* the run loop
before your handlers — see [concepts.md §6](concepts.md#6-the-event--input-model).

---

## 7. Hosting interactive widgets: `text_input` & `textarea`

maya hosts *real* interactive input widgets in Python — cursor movement, UTF-8
editing, history, password masking — that you drop straight into a view.

```python
text_input(placeholder="", *, password=False, multiline=False)
textarea(placeholder="")     # == text_input(placeholder, multiline=True)
```

Both return a widget object with this surface:

| Member | Meaning |
|--------|---------|
| `.value` | the current text (read **and** write: `w.value = "x"`). |
| `.clear()` | empty the field. |
| `.on_submit(fn)` | register `fn(text)` for Enter (single-line) / Ctrl/Shift-Enter (multiline). Returns `fn`, so it works as a decorator. |
| `.on_change(fn)` | register `fn(text)` called on every edit. Returns `fn`. |

To make a widget *receive keystrokes*, register it with `app.focus(...)`:

```python
app.focus(*widgets) -> first_widget
```

The first widget is focused initially; **Tab** / **Shift-Tab** cycle focus
among them; the focused widget consumes keys it understands and lets the rest
fall through to your `@app.on` bindings. Place the widget directly in the view
(it coerces into the tree automatically) and read `.value`:

```python
from maya_py import App, text_input, col

app = App("name")
name = text_input("your name…")
app.focus(name)

@app.view
def view(s):
    return col("Name:", name, f"hello {name.value}")

app.run()
```

`on_submit` / `on_change` are commonly used as decorators:

```python
pw = text_input("password", password=True)
app.focus(user, pw)

@pw.on_submit
def submit(text):
    app.s.submitted = user.value
```

`textarea("notes…")` is the multi-line variant: Enter inserts a newline,
Ctrl/Shift-Enter submits.

---

## 8. The view, run, and stop

```python
@app.view             # register fn(state) -> node  (str / T / Element / widget)
def view(s): ...

app.run()             # start the loop; blocks until stop() / Ctrl-C
app.stop()            # request exit (call from any handler)
```

- `@app.view` registers the one view function. Its return value is coerced to
  an element — a bare string, a `T(...)`, a layout container, or an input
  widget all work as the root.
- `app.run()` blocks. It can't be nested (calling it re-entrantly raises).
- `app.stop()` sets a flag the loop checks each cycle; the app exits cleanly
  after the current frame. `quit_keys` is sugar for `@app.on(...key): app.stop()`.

---

## 9. Automatic scrolling

This is a maya superpower (full detail in
[concepts.md §6](concepts.md#6-the-event--input-model) and
[widgets.md](widgets.md)): a `scroll_state()` placed inside a `viewport(...)`
and/or `scrollbar(...)` **auto-dispatches** — the run loop forwards arrows,
PgUp/PgDn, Home/End and (with `mouse=True`) the wheel and scrollbar drag to
every on-screen scroll state **with no handler code of yours**.

```python
from maya_py import App, card, col, row, viewport, scrollbar, scroll_state

LINES = [f"line {i:03d}" for i in range(200)]

app = App("log", mouse=True)
s = scroll_state()                 # auto-dispatch is on
app.state(s=s, vh=14)

CONTENT = col(*LINES)              # built once

@app.view
def view(st):
    # viewport + scrollbar sit side by side, so wrap them in a `row`.
    # `card` is a column — putting them straight into it stacks the
    # scrollbar *below* the content instead of beside it.
    return card(
        row(
            viewport(CONTENT, st.s, height=st.vh, grow=1),
            scrollbar(st.s, st.vh, thumb_color="sky"),
        ),
        title="log",
    )

app.run()
```

No `@app.on("up")`, no wheel handler — navigation comes for free. You only call
`scroll_handle(state, ev)` manually if you're driving the low-level
[`run`](rendering.md) loop yourself. The `ScrollState` exposes helpers like
`scroll_to_top()`, `scroll_to_bottom()`, `.y`, `.max_y` for your own keys
(e.g. binding `g`/`G` to jump). Full scrolling example:
[scroll.py](https://github.com/1ay1/maya-py/blob/master/examples/scroll.py).

---

## 10. Conditional styling: `T.opt(**flags)`

When a view styles by state, branching with `if` gets noisy. The `T` builder's
`.opt(...)` applies attributes **conditionally** — only truthy flags take
effect — and `.fg(None)` is a no-op, so a dynamic label reads as one chain:

```python
T.opt(*, bold=False, dim=False, italic=False,
      underline=False, strike=False, inverse=False) -> T
```

```python
from maya_py import T

# a todo line: highlight when focused, dim+strike when done
T(text).fg("sky" if focused else None).opt(dim=done, strike=done)
```

Pair it with [`when(cond, then, else_)`](text-and-style.md) for conditional
*content*. Together they keep state-driven views declarative instead of
imperative `if` ladders.

---

## 11. Performance in a live app

The view is re-run every frame, so building the tree in Python is the cost
floor (see [concepts.md §7](concepts.md#7-the-performance-model-this-is-what-separates-experts)).
Two reflexes:

- **`memo`** stable sub-trees, keyed by small comparable summaries — never the
  whole state object: `header(s.title, len(s.items))`, not `header(s)`.
- **Tuple cells** (`(text, fg)`) instead of `T` in hot per-frame loops.

And don't render to a string and print it in a loop — that throws away maya's
diff.

---

## 12. A complete worked app: focused login form

This ties together `model=`, `app.focus`, `text_input` (incl. `password=`),
`on_submit` as a decorator, conditional styling, and `quit_keys`. Runnable as-is.

```python
from maya_py import App, text_input, card, col, row, b, dim_text, T

app = App("login", submitted=None, quit_keys=("esc",))

user = text_input("username")
pw = text_input("password", password=True)
app.focus(user, pw)                      # user focused first; Tab → pw

@pw.on_submit                            # Enter in the password field submits
def submit(_text):
    app.s.submitted = user.value

@app.view
def view(s):
    if s.submitted is not None:
        return card(b(f"Welcome, {s.submitted}!").fg("green"), title="login")
    return card(
        col(
            row(T("user ").fg("slate"), user),
            row(T("pass ").fg("slate"), pw),
            dim_text("Tab to switch · Enter to submit · Esc to quit"),
            gap=1,
        ),
        title="login",
    )

app.run()
```

What's happening:

- **State** is the attribute bag with one field, `submitted`. `quit_keys=("esc",)`
  auto-binds Esc to `stop()`.
- **Two widgets** are registered with `app.focus`; Tab cycles between them. The
  focused field gets every key first, so there are no `@app.on` bindings to
  conflict with typing.
- **`@pw.on_submit`** wires Enter-in-password to copy the username into state.
- **The view** branches on `s.submitted`: the same pure function renders either
  the form or the welcome card. The widgets coerce into the tree directly; their
  live `.value` is read implicitly by maya as it builds them.

For a `model=` + declarative `keys=` + `memo` + `.opt` example, see the todo
app: [todo.py](https://github.com/1ay1/maya-py/blob/master/examples/todo.py).
More: [counter.py](https://github.com/1ay1/maya-py/blob/master/examples/counter.py),
[login.py](https://github.com/1ay1/maya-py/blob/master/examples/login.py),
[scroll.py](https://github.com/1ay1/maya-py/blob/master/examples/scroll.py).

---

## Testing apps headlessly (`app.test()` → `Pilot`)

You can drive an app with no terminal at all. `app.test()` returns a **`Pilot`**
that feeds synthetic events through the *same* handler + view path the live
loop uses, and renders frames to a plain string you can assert on. No PTY, no
threads, fully deterministic — ideal for unit tests and CI.

```python
from maya_py import App, card, b

def build():
    app = App("counter", n=0, quit_keys=("q",))
    app.on("+")(lambda s: setattr(s, "n", s.n + 1))
    app.view(lambda s: card(b(f"Count: {s.n}"), title="counter"))
    return app

def test_counter():
    app = build()
    p = app.test(width=40)
    p.press("+", "+", "+")          # three increments
    assert app.s.n == 3
    assert "Count: 3" in p.render() # the actual rendered frame
    p.press("q")
    assert not p.running            # quit key took effect
```

The `Pilot` surface mirrors everything a real user can do — each method returns
the pilot, so calls chain:

| Method | What it does |
|--------|--------------|
| `press(*keys, ctrl=, alt=, shift=)` | Press named (`"up"`, `"enter"`, `"esc"`, `"tab"`, `"space"`) or single-char keys |
| `type(text)` | Type a string one char-event at a time (for `text_input`) |
| `click(col, row, button="left")` | Mouse press+release at a 1-based cell |
| `scroll("up"\|"down", col, row)` | Wheel scroll |
| `paste(text)` | Bracketed paste |
| `resize(cols, rows)` | Terminal resize (also sets render width) |
| `tick(dt=1/30)` | Advance `@app.on_frame` handlers by `dt` seconds, deterministically |
| `send(ev)` | Feed a raw event from a `maya.make_*` factory |
| `render(width=None)` | The current view as a string — the thing to assert on |
| `.running` / `.state` | Quit flag / the app's state object |

Under the hood these use synthetic-event factories you can also call directly
— `maya.make_key("a", ctrl=True)`, `make_mouse`, `make_scroll`, `make_paste`,
`make_resize` — which produce the exact same `Event` the live loop delivers, so
every `key()` / `mouse_*()` predicate treats them as real input.

---

## Where to go next

- **[Program (MVU)](program.md)** — the pure, testable runtime; when state and
  effects should be data.
- **[Widgets](widgets.md)** — the native renderer catalog (incl. `viewport` /
  `scrollbar` / `ScrollState`).
- **[Layout](layout.md)** — `row` / `col` / `card` / `grow` / `gap` / `justify`.
- **[Text & Style](text-and-style.md)** — `T`, `when`, palettes, tuple cells.
- **[Low-Level API](low-level.md)** — `run`, the raw `Event` and its predicates.
- **[Concepts](concepts.md)** — the mental model behind all of it.
