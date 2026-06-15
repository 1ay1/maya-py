# How maya-py works (and how to think in it)

[← Manual index](index.md)

This page is the mental model. Once these ideas click, every other page in the
manual — and every design decision you'll make in your own apps — follows from
them. Read it once end-to-end; come back to it when something surprises you.

---

## 1. The one-sentence model

> **You write a pure function from *state* to an *element tree*; maya lays it
> out, paints it to a cell grid, diffs that grid against what's already on the
> terminal, and writes only the bytes that changed.**

Everything else — the easy API, the `App` class, `memo`, tuple cells, the MVU
`Program` — is in service of making that loop fast, correct, and pleasant to
write. Hold onto two consequences:

1. **Your view is a description, not a sequence of commands.** You never "move
   the cursor" or "clear the screen." You return *what the screen should look
   like now*, and maya computes the minimal way to get there.
2. **The expensive part is building the tree in Python; the cheap part is
   maya's native render.** Almost every performance technique is about
   *building less* (see §7).

---

## 2. The render pipeline

A single frame flows through five stages. Three live in Python, two in C++:

```
   your view(state)            build         (Python + pybind11 boundary)
        │  returns
        ▼
   Element tree                 ─┐
        │                        │
        ▼                        │ maya, native C++
   Flexbox layout (Yoga)         │   ~flat cost in tree size
        │  → x/y/w/h per node    │
        ▼                        │
   Paint → Canvas (cell grid)    │   each cell = char + 64-bit packed style id
        │                        │
        ▼                        │
   Diff vs previous frame (SIMD) ─┘   → only changed cells
        │
        ▼
   Bytes on the wire (ANSI/SGR escapes) → your terminal
```

- **Element tree** — immutable nodes (`Element`) describing boxes, text, and
  widgets. Built by `card(...)`, `row(...)`, `T(...).fg(...)`, the widget
  functions, etc. Each call crosses into C++ once.
- **Layout** — maya runs a flexbox solver (Yoga) over the tree: it resolves
  every node's position and size from your `width`/`grow`/`gap`/`align`/…
  constraints. This is why a `row(...)` with a `grow(...)` child "just fills."
- **Paint** — the laid-out tree is rasterized into a **Canvas**: a flat grid of
  cells. Each cell packs its glyph plus a 16-bit *style id* into 64 bits, so two
  cells are equal iff their 64-bit words are equal (this makes the diff fast).
- **Diff** — the new Canvas is compared against the previous frame's grid with
  SIMD. Only cells that actually changed produce output.
- **Wire** — changed cells are serialized to the minimal ANSI escape sequence
  and written to the terminal.

You can observe the boundaries directly: `to_string(node)` runs build + layout +
paint + serialize once (no diff, no previous frame); `show(node)` does the same
straight to stdout; the interactive loops add the diff + wire stages and repeat.

---

## 3. Elements are values; strings *are* elements

The easy API leans on one trick: **anywhere a child is expected, a bare `str`
(or a styled `T`, or a tuple) is accepted and coerced into an element.** So
`card("hello")` and `row("a", "b")` work without wrapping. This is why the docs
say "strings are UI."

Three things flow into a layout container as children:

| You pass | Becomes |
|----------|---------|
| `"text"` | a text leaf |
| `T("text").fg("sky").bold` | a styled text leaf (one boundary crossing when built) |
| `("text", "sky")` / `("text", fg, bg, attrs)` | a styled leaf built from raw scalars — *no `T` object* |
| `card(...)`, `row(...)`, a widget | a nested element subtree |

`T` is a **fluent builder**: `T("x").bold.fg("sky")` accumulates style in pure
Python and makes a *single* crossing into C++ when the element is finally built
(then caches it on the `T`). The tuple form skips even the `T` allocation — it's
the fastest way to emit many styled cells (tables, dashboards, per-frame redraws).

> **Expert habit:** reach for `T`/markup for one-off UI (it reads well), and for
> tuple cells in hot per-frame loops. Both produce byte-identical output.

---

## 4. Two runtimes: `App` and `Program`

maya-py gives you two ways to run an interactive loop. They compile down to the
same render pipeline; they differ in *how you manage state and side effects*.

### `App` — imperative state, the 90% path

```python
from maya_py import App, card, b

app = App("counter", n=0, quit_keys=("q", "esc"))

@app.on("+", "=")
def inc(s): s.n += 1        # mutate state in place

@app.view
def view(s):                # pure: state -> element tree
    return card(b(f"Count: {s.n}"))

app.run()
```

The model: **state is a mutable bag** (`app.s`), **handlers mutate it**, and the
**view re-renders from it** after every handled event. The full surface:

