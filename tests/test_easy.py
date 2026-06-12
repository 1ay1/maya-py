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


def test_memo_caches_until_args_change():
    from maya_py import memo
    calls = []

    @memo
    def build(label):
        calls.append(label)
        return card(label)

    a1 = build("x")
    a2 = build("x")          # same args -> cached, builder NOT called again
    assert a1 is a2
    assert calls == ["x"]
    build("y")               # new args -> rebuild
    assert calls == ["x", "y"]


def test_T_fast_path_renders_colors():
    # the styled_text fast path must still produce correct SGR output
    out = maya.to_string(T("hi").bold.fg("sky").bg("red"), 20)
    assert "hi" in out
    # element is cached on the T after first build
    t = T("z").fg("green")
    assert t.element() is t.element()


def test_T_color_object_still_works():
    # passing a raw Color (low-level) routes through the slow path correctly
    out = maya.to_string(T("c").fg(maya.Color.cyan()), 20)
    assert "c" in out


def test_trow_byte_identical_to_row_of_T():
    from maya_py import trow, DIM
    a = row(T("svc").fg("sky"), c("OK", "green"), T("5ms").dim,
            T("100").fg("gold"), gap=2)
    b_ = trow(("svc", "sky"), ("OK", "green"), ("5ms", None, None, DIM),
              ("100", "gold"), gap=2)
    assert maya.to_string(a, 60) == maya.to_string(b_, 60)


def test_trow_plain_strings():
    from maya_py import trow
    out = maya.to_string(trow("a", "b", "c", gap=1), 20)
    assert "a" in out and "b" in out and "c" in out


def test_tcol_stacks_vertically():
    from maya_py import tcol
    out = maya.to_string(tcol(("top", "sky"), ("bot", "red")), 20)
    assert "top" in out and "bot" in out
    assert out.count("\n") >= 1   # two rows


def test_field_fast_path_matches_T_path():
    # plain-string value goes through trow; a T value goes through row(T)
    plain = maya.to_string(field("Status", "Online", value_color="green"), 30)
    via_t = maya.to_string(field("Status", T("Online").fg("green")), 30)
    assert plain == via_t


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("done")
