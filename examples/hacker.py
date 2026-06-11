"""hacker.py — a "hollywood hacker" terminal: cascading hex dumps, a fake
breach progress, scrolling logs, and a node map lighting up.

Pure theatre — everything is synthesised. Showcases dense coloured text,
live state, and multi-pane layout.

  space pause · q/esc quit

    PYTHONPATH=src python examples/hacker.py
"""

import sys
import os
import random
import string

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, component, progress,
                     badge, divider)

HEX = "0123456789abcdef"
HOSTS = ["10.0.0.%d", "192.168.1.%d", "172.16.%d.1", "fw-edge-%02d",
         "db-prod-%02d", "vault-%02d"]
STAGES = ["scanning ports", "fuzzing endpoints", "bypassing WAF",
          "escalating privileges", "exfiltrating", "covering tracks"]

app = App("hacker", inline=True, fps=18)
app.state(t=0, log=[], prog=0.0, stage=0, nodes=[0] * 24, paused=False)


def _hexline(n):
    addr = random.randint(0, 0xFFFFFF)
    data = " ".join("".join(random.choice(HEX) for _ in range(2))
                    for _ in range(12))
    return f"{addr:06x}  {data}"


def _logline():
    host = random.choice(HOSTS) % random.randint(1, 99)
    verb = random.choice(["ACCESS", "DENY", "ROOT", "INJECT", "DUMP", "PWN"])
    clr = {"ACCESS": "lime", "DENY": "red", "ROOT": "gold",
           "INJECT": "magenta", "DUMP": "cyan", "PWN": "lime"}[verb]
    return (verb, clr, f"{host}: {random.choice(['200 OK','403','sudo su','0x%x'%random.randint(0,1<<20)])}")


def step(s):
    s.t += 1
    s.log.insert(0, _logline())
    s.log = s.log[:10]
    s.prog += random.uniform(0.005, 0.03)
    if s.prog >= 1.0:
        s.prog = 0.0
        s.stage = (s.stage + 1) % len(STAGES)
    for i in range(len(s.nodes)):
        if random.random() < 0.12:
            s.nodes[i] = random.choice([0, 1, 2])


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("q", "esc")
def _quit(s): app.stop()


def hexdump():
    def draw(w, h):
        rows = []
        for _ in range(12):
            line = _hexline(0)
            rows.append(T(line).fg(random.choice(["lime", "green", "teal"])))
        return col(*rows, gap=0)
    return component(draw, height=12)


def logpane(s):
    rows = []
    for verb, clr, msg in s.log:
        rows.append(row(badge(verb, kind="success" if clr == "lime" else
                              "error" if clr == "red" else "warning"),
                        T(msg).fg(clr), gap=1))
    return col(*rows, gap=0)


def nodemap(s):
    glyphs = {0: ("·", "slate"), 1: ("◆", "lime"), 2: ("◈", "red")}
    rows = []
    for r in range(4):
        segs = []
        for c in range(6):
            g, clr = glyphs[s.nodes[r * 6 + c]]
            segs.append(T(f" {g} ").fg(clr))
        rows.append(row(*segs, gap=0))
    return col(*rows, gap=0)


@app.view
def view(s):
    if not s.paused:
        step(s)
    return card(
        row(b("⛁ BREACH").fg("lime"),
            badge("LIVE" if not s.paused else "HOLD",
                  kind="error" if not s.paused else "warning"),
            dim_text(f"t+{s.t}s"), justify="between"),
        row(
            card(hexdump(), title="memory dump", pad=1),
            col(
                card(logpane(s), title="access log", pad=1),
                card(nodemap(s), title="node map", pad=1),
                gap=1,
            ),
            gap=2,
        ),
        progress(s.prog, f"⚡ {STAGES[s.stage]}", width=50, fill="lime"),
        dim_text("space pause · q quit · (it's all fake, relax)"),
        title="hacker", gap=1,
    )


if __name__ == "__main__":
    app.run()
