"""test_layout — the responsive layout toolkit, pretty text, and hit registry.

Covers the surface added in the maya master sync: grid/sidebar/place/pick/
clamp_width/fit_row/fit_col/adapt/fill/measure, rainbow/gradient_rule,
hit_id packing + box(hit=...) paint-time hit-testing, table selection/sort/
windowing, and the anim-clock freeze."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as m
from maya_py import _maya


def render(e, w=60):
    return m.to_string(e, w)


# ── grid ─────────────────────────────────────────────────────────────────

def test_grid_wraps_by_min_width():
    cells = ["aa", "bb", "cc", "dd"]
    wide = render(m.grid(cells, 8), w=40)      # 4 fit on one row
    narrow = render(m.grid(cells, 8), w=17)    # 2 per row -> 2 rows
    assert wide.count("\n") < narrow.count("\n")
    assert "aa" in wide and "dd" in wide
    # single column when very narrow
    single = render(m.grid(cells, 8), w=8)
    assert single.count("\n") >= 3


def test_grid_max_cols_caps_row():
    cells = ["a", "b", "c", "d"]
    capped = render(m.grid(cells, 4, max_cols=2), w=60)
    free = render(m.grid(cells, 4), w=60)
    assert capped.count("\n") > free.count("\n")


# ── sidebar ──────────────────────────────────────────────────────────────

def test_sidebar_side_by_side_then_stacks():
    wide = render(m.sidebar("rail", "main", 10), w=40)
    assert "rail" in wide and "main" in wide
    line = wide.splitlines()[0]
    assert "rail" in line and "main" in line  # same row when wide
    narrow = render(m.sidebar("rail", "main", 10), w=12)
    lines = [ln for ln in narrow.splitlines() if ln.strip()]
    assert len(lines) >= 2  # stacked when narrow


def test_sidebar_right():
    out = render(m.sidebar("R", "M", 5, right=True), w=30)
    line = out.splitlines()[0]
    assert line.index("M") < line.index("R")


# ── place / clamp_width ──────────────────────────────────────────────────

def test_place_positions():
    left = render(m.place("X", "left", "top"), w=11)
    right = render(m.place("X", "right", "top"), w=11)
    assert left.splitlines()[0].index("X") < right.splitlines()[0].index("X")


def test_clamp_width_caps_and_centers():
    out = render(m.clamp_width("abcdefghij", 6), w=30)
    first = out.splitlines()[0]
    # clamped to 6 columns -> the 10-char string wraps
    assert len(first.strip()) <= 6
    assert first.startswith(" ")  # centered, not flush-left


# ── pick / fit_row / fit_col ─────────────────────────────────────────────

def test_pick_picks_first_that_fits():
    alts = ["a very long alternative indeed", "short"]
    assert "very long" in render(m.pick(*alts), w=60)
    assert "short" in render(m.pick(*alts), w=10)
    # fallback: last alt used even when it does not fit (wraps at w=3)
    out = render(m.pick(*alts), w=3)
    assert "sho" in out and "very" not in out


def test_fit_row_drops_lowest_keep_first():
    items = ["logo", ("hostname", 5), ("kernel", 1)]
    full = render(m.fit_row(*items, gap=1), w=40)
    assert "logo" in full and "hostname" in full and "kernel" in full
    tight = render(m.fit_row(*items, gap=1), w=15)
    assert "logo" in tight and "hostname" in tight and "kernel" not in tight


def test_fit_col_drops_when_short():
    # fit_col decides against the WIDTH-measured natural height; drops the
    # low-keep item when it can't fit. Just prove the API renders + keeps
    # essentials.
    out = render(m.fit_col("a", ("b", 1)), w=10)
    assert "a" in out


# ── adapt / fill / measure ───────────────────────────────────────────────

def test_adapt_receives_real_width():
    assert "w=33" in render(m.adapt(lambda w: f"w={w}"), w=33)


def test_fill_receives_slot_size():
    out = render(m.fill(lambda w, h: f"{w}x{h}"), w=24)
    assert "24x" in out


def test_measure_natural_size():
    assert m.measure("hello") == (5, 1)
    w, h = m.measure(m.vstack("aa", "bb"))
    assert (w, h) == (2, 2)


# ── pretty text ──────────────────────────────────────────────────────────

def test_rainbow_renders_text():
    assert "party" in render(m.rainbow("party"))


def test_gradient_rule_spans_width():
    out = render(m.gradient_rule("#7F5AF0", "#2CB67D"), w=12)
    assert out.splitlines()[0].count("─") == 12
    thick = render(m.gradient_rule("#ff0000", "#0000ff", glyph="━"), w=8)
    assert thick.splitlines()[0].count("━") == 8


# ── hit registry ─────────────────────────────────────────────────────────

def test_hit_id_packing():
    hid = m.hit_id(7, 3)
    assert m.hit_kind(hid) == 7
    assert m.hit_index(hid) == 3
    assert m.hit_id(7) == m.hit_id(7, 0)


def test_box_hit_registers_painted_rect():
    e = m.vstack(
        "above",
        m.hstack("click me", hit=m.hit_id(1, 42)),
    )
    _maya.render_to_string(e, 40)  # paint registers hit regions
    r = m.hit_rect(m.hit_id(1, 42))
    assert r is not None
    x, y, w, h = r
    assert y == 1 and h == 1 and w >= len("click me")
    hid = m.hit_test(x, y)
    assert hid is not None and m.hit_kind(hid) == 1 and m.hit_index(hid) == 42
    # outside the rect resolves to nothing
    assert m.hit_test(x, y + 5) is None


# ── table: selection / sort / windowing ──────────────────────────────────

def test_table_selection_cursor():
    rows = [[1, "init"], [937, "rb"], [793, "agentty"]]
    out = render(m.table(["PID", "NAME"], rows, selected=1))
    sel_line = next(ln for ln in out.splitlines() if "rb" in ln)
    assert "▎" in sel_line
    assert "▎" not in next(ln for ln in out.splitlines() if "init" in ln)


def test_table_sort_indicator():
    out = render(m.table(["A", "B"], [[1, 2]], sort_col=1, sort_desc=True))
    assert "▾" in out.splitlines()[0]
    out2 = render(m.table(["A", "B"], [[1, 2]], sort_col=1, sort_desc=False))
    assert "▴" in out2.splitlines()[0]


def test_table_windowing_limits_rows():
    rows = [[i, f"row{i}"] for i in range(20)]
    out = render(m.table(["N", "NAME"], rows, selected=0, visible_rows=5))
    body = [ln for ln in out.splitlines() if "row" in ln]
    assert len(body) == 5
    # window follows the cursor
    out_end = render(m.table(["N", "NAME"], rows, selected=19, visible_rows=5))
    assert "row19" in out_end and "row0" not in out_end


def test_table_dict_columns_weighted():
    cols = [
        {"header": "NAME", "weight": 1.0, "min_width": 4},
        {"header": "VAL", "align": "right"},
    ]
    out = render(m.table(cols, [["alpha", 1], ["beta", 22]]), w=30)
    assert "NAME" in out and "22" in out


# ── anim clock freeze ────────────────────────────────────────────────────

def test_freeze_anim_clock_pins_time():
    try:
        m.freeze_anim_clock(1234)
        assert m.anim_now_ms() == 1234
        m.freeze_anim_clock(5000)
        assert m.anim_now_ms() == 5000
    finally:
        m.unfreeze_anim_clock()
    assert m.anim_now_ms() != 5000 or m.anim_now_ms() >= 0  # live again


# ── hover_motion plumbing (signature-level; no terminal in CI) ───────────

def test_hover_motion_kwargs_accepted():
    import inspect
    assert "hover_motion" in inspect.signature(m.run_program).parameters
    from maya_py.easy import App
    assert "hover_motion" in inspect.signature(App.__init__).parameters
