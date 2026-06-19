"""widgets_gallery.py — every maya-py widget in one screen.

    PYTHONPATH=src python examples/widgets_gallery.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    col, row, card, b,
    sparkline, gauge, progress, badge, divider, spinner,
    table, callout, status_banner, breadcrumb, tabs, bar_chart, gradient, heatmap,
    checkbox, toggle, radio, select, slider, button, line_chart, link,
    key_help, timeline, tree, list_view, menu, disclosure, toast, todo_list,
    title_chip, model_badge, file_ref, inline_diff, thinking, markdown,
    picker, dim_text,
    popup, overlay, user_message, assistant_message, system_banner,
    phase_chip, context_gauge, context_window, diff_view, tool_call,
    git_graph, git_status, shortcut_row, plan_view,
)


def gallery():
    return col(
        gradient("maya-py widget gallery", "sky", "magenta"),
        breadcrumb(["maya", "widgets", "gallery"]),
        divider("charts", color="slate"),
        row(
            card(
                b("sparkline"),
                sparkline([3, 1, 4, 1, 5, 9, 2, 6, 5, 3], label="req/s",
                          color="sky", show_last=True),
                b("bar chart"),
                bar_chart([("jan", 4, "sky"), ("feb", 9, "green"), ("mar", 6)]),
                title="data",
            ),
            card(
                b("gauge"), gauge(0.72, "load", color="green"),
                b("progress"), progress(0.45, "build", width=22, fill="lime"),
                title="meters",
            ),
            gap=1,
        ),
        divider("status", color="slate"),
        row(
            badge("PASS", kind="success"),
            badge("WARN", kind="warning"),
            badge("FAIL", kind="error"),
            badge("INFO", kind="info"),
            row(spinner(), " working", gap=0),
            gap=2,
        ),
        status_banner("context compacted — 4 messages dropped", kind="warning"),
        callout("Heads up", "disk is 92% full on /var", kind="warning"),
        divider("tabular", color="slate"),
        tabs(["Overview", "Logs", "Settings"], active=0),
        table(
            ["Service", ("Status", 0, "center"), ("p99 ms", 0, "right")],
            [["api", "ok", "42"], ["worker", "ok", "118"], ["cache", "degraded", "7"]],
            bordered=True, title="services",
        ),
        divider("heatmap", color="slate"),
        heatmap(
            [[0.1, 0.4, 0.8, 0.9], [0.3, 0.6, 0.5, 0.2], [0.9, 0.7, 0.4, 0.1]],
            low="slate", high="lime",
        ),
        divider("controls", color="slate"),
        row(
            card(
                checkbox("Enable telemetry", checked=True),
                checkbox("Beta features", checked=False),
                toggle("Dark mode", on=True),
                title="checks",
            ),
            card(
                b("radio"), radio(["Small", "Medium", "Large"], selected=1),
                b("select"), select(["Build", "Test", "Deploy"], cursor=0),
                title="choice",
            ),
            card(
                b("slider"), slider(0.6, "volume", width=20, fill="sky"),
                b("buttons"),
                row(button("Save", variant="primary"),
                    button("Delete", variant="danger"), gap=1),
                title="input",
            ),
            gap=1,
        ),
        divider("line chart", color="slate"),
        line_chart([2, 5, 3, 8, 6, 9, 4, 7, 5, 8, 6, 10], height=6,
                   label="rps", color="sky"),
        divider("navigation", color="slate"),
        row(
            tree({"label": "src", "expanded": True, "children": [
                {"label": "main.py"},
                {"label": "widget", "expanded": True,
                 "children": [{"label": "table.hpp"}, {"label": "tree.hpp"}]},
            ]}),
            list_view([("Ada", "engineer", "★"), ("Bob", "designer")], cursor=0),
            key_help([("↑↓", "move"), ("enter", "select"), ("q", "quit")],
                     title="keys"),
            gap=2,
        ),
        divider("agent UI", color="slate"),
        row(model_badge("Opus 4.8", compact=True),
            title_chip("session", edge_color="cyan"),
            file_ref("src/main.py", line=42), gap=2),
        todo_list(
            [("design API", "completed"), ("implement", "in_progress"),
             ("write tests", "pending")],
            description="current sprint", status="running", elapsed=42.0,
        ),
        timeline([
            ("clone", "", "0.4s", "completed"),
            ("compile", "", "2.1s", "completed"),
            ("link", "", "", "in_progress", 8),
        ]),
        thinking("The user wants a flexbox layout, so I should...",
                 active=True, max_lines=3),
        inline_diff("const x = 1", "const x = 42", label="app.ts"),
        markdown("### Notes\n- maya renders **GFM** inline\n- `code` too"),
        toast([("Build succeeded", "success"), ("3 warnings", "warning")]),
        divider("command palette", color="slate"),
        picker(
            [
                ("Opus 4.8", "anthropic", True),
                ("Sonnet 4", "anthropic"),
                {"leading": "GPT-5", "trailing": "openai", "active": True},
                ("Gemini 2.5", "google"),
            ],
            title="Models",
            accent="cyan",
            header=[dim_text("  search: opus_")],
            footer=[dim_text("  ↑↓ move · enter select · esc cancel")],
            min_width=46,
        ),
        divider("agent chrome", color="slate"),
        row(
            phase_chip("Thinking", glyph="✷", color="magenta", elapsed=4.2),
            system_banner("context window 80% full", level="warning"),
            gap=2,
        ),
        context_gauge(160000, 200000),
        context_window(
            [("System", 12400, "blue"), ("History", 89200, "magenta"),
             ("Tools", 32100, "yellow"), ("Response", 11534, "green")],
            width=44,
        ),
        tool_call("Read", kind="read", description="src/auth.py",
                  status="completed", elapsed=1.2),
        shortcut_row([("q", "quit"), ("/", "search"), ("?", "help")]),
        plan_view([("Read middleware", "completed"),
                   ("Run tests", "in_progress"), "Ship it"]),
        divider("messages & git", color="slate"),
        user_message("show me the project structure"),
        assistant_message(markdown("Here's the **layout**:")),
        popup("Saved to disk", style="info"),
        overlay(
            card(b("editor"), dim_text("def main():"), dim_text("    ..."),
                 title="app.py"),
            popup("unsaved changes", style="warning"),
        ),
        git_status(branch="main", ahead=2, modified=3, staged=1),
        git_graph([
            ("a9f3cf1", "Fix auth token expiry", "", "2m ago", 0, False, True),
            ("9bf4e21", "Add rate limiting", "", "5m ago", 1),
            ("a1c3d7f", "Merge branch", "", "8m ago", 0, True),
        ]),
        diff_view("app.ts",
                  "@@ -1,3 +1,3 @@\n const x = 1\n-let y = 2\n+let y = 42\n const z = 3\n"),
        gap=1,
    )


if __name__ == "__main__":
    maya.print(gallery())
