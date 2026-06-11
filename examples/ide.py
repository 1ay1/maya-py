"""ide.py — a VS Code / Zed-inspired terminal IDE layout.

A file tree on the left, a tabbed editor with line numbers + faux syntax
highlighting in the centre, an outline + diagnostics + git status on the
right, and a status bar along the bottom. Toggle panels, cycle tabs, and run
a simulated build.

  Tab cycle tabs · 1/2/3 toggle panels · b build · q/esc quit

    PYTHONPATH=src python examples/ide.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, tree,
                     progress, divider, file_ref)

FILES = {
    "main.py": [
        ("def", "kw"), (" ", ""), ("main", "fn"), ("():", ""),
    ],
}

# (text, kind) tokens per line, per file
CODE = {
    "main.py": [
        [("import", "kw"), (" maya_py ", "id"), ("as", "kw"), (" maya", "id")],
        [],
        [("def", "kw"), (" ", ""), ("main", "fn"), ("():", "")],
        [("    app", "id"), (" = ", ""), ("maya", "id"), (".App(", ""),
         ('"hello"', "str"), (")", "")],
        [("    ", ""), ("@app", "dec"), (".view", "id")],
        [("    def", "kw"), (" view", "fn"), ("(s):", "")],
        [("        return", "kw"), (" card(", "fn"),
         ('"Hello, maya"', "str"), (")", "")],
        [],
        [("if", "kw"), (" __name__ == ", ""), ('"__main__"', "str"), (":", "")],
        [("    main", "fn"), ("()", "")],
    ],
    "widgets.py": [
        [("from", "kw"), (" maya_py ", "id"), ("import", "kw"), (" col, gauge", "id")],
        [],
        [("def", "kw"), (" dashboard", "fn"), ("():", "")],
        [("    return", "kw"), (" col(", "fn")],
        [("        gauge(", "fn"), ("0.72", "num"), (", ", ""),
         ('"load"', "str"), ("),", "")],
        [("    )", "")],
    ],
    "README.md": [
        [("# maya-py", "h")],
        [],
        [("Fast terminal UIs in ", "id"), ("**Python**", "str"), (".", "id")],
        [("- 90+ widgets", "id")],
        [("- sub-ms render", "id")],
    ],
}
TABS = list(CODE.keys())

COLORS = {"kw": "magenta", "fn": "sky", "str": "lime", "num": "gold",
          "dec": "gold", "h": "sky", "id": "white", "": "white"}

FILE_TREE = {
    "label": "my-project", "expanded": True, "children": [
        {"label": "src", "expanded": True, "children": [
            {"label": "main.py", "selected": True},
            {"label": "widgets.py"},
        ]},
        {"label": "tests", "children": [{"label": "test_app.py"}]},
        {"label": "README.md"},
        {"label": "pyproject.toml"},
    ]
}

DIAGS = [
    ("error", "red", "main.py:7", "undefined name 'crd'"),
    ("warn", "gold", "widgets.py:5", "unused import 'col'"),
    ("info", "sky", "main.py:3", "consider a type hint"),
]

app = App("ide", inline=True, fps=12)
app.state(tab=0, left=True, right=True, bottom=True,
          building=False, build_p=0.0, build_until=0.0)


@app.on("tab")
def _tab(s): s.tab = (s.tab + 1) % len(TABS)


@app.on("1")
def _l(s): s.left = not s.left


@app.on("2")
def _r(s): s.right = not s.right


@app.on("3")
def _bt(s): s.bottom = not s.bottom


@app.on("b")
def _build(s):
    s.building = True
    s.build_p = 0.0
    s.build_until = time.time() + 2.5


@app.on("q", "esc")
def _quit(s): app.stop()


def editor(s):
    name = TABS[s.tab]
    lines = CODE[name]
    rows = []
    for i, toks in enumerate(lines):
        segs = [T(f"{i+1:>3} ").fg("slate")]
        if not toks:
            segs.append(T(""))
        for text, kind in toks:
            segs.append(T(text).fg(COLORS.get(kind, "white")))
        rows.append(row(*segs, gap=0))
    return col(*rows, gap=0)


def tabbar(s):
    segs = []
    for i, name in enumerate(TABS):
        active = i == s.tab
        if active:
            segs.append(T(f" {name} ").fg("white").bold.bg("slate"))
        else:
            segs.append(T(f" {name} ").fg("slate"))
    return row(*segs, gap=1)


def outline():
    return col(
        row(T("ƒ").fg("sky"), dim_text("main")),
        row(T("ƒ").fg("sky"), dim_text("view")),
        row(T("ƒ").fg("sky"), dim_text("dashboard")),
        gap=0,
    )


def diagnostics():
    rows = []
    for lvl, clr, loc, msg in DIAGS:
        rows.append(col(
            row(badge(lvl.upper(),
                      kind="error" if lvl == "error" else
                           "warning" if lvl == "warn" else "info"),
                T(loc).fg("slate"), gap=1),
            T("  " + msg).fg("white"),
            gap=0,
        ))
    return col(*rows, gap=1)


def terminal_pane(s):
    if s.building:
        return col(
            dim_text("$ cmake --build build -j10"),
            progress(s.build_p, "building", width=40,
                     fill="lime" if s.build_p >= 1 else "sky"),
            T("✓ done" if s.build_p >= 1 else "compiling…").fg(
                "lime" if s.build_p >= 1 else "gold"),
            gap=0,
        )
    return col(
        dim_text("$ python examples/ide.py"),
        T("running…").fg("lime"),
        dim_text("press 'b' to simulate a build"),
        gap=0,
    )


@app.view
def view(s):
    if s.building:
        rem = s.build_until - time.time()
        s.build_p = min(1.0, 1.0 - rem / 2.5)
        if rem <= 0:
            s.build_p = 1.0
    center = card(
        tabbar(s),
        divider(color="slate"),
        editor(s),
        title=None, pad=1, gap=0, grow=1, basis=0, shrink=1,
    )
    panes = [center]
    if s.left:
        panes.insert(0, card(tree(FILE_TREE), title="explorer", pad=1,
                             basis=26, grow=0, shrink=0))
    if s.right:
        panes.append(col(
            card(outline(), title="outline", pad=1),
            card(diagnostics(), title="problems", pad=1),
            card(col(row(T("●").fg("gold"), dim_text("main ↑2 ↓0"), gap=1),
                     row(T("M").fg("gold"), dim_text("main.py"), gap=1),
                     row(T("A").fg("lime"), dim_text("widgets.py"), gap=1),
                     gap=0),
                 title="git", pad=1),
            gap=1, basis=30, grow=0, shrink=0,
        ))
    bottom = []
    if s.bottom:
        bottom = [card(terminal_pane(s), title="terminal", pad=1)]
    return col(
        row(b("◧ maya ide").fg("sky"),
            dim_text(TABS[s.tab]),
            badge("PYTHON", kind="info"), justify="between"),
        row(*panes, gap=1),
        *bottom,
        row(T(" main ").bg("slate").fg("white"),
            dim_text("UTF-8 · LF · Python"),
            dim_text("Tab tabs · 1/2/3 panels · b build · q quit"),
            justify="between"),
        gap=1,
    )


if __name__ == "__main__":
    app.run()
