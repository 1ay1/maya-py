"""life.py — Conway's Game of Life with half-block rendering + heat aging.

Each terminal row holds two pixel rows (▀). Live cells age through a colour
gradient (green → cyan → blue → purple). Toroidal grid that resizes to fill the
whole terminal — grow the window and the world grows with it.

  space pause · enter step · +/- speed · c clear · r random · g glider gun
  p pulsar · q/esc quit

    PYTHONPATH=src python examples/life.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component
from maya_py import halfblock

GRADIENT = [
    (100, 255, 120), (0, 220, 220), (40, 120, 255),
    (140, 60, 220), (90, 50, 130),
]


def _age_color(age):
    if age <= 1:
        return GRADIENT[0]
    if age <= 5:
        return GRADIENT[1]
    if age <= 20:
        return GRADIENT[2]
    if age <= 80:
        return GRADIENT[3]
    return GRADIENT[4]


app = App.inline("life", fps=30)
app.state(cur=[], age=[], pw=0, ph=0, gen=0, pop=0, paused=False,
          interval=4, accum=0, name="random")


def _ensure(s, w, h):
    if w != s.pw or h != s.ph:
        s.pw, s.ph = w, h
        randomize(s)


def _idx(s, x, y):
    return (y % s.ph) * s.pw + (x % s.pw)


def randomize(s):
    n = s.pw * s.ph
    s.cur = [random.random() < 0.28 for _ in range(n)]
    s.age = [1 if c else 0 for c in s.cur]
    s.gen = 0
    s.name = "random"


def clear(s):
    n = s.pw * s.ph
    s.cur = [False] * n
    s.age = [0] * n
    s.gen = 0
    s.name = "empty"


def _place(s, pattern, ox, oy, name):
    clear(s)
    for (dx, dy) in pattern:
        i = _idx(s, ox + dx, oy + dy)
        s.cur[i] = True
        s.age[i] = 1
    s.name = name


GLIDER_GUN = [
    (0, 4), (0, 5), (1, 4), (1, 5), (10, 4), (10, 5), (10, 6),
    (11, 3), (11, 7), (12, 2), (12, 8), (13, 2), (13, 8), (14, 5),
    (15, 3), (15, 7), (16, 4), (16, 5), (16, 6), (17, 5),
    (20, 2), (20, 3), (20, 4), (21, 2), (21, 3), (21, 4), (22, 1), (22, 5),
    (24, 0), (24, 1), (24, 5), (24, 6), (34, 2), (34, 3), (35, 2), (35, 3),
]

PULSAR = [
    (2, 0), (3, 0), (4, 0), (8, 0), (9, 0), (10, 0),
    (0, 2), (5, 2), (7, 2), (12, 2), (0, 3), (5, 3), (7, 3), (12, 3),
    (0, 4), (5, 4), (7, 4), (12, 4), (2, 5), (3, 5), (4, 5), (8, 5), (9, 5), (10, 5),
]


def step(s):
    pw, ph = s.pw, s.ph
    cur, age = s.cur, s.age
    nxt = [False] * (pw * ph)
    nage = [0] * (pw * ph)
    pop = 0
    for y in range(ph):
        for x in range(pw):
            n = 0
            for dy in (-1, 0, 1):
                yy = (y + dy) % ph
                base = yy * pw
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    if cur[base + (x + dx) % pw]:
                        n += 1
            i = y * pw + x
            alive = cur[i]
            if (alive and n in (2, 3)) or (not alive and n == 3):
                nxt[i] = True
                nage[i] = (age[i] + 1) if alive else 1
                pop += 1
    s.cur, s.age, s.pop = nxt, nage, pop
    s.gen += 1


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("enter")
def _step(s): step(s)


@app.on("+", "=")
def _faster(s): s.interval = max(1, s.interval - 1)


@app.on("-")
def _slower(s): s.interval = min(12, s.interval + 1)


@app.on("c")
def _clear(s): clear(s)


@app.on("r")
def _random(s): randomize(s)


@app.on("g")
def _gun(s): _place(s, GLIDER_GUN, 6, 8, "glider gun")


@app.on("p")
def _pulsar(s): _place(s, PULSAR, s.pw // 2 - 6, s.ph // 2 - 3, "pulsar")


app.quit_on("q", "esc")


def board(s):
    def draw(w, h):
        h = max(1, min(h, 60))
        _ensure(s, w, h * 2)
        if not s.paused:
            s.accum += 1
            if s.accum >= s.interval:
                s.accum = 0
                step(s)
        grid = []
        for y in range(s.ph):
            base = y * s.pw
            crow = []
            for x in range(s.pw):
                i = base + x
                crow.append(_age_color(s.age[i]) if s.cur[i] else None)
            grid.append(crow)
        return halfblock(grid)
    return component(draw, grow=1)


@app.view
def view(s):
    return card(
        row(b("life").fg((100, 255, 120)),
            dim_text(f"{s.name} · gen {s.gen} · pop {s.pop} · "
                     f"{'paused' if s.paused else 'running'}"),
            justify="between"),
        board(s),
        dim_text("space pause · enter step · +/- speed · c clear · r random · "
                 "g gun · p pulsar · q quit"),
        title="conway", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
