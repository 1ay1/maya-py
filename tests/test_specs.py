"""test_specs — the native spec-flattening engine (stack_specs/rows_specs).

row()/col()/rows() flatten children entirely in C++ since 0.3.1. These tests
pin the semantics: palette + #hex + tuple colours, T-slot reads, Element
passthrough, the Python fallback for exotic children, and error behaviour —
all byte-identical to the pre-native path."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import maya_py as m
from maya_py import row, col, rows, T


def render(e, w=40):
    return m.to_string(e, w)


def test_tuple_specs_palette_and_hex():
    out = render(row(("a", "sky"), ("b", "#ff0000"), ("c", (10, 20, 30))))
    assert out.splitlines()[0] == "abc"
    # repeated #hex literal hits the native memo (same output, no error)
    out2 = render(row(("d", "#ff0000")))
    assert "d" in out2


def test_bare_str_and_attrs():
    out = render(row("x", ("y", None, None, m.DIM), gap=1))
    assert "x y" in out


def test_plain_int_T_flattens_natively():
    out = render(row(T("bold").bold, T("colored").fg("gold")))
    assert "boldcolored" in out


def test_color_object_T_falls_back():
    # A T carrying a Color OBJECT can't flatten natively — the fallback
    # path must produce the styled text all the same.
    t = T("hsl").fg(m.Color.hsl(120, 0.5, 0.5))
    out = render(row(t, "tail"))
    assert "hsltail" in out


def test_element_passthrough_mixed():
    # built Elements mix with tuple specs in ONE native call
    out = render(row(m.text("a"), ("b", "sky"), "c"))
    assert out.splitlines()[0] == "abc"


def test_nested_boxes_render():
    out = render(col(row("a", "b"), row("c", "d")))
    assert out.splitlines() == ["ab", "cd"]


def test_unknown_color_raises_valueerror():
    with pytest.raises(ValueError):
        render(row(("x", "notacolor")))


def test_rows_generator_and_lists():
    out = render(rows([("a", "sky"), ("b",)] for _ in range(3)))
    assert out.splitlines() == ["ab", "ab", "ab"]
    out2 = render(rows([[("x",)], [("y",)]]))
    assert out2.splitlines() == ["x", "y"]


def test_rows_single_cell_collapse():
    # single-cell rows must not grow a wrapper box (flat col of text)
    a = render(rows([[("one", "sky")], [("two", "gold")]]))
    b = render(col(("one", "sky"), ("two", "gold")))
    assert a == b


def test_rows_transpose():
    out = render(rows([[("a",), ("b",)], [("c",), ("d",)]], transpose=True))
    lines = out.splitlines()
    assert lines[0] == "ac" and lines[1] == "bd"


def test_rows_inner_gap_and_gap():
    out = render(rows([[("a",), ("b",)]], inner_gap=2))
    assert out.splitlines()[0] == "a  b"
    out2 = render(rows([[("a",)], [("b",)]], gap=1))
    assert out2.splitlines() == ["a", "", "b"]


def test_rows_fallback_on_element_cell():
    # an Element cell forces the Python fallback — same visual result
    out = render(rows([[m.text("el"), ("t", "sky")]]))
    assert "elt" in out


def test_rows_empty():
    assert render(rows([])) == ""


def test_equivalence_T_vs_tuple_vs_rows():
    """The three idioms must produce byte-identical output."""
    data = [("svc-a", "OK"), ("svc-b", "ERR")]
    via_T = render(col(*[row(T(n).fg("sky"), T(s).fg("red"), gap=1)
                         for n, s in data]))
    via_tuple = render(col(*[row((n, "sky"), (s, "red"), gap=1)
                             for n, s in data]))
    via_rows = render(rows(([(n, "sky"), (s, "red")] for n, s in data),
                           inner_gap=1))
    assert via_T == via_tuple == via_rows


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("done")
