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


# ── controls ────────────────────────────────────────────────────────
def test_checkbox_and_toggle():
    check("checkbox_checked", "[x]" in render(m.checkbox("Accept", True)))
    check("checkbox_unchecked", "[ ]" in render(m.checkbox("Accept", False)))
    check("toggle_label", "Dark" in render(m.toggle("Dark", True)))


def test_radio_and_select():
    r = render(m.radio(["A", "B", "C"], selected=1))
    check("radio_items", "A" in r and "B" in r and "C" in r)
    s = render(m.select(["One", "Two", "Three"], cursor=1))
    check("select_cursor", "❯" in s)


def test_slider():
    out = render(m.slider(0.5, "Vol", width=20))
    check("slider_pct", "50%" in out)
    check("slider_fill", "█" in out)


def test_button_variants():
    check("button_label", "Save" in render(m.button("Save", variant="primary")))
    # all four variants render without error
    for v in ("default", "primary", "danger", "ghost"):
        render(m.button("x", variant=v))
    check("button_variants", True)


def test_calendar():
    out = render(m.calendar(2025, 6, today=(2025, 6, 11)))
    check("calendar_month", "June" in out or "2025" in out)


# ── charts ──────────────────────────────────────────────────────────
def test_line_chart():
    out = render(m.line_chart([1, 3, 2, 5, 4, 6], label="lat", color="green"))
    check("line_chart_label", "lat" in out)


def test_flame_and_waterfall():
    f = render(m.flame_chart([("main", 0, 10, 0), ("work", 2, 5, 1, "red")],
                             time_scale=10))
    check("flame_label", "main" in f)
    wf = render(m.waterfall([("GET /", 0, 1.2, "blue"), ("POST /x", 1.2, 0.8)],
                            time_scale=2))
    check("waterfall_label", "GET /" in wf)


# ── navigation / lists ──────────────────────────────────────────────
def test_link_and_breadcrumb():
    check("link_text", "maya" in render(m.link("maya", "https://x")))


def test_key_help():
    out = render(m.key_help([("ctrl+c", "quit"), ("j", "down", "nav")], title="Keys"))
    check("key_help_title", "Keys" in out)
    check("key_help_binding", "quit" in out)


def test_timeline():
    out = render(m.timeline([("build", "", "1.2s", "completed"),
                             ("test", "", "", "in_progress", 8)]))
    check("timeline_events", "build" in out and "test" in out)


def test_tree():
    # the root dict is the implicit container; its children are the visible
    # top-level rows.
    out = render(m.tree({"label": "root", "expanded": True,
                         "children": [{"label": "alpha"},
                                      {"label": "beta", "expanded": True,
                                       "children": [{"label": "gamma"}]}]}))
    check("tree_rows", "alpha" in out and "beta" in out and "gamma" in out)


def test_list_and_menu():
    lv = render(m.list_view([("Ada", "engineer", "*"), "Bob"], cursor=0))
    check("list_items", "Ada" in lv and "Bob" in lv)
    mn = render(m.menu([("Open", "^O"), {"separator": True}, ("Quit", "^Q", False)]))
    check("menu_items", "Open" in mn and "Quit" in mn)


def test_disclosure():
    out = render(m.disclosure("Details", open=True, content=m.markdown("**hi**")))
    check("disclosure_label", "Details" in out)
    check("disclosure_content", "hi" in out)


# ── agent UI / notifications ────────────────────────────────────────
def test_toast():
    out = render(m.toast([("Saved", "success"), ("Careful", "warning")]))
    check("toast_messages", "Saved" in out and "Careful" in out)


def test_todo_list():
    out = render(m.todo_list([("Write code", "completed"), ("Test", "in_progress")],
                             description="Sprint", status="running", elapsed=12.0))
    check("todo_items", "Write code" in out and "Test" in out)


def test_title_and_model_badge():
    check("title_chip", "Session" in render(m.title_chip("Session", edge_color="cyan")))
    check("model_badge", "Opus" in render(m.model_badge("Opus 4", compact=True)))


def test_file_ref_and_inline_diff():
    fr = render(m.file_ref("src/main.py", line=42))
    check("file_ref_path", "main.py" in fr and "42" in fr)
    d = render(m.inline_diff("foo bar", "foo baz", label="x.py"))
    check("inline_diff", "foo" in d)


def test_thinking_and_markdown():
    check("thinking", "think" in render(m.thinking("let me think...", active=True)))
    out = render(m.markdown("# Title\n- **bold** item"))
    check("markdown", "Title" in out and "bold" in out)


# ── graphics ────────────────────────────────────────────────────────
def test_image_and_canvas():
    img = render(m.image([[1, 0, 1], [0, 1, 0]], color="magenta"))
    check("image_nonempty", len(img.strip()) > 0)
    cv = render(m.canvas([["red", "blue", None], [None, "green", "yellow"]]))
    check("canvas_nonempty", len(cv.strip()) > 0)


# ── command palette ──────────────────────────────────────────────
def test_picker():
    out = render(m.picker(
        [("Opus 4.8", "anthropic", True), ("Sonnet", "anthropic"),
         {"leading": "GPT-5", "trailing": "openai", "active": True}],
        title="Models", accent="cyan",
        header=[m.dim_text("  search: o_")],
        footer=[m.dim_text("  enter select")],
        min_width=44,
    ))
    check("picker_rows", "Opus 4.8" in out and "GPT-5" in out)
    check("picker_title", "Models" in out)
    check("picker_header_footer", "search" in out and "select" in out)
    # cursor edge bar (▎) appears on the selected/active rows
    check("picker_cursor_bar", "▎" in out)


def test_picker_selected_index():
    # a bare `selected` index marks that row (cursor bar) even with str rows
    out = render(m.picker(["Apple", "Banana", "Cherry"], title="Fruit",
                          selected=1, min_width=24))
    check("picker_selected_index", "▎" in out and "Banana" in out)


def test_new_widget_color_coercion():
    render(m.slider(0.5, fill="sky", track=(40, 40, 40)))
    render(m.line_chart([1, 2, 3], color="#33cc88"))
    render(m.canvas([[(255, 0, 0)]]))
    render(m.title_chip("x", edge_color="cyan", text_color="white"))
    check("new_widget_color_coercion", True)


if __name__ == "__main__":
    g = dict(globals())
    for name, fn in sorted(g.items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print(f"\n{_passed} checks passed")
