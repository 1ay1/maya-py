"""hacker.py — Cyberpunk Hacker Terminal (NEXUS://BREACH).

A faithful port of maya's `examples/hacker.cpp`. A movie-style "hacking"
terminal: a live targets panel, a scrolling terminal log with expanded
templates, an intel sidebar with native sparklines, a password-crack progress
bar, a net-topology heatmap and system-load gauges, plus a hex-dump footer and
breach / extract / cover-tracks sequences. Pure eye candy, all simulated.

  Controls:
    space  initiate breach     e  extract data     c  cover tracks
    1/2/3  theme               q/Esc  quit

    PYTHONPATH=src python examples/hacker.py
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, grow, spacer,
    sparkline, progress, heatmap, badge,
    Theme, ThemeSet, clamp,
)


def randi(lo, hi):
    return random.randint(lo, hi)


def randf(lo, hi):
    return random.uniform(lo, hi)


# Themes: named colour roles, cycled with keys 1/2/3
themes = ThemeSet(
    Theme("PHOSPHOR", primary=(0, 255, 65), bright=(0, 255, 136), dim=(0, 100, 30),
          accent=(0, 200, 100), alert=(255, 50, 50), border=(0, 60, 20)),
    Theme("AMBER", primary=(255, 176, 0), bright=(255, 220, 80), dim=(140, 90, 0),
          accent=(255, 200, 60), alert=(255, 60, 60), border=(80, 55, 0)),
    Theme("ICE", primary=(0, 200, 255), bright=(100, 220, 255), dim=(0, 80, 130),
          accent=(0, 160, 220), alert=(255, 50, 80), border=(0, 40, 70)),
)


def TH():
    return themes.current


def rand_hex_str(n):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def rand_ip():
    return f"{randi(10, 223)}.{randi(0, 255)}.{randi(0, 255)}.{randi(1, 254)}"


HOST_PREFIX = ["srv", "node", "db", "proxy", "gw", "vpn", "fw", "core", "edge", "cache"]
HOST_SUFFIX = [".corp.net", ".darknet.io", ".shadow.sys", ".zero.lan", ".ghost.onion"]


def rand_hostname():
    return f"{random.choice(HOST_PREFIX)}-{randi(1, 99)}{random.choice(HOST_SUFFIX)}"


def block_bar(v, width):
    filled = clamp(int(v * width), 0, width)
    return "█" * filled + "░" * (width - filled)


DOT_SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def dot_spin(frame):
    return DOT_SPIN[frame % 10]


MAX_LOG = 18

SERVICES = ["ssh", "http", "https", "mysql", "redis", "postgres", "ftp", "smtp", "dns", "telnet"]
PORTS = [22, 80, 443, 3306, 6379, 5432, 21, 25, 53, 23]

LOG_TEMPLATES = [
    "Scanning port %PORT%... OPEN",
    "Injecting payload 0x%HEX8%...",
    "Bruteforce attempt on %SVC% service",
    "Buffer overflow at 0x%HEX8%",
    "ARP spoofing %IP% -> gateway",
    "Decrypting RSA-2048 key... %N%%",
    "SQL injection vector found on /api/%SVC%",
    "Reverse shell established to %IP%:%PORT%",
    "Privilege escalation via CVE-2026-%HEX4%",
    "Dumping /etc/shadow from %IP%",
    "Exploiting %SVC% daemon at %IP%:%PORT%",
    "Cracking WPA2 handshake... %N% keys/s",
    "Tunneling through %N% proxy hops",
    "Memory address 0x%HEX8% mapped",
    "Bypassing firewall rule #%N%",
    "Extracting credentials from %IP%",
    "Payload delivered to %SVC% on %PORT%",
    "Hooking syscall table at 0x%HEX8%",
    "Sniffing packets on eth0... %N% captured",
    "Defeating 2FA on %IP%",
    "Rootkit injected into kernel ring 0",
    "DNS cache poisoned for %SVC%",
    "Heap spray successful: 0x%HEX8%",
    "Zero-day CVE-2026-%HEX4% triggered",
]


def expand_template(tpl):
    out = tpl
    while "%PORT%" in out:
        out = out.replace("%PORT%", str(PORTS[randi(0, 9)]), 1)
    while "%HEX8%" in out:
        out = out.replace("%HEX8%", rand_hex_str(8), 1)
    while "%HEX4%" in out:
        out = out.replace("%HEX4%", rand_hex_str(4), 1)
    while "%IP%" in out:
        out = out.replace("%IP%", rand_ip(), 1)
    while "%SVC%" in out:
        out = out.replace("%SVC%", SERVICES[randi(0, 9)], 1)
    while "%N%" in out:
        out = out.replace("%N%", str(randi(1, 9999)), 1)
    return out


TOAST_MESSAGES = [
    "FIREWALL DETECTED", "ENCRYPTING CHANNEL", "BACKDOOR INSTALLED",
    "IDS ALERT BYPASSED", "PAYLOAD DELIVERED", "ROOT ACCESS OBTAINED",
    "EVIDENCE DESTROYED", "PROXY CHAIN ROTATED", "MEMORY WIPED",
    "TRACE ELIMINATED",
]


class State:
    def __init__(self):
        # targets: [ip, hostname, port, service, status, vuln, scan_progress, age]
        self.targets = []
        self.terminal_log = []  # [timestamp, message, level, opacity]
        self.inbound_spark = [0.0] * 20
        self.outbound_spark = [0.0] * 20
        self.spark_idx = 0
        self.crack_progress = 0.0
        self.heatmap_data = [[0.0] * 8 for _ in range(6)]
        self.cpu_load = 0.45
        self.mem_load = 0.62
        self.net_load = 0.38
        self.disk_io = 0.25
        self.hex_dump_line = ""
        self.toasts = []  # [message, level, ttl]
        self.elapsed = 0.0
        self.frame = 0
        self.next_target_time = 2.0
        self.next_toast_time = 4.0
        self.breaching = False
        self.breach_timer = 0.0
        self.breach_phase = 0
        self.covering = False
        self.cover_timer = 0.0
        self.extracting = False
        self.extract_timer = 0.0
        self.init_state()

    def timestamp(self):
        total = int(self.elapsed)
        h = (total // 3600) % 24
        m = (total // 60) % 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def add_log(self, msg, level=0):
        self.terminal_log.append([self.timestamp(), msg, level, 1.0])
        if len(self.terminal_log) > MAX_LOG:
            self.terminal_log.pop(0)

    def init_state(self):
        for i in range(5):
            si = randi(0, 9)
            status = "OPEN" if i < 3 else "SCANNING"
            self.targets.append([
                rand_ip(), rand_hostname(), PORTS[si], SERVICES[si],
                status, randi(0, 3),
                1.0 if i < 3 else randf(0.1, 0.7), randf(10, 120),
            ])
        self.add_log("NEXUS://BREACH v4.2.0 initialized", 1)
        self.add_log("Loading exploit database... 2,847 modules", 0)
        self.add_log("Establishing encrypted tunnel via TOR", 0)
        self.add_log("Proxy chain: 3 hops active", 1)
        self.add_log("Target acquisition mode: ACTIVE", 2)
        self.heatmap_data = [[randf(0, 0.6) for _ in range(8)] for _ in range(6)]
        self.hex_dump_line = rand_hex_str(48)


S = State()


def tick(dt):
    s = S
    s.elapsed += dt
    s.frame += 1

    if s.frame % 3 == 0:
        s.inbound_spark[s.spark_idx] = randf(0.1, 1.0)
        s.outbound_spark[s.spark_idx] = randf(0.05, 0.7)
        s.spark_idx = (s.spark_idx + 1) % 20

    s.crack_progress += randf(0.001, 0.004) * dt * 15.0
    if s.crack_progress > 1.0:
        s.crack_progress = randf(0.0, 0.15)

    for r in range(6):
        for c in range(8):
            s.heatmap_data[r][c] = clamp(s.heatmap_data[r][c] + randf(-0.05, 0.06), 0, 1)
    hr, hc = randi(0, 5), randi(0, 7)
    s.heatmap_data[hr][hc] = clamp(s.heatmap_data[hr][hc] + 0.15, 0, 1)

    s.cpu_load = clamp(s.cpu_load + randf(-0.03, 0.04), 0.1, 0.99)
    s.mem_load = clamp(s.mem_load + randf(-0.02, 0.02), 0.3, 0.95)
    s.net_load = clamp(s.net_load + randf(-0.04, 0.05), 0.05, 0.95)
    s.disk_io = clamp(s.disk_io + randf(-0.03, 0.03), 0.05, 0.80)

    s.hex_dump_line = rand_hex_str(64)

    if randi(0, 4) == 0:
        idx = randi(0, 23)
        lvl = 1 if randi(0, 6) == 0 else (2 if randi(0, 8) == 0 else 0)
        s.add_log(expand_template(LOG_TEMPLATES[idx]), lvl)

    if randi(0, 20) == 0:
        pct = randf(0.2, 0.98)
        filled = int(pct * 20)
        bar = "█" * filled + "░" * (20 - filled)
        s.add_log(f"{bar} {int(pct * 100)}% Decrypting...", 0)

    if randi(0, 15) == 0:
        line = "0x" + rand_hex_str(4) + ": " + "".join(rand_hex_str(2) + " " for _ in range(8))
        s.add_log(line, 0)

    if s.elapsed > s.next_target_time:
        s.next_target_time = s.elapsed + randf(3, 8)
        if len(s.targets) < 12:
            si = randi(0, 9)
            ip = rand_ip()
            host = rand_hostname()
            s.targets.append([ip, host, PORTS[si], SERVICES[si], "SCANNING",
                              randi(0, 3), 0.0, 0.0])
            s.add_log(f"New target discovered: {ip} ({host})", 1)

    for t in s.targets:
        t[7] += dt
        if t[4] == "SCANNING":
            t[6] += randf(0.01, 0.05)
            if t[6] >= 1.0:
                t[6] = 1.0
                t[4] = "OPEN"
                t[5] = randi(1, 3)
                s.add_log(f"Port {t[2]}/{t[3]} OPEN on {t[0]}", 1)

    if s.elapsed > s.next_toast_time:
        s.next_toast_time = s.elapsed + randf(5, 12)
        lvl = "error" if randi(0, 3) == 0 else ("warning" if randi(0, 2) == 0 else "success")
        s.toasts.append([TOAST_MESSAGES[randi(0, 9)], lvl, 3.5])
    for t in s.toasts:
        t[2] -= dt
    s.toasts = [t for t in s.toasts if t[2] > 0]

    if s.breaching:
        s.breach_timer -= dt
        if s.breach_timer <= 0:
            s.breach_phase += 1
            s.breach_timer = randf(0.5, 1.5)
            ph = s.breach_phase
            if ph == 1:
                s.add_log(">>> BREACH SEQUENCE INITIATED <<<", 3)
                s.add_log("Probing target defenses...", 2)
            elif ph == 2:
                s.add_log("Firewall rule injection: COMPLETE", 1)
                s.add_log("Escalating privileges...", 2)
            elif ph == 3:
                ip = s.targets[0][0] if s.targets else "unknown"
                s.add_log(f"Root shell obtained on {ip}", 1)
                s.toasts.append(["ACCESS GRANTED", "success", 3.5])
            elif ph == 4:
                s.add_log("Installing persistent backdoor...", 0)
                s.add_log("Modifying syslog to hide traces", 0)
            elif ph >= 5:
                s.add_log(">>> BREACH COMPLETE <<<", 1)
                if s.targets:
                    s.targets[0][4] = "EXPLOITED"
                s.breaching = False
                s.breach_phase = 0

    if s.covering:
        s.cover_timer -= dt
        for entry in s.terminal_log:
            entry[3] = max(0.1, entry[3] - dt * 0.8)
        if s.cover_timer <= 0:
            s.covering = False
            purge = min(len(s.terminal_log), randi(3, 8))
            del s.terminal_log[:purge]
            s.add_log(f"Tracks covered. {purge} log entries purged.", 1)
            s.toasts.append(["EVIDENCE DESTROYED", "warning", 3.5])

    if s.extracting:
        s.extract_timer -= dt
        if s.extract_timer <= 0:
            s.extracting = False
            s.add_log(f"Extraction complete: {randi(128, 4096)} MB exfiltrated", 1)
            s.toasts.append(["DATA EXFILTRATED", "success", 3.5])
        else:
            for _ in range(3):
                line = "0x" + rand_hex_str(8) + ": " + "".join(rand_hex_str(4) + " " for _ in range(8))
                s.add_log(line, 0)


# ── Panels ───────────────────────────────────────────────────────────────────

def build_header():
    s = S
    spin = dot_spin(s.frame)
    blink = (s.frame // 8) % 2 == 0
    dot = "●" if blink else "○"
    conn = f"TOR x3 | PROXY: {rand_ip()} | LAT: {randi(12, 350)}ms"
    return row(
        T(spin).fg(TH().primary),
        T("NEXUS://BREACH").fg(TH().bright).bold,
        T("v4.2.0").dim,
        T(dot).fg(TH().primary if blink else TH().dim),
        T(" CONNECTED").fg(TH().primary),
        spacer(),
        T(conn).fg(TH().dim),
        spacer(),
        T(TH().name).fg(TH().accent).bold,
        T("0x" + rand_hex_str(6)).fg(TH().dim),
        gap=1, pad=(0, 1),
    )


def build_targets_panel():
    s = S
    rows = [row(
        T("IP/HOST").dim.bold, T("PORT").dim.bold, T("STATUS").dim.bold,
        T("VULN").dim.bold, gap=1,
    )]
    for ip, host, port, _svc, status, vuln, scan, _age in s.targets:
        if status == "EXPLOITED":
            st_col = TH().primary
            st_t = T("EXPLOITED").fg(st_col).bold
        elif status == "OPEN":
            st_t = T("OPEN").fg((100, 200, 255))
        elif status == "SCANNING":
            st_t = T(f"SCANNING {int(scan * 100)}%").dim
        else:
            st_t = T("LOCKED").fg((255, 60, 60))
        if vuln == 3:
            vuln_el = badge("CRIT", kind="error")
        elif vuln == 2:
            vuln_el = badge("HIGH", kind="warning")
        elif vuln == 1:
            vuln_el = T("MED").fg((229, 192, 123))
        else:
            vuln_el = T("")
        display = ip if len(ip) >= 18 else host[:18]
        rows.append(row(
            T(display).fg(TH().accent),
            T(str(port)).dim,
            st_t,
            vuln_el,
            gap=1,
        ))
    while len(rows) < 11:
        rows.append(T(""))
    return card(*rows, title=" TARGETS ", border_color=TH().border, pad=(0, 1))


def build_terminal_panel():
    s = S
    rows = []
    for ts, msg, lvl, opacity in s.terminal_log:
        if lvl == 1:
            mc = TH().primary
            t_msg = T(msg).fg(mc).bold
        elif lvl == 2:
            t_msg = T(msg).fg((255, 200, 60)).bold
        elif lvl == 3:
            t_msg = T(msg).fg((255, 50, 50)).bold
        else:
            t_msg = T(msg).fg(TH().primary)
        ts_t = T(f"[{ts}]").dim
        if opacity < 0.5:
            ts_t = ts_t.dim
            t_msg = t_msg.dim
        rows.append(row(ts_t, t_msg, gap=1))
    while len(rows) < MAX_LOG:
        rows.append(T(""))
    return card(*rows, title=" TERMINAL ", border_color=TH().border, pad=(0, 1))


def build_intel_panel():
    s = S
    in_data = [s.inbound_spark[(s.spark_idx + k) % 20] for k in range(20)]
    out_data = [s.outbound_spark[(s.spark_idx + k) % 20] for k in range(20)]

    def gauge_line(label, val):
        bar = block_bar(val, 12)
        if val > 0.8:
            bc = (255, 60, 60)
        elif val > 0.5:
            bc = (255, 200, 60)
        else:
            bc = TH().primary
        return row(T(label).dim, T(bar).fg(bc), T(f"{int(val * 100):3d}%").dim, gap=1)

    return card(
        T("NETWORK TRAFFIC").fg(TH().bright).bold,
        sparkline(in_data, label="IN ", color=TH().primary, show_last=True),
        sparkline(out_data, label="OUT", color=TH().accent, show_last=True),
        T(""),
        T("PASSWORD CRACK").fg(TH().bright).bold,
        progress(s.crack_progress, "bcrypt", width=24, fill=TH().primary,
                 track=TH().border),
        T(""),
        T("NET TOPOLOGY").fg(TH().bright).bold,
        heatmap(s.heatmap_data, low=TH().border, high=TH().primary),
        T(""),
        T("SYSTEM LOAD").fg(TH().bright).bold,
        gauge_line("CPU", s.cpu_load),
        gauge_line("MEM", s.mem_load),
        gauge_line("NET", s.net_load),
        gauge_line("I/O", s.disk_io),
        title=" INTEL ", border_color=TH().border, pad=(0, 1),
    )


def build_hex_footer():
    s = S
    addr = "0x" + rand_hex_str(4) + ": "
    pairs = [s.hex_dump_line[i:i + 2] for i in range(0, 32, 2)]
    hex_part = " ".join(pairs)
    ascii_part = "|" + "".join(chr(randi(33, 126)) for _ in range(16)) + "|"

    def key(k, lab):
        return [T(k).fg(TH().bright).bold, T(lab).fg((120, 120, 140))]

    parts = [T(addr + hex_part + "  " + ascii_part).dim, spacer()]
    parts += key(" SPC", ":breach")
    parts += key("e", ":extract")
    parts += key("c", ":cover")
    parts += key("1-3", ":theme")
    parts += key("q", ":quit")
    return row(*parts, gap=0, pad=(0, 1), bg=(20, 20, 30))


def build_toasts():
    if not S.toasts:
        return None
    kindmap = {"error": "error", "warning": "warning", "success": "success"}
    return row(*[badge(msg, kind=kindmap[lvl]) for msg, lvl, _ in S.toasts], gap=1)


# ── App ──────────────────────────────────────────────────────────────────────

app = App("NEXUS://BREACH", inline=False, fps=15)
app.state(_t=0.0)


@app.on("1")
def _t1(s):
    themes.set(0)


@app.on("2")
def _t2(s):
    themes.set(1)


@app.on("3")
def _t3(s):
    themes.set(2)


@app.on("space")
def _breach(s):
    if not S.breaching:
        S.breaching = True
        S.breach_timer = 0.3
        S.breach_phase = 0
        S.toasts.append(["BREACH SEQUENCE INITIATED", "error", 3.5])


@app.on("e")
def _extract(s):
    if not S.extracting:
        S.extracting = True
        S.extract_timer = 3.0
        S.add_log(">>> DATA EXTRACTION STARTED <<<", 3)
        S.toasts.append(["EXTRACTING DATA", "warning", 3.5])


@app.on("c")
def _cover(s):
    if not S.covering:
        S.covering = True
        S.cover_timer = 2.0
        S.add_log(">>> COVERING TRACKS <<<", 2)
        S.toasts.append(["WIPING EVIDENCE", "warning", 3.5])


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 15.0)


@app.view
def view(s):
    main = row(
        grow(col(build_targets_panel())),
        grow(col(build_terminal_panel()), 2.0),
        grow(col(build_intel_panel())),
        gap=1,
    )
    layout = [build_header(), main]
    toasts = build_toasts()
    if toasts is not None:
        layout.append(toasts)
    layout.append(build_hex_footer())
    return col(*layout, gap=0)


if __name__ == "__main__":
    app.run()
