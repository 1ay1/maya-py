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

`col` / `row` / `card` keywords: `border` (`"round"`/`"double"`/...), `pad`,
`gap`, `title`, `border_color`, `bg`, `align`, `justify`, `width`, `height`,
`grow`.

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
- `examples/counter.py` — interactive counter (`App`).
- `examples/todo.py` — arrow-key menu with toggles (`App`).
- `examples/live_spinner.py` — inline animation (`animate`).

Run any of them:

```bash
PYTHONPATH=src python examples/todo.py
```

## Install

> **Not on PyPI yet** — `pip install maya-py` (by bare name) does **not** work
> until the package is published to PyPI. Install from the GitHub Releases
> instead, using one of the commands below.

**The wheels are standalone — no compiler needed.** maya-py ships precompiled
binary wheels for CPython 3.9–3.14 (Linux x86_64). The easiest path lets pip
pick the right wheel for your Python from the release's asset list:

```bash
pip install --find-links \
  https://github.com/1ay1/maya-py/releases/expanded_assets/v0.1.1 \
  maya-py
```

Or install a specific `.whl` by direct URL (no `--find-links` needed):

```bash
# e.g. CPython 3.13 on x86_64 Linux
pip install https://github.com/1ay1/maya-py/releases/download/v0.1.1/maya_py-0.1.1-cp313-cp313-manylinux_2_28_x86_64.whl
```

The wheel already contains the compiled extension. It works even on machines
with a **very old C++ toolchain** (or none at all), because:

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
  `vstack`/`hstack`, `blank()`.
- Styles compose with `|`: `maya.bold | maya.fg(255, 128, 0)`, or
  `maya.style(fg=(80,220,120), bold=True)`.
- `render_to_string(element, width=80)`, `print(element)`,
  `live(render_fn, fps=30)`, `run(event_fn, render_fn, ...)`.
- Event predicates: `key(ev, "q")`, `key_special(ev, SpecialKey.Up)`,
  `ctrl(ev, "c")`, `alt(ev, "x")`, `any_key(ev)`, `resized(ev)`.

## Notes

maya's compile-time DSL (`t<"...">`, type-state pipes) can't cross the Python
boundary, so `maya-py` routes everything through maya's equivalent runtime
builders. The element trees produced are identical.

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
