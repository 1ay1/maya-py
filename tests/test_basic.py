"""Basic smoke tests — render Elements to strings (no tty needed)."""
import maya_py as maya


def test_text_render():
    out = maya.render_to_string(maya.text("hello"), 20)
    assert "hello" in out


def test_box_borders():
    ui = maya.box(maya.text("x"), border=maya.Round, padding=1)
    out = maya.render_to_string(ui, 20)
    assert "╭" in out and "╰" in out
    assert "x" in out


def test_vstack_stacks():
    ui = maya.vstack(maya.text("aaa"), maya.text("bbb"))
    out = maya.render_to_string(ui, 20)
    lines = [l for l in out.splitlines() if l.strip()]
    # the two texts land on different rows
    assert any("aaa" in l for l in lines)
    assert any("bbb" in l for l in lines)
    a = next(i for i, l in enumerate(lines) if "aaa" in l)
    b = next(i for i, l in enumerate(lines) if "bbb" in l)
    assert a != b


def test_style_composition():
    s = maya.bold | maya.fg(255, 0, 0)
    assert not s.empty()
    assert "1" in s.to_sgr()  # bold code


def test_color_constructors():
    assert maya.rgb(1, 2, 3) is not None
    assert maya.hex(0xFF8800) is not None
    assert maya.Color.cyan() is not None


def test_truncation():
    ui = maya.text("a very long string indeed", maya.Style(), maya.TextWrap.TruncateEnd)
    out = maya.render_to_string(ui, 10)
    assert "…" in out


def test_print_routes_string(capsys):
    maya.print("plain")
    assert "plain" in capsys.readouterr().out


if __name__ == "__main__":
    # Allow running without pytest.
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and "capsys" not in fn.__code__.co_varnames:
            fn()
            print(f"ok  {name}")
    print("done")
