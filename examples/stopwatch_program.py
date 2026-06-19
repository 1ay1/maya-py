"""stopwatch — a pure MVU Program with timer subscriptions and batched effects.

The Elm Architecture, faithfully: an immutable Model, a closed Msg set, a pure
``update`` (no I/O, no mutation), effects described as ``Cmd`` data, and event
sources described as ``Sub`` data. The runtime performs the effects; your code
stays pure and testable.

What this shows off beyond the basic counter:
  • Sub.every   — a recurring timer message (the tick), declared by the model
  • Sub.batch   — combine the timer with key handling
  • Cmd.batch   — emit several effects from one transition
  • a real running/paused state machine, all in one pure ``update``

Run it::         python examples/stopwatch_program.py
Self-test it::   python examples/stopwatch_program.py --test   (no terminal)

  space  start/pause     r  reset     q/Esc  quit
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import Cmd, Sub, Program
from maya_py import card, col, row, T, fmt_duration


TICK_MS = 50   # timer resolution


class Stopwatch(Program):
    title = "stopwatch"

    # ── Model: a plain immutable dict ──────────────────────────────────────
    def init(self):
        model = {"elapsed": 0.0, "running": False}
        return model, Cmd.set_title("stopwatch")

    # ── Update: pure transition, returns model | (model, Cmd) ──────────────
    def update(self, m, msg):
        if msg == "tick":
            if not m["running"]:
                return m
            return {**m, "elapsed": m["elapsed"] + TICK_MS / 1000.0}
        if msg == "toggle":
            return {**m, "running": not m["running"]}
        if msg == "reset":
            # Stop AND zero the clock — one transition, batched effects.
            return {"elapsed": 0.0, "running": False}, Cmd.batch(
                Cmd.set_title("stopwatch (reset)"),
                Cmd.force_redraw(),
            )
        if msg == "quit":
            return m, Cmd.quit()
        return m

    # ── View: model -> Element, a pure function ────────────────────────────
    def view(self, m):
        running = m["running"]
        clock = fmt_duration(m["elapsed"], centis=True)
        status = "running" if running else "paused"
        accent = "green" if running else "slate"
        return card(
            T("Stopwatch").bold.fg("gold"),
            T(clock).bold.fg(accent),
            row(T("\u25cf").fg(accent), T(status).dim, gap=1),
            T("space start/pause \u00b7 r reset \u00b7 q quit").dim,
            title="stopwatch",
            gap=1,
        )

    # ── Subscribe: model -> Sub, the event sources for this state ──────────
    def subscribe(self, m):
        def on_key(ev):
            if maya.key(ev, " "):
                return "toggle"
            if maya.key(ev, "r"):
                return "reset"
            if maya.key(ev, "q") or maya.key_special(ev, maya.SpecialKey.Escape):
                return "quit"
            return None

        # A recurring tick PLUS key handling, combined declaratively. The timer
        # always fires; update() ignores it while paused, so the subscription
        # stays a pure function of the model with no conditional plumbing.
        return Sub.batch(
            Sub.every(TICK_MS, "tick"),
            Sub.on_key(on_key),
        )


def _self_test():
    """Prove the pure architecture headlessly \u2014 no terminal, fully deterministic.

    This is the part that makes the Elm Architecture worth it: every transition
    is a unit test, and the WHOLE app is exercised through ``ProgramPilot``.
    """
    p = Stopwatch().test()
    assert p.model == {"elapsed": 0.0, "running": False}
    assert len(p.cmds) == 1                       # init's Cmd.set_title

    # Ticks while paused are ignored \u2014 update stays pure.
    p.send("tick", "tick")
    assert p.model["elapsed"] == 0.0

    # Start, then five ticks advance the clock by 5 * 50ms = 0.25s.
    p.send("toggle")
    assert p.model["running"] is True
    p.send("tick", "tick", "tick", "tick", "tick")
    assert abs(p.model["elapsed"] - 0.25) < 1e-9

    # Pause freezes it.
    p.send("toggle")
    p.send("tick", "tick")
    assert abs(p.model["elapsed"] - 0.25) < 1e-9

    # Reset zeroes the clock and emits a batched effect.
    before = len(p.cmds)
    p.send("reset")
    assert p.model == {"elapsed": 0.0, "running": False}
    assert len(p.cmds) == before + 1

    # The view renders the model purely.
    assert "0:00.00" in p.view_string(40)
    assert "paused" in p.view_string(40)

    print("stopwatch self-test: all pure-update transitions pass \u2713")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        Stopwatch().run()
