"""stocks.py — a live stock ticker with sparklines and a gainers/losers board.

Mocked random-walk prices update each tick; each symbol carries a rolling
sparkline, a coloured % change, and a mini bid/ask. A market-index gauge sits
on top. Pure UI over live state.

  space pause · q/esc quit

    PYTHONPATH=src python examples/stocks.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, sparkline, gauge,
                     divider)

SYMS = [
    ("AAPL", 189.2), ("MSFT", 421.0), ("NVDA", 877.5), ("GOOGL", 142.3),
    ("AMZN", 178.9), ("META", 502.1), ("TSLA", 251.4), ("AMD", 162.8),
    ("NFLX", 612.0), ("INTC", 43.1), ("BTC", 64210.0), ("ETH", 3420.0),
]

app = App("stocks", inline=True, fps=4)
app.state(prices={}, hist={}, base={}, paused=False)


def _init(s):
    for sym, p in SYMS:
        s.prices[sym] = p
        s.base[sym] = p
        s.hist[sym] = [p] * 24


_init(app.s)


def step(s):
    for sym, _ in SYMS:
        drift = random.uniform(-0.012, 0.012)
        s.prices[sym] *= (1 + drift)
        h = s.hist[sym]
        h.append(s.prices[sym])
        if len(h) > 24:
            h.pop(0)


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("q", "esc")
def _quit(s): app.stop()


def _pct(s, sym):
    return (s.prices[sym] - s.base[sym]) / s.base[sym] * 100


def ticker_row(s, sym):
    p = s.prices[sym]
    pct = _pct(s, sym)
    up = pct >= 0
    clr = "lime" if up else "red"
    arrow = "▲" if up else "▼"
    spark = sparkline(s.hist[sym], color=clr, show_last=False)
    return row(
        T(f"{sym:<6}").fg("white").bold,
        T(f"{p:>10.2f}").fg("white"),
        spark,
        T(f"{arrow} {pct:+6.2f}%").fg(clr),
        gap=2, justify="between",
    )


@app.view
def view(s):
    if not s.paused:
        step(s)
    # market breadth
    gainers = sum(1 for sym, _ in SYMS if _pct(s, sym) >= 0)
    breadth = gainers / len(SYMS)
    movers = sorted(SYMS, key=lambda sp: _pct(s, sp[0]), reverse=True)
    top = movers[0][0]
    bot = movers[-1][0]
    return card(
        row(b("📈 maya markets").fg("lime"),
            dim_text(f"{'paused' if s.paused else 'live'} · "
                     f"breadth {gainers}/{len(SYMS)}"),
            justify="between"),
        gauge(breadth, "advancers", color="lime" if breadth >= 0.5 else "red"),
        divider("watchlist", color="slate"),
        col(*[ticker_row(s, sym) for sym, _ in SYMS], gap=0),
        row(
            T("▲ top: ").fg("lime"), T(f"{top} {_pct(s, top):+.2f}%").fg("lime"),
            dim_text("   "),
            T("▼ bot: ").fg("red"), T(f"{bot} {_pct(s, bot):+.2f}%").fg("red"),
            gap=0,
        ),
        dim_text("space pause · q quit"),
        title="stocks", gap=1,
    )


if __name__ == "__main__":
    app.run()
