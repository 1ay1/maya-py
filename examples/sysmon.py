"""sysmon.py — Fullscreen System Monitor / Hacker Console.

A faithful port of maya's `examples/sysmon.cpp`. A live dashboard of fake
telemetry: CPU cores with braille sparklines, memory banks, network interfaces,
a process table, an entropy pool, and a scrolling activity log — all built from
unicode block/braille glyphs inside maya's native text/box layout.

  Controls:
    q/Esc quit · p pause · s cycle process sort · l toggle log
    1/2/3 speed (0.25/1/4×) · space log burst

    PYTHONPATH=src python examples/sysmon.py
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, card, spacer, clamp, randf, randi, spin, bar, keyhints  # noqa: E402


def usage_color(v):
    if v > 0.8:
        return (255, 60, 60)
    if v > 0.5:
        return (255, 200, 60)
    return (0, 255, 136)


def level_color(lvl):
    if lvl == 2:
        return (255, 60, 60)
    if lvl == 1:
        return (255, 200, 60)
    return (80, 80, 100)


BRAILLE_BARS = ["⠀", "⣀", "⣤", "⣴", "⣶", "⣷", "⣿", "⣿"]


def braille_bar(v):
    return BRAILLE_BARS[clamp(int(v * 7), 0, 7)]


def hex_char():
    return random.choice("0123456789abcdef")


NUM_CORES = 8
NUM_MEM = 4
NUM_NET = 3
MAX_LOG = 8

SORT_NAMES = ["cpu", "mem", "pid"]

LOG_MSGS = [
    "kernel: TCP connection established 10.0.3.17:443",
    "systemd: Started Session 4823 of user deploy",
    "sshd: Accepted publickey for root from 192.168.1.5",
    "kernel: eth0: link up, 10Gbps full duplex",
    "docker: container nginx-prod health check passed",
    "cron: (deploy) CMD (/usr/bin/backup.sh)",
    "kernel: CPU0: Core temperature above threshold",
    "postgres: checkpoint complete: wrote 1247 buffers",
    "nginx: 200 GET /api/v2/metrics 14ms",
    "redis: Background saving terminated with success",
    "kernel: audit: type=1400 apparmor=DENIED",
    "systemd: Reached target Multi-User System",
    "kubelet: Successfully pulled image registry/app:v2.3",
    "kernel: usb 1-2: new high-speed USB device",
    "fail2ban: Ban 45.137.21.9 for repeated failures",
    "kernel: Out of memory: Killed process 9921 (chrome)",
]


class Core:
    __slots__ = ("usage", "temp", "freq", "history", "hist_idx")

    def __init__(self):
        self.usage = 0.0
        self.temp = 45.0
        self.freq = 3.2
        self.history = [0.0] * 20
        self.hist_idx = 0


class State:
    def __init__(self):
        self.cores = [Core() for _ in range(NUM_CORES)]
        # mem banks: [name, used(0..1), total_gb]
        self.mem_banks = [
            ["DIMM-A1", 0.62, 16],
            ["DIMM-A2", 0.45, 16],
            ["DIMM-B1", 0.38, 32],
            ["DIMM-B2", 0.21, 32],
        ]
        # net: [name, rx_mbps, tx_mbps, rx_total, tx_total, rx_spark[16], spark_idx]
        self.net_ifaces = [
            ["eth0", 0.0, 0.0, 0.0, 0.0, [0.0] * 16, 0],
            ["wlan0", 0.0, 0.0, 0.0, 0.0, [0.0] * 16, 0],
            ["lo", 0.0, 0.0, 0.0, 0.0, [0.0] * 16, 0],
        ]
        # processes: [name, pid, cpu, mem_mb]
        self.processes = [
            ["systemd", 1, 0.1, 12.4],
            ["sshd", 892, 0.3, 8.2],
            ["postgres", 1204, 4.2, 256.0],
            ["nginx", 1567, 1.8, 64.0],
            ["node", 2341, 12.5, 512.0],
            ["redis-server", 3012, 2.1, 128.0],
            ["containerd", 445, 3.7, 96.0],
            ["kubelet", 512, 5.2, 384.0],
        ]
        # log: [timestamp, msg, level]
        self.activity_log = []
        self.uptime = 0.0
        self.frame_count = 0
        self.entropy_pool = 0.72
        self.total_syscalls = 0
        self.paused = False
        self.show_log = True
        self.sort_mode = 0
        self.speed = 1.0
        self.init_state()

    def init_state(self):
        for c in self.cores:
            c.usage = randf(0.05, 0.4)
            c.temp = randf(42, 58)
            c.freq = randf(2.8, 4.2)


S = State()


def tick(dt):
    s = S
    if s.paused:
        s.frame_count += 1
        return
    dt *= s.speed
    s.uptime += dt
    s.frame_count += 1
    s.total_syscalls += randi(800, 3000)

    for c in s.cores:
        target = randf(0.02, 0.95)
        if randi(0, 60) == 0:
            target = randf(0.8, 1.0)
        c.usage += (target - c.usage) * 0.15
        c.temp = 42.0 + c.usage * 38.0 + randf(-2, 2)
        c.freq = 2.4 + c.usage * 2.0 + randf(-0.1, 0.1)
        c.history[c.hist_idx] = c.usage
        c.hist_idx = (c.hist_idx + 1) % 20

    for mb in s.mem_banks:
        mb[1] = clamp(mb[1] + randf(-0.01, 0.015), 0.05, 0.95)

    for n in s.net_ifaces:
        is_lo = n[0] == "lo"
        base_rx = randf(0, 5) if is_lo else randf(0, 800)
        base_tx = randf(0, 5) if is_lo else randf(0, 200)
        n[1] += (base_rx - n[1]) * 0.2
        n[2] += (base_tx - n[2]) * 0.2
        n[3] += n[1] * dt * 125000
        n[4] += n[2] * dt * 125000
        n[5][n[6]] = n[1] / 800.0
        n[6] = (n[6] + 1) % 16

    for p in s.processes:
        p[2] = clamp(p[2] + randf(-2, 2), 0, 100)
        p[3] = max(1, p[3] + randf(-5, 5))

    s.entropy_pool = clamp(s.entropy_pool + randf(-0.03, 0.03), 0.3, 1.0)

    if randi(0, 8) == 0:
        lvl = 0 if randi(0, 10) < 7 else (2 if randi(0, 3) == 0 else 1)
        s.activity_log.append([s.uptime, LOG_MSGS[randi(0, 15)], lvl])
        if len(s.activity_log) > MAX_LOG:
            s.activity_log.pop(0)


# ── Panels ───────────────────────────────────────────────────────────────────

def build_header():
    s = S
    h = "".join(hex_char() for _ in range(8))
    glyph = spin(s.frame_count)
    parts = [
        T(f"{glyph} SYSMON").fg((0, 255, 136)).bold,
        T(" v3.7.1").dim,
    ]
    if s.paused:
        parts.append(T(" ⏸ PAUSED").fg((255, 60, 60)).bold)
    parts.append(T(f" ×{int(s.speed)}").fg((255, 200, 60)))
    parts.extend([
        spacer(),
        T("node:").dim,
        T("prod-us-east-1a").fg((100, 180, 255)),
        T(f" 0x{h}").fg((80, 80, 100)),
    ])
    return row(*parts, gap=0, pad=(0, 1))


def build_cpu_panel():
    s = S
    rows = []
    for i, c in enumerate(s.cores):
        spark = "".join(braille_bar(c.history[(c.hist_idx + k) % 20]) for k in range(20))
        pct = int(c.usage * 100)
        freq_i = int(c.freq * 10)
        freq_str = f"{freq_i // 10}.{freq_i % 10}GHz"
        ubar = bar(c.usage, 12, fill="▓", track="░")
        rows.append(row(
            T(f"CPU{i}").fg((100, 180, 255)).bold,
            T(ubar).fg(usage_color(c.usage)),
            T(f"{pct}%").bold,
            T(f"{int(c.temp)}°C").dim,
            T(freq_str).dim,
            T(spark).fg((80, 200, 255)),
            gap=1,
        ))
    avg = sum(c.usage for c in s.cores) / len(s.cores)
    rows.append(row(
        T("TOTAL").fg((255, 200, 60)).bold,
        T(bar(avg, 12, fill="▓", track="░")).fg((255, 200, 60)),
        T(f"{int(avg * 100)}%").bold,
        T(f"load:{int(avg * 8 * 1.2 * 10) / 10}").dim,
        gap=1,
    ))
    return card(*rows, title=" CPU ", border_color=(50, 55, 70), pad=(0, 1))


def build_mem_panel():
    s = S
    rows = []
    total_used = 0.0
    total_cap = 0.0
    for name, used, total_gb in s.mem_banks:
        used_gb = used * total_gb
        total_used += used_gb
        total_cap += total_gb
        ubar = bar(used, 16, fill="▓", track="░")
        rows.append(row(
            T(name).fg((100, 180, 255)),
            T(ubar).fg(usage_color(used)),
            T(f"{int(used_gb)}/{total_gb}G").dim,
            gap=1,
        ))
    pct = int(total_used / total_cap * 100) if total_cap else 0
    rows.append(row(
        T("TOTAL").fg((255, 200, 60)).bold,
        T(f"{int(total_used)}/{int(total_cap)} GB").bold,
        T(f"({pct}%)").dim,
        T("swap: 0K").dim,
        gap=1,
    ))
    return card(*rows, title=" MEM ", border_color=(50, 55, 70), pad=(0, 1))


def fmt_bytes(v):
    if v > 1e9:
        return f"{v / 1e9:.1f}G"
    if v > 1e6:
        return f"{v / 1e6:.1f}M"
    if v > 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{int(v)}B"


def build_net_panel():
    s = S
    rows = []
    for n in s.net_ifaces:
        spark = "".join(braille_bar(n[5][(n[6] + k) % 16]) for k in range(16))
        rows.append(row(
            T(n[0]).fg((100, 180, 255)).bold,
            T(f"▲ {int(n[2])}").fg((255, 120, 80)),
            T(f"▼ {int(n[1])}").fg((0, 255, 136)),
            T("Mb/s").dim,
            T(f"{fmt_bytes(n[3])}/{fmt_bytes(n[4])}").dim,
            T(spark).fg((120, 80, 255)),
            gap=1,
        ))
    return card(*rows, title=" NET ", border_color=(50, 55, 70), pad=(0, 1))


def build_proc_panel():
    s = S
    procs = list(s.processes)
    if s.sort_mode == 0:
        procs.sort(key=lambda p: p[2], reverse=True)
    elif s.sort_mode == 1:
        procs.sort(key=lambda p: p[3], reverse=True)
    else:
        procs.sort(key=lambda p: p[1])
    rows = [row(
        T("PID").dim.bold, T("NAME").dim.bold, T("CPU%").dim.bold,
        T("MEM").dim.bold, gap=1,
    )]
    for name, pid, cpu, mem_mb in procs[:6]:
        rows.append(row(
            T(str(pid)).fg((100, 180, 255)),
            T(name).bold,
            T(f"{int(cpu)}%").fg(usage_color(cpu / 100)),
            T(f"{int(mem_mb)}M").dim,
            gap=1,
        ))
    return card(*rows, title=f" PROC [sort:{SORT_NAMES[s.sort_mode]}] ",
                border_color=(50, 55, 70), pad=(0, 1))


def build_log_panel():
    s = S
    rows = []
    for ts, msg, lvl in s.activity_log:
        mins = int(ts) // 60
        secs = int(ts) % 60
        tag = "ERR " if lvl == 2 else ("WARN" if lvl == 1 else "INFO")
        rows.append(row(
            T(f"{mins:02d}:{secs:02d}").dim,
            T(tag).fg(level_color(lvl)).bold,
            T(msg).dim,
            gap=1,
        ))
    while len(rows) < MAX_LOG:
        rows.append(T(""))
    return card(*rows, title=" LOG ", border_color=(50, 55, 70), pad=(0, 1))


def build_status_bar():
    s = S
    mins = int(s.uptime) // 60
    secs = int(s.uptime) % 60
    entropy_bar = bar(s.entropy_pool, 8, fill="▓", track="░")
    sc = s.total_syscalls
    if sc > 1e9:
        sc_str = f"{sc / 1e9:.1f}G"
    elif sc > 1e6:
        sc_str = f"{sc / 1e6:.1f}M"
    elif sc > 1e3:
        sc_str = f"{sc / 1e3:.1f}K"
    else:
        sc_str = str(sc)
    return row(
        T(f" ⏱ {mins:02d}:{secs:02d}").fg((100, 180, 255)),
        T("  entropy:").fg((140, 140, 160)),
        T(entropy_bar).fg((0, 255, 136)),
        T("  syscalls:").fg((140, 140, 160)),
        T(sc_str).fg((255, 200, 60)),
        T(f"  f:{s.frame_count}").fg((100, 100, 120)),
        spacer(),
        keyhints(("q", "quit"), ("p", "pause"), ("s", "sort"), ("l", "log"),
                 ("1-3", "speed"), ("␣", "burst")),
        gap=0, pad=(0, 1), bg=(30, 30, 42),
    )


# ── App ──────────────────────────────────────────────────────────────────────

app = App.fullscreen("sysmon", fps=15)
app.state(_t=0.0)


@app.on("p")
def _pause(s):
    S.paused = not S.paused


@app.on("l")
def _log(s):
    S.show_log = not S.show_log


@app.on("s")
def _sort(s):
    S.sort_mode = (S.sort_mode + 1) % 3


@app.on("1")
def _sp1(s):
    S.speed = 0.25


@app.on("2")
def _sp2(s):
    S.speed = 1.0


@app.on("3")
def _sp3(s):
    S.speed = 4.0


@app.on("space")
def _burst(s):
    for _ in range(5):
        S.activity_log.append([S.uptime, LOG_MSGS[randi(0, 15)], randi(0, 2)])
    while len(S.activity_log) > MAX_LOG:
        S.activity_log.pop(0)


app.quit_on("q", "esc")


app.simulate(tick)


@app.view
def view(s):
    panels = [
        build_header(),
        build_cpu_panel(),
        build_mem_panel(),
        build_net_panel(),
        build_proc_panel(),
    ]
    if S.show_log:
        panels.append(build_log_panel())
    panels.append(build_status_bar())
    return col(*panels, gap=0)


if __name__ == "__main__":
    app.run()
