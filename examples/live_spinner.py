"""Inline animation — a live spinner that re-renders at 30fps.

Runs for ~3 seconds then quits itself.
"""
import math
import time
import maya_py as maya

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
start = time.time()
n = 0


def render(dt):
    global n
    n += 1
    elapsed = time.time() - start
    if elapsed > 3.0:
        maya.quit()

    spin = FRAMES[n % len(FRAMES)]
    bar_len = int((math.sin(elapsed * 2) * 0.5 + 0.5) * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    return maya.box(
        maya.hstack(
            maya.text(spin, maya.fg(100, 200, 255)),
            maya.text(" working ", maya.bold),
            maya.text(bar, maya.fg(80, 220, 120)),
            gap=0,
        ),
        border=maya.Round,
        padding=(0, 1),
    )


maya.live(render, fps=30)
