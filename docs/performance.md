# Performance

[← Manual index](index.md)

This page is honest about where maya-py is fast, where it isn't, and how to
get the most out of it. The benchmarks come from `examples/bench.py` and
`examples/bench_live.py`; run them on your own machine for local numbers.

## The mental model

maya-py has two costs per frame:

1. **Build** — constructing the element tree in Python and crossing the
   pybind11 boundary into C++. This is pure Python interpreter work plus a
   fixed per-call cost (~300 ns/crossing). **You cannot make this run at C++
   speed** — every `card(...)` is a Python function call.
2. **Render** — maya's native layout (Yoga flexbox), cell diff (SIMD), and
   serialization. This is fast C++ and roughly flat in tree size.

The trick to speed is **doing less Build work**, because Render is already
cheap and Build is where the time goes.

## Benchmark 1: render to a string

A 30-row dashboard, rendered to a string repeatedly:

| path | per render |
|------|-----------|
| maya-py (build + render) | ~340 µs |
| tuned pure-Python equivalent | ~68 µs |

Breakdown of maya-py's 340 µs:

- ~210 µs **Build** (Python + pybind11)
- ~115 µs **Render** (native)

So **~65% of the time is the Python boundary, not maya.** For pure one-shot
string output, a well-written pure-Python renderer (e.g. Rich) can beat
maya-py, because it skips the marshalling.

**Takeaway:** if all you do is render static output once, maya-py's advantage
is small or negative. Its strength is elsewhere.

## Benchmark 2: live redraw (where maya wins)

This is what maya was built for. When you redraw a frame and only part of it
changed, maya's cell diff emits **only the changed cells**. A string renderer
must re-emit the whole frame every time.

400 frames, only one line changing each frame:

| path | bytes written per frame |
|------|------------------------|
| maya-py (diff) | ~112 B |
| re-emit whole frame | ~1238 B |

**maya writes ~11× fewer bytes to the terminal.** On a real tty — and
especially over SSH or any slow link — bytes-on-wire is the actual bottleneck,
and this is a decisive, structural win that no pure-Python library matches.

## `memo`

The single biggest lever for live-app speed. `memo` caches a built sub-tree by
its arguments: if the inputs didn't change, it returns the **same** `Element`
object instead of rebuilding it in Python.

```python
from maya_py import memo, card, col, b

@memo
def header(title, count):          # rebuilt only when title/count change
    return card(b(title), f"{count} items")

def view(s):
    return col(header(s.title, len(s.items)), body(s))
```

When `header`'s args are unchanged across frames, the hot frame does **no
Python tree construction** for that sub-tree — it hands maya the cached
`Element`, and maya's diff takes over. The steady-state frame approaches
"native render only".

### How `memo` works

- It's a decorator returning a callable that remembers `(args) -> Element`.
- On each call it compares the new positional args to the cached key with
  `!=`. If equal, returns the cached element; otherwise rebuilds and re-caches.
- **Args must be comparable** (ints, strings, tuples — not unhashable mutable
  objects you mutate in place). Pass *values*, not the whole state object:
  `header(s.title, len(s.items))`, not `header(s)`.

### When to use it

- Headers, footers, legends, help bars — anything that changes rarely.
- Large static tables where only a cursor or a counter moves.
- Any sub-tree whose inputs are a small, comparable summary of state.

### When *not* to

- Sub-trees that change every frame anyway (memo just adds a comparison).
- Builders whose args aren't cheaply comparable.

## Fluent styling is already optimized

`T("x").bold.fg("sky")` accumulates state in pure Python and makes a **single**
boundary crossing when the element is built — 4.8× faster than the naive
"one pybind call per `.bold`/`.fg`" approach. The built element is then cached
on the `T`. You don't need to do anything special; just use `T` and the markup
helpers.

```
T("x").bold.fg("sky")     # 346 ns  (was 1649 ns before the optimization)
```

## Practical fast-frame checklist

1. Use `T` / markup helpers for styling (already cheap).
2. Wrap rarely-changing sub-trees in `@memo`.
3. Pass *comparable summaries* to memoized builders, not mutable state.
4. For animations, let maya's diff do the work — don't clear and re-render
   manually.
5. Don't render to a string in a hot loop if you can render live (the diff is
   the whole point).

## Reproducing the numbers

```bash
PYTHONPATH=src python examples/bench.py --rows 30 --iters 3000
PYTHONPATH=src python examples/bench_live.py --frames 400 --rows 20
```

`bench.py` reports the build/render split and the string-render comparison.
`bench_live.py` reports bytes-on-wire for the live diff path.

## Honest bottom line

- **Building UI in Python has a floor** you can't remove — interpreter
  overhead per call. maya-py won't make tree construction C++-fast.
- **For the thing that matters in a terminal** — incremental redraws and bytes
  on the wire — maya-py is genuinely fast, and `memo` lets the steady-state
  frame skip Python almost entirely.

## Next

- [Low-Level API](low-level.md) — the primitives under the easy layer.
- [API Reference](api-reference.md) — every symbol at a glance.
