"""bench_vs_rich.py — head-to-head: maya-py vs Rich on identical workloads.

Rich is the de-facto standard for styled terminal output in Python, and its
render loop (Console.print → Segment stream → ANSI) is what Textual builds
on, so beating it here is the honest "fastest around" test.

Three workloads, both libraries rendering the SAME content to a string:

  1. dashboard  — bordered panel, title, rule, fields, 30-row colored table
                  (the bench.py workload, expressed in each library's idiom)
  2. log flood  — 200 styled log lines (timestamp dim, level colored, text)
  3. table      — 100×6 data table with header + alignment

Run:  PYTHONPATH=src python examples/bench_vs_rich.py [--iters N]

Requires: pip install rich  (skips gracefully if missing).
"""
from __future__ import annotations

import sys
import time
import statistics

import maya_py as maya
from maya_py import card, col, row, rows, hr, b, T, DIM

try:
    import rich
    from rich.console import Console
    from rich.table import Table as RichTable
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich.console import Group
    import io as _io
except ImportError:
    print("rich not installed — pip install rich")
    sys.exit(0)


ITERS = 300
for i, a in enumerate(sys.argv):
    if a == "--iters":
        ITERS = int(sys.argv[i + 1])

WIDTH = 80

STATUSES = [("OK", "green"), ("WARN", "orange"), ("ERR", "red")]
RICH_COLORS = {"green": "green", "orange": "dark_orange", "red": "red",
               "sky": "sky_blue1", "gold": "gold1", "slate": "grey54"}


def make_services(n):
    return [
        {"name": f"svc-{i:03d}", "status": STATUSES[i % 3],
         "latency": f"{(i * 7) % 90 + 3}ms", "rps": str((i * 131) % 9000)}
        for i in range(n)
    ]


def make_logs(n):
    levels = [("INFO", "green"), ("WARN", "orange"), ("ERROR", "red")]
    return [
        {"ts": f"12:{i % 60:02d}:{(i * 7) % 60:02d}", "level": levels[i % 3],
         "msg": f"request {i} handled in {(i * 13) % 200}ms path=/api/v1/x{i % 10}"}
        for i in range(n)
    ]


# ── workload 1: dashboard ────────────────────────────────────────────────────

def maya_dashboard(data):
    table = rows(
        [(d["name"], "sky"), (d["status"][0], d["status"][1]),
         (d["latency"], None, None, DIM), (d["rps"], "gold")]
        for d in data
    )
    return card(
        b("Service Dashboard").fg("sky"),
        hr(40),
        row(("Region:", "slate"), ("us-east-1", "green"), gap=1),
        row(("Healthy:", "slate"),
            (f"{sum(1 for d in data if d['status'][0] == 'OK')}/{len(data)}",),
            gap=1),
        hr(40),
        table,
        title="services",
    )


def rich_dashboard(data, console):
    t = RichTable.grid(padding=(0, 1))
    for _ in range(4):
        t.add_column()
    for d in data:
        t.add_row(
            Text(d["name"], style=RICH_COLORS["sky"]),
            Text(d["status"][0], style=RICH_COLORS[d["status"][1]]),
            Text(d["latency"], style="dim"),
            Text(d["rps"], style=RICH_COLORS["gold"]),
        )
    body = Group(
        Text("Service Dashboard", style=f"bold {RICH_COLORS['sky']}"),
        Rule(style=RICH_COLORS["slate"]),
        Text.assemble(("Region: ", RICH_COLORS["slate"]), ("us-east-1", "green")),
        Text.assemble(("Healthy: ", RICH_COLORS["slate"]),
                      (f"{sum(1 for d in data if d['status'][0] == 'OK')}/{len(data)}",)),
        Rule(style=RICH_COLORS["slate"]),
        t,
    )
    console.print(Panel(body, title="services", expand=False))


# ── workload 2: log flood ────────────────────────────────────────────────────

def maya_logs(logs):
    return rows(
        [(l["ts"], None, None, DIM), (l["level"][0], l["level"][1]), (l["msg"],)]
        for l in logs
    )


def rich_logs(logs, console):
    for l in logs:
        console.print(
            Text.assemble((l["ts"], "dim"),
                          (" " + l["level"][0], RICH_COLORS[l["level"][1]]),
                          (" " + l["msg"], "")),
        )


# ── workload 3: data table ───────────────────────────────────────────────────

def maya_table(data):
    return maya.table(
        ["SERVICE", "STATUS", "LATENCY", "RPS", "REGION", "VER"],
        [[d["name"], d["status"][0], d["latency"], d["rps"], "us-east-1", "1.0"]
         for d in data],
    )


def rich_table(data, console):
    t = RichTable()
    for h in ("SERVICE", "STATUS", "LATENCY", "RPS", "REGION", "VER"):
        t.add_column(h)
    for d in data:
        t.add_row(d["name"], d["status"][0], d["latency"], d["rps"],
                  "us-east-1", "1.0")
    console.print(t)


# ── harness ──────────────────────────────────────────────────────────────────

def time_maya(build, iters):
    # full pipeline: build + layout + paint + serialize
    best = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(iters):
            maya.render_to_string(build(), WIDTH)
        best.append((time.perf_counter() - t0) / iters)
    return min(best)


def time_rich(fn, iters):
    # Console is constructed ONCE outside the timed loop (an app would),
    # and only the StringIO sink is swapped per frame — no setup cost is
    # charged to Rich.
    console = Console(file=_io.StringIO(), width=WIDTH, force_terminal=True,
                      color_system="truecolor", highlight=False)
    best = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(iters):
            console.file = _io.StringIO()
            fn(console)
        best.append((time.perf_counter() - t0) / iters)
    return min(best)


def fmt(s):
    return f"{s * 1e6:8.1f} µs"


def main():
    services = make_services(30)
    logs = make_logs(200)
    tdata = make_services(100)

    from importlib.metadata import version as _pkg_version
    print(f"maya-py vs Rich {_pkg_version('rich')}  —  width={WIDTH}, "
          f"{ITERS} iters/test, best of 5 runs\n")

    rows_out = []
    for name, m_fn, r_fn, iters in (
        ("dashboard (30 rows)", lambda: maya_dashboard(services),
         lambda c: rich_dashboard(services, c), ITERS),
        ("log flood (200 lines)", lambda: maya_logs(logs),
         lambda c: rich_logs(logs, c), max(ITERS // 4, 20)),
        ("table 100×6", lambda: maya_table(tdata),
         lambda c: rich_table(tdata, c), max(ITERS // 4, 20)),
    ):
        mt = time_maya(m_fn, iters)
        rt = time_rich(r_fn, iters)
        rows_out.append((name, mt, rt))
        print(f"  {name:24s}  maya-py {fmt(mt)}   rich {fmt(rt)}   "
              f"→  maya-py {rt / mt:5.1f}× faster")

    geo = 1.0
    for _, mt, rt in rows_out:
        geo *= rt / mt
    geo **= 1.0 / len(rows_out)
    print(f"\n  geometric mean: maya-py {geo:.1f}× faster than Rich")
    print("  (both sides render identical content to a string; Rich uses its")
    print("   idiomatic API — Table.grid/Text.assemble/Panel — with a single")
    print("   pre-built Console, highlight off; only the StringIO sink is")
    print("   swapped per frame.)")


if __name__ == "__main__":
    main()
