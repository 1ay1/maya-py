"""maya_py.easy — the friendly, batteries-included API.

Everything here is sugar over the primitives in ``maya_py._maya``. The goal:
make a UI or an interactive app trivial to write.

Three ideas:

1. **Strings are elements.** Anywhere a child is expected you can pass a plain
   ``str``. To style it, wrap it in ``T("...")`` and chain:

       T("Hello").bold.fg("sky")          # fluent
       b("Hello") + "  " + dim("world")   # markup-ish helpers

2. **Layout reads top-to-bottom.** ``col(...)`` / ``row(...)`` accept bare
   strings and Elements, with keyword styling (border, pad, gap, ...).

3. **Apps are a class with decorators.** No event dispatch boilerplate:

       app = App("counter")
       app.state(n=0)

       @app.on("+")
       def inc(s): s.n += 1

       @app.on("q", "esc")
       def quit(s): app.stop()

       @app.view
       def view(s):
           return card(f"Count: {s.n}", title="counter")

       app.run()
"""

from __future__ import annotations

from typing import Any, Callable

from . import _maya
from ._maya import Element, Style, Color, SpecialKey

# ── Named color palette ─────────────────────────────────────────────────────
# Friendly names → packed 0xRRGGBB int. Keeping these as ints (not Color
# objects) means resolving a color name is pure Python — no boundary crossing
# until the single styled_text() call that builds the element.
def _pack(r: int, g: int, b: int) -> int:
    return ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


_PALETTE: dict[str, int] = {
    "black": _pack(0, 0, 0), "white": _pack(235, 235, 235),
    "red": _pack(220, 80, 80), "green": _pack(80, 220, 120), "blue": _pack(90, 150, 250),
    "yellow": _pack(230, 210, 90), "magenta": _pack(210, 110, 210), "cyan": _pack(90, 210, 220),
    "gray": _pack(150, 150, 150), "grey": _pack(150, 150, 150),
    "orange": _pack(245, 160, 60), "purple": _pack(170, 120, 230), "pink": _pack(240, 130, 180),
    "teal": _pack(60, 200, 190), "lime": _pack(160, 230, 90), "sky": _pack(100, 180, 255),
    "gold": _pack(255, 200, 60), "slate": _pack(120, 135, 160),
}


def _rgb_int(value: Any) -> int:
    """Resolve a color-ish value to a packed 0xRRGGBB int. Pure Python."""
    if isinstance(value, int):
        return value & 0xFFFFFF
    if isinstance(value, str):
        v = value.strip().lower()
        hit = _PALETTE.get(v)
        if hit is not None:
            return hit
        if v.startswith("#"):
            h = v[1:]
            if len(h) == 3:
                h = h[0] * 2 + h[1] * 2 + h[2] * 2
            return int(h, 16) & 0xFFFFFF
        raise ValueError(f"unknown color: {value!r}")
    if isinstance(value, (tuple, list)):
        return _pack(int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, Color):
        # A real Color object — we can't unpack it cheaply, so fall back to
        # the slow path by stashing it; element() will use with_fg.
        return -2  # sentinel: "use the Color object"
    raise TypeError(f"cannot make a color from {value!r}")


