"""matrix.py — Matrix digital rain.

A faithful port of maya's `examples/matrix.cpp`. A column-based cascade of
half-width katakana + digits + latin, with a bright leading head and a fading
trail, two stream layers per column for density, four colour modes, and a
glitchy "WAKE UP NEO" message reveal. Rendered through maya's native
tuple-cell `row` fast path (packed colours, no per-cell allocation).

  Keys: q/Esc quit · space pause · m message · 1-4 mode
        (1 CLASSIC · 2 MULTI-COLOR · 3 RED PILL · 4 RAINBOW)

    PYTHONPATH=src python examples/matrix.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, box, col, component, row, BOLD, clamp as clampi  # noqa: E402

# CHARSET: half-width katakana U+FF66..U+FF9D (56), digits, latin A-Z.
CHARSET = (
    [chr(c) for c in range(0xFF66, 0xFF9E)]
    + [str(d) for d in range(10)]
    + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
)
CHARSET_SIZE = len(CHARSET)

BRIGHTNESS_LEVELS = 32
TRAIL_LENGTH = 24

# Color modes
M_CLASSIC, M_MULTI, M_REDPILL, M_RAINBOW = range(4)
MODE_NAMES = ["CLASSIC", "MULTI-COLOR", "RED PILL", "RAINBOW"]

NUM_HUES = 6
HUES = [120, 180, 270, 300, 90, 160]
RAINBOW_HUES = 64

ROWS = 22
MSG_DURATION = 90
MSG_TEXT = "WAKE UP NEO"


def hsv_to_rgb(h, s, v):
    c = v * s
    x = c * (1 - abs(math.fmod(h / 60.0, 2) - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def pack(rgb):
    return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]


# ── Palettes (precomputed packed ints) ───────────────────────────────────────

def build_palettes():
    # Classic green
    green = []
    for i in range(BRIGHTNESS_LEVELS):
        t = i / (BRIGHTNESS_LEVELS - 1)
        green.append(pack((int(t * t * 80), int(30 + t * 225), 0)))
    head_classic = pack((220, 255, 220))

    # Multi-color (per hue)
    hue_styles = []
    hue_heads = []
    for h_idx in range(NUM_HUES):
        col = []
        for i in range(BRIGHTNESS_LEVELS):
            t = i / (BRIGHTNESS_LEVELS - 1)
            col.append(pack(hsv_to_rgb(HUES[h_idx], 0.8, 0.15 + t * 0.85)))
        hue_styles.append(col)
        hue_heads.append(pack(hsv_to_rgb(HUES[h_idx], 0.2, 1.0)))

    # Red pill
    red = []
    for i in range(BRIGHTNESS_LEVELS):
        t = i / (BRIGHTNESS_LEVELS - 1)
        red.append(pack((int(30 + t * 225), int(t * t * 40), 0)))
    head_red = pack((255, 200, 200))

    # Rainbow
    rainbow = []
    rainbow_heads = []
    for hi in range(RAINBOW_HUES):
        hue = 360 * hi / RAINBOW_HUES
        col = []
        for i in range(BRIGHTNESS_LEVELS):
            t = i / (BRIGHTNESS_LEVELS - 1)
            col.append(pack(hsv_to_rgb(hue, 0.85, 0.12 + t * 0.88)))
        rainbow.append(col)
        rainbow_heads.append(pack(hsv_to_rgb(hue, 0.15, 1.0)))

    return {
        "green": green, "head_classic": head_classic,
        "hue": hue_styles, "hue_head": hue_heads,
        "red": red, "head_red": head_red,
        "rainbow": rainbow, "rainbow_head": rainbow_heads,
    }


PAL = build_palettes()


# ── Streams ──────────────────────────────────────────────────────────────────

class Stream:
    __slots__ = ("y_pos", "speed", "gap_remaining", "trail_len", "hue_offset", "chars")

    def __init__(self):
        self.y_pos = 0.0
        self.speed = 1
        self.gap_remaining = 0
        self.trail_len = TRAIL_LENGTH
        self.hue_offset = 0
        self.chars = []


def rand_char_idx():
    return random.randrange(CHARSET_SIZE)


def init_stream(s, col_height):
    s.y_pos = -random.randint(0, col_height)
    s.speed = random.randint(1, 4)
    s.gap_remaining = 0
    s.trail_len = random.randint(12, 24)
    s.hue_offset = random.randint(0, 5)
    s.chars = [rand_char_idx() for _ in range(col_height)]


def reset_stream(s, col_height):
    s.y_pos = -random.randint(2, 12)
    s.speed = random.randint(1, 4)
    s.gap_remaining = random.randint(4, 30)
    s.trail_len = random.randint(12, 24)
    s.hue_offset = random.randint(0, 5)
    s.chars = [rand_char_idx() for _ in range(col_height)]


class World:
    def __init__(self):
        self.w = 0
        self.h = 0
        self.streams = []
        self.mode = M_CLASSIC
        self.paused = False
        self.frame = 0
        self.msg_active = False
        self.msg_timer = 0

    def ensure(self, w, rain_h):
        if w != self.w or rain_h != self.h:
            self.w = w
            self.h = rain_h
            num = w * 2
            self.streams = []
            ch = max(rain_h, 1)
            for i in range(num):
                s = Stream()
                init_stream(s, ch)
                if i >= w:
                    s.y_pos -= random.randint(0, ch)
                self.streams.append(s)

    def step(self):
        if self.paused:
            return
        self.frame += 1
        if self.msg_active:
            self.msg_timer -= 1
            if self.msg_timer <= 0:
                self.msg_active = False
        rain_h = self.h
        w = self.w
        for si, s in enumerate(self.streams):
            if s.gap_remaining > 0:
                s.gap_remaining -= 1
                continue
            s.y_pos += s.speed
            if random.randint(0, 3) == 0:
                mutate_row = int(s.y_pos) - random.randint(1, s.trail_len)
                if 0 <= mutate_row < rain_h:
                    s.chars[mutate_row] = rand_char_idx()
            if int(s.y_pos) - s.trail_len > rain_h:
                reset_stream(s, rain_h)


W = World()


def trail_style(col_x, brightness, hue_offset):
    b = clampi(brightness, 0, 31)
    mode = W.mode
    if mode == M_CLASSIC:
        return PAL["green"][b]
    if mode == M_MULTI:
        return PAL["hue"][hue_offset % 6][b]
    if mode == M_REDPILL:
        return PAL["red"][b]
    hi = ((col_x * 64 // max(W.w, 1)) + W.frame // 3) % 64
    return PAL["rainbow"][hi][b]


def head_style(col_x, hue_offset):
    mode = W.mode
    if mode == M_CLASSIC:
        return PAL["head_classic"]
    if mode == M_MULTI:
        return PAL["hue_head"][hue_offset % 6]
    if mode == M_REDPILL:
        return PAL["head_red"]
    hi = ((col_x * 64 // max(W.w, 1)) + W.frame // 3) % 64
    return PAL["rainbow_head"][hi]


_MSG_WHITE = pack((255, 255, 255))


def _draw(w, _h):
    rain_h = ROWS
    if w <= 0:
        return col()
    W.ensure(w, rain_h)

    # grid[y][x] = (char_idx, packed_fg, bold) or None
    grid = [[None] * w for _ in range(rain_h)]
    for si, s in enumerate(W.streams):
        col_x = si % w
        head_y = int(s.y_pos)
        for i in range(s.trail_len + 1):
            y = head_y - i
            if not (0 <= y < rain_h):
                continue
            ci = s.chars[y]
            if i == 0:
                grid[y][col_x] = (ci, head_style(col_x, s.hue_offset), True)
            else:
                fade = 1.0 - i / s.trail_len
                brightness = int(fade * (BRIGHTNESS_LEVELS - 1))
                grid[y][col_x] = (ci, trail_style(col_x, brightness, s.hue_offset), False)

    # Message reveal
    if W.msg_active and W.msg_timer > 0:
        msg_len = len(MSG_TEXT)
        mx = (w - msg_len) // 2
        my = rain_h // 2
        progress = W.msg_timer / MSG_DURATION
        alpha = (1 - progress) * 2 if progress > 0.5 else progress * 2
        alpha = max(0.0, min(1.0, alpha))
        if alpha > 0.15 and 0 <= my < rain_h:
            for i, mc in enumerate(MSG_TEXT):
                x = mx + i
                if mc == " " or not (0 <= x < w):
                    continue
                if alpha > 0.4:
                    show = mc
                else:
                    show = mc if random.randint(0, 3) == 0 else CHARSET[rand_char_idx()]
                # store as literal char via a sentinel char_idx of -1
                grid[my][x] = (("LIT", show), _MSG_WHITE, True)

    rows = []
    for y in range(rain_h):
        gr = grid[y]
        specs = []
        for x in range(w):
            cell = gr[x]
            if cell is None:
                specs.append(" ")
                continue
            ci, fg, bold = cell
            if isinstance(ci, tuple) and ci[0] == "LIT":
                ch = ci[1]
            else:
                ch = CHARSET[ci]
            specs.append((ch, fg, -1, BOLD if bold else 0))
        rows.append(row(*specs, gap=0))
    return col(*rows, gap=0)


# ── App ──────────────────────────────────────────────────────────────────────

app = App.inline("matrix", fps=30)
app.state(_t=0.0)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on("space")
def _pause(s):
    W.paused = not W.paused


@app.on("m")
def _message(s):
    W.msg_active = True
    W.msg_timer = MSG_DURATION


@app.on("1")
def _m1(s):
    W.mode = M_CLASSIC


@app.on("2")
def _m2(s):
    W.mode = M_MULTI


@app.on("3")
def _m3(s):
    W.mode = M_REDPILL


@app.on("4")
def _m4(s):
    W.mode = M_RAINBOW


@app.on_frame
def _frame(s, dt):
    W.step()


@app.view
def view(s):
    status = row(
        T("MATRIX").fg((0, 200, 0)).bold,
        T(" │ [1-4] mode │ [m] message │ [space] pause │ [q] quit").fg((60, 60, 60)),
        T("   " + MODE_NAMES[W.mode]).fg((0, 200, 0)).bold,
        T("   PAUSED" if W.paused else "").fg((0, 200, 0)).bold,
        gap=0,
    )
    return col(box(component(_draw, height=ROWS), height=ROWS), status, gap=0)


if __name__ == "__main__":
    app.run()
