"""sysmon.py — a live system-monitor dashboard.

Animated at 10fps: rolling sparklines, gauges, a bar chart and a log feed,
all driven by synthetic metrics (no psutil needed). Ctrl-C or 'q' to quit.

    PYTHONPATH=src python examples/sysmon.py
"""

import sys
import os
import math
import random
import time
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    col, row, card, b, dim_text, T,
    sparkline, gauge, progress, bar_chart, status_banner, badge,
)

start = time.time()
cpu_hist = deque([random.random() for _ in range(24)], maxlen=24)
net_hist = deque([random.random() for _ in range(24)], maxlen=24)
logs = deque(maxlen=6)
_last_log = 0.0

LOG_LINES = [
    ("info", "GET /api/health 200 4ms"),
    ("info", "cache hit ratio 0.94"),
    ("warn", "worker queue depth 128"),
    ("info", "POST /ingest 201 18ms"),
    ("err", "upstream timeout: db-3"),
    ("info", "checkpoint flushed"),
    ("warn", "memory pressure: 81%"),
]


def tick():
    t = time.time() - start
    cpu = max(0.02, min(0.98, 0.5 + 0.4 * math.sin(t * 0.8) + random.uniform(-0.1, 0.1)))
    net = max(0.02, min(0.98, 0.5 + 0.4 * math.cos(t * 1.3) + random.uniform(-0.12, 0.12)))
    cpu_hist.append(cpu)
    net_hist.append(net)
    return cpu, net


def maybe_log():
    global _last_log
    now = time.time()
    if now - _last_log > 0.7:
        _last_log = now
        logs.append(random.choice(LOG_LINES))


def log_view():
    rows = []
    for kind, msg in logs:
        tag = {"info": ("•", "sky"), "warn": ("▲", "gold"), "err": ("✖", "red")}[kind]
        rows.append(row(T(tag[0]).fg(tag[1]), dim_text(msg), gap=1))
    while len(rows) < 6:
        rows.append(dim_text(" "))
    return col(*rows)


def render(dt):
    t = time.time() - start
    if t > 30:           # auto-quit so the demo doesn't run forever
        maya.quit()
    cpu, net = tick()
    maybe_log()
    mem = 0.5 + 0.3 * math.sin(t * 0.4)
    disk = 0.62

    health = "ok" if cpu < 0.9 else "degraded"
    banner_kind = "info" if cpu < 0.9 else "warning"

    return col(
        row(
            b("◆ sysmon").fg("sky"),
            dim_text(f"  uptime {int(t)}s"),
            badge("LIVE", kind="error"),
            justify="between",
        ),
        status_banner(f"cluster status: {health}", kind=banner_kind),
        row(
            card(
                dim_text("CPU"),
                sparkline(list(cpu_hist), color="sky", show_last=True),
                dim_text("NET"),
                sparkline(list(net_hist), color="lime", show_last=True),
                title="throughput", grow=1,
            ),
            card(
                gauge(cpu, "cpu", color="sky"),
                title="load",
            ),
            gap=1,
        ),
        card(
            progress(mem, "mem", width=0, fill="magenta"),
            progress(disk, "disk", width=0, fill="gold"),
            bar_chart([
                ("api", 4 + 3 * abs(math.sin(t)), "sky"),
                ("db", 9 * abs(math.cos(t * 0.7)), "magenta"),
                ("cache", 2 + abs(math.sin(t * 2)), "lime"),
            ], max_value=12),
            title="resources",
        ),
        card(log_view(), title="logs"),
        dim_text("Ctrl-C to quit  ·  auto-stops after 30s"),
        gap=1,
    )


if __name__ == "__main__":
    maya.animate(render, fps=10)
