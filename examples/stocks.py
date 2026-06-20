"""stocks.py — Live Stock Ticker Dashboard (inline mode).

A faithful port of maya's `examples/stocks.cpp`. A visually rich terminal
dashboard with animated braille price charts, sparklines, colour-coded
gains/losses, a portfolio summary, a selectable watchlist with timeframes, and
a scrolling news feed. All data is simulated with correlated random walks.

  Controls:
    ↑/↓ or j/k  select stock      ←/→ or h/l  timeframe
    r  random market event        space  toggle market open/closed
    t  cycle theme                q/Esc  quit

    PYTHONPATH=src python examples/stocks.py
"""

from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, spacer, grow, memo,
    clamp, spark, fixed as _fw, Theme, ThemeSet,
)


def spark_line(data, width):
    """Thin shim onto the DSL ``spark`` (kept for call-site readability)."""
    return spark(data, width)


def randf(lo, hi):
    return random.uniform(lo, hi)


def randi(lo, hi):
    return random.randint(lo, hi)


# Themes: named colour roles, cycled with 't'
themes = ThemeSet(
    Theme("NEON", accent=(0, 220, 255), gain=(0, 255, 120), loss=(255, 50, 80),
          muted=(80, 80, 100), border=(35, 40, 55), dim=(60, 60, 75), label=(140, 180, 220)),
    Theme("AMBER", accent=(255, 180, 0), gain=(80, 255, 120), loss=(255, 80, 60),
          muted=(120, 100, 60), border=(50, 42, 25), dim=(80, 70, 45), label=(200, 170, 100)),
    Theme("VAPOR", accent=(255, 100, 220), gain=(100, 255, 200), loss=(255, 80, 100),
          muted=(100, 70, 120), border=(45, 25, 55), dim=(70, 40, 80), label=(180, 140, 220)),
    Theme("MATRIX", accent=(0, 255, 65), gain=(0, 255, 65), loss=(255, 50, 50),
          muted=(0, 100, 30), border=(0, 40, 15), dim=(0, 60, 20), label=(0, 180, 60)),
)


def TH():
    return themes.current


SPARK_CHARS = "▁▂▃▄▅▆▇█"


# Braille chart: 2x4 dots per cell. dot bit layout matches the C++ original.
_DOT_BITS = ((0x40, 0x04, 0x02, 0x01), (0x80, 0x20, 0x10, 0x08))
# A cell holds 8 dot bits → 256 possible glyphs. Precompute them once so the
# render loop is a table lookup instead of a chr()+add per cell.
_BRAILLE = [chr(0x2800 + i) for i in range(256)]


def braille_chart(data, width, height):
    if not data:
        return [""] * height
    mn = min(data)
    mx = max(data)
    rng = mx - mn
    if rng < 0.001:
        rng = 1.0
    dot_rows = height * 4
    dot_cols = width * 2
    cells = [[0] * width for _ in range(height)]
    n = len(data)
    for dx in range(dot_cols):
        di = clamp(int(dx / dot_cols * n), 0, n - 1)
        v = data[di]
        dot_y = clamp(int((v - mn) / rng * (dot_rows - 1)), 0, dot_rows - 1)
        cell_x = dx // 2
        sub_x = dx % 2
        cell_y = (dot_rows - 1 - dot_y) // 4
        sub_y = (dot_rows - 1 - dot_y) % 4
        if 0 <= cell_x < width and 0 <= cell_y < height:
            cells[cell_y][cell_x] |= _DOT_BITS[sub_x][sub_y]
    bt = _BRAILLE
    return ["".join([bt[v] for v in cells[r]]) for r in range(height)]


# Stock: symbol, name, price, open, prev_close, day_high, day_low, volume,
#        volatility, history[], vol_hist[], momentum, market_cap
S_SYM, S_NAME, S_PRICE, S_OPEN, S_PREV, S_HIGH, S_LOW, S_VOL, S_VOLAT, \
    S_HIST, S_VHIST, S_MOM, S_MCAP = range(13)