def color(value: Any) -> Color:
    """Coerce almost anything into a maya Color (for the low-level API)."""
    if isinstance(value, Color):
        return value
    packed = _rgb_int(value)
    return Color.rgb((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)


# attribute bitmask (mirrors styled_text in the C++ binding)
_BOLD, _DIM, _ITALIC, _UNDERLINE, _STRIKE, _INVERSE = 1, 2, 4, 8, 16, 32


# ── T — a fluent styled string ──────────────────────────────────────────────
class T:
    """A chainable styled string. Renders to a maya text Element.

        T("Hello").bold.fg("sky")
        T("warn").fg("orange").italic
        T("x").bg("red").fg("white")

    Chaining mutates THIS object and returns it (no per-step allocation, no
    per-step boundary crossing). The styled Element is built lazily in a
    SINGLE pybind call at .element() time, then cached. This is what makes
    the fluent API cost ~one C++ crossing per element instead of five.

    Concatenate with ``+`` to append plain text (keeps the left style).
    """

    __slots__ = ("_s", "_fg", "_bg", "_attrs", "_cache")

    def __init__(self, s: Any = ""):
        self._s = s if type(s) is str else str(s)
        self._fg = -1
        self._bg = -1
        self._attrs = 0
        self._cache = None  # built Element, invalidated on any mutation

    # -- attribute toggles (return self; no allocation, no pybind) ------------
    @property
    def bold(self) -> "T": self._attrs |= _BOLD; self._cache = None; return self
    @property
    def dim(self) -> "T": self._attrs |= _DIM; self._cache = None; return self
    @property
    def italic(self) -> "T": self._attrs |= _ITALIC; self._cache = None; return self
    @property
    def underline(self) -> "T": self._attrs |= _UNDERLINE; self._cache = None; return self
    @property
    def strike(self) -> "T": self._attrs |= _STRIKE; self._cache = None; return self
    @property
    def inverse(self) -> "T": self._attrs |= _INVERSE; self._cache = None; return self

    # -- colors (resolve to packed int in pure Python) ------------------------
    def fg(self, c: Any) -> "T":
        self._fg = c if isinstance(c, Color) else _rgb_int(c)
        self._cache = None
        return self

    def bg(self, c: Any) -> "T":
        self._bg = c if isinstance(c, Color) else _rgb_int(c)
        self._cache = None
        return self

    # -- composition ----------------------------------------------------------
    def __add__(self, other: Any) -> "T":
        text = other._s if isinstance(other, T) else str(other)
        t = T(self._s + text)
        t._fg, t._bg, t._attrs = self._fg, self._bg, self._attrs
        return t

    def __radd__(self, other: Any) -> "T":
        t = T(str(other) + self._s)
        t._fg, t._bg, t._attrs = self._fg, self._bg, self._attrs
        return t

    def __str__(self) -> str:
        return self._s

    def __repr__(self) -> str:
        return f"T({self._s!r})"

    # -- render (single boundary crossing, cached) ----------------------------
    def element(self) -> Element:
        e = self._cache
        if e is None:
            fg, bg = self._fg, self._bg
            if isinstance(fg, Color) or isinstance(bg, Color):
                # Rare: a raw Color object was passed. Build a Style explicitly.
                st = Style()
                if isinstance(fg, Color):
                    st = st.with_fg(fg)
                elif fg >= 0:
                    st = st.with_fg(color(fg))
                if isinstance(bg, Color):
                    st = st.with_bg(bg)
                elif bg >= 0:
                    st = st.with_bg(color(bg))
                a = self._attrs
                if a & _BOLD: st = st.with_bold()
                if a & _DIM: st = st.with_dim()
                if a & _ITALIC: st = st.with_italic()
                if a & _UNDERLINE: st = st.with_underline()
                if a & _STRIKE: st = st.with_strikethrough()
                if a & _INVERSE: st = st.with_inverse()
                e = _maya.text(self._s, st)
            else:
                e = _maya.styled_text(self._s, fg, bg, self._attrs)
            self._cache = e
        return e


# ── markup-style shortcuts ───────────────────────────────────────────────────
def b(s: Any) -> T: return T(s).bold
def i(s: Any) -> T: return T(s).italic
def u(s: Any) -> T: return T(s).underline
def dim(s: Any) -> T: return T(s).dim
def c(s: Any, col: Any) -> T: return T(s).fg(col)


# ── element coercion ─────────────────────────────────────────────────────────
def _el(x: Any) -> Element:
    """Turn str / T / Element into an Element."""
    if isinstance(x, Element):
        return x
    if isinstance(x, T):
        return x.element()
    if isinstance(x, str):
        return _maya.text(x)
    if x is None:
        return _maya.blank()
    raise TypeError(f"not a renderable child: {x!r}")


def _children(items) -> list[Element]:
    return [_el(x) for x in items]


# ── layout ───────────────────────────────────────────────────────────────────
#
# _box forwards the FULL maya BoxBuilder surface. Most opts pass straight
# through to _maya.box; a handful accept friendly string aliases (border,
# align, justify, wrap, overflow) or color-ish values (border_color, bg, fg)
# which we resolve here. Sizes (width/height/min_*/max_*/basis) accept int,
# float, "N%", "auto", or a Dimension — _maya.box coerces them.

_ENUM_OPTS = {
    "border": lambda v: v if not isinstance(v, str) else _lookup(_BORDERS, v, "border"),
    "align": lambda v: v if not isinstance(v, str) else _lookup(_ALIGN, v, "align"),
    "align_self": lambda v: v if not isinstance(v, str) else _lookup(_ALIGN, v, "align_self"),
    "justify": lambda v: v if not isinstance(v, str) else _lookup(_JUSTIFY, v, "justify"),
    "wrap": lambda v: v if not isinstance(v, str) else _lookup(_WRAP, v, "wrap"),
    "overflow": lambda v: v if not isinstance(v, str) else _lookup(_OVERFLOW, v, "overflow"),
}
_COLOR_OPTS = ("border_color", "bg", "fg")
# user-friendly aliases -> real maya.box kwarg
_ALIASES = {"pad": "padding", "title": "_title"}


def _box(children, *, direction, **opts) -> Element:
    out: dict[str, Any] = {"direction": direction}

    # title is sugar: a centered border_text + a default Round border.
    title = opts.pop("title", None)
    if title is not None:
        out["border_text"] = f" {title} "
        opts.setdefault("border", "round")

    pad = opts.pop("pad", None)
    if pad is not None:
        out["padding"] = pad

    for k, v in opts.items():
        if v is None:
            continue
        if k in _ENUM_OPTS:
            out[k] = _ENUM_OPTS[k](v)
        elif k in _COLOR_OPTS:
            out[k] = color(v)
        elif k == "style" and not isinstance(v, Style):
            raise TypeError("style= must be a maya Style")
        else:
            out[k] = v

    return _maya.box(*_children(children), **out)


def _lookup(table: dict, key: str, what: str):
    """Case-insensitive enum-name lookup with a helpful error."""
    hit = table.get(key.lower())
    if hit is None:
        opts = ", ".join(sorted(table))
        raise ValueError(f"unknown {what} {key!r}; valid: {opts}")
    return hit


_BORDERS = {
    "round": _maya.BorderStyle.Round, "single": _maya.BorderStyle.Single,
    "double": _maya.BorderStyle.Double, "bold": _maya.BorderStyle.Bold,
    "classic": _maya.BorderStyle.Classic, "dashed": _maya.BorderStyle.Dashed,
    "singledouble": _maya.BorderStyle.SingleDouble,
    "doublesingle": _maya.BorderStyle.DoubleSingle,
    "arrow": _maya.BorderStyle.Arrow,
    "none": _maya.BorderStyle.None_,
}
_ALIGN = {"start": _maya.Align.Start, "center": _maya.Align.Center,
          "end": _maya.Align.End, "stretch": _maya.Align.Stretch,
          "baseline": _maya.Align.Baseline}
_JUSTIFY = {"start": _maya.Justify.Start, "center": _maya.Justify.Center,
            "end": _maya.Justify.End, "between": _maya.Justify.SpaceBetween,
            "around": _maya.Justify.SpaceAround, "evenly": _maya.Justify.SpaceEvenly}
_WRAP = {"nowrap": _maya.FlexWrap.NoWrap, "wrap": _maya.FlexWrap.Wrap,
        "reverse": _maya.FlexWrap.WrapReverse, "wrapreverse": _maya.FlexWrap.WrapReverse}
_OVERFLOW = {"visible": _maya.Overflow.Visible, "hidden": _maya.Overflow.Hidden,
             "scroll": _maya.Overflow.Scroll}


def col(*children, **opts) -> Element:
    """Vertical stack. Children may be strings, T's, or Elements."""
    return _box(children, direction=_maya.FlexDirection.Column, **opts)


def row(*children, **opts) -> Element:
    """Horizontal stack."""
    return _box(children, direction=_maya.FlexDirection.Row, **opts)


def card(*children, title=None, **opts) -> Element:
    """A bordered, padded vertical box. The everyday container."""
    opts.setdefault("pad", 1)
    opts.setdefault("border", _maya.BorderStyle.Round)
    return col(*children, title=title, **opts)


def center(*children, **opts) -> Element:
    """A box that centers its children on both axes.

    By default a column; pass ``direction=maya.Row`` (or use ``row``-style
    opts) for horizontal centering. Combine with ``grow=1`` / ``height``
    to center within a region.
    """
    opts.setdefault("align", "center")
    opts.setdefault("justify", "center")
    opts.setdefault("direction", _maya.FlexDirection.Column)
    return _box(children, **opts)


def stack(*layers) -> Element:
    """Z-stack: layers paint on top of each other; the FIRST layer sets the
    size, later ones overlay (clipped to it). Great for badges/overlays.

        stack(card(body, height=10), T("NEW").fg("red"))
    """
    return _maya.zstack(*_children(layers))


def component(render_fn: Callable[[int, int], Any], *, grow: float | None = None,
              width=None, height=None) -> Element:
    """A size-aware element. ``render_fn(w, h)`` is called once layout has
    allocated a width/height, and returns the node to fill that space.

    Use it to draw things that need to know their box — bars, gauges, ASCII
    charts, progress fills:

        def bar(w, h):
            filled = int(w * pct)
            return T("█" * filled + "░" * (w - filled)).fg("green")
        col("Loading", component(bar, height=1))
    """
    def cb(w: int, h: int):
        return _el(render_fn(w, h))
    return _maya.component(cb, grow=grow, width=width, height=height)


def nothing() -> Element:
    """A zero-row transparent fragment. Use for a view slot that should
    consume NO space when its content is absent (vs ``spacer()`` = one row)."""
    return _maya.nothing()


def grow(child: Any, factor: float = 1.0, **opts) -> Element:
    """Wrap a child so it expands to fill available space along the main axis.

        row(sidebar, grow(main_content))
    """
    return _box([child], direction=_maya.FlexDirection.Column, grow=factor, **opts)


# ── dimension sugar ─────────────────────────────────────────────────────────
# width=/height=/etc already accept int, "N%", "auto", or a float in (0,1].
# These build an explicit Dimension when you want to be unambiguous.
def pct(value: float) -> "_maya.Dimension":
    """A percentage size, e.g. ``width=pct(50)``."""
    return _maya.Dimension.percent(float(value))


def cells(value: int) -> "_maya.Dimension":
    """A fixed cell size, e.g. ``width=cells(20)``."""
    return _maya.Dimension.fixed(int(value))


def auto() -> "_maya.Dimension":
    """Auto size (content-driven / fill parent)."""
    return _maya.Dimension.auto()


# ── border helpers ──────────────────────────────────────────────────────────
def sides(*, top=True, right=True, bottom=True, left=True):
    """Per-side border toggle for ``border_sides=``.

        card(body, border_sides=sides(top=False, bottom=False))
    """
    return _maya.BorderSides(top, right, bottom, left)


def field(label: str, value: Any, *, label_color="slate", value_color=None) -> Element:
    """A 'Label: value' row with a dim label."""
    val = value if isinstance(value, (T, Element)) else T(str(value))
    if value_color is not None and isinstance(val, T):
        val = val.fg(value_color)
    return row(T(label + ":").fg(label_color), val, gap=1)


def hr(width: int = 40, char: str = "─", col: str = "slate") -> Element:
    """A horizontal rule."""
    return T(char * width).fg(col).element()


def spacer() -> Element:
    """A one-row blank gap."""
    return _maya.blank()


# ── memo — cache a built sub-tree across frames ─────────────────────────────
# The single biggest speed lever for live apps: if a sub-UI's inputs didn't
# change, DON'T rebuild it in Python — hand maya the same cached Element. The
# hot frame then does no Python tree construction at all, just maya's native
# layout + diff.
#
#   @memo
#   def header(title, count):          # rebuilt only when args change
#       return card(b(title), f"{count} items")
#
#   def view(s):
#       return col(header(s.title, len(s.items)), body(s))
class _Memo:
    __slots__ = ("_fn", "_key", "_val")

    def __init__(self, fn):
        self._fn = fn
        self._key = _MISSING
        self._val = None

    def __call__(self, *args):
        if args != self._key:
            self._key = args
            self._val = _el(self._fn(*args))
        return self._val


_MISSING = object()


def memo(fn):
    """Decorator: cache a builder by its positional args (must be hashable/
    comparable). Returns the same Element until the args change — so unchanged
    sub-trees skip Python rebuild entirely."""
    return _Memo(fn)


# ── rendering ────────────────────────────────────────────────────────────────
def show(node: Any, width: int | None = None) -> None:
    """Render any node (str / T / Element) to stdout, once."""
    _maya.print_element(_el(node), width)


def to_string(node: Any, width: int = 80) -> str:
    return _maya.render_to_string(_el(node), width)


# ── App — interactive app with decorator key bindings ────────────────────────
class _State:
    """A tiny attribute bag for app state."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


# friendly key aliases → matcher
_SPECIAL = {
    "up": SpecialKey.Up, "down": SpecialKey.Down,
    "left": SpecialKey.Left, "right": SpecialKey.Right,
    "enter": SpecialKey.Enter, "return": SpecialKey.Enter,
    "esc": SpecialKey.Escape, "escape": SpecialKey.Escape,
    "tab": SpecialKey.Tab, "backtab": SpecialKey.BackTab,
    "space": None,  # handled as ' '
    "backspace": SpecialKey.Backspace, "delete": SpecialKey.Delete,
    "home": SpecialKey.Home, "end": SpecialKey.End,
    "pageup": SpecialKey.PageUp, "pagedown": SpecialKey.PageDown,
}

# friendly mouse-button names → MouseButton enum
_MOUSE_BTN = {
    "left": _maya.MouseButton.Left,
    "right": _maya.MouseButton.Right,
    "middle": _maya.MouseButton.Middle,
}


class App:
    """An interactive maya app with zero event-loop boilerplate.

        app = App("demo", inline=True)
        app.state(n=0)

        @app.on("+", "=")
        def inc(s): s.n += 1

        @app.on("q", "esc")
        def quit(s): app.stop()

        @app.view
        def view(s):
            return card(f"n = {s.n}")

        app.run()

    Handlers receive the state object and may return nothing. Returning a
    new view is unnecessary — the view function is re-evaluated every frame.
    """

    def __init__(self, title: str = "", *, inline: bool = True,
                 mouse: bool = False, fps: int = 0, quit_on_ctrl_c: bool = True):
        self.title = title
        self.inline = inline
        self.mouse = mouse
        self.fps = fps
        self.quit_on_ctrl_c = quit_on_ctrl_c
        self._state = _State()
        self._bindings: list[tuple[Callable[[Any], bool], Callable]] = []
        self._view: Callable[[Any], Any] | None = None
        self._any: list[Callable] = []
        self._clicks: list[tuple[Any, Callable]] = []   # (button|None, fn)
        self._scrolls: list[Callable] = []
        self._mouse_any: list[Callable] = []
        self._running = True
        self._ctrl_c_bound = False  # set if the user binds ctrl+c themselves

    # -- state ---------------------------------------------------------------
    def state(self, **kw) -> _State:
        """Seed initial state. Returns the state object."""
        self._state.__dict__.update(kw)
        return self._state

    @property
    def s(self) -> _State:
        return self._state

    # -- bindings ------------------------------------------------------------
    def on(self, *keys: str):
        """Decorator: bind one or more keys to a handler ``fn(state)``.

        Keys are chars ("q", "+") or names ("up", "esc", "enter", "space").
        """
        if any(k.lower().replace(" ", "") in ("ctrl+c", "^c") for k in keys):
            self._ctrl_c_bound = True
        matchers = [self._matcher(k) for k in keys]

        def deco(fn):
            self._bindings.append((lambda ev: any(m(ev) for m in matchers), fn))
            return fn
        return deco

    def on_key(self, fn):
        """Decorator: call ``fn(state, event)`` for every key event."""
        self._any.append(fn)
        return fn

    # -- mouse bindings ------------------------------------------------------
    def on_click(self, button: str = "left"):
        """Decorator: bind a mouse-button PRESS to ``fn(state, col, row)``.

        ``button`` is "left" / "right" / "middle" (or "any"). Registering any
        mouse handler auto-enables mouse reporting.

        Example::

            @app.on_click()
            def click(s, col, row): s.last = (col, row)
        """
        self.mouse = True
        btn = None if button.lower() in ("any", "") else _MOUSE_BTN[button.lower()]

        def deco(fn):
            self._clicks.append((btn, fn))
            return fn
        return deco

    def on_scroll(self, fn):
        """Decorator: call ``fn(state, direction)`` on wheel scroll, where
        ``direction`` is -1 (up) or +1 (down). Auto-enables mouse reporting."""
        self.mouse = True
        self._scrolls.append(fn)
        return fn

    def on_mouse(self, fn):
        """Decorator: call ``fn(state, event)`` for EVERY mouse event (press,
        release, move, scroll). Use the ``maya.mouse_*`` predicates on the
        event. Auto-enables mouse reporting."""
        self.mouse = True
        self._mouse_any.append(fn)
        return fn

    def view(self, fn):
        """Decorator: register the view function ``fn(state) -> node``."""
        self._view = fn
        return fn

    def stop(self) -> None:
        """Request the app to quit."""
        self._running = False

    # -- internals -----------------------------------------------------------
    def _matcher(self, k: str) -> Callable[[Any], bool]:
        key = k.lower()
        if key == "space":
            return lambda ev: _maya.key(ev, " ")
        if key in _SPECIAL and _SPECIAL[key] is not None:
            sk = _SPECIAL[key]
            return lambda ev: _maya.key_special(ev, sk)
        if key.startswith("ctrl+") and len(key) == 6:
            ch = key[5]
            return lambda ev: _maya.ctrl(ev, ch)
        if key.startswith("alt+") and len(key) == 5:
            ch = key[4]
            return lambda ev: _maya.alt(ev, ch)
        # single character (use original case so '+' etc. survive)
        ch = k
        return lambda ev: _maya.key(ev, ch)

    def _event(self, ev) -> bool:
        # Ctrl-C arrives as a key event (raw mode disables tty signals), so a
        # frozen app can always be killed unless the user took over ctrl+c.
        if self.quit_on_ctrl_c and not self._ctrl_c_bound and _maya.ctrl(ev, "c"):
            self._running = False
            return False

        # Mouse events route to mouse handlers only (never key bindings).
        if _maya.is_mouse(ev):
            for fn in self._mouse_any:
                fn(self._state, ev)
            if _maya.scrolled_up(ev):
                for fn in self._scrolls:
                    fn(self._state, -1)
            elif _maya.scrolled_down(ev):
                for fn in self._scrolls:
                    fn(self._state, +1)
            else:
                pos = _maya.mouse_pos(ev)
                for btn, fn in self._clicks:
                    if _maya.mouse_clicked(ev) if btn is None else _maya.mouse_clicked(ev, btn):
                        col, row = pos if pos else (0, 0)
                        fn(self._state, col, row)
            return self._running

        for fn in self._any:
            fn(self._state, ev)
        for match, fn in self._bindings:
            if match(ev):
                fn(self._state)
                break
        return self._running

    def _render(self) -> Element:
        if self._view is None:
            return _maya.text("(no view registered)")
        return _el(self._view(self._state))

    def run(self) -> None:
        """Start the event loop. Blocks until a handler calls ``stop()``
        (or the user presses Ctrl-C, unless ``quit_on_ctrl_c=False``)."""
        if getattr(self, "_in_run", False):
            raise RuntimeError("App.run() is already running (cannot nest)")
        self._in_run = True
        self._running = True
        try:
            _maya.run(self._event, self._render,
                      title=self.title, inline_mode=self.inline,
                      mouse=self.mouse, fps=self.fps)
        finally:
            self._in_run = False


# ── live animation (kept simple) ─────────────────────────────────────────────
def animate(render_fn: Callable[[float], Any], *, fps: int = 30) -> None:
    """Run an inline animation. ``render_fn(dt)`` returns a node each frame.

    Call ``maya_py.quit()`` (or raise) to stop.
    """
    _maya.live(lambda dt: _el(render_fn(dt)), fps=fps)


__all__ = [
    "T", "b", "i", "u", "dim", "c", "color",
    "col", "row", "card", "field", "hr", "spacer", "memo",
    "center", "stack", "component", "nothing", "grow",
    "pct", "cells", "auto", "sides",
    "show", "to_string", "App", "animate",
]
