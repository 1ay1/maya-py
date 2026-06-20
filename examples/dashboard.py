"""dashboard.py — NEXUS: Cyberpunk Mission Control Dashboard.

A faithful port of maya's `examples/dashboard.cpp`: a dual-channel waveform
oscilloscope, a spectrum analyzer with reflection + peak hold, a rotating radar
sweep with braille trails and blips, a live hex data waterfall, system gauges
with sparkline history, dual-channel network throughput, an animated
spirograph, and a particle engine.

Every panel is drawn on maya-py's native `Surface` — a braille/char grid that
runs entirely in C++. A `Pen` scoped to each panel's interior plots curves,
lines and rings in pixel-space; `ramp()` builds the colour gradients. No
per-pixel Python, no hand-rolled software renderer.

  Keys: q/Esc quit · 1-4 theme · space pause · +/- speed
        p particles · g glitch · w waveform mode · r reset

    PYTHONPATH=src python examples/dashboard.py
"""

from __future__ import annotations

import math
import random

import _bootstrap  # noqa: F401,E402

from maya_py import (App, box, col, component, Surface, ramp, rgb_lerp,  # noqa: E402
                     Theme, ThemeSet, clamp)

PI = 3.14159265
TAU = 6.28318530

ROWS = 30  # fixed render height

random.seed(42)

# ── Themes: named colour roles, cycled with keys 1-4 ──────────────────────
themes = ThemeSet(
    Theme("CYBER", accent=(0, 255, 200), dim=(0, 80, 60), bg=(5, 10, 15),
          hot=(255, 0, 100), cold=(0, 100, 255)),
    Theme("NEON", accent=(255, 0, 255), dim=(80, 0, 80), bg=(10, 5, 15),
          hot=(255, 255, 0), cold=(0, 200, 255)),
    Theme("EMBER", accent=(255, 120, 0), dim=(80, 40, 0), bg=(15, 8, 5),
          hot=(255, 40, 40), cold=(255, 200, 60)),
    Theme("ARCTIC", accent=(100, 200, 255), dim=(30, 60, 80), bg=(5, 10, 18),
          hot=(255, 255, 255), cold=(0, 150, 200)),
)


