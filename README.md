# maya-py

Python bindings for [**maya**](https://github.com/1ay1/maya) — a C++26 TUI
framework with flexbox layout, a SIMD cell-diff renderer, and an Elm-style
runtime. `maya-py` exposes maya's runtime element-builder surface so you can
build styled terminal UIs, render them inline or fullscreen, and drive
interactive apps from plain Python callbacks.

```python
import maya_py as maya

ui = maya.box(
    maya.text("Hello World", maya.bold | maya.fg(100, 180, 255)),
    maya.box(
        maya.text("Status:", maya.dim),
        maya.text("Online", maya.bold | maya.fg(80, 220, 120)),
        gap=1,
    ),
    border=maya.Round, padding=1,
)
maya.print(ui)
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

## API

### Elements

- `text(content, style=None, wrap=TextWrap.Wrap)` — a styled text leaf.
- `box(*children, **opts)` — a flex container. Children may be Elements or
  plain strings (auto-wrapped). Strings stack along the box direction.
- `vstack(*children, **opts)` / `hstack(*children, **opts)` — box with the
  direction fixed to Column / Row.
- `blank()` — a one-row spacer.

`box` keyword options: `direction`, `gap`, `padding` (int or 2/4-tuple),
`margin`, `border`, `border_color`, `border_text`, `bg`, `fg`, `grow`,
`align`, `justify`, `width`, `height`.

### Styles & colors

Compose styles with `|`:

```python
maya.bold | maya.fg(255, 128, 0)
maya.style(fg=(80, 220, 120), bold=True, underline=True)
```

- Flags: `maya.bold`, `maya.dim`, `maya.italic`, `maya.underline`,
  `maya.strikethrough`, `maya.inverse`.
- `fg(...)` / `bg(...)` accept `(r, g, b)`, three ints, a hex int, or a `Color`.
- `rgb(r, g, b)`, `hex(0xRRGGBB)`, and named `Color.cyan()` etc.

### Rendering

- `print(element, width=None)` — render to stdout (one-shot). Plain strings
  fall through to the builtin `print`.
- `render_to_string(element, width=80)` — render to a plain string (no tty).
- `live(render_fn, fps=30)` — inline animation loop. `render_fn(dt)` returns
  an Element each frame; call `maya.quit()` to stop.
- `run(event_fn, render_fn, title="", inline_mode=False, mouse=False, fps=0)`
  — interactive event loop. `event_fn(ev)` returns `False` to quit;
  `render_fn()` returns the current Element.

### Events

Inside `run`'s `event_fn`, match input with `key(ev, "q")`,
`key_special(ev, SpecialKey.Up)`, `ctrl(ev, "c")`, `alt(ev, "x")`,
`any_key(ev)`, `resized(ev)`.

## Examples

- `examples/hello.py` — static styled card.
- `examples/counter.py` — interactive counter (`run`).
- `examples/live_spinner.py` — inline animation (`live`).

## Notes

maya's compile-time DSL (`t<"...">`, type-state pipes) can't cross the Python
boundary, so `maya-py` routes everything through maya's equivalent runtime
builders. The element trees produced are identical.

## License

MIT (same as maya).
