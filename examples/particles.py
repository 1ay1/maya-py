"""particles.py — PARTICLES: real-time particle physics simulation.

A faithful port of maya's `examples/particles.cpp`. A particle system rendered
through maya's native half-block surface (`halfblock`, 2x vertical resolution),
with five physics modes switched by number keys:

  1 FIREWORKS  rockets launch, arc under gravity, explode at apex into
               hue-varied bursts with sparkle and trails.
  2 GALAXY     spiral-arm placement with orbital velocities and 1/r^2
               gravity toward the centre; coloured by speed.
  3 FOUNTAIN   continuous water-blue spray with wind oscillation, ground
               bounce and splash droplets.
  4 VORTEX     two roaming attractors with radial + tangential force,
               warm/cool particle families.
  5 STARFIELD  warp-speed stars accelerating outward from the centre with
               velocity streak lines.

The C++ original drives maya's raw Canvas at 60fps with a 256-entry quantized
style LUT and up to 5000 particles. This port keeps the math, constants and
colours byte-for-byte faithful, but pure-Python particle loops are slow, so the
internal pixel buffer and particle count are CAPPED (see MAX_PW / MAX_PH /
MAX_PARTICLES) to keep frame time bounded regardless of window size.

  Keys: 1-5 mode · space burst · r reset · q/Esc quit

    PYTHONPATH=src python examples/particles.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, component, halfblock, row, upscale, target_size  # noqa: E402

# Pure-Python particle physics is far slower than the threaded C++ at 60fps, so
# the internal pixel buffer (MAX_PW x MAX_PH pixels) and the live particle count
# (MAX_PARTICLES) are CAPPED independently of the terminal size. The half-block
# field is emitted at its natural (small) size. The MATH is faithful; only the
# resolution and particle budget are bounded. Raise these for more detail at a
# lower framerate. (C++ caps particles at 5000 and uses full window resolution.)
MAX_PW = 96
MAX_PH = 48
MAX_PARTICLES = 1400

# Fixed render height in cells (maya's fullscreen height arg is a huge sentinel,
# so we never size the grid to the raw h). MAX_PH = ROWS * 2 half-block pixels.
ROWS = MAX_PH // 2

PI = 3.14159265
TAU = 6.28318530

TRAIL_LEN = 4


# ── Math helpers ──────────────────────────────────────────────────────────

def clampf(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def length(vx, vy):
    return math.sqrt(vx * vx + vy * vy)


def randf(lo, hi):
    return random.uniform(lo, hi)


def randf01():
    return random.random()


def gauss(mean, stddev):
    return random.gauss(mean, stddev)


def hsv_to_rgb(h, s, v):
    h = math.fmod(h, 1.0)
    if h < 0.0:
        h += 1.0
    hi = int(h * 6.0)
    f = h * 6.0 - hi
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    m = hi % 6
    if m == 0:
        return v, t, p
    if m == 1:
        return q, v, p
    if m == 2:
        return p, v, t
    if m == 3:
        return p, q, v
    if m == 4:
        return t, p, v
    return v, p, q


# ── Particle ──────────────────────────────────────────────────────────────
#
# A particle is a flat list (faster than attributes in tight Python loops):
#   [ x, y, vx, vy, ax, ay, life, max_life, r, g, b, size, type,
#     trail_count, [trail_x...], [trail_y...] ]
P_X, P_Y, P_VX, P_VY, P_AX, P_AY = 0, 1, 2, 3, 4, 5
P_LIFE, P_MAXLIFE, P_R, P_G, P_B, P_SIZE = 6, 7, 8, 9, 10, 11
P_TYPE, P_TRAILN, P_TX, P_TY = 12, 13, 14, 15


def make_particle(x, y, vx, vy, ax, ay, life, max_life, r, g, b, size, ptype):
    return [x, y, vx, vy, ax, ay, life, max_life, r, g, b, size, ptype,
            0, [0.0] * TRAIL_LEN, [0.0] * TRAIL_LEN]


# ── State ─────────────────────────────────────────────────────────────────

class Sim:
    def __init__(self):
        self.particles = []
        self.mode = 0  # 0=fireworks 1=galaxy 2=fountain 3=vortex 4=starfield
        self.pw = MAX_PW
        self.ph = MAX_PH
        self.time = 0.0
        self.frame = 0
        # Pixel buffer: flat list of [r, g, b], pw*ph entries.
        self.pixels = [[0.0, 0.0, 0.0] for _ in range(self.pw * self.ph)]


G = Sim()
random.seed(42)


# ── Pixel buffer ──────────────────────────────────────────────────────────

def clear_pixels():
    for px in G.pixels:
        px[0] = px[1] = px[2] = 0.0


def plot(fx, fy, r, g, b, alpha=1.0):
    px = int(fx)
    py = int(fy)
    if px < 0 or px >= G.pw or py < 0 or py >= G.ph:
        return
    p = G.pixels[py * G.pw + px]
    p[0] += r * alpha
    p[1] += g * alpha
    p[2] += b * alpha


def plot_glow(fx, fy, r, g, b, brightness):
    plot(fx, fy, r, g, b, brightness)
    dim = brightness * 0.3
    plot(fx - 1, fy, r, g, b, dim)
    plot(fx + 1, fy, r, g, b, dim)
    plot(fx, fy - 1, r, g, b, dim)
    plot(fx, fy + 1, r, g, b, dim)
    corner = brightness * 0.1
    plot(fx - 1, fy - 1, r, g, b, corner)
    plot(fx + 1, fy - 1, r, g, b, corner)
    plot(fx - 1, fy + 1, r, g, b, corner)
    plot(fx + 1, fy + 1, r, g, b, corner)


# ── Particle spawning per mode ────────────────────────────────────────────

def spawn_firework_rocket():
    x = randf(G.pw * 0.1, G.pw * 0.9)
    y = float(G.ph - 1)
    vx = randf(-1.5, 1.5)
    vy = randf(-14.0, -9.0)
    max_life = randf(0.6, 1.0)
    G.particles.append(make_particle(
        x, y, vx, vy, 0.0, 0.15, max_life, max_life,
        1.0, 0.9, 0.7, 1.5, 0))  # type 0 = rocket


def spawn_firework_burst(cx, cy):
    hue = randf01()
    count = int(randf(40, 80))
    for _ in range(count):
        angle = randf(0.0, TAU)
        speed = randf(1.0, 8.0)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        lt = randf(0.5, 1.2)
        h = hue + randf(-0.08, 0.08)
        r, g, b = hsv_to_rgb(h, randf(0.6, 1.0), 1.0)
        size = randf(0.6, 1.2)
        G.particles.append(make_particle(
            cx, cy, vx, vy, 0.0, 0.12, lt, lt, r, g, b, size, 1))


def spawn_galaxy_particles(count):
    cx = G.pw * 0.5
    cy = G.ph * 0.5
    for _ in range(count):
        arm = float(int(randf(0, 3))) * TAU / 3.0
        dist = randf(5.0, min(G.pw, G.ph) * 0.45)
        angle = arm + dist * 0.04 + randf(-0.3, 0.3)
        x = cx + math.cos(angle) * dist + gauss(0, 3.0)
        y = cy + math.sin(angle) * dist + gauss(0, 3.0)
        dx = x - cx
        dy = y - cy
        r = math.sqrt(dx * dx + dy * dy) + 0.1
        orbital_speed = 30.0 / math.sqrt(r)
        vx = -dy / r * orbital_speed + gauss(0, 0.5)
        vy = dx / r * orbital_speed + gauss(0, 0.5)
        size = randf(0.4, 1.0)
        G.particles.append(make_particle(
            x, y, vx, vy, 0.0, 0.0, 999.0, 999.0,
            1.0, 0.8, 0.6, size, 0))


def spawn_fountain_particles(count):
    cx = G.pw * 0.5
    base_y = G.ph * 0.85
    for _ in range(count):
        x = cx + gauss(0, 3.0)
        y = base_y
        vx = gauss(0, 3.0)
        vy = randf(-12.0, -7.0)
        ax = gauss(0.0, 0.02)  # slight wind
        lt = randf(1.0, 2.5)
        hue = randf(0.5, 0.65)
        r, g, b = hsv_to_rgb(hue, randf(0.5, 0.9), randf(0.7, 1.0))
        size = randf(0.5, 1.0)
        G.particles.append(make_particle(
            x, y, vx, vy, ax, 0.18, lt, lt, r, g, b, size, 0))


def spawn_vortex_particles(count):
    v1x, v1y = G.pw * 0.35, G.ph * 0.5
    v2x, v2y = G.pw * 0.65, G.ph * 0.5
    for i in range(count):
        left = (i % 2 == 0)
        cx = v1x if left else v2x
        cy = v1y if left else v2y
        angle = randf(0.0, TAU)
        dist = randf(2.0, min(G.pw, G.ph) * 0.25)
        x = cx + math.cos(angle) * dist
        y = cy + math.sin(angle) * dist
        vx = gauss(0, 1.0)
        vy = gauss(0, 1.0)
        lt = randf(2.0, 5.0)
        hue = randf(0.0, 0.1) if left else randf(0.55, 0.75)
        r, g, b = hsv_to_rgb(hue, randf(0.6, 1.0), randf(0.7, 1.0))
        size = randf(0.4, 0.9)
        ptype = 0 if left else 1
        G.particles.append(make_particle(
            x, y, vx, vy, 0.0, 0.0, lt, lt, r, g, b, size, ptype))


def spawn_starfield(count):
    cx = G.pw * 0.5
    cy = G.ph * 0.5
    for _ in range(count):
        angle = randf(0.0, TAU)
        dist = randf(1.0, 15.0)
        x = cx + math.cos(angle) * dist
        y = cy + math.sin(angle) * dist
        dx = x - cx
        dy = y - cy
        r = math.sqrt(dx * dx + dy * dy) + 0.1
        speed = randf(2.0, 6.0)
        vx = dx / r * speed
        vy = dy / r * speed
        lt = randf(2.0, 5.0)
        temp = randf(0.0, 1.0)
        if temp < 0.6:
            cr, cg, cb = 0.9, 0.9, 1.0
        elif temp < 0.8:
            cr, cg, cb = 1.0, 0.85, 0.6
        else:
            cr, cg, cb = 0.6, 0.7, 1.0
        size = randf(0.3, 1.2)
        G.particles.append(make_particle(
            x, y, vx, vy, 0.0, 0.0, lt, lt, cr, cg, cb, size, 0))


# ── Reset ─────────────────────────────────────────────────────────────────

def reset_particles():
    G.particles = []
    G.time = 0.0
    if G.mode == 1:
        spawn_galaxy_particles(min(2500, MAX_PARTICLES))
    elif G.mode == 2:
        pass  # fountain spawns continuously
    elif G.mode == 3:
        spawn_vortex_particles(min(2000, MAX_PARTICLES))
    elif G.mode == 4:
        spawn_starfield(min(1500, MAX_PARTICLES))
    # mode 0 (fireworks) spawns periodically


# Population targets, scaled by the particle cap.
GALAXY_POP = min(2500, MAX_PARTICLES)
VORTEX_POP = min(2000, MAX_PARTICLES)


# ── Physics update ────────────────────────────────────────────────────────

def update_particles(dt):
    G.time += dt

    # Mode-specific spawning
    if G.mode == 0:  # Fireworks: periodic rocket launches
        if G.frame % 15 == 0:
            spawn_firework_rocket()
    elif G.mode == 1:  # Galaxy: maintain population
        if len(G.particles) < GALAXY_POP:
            spawn_galaxy_particles(5)
    elif G.mode == 2:  # Fountain: continuous spray
        spawn_fountain_particles(8)
    elif G.mode == 3:  # Vortex: maintain population
        if len(G.particles) < VORTEX_POP:
            spawn_vortex_particles(10)
    elif G.mode == 4:  # Starfield: continuous spawning
        spawn_starfield(10)

    cx = G.pw * 0.5
    cy = G.ph * 0.5
    mode = G.mode
    parts = G.particles
    new_particles = []  # splash droplets spawned mid-loop

    for p in parts:
        # Save trail
        tc = p[P_TRAILN]
        tx = p[P_TX]
        ty = p[P_TY]
        if tc < TRAIL_LEN:
            tx[tc] = p[P_X]
            ty[tc] = p[P_Y]
            p[P_TRAILN] = tc + 1
        else:
            for i in range(TRAIL_LEN - 1):
                tx[i] = tx[i + 1]
                ty[i] = ty[i + 1]
            tx[TRAIL_LEN - 1] = p[P_X]
            ty[TRAIL_LEN - 1] = p[P_Y]

        # Mode-specific forces
        if mode == 1:  # Galaxy: gravitational attraction to center
            dx = cx - p[P_X]
            dy = cy - p[P_Y]
            r = math.sqrt(dx * dx + dy * dy) + 1.0
            force = 800.0 / (r * r)
            if force > 5.0:
                force = 5.0
            p[P_AX] = dx / r * force
            p[P_AY] = dy / r * force
            p[P_VX] *= 0.998
            p[P_VY] *= 0.998
        elif mode == 2:  # Fountain: slight wind oscillation + ground bounce
            p[P_AX] = math.sin(G.time * 0.5) * 0.05
            ground = G.ph * 0.85
            if p[P_Y] >= ground and p[P_VY] > 0:
                p[P_VY] *= -0.3
                p[P_VX] *= 0.8
                p[P_Y] = ground - 1
                if abs(p[P_VY]) > 1.0 and \
                        len(parts) + len(new_particles) < min(4000, MAX_PARTICLES):
                    for _ in range(2):
                        sx = p[P_X] + randf(-2, 2)
                        sy = ground - 1
                        svx = randf(-2, 2)
                        svy = randf(-3, -1)
                        slt = randf(0.2, 0.5)
                        sp = make_particle(
                            sx, sy, svx, svy, 0.0, 0.18, slt, slt,
                            p[P_R] * 0.8, p[P_G] * 0.8, p[P_B] * 0.8, 0.3, 1)
                        new_particles.append(sp)
        elif mode == 3:  # Vortex: two attractors with tangential force
            v1x = G.pw * 0.35 + math.sin(G.time * 0.3) * G.pw * 0.05
            v1y = G.ph * 0.5 + math.cos(G.time * 0.4) * G.ph * 0.05
            v2x = G.pw * 0.65 + math.cos(G.time * 0.35) * G.pw * 0.05
            v2y = G.ph * 0.5 + math.sin(G.time * 0.45) * G.ph * 0.05
            atx = v1x if p[P_TYPE] == 0 else v2x
            aty = v1y if p[P_TYPE] == 0 else v2y
            dx = atx - p[P_X]
            dy = aty - p[P_Y]
            r = math.sqrt(dx * dx + dy * dy) + 1.0
            force = 200.0 / (r + 10.0)
            p[P_AX] = dx / r * force + (-dy / r) * force * 0.8
            p[P_AY] = dy / r * force + (dx / r) * force * 0.8
            p[P_VX] *= 0.99
            p[P_VY] *= 0.99
        elif mode == 4:  # Starfield: accelerate outward
            dx = p[P_X] - cx
            dy = p[P_Y] - cy
            r = math.sqrt(dx * dx + dy * dy) + 0.1
            accel = 1.5 + r * 0.03
            p[P_AX] = dx / r * accel
            p[P_AY] = dy / r * accel

        # Integrate
        p[P_VX] += p[P_AX] * dt
        p[P_VY] += p[P_AY] * dt
        p[P_X] += p[P_VX]
        p[P_Y] += p[P_VY]
        p[P_LIFE] -= dt

        # Fireworks: rocket explodes when velocity reverses or near apex
        if mode == 0 and p[P_TYPE] == 0 and p[P_VY] >= -1.0:
            spawn_firework_burst(p[P_X], p[P_Y])
            p[P_LIFE] = 0.0

    if new_particles:
        parts.extend(new_particles)

    # Remove dead particles and out-of-bounds
    margin = 20.0
    pw, ph = G.pw, G.ph
    alive = []
    for p in parts:
        if p[P_LIFE] <= 0.0:
            continue
        if p[P_X] < -margin or p[P_X] >= pw + margin or \
                p[P_Y] < -margin or p[P_Y] >= ph + margin:
            continue
        alive.append(p)
    G.particles = alive

    # Cap particle count (C++ caps at 5000; we cap at MAX_PARTICLES)
    if len(G.particles) > MAX_PARTICLES:
        G.particles = G.particles[len(G.particles) - MAX_PARTICLES:]


# ── Render particles into pixel buffer ────────────────────────────────────

def render_particles():
    clear_pixels()
    mode = G.mode
    pw, ph = G.pw, G.ph

    for p in G.particles:
        age = 1.0 - (p[P_LIFE] / p[P_MAXLIFE])  # 0=new, 1=dead
        fade = max(0.0, p[P_LIFE] / p[P_MAXLIFE])

        cr, cg, cb = p[P_R], p[P_G], p[P_B]

        if mode == 1:
            # Galaxy: color by velocity magnitude
            speed = length(p[P_VX], p[P_VY])
            t = clampf(speed / 15.0, 0.0, 1.0)
            if t < 0.5:
                s = t * 2.0
                cr = 1.0 - s * 0.5
                cg = s
                cb = s * 0.3
            else:
                s = (t - 0.5) * 2.0
                cr = 0.5 - s * 0.5
                cg = 1.0 - s * 0.5
                cb = 0.3 + s * 0.7
        elif mode == 4:
            # Starfield: brighter further from center
            dx = p[P_X] - pw * 0.5
            dy = p[P_Y] - ph * 0.5
            dist = math.sqrt(dx * dx + dy * dy)
            maxd = math.sqrt(float(pw * pw + ph * ph)) * 0.5
            t = clampf(dist / maxd, 0.0, 1.0)
            fade *= (0.3 + t * 0.7)

        brightness = fade * p[P_SIZE]

        # Draw trails
        tc = p[P_TRAILN]
        tx = p[P_TX]
        ty = p[P_TY]
        for t in range(tc):
            trail_fade = float(t + 1) / float(tc + 1)
            trail_fade *= 0.3 * fade
            plot(tx[t], ty[t], cr, cg, cb, trail_fade * p[P_SIZE])

        # Draw particle with glow
        if p[P_SIZE] > 0.8:
            plot_glow(p[P_X], p[P_Y], cr, cg, cb, brightness)
        else:
            plot(p[P_X], p[P_Y], cr, cg, cb, brightness)

        # Firework sparkle effect
        if mode == 0 and p[P_TYPE] == 1 and age > 0.5:
            sparkle = (math.sin(G.time * 30.0 + p[P_X] * 7.0 + p[P_Y] * 11.0) + 1.0) * 0.5
            if sparkle > 0.7:
                plot(p[P_X], p[P_Y], 1.0, 1.0, 1.0, sparkle * fade * 0.5)

        # Starfield streak lines
        if mode == 4:
            speed = length(p[P_VX], p[P_VY])
            if speed > 3.0:
                streak_len = min(speed * 0.4, 8.0)
                nx = -p[P_VX] / speed
                ny = -p[P_VY] / speed
                s = 1.0
                while s < streak_len:
                    sf = 1.0 - s / streak_len
                    plot(p[P_X] + nx * s, p[P_Y] + ny * s, cr, cg, cb,
                         brightness * sf * 0.5)
                    s += 1.0


# ── Tone mapping → half-block grid ────────────────────────────────────────

def _tm(v):
    # Simple clamp with slight gamma (sqrt), as in the C++ paint().
    return clampf(math.sqrt(clampf(v, 0.0, 1.0)), 0.0, 1.0)


def pixels_to_grid():
    pw, ph = G.pw, G.ph
    pix = G.pixels
    grid = [[None] * pw for _ in range(ph)]
    for y in range(ph):
        rowg = grid[y]
        base = y * pw
        for x in range(pw):
            p = pix[base + x]
            r = p[0]
            g = p[1]
            b = p[2]
            if r > 0.0 or g > 0.0 or b > 0.0:
                rowg[x] = (int(_tm(r) * 255), int(_tm(g) * 255), int(_tm(b) * 255))
    return grid


# ── App ───────────────────────────────────────────────────────────────────

app = App("particles", inline=False, fps=30)
app.state(_t=0.0)

MODE_NAMES = ["FIREWORKS", "GALAXY", "FOUNTAIN", "VORTEX", "STARFIELD"]


def _set_mode(m):
    G.mode = m
    reset_particles()


@app.on("1")
def _m1(s):
    _set_mode(0)


@app.on("2")
def _m2(s):
    _set_mode(1)


@app.on("3")
def _m3(s):
    _set_mode(2)


@app.on("4")
def _m4(s):
    _set_mode(3)


@app.on("5")
def _m5(s):
    _set_mode(4)


@app.on("r")
def _reset(s):
    reset_particles()


@app.on("space")
def _burst(s):
    # Burst at random position
    bx = randf(G.pw * 0.15, G.pw * 0.85)
    by = randf(G.ph * 0.15, G.ph * 0.85)
    if G.mode == 0:
        spawn_firework_burst(bx, by)
    else:
        hue = randf01()
        count = 60
        ay = 0.15 if G.mode == 2 else 0.0
        for _ in range(count):
            angle = randf(0.0, TAU)
            speed = randf(2.0, 10.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            lt = randf(0.5, 1.5)
            h = hue + randf(-0.1, 0.1)
            r, g, b = hsv_to_rgb(h, 0.9, 1.0)
            size = randf(0.5, 1.2)
            G.particles.append(make_particle(
                bx, by, vx, vy, 0.0, ay, lt, lt, r, g, b, size, 1))


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _tick(s, dt):
    G.frame += 1
    # Match the C++ fixed-step feel: clamp dt to 0.05 like paint().
    update_particles(min(1.0 / 30.0, 0.05))


def _field(w, h):
    # Render into the CAPPED internal pixel buffer (frame time bounded), then
    # NEAREST-NEIGHBOUR UPSCALE it to fill the whole half-block field so the
    # particle field fills the screen exactly like the C++ fullscreen original
    # — identical layout, lower detail. Raise MAX_PW/MAX_PH for resolution.
    render_particles()
    out_w, out_h = target_size(w, h)
    return halfblock(upscale(pixels_to_grid(), out_w, out_h))


@app.view
def view(s):
    # The smoke harness drives view(s) a few times with no frame handler, so
    # advance the simulation here too (idempotent enough for one frame).
    G.frame += 1
    update_particles(min(1.0 / 30.0, 0.05))

    status = row_status()
    return col(
        component(_field, grow=1),
        status,
        gap=0,
    )


def row_status():
    accent = (80, 200, 255)
    txt = (180, 180, 180)
    return row(
        T("PARTICLES").fg(accent).bold,
        T(" │ ").fg(txt),
        T(MODE_NAMES[G.mode]).fg(accent).bold,
        T(f" │ {len(G.particles)} particles │ "
          "[1-5] mode [spc] burst [r] reset [q] quit").fg(txt),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
