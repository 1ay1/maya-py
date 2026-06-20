"""fps.py — FPS: a Wolfenstein-style raycaster.

A faithful port of maya's `examples/fps.cpp`. DDA raycasting against a tile
map with real brick-textured walls (running-bond mortar lines, per-brick
colour variation, surface roughness, edge weathering), cool stone floors,
a dark torch-lit dungeon with ten flickering torches doing inverse-square
lighting, enemies (grunt/fast/heavy) with simple chase AI, health/ammo
pickups, a bobbing weapon with muzzle flash + recoil, a crosshair, a
vignette + damage-flash post-process, a minimap, and half-block rendering.

The C++ original drives maya's raw Canvas at 30fps across every CPU core
(`g_pixel_w = w`, `g_pixel_h = (h-1)*2`). This port keeps the math faithful
and renders through maya's native half-block surface (`halfblock`), but the
per-column raycast + per-pixel texturing runs in pure Python — so the
internal pixel buffer is CAPPED to MAX_PW × MAX_PH (independent of the
terminal size) to keep frame time bounded. Only the resolution is bounded;
the raycasting/texturing/lighting math is byte-for-byte the C++. Raise
MAX_PW / MAX_PH to trade framerate for detail.

  Keys: WASD/arrows move · ,/. turn · space shoot · m minimap · r restart · q/esc quit

    PYTHONPATH=src python examples/fps.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, component, halfblock  # noqa: E402

# Pure-Python raycasting is far slower than the threaded C++. We render into a
# small internal pixel buffer whose size is CAPPED (independent of the terminal
# size) so a large window can't push frame time to seconds — the half-block
# field is then emitted at its natural (small) size. Raise MAX_PW / MAX_PH for
# more detail at lower framerate.
MAX_PW = 96
MAX_PH = 56

PI = 3.14159265


# ── Math ────────────────────────────────────────────────────────────────────

def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = clampf((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def col_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def col_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def col_lerp(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def col_clamp(c):
    return (clampf(c[0], 0, 1), clampf(c[1], 0, 1), clampf(c[2], 0, 1))


def hash2(x, y):
    h = math.sin(x * 127.1 + y * 311.7) * 43758.5453
    return h - math.floor(h)


def value_noise(x, y):
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    a = hash2(ix, iy)
    b = hash2(ix + 1, iy)
    c = hash2(ix, iy + 1)
    d = hash2(ix + 1, iy + 1)
    return lerp(lerp(a, b, fx), lerp(c, d, fx), fy)


def fbm(x, y, octaves):
    s = 0.0
    amp = 0.5
    for _ in range(octaves):
        s += value_noise(x, y) * amp
        x *= 2.17
        y *= 2.17
        amp *= 0.5
    return s


# ── Map ─────────────────────────────────────────────────────────────────────

MAP_W = 24
MAP_H = 24

# 0=empty, 1-5=wall types, 6=door, 9=exit
G_MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 2, 2, 2, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 0, 0, 4, 4, 4, 0, 0, 1],
    [1, 0, 0, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 4, 0, 0, 1],
    [1, 0, 0, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 4, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 6, 3, 3, 3, 0, 0, 0, 0, 0, 4, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 4, 4, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 5, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 5, 0, 5, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 0, 0, 1],
    [1, 5, 0, 5, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 1],
    [1, 5, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 1],
    [1, 5, 0, 5, 0, 0, 2, 2, 6, 2, 2, 0, 0, 0, 0, 0, 3, 0, 0, 5, 5, 5, 0, 1],
    [1, 5, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 5, 0, 5, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 9, 5, 0, 1],
    [1, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 5, 5, 5, 0, 1],
    [1, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 4, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 4, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


# ── Wall materials ──────────────────────────────────────────────────────────
# Each: (base color, mortar color, brick_w, brick_h)
WALL_MATS = [
    ((0, 0, 0), (0, 0, 0), 1, 1),                                  # 0: unused
    ((0.52, 0.10, 0.07), (0.22, 0.18, 0.15), 0.25, 0.12),         # 1: classic red brick
    ((0.55, 0.12, 0.06), (0.24, 0.20, 0.16), 0.20, 0.10),         # 2: red-orange brick
    ((0.40, 0.07, 0.06), (0.18, 0.14, 0.12), 0.22, 0.11),         # 3: dark crimson brick
    ((0.48, 0.14, 0.08), (0.20, 0.16, 0.13), 0.28, 0.14),         # 4: warm brick
    ((0.44, 0.10, 0.07), (0.19, 0.15, 0.13), 0.25, 0.13),         # 5: old dark brick
    ((0.50, 0.40, 0.12), (0.25, 0.20, 0.10), 0.30, 0.15),         # 6: gold door
    ((0, 0, 0), (0, 0, 0), 1, 1),                                  # 7: unused
    ((0, 0, 0), (0, 0, 0), 1, 1),                                  # 8: unused
    ((0.58, 0.08, 0.05), (0.25, 0.12, 0.08), 0.22, 0.12),         # 9: exit
]


# ── Torches ─────────────────────────────────────────────────────────────────
# (x, y, color, intensity)
G_TORCHES = [
    (1.5, 1.5, (1.0, 0.75, 0.35), 5.0),
    (11.5, 1.5, (1.0, 0.75, 0.35), 5.0),
    (22.5, 1.5, (0.5, 0.6, 0.9), 4.0),
    (1.5, 8.5, (1.0, 0.75, 0.35), 5.0),
    (22.5, 8.5, (1.0, 0.70, 0.30), 5.0),
    (11.5, 11.5, (1.0, 0.80, 0.40), 5.5),
    (1.5, 22.5, (1.0, 0.75, 0.35), 5.0),
    (22.5, 22.5, (0.4, 0.75, 0.45), 4.0),
    (11.5, 17.5, (1.0, 0.60, 0.25), 5.5),
    (20.5, 15.5, (1.0, 0.30, 0.12), 6.0),
]
NUM_TORCHES = len(G_TORCHES)


# ── Constants ───────────────────────────────────────────────────────────────

FOV = PI / 3.0
MOVE_SPD = 0.10
TURN_SPD = 0.05
MOVE_HOLD_FRAMES = 5
TURN_HOLD_FRAMES = 3
COLLISION_R = 0.2

# Key actions
K_FWD, K_BACK, K_LEFT, K_RIGHT, K_TURN_L, K_TURN_R, K_COUNT = range(7)


# ── Game state ──────────────────────────────────────────────────────────────

class G:
    px = 2.5
    py = 2.5
    pa = 0.0
    health = 100
    ammo = 50
    score = 0
    kills = 0
    won = False
    dead = False
    show_map = True
    frame = 0
    flash = 0
    hit_flash = 0
    weapon_bob = 0.0
    key_last = [-100, -100, -100, -100, -100, -100]
    enemies = []   # each: dict(x, y, hp, max_hp, type, timer, active, alert, dist)
    pickups = []   # each: dict(x, y, type, taken)

    # Internal pixel buffer (flat list of [r,g,b] floats 0..255)
    pixels = []
    pw = 0
    ph = 0
    zbuf = []


def spawn_enemies():
    specs = [
        (11.5, 3.5, 30, 0),
        (20.5, 5.5, 30, 0),
        (3.5, 12.5, 20, 1),
        (8.5, 12.5, 50, 2),
        (18.5, 11.5, 30, 0),
        (8.5, 18.5, 20, 1),
        (13.5, 19.5, 30, 0),
        (6.5, 6.5, 50, 2),
    ]
    G.enemies = [
        {"x": x, "y": y, "hp": hp, "max_hp": hp, "type": t,
         "timer": 0.0, "active": True, "alert": False, "dist": 0.0}
        for (x, y, hp, t) in specs
    ]


def spawn_pickups():
    specs = [
        (4.5, 1.5, 1), (11.5, 7.5, 0), (1.5, 11.5, 1), (16.5, 1.5, 0),
        (22.5, 8.5, 1), (7.5, 17.5, 0), (14.5, 17.5, 1), (22.5, 17.5, 0),
    ]
    G.pickups = [{"x": x, "y": y, "type": t, "taken": False} for (x, y, t) in specs]


def reset_game():
    G.px = 2.5
    G.py = 2.5
    G.pa = 0.0
    G.health = 100
    G.ammo = 50
    G.score = 0
    G.kills = 0
    G.dead = False
    G.won = False
    G.flash = 0
    G.hit_flash = 0
    G.frame = 0
    G.weapon_bob = 0.0
    G.key_last = [-100, -100, -100, -100, -100, -100]
    spawn_enemies()
    spawn_pickups()


# ── Pixel buffer ────────────────────────────────────────────────────────────

def px_set(x, y, r, g, b):
    if 0 <= x < G.pw and 0 <= y < G.ph:
        i = (y * G.pw + x) * 3
        p = G.pixels
        p[i] = r
        p[i + 1] = g
        p[i + 2] = b


def px_blend(x, y, c, alpha):
    if x < 0 or x >= G.pw or y < 0 or y >= G.ph:
        return
    i = (y * G.pw + x) * 3
    p = G.pixels
    p[i] = clampf(lerp(p[i] / 255.0, c[0], alpha) * 255.0, 0, 255)
    p[i + 1] = clampf(lerp(p[i + 1] / 255.0, c[1], alpha) * 255.0, 0, 255)
    p[i + 2] = clampf(lerp(p[i + 2] / 255.0, c[2], alpha) * 255.0, 0, 255)


def px_get(x, y):
    if 0 <= x < G.pw and 0 <= y < G.ph:
        i = (y * G.pw + x) * 3
        p = G.pixels
        return (p[i], p[i + 1], p[i + 2])
    return (0, 0, 0)


def buffer_resize(pw, ph):
    if pw != G.pw or ph != G.ph:
        G.pw = pw
        G.ph = ph
        G.pixels = [0.0] * (pw * ph * 3)
        G.zbuf = [0.0] * pw


# ── Collision ───────────────────────────────────────────────────────────────

def is_solid(mx, my):
    if mx < 0 or mx >= MAP_W or my < 0 or my >= MAP_H:
        return True
    t = G_MAP[my][mx]
    return t != 0 and t != 6


def can_move(nx, ny):
    r = COLLISION_R
    return (not is_solid(int(nx - r), int(ny - r))
            and not is_solid(int(nx + r), int(ny - r))
            and not is_solid(int(nx - r), int(ny + r))
            and not is_solid(int(nx + r), int(ny + r)))


# ── Game logic ──────────────────────────────────────────────────────────────

def shoot():
    if G.ammo <= 0 or G.dead:
        return
    G.ammo -= 1
    G.flash = 4

    dx = math.cos(G.pa)
    dy = math.sin(G.pa)
    best_dist = 999.0
    hit = None

    for e in G.enemies:
        if not e["active"]:
            continue
        ex = e["x"] - G.px
        ey = e["y"] - G.py
        proj = ex * dx + ey * dy
        if proj < 0.1:
            continue
        perp = abs(ex * (-dy) + ey * dx)
        if perp < 0.3 + proj * 0.04 and proj < best_dist:
            best_dist = proj
            hit = e

    if hit is not None:
        dmg = max(5, 25 - int(best_dist * 2.0))
        hit["hp"] -= dmg
        hit["alert"] = True
        if hit["hp"] <= 0:
            hit["active"] = False
            G.score += (hit["type"] + 1) * 100
            G.kills += 1


def tick(dt):
    if G.dead or G.won:
        return

    G.frame += 1
    if G.flash > 0:
        G.flash -= 1
    if G.hit_flash > 0:
        G.hit_flash -= 1

    def held(k):
        window = TURN_HOLD_FRAMES if (k == K_TURN_L or k == K_TURN_R) else MOVE_HOLD_FRAMES
        return (G.frame - G.key_last[k]) < window

    move_fwd = (1.0 if held(K_FWD) else 0.0) - (1.0 if held(K_BACK) else 0.0)
    move_strafe = (1.0 if held(K_RIGHT) else 0.0) - (1.0 if held(K_LEFT) else 0.0)
    turn = (1.0 if held(K_TURN_R) else 0.0) - (1.0 if held(K_TURN_L) else 0.0)

    G.pa += turn * TURN_SPD

    fwd_x = math.cos(G.pa)
    fwd_y = math.sin(G.pa)
    right_x = math.cos(G.pa + PI / 2.0)
    right_y = math.sin(G.pa + PI / 2.0)

    mx = fwd_x * move_fwd + right_x * move_strafe
    my = fwd_y * move_fwd + right_y * move_strafe

    ml = math.sqrt(mx * mx + my * my)
    if ml > 0.01:
        mx /= ml
        my /= ml
        spd = MOVE_SPD * min(ml, 3.0)
        nx = G.px + mx * spd
        ny = G.py + my * spd
        if can_move(nx, G.py):
            G.px = nx
        if can_move(G.px, ny):
            G.py = ny
        G.weapon_bob += ml * 0.3

    # Check exit
    if (0 <= int(G.px) < MAP_W and 0 <= int(G.py) < MAP_H
            and G_MAP[int(G.py)][int(G.px)] == 9):
        G.won = True
        G.score += G.health * 10

    # Pickups
    for p in G.pickups:
        if p["taken"]:
            continue
        dx = G.px - p["x"]
        dy = G.py - p["y"]
        if dx * dx + dy * dy < 0.5:
            p["taken"] = True
            if p["type"] == 0:
                G.health = min(100, G.health + 25)
            else:
                G.ammo = min(99, G.ammo + 15)
            G.score += 50

    # Enemy AI
    for e in G.enemies:
        if not e["active"]:
            continue
        dx = G.px - e["x"]
        dy = G.py - e["y"]
        e["dist"] = math.sqrt(dx * dx + dy * dy)
        if e["dist"] < 8.0:
            e["alert"] = True
        if not e["alert"]:
            continue
        e["timer"] += dt

        speed = 2.5 if e["type"] == 1 else (1.0 if e["type"] == 2 else 1.8)
        if e["dist"] > 1.2:
            emx = dx / e["dist"] * speed * dt
            emy = dy / e["dist"] * speed * dt
            enx = e["x"] + emx
            eny = e["y"] + emy
            if (0 <= int(enx) < MAP_W and 0 <= int(eny) < MAP_H
                    and G_MAP[int(eny)][int(enx)] == 0):
                e["x"] = enx
                e["y"] = eny
        if e["dist"] < 1.5 and e["timer"] > 0.8:
            e["timer"] = 0.0
            dmg = 15 if e["type"] == 2 else (8 if e["type"] == 1 else 10)
            G.health -= dmg
            G.hit_flash = 6
            if G.health <= 0:
                G.health = 0
                G.dead = True


# ── Raycasting ──────────────────────────────────────────────────────────────

def cast_ray(angle):
    """Returns (dist, wall_type, wall_x, side, map_x, map_y)."""
    dx = math.cos(angle)
    dy = math.sin(angle)
    mx = int(G.px)
    my = int(G.py)
    delta_x = 1e30 if dx == 0.0 else abs(1.0 / dx)
    delta_y = 1e30 if dy == 0.0 else abs(1.0 / dy)
    step_x = -1 if dx < 0 else 1
    step_y = -1 if dy < 0 else 1
    side_x = (G.px - mx) * delta_x if dx < 0 else (mx + 1.0 - G.px) * delta_x
    side_y = (G.py - my) * delta_y if dy < 0 else (my + 1.0 - G.py) * delta_y

    side_hit = False
    for _ in range(64):
        if side_x < side_y:
            side_x += delta_x
            mx += step_x
            side_hit = False
        else:
            side_y += delta_y
            my += step_y
            side_hit = True
        if mx < 0 or mx >= MAP_W or my < 0 or my >= MAP_H:
            break
        t = G_MAP[my][mx]
        if t > 0:
            if not side_hit:
                perp = side_x - delta_x
                wx = G.py + perp * dy
            else:
                perp = side_y - delta_y
                wx = G.px + perp * dx
            wx -= math.floor(wx)
            return (perp, t, wx, side_hit, mx, my)
    return (64.0, 0, 0.0, False, 0, 0)


# ── Lighting ────────────────────────────────────────────────────────────────

def compute_light(wx, wy):
    # Cool dim ambient — dark dungeon baseline
    total = [0.06, 0.06, 0.09]
    for i in range(NUM_TORCHES):
        tx, ty, tcol, tint = G_TORCHES[i]
        dx = wx - tx
        dy = wy - ty
        d2 = dx * dx + dy * dy
        atten = tint / (1.0 + d2 * 0.5)
        flicker = 0.88 + 0.12 * math.sin(G.frame * 0.15 + i * 2.3)
        f = atten * flicker
        total[0] += tcol[0] * f
        total[1] += tcol[1] * f
        total[2] += tcol[2] * f
    return total


# ── Brick wall texture ──────────────────────────────────────────────────────

def wall_texture(u, v, wall_type, side):
    base, mortar_c, bw, bh = WALL_MATS[wall_type]

    # Door: flat color with panel detail instead of bricks
    if wall_type == 6:
        panel_v = math.fmod(v * 4.0, 1.0)
        panel_u = math.fmod(u * 2.0, 1.0)
        frame = min(min(panel_u, 1.0 - panel_u), min(panel_v, 1.0 - panel_v))
        is_frame = smoothstep(0.08, 0.05, frame)
        door = base
        trim = col_mul(base, 0.65)
        c = col_lerp(door, trim, is_frame)
        grain = value_noise(u * 1.0, v * 30.0) * 0.08
        c = col_mul(c, 0.92 + grain)
        return col_mul(c, 0.75) if side else c

    # Brick grid coordinates
    row_v = v / bh
    row_i = int(math.floor(row_v))
    row_f = row_v - row_i

    # Running bond: offset every other row by half a brick width
    u_offset = u + (row_i & 1) * bw * 0.5
    col_u = u_offset / bw
    col_i = int(math.floor(col_u))
    col_f = col_u - col_i

    # Mortar lines
    mortar_w = 0.06
    mu = min(col_f, 1.0 - col_f) / mortar_w
    mv = min(row_f, 1.0 - row_f) / mortar_w
    mortar_mask = clampf(min(mu, mv), 0.0, 1.0)

    if mortar_mask < 0.5:
        mortar = mortar_c
        depth_noise = value_noise(u * 40.0 + 3.0, v * 40.0 + 7.0)
        mortar = col_mul(mortar, 0.85 + depth_noise * 0.3)
        if side:
            mortar = col_mul(mortar, 0.8)
        return mortar

    # Per-brick identity (deterministic from grid cell)
    brick_id = hash2(col_i + wall_type * 100.0, row_i + wall_type * 37.0)
    brick_id2 = hash2(col_i + 50.0, row_i + 90.0)

    cr, cg, cb = base
    # Hue shift
    hue_shift = (brick_id - 0.5) * 0.12
    cr = clampf(cr + hue_shift, 0, 1)
    cg = clampf(cg + hue_shift * 0.3, 0, 1)
    # Value shift
    value_shift = (brick_id2 - 0.5) * 0.15
    s = 1.0 + value_shift
    cr *= s
    cg *= s
    cb *= s

    # Surface roughness
    rough = value_noise((u + brick_id * 10.0) * 25.0, (v + brick_id2 * 10.0) * 25.0)
    s = 0.88 + rough * 0.24
    cr *= s
    cg *= s
    cb *= s

    # Coarse pitting / chips
    pit = value_noise(u * 12.0 + brick_id * 5.0, v * 12.0 + brick_id2 * 5.0)
    if pit > 0.78:
        s = 0.7 + (pit - 0.78) * 2.0
        cr *= s
        cg *= s
        cb *= s

    # Edge weathering
    edge_u = smoothstep(0.0, 0.2, min(col_f, 1.0 - col_f) / mortar_w - 0.5)
    edge_v = smoothstep(0.0, 0.2, min(row_f, 1.0 - row_f) / mortar_w - 0.5)
    edge_ao = min(edge_u, edge_v)
    s = 0.82 + edge_ao * 0.18
    cr *= s
    cg *= s
    cb *= s

    # Side face shading
    if side:
        cr *= 0.72
        cg *= 0.72
        cb *= 0.72

    return col_clamp((cr, cg, cb))


# ── Floor texture ───────────────────────────────────────────────────────────

def floor_texture(wx, wy):
    iu = math.floor(wx)
    iv = math.floor(wy)
    fu = wx - iu
    fv = wy - iv

    # Grout lines
    grout_w = 0.05
    gu = min(fu, 1.0 - fu) / grout_w
    gv = min(fv, 1.0 - fv) / grout_w
    grout_edge = clampf(min(gu, gv), 0.0, 1.0)

    if grout_edge < 0.5:
        depth = (1.0 - grout_edge) * 0.015
        return (0.03 - depth, 0.03 - depth, 0.04 - depth)

    # Checkerboard tint
    check = (int(iu) + int(iv)) & 1
    base = 0.14 if check else 0.11

    # Per-tile identity
    tid = hash2(iu, iv)
    tid2 = hash2(iu + 37.0, iv + 91.0)
    variation = (tid - 0.5) * 0.03

    if tid < 0.33:
        c = [base * 0.90 + variation, base * 0.85 + variation, base * 0.80 + variation]
    elif tid < 0.66:
        c = [base * 0.82 + variation, base * 0.82 + variation, base * 0.90 + variation]
    else:
        c = [base * 0.85 + variation, base * 0.80 + variation, base * 0.88 + variation]

    # Stone grain
    grain = fbm(wx * 14.0 + tid * 100.0, wy * 14.0 + tid2 * 100.0, 3)
    fine = (grain - 0.5) * 0.04
    c[0] = clampf(c[0] + fine, 0, 1)
    c[1] = clampf(c[1] + fine * 0.9, 0, 1)
    c[2] = clampf(c[2] + fine * 0.85, 0, 1)

    # Mineral veins
    vein = value_noise(wx * 6.0 + tid * 30.0, wy * 4.0 + tid2 * 30.0)
    vein_mask = smoothstep(0.47, 0.53, vein)
    s = 1.0 - (1.0 - vein_mask) * 0.05
    c[0] *= s
    c[1] *= s
    c[2] *= s

    # Edge AO
    if grout_edge < 1.0:
        ao = 0.72 + grout_edge * 0.28
        c[0] *= ao
        c[1] *= ao
        c[2] *= ao

    return col_clamp((c[0], c[1], c[2]))


# ── Render column ───────────────────────────────────────────────────────────

FOG_COLOR = (0.02, 0.02, 0.04)


def render_column(colx, pixel_h):
    angle = G.pa - FOV / 2.0 + FOV * (colx / G.pw)
    perp_dist, wall_type, wall_x, side, map_x, map_y = cast_ray(angle)

    perp = perp_dist * math.cos(angle - G.pa)
    G.zbuf[colx] = perp

    wall_h = pixel_h / (perp + 0.001)
    wall_top = int((pixel_h - wall_h) / 2.0)
    wall_bot = int((pixel_h + wall_h) / 2.0)

    # Wall hit world position for lighting
    if not side:
        hit_wx = map_x + (0.0 if math.cos(angle) > 0 else 1.0)
        hit_wy = G.py + perp_dist * math.sin(angle)
    else:
        hit_wx = G.px + perp_dist * math.cos(angle)
        hit_wy = map_y + (0.0 if math.sin(angle) > 0 else 1.0)

    ca = math.cos(angle)
    sa = math.sin(angle)
    wall_span = (wall_bot - wall_top) if (wall_bot - wall_top) != 0 else 1

    for y in range(pixel_h):
        if y < wall_top:
            # Ceiling: dark stone
            row_dist = pixel_h / (pixel_h - 2.0 * y + 0.001)
            ceil_x = G.px + row_dist * ca
            ceil_y = G.py + row_dist * sa
            n = value_noise(ceil_x * 3.0, ceil_y * 3.0)
            ceil_col = (0.06 + n * 0.03, 0.05 + n * 0.025, 0.06 + n * 0.02)
            light = compute_light(ceil_x, ceil_y)
            fog = min(row_dist * 0.05, 0.80)
            lit = col_clamp((ceil_col[0] * light[0] * 1.8,
                             ceil_col[1] * light[1] * 1.8,
                             ceil_col[2] * light[2] * 1.8))
            color = col_lerp(lit, FOG_COLOR, fog)

        elif y >= wall_bot:
            # Floor
            row_dist = pixel_h / (2.0 * y - pixel_h + 0.001)
            floor_x = G.px + row_dist * ca
            floor_y = G.py + row_dist * sa
            tex = floor_texture(floor_x, floor_y)
            light = compute_light(floor_x, floor_y)
            fog = min(row_dist * 0.05, 0.80)
            lit = list(col_clamp((tex[0] * light[0] * 2.0,
                                  tex[1] * light[1] * 2.0,
                                  tex[2] * light[2] * 2.0)))
            # Torch glow puddles on floor
            for ti in range(NUM_TORCHES):
                tx, ty, tcol, _ = G_TORCHES[ti]
                tdx = floor_x - tx
                tdy = floor_y - ty
                td2 = tdx * tdx + tdy * tdy
                if td2 < 2.5:
                    glow = (1.0 - td2 / 2.5) * 0.06
                    flicker = 0.85 + 0.15 * math.sin(G.frame * 0.18 + ti * 1.5)
                    f = glow * flicker
                    lit[0] += tcol[0] * f
                    lit[1] += tcol[1] * f
                    lit[2] += tcol[2] * f
            color = col_lerp(col_clamp(tuple(lit)), FOG_COLOR, fog)

        else:
            # Wall
            if wall_type == 0:
                color = (0, 0, 0)
            else:
                v_coord = (y - wall_top) / wall_span
                tex = wall_texture(wall_x, v_coord, wall_type, side)
                light = compute_light(hit_wx, hit_wy)
                fog = min(perp * 0.04, 0.75)
                lit = col_clamp((tex[0] * light[0] * 2.0,
                                 tex[1] * light[1] * 2.0,
                                 tex[2] * light[2] * 2.0))
                color = col_lerp(lit, FOG_COLOR, fog)
                # Door glow
                if wall_type == 6:
                    glow = 0.5 + 0.5 * math.sin(G.frame * 0.15)
                    color = (color[0] + glow * 0.06, color[1] + glow * 0.04, color[2])
                # Exit pulse
                if wall_type == 9:
                    glow = 0.5 + 0.5 * math.sin(G.frame * 0.2)
                    color = (color[0] + glow * 0.10, color[1] + glow * 0.02, color[2])

        color = col_clamp(color)
        px_set(colx, y, color[0] * 255.0, color[1] * 255.0, color[2] * 255.0)


# ── Enemy sprite ────────────────────────────────────────────────────────────

def render_sprite(sx, sy, etype, hp, max_hp, sprite_scale, pixel_h):
    dx = sx - G.px
    dy = sy - G.py
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.1 or dist > 20.0:
        return

    cos_a = math.cos(G.pa)
    sin_a = math.sin(G.pa)
    rcos = math.cos(G.pa + PI / 2.0)
    rsin = math.sin(G.pa + PI / 2.0)
    inv_det = 1.0 / (rcos * sin_a - rsin * cos_a)
    tx = inv_det * (sin_a * dx - cos_a * dy)
    ty = inv_det * (-rsin * dx + rcos * dy)
    if ty < 0.2:
        return

    screen_x = int((G.pw / 2.0) * (1.0 + tx / ty))
    h = sprite_scale * pixel_h / ty
    s_top = int((pixel_h - h) / 2.0)
    s_bot = int((pixel_h + h) / 2.0)
    s_left = screen_x - int(h / 2.0)
    s_right = screen_x + int(h / 2.0)

    fog = min(ty * 0.05, 0.75)
    light = compute_light(sx, sy)

    if etype == 0:
        body_col = (0.65, 0.18, 0.14)
        head_col = (0.72, 0.25, 0.20)
    elif etype == 1:
        body_col = (0.16, 0.55, 0.22)
        head_col = (0.22, 0.65, 0.30)
    elif etype == 2:
        body_col = (0.22, 0.22, 0.60)
        head_col = (0.30, 0.30, 0.70)
    else:
        body_col = (0.4, 0.4, 0.4)
        head_col = (0.5, 0.5, 0.5)
    eye_col = (0.90, 0.85, 0.40)

    span_x = (s_right - s_left) if (s_right - s_left) != 0 else 1
    span_y = (s_bot - s_top) if (s_bot - s_top) != 0 else 1

    for colx in range(max(0, s_left), min(G.pw, s_right)):
        if ty >= G.zbuf[colx]:
            continue
        u = (colx - s_left) / span_x
        cx = u - 0.5

        for rowy in range(max(0, s_top), min(pixel_h, s_bot)):
            v = (rowy - s_top) / span_y
            cy = v - 0.5

            c = None

            body_r = 0.35 - abs(cy) * 0.15
            if 0.25 < v < 0.95 and abs(cx) < body_r:
                shade = 1.0 - abs(cx) / body_r * 0.3
                c = col_mul(body_col, shade)

            hdx = cx
            hdy = cy - 0.15
            hd = math.sqrt(hdx * hdx + hdy * hdy)
            if hd < 0.18:
                shade = 1.0 - hd / 0.18 * 0.25
                c = col_mul(head_col, shade)
                if 0.28 < v < 0.36:
                    if abs(cx + 0.07) < 0.03 or abs(cx - 0.07) < 0.03:
                        c = eye_col
                if 0.36 < v < 0.40 and abs(cx) < 0.06:
                    c = (0.15, 0.06, 0.06)

            arm_w = 0.12 if etype == 2 else 0.08
            if 0.35 < v < 0.65:
                if abs(cx + 0.30) < arm_w or abs(cx - 0.30) < arm_w:
                    c = col_mul(body_col, 0.80)

            if c is None:
                continue

            lit = col_clamp((c[0] * light[0] * 1.8,
                             c[1] * light[1] * 1.8,
                             c[2] * light[2] * 1.8))
            final_c = col_clamp(col_lerp(lit, FOG_COLOR, fog))
            px_set(colx, rowy, final_c[0] * 255.0, final_c[1] * 255.0, final_c[2] * 255.0)

    # Health bar
    if hp < max_hp and hp > 0:
        bar_w = max(4, (s_right - s_left) // 2)
        bar_y = max(0, s_top - 3)
        bar_x = screen_x - bar_w // 2
        pct = hp / max_hp
        for bx in range(bar_w):
            pxx = bar_x + bx
            if pxx < 0 or pxx >= G.pw or ty >= G.zbuf[pxx]:
                continue
            if (bx / bar_w) < pct:
                px_set(pxx, bar_y, 60, 200, 80)
            else:
                px_set(pxx, bar_y, 80, 30, 30)


# ── Pickup sprite ───────────────────────────────────────────────────────────

def render_pickup(sx, sy, ptype, pixel_h):
    dx = sx - G.px
    dy = sy - G.py
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.1 or dist > 15.0:
        return

    cos_a = math.cos(G.pa)
    sin_a = math.sin(G.pa)
    rcos = math.cos(G.pa + PI / 2.0)
    rsin = math.sin(G.pa + PI / 2.0)
    inv_det = 1.0 / (rcos * sin_a - rsin * cos_a)
    tx = inv_det * (sin_a * dx - cos_a * dy)
    ty = inv_det * (-rsin * dx + rcos * dy)
    if ty < 0.2:
        return

    screen_x = int((G.pw / 2.0) * (1.0 + tx / ty))
    h = 0.4 * pixel_h / ty
    s_top = int((pixel_h - h) / 2.0)
    s_bot = int((pixel_h + h) / 2.0)
    s_left = screen_x - int(h / 2.0)
    s_right = screen_x + int(h / 2.0)

    pulse = 0.6 + 0.4 * math.sin(G.frame * 0.12)
    if ptype == 0:
        color = (0.15, 0.70 * pulse, 0.22)
    else:
        color = (0.22, 0.45 * pulse, 0.80 * pulse)
    fog = min(ty * 0.05, 0.75)

    span_x = (s_right - s_left) if (s_right - s_left) != 0 else 1
    span_y = (s_bot - s_top) if (s_bot - s_top) != 0 else 1

    for colx in range(max(0, s_left), min(G.pw, s_right)):
        if ty >= G.zbuf[colx]:
            continue
        u = (colx - s_left) / span_x
        for rowy in range(max(0, s_top), min(pixel_h, s_bot)):
            v = (rowy - s_top) / span_y
            cx = u - 0.5
            cy = v - 0.5
            d = math.sqrt(cx * cx + cy * cy)
            if d > 0.35:
                continue
            glow = 1.0 - d / 0.35
            glow = glow * glow
            c = col_mul(color, glow)
            if d < 0.12:
                core = 1.0 - d / 0.12
                c = (c[0] + core * 0.3, c[1] + core * 0.3, c[2] + core * 0.3)
            final_c = col_clamp(col_lerp(c, FOG_COLOR, fog))
            px_set(colx, rowy, final_c[0] * 255.0, final_c[1] * 255.0, final_c[2] * 255.0)


# ── Weapon sprite ───────────────────────────────────────────────────────────

def draw_weapon(pixel_h):
    w = G.pw
    base_x = w // 2 + 4
    base_y = pixel_h + 2

    bob_x = math.sin(G.weapon_bob) * 4.0
    bob_y = abs(math.cos(G.weapon_bob * 2.0)) * 3.0
    recoil = G.flash * 4.0 if G.flash > 0 else 0.0

    ox = base_x + int(bob_x)
    oy = base_y + int(bob_y + recoil)

    # Gun barrel — dark metal
    for dy in range(-22, 1):
        for dx in range(-4, 5):
            t = 1.0 - (-dy) / 22.0
            r = abs(dx) / 4.5
            shade = 0.18 + t * 0.08
            shade *= (1.0 - r * r * 0.4)
            highlight = 0.05 if (dx == -2 or dx == -3) else 0.0
            cr = clampf((shade + highlight) * 0.80, 0, 1)
            cg = clampf((shade + highlight) * 0.82, 0, 1)
            cb = clampf((shade + highlight) * 0.90, 0, 1)
            px_set(ox + dx, oy + dy, cr * 255.0, cg * 255.0, cb * 255.0)

    # Muzzle ring
    for dx in range(-3, 4):
        r = abs(dx) / 3.5
        shade = 0.22 * (1.0 - r * 0.4)
        px_set(ox + dx, oy - 22, shade * 200.0, shade * 205.0, shade * 220.0)

    # Receiver
    for dy in range(0, 6):
        for dx in range(-6, 7):
            r = abs(dx) / 7.0
            shade = 0.20 - r * 0.04
            px_set(ox + dx, oy + dy,
                   clampf(shade * 0.80, 0, 1) * 255.0,
                   clampf(shade * 0.80, 0, 1) * 255.0,
                   clampf(shade * 0.88, 0, 1) * 255.0)

    # Grip — dark wood
    for dy in range(5, 15):
        for dx in range(-4, 5):
            t = (dy - 5) / 9.0
            r = abs(dx) / 5.0
            shade = 0.16 + t * 0.04
            shade *= (1.0 - r * 0.2)
            grain = math.sin(dy * 1.5 + dx * 0.3) * 0.015
            shade += grain
            px_set(ox + dx, oy + dy,
                   clampf(shade * 1.2, 0, 1) * 255.0,
                   clampf(shade * 0.80, 0, 1) * 255.0,
                   clampf(shade * 0.50, 0, 1) * 255.0)

    # Muzzle flash
    if G.flash > 0:
        flash_y = oy - 24
        strength = G.flash / 4.0
        r1 = 4
        for dy in range(-r1, r1 + 1):
            for dx in range(-r1, r1 + 1):
                d = math.sqrt(dx * dx + dy * dy)
                if d > r1:
                    continue
                t = 1.0 - d / r1
                px_blend(ox + dx, flash_y + dy, (1.0, 0.95, 0.7), t * t * strength)
        r2 = 7 + G.flash
        for dy in range(-r2, r2 + 1):
            for dx in range(-r2, r2 + 1):
                d = math.sqrt(dx * dx + dy * dy)
                if d > r2:
                    continue
                t = 1.0 - d / r2
                px_blend(ox + dx, flash_y + dy, (1.0, 0.70, 0.25), t * t * strength * 0.35)


# ── Crosshair ───────────────────────────────────────────────────────────────

def draw_crosshair(pixel_h):
    cx = G.pw // 2
    cy = pixel_h // 2
    gap = 2
    length = 5
    cc = (0.8, 0.8, 0.8)
    alpha = 0.7
    for i in range(gap, gap + length):
        px_blend(cx + i, cy, cc, alpha)
        px_blend(cx - i, cy, cc, alpha)
        px_blend(cx, cy + i, cc, alpha)
        px_blend(cx, cy - i, cc, alpha)
    px_blend(cx, cy, cc, 0.8)


# ── Post-processing ─────────────────────────────────────────────────────────

def post_process(pixel_h):
    w = G.pw
    h = pixel_h
    center_x = w * 0.5
    center_y = h * 0.5
    p = G.pixels
    hit_alpha = (G.hit_flash / 6.0 * 0.30) if G.hit_flash > 0 else 0.0
    for y in range(h):
        dyv = (y - center_y) / center_y if center_y else 0.0
        dyv2 = dyv * dyv * 0.3
        for x in range(w):
            i = (y * w + x) * 3
            r = p[i] / 255.0
            g = p[i + 1] / 255.0
            b = p[i + 2] / 255.0
            dxv = (x - center_x) / center_x if center_x else 0.0
            vig = 1.0 - (dxv * dxv * 0.5 + dyv2) * 0.18
            vig = clampf(vig, 0.6, 1.0)
            r *= vig
            g *= vig
            b *= vig
            if hit_alpha > 0.0:
                r = clampf(r + hit_alpha * 0.4, 0, 1)
                g *= (1.0 - hit_alpha * 0.4)
                b *= (1.0 - hit_alpha * 0.4)
            p[i] = clampf(r, 0, 1) * 255.0
            p[i + 1] = clampf(g, 0, 1) * 255.0
            p[i + 2] = clampf(b, 0, 1) * 255.0


# ── Minimap ─────────────────────────────────────────────────────────────────

MM_WALL = (80, 50, 45)
MM_EMPTY = (20, 18, 25)
MM_PLAYER = (230, 210, 60)
MM_ENEMY = (220, 50, 50)


def draw_minimap(grid, gw, gh):
    """Draw the minimap into the top-right of the half-block pixel grid.

    The C++ paints map cells onto canvas cells with U+2588; here we paint
    blocks of 2x2 internal pixels (one half-block cell) per map tile.
    """
    cell = 2  # half-block cells per map tile, each cell = 2 px tall
    map_size = min(12, min(gw // 4, gh // 3))
    if map_size < 4:
        return
    ox_cell = gw - (map_size * cell) - 1
    oy_cell = 1
    view_r = map_size // 2
    pmx = int(G.px)
    pmy = int(G.py)

    for dy in range(-view_r, view_r):
        for dx in range(-view_r, view_r):
            mx = pmx + dx
            my = pmy + dy
            color = MM_EMPTY
            if mx < 0 or mx >= MAP_W or my < 0 or my >= MAP_H:
                color = MM_WALL
            elif G_MAP[my][mx] > 0:
                color = MM_WALL
            if mx == pmx and my == pmy:
                color = MM_PLAYER
            for e in G.enemies:
                if not e["active"]:
                    continue
                if int(e["x"]) == mx and int(e["y"]) == my:
                    color = MM_ENEMY
            # paint a cell x cell block of half-block cells
            scx = ox_cell + (dx + view_r) * cell
            scy = oy_cell + (dy + view_r) * cell
            for cyo in range(cell):
                yy = scy + cyo
                if yy < 0 or yy >= gh:
                    continue
                rowg = grid[yy]
                for cxo in range(cell):
                    xx = scx + cxo
                    if 0 <= xx < gw:
                        rowg[xx] = color


# ── Render the full frame into a half-block grid ─────────────────────────────

def render_field(w, h):
    # CAP the internal pixel buffer (bounded frame time regardless of window).
    pw = max(16, min(MAX_PW, w))
    ph = max(2, min(MAX_PH, h * 2))
    if ph % 2:
        ph += 1
    buffer_resize(pw, ph)

    pixel_h = ph

    # Clear
    p = G.pixels
    for i in range(len(p)):
        p[i] = 0.0

    # Walls / floor / ceiling
    for x in range(pw):
        render_column(x, pixel_h)

    # Sprites (farthest first)
    sorted_enemies = []
    for e in G.enemies:
        if e["active"]:
            e["dist"] = math.sqrt((e["x"] - G.px) ** 2 + (e["y"] - G.py) ** 2)
            sorted_enemies.append(e)
    sorted_enemies.sort(key=lambda e: e["dist"], reverse=True)
    for e in sorted_enemies:
        scale = 0.65 if e["type"] == 1 else (1.0 if e["type"] == 2 else 0.8)
        render_sprite(e["x"], e["y"], e["type"], e["hp"], e["max_hp"], scale, pixel_h)

    # Pickups
    for pk in G.pickups:
        if not pk["taken"]:
            render_pickup(pk["x"], pk["y"], pk["type"], pixel_h)

    # Weapon + crosshair
    draw_weapon(pixel_h)
    draw_crosshair(pixel_h)

    # Post-processing
    post_process(pixel_h)

    # Build half-block grid (rows of (r,g,b) tuples)
    gw = pw
    gh = ph
    grid = [None] * gh
    for y in range(gh):
        base = y * pw * 3
        rowg = [None] * gw
        for x in range(gw):
            i = base + x * 3
            rowg[x] = (int(p[i]), int(p[i + 1]), int(p[i + 2]))
        grid[y] = rowg

    # Minimap overlay
    if G.show_map:
        draw_minimap(grid, gw, gh)

    return halfblock(grid)


# ── App ─────────────────────────────────────────────────────────────────────

app = App("fps", inline=False, fps=30)
app.state(_t=0.0)


@app.on("w", "up")
def _fwd(s):
    if G.dead or G.won:
        return
    G.key_last[K_FWD] = G.frame
    G.key_last[K_BACK] = -100


@app.on("s", "down")
def _back(s):
    if G.dead or G.won:
        return
    G.key_last[K_BACK] = G.frame
    G.key_last[K_FWD] = -100


@app.on("a")
def _strafe_l(s):
    if G.dead or G.won:
        return
    G.key_last[K_LEFT] = G.frame
    G.key_last[K_RIGHT] = -100


@app.on("d")
def _strafe_r(s):
    if G.dead or G.won:
        return
    G.key_last[K_RIGHT] = G.frame
    G.key_last[K_LEFT] = -100


@app.on("left", ",")
def _turn_l(s):
    if G.dead or G.won:
        return
    G.key_last[K_TURN_L] = G.frame
    G.key_last[K_TURN_R] = -100


@app.on("right", ".")
def _turn_r(s):
    if G.dead or G.won:
        return
    G.key_last[K_TURN_R] = G.frame
    G.key_last[K_TURN_L] = -100


@app.on("space")
def _shoot(s):
    if G.dead or G.won:
        return
    shoot()


@app.on("m")
def _toggle_map(s):
    if G.dead or G.won:
        return
    G.show_map = not G.show_map


@app.on("r")
def _restart(s):
    reset_game()


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _tick(s, dt):
    tick(1.0 / 30.0)


@app.view
def view(s):
    if G.dead or G.won:
        title = "YOU DIED" if G.dead else "ESCAPE!"
        tcol = (220, 60, 60) if G.dead else (80, 220, 120)
        over = row(
            T(title).fg(tcol).bold,
            T(f"   SCORE {G.score}  KILLS {G.kills}").fg((220, 180, 60)).bold,
            T("   [r] restart  [q] quit").fg((150, 150, 160)),
            gap=0,
        )
        return col(component(render_field, grow=1), over, gap=0)

    hud = row(
        T("FPS").fg((220, 180, 70)).bold,
        T(f"  \u2665{G.health}").fg((70, 210, 90)).bold,
        T(f"  \u25aa{G.ammo}").fg((90, 180, 230)).bold,
        T(f"   K:{G.kills}").fg((100, 95, 110)),
        T(f"  \u2605{G.score}").fg((220, 180, 70)).bold,
        gap=0,
    )
    help_line = T(
        "[wasd] move  [,/.] turn  [space] shoot  [m] map  [r] restart  [q] quit"
    ).fg((80, 75, 90))
    return col(
        component(render_field, grow=1),
        hud,
        help_line,
        gap=0,
    )


spawn_enemies()
spawn_pickups()


if __name__ == "__main__":
    app.run()
