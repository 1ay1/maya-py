"""inline_progress.py — inline rendering with print + live (no alt-screen).

Both APIs render INLINE: output stays in the terminal's normal scrollback like
any other program, no full-screen takeover.

  * maya.print(el)            one-shot render of an Element
  * maya.live(render_fn, fps) a looped inline animation that finalizes in place

This animates a 3-second progress bar, then prints a final summary card.

    PYTHONPATH=src python examples/inline_progress.py
"""

import time

import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import col, row, card, b, dim_text, T, badge

BAR_W = 40
DURATION = 3.0
_start = time.time()


def progress_card(fraction):
    fraction = max(0.0, min(1.0, fraction))
    filled = int(fraction * BAR_W + 0.5)
    bar = "█" * filled + "░" * (BAR_W - filled)
    elapsed = time.time() - _start
    return card(
        b("Working").fg((140, 200, 255)),
        row(
            T(bar).fg((100, 220, 160)),
            T(f"{int(fraction * 100):>3}%").bold,
            dim_text(f"{elapsed:.1f}s"),
            gap=2,
        ),
        title="build", pad=1,
    )


def summary():
    return card(
        row(badge("DONE", kind="success"), b("build complete").fg("lime"), gap=1),
        dim_text("3 targets · 0 errors · 1.8s"),
        col(
            row(T("✓").fg("lime"), "compile maya", gap=1),
            row(T("✓").fg("lime"), "link _maya.so", gap=1),
            row(T("✓").fg("lime"), "run tests (61 passed)", gap=1),
        ),
        title="summary", pad=1, gap=1,
    )


def render(dt):
    frac = (time.time() - _start) / DURATION
    if frac >= 1.0:
        maya.quit()
    return progress_card(frac)


if __name__ == "__main__":
    print("→ maya.live: animating a progress bar inline...\n")
    maya.live(render, fps=20)
    print()
    print("→ maya.print: final summary card\n")
    maya.print(summary())
    print()
