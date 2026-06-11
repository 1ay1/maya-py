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

Requires a C++26 compiler (GCC 15+) and CMake ≥ 3.28 — maya itself is compiled
from source on install (pulled via CMake `FetchContent`, or from a sibling
`../maya-src` checkout if present).

```bash
pip install .
```

For development, build the extension in place:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
cp build/_maya*.so src/maya_py/
PYTHONPATH=src python examples/hello.py
```

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

## License

MIT (same as maya).