STOCK_DEFS = [
    ("AAPL", "Apple Inc.", 189.84, 188.50, 187.20, 191.30, 187.10, 62.4, 0.012, 0.3, 2940),
    ("NVDA", "NVIDIA Corp.", 875.28, 868.00, 862.50, 882.40, 860.10, 48.7, 0.025, 0.8, 2150),
    ("MSFT", "Microsoft Corp.", 415.60, 413.20, 412.80, 418.90, 411.50, 28.3, 0.010, 0.2, 3090),
    ("GOOGL", "Alphabet Inc.", 157.25, 155.80, 156.40, 158.60, 155.20, 22.1, 0.015, -0.1, 1940),
    ("AMZN", "Amazon.com Inc.", 186.51, 184.90, 185.30, 188.20, 184.10, 35.6, 0.018, 0.5, 1930),
    ("TSLA", "Tesla Inc.", 248.42, 245.00, 243.80, 252.30, 242.60, 95.2, 0.035, -0.4, 790),
    ("META", "Meta Platforms Inc.", 505.75, 502.30, 501.90, 509.80, 500.10, 18.9, 0.020, 0.6, 1280),
    ("AMD", "Advanced Micro Dev.", 164.38, 162.50, 161.80, 166.70, 161.20, 42.8, 0.028, 0.4, 265),
]

TF_LABELS = ["1m", "5m", "15m", "1h", "1d"]
TF_POINTS = [60, 120, 200, 350, 500]

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

INITIAL_NEWS = [
    ("Reuters", "Fed signals potential rate cut in September meeting", 1, 45),
    ("Bloomberg", "NVIDIA announces next-gen Blackwell Ultra GPU architecture", 1, 120),
    ("CNBC", "Tech sector leads S&P 500 to new all-time high", 1, 230),
    ("WSJ", "Tesla recalls 125K vehicles over seatbelt warning system", -1, 380),
    ("Reuters", "Apple Vision Pro sales exceed analyst expectations", 1, 510),
    ("Bloomberg", "Semiconductor supply chain bottleneck easing globally", 1, 640),
]

HEADLINES = [
    "beats Q3 earnings, raises full-year guidance",
    "announces $50B stock buyback program",
    "faces antitrust scrutiny in EU markets",
    "unveils breakthrough AI chip architecture",
    "reports record quarterly cloud revenue",
    "CEO sells 200K shares in planned transaction",
    "expands manufacturing capacity in Asia",
    "partners with major automaker on EV tech",
    "downgraded by analysts on valuation concerns",
    "wins landmark government contract",
    "data center demand surges past forecasts",
    "insider buying signals confidence in turnaround",
]
SOURCES = ["Reuters", "Bloomberg", "CNBC", "WSJ", "FT"]


class State:
    def __init__(self):
        self.stocks = []
        self.news = []
        self.selected = 0
        self.timeframe = 2
        self.market_open = True
        self.elapsed = 0.0
        self.frame = 0
        self.init_state()

    def init_state(self):
        self.stocks = []
        for d in STOCK_DEFS:
            st = list(d[:9]) + [[], [], d[9], d[10]]
            # st: sym,name,price,open,prev,high,low,vol,volat,hist,vhist,mom,mcap
            prev = st[S_PREV]
            volat = st[S_VOLAT]
            mom = st[S_MOM]
            hist = []
            vhist = []
            p = prev
            for _ in range(500):
                p += randf(-1, 1) * volat * p + mom * volat * p * 0.1
                p = max(p, prev * 0.85)
                hist.append(p)
                vhist.append(randf(0.3, 1.0) * st[S_VOL])
            st[S_HIST] = hist
            st[S_VHIST] = vhist
            st[S_PRICE] = hist[-1]
            st[S_HIGH] = max(hist)
            st[S_LOW] = min(hist)
            self.stocks.append(st)
        self.news = [list(n) for n in INITIAL_NEWS]


S = State()


