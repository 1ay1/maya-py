"""Headless App driving via Pilot — no PTY, no terminal.

These exercise the SAME App._event / view path the live loop uses, by feeding
synthetic events from the native make_* factories. If these pass, an app's
handler + view logic is correct independent of any terminal.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, Pilot, card, col, b, dim_text, text_input


def _counter():
    app = App("counter", n=0, quit_keys=("q", "esc"))

    @app.on("+", "=")
    def inc(s):
        s.n += 1

    @app.on("-")
    def dec(s):
        s.n -= 1

    @app.on("r")
    def reset(s):
        s.n = 0

    @app.view
    def view(s):
        return card(b(f"Count: {s.n}"), dim_text("hint"), title="counter")

    return app


def test_event_factories_are_recognised():
    assert maya.key(maya.make_key("a"), "a")
    assert maya.event_char(maya.make_key("a")) == "a"
    assert maya.ctrl(maya.make_key("c", ctrl=True), "c")
    assert maya.key_special(maya.make_key("up"), maya.SpecialKey.Up)
    assert maya.key_special(maya.make_key("enter"), maya.SpecialKey.Enter)
    e = maya.make_mouse(5, 3, "left", "press")
    assert maya.mouse_clicked(e) and maya.mouse_pos(e) == (5, 3)
    assert maya.scrolled_up(maya.make_scroll("up"))
    assert maya.scrolled_down(maya.make_scroll("down"))
    assert maya.pasted(maya.make_paste("hi")) == "hi"
    assert maya.resize_size(maya.make_resize(120, 40)) == (120, 40)


def test_pilot_press_and_render():
    app = _counter()
    p = app.test(width=40)
    assert isinstance(p, Pilot)
    p.press("+", "+", "+", "+", "-")  # +4 -1 = 3
    assert app.s.n == 3
    assert "Count: 3" in p.render()


def test_pilot_quit_key_stops():
    app = _counter()
    p = app.test()
    assert p.running
    p.press("q")
    assert not p.running


def test_pilot_ctrl_c_quits_by_default():
    app = _counter()
    p = app.test()
    p.press("c", ctrl=True)
    assert not p.running


def test_pilot_reset_handler():
    app = _counter()
    p = app.test()
    p.press("+", "+", "+")
    assert app.s.n == 3
    p.press("r")
    assert app.s.n == 0


def test_pilot_keys_map_model():
    class Todo:
        def __init__(self):
            self.items = [("a", False), ("b", False), ("c", False)]
            self.cursor = 0

        def move(self, d):
            self.cursor = (self.cursor + d) % len(self.items)

        def toggle(self):
            t, d = self.items[self.cursor]
            self.items[self.cursor] = (t, not d)

    app = App("todo", model=Todo(), quit_keys=("q",),
              keys={"down": lambda s: s.move(+1),
                    "up": lambda s: s.move(-1),
                    "space": lambda s: s.toggle()})

    @app.view
    def view(s):
        return col(*[f"{'>' if i == s.cursor else ' '} {t} {d}"
                     for i, (t, d) in enumerate(s.items)])

    p = app.test()
    p.press("down", "down")
    assert app.s.cursor == 2
    p.press("space")
    assert app.s.items[2][1] is True
    p.press("up")
    assert app.s.cursor == 1


def test_pilot_text_input_focus():
    app = App("form", quit_keys=("esc",))
    name = text_input("name")
    app.focus(name)

    @app.view
    def view(s):
        return col("Name:", name, f"hi {name.value}")

    p = app.test(width=40)
    p.type("Ada")
    assert name.value == "Ada"
    assert "hi Ada" in p.render()
    p.press("backspace")
    assert name.value == "Ad"


def test_pilot_frame_ticks_deterministic():
    app = App("anim", t=0.0)

    @app.on_frame
    def tick(s, dt):
        s.t += dt

    @app.view
    def view(s):
        return col(f"t={s.t:.1f}")

    p = app.test()
    p.tick(0.5)
    p.tick(0.5)
    p.tick(1.0)
    assert abs(app.s.t - 2.0) < 1e-9


def test_pilot_mouse_click_and_scroll():
    app = App("m", last=None, scrolls=0)

    @app.on_click("left")
    def clk(s, c, r):
        s.last = (c, r)

    @app.on_scroll
    def scr(s, d):
        s.scrolls += d

    @app.view
    def view(s):
        return col(f"{s.last} {s.scrolls}")

    p = app.test()
    p.click(7, 3)
    assert app.s.last == (7, 3)
    p.scroll("up")     # -1
    p.scroll("down")   # +1
    p.scroll("down")   # +1
    assert app.s.scrolls == 1


def test_pilot_paste_and_resize():
    app = App("pr", pasted=None, size=None)

    @app.on_paste
    def on_paste(s, text):
        s.pasted = text

    @app.on_resize
    def on_resize(s, cols, rows):
        s.size = (cols, rows)

    @app.view
    def view(s):
        return col(f"{s.pasted} {s.size}")

    p = app.test()
    p.paste("clipboard")
    assert app.s.pasted == "clipboard"
    p.resize(120, 40)
    assert app.s.size == (120, 40)


def test_pilot_context_manager():
    app = _counter()
    with app.test() as p:
        p.press("+", "+")
        assert p.state.n == 2
        p.press("q")
        assert not p.running
