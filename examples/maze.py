"""maze.py — watch a maze generate, then solve itself.

A recursive-backtracker carves a perfect maze, animated cell by cell; then a
breadth-first search floods from the start, painting its frontier, until it
reaches the exit and back-traces the shortest path in gold. Toroidal-free grid
that fills the terminal. Half-block rendering (`▀`) for crisp 2× resolution.

  space — pause / resume       enter — single-step (while paused)
  +/-   — slower / faster       n — new maze (regenerate)
  r     — replay the solve      q/esc — quit
  click — set the START cell (re-solves)   right-click — set the GOAL

    PYTHONPATH=src python examples/maze.py
"""

import sys
import os
import random
from collections import deque

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    App, T, b, col, row, card, dim_text, component, badge, grow,
    scroll_state, viewport,
)
from maya_py import halfblock

# colours — walls are dark, carved passages are BRIGHT so the maze is visible.
WALL = (18, 20, 30)         # dark background between corridors
FLOOR = (120, 130, 165)     # carved passage (bright, high-contrast on WALL)
CARVE = (90, 230, 140)      # generator head
FRONTIER = (70, 120, 220)   # BFS visited
HEAD = (130, 210, 255)      # BFS frontier edge
PATH = (255, 205, 80)       # final shortest path
START_C = (90, 235, 140)
GOAL_C = (255, 95, 95)

# phases
GEN, SOLVE, DONE = 0, 1, 2


app = App.fullscreen("maze", mouse=True, fps=60)
s = app.state(
    cw=0, ch=0,              # maze grid size in CELLS (each cell = 2px block)
    grid=None,              # wall bitmask per cell: bit0=N bit1=E bit2=S bit3=W open
    phase=GEN,
    stack=None, visited=None,   # generator state
    bfs=None, came=None, seen=None, path=None,   # solver state
    start=(0, 0), goal=None,     # solve endpoints (goal None = far corner)
    speed=12, paused=False, step_once=False,
    vp=scroll_state(), pitch=3,  # painted-rect recorder + current px pitch
    flash=None,                  # (cx, cy, ttl) transient click ripple
)

# wall-open bits
N, E, S, W = 1, 2, 4, 8
DIRS = [(0, -1, N, S), (1, 0, E, W), (0, 1, S, N), (-1, 0, W, E)]


def new_maze(st, cw, ch):
    st.cw, st.ch = cw, ch
    st.grid = [0] * (cw * ch)
    st.visited = [False] * (cw * ch)
    st.stack = [(0, 0)]
    st.visited[0] = True
    st.phase = GEN
    st.bfs = st.came = st.seen = st.path = None


def gen_step(st):
    """One carve step of the recursive backtracker."""
    if not st.stack:
        start_solve(st)
        return
    cw, ch = st.cw, st.ch
    if cw == 0 or ch == 0:
        return
    x, y = st.stack[-1]
    nbrs = []
    for dx, dy, ob, nb in DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < cw and 0 <= ny < ch and not st.visited[ny * cw + nx]:
            nbrs.append((nx, ny, ob, nb))
    if nbrs:
        nx, ny, ob, nb = random.choice(nbrs)
        st.grid[y * cw + x] |= ob
        st.grid[ny * cw + nx] |= nb
        st.visited[ny * cw + nx] = True
        st.stack.append((nx, ny))
    else:
        st.stack.pop()


def start_solve(st):
    cw, ch = st.cw, st.ch
    if cw == 0 or ch == 0:
        return
    sx, sy = st.start
    sx = max(0, min(cw - 1, sx)); sy = max(0, min(ch - 1, sy))
    st.phase = SOLVE
    st.bfs = deque([(sx, sy)])
    st.seen = [False] * (cw * ch)
    st.came = [None] * (cw * ch)
    st.seen[sy * cw + sx] = True
    st.path = None


