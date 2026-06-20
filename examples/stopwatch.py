"""stopwatch.py — a live stopwatch with laps, built on the App runtime.

  space  start/stop    l  lap    r  reset    q/Esc  quit

    PYTHONPATH=src python examples/stopwatch.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, divider, badge

app = App.inline("stopwatch", fps=20)
app.state(running=False, base=0.0, started_at=0.0, laps=[])


def elapsed(s):
    return s.base + (time.time() - s.started_at if s.running else 0.0)


def fmt(t):
    m_ = int(t // 60)
    sec = int(t % 60)
    cs = int((t * 100) % 100)
    return f"{m_:02d}:{sec:02d}.{cs:02d}"


@app.on("space")
def toggle(s):
    if s.running:
        s.base += time.time() - s.started_at
        s.running = False
    else:
        s.started_at = time.time()
        s.running = True


@app.on("l")
def lap(s):
    if s.running or s.base > 0:
        s.laps.append(elapsed(s))


@app.on("r")
def reset(s):
    s.running = False
    s.base = 0.0
    s.laps = []


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    t = elapsed(s)
    state = badge("RUNNING", kind="success") if s.running else badge("STOPPED", kind="warning")

    lap_rows = []
    prev = 0.0
    for i, lt in enumerate(s.laps[-6:], start=max(1, len(s.laps) - 5)):
        split = lt - prev if i == 1 else lt - s.laps[i - 2]
        prev = lt
        lap_rows.append(row(
            dim_text(f"lap {i}"),
            T(fmt(lt)).fg("sky"),
            dim_text(f"(+{fmt(split)})"),
            gap=2,
        ))
    if not lap_rows:
        lap_rows = [dim_text("no laps yet — press 'l'")]

    return card(
        row(b("⏱  stopwatch").fg("gold"), state, justify="between"),
        divider(color="slate"),
        T(fmt(t)).fg("white").bold,   # big-ish time
        divider("laps", color="slate"),
        col(*lap_rows),
        dim_text("space start/stop · l lap · r reset · q quit"),
        title="stopwatch", gap=1,
    )


if __name__ == "__main__":
    app.run()
