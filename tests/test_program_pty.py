"""PTY-driven live test of run_program: spawn an MVU app in a pseudo-terminal,
feed three '+' keys, and confirm each one re-rendered (the model grew and the
view appended a glyph), then 'q' quits cleanly.

NOTE: inline mode emits a CELL DIFF, not whole frames — after the first paint a
state change rewrites only the changed cells, so asserting on a literal like
"N=2" in the byte stream is wrong (it never reappears). We assert on a glyph
whose COUNT grows with the model instead.
"""

import sys, os, pty, time, select

SRC = os.path.join(os.path.dirname(__file__), "..", "src")

prog = r"""
import sys
sys.path.insert(0, %r)
import maya_py as maya
from maya_py import Cmd, Sub, Program

class C(Program):
    title = "t"
    def init(self): return {"n": 0}
    def update(self, m, msg):
        if msg == "inc":  return {**m, "n": m["n"] + 1}
        if msg == "quit": return m, Cmd.quit()
        return m
    def view(self, m):
        # The view's visible width grows by one 'X' per increment, so the
        # glyph COUNT in the wire stream tracks the number of re-renders.
        return maya.box(maya.text("VAL " + "X" * m["n"]),
                        border=maya.Round, padding=1)
    def subscribe(self, m):
        return Sub.on_key(lambda ev:
            "inc"  if maya.key(ev, "+") else
            "quit" if maya.key(ev, "q") else None)

C().run(inline=True)
""" % SRC


def test_program_pty():
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", prog])
        return  # unreachable in the child after execv
    out = b""
    deadline = time.time() + 10
    primed = False
    quit_sent = False
    exited = False
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                exited = True
                break
            if not chunk:
                exited = True
                break
            out += chunk
        if not primed and b"VAL" in out:
            time.sleep(0.2)
            os.write(fd, b"+++")     # three increments
            primed = True
            time.sleep(0.5)
        elif primed and not quit_sent and out.count(b"X") >= 3:
            os.write(fd, b"q")       # quit
            quit_sent = True
    try:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
    except OSError:
        pass

    x_count = out.count(b"X")
    rendered_initial = b"VAL" in out
    re_rendered = x_count >= 3          # 3 increments => 3 X glyphs on the wire
    quit_ok = quit_sent

    print("rendered initial frame:", rendered_initial)
    print("re-rendered on each key (>=3 X glyphs):", re_rendered, f"({x_count})")
    print("quit issued cleanly:", quit_ok)
    assert rendered_initial, "initial frame never rendered"
    assert re_rendered, f"expected >=3 X glyphs on the wire, got {x_count}"
    assert quit_ok, "quit was never issued"


if __name__ == "__main__":
    try:
        test_program_pty()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    sys.exit(0)
