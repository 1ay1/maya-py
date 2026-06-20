"""clock.py — a live analog clock drawn on maya's imperative Canvas.

A real ticking analog clock: tick marks, three hands (hour / minute / sweeping
second), a coloured progress arc for the minute, plus a digital readout and the
date. Drawn pixel-by-pixel on the half-block ``Canvas`` surface, so it's smooth
truecolor at double vertical resolution.

  t — toggle 12h / 24h digital readout
  s — toggle the smooth (vs ticking) second hand
  q/esc — quit

    PYTHONPATH=src python examples/clock.py
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, T, b, col, row, card, dim_text, Canvas, badge

# canvas is square-ish in pixels; height cells × 2 = pixel rows
CW, CH = 60, 30          # 60×60 pixels
CX, CY = CW // 2, CH      # centre (pixel space; CH cells → 2*CH px tall)
R = min(CX, CY) - 3       # clock radius in pixels

FACE = (28, 32, 44)
RING = (90, 110, 150)
TICK = (130, 150, 190)
TICK5 = (200, 215, 240)
HOUR_C = (120, 200, 255)
MIN_C = (140, 240, 170)
SEC_C = (255, 110, 110)
ARC_C = (80, 130, 220)


def _pt(cx, cy, ang, length):
    # ang: 0 at 12 o'clock, clockwise
    return (cx + math.sin(ang) * length, cy - math.cos(ang) * length)


def draw_clock(now, smooth):
    c = Canvas(CW, CH)
    c.fill(FACE)

    # outer ring (approximate a circle with line segments)
    seg = 96
    px, py = _pt(CX, CY, 0, R)
    for i in range(1, seg + 1):
        a = 2 * math.pi * i / seg
        nx, ny = _pt(CX, CY, a, R)
        c.line(int(px), int(py), int(nx), int(ny), RING)
        px, py = nx, ny

    # tick marks
    for m in range(60):
        a = 2 * math.pi * m / 60
        if m % 5 == 0:
            x1, y1 = _pt(CX, CY, a, R - 5)
            col = TICK5
        else:
            x1, y1 = _pt(CX, CY, a, R - 2)
            col = TICK
        x2, y2 = _pt(CX, CY, a, R)
        c.line(int(x1), int(y1), int(x2), int(y2), col)

    h = now.tm_hour % 12
    mn = now.tm_min
    sec = now.tm_sec
    frac = (time.time() % 1.0) if smooth else 0.0

    sec_v = sec + frac
    min_v = mn + sec_v / 60.0
    hour_v = h + min_v / 60.0

    # minute-progress arc along the rim
    steps = int((min_v / 60.0) * seg)
    px, py = _pt(CX, CY, 0, R - 1)
    for i in range(1, steps + 1):
        a = 2 * math.pi * i / seg
        nx, ny = _pt(CX, CY, a, R - 1)
        c.line(int(px), int(py), int(nx), int(ny), ARC_C)
        px, py = nx, ny

    # hands
    ha = 2 * math.pi * hour_v / 12
    ma = 2 * math.pi * min_v / 60
    sa = 2 * math.pi * sec_v / 60
    hx, hy = _pt(CX, CY, ha, R * 0.5)
    mx, my = _pt(CX, CY, ma, R * 0.78)
    sx, sy = _pt(CX, CY, sa, R * 0.86)
    # tail of the second hand for balance
    tx, ty = _pt(CX, CY, sa + math.pi, R * 0.2)

    c.line(CX, CY, int(hx), int(hy), HOUR_C)
    c.line(CX, CY, int(mx), int(my), MIN_C)
    c.line(int(tx), int(ty), int(sx), int(sy), SEC_C)

    # hub
    c.set_pixel(CX, CY, (255, 255, 255))
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        c.set_pixel(CX + ox, CY + oy, SEC_C)

    return c.element()


app = App.inline("clock", fps=20)
app.state(h24=True, smooth=True)


@app.on("t")
def _fmt(st): st.h24 = not st.h24


@app.on("s")
def _smooth(st): st.smooth = not st.smooth


app.quit_on("q", "esc")


WDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@app.view
def view(st):
    now = time.localtime()
    if st.h24:
        digital = time.strftime("%H:%M:%S", now)
        ampm = ""
    else:
        digital = time.strftime("%I:%M:%S", now).lstrip("0")
        ampm = time.strftime(" %p", now)

    date = f"{WDAY[now.tm_wday]} {now.tm_mday} {MON[now.tm_mon - 1]} {now.tm_year}"

    readout = row(
        b(digital).fg("sky"),
        T(ampm).fg("slate") if ampm else dim_text(""),
        gap=0,
    )

    side = col(
        dim_text("now"),
        readout,
        dim_text(date),
        T("").fg("slate"),
        badge("24h" if st.h24 else "12h", kind="info"),
        badge("smooth" if st.smooth else "tick",
              kind="success" if st.smooth else "warning"),
        gap=0,
    )

    return card(
        row(
            card(draw_clock(now, st.smooth), border="round",
                 border_color="slate", pad=0),
            side,
            gap=3, align="center",
        ),
        dim_text("t 12/24h · s smooth-hand · q quit"),
        title="analog clock", gap=1,
    )


if __name__ == "__main__":
    app.run()
