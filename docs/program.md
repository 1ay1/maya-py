# Program (MVU)

[← Manual index](index.md)

maya's primary architecture is **MVU** — Model, View, Update — the Elm
Architecture, the same model the C++ framework runs through `run<P>`. If you
have not read [How maya-py works §4](concepts.md) yet, read it first: it places
`Program` next to `App` and explains *why* the two runtimes exist. This page is
the deep dive into `Program`.

A `Program` is four functions over an **immutable model** and a **closed set of
messages**:

| Function             | Signature                  | Role                            |
|----------------------|----------------------------|---------------------------------|
| `init()`             | `-> model \| (model, Cmd)` | initial state + startup effect  |
| `update(model, msg)` | `-> model \| (model, Cmd)` | pure state transition           |
| `view(model)`        | `-> Element`               | pure rendering                  |
| `subscribe(model)`   | `-> Sub`                   | declarative event sources       |

The whole architecture rests on one discipline: **`update` performs no I/O.**
Side effects are not *done* inside `update` — they are *returned* as `Cmd` data.
Input sources are not *registered* imperatively — they are *declared* as `Sub`
data. The runtime owns the impure world: it performs every `Cmd`, listens to
every `Sub`, and feeds the results back to `update` as ordinary messages. Your
code is a pure description; maya is the interpreter.

This is not a Python reimplementation. `Cmd` and `Sub` are the native maya value
types (re-exported verbatim from the `_maya` extension), built by the same smart
constructors the C++ side uses. An effect or subscription you return from Python
is interpreted by maya's real runtime, with the same timer reconciliation and
animation scheduling as `run<P>`.

---

## 1. Why purity matters

Because `update` is `(model, msg) -> (model[, Cmd])` with no terminal, no clock,
and no network inside it, it is a plain function you can call from a test:

```python
from maya_py import Cmd
from myapp import update          # your update; needs no maya runtime to call

def test_increment():
    assert update({"count": 0}, "inc") == {"count": 1}

def test_quit_emits_cmd():
    model, cmd = update({"count": 3}, "quit")
    assert model == {"count": 3}
    assert isinstance(cmd, Cmd)    # the effect is *data*, returned not performed
```

No event loop is started, no alt screen is entered, nothing is drawn. You assert
on the returned model — and, when there is an effect, on the returned `Cmd`. See
[§7](#7-testing-update-without-a-terminal) for the full pattern. This testability
is the single biggest reason to reach for `Program` over [`App`](apps.md): your
core logic is verifiable in milliseconds, with no terminal and no flakiness.

The flip side of the discipline: **never mutate the model in `update`.** Return
a new value (`{**m, "count": m["count"] + 1}`), never `m["count"] += 1`. A
mutated model defeats the architecture and breaks the very testability you came
for.

---

## 2. Two ways to write a Program

Both forms compile to the identical runtime loop; pick the ergonomics you like.

### Plain functions + `run_program`

```python
import maya_py as maya
from maya_py import Cmd, Sub, run_program

def init():
    return {"count": 0}

def update(model, msg):
    if msg == "inc":  return {**model, "count": model["count"] + 1}
    if msg == "dec":  return {**model, "count": model["count"] - 1}
    if msg == "quit": return model, Cmd.quit()
    return model

def view(model):
    return maya.card(maya.text(f"count: {model['count']}"))

def subscribe(model):
    return Sub.on_key(lambda ev:
        "inc"  if maya.key(ev, "+") else
        "dec"  if maya.key(ev, "-") else
        "quit" if maya.key(ev, "q") else None)

run_program(init, update, view, subscribe, title="counter")
```

### A `Program` subclass

Override the four hooks and call `.run()`. Same semantics, OO ergonomics:

```python
import maya_py as maya
from maya_py import Cmd, Sub, Program

class Counter(Program):
    title = "counter"

    def init(self):            return {"count": 0}
    def view(self, m):         return maya.card(maya.text(f"count: {m['count']}"))
    def subscribe(self, m):    return Sub.on_key(lambda ev:
        "inc" if maya.key(ev, "+") else "quit" if maya.key(ev, "q") else None)

    def update(self, m, msg):
        if msg == "inc":  return {**m, "count": m["count"] + 1}
        if msg == "quit": return m, Cmd.quit()
        return m

Counter().run()
```

The default `Program.init` returns `{}`, the default `update` is the identity,
and the default `subscribe` returns `Sub.none()`. `view` has no default — it
raises `NotImplementedError` until you override it.

---

## 3. The signatures (from source)

### `run_program`

```python
run_program(
    init: Callable[[], Any],
    update: Callable[[Model, Msg], Any],
    view: Callable[[Model], Any],
    subscribe: Optional[Callable[[Model], Any]] = None,
    *,
    title: str = "",
    inline: bool = False,
    mouse: bool = False,
    fps: int = 0,
) -> None
```

- `init()` returns `model` **or** `(model, Cmd)` — pair it with a `Cmd` to run a
  startup effect (set the title, kick off a fetch, start a timer-equivalent).
- `update(model, msg)` returns `model` **or** `(model, Cmd)`.
- `view(model)` returns an `Element` (use the easy API: `card`, `row`, `text`, …).
- `subscribe(model)` returns a `Sub`. It is **optional** — omit it (or pass
  `None`) for a program with no event sources.
- `title` — terminal window title.
- `inline=True` renders into the terminal's own scrollback (no alternate
  screen), like a rich prompt; `inline=False` (the default here) takes the full
  screen. See [concepts §5](concepts.md) on inline vs. alternate screen.
