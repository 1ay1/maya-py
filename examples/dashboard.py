"""dashboard.py — NEXUS: Cyberpunk Mission Control Dashboard.

A faithful port of maya's `examples/dashboard.cpp`. A flashy animated data-viz
dashboard: a dual-channel waveform oscilloscope, a spectrum analyzer with
reflection + peak hold, a rotating radar sweep with braille trails and blips, a
live hex data waterfall, system gauges with sparkline history, dual-channel
network throughput, an animated spirograph, and a particle engine — all drawn
with braille/block glyphs through maya's native tuple-cell `row`.

  Keys: q/Esc quit · 1-4 theme · space pause · +/- speed
        p particles · g glitch · w waveform mode · r reset

    PYTHONPATH=src python examples/dashboard.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, box, col, component, row  # noqa: E402

PI = 3.14159265
TAU = 6.28318530

ROWS = 30  # fixed render height

random.seed(42)

# ── Themes: name, accent, dim, bg, hot, cold ─────────────────────────────────
THEMES = [
    ("CYBER", (0, 255, 200), (0, 80, 60), (5, 10, 15), (255, 0, 100), (0, 100, 255)),
    ("NEON", (255, 0, 255), (80, 0, 80), (10, 5, 15), (255, 255, 0), (0, 200, 255)),
    ("EMBER", (255, 120, 0), (80, 40, 0), (15, 8, 5), (255, 40, 40), (255, 200, 60)),
    ("ARCTIC", (100, 200, 255), (30, 60, 80), (5, 10, 18), (255, 255, 255), (0, 150, 200)),
]
TH_NAME, TH_ACCENT, TH_DIM, TH_BG, TH_HOT, TH_COLD = range(6)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def clampi(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def lerp8(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return int(a + (b - a) * t)


def col_lerp(a, b, t):
    return (lerp8(a[0], b[0], t), lerp8(a[1], b[1], t), lerp8(a[2], b[2], t))


def pack(rgb):
    return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]


# ── State ────────────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.theme = 0
        self.time = 0.0
        self.speed = 1.0
        self.paused = False
        self.frame = 0
        self.wave_mode = 0
        self.spectrum = [0.0] * 64
        self.spectrum_peak = [0.0] * 64
        self.spectrum_vel = [0.0] * 64
        self.radar_angle = 0.0
        self.blips = []  # [angle, dist, life, max_life]
        self.blip_timer = 0.0
        self.particles = []  # [x, y, vx, vy, life, max_life, r, g, b]
        self.hex_lines = []  # [addr, [16 bytes]]
        self.hex_timer = 0.0
        self.hex_addr = 0x00400000
        self.net_data = [0.0] * 120
        self.net_data2 = [0.0] * 120
        self.net_idx = 0
        self.net_timer = 0.0
        self.spiro_t = 0.0
        self.spiro_trail = []  # [x, y, pattern]
        self.gauges = [0.45, 0.72, 0.33, 0.88, 0.56, 0.21]
        self.gauge_targets = [0.65, 0.80, 0.40, 0.75, 0.60, 0.30]
        self.gauge_history = [[0.0] * 60 for _ in range(6)]
        self.gauge_hist_idx = 0
        self.gauge_hist_timer = 0.0
        self.glitch_timer = 0.0


W = World()


def TH():
    return THEMES[W.theme]


def spawn_burst(cx, cy, count):
    th = TH()
    for _ in range(count):
        angle = random.uniform(0, TAU)
        speed = random.uniform(5, 25)
        life = random.uniform(1, 3)
        blend = random.uniform(0, 1)
        r = lerp8(th[TH_ACCENT][0], th[TH_HOT][0], blend)
        g = lerp8(th[TH_ACCENT][1], th[TH_HOT][1], blend)
        b = lerp8(th[TH_ACCENT][2], th[TH_HOT][2], blend)
        W.particles.append([cx, cy, math.cos(angle) * speed,
                            math.sin(angle) * speed * 0.5, life, life, r, g, b])


def wave_sample(t):
    m = W.wave_mode
    gt = W.time
    if m == 0:
        return 0.8 * math.sin(t * 4 + gt * 3) * math.cos(t * 1.5 + gt * 0.7)
    if m == 1:
        return 0.7 * math.sin(t * 3 + gt * 2) + 0.3 * math.sin(t * 7 + gt * 5)
    if m == 2:
        return (0.6 * math.sin(t * 5 + gt * 4) + 0.3 * math.sin(t * 13 + gt * 7)
                + 0.1 * math.sin(t * 29 + gt * 11))
    phase = math.fmod(t * 2 + gt * 1.5, TAU)
    return math.exp(-phase * 2) * math.sin(phase * 8) * 0.9


def tick(dt):
    w = W
    if w.paused:
        return
    t = dt * w.speed
    w.time += t
    w.frame += 1

    # Spectrum
    for i in range(64):
        freq = 1.2 + i * 0.35
        target = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(w.time * freq + i * 0.5))
        envelope = 1.0 - i / 80.0
        envelope *= 0.6 + 0.4 * math.sin(w.time * 0.4 + i * 0.08)
        target *= clamp(envelope, 0.0, 1.0)
        beat = 0.5 + 0.5 * math.sin(w.time * 3.5)
        target *= 0.7 + 0.3 * beat
        target += 0.08 * math.sin(w.time * 11 + i * 1.7)
        target = clamp(target, 0.02, 1.0)
        w.spectrum[i] += (target - w.spectrum[i]) * 10.0 * t
        if w.spectrum[i] > w.spectrum_peak[i]:
            w.spectrum_peak[i] = w.spectrum[i]
            w.spectrum_vel[i] = 0.0
        else:
            w.spectrum_vel[i] += 1.5 * t
            w.spectrum_peak[i] -= w.spectrum_vel[i] * t
            if w.spectrum_peak[i] < w.spectrum[i]:
                w.spectrum_peak[i] = w.spectrum[i]

    # Radar
    w.radar_angle += 2.0 * t
    if w.radar_angle > TAU:
        w.radar_angle -= TAU
    w.blip_timer += t
    if w.blip_timer > 0.6:
        w.blip_timer = 0.0
        a = random.uniform(0, TAU)
        d = random.uniform(0.15, 0.92)
        life = random.uniform(3, 6)
        w.blips.append([a, d, life, life])
    for b in w.blips:
        b[2] -= t
    w.blips = [b for b in w.blips if b[2] > 0]

    # Particles
    for p in w.particles:
        p[3] += 12.0 * t
        p[0] += p[2] * t
        p[1] += p[3] * t
        p[4] -= t
    w.particles = [p for p in w.particles if p[4] > 0]

    # Hex waterfall
    w.hex_timer += t
    if w.hex_timer > 0.05:
        w.hex_timer = 0.0
        w.hex_lines.append([w.hex_addr, [random.randint(0, 255) for _ in range(16)]])
        w.hex_addr += 16
        if len(w.hex_lines) > 200:
            w.hex_lines.pop(0)

    # Network
    w.net_timer += t
    if w.net_timer > 0.08:
        w.net_timer = 0.0
        idx = w.net_idx % 120
        base = 0.35 + 0.25 * math.sin(w.time * 0.8)
        spike = 0.3 * (0.5 + 0.5 * math.sin(w.time * 4)) ** 3
        noise = 0.08 * math.sin(w.time * 17) + 0.05 * math.sin(w.time * 31)
        w.net_data[idx] = clamp(base + spike + noise, 0.02, 1.0)
        tx_base = 0.2 + 0.15 * math.sin(w.time * 1.1 + 1)
        tx_spike = 0.2 * (0.5 + 0.5 * math.sin(w.time * 3 + 2)) ** 3
        w.net_data2[idx] = clamp(tx_base + tx_spike + noise * 0.5, 0.02, 0.8)
        w.net_idx += 1

    # Spirograph
    w.spiro_t += 3.0 * t
    for sub in range(3):
        st = w.spiro_t + sub * 0.15
        R, r, d = 5.0, 3.0, 4.0
        sx = (R - r) * math.cos(st) + d * math.cos((R - r) / r * st)
        sy = (R - r) * math.sin(st) - d * math.sin((R - r) / r * st)
        w.spiro_trail.append([sx, sy, 0])
        R, r, d = 4.0, 1.5, 3.5
        sx = (R + r) * math.cos(st * 0.7) - d * math.cos((R + r) / r * st * 0.7)
        sy = (R + r) * math.sin(st * 0.7) - d * math.sin((R + r) / r * st * 0.7)
        w.spiro_trail.append([sx, sy, 1])
    while len(w.spiro_trail) > 3000:
        del w.spiro_trail[:6]

    # Gauges
    w.gauge_hist_timer += t
    if w.gauge_hist_timer > 0.2:
        w.gauge_hist_timer = 0.0
        for i in range(6):
            w.gauge_history[i][w.gauge_hist_idx % 60] = w.gauges[i]
        w.gauge_hist_idx += 1
    for i in range(6):
        w.gauges[i] += (w.gauge_targets[i] - w.gauges[i]) * 2.5 * t
        if abs(w.gauges[i] - w.gauge_targets[i]) < 0.02:
            w.gauge_targets[i] = random.uniform(0.1, 0.95)

    if w.glitch_timer > 0:
        w.glitch_timer -= t


# ── Cell buffer + braille drawing ────────────────────────────────────────────

class Cells:
    """A character grid with per-cell packed-int fg, rendered via row()."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.bg = bg
        self.ch = [[" "] * w for _ in range(h)]
        self.fg = [[None] * w for _ in range(h)]

    def set(self, x, y, ch, fg):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ch[y][x] = ch
            self.fg[y][x] = fg

    def get_char(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.ch[y][x]
        return " "

    def write(self, x, y, text, fg):
        for i, c in enumerate(text):
            self.set(x + i, y, c, fg)

    def to_element(self):
        bgp = pack(self.bg)
        out_rows = []
        for y in range(self.h):
            specs = []
            chr_row = self.ch[y]
            fg_row = self.fg[y]
            for x in range(self.w):
                c = chr_row[x]
                f = fg_row[x]
                if f is None:
                    specs.append((c, pack((120, 120, 120)), bgp))
                else:
                    specs.append((c, f, bgp))
            out_rows.append(row(*specs, gap=0))
        return col(*out_rows, gap=0)


BRAILLE_DOT = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]