| Member | Role |
|--------|------|
| `App(title="", *, inline=True, mouse=False, fps=0, quit_on_ctrl_c=True, quit_keys=(), model=None, keys=None, **state)` | construct; seed state as kwargs, or pass your own `model=` object, or bind keys declaratively with `keys={...}` |
| `app.state(**kw)` / `app.s` | seed / access the live state bag |
| `@app.on(*keys)` | run `fn(state)` on those keys |
| `@app.on_key` | catch-all `fn(state, event)` |
| `@app.on_frame` | per-frame tick `fn(state, dt)` — enables continuous animation |
| `@app.on_paste` / `@app.on_resize` | `fn(state, text)` / `fn(state, cols, rows)` |
| `@app.on_click` / `@app.on_scroll` / `@app.on_mouse` | mouse handlers (needs `mouse=True`) |
| `app.focus(*widgets)` | register interactive widgets; the focused one gets keys, Tab cycles |
| `@app.view` | register the `state -> node` view |
| `app.run()` / `app.stop()` | start (blocks) / request exit |

### `Program` — the Elm Architecture (MVU), the control-freak path

```python
from maya_py import run_program, Cmd, Sub, card

def init():   return {"n": 0}
def update(model, msg):
    if msg == "inc": return {"n": model["n"] + 1}, Cmd.none()
    return model, Cmd.none()
def view(model): return card(f"Count: {model['n']}")

run_program(init, update, view)
```

Here **state is immutable**: `update` is a *pure* function `(model, msg) ->
(new_model, Cmd)`. Side effects never happen inline — you *return* them as a
`Cmd`, and the runtime performs them and feeds results back as messages. Inputs
arrive through `Sub`scriptions.

- **`Cmd`** (effects to run): `none`, `quit`, `batch`, `after`, `task`,
  `isolated_task`, `set_title`, `write_clipboard`, `query_clipboard`,
  `force_redraw`, `reset_inline`, `commit_scrollback`, `commit_scrollback_overflow`.
- **`Sub`** (input sources): `none`, `batch`, `on_key`, `on_mouse`, `on_paste`,
  `on_resize`, `every` (timer), `on_animation_frame`.

**When to use which.** Use `App` for almost everything — it's less ceremony.
Reach for `Program` when you want *testable* update logic (it's a pure function,
so you can assert on `update(model, msg)` with no terminal), when effects are
complex enough that returning them as data beats scattering them through
handlers, or when concurrency (`Cmd.task`) needs to be explicit. They're not
mixed in one app; pick one per program.

---

## 5. The frame lifecycle

What actually happens between "you press a key" and "the screen updates":

1. **Input** arrives (key, mouse, paste, resize) and is decoded into an `Event`.
2. The runtime **routes** it: scroll states get first refusal (see §6), then
   your handlers (`@app.on(...)`, `on_key`, …) run and mutate/transform state.
3. If anything changed (or `on_frame`/an animation tick fired), the runtime
   calls your **view** to get a fresh element tree.
4. The tree is **laid out, painted, diffed** against the previous frame, and the
   **changed cells** are written.
5. The loop **waits** — until the next input, or, if a frame rate is set, until
   the next frame deadline.

Two details that trip people up:

- **`fps=0` means "redraw only when something changes."** That's the efficient
  default for most apps — no input, no work. Set `fps>0` (or use `on_frame` /
  `Sub.every` / `animate`) only when you need continuous motion (clocks,
  spinners, games, progress).
- **Inline vs alternate screen.** `App(inline=True)` (the default) renders *in
  place* in your scrollback, like a rich prompt; the diff preserves stable rows
  so output above is untouched. This is what makes maya feel native in a normal
  terminal session rather than taking over the whole screen.

---

## 6. The event & input model

### Keys

In `App`, bind by name: `@app.on("q", "enter", "ctrl+c", "up", "+")`. Names cover
chars (`"q"`, `"+"`), specials (`"up"`, `"enter"`, `"esc"`, `"tab"`,
`"backspace"`, `"home"`, `"pageup"`, …) and combos (`"ctrl+c"`, `"alt+x"`). For a
catch-all, `@app.on_key` gives you the raw `Event`, which you inspect with the
low-level predicates: `key(ev, "c")`, `key_special(ev, SpecialKey.Up)`,
`ctrl(ev, "c")`, `alt(ev, "x")`, `event_char(ev)` (the typed character or
`None`), `any_key(ev)`.

### Mouse

Set `mouse=True`, then use `@app.on_click` / `@app.on_scroll` / `@app.on_mouse`,
or the predicates: `is_mouse(ev)`, `mouse_clicked/released/moved(ev)`,
`mouse_button(ev)`, `mouse_pos(ev)` (1-based `(col, row)`), `scrolled_up/down(ev)`.

Coordinates are **frame-relative**: even in inline mode (where the app sits
partway down the terminal) a click on your top-left cell reports `(1, 1)`, and
clicks/scrolls outside the frame are dropped. The trade-off is structural:
**while mouse capture is on, the terminal gives the scroll wheel to your app, so
its own scrollback stops scrolling** until the app exits — that's the terminal
mouse protocol, not maya. `app.set_mouse(on)` toggles capture at runtime so you
can hand the wheel back to the terminal on demand (see [Apps](apps.md)); if an
app doesn't need the mouse, leave `mouse=False` and native scroll just works.

### Paste & resize

`@app.on_paste` delivers bracketed-paste text in one shot (don't reconstruct it
keystroke-by-keystroke); `@app.on_resize` gives new `(cols, rows)`. Low-level:
`pasted(ev)`, `resized(ev)`, `resize_size(ev)`.

