"""matrix.py — falling "digital rain", animated with maya's reveal renderer.

A column-based green cascade with a bright leading char and a fading tail.
Auto-stops after 20s; Ctrl-C to quit early.

    PYTHONPATH=src python examples/matrix.py
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import component, col, T

GLYPHS = "ｱｲｳｴｵｶｷｸｹｺ01<>=*+-|/\\"
start = time.time()

# per-column drop position + speed, lazily sized to the terminal width
_cols = None
_rows = 0


def _ensure(w, h):
    global _cols, _rows
    if _cols is None or len(_cols) != w or _rows != h:
        _cols = [{"y": random.uniform(-h, 0),
                  "speed": random.uniform(0.3, 1.2),
                  "len": random.randint(4, h)} for _ in range(w)]
        _rows = h


def rain(rows):
    def draw(w, h):
        h = rows  # use a fixed row count; ignore any unbounded allocation
        if w <= 0 or h <= 0:
            return T("")
        _ensure(w, h)
        # build a grid of (char, brightness) then color it
        grid = [[None] * w for _ in range(h)]
        for x, cdef in enumerate(_cols):
            cdef["y"] += cdef["speed"]
            head = int(cdef["y"])
            if head - cdef["len"] > h:
                cdef["y"] = random.uniform(-h, 0)
                cdef["speed"] = random.uniform(0.3, 1.2)
                cdef["len"] = random.randint(4, h)
            for i in range(cdef["len"]):
                y = head - i
                if 0 <= y < h:
                    bright = 1.0 - (i / cdef["len"])
                    grid[y][x] = bright
        # render rows
        out = []
        for y in range(h):
            parts = []
            for x in range(w):
                b = grid[y][x]
                if b is None:
                    parts.append(" ")
                elif b > 0.92:
                    parts.append(T(random.choice(GLYPHS)).fg("white").bold)
                elif b > 0.5:
                    parts.append(T(random.choice(GLYPHS)).fg(maya.rgb(80, 255, 120)))
                else:
                    g = int(40 + b * 120)
                    parts.append(T(random.choice(GLYPHS)).fg(maya.rgb(20, g, 40)))
            out.append(maya.row(*parts, gap=0))
        return col(*out)
    return component(draw, height=rows)


ROWS = 18


def render(dt):
    if time.time() - start > 20:
        maya.quit()
    return maya.box(rain(ROWS), height=ROWS)


if __name__ == "__main__":
    maya.animate(render, fps=14)
