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
        gap=1,
    )


if __name__ == "__main__":
    maya.print(gallery())
