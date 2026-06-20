"""dsl.py — a tour of maya-py's numeric / colour / data DSL.

Every live or visual terminal app reaches for the same vocabulary: clamp a
value, lerp between two, remap a range, ease an animation, sweep a hue, turn a
list of numbers into a sparkline. maya-py ships all of it so you never redefine
`clamp` again:

  • numeric   clamp · lerp · norm · remap · smoothstep · wrap · approach
  • animation oscillate · pulse · ease(kind)
  • colour    hsv · mix · lighten · darken · alpha
  • data→text spark · bar · fixed · human · percent
  • theme     Theme · ThemeSet (named colour roles, no index constants)

This app animates them all off a single time `t`.

    PYTHONPATH=src python examples/dsl.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, b, dim_text,
    clamp, lerp, remap, smoothstep, wrap, oscillate, pulse, ease,
    hsv, mix, lighten, darken, spark, bar, fixed, human, percent,
    Theme, ThemeSet,
)


# A ThemeSet replaces the old `THEMES[i][TH_ACCENT]` index-constant pattern:
# named colour roles, read by attribute, cycled with .next().
themes = ThemeSet(
    Theme("CYBER", accent=(0, 255, 200), hot=(255, 0, 100), cold=(0, 100, 255)),
    Theme("EMBER", accent=(255, 120, 0), hot=(255, 40, 40), cold=(255, 200, 60)),
    Theme("VAPOR", accent=(255, 100, 220), hot=(255, 80, 100), cold=(100, 255, 200)),
)


app = App("dsl", inline=True, fps=30, t=0.0)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on("t")
def _cycle_theme(s):
    themes.next()


@app.on_frame
def _tick(s, dt):
    s.t += dt


def numeric_panel(t):
    """Drive a few values off t and show the building blocks."""
    osc = oscillate(t, 0, 1, period=2.0)          # 0..1 sine, 2s period
    eased = ease(osc, "inout")
    rows = [
        row(dim_text(fixed("oscillate", 10)), T(bar(osc, 10)).fg("sky"),
            T(percent(osc)).fg("sky"), gap=1),
        row(dim_text(fixed("ease", 10)), T(bar(eased, 10)).fg("purple"),
            T(percent(eased)).fg("purple"), gap=1),
        row(dim_text(fixed("remap 2π", 10)),
            T(bar(remap(wrap(t, 2 * math.pi), 0, 2 * math.pi, 0, 1), 10)).fg("lime"),
            gap=1),
        row(dim_text(fixed("pulse 1Hz", 10)),
            T("● ON" if pulse(t, 1.0) else "○ off").fg("gold" if pulse(t, 1.0) else "slate"),
            gap=1),
    ]
    return card(b("numeric · animation"), *rows, title="building blocks",
                gap=0, width=32)


def colour_panel(t):
    """Sweep a hue and show mix / lighten / darken off it."""
    base = hsv(wrap(t * 0.15, 1.0))               # cycling base hue
    swatch = "████"
    hue_row = row(*[T(swatch).fg(hsv(i / 18 + t * 0.1)) for i in range(18)], gap=0)
    ops = row(
        T(swatch).fg(darken(base, 0.4)), T(swatch).fg(darken(base, 0.2)),
        T(swatch).fg(base),
        T(swatch).fg(lighten(base, 0.25)), T(swatch).fg(lighten(base, 0.5)),
        dim_text("  darken → base → lighten"), gap=0,
    )
    blend = row(*[T(swatch).fg(mix("#ff2d55", "#0aefff", i / 11)) for i in range(12)],
                gap=0)
    return card(
        b("colour"),
        row(dim_text(fixed("hue sweep", 11)), hue_row, gap=1),
        row(dim_text(fixed("shade ops", 11)), ops, gap=1),
        row(dim_text(fixed("mix a→b", 11)), blend, gap=1),
        title="colour", gap=0,
    )


def data_panel(t):
    """Live sparklines + human-formatted numbers."""
    cpu = [oscillate(t - i * 0.08, 0.2, 1.0, 1.4) for i in range(32)][::-1]
    net = [abs(math.sin(t * 1.7 - i * 0.2)) for i in range(32)][::-1]
    reqs = 1_240 + 8_600 * oscillate(t, 0, 1, 3.0)
    return card(
        b("data → text"),
        row(dim_text(fixed("cpu", 6)), T(spark(cpu, 32)).fg("lime"),
            T(percent(cpu[-1])).fg("lime"), gap=1),
        row(dim_text(fixed("net", 6)), T(spark(net, 32)).fg("sky"),
            T(percent(net[-1])).fg("sky"), gap=1),
        row(dim_text(fixed("req/s", 6)), T(human(reqs)).bold.fg("gold"),
            dim_text("·"), dim_text(human(reqs * 3600) + " /h"), gap=1),
        title="data", gap=0,
    )


def theme_panel(t):
    """Named colour roles from the active theme — no integer index constants."""
    th = themes.current
    swatch = "████"
    chips = []
    for i, name in enumerate(themes.names()):
        active = i == themes.index
        chips.append(T(f"{i + 1}:{name}").fg("white" if active else "slate")
                     .opt(bold=active, dim=not active))
    return card(
        b("theme"),
        row(*chips, gap=1),
        row(dim_text(fixed("accent", 7)), T(swatch).fg(th.accent),
            T(swatch).fg(th.shade("accent", 0.3)),
            T(swatch).fg(th.shade("accent", -0.4)), gap=1),
        row(dim_text(fixed("hot/cold", 9)), T(swatch).fg(th.hot),
            T(swatch).fg(th.cold),
            dim_text("  ramp"),
            *[T("█").fg(mix(th.cold, th.hot, i / 11)) for i in range(12)], gap=1),
        title=f"theme · {th.name}", gap=0,
    )


@app.view
def view(s):
    return col(
        row(b("maya-py DSL").fg(hsv(wrap(s.t * 0.1, 1.0))),
            dim_text("— numeric · colour · data · theme, off one clock"), gap=1),
        row(numeric_panel(s.t), colour_panel(s.t), gap=1),
        row(data_panel(s.t), theme_panel(s.t), gap=1),
        dim_text("t cycle theme · q quit"),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
