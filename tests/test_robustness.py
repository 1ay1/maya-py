"""Robustness / edge-case regression tests.

Each test here pins a bug that was found and fixed in the audit. They cover
the boundary between Python and the C++ binding: bad inputs, empty trees,
unicode, error reporting, the interactive event loop (run under a pty), GIL /
Ctrl-C handling, and terminal restoration on exceptions.

Run headless with:  PYTHONPATH=src python3 tests/test_robustness.py
"""
import os
import pty
import re
import signal
import sys
import time

import maya_py as m
from maya_py import App, T, card, col, row, field, hr, to_string


# ── element building: edge cases ─────────────────────────────────────────────
def test_empty_containers_render():
    for node in (col(), row(), card()):
        assert isinstance(to_string(node, 20), str)


def test_none_child_becomes_blank():
    out = to_string(col("a", None, "b"), 20)
    assert "a" in out and "b" in out


def test_deep_nesting_does_not_crash():
    node = col(*[card(str(i)) for i in range(50)])
    assert isinstance(to_string(node, 40), str)


def test_unicode_and_wide_chars():
    out = to_string(card("héllo 世界 🎉"), 30)
    assert "héllo" in out


def test_very_long_string_wraps():
    out = to_string(card("x" * 5000), 40)
    assert isinstance(out, str) and len(out) > 0


# ── padding / margin arity ───────────────────────────────────────────────────
def test_padding_all_valid_forms():
    assert to_string(card("x", pad=2), 20)
    assert to_string(col("x", pad=(2,)), 20)
    assert to_string(col("x", pad=(1, 2)), 20)
    assert to_string(col("x", pad=(1, 2, 3, 4)), 20)
    assert to_string(col("x", pad=[1, 2]), 20)


def test_padding_bad_arity_raises():
    try:
        to_string(col("x", pad=(1, 2, 3)), 20)
        assert False, "3-tuple padding should raise"
    except ValueError:
        pass


# ── color resolution ─────────────────────────────────────────────────────────
def test_color_forms():
    for v in ("#f80", "#ff8800", "sky", (255, 128, 0), 0xFF8800, m.Color.red()):
        assert to_string(T("x").fg(v), 10)


def test_unknown_color_name_raises():
    try:
        T("x").fg("octarine").element()
        assert False
    except ValueError:
        pass


# ── friendly enum-name errors ────────────────────────────────────────────────
def test_unknown_border_align_justify_raise_valueerror():
    for kw in ({"border": "rounded"}, {"align": "middle"}, {"justify": "spread"}):
        try:
            col("x", **kw)
            assert False, f"{kw} should raise"
        except ValueError as e:
            assert "valid:" in str(e)


def test_bad_child_type_raises_typeerror():
    try:
        to_string(col(42), 20)
        assert False
    except TypeError:
        pass


# ── App wiring (no event loop) ───────────────────────────────────────────────
def test_app_default_view_when_unregistered():
    app = App("x")
    assert isinstance(app._render(), m.Element)


def test_app_ctrl_c_bound_flag_tracks_user_binding():
    app = App("x")
    assert app._ctrl_c_bound is False

    @app.on("ctrl+c")
    def _q(s):
        app.stop()

    assert app._ctrl_c_bound is True


def test_app_view_returning_str_is_coerced():
    app = App("x")

    @app.view
    def v(s):
        return "just a string"

    assert isinstance(app._render(), m.Element)


# ── interactive loop under a pty ─────────────────────────────────────────────
def _spawn(code: str, keys: list[bytes], settle: float = 0.5):
    """Run `code` in a child pty, send `keys`, return (exited, output_text).

    Uses non-blocking reads with a hard wall-clock deadline so a child that
    refuses to die (the negative-path tests) can never hang the suite.
    """
    import fcntl
    import select

    path = "/tmp/_maya_robustness_child.py"
    with open(path, "w") as f:
        f.write(code)
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.execvp(sys.executable, [sys.executable, path])

    # non-blocking master fd
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    deadline = time.time() + settle + 0.25 * len(keys) + 1.5
    out = b""

    def drain():
        nonlocal out
        try:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                d = os.read(fd, 4096)
                if d:
                    out += d
        except (OSError, ValueError):
            pass

    time.sleep(settle)
    drain()
    for k in keys:
        try:
            os.write(fd, k)
        except OSError:
            break
        time.sleep(0.25)
        drain()

    exited = False
    while time.time() < deadline:
        drain()
        try:
            wpid, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            wpid = pid
        if wpid != 0:
            exited = True
            break
        time.sleep(0.05)

    if not exited:
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except (ChildProcessError, ProcessLookupError):
            pass
    try:
        os.close(fd)
    except OSError:
        pass
    return exited, out.decode("utf-8", "replace")


