"""dashboard.py — shows off the full maya-py layout surface.

A two-pane dashboard: a fixed-width sidebar and a growing main area, with
percent widths, a z-stack badge, partial borders, centered content, and a
size-aware progress bar drawn with component(). Static render — run with:

    PYTHONPATH=src python examples/dashboard.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    T, b, col, row, card, center, stack, grow, component,
    field, hr, pct, cells, sides,
)


def progress(frac, label):
    """A bar that fills whatever width the layout hands it."""
    def draw(w, h):
        filled = int(w * frac)
        bar = T("█" * filled).fg("green") + T("░" * (w - filled)).fg("slate")
        return bar
    return col(T(label).fg("slate"), component(draw, height=1))


def sidebar():
    return card(
        field("User", T("ada").fg("sky")),
        field("Plan", T("Pro").fg("gold")),
        hr(16),
        field("Tasks", "7"),
        field("Done", T("4").fg("green")),
        title="account",
        width=pct(34),
    )


def main_pane():
    # A z-stack: the panel sets the size, the badge overlays the top-right.
    panel = card(
        b("System Status").fg("white"),
        T("All services nominal").fg("green"),
        maya.spacer(),
        progress(0.72, "CPU"),
        progress(0.41, "Memory"),
        progress(0.93, "Disk"),
        title="overview",
    )
    badge = row(T(" LIVE ").bg("red").fg("white").bold, justify="end")
    return grow(stack(panel, badge))


def footer():
    return card(
        row(
            T("q quit").fg("slate"),
            grow(center("maya-py dashboard demo", direction=maya.Row)),
            T("↑↓ nav").fg("slate"),
        ),
        border_sides=sides(top=True, right=False, bottom=False, left=False),
        pad=(0, 1),
    )


def dashboard():
    return col(
        row(sidebar(), main_pane(), gap=1),
        footer(),
        gap=1,
    )


if __name__ == "__main__":
    maya.print(dashboard())
