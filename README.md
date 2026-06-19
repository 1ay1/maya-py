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

A full reference manual lives in [`docs/`](https://1ay1.github.io/maya-py/):

- [Getting Started](https://1ay1.github.io/maya-py/getting-started/) — install, first UI, first app.
- [How It Works (Concepts)](https://1ay1.github.io/maya-py/concepts/) — the mental model: render pipeline, runtimes, performance, pitfalls.
- [Text & Style](https://1ay1.github.io/maya-py/text-and-style/) — `T`, markup helpers, colors.
- [Layout](https://1ay1.github.io/maya-py/layout/) — `col`, `row`, `card`, `field`, `hr`, options.
- [Apps](https://1ay1.github.io/maya-py/apps/) — the `App` class, key bindings, state, the view.
- [Widgets](https://1ay1.github.io/maya-py/widgets/) — 58 native renderers: charts, controls, agent UI, scrolling.
- [Rendering](https://1ay1.github.io/maya-py/rendering/) — `show`, `to_string`, `animate`, `run`.
- [Performance](https://1ay1.github.io/maya-py/performance/) — `memo`, the boundary tax, benchmarks.
- [API Reference](https://1ay1.github.io/maya-py/api-reference/) — every public symbol.
- [Low-Level API](https://1ay1.github.io/maya-py/low-level/) — primitives and the native binding.
- [Distribution](https://1ay1.github.io/maya-py/distribution/) — standalone wheels for old machines.

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

Available — every color argument takes a name / `(r,g,b)` / `"#rrggbb"` /
`Color`, same as everywhere else:

- **charts & meters**: `sparkline`, `gauge`, `progress`, `bar_chart`,
  `line_chart`, `heatmap`, `flame_chart`, `waterfall`
- **controls** (rendered in any state — pass `checked`/`on`/`selected`/`cursor`):
  `checkbox`, `toggle`, `radio`, `select`, `slider`, `button`
- **text & labels**: `badge`, `divider`, `spinner`, `callout`, `status_banner`,
  `breadcrumb`, `tabs`, `gradient`, `link`, `title_chip`, `model_badge`,
  `file_ref`, `markdown`
- **structure & nav**: `table`, `tree`, `list_view`, `menu`, `disclosure`,
  `key_help`, `calendar`, `timeline`, `picker` (bordered command palette)
- **agent UI**: `thinking`, `todo_list`, `toast`, `inline_diff`,
  `tool_call`, `plan_view`, `phase_chip`, `context_gauge`, `context_window`,
  `diff_view`, `git_graph`, `git_status`, `shortcut_row`, `system_banner`,
  `popup`, `overlay`, `user_message`, `assistant_message`
- **graphics**: `image` (1-bit braille), `canvas` (color half-block grid),
  `Canvas` (imperative drawing surface: `set_pixel`/`line`/`rect`/`fill`)

```python
from maya_py import col, row, checkbox, slider, todo_list, timeline, tree

col(
    checkbox("Ship it", checked=True),
    slider(0.6, "volume", width=24, fill="sky"),
    todo_list([("design", "completed"), ("build", "in_progress"), "test"],
              description="sprint", status="running"),
    timeline([("clone", "", "0.4s", "completed"),
              ("compile", "", "", "in_progress", 8)]),
    tree({"label": "src", "expanded": True,
          "children": [{"label": "main.py"}, {"label": "util.py"}]}),
    gap=1,
)
```

List/tuple inputs are flexible: list items accept `"str"`,
`(label, description, icon)`, or `{...}` dicts; timeline/todo statuses accept
strings (`"completed"`, `"in_progress"`, ...) or the exported enums
(`TaskStatus`, `TodoItemStatus`, `ToastLevel`, `ButtonVariant`,
`ToolCallKind`, `ToolCallStatus`, `PopupStyle`, `BannerLevel`).

### Scrolling: viewport + scrollbar

Clip tall/wide content to a window and pair it with a live scrollbar.
Scrolling **just works with no handler code** — exactly like maya, the run
loop auto-forwards ↑↓ / PgUp / PgDn / Home / End and the mouse wheel + scrollbar
drag to every on-screen scroll state:

```python
from maya_py import App, col, row, T, scroll_state, viewport, scrollbar

app = App("log", mouse=True)            # mouse=True for wheel + thumb drag
s = scroll_state()                      # auto-dispatch on (the maya default)
app.state(s=s)
content = col(*[T(f"line {i}") for i in range(200)])

@app.on("q", "esc")
def quit(st): app.stop()

@app.view
def view(st):
    return row(
        viewport(content, st.s, height=14, grow=1),   # 14-row window, fills width
        scrollbar(st.s, 14, style="neon", thumb_color="sky"),
        gap=1,
    )

app.run()
```

That's the whole thing — no scroll handler. `viewport(content, state, width=,
height=, grow=)` clips + scrolls (0 on an axis = fill; `grow=1` expands to fill
its row/column so a sibling scrollbar pins to the edge).
`scrollbar(state, size, axis="y"|"x", style=, thumb_color=, track_color=)` draws
the bar; `style` is a preset name — `line`, `block`, `slim`, `heavy`, `double`,
`dotted`, `dashed`, `braille`, `ascii`, `shadow`, `minimal`, `neon`, `retro`,
`danger`, `pixel`. The `ScrollState` exposes `x`/`y`/`max_x`/`max_y`,
`scroll_by`, `scroll_to`, `scroll_to_top/bottom`, `at_top()`/`at_bottom()`, and
`viewport_bounds` (the painted rect, for click hit-testing).

Need custom routing (several independent scroll regions)? Set
`state.auto_dispatch = False` and call `scroll_handle(state, ev)` yourself
inside `@app.on_key` / `@app.on_mouse`. Don't do both — that double-scrolls.

### Apps: a class with decorators, no event loop

```python
from maya_py import App, card, b

app = App("counter", n=0, quit_keys=("q", "esc"))   # state + quit in the constructor

@app.on("+", "=")
def inc(s): s.n += 1

@app.on("-")
def dec(s): s.n -= 1

@app.view
def view(s):
    return card(b(f"Count: {s.n}").fg("sky"), title="counter")

app.run()
```

Key names: single chars (`"q"`, `"+"`), `"up"/"down"/"left"/"right"`,
`"enter"`, `"esc"`, `"space"`, `"tab"`/`"shift+tab"`, `"home"/"end"`,
`"pgup"/"pgdn"`, `"insert"/"delete"`, `"f1"`–`"f12"`, and modifier prefixes
`"ctrl+s"`, `"alt+x"`, `"shift+a"`. A **typo'd key spec raises** with a
did-you-mean hint instead of silently never firing. Handlers
get the state object; the view re-renders every frame.

### Text input

Real interactive `Input` widgets — type into them, `Tab` between them, read
`.value`. Register them with `app.focus(...)` and drop them in the view:

```python
from maya_py import App, text_input, col

app = App("search")
query = text_input("type to filter…")
app.focus(query)

@app.view
def view(s):
    return col(query, f"searching: {query.value}")

app.run()
```

`text_input(password=True)` masks, `textarea()` is multi-line. `@query.on_submit`
fires on Enter. An animation tick is `@app.on_frame def tick(s, dt): ...`.

### Declarative state: `For`, `bind`, `@app.derive`

The view is a pure function of state, so the whole UI reads top-to-bottom.
Three helpers kill the last of the glue — list comprehensions, widget
read-back, and recomputed fields:

```python
from maya_py import App, text_input, card, col, For

app = App("cart", items=[("Pen", 2.0), ("Mug", 9.5)], name="")

# 1) @app.derive — a computed field, recomputed on access (no stale cache):
@app.derive
def total(s): return sum(price for _, price in s.items)

# 2) bind=(state, field) — the input mirrors a state field both ways, so the
#    view reads s.name directly and never touches widget.value:
name = text_input("your name…", bind=(app.s, "name"))
app.focus(name)

@app.view
def view(s):
    return card(
        # 3) For(...) maps a list into a box — like SwiftUI ForEach / JSX map.
        #    A two-param renderer gets (index, item) for free.
        For(s.items, lambda it: col(f"{it[0]}  ${it[1]:.2f}")),
        col("Name:", name, f"hello {s.name}"),
        f"Total: ${s.total:.2f}",
        title="cart",
    )

app.run()
```

- **`For(items, render, *, into=col, empty=None, **opts)`** — map a sequence
  into a container. `render(item)` or `render(index, item)` (auto-detected).
  `empty=` shows a fallback when the list is empty.
- **`text_input(..., bind=(state, "field"))`** — two-way binding: the field
  seeds the input and every keystroke writes back. No `.value` plumbing.
- **`@app.derive`** — install `fn(state)` as a read-only computed property on
  the state object. Works with the default state bag *and* `model=` objects.

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

### The Elm Architecture: `Program` (pure, testable, no mutation)

When you want the full discipline — an immutable `Model`, a closed set of
`Msg`, a **pure** `update`, and side effects described as data — maya-py
exposes maya's native MVU runtime as a `Program`. This is the *same* `run<P>`
loop the C++ side uses, so the effects and subscriptions you return from
Python are interpreted by maya's real runtime, not a reimplementation.

```python
import maya_py as maya
from maya_py import Cmd, Sub, Program, card, T

class Counter(Program):
    title = "counter"

    def init(self):                       # -> model | (model, Cmd)
        return {"n": 0}, Cmd.set_title("counter")

    def update(self, m, msg):             # pure: no I/O, no mutation
        if msg == "inc":   return {**m, "n": m["n"] + 1}
        if msg == "dec":   return {**m, "n": m["n"] - 1}
        if msg == "quit":  return m, Cmd.quit()
        return m

    def view(self, m):                    # model -> Element
        return card(T(f"count: {m['n']}").bold)

    def subscribe(self, m):               # model -> event sources
        return Sub.on_key(lambda ev:
            "inc" if maya.key(ev, "+") else
            "dec" if maya.key(ev, "-") else
            "quit" if maya.key(ev, "q") else None)

Counter().run()
```

`update` never touches the terminal, so it stays a pure state transition you
can unit-test in isolation. Effects are **`Cmd`** values — `Cmd.quit()`,
`Cmd.set_title(...)`, `Cmd.after(ms, msg)`, `Cmd.task(fn)` (async work),
`Cmd.batch(...)`, clipboard + scrollback commands. Event sources are **`Sub`**
values — `Sub.on_key`, `Sub.on_mouse`, `Sub.on_resize`, `Sub.on_paste`,
`Sub.every(ms, msg)` (a timer), `Sub.on_animation_frame(msg)`, `Sub.batch(...)`.
There's a plain-function form too: `run_program(init, update, view, subscribe)`.

**The whole architecture is headlessly testable.** Because `update` is pure,
`Program.test()` hands you a `ProgramPilot` that runs the real
`init`/`update`/`view` with no terminal — you dispatch *messages* (exactly like
`elm-test`), thread the immutable model, and assert on it and the rendered view:

```python
p = Counter().test()
p.send("inc", "inc", "inc", "dec")        # dispatch messages in order
assert p.model == {"n": 2}
assert p.cmds                              # Cmd.set_title was emitted at init
assert "count: 2" in p.view_string(40)
```

**Purity is enforced, not just encouraged.** The pilot runs in strict mode by
default: it snapshots the model before every `update`/`view` and raises
`ImpureUpdateError` if a hook mutated it in place instead of returning a new
one. So the moment someone writes the tempting `m["n"] += 1; return m`, their
tests fail loudly with a pointer to the exact hook — the beautiful, pure
architecture is the *verified* one, and the subtle stale-view bug never ships:

```python
class Sloppy(Program):
    def update(self, m, msg):
        m["n"] += 1        # in-place mutation — the TEA sin
        return m
    ...

Sloppy().test().send("inc")   # raises ImpureUpdateError: update() mutated the
                              # model in place. Return a NEW model ({**m, ...}).
```

The check costs nothing at runtime (it lives in the test pilot), and there's an
escape hatch — `prog.test(strict=False)` — for an intentionally huge or
un-deep-copyable model.

See `examples/counter_program.py` and `examples/stopwatch_program.py` (the
latter uses `Sub.every` timers, `Sub.batch`, and `Cmd.batch`, and ships a
`--test` self-check that proves every transition with the pilot).

## Examples

**Every maya C++ example is ported 1:1 to Python** — 34 of them, plus extras.
Most are full apps you can drive; run any with `PYTHONPATH=src python
examples/NAME.py`. A headless `examples/smoke_all.py` renders one frame of
each (CI-friendly, no TTY needed).

**Games & toys** (half-block pixel rendering via `examples/_halfblock.py`):

- `snake.py` — playable Snake (arrow keys / WASD).
- `breakout.py` — Breakout/Arkanoid with bricks, comet trail, particles.
- `life.py` — Conway's Game of Life with heat-aging palettes + patterns.
- `sorts.py` — five sorting algorithms racing side by side.
- `maze.py` — watch a maze carve itself (recursive backtracker) then a BFS
  flood-solve it; **click to set the start cell, right-click the goal**.

**Graphics & sims** (`animate` / `App` render loops):

- `doom_fire.py` — the classic Doom fire effect, 3 palettes.
- `fluid.py` — advection fluid / plasma with curl-noise velocity.
- `particles.py` — a gravity particle fountain.
- `space.py` — warp-speed starfield. `space3d.py` — rotating 3D wireframes.
- `raymarch.py` — a real-time raymarched SDF scene (sphere + plane).
- `fps.py` — a Wolfenstein-style textured raycaster with a minimap.
- `mandelbrot.py` — a zooming coloured Mandelbrot. `matrix.py` — digital rain.
- `canvas.py` — the `Canvas` drawing surface: lines, rects, a live plot.
- `clock.py` — a live analog clock drawn on the `Canvas` (hands, ticks, arc).
- `gravity.py` — an n-body gravity sandbox; **mouse-hover crosshair, click to
  spawn an orbiting burst** at the exact pixel.
- `boids.py` — Reynolds flocking; **the mouse leads or scatters the flock**
  (precise, viewport-bounds hit-testing — no hardcoded offsets).

**Dashboards & data:**

- `dashboard.py` — full-power layout (sidebar, z-stack, size-aware bars).
- `sysmon.py` — live system monitor (sparklines, gauges, log feed).
- `stocks.py` — stock ticker with sparklines + a gainers board.
- `spectrum.py` — a faux audio spectrum analyzer. `music.py` — a player UI.
- `hacker.py` — a "hollywood hacker" terminal of fake breaches.

**Apps & agent UI:**

- `deploy.py` — a CI/CD pipeline dashboard with a live stage timeline.
- `chat.py` — a chat client with bubbles + typing indicator.
- `messenger.py` — multi-channel chat with unread badges + a composer.
- `ide.py` — a VS Code / Zed-style mini IDE (tree, tabs, diagnostics, git).
- `agent.py` / `agent_session.py` — Claude-Code-style agent sessions:
  thinking → tool cards → todo plan → streaming markdown answer.
- `widgets.py` — one-shot widget showcase. `widgets_gallery.py` — live version.
- `markup.py` — a GFM markdown render that flows into scrollback (pipe to `less -R`).
- `inline_progress.py` — inline `print` + `live` (no alt-screen takeover).

**Primitives & basics:**

- `hello.py` static card · `counter.py` / `stopwatch.py` / `todo.py` `App`
  basics · `paint.py` mouse painter · `live_spinner.py` inline animation.
- `counter_program.py` / `stopwatch_program.py` — the pure **MVU `Program`**
  (Elm Architecture): immutable model, pure `update`, `Cmd`/`Sub` effects, and
  a headless `--test` self-check.
- `form.py` — the declarative trio (`For`, `bind=`, `@app.derive`) in one cart.
- `scroll.py` / `scroll_clip.py` / `scroll_2d.py` / `scroll_slice.py` /
  `scroll_styles.py` — every scrolling pattern (clip, two-axis, million-row
  slice, and all 15 scrollbar styles).

Run any of them:

```bash
PYTHONPATH=src python examples/agent_session.py
```

## Install

**The wheels are standalone — no compiler needed.** maya-py ships precompiled
binary wheels for CPython 3.9–3.14 on **Linux** (x86_64; aarch64 configured),
**Windows** (x64), and **macOS** (Apple Silicon / arm64), so on a normal
machine you just:

```bash
pip install maya-py
```

That's it — the wheel already contains the compiled extension, and pip picks
the right one for your OS / architecture / Python automatically.

Then scaffold a runnable app and go:

```bash
maya new myapp     # writes myapp.py — a working counter app
python myapp.py    # run it (q / Esc to quit)
```

(`maya new`, `maya demo`, `maya version` also work as `python -m maya_py ...`.)

> **Terminal note.** maya speaks ANSI/VT escapes + truecolor + UTF-8. On
> Linux and macOS any modern terminal works. On **Windows use Windows
> Terminal** (the default on Windows 11; free on Windows 10) or any VT-capable
> host — the legacy `cmd.exe` console works too (maya enables
> `ENABLE_VIRTUAL_TERMINAL_PROCESSING` on startup), but Windows Terminal
> gives the best Unicode + color fidelity.

<details>
<summary>Installing straight from a GitHub Release (no PyPI)</summary>

If you'd rather not use PyPI (or want a specific build), install from the
release assets. Let pip pick the right wheel for your Python:

```bash
pip install --find-links \
  https://github.com/1ay1/maya-py/releases/expanded_assets/v0.2.6 \
  maya-py
```

Or install a specific `.whl` by direct URL:

```bash
# e.g. CPython 3.13 on x86_64 Linux
pip install https://github.com/1ay1/maya-py/releases/download/v0.2.6/maya_py-0.2.6-cp313-cp313-manylinux_2_28_x86_64.whl
```

</details>

The Linux and macOS wheels work even on machines with a **very old C++
toolchain** (or none at all), because:

- the wheel is built inside a `manylinux_2_28` container, so it targets
  glibc 2.28 (2019) and runs on that-or-newer distros;
- it **statically links libstdc++/libgcc**, so it doesn't need the host's
  (old) C++ runtime — it depends only on baseline `libc`/`libm`.

The Windows wheel links the UCRT present on every Windows 10+ machine. Nothing
on your machine is compiled at install time, so your system compiler is
irrelevant.

### No matching wheel? Build from the sdist

If no prebuilt wheel matches your platform/Python, install the source
distribution; this compiles the extension locally and needs a
C++23-capable toolchain and CMake ≥ 3.28:

- **Linux:** GCC ≥ 14 or Clang ≥ 18
- **macOS:** Homebrew GCC (`brew install gcc`) — AppleClang is rejected
  (it misses C++23 library bits maya needs); CMake auto-picks the `gcc-*`
  driver
- **Windows:** Visual Studio 2022 ≥ 17.10 (MSVC `cl` ≥ 19.40), "Desktop
  development with C++" workload

```bash
pip install \
  https://github.com/1ay1/maya-py/releases/download/v0.2.6/maya_py-0.2.6.tar.gz
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
- `scroll_state()`, `viewport(content, state, width=, height=)`,
  `scrollbar(state, size, axis=, style=)`, `scroll_handle(state, ev)` — the
  scrollable-window + scrollbar pair (maya's `ScrollState` + `scrollbar_y/x`).
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
renderer still edges ahead — building the element tree in Python and crossing
pybind11 costs more than maya's native render saves:

| path | per render |
|------|-----------|
| maya-py (build + render) | ~145 µs |
| pure-Python equivalent | ~70 µs |

~80% of maya-py's time is the Python tree construction + boundary crossing,
not maya — the native render itself is only ~24 µs. So **if you only render
static output once, a pure-Python lib like Rich is still a touch faster** (now
~2×, down from ~5×).

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

Three levers close most of the Python-side gap:

1. **Fluent styling is free.** `T("x").bold.fg("sky")` accumulates state in
   pure Python and makes a *single* boundary crossing when the element is
   built (4.8× faster than the naive one-call-per-`.bold` approach).

2. **Pass styled cells as tuples to skip the `T` objects.** `row`/`col`
   accept `(text, fg[, bg[, attrs]])` tuple specs directly — in a hot redraw
   path (tables, lists, dashboards) the throwaway `T` per cell is the
   dominant build cost, and the tuple form flattens the whole row in one
   boundary crossing. Byte-identical output, same API:

   ```python
   from maya_py import row, T, c, DIM

   # reads nicer for one-off UI:
   row(T(name).fg("sky"), c(status, color), T(latency).dim, gap=2)
   # faster (tuple cells, zero T allocations — use in per-frame loops):
   row((name, "sky"), (status, color), (latency, None, None, DIM), gap=2)
   ```

   You can mix both, and any built Element / nested box / component child
   transparently falls back to the general path — so `row(sidebar,
   grow(main))` still works. (`trow`/`tcol` are kept as back-compat aliases;
   new code can just use `row`/`col`.)

3. **`memo` caches unchanged sub-trees.** In a live app, wrap builders whose
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

**Bottom line:** building a UI in Python always costs Python calls, but the
thing that actually matters in a terminal — the per-frame redraw — is now
*faster than a hand-tuned pure-Python renderer*: maya's native layout + paint
renders the cached tree in ~25µs vs ~70µs for the bespoke string-builder in
`examples/bench.py`, while still doing real flexbox, wrapping, and a
partial-frame diff. `memo` + tuple-cell `row`/`col` let the steady-state frame
skip Python almost entirely.

## License

MIT (same as maya).