def lerp8(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return int(a + (b - a) * t)


def clampi(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


VBLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


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
    return themes[W.theme]


def spawn_burst(cx, cy, count):
    th = TH()
    for _ in range(count):
        angle = random.uniform(0, TAU)
        speed = random.uniform(5, 25)
        life = random.uniform(1, 3)
        blend = random.uniform(0, 1)
        r = lerp8(th.accent[0], th.hot[0], blend)
        g = lerp8(th.accent[1], th.hot[1], blend)
        b = lerp8(th.accent[2], th.hot[2], blend)
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


# ── Panels — each draws onto the shared Surface ──────────────────────────────

def _spectrum_stops(th):
    """The accent→hot→white spectrum ramp shared by spectrum + hex heat."""
    return [th.cold, th.accent, th.hot, (255, 240, 255)]


def draw_waveform(s, x, y, w, h):
    th = TH()
    pen = s.panel(x, y, w, h, fg=th.dim, title=" WAVEFORM ")
    if pen.pw < 16 or pen.ph < 16:
        return
    fill = ramp([th.accent, th.bg], 8)
    ph1 = pen.ph - 1
    ys = [int(clamp(0.5 - wave_sample(px / pen.pw * TAU) * 0.45, 0, 1) * ph1)
          for px in range(pen.pw)]
    pen.fill_curve_raw(ys, ph1 // 2, ramp_fg=fill,
                       line_fg=th.accent, thick=2)

    modes = ["SINE", "LISSAJOUS", "NOISE", "HEARTBEAT"]
    amp = abs(wave_sample(W.time * 0.5))
    buf = " %s A:%.2f " % (modes[W.wave_mode], amp)
    s.write(max(x + 1, x + w - len(buf) - 2), y, buf, fg=th.accent)


def draw_spectrum(s, x, y, w, h):
    th = TH()
    s.box(x, y, w, h, fg=th.dim, title=" SPECTRUM ")
    iw, ih = w - 2, h - 2
    if iw < 4 or ih < 3:
        return
    ox, oy = x + 1, y + 1
    num_bars = min(64, iw)
    pal = ramp([th.cold, th.accent, th.hot, (255, 240, 255)], 12)
    hot = th.hot
    for i in range(num_bars):
        val = W.spectrum[i * 64 // num_bars]
        bar_h = max(1, int(val * ih))
        bx0 = ox + i * iw // num_bars
        bx1 = ox + (i + 1) * iw // num_bars
        draw_w = bx1 - bx0
        if draw_w > 2:
            draw_w -= 1
        for j in range(ih):
            cy = oy + ih - 1 - j
            if j < bar_h:
                si = clampi(int(j / ih * 11), 0, 11)
                ch, fg = ("▀", pal[min(si + 2, 11)]) if j == bar_h - 1 else ("█", pal[si])
                for k in range(draw_w):
                    s.set_fg(bx0 + k, cy, ch, fg)
        peak = int((1 - W.spectrum_peak[i * 64 // num_bars]) * ih)
        if 0 <= peak < ih:
            for k in range(draw_w):
                s.set(bx0 + k, oy + peak, "━", fg=hot)


def draw_radar(s, x, y, w, h):
    th = TH()
    dim, accent, hot = th.dim, th.accent, th.hot
    grid_c = (max(5, dim[0] // 3), max(5, dim[1] // 3), max(5, dim[2] // 3))
    pen = s.panel(x, y, w, h, fg=dim, title=" RADAR ")
    if pen.pw < 16 or pen.ph < 24:
        return
    cpx, cpy = pen.pw // 2, pen.ph // 2
    rx, ry = pen.pw // 2 - 2, pen.ph // 2 - 2
    trail = ramp([th.accent, th.bg], 10)
    # rings
    for ring in range(1, 4):
        pen.ring(cpx, cpy, rx * ring / 3, ry * ring / 3, fg=dim)
    # crosshairs
    pen.line(0, cpy, pen.pw - 1, cpy, fg=grid_c)
    pen.line(cpx, 0, cpx, pen.ph - 1, fg=grid_c)
    # sweep — 10 trailing beams, one native ray each
    far = max(rx, ry)
    for k in range(10):
        a = W.radar_angle - k * 0.06
        pen.ray(cpx, cpy, a, rx, ry, near=0, far=far, fg=trail[min(k, 9)])
    # blips — batch each 3x3 cluster, grouped by colour
    hot_pts, acc_pts, dim_pts = [], [], []
    for angle, dist, life, max_life in W.blips:
        intensity = clamp(life / max_life, 0, 1)
        bpx = int(cpx + math.cos(angle) * dist * rx)
        bpy = int(cpy + math.sin(angle) * dist * ry)
        side = acc_pts if intensity > 0.5 else dim_pts
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                (hot_pts if dx == 0 and dy == 0 else side).extend((bpx + dx, bpy + dy))
    pen.points(dim_pts, fg=dim)
    pen.points(acc_pts, fg=accent)
    pen.points(hot_pts, fg=hot)
    # cardinal labels + reticle
    iw, ih = w - 2, h - 2
    cx_r, cy_r = x + 1 + iw // 2, y + 1 + ih // 2
    s.write(cx_r, y + 1, "N", fg=accent)
    s.write(cx_r, y + ih, "S", fg=accent)
    s.write(x + 1, cy_r, "W", fg=accent)
    s.write(x + iw, cy_r, "E", fg=accent)
    s.set(cx_r, cy_r, "+", fg=accent)
    buf = " %dT " % len(W.blips)
    s.write(x + w - len(buf) - 2, y, buf, fg=(190, 190, 200))


def draw_hex(s, x, y, w, h):
    th = TH()
    dim, accent = th.dim, th.accent
    vdim = (dim[0] // 2, dim[1] // 2, dim[2] // 2)
    addr_c = (accent[0] // 2, accent[1] // 2, accent[2] // 2)
    heat = ramp([th.cold, th.accent, th.hot, (255, 240, 255)], 8)
    s.box(x, y, w, h, fg=dim, title=" DATA STREAM ")
    iw, ih = w - 2, h - 2
    if iw < 20 or ih < 2:
        return
    s.write(x + 1, y + 1, "ADDRESS", fg=dim)
    hx = x + 10
    for i in range(16):
        if hx + 2 >= x + w - 1:
            break
        s.write(hx, y + 1, "%02X" % i, fg=vdim)
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
        fresh = 1 - (size - start - r - 1) / max(1, data_h)
        s.write(x + 1, cy, "%08X" % (addr & 0xFFFFFFFF),
                fg=accent if fresh > 0.9 else addr_c)
        s.set(x + 9, cy, ":", fg=vdim)
        hex_x = x + 10
        for i, val in enumerate(byts):
            if hex_x + 2 >= x + w - 1:
                break
            if fresh > 0.85:
                fg = heat[clampi(val // 32, 0, 7)]
                s.set_fg(hex_x, cy, "%X" % (val >> 4), fg)
                s.set_fg(hex_x + 1, cy, "%X" % (val & 0xF), fg)
            else:
                fg = dim if fresh > 0.4 else vdim
                s.write(hex_x, cy, "%02X" % val, fg=fg)
            hex_x += 3
            if i == 7:
                hex_x += 1


def draw_gauges(s, x, y, w, h):
    th = TH()
    dim, accent, hot, cold = th.dim, th.accent, th.hot, th.cold
    vdim = (dim[0] // 2, dim[1] // 2, dim[2] // 2)
    label_c = (160, 160, 170)
    bar = ramp([th.cold, th.accent, th.hot], 8)
    labels = ["CPU", "GPU", "MEM", "NET", "DSK", "PWR"]
    s.box(x, y, w, h, fg=dim, title=" SYSTEMS ")
    iw, ih = w - 2, h - 2
    if iw < 12 or ih < 1:
        return
    row_h = 2
    rows = min(6, ih // row_h)
    if rows < 1:
        rows, row_h = min(6, ih), 1
    bar_w = iw - 9
    if bar_w < 4:
        return
    for i in range(rows):
        cy = y + 1 + i * row_h
        val = W.gauges[i]
        s.write(x + 1, cy, labels[i], fg=hot if val > 0.8 else label_c)
        filled = int(val * bar_w)
        for j in range(bar_w):
            cx = x + 5 + j
            if j < filled:
                s.set_fg(cx, cy, "█", bar[clampi(int(j / bar_w * 7), 0, 7)])
            elif j == filled:
                s.set(cx, cy, "▌", fg=hot if val > 0.85 else (accent if val > 0.6 else cold))
            else:
                s.set(cx, cy, "░", fg=vdim)
        s.write(x + w - 5, cy, "%3d%%" % int(val * 100),
                fg=hot if val > 0.8 else (accent if val > 0.5 else cold))
        if row_h >= 2 and cy + 1 < y + h - 1:
            spark_w = min(bar_w, 60)
            for j in range(spark_w):
                hi = (W.gauge_hist_idx - spark_w + j + 60) % 60
                bi = clampi(int(W.gauge_history[i][hi] * 7), 0, 7)
                s.set(x + 5 + j, cy + 1, VBLOCKS[bi + 1], fg=dim)


def draw_network(s, x, y, w, h):
    th = TH()
    dim, accent, hot = th.dim, th.accent, th.hot
    pen = s.panel(x, y, w, h, fg=dim, title=" NETWORK ")
    if pen.pw < 16 or pen.ph < 16:
        return
    fill = ramp([th.accent, th.bg], 8)
    samples = min(pen.pw, 120)
    ph1 = pen.ph - 1

    def sample(data):
        ys = []
        base = W.net_idx - samples
        for i in range(samples):
            idx = (base + i + 120) % 120
            ys.append(clampi(int((1 - data[idx]) * ph1), 0, ph1))
        return ys

    # RX: shaded area fill + accent line, one native call
    pen.fill_curve_raw(sample(W.net_data), ph1, ramp_fg=fill,
                       line_fg=accent, thick=2)
    # TX: just the hot line as a thin polyline
    ys2 = sample(W.net_data2)
    pts = []
    for i, y in enumerate(ys2):
        pts.extend((i, y))
    pen.path(pts, fg=hot)


def draw_spirograph(s, x, y, w, h):
    th = TH()
    pen = s.panel(x, y, w, h, fg=th.dim, title=" SIGNAL ")
    if pen.pw < 12 or pen.ph < 16:
        return
    pal = ramp([th.bg, th.accent, th.hot], 8)
    cpx, cpy = pen.pw // 2, pen.ph // 2
    scale = min(pen.pw // 20, pen.ph // 20) or 1
    prev = [(-999, -999), (-999, -999)]
    n = len(W.spiro_trail)
    for i, (sx, sy, pat) in enumerate(W.spiro_trail):
        ppx, ppy = int(cpx + sx * scale), int(cpy + sy * scale)
        si = clampi(int((i / n if n else 0) * 7), 0, 7)
        if pat == 1:
            si = clampi(7 - si, 0, 7)
        pp = prev[pat]
        if pp[0] != -999:
            if abs(ppx - pp[0]) < pen.pw / 3 and abs(ppy - pp[1]) < pen.ph / 3:
                pen.line(pp[0], pp[1], ppx, ppy, fg=pal[si])
            else:
                pen.plot_fg(ppx, ppy, pal[si])
        else:
            pen.plot_fg(ppx, ppy, pal[si])
        prev[pat] = (ppx, ppy)


def draw_particles(s, w, h):
    for p in W.particles:
        px, py = int(p[0]), int(p[1])
        if 0 <= px < w and 0 <= py < h:
            age = 1 - p[4] / p[5]
            ch = "*" if age < 0.2 else ("o" if age < 0.5 else ".")
            fade = clamp(1 - age, 0, 1)
            s.set(px, py, ch, fg=(int(p[6] * fade), int(p[7] * fade), int(p[8] * fade)))


def draw_status(s, w, h):
    th = TH()
    y = h - 1
    accent, dim, hot, bg = th.accent, th.dim, th.hot, th.bg
    vdim = (dim[0] // 2, dim[1] // 2, dim[2] // 2)
    data_c = (190, 190, 200)
    s.rect(0, y, w, 1, ch=" ", fg=bg)
    s.write(1, y, "NEXUS", fg=accent)
    s.set(7, y, "│", fg=dim)
    chip_x = 9
    for i in range(4):
        name = themes[i].name
        active = i == W.theme
        s.set(chip_x, y, str(1 + i), fg=accent if active else vdim)
        s.set(chip_x + 1, y, ":", fg=vdim)
        s.write(chip_x + 2, y, name, fg=accent if active else vdim)
        chip_x += 2 + len(name) + 1
    s.set(chip_x, y, "│", fg=dim)
    wave_names = ["SIN", "LIS", "NOI", "HRT"]
    s.write(chip_x + 2, y, wave_names[W.wave_mode], fg=accent)
    spinners = ["|", "/", "-", "\\"]
    live_x = chip_x + 6
    s.set(live_x, y, "│", fg=dim)
    s.write(live_x + 2, y, "||" if W.paused else spinners[(W.frame // 4) % 4],
            fg=hot if W.paused else accent)
    s.write(live_x + 5, y, "PAUSED" if W.paused else "LIVE",
            fg=hot if W.paused else data_c)
    fps_est = W.frame / W.time if W.time > 1 else 0
    stats = "%dfps %ds %dp %dT" % (int(fps_est), int(W.time),
                                   len(W.particles), len(W.blips))
    stats_x = w // 2
    s.set(stats_x - 1, y, "│", fg=dim)
    s.write(stats_x + 1, y, stats, fg=data_c)


# ── App ──────────────────────────────────────────────────────────────────────

app = App.inline("NEXUS", fps=30)
app.state(_t=0.0)


app.quit_on("q", "esc")


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


app.simulate(tick)


def _screen(w, _h):
    h = ROWS
    if w < 40 or h < 8:
        return col()
    s = Surface(w, h, bg=TH().bg)
    avail_h = h - 1
    top_h = max(6, avail_h * 35 // 100)
    mid_h = max(6, avail_h * 35 // 100)
    bot_h = max(4, avail_h - top_h - mid_h)
    wave_w = w * 60 // 100
    draw_waveform(s, 0, 0, wave_w, top_h)
    draw_radar(s, wave_w, 0, w - wave_w, top_h)
    spec_w = w * 40 // 100
    gauge_w = w * 30 // 100
    spiro_w = w - spec_w - gauge_w
    draw_spectrum(s, 0, top_h, spec_w, mid_h)
    draw_gauges(s, spec_w, top_h, gauge_w, mid_h)
    draw_spirograph(s, spec_w + gauge_w, top_h, spiro_w, mid_h)
    hex_w = w * 50 // 100
    draw_hex(s, 0, top_h + mid_h, hex_w, bot_h)
    draw_network(s, hex_w, top_h + mid_h, w - hex_w, bot_h)
    draw_particles(s, w, h)
    draw_status(s, w, h)
    return s.element()


@app.view
def view(s):
    return box(component(_screen, height=ROWS), height=ROWS)


if __name__ == "__main__":
    app.run()
