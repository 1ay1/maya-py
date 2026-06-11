"""test_scroll — the scrollbar widget + viewport + ScrollState work end-to-end."""

import sys
import os
import time
import pty
import signal
import select
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as m

_passed = 0


def check(name, cond):
    global _passed
    assert cond, f"FAIL {name}"
    _passed += 1
    print("ok ", name)


def _content(n=40):
    return m.col(*[m.T(f"row {i:02d}") for i in range(n)])


def test_scroll_state_defaults():
    s = m.scroll_state()
    check("state_zero", s.x == 0 and s.y == 0 and s.max_x == 0 and s.max_y == 0)
    s.scroll_by(0, 5)
    check("scroll_by_clamps_to_max0", s.y == 0)  # max_y still 0


def test_viewport_clips_and_writes_back_max():
    s = m.scroll_state()
    ui = m.row(m.viewport(_content(40), s, height=10), m.scrollbar(s, 10))
    out = m.to_string(ui, 40)
    # only 10 rows visible
    body_rows = [l for l in out.splitlines() if "row" in l]
    check("viewport_clips_to_10", len(body_rows) == 10)
    check("max_y_written_back", s.max_y == 30)  # 40 content - 10 viewport
    # top of content shows first
    check("shows_top", "row 00" in out)
    check("hides_overflow", "row 30" not in out)


def test_viewport_grow_fills_width():
    s = m.scroll_state()
    # viewport with grow=1 next to a scrollbar should push the bar to the edge
    ui = m.row(m.viewport(_content(40), s, height=8, grow=1),
               m.scrollbar(s, 8, style="line"))
    out = m.to_string(ui, 50)
    # the bar glyph (│ or ┃) should appear near the right edge of every body row
    body = [l for l in out.splitlines() if "row" in l]
    last_cols = [len(l.rstrip()) for l in body]
    check("grow_pushes_bar_right", max(last_cols) >= 48)


def test_viewport_bounds_written_back():
    # viewport_bounds records the painted rect so apps can hit-test clicks
    # without hardcoding offsets. It's written by the interactive renderer;
    # render_to_string establishes the layout. Before any paint it's zero.
    s = m.scroll_state()
    x0, y0, w0, h0 = s.viewport_bounds
    check("bounds_zero_initially", w0 == 0 and h0 == 0)
    # bounds is a 4-tuple accessor that doesn't raise
    ui = m.row(m.viewport(_content(40), s, width=20, height=8), m.scrollbar(s, 8))
    m.to_string(ui, 40)
    bx, by, bw, bh = s.viewport_bounds
    check("bounds_is_4tuple", isinstance(s.viewport_bounds, tuple)
          and len(s.viewport_bounds) == 4)


def test_scroll_position_moves_window():
    s = m.scroll_state()
    ui = lambda: m.row(m.viewport(_content(40), s, height=8), m.scrollbar(s, 8))
    m.to_string(ui(), 40)            # establish max_y
    s.scroll_to(0, 10)
    out = m.to_string(ui(), 40)
    check("scrolled_window", "row 10" in out and "row 00" not in out)
    s.scroll_to_bottom()
    out = m.to_string(ui(), 40)
    check("bottom_shows_last", "row 39" in out)
    check("at_bottom_flag", s.at_bottom())


def test_scrollbar_thumb_positions():
    s = m.scroll_state()
    ui = lambda: m.row(m.viewport(_content(40), s, height=10),
                       m.scrollbar(s, 10, style="line"))
    m.to_string(ui(), 30)           # max_y = 30
    # at top: thumb (┃) should be in the FIRST rows
    s.scroll_to_top()
    top = m.to_string(ui(), 30)
    top_lines = [l for l in top.splitlines() if "row" in l]
    first_thumb = next(i for i, l in enumerate(top_lines) if "┃" in l)
    # at bottom: thumb should be in the LAST rows
    s.scroll_to_bottom()
    bot = m.to_string(ui(), 30)
    bot_lines = [l for l in bot.splitlines() if "row" in l]
    last_thumb = max(i for i, l in enumerate(bot_lines) if "┃" in l)
    check("thumb_moves_down", first_thumb < last_thumb)


