# maya-py Reference Manual

Complete documentation for **maya-py** — Python bindings for the
[maya](https://github.com/1ay1/maya) C++26 TUI framework.

maya-py gives you two layers:

- **The easy API** (`maya_py.col`, `card`, `T`, `App`, …) — the recommended
  surface. Strings are UI, styling is fluent, apps are a class with
  decorators. This is what 95% of code should use.
- **The low-level API** (`maya_py.box`, `text`, `Style`, `Color`, `run`, …) —
  thin pybind11 wrappers over maya's runtime element builders, for when you
  want explicit control.

Everything in the easy API is built on the low-level API, so you can mix them
freely.

## Table of contents

1. [Getting Started](getting-started.md) — install, your first UI, your first app.
2. [How It Works (Concepts)](concepts.md) — the mental model the whole manual rests on.
3. [Text & Style](text-and-style.md) — `T`, markup helpers, colors.
4. [Layout](layout.md) — `col`, `row`, `card`, `field`, `hr`, `spacer`, and all box options.
5. [Responsive & Mouse](responsive.md) — `grid`/`sidebar`/`fit_row`/`pick` layouts that re-solve on resize, plus the paint-time mouse hit registry.
6. [Apps](apps.md) — the `App` class, key bindings, state, the view function.
7. [The Program model (MVU)](program.md) — pure `init`/`update`/`view`/`subscribe`, `Cmd` effects, `Sub` sources — the same model as C++ `run<P>`.
8. [Widgets](widgets.md) — 80+ native renderers: charts, controls, tables, agent UI, scrolling.
9. [Rendering](rendering.md) — `show`, `to_string`, `animate`, `live`, `run`.
10. [Performance](performance.md) — `memo`, the boundary tax, benchmarks, fast patterns.
11. [API Reference](api-reference.md) — every public symbol, one table.
12. [Low-Level API](low-level.md) — primitives, enums, the native binding.
13. [Distribution & Standalone Wheels](distribution.md) — how it installs without a compiler.

## A complete example

```python
from maya_py import App, card, col, row, field, b, c, T, hr, memo

app = App("dashboard", inline=True)
app.state(services=[("api", True), ("db", True), ("cache", False)], cursor=0)


@app.on("up")
def up(s):
    s.cursor = (s.cursor - 1) % len(s.services)


@app.on("down")
def down(s):
    s.cursor = (s.cursor + 1) % len(s.services)


@app.on("q", "esc")
def quit_(s):
    app.stop()


@memo
def header(healthy, total):
    return col(b("Service Health").fg("sky"), field("Up", f"{healthy}/{total}"), hr(30))


@app.view
def view(s):
    healthy = sum(1 for _, ok in s.services if ok)
    rows = []
    for idx, (name, ok) in enumerate(s.services):
        status = c("● up", "green") if ok else c("● down", "red")
        label = T(name).fg("sky").bold if idx == s.cursor else T(name)
        rows.append(row(c("›", "sky") if idx == s.cursor else " ", label, status, gap=2))
    return card(header(healthy, len(s.services)), col(*rows), title="health")


app.run()
```

## Conventions used in this manual

- `node` means anything renderable: a `str`, a `T`, or an `Element`.
- "boundary crossing" / "pybind call" means a call from Python into the
  compiled C++ extension. These have a fixed cost (~300 ns); the easy API is
  designed to minimize them.
- Code blocks assume `from maya_py import ...` or `import maya_py as maya`.

## Versions

This manual documents maya-py **0.3.1**. The API is young and may change.
