"""Headless tests for the MVU Program runtime (Cmd / Sub / update / view).

These exercise the pure layer and the native Cmd/Sub value types WITHOUT
entering the terminal loop (run_program blocks on a real tty). The loop itself
is maya's own run<P> logic, verified in C++; here we confirm the Python
plumbing: Cmd/Sub construct, update transitions are pure, view returns an
Element, and the Program base class wires the hooks.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import Cmd, Sub, Program

ok = 0
fail = 0

def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"  FAIL: {name}")


# ── Cmd value type ──────────────────────────────────────────────────────────
check("Cmd.none", isinstance(Cmd.none(), Cmd))
check("Cmd.quit", isinstance(Cmd.quit(), Cmd))
check("Cmd.batch", isinstance(Cmd.batch(Cmd.none(), Cmd.quit()), Cmd))
check("Cmd.after", isinstance(Cmd.after(100, "tick"), Cmd))
check("Cmd.set_title", isinstance(Cmd.set_title("hi"), Cmd))
check("Cmd.write_clipboard", isinstance(Cmd.write_clipboard("x"), Cmd))
check("Cmd.query_clipboard", isinstance(Cmd.query_clipboard(), Cmd))
check("Cmd.task", isinstance(Cmd.task(lambda d: d("done")), Cmd))
check("Cmd.isolated_task", isinstance(Cmd.isolated_task(lambda d: d("done")), Cmd))
check("Cmd.commit_scrollback", isinstance(Cmd.commit_scrollback(3), Cmd))
check("Cmd.commit_scrollback_overflow", isinstance(Cmd.commit_scrollback_overflow(), Cmd))
check("Cmd.force_redraw", isinstance(Cmd.force_redraw(), Cmd))
check("Cmd.reset_inline", isinstance(Cmd.reset_inline(), Cmd))

# ── Sub value type ──────────────────────────────────────────────────────────
check("Sub.none", isinstance(Sub.none(), Sub))
check("Sub.on_key", isinstance(Sub.on_key(lambda ev: None), Sub))
check("Sub.on_mouse", isinstance(Sub.on_mouse(lambda ev: None), Sub))
check("Sub.on_resize", isinstance(Sub.on_resize(lambda w, h: "r"), Sub))
check("Sub.on_paste", isinstance(Sub.on_paste(lambda t: "p"), Sub))
check("Sub.every", isinstance(Sub.every(16, "tick"), Sub))
check("Sub.on_animation_frame", isinstance(Sub.on_animation_frame("frame"), Sub))
check("Sub.batch", isinstance(Sub.batch(Sub.none(), Sub.every(16, "t")), Sub))


# ── Pure Program transitions ────────────────────────────────────────────────
class Counter(Program):
    def init(self):
        return {"count": 0}, Cmd.set_title("x")

    def update(self, m, msg):
        if msg == "inc":
            return {**m, "count": m["count"] + 1}
        if msg == "quit":
            return m, Cmd.quit()
        return m

    def view(self, m):
        return maya.card(maya.text(f"count: {m['count']}"))

    def subscribe(self, m):
        return Sub.on_key(lambda ev: "inc" if maya.key(ev, "+") else None)


c = Counter()

# init returns (model, Cmd)
m0, cmd0 = c.init()
check("init model", m0 == {"count": 0})
check("init cmd", isinstance(cmd0, Cmd))

# update is a pure transition
m1 = c.update(m0, "inc")
check("update inc", m1 == {"count": 1})
check("update inc immutable", m0 == {"count": 0})

m2 = c.update(m1, "inc")
check("update inc twice", m2 == {"count": 2})

# update returning (model, Cmd)
res = c.update(m2, "quit")
check("update quit pair", isinstance(res, tuple) and isinstance(res[1], Cmd))

# unknown msg = identity
check("update unknown", c.update(m2, "???") == m2)

# view returns an Element
v = c.view(m2)
check("view -> Element", isinstance(v, maya.Element))
rendered = maya.to_string(v, 40)
check("view renders count", "count: 2" in rendered)

# subscribe returns a Sub
check("subscribe -> Sub", isinstance(c.subscribe(m2), Sub))


# ── Plain-function form ──────────────────────────────────────────────────────
def init():
    return {"n": 5}

def update(m, msg):
    return {**m, "n": m["n"] + 1} if msg == "up" else m

def view(m):
    return maya.text(str(m["n"]))

check("fn init", init() == {"n": 5})
check("fn update", update(init(), "up") == {"n": 6})
check("fn view", isinstance(view(init()), maya.Element))


print(f"\nprogram: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
