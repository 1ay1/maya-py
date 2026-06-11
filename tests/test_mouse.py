"""test_mouse — mouse events flow through the bindings and the App runtime.

These drive a child app in a pty, feed it raw SGR mouse sequences, and check
the handlers fire with correct coordinates. Mouse reporting must be enabled
(App(mouse=True) or any @app.on_click/@app.on_scroll auto-enables it).
"""

import os
import sys
import time
import pty
import select
import signal
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as m


def _run_child(body: str, raw_sequences: list[bytes], settle: float = 0.8):
    """Run a child app, feed raw bytes, return (exit_code, stderr_text)."""
    src = (
        "import sys, os\n"
        'sys.path.insert(0, os.path.join(os.getcwd(), "src"))\n'
        "import maya_py as m\n"
        'app = m.App("t", inline=True)\n'
        "app.state(log=[])\n"
        + body
        + '\n@app.on("q", "esc")\ndef _q(s): app.stop()\n'
        '@app.view\ndef _v(s): return m.card("ok")\n'
        "app.run()\n"
    )
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(src)
    f.close()

    err = tempfile.NamedTemporaryFile(delete=False)
    pid, fd = pty.fork()
    if pid == 0:
        # child: redirect stderr to the temp file, then exec
        os.dup2(err.fileno(), 2)
        os.execvp(sys.executable, [sys.executable, f.name])

    time.sleep(settle)
    for seq in raw_sequences:
        try:
            os.write(fd, seq)
        except OSError:
            break
        time.sleep(0.12)
    # quit
    try:
        os.write(fd, b"q")
    except OSError:
        pass

    deadline = time.time() + 3.0
    status = None
    while time.time() < deadline:
        try:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                os.read(fd, 4096)
        except OSError:
            pass
        wpid, st = os.waitpid(pid, os.WNOHANG)
        if wpid != 0:
            status = st
            break
    if status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        code = "HUNG"
    elif os.WIFSIGNALED(status):
        code = -os.WTERMSIG(status)
    else:
        code = os.WEXITSTATUS(status)
    try:
        os.close(fd)
    except OSError:
        pass
    err.flush()
    return code, open(err.name).read()


def test_on_click_fires_with_coords():
    body = (
        '@app.on_click("left")\n'
        "def _c(s, col, row):\n"
        '    sys.stderr.write(f"CLICK {col} {row}\\n"); sys.stderr.flush()\n'
    )
    # SGR left press at protocol col=6, row=4 (1-based)
    code, err = _run_child(body, [b"\x1b[<0;6;4M", b"\x1b[<0;6;4m"])
    assert code == 0, f"app crashed/hung: {code}"
    assert "CLICK 6 4" in err, err


def test_on_scroll_direction():
    body = (
        "@app.on_scroll\n"
        "def _s(s, d):\n"
        '    sys.stderr.write(f"SCROLL {d}\\n"); sys.stderr.flush()\n'
    )
    # button 64 = wheel up, 65 = wheel down
    code, err = _run_child(body, [b"\x1b[<64;5;5M", b"\x1b[<65;5;5M"])
    assert code == 0
    assert "SCROLL -1" in err, err
    assert "SCROLL 1" in err, err


def test_right_click_distinct_from_left():
    body = (
        '@app.on_click("right")\n'
        "def _r(s, col, row):\n"
        '    sys.stderr.write(f"RIGHT {col} {row}\\n"); sys.stderr.flush()\n'
        '@app.on_click("left")\n'
        "def _l(s, col, row):\n"
        '    sys.stderr.write(f"LEFT {col} {row}\\n"); sys.stderr.flush()\n'
    )
    # button 2 = right, button 0 = left
    code, err = _run_child(body, [b"\x1b[<2;3;3M", b"\x1b[<0;7;7M"])
    assert code == 0
    assert "RIGHT 3 3" in err, err
    assert "LEFT 7 7" in err, err


def test_on_click_auto_enables_mouse():
    # No mouse=True passed, but on_click must turn it on (else no events arrive).
    app = m.App("t")
    assert app.mouse is False

    @app.on_click("left")
    def _c(s, col, row):
        pass

    assert app.mouse is True


def test_mouse_predicates_exist():
    for name in ("mouse_clicked", "mouse_released", "mouse_moved",
                 "scrolled_up", "scrolled_down", "mouse_pos",
                 "mouse_button", "mouse_kind", "is_mouse"):
        assert hasattr(m, name), name
    assert m.MouseButton.Left is not None
    assert m.MouseEventKind.Press is not None


def test_mouse_mode_enabled_and_disabled_on_exit():
    # The core fix: an App(mouse=True) MUST emit the SGR mouse-tracking
    # enable on start and the matching DISABLE on exit. Without the disable
    # the terminal echoes raw mouse reports into the user's shell after the
    # app quits (the reported bug). Capture the pty master = what the app
    # writes to the terminal.
    src = (
        "import sys, os\n"
        'sys.path.insert(0, os.path.join(os.getcwd(), "src"))\n'
        "import maya_py as m\n"
        'app = m.App("t", inline=True, mouse=True)\n'
        '@app.on_click("left")\n'
        "def _c(s, col, row): pass\n"
        '@app.on("q", "esc")\n'
        "def _q(s): app.stop()\n"
        '@app.view\ndef _v(s): return m.card("ok")\n'
        "app.run()\n"
    )
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(src)
    f.close()
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(sys.executable, [sys.executable, f.name])
    buf = b""
    time.sleep(0.8)
    os.write(fd, b"q")
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                buf += os.read(fd, 8192)
        except OSError:
            break
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
    assert b"\x1b[?1003h" in buf, "mouse any-event tracking (1003h) was never enabled"
    assert b"\x1b[?1006h" in buf, "SGR mouse mode (1006h) was never enabled"
    assert b"\x1b[?1003l" in buf, "mouse tracking (1003l) was never DISABLED on exit"
    assert b"\x1b[?1006l" in buf, "SGR mouse mode (1006l) was never DISABLED on exit"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print("done" if not failures else f"{failures} FAILURES")
    sys.exit(1 if failures else 0)
