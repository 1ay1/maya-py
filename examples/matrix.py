"""matrix.py — falling "digital rain" (the Matrix screensaver), interactive.

A column-based green cascade with a bright white leading char and a fading
tail. Built for speed: each frame's cells go through the zero-allocation
``trow`` fast path (packed-int colors, no per-cell ``T`` objects), so an
80×24 screen of rain stays smooth.

    PYTHONPATH=src python examples/matrix.py

Keys:  q / esc  quit      space  pause/resume      r  reseed
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, component, col, trow, BOLD

GLYPHS = "ｱｲｳｴｵｶｷｸｹｺ01<>=*+-|/\\"
_NG = len(GLYPHS)

# Pre-pack the colors as 0xRRGGBB ints once (trow takes packed ints directly,
# so there is no Color object built per cell — that was the old slow path).
_WHITE = 0xF0F0F0                                   # bright leading head
_BRIGHT = (80 << 16) | (255 << 8) | 120             # mid tail, vivid green
_TAIL = [((20 << 16) | (g << 8) | 40) for g in range(40, 161)]  # fading green ramp


def _new_col(h):
    return [random.uniform(-h, 0), random.uniform(0.3, 1.2), random.randint(4, max(4, h))]


def _seed_col(h):
    # Initial seed: scatter heads across the whole height (not all above the
    # top) so the very first frame already shows rain instead of a blank
    # screen that fills in over the next second.
    return [random.uniform(0, h), random.uniform(0.3, 1.2), random.randint(4, max(4, h))]


class Rain:
    """Mutable per-column drop state, lazily sized to the terminal."""
    __slots__ = ("w", "h", "cols")

    def __init__(self):
        self.w = self.h = 0
        self.cols = []

    def ensure(self, w, h):
        if w != self.w or h != self.h:
            self.w, self.h = w, h
            self.cols = [_seed_col(h) for _ in range(w)]

    def step(self):
        h = self.h
        for cdef in self.cols:
            cdef[0] += cdef[1]          # advance head
            if cdef[0] - cdef[2] > h:   # fell off the bottom → respawn at top
                cdef[0], cdef[1], cdef[2] = _new_col(h)


_rain = Rain()


def _draw(w, h):
    # NB: under a fixed/`grow` component the `h` arg is maya's fullscreen
    # sentinel (~2**20), NOT the real row count. We drive a fixed ROWS grid
    # and ignore `h` entirely (building an h-row grid would allocate a
    # million rows and hang).
    h = ROWS
    if w <= 0:
        return col()
    _rain.ensure(w, h)
    cols = _rain.cols

    # grid[y][x] = brightness in [0,1] or None (blank)
    grid = [[None] * w for _ in range(h)]
    for x in range(w):
        head, _spd, length = cols[x]
        ih = int(head)
        inv = 1.0 / length
        for i in range(length):
            y = ih - i
            if 0 <= y < h:
                grid[y][x] = 1.0 - i * inv

    rnd = random.random
    choice_i = random.randrange
    rows = []
    ntail = len(_TAIL)
    for y in range(h):
        row = grid[y]
        # Each cell is a (text, fg, bg, attrs) spec. Blanks are plain " "
        # (no style). trow builds the whole row in ONE crossing.
        specs = []
        ap = specs.append
        for x in range(w):
            b = row[x]
            if b is None:
                ap(" ")
                continue
            ch = GLYPHS[choice_i(_NG)]
            if b > 0.92:
                ap((ch, _WHITE, -1, BOLD))
            elif b > 0.5:
                ap((ch, _BRIGHT, -1, 0))
            else:
                ap((ch, _TAIL[min(ntail - 1, int(b * ntail))], -1, 0))
        rows.append(trow(*specs, gap=0))
    return col(*rows, gap=0)


ROWS = 22

app = App("matrix", inline=True, fps=16)
app.state(paused=False)


@app.on("q", "esc")
def quit(s):
    app.stop()


@app.on("space")
def pause(s):
    s.paused = not s.paused


@app.on("r")
def reseed(s):
    _rain.w = _rain.h = 0   # force ensure() to rebuild next frame


@app.view
def view(s):
    if not s.paused:
        _rain.step()
    return maya.box(component(_draw, height=ROWS), height=ROWS)


if __name__ == "__main__":
    app.run()