def tick(dt):
    s = S
    s.elapsed += dt
    s.frame += 1
    if not s.market_open:
        return
    for st in s.stocks:
        price = st[S_PRICE]
        volat = st[S_VOLAT]
        mom = st[S_MOM]
        prev = st[S_PREV]
        drift = mom * volat * price * dt
        noise = randf(-1, 1) * volat * price * math.sqrt(dt) * 3.0
        price += drift + noise
        price = clamp(price, prev * 0.80, prev * 1.20)
        st[S_PRICE] = price
        if randi(0, 200) == 0:
            st[S_MOM] = randf(-1.0, 1.0)
        st[S_HIST].pop(0)
        st[S_HIST].append(price)
        st[S_VHIST].pop(0)
        st[S_VHIST].append(randf(0.2, 1.2) * st[S_VOL])
        st[S_HIGH] = max(st[S_HIGH], price)
        st[S_LOW] = min(st[S_LOW], price)
    if randi(0, 120) == 0:
        sent = randi(0, 2) - 1
        sym = s.stocks[randi(0, len(s.stocks) - 1)][S_SYM]
        s.news.insert(0, [SOURCES[randi(0, 4)],
                          f"{sym}: {HEADLINES[randi(0, 11)]}", sent, 0.0])
        if len(s.news) > 6:
            s.news.pop()
    for n in s.news:
        n[3] += dt


# ── Formatting ───────────────────────────────────────────────────────────────

def fmt_price(p):
    return f"{p:.2f}"


def fmt_change(price, ref):
    diff = price - ref
    pct = diff / ref * 100 if ref else 0
    return f"{diff:+.2f} ({pct:+.2f}%)"


def fmt_pct(price, ref):
    pct = (price - ref) / ref * 100 if ref else 0
    return f"{pct:+.2f}%"


def fmt_vol(v):
    if v >= 1000:
        return f"{v / 1000:.1f}B"
    if v >= 1:
        return f"{v:.1f}M"
    return f"{v * 1000:.0f}K"


def fmt_mcap(b):
    return f"${b / 1000:.1f}T"


def fmt_time(secs):
    if secs < 60:
        return f"{int(secs)}s"
    if secs < 3600:
        return f"{int(secs / 60)}m"
    return f"{int(secs / 3600)}h"


def chg_color(v):
    if v > 0:
        return TH().gain
    if v < 0:
        return TH().loss
    return TH().muted


def chg_T(text, v):
    if v == 0:
        return T(text).fg(TH().muted)
    return T(text).fg(chg_color(v)).bold


# ── Panels ───────────────────────────────────────────────────────────────────

def build_header():
    s = S
    total_change = sum((st[S_PRICE] - st[S_PREV]) / st[S_PREV] for st in s.stocks) / len(s.stocks)
    idx_val = 5234.18 * (1 + total_change)
    spin = SPINNERS[s.frame % 10]
    mkt = "● LIVE" if s.market_open else "○ CLOSED"
    blocks = ["░", "▒", "▓", "█", "▓", "▒"]
    phase = s.frame % 24
    grad = "".join(blocks[(i + phase) % 6] for i in range(6))
    accent = TH().accent
    return row(
        T(spin).fg(accent),
        T("TERMINAL").fg(accent).bold,
        T("TRADER").fg((255, 255, 255)).bold,
        T(" " + grad).fg(accent),
        spacer(),
        T("S&P 500").dim,
        chg_T(f"{idx_val:.2f}", total_change),
        chg_T(fmt_change(idx_val, 5234.18), total_change),
        spacer(),
        T(mkt).fg(TH().gain if s.market_open else TH().loss),
        T("  " + TH().name).fg(accent),
        gap=1, pad=(0, 1),
    )


def build_portfolio_bar():
    s = S
    total_val = sum(st[S_PRICE] * 100 for st in s.stocks)
    total_prev = sum(st[S_PREV] * 100 for st in s.stocks)
    pnl = total_val - total_prev
    best = max(s.stocks, key=lambda st: (st[S_PRICE] - st[S_PREV]) / st[S_PREV])
    worst = min(s.stocks, key=lambda st: (st[S_PRICE] - st[S_PREV]) / st[S_PREV])
    gain = TH().gain
    loss = TH().loss
    return row(
        T("Portfolio").dim,
        T(f"${fmt_price(total_val)}").bold,
        T("P&L").dim,
        chg_T(fmt_change(total_val, total_prev), pnl),
        T("│").dim,
        T(f" ▲ {best[S_SYM]}").fg(gain),
        T(fmt_pct(best[S_PRICE], best[S_PREV])).fg(gain),
        T(f"  ▼ {worst[S_SYM]}").fg(loss),
        T(fmt_pct(worst[S_PRICE], worst[S_PREV])).fg(loss),
        gap=1, pad=(0, 1),
    )


