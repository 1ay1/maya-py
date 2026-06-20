"""space3d.py — TERRAIN: 3D flight over raymarched terrain.

A faithful port of maya's `examples/space3d.cpp`. Per-pixel raymarched
heightmap terrain with water reflections, ambient occlusion, soft shadows,
procedural erosion-like texturing, a golden-hour sky with atmospheric
scattering, and collectible rings.

The C++ original drives maya's raw Canvas at 30fps across every CPU core. This
port keeps the math byte-for-byte faithful and renders through maya's native
half-block surface (`halfblock`), but the per-pixel raymarch runs in pure
Python — so it's a low-resolution slideshow rather than a 30fps flight. The
MAX_PW / MAX_PH knobs trade resolution for framerate.

  Keys: WASD/arrows steer · space ascend · c descend · b boost · r reset · q quit

    PYTHONPATH=src python examples/space3d.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, component, halfblock, upscale, target_size  # noqa: E402

# Pure-Python raymarching is ~100x slower than the threaded C++. We render into
# a small internal pixel buffer whose size is CAPPED (independent of the
# terminal size) so a large window can't push frame time to seconds — the
# half-block field is then stretched to fill the available cells. Raise
# MAX_PW / MAX_PH for more detail at lower framerate.
MAX_PW = 24
MAX_PH = 16

PI = 3.14159265
TAU = 6.28318530


# ── Math ────────────────────────────────────────────────────────────────────

def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = clampf((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vlen(v):
    return math.sqrt(dot(v, v))


def normalize(v):
    inv = 1.0 / (vlen(v) + 1e-9)
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def reflect(i, n):
    k = 2.0 * dot(i, n)
    return (i[0] - n[0] * k, i[1] - n[1] * k, i[2] - n[2] * k)


def col_lerp(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def col_clamp(c):
    return (clampf(c[0], 0, 1), clampf(c[1], 0, 1), clampf(c[2], 0, 1))


# ── Noise ───────────────────────────────────────────────────────────────────

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
    freq = 1.0
    for _ in range(octaves):
        s += value_noise(x * freq, y * freq) * amp
        freq *= 2.03
        amp *= 0.48
    return s


def ridged_noise(x, y, octaves):
    s = 0.0
    amp = 0.6
    freq = 1.0
    prev = 1.0
    for _ in range(octaves):
        n = value_noise(x * freq, y * freq)
        n = 1.0 - abs(n * 2.0 - 1.0)
        n = n * n
        s += n * amp * prev
        prev = n
        freq *= 2.1
        amp *= 0.5
    return s


# ── Terrain ─────────────────────────────────────────────────────────────────

def terrain_height(x, z):
    base = fbm(x * 0.003, z * 0.003, 4) * 40.0 - 10.0
    mountain_mask = smoothstep(0.35, 0.65, value_noise(x * 0.002, z * 0.002))
    ridges = ridged_noise(x * 0.008 + 3.7, z * 0.008 + 1.3, 5) * 55.0
    h = base + ridges * mountain_mask
    gully = value_noise(x * 0.025, z * 0.025)
    gully = smoothstep(0.4, 0.6, gully)
    h += (gully - 0.5) * 6.0
    h += fbm(x * 0.05, z * 0.05, 3) * 2.5
    if h < 3.0:
        h = lerp(h, -2.0, smoothstep(3.0, -5.0, h))
    return h


def terrain_normal(x, z):
    e = 0.15
    hc = terrain_height(x, z)
    hx = terrain_height(x + e, z)
    hz = terrain_height(x, z + e)
    return normalize((-(hx - hc) / e, 1.0, -(hz - hc) / e))


# ── Sky model ───────────────────────────────────────────────────────────────

G_SUN_DIR = normalize((0.5, 0.28, -0.7))
G_SUN_COLOR = (1.6, 1.15, 0.7)


def sky_color(rd):
    y = rd[1]
    zenith = (0.15, 0.22, 0.55)
    mid_sky = (0.30, 0.38, 0.68)
    horizon = (0.75, 0.52, 0.30)
    low_hori = (0.90, 0.50, 0.18)

    if y > 0.5:
        sky = col_lerp(mid_sky, zenith, (y - 0.5) / 0.5)
    elif y > 0.12:
        sky = col_lerp(horizon, mid_sky, (y - 0.12) / 0.38)
    elif y > 0.0:
        sky = col_lerp(low_hori, horizon, y / 0.12)
    else:
        sky = low_hori

    sun_dot = clampf(dot(rd, G_SUN_DIR), 0.0, 1.0)
    mie = sun_dot ** 5.0
    sky = (sky[0] + mie * 0.5, sky[1] + mie * 0.30, sky[2] + mie * 0.08)
    mie2 = sun_dot ** 24.0
    sky = (sky[0] + mie2 * 0.4, sky[1] + mie2 * 0.22, sky[2] + mie2 * 0.05)
    disk = sun_dot ** 800.0
    sky = (sky[0] + disk * 4.0, sky[1] + disk * 3.2, sky[2] + disk * 2.0)
    corona = sun_dot ** 128.0
    sky = (sky[0] + corona * 0.6, sky[1] + corona * 0.35, sky[2] + corona * 0.12)

    if y > 0.35:
        su = math.atan2(rd[0], rd[2]) * 80.0
        sv = rd[1] * 100.0
        star = hash2(math.floor(su), math.floor(sv))
        if star > 0.988:
            bright = (star - 0.988) * 70.0 * smoothstep(0.35, 0.65, y)
            sky = (sky[0] + bright, sky[1] + bright, sky[2] + bright * 0.9)

    if 0.02 < y < 0.4:
        cu = math.atan2(rd[0], rd[2]) * 2.5
        cv = y * 8.0
        cloud = fbm(cu + 0.3, cv + 1.7, 3)
        cloud = smoothstep(0.42, 0.62, cloud)
        cloud_col = col_lerp((0.9, 0.75, 0.55), (1.0, 0.9, 0.8), y * 3.0)
        sky = col_lerp(sky, cloud_col, cloud * 0.25)

    return col_clamp(sky)


# ── Atmosphere / fog ────────────────────────────────────────────────────────

def apply_fog(color, dist, rd):
    fog_amount = 1.0 - math.exp(-dist * 0.0008)
    fog_amount = clampf(fog_amount, 0.0, 1.0)
    sun_factor = clampf(dot(rd, G_SUN_DIR) * 0.5 + 0.5, 0.0, 1.0)
    sun_factor = sun_factor * sun_factor
    fog_col = col_lerp((0.42, 0.45, 0.58), (0.72, 0.52, 0.30), sun_factor)
    inscatter = clampf(dot(rd, G_SUN_DIR), 0, 1) ** 8.0
    fog_col = (fog_col[0] + inscatter * 0.15, fog_col[1] + inscatter * 0.08,
               fog_col[2] + inscatter * 0.02)
    return col_lerp(color, fog_col, fog_amount)


# ── Camera / player state ───────────────────────────────────────────────────

WATER_LEVEL = 0.0
MIN_HEIGHT = 4.0
CAM_PITCH_RANGE = 0.35
BASE_SPEED = 40.0
BOOST_SPEED = 120.0
STEER_RATE = 1.8
PITCH_RATE = 0.8
VERT_RATE = 18.0
HOLD_FRAMES = 5

K_UP, K_DOWN, K_LEFT, K_RIGHT, K_ASCEND, K_DESCEND, K_BOOST, K_COUNT = range(8)


class World:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cam_pos = [0.0, 35.0, 0.0]
        self.cam_yaw = 0.0
        self.cam_pitch = -0.06
        self.speed = BASE_SPEED
        self.boost = 0.0
        self.frame = 0
        self.time = 0.0
        self.dist = 0.0
        self.score = 0
        self.rings = []  # each: [x, y, z, radius, collected]
        self.key_last = [-100] * K_COUNT


G = World()


def spawn_rings_ahead():
    ahead_z = G.cam_pos[2] - 200.0
    for i in range(5):
        rz = ahead_z - i * 60.0
        exists = any(abs(r[2] - rz) < 30.0 for r in G.rings)
        if exists:
            continue
        rx = G.cam_pos[0] + (hash2(rz * 0.1, 0.0) - 0.5) * 80.0
        th = terrain_height(rx, rz)
        ry = max(th, WATER_LEVEL) + 12.0 + hash2(rz * 0.1, 1.0) * 15.0
        G.rings.append([rx, ry, rz, 5.0, False])
    cz = G.cam_pos[2]
    G.rings = [r for r in G.rings if not (r[2] > cz + 50.0)]


def game_tick(dt):
    G.frame += 1
    G.time += dt

    def held(k):
        return (G.frame - G.key_last[k]) < HOLD_FRAMES

    turn = (1.0 if held(K_RIGHT) else 0.0) - (1.0 if held(K_LEFT) else 0.0)
    pitch = (1.0 if held(K_UP) else 0.0) - (1.0 if held(K_DOWN) else 0.0)
    vert = (1.0 if held(K_ASCEND) else 0.0) - (1.0 if held(K_DESCEND) else 0.0)
    boosting = held(K_BOOST)

    G.cam_yaw += turn * STEER_RATE * dt
    G.cam_pitch += pitch * PITCH_RATE * dt
    G.cam_pitch = clampf(G.cam_pitch, -CAM_PITCH_RANGE, CAM_PITCH_RANGE)

    target_speed = BOOST_SPEED if boosting else BASE_SPEED
    G.speed = lerp(G.speed, target_speed, 3.0 * dt)
    G.boost = lerp(G.boost, 1.0 if boosting else 0.0, 4.0 * dt)

    fwd_x = math.sin(G.cam_yaw)
    fwd_z = -math.cos(G.cam_yaw)
    G.cam_pos[0] += fwd_x * G.speed * dt
    G.cam_pos[2] += fwd_z * G.speed * dt
    G.cam_pos[1] += vert * VERT_RATE * dt

    ground = terrain_height(G.cam_pos[0], G.cam_pos[2])
    min_y = max(ground, WATER_LEVEL) + MIN_HEIGHT
    if G.cam_pos[1] < min_y:
        G.cam_pos[1] = lerp(G.cam_pos[1], min_y, 8.0 * dt)
    G.cam_pos[1] = clampf(G.cam_pos[1], min_y, 120.0)

    G.dist += G.speed * dt

    spawn_rings_ahead()
    cp = G.cam_pos
    for r in G.rings:
        if r[4]:
            continue
        d = vlen((cp[0] - r[0], cp[1] - r[1], cp[2] - r[2]))
        if d < r[3] + 3.0:
            r[4] = True
            G.score += 100


# ── Soft shadow ─────────────────────────────────────────────────────────────

def soft_shadow(pos):
    res = 1.0
    t = 1.0
    i = 0
    while i < 32 and t < 80.0:
        p = (pos[0] + G_SUN_DIR[0] * t, pos[1] + G_SUN_DIR[1] * t,
             pos[2] + G_SUN_DIR[2] * t)
        h = terrain_height(p[0], p[2])
        diff = p[1] - h
        if diff < 0.1:
            return 0.0
        res = min(res, 8.0 * diff / t)
        t += clampf(diff * 0.5, 0.5, 6.0)
        i += 1
    return clampf(res, 0.0, 1.0)


# ── Ambient occlusion ───────────────────────────────────────────────────────

def ambient_occlusion(pos, normal):
    ao = 0.0
    scale = 1.0
    for i in range(1, 5):
        dist = float(i) * 1.5
        p = (pos[0] + normal[0] * dist, pos[1] + normal[1] * dist,
             pos[2] + normal[2] * dist)
        h = terrain_height(p[0], p[2])
        diff = p[1] - h
        ao += (dist - clampf(diff, 0.0, dist)) * scale
        scale *= 0.55
    return clampf(1.0 - ao * 0.15, 0.0, 1.0)


# ── Terrain shading ─────────────────────────────────────────────────────────

def terrain_shade(pos, normal, rd):
    h = pos[1]
    slope = 1.0 - normal[1]

    if h < 0.8:
        wet = smoothstep(0.8, -0.5, h)
        c = col_lerp((0.60, 0.52, 0.36), (0.35, 0.30, 0.22), wet)
    elif h < 6.0:
        t = (h - 0.8) / 5.2
        c = col_lerp((0.22, 0.38, 0.12), (0.18, 0.32, 0.09), t)
        patch = value_noise(pos[0] * 0.08, pos[2] * 0.08)
        c = col_lerp(c, (0.28, 0.40, 0.15), smoothstep(0.4, 0.6, patch) * 0.4)
    elif h < 18.0:
        t = (h - 6.0) / 12.0
        c = col_lerp((0.14, 0.25, 0.08), (0.24, 0.28, 0.14), t)
        trees = value_noise(pos[0] * 0.2, pos[2] * 0.2)
        k = 0.75 + trees * 0.5
        c = (c[0] * k, c[1] * k, c[2] * k)
    elif h < 32.0:
        t = (h - 18.0) / 14.0
        c = col_lerp((0.38, 0.34, 0.28), (0.50, 0.47, 0.43), t)
        if t < 0.4:
            lichen = value_noise(pos[0] * 0.15 + 7.0, pos[2] * 0.15 + 3.0)
            if lichen > 0.5:
                c = col_lerp(c, (0.30, 0.35, 0.18), (lichen - 0.5) * 0.6)
    else:
        t = clampf((h - 32.0) / 12.0, 0, 1)
        c = col_lerp((0.52, 0.50, 0.48), (0.92, 0.93, 0.96), t)

    if slope > 0.25:
        rock_t = smoothstep(0.25, 0.55, slope)
        rock_var = value_noise(pos[0] * 0.12 + 5.0, pos[2] * 0.12 + 9.0)
        cliff = (0.38 + rock_var * 0.08, 0.34 + rock_var * 0.06,
                 0.28 + rock_var * 0.05)
        layers = math.sin(pos[1] * 1.2 + value_noise(pos[0] * 0.05, pos[2] * 0.05) * 3.0)
        kk = 0.85 + layers * 0.15
        cliff = (cliff[0] * kk, cliff[1] * kk, cliff[2] * kk)
        c = col_lerp(c, cliff, rock_t)

    micro = value_noise(pos[0] * 0.5, pos[2] * 0.5)
    km = 0.9 + micro * 0.2
    c = (c[0] * km, c[1] * km, c[2] * km)

    ndotl = clampf(dot(normal, G_SUN_DIR), 0.0, 1.0)
    shadow = soft_shadow((pos[0] + normal[0] * 0.3, pos[1] + normal[1] * 0.3,
                          pos[2] + normal[2] * 0.3))
    ao = ambient_occlusion(pos, normal)

    sky_ambient = (0.20, 0.25, 0.40)
    ground_bounce = (0.06, 0.05, 0.03)
    sky_factor = normal[1] * 0.5 + 0.5
    amb = col_lerp(ground_bounce, sky_ambient, sky_factor)
    amb = (amb[0] * ao, amb[1] * ao, amb[2] * ao)

    dl = ndotl * shadow
    direct = (G_SUN_COLOR[0] * dl, G_SUN_COLOR[1] * dl, G_SUN_COLOR[2] * dl)

    lit = (c[0] * (amb[0] + direct[0]), c[1] * (amb[1] + direct[1]),
           c[2] * (amb[2] + direct[2]))

    if h < 2.0 or h > 35.0:
        half_v = normalize((G_SUN_DIR[0] - rd[0], G_SUN_DIR[1] - rd[1],
                            G_SUN_DIR[2] - rd[2]))
        spec = clampf(dot(normal, half_v), 0, 1) ** (32.0 if h < 2.0 else 16.0)
        spec *= shadow
        ss = 0.2 if h < 2.0 else 0.08
        lit = (lit[0] + spec * ss, lit[1] + spec * ss * 0.9, lit[2] + spec * ss * 0.7)

    return col_clamp(lit)


# ── Water shading ───────────────────────────────────────────────────────────

def water_shade(pos, rd, dist):
    t = G.time
    w1 = math.sin(pos[0] * 0.25 + t * 1.0) * math.cos(pos[2] * 0.18 + t * 0.7)
    w2 = math.sin(pos[0] * 0.6 - t * 0.5 + 1.0) * math.cos(pos[2] * 0.45 + t * 1.3)
    w3 = math.sin(pos[0] * 1.1 + t * 0.8 + 3.0) * math.cos(pos[2] * 0.9 - t * 0.4)
    wave = w1 * 0.5 + w2 * 0.3 + w3 * 0.2

    water_n = normalize((
        wave * 0.12 + math.cos(pos[0] * 0.4 + t * 0.9) * 0.04,
        1.0,
        wave * 0.10 + math.sin(pos[2] * 0.35 + t * 0.6) * 0.04,
    ))

    cos_i = clampf(abs(dot(rd, water_n)), 0, 1)
    fresnel = 0.02 + 0.98 * (1.0 - cos_i) ** 5.0

    refl = reflect(rd, water_n)
    if refl[1] < 0.01:
        refl = (refl[0], 0.01, refl[2])
    refl = normalize(refl)
    refl_col = sky_color(refl)

    deep = (0.01, 0.04, 0.09)
    shallow = smoothstep(20.0, 2.0, dist)
    water_body = col_lerp(deep, (0.04, 0.12, 0.15), shallow)

    spec = clampf(dot(refl, G_SUN_DIR), 0, 1) ** 512.0
    sun_spec = (1.5 * spec, 1.2 * spec, 0.8 * spec)

    broad = clampf(dot(refl, G_SUN_DIR), 0, 1) ** 12.0
    broad_col = (0.45 * broad * 0.25, 0.32 * broad * 0.25, 0.15 * broad * 0.25)

    water = col_lerp(water_body, refl_col, fresnel)
    water = (water[0] + sun_spec[0] + broad_col[0],
             water[1] + sun_spec[1] + broad_col[1],
             water[2] + sun_spec[2] + broad_col[2])

    rd_flat = normalize((rd[0], 0, rd[2]))
    sun_flat = normalize((G_SUN_DIR[0], 0, G_SUN_DIR[2]))
    sun_path = clampf(dot(rd_flat, sun_flat), 0, 1) ** 3.0
    glitter = sun_path * (0.5 + 0.5 * wave)
    water = (water[0] + glitter * 0.25, water[1] + glitter * 0.12,
             water[2] + glitter * 0.04)

    return col_clamp(water)


# ── Render one pixel ────────────────────────────────────────────────────────

def render_pixel(px, py, pw, ph):
    u = (2.0 * px - pw) / float(ph)
    v_coord = (ph - 2.0 * py) / float(ph)

    cy = math.cos(G.cam_yaw)
    sy = math.sin(G.cam_yaw)
    cp = math.cos(G.cam_pitch)
    sp = math.sin(G.cam_pitch)
    fwd = (sy * cp, sp, -cy * cp)
    right = (cy, 0.0, sy)
    up = (-sy * sp, cp, cy * sp)

    focal = 1.0
    rd = normalize((fwd[0] * focal + right[0] * u + up[0] * v_coord,
                    fwd[1] * focal + right[1] * u + up[1] * v_coord,
                    fwd[2] * focal + right[2] * u + up[2] * v_coord))

    cam = G.cam_pos
    max_dist = 600.0
    dt_step = 0.6
    t = 0.3
    hit_terrain = False
    hit_pos = (0.0, 0.0, 0.0)
    hit_t = max_dist

    water_t = max_dist
    if rd[1] < -0.001:
        water_t = (cam[1] - WATER_LEVEL) / (-rd[1])
        if water_t < 0:
            water_t = max_dist

    step = 0
    while step < 200 and t < max_dist:
        p = (cam[0] + rd[0] * t, cam[1] + rd[1] * t, cam[2] + rd[2] * t)
        h = terrain_height(p[0], p[2])
        if p[1] < h:
            lo = t - dt_step
            hi = t
            for _ in range(8):
                mid = (lo + hi) * 0.5
                mp = (cam[0] + rd[0] * mid, cam[1] + rd[1] * mid, cam[2] + rd[2] * mid)
                if mp[1] < terrain_height(mp[0], mp[2]):
                    hi = mid
                else:
                    lo = mid
            hit_t = (lo + hi) * 0.5
            hit_pos = (cam[0] + rd[0] * hit_t, cam[1] + rd[1] * hit_t,
                       cam[2] + rd[2] * hit_t)
            hit_terrain = True
            break
        above = p[1] - h
        dt_step = clampf(above * 0.3, 0.3, 6.0)
        t += dt_step
        step += 1

    if hit_terrain and hit_t < water_t:
        n = terrain_normal(hit_pos[0], hit_pos[2])
        color = terrain_shade(hit_pos, n, rd)
        color = apply_fog(color, hit_t, rd)
    elif water_t < max_dist and water_t < hit_t:
        wp = (cam[0] + rd[0] * water_t, cam[1] + rd[1] * water_t, cam[2] + rd[2] * water_t)
        color = water_shade(wp, rd, water_t)
        color = apply_fog(color, water_t, rd)
    else:
        color = sky_color(rd)

    for ring in G.rings:
        if ring[4]:
            continue
        to_ring = (ring[0] - cam[0], ring[1] - cam[1], ring[2] - cam[2])
        along = dot(to_ring, fwd)
        if along < 2.0 or along > 300.0:
            continue
        rx = dot(to_ring, right)
        ry = dot(to_ring, up)
        screen_x = rx / along * focal
        screen_y = ry / along * focal
        du = u - screen_x
        dv = v_coord - screen_y
        screen_r = ring[3] / along * focal
        d = math.sqrt(du * du + dv * dv)
        ring_edge = abs(d - screen_r)
        thickness = clampf(0.5 / along * focal, 0.005, 0.08)
        if ring_edge < thickness:
            t_ring = 1.0 - ring_edge / thickness
            t_ring = t_ring * t_ring
            pulse = 0.7 + 0.3 * math.sin(G.time * 4.0)
            ring_col = (1.0 * pulse, 0.8 * pulse, 0.2 * pulse)
            color = col_lerp(color, ring_col, t_ring * 0.9)
        elif ring_edge < thickness * 3.0:
            glow = 1.0 - (ring_edge - thickness) / (thickness * 2.0)
            g2 = glow * glow * 0.2
            color = (color[0] + 0.8 * g2, color[1] + 0.6 * g2, color[2] + 0.1 * g2)

    return color


# ── Post-processing ─────────────────────────────────────────────────────────

def tonemap(x):
    a = x * (x * 2.51 + 0.03)
    d = x * (x * 2.43 + 0.59) + 0.14
    return clampf(a / d, 0.0, 1.0)


def post_process(px, py, color, pw, ph):
    cx = pw * 0.5
    cy = ph * 0.5
    r = tonemap(color[0])
    g = tonemap(color[1])
    b = tonemap(color[2])
    dx = (px - cx) / cx if cx else 0.0
    dy = (py - cy) / cy if cy else 0.0
    vig = 1.0 - (dx * dx + dy * dy) * 0.12
    vig = clampf(vig, 0.6, 1.0)
    r *= vig
    g *= vig
    b *= vig
    return (int(clampf(r, 0, 1) * 255), int(clampf(g, 0, 1) * 255),
            int(clampf(b, 0, 1) * 255))


# ── App ─────────────────────────────────────────────────────────────────────

app = App("terrain", inline=False, fps=30)
app.state(_t=0.0)


def _press(*ks):
    for k in ks:
        G.key_last[k] = G.frame


@app.on("w", "up")
def _up(s):
    G.key_last[K_UP] = G.frame
    G.key_last[K_DOWN] = -100


@app.on("s", "down")
def _down(s):
    G.key_last[K_DOWN] = G.frame
    G.key_last[K_UP] = -100


@app.on("a", "left")
def _left(s):
    G.key_last[K_LEFT] = G.frame
    G.key_last[K_RIGHT] = -100


@app.on("d", "right")
def _right(s):
    G.key_last[K_RIGHT] = G.frame
    G.key_last[K_LEFT] = -100


@app.on("space")
def _ascend(s):
    G.key_last[K_ASCEND] = G.frame


@app.on("c")
def _descend(s):
    G.key_last[K_DESCEND] = G.frame


@app.on("b")
def _boost(s):
    G.key_last[K_BOOST] = G.frame


@app.on("r")
def _reset(s):
    G.reset()


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _tick(s, dt):
    game_tick(1.0 / 30.0)


def _field(w, h):
    # Pure-Python raymarch is ~100x slower than the threaded C++, so we compute
    # a small CAPPED internal buffer (bounded frame time regardless of window
    # size) and then NEAREST-NEIGHBOUR UPSCALE it to the full cell area so the
    # scene fills the screen exactly like the C++ original — identical layout,
    # lower detail. Raise MAX_PW/MAX_PH to trade fps for sharpness.
    out_w, out_h = target_size(w, h)
    pw = max(1, min(MAX_PW, out_w))
    ph = max(2, min(MAX_PH, out_h))
    if ph % 2:
        ph += 1
    small = [[None] * pw for _ in range(ph)]
    for y in range(ph):
        rowp = small[y]
        for x in range(pw):
            color = render_pixel(x, y, pw, ph)
            rowp[x] = post_process(x, y, color, pw, ph)
    return halfblock(upscale(small, out_w, out_h))


@app.view
def view(s):
    ground_h = terrain_height(G.cam_pos[0], G.cam_pos[2])
    alt = int(G.cam_pos[1] - max(ground_h, WATER_LEVEL))
    kmh = int(G.speed * 3.6)
    spd_col = (255, 150, 50) if G.boost > 0.5 else (100, 220, 100)
    hud = row(
        T("TERRAIN").fg((255, 180, 60)).bold,
        T(f"  {alt}m  ").fg((100, 160, 220)),
        T(f"{kmh}km/h").fg(spd_col).bold,
        T(f"   ★{G.score}").fg((255, 180, 60)).bold,
        T(f"   {G.dist / 1000.0:.1f}km").fg((80, 200, 255)).bold,
        gap=0,
    )
    help_line = T(
        "[wasd] steer  [space] ascend  [c] descend  [b] boost  [r] reset  [q] quit"
    ).fg((70, 65, 80))
    return col(
        component(_field, grow=1),
        hud,
        help_line,
        gap=0,
    )


if __name__ == "__main__":
    app.run()
