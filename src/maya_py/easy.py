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
# Friendly names → (r, g, b). Covers ANSI names plus a few nice extras.
_PALETTE: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0), "white": (235, 235, 235),
    "red": (220, 80, 80), "green": (80, 220, 120), "blue": (90, 150, 250),
    "yellow": (230, 210, 90), "magenta": (210, 110, 210), "cyan": (90, 210, 220),
    "gray": (150, 150, 150), "grey": (150, 150, 150),
    "orange": (245, 160, 60), "purple": (170, 120, 230), "pink": (240, 130, 180),
    "teal": (60, 200, 190), "lime": (160, 230, 90), "sky": (100, 180, 255),
    "gold": (255, 200, 60), "slate": (120, 135, 160),
}


def color(value: Any) -> Color:
    """Coerce almost anything into a maya Color.

    Accepts: a ``Color``, a palette name ("red", "sky"), a "#RRGGBB" / "#RGB"
    string, an (r, g, b) tuple, or an ``0xRRGGBB`` int.
    """
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _PALETTE:
            return Color.rgb(*_PALETTE[v])
        if v.startswith("#"):
            h = v[1:]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            return Color.rgb(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        raise ValueError(f"unknown color: {value!r}")
    if isinstance(value, (tuple, list)):
        return Color.rgb(int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, int):
        return Color.rgb((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
    raise TypeError(f"cannot make a color from {value!r}")


# ── T — a fluent styled string ──────────────────────────────────────────────
class T:
    """A chainable styled string. Renders to a maya text Element.

        T("Hello").bold.fg("sky")
        T("warn").fg("orange").italic
        T("x").bg("red").fg("white")

    Chaining returns a NEW T (immutable), so it's safe to reuse a base style.
    Concatenate with ``+`` (strings or other T's) to build inline runs — note
    the result keeps the LEFT operand's style for the appended plain text.
    """

    __slots__ = ("_s", "_style")

    def __init__(self, s: Any = "", style: Style | None = None):
        self._s = str(s)
        self._style = style or Style()

    # -- attribute toggles (properties, so no parens needed) ------------------
    def _with(self, st: Style) -> "T":
        return T(self._s, st)

    @property
    def bold(self) -> "T": return self._with(self._style.with_bold())
    @property
    def dim(self) -> "T": return self._with(self._style.with_dim())
    @property
    def italic(self) -> "T": return self._with(self._style.with_italic())
    @property
    def underline(self) -> "T": return self._with(self._style.with_underline())
    @property
    def strike(self) -> "T": return self._with(self._style.with_strikethrough())
    @property
    def inverse(self) -> "T": return self._with(self._style.with_inverse())

    # -- colors (methods, take an argument) -----------------------------------
    def fg(self, c: Any) -> "T": return self._with(self._style.with_fg(color(c)))
    def bg(self, c: Any) -> "T": return self._with(self._style.with_bg(color(c)))

    # -- composition ----------------------------------------------------------
    def __add__(self, other: Any) -> "T":
        text = other._s if isinstance(other, T) else str(other)
        return T(self._s + text, self._style)

    def __radd__(self, other: Any) -> "T":
        return T(str(other) + self._s, self._style)

    def __str__(self) -> str:
        return self._s

    def __repr__(self) -> str:
        return f"T({self._s!r})"

    # -- render ---------------------------------------------------------------
    def element(self) -> Element:
        return _maya.text(self._s, self._style)


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
def _box(children, *, direction, border=None, pad=None, gap=0, title=None,
         border_color=None, bg=None, align=None, justify=None,
         width=None, height=None, grow=None) -> Element:
    opts: dict[str, Any] = {"direction": direction, "gap": gap}
    if border is not None:
        opts["border"] = border if not isinstance(border, str) else _BORDERS[border.lower()]
    if pad is not None:
        opts["padding"] = pad
    if title is not None:
        opts["border_text"] = f" {title} "
        opts.setdefault("border", _maya.BorderStyle.Round)
    if border_color is not None:
        opts["border_color"] = color(border_color)
    if bg is not None:
        opts["bg"] = color(bg)
    if align is not None:
        opts["align"] = align if not isinstance(align, str) else _ALIGN[align.lower()]
    if justify is not None:
        opts["justify"] = justify if not isinstance(justify, str) else _JUSTIFY[justify.lower()]
    if width is not None:
        opts["width"] = width
    if height is not None:
        opts["height"] = height
    if grow is not None:
        opts["grow"] = grow
    return _maya.box(*_children(children), **opts)


_BORDERS = {
    "round": _maya.BorderStyle.Round, "single": _maya.BorderStyle.Single,
    "double": _maya.BorderStyle.Double, "bold": _maya.BorderStyle.Bold,
    "classic": _maya.BorderStyle.Classic, "dashed": _maya.BorderStyle.Dashed,
    "none": _maya.BorderStyle.None_,
}
_ALIGN = {"start": _maya.Align.Start, "center": _maya.Align.Center,
          "end": _maya.Align.End, "stretch": _maya.Align.Stretch}
_JUSTIFY = {"start": _maya.Justify.Start, "center": _maya.Justify.Center,
            "end": _maya.Justify.End, "between": _maya.Justify.SpaceBetween,
            "around": _maya.Justify.SpaceAround, "evenly": _maya.Justify.SpaceEvenly}


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
                 mouse: bool = False, fps: int = 0):
        self.title = title
        self.inline = inline
        self.mouse = mouse
        self.fps = fps
        self._state = _State()
        self._bindings: list[tuple[Callable[[Any], bool], Callable]] = []
        self._view: Callable[[Any], Any] | None = None
        self._any: list[Callable] = []
        self._running = True

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
        matchers = [self._matcher(k) for k in keys]

        def deco(fn):
            self._bindings.append((lambda ev: any(m(ev) for m in matchers), fn))
            return fn
        return deco

    def on_key(self, fn):
        """Decorator: call ``fn(state, event)`` for every key event."""
        self._any.append(fn)
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
        """Start the event loop. Blocks until a handler calls ``stop()``."""
        self._running = True
        _maya.run(self._event, self._render,
                  title=self.title, inline_mode=self.inline,
                  mouse=self.mouse, fps=self.fps)


# ── live animation (kept simple) ─────────────────────────────────────────────
def animate(render_fn: Callable[[float], Any], *, fps: int = 30) -> None:
    """Run an inline animation. ``render_fn(dt)`` returns a node each frame.

    Call ``maya_py.quit()`` (or raise) to stop.
    """
    _maya.live(lambda dt: _el(render_fn(dt)), fps=fps)


__all__ = [
    "T", "b", "i", "u", "dim", "c", "color",
    "col", "row", "card", "field", "hr", "spacer",
    "show", "to_string", "App", "animate",
]
