"""messenger.py — a multi-channel terminal chat with a peer-simulation feed.

Four channels in a sidebar; the active channel shows a scrolling conversation
that peers keep adding to on a timer. A composer line at the bottom lets you
type and send into the active channel. Unread counts badge inactive channels.

  type · Enter send · Tab next channel · Shift+Tab prev · Esc/Ctrl-C quit

    PYTHONPATH=src python examples/messenger.py
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, divider,
                     scroll_state, viewport, scrollbar)

CHANNELS = ["#general", "#dev", "#random", "#incidents"]
PEERS = [("ada", "lime"), ("linus", "sky"), ("grace", "magenta"),
         ("dennis", "gold")]
CHATTER = {
    "#general": ["morning all ☀️", "coffee machine is down again",
                 "who's on call?", "lunch at 12?"],
    "#dev": ["pushed the fix to main", "tests are green", "rebasing now",
             "can someone review #482?", "ship it 🚀"],
    "#random": ["look at this cat 🐈", "friday!!", "anyone watch the game?",
                "🎉🎉🎉"],
    "#incidents": ["p99 latency spiking", "rolling back deploy", "mitigated ✅",
                   "post-mortem scheduled"],
}

app = App("messenger", inline=True, fps=8)
s = scroll_state()
app.state(s=s, active=0, msgs={c: [] for c in CHANNELS},
          unread={c: 0 for c in CHANNELS}, input="", t=0.0, next_peer=0.0)

# seed
for c in CHANNELS:
    for _ in range(3):
        who, clr = random.choice(PEERS)
        app.s.msgs[c].append((who, clr, random.choice(CHATTER[c]), False))


def _peer_tick(st):
    if time.time() < st.next_peer:
        return
    st.next_peer = time.time() + random.uniform(1.2, 2.8)
    c = random.choice(CHANNELS)
    who, clr = random.choice(PEERS)
    st.msgs[c].append((who, clr, random.choice(CHATTER[c]), False))
    st.msgs[c] = st.msgs[c][-40:]
    if c != CHANNELS[st.active]:
        st.unread[c] += 1


_PRINTABLE = ("abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ"
              "0123456789 ,.!?'\"@#%&()-_/:;")


def _make_typer(ch):
    def _typer(st):
        st.input += ch
    return _typer


for _ch in _PRINTABLE:
    app.on(_ch)(_make_typer(_ch))


@app.on("backspace")
def _bs(st): st.input = st.input[:-1]


@app.on("enter")
def _send(st):
    if st.input.strip():
        c = CHANNELS[st.active]
        st.msgs[c].append(("you", "white", st.input.strip(), True))
        st.input = ""


@app.on("tab")
def _next(st):
    st.active = (st.active + 1) % len(CHANNELS)
    st.unread[CHANNELS[st.active]] = 0


@app.on("shift+tab")
def _prev(st):
    st.active = (st.active - 1) % len(CHANNELS)
    st.unread[CHANNELS[st.active]] = 0


@app.on("esc", "ctrl+c")
def _quit(st):
    if st.input:
        st.input = ""
    else:
        app.stop()


def channel_list(st):
    rows = []
    for i, c in enumerate(CHANNELS):
        active = i == st.active
        bar = T("▎").fg("sky") if active else T(" ")
        name = T(c).fg("white").bold if active else T(c).fg("slate")
        un = st.unread[c]
        tail = badge(str(un), kind="error") if un else T("")
        rows.append(row(bar, name, tail, justify="between", gap=1))
    return col(*rows, gap=0)


def conversation(st):
    c = CHANNELS[st.active]
    rows = []
    for who, clr, text, mine in st.msgs[c]:
        head = T(f"{who}").fg(clr).bold
        rows.append(col(row(head, dim_text("now"), gap=1),
                        T("  " + text).fg("white"), gap=0))
    return col(*rows, gap=1)


@app.view
def view(st):
    st.t += 0.1
    _peer_tick(st)
    c = CHANNELS[st.active]
    return card(
        row(b("✉ maya messenger").fg("sky"),
            badge("online", kind="success"), justify="between"),
        row(
            card(channel_list(st), title="channels", pad=1),
            col(
                card(
                    row(b(c).fg("white"),
                        dim_text(f"{len(st.msgs[c])} messages"),
                        justify="between"),
                    row(viewport(conversation(st), st.s, height=14, grow=1),
                        scrollbar(st.s, 14, style="slim", thumb_color="sky"),
                        gap=1),
                    pad=1, gap=1,
                ),
                row(T("›").fg("sky"),
                    T(st.input + "▏").fg("white") if st.input
                    else dim_text(f"message {c}…"), gap=1),
                gap=1,
            ),
            gap=2,
        ),
        dim_text("type · Enter send · Tab/Shift+Tab switch · Esc/Ctrl-C quit"),
        title="messenger", gap=1,
    )


if __name__ == "__main__":
    app.run()
