"""breakout.py — a Breakout / Arkanoid clone, half-block rendered.

Multi-hit coloured bricks, a comet trail on the ball, particle bursts on hit,
score and lives. Bounce physics off the paddle vary the angle by where you hit.

  ←/→ or a/d move · space launch / pause · r restart · q/esc quit

    PYTHONPATH=src python examples/breakout.py
"""

import math
import random

import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component
from maya_py import halfblock

PW, PH = 80, 48
BROWS, BCOLS = 7, 10
BW = PW // BCOLS                       # brick width in pixels
BH = 3
TOP = 4                                # bricks start row
TRAIL = 7

_sized = False                         # become True after first layout

ROW_CLR = [
    (255, 60, 60), (255, 140, 30), (255, 220, 40), (50, 220, 80),
    (40, 210, 230), (70, 100, 255), (160, 80, 220),
]
ROW_PTS = [70, 60, 50, 40, 30, 20, 10]

app = App.inline("breakout", fps=30)
app.state(bricks=[], px=PW / 2, padw=14, ball=None, trail=[], parts=[],
          score=0, lives=3, level=1, stuck=True, paused=False, over=False,
          win=False, kl=False, kr=False)


def reset_bricks(s):
    # bricks[r][c] = hp (0 = gone)
    s.bricks = [[2 if r < 2 else 1 for c in range(BCOLS)] for r in range(BROWS)]


def reset_ball(s):
    s.ball = [s.px, PH - BH - 3, 0.0, 0.0]
    s.trail = []
    s.stuck = True


def new_game(s):
    s.score = 0
    s.lives = 3
    s.level = 1
    s.px = PW / 2
    s.padw = 14
    s.parts = []
    s.over = False
    s.win = False
    reset_bricks(s)
    reset_ball(s)


new_game(app.s)


def launch(s):
    if s.stuck:
        s.stuck = False
        ang = random.uniform(-0.4, 0.4)
        s.ball[2] = math.sin(ang) * 0.9
        s.ball[3] = -0.9


def _burst(s, x, y, c):
    for _ in range(8):
        a = random.uniform(0, math.tau)
        sp = random.uniform(0.3, 1.0)
        s.parts.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 12, c])


@app.on("left", "a")
def _l(s): s.px = max(s.padw / 2, s.px - 3)


@app.on("right", "d")
def _r(s): s.px = min(PW - s.padw / 2, s.px + 3)


@app.on("space")
def _sp(s):
    if s.over or s.win:
        new_game(s)
    elif s.stuck:
        launch(s)
    else:
        s.paused = not s.paused


@app.on("r")
def _restart(s): new_game(s)


app.quit_on("q", "esc")


def step(s):
    if s.paused or s.over or s.win:
        return
    if s.stuck:
        s.ball[0] = s.px
        return
    bx, by, vx, vy = s.ball
    # trail
    s.trail.insert(0, (bx, by))
    s.trail = s.trail[:TRAIL]
    bx += vx
    by += vy
    # walls
    if bx <= 0:
        bx = 0
        vx = -vx
    elif bx >= PW - 1:
        bx = PW - 1
        vx = -vx
    if by <= 0:
        by = 0
        vy = -vy
    # paddle
    pad_y = PH - 2
    if vy > 0 and pad_y - 1 <= by <= pad_y + 1:
        if s.px - s.padw / 2 <= bx <= s.px + s.padw / 2:
            off = (bx - s.px) / (s.padw / 2)
            ang = off * 1.0
            spd = math.hypot(vx, vy)
            vx = math.sin(ang) * spd
            vy = -abs(math.cos(ang) * spd)
            by = pad_y - 1
    # bricks
    col_ = int(bx // BW)
    rowf = (by - TOP) / BH
    rr = int(rowf)
    if 0 <= rr < BROWS and 0 <= col_ < BCOLS and s.bricks[rr][col_] > 0:
        s.bricks[rr][col_] -= 1
        s.score += ROW_PTS[rr]
        _burst(s, bx, by, ROW_CLR[rr])
        vy = -vy
    # bottom — lose ball
    if by >= PH - 1:
        s.lives -= 1
        if s.lives <= 0:
            s.over = True
        else:
            reset_ball(s)
        return
    s.ball = [bx, by, vx, vy]
    # win check
    if all(hp == 0 for rowb in s.bricks for hp in rowb):
        s.win = True
    # particles
    alive = []
    for p in s.parts:
        p[0] += p[2]; p[1] += p[3]; p[4] -= 1
        if p[4] > 0:
            alive.append(p)
    s.parts = alive


def field(s):
    def draw(w, h):
        global PW, PH, BW, _sized
        h = max(8, min(h, 60))
        nw, nh = w, h * 2
        if nw != PW or nh != PH:
            PW, PH = nw, nh
            BW = PW // BCOLS
            if not _sized:
                _sized = True
            new_game(s)
        step(s)
        grid = [[None] * PW for _ in range(PH)]
        # bricks
        for r in range(BROWS):
            for c in range(BCOLS):
                hp = s.bricks[r][c]
                if hp <= 0:
                    continue
                clr = ROW_CLR[r]
                if hp == 1:
                    clr = tuple(int(v * 0.55) for v in clr)
                for yy in range(BH - 1):
                    for xx in range(BW - 1):
                        grid[TOP + r * BH + yy][c * BW + xx] = clr
        # trail
        for i, (tx, ty) in enumerate(s.trail):
            f = 1.0 - i / TRAIL
            x, y = int(tx), int(ty)
            if 0 <= x < PW and 0 <= y < PH:
                grid[y][x] = (int(120 * f), int(180 * f), int(255 * f))
        # ball
        bx, by = int(s.ball[0]), int(s.ball[1])
        if 0 <= bx < PW and 0 <= by < PH:
            grid[by][bx] = (255, 255, 255)
        # paddle
        py = PH - 2
        x0 = int(s.px - s.padw / 2)
        for x in range(x0, x0 + s.padw):
            if 0 <= x < PW:
                grid[py][x] = (200, 220, 255)
                grid[py + 1][x] = (120, 150, 220) if py + 1 < PH else None
        # particles
        for p in s.parts:
            x, y = int(p[0]), int(p[1])
            if 0 <= x < PW and 0 <= y < PH:
                grid[y][x] = p[5]
        return halfblock(grid)
    return component(draw, grow=1)


@app.view
def view(s):
    hearts = "♥ " * s.lives
    if s.over:
        status = T("GAME OVER — space to restart").fg("red").bold
    elif s.win:
        status = T("YOU WIN! — space to restart").fg("lime").bold
    elif s.stuck:
        status = T("space to launch").fg("gold")
    elif s.paused:
        status = T("PAUSED").fg("gold")
    else:
        status = dim_text("playing")
    return card(
        row(b("breakout").fg((255, 220, 40)),
            dim_text(f"score {s.score}"),
            T(hearts).fg("red"),
            status, justify="between"),
        field(s),
        dim_text("←→/ad move · space launch/pause · r restart · q quit"),
        title="arkanoid", gap=0, pad=0,
    )


if __name__ == "__main__":
    app.run()
