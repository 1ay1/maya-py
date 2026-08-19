# Changelog

All notable changes to maya-py are recorded here. Versions follow
[semantic versioning](https://semver.org/) (though the API is young and the
minor series may still shift).

## 0.3.1

The performance release: element **build now flattens entirely in C++**.

### Changed

- **Native spec-flattening engine.** `row()`/`col()`/`rows()` hand their raw
  children straight to new native entry points (`stack_specs`/`rows_specs`):
  palette-name resolution (`"sky"` → packed RGB, `#hex` parsed and memoised
  natively), tuple-spec parsing, `T`-slot reads, and box construction all
  happen in one C++ call per container — **zero per-cell Python**. The
  palette, the `T` class, and the slow-path colour resolver are registered
  once at import (`_register_specs`); anything the native side doesn't
  recognise (a `T` carrying a `Color` object, exotic types) falls back to
  the old Python path with identical semantics. Output is byte-identical
  (golden verified).
- Benchmarks (30-row dashboard, `examples/bench.py`): the `rows()` idiom
  build dropped ~99 µs → ~39 µs; full build+render ~147 µs → ~83 µs —
  within ~20% of a bespoke pure-Python ANSI concatenator that does no
  layout at all, and **~76× faster than Rich** (geometric mean over
  dashboard / log-flood / table workloads, `examples/bench_vs_rich.py`).

### Added

- `examples/bench_vs_rich.py` — honest head-to-head against Rich on three
  identical workloads (dashboard, 200-line log flood, 100×6 table).
- `examples/bench.py` now reports the `rows()` idiom variant.

## 0.3.0

Synced with the latest **maya** master (123 upstream commits) and bound the
new API surface: the responsive layout toolkit, the paint-time mouse hit
registry, the table overhaul, and hover-motion mouse reporting.

### Added

- **Responsive layout toolkit** (new `maya_py.layout` module, re-exported at
  the top level). Width-aware building blocks that re-solve themselves live
  on every terminal resize:
    - `grid(cells, min)` — auto-flow grid: as many `min`-wide cells per row
      as fit, wraps the rest, stacks to one column when narrow. One number
      is the whole API.
    - `sidebar(rail, main, width)` — fixed-width rail beside a main pane;
      stacks vertically when the slot is too narrow.
    - `fit_row(...)` / `fit_col(...)` — rows/columns that **drop** optional
      items (tagged `(el, keep)`, lower sheds first) when space runs out.
    - `pick(rich, medium, tiny)` — semantic zoom: the first alternative
      that fits the width wins; the last is the fallback.
    - `place(child, h, v)` — the 9-position grid (center a dialog, corner a
      toast) inside the slot flex gives the wrapper.
    - `clamp_width(el, max)` — cap content width on ultrawide terminals and
      center it (libadwaita's AdwClamp, for terminals).
    - `adapt(fn)` / `fill(fn)` — custom width-aware / slot-filling
      components driven by a Python callable receiving the real slot size.
    - `measure(el)` — an Element's natural `(width, height)`, the primitive
      the whole toolkit is built on.
- **Pretty text.** `rainbow(text)` (HSL hue sweep) and
  `gradient_rule(*stops, glyph="─")` (a full-width gradient divider that
  spans whatever width it is given).
- **Paint-time mouse hit registry.** Tag any box with `hit=hit_id(kind, i)`
  and the *renderer* records its absolute painted rect each frame;
  `hit_test(x, y)` resolves a mouse event to the topmost id and
  `hit_rect(id)` anchors popups to a target. Correct by construction — no
  hand-mirrored layout math. (`hit_kind` / `hit_index` unpack the id.)
- **Table overhaul** (mirrors maya's htop-grade `Table`): `selected=` draws
  the ▎ selection cursor (+ optional `selected_bg` band), `sort_col=` /
  `sort_desc=` render the ▾/▴ sort indicator, `visible_rows=` fixes the
  body height and windows around the cursor with a scrollbar
  (`window_top=` pins it, `show_scrollbar=False` hides the gutter), and
  dict columns `{header, width, align, keep, weight, min_width, max_width}`
  get responsive weighted sizing — whole columns shed lowest-`keep` first
  when the table is too narrow instead of shearing mid-cell.
- **Hover motion.** `App(hover_motion=True)`, `run(...)`,
  `run_program(...)`, and `Program.hover_motion` enable mouse mode 1003 so
  bare (no-button) motion reaches your handlers for hover highlights.
- **Deterministic clock pinning.** `freeze_anim_clock(at_ms)` /
  `unfreeze_anim_clock()` pin maya's animation clock at an absolute value
  for reproducible headless renders (`advance_anim_clock_ms` remains the
  additive form).

### Changed

- Rebuilt against maya master with the new engine internals: the streaming
  reveal/scrollback fixes, the O(chunk) streaming-markdown renderer, TeX
  math rendering in markdown (`$$ … $$`, `\boxed`, arrays, norms), the
  signal-graph diamond-double-fire fix, DEL/C1 control-code filtering, and
  the render-scaling performance pass all come along for free.
- The mouse-off guard emitted on every exit path now also disables mode
  1003 (hover motion).

## 0.2.13

Rebuilt against the latest **maya** (`master`, C++26 core) and hardened the
widget bindings.

### Fixed

- **Use-after-free in four stateful widgets.** maya's `List`, `Menu`,
  `SearchResult`, and `CommandPalette` now build lazily — their
  `operator Element()` returns an element that captures `this`. The Python
  bindings previously returned a *stack-local* widget, so the resulting element
  held a dangling pointer that was dereferenced at render time
  (`MemoryError: std::bad_alloc` / `vector::reserve`). Each widget is now
  heap-owned and kept alive for the element's whole lifetime.
  Affected factories: [`list_view`](widgets.md), [`menu`](widgets.md),
  [`search_result`](widgets.md), [`command_palette`](widgets.md).

### Added

- **`Align.Auto` / `align_self="auto"`.** The default cross-axis value for a
  child; it inherits the container's `align`. See
  [Layout → align](layout.md#align-cross-axis-alignment).

## 0.2.11

- Prior release. See the
  [GitHub releases](https://github.com/1ay1/maya-py/releases) for the full
  history of earlier versions.
