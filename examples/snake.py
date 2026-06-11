"""snake.py — a playable Snake game in the terminal, built on the App runtime.

  ↑/↓/←/→ or WASD to steer · p pause · r restart · q/Esc quit

    PYTHONPATH=src python examples/snake.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component

W, H = 24, 14  # play-field in cells

app = App("snake", inline=True, fps=12)   # fps drives the tick via on_key? no —
# the App re-renders every frame; we advance the snake from a frame counter.


def fresh_state(s):
    s.snake = [(W // 2, H // 2), (W // 2 - 1, H // 2), (W // 2 - 2, H // 2)]
    s.dir = (1, 0)
    s.pending = (1, 0)
    s.food = _spawn_food(s.snake)
    s.score = 0
    s.dead = False
    s.paused = False
    s.frame = 0


def _spawn_food(snake):
    while True:
        p = (random.randint(0, W - 1), random.randint(0, H - 1))
        if p not in snake:
            return p


app.state(snake=[], dir=(1, 0), pending=(1, 0), food=(0, 0),
          score=0, dead=False, paused=False, frame=0)
fresh_state(app.s)


def step(s):
    if s.dead or s.paused:
        return
    s.dir = s.pending
    hx, hy = s.snake[0]
    nx, ny = hx + s.dir[0], hy + s.dir[1]
    # walls wrap
    nx %= W
    ny %= H
    if (nx, ny) in s.snake:
        s.dead = True
        return
    s.snake.insert(0, (nx, ny))
    if (nx, ny) == s.food:
        s.score += 1
        s.food = _spawn_food(s.snake)
    else:
        s.snake.pop()


def _turn(s, d):
    # forbid 180° reversals
    if (d[0] == -s.dir[0] and d[1] == -s.dir[1]):
        return
    s.pending = d


@app.on("up", "w")
def _up(s): _turn(s, (0, -1))


@app.on("down", "s")
def _down(s): _turn(s, (0, 1))


@app.on("left", "a")
def _left(s): _turn(s, (-1, 0))


@app.on("right", "d")
def _right(s): _turn(s, (1, 0))


@app.on("p")
def _pause(s): s.paused = not s.paused


@app.on("r")
def _restart(s): fresh_state(s)


@app.on("q", "esc")
def _quit(s): app.stop()


def field(s):
    def draw(w, h):
        grid = [[" "] * W for _ in range(H)]
        fx, fy = s.food
        grid[fy][fx] = "●"
        for i, (x, y) in enumerate(s.snake):
            grid[y][x] = "█" if i == 0 else "▓"
        # one Element per ROW (not per cell) — cheap and overflow-safe
        return col(*[T("".join(grid[y])).fg("lime") for y in range(H)])
    return component(draw, height=H, width=W)


@app.view
def view(s):
    # tick the game each frame
    s.frame += 1
    if s.frame % 1 == 0:
        step(s)

    status = (T("PAUSED").fg("gold") if s.paused
              else T("GAME OVER").fg("red").bold if s.dead
              else T("playing").fg("lime"))
    return card(
        row(b("snake").fg("lime"), dim_text(f"score {s.score}"),
            status, justify="between"),
        card(field(s), border="round", border_color="slate", pad=0),
        dim_text("↑↓←→/wasd move · p pause · r restart · q quit"),
        title="snake", gap=1,
    )


if __name__ == "__main__":
    app.run()
