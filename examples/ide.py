"""ide.py — VS Code / Zed-inspired terminal IDE layout.

A faithful 1:1 port of maya's C++ example ``examples/ide.cpp``: a file tree on
the left, a tabbed editor with line numbers and syntax highlighting in the
centre, an outline / diagnostics / git-changes sidebar on the right, a terminal
panel with build output at the bottom, and a status bar.

Controls:
  Tab       cycle open file tabs
  1         toggle left sidebar
  2         toggle right sidebar
  3         toggle bottom panel
  b         simulate build (progress bar + diagnostics)
  q/Esc     quit

Usage:  PYTHONPATH=src python examples/ide.py
"""


import _bootstrap  # noqa: F401,E402

from maya_py import (App, col, row, card, T, badge, sparkline, breadcrumb,
                     progress, grow, component, to_string)
from maya_py.easy import BOLD, UNDERLINE, DIM

# ── Syntax theme (rgb tuples) ────────────────────────────────────────────────
KW = (198, 120, 221)     # keywords — purple
STR = (152, 195, 121)    # strings — green
CMT = (92, 99, 112)      # comments — gray
TYPE = (86, 182, 194)    # types — cyan
NUM = (209, 154, 102)    # numbers — orange
FN = (229, 192, 123)     # functions — yellow
PLAIN = (171, 178, 191)  # plain text
PUNCT = (150, 156, 170)  # punctuation

BORDER = (50, 55, 70)
LINE_NUM = (92, 99, 112)

# Fixed panel widths (match ide.cpp: EXPLORER width 22, right sidebar width 28).
EXPLORER_W = 22
SIDEBAR_W = 28


def run(start, length, color, attrs=0):
    """A styled run relative to line start: (offset, length, color, attrs)."""
    return (start, length, color, attrs)


# ── File tree data ───────────────────────────────────────────────────────────
# (name, depth, is_dir, expanded, ext)
file_tree = [
    ("src",            0, True,  True,  ""),
    ("main.cpp",       1, False, False, ".cpp"),
    ("app.cpp",        1, False, False, ".cpp"),
    ("app.hpp",        1, False, False, ".hpp"),
    ("renderer.cpp",   1, False, False, ".cpp"),
    ("renderer.hpp",   1, False, False, ".hpp"),
    ("widget",         1, True,  True,  ""),
    ("button.cpp",     2, False, False, ".cpp"),
    ("button.hpp",     2, False, False, ".hpp"),
    ("input.cpp",      2, False, False, ".cpp"),
    ("utils",          0, True,  False, ""),
    ("tests",          0, True,  True,  ""),
    ("test_app.cpp",   1, False, False, ".cpp"),
    ("test_widget.cpp", 1, False, False, ".cpp"),
    ("CMakeLists.txt", 0, False, False, ".txt"),
    ("README.md",      0, False, False, ".md"),
    ("config.py",      0, False, False, ".py"),
]

# ── Tab data ─────────────────────────────────────────────────────────────────
# (name, path, language, breadcrumb)
tabs = [
    ("main.cpp",   "src/main.cpp",          "C++",    ["src", "main.cpp"]),
    ("app.hpp",    "src/app.hpp",           "C++",    ["src", "app.hpp"]),
    ("button.cpp", "src/widget/button.cpp", "C++",    ["src", "widget", "button.cpp"]),
    ("config.py",  "config.py",             "Python", ["config.py"]),
]