def braille_plot(c, ox, oy, bw, bh, px, py, fg):
    bx = px // 2
    by = py // 4
    if bx < 0 or bx >= bw or by < 0 or by >= bh:
        return
    dcol = px % 2
    drow = py % 4
    dot_idx = (drow + dcol * 3) if drow < 3 else (6 + dcol)
    existing = c.get_char(ox + bx, oy + by)
    o = ord(existing)
    dots = (o - 0x2800) if 0x2800 <= o <= 0x28FF else 0
    dots |= BRAILLE_DOT[dot_idx]
    c.set(ox + bx, oy + by, chr(0x2800 + dots), fg)


def braille_line(c, ox, oy, bw, bh, x0, y0, x1, y1, fg):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    steps = max(dx, dy)
    if steps == 0:
        braille_plot(c, ox, oy, bw, bh, x0, y0, fg)
        return
    for i in range(steps + 1):
        px = x0 + (x1 - x0) * i // steps
        py = y0 + (y1 - y0) * i // steps
        braille_plot(c, ox, oy, bw, bh, px, py, fg)


VBLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def draw_box(c, x, y, w, h, fg, title=None):
    if w < 2 or h < 2:
        return
    c.set(x, y, "╭", fg)
    c.set(x + w - 1, y, "╮", fg)
    c.set(x, y + h - 1, "╰", fg)
    c.set(x + w - 1, y + h - 1, "╯", fg)
    for i in range(1, w - 1):
        c.set(x + i, y, "─", fg)
        c.set(x + i, y + h - 1, "─", fg)
    for j in range(1, h - 1):
        c.set(x, y + j, "│", fg)
        c.set(x + w - 1, y + j, "│", fg)
    if title:
        tx = x + 2
        c.set(tx - 1, y, "┤", fg)
        c.write(tx, y, title, fg)
        c.set(tx + len(title), y, "├", fg)


