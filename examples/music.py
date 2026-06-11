"""music.py — a music player UI with an animated equalizer and a now-playing card.

A mocked player: a track list, a seek bar that advances, an animated EQ
spectrum, and transport controls. Pure UI — no audio — showcasing layout,
gauges, sparklines, and live state.

  space play/pause · ←/→ seek · ↑/↓ track · q/esc quit

    PYTHONPATH=src python examples/music.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, component,
                     sparkline, progress, badge)

TRACKS = [
    ("Nightcall", "Kavinsky", 257),
    ("Midnight City", "M83", 244),
    ("Resonance", "Home", 211),
    ("Strobe", "deadmau5", 634),
    ("Teardrop", "Massive Attack", 330),
    ("Breathe", "Télépopmusik", 281),
]

EQ_BANDS = 28
EQ_H = 8
BLOCKS = "▁▂▃▄▅▆▇█"

app = App("music", inline=True, fps=24)
app.state(cur=0, pos=0.0, playing=True, t=0.0, eq=[0.0] * EQ_BANDS)


def step(s):
    s.t += 0.1
    if s.playing:
        s.pos += 1 / app_fps
        dur = TRACKS[s.cur][2]
        if s.pos >= dur:
            s.pos = 0.0
            s.cur = (s.cur + 1) % len(TRACKS)
    # animate EQ
    for i in range(EQ_BANDS):
        target = (0.5 + 0.5 * math.sin(s.t * 3 + i * 0.5)) * (0.4 + 0.6 * random.random())
        if not s.playing:
            target *= 0.15
        s.eq[i] = max(target, s.eq[i] * 0.8)


app_fps = 24


@app.on("space")
def _play(s): s.playing = not s.playing


@app.on("left")
def _seek_b(s): s.pos = max(0, s.pos - 10)


@app.on("right")
def _seek_f(s): s.pos = min(TRACKS[s.cur][2], s.pos + 10)


@app.on("up", "k")
def _prev(s): s.cur = (s.cur - 1) % len(TRACKS); s.pos = 0.0


@app.on("down", "j")
def _next(s): s.cur = (s.cur + 1) % len(TRACKS); s.pos = 0.0


@app.on("q", "esc")
def _quit(s): app.stop()


def _fmt(sec):
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def equalizer(s):
    def draw(w, h):
        lines = []
        for rowi in range(EQ_H):
            segs = []
            for i in range(EQ_BANDS):
                lv = s.eq[i]
                lo = (EQ_H - 1 - rowi) / EQ_H
                hi = (EQ_H - rowi) / EQ_H
                hue = (60 + i * 6, 200 - i * 3, 255 - i * 5)
                if lv >= hi:
                    segs.append(T("██").fg(maya.rgb(*hue)))
                elif lv > lo:
                    ch = BLOCKS[min(7, int((lv - lo) / (hi - lo) * 7))]
                    segs.append(T(ch + ch).fg(maya.rgb(*hue)))
                else:
                    segs.append(T("  "))
            lines.append(row(*segs, gap=0))
        return col(*lines, gap=0)
    return component(draw, height=EQ_H, width=EQ_BANDS * 2)


def track_list(s):
    rows = []
    for i, (title, artist, dur) in enumerate(TRACKS):
        sel = i == s.cur
        bar = T("▎").fg("magenta") if sel else T(" ")
        name = T(title).fg("white").bold if sel else T(title).fg("slate")
        rows.append(row(bar, name, dim_text(artist), dim_text(_fmt(dur)),
                        justify="between", gap=1))
    return col(*rows, gap=0)


@app.view
def view(s):
    step(s)
    title, artist, dur = TRACKS[s.cur]
    frac = s.pos / dur if dur else 0
    icon = "⏸" if s.playing else "▶"
    return card(
        row(b("♫ maya music").fg((130, 200, 255)),
            badge("PLAYING" if s.playing else "PAUSED",
                  kind="success" if s.playing else "warning"),
            justify="between"),
        row(
            card(track_list(s), title="queue", pad=1),
            col(
                card(
                    b(title).fg("white"),
                    dim_text(artist),
                    equalizer(s),
                    title="now playing", pad=1, gap=1,
                ),
                progress(frac, f"{icon} {_fmt(s.pos)} / {_fmt(dur)}",
                         width=44, fill=(130, 200, 255)),
                gap=1,
            ),
            gap=2,
        ),
        dim_text("space play/pause · ←→ seek · ↑↓ track · q quit"),
        title="player", gap=1,
    )


if __name__ == "__main__":
    app.run()
