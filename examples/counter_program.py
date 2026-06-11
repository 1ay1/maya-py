"""counter — the canonical maya MVU Program in Python.

A faithful port of maya's C++ counter example: pure init/update/view/subscribe
over an immutable model, side effects as Cmd, key events as Sub. Run it::

    python examples/counter_program.py

    +/k/up    increment        -/j/down   decrement
    r         reset            q/Esc      quit
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import Cmd, Sub, Program


class Counter(Program):
    title = "counter"

    def init(self):
        # Initial model + a startup effect (set the window title).
        return {"count": 0}, Cmd.set_title("maya counter")

    def update(self, m, msg):
        if msg == "inc":
            return {**m, "count": m["count"] + 1}
        if msg == "dec":
            return {**m, "count": m["count"] - 1}
        if msg == "reset":
            return {**m, "count": 0}
        if msg == "quit":
            return m, Cmd.quit()
        return m

    def view(self, m):
        n = m["count"]
        color = maya.fg(80, 220, 120) if n >= 0 else maya.fg(240, 100, 100)
        return maya.box(
            maya.text("Counter", maya.bold | maya.fg(120, 180, 255)),
            maya.blank(),
            maya.text(f"{n}", maya.bold | color),
            maya.blank(),
            maya.text("+/-  adjust    r  reset    q  quit", maya.dim),
            direction=maya.Column,
            border=maya.Round, padding=2, gap=0,
        )

    def subscribe(self, m):
        def on_key(ev):
            if maya.key(ev, "+") or maya.key(ev, "k"):
                return "inc"
            if maya.key(ev, "-") or maya.key(ev, "j"):
                return "dec"
            if maya.key(ev, "r"):
                return "reset"
            if maya.key(ev, "q"):
                return "quit"
            return None
        return Sub.on_key(on_key)


if __name__ == "__main__":
    Counter().run()
