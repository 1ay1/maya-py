"""space.py — NASA-style Mission Control Dashboard.

A faithful port of maya's `examples/space.cpp`. An animated spacecraft
telemetry display tracking a journey to Mars: gauges, sparklines, a thermal
heatmap, a trajectory line chart, a power bar chart, crew status with badges
and health bars, subsystem health, a scrolling comm log, random event toasts,
and a physics simulation — all rendered with maya's native widgets.

  Controls:
    q/Esc   quit
    space   manual thruster burn
    a       abort sequence
    d       diagnostics dump
    1-3     mission phase (launch/transit/orbit)

    PYTHONPATH=src python examples/space.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, b, col, row, card, grow, spacer,
    gauge, sparkline, heatmap, line_chart, bar_chart, badge, callout,
)


def randf(lo, hi):
    return random.uniform(lo, hi)


def randi(lo, hi):
    return random.randint(lo, hi)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def fmt_f(v, decimals=1):
    return f"{v:.{decimals}f}"


def fmt_time(total_secs):
    h = int(total_secs) // 3600
    m = (int(total_secs) % 3600) // 60
    s = int(total_secs) % 60
    return f"{h:03d}:{m:02d}:{s:02d}"


DOT_SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def dot_spin(frame):
    return DOT_SPIN[frame % 10]


HIST_SIZE = 30
MAX_LOG = 6

PHASE_NAMES = ["LAUNCH", "TRANSIT", "ORBIT INSERTION"]

LOG_MSGS = [
    "CAPCOM: telemetry nominal, all stations go",
    "NAV: trajectory correction delta-v computed",
    "EECOM: power bus voltage within limits",
    "FLIGHT: GO for next burn window",
    "GNC: attitude stable, drift < 0.01 deg/s",
    "FIDO: orbit parameters confirmed",
    "CAPCOM: crew health check satisfactory",
    "RETRO: abort window T+04:32 to T+06:15",
    "INCO: high-gain antenna locked on DSN",
    "SURGEON: crew vitals nominal",
    "BOOSTER: stage separation confirmed",
    "TELMU: thermal margins acceptable",
]

EVENTS = [
    ("Micrometeorite detected — hull scan initiated", "warning"),
    ("Solar flare warning — radiation spike", "error"),
    ("Comm signal degraded — switching to backup", "warning"),
    ("Course correction burn completed", "success"),
    ("Deep Space Network handover complete", "info"),
    ("Thermal anomaly detected in module B4", "warning"),
]


class State:
    def __init__(self):
        # Telemetry
        self.fuel = 0.92
        self.o2 = 0.97
        self.power = 0.85
        self.hull = 1.0
        # Navigation
        self.pos_x = self.pos_y = self.pos_z = 0.0
        self.heading = 47.3
        self.dist_to_target = 225000000.0  # km to Mars
        self.velocity = 11.2  # km/s
        self.altitude = 400.0  # km
        self.temperature = 22.0
        # History
        self.vel_hist = [11.2] * HIST_SIZE
        self.alt_hist = [400.0] * HIST_SIZE
        self.temp_hist = [22.0] * HIST_SIZE
        self.traj_hist = [400.0] * HIST_SIZE
        # Heatmap 8x8
        self.thermal_grid = [[0.3] * 8 for _ in range(8)]
        # Crew: [name, role, health, stress]
        self.crew = [
            ["Cmdr. Chen", "Commander", 0.95, 0.12],
            ["Dr. Okafor", "Flight Surgeon", 0.88, 0.18],
            ["Lt. Vasquez", "Pilot", 0.92, 0.15],
            ["Eng. Petrov", "Engineer", 0.90, 0.20],
        ]
        # Subsystems: [name, status(0 ok/1 warn/2 fail), uptime]
        self.subsystems = [
            ["Main Engine", 0, 1.0],
            ["Life Support", 0, 1.0],
            ["Comms Array", 0, 1.0],
            ["Nav Computer", 0, 1.0],
            ["Solar Panels", 0, 1.0],
            ["Thermal Ctrl", 0, 1.0],
            ["Attitude Ctrl", 0, 1.0],
            ["Rad Shield", 0, 1.0],
        ]
        # Power distribution
        self.pwr_engines = 0.35
        self.pwr_lifesup = 0.25
        self.pwr_comms = 0.15
        self.pwr_nav = 0.10
        self.pwr_thermal = 0.10
        self.pwr_shield = 0.05
        # Comm log: [timestamp, msg, severity]
        self.comm_log = []
        # Toasts: [msg, severity, ttl]
        self.toasts = []
        # Mission
        self.mission_phase = 0
        self.elapsed = 0.0
        self.frame_count = 0
        self.abort_sequence = False
        self.abort_timer = 0.0
        self.diag_mode = False
        self.diag_timer = 0.0
        self.init_state()

    def init_state(self):
        for i in range(HIST_SIZE):
            self.vel_hist[i] = 11.2 + randf(-0.3, 0.3)
            self.alt_hist[i] = 400.0 + randf(-10, 10)
            self.temp_hist[i] = 22.0 + randf(-2, 2)
            self.traj_hist[i] = 400.0 + i * 5.0 + randf(-5, 5)
        for r in range(8):
            for c in range(8):
                self.thermal_grid[r][c] = randf(0.15, 0.45)


W = State()


def tick(dt):
    s = W
    s.elapsed += dt
    s.frame_count += 1

    if s.abort_sequence:
        s.abort_timer -= dt
        if s.abort_timer <= 0:
            s.abort_sequence = False
    if s.diag_mode:
        s.diag_timer -= dt
        if s.diag_timer <= 0:
            s.diag_mode = False

    for t in s.toasts:
        t[2] -= dt
    s.toasts = [t for t in s.toasts if t[2] > 0]

    fuel_rate = 0.0008 if s.mission_phase == 0 else 0.0002
    s.fuel = clamp(s.fuel - fuel_rate * dt, 0.0, 1.0)

    s.o2 = clamp(s.o2 + randf(-0.002, 0.001) * dt, 0.3, 1.0)
    s.power = clamp(s.power + randf(-0.003, 0.003) * dt, 0.2, 1.0)
    s.hull = clamp(s.hull + randf(-0.0001, 0.00005) * dt, 0.5, 1.0)

    vel_drift = 0.05 if s.mission_phase == 0 else -0.01
    s.velocity = clamp(s.velocity + vel_drift * dt + randf(-0.1, 0.1) * dt, 3.0, 30.0)

    alt_rate = 15.0 if s.mission_phase == 0 else (-2.0 if s.mission_phase == 2 else 5.0)
    s.altitude = max(100.0, s.altitude + alt_rate * dt + randf(-2, 2) * dt)

    sun_angle = math.sin(s.elapsed * 0.1)
    s.temperature = 20.0 + sun_angle * 15.0 + randf(-0.5, 0.5)

    s.pos_x += s.velocity * 0.7 * dt
    s.pos_y += s.velocity * 0.3 * dt + randf(-0.1, 0.1)
    s.pos_z += randf(-0.05, 0.05)
    s.heading = math.fmod(s.heading + randf(-0.2, 0.2) + 360.0, 360.0)
    s.dist_to_target = max(0.0, s.dist_to_target - s.velocity * dt)

    def push_hist(h, v):
        h.pop(0)
        h.append(v)

    push_hist(s.vel_hist, s.velocity)
    push_hist(s.alt_hist, s.altitude)
    push_hist(s.temp_hist, s.temperature)
    push_hist(s.traj_hist, s.altitude)

    for r in range(8):
        for c in range(8):
            cell = s.thermal_grid[r][c]
            base = (8 - r) / 8.0 * 0.3
            sun = (sun_angle + 1.0) / 2.0 * 0.3
            cell += (base + sun + randf(-0.05, 0.05) - cell) * 0.15
            s.thermal_grid[r][c] = clamp(cell, 0.0, 1.0)

    for c in s.crew:
        c[2] = clamp(c[2] + randf(-0.002, 0.001) * dt, 0.4, 1.0)
        c[3] = clamp(c[3] + randf(-0.003, 0.004) * dt, 0.0, 0.8)

    for sub in s.subsystems:
        sub[2] += dt
        if randi(0, 500) == 0:
            sub[1] = randi(0, 1)
        elif randi(0, 2000) == 0:
            sub[1] = 2
        if sub[1] > 0 and randi(0, 100) == 0:
            sub[1] = 0

    s.pwr_engines = clamp(s.pwr_engines + randf(-0.01, 0.01), 0.1, 0.5)
    s.pwr_lifesup = clamp(s.pwr_lifesup + randf(-0.005, 0.005), 0.15, 0.35)
    s.pwr_comms = clamp(s.pwr_comms + randf(-0.005, 0.005), 0.05, 0.25)

    if randi(0, 15) == 0:
        lvl = 0 if randi(0, 10) < 7 else (2 if randi(0, 3) == 0 else 1)
        s.comm_log.append([s.elapsed, LOG_MSGS[randi(0, 11)], lvl])
        if len(s.comm_log) > MAX_LOG:
            s.comm_log.pop(0)

    if randi(0, 200) == 0:
        msg, sev = EVENTS[randi(0, 5)]
        s.toasts.append([msg, sev, 5.0])
        if sev == "error":
            s.hull = max(0.5, s.hull - 0.02)
        if sev == "warning" and randi(0, 2) == 0:
            s.subsystems[randi(0, 7)][1] = 1


# ── UI builders ──────────────────────────────────────────────────────────────

def panel(label, *children):
    return card(*children, title=label, border_color=(40, 45, 60), pad=(0, 1))


def status_color(v):
    if v > 0.7:
        return (0, 255, 136)
    if v > 0.4:
        return (255, 200, 60)
    return (255, 60, 60)


def severity_color(lvl):
    if lvl == 2:
        return (255, 60, 60)
    if lvl == 1:
        return (255, 200, 60)
    return (80, 80, 100)


def build_header():
    s = W
    spin = dot_spin(s.frame_count)
    met = fmt_time(s.elapsed)
    phase_str = PHASE_NAMES[s.mission_phase]
    phase_sty = ((255, 140, 50) if s.mission_phase == 0
                 else (100, 180, 255) if s.mission_phase == 1
                 else (0, 255, 136))
    parts = [
        T(spin).fg((0, 180, 255)),
        T(" MISSION CONTROL").bold.fg((0, 180, 255)),
        T(" ─ ").dim,
        T("ARES VII").bold.fg((255, 255, 255)),
        spacer(),
        T(f"MET {met}").fg((100, 180, 255)),
        T("  PHASE: ").dim,
        T(phase_str).fg(phase_sty).bold,
    ]
    if s.abort_sequence:
        parts.append(T(f" ABORT T-{fmt_f(s.abort_timer, 0)}s").fg((255, 50, 50)).bold)
    if s.diag_mode:
        parts.append(T("  [DIAG]").fg((255, 200, 60)))
    return row(*parts, gap=0, pad=(0, 1))


def build_telemetry_panel():
    s = W
    return panel(
        " TELEMETRY ",
        row(
            grow(gauge(s.fuel, "FUEL", color=(0, 255, 136))),
            grow(gauge(s.o2, "O2", color=(100, 180, 255))),
            grow(gauge(s.power, "POWER", color=(255, 200, 60))),
            grow(gauge(s.hull, "HULL", color=(198, 160, 246))),
            gap=1,
        ),
    )


def build_sparklines_panel():
    s = W
    return panel(
        " SENSORS ",
        sparkline(s.vel_hist, label="VEL", color=(0, 255, 200), show_min_max=True),
        sparkline(s.alt_hist, label="ALT", color=(100, 180, 255), show_min_max=True),
        sparkline(s.temp_hist, label="TMP", color=(255, 140, 50), show_min_max=True),
    )


def build_nav_panel():
    s = W
    coord = f"{s.pos_x:.1f}, {s.pos_y:.1f}, {s.pos_z:.1f}"
    dist_str = f"{s.dist_to_target / 1000000.0:.1f}M km"
    return panel(
        " NAVIGATION ",
        row(T("COORD").fg((100, 180, 255)), T(coord).dim, gap=2),
        row(T("HDG").fg((100, 180, 255)), T(f"{fmt_f(s.heading, 1)}°").dim, gap=2),
        row(T("VEL").fg((100, 180, 255)),
            T(f"{fmt_f(s.velocity, 2)} km/s").fg(status_color(s.velocity / 15.0)), gap=2),
        row(T("DIST").fg((100, 180, 255)), T(dist_str).fg((255, 200, 60)), gap=2),
    )


def build_heatmap_panel():
    return panel(
        " THERMAL SIGNATURE ",
        heatmap(W.thermal_grid, low=(20, 20, 80), high=(255, 80, 30),
                y_labels=["F1", "F2", "F3", "F4", "A1", "A2", "A3", "A4"]),
    )


def build_trajectory_panel():
    return panel(
        " TRAJECTORY ",
        line_chart(W.traj_hist, height=6, label="Altitude (km)", color=(0, 200, 255)),
    )


def build_comm_log_panel():
    s = W
    rows = []
    for ts, msg, sev in s.comm_log:
        mins = int(ts) // 60
        secs = int(ts) % 60
        tag = "ERR " if sev == 2 else ("WARN" if sev == 1 else "INFO")
        rows.append(row(
            T(f"T+{mins:02d}:{secs:02d}").dim,
            T(tag).fg(severity_color(sev)).bold,
            T(msg).dim,
            gap=1,
        ))
    while len(rows) < MAX_LOG:
        rows.append(T(""))
    return panel(" COMM LOG ", *rows)


def build_crew_panel():
    rows = []
    for name, role, health, _stress in W.crew:
        health_pct = int(health * 100)
        kind = ("info" if role == "Commander"
                else "warning" if role == "Pilot"
                else "success" if role == "Flight Surgeon"
                else "tool")
        filled = int(health * 10)
        bar = "█" * filled + "─" * (10 - filled)
        rows.append(row(
            T(name).fg((200, 200, 220)).bold,
            badge(role, kind=kind),
            T(bar).fg(status_color(health)),
            T(f"{health_pct}%").dim,
            gap=1,
        ))
    return panel(" CREW STATUS ", *rows)


def build_subsystems_panel():
    rows = []
    for name, status, _uptime in W.subsystems:
        icon = "✓" if status == 0 else ("⚠" if status == 1 else "✗")
        sty = ((0, 255, 136) if status == 0
               else (255, 200, 60) if status == 1
               else (255, 60, 60))
        label = "NOMINAL" if status == 0 else ("CAUTION" if status == 1 else "OFFLINE")
        rows.append(row(
            T(icon).fg(sty),
            T(name).dim,
            T(label).fg(sty),
            gap=1,
        ))
    return panel(" SUBSYSTEMS ", *rows)


def build_power_panel():
    s = W
    return panel(
        " POWER DIST ",
        bar_chart([
            ("Engines", s.pwr_engines, (255, 140, 50)),
            ("Life Sup", s.pwr_lifesup, (0, 255, 136)),
            ("Comms", s.pwr_comms, (100, 180, 255)),
            ("Nav", s.pwr_nav, (198, 160, 246)),
            ("Thermal", s.pwr_thermal, (255, 200, 60)),
            ("Shielding", s.pwr_shield, (255, 80, 100)),
        ], max_value=0.5),
    )


def build_toasts():
    if not W.toasts:
        return None
    return col(*[callout(msg, kind=sev) for msg, sev, _ttl in W.toasts], gap=0)


def build_status_bar():
    s = W
    warnings = sum(1 for sub in s.subsystems if sub[1] == 1)
    errors = sum(1 for sub in s.subsystems if sub[1] == 2)
    overall = "RED" if errors else ("YELLOW" if warnings else "GREEN")
    overall_sty = ((255, 60, 60) if errors
                   else (255, 200, 60) if warnings
                   else (0, 255, 136))
    return row(
        T(" STATUS: ").fg((140, 140, 160)),
        T(overall).fg(overall_sty).bold,
        T(f"  FUEL:{int(s.fuel * 100)}%").fg(status_color(s.fuel)),
        spacer(),
        T(" ␣").bold.fg((180, 220, 255)), T(":burn").fg((120, 120, 140)),
        T(" a").bold.fg((180, 220, 255)), T(":abort").fg((120, 120, 140)),
        T(" d").bold.fg((180, 220, 255)), T(":diag").fg((120, 120, 140)),
        T(" 1-3").bold.fg((180, 220, 255)), T(":phase").fg((120, 120, 140)),
        T(" q").bold.fg((180, 220, 255)), T(":quit ").fg((120, 120, 140)),
        gap=0, pad=(0, 1), bg=(30, 30, 42),
    )


# ── App ──────────────────────────────────────────────────────────────────────

app = App("ARES VII Mission Control", inline=False, fps=15)
app.state(_t=0.0)


def _log(msg, sev):
    W.comm_log.append([W.elapsed, msg, sev])
    if len(W.comm_log) > MAX_LOG:
        W.comm_log.pop(0)


@app.on("space")
def _burn(s):
    if W.fuel > 0.05:
        W.fuel -= 0.03
        W.velocity += 1.5
        W.toasts.append(["Manual thruster burn executed — delta-v +1.5 km/s", "success", 3.0])
        _log("FLIGHT: Manual burn confirmed, delta-v applied", 0)
    else:
        W.toasts.append(["FUEL CRITICAL — burn denied", "error", 4.0])


@app.on("a")
def _abort(s):
    if not W.abort_sequence:
        W.abort_sequence = True
        W.abort_timer = 10.0
        W.toasts.append(["ABORT SEQUENCE INITIATED — T-10s", "error", 5.0])
        _log("FLIGHT: ABORT ABORT ABORT — all stations standby", 2)
        for c in W.crew:
            c[3] += 0.15
    else:
        W.abort_sequence = False
        W.toasts.append(["Abort sequence cancelled", "info", 3.0])


@app.on("d")
def _diag(s):
    W.diag_mode = not W.diag_mode
    W.diag_timer = 5.0
    if W.diag_mode:
        W.toasts.append(["Diagnostics scan in progress...", "info", 3.0])
        for sub in W.subsystems:
            if sub[1] > 0:
                sub[1] = 0
                break


@app.on("1")
def _p1(s):
    W.mission_phase = 0
    W.toasts.append(["Phase set: LAUNCH", "info", 2.0])


@app.on("2")
def _p2(s):
    W.mission_phase = 1
    W.toasts.append(["Phase set: TRANSIT", "info", 2.0])


@app.on("3")
def _p3(s):
    W.mission_phase = 2
    W.toasts.append(["Phase set: ORBIT INSERTION", "info", 2.0])


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 15.0)


@app.view
def view(s):
    left = grow(col(
        build_telemetry_panel(),
        build_sparklines_panel(),
        build_nav_panel(),
    ))
    center = grow(col(
        build_heatmap_panel(),
        build_trajectory_panel(),
        build_comm_log_panel(),
    ))
    right = grow(col(
        build_crew_panel(),
        build_subsystems_panel(),
        build_power_panel(),
    ))
    main_area = row(left, center, right, gap=1)

    layout = [build_header(), main_area]
    toasts = build_toasts()
    if toasts is not None:
        layout.append(toasts)
    layout.append(build_status_bar())
    return col(*layout, gap=0)


if __name__ == "__main__":
    app.run()