### Scrolling is (mostly) automatic

This is a maya superpower worth internalizing: a `scroll_state()` you put in a
`viewport(...)`/`scrollbar(...)` **auto-dispatches** — the run loop forwards
arrows / PgUp / PgDn / Home / End and (with `mouse=True`) the wheel and scrollbar
drag to every on-screen scroll state *without any handler code*. You only call
`scroll_handle(state, ev)` manually if you're driving the low-level `run` loop
yourself. Build a scrolling log or list by composing `viewport` + `scrollbar`;
the navigation comes for free.

### Focus

`app.focus(w1, w2, ...)` registers interactive widgets (e.g. `text_input`,
`textarea`). The focused widget receives keys; Tab cycles focus. This is how you
host real input fields inside an otherwise-declarative view.

---

## 7. The performance model (this is what separates experts)

Re-read §1: **build is the floor, render is cheap.** Concretely, for a 30-row
dashboard, building the tree in Python costs ~100 µs and maya's native render
~24 µs — so ~80% of a frame is the Python boundary, not maya. You make apps fast
by *not rebuilding what didn't change*:

### `memo` — skip Python tree construction

```python
from maya_py import memo, card, b

@memo
def header(title, count):        # rebuilt only when title/count change
    return card(b(title), f"{count} items")
```

`memo` caches a built sub-tree keyed by its **positional args**. If the args are
unchanged since last frame, it returns the *same `Element` object* — zero Python
work, and maya's diff sees an unchanged subtree. Pass *comparable summaries*
(`header(s.title, len(s.items))`), never the whole mutable state bag
(`header(s)` defeats it). This is the single biggest lever for a live app: a
steady-state frame can do almost no Python at all.

### Tuple cells — skip `T` allocations

In a hot redraw of many styled cells (a table, a chart, a per-frame grid), the
throwaway `T` per cell dominates build cost. Pass `(text, fg[, bg[, attrs]])`
tuples to `row`/`col` instead — same output, far fewer allocations.

### The diff is the real win — don't fight it

Because maya emits only changed cells, a live redraw where one line changes
writes ~11× fewer bytes than re-printing the frame. On a real terminal — and
especially over SSH — **bytes on the wire are the bottleneck**, and this is a
structural advantage no string-concatenating renderer matches. The corollary:
**don't render to a string in a hot loop and print it yourself** — you'd throw
the diff away and re-emit everything every frame.

### Two subtleties from the engine room

- **Colors are interned, for the life of the run.** maya keeps a `StylePool` of
  every distinct style it has seen and never evicts it (id space is 16-bit). An
  animation that emits a *fresh shade per cell per frame* (e.g. an uncached
  continuous gradient) keeps growing that pool. **Quantize continuous colors to
  a fixed palette** (precompute N steps and index into them) so the pool stays
  bounded. Static and few-color UIs never notice this.
- **Output is non-blocking and back-pressured.** On a slow terminal the writer
  buffers what the wire can't yet take and the loop *defers* the next frame
  rather than piling up — so a heavy full-screen animation degrades to a lower
  effective frame rate instead of growing memory. You get this for free; just
  know that "my 60fps plasma runs at 30 on this terminal" is the system working
  as intended.

---

## 8. Common pitfalls (and the expert's reflex)

| Pitfall | Why it bites | Do this instead |
|---------|--------------|-----------------|
| Rebuilding everything every frame | Python build cost dominates | `memo` the stable sub-trees; pass comparable args |
| `memo`-ing on the whole state object | identity/compare never matches → never cached | pass small comparable summaries |
| Rendering to a string and printing it in a loop | throws away the diff; re-emits the whole frame | use `App`/`animate`/`live` so the diff runs |
| `fps>0` for a static UI | burns CPU redrawing identical frames | leave `fps=0`; redraw only on change |
| Fresh color per cell per frame | unbounded `StylePool` growth | quantize to a fixed palette |
| Reconstructing pasted text keystroke-by-keystroke | bracketed paste arrives whole | handle it in `@app.on_paste` |
| Hand-rolling scroll key handling | scroll states auto-dispatch | compose `viewport` + `scrollbar` and let the loop route |
| Mutating state inside `Program.update` | `update` must be pure | return a new model + `Cmd` |
| A size-aware `component`/`pixel_canvas` in `to_string` | it needs the live renderer's measure pass | render it via `animate`/`run`, or use `halfblock` with a grid for static output |

---

## 9. A reading order from here

- **[Getting Started](getting-started.md)** — install and your first UI + app.
- **[Text & Style](text-and-style.md)** and **[Layout](layout.md)** — the
  building blocks (§3 in depth).
- **[Apps](apps.md)** and **[Program (MVU)](program.md)** — the two runtimes
  (§4 in depth).
- **[Widgets](widgets.md)** — the native renderer catalog.
- **[Rendering](rendering.md)** — `show` / `to_string` / `animate` / `run` (the
  pipeline entry points, §2).
- **[Performance](performance.md)** — the benchmarks and techniques behind §7.
- **[Low-Level API](low-level.md)** and **[API Reference](api-reference.md)** —
  the primitives and the complete symbol list.
