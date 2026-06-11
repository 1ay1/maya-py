# Rendering

[← Manual index](index.md)

There are four ways to get an element onto the screen, from simplest to most
involved:

| Function | Use for |
|----------|---------|
| `show(node)` | One-shot styled output to stdout. |
| `to_string(node)` | Render to a string (testing, capture, no tty). |
| `animate(fn)` | Inline animation loop. |
| `run(...)` | Full interactive event loop (the `App` class wraps this). |

All of them accept a **node** — a `str`, a `T`, or an `Element`.

## `show(node, width=None)`

Renders once to stdout and returns. The everyday "print a styled thing"
function. Does **not** use the alternate screen — output stays in your
scrollback like normal program output.

```python
import maya_py as maya
from maya_py import card, b

maya.show(card(b("done").fg("green"), title="build"))
```

`width` defaults to the detected terminal width. Pass an int to force it.

### `maya.print(...)`

`maya.print` is a convenience that routes `Element`s to `show` but lets plain
strings fall through to the builtin `print`:

```python
maya.print(card("hi"))      # rendered
maya.print("just text")     # builtin print
```

This is handy when you `import maya_py as maya` and want one `print` for both.

## `to_string(node, width=80)`

Renders to a plain string (with ANSI escapes). No terminal needed — ideal for
tests, snapshotting, or piping.

```python
from maya_py import to_string, card

text = to_string(card("hi"), width=40)
assert "hi" in text
```

## `animate(render_fn, *, fps=30)`

Runs an **inline animation loop**. `render_fn(dt)` is called each frame with
the seconds elapsed since the last frame, and returns a node. Call
`maya.quit()` to stop.

```python
import time
import maya_py as maya
from maya_py import animate, card

start = time.time()
n = 0

def render(dt):
    global n
    n += 1
    if time.time() - start > 3:
        maya.quit()
    return card(f"frame {n}  (dt={dt*1000:.1f}ms)")

animate(render, fps=30)
```

`animate` is inline (stays in scrollback) and re-renders at the given fps.
Because it uses maya's cell diff, only changed cells are written each frame.

### `maya.quit()`

Requests the current `animate` / `live` / `run` loop to stop. For an `App`,
prefer `app.stop()`.

## `run(event_fn, render_fn, ...)` — low-level loop

The interactive loop that `App` is built on. Use it directly only if you want
to bypass the `App` ergonomics.

```python
import maya_py as maya
from maya_py import card, b

n = 0

def on_event(ev):
    global n
    if maya.key(ev, "q"):
        return False           # returning False quits
    if maya.key(ev, "+"):
        n += 1
    return True

def view():
    return card(b(f"Count: {n}"))

maya.run(on_event, view, title="counter", inline_mode=True)
```

Signature:

```python
run(event_fn, render_fn, *, title="", inline_mode=False, mouse=False, fps=0)
```

- `event_fn(ev) -> bool` — return `False` to quit, `True`/`None` to continue.
- `render_fn() -> node` — returns the current UI.
- `inline_mode` — `True` for inline, `False` for fullscreen.
- `mouse`, `fps` — as in `App`.

Match events inside `event_fn` with the [event predicates](low-level.md#events).

## `live(render_fn, ...)` — low-level animation

The primitive `animate` wraps. Takes `render_fn(dt) -> Element` (note: must
return an `Element`, not a bare string — `animate` does the coercion for you).

```python
from maya_py import live, Element, text

live(lambda dt: text("tick"), fps=30, max_width=0, cursor=False)
```

- `max_width=0` auto-detects width.
- `cursor=False` hides the cursor during the loop.

Prefer `animate` unless you specifically need to skip the node coercion.

## Inline vs fullscreen

- **Inline** (`inline=True` / `inline_mode=True`): the UI lives in the
  terminal's normal scrollback, like Claude Code. Output above it is
  preserved; the UI redraws in place. Best for tools and assistants.
- **Fullscreen** (`inline=False`): switches to the alternate screen buffer
  (like `vim` / `htop`). The previous terminal contents are hidden and
  restored on exit. Best for dashboards and games.

## Next

- [Performance](performance.md) — make redraws cheap with `memo`.
- [Apps](apps.md) — the high-level `App` wrapper around `run`.
