"""snake.py — Snake with half-block pixels, gradient body, particles & trails.

A faithful port of maya's `examples/snake.cpp`. The C++ original drives maya's
raw Canvas at 60fps, rendering the playfield as half-block pixels (▀ U+2580,
fg = top pixel, bg = bottom pixel) so every terminal cell holds two vertical
pixels. This port keeps the game logic byte-for-byte faithful and renders
through maya's native half-block surface (`halfblock`):

  • half-block pixel playfield (2 pixel rows per terminal cell)
  • snake body painted along a 4-stop gradient (green → cyan → blue → purple)
  • particle bursts when food is eaten (radial, fading)
  • ghost trails left behind the tail
  • three food kinds — Normal (red, +10), Speed (yellow, +15, speeds up),
    Mega (rainbow, +50, grows the snake by 4 extra segments)
  • a WALL / WRAP toggle (Shift-W)
  • speed ramps up every 5 foods eaten (tick_rate shrinks toward MIN_TICK)

  Keys: arrows / wasd / hjkl move · space pause · W wrap · r restart · q/Esc quit

    PYTHONPATH=src python examples/snake.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, component, halfblock  # noqa: E402

# ── Tunables (match snake.cpp) ───────────────────────────────────────────────

SNAKE_GRAD = 32
PARTICLE_LIFE = 15
TRAIL_LIFE = 10
INIT_TICK = 7
MIN_TICK = 3

# Fixed playfield in PIXELS (half-block: 2 pixel rows per terminal cell). The
# C++ derives this from the terminal size; we pin a sane fixed board so a huge
# fullscreen height can't size a giant grid. ROWS terminal cells -> 2*ROWS px.
COLS = 64          # pixel columns == terminal columns
ROWS = 22          # terminal cell rows for the playfield
PW = COLS          # playfield pixel width
PH = ROWS * 2      # playfield pixel height

BG = (10, 10, 18)  # background colour

# Food kinds
F_NORMAL, F_SPEED, F_MEGA = 0, 1, 2


# ── Colour helpers ───────────────────────────────────────────────────────────

def _lerp_color(a, b, t):
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


_GRAD_STOPS = (
    (57, 255, 20),    # neon green
    (0, 255, 200),    # cyan
    (30, 100, 255),   # blue
    (160, 40, 220),   # purple
)


def _snake_gradient(i):
    """4-stop gradient green → cyan → blue → purple over [0, SNAKE_GRAD)."""
    t = float(i) / float(SNAKE_GRAD - 1) * 3.0
    seg = min(int(t), 2)
    return _lerp_color(_GRAD_STOPS[seg], _GRAD_STOPS[seg + 1], t - seg)


# Precomputed style tables (colours, matching the C++ StylePool intern tables).
S_BORDER = (50, 50, 65)
S_SNAKE = [_snake_gradient(i) for i in range(SNAKE_GRAD)]

S_FOOD_NORMAL = []
S_FOOD_SPEED = []
S_FOOD_MEGA = []
for _i in range(8):
    _b = 0.5 + 0.5 * math.sin(_i * 3.14159 / 4.0)
    _v = int(120 + 135 * _b)
    S_FOOD_NORMAL.append((_v, int(30 * _b), int(30 * _b)))
    S_FOOD_SPEED.append((_v, _v, int(30 * _b)))
    _hue = float(_i) / 8.0 * 6.2832
    S_FOOD_MEGA.append((
        int(128 + 127 * math.sin(_hue)),
        int(128 + 127 * math.sin(_hue + 2.094)),
        int(128 + 127 * math.sin(_hue + 4.189)),
    ))

S_PARTICLE = []
for _i in range(PARTICLE_LIFE):
    _t = float(_i) / float(PARTICLE_LIFE - 1)
    _v = int(255 * (1.0 - _t))
    S_PARTICLE.append((_v, _v, _v // 2))

S_TRAIL = []
for _i in range(TRAIL_LIFE):
    _t = float(_i) / float(TRAIL_LIFE - 1)
    _v = int(60 * (1.0 - _t))
    S_TRAIL.append((20 + _v // 2, 40 + _v, 20 + _v // 3))


# ── Game state ───────────────────────────────────────────────────────────────

app = App("snake", inline=False, fps=60)


def reset_game(s):
    cx, cy = PW // 2, PH // 2
    s.snake = [(cx - i, cy) for i in range(5)]
    s.dx, s.dy = 1, 0
    s.qdx, s.qdy = 1, 0
    s.alive = True
    s.paused = False
    s.score = 0
    s.eaten = 0
    s.tick_rate = INIT_TICK
    s.frame = 0
    s.particles = []   # each: [x, y, vx, vy, life]
    s.trails = []      # each: [x, y, fade]
    spawn_food(s)


def spawn_food(s):
    occupied = set(s.snake)
    while True:
        fx = random.randint(1, PW - 2)
        fy = random.randint(1, PH - 2)
        if (fx, fy) not in occupied:
            break
    k = random.randint(0, 9)
    kind = F_NORMAL if k < 6 else F_SPEED if k < 9 else F_MEGA
    s.food = (fx, fy, kind)


def spawn_particles(s, x, y):
    n = 8 + random.randint(0, 8)
    for _ in range(n):
        a = random.uniform(0.0, 6.2832)
        sp = random.uniform(0.5, 2.5)
        s.particles.append([float(x), float(y),
                            math.cos(a) * sp, math.sin(a) * sp,
                            PARTICLE_LIFE])


app.state(snake=[], dx=1, dy=0, qdx=1, qdy=0, alive=True, paused=False,
          wrap=False, score=0, high=0, eaten=0, tick_rate=INIT_TICK, frame=0,
          food=(0, 0, F_NORMAL), particles=[], trails=[])
reset_game(app.s)


# ── Simulation ───────────────────────────────────────────────────────────────

def step(s):
    """Advance the snake one cell (called when frame % tick_rate == 0)."""
    s.dx, s.dy = s.qdx, s.qdy
    hx, hy = s.snake[0]
    nx, ny = hx + s.dx, hy + s.dy

    # Wall / wrap (playfield interior is [1, PW-2] × [1, PH-2]).
    if s.wrap:
        if nx < 1:
            nx = PW - 2
        elif nx >= PW - 1:
            nx = 1
        if ny < 1:
            ny = PH - 2
        elif ny >= PH - 1:
            ny = 1
    else:
        if nx < 1 or nx >= PW - 1 or ny < 1 or ny >= PH - 1:
            s.alive = False
            s.high = max(s.high, s.score)

    # Self collision.
    if s.alive:
        for sx, sy in s.snake:
            if sx == nx and sy == ny:
                s.alive = False
                s.high = max(s.high, s.score)
                break

    if not s.alive:
        return

    s.snake.insert(0, (nx, ny))
    fx, fy, kind = s.food
    if nx == fx and ny == fy:
        pts = 50 if kind == F_MEGA else 15 if kind == F_SPEED else 10
        s.score += pts
        s.eaten += 1
        if s.eaten % 5 == 0:
            s.tick_rate = max(MIN_TICK, s.tick_rate - 1)
        if kind == F_SPEED:
            s.tick_rate = max(MIN_TICK, s.tick_rate - 1)
        spawn_particles(s, fx, fy)
        # Grow: don't pop tail (add extra segments for mega).
        extra = 4 if kind == F_MEGA else 0
        for _ in range(extra):
            s.snake.append(s.snake[-1])
        spawn_food(s)
    else:
        # Trail from old tail position.
        tx, ty = s.snake[-1]
        s.trails.append([tx, ty, TRAIL_LIFE])
        s.snake.pop()


@app.on_frame
def _tick(s, dt):
    if s.alive and not s.paused and (s.frame % s.tick_rate) == 0:
        step(s)

    # Update particles.
    for p in s.particles:
        p[0] += p[2]
        p[1] += p[3]
        p[2] *= 0.92
        p[3] *= 0.92
        p[4] -= 1
    s.particles = [p for p in s.particles if p[4] > 0]

    # Update trails.
    for t in s.trails:
        t[2] -= 1
    s.trails = [t for t in s.trails if t[2] > 0]

    s.frame += 1


# ── Input ────────────────────────────────────────────────────────────────────

def _set_dir(s, dx, dy):
    # Forbid 180° reversal.
    if s.dx != -dx or s.dy != -dy:
        s.qdx, s.qdy = dx, dy


@app.on("up", "k", "w")
def _up(s): _set_dir(s, 0, -1)


@app.on("down", "j", "s")
def _down(s): _set_dir(s, 0, 1)


@app.on("left", "h", "a")
def _left(s): _set_dir(s, -1, 0)


@app.on("right", "l", "d")
def _right(s): _set_dir(s, 1, 0)


@app.on("space")
def _pause(s):
    if s.alive:
        s.paused = not s.paused


@app.on("W")
def _wrap(s):
    s.wrap = not s.wrap


@app.on("r")
def _restart(s):
    if not s.alive:
        reset_game(s)


@app.on("q", "esc")
def _quit(s):
    app.stop()


# ── Render ───────────────────────────────────────────────────────────────────

def _field(s):
    def draw(w, h):
        grid = [[None] * PW for _ in range(PH)]

        def px(x, y, color):
            if 0 <= x < PW and 0 <= y < PH:
                grid[y][x] = color

        # 1. Border.
        for x in range(PW):
            px(x, 0, S_BORDER)
            px(x, PH - 1, S_BORDER)
        for y in range(PH):
            px(0, y, S_BORDER)
            px(PW - 1, y, S_BORDER)

        # 2. Trails.
        for tx, ty, fade in s.trails:
            idx = TRAIL_LIFE - fade
            if 0 <= idx < TRAIL_LIFE:
                px(tx, ty, S_TRAIL[idx])

        # 3. Food (pulsing).
        fx, fy, kind = s.food
        if kind == F_NORMAL:
            fs = S_FOOD_NORMAL[(s.frame // 4) % 8]
        elif kind == F_SPEED:
            fs = S_FOOD_SPEED[(s.frame // 4) % 8]
        else:
            fs = S_FOOD_MEGA[(s.frame // 2) % 8]
        px(fx, fy, fs)

        # 4. Snake (gradient).
        n = len(s.snake)
        for i, (sx, sy) in enumerate(s.snake):
            grad = (i * (SNAKE_GRAD - 1) // (n - 1)) if n > 1 else 0
            px(sx, sy, S_SNAKE[grad])

        # 5. Particles.
        for p in s.particles:
            idx = PARTICLE_LIFE - p[4]
            if 0 <= idx < PARTICLE_LIFE:
                px(int(p[0] + 0.5), int(p[1] + 0.5), S_PARTICLE[idx])

        return halfblock(grid, bg=BG)

    return component(draw, grow=1)


_KINDS = {F_NORMAL: "Normal", F_SPEED: "Speed", F_MEGA: "Mega"}


@app.view
def view(s):
    speed_level = INIT_TICK - s.tick_rate + 1

    if not s.alive:
        status = T("GAME OVER — press r to restart").fg((255, 60, 60)).bold
    elif s.paused:
        status = T("PAUSED").fg((140, 140, 160)).bold
    else:
        status = T(f"{_KINDS[s.food[2]]} food").fg((100, 100, 120))

    # Status bar — mirrors the C++ bottom bar.
    bar = row(
        T("SNAKE").fg((57, 255, 20)).bold,
        T(f"  Score: ").fg((100, 100, 120)) + T(f"{s.score}").fg((255, 200, 60)).bold,
        T(f"  High: {s.high}").fg((100, 100, 120)),
        T(f"  Speed: {speed_level}").fg((100, 100, 120)),
        T(f"  {'WRAP' if s.wrap else 'WALL'}").fg(
            (57, 255, 20) if s.wrap else (100, 100, 120)).bold,
        status,
        gap=0, justify="between",
    )

    help_line = T(
        "[wasd/hjkl] move  [space] pause  [W] wrap  [r] restart  [q] quit"
    ).fg((60, 60, 75))

    return col(
        _field(s),
        bar,
        help_line,
        gap=0,
    )


if __name__ == "__main__":
    app.run()