# ── Fake code content ─────────────────────────────────────────────────────────
# Each code line is (text, [run(offset, len, color), ...]).
def make_main_cpp():
    return [
        ("#include <iostream>", [run(0, 8, KW), run(9, 10, STR)]),
        ("#include \"app.hpp\"", [run(0, 8, KW), run(9, 9, STR)]),
        ("", []),
        ("// Entry point for the application",
         [run(0, len("// Entry point for the application"), CMT)]),
        ("namespace app {", [run(0, 9, KW), run(10, 3, TYPE), run(14, 1, PUNCT)]),
        ("", []),
        ("int main(int argc, char** argv) {",
         [run(0, 3, TYPE), run(4, 4, FN), run(9, 3, TYPE), run(20, 4, TYPE)]),
        ("    auto config = Config::load(\"app.toml\");",
         [run(4, 4, KW), run(17, 6, TYPE), run(25, 4, FN), run(30, 10, STR)]),
        ("    auto app = Application(config);",
         [run(4, 4, KW), run(15, 11, TYPE)]),
        ("", []),
        ("    // Initialize the rendering pipeline",
         [run(0, len("    // Initialize the rendering pipeline"), CMT)]),
        ("    if (!app.init()) {", [run(4, 2, KW), run(12, 4, FN)]),
        ("        std::cerr << \"Failed to initialize\\n\";",
         [run(8, 3, TYPE), run(22, 24, STR)]),
        ("        return 1;", [run(8, 6, KW), run(15, 1, NUM)]),
        ("    }", []),
        ("", []),
        ("    app.run();  // blocks until quit",
         [run(8, 3, FN), run(16, 20, CMT)]),
        ("    return 0;", [run(4, 6, KW), run(11, 1, NUM)]),
        ("}", []),
        ("", []),
        ("} // namespace app", [run(2, 16, CMT)]),
    ]


def make_app_hpp():
    return [
        ("#pragma once", [run(0, 12, KW)]),
        ("", []),
        ("#include <string>", [run(0, 8, KW), run(9, 8, STR)]),
        ("#include <vector>", [run(0, 8, KW), run(9, 8, STR)]),
        ("#include <memory>", [run(0, 8, KW), run(9, 8, STR)]),
        ("", []),
        ("namespace app {", [run(0, 9, KW), run(10, 3, TYPE)]),
        ("", []),
        ("struct Config {", [run(0, 6, KW), run(7, 6, TYPE)]),
        ("    std::string title;", [run(4, 3, TYPE), run(9, 6, TYPE)]),
        ("    int width  = 1280;", [run(4, 3, TYPE), run(17, 4, NUM)]),
        ("    int height = 720;", [run(4, 3, TYPE), run(17, 3, NUM)]),
        ("    bool vsync = true;", [run(4, 4, TYPE), run(17, 4, KW)]),
        ("", []),
        ("    static Config load(std::string_view path);",
         [run(4, 6, KW), run(11, 6, TYPE), run(18, 4, FN), run(23, 3, TYPE),
          run(28, 11, TYPE)]),
        ("};", []),
        ("", []),
        ("class Application {", [run(0, 5, KW), run(6, 11, TYPE)]),
        ("public:", [run(0, 6, KW)]),
        ("    explicit Application(const Config& cfg);",
         [run(4, 8, KW), run(13, 11, TYPE), run(25, 5, KW), run(31, 6, TYPE)]),
        ("", []),
        ("    bool init();", [run(4, 4, TYPE), run(9, 4, FN)]),
        ("    void run();", [run(4, 4, TYPE), run(9, 3, FN)]),
        ("    void quit();", [run(4, 4, TYPE), run(9, 4, FN)]),
        ("};", []),
        ("", []),
        ("} // namespace app", [run(2, 16, CMT)]),
    ]


def make_button_cpp():
    return [
        ("#include \"button.hpp\"", [run(0, 8, KW), run(9, 12, STR)]),
        ("", []),
        ("namespace app::widget {",
         [run(0, 9, KW), run(10, 3, TYPE), run(15, 6, TYPE)]),
        ("", []),
        ("Button::Button(std::string label, Callback on_click)",
         [run(0, 6, TYPE), run(8, 6, TYPE), run(15, 3, TYPE), run(20, 6, TYPE),
          run(35, 8, TYPE)]),
        ("    : label_(std::move(label))",
         [run(6, 6, PLAIN), run(13, 3, TYPE), run(18, 4, FN)]),
        ("    , on_click_(std::move(on_click))",
         [run(16, 3, TYPE), run(21, 4, FN)]),
        ("{}", []),
        ("", []),
        ("void Button::render(Canvas& canvas) {",
         [run(0, 4, TYPE), run(5, 6, TYPE), run(13, 6, FN), run(20, 6, TYPE)]),
        ("    auto [x, y, w, h] = bounds();", [run(4, 4, KW), run(27, 6, FN)]),
        ("", []),
        ("    // Draw button background",
         [run(0, len("    // Draw button background"), CMT)]),
        ("    for (int i = 0; i < w; ++i) {",
         [run(4, 3, KW), run(9, 3, TYPE), run(17, 1, NUM)]),
        ("        canvas.set(x + i, y, ' ', style_);",
         [run(15, 3, FN), run(35, 3, STR)]),
        ("    }", []),
        ("", []),
        ("    // Center the label text",
         [run(0, len("    // Center the label text"), CMT)]),
        ("    int offset = (w - static_cast<int>(label_.size())) / 2;",
         [run(4, 3, TYPE), run(18, 11, KW), run(30, 3, TYPE)]),
        ("    canvas.write(x + offset, y, label_, style_);", [run(11, 5, FN)]),
        ("}", []),
        ("", []),
        ("} // namespace app::widget", [run(2, 24, CMT)]),
    ]