# ── Panels ───────────────────────────────────────────────────────────────────

def draw_waveform(c, x, y, w, h):
    th = TH()
    accent = pack(th[TH_ACCENT])
    grid_c = pack((max(5, th[TH_DIM][0] // 3), max(5, th[TH_DIM][1] // 3),
                   max(5, th[TH_DIM][2] // 3)))
    draw_box(c, x, y, w, h, pack(th[TH_DIM]), " WAVEFORM ")
    iw = w - 2
    ih = h - 2
    if iw < 8 or ih < 4:
        return
    ox = x + 1
    oy = y + 1
    bw = iw
    bh = ih
    pw = bw * 2
    ph = bh * 4
    center_py = ph // 2
    ch1 = []
    for px in range(pw):
        t1 = px / pw * TAU
        v1 = wave_sample(t1)
        ch1.append(clampi(int((0.5 - v1 * 0.45) * ph), 0, ph - 1))
    # area fill
    wave_fill = [pack(col_lerp(th[TH_ACCENT], th[TH_BG], i / 7)) for i in range(8)]
    for px in range(pw):
        py1 = ch1[px]
        top = min(py1, center_py)
        bot = max(py1, center_py)
        for fill_py in range(top, bot + 1):
            dist = abs(fill_py - py1) / max(1, bot - top)
            fi = clampi(int(dist * 7), 0, 7)
            braille_plot(c, ox, oy, bw, bh, px, fill_py, wave_fill[fi])
    # main line
    for px in range(pw):
        py1 = ch1[px]
        braille_plot(c, ox, oy, bw, bh, px, py1, accent)
        if py1 > 0:
            braille_plot(c, ox, oy, bw, bh, px, py1 - 1, accent)
        if py1 < ph - 1:
            braille_plot(c, ox, oy, bw, bh, px, py1 + 1, accent)

    # Mode + readout in title bar (right-aligned), matching the C++ original.
    modes = ["SINE", "LISSAJOUS", "NOISE", "HEARTBEAT"]
    amp = abs(wave_sample(W.time * 0.5))
    amp_buf = " %s A:%.2f " % (modes[W.wave_mode], amp)
    label_x = x + w - len(amp_buf) - 2
    c.write(max(ox, label_x), y, amp_buf, accent)


def draw_spectrum(c, x, y, w, h):
    th = TH()
    draw_box(c, x, y, w, h, pack(th[TH_DIM]), " SPECTRUM ")
    iw = w - 2
    ih = h - 2
    if iw < 4 or ih < 3:
        return
    ox = x + 1
    oy = y + 1
    num_bars = min(64, iw)
    spec_pal = [pack(_spectrum_color(i / 11, th)) for i in range(12)]
    hot = pack(th[TH_HOT])
    for i in range(num_bars):
        val = W.spectrum[i * 64 // num_bars]
        bar_h = max(1, int(val * ih))
        bx_start = ox + i * iw // num_bars
        bx_end = ox + (i + 1) * iw // num_bars
        draw_w = bx_end - bx_start
        if draw_w > 2:
            draw_w -= 1
        for j in range(ih):
            cy = oy + ih - 1 - j
            if j < bar_h:
                grad = j / ih
                si = clampi(int(grad * 11), 0, 11)
                if j == bar_h - 1:
                    ch, sty = "▀", spec_pal[min(si + 2, 11)]
                else:
                    ch, sty = "█", spec_pal[si]
                for k in range(draw_w):
                    c.set(bx_start + k, cy, ch, sty)
        peak_row = int((1 - W.spectrum_peak[i * 64 // num_bars]) * ih)
        if 0 <= peak_row < ih:
            for k in range(draw_w):
                c.set(bx_start + k, oy + peak_row, "━", hot)


def _spectrum_color(t, th):
    cold, accent, hot = th[TH_COLD], th[TH_ACCENT], th[TH_HOT]
    if t < 0.3:
        return col_lerp(cold, accent, t / 0.3)
    if t < 0.65:
        return col_lerp(accent, hot, (t - 0.3) / 0.35)
    return col_lerp(hot, (255, 240, 255), (t - 0.65) / 0.35)


def draw_radar(c, x, y, w, h):
    th = TH()
    dim = pack(th[TH_DIM])
    accent = pack(th[TH_ACCENT])
    hot = pack(th[TH_HOT])
    grid_c = pack((max(5, th[TH_DIM][0] // 3), max(5, th[TH_DIM][1] // 3),
                   max(5, th[TH_DIM][2] // 3)))
    draw_box(c, x, y, w, h, dim, " RADAR ")
    iw = w - 2
    ih = h - 2
    if iw < 8 or ih < 6:
        return
    ox = x + 1
    oy = y + 1
    bw = iw
    bh = ih
    pw = bw * 2
    ph = bh * 4
    cpx = pw // 2
    cpy = ph // 2
    rx = pw // 2 - 2
    ry = ph // 2 - 2
    radar_pal = [pack(col_lerp(th[TH_ACCENT], th[TH_BG], i / 9)) for i in range(10)]
    # rings
    for ring in range(1, 4):
        frac = ring / 3
        steps = max(2, int(max(rx, ry) * frac * 4))
        for s in range(steps):
            a = TAU * s / steps
            braille_plot(c, ox, oy, bw, bh,
                         int(cpx + math.cos(a) * rx * frac),
                         int(cpy + math.sin(a) * ry * frac), dim)
    # crosshairs
    for px in range(pw):
        braille_plot(c, ox, oy, bw, bh, px, cpy, grid_c)
    for py in range(ph):
        braille_plot(c, ox, oy, bw, bh, cpx, py, grid_c)
    # sweep
    for trail in range(10):
        a_center = W.radar_angle - trail * 0.06
        si = min(trail, 9)
        line_steps = max(rx, ry)
        for d in range(2, line_steps):
            frac = d / line_steps
            braille_plot(c, ox, oy, bw, bh,
                         int(cpx + math.cos(a_center) * rx * frac),
                         int(cpy + math.sin(a_center) * ry * frac), radar_pal[si])
    # blips
    for angle, dist, life, max_life in W.blips:
        intensity = clamp(life / max_life, 0, 1)
        bpx = int(cpx + math.cos(angle) * dist * rx)
        bpy = int(cpy + math.sin(angle) * dist * ry)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                fg = hot if (dx == 0 and dy == 0) else (accent if intensity > 0.5 else dim)
                braille_plot(c, ox, oy, bw, bh, bpx + dx, bpy + dy, fg)

    # Cardinal labels + center reticle (cell-space, like the C++ original).
    cx_r = ox + iw // 2
    cy_r = oy + ih // 2
    c.write(cx_r, oy, "N", accent)
    c.write(cx_r, oy + ih - 1, "S", accent)
    c.write(ox, cy_r, "W", accent)
    c.write(ox + iw - 1, cy_r, "E", accent)
    c.set(cx_r, cy_r, "+", pack(th[TH_ACCENT]))

    # Blip count in title bar (right-aligned).
    count_buf = " %dT " % len(W.blips)
    data_c = pack((190, 190, 200))
    c.write(x + w - len(count_buf) - 2, y, count_buf, data_c)


def draw_hex(c, x, y, w, h):
    th = TH()
    dim = pack(th[TH_DIM])
    accent = pack(th[TH_ACCENT])
    vdim = pack((th[TH_DIM][0] // 2, th[TH_DIM][1] // 2, th[TH_DIM][2] // 2))
    hex_addr_c = pack((th[TH_ACCENT][0] // 2, th[TH_ACCENT][1] // 2, th[TH_ACCENT][2] // 2))
    heat_pal = [pack(_spectrum_color(i / 7, th)) for i in range(8)]
    draw_box(c, x, y, w, h, dim, " DATA STREAM ")
    iw = w - 2
    ih = h - 2
    if iw < 20 or ih < 2:
        return
    c.write(x + 1, y + 1, "ADDRESS", dim)
    hx = x + 10
    for i in range(16):
        if hx + 2 >= x + w - 1:
            break
        c.write(hx, y + 1, f"{i:02X}", vdim)
        hx += 3
        if i == 7:
            hx += 1
    data_h = ih - 1
    size = len(W.hex_lines)
    start = max(0, size - data_h)
    for r in range(data_h):
        if start + r >= size:
            break
        addr, byts = W.hex_lines[start + r]
        cy = y + 2 + r
        age = (size - start - r - 1) / max(1, data_h)
        freshness = 1 - age
        c.write(x + 1, cy, f"{addr & 0xFFFFFFFF:08X}", accent if freshness > 0.9 else hex_addr_c)
        c.set(x + 9, cy, ":", vdim)
        hex_x = x + 10
        for i, val in enumerate(byts):
            if hex_x + 2 >= x + w - 1:
                break
            heat = clampi(val // 32, 0, 7)
            sty = heat_pal[heat] if freshness > 0.85 else (dim if freshness > 0.4 else vdim)
            c.write(hex_x, cy, f"{val:02X}", sty)
            hex_x += 3
            if i == 7:
                hex_x += 1


def draw_gauges(c, x, y, w, h):
    th = TH()
    dim = pack(th[TH_DIM])
    accent = pack(th[TH_ACCENT])
    hot = pack(th[TH_HOT])
    cold = pack(th[TH_COLD])
    vdim = pack((th[TH_DIM][0] // 2, th[TH_DIM][1] // 2, th[TH_DIM][2] // 2))
    label_c = pack((160, 160, 170))
    bar_pal = []
    for i in range(8):
        t = i / 7
        if t < 0.5:
            bar_pal.append(pack(col_lerp(th[TH_COLD], th[TH_ACCENT], t * 2)))
        else:
            bar_pal.append(pack(col_lerp(th[TH_ACCENT], th[TH_HOT], (t - 0.5) * 2)))
    labels = ["CPU", "GPU", "MEM", "NET", "DSK", "PWR"]
    draw_box(c, x, y, w, h, dim, " SYSTEMS ")
    iw = w - 2
    ih = h - 2
    if iw < 12 or ih < 1:
        return
    row_h = 2
    rows = min(6, ih // row_h)
    if rows < 1:
        rows = min(6, ih)
        row_h = 1
    bar_w = iw - 9
    if bar_w < 4:
        return
    for i in range(rows):
        cy = y + 1 + i * row_h
        val = W.gauges[i]
        c.write(x + 1, cy, labels[i], hot if val > 0.8 else label_c)
        filled_full = int(val * bar_w)
        for j in range(bar_w):
            cx = x + 5 + j
            if j < filled_full:
                grad = j / bar_w
                si = clampi(int(grad * 7), 0, 7)
                c.set(cx, cy, "█", bar_pal[si])
            elif j == filled_full:
                c.set(cx, cy, "▌", hot if val > 0.85 else (accent if val > 0.6 else cold))
            else:
                c.set(cx, cy, "░", vdim)
        c.write(x + w - 5, cy, f"{int(val * 100):3d}%",
                hot if val > 0.8 else (accent if val > 0.5 else cold))
        if row_h >= 2 and cy + 1 < y + h - 1:
            spark_w = min(bar_w, 60)
            for j in range(spark_w):
                hi = (W.gauge_hist_idx - spark_w + j + 60) % 60
                hv = W.gauge_history[i][hi]
                bi = clampi(int(hv * 7), 0, 7)
                c.set(x + 5 + j, cy + 1, VBLOCKS[bi + 1], dim)


def draw_network(c, x, y, w, h):
    th = TH()
    dim = pack(th[TH_DIM])
    accent = pack(th[TH_ACCENT])
    hot = pack(th[TH_HOT])
    grid_c = pack((max(5, th[TH_DIM][0] // 3), max(5, th[TH_DIM][1] // 3),
                   max(5, th[TH_DIM][2] // 3)))
    net_fill = [pack(col_lerp(th[TH_ACCENT], th[TH_BG], i / 7)) for i in range(8)]
    draw_box(c, x, y, w, h, dim, " NETWORK ")
    iw = w - 2
    ih = h - 2
    if iw < 8 or ih < 4:
        return
    ox = x + 1
    oy = y + 1
    bw = iw
    bh = ih
    pw = bw * 2
    ph = bh * 4
    samples = min(pw, 120)

    def get_py(data, i):
        idx = (W.net_idx - samples + i + 120) % 120
        return clampi(int((1 - data[idx]) * (ph - 1)), 0, ph - 1)

    for i in range(samples):
        top = get_py(W.net_data, i)
        bpx = i * pw // samples
        for py in range(top, ph):
            depth = (py - top) / max(1, ph - top)
            fi = clampi(int(depth * 7), 0, 7)
            braille_plot(c, ox, oy, bw, bh, bpx, py, net_fill[fi])
        braille_plot(c, ox, oy, bw, bh, bpx, top, accent)
        if top > 0:
            braille_plot(c, ox, oy, bw, bh, bpx, top - 1, accent)
        if top < ph - 1:
            braille_plot(c, ox, oy, bw, bh, bpx, top + 1, accent)
        top2 = get_py(W.net_data2, i)
        braille_plot(c, ox, oy, bw, bh, bpx, top2, hot)
        if top2 > 0:
            braille_plot(c, ox, oy, bw, bh, bpx, top2 - 1, hot)


def draw_spirograph(c, x, y, w, h):
    th = TH()
    dim = pack(th[TH_DIM])
    braille_pal = []
    for i in range(8):
        t = i / 7
        if t < 0.5:
            braille_pal.append(pack(col_lerp(th[TH_BG], th[TH_ACCENT], t * 2)))
        else:
            braille_pal.append(pack(col_lerp(th[TH_ACCENT], th[TH_HOT], (t - 0.5) * 2)))
    draw_box(c, x, y, w, h, dim, " SIGNAL ")
    iw = w - 2
    ih = h - 2
    if iw < 6 or ih < 4:
        return
    ox = x + 1
    oy = y + 1
    bw = iw
    bh = ih
    pw = bw * 2
    ph = bh * 4
    cpx = pw // 2
    cpy = ph // 2
    scale = min(pw // 20, ph // 20) or 1
    prev = [(-999, -999), (-999, -999)]
    n = len(W.spiro_trail)
    for i, (sx, sy, pat) in enumerate(W.spiro_trail):
        ppx = int(cpx + sx * scale)
        ppy = int(cpy + sy * scale)
        age = i / n if n else 0
        si = clampi(int(age * 7), 0, 7)
        if pat == 1:
            si = clampi(7 - si, 0, 7)
        pp = prev[pat]
        if pp[0] != -999:
            dx = abs(ppx - pp[0])
            dy = abs(ppy - pp[1])
            if dx < pw / 3 and dy < ph / 3:
                braille_line(c, ox, oy, bw, bh, pp[0], pp[1], ppx, ppy, braille_pal[si])
            else:
                braille_plot(c, ox, oy, bw, bh, ppx, ppy, braille_pal[si])
        else:
            braille_plot(c, ox, oy, bw, bh, ppx, ppy, braille_pal[si])
        prev[pat] = (ppx, ppy)


def draw_particles(c, w, h):
    th = TH()
    for p in W.particles:
        px = int(p[0])
        py = int(p[1])
        if 0 <= px < w and 0 <= py < h:
            age = 1 - p[4] / p[5]
            ch = "*" if age < 0.2 else ("o" if age < 0.5 else ".")
            fade = clamp(1 - age, 0, 1)
            c.set(px, py, ch, pack((int(p[6] * fade), int(p[7] * fade), int(p[8] * fade))))


def draw_status(c, w, h):
    th = TH()
    y = h - 1
    accent = pack(th[TH_ACCENT])
    bright = accent
    dim = pack(th[TH_DIM])
    vdim = pack((th[TH_DIM][0] // 2, th[TH_DIM][1] // 2, th[TH_DIM][2] // 2))
    data_c = pack((190, 190, 200))
    bg = pack(th[TH_BG])
    for x in range(w):
        c.set(x, y, " ", bg)
    c.write(1, y, "NEXUS", bright)
    c.set(7, y, "│", dim)
    chip_x = 9
    for i in range(4):
        name = THEMES[i][TH_NAME]
        active = i == W.theme
        c.set(chip_x, y, str(1 + i), bright if active else vdim)
        c.set(chip_x + 1, y, ":", vdim)
        c.write(chip_x + 2, y, name, accent if active else vdim)
        chip_x += 2 + len(name) + 1
    c.set(chip_x, y, "│", dim)
    wave_names = ["SIN", "LIS", "NOI", "HRT"]
    c.write(chip_x + 2, y, wave_names[W.wave_mode], accent)
    spinners = ["|", "/", "-", "\\"]
    live_x = chip_x + 6
    c.set(live_x, y, "│", dim)
    live_x += 2
    c.write(live_x, y, "||" if W.paused else spinners[(W.frame // 4) % 4],
            pack(th[TH_HOT]) if W.paused else accent)
    c.write(live_x + 3, y, "PAUSED" if W.paused else "LIVE",
            pack(th[TH_HOT]) if W.paused else data_c)
    fps_est = W.frame / W.time if W.time > 1 else 0
    stats = f"{int(fps_est)}fps {int(W.time)}s {len(W.particles)}p {len(W.blips)}T"
    stats_x = w // 2
    c.set(stats_x - 1, y, "│", dim)
    c.write(stats_x + 1, y, stats, data_c)


# ── App ──────────────────────────────────────────────────────────────────────

app = App("NEXUS", inline=True, fps=30)
app.state(_t=0.0)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on("space")
def _pause(s):
    W.paused = not W.paused


@app.on("w")
def _wave(s):
    W.wave_mode = (W.wave_mode + 1) % 4


@app.on("+", "=")
def _faster(s):
    W.speed = min(W.speed + 0.25, 4.0)


@app.on("-")
def _slower(s):
    W.speed = max(W.speed - 0.25, 0.25)


@app.on("g")
def _glitch(s):
    W.glitch_timer = 0.5


@app.on("r")
def _reset(s):
    W.time = 0.0
    W.frame = 0
    W.particles.clear()
    W.hex_lines.clear()
    W.blips.clear()
    W.spiro_trail.clear()
    W.hex_addr = 0x00400000
    W.net_idx = 0
    for i in range(6):
        W.gauges[i] = 0.5
        W.gauge_targets[i] = 0.5


@app.on("p")
def _particles(s):
    spawn_burst(40, 15, 50)


@app.on("1")
def _t1(s):
    W.theme = 0


@app.on("2")
def _t2(s):
    W.theme = 1


@app.on("3")
def _t3(s):
    W.theme = 2


@app.on("4")
def _t4(s):
    W.theme = 3


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 30.0)


def _screen(w, _h):
    h = ROWS
    if w < 40 or h < 8:
        return col()
    c = Cells(w, h, TH()[TH_BG])
    status_h = 1
    avail_h = h - 1
    top_h = max(6, avail_h * 35 // 100)
    mid_h = max(6, avail_h * 35 // 100)
    bot_h = max(4, avail_h - top_h - mid_h)
    wave_w = w * 60 // 100
    draw_waveform(c, 0, 0, wave_w, top_h)
    draw_radar(c, wave_w, 0, w - wave_w, top_h)
    spec_w = w * 40 // 100
    gauge_w = w * 30 // 100
    spiro_w = w - spec_w - gauge_w
    draw_spectrum(c, 0, top_h, spec_w, mid_h)
    draw_gauges(c, spec_w, top_h, gauge_w, mid_h)
    draw_spirograph(c, spec_w + gauge_w, top_h, spiro_w, mid_h)
    hex_w = w * 50 // 100
    draw_hex(c, 0, top_h + mid_h, hex_w, bot_h)
    draw_network(c, hex_w, top_h + mid_h, w - hex_w, bot_h)
    draw_particles(c, w, h)
    draw_status(c, w, h)
    return c.to_element()


@app.view
def view(s):
    return box(component(_screen, height=ROWS), height=ROWS)


if __name__ == "__main__":
    app.run()
