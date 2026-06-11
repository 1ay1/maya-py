"""widgets.py — a one-shot showcase of maya's native widget renderers.

Prints a full gallery to stdout (no alt-screen) — the same C++ renderers maya
itself uses, driven from Python. For the LIVE animated version see
widgets_gallery.py.

    PYTHONPATH=src python examples/widgets.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    col, row, card, b, dim_text,
    sparkline, gauge, progress, badge, divider, spinner,
    table, callout, status_banner, breadcrumb, tabs, bar_chart, gradient,
    heatmap, checkbox, toggle, radio, select, slider, button, line_chart,
    link, key_help, timeline, tree, list_view, menu, disclosure, toast,
    todo_list, title_chip, model_badge, file_ref, inline_diff, thinking,
    markdown, picker, dim_text as _dt,
)


def showcase():
    return col(
        gradient("maya widget showcase", "sky", "magenta"),
        breadcrumb(["maya", "widgets", "showcase"]),

        divider("charts & meters", color="slate"),
        row(
            card(b("sparkline"),
                 sparkline([3, 1, 4, 1, 5, 9, 2, 6, 5, 3], label="req/s",
                           color="sky", show_last=True),
                 b("bar chart"),
                 bar_chart([("jan", 4, "sky"), ("feb", 9, "green"), ("mar", 6)]),
                 b("line chart"),
                 line_chart([2, 5, 3, 8, 6, 9, 4, 7], height=5, color="lime"),
                 title="data", pad=1),
            card(b("gauge"), gauge(0.72, "load", color="green"),
                 b("progress"), progress(0.45, "build", width=22, fill="lime"),
                 b("slider"), slider(0.6, "vol", width=20, fill="sky"),
                 title="meters", pad=1),
            gap=1,
        ),

        divider("controls", color="slate"),
        row(
            card(checkbox("telemetry", checked=True),
                 checkbox("beta", checked=False),
                 toggle("dark mode", on=True), title="checks", pad=1),
            card(b("radio"), radio(["S", "M", "L"], selected=1),
                 b("select"), select(["Build", "Test", "Ship"], cursor=0),
                 title="choice", pad=1),
            card(b("buttons"),
                 row(button("Save", variant="primary"),
                     button("Delete", variant="danger"), gap=1),
                 title="actions", pad=1),
            gap=1,
        ),

        divider("status & labels", color="slate"),
        row(badge("PASS", kind="success"), badge("WARN", kind="warning"),
            badge("FAIL", kind="error"), badge("INFO", kind="info"),
            row(spinner(), " working", gap=0),
            model_badge("Opus 4.8", compact=True),
            title_chip("session", edge_color="cyan"),
            file_ref("src/main.py", line=42), gap=2),
        status_banner("context compacted — 4 messages dropped", kind="warning"),
        callout("Heads up", "disk is 92% full on /var", kind="warning"),

        divider("tabular & nav", color="slate"),
        tabs(["Overview", "Logs", "Settings"], active=0),
        row(
            table(["Service", ("Status", 0, "center"), ("p99", 0, "right")],
                  [["api", "ok", "42"], ["worker", "ok", "118"],
                   ["cache", "degraded", "7"]],
                  bordered=True, title="services"),
            tree({"label": "src", "expanded": True, "children": [
                {"label": "main.py"},
                {"label": "widget", "expanded": True, "children": [
                    {"label": "table.hpp"}, {"label": "tree.hpp"}]}]}),
            key_help([("↑↓", "move"), ("enter", "select"), ("q", "quit")],
                     title="keys"),
            gap=2,
        ),

        divider("agent UI", color="slate"),
        todo_list([("design API", "completed"), ("implement", "in_progress"),
                   ("write tests", "pending")],
                  description="current sprint", status="running", elapsed=42.0),
        timeline([("clone", "", "0.4s", "completed"),
                  ("compile", "", "2.1s", "completed"),
                  ("link", "", "", "in_progress", 8)]),
        thinking("The user wants a flexbox layout, so I should…",
                 active=True, max_lines=2),
        inline_diff("const x = 1", "const x = 42", label="app.ts"),
        markdown("### Notes\n- maya renders **GFM** inline\n- `code` too"),
        toast([("Build succeeded", "success"), ("3 warnings", "warning")]),

        divider("command palette", color="slate"),
        picker([("Opus 4.8", "anthropic", True), ("Sonnet 4", "anthropic"),
                {"leading": "GPT-5", "trailing": "openai", "active": True},
                ("Gemini 2.5", "google")],
               title="Models", accent="cyan",
               header=[_dt("  search: opus_")],
               footer=[_dt("  ↑↓ move · enter select · esc cancel")],
               min_width=46),

        heatmap([[0.1, 0.4, 0.8, 0.9], [0.3, 0.6, 0.5, 0.2],
                 [0.9, 0.7, 0.4, 0.1]], low="slate", high="lime"),
        gap=1,
    )


if __name__ == "__main__":
    maya.print(showcase())
