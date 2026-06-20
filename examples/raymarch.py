"""raymarch.py — RAYMARCH: real-time SDF 3D renderer.

A faithful port of maya's `examples/raymarch.cpp`. A signed-distance-field
raymarcher with reflective surfaces, a sunset sky, a hash-based twinkling star
field, Fresnel-Schlick reflectivity, ACES-ish tone mapping, soft shadows,
ambient occlusion, colored key/fill lights, and four switchable scenes
(sphere+torus, metaballs, columns, cathedral) viewed through an orbit camera.

The C++ original threads the per-pixel raymarch across every CPU core and runs
at 30fps. This port keeps the math/constants/colors byte-for-byte faithful and
renders through maya's native half-block surface (`halfblock`), but the
per-pixel raymarch runs in pure Python — so it's a low-resolution slideshow
rather than a 30fps render. The MAX_PW / MAX_PH knobs trade resolution for
framerate; raise them for more detail at lower framerate.

  Keys: ←→ orbit speed · ↑↓ pitch · 1-4 scene · space pause · q/Esc quit

    PYTHONPATH=src python examples/raymarch.py
"""

from __future__ import annotations

import math

import _bootstrap  # noqa: F401,E402

from maya_py import App, T, col, component, halfblock, row, upscale, target_size  # noqa: E402

# Pure-Python raymarching is ~100x slower than the threaded C++. We render into
# a small internal pixel buffer whose size is CAPPED (independent of the
# terminal size) so a large window can't push frame time to seconds — the
# half-block field is emitted at its natural (small) size. Raise MAX_PW/MAX_PH
# for more detail at lower framerate. Reflections + soft shadows + AO make each
# pixel expensive, so these caps are deliberately small.
MAX_PW = 22
MAX_PH = 14

PI = 3.14159265
TAU = 6.28318530
EPS = 0.001
MAX_STEPS = 64
MAX_DIST = 50.0


# ── vec3 (as plain tuples) ───────────────────────────────────────────────────

