"""scroll.py — a scrollable log viewer with a live scrollbar.

Mouse wheel or arrow keys scroll; the scrollbar thumb tracks position. Try the
different bar styles with [ and ].

  ↑/↓ · wheel   scroll        PgUp/PgDn   page        Home/End   jump
  [ ]           bar style     g           top         G          bottom
  q/Esc         quit

    PYTHONPATH=src python examples/scroll.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    App, col, row, card, b, dim_text, T,
    scroll_state, viewport, scrollbar,
)

LINES = [
    (f"{i:03d}", txt)
    for i, txt in enumerate([
        "boot: kernel handoff complete",
        "init: mounting /dev, /proc, /sys",
        "net: eth0 link up, dhcp lease 10.0.0.42",
        "auth: pam stack loaded",
        "db: connection pool warmed (16 conns)",
        "cache: redis ping 0.3ms",
        "queue: 3 workers online",
        "http: listening on :8080",
        "metrics: prometheus scrape registered",
        "tls: certificate valid until 2027-01-01",
        "feature-flags: 42 flags hydrated",
        "scheduler: cron table parsed (7 jobs)",
        "GET /healthz 200 1ms",
        "GET /api/users 200 14ms",
        "POST /api/orders 201 31ms",
        "WARN slow query 312ms on orders.idx_created",
        "GET /api/users/8821 200 4ms",
        "cache eviction: 128 keys (LRU)",
        "DELETE /api/sessions/old 204 2ms",
        "ERROR upstream timeout: payments-3",
        "retry: payments-3 attempt 2/3",
        "payments-3 recovered, latency 88ms",
        "GET /dashboard 200 22ms",
        "ws: client connected (id=44a1)",
        "ws: 1240 msgs/s peak",
        "gc: pause 1.2ms (young gen)",
        "config reload: 0 changes",
        "backup: snapshot started",
        "backup: 2.3 GB written in 4.1s",
        "audit: 0 anomalies",
        "shutdown signal ignored (drain mode)",
        "GET /healthz 200 1ms",
    ])
]

STYLES = ["line", "block", "slim", "neon", "braille", "shadow", "double"]

app = App("scroll", inline=True, mouse=True)
s = scroll_state()
s.step_y = 1
app.state(s=s, style=0, vh=14)


def _route(st, ev):
    if maya.scroll_handle(st.s, ev):
        return True
    return False


@app.on_key
def keys(st, ev):
    _route(st, ev)


@app.on_mouse
def mouse(st, ev):
    _route(st, ev)


@app.on("[")
def prev_style(st):
    st.style = (st.style - 1) % len(STYLES)


@app.on("]")
def next_style(st):
    st.style = (st.style + 1) % len(STYLES)


@app.on("g")
def top(st):
    st.s.scroll_to_top()


@app.on("G")
def bottom(st):
    st.s.scroll_to_bottom()


@app.on("q", "esc")
def quit_(st):
    app.stop()


def log_body():
    rows = []
    for num, txt in LINES:
        color = ("red" if "ERROR" in txt else
                 "gold" if "WARN" in txt else
                 "lime" if "recovered" in txt else "slate")
        rows.append(row(dim_text(num), T(txt).fg(color), gap=1))
    return col(*rows)


CONTENT = log_body()


@app.view
def view(st):
    vh = st.vh
    pct = 0 if st.s.max_y == 0 else round(100 * st.s.y / st.s.max_y)
    style = STYLES[st.style]
    return card(
        row(b("≡ system.log").fg("sky"),
            dim_text(f"{style} · {pct}%  ({st.s.y}/{st.s.max_y})"),
            justify="between"),
        row(
            viewport(CONTENT, st.s, height=vh),
            scrollbar(st.s, vh, style=style, thumb_color="sky"),
            gap=1,
        ),
        dim_text("↑↓/wheel scroll · PgUp/PgDn page · g/G top/bottom · [ ] style · q quit"),
        title="log viewer", gap=1,
    )


if __name__ == "__main__":
    app.run()
