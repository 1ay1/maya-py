"""music.py — Terminal music player with animated visualizations.

A faithful port of maya's `examples/music.cpp`. A Spotify/Apple-Music-inspired
player with animated heatmap album art, a sparkline audio visualizer, a seek
bar, genre badges, and a scrollable playlist — all simulated, all rendered
through maya's native widgets.

  Controls:
    space   play/pause      n  next        p  prev
    s       shuffle         r  repeat      +/-  volume
    j/k or ↑/↓  scroll playlist            q/Esc  quit

    PYTHONPATH=src python examples/music.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, grow, spacer,
    heatmap, sparkline, progress, badge, clamp, randf, bar,
)


# Track: title, artist, genre, duration, freq_base, freq_mod, low(rgb), high(rgb)
TRACKS = [
    ("Neon Dreams", "Synthwave Collective", "Synthwave", 15.0, 2.0, 1.5, (20, 0, 60), (0, 255, 200)),
    ("Binary Sunset", "The Algorithms", "Ambient", 15.0, 1.2, 0.8, (10, 10, 40), (255, 140, 50)),
    ("Stack Overflow", "Debug Mode", "Electronic", 15.0, 3.5, 2.2, (40, 5, 10), (255, 60, 80)),
    ("Quantum Entangled", "Hadron", "IDM", 15.0, 4.0, 3.0, (15, 0, 40), (180, 80, 255)),
    ("Hello World", "printf()", "Chiptune", 15.0, 5.0, 4.0, (5, 30, 5), (80, 255, 80)),
    ("Segmentation Fault", "Core Dump", "Industrial", 15.0, 1.8, 1.0, (30, 10, 10), (255, 30, 30)),
    ("Recursive Dreams", "Lambda Express", "Downtempo", 15.0, 0.8, 0.5, (5, 5, 30), (100, 180, 255)),
    ("Kernel Panic", "Ring Zero", "Darkwave", 15.0, 2.5, 1.8, (25, 0, 25), (200, 0, 100)),
    ("Garbage Collector", "Heap Alloc", "Techno", 15.0, 6.0, 3.5, (10, 10, 10), (0, 200, 180)),
    ("Undefined Behavior", "Volatile Memory", "Glitch", 15.0, 7.0, 5.0, (20, 20, 0), (255, 255, 0)),
    ("git push --force", "Merge Conflict", "Punk", 15.0, 4.5, 2.8, (30, 5, 0), (255, 120, 0)),
    ("Async Await", "Event Loop", "House", 15.0, 3.0, 2.0, (0, 10, 30), (60, 160, 255)),
    ("Deep Learning Blues", "Neural Net", "Blues", 15.0, 1.5, 0.7, (10, 5, 25), (80, 120, 220)),
    ("Pointer Arithmetic", "Memory Leak", "Math Rock", 15.0, 5.5, 3.8, (15, 15, 5), (220, 200, 100)),
    ("404 Not Found", "HTTP Response", "Lo-Fi", 15.0, 1.0, 0.6, (8, 8, 20), (150, 150, 180)),
]

# Field indices
T_TITLE, T_ARTIST, T_GENRE, T_DUR, T_FB, T_FM, T_LOW, T_HIGH = range(8)

VIS_BINS = 32


class State:
    def __init__(self):
        self.current_track = 0
        self.progress = 0.0
        self.playing = True
        self.shuffle_on = False
        self.repeat_mode = 0  # 0 off, 1 one, 2 all
        self.volume = 0.75
        self.playlist_scroll = 0
        self.frame = 0
        self.vis_left = [0.0] * VIS_BINS
        self.vis_right = [0.0] * VIS_BINS
        self.shuffle_order = []
        self.init_shuffle()

    def init_shuffle(self):
        self.shuffle_order = list(range(len(TRACKS)))
        random.shuffle(self.shuffle_order)

    def advance_track(self, direction):
        if self.shuffle_on and direction == 1:
            try:
                i = self.shuffle_order.index(self.current_track)
                self.current_track = self.shuffle_order[(i + 1) % len(self.shuffle_order)]
            except ValueError:
                self.current_track = self.shuffle_order[0]
            self.progress = 0.0
            return
        self.current_track += direction
        if self.current_track >= len(TRACKS):
            self.current_track = 0 if self.repeat_mode == 2 else len(TRACKS) - 1
        if self.current_track < 0:
            self.current_track = 0
        self.progress = 0.0


S = State()


def tick(dt):
    s = S
    s.frame += 1
    if not s.playing:
        return
    trk = TRACKS[s.current_track]
    s.progress += dt / trk[T_DUR]
    if s.progress >= 1.0:
        s.progress = 0.0
        if s.repeat_mode != 1:
            s.advance_track(1)
    t = s.frame / 15.0
    fb, fm = trk[T_FB], trk[T_FM]
    for i in range(VIS_BINS):
        fi = i / VIS_BINS
        sig = (math.sin(t * fb + fi * 6.28) * 0.3
               + math.sin(t * fm * 2.0 + fi * 12.56) * 0.2
               + randf(-0.15, 0.15))
        energy = clamp((0.5 + sig) * s.volume, 0.05, 1.0)
        s.vis_left[i] += (energy - s.vis_left[i]) * 0.4
        sig2 = (math.sin(t * fb * 1.1 + fi * 6.28 + 1.0) * 0.3
                + math.cos(t * fm * 1.8 + fi * 12.56) * 0.2
                + randf(-0.15, 0.15))
        energy2 = clamp((0.5 + sig2) * s.volume, 0.05, 1.0)
        s.vis_right[i] += (energy2 - s.vis_right[i]) * 0.4


def fmt_time(seconds):
    m = int(seconds) // 60
    sec = int(seconds) % 60
    return f"{m}:{sec:02d}"


def genre_kind(genre):
    if genre in ("Synthwave", "Electronic", "Techno", "House"):
        return "info"
    if genre in ("Ambient", "Downtempo", "Lo-Fi"):
        return "success"
    if genre in ("Industrial", "Darkwave", "Punk"):
        return "error"
    if genre in ("IDM", "Glitch", "Math Rock"):
        return "warning"
    return "tool"


# ── Panels ───────────────────────────────────────────────────────────────────

def build_now_playing():
    trk = TRACKS[S.current_track]
    icon = "▶" if S.playing else "⏸"
    icon_col = (0, 220, 120) if S.playing else (255, 200, 60)
    return row(
        T(icon).fg(icon_col),
        T(trk[T_TITLE]).fg((255, 255, 255)).bold,
        T("  "),
        T(trk[T_ARTIST]).fg((170, 170, 190)),
        T("  "),
        badge(trk[T_GENRE], kind=genre_kind(trk[T_GENRE])),
        spacer(),
        T(f"{fmt_time(S.progress * trk[T_DUR])} / {fmt_time(trk[T_DUR])}").dim,
        gap=0, pad=(0, 1),
    )


def build_album_art():
    trk = TRACKS[S.current_track]
    fb, fm = trk[T_FB], trk[T_FM]
    t = S.frame / 15.0
    rows = 6
    cols = 20
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            fr = r / rows
            fc = c / cols
            v = (math.sin(fc * fb * 3.14 + t * fm) * 0.3
                 + math.cos(fr * fm * 3.14 + t * fb * 0.7) * 0.3
                 + math.sin((fr + fc) * 4.0 + t * 1.5) * 0.2
                 + 0.5)
            line.append(clamp(v, 0.0, 1.0))
        grid.append(line)
    low = trk[T_LOW]
    high = trk[T_HIGH]
    art = heatmap(grid, low=low, high=high)
    bc = (high[0] // 2, high[1] // 2, high[2] // 2)
    return card(art, title=" Album Art ", border_color=bc, pad=(0, 1))


def build_progress():
    trk = TRACKS[S.current_track]
    high = trk[T_HIGH]
    label = f"{fmt_time(S.progress * trk[T_DUR])} / {fmt_time(trk[T_DUR])}"
    bar = progress(S.progress, label, fill=high, track=(40, 42, 50),
                   show_percentage=False)
    return col(bar, pad=(0, 1))


def build_controls():
    trk = TRACKS[S.current_track]
    accent = trk[T_HIGH]

    def ctrl(icon, active):
        return T(icon).fg(accent).bold if active else T(icon).dim

    play_icon = "▶" if S.playing else "⏸"
    rep_label = ["off", "one", "all"][S.repeat_mode]
    return row(
        T("    "),
        ctrl("⏮", False), T("  "),
        ctrl(play_icon, True), T("  "),
        ctrl("⏭", False), T("    "),
        ctrl("🔀", S.shuffle_on), T(" "),
        T("on" if S.shuffle_on else "off").fg((0, 220, 120) if S.shuffle_on else (80, 80, 100)),
        T("    "),
        ctrl("🔁", S.repeat_mode > 0), T(" "),
        T(rep_label).fg((0, 220, 120) if S.repeat_mode > 0 else (80, 80, 100)),
        spacer(),
        gap=0, pad=(0, 1),
    )


def build_playlist():
    visible = 8
    n = len(TRACKS)
    cur = S.current_track
    if cur < S.playlist_scroll:
        S.playlist_scroll = cur
    if cur >= S.playlist_scroll + visible:
        S.playlist_scroll = cur - (visible - 1)
    S.playlist_scroll = clamp(S.playlist_scroll, 0, max(0, n - visible))
    scroll = S.playlist_scroll

    header = row(
        T("#").dim.bold, T("TITLE").dim.bold, T("ARTIST").dim.bold,
        T("TIME").dim.bold, gap=1,
    )
    rows = [header]
    for i in range(scroll, min(scroll + visible, n)):
        trk = TRACKS[i]
        is_cur = i == cur
        num_col = trk[T_HIGH] if is_cur else (80, 80, 100)
        title_col = (255, 255, 255) if is_cur else (190, 190, 200)
        artist_col = trk[T_HIGH] if is_cur else (120, 120, 140)
        num = " ▶ " if is_cur else f" {i + 1} "
        rows.append(row(
            T(num).fg(num_col).bold,
            T(trk[T_TITLE]).fg(title_col),
            T(trk[T_ARTIST]).fg(artist_col),
            T(fmt_time(trk[T_DUR])).dim,
            gap=1,
        ))
    if n > visible:
        e = min(scroll + visible, n)
        rows.append(row(spacer(), T(f"{scroll + 1}-{e} of {n}").dim))
    return card(*rows, title=" Playlist ", border_color=(50, 55, 70), pad=(0, 1))


def build_visualizer():
    trk = TRACKS[S.current_track]
    high = trk[T_HIGH]
    high2 = (min(255, high[0] + 40), min(255, high[1] + 40), min(255, high[2] + 40))
    return card(
        sparkline(S.vis_left, label="L", color=high, range_min=0, range_max=1),
        sparkline(S.vis_right, label="R", color=high2, range_min=0, range_max=1),
        title=" Visualizer ", border_color=(50, 55, 70), pad=(0, 1),
    )


def build_queue():
    n = len(TRACKS)
    cur = S.current_track
    rows = [T("Up Next").fg((170, 170, 190)).bold]
    for i in range(1, 5):
        if S.shuffle_on:
            try:
                pos = S.shuffle_order.index(cur)
            except ValueError:
                pos = 0
            idx = S.shuffle_order[(pos + i) % len(S.shuffle_order)]
        else:
            idx = (cur + i) % n
        trk = TRACKS[idx]
        rows.append(row(
            T(f"{i}.").dim,
            T(trk[T_TITLE]).fg((200, 200, 210)),
            T("  "),
            T(trk[T_ARTIST]).dim,
            gap=0,
        ))
    return card(*rows, title=" Queue ", border_color=(50, 55, 70), pad=(0, 1))


def build_status_bar():
    trk = TRACKS[S.current_track]
    accent = trk[T_HIGH]
    vol_pct = int(S.volume * 100)
    rep_str = ["off", "one", "all"][S.repeat_mode]
    return row(
        T(" VOL").fg((140, 140, 160)),
        T(" " + bar(S.volume, 10, fill="█", track="─")).fg(accent),
        T(f" {vol_pct}%").fg((140, 140, 160)),
        T("  |").fg((60, 60, 80)),
        T("  repeat:").fg((140, 140, 160)),
        T(rep_str).fg((0, 220, 120) if S.repeat_mode > 0 else (80, 80, 100)),
        T("  shuffle:").fg((140, 140, 160)),
        T("on" if S.shuffle_on else "off").fg((0, 220, 120) if S.shuffle_on else (80, 80, 100)),
        spacer(),
        T(" spc").fg((180, 220, 255)).bold, T(":play").fg((120, 120, 140)),
        T(" n").fg((180, 220, 255)).bold, T(":next").fg((120, 120, 140)),
        T(" p").fg((180, 220, 255)).bold, T(":prev").fg((120, 120, 140)),
        T(" s").fg((180, 220, 255)).bold, T(":shuf").fg((120, 120, 140)),
        T(" r").fg((180, 220, 255)).bold, T(":rep").fg((120, 120, 140)),
        T(" +/-").fg((180, 220, 255)).bold, T(":vol").fg((120, 120, 140)),
        T(" q").fg((180, 220, 255)).bold, T(":quit ").fg((120, 120, 140)),
        gap=0, pad=(0, 1), bg=(30, 30, 42),
    )


# ── App ──────────────────────────────────────────────────────────────────────

app = App.fullscreen("music", fps=15)
app.state(_t=0.0)


@app.on("space")
def _play(s):
    S.playing = not S.playing


@app.on("n")
def _next(s):
    S.advance_track(1)


@app.on("p")
def _prev(s):
    S.advance_track(-1)


@app.on("s")
def _shuffle(s):
    S.shuffle_on = not S.shuffle_on
    if S.shuffle_on:
        S.init_shuffle()


@app.on("r")
def _repeat(s):
    S.repeat_mode = (S.repeat_mode + 1) % 3


@app.on("+", "=")
def _volup(s):
    S.volume = min(1.0, S.volume + 0.05)


@app.on("-")
def _voldown(s):
    S.volume = max(0.0, S.volume - 0.05)


@app.on("j", "down")
def _scrolldown(s):
    S.playlist_scroll = min(S.playlist_scroll + 1, max(0, len(TRACKS) - 8))


@app.on("k", "up")
def _scrollup(s):
    S.playlist_scroll = max(0, S.playlist_scroll - 1)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 15.0)


@app.view
def view(s):
    left = grow(col(build_album_art(), build_visualizer(), build_queue()))
    right = grow(col(build_playlist()), 2.0)
    return col(
        build_now_playing(),
        build_progress(),
        build_controls(),
        row(left, right, gap=1),
        build_status_bar(),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