def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vmulv(a, b):
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def vneg(a):
    return (-a[0], -a[1], -a[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(v):
    return math.sqrt(dot(v, v))


def normalize(v):
    inv = 1.0 / (length(v) + 1e-9)
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def vabs(v):
    return (abs(v[0]), abs(v[1]), abs(v[2]))


def vmax_s(v, b):
    return (max(v[0], b), max(v[1], b), max(v[2], b))


def vmin_s(v, b):
    return (min(v[0], b), min(v[1], b), min(v[2], b))


def vmix(a, b, t):
    return vadd(vscale(a, 1.0 - t), vscale(b, t))


def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def smoothstep(e0, e1, x):
    t = clampf((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ── SDF primitives ───────────────────────────────────────────────────────────

def sd_sphere(p, r):
    return length(p) - r


def sd_torus(p, r1, r2):
    q = math.sqrt(p[0] * p[0] + p[2] * p[2]) - r1
    return math.sqrt(q * q + p[1] * p[1]) - r2


def sd_plane(p, n, h):
    return dot(p, n) + h


def sd_box(p, b):
    d = vsub(vabs(p), b)
    return length(vmax_s(d, 0.0)) + min(max(d[0], max(d[1], d[2])), 0.0)


def sd_capsule(p, a, b, r):
    ab = vsub(b, a)
    ap = vsub(p, a)
    t = clampf(dot(ap, ab) / dot(ab, ab), 0.0, 1.0)
    return length(vsub(p, vadd(a, vscale(ab, t)))) - r


def smooth_union(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


# ── Rotation ─────────────────────────────────────────────────────────────────

def rot_y(p, a):
    c = math.cos(a)
    s = math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def rot_x(p, a):
    c = math.cos(a)
    s = math.sin(a)
    return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)


def rot_z(p, a):
    c = math.cos(a)
    s = math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2])


# ── Global state ─────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.scene = 0
        self.time = 0.0
        self.paused = False
        self.orbit_speed = 0.3
        self.pitch = 0.3
        self.frame = 0
        self.elapsed = 0.0


G = World()


# ── Scenes ───────────────────────────────────────────────────────────────────
# Material IDs: 0=ground, 1=primary, 2=secondary, 3=sky, 4=emissive
# A "Hit" is the tuple (d, mat).

def scene_classic(p):
    ground = sd_plane(p, (0, 1, 0), 0.0)
    bob = math.sin(G.time * 1.8) * 0.5 + 1.5
    sphere = sd_sphere(vsub(p, (0, bob, 0)), 1.0)
    tp = rot_y(vsub(p, (0, 1.2, 0)), G.time * 0.6)
    tp = rot_x(tp, G.time * 0.4)
    torus = sd_torus(tp, 2.0, 0.35)

    # Floating crystal ring
    rp = rot_y(vsub(p, (0, bob, 0)), -G.time * 1.2)
    ring = sd_torus(rp, 1.8, 0.06)

    d, mat = ground, 0
    if sphere < d:
        d, mat = sphere, 1
    if torus < d:
        d, mat = torus, 2
    if ring < d:
        d, mat = ring, 4
    return (d, mat)


def scene_metaballs(p):
    ground = sd_plane(p, (0, 1, 0), 0.0)
    t = G.time * 0.8
    s1 = sd_sphere(vsub(p, (math.sin(t) * 1.5, 1.2 + math.sin(t * 1.3) * 0.4, math.cos(t) * 1.5)), 0.8)
    s2 = sd_sphere(vsub(p, (math.cos(t * 0.7) * 1.8, 1.5 + math.cos(t * 1.1) * 0.3, math.sin(t * 0.9) * 1.8)), 0.7)
    s3 = sd_sphere(vsub(p, (0, 1.0 + math.sin(t * 1.6) * 0.6, 0)), 0.9)
    s4 = sd_sphere(vsub(p, (math.sin(t * 1.1) * 1.2, 0.8 + math.cos(t * 0.8) * 0.5, math.cos(t * 1.4) * 1.2)), 0.5)
    blob = smooth_union(smooth_union(s1, s2, 0.8), smooth_union(s3, s4, 0.8), 0.8)

    d, mat = ground, 0
    if blob < d:
        d, mat = blob, 1
    return (d, mat)


def scene_columns(p):
    ground = sd_plane(p, (0, 1, 0), 0.0)
    # Infinite repeating columns
    rx = math.fmod(abs(p[0]) + 2.0, 4.0) - 2.0
    rz = math.fmod(abs(p[2]) + 2.0, 4.0) - 2.0
    rp = (rx, p[1], rz)
    column = sd_box(vsub(rp, (0, 2.5, 0)), (0.3, 2.5, 0.3))
    # Floating orb
    orb = sd_sphere(vsub(p, (0, 2.0 + math.sin(G.time) * 0.5, 0)), 0.6)
    # Orbiting emissive particles
    p1 = sd_sphere(vsub(p, (math.sin(G.time * 1.5) * 3.0, 1.5 + math.cos(G.time * 2.0) * 0.5, math.cos(G.time * 1.5) * 3.0)), 0.15)
    p2 = sd_sphere(vsub(p, (math.cos(G.time * 1.2) * 2.5, 2.5 + math.sin(G.time * 1.7) * 0.3, math.sin(G.time * 1.2) * 2.5)), 0.12)

    d, mat = ground, 0
    if column < d:
        d, mat = column, 2
    if orb < d:
        d, mat = orb, 1
    if p1 < d:
        d, mat = p1, 4
    if p2 < d:
        d, mat = p2, 4
    return (d, mat)


def scene_cathedral(p):
    ground = sd_plane(p, (0, 1, 0), 0.0)

    # Tall arched columns in a circle
    cols = MAX_DIST
    for i in range(8):
        a = float(i) * TAU / 8.0
        r = 4.0
        cp = (math.cos(a) * r, 0, math.sin(a) * r)
        c = sd_capsule(p, cp, vadd(cp, (0, 5.0, 0)), 0.2)
        cols = min(cols, c)

    # Central glowing orb
    orb = sd_sphere(vsub(p, (0, 3.0 + math.sin(G.time * 0.7) * 0.3, 0)), 0.8)

    # Rotating rings around orb
    r1p = rot_y(vsub(p, (0, 3.0, 0)), G.time * 0.5)
    r1p = rot_x(r1p, PI * 0.3)
    ring1 = sd_torus(r1p, 1.8, 0.05)
    r2p = rot_y(vsub(p, (0, 3.0, 0)), -G.time * 0.4)
    r2p = rot_z(r2p, PI * 0.4)
    ring2 = sd_torus(r2p, 2.2, 0.04)

    d, mat = ground, 0
    if cols < d:
        d, mat = cols, 2
    if orb < d:
        d, mat = orb, 1
    if ring1 < d:
        d, mat = ring1, 4
    if ring2 < d:
        d, mat = ring2, 4
    return (d, mat)


def map_scene(p):
    if G.scene == 1:
        return scene_metaballs(p)
    if G.scene == 2:
        return scene_columns(p)
    if G.scene == 3:
        return scene_cathedral(p)
    return scene_classic(p)


def map_dist(p):
    return map_scene(p)[0]


# ── Raymarching ──────────────────────────────────────────────────────────────

def raymarch(ro, rd):
    t = 0.0
    hit_d, hit_mat = MAX_DIST, 3
    i = 0
    while i < MAX_STEPS and t < MAX_DIST:
        p = vadd(ro, vscale(rd, t))
        sd, smat = map_scene(p)
        if sd < EPS:
            hit_d, hit_mat = t, smat
            break
        t += sd
        i += 1
    return (t, hit_mat)


def calc_normal(p):
    e = 0.001
    d = map_dist(p)
    return normalize((
        map_dist(vadd(p, (e, 0, 0))) - d,
        map_dist(vadd(p, (0, e, 0))) - d,
        map_dist(vadd(p, (0, 0, e))) - d,
    ))


# ── Lighting ─────────────────────────────────────────────────────────────────

def soft_shadow(ro, rd, mint, maxt, k):
    res = 1.0
    t = mint
    i = 0
    while i < 20 and t < maxt:
        d = map_dist(vadd(ro, vscale(rd, t)))
        if d < EPS:
            return 0.0
        res = min(res, k * d / t)
        t += max(d, 0.02)
        i += 1
    return max(res, 0.0)


def calc_ao(p, n):
    occ = 0.0
    scale = 1.0
    for i in range(3):
        h = 0.01 + 0.15 * float(i)
        d = map_dist(vadd(p, vscale(n, h)))
        occ += (h - d) * scale
        scale *= 0.95
    return max(1.0 - 3.0 * occ, 0.0)


def fresnel(cos_theta, f0):
    return f0 + (1.0 - f0) * math.pow(1.0 - clampf(cos_theta, 0.0, 1.0), 5.0)


# Color helpers (Color3 == plain (r, g, b) tuple of floats).
def cmix(a, b, t):
    return (a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t, a[2] * (1 - t) + b[2] * t)


def cadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def cmul_s(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cmul(a, b):
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


# ── Sky ──────────────────────────────────────────────────────────────────────

def sky_color(rd):
    y = rd[1]

    # Sunset gradient: deep blue → orange → warm horizon
    deep_sky = (0.02, 0.03, 0.12)   # deep navy
    mid_sky = (0.08, 0.05, 0.20)    # purple
    horizon = (0.45, 0.18, 0.08)    # warm orange
    ground_c = (0.02, 0.02, 0.03)   # below horizon

    if y < 0.0:
        c = cmix(ground_c, horizon, smoothstep(-0.3, 0.0, y))
    elif y < 0.15:
        c = cmix(horizon, mid_sky, smoothstep(0.0, 0.15, y))
    else:
        c = cmix(mid_sky, deep_sky, smoothstep(0.15, 0.7, y))

    # Sun glow
    sun_dir = normalize((0.6, 0.15, -0.4))
    sun_dot = max(dot(rd, sun_dir), 0.0)
    sun = math.pow(sun_dot, 64.0)
    glow = math.pow(sun_dot, 8.0)
    c = cadd(c, (sun * 2.0, sun * 1.5, sun * 0.8))
    c = cadd(c, (glow * 0.3, glow * 0.12, glow * 0.04))

    # Stars (hash-based, only in upper sky)
    if y > 0.2:
        star_h = abs(math.sin(rd[0] * 213.17 + rd[2] * 437.23) *
                     math.cos(rd[0] * 171.31 + rd[2] * 339.41))
        star_h = math.pow(star_h, 80.0)
        star_bright = star_h * smoothstep(0.2, 0.5, y) * 2.0
        # Twinkling
        twinkle = 0.7 + 0.3 * math.sin(G.time * 3.0 + rd[0] * 100.0 + rd[2] * 200.0)
        star_bright *= twinkle
        c = cadd(c, (star_bright, star_bright, star_bright * 1.2))

    return c


# ── Shading ──────────────────────────────────────────────────────────────────

def get_reflection(p, n, rd, depth):
    if depth > 1:
        return sky_color(rd)
    refl_dir = vsub(rd, vscale(n, 2.0 * dot(rd, n)))
    refl_ro = vadd(p, vscale(n, 0.03))
    rd_t, rd_mat = raymarch(refl_ro, refl_dir)
    if rd_t >= MAX_DIST:
        return sky_color(refl_dir)
    rp = vadd(refl_ro, vscale(refl_dir, rd_t))
    rn = calc_normal(rp)
    rc = shade(rp, rn, refl_dir, rd_mat, depth + 1)
    # Fade reflections with distance
    fog = 1.0 - math.exp(-0.02 * rd_t * rd_t)
    return cmix(rc, sky_color(refl_dir), fog)


def shade(p, n, rd, mat, depth):
    # Two lights: warm key + cool fill
    key_dir = normalize((0.6, 0.8, -0.4))
    fill_dir = normalize((-0.4, 0.3, 0.6))
    key_col = (1.2, 0.95, 0.7)    # warm sun
    fill_col = (0.15, 0.18, 0.35)  # cool sky fill

    key_diff = max(dot(n, key_dir), 0.0)
    fill_diff = max(dot(n, fill_dir), 0.0)
    shadow = soft_shadow(vadd(p, vscale(n, 0.02)), key_dir, 0.02, 12.0, 16.0)
    ao = calc_ao(p, n)

    # Specular (Blinn-Phong)
    half_v = normalize(vsub(key_dir, rd))
    ndh = max(dot(n, half_v), 0.0)

    # Fresnel for reflectivity
    ndv = max(dot(n, vscale(rd, -1.0)), 0.0)

    albedo = (0.0, 0.0, 0.0)
    roughness = 0.5
    metallic = 0.0
    emissive = 0.0

    if mat == 0:
        # Reflective checkerboard ground
        cx = int(math.floor(p[0] + 0.001)) + int(math.floor(p[2] + 0.001))
        if cx & 1:
            albedo = (0.40, 0.38, 0.42)
        else:
            albedo = (0.10, 0.10, 0.12)
        roughness = 0.3
        metallic = 0.1
    elif mat == 1:
        # Chrome/glass sphere — highly reflective
        if G.scene == 1:
            # Metaballs: iridescent color based on normal
            t = G.time * 0.3
            albedo = (
                0.3 + 0.3 * math.sin(n[0] * 3.0 + t),
                0.3 + 0.3 * math.sin(n[1] * 3.0 + t + 2.1),
                0.5 + 0.3 * math.sin(n[2] * 3.0 + t + 4.2),
            )
            metallic = 0.7
            roughness = 0.15
        elif G.scene == 3:
            # Cathedral: glowing crystal orb
            albedo = (0.4, 0.7, 1.0)
            metallic = 0.9
            roughness = 0.05
            emissive = 0.6 + 0.3 * math.sin(G.time * 2.0)
        else:
            albedo = (0.15, 0.3, 0.8)
            metallic = 0.9
            roughness = 0.05
    elif mat == 2:
        if G.scene == 2:
            # Marble columns
            marble = 0.5 + 0.5 * math.sin(p[1] * 5.0 + math.sin(p[0] * 2.0) * 2.0)
            albedo = (0.75 * marble + 0.2, 0.72 * marble + 0.18, 0.68 * marble + 0.15)
            roughness = 0.4
        elif G.scene == 3:
            # Cathedral columns: dark stone
            albedo = (0.25, 0.22, 0.28)
            roughness = 0.7
        else:
            # Gold torus
            albedo = (0.9, 0.65, 0.15)
            metallic = 0.85
            roughness = 0.15
    elif mat == 4:
        # Emissive
        pulse = 0.7 + 0.3 * math.sin(G.time * 4.0)
        if G.scene == 3:
            albedo = (0.3 * pulse, 0.6 * pulse, 1.0 * pulse)
        elif G.scene == 0:
            albedo = (0.2 * pulse, 0.8 * pulse, 1.0 * pulse)
        else:
            albedo = (1.0 * pulse, 0.4 * pulse, 0.1 * pulse)
        emissive = 2.0

    # Specular power from roughness
    spec_power = 2.0 / (roughness * roughness + 0.001)
    spec = math.pow(ndh, spec_power)

    # Fresnel blend
    f = fresnel(ndv, 0.7 if metallic > 0.5 else 0.04)

    # Diffuse contribution
    diff_light = cadd(
        cmul_s(key_col, key_diff * shadow),
        cmul_s(fill_col, fill_diff),
    )
    diffuse = cmul_s(cmul(albedo, diff_light), 1.0 - f * metallic)

    # Specular contribution (metallic tints specular with albedo)
    spec_col = albedo if metallic > 0.5 else (1.0, 1.0, 1.0)
    specular = cmul_s(cmul(spec_col, key_col), spec * shadow * f)

    # Ambient
    ambient = cmul_s(albedo, 0.08)

    color = cadd(cadd(diffuse, specular), ambient)

    # Reflections for metallic/smooth surfaces
    if (metallic > 0.3 or roughness < 0.35) and depth < 1:
        refl = get_reflection(p, n, rd, depth)
        refl_strength = f * (1.0 - roughness * 0.7)
        if metallic > 0.5:
            color = cmix(color, cmul(refl, albedo), refl_strength * 0.6)
        else:
            color = cmix(color, refl, refl_strength * 0.25)

    # Ground reflection (subtle)
    if mat == 0 and depth < 1:
        refl = get_reflection(p, n, rd, depth)
        ground_f = fresnel(ndv, 0.02)
        color = cmix(color, refl, ground_f * 0.35)

    # Emissive glow
    if emissive > 0.0:
        color = cadd(color, cmul_s(albedo, emissive))

    # Apply AO
    color = cmul_s(color, ao)

    return color


# ── Render a single pixel ────────────────────────────────────────────────────

def _tonemap(x):
    a = x * (x + 0.0245786) - 0.000090537
    b = x * (0.983729 * x + 0.4329510) + 0.238081
    return clampf(a / b, 0.0, 1.0)


def render_pixel(ro, rd):
    hd, hmat = raymarch(ro, rd)
    if hd >= MAX_DIST:
        return sky_color(rd)

    p = vadd(ro, vscale(rd, hd))
    n = calc_normal(p)
    color = shade(p, n, rd, hmat, 0)

    # Distance fog — tinted with warm horizon
    fog = 1.0 - math.exp(-0.012 * hd * hd)
    fog_col = sky_color(rd)
    color = cmix(color, fog_col, fog)

    # Tone mapping (ACES-ish)
    color = (_tonemap(color[0]), _tonemap(color[1]), _tonemap(color[2]))

    return color


# ── Frame / camera ───────────────────────────────────────────────────────────

def game_tick(dt):
    dt = min(dt, 0.1)
    if not G.paused:
        G.time += dt
        G.elapsed += dt
    G.frame += 1


def _field(w, h):
    # Render a small CAPPED internal buffer in pure Python (bounded frame time),
    # then NEAREST-NEIGHBOUR UPSCALE it to fill the whole half-block field so the
    # scene fills the screen exactly like the threaded C++ original — identical
    # layout, lower detail. Raise MAX_PW/MAX_PH to trade fps for detail.
    out_w, out_h = target_size(w, h)
    pixel_w = max(1, min(MAX_PW, out_w))
    pixel_h = max(2, min(MAX_PH, out_h))
    if pixel_h % 2:
        pixel_h += 1

    # Camera (faithful to the C++ orbit camera).
    angle = G.time * G.orbit_speed
    cam_r = 8.0 if G.scene == 3 else 6.0
    cam_y = 2.5 + math.sin(G.time * 0.2) * 0.8
    ro = (math.cos(angle) * cam_r, cam_y, math.sin(angle) * cam_r)
    target = (0.0, 2.5 if G.scene == 3 else 1.0, 0.0)

    # Camera basis
    fwd = normalize(vsub(target, ro))
    right = normalize((fwd[2], 0.0, -fwd[0]))
    up = (
        right[1] * fwd[2] - right[2] * fwd[1],
        right[2] * fwd[0] - right[0] * fwd[2],
        right[0] * fwd[1] - right[1] * fwd[0],
    )
    cp = math.cos(G.pitch)
    sp = math.sin(G.pitch)
    fwd2 = vadd(vscale(fwd, cp), vscale(up, sp))
    up2 = vsub(vscale(up, cp), vscale(fwd, sp))

    aspect = float(pixel_w) / float(pixel_h)
    fov = 1.2

    grid = [[None] * pixel_w for _ in range(pixel_h)]
    for py in range(pixel_h):
        v = (1.0 - 2.0 * (py + 0.5) / pixel_h) * fov
        rowg = grid[py]
        for px in range(pixel_w):
            u = (2.0 * (px + 0.5) / pixel_w - 1.0) * aspect * fov
            rd = normalize(vadd(vadd(fwd2, vscale(right, u)), vscale(up2, v)))
            c = render_pixel(ro, rd)
            rowg[px] = (int(clampf(c[0], 0, 1) * 255),
                        int(clampf(c[1], 0, 1) * 255),
                        int(clampf(c[2], 0, 1) * 255))
    return halfblock(upscale(grid, out_w, out_h))


# ── App ──────────────────────────────────────────────────────────────────────

app = App.fullscreen("RAYMARCH", fps=30)
app.state(_t=0.0)

SCENE_NAMES = ["sphere+torus", "metaballs", "columns", "cathedral"]


@app.on("space")
def _pause(s):
    G.paused = not G.paused


@app.on("1")
def _s1(s):
    G.scene = 0


@app.on("2")
def _s2(s):
    G.scene = 1


@app.on("3")
def _s3(s):
    G.scene = 2


@app.on("4")
def _s4(s):
    G.scene = 3


@app.on("left")
def _orbit_l(s):
    G.orbit_speed -= 0.1


@app.on("right")
def _orbit_r(s):
    G.orbit_speed += 0.1


@app.on("up")
def _pitch_up(s):
    G.pitch = min(G.pitch + 0.1, 1.2)


@app.on("down")
def _pitch_dn(s):
    G.pitch = max(G.pitch - 0.1, -0.2)


app.quit_on("q", "esc")


app.simulate(game_tick)


@app.view
def view(s):
    fps = int(G.frame / G.elapsed) if G.elapsed > 0.5 else 0
    status = row(
        T(f" RAYMARCH │ fps:{fps} │ {SCENE_NAMES[G.scene]} │ "
          f"[←→] orbit [↑↓] pitch [1-4] scene [spc] "
          f"{'resume' if G.paused else 'pause'} ").fg((255, 160, 60)).bold,
        T("  [q] quit").fg((80, 60, 90)),
        gap=0,
    )
    return col(component(_field, grow=1), status, gap=0)


if __name__ == "__main__":
    app.run()
