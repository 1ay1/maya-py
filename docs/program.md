# The Program model (MVU)

[← Manual index](index.md)

maya's primary architecture is **MVU** — Model, View, Update — the same model
the C++ framework exposes through `run<P>`. An application is four pure
functions over an immutable model and a closed set of messages:

| Function              | Signature                          | Role                          |
|-----------------------|------------------------------------|-------------------------------|
| `init()`              | `-> model \| (model, Cmd)`         | initial state + startup effect|
| `update(model, msg)`  | `-> model \| (model, Cmd)`         | pure state transition         |
| `view(model)`         | `-> Element`                       | pure rendering                |
| `subscribe(model)`    | `-> Sub`                           | declarative event sources     |

Side effects never happen inside `update`. They are returned as **`Cmd`**
data; event sources are returned as **`Sub`** data. The runtime interprets both
and performs all I/O. That keeps `update` a pure, testable function — same
inputs, same outputs.

This is not a simplified shim: `run_program` drives maya's own event loop with
the same `Cmd`/`Sub` interpreters, timer reconciliation, and animation
scheduling as the C++ `run<P>`.

> Prefer a lighter, imperative style? [`App`](apps.md) wraps this loop with
> mutable state and `@app.on(key)` handlers. Use `Program` when you want pure
> transitions, effects-as-data, and testable logic.

## A counter

```python
import maya_py as maya
from maya_py import Cmd, Sub, Program

class Counter(Program):
    title = "counter"

    def init(self):
        return {"count": 0}, Cmd.set_title("maya counter")

    def update(self, m, msg):
        if msg == "inc":   return {**m, "count": m["count"] + 1}
        if msg == "dec":   return {**m, "count": m["count"] - 1}
        if msg == "reset": return {**m, "count": 0}
        if msg == "quit":  return m, Cmd.quit()
        return m

    def view(self, m):
        return maya.box(
            maya.text("Counter", maya.bold),
            maya.text(str(m["count"]), maya.bold),
            border=maya.Round, padding=2,
        )

    def subscribe(self, m):
        return Sub.on_key(lambda ev:
            "inc"   if maya.key(ev, "+") else
            "dec"   if maya.key(ev, "-") else
            "reset" if maya.key(ev, "r") else
            "quit"  if maya.key(ev, "q") else None)

Counter().run()
```

`Program` is OO sugar. The same thing as plain functions:

```python
from maya_py import run_program

run_program(init, update, view, subscribe, title="counter")
```

Both forms accept `inline=True` (render into the terminal's own scrollback, no
alt screen), `mouse=True`, and `fps=N` (continuous rendering).

## Messages

A message is **any Python value** — a string, a tuple, a dataclass, an enum.
`update` pattern-matches on it. Tuples are handy for carrying a payload:

```python
def update(self, m, msg):
    match msg:
        case "tick":              return {**m, "t": m["t"] + 1}
        case ("set", value):      return {**m, "field": value}
        case ("loaded", rows):    return {**m, "rows": rows}, Cmd.none()
    return m
```

## `Cmd` — effects as data

`update` returns `(model, Cmd)` to ask the runtime to perform an effect. Return
a bare model (no tuple) when there's no effect.

| Constructor                          | Effect                                            |
|--------------------------------------|---------------------------------------------------|
| `Cmd.none()`                         | nothing                                           |
| `Cmd.quit()`                         | exit the program                                  |
| `Cmd.batch(a, b, ...)`               | run several commands                              |
| `Cmd.after(ms, msg)`                 | dispatch `msg` once after `ms` (one-shot timer)   |
| `Cmd.set_title(text)`                | set the terminal window title                     |
| `Cmd.write_clipboard(text)`          | copy to the system clipboard (OSC 52)             |
| `Cmd.query_clipboard()`              | request the clipboard; reply arrives as a paste   |
| `Cmd.task(fn)`                       | run `fn(dispatch)` on a background worker          |
| `Cmd.isolated_task(fn)`              | like `task` but on a dedicated detached thread     |
| `Cmd.commit_scrollback(rows)`        | mark top `rows` inline rows as scrollback         |
| `Cmd.commit_scrollback_overflow()`   | commit all rows that overflowed the viewport      |
| `Cmd.force_redraw()`                 | soft repaint of the live viewport (Ctrl-L)        |
| `Cmd.reset_inline()`                 | hard inline reset (wholesale content swap)        |

### Async work with `Cmd.task`

`fn` receives a `dispatch` callable. Do the slow work, then call
`dispatch(msg)` to feed the result back into `update` — on the main loop, with
the GIL held for you:

```python
def update(self, m, msg):
    if msg == "fetch":
        def work(dispatch):
            data = slow_http_get()          # runs on a worker thread
            dispatch(("loaded", data))      # back into update()
        return {**m, "loading": True}, Cmd.task(work)
    if msg[0] == "loaded":
        return {**m, "loading": False, "data": msg[1]}
    return m
```

Use `Cmd.isolated_task` for work that can wedge on a blocking syscall (slow
mounts, hung subprocess) so it leaks at most one thread instead of starving the
shared worker pool.

## `Sub` — event sources as data

`subscribe(model)` declares what the program currently listens to. It's
rebuilt after every update, so subscriptions can depend on state (e.g. only
poll while a request is in flight).

| Constructor                       | Source                                             |
|-----------------------------------|----------------------------------------------------|
| `Sub.none()`                      | nothing                                            |
| `Sub.batch(a, b, ...)`            | combine several subscriptions                      |
| `Sub.on_key(filter)`              | `filter(event) -> msg \| None` on key events       |
| `Sub.on_mouse(filter)`            | `filter(event) -> msg \| None` on mouse events     |
| `Sub.on_resize(fn)`               | `fn(width, height) -> msg` on resize               |
| `Sub.on_paste(fn)`                | `fn(text) -> msg` on bracketed paste               |
| `Sub.every(ms, msg)`              | emit `msg` every `ms` ms (animation / polling)     |
| `Sub.on_animation_frame(msg)`     | emit `msg` at ~60fps (sugar for `every(16, msg)`)  |

The key/mouse filters receive the opaque `Event` and use the predicates
(`maya.key`, `maya.ctrl`, `maya.mouse_clicked`, …) to classify it — exactly the
same predicates the [`App`](apps.md) handlers use. Return `None` to ignore an
event.

### A self-driving clock

```python
class Clock(Program):
    def init(self):           return {"t": 0}
    def update(self, m, msg):  return {**m, "t": m["t"] + 1}   # on each tick
    def view(self, m):        return maya.text(f"t = {m['t']}")
    def subscribe(self, m):   return Sub.every(1000, "tick")

Clock().run()
```

No keypress needed — the timer subscription drives the model forward. Drop the
subscription (return `Sub.none()` for some state) and the timer stops; maya
reconciles the timer set against `subscribe` every loop iteration.

## Why pure?

Because `update` performs no I/O, you can unit-test the entire logic of an app
without a terminal:

```python
c = Counter()
m0, _ = c.init()
assert c.update(m0, "inc") == {"count": 1}
assert c.update({"count": 5}, "reset") == {"count": 0}
```

See [`examples/counter_program.py`](https://github.com/1ay1/maya-py/blob/master/examples/counter_program.py) for a
complete runnable program and `tests/test_program.py` for the test suite.
