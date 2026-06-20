"""spectrum.py — Audio Spectrum Analyzer.

A faithful port of maya's `examples/spectrum.cpp`. A simulated real-time
spectrum analyzer with four visualization modes (bars, mirror, circular,
waterfall). Audio is synthesized from layered sine oscillators that evolve over
time, with beat detection driving a screen flash. Bars/mirror/waterfall render
through maya's native tuple-cell `row`; the circular mode uses the half-block
surface.

  Keys: 1 BARS · 2 MIRROR · 3 CIRCULAR · 4 WATERFALL
        space change track · q/Esc quit

    PYTHONPATH=src python examples/spectrum.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, box, col, component, row, halfblock, clamp  # noqa: E402

NUM_BARS = 64
NUM_WATERFALL = 128
PEAK_DECAY = 0.012
BAR_SMOOTH = 0.25
TWO_PI = 6.28318530717959

ROWS = 24  # fixed render height (fullscreen sentinel can't be used for grids)

MODE_NAMES = ["BARS", "MIRROR", "CIRCULAR", "WATERFALL"]
TRACK_NAMES = ["EDM", "AMBIENT", "ROCK", "SYNTHWAVE", "GLITCH"]

clampi = clamp


# ── Color gradients ──────────────────────────────────────────────────────────

def gradient_color(t):
    t = clamp(t, 0.0, 1.0)
    if t < 0.25:
        s = t / 0.25
        return (0, int(s * 200), int(200 + s * 55))
    if t < 0.5:
        s = (t - 0.25) / 0.25
        return (0, int(200 + s * 55), int(255 - s * 255))
    if t < 0.75:
        s = (t - 0.5) / 0.25
        return (int(s * 255), int(255 - s * 30), 0)
    s = (t - 0.75) / 0.25
    return (255, int(225 - s * 225), 0)


def waterfall_color(t):
    t = clamp(t, 0.0, 1.0)
    if t < 0.2:
        s = t / 0.2
        return (0, 0, int(s * 180))
    if t < 0.4:
        s = (t - 0.2) / 0.2
        return (int(s * 140), 0, int(180 + s * 75))
    if t < 0.6:
        s = (t - 0.4) / 0.2
        return (int(140 + s * 115), int(s * 40), int(255 - s * 255))
    if t < 0.8:
        s = (t - 0.6) / 0.2
        return (255, int(40 + s * 215), 0)
    s = (t - 0.8) / 0.2
    return (255, 255, int(s * 255))


GRAD = [gradient_color(i / 63) for i in range(64)]


def grad_idx(t):
    return clampi(int(t * 63), 0, 63)


def circ_idx(t):
    return clampi(int(t * 15), 0, 15)


# ── Audio simulation ─────────────────────────────────────────────────────────

# Each oscillator: (freq, amp, phase, mod_freq, mod_depth)
TRACK_OSCS = [
    # 0 EDM
    [(2, 0.9, 0, 0.5, 0.8), (4, 0.7, 0.3, 1.0, 0.5), (8, 0.5, 1.0, 2.0, 0.6),
     (16, 0.4, 0.5, 3.0, 0.4), (24, 0.3, 0.8, 4.5, 0.5), (32, 0.25, 1.2, 6.0, 0.3),
     (48, 0.15, 0.2, 8.0, 0.7)],
    # 1 AMBIENT
    [(1.5, 0.4, 0, 0.1, 0.3), (3, 0.5, 0.7, 0.15, 0.4), (6, 0.6, 1.4, 0.2, 0.5),
     (12, 0.7, 0.3, 0.25, 0.3), (20, 0.5, 2.0, 0.3, 0.4), (30, 0.3, 1.1, 0.4, 0.5),
     (45, 0.2, 0.5, 0.5, 0.6)],
    # 2 ROCK
    [(2.5, 0.8, 0, 2.0, 0.9), (5, 0.6, 0.5, 2.0, 0.7), (10, 0.7, 1.0, 4.0, 0.5),
     (15, 0.5, 0.3, 3.0, 0.6), (22, 0.6, 0.8, 5.0, 0.4), (35, 0.4, 1.5, 7.0, 0.5),
     (50, 0.3, 0.2, 9.0, 0.3)],
    # 3 SYNTHWAVE
    [(1.8, 0.6, 0, 0.8, 0.6), (3.6, 0.5, 1.0, 1.2, 0.5), (7.2, 0.7, 0.5, 1.6, 0.7),
     (14, 0.8, 1.5, 2.4, 0.4), (21, 0.6, 0.3, 3.2, 0.6), (28, 0.5, 0.8, 4.0, 0.5),
     (42, 0.35, 1.2, 5.5, 0.4)],
    # 4 GLITCH
    [(3, 0.7, 0, 3.0, 0.9), (7, 0.5, 0.4, 5.0, 0.8), (11, 0.6, 0.9, 7.0, 0.7),
     (17, 0.5, 1.3, 11.0, 0.6), (23, 0.4, 0.2, 13.0, 0.8), (37, 0.3, 0.7, 17.0, 0.5),
     (53, 0.2, 1.1, 19.0, 0.7)],
]


class World:
    def __init__(self):
        self.mode = 0
        self.track = 0
        self.spectrum = [0.0] * NUM_BARS
        self.display = [0.0] * NUM_BARS
        self.peaks = [0.0] * NUM_BARS
        self.peak_vel = [0.0] * NUM_BARS
        self.waterfall = []
        self.bass_avg = 0.0
        self.bass_energy = 0.0
        self.beat = False
        self.beat_flash = 0
        self.time = 0.0


W = World()


def generate_spectrum(dt):
    w = W
    w.time += dt
    oscs = TRACK_OSCS[w.track]
    for i in range(NUM_BARS):
        freq_pos = i / NUM_BARS
        val = 0.0
        for freq, amp, phase, mod_freq, mod_depth in oscs:
            osc_pos = freq / 64.0
            dist = abs(freq_pos - osc_pos)
            spread = 0.08 + osc_pos * 0.05
            influence = math.exp(-dist * dist / (2 * spread * spread))
            mod = 1.0 - mod_depth * (0.5 + 0.5 * math.sin(TWO_PI * mod_freq * w.time + phase))
            val += amp * mod * influence
        harmonic = 0.15 * math.sin(TWO_PI * (3.0 + freq_pos * 20.0) * w.time * 0.1)
        val += harmonic * (1.0 - freq_pos)
        val += random.uniform(-0.02, 0.02)
        w.spectrum[i] = clamp(val, 0.0, 1.0)

    bass = sum(w.spectrum[: NUM_BARS // 8]) / (NUM_BARS // 8)
    w.bass_avg = w.bass_avg * 0.95 + bass * 0.05
    w.bass_energy = bass
    w.beat = bass > w.bass_avg * 1.4 and bass > 0.4
    if w.beat:
        w.beat_flash = 6
    if w.beat_flash > 0:
        w.beat_flash -= 1

    for i in range(NUM_BARS):
        target = w.spectrum[i]
        speed = 0.4 if target > w.display[i] else BAR_SMOOTH
        w.display[i] += (target - w.display[i]) * speed
        if w.display[i] > w.peaks[i]:
            w.peaks[i] = w.display[i]
            w.peak_vel[i] = 0.0
        else:
            w.peak_vel[i] += PEAK_DECAY * 0.5
            w.peaks[i] -= w.peak_vel[i]
            if w.peaks[i] < 0:
                w.peaks[i] = 0.0

    w.waterfall.append(list(w.display))
    if len(w.waterfall) > NUM_WATERFALL:
        w.waterfall.pop(0)


# ── Rendering helpers ────────────────────────────────────────────────────────

def _blank_grid(w, h, bg):
    return [[bg] * w for _ in range(h)]


# Mode 0 — bars (full colored cells via row tuple-cells)
def paint_bars(w, h):
    bar_area_h = h
    num_bars = min(64, max(1, w // 2))
    bar_width = max(1, w // num_bars)
    gap = 1 if bar_width > 2 else 0
    draw_w = bar_width - gap
    # cell grid of (char, fg) or None
    grid = [[None] * w for _ in range(bar_area_h)]
    for i in range(num_bars):
        val = W.display[i]
        bar_h = int(val * bar_area_h)
        peak_y = int(W.peaks[i] * bar_area_h)
        x0 = i * bar_width
        for j in range(bar_h + 1):
            y = bar_area_h - 1 - j
            if 0 <= y < bar_area_h:
                t = j / bar_area_h
                color = GRAD[grad_idx(t)]
                for dx in range(draw_w):
                    if x0 + dx < w:
                        grid[y][x0 + dx] = ("█", color)
        if 0 < peak_y < bar_area_h:
            py = bar_area_h - 1 - peak_y
            t = peak_y / bar_area_h
            color = GRAD[grad_idx(t)]
            for dx in range(draw_w):
                if x0 + dx < w:
                    grid[py][x0 + dx] = ("▔", color)
    return _grid_to_rows(grid, w, bar_area_h)


def paint_mirror(w, h):
    bar_area_h = h
    num_bars = min(64, max(1, w // 2))
    bar_width = max(1, w // num_bars)
    gap = 1 if bar_width > 2 else 0
    draw_w = bar_width - gap
    mid = bar_area_h // 2
    grid = [[None] * w for _ in range(bar_area_h)]
    for i in range(num_bars):
        val = W.display[i]
        half_h = int(val * mid)
        x0 = i * bar_width
        for j in range(half_h + 1):
            t = j / mid if mid else 0
            color = GRAD[grad_idx(t)]
            yu = mid - 1 - j
            yl = mid + j
            for dx in range(draw_w):
                x = x0 + dx
                if x < w:
                    if 0 <= yu < bar_area_h:
                        grid[yu][x] = ("█", color)
                    if 0 <= yl < bar_area_h:
                        grid[yl][x] = ("█", color)
        peak_h = int(W.peaks[i] * mid)
        if 0 < peak_h < mid:
            t = peak_h / mid
            color = GRAD[grad_idx(t)]
            pyu = mid - 1 - peak_h
            pyl = mid + peak_h
            for dx in range(draw_w):
                x = x0 + dx
                if x < w:
                    if 0 <= pyu < bar_area_h:
                        grid[pyu][x] = ("▔", color)
                    if 0 <= pyl < bar_area_h:
                        grid[pyl][x] = ("▁", color)
    return _grid_to_rows(grid, w, bar_area_h)


def paint_circular(w, h):
    bar_area_h = h
    px_w = w
    px_h = bar_area_h * 2
    cx = px_w / 2
    cy = px_h / 2
    max_r = min(cx, cy) * 0.85
    inner_r = max_r * 0.3
    pixels = [0.0] * (px_w * px_h)

    for i in range(64):
        val = W.display[i]
        angle = TWO_PI * i / 64 - math.pi / 2
        next_angle = TWO_PI * (i + 1) / 64 - math.pi / 2
        bar_len = val * (max_r - inner_r)
        steps = int(bar_len) + 1
        for s in range(steps + 1):
            r = inner_r + s
            if r > inner_r + bar_len:
                break
            arc_steps = max(2, int((next_angle - angle) * r))
            for a in range(arc_steps + 1):
                ang = angle + (next_angle - angle) * a / arc_steps
                px = int(cx + r * math.cos(ang))
                py = int(cy + r * math.sin(ang))
                if 0 <= px < px_w and 0 <= py < px_h:
                    t = s / (max_r - inner_r)
                    idx = py * px_w + px
                    if t > pixels[idx]:
                        pixels[idx] = t
        peak_r = inner_r + W.peaks[i] * (max_r - inner_r)
        mid_angle = (angle + next_angle) * 0.5
        ppx = int(cx + peak_r * math.cos(mid_angle))
        ppy = int(cy + peak_r * math.sin(mid_angle))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                x = ppx + dx
                y = ppy + dy
                if 0 <= x < px_w and 0 <= y < px_h:
                    idx = y * px_w + x
                    if 0.95 > pixels[idx]:
                        pixels[idx] = 0.95

    # Build half-block grid of colors
    grid = [[None] * px_w for _ in range(px_h)]
    for py in range(px_h):
        for px in range(px_w):
            v = pixels[py * px_w + px]
            if v > 0.01:
                grid[py][px] = GRAD[grad_idx(v)]
    return halfblock(grid)


def paint_waterfall(w, h):
    bar_area_h = h
    bars_h = max(1, bar_area_h // 4)
    wf_h = bar_area_h - bars_h
    grid = [[None] * w for _ in range(bar_area_h)]
    # mini bars on top
    num_bars = min(64, max(1, w))
    col_w = w / num_bars
    for i in range(num_bars):
        val = W.display[i]
        bar_h = int(val * bars_h)
        x0 = int(i * col_w)
        x1 = int((i + 1) * col_w)
        for j in range(bar_h):
            y = bars_h - 1 - j
            if 0 <= y < bars_h:
                t = j / bars_h
                color = GRAD[grad_idx(t)]
                for x in range(x0, x1):
                    if x < w:
                        grid[y][x] = ("█", color)
    # waterfall below
    wf_rows = len(W.waterfall)
    display_rows = min(wf_h, wf_rows)
    for r in range(wf_h):
        y = bars_h + r
        data_idx = wf_rows - display_rows + r
        if 0 <= data_idx < wf_rows:
            data = W.waterfall[data_idx]
            for i in range(num_bars):
                color = GRAD[grad_idx(data[i])]
                x0 = int(i * col_w)
                x1 = int((i + 1) * col_w)
                for x in range(x0, x1):
                    if x < w:
                        grid[y][x] = (" ", (0, 0, 0), color)
    return _grid_to_rows(grid, w, bar_area_h)


def _grid_to_rows(grid, w, h):
    rows = []
    for y in range(h):
        gr = grid[y]
        specs = []
        for x in range(w):
            cell = gr[x]
            if cell is None:
                specs.append(" ")
            elif len(cell) == 2:
                ch, fg = cell
                specs.append((ch, (fg[0] << 16) | (fg[1] << 8) | fg[2]))
            else:
                ch, fg, bg = cell
                specs.append((ch, (fg[0] << 16) | (fg[1] << 8) | fg[2],
                              (bg[0] << 16) | (bg[1] << 8) | bg[2]))
        rows.append(row(*specs, gap=0))
    return col(*rows, gap=0)


# ── App ──────────────────────────────────────────────────────────────────────

app = App.inline("spectrum", fps=30)
app.state(_t=0.0)


@app.on("1")
def _m1(s):
    W.mode = 0


@app.on("2")
def _m2(s):
    W.mode = 1


@app.on("3")
def _m3(s):
    W.mode = 2


@app.on("4")
def _m4(s):
    W.mode = 3


@app.on("space")
def _track(s):
    W.track = (W.track + 1) % 5
    for i in range(NUM_BARS):
        W.peaks[i] = 0.0
        W.peak_vel[i] = 0.0


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    generate_spectrum(1.0 / 30.0)


def _field(w, _h):
    h = ROWS
    if w <= 0:
        return col()
    if W.mode == 0:
        return paint_bars(w, h)
    if W.mode == 1:
        return paint_mirror(w, h)
    if W.mode == 2:
        return paint_circular(w, h)
    return paint_waterfall(w, h)


@app.view
def view(s):
    vu = sum(W.display) / NUM_BARS
    vu_width = 20
    vu_fill = int(vu * vu_width)
    vu_bar = "".join("|" if i < vu_fill else " " for i in range(vu_width))
    acc = (255, 100, 100) if W.beat_flash > 0 else (80, 200, 255)
    status = row(
        T(f" {MODE_NAMES[W.mode]}  Track: {TRACK_NAMES[W.track]}  VU [{vu_bar}]").fg(acc).bold,
        T("   [1-4] mode  [space] track  [q] quit").fg((60, 60, 80)),
        gap=0,
    )
    return col(box(component(_field, height=ROWS), height=ROWS), status, gap=0)


if __name__ == "__main__":
    app.run()