def test_all_scrollbar_styles_render():
    s = m.scroll_state()
    m.to_string(m.viewport(_content(40), s, height=8), 30)  # set max_y
    styles = ["line", "block", "slim", "heavy", "double", "dotted", "dashed",
              "braille", "ascii", "shadow", "minimal", "neon", "retro",
              "danger", "pixel"]
    for st in styles:
        out = m.to_string(m.scrollbar(s, 8, style=st), 4)
        check(f"style_{st}", len(out.strip()) > 0)


def test_horizontal_scrollbar():
    s = m.scroll_state()
    wide = m.row(*[m.T(f"c{i}") for i in range(40)], gap=1)
    ui = m.col(m.viewport(wide, s, width=20), m.scrollbar(s, 20, axis="x"))
    out = m.to_string(ui, 24)
    check("hbar_renders", len(out.strip()) > 0)


def test_thumb_color_override():
    s = m.scroll_state()
    m.to_string(m.viewport(_content(40), s, height=8), 30)
    out = m.to_string(m.scrollbar(s, 8, style="block", thumb_color="lime"), 4)
    check("color_override_ok", "█" in out)


def test_unknown_style_raises():
    s = m.scroll_state()
    try:
        m.scrollbar(s, 8, style="nope")
        check("unknown_style_raises", False)
    except ValueError:
        check("unknown_style_raises", True)


# ── interactive event routing (pty) ──────────────────────────────────────────
# Tests maya's NATIVE behavior: with scroll_state() (auto_dispatch on) the run
# loop forwards arrows + wheel to the scroll state automatically — NO handler.
def _drive(seqs):
    prog = (
        "import sys, os\n"
        'sys.path.insert(0, os.path.join(os.getcwd(), "src"))\n'
        "import maya_py as m\n"
        'app = m.App("t", inline=True, mouse=True)\n'
        "s = m.scroll_state()\n"          # auto_dispatch on (maya default)
        "app.state(s=s)\n"
        "content = m.col(*[m.T(f'r{i}') for i in range(40)])\n"
        '@app.on("q", "esc")\n'
        "def q(st): app.stop()\n"
        "@app.view\n"
        "def v(st):\n"
        '    sys.stderr.write(f"Y {st.s.y}\\n"); sys.stderr.flush()\n'
        "    return m.row(m.viewport(content, st.s, height=10), m.scrollbar(st.s, 10))\n"
        "app.run()\n"
    )
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(prog)
    f.close()
    err = tempfile.NamedTemporaryFile(delete=False)
    pid, fd = pty.fork()
    if pid == 0:
        os.dup2(err.fileno(), 2)
        os.execvp(sys.executable, [sys.executable, f.name])
    time.sleep(0.7)
    for seq in seqs:
        os.write(fd, seq)
        time.sleep(0.15)
    os.write(fd, b"q")
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                os.read(fd, 4096)
        except OSError:
            pass
        wpid, _ = os.waitpid(pid, os.WNOHANG)
        if wpid != 0:
            break
    else:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    try:
        os.close(fd)
    except OSError:
        pass
    err.flush()
    # collect the distinct y values the view observed, in order
    ys = []
    for line in open(err.name).read().splitlines():
        if line.startswith("Y "):
            try:
                v = int(line[2:])
            except ValueError:
                continue
            if not ys or ys[-1] != v:
                ys.append(v)
    return ys


def test_arrow_keys_auto_scroll():
    ys = _drive([b"\x1b[B", b"\x1b[B", b"\x1b[B"])  # Down x3
    # auto-dispatch: no handler, the view sees y climb 0 → 3
    check("arrow_auto_scrolls", max(ys) >= 3, )


def test_wheel_auto_scrolls():
    # wheel-down inside the viewport (near top-left)
    ys = _drive([b"\x1b[<65;3;3M", b"\x1b[<65;3;4M", b"\x1b[<65;3;4M"])
    check("wheel_auto_scrolls", max(ys) >= 1)


if __name__ == "__main__":
    g = dict(globals())
    for name, fn in sorted(g.items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print(f"\n{_passed} checks passed")
