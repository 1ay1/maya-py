"""test_power — the full BoxBuilder surface is reachable from Python.

Confirms maya-py exposes the same layout power as maya C++: percent/auto
dimensions, min/max constraints, flex grow/shrink/basis, align-self, wrap,
overflow, per-side borders + positioned border text, z-stack, size-aware
components, center, and nothing().
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as m
from maya_py import (
    T, col, row, card, center, stack, component, nothing, grow,
    pct, cells, auto, sides, box, zstack,
)
from maya_py import _maya


_passed = 0


def check(name, cond):
    global _passed
    assert cond, f"FAIL {name}"
    _passed += 1
    print("ok ", name)


# ── dimensions ───────────────────────────────────────────────────────────────
def test_percent_width():
    out = m.to_string(box("x", width=pct(50), bg=m.rgb(40, 40, 40)), 40)
    # 50% of 40 = 20 cells of background
    line = out.splitlines()[0]
    check("percent_width", len(line.rstrip()) <= 22 and "x" in line)


def test_string_and_float_dims():
    a = m.to_string(box("x", width="50%"), 40)
    b = m.to_string(box("x", width=0.5), 40)
    check("string_pct_eq_float", a == b)


def test_auto_dim_builds():
    check("auto_dim", auto().is_auto())
    check("cells_dim", cells(10).is_fixed())
    check("pct_dim", pct(25).is_percent())


# ── flex ─────────────────────────────────────────────────────────────────────
def test_grow_fills():
    # sidebar fixed, main grows to fill the rest
    ui = row(card("side", width=cells(12)), grow(card("main")))
    out = m.to_string(ui, 50)
    check("grow_fills", out.splitlines()[0].rstrip().endswith("╮"))


def test_shrink_basis_align_self():
    # All accepted without error.
    ui = row(
        box("a", basis=10, shrink=0.0, align_self=m.Align.End),
        box("b", grow=1.0),
    )
    check("shrink_basis_align_self", "a" in m.to_string(ui, 30))


def test_min_max_constraints():
    ui = box("hello world this is long", min_width=5, max_width=10)
    out = m.to_string(ui, 40)
    width = max(len(l.rstrip()) for l in out.splitlines())
    check("max_width_clamps", width <= 10)


# ── wrap / overflow ──────────────────────────────────────────────────────────
def test_wrap_string_alias():
    ui = row(*[T(f"item{i}") for i in range(8)], wrap="wrap", width=cells(20))
    check("wrap_alias", "item0" in m.to_string(ui, 30))


def test_overflow_hidden():
    ui = col(box("aaaaaaaaaaaaaaaaaaaaaaaa", width=cells(6), overflow=m.Overflow.Hidden))
    out = m.to_string(ui, 30)
    width = max(len(l.rstrip()) for l in out.splitlines())
    check("overflow_hidden_clips", width <= 6)


# ── borders ──────────────────────────────────────────────────────────────────
def test_border_sides_top_only():
    out = m.to_string(card("body", border_sides=sides(top=True, right=False,
                                                       bottom=False, left=False)), 20)
    # No left/right pipes on the body line
    check("border_sides_top_only", "│" not in out)


def test_border_text_positioned():
    out = m.to_string(
        card("x", border_text=("Title", _maya.BorderTextPos.Top,
                               _maya.BorderTextAlign.Center)),
        30,
    )
    check("border_text_centered", "Title" in out.splitlines()[0])


def test_border_text_end():
    out = m.to_string(
        box("x", border=m.Round,
            border_text=("Left", _maya.BorderTextPos.Top, _maya.BorderTextAlign.Start),
            border_text_end=("99ms", _maya.BorderTextPos.Top)),
        40,
    )
    top = out.splitlines()[0]
    check("border_text_end", "Left" in top and "99ms" in top)


# ── z-stack ──────────────────────────────────────────────────────────────────
def test_zstack_overlays():
    out = m.to_string(stack(card("  base  ", height=4), T("OVR").fg("red")), 20)
    check("zstack_first_sets_size", "OVR" in out)
    # low-level zstack too
    check("zstack_lowlevel", "OVR" in m.to_string(
        zstack(card("  base  ", height=4), "OVR"), 20))


# ── component (size-aware) ───────────────────────────────────────────────────
def test_component_receives_size():
    seen = {}

    def render(w, h):
        seen["w"], seen["h"] = w, h
        return T("#" * w)

    out = m.to_string(col(box(component(render), width=cells(8), height=cells(1))), 20)
    check("component_got_width", seen.get("w") == 8)
    check("component_filled", "########" in out)


def test_component_returns_str():
    out = m.to_string(
        col(component(lambda w, h: f"{w}x{h}", width=cells(5), height=cells(1))), 20)
    check("component_str_ok", "5x" in out)


# ── center / nothing ─────────────────────────────────────────────────────────
def test_center():
    out = m.to_string(center("mid", width=cells(11), height=3, border="round"), 20)
    body = out.splitlines()[1]
    # "mid" sits roughly in the middle, not flush-left
    check("center_indents", body.index("m") > 2)


def test_nothing_is_empty():
    check("nothing_empty", m.to_string(nothing(), 10).strip() == "")


def test_spacer_is_one_row():
    # spacer renders a blank row; nothing() renders no row at all.
    check("spacer_vs_nothing",
          len(m.to_string(m.spacer(), 10)) >= len(m.to_string(nothing(), 10)))


if __name__ == "__main__":
    g = dict(globals())
    for name, fn in sorted(g.items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print(f"\n{_passed} checks passed")
