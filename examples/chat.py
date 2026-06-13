"""chat.py — a terminal chat client with a live conversation + typing indicator.

Type a message and press Enter; a mock "bot" replies after a beat with a typing
animation. The composer is a real `text_input` widget — no hand-rolled keystroke
handling — and the per-frame simulation lives in `@app.on_frame`, so the view is
a pure function of state.

  type · Enter send · Esc clear/quit · Ctrl-C quit

    PYTHONPATH=src python examples/chat.py
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, divider,
                     text_input)

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
app.state(
    msgs=[
        ("bot", "Hey! I'm maya-bot. Ask me anything."),
        ("me", "are the deploys passing?"),
        ("bot", "Yep — last 6 builds all green."),
    ],
    typing=False, typing_until=0.0, t=0.0,
)

# The composer is a real interactive widget: it owns its buffer + cursor.
composer = text_input("type a message…")
app.focus(composer)


@composer.on_submit
def _send(text):
    text = text.strip()
    if not text:
        return
    app.s.msgs.append(("me", text))
    app.s.typing = True
    app.s.typing_until = time.time() + random.uniform(0.8, 1.6)
    composer.clear()


@app.on("esc")
def _esc(st):
    if composer.value:
        composer.clear()      # first Esc clears a draft …
    else:
        app.stop()            # … a second one quits


@app.on_frame
def tick(st, dt):
    st.t += dt
    # Resolve a pending "bot is typing" into an actual reply.
    if st.typing and time.time() >= st.typing_until:
        st.typing = False
        st.msgs.append(("bot", random.choice(REPLIES)))


def bubble(who, text):
    me = who == "me"
    avatar = T(" 🙂 " if me else " 🤖 ").bg("slate")
    body = card(T(text).fg("white"), pad=0, border="round",
                border_color="sky" if me else "slate")
    return (row(body, avatar, justify="end", gap=1) if me
            else row(avatar, body, justify="start", gap=1))


def history(st):
    # Recent messages; older ones flow into the terminal's own scrollback
    # (inline mode), so no in-app viewport/scrollbar is needed.
    rows = [bubble(who, text) for who, text in st.msgs[-12:]]
    if st.typing:
        dots = "." * (1 + int(st.t * 3) % 3)
        rows.append(row(T(" 🤖 ").bg("slate"), dim_text(f"typing{dots}"), gap=1))
    return col(*rows, gap=1)


@app.view
def view(st):
    return card(
        row(b("💬 maya chat").fg("sky"),
            badge("online", kind="success"), justify="between"),
        history(st),
        divider(color="slate"),
        row(T("›").fg("sky"), composer, gap=1),
        dim_text("Enter send · Esc clear/quit · Ctrl-C quit"),
        title="chat", gap=1,
    )


if __name__ == "__main__":
    app.run()