def build_watchlist():
    s = S
    accent = TH().accent
    label = TH().label
    muted = TH().muted
    tabs = []
    for i, lab in enumerate(TF_LABELS):
        if i == s.timeframe:
            tabs.append(T(f" {lab} ").bg(accent).fg((0, 0, 0)).bold)
        else:
            tabs.append(T(f" {lab} ").dim)
    tab_row = row(*tabs, gap=1)
    header = row(
        T(_fw("", 2)).dim, T(_fw("SYMBOL", 6)).dim.bold, T(_fw("LAST", 10)).dim.bold,
        T(_fw("CHG", 10)).dim.bold, T(_fw("CHG%", 10)).dim.bold,
        T(_fw("MCAP", 8)).dim.bold, T(_fw("VOL", 7)).dim.bold,
        T("CHART").dim.bold, gap=1,
    )
    rows = [tab_row, header]
    for i, st in enumerate(s.stocks):
        chg = st[S_PRICE] - st[S_PREV]
        pct = chg / st[S_PREV] * 100
        sel = i == s.selected
        marker = "▸ " if sel else "  "
        sel_col = (255, 255, 255) if sel else (180, 180, 190)
        sym_col = accent if sel else label
        recent = st[S_HIST][-min(TF_POINTS[s.timeframe], len(st[S_HIST])):]
        spark = spark_line(recent, 16)
        rows.append(row(
            T(_fw(marker, 2)).fg(sel_col),
            T(_fw(st[S_SYM], 6)).fg(sym_col),
            T(_fw(fmt_price(st[S_PRICE]), 10)).fg(sel_col),
            chg_T(_fw(f"{chg:+.2f}", 10), chg),
            chg_T(_fw(f"{pct:+.2f}%", 10), chg),
            T(_fw(fmt_mcap(st[S_MCAP]), 8)).fg(muted),
            T(_fw(fmt_vol(st[S_VOL]), 7)).fg(muted),
            T(spark).fg(TH().gain if chg >= 0 else TH().loss),
            gap=1,
        ))
    return card(*rows, title="WATCHLIST", border_color=TH().border, pad=(0, 1))


def build_chart():
    s = S
    st = s.stocks[s.selected]
    pts = TF_POINTS[s.timeframe]
    data = st[S_HIST][-pts:]
    chart_w = 55
    chart_h = 10
    chart_rows = braille_chart(data, chart_w, chart_h)
    chg = st[S_PRICE] - st[S_PREV]
    chart_col = TH().gain if chg >= 0 else TH().loss
    mn = min(data)
    mx = max(data)
    accent = TH().accent
    muted = TH().muted
    title_row = row(
        T(st[S_SYM]).fg(accent).bold,
        T(" " + st[S_NAME]).fg(muted),
        grow(T("")),
        T(f"${fmt_price(st[S_PRICE])}").fg((255, 255, 255)).bold,
        chg_T(" " + fmt_change(st[S_PRICE], st[S_PREV]), chg),
        gap=0,
    )
    # Current price marker (┌ $price), indented under the y-axis labels.
    price_tag = " $" + fmt_price(st[S_PRICE]) + " "
    marker_row = row(
        T(_fw("", 8)),
        chg_T("┌" + price_tag, chg),
        gap=0,
    )
    body = []
    for r in range(chart_h):
        label_val = mx - (mx - mn) * r / (chart_h - 1) if chart_h > 1 else mx
        sep = "┤" if r == 0 else "│"
        body.append(row(
            T(_fw(f"{label_val:7.2f}", 8)).fg(muted),
            T(sep).dim,
            T(chart_rows[r]).fg(chart_col),
            gap=0,
        ))
    xaxis = row(T(_fw("", 8)), T("└" + "─" * chart_w).dim, gap=0)
    stats = row(
        T(_fw("Open", 5)).fg(muted), T(_fw(fmt_price(st[S_OPEN]), 10)).fg((200, 200, 210)),
        T(_fw("High", 5)).fg(muted), T(_fw(fmt_price(st[S_HIGH]), 10)).fg(TH().gain),
        T(_fw("Low", 5)).fg(muted), T(_fw(fmt_price(st[S_LOW]), 10)).fg(TH().loss),
        T(_fw("Vol", 5)).fg(muted), T(_fw(fmt_vol(st[S_VOL]), 7)).fg((200, 200, 210)),
        T(_fw("MCap", 5)).fg(muted), T(fmt_mcap(st[S_MCAP])).fg((200, 200, 210)),
        gap=1,
    )
    vdata = st[S_VHIST][-pts:]
    vol_spark = spark_line(vdata, chart_w)
    vol_row = row(T(_fw("Volume", 8)).fg(muted), T("│").dim, T(vol_spark).fg(muted), gap=0)
    return card(
        title_row, marker_row, *body, xaxis, stats, vol_row,
        title=f"{st[S_SYM]} · {TF_LABELS[s.timeframe]}",
        border_color=TH().border, pad=(0, 1),
    )


