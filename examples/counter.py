"""Interactive counter — the simple run() loop driven from Python.

  +/=  increment    -  decrement    r  reset    q/Esc  quit
"""
import maya_py as maya

count = 0


def on_event(ev):
    global count
    if maya.key(ev, "q") or maya.key_special(ev, maya.SpecialKey.Escape):
        return False  # quit
    if maya.key(ev, "+") or maya.key(ev, "="):
        count += 1
    elif maya.key(ev, "-"):
        count -= 1
    elif maya.key(ev, "r"):
        count = 0
    return True


def view():
    return maya.box(
        maya.vstack(
            maya.text("Counter", maya.bold | maya.fg(100, 180, 255)),
            maya.blank(),
            maya.text(str(count), maya.bold),
            maya.blank(),
            maya.text("+/- change   r reset   q quit", maya.dim),
        ),
        border=maya.Round,
        padding=1,
    )


maya.run(on_event, view, title="counter", inline_mode=True)
