"""widgets.py — Showcase of visualization widgets (faithful port of widgets.cpp).

Demonstrates 7 native maya visualization widgets in a single dashboard:
  context_window, flame_chart, git_graph, inline_diff,
  timeline, token_stream, waterfall

Every widget is the real maya C++ renderer (pybind11-bound) — nothing is
reimplemented in Python. The view layout mirrors widgets.cpp 1:1.

Controls:
  tab        cycle focus between panels
  space      animate (advance frame / toggle streaming)
  r          reset to initial state
  q/Esc      quit

    PYTHONPATH=src python examples/widgets.py
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (
    App, card, row, col, T, spacer, grow, when,
    context_window, flame_chart, git_graph, inline_diff,
    timeline, token_stream, waterfall,
)

# Deterministic RNG, matching the C++ std::mt19937{42} seed intent.
_rng = random.Random(42)


def randf(lo, hi):
    return _rng.uniform(lo, hi)


# ── colors (match widgets.cpp) ──────────────────────────────────────────────
FOCUS = (97, 175, 239)
UNFOCUS = (50, 54, 62)


def edge(focused):
    return FOCUS if focused else UNFOCUS


# ── panel builders (each wraps a native widget in a Round panel) ─────────────

def build_context_window(focused):
    return card(
        context_window(
            [("System", 12400, (97, 175, 239)),
             ("History", 89200, (198, 120, 221)),
             ("Tools", 32100, (229, 192, 123)),
             ("Response", 11534, (152, 195, 121))],
            max_tokens=200000, width=44),
        title="Context Window", border_color=edge(focused), pad=(0, 1),
    )


def build_flame_chart(focused):
    return card(
        flame_chart(
            [("request", 0.0, 12.0, 0),
             ("thinking", 0.0, 4.2, 1),
             ("tool calls", 4.5, 5.0, 1),
             ("responding", 9.8, 2.2, 1),
             ("read file", 4.5, 1.5, 2),
             ("edit file", 6.2, 2.0, 2),
             ("run tests", 8.5, 1.2, 2)],
            time_scale=12.0, width=52),
        title="Flame Chart", border_color=edge(focused), pad=(0, 1),
    )


def build_git_graph(focused):
    return card(
        git_graph([
            {"hash": "a9f3cf1", "message": "fix fps and add space3d",        "time": "2m ago",  "branch": 0, "is_head": True},
            {"hash": "9f2b7d4", "message": "shorten key hold window",        "time": "5m ago",  "branch": 0},
            {"hash": "2047a1e", "message": "held-key tracking",              "time": "12m ago", "branch": 0},
            {"hash": "5a29502", "message": "fps: dark red walls, twilight",  "time": "1h ago",  "branch": 1},
            {"hash": "09591cd", "message": "sorts: 8 algorithms",            "time": "2h ago",  "branch": 0, "is_merge": True},
            {"hash": "3a5d90e", "message": "make macos hotpath faster",      "time": "3h ago",  "branch": 0},
            {"hash": "600c537", "message": "syntax highlighting in markdown", "time": "4h ago",  "branch": 1},
            {"hash": "2f8ffec", "message": "merge Elm architecture",         "time": "5h ago",  "branch": 0, "is_merge": True},
        ]),
        title="Git Graph", border_color=edge(focused), pad=(0, 1),
    )


def build_inline_diff(focused):
    return card(
        inline_diff("const SESSION_TIMEOUT = 3600;",
                    "const TOKEN_EXPIRY = '1h';",
                    label="src/config.ts"),
        T(""),
        inline_diff("app.use(session({ secret: process.env.SECRET }))",
                    "app.use(jwt({ algorithm: 'RS256', publicKey: KEY }))",
                    label="src/middleware/auth.ts"),
        title="Inline Diff", border_color=edge(focused), pad=(0, 1),
    )


def build_timeline(s, focused):
    return card(
        timeline([
            ("Read auth middleware", "Read 42 lines from src/auth.ts", "1.2s", "completed"),
            ("Analyze dependencies", "Found 3 affected modules", "0.8s", "completed"),
            ("Edit auth.ts", "Replaced session with JWT tokens", "2.0s", "completed", 12),
            ("Edit middleware/index.ts", "Updated exports", "0.4s", "in_progress", 6),
            ("Run test suite", "", "", "pending"),
            ("Verify deployment", "", "", "pending"),
        ], frame=s.frame, track_width=36),
        title="Timeline", border_color=edge(focused), pad=(0, 1),
    )


def build_token_stream(s, focused):
    return card(
        token_stream(total_tokens=s.total_tokens,
                     tokens_per_sec=s.tokens_per_sec,
                     peak_rate=s.peak_rate,
                     elapsed=s.elapsed,
                     history=s.rate_history),
        title="Token Stream", border_color=edge(focused), pad=(0, 1),
    )


def build_waterfall(s, focused):
    return card(
        waterfall([
            ("Read auth.ts",      0.0, 1.2, (97, 175, 239)),
            ("Read config.ts",    0.3, 0.8, (97, 175, 239)),
            ("Analyze imports",   1.0, 1.5, (198, 120, 221)),
            ("Edit auth.ts",      2.0, 2.3, (229, 192, 123)),
            ("Edit middleware.ts", 2.5, 1.8, (229, 192, 123)),
            ("Write token.ts",    3.5, 1.2, (152, 195, 121)),
            ("Run tests",         4.8, 3.5, (152, 195, 121)),
        ], bar_width=36, frame=s.frame),
        title="Waterfall", border_color=edge(focused), pad=(0, 1),
    )


# ── app ──────────────────────────────────────────────────────────────────────

app = App("widgets", inline=False, fps=20)
app.state(frame=0, elapsed=0.0, streaming=True, total_tokens=0,
          tokens_per_sec=0.0, peak_rate=0.0, rate_history=[0.0] * 32, panel=0)


def _reset(s):
    s.frame = 0
    s.elapsed = 0.0
    s.total_tokens = 0
    s.tokens_per_sec = 0.0
    s.peak_rate = 0.0
    s.rate_history = [0.0] * 32
    # streaming + panel preserved (matches ResetState semantics)


@app.on_frame
def tick(s, dt):
    s.frame += 1
    s.elapsed += 0.05
    if s.streaming:
        base = 60.0 + 30.0 * math.sin(s.elapsed * 0.8)
        noise = randf(-10.0, 10.0)
        s.tokens_per_sec = max(5.0, base + noise)
        s.total_tokens += int(s.tokens_per_sec * 0.05)
        if s.tokens_per_sec > s.peak_rate:
            s.peak_rate = s.tokens_per_sec
        s.rate_history.append(s.tokens_per_sec)
        if len(s.rate_history) > 32:
            s.rate_history.pop(0)


@app.on("space")
def toggle_stream(s):
    s.streaming = not s.streaming


@app.on("tab")
def next_panel(s):
    s.panel = (s.panel + 1) % 7


@app.on("r")
def reset_state(s):
    _reset(s)


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    title_bar = row(
        T("Widget Showcase").fg((100, 180, 255)).bold,
        T("   "),
        when(s.streaming,
             T("STREAMING").fg((80, 220, 120)).bold,
             T("PAUSED").dim),
        T("   "),
        T(f"frame:{s.frame} elapsed:{s.elapsed:.1f}s tokens:{s.total_tokens}").dim,
    )

    left_col = col(
        build_context_window(s.panel == 0),
        build_flame_chart(s.panel == 1),
        build_inline_diff(s.panel == 3),
    )
    right_col = col(
        build_git_graph(s.panel == 2),
        build_token_stream(s, s.panel == 5),
        build_waterfall(s, s.panel == 6),
    )
    main_area = row(grow(left_col), grow(right_col))

    bottom_row = build_timeline(s, s.panel == 4)

    help_ = T("tab cycle panels  space stream  r reset  q quit").dim

    return col(
        title_bar,
        spacer(),
        main_area,
        bottom_row,
        spacer(),
        help_,
        pad=1,
    )


if __name__ == "__main__":
    app.run()