def build_news():
    s = S
    muted = TH().muted
    gain = TH().gain
    loss = TH().loss
    rows = []
    for source, headline, sent, age in s.news[:5]:
        icon = "▲" if sent > 0 else ("▼" if sent < 0 else "─")
        col_c = gain if sent > 0 else (loss if sent < 0 else muted)
        rows.append(row(
            T(_fw(icon, 2)).fg(col_c),
            T(_fw(source, 11)).fg(TH().label),
            T(headline).fg(muted),
            grow(T("")),
            T(fmt_time(age)).fg((50, 50, 60)),
            gap=1,
        ))
    while len(rows) < 5:
        rows.append(T(""))
    return card(*rows, title="NEWS", border_color=TH().border, pad=(0, 1))


@memo
def build_footer(_theme):
    accent = TH().accent
    muted = TH().muted

    def key(k, kw, lab, lw):
        return [T(_fw(k, kw)).fg(accent).bold, T(_fw(lab, lw)).fg(muted)]

    parts = []
    parts += key(" ↑↓", 4, "select", 7)
    parts += key("←→", 3, "time", 5)
    parts += key("r", 2, "event", 6)
    parts += key("␣", 2, "mkt", 4)
    parts += key("t", 2, "theme", 6)
    parts += [T(_fw("q", 2)).fg(accent).bold, T("quit").fg(muted)]
    parts.append(spacer())
    parts.append(T("powered by ").fg((55, 55, 70)))
    parts.append(T("maya").fg(accent))
    return row(*parts, gap=0, pad=(0, 1), bg=(25, 25, 35))


# ── App ──────────────────────────────────────────────────────────────────────

app = App.inline("Terminal Trader", fps=20)
app.state(_t=0.0)


@app.on("up", "k")
def _up(s):
    S.selected = max(0, S.selected - 1)


@app.on("down", "j")
def _down(s):
    S.selected = min(len(S.stocks) - 1, S.selected + 1)


@app.on("left", "h")
def _left(s):
    S.timeframe = max(0, S.timeframe - 1)


@app.on("right", "l")
def _right(s):
    S.timeframe = min(4, S.timeframe + 1)


@app.on("r")
def _event(s):
    st = S.stocks[randi(0, len(S.stocks) - 1)]
    shock = randf(-0.08, 0.08)
    st[S_PRICE] *= (1 + shock)
    st[S_MOM] = 1.0 if shock > 0 else -1.0


@app.on("space")
def _market(s):
    S.market_open = not S.market_open


@app.on("t")
def _theme(s):
    themes.next()


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 20.0)


@app.view
def view(s):
    return col(
        build_header(),
        build_portfolio_bar(),
        build_watchlist(),
        build_chart(),
        build_news(),
        build_footer(themes.index),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