- `mouse=True` enables mouse event reporting (so `Sub.on_mouse` fires).
- `fps>0` drives continuous rendering at that frame rate; `fps=0` (default) means
  "redraw only when the model changes." Set `fps>0` only for continuous motion —
  but note that timer-driven motion is usually better expressed with `Sub.every`
  or `Sub.on_animation_frame` (see [§6](#6-sub--input-sources-as-data)).

`run_program` blocks until `Cmd.quit()` is returned or the user hits Ctrl-C.

### `Program`

```python
class Program:
    title: str = ""
    inline: bool = False
    mouse: bool = False
    fps: int = 0

    def init(self) -> Any: ...                     # model | (model, Cmd)
    def update(self, model, msg) -> Any: ...        # model | (model, Cmd)
    def view(self, model) -> Any: ...               # -> Element  (must override)
    def subscribe(self, model) -> Any: ...          # -> Sub  (default Sub.none())

    def run(self, *, title=None, inline=None, mouse=None, fps=None) -> None: ...
```

The class attributes (`title`, `inline`, `mouse`, `fps`) supply defaults;
keyword args to `.run()` override them per launch. Internally `.run()` just
forwards your bound hooks to `run_program`.

---

## 4. Messages

A message is **any Python value** — a string, a tuple, an int, a dataclass, an
enum. `update` dispatches on it however you like. Strings read well for simple
intents; tuples (or dataclasses) carry payloads:

```python
def update(model, msg):
    match msg:
        case "tick":            return {**model, "t": model["t"] + 1}
        case ("set", value):    return {**model, "field": value}
        case ("loaded", rows):  return {**model, "rows": rows, "loading": False}
    return model
```

Messages arrive from exactly two places: a `Cmd` the runtime ran (e.g. a
background `task` calling `dispatch(msg)`, or an `after` timer firing) and a
`Sub` the runtime is listening to (a keypress your `on_key` filter mapped to a
message, an `every` timer). There is no other way to mutate the model — which is
why the message set is "closed" and `update` is exhaustively testable.

---

## 5. `Cmd` — effects as data

`Cmd` is a native maya value type. You build one with a constructor and return it
from `init` or `update` (as `(model, cmd)`); the runtime performs the effect and,
where an effect produces a result, dispatches it back as a message. Return a
**bare model** (no tuple) when there is no effect — that is sugar for `Cmd.none()`.

| Constructor | Real signature | Effect |
|-------------|----------------|--------|
| `Cmd.none()` | `none()` | do nothing (the no-op effect) |
| `Cmd.quit()` | `quit()` | exit the program; `run_program` returns |
| `Cmd.batch(*cmds)` | `batch(*args)` | perform several commands together |
| `Cmd.after(ms, msg)` | `after(ms: float, msg: object)` | dispatch `msg` once after `ms` milliseconds (one-shot timer) |
| `Cmd.task(fn)` | `task(fn: Callable)` | run `fn(dispatch)` on a background worker thread |
| `Cmd.isolated_task(fn)` | `isolated_task(fn: Callable)` | like `task`, but on a dedicated detached thread |
| `Cmd.set_title(title)` | `set_title(title: str)` | set the terminal window title |
| `Cmd.write_clipboard(text)` | `write_clipboard(text: str)` | copy `text` to the system clipboard (OSC 52) |
| `Cmd.query_clipboard()` | `query_clipboard()` | request the clipboard contents; the reply arrives as a paste event |
| `Cmd.force_redraw()` | `force_redraw()` | force a soft repaint of the live viewport (like Ctrl-L) |
| `Cmd.reset_inline()` | `reset_inline()` | hard inline reset — a wholesale content swap of the inline region |
| `Cmd.commit_scrollback(rows)` | `commit_scrollback(rows: int)` | mark the top `rows` inline rows as permanent scrollback (they stop being repainted) |
| `Cmd.commit_scrollback_overflow()` | `commit_scrollback_overflow()` | commit every row that has overflowed the inline viewport into scrollback |

The effect-as-data idea in one line: **`update` decides *what* should happen and
returns it; the runtime decides *when* and *how* to do it and turns any result
back into a message.** That is what keeps `update` pure.

### `Cmd.batch` — more than one effect

```python
def update(self, m, msg):
    if msg == "start":
        return {**m, "running": True}, Cmd.batch(
            Cmd.set_title("working…"),
            Cmd.after(5000, "timeout"),
        )
    return m
```

### `Cmd.after` — one-shot timer

`Cmd.after(ms, msg)` dispatches `msg` exactly once after `ms` milliseconds.
Re-issue it from `update` to build a self-restarting timer (an alternative to a
`Sub.every` subscription when you want the cadence to depend on per-tick logic):

```python
def update(self, m, msg):
    if msg == "tick":
        return {**m, "t": m["t"] + 1}, Cmd.after(1000, "tick")   # schedule the next
    return m
```

### `Cmd.task` / `Cmd.isolated_task` — async work

`fn` receives a `dispatch` callable. Do the slow work on the worker, then call
`dispatch(msg)` to feed the result back into `update`:

```python
def update(self, m, msg):
    if msg == "fetch":
        def work(dispatch):
            data = slow_http_get()          # runs off the main loop
            dispatch(("loaded", data))      # re-enters update() as a message
        return {**m, "loading": True}, Cmd.task(work)
    if isinstance(msg, tuple) and msg[0] == "loaded":
        return {**m, "loading": False, "data": msg[1]}
    return m
```

`dispatch` is safe to call from the worker thread — the runtime marshals the
message back onto the main loop. Use `Cmd.isolated_task` for work that can wedge
on a blocking syscall (a hung subprocess, a slow network mount): it runs on its
own detached thread, so at worst it leaks that one thread instead of starving the
shared worker pool.

### Clipboard

`Cmd.write_clipboard(text)` copies via OSC 52 (works over SSH on capable
terminals). `Cmd.query_clipboard()` asks for the current contents; because there
is no synchronous return, the reply comes back as a **paste event** — declare a
`Sub.on_paste(...)` to receive it.

### Inline & scrollback commands

These matter when `inline=True`. `Cmd.commit_scrollback(rows)` freezes the top
`rows` of the inline region into the terminal's real scrollback so they are never
repainted again (useful for an append-only log where old lines should scroll away
naturally). `Cmd.commit_scrollback_overflow()` does the same for whatever has
already overflowed the viewport. `Cmd.force_redraw()` and `Cmd.reset_inline()`
are escape hatches for repainting the live region — the soft and hard variants
respectively.

---

## 6. `Sub` — input sources as data

`subscribe(model)` declares **what the program is currently listening to**. It is
called after every update, so subscriptions can depend on the model: listen to a
timer only while a request is in flight, stop listening when a modal closes, and
so on. maya **reconciles** the declared set against the live one every iteration —
when a `Sub.every` disappears from what you return, its timer is torn down; when
it reappears, it is restarted. You never start or stop a source imperatively.

| Constructor | Real signature | Source |
|-------------|----------------|--------|
| `Sub.none()` | `none()` | nothing (the default `subscribe`) |
| `Sub.batch(*subs)` | `batch(*args)` | combine several subscriptions |
| `Sub.on_key(filter)` | `on_key(filter: Callable)` | `filter(event) -> msg \| None` on each key event |
| `Sub.on_mouse(filter)` | `on_mouse(filter: Callable)` | `filter(event) -> msg \| None` on each mouse event (needs `mouse=True`) |
| `Sub.on_paste(fn)` | `on_paste(fn: Callable)` | `fn(text) -> msg` on bracketed-paste (and clipboard-query replies) |
| `Sub.on_resize(fn)` | `on_resize(fn: Callable)` | `fn(width, height) -> msg` on terminal resize |
| `Sub.every(ms, msg)` | `every(ms: float, msg: object)` | dispatch `msg` every `ms` milliseconds (timer / polling / animation) |
| `Sub.on_animation_frame(msg)` | `on_animation_frame(msg: object)` | dispatch `msg` once per rendered animation frame |

### How subscriptions deliver messages

A `Sub` does not handle anything itself — it **maps a raw event to a message**
(or to `None` to ignore it), and the runtime feeds that message to `update`. The
key and mouse filters receive the opaque `Event` and classify it with the same
predicates the [`App`](apps.md) handlers use:

```python
def subscribe(self, m):
    return Sub.on_key(lambda ev:
        "inc"   if maya.key(ev, "+") else
        "dec"   if maya.key(ev, "-") else
        "left"  if maya.key_special(ev, maya.SpecialKey.Left) else
        "quit"  if maya.key(ev, "q") or maya.key_special(ev, maya.SpecialKey.Esc) else
        None)                                   # None → event ignored
```

Returning `None` from a filter means "not for me" — the event falls through.
`Sub.on_paste` and `Sub.on_resize` take a plain function of the payload
(`text`, or `(width, height)`) rather than an `Event`.

Combine sources with `Sub.batch`:

```python
def subscribe(self, m):
    return Sub.batch(
        Sub.on_key(keymap),
        Sub.every(1000, "tick"),
        Sub.on_resize(lambda w, h: ("resized", w, h)),
    )
```

### Timers vs. `fps`

`Sub.every(ms, msg)` is the idiomatic way to drive a program forward on a clock —
prefer it over setting `fps>0`, because it dispatches a *message* (so the change
flows through `update` and stays testable) rather than just forcing a blind
repaint. `Sub.on_animation_frame(msg)` fires once per rendered frame, for
motion that should track the display's actual cadence (games, smooth animation).

---

## 7. A complete worked program: a self-driving clock

This program needs no keypress to run — a `Sub.every` timer drives the model, a
startup `Cmd` sets the title, and `q` quits. It is runnable as-is with
`from maya_py import ...`.

```python
import time
import maya_py as maya
from maya_py import Cmd, Sub, Program


class Clock(Program):
    title = "clock"

    def init(self):
        # initial model + a startup effect
        return {"now": time.strftime("%H:%M:%S"), "ticks": 0}, Cmd.set_title("maya clock")

    def update(self, m, msg):
        if msg == "tick":
            return {**m, "now": time.strftime("%H:%M:%S"), "ticks": m["ticks"] + 1}
        if msg == "quit":
            return m, Cmd.quit()
        return m

    def view(self, m):
        return maya.box(
            maya.text("Clock", maya.bold | maya.fg(120, 180, 255)),
            maya.blank(),
            maya.text(m["now"], maya.bold),
            maya.blank(),
            maya.text(f"{m['ticks']} ticks   ·   q to quit", maya.dim),
            direction=maya.Column,
            border=maya.Round,
            padding=2,
        )

    def subscribe(self, m):
        return Sub.batch(
            Sub.every(1000, "tick"),                                  # one message per second
            Sub.on_key(lambda ev: "quit" if maya.key(ev, "q") else None),
        )


if __name__ == "__main__":
    Clock().run()
```

The same program as plain functions and `run_program`:

```python
def init():            return {"now": time.strftime("%H:%M:%S"), "ticks": 0}
def update(m, msg):    ...     # identical body
def view(m):           ...     # identical body
def subscribe(m):      return Sub.every(1000, "tick")

run_program(init, update, view, subscribe, title="clock")
```

For the canonical counter, see
[`examples/counter_program.py`](https://github.com/1ay1/maya-py/blob/master/examples/counter_program.py).

---

## 8. Testing `update` without a terminal

Because `update` is pure, the test suite never opens a terminal. Pull `update`
(and `init`) into a test and assert on the returned value:

```python
from maya_py import Cmd
from clock import Clock          # the module above

def test_init_sets_title():
    model, cmd = Clock().init()
    assert model["ticks"] == 0
    assert isinstance(cmd, Cmd)              # startup effect is data

def test_tick_advances():
    after = Clock().update({"now": "", "ticks": 4}, "tick")
    assert after["ticks"] == 5               # bare model, no Cmd

def test_quit_emits_cmd():
    model, cmd = Clock().update({"now": "", "ticks": 1}, "quit")
    assert model == {"now": "", "ticks": 1}  # model unchanged
    assert isinstance(cmd, Cmd)              # the quit effect, returned not run
```

Two patterns to internalize:

- When `update` has no effect it returns a **bare model**; when it does, a
  **`(model, Cmd)` tuple**. Assert on the model with `==`, and on the presence of
  an effect with `isinstance(cmd, Cmd)`. `Cmd` is opaque (a native value), so you
  assert *that* an effect was returned, not its internals.
- For a `Cmd.task`, the work runs through `dispatch`; in a test you simply feed
  the resulting message straight into `update` (e.g. `update(m, ("loaded", rows))`)
  to verify the second half of the flow — no thread, no network needed.

This is the payoff of purity from [concepts §4](concepts.md): your entire state
machine is verifiable in isolation.

---

## 9. When to use `Program` vs. `App`

Both runtimes ([`App`](apps.md) and `Program`) compile to the identical render
pipeline; they differ only in how you manage state and effects.

**Use [`App`](apps.md)** for almost everything — it is the 90% path. State is a
mutable bag, handlers mutate it in place (`@app.on("+")`), and the view
re-renders from it. Less ceremony, faster to write.

**Reach for `Program`** when:

- you want **testable logic** — `update` is a pure function, so you can assert on
  `update(model, msg)` with no terminal (the reason most people choose it);
- **effects are complex enough** that returning them as data (`Cmd`) beats
  scattering side effects through imperative handlers;
- **concurrency must be explicit** — `Cmd.task` makes background work and its
  result message a visible part of the architecture;
- you are porting an existing Elm/`run<P>` design and want the same shape.

They are not mixed in one application — pick one runtime per program. When in
doubt, start with `App`; move to `Program` when the logic grows enough that you
want it under test.

---

## See also

- [How maya-py works §4](concepts.md) — `App` vs. `Program`, the mental model.
- [Apps](apps.md) — the imperative runtime in depth.
- [`examples/counter_program.py`](https://github.com/1ay1/maya-py/blob/master/examples/counter_program.py) — the canonical MVU counter.
