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


# ── friendly errors ──────────────────────────────────────────────────────────

def test_unknown_color_suggests_nearest():
    import pytest
    from maya_py import T
    with pytest.raises(ValueError) as ei:
        T("x").fg("skyblue")
    msg = str(ei.value)
    assert "unknown color" in msg
    assert "did you mean" in msg          # nearest-match hint
    assert "sky" in msg                   # valid names listed


def test_view_returning_none_names_the_view():
    import pytest
    from maya_py import App, col
    app = App("x")

    @app.view
    def myview(s):
        col("oops, forgot return")

    with pytest.raises(TypeError) as ei:
        app.test().render()
    msg = str(ei.value)
    assert "myview" in msg and "None" in msg and "return" in msg


def test_view_returning_wrong_type_names_the_view():
    import pytest
    from maya_py import App
    app = App("y")
    app.view(lambda s: 42)
    with pytest.raises(TypeError) as ei:
        app.test().render()
    assert "not renderable" in str(ei.value) or "renderable" in str(ei.value)


# ── CLI scaffold ─────────────────────────────────────────────────────────────

def test_cli_new_creates_runnable_app(tmp_path):
    import os
    from maya_py.__main__ import main
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = main(["new", "My Cool App"])
        assert rc == 0
        f = tmp_path / "My_Cool_App.py"
        assert f.exists()
        body = f.read_text()
        assert "App(" in body and "app.run()" in body
        # second call refuses to overwrite
        assert main(["new", "My Cool App"]) == 1
    finally:
        os.chdir(cwd)


def test_cli_version_and_help():
    from maya_py.__main__ import main
    assert main(["version"]) == 0
    assert main([]) == 0            # help
    assert main(["bogus"]) == 2     # unknown command


# ── declarative helpers: For / bind / derive ─────────────────────────────────

def test_for_maps_items_into_box():
    from maya_py import For, T
    out = maya.to_string(For([1, 2, 3], lambda x: T(f"item {x}")), 30)
    assert "item 1" in out and "item 2" in out and "item 3" in out


def test_for_two_param_renderer_gets_index():
    from maya_py import For, T
    out = maya.to_string(For(["a", "b"], lambda i, x: T(f"{i}:{x}")), 30)
    assert "0:a" in out and "1:b" in out


def test_for_empty_shows_fallback_and_nothing():
    from maya_py import For
    assert "none" in maya.to_string(For([], lambda x: x, empty="none"), 20)
    # No empty= → a zero-row fragment (renders blank).
    assert maya.to_string(For([], lambda x: x), 20).strip() == ""


def test_input_bind_writes_back_to_state():
    app = App("form", name="")
    name = text_input("your name", bind=(app.s, "name"))
    app.focus(name)
    app.view(lambda s: col("Name:", name, f"hi {s.name}"))
    p = app.test(width=30)
    p.type("Ada")
    assert app.s.name == "Ada"
    assert "hi Ada" in p.render()
    p.press("backspace")
    assert app.s.name == "Ad"


def test_input_bind_seeds_initial_value():
    app = App("form", name="Grace")
    name = text_input(bind=(app.s, "name"))
    assert name.value == "Grace"


def test_derive_exposes_computed_field():
    app = App("cart", items=[2.0, 3.5])

    @app.derive
    def total(s):
        return sum(s.items)

    assert app.s.total == 5.5
    app.s.items.append(4.0)
    assert app.s.total == 9.5      # recomputed on access, no stale cache


def test_derive_is_isolated_per_app():
    a = App("a", x=1)
    b = App("b", y=2)

    @a.derive
    def double(s):
        return s.x * 2

    @b.derive
    def triple(s):
        return s.y * 3

    assert a.s.double == 2 and b.s.triple == 6
    assert not hasattr(a.s, "triple")     # b's field must not leak onto a
    assert not hasattr(b.s, "double")


def test_derive_works_on_model_object():
    class Cart:
        def __init__(self):
            self.items = [1, 2, 3]

    app = App("m", model=Cart())

    @app.derive
    def count(s):
        return len(s.items)

    assert app.s.count == 3


# ── MVU Program harness (the Elm Architecture, headless) ────────────────────

from maya_py import Cmd, Program, program_test  # noqa: E402


class _Counter(Program):
    def init(self):
        return {"count": 0}, Cmd.set_title("counter")

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
        return card(b(f"count: {m['count']}"), title="counter")


def test_program_pilot_threads_pure_update():
    p = _Counter().test()
    assert p.model == {"count": 0}
    p.send("inc", "inc", "inc", "dec")
    assert p.model == {"count": 2}
    assert "count: 2" in p.view_string(40)


def test_program_pilot_captures_cmds():
    p = _Counter().test()
    assert len(p.cmds) == 1          # init's Cmd.set_title
    assert isinstance(p.last_cmd, Cmd)
    p.send("inc")                    # no cmd
    assert len(p.cmds) == 1
    p.send("quit")                   # Cmd.quit()
    assert len(p.cmds) == 2


def test_program_update_is_pure_and_immutable():
    c = _Counter()
    m0, _cmd = c.init()
    m1 = c.update(m0, "inc")
    assert m1 == {"count": 1}
    assert m0 == {"count": 0}        # original untouched
    assert c.update(m0, "???") == m0  # unknown msg = identity


def test_program_pilot_chains():
    p = _Counter().test().send("inc").send("inc").send("reset")
    assert p.model == {"count": 0}


def test_program_test_function_form():
    def init():
        return {"n": 5}

    def update(m, msg):
        return {**m, "n": m["n"] + 1} if msg == "up" else m

    p = program_test(init, update)       # no view
    p.send("up", "up", "up")
    assert p.model == {"n": 8}
    # view_string without a view raises, faithfully
    raised = False
    try:
        p.view_string()
    except RuntimeError:
        raised = True
    assert raised