def make_config_py():
    return [
        ("#!/usr/bin/env python3", [run(0, 22, CMT)]),
        ("\"\"\"Application configuration module.\"\"\"",
         [run(0, len("\"\"\"Application configuration module.\"\"\""), STR)]),
        ("", []),
        ("import toml", [run(0, 6, KW)]),
        ("from pathlib import Path",
         [run(0, 4, KW), run(14, 6, KW), run(21, 4, TYPE)]),
        ("", []),
        ("DEFAULT_WIDTH  = 1280", [run(17, 4, NUM)]),
        ("DEFAULT_HEIGHT = 720", [run(17, 3, NUM)]),
        ("", []),
        ("class AppConfig:", [run(0, 5, KW), run(6, 9, TYPE)]),
        ("    \"\"\"Holds parsed app configuration.\"\"\"",
         [run(4, len("    \"\"\"Holds parsed app configuration.\"\"\"") - 4, STR)]),
        ("", []),
        ("    def __init__(self, path: str = \"app.toml\"):",
         [run(4, 3, KW), run(8, 8, FN), run(22, 3, TYPE), run(33, 10, STR)]),
        ("        self.data = toml.load(path)",
         [run(8, 4, KW), run(25, 4, FN)]),
        ("", []),
        ("    @property", [run(4, 9, KW)]),
        ("    def title(self) -> str:",
         [run(4, 3, KW), run(8, 5, FN), run(23, 3, TYPE)]),
        ("        return self.data.get(\"title\", \"Untitled\")",
         [run(8, 6, KW), run(33, 7, STR), run(42, 10, STR)]),
    ]


code_buffers = [
    make_main_cpp(),
    make_app_hpp(),
    make_button_cpp(),
    make_config_py(),
]

# ── Outline data: (name, kind, line) per tab ─────────────────────────────────
outlines = [
    [("main", "fn", 7), ("config", "var", 8), ("app", "var", 9),
     ("init", "fn", 12), ("run", "fn", 17)],
    [("Config", "struct", 9), ("load", "fn", 16), ("Application", "class", 19),
     ("init", "fn", 24), ("run", "fn", 25), ("quit", "fn", 26)],
    [("Button", "class", 5), ("render", "fn", 10), ("offset", "var", 20),
     ("write", "fn", 21)],
    [("DEFAULT_WIDTH", "var", 7), ("DEFAULT_HEIGHT", "var", 8),
     ("AppConfig", "class", 10), ("__init__", "fn", 13), ("title", "fn", 17)],
]

# ── Diagnostics: (file, line, message, severity[0=err,1=warn,2=info]) ─────────
diagnostics = [
    ("src/renderer.cpp", 42, "unused variable 'tmp'", 1),
    ("src/app.cpp", 87, "implicit conversion loses precision", 1),
    ("src/widget/input.cpp", 15, "uninitialized member 'buf_'", 0),
    ("src/main.cpp", 23, "consider using std::string_view", 2),
    ("tests/test_app.cpp", 9, "deprecated function 'setUp'", 1),
]

