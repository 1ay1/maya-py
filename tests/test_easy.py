"""Tests for the friendly high-level API (maya_py.easy)."""
import maya_py as maya
from maya_py import T, b, c, col, row, card, field, hr, color, App


def test_T_chain_renders():
    out = maya.to_string(T("hi").bold.fg("sky"), 20)
    assert "hi" in out


def test_bare_strings_in_layout():
    out = maya.to_string(col("alpha", "beta"), 20)
    assert "alpha" in out and "beta" in out


def test_color_names_and_hex():
    assert color("red") is not None
    assert color("#ff8800") is not None
    assert color("#f80") is not None       # short hex
    assert color((1, 2, 3)) is not None
    assert color(0xFF8800) is not None


def test_field_renders_label_and_value():
    out = maya.to_string(field("Status", "Online"), 30)
    assert "Status:" in out and "Online" in out


def test_card_has_border_and_title():
    out = maya.to_string(card("body", title="hi"), 20)
    assert "╭" in out and "hi" in out and "body" in out


def test_markup_helpers():
    assert "x" in maya.to_string(b("x"), 10)
    assert "x" in maya.to_string(c("x", "green"), 10)


def test_hr():
    out = maya.to_string(hr(5), 20)
    assert "─" in out


def test_T_concat_keeps_left_style():
    t = b("bold ") + "plain"
    out = maya.to_string(t, 30)
    assert "bold plain" in out


def test_app_bindings_dispatch():
    app = App("t")
    app.state(n=0)

    @app.on("+")
    def inc(s):
        s.n += 1

    @app.on("q")
    def quit_(s):
        app.stop()

    # exercise the matcher table without a tty
    assert app.s.n == 0
    inc(app.s)
    inc(app.s)
    assert app.s.n == 2
    # quit handler flips running flag
    quit_(app.s)
    assert app._running is False


def test_app_view_renders():
    app = App("t")
    app.state(msg="hello")

    @app.view
    def v(s):
        return card(s.msg)

    out = maya.to_string(app._render(), 20)
    assert "hello" in out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("done")
