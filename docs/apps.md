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

## `App(title="", *, inline=True, mouse=False, fps=0)`

| Argument | Default | Meaning |
|----------|---------|---------|
| `title` | `""` | Terminal window title (OSC 0). |
| `inline` | `True` | `True` = inline mode (lives in scrollback, Claude-Code style). `False` = fullscreen alt-screen. |
| `mouse` | `False` | Enable mouse event reporting. |
| `fps` | `0` | `0` = event-driven (render only after input). `>0` = continuous render at N fps (for animations driven by wall-clock). |

## State

### `app.state(**kw)`

Seeds initial state and returns the state object. Call once at setup.

```python
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
[event predicates](low-level.md#events) (`key`, `ctrl`, etc.) if needed.

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