# ── Git changes: (file, added, removed, status) ──────────────────────────────
git_changes = [
    ("src/main.cpp", 12, 3, "M"),
    ("src/app.cpp", 45, 18, "M"),
    ("src/widget/button.cpp", 8, 0, "A"),
    ("src/renderer.hpp", 3, 7, "M"),
    ("config.py", 5, 0, "A"),
]

# ── Build output ─────────────────────────────────────────────────────────────
build_log = [
    "$ cmake --build build --target app",
    "[1/12] Compiling src/main.cpp",
    "[2/12] Compiling src/app.cpp",
    "[3/12] Compiling src/renderer.cpp",
]

build_complete_log = [
    "$ cmake --build build --target app",
    "[1/12] Compiling src/main.cpp",
    "[2/12] Compiling src/app.cpp",
    "[3/12] Compiling src/renderer.cpp",
    "[4/12] Compiling src/widget/button.cpp",
    "[5/12] Compiling src/widget/input.cpp",
    "[6/12] Linking libwidget.a",
    "[7/12] Linking app",
    "",
    "src/renderer.cpp:42:9: warning: unused variable 'tmp'",
    "src/app.cpp:87:15: warning: implicit conversion",
    "src/widget/input.cpp:15:5: error: uninitialized member",
    "",
    "Build finished with 1 error, 2 warnings.",
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def _runs_to_cells(text, runs):
    """Convert (text + ordered runs) into row tuple-cells covering the whole
    line, filling uncovered spans with PLAIN."""
    cells = []
    pos = 0
    for off, length, color, attrs in runs:
        if off > pos:
            cells.append((text[pos:off], PLAIN))
        cells.append((text[off:off + length], color, None, attrs))
        pos = off + length
    if pos < len(text):
        cells.append((text[pos:], PLAIN))
    return cells


def _clip_cells(cells, width):
    """Hard-clip a list of tuple-cells to ``width`` display columns, mirroring
    maya's ``| clip`` (no ellipsis) so fixed-width panels never wrap."""
    out = []
    used = 0
    for cell in cells:
        text = cell[0]
        if used >= width:
            break
        if used + len(text) > width:
            text = text[:width - used]
            cell = (text,) + tuple(cell[1:])
        out.append(cell)
        used += len(text)
    return out


def _clip_row(cells, width):
    return row(*_clip_cells(cells, width), gap=0)


def _panel_widths(avail):
    """Replicate maya's flex-shrink distribution of the three main columns.

    Measured from the C++ binary (explorer width(22), sidebar width(28),
    editor grow(1)) under flex pressure: both fixed panels shrink linearly
    at 1/5 of available width while the editor absorbs the remainder.
    """
    explorer = max(8, min(EXPLORER_W, avail // 5 - 2))
    sidebar = max(10, min(SIDEBAR_W, avail // 5 + 3))
    editor = max(10, avail - explorer - sidebar)
    return explorer, editor, sidebar


# ── UI Builders ──────────────────────────────────────────────────────────────
def build_file_tree(s, pw):
    rows = []
    for i, (name, depth, is_dir, expanded, ext) in enumerate(file_tree):
        indent = "  " * depth
        if is_dir:
            icon = "▾ " if expanded else "▸ "
            name_color = (200, 204, 212)
            name_attrs = BOLD
        else:
            icon = "  "
            if ext == ".cpp":
                name_color = (97, 175, 239)
            elif ext == ".hpp":
                name_color = (152, 195, 121)
            elif ext == ".py":
                name_color = (229, 192, 123)
            elif ext == ".md":
                name_color = (92, 99, 112)
            else:
                name_color = (171, 178, 191)
            name_attrs = 0

        if i == s.selected_file:
            name_attrs = name_attrs | BOLD | UNDERLINE

        cells = []
        if indent:
            cells.append((indent, (50, 55, 70)))
        cells.append((icon, (150, 156, 170)))
        cells.append((name, name_color, None, name_attrs))
        rows.append(_clip_row(cells, pw - 4))

    return card(*rows, title="EXPLORER", border_color=BORDER, pad=(0, 1),
                width=pw, shrink=0)


def build_tab_bar(s):
    active = (97, 175, 239)
    inactive = (150, 156, 170)
    sep = (50, 55, 70)
    cells = []
    for i, (name, _path, _lang, _bc) in enumerate(tabs):
        if i > 0:
            cells.append((" | ", sep))
        if i == s.active_tab:
            cells.append((name, active, None, BOLD | UNDERLINE))
        else:
            cells.append((name, inactive))
    return row(*cells, gap=0)


def build_breadcrumb(s):
    return breadcrumb(tabs[s.active_tab][3])


def build_code_editor(s, vis):
    lines = code_buffers[s.active_tab]

    def draw(w, h):
        cw = max(1, min(int(w), 400))
        # maya's vstack clips overflow keeping the tail: show the last `vis`
        # lines so the bottom of the buffer stays visible (matches C++).
        start = max(0, len(lines) - vis)
        rows = []
        for i in range(start, len(lines)):
            text, runs = lines[i]
            num_str = "%3d " % (i + 1)
            cells = [(num_str, LINE_NUM)]
            cells.extend(_runs_to_cells(text, runs))
            rows.append(_clip_row(cells, cw))
        return col(*rows, gap=0)

    return component(draw, grow=1)


def build_minimap(s):
    lines = code_buffers[s.active_tab]
    density = [min(max(len(text) / 60.0, 0.0), 1.0) for text, _runs in lines]
    return sparkline(density, color=(60, 80, 120))


def build_editor_panel(s, pw, code_h):
    return card(
        build_tab_bar(s),
        build_breadcrumb(s),
        row(build_code_editor(s, code_h), build_minimap(s), gap=1),
        title=tabs[s.active_tab][0],
        border_color=BORDER,
        pad=(0, 1),
        width=pw,
        shrink=0,
    )


def build_outline_panel(s, pw):
    syms = outlines[s.active_tab]
    rows = []
    for name, kind, line in syms:
        if kind == "fn":
            icon, icon_color = "f ", (198, 120, 221)
        elif kind == "class":
            icon, icon_color = "C ", (229, 192, 123)
        elif kind == "struct":
            icon, icon_color = "S ", (86, 182, 194)
        else:
            icon, icon_color = "v ", (152, 195, 121)
        line_str = ":" + str(line)
        rows.append(_clip_row([
            (icon, icon_color),
            (name, (200, 204, 212)),
            (line_str, (92, 99, 112)),
        ], pw - 4))
    return card(*rows, title="OUTLINE", border_color=BORDER, pad=(0, 1))


def build_diagnostics_panel(s, pw):
    rows = []
    for file, line, message, severity in diagnostics:
        if severity == 0:
            b = badge("ERR", kind="error")
        elif severity == 1:
            b = badge("WRN", kind="warning")
        else:
            b = badge("INF", kind="info")
        loc = file + ":" + str(line)
        # badge (~5 cols) + gap(1) consumes ~6; clip loc+message to the rest.
        rest = _clip_cells([
            (loc, (100, 180, 255)),
            (" " + message, None, None, DIM),
        ], pw - 4 - 6)
        rows.append(row(b, row(*rest, gap=0), gap=1))
    return card(*rows, title="DIAGNOSTICS", border_color=BORDER, pad=(0, 1))


def build_git_panel(s, pw):
    rows = []
    for file, added, removed, status in git_changes:
        if status == "M":
            status_color = (229, 192, 123)
        elif status == "A":
            status_color = (152, 195, 121)
        else:
            status_color = (224, 108, 117)
        adds = "+" + str(added)
        dels = "-" + str(removed)
        del_color = (224, 108, 117) if removed > 0 else (92, 99, 112)
        rows.append(_clip_row([
            (status, status_color, None, BOLD),
            (" ", PLAIN),
            (file, (171, 178, 191)),
            (" ", PLAIN),
            (adds, (152, 195, 121)),
            (" ", PLAIN),
            (dels, del_color),
        ], pw - 4))
    return card(*rows, title="GIT CHANGES", border_color=BORDER, pad=(0, 1))


def build_right_sidebar(s, pw):
    return col(
        build_outline_panel(s, pw),
        build_diagnostics_panel(s, pw),
        build_git_panel(s, pw),
        width=pw,
        shrink=0,
    )


def build_terminal_panel(s):
    log = build_complete_log if (s.building or s.build_done) else build_log
    if s.building:
        show_lines = min(len(log), int(s.build_progress * len(log)))
    else:
        show_lines = len(log)

    rows = []
    for i in range(min(show_lines, len(log))):
        line = log[i]
        if line.startswith("$"):
            line_color = (152, 195, 121)
            attrs = 0
        elif "error" in line:
            line_color = (224, 108, 117)
            attrs = 0
        elif "warning" in line:
            line_color = (229, 192, 123)
            attrs = 0
        elif "Build finished" in line:
            line_color = (200, 204, 212)
            attrs = BOLD
        else:
            line_color = (120, 126, 140)
            attrs = 0
        rows.append(row((line, line_color, None, attrs), gap=0))

    if s.building:
        rows.append(progress(s.build_progress, "Building..."))

    while len(rows) < 4:
        rows.append(T(""))

    return card(*rows, title="TERMINAL", border_color=BORDER, pad=(0, 1))


def build_status_bar(s):
    name, _path, language, _bc = tabs[s.active_tab]
    errors = sum(1 for d in diagnostics if d[3] == 0)
    warnings = sum(1 for d in diagnostics if d[3] == 1)
    err_str = str(errors) + " errors"
    warn_str = str(warnings) + " warnings"
    return row(
        T(" " + name).bold.fg((97, 175, 239)),
        T("  Ln 1, Col 1").fg((140, 140, 160)),
        T("  " + language).fg((171, 178, 191)),
        T("  UTF-8").fg((140, 140, 160)),
        grow(T("")),
        badge(err_str, kind="error"),
        T(" "),
        badge(warn_str, kind="warning"),
        T("  "),
        badge("main", kind="info"),
        T(" "),
        bg=(30, 30, 42),
        pad=(0, 1),
    )


# ── Render ───────────────────────────────────────────────────────────────────
def render(s):
    def draw_main(w, h):
        avail = max(30, int(w))
        exp_w, ed_w, sb_w = _panel_widths(avail)
        # Reclaim space from any hidden panels so the editor fills the row.
        if not s.show_left:
            ed_w += exp_w
        if not s.show_right:
            ed_w += sb_w
        # Editor card: 2 border rows + tab bar + breadcrumb above the code.
        # Available vertical space = terminal height, minus the status bar (1)
        # and the terminal panel (6) when shown, minus this card's chrome (4).
        used = 1
        if s.show_bottom:
            used += 6
        code_h = max(1, s.term_h - used - 4)
        columns = []
        if s.show_left:
            columns.append(build_file_tree(s, exp_w))
        columns.append(build_editor_panel(s, ed_w, code_h))
        if s.show_right:
            columns.append(build_right_sidebar(s, sb_w))
        return row(*columns, gap=0)

    main_row = component(draw_main, grow=1)

    main_stack = [main_row]
    if s.show_bottom:
        main_stack.append(build_terminal_panel(s))
    main_stack.append(build_status_bar(s))

    return col(*main_stack)


# ── App ──────────────────────────────────────────────────────────────────────
app = App.fullscreen("ide", fps=10)
app.state(active_tab=0, show_left=True, show_right=True, show_bottom=True,
          building=False, build_progress=0.0, build_done=False, frame=0,
          selected_file=3, term_h=28)


@app.on_resize
def _resize(s, cols, rows):
    s.term_h = rows


app.quit_on("q", "esc")


@app.on("tab")
def _tab(s):
    s.active_tab = (s.active_tab + 1) % 4


@app.on("1")
def _left(s):
    s.show_left = not s.show_left


@app.on("2")
def _right(s):
    s.show_right = not s.show_right


@app.on("3")
def _bottom(s):
    s.show_bottom = not s.show_bottom


@app.on("b")
def _build(s):
    if not s.building:
        s.building = True
        s.build_progress = 0.0
        s.build_done = False


@app.on_frame
def _tick(s, dt):
    s.frame += 1
    if s.building:
        s.build_progress += 0.02
        if s.build_progress >= 1.0:
            s.build_progress = 1.0
            s.building = False
            s.build_done = True


@app.view
def view(s):
    return render(s)


if __name__ == "__main__":
    app.run()
