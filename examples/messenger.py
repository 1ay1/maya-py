"""messenger.py — a multi-channel terminal chat with a peer-simulation feed.

A faithful port of maya's ``examples/messenger.cpp``. Simulates a small group
of peers chatting across group channels and 1-1 DMs, driven by a deterministic
script + ambient-phrase generator. Demonstrates a full text composer with
cursor editing, a scrollable message viewport with a live scrollbar, two modal
overlays (a channel jumper and a help screen), presence/status, slash commands,
and unread/mention badges — all native maya widgets, no hand-rolled rendering.

Controls

  composer
    type              insert character
    ←/→               move cursor
    ^A / ^E           jump to line start / end
    ^W                delete previous word
    ^U / ^K           clear to start / end of line
    backspace         delete previous char
    enter             send (or run a /command)

  navigation
    tab / shift+tab   next / previous channel
    ↑ ↓               scroll one message
    PgUp / PgDn       scroll one page
    end               jump to latest
    ^G                channel jumper
    ^L                clear current channel
    ^P                toggle the right info panel
    q / esc / ^C      quit  (esc first clears the composer)

  slash commands  (type into composer, press enter)
    /help                       this list
    /me <action>                emote, e.g. /me shrugs
    /clear                      clear current channel
    /topic <text>               retitle channel
    /status active|away|dnd|offline   set presence
    /who                        list members as a system message
    /quit                       exit

Adaptation note: the C++ runs in Mode::Fullscreen on the Elm-shaped Program
with a Sub::every(50ms) tick and a raw-mouse drag/wheel router. The Python
``App`` harness is inline + @app.on_frame driven, so the peer simulation runs
off a per-frame clock and scrolling uses the auto-dispatched ScrollState
(arrows / PgUp / PgDn / End / wheel). Cursor editing, slash commands, overlays,
presence and the script/ambient feed are ported faithfully.

    PYTHONPATH=src python examples/messenger.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya  # noqa: F401
from maya_py import (
    App, col, row, card, b, dim_text, T, badge, spacer, center,
    scroll_state, viewport, scrollbar, overlay, pct,
)

# ─── Palette ─────────────────────────────────────────────────────────────────

ACCENT = (120, 200, 220)
AMBER = (230, 180, 100)
GREEN = (140, 200, 130)
RED = (230, 110, 110)
PINK = (230, 130, 190)
PURPLE = (180, 130, 230)
TEXT = (220, 224, 232)
MUTED = (124, 132, 148)
DIM = (82, 88, 102)

# ─── Domain data ─────────────────────────────────────────────────────────────

# (name, color, presence)  — presence: active | away | dnd | offline
YOU = 0
USERS = [
    ["you", ACCENT, "active"],
    ["alice", PINK, "active"],
    ["bob", AMBER, "active"],
    ["carla", GREEN, "active"],
    ["dave", PURPLE, "away"],
]

# (name, topic, messages, unread, flash_until) — messages built at init
CHANNEL_SEED = [
    ("#general", "the catch-all room"),
    ("#dev", "engineering chatter"),
    ("#random", "the off-topic zone"),
    ("#help", "stuck? ask here"),
    ("alice", "direct message"),
    ("bob", "direct message"),
    ("carla", "direct message"),
]

# Scripted bot timeline: (typing_at, send_at, channel_idx, uid, body)
SCRIPT_SEED = [
    (1.5, 3.5, 0, 1, "hey, anyone awake?"),
    (4.2, 6.5, 0, 2, "morning, just kicked off the deploy"),
    (7.0, 10.0, 1, 3, "seeing weird latency in the diff layer — anyone touch it?"),
    (10.5, 13.0, 1, 2, "yeah I rebased onto main last night, you might be hitting f620030"),
    (13.5, 16.0, 0, 1, "@you we need a UI review when you have a sec"),
    (16.5, 19.0, 2, 4, "anyone seen the new builds? the renderer demos go hard"),
    (19.5, 21.0, 1, 3, "the strip renderer is going to be wild when it lands"),
    (21.5, 23.5, 3, 2, "if anyone hits permission prompts try --allow-bash"),
    (24.0, 26.5, 0, 1, "lunch?"),
    (27.0, 29.5, 0, 2, "im in. 12:30?"),
    (5.0, 7.5, 4, 1, "@you hey, got a min for a quick UI Q?"),
    (8.5, 10.5, 4, 1, "the composer caret position drifts when I paste, expected?"),
    (12.0, 14.5, 5, 2, "btw — interested in the A3 strip renderer work? I'm picking it up next week"),
    (18.0, 20.0, 6, 3, "lunch tomorrow? trying that new ramen place"),
    (30.0, 32.0, 1, 3, "@you can you take a look at PR #4421 when you're back?"),
    (33.0, 35.0, 4, 1, "@you nvm figured it out — utf8 boundary thing"),
]

AMBIENT = [
    "ship it", "lgtm", "I'll take a look in a bit",
    "did anyone update the docs for that?", "merge conflict",
    "tests are green", "tests are red", "rebase needed",
    "+1", "approved", "can someone review #4421",
    "I think the cache is invalidating wrong", "saw it, will fix",
    "this is fine", "back from coffee", "afk for 20",
    "anyone seen carla's last PR?", "@you do you have a min later?",
    "OOO friday", "huh, that's a new one", "reverted it for now",
    "small nit but otherwise good", "branch was force-pushed, fyi",
    "going to grab dinner, brb",
]

EMOJI = {"+1": "+1", "heart": "♥", "fire": "★", "eyes": "◉",
         "rocket": "▲", "tada": "✦"}


# ─── Pure helpers ────────────────────────────────────────────────────────────

def is_dm(name):
    return bool(name) and name[0] != "#"


def dm_uid(name):
    for i, u in enumerate(USERS):
        if u[0] == name:
            return i
    return -1


def mentions_you(body):
    return "@you" in body


def presence_dot(p):
    return "●" if p in ("active", "dnd") else "○"


def presence_color(p):
    return {"active": GREEN, "away": AMBER, "dnd": RED}.get(p, DIM)


def presence_label(p):
    return p


def fmt_age(clock, ts):
    if ts < 0:
        return "—"
    age = int(clock - ts)
    if age <= 1:
        return "now"
    if age < 60:
        return f"{age}s"
    if age < 3600:
        return f"{age // 60}m"
    return f"{age // 3600}h"


def fmt_clock(clock):
    sec = max(0, int(clock))
    if sec >= 3600:
        return f"{sec // 3600}:{(sec // 60) % 60:02d}:{sec % 60:02d}"
    return f"{sec // 60}:{sec % 60:02d}"


def two_letter(name):
    n = name[1:] if name.startswith("#") else name
    a = n[0].upper() if n else "?"
    bb = n[1].upper() if len(n) > 1 else " "
    return a + bb


def channel_color(idx):
    return [ACCENT, AMBER, GREEN, PINK, PURPLE][((idx % 5) + 5) % 5]


def circled_digit(n):
    g = ["❶", "❷", "❸", "❹", "❺", "❻", "❼", "❽", "❾", "❿"]
    if n <= 0:
        return ""
    if n <= 10:
        return g[n - 1]
    return str(n)


def truncate(s, mx):
    if len(s) <= mx:
        return s
    out = s[:mx - 3].rstrip()
    return out + "..."


def avatar(name, clr):
    # 4-cell colored chip (the one place bg color is used, like the C++).
    return T(" " + two_letter(name) + " ").bg(clr).fg((20, 22, 28)).bold


def prev_word(s, pos):
    while pos > 0 and s[pos - 1].isspace():
        pos -= 1
    while pos > 0 and not s[pos - 1].isspace():
        pos -= 1
    return pos


def reactions_chips(rs):
    return "  ".join(f"[{EMOJI.get(e, e)} {c}]" for e, c in rs)


# ─── Mutable model ───────────────────────────────────────────────────────────

class Channel:
    def __init__(self, name, topic):
        self.name = name
        self.topic = topic
        self.messages = []   # each: dict(uid, body, ts, mention, action, reactions)
        self.unread = 0
        self.flash_until = 0.0


def make_message(uid, body, ts, mention=False, action=False):
    return {"uid": uid, "body": body, "ts": ts,
            "mention": mention, "action": action, "reactions": []}


# xorshift32 — deterministic, mirrors the C++ rng.
class Rng:
    def __init__(self, seed=0x12345):
        self.s = seed

    def next(self):
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        self.s = s & 0xFFFFFFFF
        return self.s


# ─── App ─────────────────────────────────────────────────────────────────────

app = App("messenger", inline=True, fps=20)


def _init_channels():
    chans = []
    for name, topic in CHANNEL_SEED:
        ch = Channel(name, topic)
        ch.messages.append(make_message(-1, f"joined {name} · {topic}", -10.0))
        chans.append(ch)
    return chans


app.state(
    channels=_init_channels(),
    script=list(SCRIPT_SEED),
    typing=[],                     # list of (uid, channel, until)
    active=0,
    composer="",
    cursor=0,                      # char offset into composer
    clock=0.0,
    tick_n=0,
    next_ambient_at=35.0,
    rng=Rng(),
    jumper_open=False,
    jumper_filter="",
    jumper_index=0,
    help_open=False,
    right_panel=True,
    msg_scroll=scroll_state(),
)
app.s.msg_scroll.step_y = 1


# ─── Simulation (peer feed) ──────────────────────────────────────────────────

def deliver(st, chan, uid, body, action=False):
    if not (0 <= chan < len(st.channels)):
        return
    msg = make_message(uid, body, st.clock,
                       mention=(not action and mentions_you(body)),
                       action=action)
    ch = st.channels[chan]
    ch.messages.append(msg)
    ch.messages = ch.messages[-200:]
    st.typing = [t for t in st.typing if not (t[0] == uid and t[1] == chan)]
    if chan != st.active:
        ch.unread += 1
        if msg["mention"]:
            ch.flash_until = st.clock + 4.0
    else:
        st.msg_scroll.scroll_to_bottom()


def push_system(ch, body, clock):
    ch.messages.append(make_message(-1, body, clock))


def tick_bots(st, dt):
    st.clock += dt
    st.tick_n += 1

    st.typing = [t for t in st.typing if t[2] > st.clock]

    remaining = []
    for ev in st.script:
        typing_at, send_at, chan, uid, body = ev
        if typing_at <= st.clock < send_at:
            active = any(t[0] == uid and t[1] == chan for t in st.typing)
            if not active:
                st.typing.append((uid, chan, send_at + 0.05))
            remaining.append(ev)
        elif send_at <= st.clock:
            deliver(st, chan, uid, body)
        else:
            remaining.append(ev)
    st.script = remaining

    if not st.script and st.clock >= st.next_ambient_at:
        r1, r2, r3, r4 = (st.rng.next() for _ in range(4))
        uid = 1 + r1 % (len(USERS) - 1)
        chan = r2 % len(st.channels)
        if is_dm(st.channels[chan].name):
            partner = dm_uid(st.channels[chan].name)
            if partner > 0:
                uid = partner
        body = AMBIENT[r3 % len(AMBIENT)]
        st.script.append((st.clock, st.clock + 1.6, chan, uid, body))
        st.next_ambient_at = st.clock + 3.5 + (r4 % 50) / 10.0

    # Sporadic reactions on a recent message.
    if st.tick_n % 60 == 0:
        chan = st.rng.next() % len(st.channels)
        ch = st.channels[chan]
        if len(ch.messages) >= 2:
            span = min(3, len(ch.messages))
            idx = len(ch.messages) - 1 - (st.rng.next() % span)
            if idx >= 0 and ch.messages[idx]["uid"] != -1:
                ems = ["+1", "heart", "fire", "eyes", "rocket", "tada"]
                pick = ems[st.rng.next() % len(ems)]
                rs = ch.messages[idx]["reactions"]
                for i, (e, c) in enumerate(rs):
                    if e == pick:
                        rs[i] = (e, c + 1)
                        break
                else:
                    rs.append((pick, 1))


# ─── Slash commands ──────────────────────────────────────────────────────────

def run_command(st, body):
    """Returns True if consumed as a command (don't deliver as a message)."""
    if not body or body[0] != "/":
        return False
    body = body[1:]
    head, _, arg = body.partition(" ")
    cmd, arg = head, arg.strip()
    ch = st.channels[st.active]

    if cmd == "help":
        st.help_open = True
        return True
    if cmd == "me" and arg:
        deliver(st, st.active, YOU, arg, action=True)
        return True
    if cmd == "clear":
        ch.messages.clear()
        push_system(ch, "channel cleared", st.clock)
        st.msg_scroll.scroll_to_bottom()
        return True
    if cmd == "topic" and arg:
        ch.topic = arg
        push_system(ch, f"you changed the topic to: {ch.topic}", st.clock)
        return True
    if cmd == "status" and arg:
        if arg in ("active", "away", "dnd", "offline"):
            USERS[YOU][2] = arg
            push_system(ch, f"you are now {arg}", st.clock)
        return True
    if cmd == "who":
        lst = "members: " + ", ".join(
            f"{u[0]} ({u[2]})" for u in USERS)
        push_system(ch, lst, st.clock)
        return True
    if cmd in ("quit", "exit"):
        app.stop()
        return True
    push_system(ch, f"unknown command: /{cmd}  (try /help)", st.clock)
    return True


# ─── Key handlers ────────────────────────────────────────────────────────────

@app.on_key
def _typing(st, ev):
    """Free-form composer / jumper typing (printable chars only)."""
    cp = maya.event_char(ev)
    if cp is None or maya.ctrl(ev, cp) or maya.alt(ev, cp):
        return
    if not cp or ord(cp[0]) < 0x20:
        return
    if st.help_open:
        return
    if st.jumper_open:
        if len(st.jumper_filter) < 32:
            st.jumper_filter += cp
        st.jumper_index = 0
        return
    if len(st.composer) < 500:
        st.composer = st.composer[:st.cursor] + cp + st.composer[st.cursor:]
        st.cursor += len(cp)


@app.on("backspace")
def _backspace(st):
    if st.help_open:
        st.help_open = False
        return
    if st.jumper_open:
        st.jumper_filter = st.jumper_filter[:-1]
        st.jumper_index = 0
        return
    if st.cursor > 0:
        st.composer = st.composer[:st.cursor - 1] + st.composer[st.cursor:]
        st.cursor -= 1


@app.on("enter")
def _enter(st):
    if st.help_open:
        st.help_open = False
        return
    if st.jumper_open:
        _jumper_pick(st)
        return
    s = st.composer.strip()
    if not s:
        return
    if s in ("/quit", "/exit"):
        app.stop()
        return
    if s[0] == "/":
        run_command(st, s)
    else:
        deliver(st, st.active, YOU, s)
    st.composer = ""
    st.cursor = 0
    st.msg_scroll.scroll_to_bottom()


@app.on("left")
def _left(st):
    if not (st.help_open or st.jumper_open):
        st.cursor = max(0, st.cursor - 1)


@app.on("right")
def _right(st):
    if not (st.help_open or st.jumper_open):
        st.cursor = min(len(st.composer), st.cursor + 1)


@app.on("ctrl+a")
def _home(st): st.cursor = 0


@app.on("ctrl+e")
def _end(st): st.cursor = len(st.composer)


@app.on("home")
def _khome(st):
    if not (st.help_open or st.jumper_open):
        st.cursor = 0


@app.on("ctrl+w")
def _del_word(st):
    p = prev_word(st.composer, st.cursor)
    st.composer = st.composer[:p] + st.composer[st.cursor:]
    st.cursor = p


@app.on("ctrl+u")
def _del_to_start(st):
    st.composer = st.composer[st.cursor:]
    st.cursor = 0


@app.on("ctrl+k")
def _del_to_end(st):
    st.composer = st.composer[:st.cursor]


@app.on("tab")
def _next_ch(st):
    if st.jumper_open:
        _jumper_move(st, +1)
        return
    n = len(st.channels)
    st.active = (st.active + 1) % n
    st.channels[st.active].unread = 0
    st.msg_scroll.scroll_to_bottom()


@app.on("shift+tab")
def _prev_ch(st):
    if st.jumper_open:
        _jumper_move(st, -1)
        return
    n = len(st.channels)
    st.active = (st.active - 1) % n
    st.channels[st.active].unread = 0
    st.msg_scroll.scroll_to_bottom()


@app.on("up")
def _up(st):
    if st.jumper_open:
        _jumper_move(st, -1)


@app.on("down")
def _down(st):
    if st.jumper_open:
        _jumper_move(st, +1)


@app.on("end")
def _latest(st):
    if not (st.help_open or st.jumper_open):
        st.msg_scroll.scroll_to_bottom()


@app.on("ctrl+g")
def _jump_toggle(st):
    if st.jumper_open:
        st.jumper_open = False
    else:
        st.jumper_open = True
        st.jumper_filter = ""
        st.jumper_index = 0


@app.on("ctrl+h")
def _help(st):
    st.help_open = True


@app.on("ctrl+l")
def _clear(st):
    ch = st.channels[st.active]
    ch.messages.clear()
    push_system(ch, "channel cleared", st.clock)
    st.msg_scroll.scroll_to_bottom()


@app.on("ctrl+p")
def _toggle_panel(st):
    st.right_panel = not st.right_panel


@app.on("esc")
def _esc(st):
    if st.help_open:
        st.help_open = False
    elif st.jumper_open:
        st.jumper_open = False
    elif st.composer:
        st.composer = ""
        st.cursor = 0
    else:
        app.stop()


@app.on("q")
def _q(st):
    # Only quit on bare 'q' when the composer is empty (else 'q' types).
    if not st.composer and not st.jumper_open and not st.help_open:
        app.stop()


# ─── Jumper helpers ──────────────────────────────────────────────────────────

def jumper_matches(st):
    needle = st.jumper_filter.lower()
    return [i for i, ch in enumerate(st.channels)
            if not needle or needle in ch.name.lower()]


def _jumper_move(st, d):
    n = len(jumper_matches(st))
    st.jumper_index = max(0, min(max(0, n - 1), st.jumper_index + d))


def _jumper_pick(st):
    matches = jumper_matches(st)
    if matches:
        idx = max(0, min(st.jumper_index, len(matches) - 1))
        st.active = matches[idx]
        st.channels[st.active].unread = 0
        st.msg_scroll.scroll_to_bottom()
    st.jumper_open = False


# ─── Per-frame tick ──────────────────────────────────────────────────────────

@app.on_frame
def _frame(st, dt):
    if not (st.help_open or st.jumper_open):
        tick_bots(st, dt)
    else:
        # keep the clock advancing for the caret blink even when modal.
        st.tick_n += 1


# ─── View builders ───────────────────────────────────────────────────────────

def build_message(st, msg, compact):
    uid = msg["uid"]
    if uid < 0:
        return center(T(f"• {msg['body']} •").fg(DIM).italic)
    if msg["action"]:
        u = USERS[uid]
        return row(T("  * ").fg(MUTED),
                   T(f"{u[0]} {msg['body']}").fg(u[1]).italic)
    if uid == YOU:
        return _own_message(st, msg)
    return _peer_message(st, msg, compact)


def _own_message(st, msg):
    age = int(st.clock - msg["ts"])
    check = "✓✓" if age >= 2 else "✓"
    check_c = ACCENT if age >= 5 else MUTED if age >= 2 else DIM
    border_c = AMBER if msg["mention"] else ACCENT
    body = T(msg["body"]).fg(TEXT)
    if msg["mention"]:
        body = body.bold
    rows = [body]
    if msg["reactions"]:
        rows.append(T(reactions_chips(msg["reactions"])).fg(AMBER).dim)
    rows.append(row(spacer(), T(fmt_age(st.clock, msg["ts"])).fg(DIM),
                    T("  "), T(check).fg(check_c).bold))
    bubble = col(*rows, border="round", border_color=border_c, pad=(0, 1))
    return row(spacer(), bubble)


def _peer_message(st, msg, compact):
    uid = msg["uid"]
    u = USERS[uid]
    group = not is_dm(st.channels[st.active].name)
    border_c = AMBER if msg["mention"] else MUTED
    rows = []
    if not compact and group:
        rows.append(T(u[0]).fg(u[1]).bold)
    body = T(msg["body"]).fg(TEXT)
    if msg["mention"]:
        body = body.bold
    rows.append(body)
    if msg["reactions"]:
        rows.append(T(reactions_chips(msg["reactions"])).fg(AMBER).dim)
    rows.append(row(spacer(), T(fmt_age(st.clock, msg["ts"])).fg(DIM)))
    bubble = col(*rows, border="round", border_color=border_c, pad=(0, 1))
    return row(bubble, spacer())


def build_messages_inner(st):
    ch = st.channels[st.active]
    rows = [center(T("── Today ──").fg(MUTED).bold), T("")]
    if all(m["uid"] < 0 for m in ch.messages):
        rows += [T(""), T(""),
                 T(f"  ✦  {ch.name} is quiet right now").fg(MUTED),
                 T(""),
                 T("  say hi, or try /help for commands").fg(DIM).italic]
    prev_author = -2
    prev_ts = -1000.0
    for msg in ch.messages:
        compact = (prev_author == msg["uid"]
                   and (msg["ts"] - prev_ts) < 60.0
                   and msg["uid"] >= 0 and not msg["action"])
        if prev_author != -2:
            rows.append(T(""))
        rows.append(build_message(st, msg, compact))
        prev_author = -3 if msg["action"] else msg["uid"]
        prev_ts = msg["ts"]
    return col(*rows)


def build_typing_indicator(st):
    names = [USERS[t[0]][0] for t in st.typing
             if t[1] == st.active and t[0] != YOU]
    if not names:
        return T("")
    if len(names) == 1:
        s = f"{names[0]} is typing"
    elif len(names) == 2:
        s = f"{names[0]} and {names[1]} are typing"
    else:
        s = f"{len(names)} people are typing"
    s += ["   ", ".  ", ".. ", "..."][(st.tick_n // 6) % 4]
    return row(T("  ⋯  ").fg(AMBER), T(s).fg(MUTED).italic)


def build_header(st):
    ch = st.channels[st.active]
    self_u = USERS[YOU]
    active_n = sum(1 for u in USERS if u[2] == "active")
    pending_mentions = 0
    pending_unread = 0
    for i, c in enumerate(st.channels):
        if i == st.active:
            continue
        if c.flash_until > st.clock:
            pending_mentions += 1
        pending_unread += c.unread
    dm = is_dm(ch.name)
    partner = dm_uid(ch.name) if dm else -1
    if dm and partner >= 0:
        subtitle = T(presence_label(USERS[partner][2])).fg(
            presence_color(USERS[partner][2])).dim
    else:
        subtitle = T(f"{active_n} online  ·  {ch.topic}").fg(MUTED)
    av_c = USERS[partner][1] if (dm and partner >= 0) else channel_color(st.active)
    left = row(T(" "), avatar(ch.name, av_c), T("  "),
               col(T(ch.name).fg(ACCENT).bold, subtitle), gap=0)
    right_items = []
    if pending_mentions:
        right_items += [T(circled_digit(pending_mentions)).fg(AMBER).bold, T("  ")]
    elif pending_unread:
        right_items += [T(str(pending_unread)).fg(AMBER).bold, T("  ")]
    right_items += [
        T(presence_dot(self_u[2])).fg(presence_color(self_u[2])),
        T("  "), T(fmt_clock(st.clock)).fg(DIM)]
    return row(left, spacer(), row(*right_items, gap=0), pad=(0, 1))


def build_composer(st):
    empty = not st.composer
    is_command = (not empty) and st.composer[0] == "/"
    caret_on = (st.tick_n // 10) % 2 == 0
    caret = "│" if caret_on else " "
    count = f"{len(st.composer)}/500"
    count_c = AMBER if len(st.composer) > 400 else DIM
    body_c = ACCENT if is_command else TEXT
    parts = [T("😊  ").fg(MUTED)]
    if is_command:
        parts.append(T("❯ ").fg(AMBER).bold)
    if empty:
        parts += [T(caret).fg(ACCENT).bold, T(" Message").fg(DIM).italic]
    else:
        c = max(0, min(st.cursor, len(st.composer)))
        parts += [T(st.composer[:c]).fg(body_c),
                  T(caret).fg(ACCENT).bold,
                  T(st.composer[c:]).fg(body_c)]
    right_btn = (T("🎤 ").fg(MUTED) if empty
                 else T(" ⏎ ").fg(ACCENT).bold)
    parts += [spacer(), T(count).fg(count_c), T("  "),
              T("📎 ").fg(MUTED), right_btn]
    return row(*parts, pad=(0, 2), gap=0)


# ─── Sidebars ────────────────────────────────────────────────────────────────

def append_chat_row(rows, st, i):
    ch = st.channels[i]
    active = i == st.active
    flash = ch.flash_until > st.clock
    dm = is_dm(ch.name)
    last = next((m for m in reversed(ch.messages) if m["uid"] >= 0), None)
    name_c = ACCENT if active else TEXT
    name = T(ch.name).fg(AMBER if flash else name_c)
    if active or flash:
        name = name.bold
    bar = T("▌").fg(ACCENT).bold if active else T(" ")
    selector = T(" ▶").fg(ACCENT).bold if active else T("  ")
    av_c = (USERS[dm_uid(ch.name)][1] if dm and dm_uid(ch.name) >= 0
            else channel_color(i))
    age = fmt_age(st.clock, last["ts"]) if last else ""
    rows.append(row(bar, selector, T(" "), avatar(ch.name, av_c), T("  "),
                    name, spacer(), T(age).fg(DIM), T(" "), gap=0))
    if last:
        if last["action"]:
            body = f"* {USERS[last['uid']][0]} {last['body']}"
        elif dm:
            body = ("you: " if last["uid"] == YOU else "") + last["body"]
        else:
            body = f"{USERS[last['uid']][0]}: {last['body']}"
        preview = truncate(body, 22)
        prev_c = AMBER if last["mention"] else MUTED
        preview_t = T(preview).fg(prev_c)
    else:
        preview_t = T("no messages yet").fg(MUTED).italic
    if flash:
        bdg = T(" !").fg(AMBER).bold
    elif ch.unread > 0:
        bdg = T(" " + circled_digit(ch.unread)).fg(AMBER).bold
    else:
        bdg = T("")
    rows.append(row(bar, T("         "), preview_t, spacer(), bdg, T(" "), gap=0))
    rows.append(T(""))


def build_channel_list(st):
    rows = [
        row(T("🔍  ").fg(MUTED), T("Search").fg(DIM).italic, spacer(),
            border="round", border_color=MUTED, pad=(0, 1), gap=0),
        T(""),
        T(" — CHATS").fg(MUTED).bold, T(""),
    ]
    for i, ch in enumerate(st.channels):
        if not is_dm(ch.name):
            append_chat_row(rows, st, i)
    rows += [T(" — DIRECT MESSAGES").fg(MUTED).bold, T("")]
    for i, ch in enumerate(st.channels):
        if is_dm(ch.name):
            append_chat_row(rows, st, i)
    rows += [T(" — SHORTCUTS").fg(MUTED).bold, T("")]
    for kk, desc in [("tab", "next"), ("^G", "jump"), ("^H", "help"),
                     ("^L", "clear"), ("^P", "panel"), ("q", "quit")]:
        rows.append(row(T(" " + kk).fg(TEXT), spacer(), T(desc).fg(MUTED), gap=0))
    return col(*rows, pad=(0, 1))


def build_member_list(st):
    ch = st.channels[st.active]
    av_c = channel_color(st.active)
    online = sum(1 for u in USERS if u[2] == "active")
    rows = [
        row(T(" — CHANNEL INFO").fg(MUTED).bold, spacer(), T("✕ ").fg(MUTED).bold, gap=0),
        T(""),
        center(col(avatar(ch.name, av_c), border="round", border_color=av_c, pad=(0, 2))),
        T(""),
        center(T(ch.name).fg(TEXT).bold),
        center(T(ch.topic).fg(MUTED).italic),
        T(""),
        center(T(f"{online} online  ·  {len(USERS)} total").fg(DIM).italic),
        T(""),
        T(" — MEMBERS").fg(MUTED).bold, T(""),
    ]
    for i, u in enumerate(USERS):
        typing_now = any(t[0] == i for t in st.typing)
        if typing_now:
            status = T("typing…").fg(AMBER).italic
        else:
            label = u[2] + (" (you)" if i == YOU else "")
            status = T(label).fg(presence_color(u[2])).dim
        rows.append(row(T(" "), avatar(u[0], u[1]), T("  "),
                        col(T(u[0]).fg(TEXT).bold, status),
                        spacer(),
                        T(presence_dot(u[2])).fg(presence_color(u[2])),
                        T(" "), gap=0))
        rows.append(T(""))
    rows += [T(" — ACTIONS").fg(MUTED).bold, T(""),
             row(T("  +  ").fg(ACCENT).bold, T("invite someone").fg(TEXT), gap=0),
             row(T("  ⚙  ").fg(MUTED).bold, T("channel settings").fg(TEXT), gap=0),
             row(T("  🔍  ").fg(MUTED).bold, T("search members").fg(TEXT), gap=0),
             T(""),
             T(" /status to change yours").fg(DIM).italic]
    return col(*rows, pad=(0, 1))


def build_dm_info_panel(st):
    ch = st.channels[st.active]
    uid = dm_uid(ch.name)
    if uid < 0:
        return T("")
    u = USERS[uid]
    rows = [
        row(T(" USER INFO").fg(MUTED).bold, spacer(), T("✕ ").fg(MUTED).bold, gap=0),
        T(""),
        center(col(avatar(u[0], u[1]), border="round", border_color=u[1], pad=(0, 2))),
        T(""),
        center(T(u[0]).fg(TEXT).bold),
        center(row(T(presence_dot(u[2]) + " ").fg(presence_color(u[2])),
                   T(presence_label(u[2])).fg(presence_color(u[2])), gap=0)),
        T(""), T(""),
        row(T(" ☎  ").fg(MUTED), col(T("+1 555 0100").fg(TEXT), T("Phone").fg(DIM)), gap=0),
        T(""),
        row(T(" @  ").fg(MUTED), col(T("@" + u[0]).fg(TEXT), T("Username").fg(DIM)), gap=0),
        T(""),
        row(T(" ⓘ  ").fg(MUTED), col(T("engineer · gardener · runner").fg(TEXT),
                                     T("Bio").fg(DIM)), gap=0),
        T(""),
        row(T(" ⚑  ").fg(MUTED), T("Notifications").fg(TEXT), spacer(),
            T("on ").fg(GREEN).bold, gap=0),
    ]
    return col(*rows, pad=1)


# ─── Overlays ────────────────────────────────────────────────────────────────

def build_jumper_overlay(st):
    matches = jumper_matches(st)
    caret = "_" if (st.tick_n // 10) % 2 == 0 else " "
    rows = [
        row(T(" ▶  go to channel  ").fg(ACCENT).bold,
            T(st.jumper_filter).fg(TEXT), T(caret).fg(ACCENT),
            spacer(),
            T(f" {len(matches)} · enter pick · esc close").fg(DIM), gap=0),
        T(""),
    ]
    if not matches:
        rows.append(T(f'  no channels match "{st.jumper_filter}"').fg(MUTED).italic)
    for i, ci in enumerate(matches):
        sel = i == st.jumper_index
        ch = st.channels[ci]
        marker = T(" ▶ ").fg(ACCENT) if sel else T("   ")
        name = T(ch.name).fg(ACCENT if sel else TEXT)
        if sel:
            name = name.bold
        badge_t = (T(" " + str(ch.unread)).fg(AMBER).bold
                   if ch.unread > 0 else T(""))
        rows.append(row(marker, name, T("   "),
                        T(ch.topic).fg(MUTED).dim, spacer(), badge_t, gap=0))
    return col(*rows, pad=(1, 2), border="round", border_color=ACCENT)


def build_help_overlay(st):
    def kr(kk, desc):
        return row(T("  " + kk).fg(AMBER), T("   "), T(desc).fg(TEXT), gap=0)

    def sec(s):
        return T("  " + s).fg(MUTED).bold

    rows = [
        T(" ✦  maya/chat  ·  help").fg(ACCENT).bold, T(""),
        sec("composer"),
        kr("←/→               ", "move cursor"),
        kr("^A   /   ^E       ", "jump to line start / end"),
        kr("^W   /   ^U   ^K  ", "delete prev word / clear to start / end"),
        kr("backspace         ", "delete previous char"),
        kr("enter             ", "send (or run /command)"), T(""),
        sec("navigation"),
        kr("tab / shift+tab   ", "next / previous channel"),
        kr("↑ ↓ PgUp PgDn end ", "scroll messages"),
        kr("^G                ", "channel jumper"),
        kr("^L                ", "clear current channel"),
        kr("^P                ", "toggle user info panel"),
        kr("q / esc / ^C      ", "quit"), T(""),
        sec("slash commands"),
        kr("/help             ", "this screen"),
        kr("/me <action>      ", "/me waves   →   * you waves"),
        kr("/topic <text>     ", "retitle the current channel"),
        kr("/status <state>   ", "active | away | dnd | offline"),
        kr("/who              ", "list members"),
        kr("/clear            ", "clear current channel"),
        kr("/quit             ", "exit"), T(""),
        T("  press any key to close").fg(DIM).italic,
    ]
    return col(*rows, pad=(1, 2), border="round", border_color=ACCENT)


# ─── View ────────────────────────────────────────────────────────────────────

@app.view
def view(st):
    header = build_header(st)
    composer = build_composer(st)
    inner = build_messages_inner(st)
    msgs = col(
        row(viewport(inner, st.msg_scroll, height=14, grow=1),
            scrollbar(st.msg_scroll, 14, style="neon", thumb_color="sky"),
            gap=0),
        build_typing_indicator(st),
        gap=0, grow=1,
    )
    middle = col(
        header,
        msgs,
        composer,
        gap=1, grow=1,
    )
    chats = col(build_channel_list(st), basis=30, grow=0, shrink=0)
    children = [
        card(chats, pad=1, basis=32, grow=0, shrink=0),
        col(middle, grow=1),
    ]
    if st.right_panel:
        inner_panel = (build_dm_info_panel(st) if is_dm(st.channels[st.active].name)
                       else build_member_list(st))
        children.append(card(inner_panel, pad=1, basis=34, grow=0, shrink=0))

    base = card(
        row(b("✉ maya messenger").fg(ACCENT),
            badge("online", kind="success"), justify="between"),
        row(*children, gap=1, grow=1),
        dim_text("type · Enter send · Tab switch · ^G jump · ^H help · q quit"),
        title="messenger", gap=1,
    )

    if st.help_open:
        return overlay(base, build_help_overlay(st), present=True)
    if st.jumper_open:
        return overlay(base, build_jumper_overlay(st), present=True)
    return base


if __name__ == "__main__":
    app.run()