_APP_SRC = """
import sys
sys.path.insert(0, "src")
import maya_py as m
app = m.App("t", inline={inline}, quit_on_ctrl_c={qcc})
{bindings}
@app.view
def v(s):
    return m.card("hi")
app.run()
"""


def test_ctrl_c_quits_event_driven_app():
    # fps=0 (event-driven) app: Ctrl-C arrives as a key event and must quit.
    src = _APP_SRC.format(inline="True", qcc="True", bindings="")
    exited, _ = _spawn(src, [b"\x03"])
    assert exited, "Ctrl-C should quit an event-driven App by default"


def test_ctrl_c_opt_out_keeps_running():
    src = _APP_SRC.format(
        inline="True", qcc="False",
        bindings='@app.on("q")\ndef q(s): app.stop()',
    )
    exited, _ = _spawn(src, [b"\x03"], settle=0.6)
    assert not exited, "quit_on_ctrl_c=False must ignore Ctrl-C"
    # but 'q' must still quit
    exited2, _ = _spawn(src, [b"q"], settle=0.6)
    assert exited2


def test_quit_key_binding_works():
    src = _APP_SRC.format(
        inline="True", qcc="True",
        bindings='@app.on("q")\ndef q(s): app.stop()',
    )
    exited, _ = _spawn(src, [b"q"])
    assert exited


def test_view_exception_restores_terminal():
    src = """
import sys
sys.path.insert(0, "src")
import maya_py as m
app = m.App("t", inline=False)   # fullscreen
@app.view
def v(s):
    raise ValueError("boom in view")
app.run()
"""
    exited, txt = _spawn(src, [], settle=0.6)
    assert exited
    # alt-screen disabled + cursor shown => terminal cleaned up by RAII
    assert ("1049l" in txt) or ("?47l" in txt)
    assert "25h" in txt
    assert "ValueError" in txt


def test_animate_ctrl_c_exits():
    src = """
import sys
sys.path.insert(0, "src")
import maya_py as m
m.animate(lambda dt: m.card(f"t={dt:.1f}"), fps=20)
"""
    exited, _ = _spawn(src, [b"\x03"], settle=0.6)
    assert exited, "Ctrl-C should break out of live()/animate()"


def test_component_in_live_app_no_segfault():
    # Regression: maya copies a ComponentElement by value many times during
    # paint with the GIL released. A naively-captured py::function would touch
    # Python refcounts off-GIL and SEGFAULT (observed: crash on frame ~1-3).
    # The component() binding stashes the callable behind a GIL-safe
    # shared_ptr. On the buggy binding the child dies of SIGSEGV within the
    # first second; on the fixed one it paints frames happily until we stop
    # it. We run for ~1.5s, then SIGTERM, and assert the child did NOT die of
    # a crash signal (SIGSEGV/SIGABRT) on its own beforehand.
    import select as _select
    import pty as _pty

    src = """
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
import maya_py as m
from maya_py import App, card, col, T, component
app = App("t", inline=True, fps=60)
app.state(n=0)
def grid():
    def draw(w, h):
        return col(*[T("#" * 12).fg("lime") for _ in range(8)])
    return component(draw, height=8, width=12)
@app.view
def v(s):
    s.n += 1
    return card(grid(), title="t")
app.run()
"""
    path = "/tmp/_maya_component_child.py"
    with open(path, "w") as f:
        f.write(src)
    pid, fd = _pty.fork()
    if pid == 0:
        os.execvp(sys.executable, [sys.executable, path])

    # Let it paint many frames for ~1.5s; a buggy build crashes in this window.
    end = time.time() + 1.5
    early_status = None
    while time.time() < end:
        try:
            r, _, _ = _select.select([fd], [], [], 0.05)
            if r:
                os.read(fd, 4096)
        except OSError:
            pass
        wpid, st = os.waitpid(pid, os.WNOHANG)
        if wpid != 0:
            early_status = st
            break

    if early_status is not None:
        # Died on its own during the paint window — only OK if it wasn't a crash.
        if os.WIFSIGNALED(early_status):
            raise AssertionError(
                "live App with component() crashed: signal "
                + str(os.WTERMSIG(early_status))
                + " (regression: GIL-unsafe component value-copy)"
            )
    else:
        # Still running after painting many frames = the fix holds. Stop it.
        os.kill(pid, signal.SIGTERM)
        try:
            _, st = os.waitpid(pid, 0)
            # SIGTERM is our doing; a SIGSEGV here would still be a crash.
            if os.WIFSIGNALED(st) and os.WTERMSIG(st) not in (signal.SIGTERM, signal.SIGKILL):
                raise AssertionError(
                    "live App with component() crashed on teardown: signal "
                    + str(os.WTERMSIG(st))
                )
        except ChildProcessError:
            pass
    try:
        os.close(fd)
    except OSError:
        pass


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print("done" if not failures else f"{failures} FAILURES")
    sys.exit(1 if failures else 0)