def solve_step(st):
    cw, ch = st.cw, st.ch
    goal = st.goal if st.goal is not None else (cw - 1, ch - 1)
    if not st.bfs:
        st.phase = DONE
        return
    x, y = st.bfs.popleft()
    if (x, y) == goal:
        # back-trace
        path = []
        cur = (x, y)
        while cur is not None:
            path.append(cur)
            cur = st.came[cur[1] * cw + cur[0]]
        st.path = path
        st.phase = DONE
        return
    cell = st.grid[y * cw + x]
    for dx, dy, ob, nb in DIRS:
        if not (cell & ob):
            continue
        nx, ny = x + dx, y + dy
        if 0 <= nx < cw and 0 <= ny < ch and not st.seen[ny * cw + nx]:
            st.seen[ny * cw + nx] = True
            st.came[ny * cw + nx] = (x, y)
            st.bfs.append((nx, ny))


def advance(st):
    # Fade the click ripple every frame (before any early-return) so it
    # animates even while the maze is paused or not yet sized.
    if st.flash and st.flash[2] > 0:
        st.flash = (st.flash[0], st.flash[1], st.flash[2] - 1)
    if st.grid is None or st.cw == 0 or st.ch == 0:
        return                       # not sized yet (first frame, before render)
    if st.paused and not st.step_once:
        return
    steps = 1 if st.step_once else max(1, st.speed)
    st.step_once = False
    for _ in range(steps):
        if st.phase == GEN:
            gen_step(st)
        elif st.phase == SOLVE:
            solve_step(st)
        else:
            break


