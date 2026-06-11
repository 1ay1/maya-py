"""chat.py — a terminal chat client with a live conversation, typing indicator,
and a scrollable history.

Type a message and press Enter; a mock "bot" replies after a beat with a
typing animation. Messages render as left/right aligned bubbles with avatars.

  type · Enter send · ↑↓ scroll history · q/esc quit (when input empty)

    PYTHONPATH=src python examples/chat.py
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, divider,
                     scroll_state, viewport, scrollbar)

REPLIES = [
    "Got it — pushing that now.",
    "Hmm, let me check the logs.",
    "That should be fixed in the latest build.",
    "Nice, the tests are green ✅",
    "Can you share the stack trace?",
    "Deploying to staging…",
    "👍 looks good to me.",
    "I'll take a look after lunch.",
]

app = App("chat", inline=True, fps=12)
s = scroll_state()
app.state(s=s, msgs=[], input="", typing=False, typing_until=0.0, t=0.0)
app.s.msgs = [
    ("bot", "Hey! I'm maya-bot. Ask me anything."),
    ("me", "are the deploys passing?"),
    ("bot", "Yep — last 6 builds all green."),
]


def _send(st, text):
    st.msgs.append(("me", text))
    st.typing = True
    st.typing_until = time.time() + random.uniform(0.8, 1.6)


# Register a handler for every printable char so typing fills the input line.
_PRINTABLE = ("abcdefghijklmnopqrstuvwxyz"
              "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
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
def _enter(st):
    if st.input.strip():
        _send(st, st.input.strip())
        st.input = ""


@app.on("esc")
def _quit(st):
    if not st.input:
        app.stop()
    else:
        st.input = ""


@app.on("ctrl+c")
def _force_quit(st): app.stop()


def bubble(who, text):
    me = who == "me"
    avatar = T(" 🙂 " if me else " 🤖 ").bg("slate")
    body = card(T(text).fg("white"), pad=0,
                border="round",
                border_color="sky" if me else "slate")
    if me:
        return row(maya.spacer() if False else T(""), body, avatar,
                   justify="end", gap=1)
    return row(avatar, body, justify="start", gap=1)


def history(st):
    rows = [bubble(who, text) for who, text in st.msgs]
    if st.typing:
        dots = "." * (1 + int(st.t * 3) % 3)
        rows.append(row(T(" 🤖 ").bg("slate"),
                        dim_text(f"typing{dots}"), gap=1))
    return col(*rows, gap=1)


@app.view
def view(st):
    st.t += 0.08
    # resolve typing → reply
    if st.typing and time.time() >= st.typing_until:
        st.typing = False
        st.msgs.append(("bot", random.choice(REPLIES)))
    return card(
        row(b("💬 maya chat").fg("sky"),
            badge("online", kind="success"), justify="between"),
        row(
            viewport(history(st), st.s, height=16, grow=1),
            scrollbar(st.s, 16, style="slim", thumb_color="sky"),
            gap=1,
        ),
        divider(color="slate"),
        row(T("›").fg("sky"),
            T(st.input + "▏").fg("white") if st.input else dim_text("type a message…"),
            gap=1),
        dim_text("Enter send · Esc clear/quit · Ctrl-C quit"),
        title="chat", gap=1,
    )


if __name__ == "__main__":
    app.run()
