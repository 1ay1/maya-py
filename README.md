# maya-py

Python bindings for [**maya**](https://github.com/1ay1/maya) — a C++26 TUI
framework with flexbox layout, a SIMD cell-diff renderer, and an Elm-style
runtime. `maya-py` gives you a **dead-simple** Python API for building styled
terminal UIs and interactive apps.

```python
import maya_py as maya
from maya_py import card, field, b, hr

maya.show(card(
    b("maya-py").fg("sky"),
    hr(20),
    field("Status", "Online", value_color="green"),
    field("Region", "us-east-1"),
    title="service",
))
```

That's the whole program. Strings *are* UI — no manual element wrapping.

## Documentation

A full reference manual lives in [`docs/`](docs/index.md):

- [Getting Started](docs/getting-started.md) — install, first UI, first app.
- [Text & Style](docs/text-and-style.md) — `T`, markup helpers, colors.
- [Layout](docs/layout.md) — `col`, `row`, `card`, `field`, `hr`, options.
- [Apps](docs/apps.md) — the `App` class, key bindings, state, the view.
- [Rendering](docs/rendering.md) — `show`, `to_string`, `animate`, `run`.
- [Performance](docs/performance.md) — `memo`, the boundary tax, benchmarks.
- [API Reference](docs/api-reference.md) — every public symbol.
- [Low-Level API](docs/low-level.md) — primitives and the native binding.
- [Distribution](docs/distribution.md) — standalone wheels for old machines.

## The 30-second tour

### Text: just style strings

```python
from maya_py import T, b, i, dim_text, c

b("bold")                 # bold
T("hi").bold.fg("sky")     # fluent chain
c("warn", "orange")        # colored
T("x").bg("red").fg("white")
```

Colors accept names (`"red"`, `"sky"`, `"gold"`), hex (`"#ff8800"`, `"#f80"`),
tuples (`(255, 128, 0)`), or ints (`0xFF8800`).

### Layout: stacks that take bare strings

```python
from maya_py import col, row, card, field, hr

col("top", "middle", "bottom")          # vertical
row("left", "right", gap=2)             # horizontal
card("body", title="hi", pad=1)          # bordered box
field("Name", "Ada")                     # "Name: Ada"
hr(40)                                   # horizontal rule
```

`col` / `row` / `card` accept the **full maya flexbox surface** as keywords:

- **box model**: `pad`, `margin`, `gap` (int or 1/2/4-tuples)
- **border**: `border` (`"round"`/`"double"`/`"bold"`/`"dashed"`/...),
  `border_color`, `border_sides=sides(top=..., left=...)`, `title`, and
  positioned `border_text=("Title", Top, Center)` / `border_text_end`
- **sizing**: `width`, `height`, `min_width`/`max_width`,
  `min_height`/`max_height` — each takes an int (cells), `"50%"`, a float
  like `0.5`, `"auto"`, or `pct(50)`/`cells(20)`/`auto()`
- **flex**: `grow`, `shrink`, `basis`, `align`, `align_self`, `justify`,
  `wrap` (`"wrap"`/`"nowrap"`/`"reverse"`), `overflow` (`"hidden"`/`"scroll"`)
- **style**: `bg`, `fg`, `style=maya.style(...)`

### Full layout power

Everything maya C++ can express, the Python API can too:

```python
from maya_py import T, col, row, card, center, stack, grow, component, pct, cells, sides

# percent widths + a flex child that fills the rest
row(
    card("nav", width=pct(30), title="sidebar"),
    grow(card("main content", title="body")),   # expands to fill
    gap=1,
)

# center anything in a region
center("ready", width=cells(20), height=5, border="round")

# z-stack: layers paint on top; the first sets the size
stack(card("  panel  ", height=6), T("NEW").fg("red").bold)

# partial borders
card("footer", border_sides=sides(top=True, right=False, bottom=False, left=False))

# a size-aware widget — render_fn(width, height) draws to fit its box
def bar(w, h):
    filled = int(w * 0.4)
    return T("█" * filled + "░" * (w - filled)).fg("green")
col("Loading", component(bar, height=1))
```

### Widgets: maya's native renderers

maya ships a library of ready-made widgets — they render through the **same C++
renderer** maya uses, then drop straight into any layout:

```python
from maya_py import col, row, sparkline, gauge, progress, badge, table, bar_chart

col(
    sparkline([3, 1, 4, 1, 5, 9, 2, 6], label="req/s", color="sky", show_last=True),
    gauge(0.72, "load", style="bar"),            # "arc" or "bar"
    progress(0.55, "build", width=24, fill="lime"),
    row(badge("PASS", kind="success"), badge("SKIP", kind="warning"), gap=1),
    table(["Name", ("Score", 0, "right")],       # (header, width, align)
          [["Ada", 99], ["Bob", 7]], bordered=True, title="top"),
    bar_chart([("jan", 4), ("feb", 9), ("mar", 6)]),
    gap=1,
)
```

Available: `sparkline`, `gauge`, `progress`, `badge`, `divider`, `spinner`,
`table`, `callout`, `status_banner`, `breadcrumb`, `tabs`, `bar_chart`,
`gradient`, `heatmap`. Every color argument takes a name / `(r,g,b)` /
`"#rrggbb"` / `Color`, same as everywhere else.

### Apps: a class with decorators, no event loop

```python
from maya_py import App, card, b

app = App("counter")
app.state(n=0)

@app.on("+", "=")
def inc(s): s.n += 1

@app.on("-")
def dec(s): s.n -= 1

@app.on("q", "esc")
def quit(s): app.stop()

@app.view
def view(s):
    return card(b(f"Count: {s.n}").fg("sky"), title="counter")

app.run()
```

Key names: single chars (`"q"`, `"+"`), `"up"/"down"/"left"/"right"`,
`"enter"`, `"esc"`, `"space"`, `"tab"`, `"ctrl+c"`, `"alt+x"`, etc. Handlers
get the state object; the view re-renders every frame.

### Mouse: clicks, scroll, drag

Decorate handlers for mouse input — registering any of them auto-enables
mouse reporting (no `mouse=True` needed):

```python
from maya_py import App, card

app = App("clicker")
app.state(hits=0, pos=(0, 0))

@app.on_click("left")          # "left" / "right" / "middle" / "any"
def click(s, col, row):        # col, row are 1-based screen cells
    s.hits += 1
    s.pos = (col, row)

@app.on_scroll
def scroll(s, direction):      # -1 up, +1 down
    s.hits += direction

@app.on_mouse
def any_mouse(s, ev):          # every mouse event (press/release/move/scroll)
    ...

@app.on("q", "esc")
def quit(s): app.stop()

@app.view
def view(s):
    return card(f"clicks {s.hits}  at {s.pos}", title="clicker")

app.run()
```

Low-level predicates work on any event too: `mouse_clicked(ev, button)`,
`mouse_released(ev)`, `mouse_moved(ev)`, `scrolled_up/down(ev)`,
`mouse_pos(ev) -> (col, row) | None`, `mouse_button(ev)`, `mouse_kind(ev)`,
`is_mouse(ev)`. Mouse needs a terminal that reports it (xterm, kitty,
iTerm2, Windows Terminal, or tmux with `set -g mouse on`).

### Animation

```python
import maya_py as maya
from maya_py import animate, card

frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
n = 0
def render(dt):
    global n; n += 1
    return card(frames[n % len(frames)] + " working")
animate(render, fps=30)   # maya.quit() to stop
```

## Examples

- `examples/hello.py` — static dashboard card.
- `examples/dashboard.py` — full-power layout: sidebar + grow, z-stack badge,
  size-aware bars, partial borders.
- `examples/widgets_gallery.py` — every widget (sparkline, gauge, table,
  heatmap, ...) on one screen.
- `examples/sysmon.py` — a live system monitor: rolling sparklines, gauges,
  bar charts and a log feed, animated at 10fps.
- `examples/snake.py` — a playable Snake game (arrow keys, `App` runtime).
- `examples/paint.py` — a mouse-driven pixel painter (click/scroll/right-click).
- `examples/stopwatch.py` — live stopwatch with lap splits.
- `examples/mandelbrot.py` — a colored ASCII Mandelbrot that zooms (`component`).
- `examples/matrix.py` — falling "digital rain" animation.
- `examples/counter.py` — interactive counter (`App`).
- `examples/todo.py` — arrow-key menu with toggles (`App`).
- `examples/live_spinner.py` — inline animation (`animate`).

Run any of them:

```bash
PYTHONPATH=src python examples/todo.py
```

## Install

**The wheels are standalone — no compiler needed.** maya-py ships precompiled
binary wheels for CPython 3.9–3.14 (Linux x86_64), so on a normal machine you
just:

```bash
pip install maya-py
```

That's it — the wheel already contains the compiled extension.

<details>
<summary>Installing straight from a GitHub Release (no PyPI)</summary>

If you'd rather not use PyPI (or want a specific build), install from the
release assets. Let pip pick the right wheel for your Python:

```bash
pip install --find-links \
  https://github.com/1ay1/maya-py/releases/expanded_assets/v0.1.1 \
  maya-py
```

Or install a specific `.whl` by direct URL:

```bash
# e.g. CPython 3.13 on x86_64 Linux
pip install https://github.com/1ay1/maya-py/releases/download/v0.1.1/maya_py-0.1.1-cp313-cp313-manylinux_2_28_x86_64.whl
```

</details>

The wheel works even on machines with a **very old C++ toolchain** (or none at
all), because:

- the wheel is built inside a `manylinux_2_28` container, so it targets
  glibc 2.28 (2019) and runs on that-or-newer distros;
- it **statically links libstdc++/libgcc**, so it doesn't need the host's
  (old) C++ runtime — it depends only on baseline `libc`/`libm`.

Nothing on your machine is compiled at install time, so your system GCC
version is irrelevant.

### No matching wheel? Build from the sdist

If no prebuilt wheel matches your platform/Python, install the source
distribution — this compiles the extension locally and needs **GCC 14+** (or
Clang 18+) and CMake ≥ 3.28:

```bash
pip install \
  https://github.com/1ay1/maya-py/releases/download/v0.1.1/maya_py-0.1.1.tar.gz
```

The compile pulls maya in via CMake `FetchContent` and takes ~1–2 minutes
(it builds maya from source). If your compiler is too old, the build aborts
early with a clear, actionable message rather than a wall of template errors.

### Development build

To hack on maya-py, build the extension in place (uses a sibling `../maya-src`
checkout if present, else clones maya):

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
cp build/_maya*.so src/maya_py/
PYTHONPATH=src python examples/hello.py
```

Wheels are produced by [cibuildwheel](https://cibuildwheel.pypa.io) via
`.github/workflows/wheels.yml` — push a `vX.Y.Z` tag to build them and attach
them to a GitHub Release automatically.

## Low-level API

The friendly layer above is built on a thin primitive surface. You rarely need
it, but it's there when you want raw control. `box`/`text` take explicit
`Style`/`Color` objects:

```python
maya.box(
    maya.text("Hello", maya.bold | maya.fg(255, 128, 0)),
    border=maya.Round, padding=1,
)
```

- `text(content, style=None, wrap=...)`, `box(*children, **opts)`,
  `vstack`/`hstack`/`zstack`, `center`, `blank()`, `nothing()`.
- `box` opts mirror maya's `BoxBuilder` 1:1: `direction`, `wrap`, `gap`,
  `padding`, `margin`, `border`, `border_color`, `border_sides`,
  `border_text`, `border_text_end`, `bg`, `fg`, `style`, `overflow`, `grow`,
  `shrink`, `basis`, `align`, `align_self`, `justify`, and
  `width`/`height`/`min_*`/`max_*` (each accepts an int, `"50%"`, `"auto"`,
  or a `Dimension`).
- `component(fn, grow=..., width=..., height=...)` — a lazy element whose
  `fn(width, height)` runs once layout allocates a size and returns the tree
  to fill it.
- Styles compose with `|`: `maya.bold | maya.fg(255, 128, 0)`, or
  `maya.style(fg=(80,220,120), bold=True)`.
- `render_to_string(element, width=80)`, `print(element)`,
  `live(render_fn, fps=30)`, `run(event_fn, render_fn, ...)`.
- Event predicates: `key(ev, "q")`, `key_special(ev, SpecialKey.Up)`,
  `ctrl(ev, "c")`, `alt(ev, "x")`, `any_key(ev)`, `resized(ev)`.

## Notes

maya's compile-time DSL (`t<"...">`, type-state pipes) is resolved by the C++
compiler and can't cross the Python boundary, so `maya-py` routes everything
through maya's equivalent *runtime* builders. The element trees produced are
identical — anything the DSL can express, the runtime API can too.

The widget functions wrap maya's own widget classes (`Sparkline`, `Gauge`,
`Table`, ...) and return the Element they build, so what you see is maya's
native rendering, not a Python reimplementation. Interactive controls that
need maya's `Program` runtime + focus + signals (`Input`, `TextArea`, full
`List`/`Tree` navigation) aren't wrapped — drive interactivity from the `App`
class instead.

## Performance

Honest numbers from `examples/bench.py` and `examples/bench_live.py`
(30-row dashboard, this machine — yours will differ):

**Rendering to a string (one-shot output).** Here a tuned pure-Python
renderer *wins* — building the element tree in Python and crossing pybind11
costs more than maya's native render saves:

| path | per render |
|------|-----------|
| maya-py (build + render) | ~340 µs |
| pure-Python equivalent | ~68 µs |

~65% of maya-py's time is the Python tree construction + boundary crossing,
not maya. So **if you only render static output, a pure-Python lib like Rich
will likely be faster.**

**Live redraw to a terminal (what maya is built for).** When you redraw a
frame and only part changed, maya's SIMD cell-diff emits *only the changed
cells*. A string renderer must re-emit the whole frame:

| path | bytes written / frame |
|------|----------------------|
| maya-py (diff) | ~112 B |
| re-emit whole frame | ~1238 B |

**maya writes ~11× fewer bytes to the terminal.** On a real tty — especially
over SSH or a slow connection — bytes-on-wire is the bottleneck, and this is a
decisive win. This is the scenario maya was designed for.

### Making it fast

Two levers close most of the Python-side gap:

1. **Fluent styling is free.** `T("x").bold.fg("sky")` accumulates state in
   pure Python and makes a *single* boundary crossing when the element is
   built (4.8× faster than the naive one-call-per-`.bold` approach).

2. **`memo` caches unchanged sub-trees.** In a live app, wrap builders whose
   inputs rarely change — the hot frame then does *no* Python tree
   construction, just maya's native diff:

   ```python
   from maya_py import memo, card, col, b

   @memo
   def header(title, count):     # rebuilt only when title/count change
       return card(b(title), f"{count} items")

   def view(s):
       return col(header(s.title, len(s.items)), body(s))
   ```

**Bottom line:** you won't get "pure C++ speed" for *building* a UI in Python
— every `card(...)` is a Python call. But for the thing that actually matters
in a terminal (incremental redraws, bytes on the wire), maya-py is genuinely
fast, and `memo` lets the steady-state frame skip Python almost entirely.

## License

MIT (same as maya).
