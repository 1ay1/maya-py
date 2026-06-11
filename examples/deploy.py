"""deploy.py — a CI/CD deploy pipeline dashboard that runs stages live.

A multi-stage pipeline (checkout → build → test → docker → deploy → smoke)
advances automatically; each stage streams log lines, shows a spinner while
running and a check/cross when done, and a timeline tracks overall progress.
A rolling throughput sparkline and a resource gauge round it out.

  space pause/resume · r restart · q/esc quit

    PYTHONPATH=src python examples/deploy.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, spinner, badge,
                     progress, sparkline, gauge, timeline, divider)

STAGES = [
    ("checkout", ["fetching origin/main", "HEAD at 4cd7a73", "clean tree"]),
    ("build", ["cmake --build build -j10", "[ 42%] compiling", "[100%] linked"]),
    ("test", ["pytest -q", "61 passed", "coverage 94%"]),
    ("docker", ["docker build .", "layer 1/8 cached", "pushed sha256:9f2a"]),
    ("deploy", ["kubectl apply -f k8s/", "rollout restart", "3/3 pods ready"]),
    ("smoke", ["GET /healthz 200", "GET /api/v1 200", "latency 38ms"]),
]

app = App("deploy", inline=True, fps=8)
app.state(stage=0, sub=0, frame=0, paused=False, done=False,
          logs=[], tput=[0.0] * 28, started=False)


def reset(s):
    s.stage = 0
    s.sub = 0
    s.frame = 0
    s.done = False
    s.logs = []
    s.tput = [0.0] * 28
    s.started = True


reset(app.s)


def step(s):
    s.frame += 1
    s.tput.append(random.uniform(0.3, 1.0))
    s.tput.pop(0)
    if s.done or s.paused:
        return
    # advance a sub-step every few frames
    if s.frame % 3 == 0:
        name, lines = STAGES[s.stage]
        if s.sub < len(lines):
            s.logs.append((name, lines[s.sub]))
            s.logs = s.logs[-12:]
            s.sub += 1
        else:
            s.stage += 1
            s.sub = 0
            if s.stage >= len(STAGES):
                s.stage = len(STAGES) - 1
                s.done = True


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("r")
def _restart(s): reset(s)


@app.on("q", "esc")
def _quit(s): app.stop()


def stage_status(s, i):
    if i < s.stage or s.done:
        return "completed"
    if i == s.stage:
        return "in_progress"
    return "pending"


def pipeline(s):
    events = []
    for i, (name, _) in enumerate(STAGES):
        st = stage_status(s, i)
        dur = f"{(i + 1) * 1.2:.1f}s" if st == "completed" else ""
        events.append((name, "", dur, st, 0))
    return timeline(events, frame=s.frame)


def logpane(s):
    rows = []
    for name, line in s.logs:
        rows.append(row(T(f"{name:>9}").fg("slate"), T("│").fg("slate"),
                        T(line).fg("white"), gap=1))
    if not rows:
        rows = [dim_text("waiting…")]
    return col(*rows, gap=0)


@app.view
def view(s):
    step(s)
    done = s.done
    overall = (s.stage + (s.sub / max(1, len(STAGES[s.stage][1])))) / len(STAGES)
    overall = min(1.0, overall)
    head_badge = (badge("SUCCESS", kind="success") if done
                  else badge("RUNNING", kind="info") if not s.paused
                  else badge("PAUSED", kind="warning"))
    return card(
        row(b("🚀 deploy pipeline").fg("sky"),
            head_badge,
            row(spinner() if (not done and not s.paused) else T("✓").fg("lime"),
                dim_text(STAGES[s.stage][0] if not done else "all green"),
                gap=1),
            justify="between"),
        row(
            card(pipeline(s), title="stages", pad=1),
            col(
                card(logpane(s), title="console", pad=1),
                row(
                    col(dim_text("throughput"),
                        sparkline(s.tput, color="lime", show_last=True)),
                    gauge(min(1.0, sum(s.tput[-6:]) / 6), "cpu", color="gold"),
                    gap=2,
                ),
                gap=1,
            ),
            gap=2,
        ),
        progress(overall, "overall", width=54,
                 fill="lime" if done else "sky"),
        dim_text("space pause · r restart · q quit"),
        title="deploy", gap=1,
    )


if __name__ == "__main__":
    app.run()