def draw_field(st):
    # Real painted viewport height (rows). 0 on the very first frame, then
    # stable thereafter. Width comes from the component's own `w` arg (always
    # correct); height is NEVER trusted from `h` (fullscreen hands it a 2**20
    # sentinel), so we drive it from the viewport's recorded painted rect.
    _, _, _, vph = st.vp.viewport_bounds

    def render(w, h):
        # each maze cell is a 2×2 pixel block + 1px wall gap → 3px pitch.
        pitch = 3
        st.pitch = pitch
        # `h` is the 2**20 fullscreen sentinel — NEVER size off it. Wait for the
        # viewport's real painted height (vph) before generating; until then
        # paint a one-row placeholder so the layout can settle and report vph.
        if vph <= 0:
            return halfblock([[WALL] * max(16, w), [WALL] * max(16, w)], bg=WALL)
        cell_rows = vph
        pw = max(16, w)
        ph = max(16, cell_rows * 2)
        cw = max(4, (pw - 1) // pitch)
        ch = max(4, (ph - 1) // pitch)
        # Only (re)generate on a genuine size change (real resize). Once latched
        # the ±1 jitter from layout rounding is ignored so a carve isn't reset.
        if st.grid is None or abs(cw - st.cw) > 1 or abs(ch - st.ch) > 1:
            new_maze(st, cw, ch)
        else:
            cw, ch = st.cw, st.ch    # keep latched size, just repaint

        # Fill with WALL (dark); carved passages are painted BRIGHT on top so
        # the maze structure stands out against the wall background.
        grid = [[WALL] * pw for _ in range(ph)]

        def block(cx, cy, color):
            ox, oy = cx * pitch + 1, cy * pitch + 1
            for yy in range(2):
                for xx in range(2):
                    px, py = ox + xx, oy + yy
                    if 0 <= px < pw and 0 <= py < ph:
                        grid[py][px] = color

        def corridor(cx, cy, ddir, color):
            # paint the 1px gap between this cell and its neighbour
            ox, oy = cx * pitch + 1, cy * pitch + 1
            if ddir == E:
                for yy in range(2):
                    if oy + yy < ph and ox + 2 < pw:
                        grid[oy + yy][ox + 2] = color
            elif ddir == S:
                for xx in range(2):
                    if oy + 2 < ph and ox + xx < pw:
                        grid[oy + 2][ox + xx] = color

        # draw all carved cells as floor + open corridors
        for cy in range(st.ch):
            for cx in range(st.cw):
                cell = st.grid[cy * st.cw + cx]
                if st.visited and st.visited[cy * st.cw + cx]:
                    block(cx, cy, FLOOR)
                if cell & E:
                    corridor(cx, cy, E, FLOOR)
                if cell & S:
                    corridor(cx, cy, S, FLOOR)

        # solver overlay
        if st.phase in (SOLVE, DONE) and st.seen:
            for cy in range(st.ch):
                for cx in range(st.cw):
                    if st.seen[cy * st.cw + cx]:
                        block(cx, cy, FRONTIER)
                        cell = st.grid[cy * st.cw + cx]
                        if cell & E and cx + 1 < st.cw and st.seen[cy * st.cw + cx + 1]:
                            corridor(cx, cy, E, FRONTIER)
                        if cell & S and cy + 1 < st.ch and st.seen[(cy + 1) * st.cw + cx]:
                            corridor(cx, cy, S, FRONTIER)
            for (cx, cy) in (st.bfs or ()):
                block(cx, cy, HEAD)

        # final path
        if st.path:
            prev = None
            for (cx, cy) in st.path:
                block(cx, cy, PATH)
                if prev is not None:
                    px, py = prev
                    if px == cx and py == cy - 1:
                        corridor(cx, py, S, PATH)
                    elif px == cx and py == cy + 1:
                        corridor(cx, cy, S, PATH)
                    elif py == cy and px == cx - 1:
                        corridor(px, cy, E, PATH)
                    elif py == cy and px == cx + 1:
                        corridor(cx, cy, E, PATH)
                prev = (cx, cy)

        # generator head
        if st.phase == GEN and st.stack:
            hx, hy = st.stack[-1]
            block(hx, hy, CARVE)

        # start / goal markers (click-configurable) — drawn LAST and made
        # unmistakable: a bright 2×2 core plus a one-pixel contrast ring so a
        # click is obviously registered even under the BFS frontier wash.
        def marker(cx, cy, core, ring):
            ox, oy = cx * pitch + 1, cy * pitch + 1
            # ring: paint the 8 surrounding pixels (incl. wall gaps) first
            for dy in range(-1, 3):
                for dx in range(-1, 3):
                    px, py = ox + dx, oy + dy
                    if 0 <= px < pw and 0 <= py < ph:
                        grid[py][px] = ring
            # core: the cell's own 2×2 block on top
            for dy in range(2):
                for dx in range(2):
                    px, py = ox + dx, oy + dy
                    if 0 <= px < pw and 0 <= py < ph:
                        grid[py][px] = core

        sx, sy = st.start
        gx, gy = st.goal if st.goal is not None else (st.cw - 1, st.ch - 1)
        marker(sx, sy, START_C, (235, 255, 240))
        marker(gx, gy, GOAL_C, (255, 235, 235))

        # click ripple: a transient ring that fades over a few frames so the
        # user sees exactly where their last click landed. The ttl is
        # decremented per-frame in advance() (NOT here — this render fn is a
        # cached component callback and may not run every frame).
        if st.flash and st.flash[2] > 0:
            fcx, fcy, ttl = st.flash
            ring = (255, 255, 255)
            ox, oy = fcx * pitch + 1, fcy * pitch + 1
            rad = 4 - ttl                # grows outward as it fades
            for dy in range(-rad, rad + 2):
                for dx in range(-rad, rad + 2):
                    if abs(dx) == rad or abs(dy) == rad or \
                       abs(dx) == rad + 1 or abs(dy) == rad + 1:
                        px, py = ox + dx, oy + dy
                        if 0 <= px < pw and 0 <= py < ph:
                            grid[py][px] = ring

        return halfblock(grid, bg=WALL)

    # Wrap in a viewport so its painted rect feeds precise mouse hit-testing.
    # grow=1 (no fixed height) lets the field claim the whole card body; the
    # render fn reads the resulting painted height back via vp.viewport_bounds.
    field = component(render, grow=1)
    return viewport(field, st.vp, grow=1)


def maze_cell_at(st, col_, row_):
    """Screen cell → maze cell. The field is half-block rendered (2 vertical
    pixels per screen row) on a 3-pixel cell pitch with a 1-pixel wall offset:
    cell (mx,my) owns pixels px∈{mx*3+1, mx*3+2}, py∈{my*3+1, my*3+2}.
    Invert from the clicked row's pixel MIDPOINT so an odd pitch can't drift
    the mapping by a cell as you move down. Returns None outside the maze."""
    x, y, w, h = st.vp.viewport_bounds
    if (w == 0 and h == 0) or st.cw == 0:
        return None
    cx = (col_ - 1) - x               # px column offset (1 col = 1 px)
    ry = (row_ - 1) - y               # screen-row offset into the field
    if cx < 0 or ry < 0:
        return None
    px = cx                           # horizontal pixel
    py = ry * 2 + 1                   # midpoint of the row's 2-pixel span
    mx = (px - 1) // st.pitch
    my = (py - 1) // st.pitch
    # snap pixels that land in the 1-px wall gap onto the nearer cell body
    if 0 <= mx < st.cw and 0 <= my < st.ch:
        return (mx, my)
    return None


@app.on_click("left")
def _set_start(st, col_, row_):
    """Left-click: move the START here and (re)solve from it."""
    cell = maze_cell_at(st, col_, row_)
    if not cell:
        return
    st.flash = (cell[0], cell[1], 3)     # ripple so the click is visible
    st.start = cell
    # If the maze is still carving, just stage the start; otherwise re-solve
    # from scratch so the BFS visibly re-floods from the new origin.
    if st.phase != GEN:
        st.path = None
        start_solve(st)


@app.on_click("right")
def _set_goal(st, col_, row_):
    """Right-click: move the GOAL here and (re)solve toward it."""
    cell = maze_cell_at(st, col_, row_)
    if not cell:
        return
    st.flash = (cell[0], cell[1], 3)
    st.goal = cell
    if st.phase != GEN:
        st.path = None
        start_solve(st)


@app.on("space")
def _pause(st): st.paused = not st.paused


@app.on("enter")
def _step(st): st.step_once = True


@app.on("+", "=")
def _faster(st): st.speed = min(60, st.speed + 2)


@app.on("-", "_")
def _slower(st): st.speed = max(1, st.speed - 2)


@app.on("n")
def _new(st):
    if st.cw and st.ch:
        st.start, st.goal = (0, 0), None
        new_maze(st, st.cw, st.ch)


@app.on("r")
def _replay(st):
    if st.phase == DONE or st.phase == SOLVE:
        start_solve(st)


@app.on("q", "esc")
def _quit(st): app.stop()


@app.view
def view(st):
    advance(st)

    phase_badge = {
        GEN: badge("carving", kind="success"),
        SOLVE: badge("solving", kind="info"),
        DONE: badge("solved", kind=""),
    }[st.phase]

    extra = ""
    if st.phase == DONE and st.path:
        extra = f"path {len(st.path)} cells"
    elif st.phase == SOLVE and st.seen:
        extra = f"visited {sum(st.seen)}"
    elif st.phase == GEN and st.visited:
        extra = f"carved {sum(st.visited)}/{st.cw * st.ch}"

    header = row(
        b("maze").fg("lime"),
        dim_text(f"{st.cw}×{st.ch} cells"),
        phase_badge,
        dim_text(extra),
        badge(f"{st.speed}×", kind="info"),
        badge("paused", kind="warning") if st.paused else dim_text(""),
        gap=2, justify="between",
    )

    body = grow(card(draw_field(st), border="round", border_color="slate",
                     pad=0, grow=1))

    return card(
        header,
        body,
        dim_text("click set-start · right-click set-goal · space pause · "
                 "enter step · +/- speed · n new · r re-solve · q quit"),
        title="recursive-backtracker · BFS solve", gap=1, height="100%",
    )


if __name__ == "__main__":
    app.run()
