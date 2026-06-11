"""test_widgets — maya's native widget renderers are reachable from Python."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as m

_passed = 0


def check(name, cond):
    global _passed
    assert cond, f"FAIL {name}"
    _passed += 1
    print("ok ", name)


def render(e, w=60):
    return m.to_string(e, w)


def test_sparkline():
    out = render(m.sparkline([1, 5, 3, 8, 2, 9], label="cpu", show_last=True))
    check("sparkline_label", "cpu" in out)
    # contains block glyphs
    check("sparkline_blocks", any(c in out for c in "▁▂▃▄▅▆▇█"))


def test_gauge_arc_and_bar():
    arc = render(m.gauge(0.5, "x"))
    bar = render(m.gauge(0.5, "x", style="bar"))
    check("gauge_pct", "50%" in arc and "50%" in bar)
    check("gauge_styles_differ", arc != bar)


def test_progress_fills():
    out = render(m.progress(0.5, width=20))
    check("progress_pct", "50%" in out)
    check("progress_fill", "█" in out)


def test_badge_kinds():
    for kind in ("success", "error", "warning", "info", "tool"):
        check(f"badge_{kind}", "[X]" in render(m.badge("X", kind=kind)))


def test_divider():
    check("divider_label", "sec" in render(m.divider("sec")))


def test_spinner():
    # a spinner is a single frame glyph
    check("spinner_nonempty", render(m.spinner()).strip() != "")


def test_table_alignment_and_border():
    out = render(m.table(
        ["Name", ("Score", 0, "right")],
        [["Ada", 99], ["Bob", 7]],
        bordered=True, title="scores",
    ))
    check("table_title", "scores" in out)
    check("table_cells", "Ada" in out and "99" in out)
    check("table_border", "╭" in out)


def test_table_plain():
    out = render(m.table(["A", "B"], [["1", "2"]]))
    check("table_plain", "A" in out and "1" in out and "╭" not in out)


def test_callout():
    out = render(m.callout("Heads up", "details here", kind="warning"))
    check("callout_title", "Heads up" in out)
    check("callout_body", "details" in out)


def test_status_banner():
    check("status_banner", "saved" in render(m.status_banner("saved")))


def test_breadcrumb():
    out = render(m.breadcrumb(["home", "projects", "maya-py"]))
    check("breadcrumb_segments", "home" in out and "maya-py" in out)


def test_tabs():
    out = render(m.tabs(["One", "Two", "Three"], active=1))
    check("tabs_labels", "One" in out and "Two" in out and "Three" in out)


def test_bar_chart():
    out = render(m.bar_chart([("a", 2), ("b", 8), ("c", 5)]))
    check("bar_chart_labels", "a" in out and "b" in out)
    check("bar_chart_bars", "█" in out)


def test_bar_chart_colors():
    # per-bar color tuple accepted
    out = render(m.bar_chart([("a", 2, "sky"), ("b", 8, (80, 220, 120))]))
    check("bar_chart_colored", "█" in out)


def test_gradient():
    check("gradient_text", "hello" in render(m.gradient("hello", "red", "blue")))


def test_heatmap():
    out = render(m.heatmap([[0.1, 0.9], [0.5, 0.3]]))
    check("heatmap_blocks", "█" in out)


def test_color_names_everywhere():
    # color names, tuples, and hex all accepted by widget wrappers
    render(m.sparkline([1, 2, 3], color="sky"))
    render(m.gauge(0.5, color=(80, 220, 120)))
    render(m.progress(0.5, fill="#ff8800"))
    check("widget_color_coercion", True)


if __name__ == "__main__":
    g = dict(globals())
    for name, fn in sorted(g.items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print(f"\n{_passed} checks passed")
