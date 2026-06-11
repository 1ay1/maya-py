# Getting Started

[← Manual index](index.md)

## Requirements

**To install a prebuilt wheel: nothing special.** maya-py ships precompiled
standalone wheels, so you don't need a C++ compiler at all — not even an old
one. See [Installing](#install) below.

**To build from source** (only if no wheel matches your platform):

- A **C++26 compiler** — GCC 15 or newer. maya itself is compiled from source.
- **CMake ≥ 3.28**.
- **Python ≥ 3.9**.

maya-py pulls maya in at build time (via CMake `FetchContent`, or from a
sibling `../maya-src` checkout if one exists), so you don't install maya
separately.

## Install

### Prebuilt wheel (recommended — no compiler)

> **Not on PyPI yet.** `pip install maya-py` by bare name fails until the
> package is published. Install from the GitHub Releases:

```bash
pip install --find-links \
  https://github.com/1ay1/maya-py/releases/expanded_assets/v0.1.2 \
  maya-py
```

This lets pip pick the right wheel (CPython 3.9–3.14, Linux x86_64) from the
release's asset list. The wheel contains the already-compiled extension. It
runs on machines with a very old (or no) C++ toolchain because it's built
against an old glibc (`manylinux_2_28`, 2019) and statically links the C++
runtime. Your system GCC version doesn't matter — nothing is compiled at
install time.

No matching wheel? Install the source distribution (compiles locally, needs
GCC 14+ / Clang 18+ and CMake ≥ 3.28):

```bash
pip install \
  https://github.com/1ay1/maya-py/releases/download/v0.1.2/maya_py-0.1.2.tar.gz
```

If your compiler is too old the build aborts early with a clear message.

### From the repo (building from source)

```bash
git clone git@github.com:1ay1/maya-py.git
cd maya-py
pip install .
```

`pip` invokes scikit-build-core, which runs CMake, compiles maya + the
extension, and installs the `maya_py` package.

### In-place dev build (no pip)

If you're hacking on maya-py itself:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
cp build/_maya*.so src/maya_py/
PYTHONPATH=src python examples/hello.py
```

The `cp` step copies the compiled `.so` next to the Python package so
`PYTHONPATH=src` can import it.

## Your first UI

A "UI" is just a tree of elements rendered to the terminal. The easiest entry
point is `show`, which renders once and returns:

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

Output:

```
╭ service ───────────╮
│                    │
│ maya-py            │
│ ────────────────── │
│ Status: Online     │
│ Region: us-east-1  │
│                    │
╰────────────────────╯
```

Things to notice:

- **Strings are UI.** `"us-east-1"` is passed directly — no wrapping needed.
- **`b("maya-py").fg("sky")`** is a styled string (bold + a named color).
- **`card(...)`** is a bordered, padded box. `title=` puts text on the border.
- **`field("Status", "Online")`** renders `Status: Online` with a dim label.

## Your first app

An interactive app is a class with decorators. No event loop to write:

```python
from maya_py import App, card, b, dim_text

app = App("counter", inline=True)
app.state(n=0)


@app.on("+", "=")
def inc(s):
    s.n += 1


@app.on("-")
def dec(s):
    s.n -= 1


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    return card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("+/- change   q quit"),
        title="counter",
    )


app.run()
```

How it works:

- **`app.state(n=0)`** seeds mutable state. Handlers receive it as `s`.
- **`@app.on("+", "=")`** binds keys to a handler. Handlers mutate `s`.
- **`@app.view`** registers the render function. It runs every frame and
  returns the current UI from state.
- **`app.run()`** starts the loop; `app.stop()` ends it.

`inline=True` keeps the app in your scrollback (like Claude Code). Drop it
(or pass `inline=False`) for a fullscreen alt-screen app.

## Running the examples

The repo ships several:

```bash
PYTHONPATH=src python examples/hello.py          # static dashboard
PYTHONPATH=src python examples/counter.py        # interactive counter
PYTHONPATH=src python examples/todo.py           # arrow-key menu
PYTHONPATH=src python examples/live_spinner.py   # animation
PYTHONPATH=src python examples/bench.py          # render benchmark
PYTHONPATH=src python examples/bench_live.py     # diff/bytes benchmark
```

## Next

- [Text & Style](text-and-style.md) — make strings beautiful.
- [Layout](layout.md) — arrange them.
- [Apps](apps.md) — the full `App` reference.
