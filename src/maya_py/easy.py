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

import time as _time
from typing import Any, Callable

from . import _maya
from ._maya import Color, Element, SpecialKey, Style

# ── Named color palette ─────────────────────────────────────────────────────
# Friendly names → packed 0xRRGGBB int. Keeping these as ints (not Color
# objects) means resolving a color name is pure Python — no boundary crossing
# until the single styled_text() call that builds the element.
def _pack(r: int, g: int, b: int) -> int:
    return ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


# Cache for (r,g,b) tuple → packed int. Frames re-pass identical literal
# colour tuples; memoising the pack turns it into one dict lookup. Bounded so
# a pathological app generating unique tuples can't grow it without limit.
_TUPLE_CACHE: dict = {}


def _unknown_color_msg(value: Any) -> str:
    """A helpful error for a bad color: nearest palette name + the full list.

    Cold path only — we're about to raise, so the difflib call is free.
    """
    import difflib
    names = sorted(n for n in _PALETTE if not n.startswith("#"))
    msg = f"unknown color {value!r}"
    if isinstance(value, str):
        near = difflib.get_close_matches(value.strip().lower(), names, n=1, cutoff=0.5)
        if near:
            msg += f" — did you mean {near[0]!r}?"
    msg += (
        "\n  valid names: " + ", ".join(names)
        + "\n  or pass: '#RRGGBB' / '#RGB', an (r,g,b) tuple, a 0xRRGGBB int, "
        "or a maya.Color"
    )
    return msg


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
    """Resolve a color-ish value to a packed 0xRRGGBB int. Pure Python.

    Hot path: a palette name (``"sky"``) is by far the most common argument,
    so it's tested FIRST with a plain dict hit and no isinstance. `type() is`
    identity checks beat isinstance for the exact built-in types; resolved
    ``#hex`` strings are memoised into the palette dict so a repeated literal
    costs one dict lookup on every subsequent frame.
    """
    # Most calls pass a palette name verbatim (already lower, no whitespace).
    if type(value) is str:
        hit = _PALETTE.get(value)
        if hit is not None:
            return hit
        v = value.strip().lower()
        hit = _PALETTE.get(v)
        if hit is not None:
            return hit
        if v.startswith("#"):
            h = v[1:]
            if len(h) == 3:
                h = h[0] * 2 + h[1] * 2 + h[2] * 2
            packed = int(h, 16) & 0xFFFFFF
            _PALETTE[value] = packed   # memoise the literal for next frame
            return packed
        raise ValueError(_unknown_color_msg(value))
    if type(value) is int:
        return value & 0xFFFFFF
    if type(value) is tuple or type(value) is list:
        # Cache (r,g,b) tuples → packed int. Examples pass the SAME literal
        # tuples every frame; a dict hit replaces three int()+shift+or ops.
        if type(value) is tuple:
            hit = _TUPLE_CACHE.get(value)
            if hit is not None:
                return hit
            packed = _pack(int(value[0]), int(value[1]), int(value[2]))
            if len(_TUPLE_CACHE) < 4096:
                _TUPLE_CACHE[value] = packed
            return packed
        return _pack(int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, int):          # int subclasses (e.g. IntEnum)
        return value & 0xFFFFFF
    if isinstance(value, str):
        return _rgb_int(str(value))
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
        # None is a no-op so conditional colour reads cleanly:
        #   T(x).fg("sky" if focused else None)
        if c is None:
            return self
        # Common case: a palette name. Inline the dict hit to skip both the
        # isinstance(Color) test and the _rgb_int call frame entirely.
        if type(c) is str:
            hit = _PALETTE.get(c)
            self._fg = hit if hit is not None else _rgb_int(c)
        else:
            self._fg = c if isinstance(c, Color) else _rgb_int(c)
        self._cache = None
        return self

    def bg(self, c: Any) -> "T":
        if c is None:
            return self
        if type(c) is str:
            hit = _PALETTE.get(c)
            self._bg = hit if hit is not None else _rgb_int(c)
        else:
            self._bg = c if isinstance(c, Color) else _rgb_int(c)
        self._cache = None
        return self

    # -- conditional attributes ----------------------------------------------
    def opt(self, *, bold: bool = False, dim: bool = False, italic: bool = False,
            underline: bool = False, strike: bool = False,
            inverse: bool = False) -> "T":
        """Apply attributes conditionally — only the truthy ones take effect.

            T(text).fg("sky" if focused else None).opt(dim=done, strike=done)

        Lets a dynamic label express its style in one declarative chain instead
        of reassigning through ``if`` branches.
        """
        a = self._attrs
        if bold: a |= _BOLD
        if dim: a |= _DIM
        if italic: a |= _ITALIC
        if underline: a |= _UNDERLINE
        if strike: a |= _STRIKE
        if inverse: a |= _INVERSE
        if a != self._attrs:
            self._attrs = a
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
            # Hot path: both fg/bg are packed ints (or -1) → one styled_text
            # crossing, no isinstance, no Style assembly.
            if type(fg) is int and type(bg) is int:
                e = _maya.styled_text(self._s, fg, bg, self._attrs)
            else:
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
            self._cache = e
        return e


# ── markup-style shortcuts ───────────────────────────────────────────────────
def b(s: Any) -> T: return T(s).bold
def i(s: Any) -> T: return T(s).italic
def u(s: Any) -> T: return T(s).underline
def dim(s: Any) -> T: return T(s).dim
def c(s: Any, col: Any) -> T: return T(s).fg(col)


# ── element coercion ─────────────────────────────────────────────────────────
def _spec_element(x):
    """Build a styled-text Element from a ``(text, fg[, bg[, attrs]])`` tuple
    cell, or None if ``x`` isn't such a spec. Lets row/col mix tuple cells
    with nested Elements: when the fused path bails (a nested box is present)
    the per-child path still understands the tuple cells."""
    if (type(x) is tuple or type(x) is list) and x and type(x[0]) is str:
        ln = len(x)
        fg = _resolve_col(x[1]) if ln > 1 else -1
        bg = _resolve_col(x[2]) if ln > 2 else -1
        at = x[3] if ln > 3 else 0
        return _maya.styled_text(x[0], fg, bg, at)
    return None


def _el(x: Any) -> Element:
    """Turn str / T / Element / (text, color) tuple (or anything with
    .element()) into an Element.

    Ordered by frequency: built children are mostly ``T`` (from b()/c()/fg())
    and already-built ``Element`` boxes, so those are tested first with
    `type() is` identity (cheaper than isinstance + MRO walk).
    """
    tx = type(x)
    if tx is T:
        e = x._cache
        return e if e is not None else x.element()
    if tx is Element:
        return x
    if tx is str:
        return _maya.text(x)
    if tx is tuple or tx is list:
        e = _spec_element(x)
        if e is not None:
            return e
    # slower fallbacks (subclasses, None, duck-typed .element())
    if isinstance(x, Element):
        return x
    if isinstance(x, T):
        return x.element()
    if isinstance(x, str):
        return _maya.text(x)
    if x is None:
        return _maya.blank()
    el = getattr(x, "element", None)
    if callable(el):
        built = el()
        if isinstance(built, Element):
            return built
    raise TypeError(f"not a renderable child: {x!r}")


def _children(items) -> list[Element]:
    # Hot path inlined: most children are T or already-built Element.
    out = []
    ap = out.append
    styled = _maya.styled_text
    for x in items:
        tx = type(x)
        if tx is T:
            e = x._cache
            if e is None:
                fg, bg = x._fg, x._bg
                # Inline the common int/int build — skip the element() frame.
                if type(fg) is int and type(bg) is int:
                    e = styled(x._s, fg, bg, x._attrs)
                    x._cache = e
                else:
                    e = x.element()
            ap(e)
        elif tx is Element:
            ap(x)
        elif tx is str:
            ap(_maya.text(x))
        else:
            ap(_el(x))
    return out


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


# opts that box_simple handles directly; anything else forces the full path.
_SIMPLE_OPTS = frozenset(("gap", "grow"))
_DIR_ROW = _maya.FlexDirection.Row


def _box(children, *, direction, **opts) -> Element:
    # FAST PATH: a plain row/col with at most gap/grow (the vast majority of
    # boxes). Skip the kwargs dict + the C++ side's ~25 opts.contains() probes
    # by calling box_simple with a pre-built child list and scalars only.
    if not opts or opts.keys() <= _SIMPLE_OPTS:
        gap = opts.get("gap", -1)
        grow = opts.get("grow", -1.0)
        return _maya.box_simple(
            _children(children),
            0 if direction == _DIR_ROW else 1,
            gap if gap is not None else -1,
            float(grow) if grow is not None else -1.0,
        )

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


def _stack(children, direction, g, gr):
    # Fused fast path: build the flat [s,fg,bg,a,...] list in ONE pass and
    # cross once via styled_text_row — no per-cell Element, no per-cell
    # boundary crossing. A child qualifies for the fast path when it is:
    #   • a tuple/list spec  (text, fg[, bg[, attrs]])   ← zero allocations
    #   • a fresh T with plain-int fg/bg                 ← throwaway T
    #   • a bare str                                     ← unstyled cell
    # The moment ANY child is a built Element / nested box / component, we
    # fall back to the general per-child path (box_simple) — those can't be
    # flattened into a text row.
    flat = []
    ext = flat.extend
    n = 0
    for x in children:
        tx = type(x)
        if (tx is tuple or tx is list) and x and type(x[0]) is str:
            ln = len(x)
            fg = _resolve_col(x[1]) if ln > 1 else -1
            bg = _resolve_col(x[2]) if ln > 2 else -1
            at = x[3] if ln > 3 else 0
            ext((x[0], fg, bg, at))
        elif tx is T:
            fg = x._fg
            bg = x._bg
            if type(fg) is not int or type(bg) is not int:
                break          # Color-object T → slow path
            ext((x._s, fg, bg, x._attrs))
        elif tx is str:
            ext((x, -1, -1, 0))
        else:
            break              # Element / box / component → slow path
        n += 1
    else:
        # Loop completed without `break` → every child was flattenable.
        if n:
            return _maya.styled_text_row(flat, n, direction, g, gr)
    return _maya.box_simple(_children(children), direction, g, gr)


def col(*children, **opts) -> Element:
    """Vertical stack. Children may be strings, T's, or Elements."""
    if not opts:
        return _stack(children, 1, -1, -1.0)
    if opts.keys() <= _SIMPLE_OPTS:
        gap = opts.get("gap", -1)
        grow = opts.get("grow", -1.0)
        g = gap if gap is not None else -1
        gr = float(grow) if grow is not None else -1.0
        return _stack(children, 1, g, gr)
    return _box(children, direction=_maya.FlexDirection.Column, **opts)


def row(*children, **opts) -> Element:
    """Horizontal stack."""
    if not opts:
        return _stack(children, 0, -1, -1.0)
    if opts.keys() <= _SIMPLE_OPTS:
        gap = opts.get("gap", -1)
        grow = opts.get("grow", -1.0)
        g = gap if gap is not None else -1
        gr = float(grow) if grow is not None else -1.0
        return _stack(children, 0, g, gr)
    return _box(children, direction=_maya.FlexDirection.Row, **opts)


def _resolve_col(c) -> int:
    # Color spec -> packed int (or -1 for unset). Mirrors T.fg's fast path.
    if c is None:
        return -1
    tc = type(c)
    if tc is int:
        return c
    if tc is str:
        hit = _PALETTE.get(c)
        return hit if hit is not None else _rgb_int(c)
    if tc is tuple:
        hit = _TUPLE_CACHE.get(c)
        if hit is not None:
            return hit
        packed = _pack(int(c[0]), int(c[1]), int(c[2]))
        if len(_TUPLE_CACHE) < 4096:
            _TUPLE_CACHE[c] = packed
        return packed
    return _rgb_int(c)


def trow(*specs, gap=-1, grow=-1.0) -> Element:
    """Alias for ``row`` kept for back-compat — ``row`` now takes the same
    ``(text, fg[, bg[, attrs]])`` tuple-cell specs at identical speed, so new
    code can just use ``row(...)``."""
    return _stack(specs, 0, gap, float(grow))


def tcol(*specs, gap=-1, grow=-1.0) -> Element:
    """Alias for ``col`` kept for back-compat (see :func:`trow`)."""
    return _stack(specs, 1, gap, float(grow))


# Attribute bitmask constants for trow/tcol specs (match make_styled_text).
BOLD = _BOLD
DIM = _DIM
ITALIC = _ITALIC
UNDERLINE = _UNDERLINE
STRIKE = _STRIKE
INVERSE = _INVERSE


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


def when(cond: Any, then: Any, else_: Any = None) -> Any:
    """Conditional element — ``then`` when ``cond`` is truthy, else ``else_``
    (or :func:`nothing` when omitted). Keeps conditionals inside the view tree
    instead of breaking out into ``if`` statements:

        col(
            header(s),
            when(s.error, callout(s.error, kind="error")),
            when(s.loading, spinner("loading…"), else_=results(s)),
        )

    ``then`` / ``else_`` may be elements or zero-arg callables; a callable for
    the un-taken branch is never invoked, so wrap an expensive branch in a
    ``lambda`` to skip building it.
    """
    branch = then if cond else else_
    if branch is None:
        return nothing()
    return branch() if callable(branch) else branch


def grow(child: Any, factor: float = 1.0, **opts) -> Element:
    """Wrap a child so it expands to fill available space along the main axis.

        row(sidebar, grow(main_content))
    """
    return _box([child], direction=_maya.FlexDirection.Column, grow=factor, **opts)


def For(items, render: Callable, *, into=col, empty: Any = None, **opts) -> Element:
    """Declarative list rendering — map ``items`` through ``render`` into a box.

    Replaces the ``col(*[row(...) for x in items])`` comprehension with a name
    that reads like the JSX ``map`` / SwiftUI ``ForEach`` it is::

        For(s.todos, lambda t: row(check(t.done), t.text))
        For(s.rows, render_row, gap=1)              # extra opts go to the box
        For(s.items, item_view, empty="(nothing here)")

    ``render`` is called as ``render(item)`` or, if it takes two parameters,
    ``render(index, item)`` — so you get the enumerate for free::

        For(s.items, lambda i, x: row(T(f"{i+1}.").dim, x.name))

    ``into`` is the container (``col`` by default, pass ``row`` for horizontal).
    ``empty`` is shown when ``items`` is empty (a node or callable; defaults to
    a zero-row :func:`nothing`). All other keyword opts pass to the container.
    """
    seq = list(items)
    if not seq:
        if empty is None:
            return nothing()
        return into(empty() if callable(empty) else empty, **opts)
    # Pass the index too when render accepts two positional params.
    two = False
    try:
        two = _arity2(render)
    except (TypeError, ValueError):
        two = False
    if two:
        kids = [render(i, x) for i, x in enumerate(seq)]
    else:
        kids = [render(x) for x in seq]
    return into(*kids, **opts)


def _arity2(fn) -> bool:
    """True if ``fn`` takes (at least) two required positional params — used so
    ``For`` can pass ``(index, item)`` to two-param renderers automatically.
    """
    import inspect
    target = fn
    if not (inspect.isfunction(target) or inspect.ismethod(target)):
        call = getattr(type(target), "__call__", None)
        if call is None:
            return False
        target = call
    try:
        params = inspect.signature(target).parameters.values()
    except (TypeError, ValueError):
        return False
    # signature() already drops a bound self/cls, so just count required
    # positional params.
    required = [
        p for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        and p.default is p.empty
    ]
    return len(required) >= 2


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
    # Fast path: a plain string/number value (the common case) builds the
    # whole row in one crossing via tuple-cell specs — no per-cell T objects.
    tv = type(value)
    if tv is str or tv is int or tv is float:
        return row((label + ":", label_color),
                   (value if tv is str else str(value), value_color),
                   gap=1)
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
    "tab": SpecialKey.Tab, "backtab": SpecialKey.BackTab, "shifttab": SpecialKey.BackTab,
    "space": None,  # handled as ' '
    "backspace": SpecialKey.Backspace, "delete": SpecialKey.Delete, "del": SpecialKey.Delete,
    "insert": SpecialKey.Insert, "ins": SpecialKey.Insert,
    "home": SpecialKey.Home, "end": SpecialKey.End,
    "pageup": SpecialKey.PageUp, "pagedown": SpecialKey.PageDown,
    "pgup": SpecialKey.PageUp, "pgdn": SpecialKey.PageDown, "pgdown": SpecialKey.PageDown,
    "f1": SpecialKey.F1, "f2": SpecialKey.F2, "f3": SpecialKey.F3, "f4": SpecialKey.F4,
    "f5": SpecialKey.F5, "f6": SpecialKey.F6, "f7": SpecialKey.F7, "f8": SpecialKey.F8,
    "f9": SpecialKey.F9, "f10": SpecialKey.F10, "f11": SpecialKey.F11, "f12": SpecialKey.F12,
}

# friendly mouse-button names → MouseButton enum
_MOUSE_BTN = {
    "left": _maya.MouseButton.Left,
    "right": _maya.MouseButton.Right,
    "middle": _maya.MouseButton.Middle,
}


def _unknown_key_msg(spec: str, base: str) -> str:
    """A helpful error for a bad key spec: nearest named key + what's valid.

    Cold path only — we're about to raise.
    """
    import difflib
    names = sorted(_SPECIAL)
    msg = f"unknown key spec {spec!r}"
    near = difflib.get_close_matches(base, names, n=1, cutoff=0.5)
    if near:
        msg += f" — did you mean {near[0]!r}?"
    msg += (
        "\n  a key is a single char ('q', '+', '?'), a named key ("
        + ", ".join(names)
        + "), or those with a ctrl+/alt+/shift+ prefix (e.g. 'ctrl+s', 'alt+x')."
    )
    return msg


def text_input(placeholder: str = "", *, password: bool = False,
               multiline: bool = False, value: str = "",
               bind: "tuple | None" = None):
    """An interactive text field — a real maya ``Input`` widget hosted in
    Python (cursor, UTF-8 editing, history, password masking). Register it
    with ``app.focus(...)`` so it receives keystrokes, read ``.value``, and
    drop it straight into a view.

        name = text_input("your name…")
        app.focus(name)

        @app.view
        def view(s): return col("Name:", name, f"hello {name.value}")

    ``name.value`` (read/write), ``name.clear()``, ``name.on_submit(fn)`` (Enter),
    ``name.on_change(fn)``.

    **Two-way binding.** Pass ``bind=(state, "field")`` and the widget mirrors
    that attribute both ways: the field seeds the input's initial text, and
    every keystroke writes back to ``state.field`` — so the view reads
    ``s.field`` directly and never touches ``.value``::

        app = App("form", name="")
        name = text_input("your name…", bind=(app.s, "name"))
        app.focus(name)
        @app.view
        def view(s): return col("Name:", name, f"hello {s.name}")
    """
    inp = _maya._widgets.Input(password=password, multiline=multiline)
    if placeholder:
        inp.set_placeholder(placeholder)
    if bind is not None:
        obj, attr = bind
        seed = getattr(obj, attr, value)
        if seed:
            inp.value = str(seed)
        # Mirror every edit back onto the bound attribute.
        inp.on_change(lambda text, _o=obj, _a=attr: setattr(_o, _a, text))
    elif value:
        inp.value = str(value)
    return inp


def textarea(placeholder: str = ""):
    """A multi-line :func:`text_input` (Enter inserts a newline; Ctrl/Shift-Enter
    submits)."""
    return text_input(placeholder, multiline=True)


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
                 mouse: bool = False, fps: int = 0, quit_on_ctrl_c: bool = True,
                 quit_keys: tuple[str, ...] = (), model: Any = None,
                 keys: "dict[str, Callable] | None" = None, **state):
        self.title = title
        self.inline = inline
        self.mouse = mouse
        self.fps = fps
        self.quit_on_ctrl_c = quit_on_ctrl_c
        self.quit_keys = tuple(quit_keys)
        # State is either your own object (`model=Todo()`) — handlers mutate it
        # and call its methods — or a plain attribute bag seeded from **kwargs.
        self._state = model if model is not None else _State()
        self._bindings: list[tuple[Callable[[Any], bool], Callable]] = []
        self._view: Callable[[Any], Any] | None = None
        self._any: list[Callable] = []
        self._frames: list[Callable] = []               # per-frame tick handlers
        self._last_frame_t: float | None = None
        self._clicks: list[tuple[Any, Callable]] = []   # (button|None, fn)
        self._scrolls: list[Callable] = []
        self._mouse_any: list[Callable] = []
        self._pastes: list[Callable] = []
        self._resizes: list[Callable] = []
        self._focusable: list = []                      # widgets receiving keys
        self._focus_idx: int = -1
        self._running = True
        self._ctrl_c_bound = False  # set if the user binds ctrl+c themselves
        # Live mouse-capture state. maya enables capture at startup when
        # `self.mouse` is set; set_mouse() flips it at runtime.
        self.mouse_active = mouse
        # Initial state passed straight to the constructor: App("counter", n=0).
        # (Ignored when a model is supplied — the model owns its own fields.)
        if state and model is None:
            self._state.__dict__.update(state)
        # quit_keys=("q","esc") auto-binds those keys to stop() — no need to
        # hand-write the quit handler every app.
        for k in self.quit_keys:
            m = self._matcher(k)
            self._bindings.append((lambda ev, m=m: m(ev),
                                   lambda s: self.stop()))
        # Declarative key → action map, an alternative to @app.on decorators:
        #   App("todo", keys={"up": lambda s: s.move(-1), "space": lambda s: s.toggle()})
        if keys:
            for k, fn in keys.items():
                m = self._matcher(k)
                self._bindings.append((lambda ev, m=m: m(ev), fn))

    # -- state ---------------------------------------------------------------
    def state(self, **kw) -> _State:
        """Seed initial state. Returns the state object."""
        self._state.__dict__.update(kw)
        return self._state

    @property
    def s(self) -> _State:
        return self._state

    def derive(self, fn):
        """Decorator: expose a **computed** field on the state object.

        ``fn(state)`` is installed as a read-only property named after the
        function, so the view reads it like any other field — no recompute
        boilerplate, no stale cache to invalidate (it's recomputed on access,
        every frame)::

            app = App("cart", items=[2.0, 3.5])

            @app.derive
            def total(s): return sum(s.items)

            @app.view
            def view(s): return card(f"Total: ${s.total:.2f}")

        Works whether state is the default attribute bag or your own ``model=``
        object (the property is attached to the state object's class). This is
        SwiftUI's computed ``var`` / Solid's derived signal, spelled in one
        decorator.
        """
        name = fn.__name__
        state = self._state
        cls = type(state)
        if cls is _State:
            # The shared attribute-bag class — give this app its own subclass so
            # one app's derived fields don't leak onto another's state.
            cls = type("_State", (_State,), {})
            state.__class__ = cls
        setattr(cls, name, property(lambda self, _f=fn: _f(self)))
        return fn

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

    def on_frame(self, fn):
        """Decorator: call ``fn(state, dt)`` once per frame, BEFORE the view
        renders, where ``dt`` is seconds since the previous frame. Put your
        animation / simulation step here so ``view(state)`` stays a pure
        function of state.

            @app.on_frame
            def tick(s, dt): s.t += dt

        Registering a frame handler turns on continuous redraw: if ``fps`` was
        left at 0 (event-driven), it defaults to 30.
        """
        self._frames.append(fn)
        if self.fps <= 0:
            self.fps = 30
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

    def set_mouse(self, on: bool) -> None:
        """Turn terminal mouse reporting on/off **while the app is running**.

        Call from a handler. Disabling hands the scroll wheel back to the
        terminal (native scrollback works again) at the cost of in-app
        clicks; enabling re-captures them. Mouse capture and native terminal
        scroll are mutually exclusive — this is the switch between them.

            @app.on("ctrl+m")
            def toggle(s): app.set_mouse(not app.mouse_active)
        """
        # Route through maya's runtime toggle so it stays in sync with the
        # terminal-restore on exit (rather than writing the escape ourselves).
        _maya.set_mouse(bool(on))
        self.mouse_active = on

    def on_paste(self, fn):
        """Decorator: call ``fn(state, text)`` on a bracketed paste. (A focused
        text widget also receives the paste automatically.)"""
        self._pastes.append(fn)
        return fn

    def on_resize(self, fn):
        """Decorator: call ``fn(state, cols, rows)`` when the terminal resizes."""
        self._resizes.append(fn)
        return fn

    # -- focus / interactive widgets -----------------------------------------
    def focus(self, *widgets):
        """Register interactive widgets (``text_input`` / ``textarea`` / any
        object with ``handle(event)`` + ``focused``) to receive keystrokes.

        The focused widget gets each key first; Tab / Shift-Tab cycle focus;
        keys a widget doesn't consume fall through to your ``@app.on`` bindings.
        Returns the first widget for convenience.
        """
        self._focusable = list(widgets)
        self._focus_idx = 0 if widgets else -1
        for j, wdg in enumerate(self._focusable):
            if not (hasattr(wdg, "handle") and hasattr(wdg, "focused")):
                raise TypeError(
                    f"focus() expects interactive widgets (text_input()/textarea() "
                    f"or any object with .handle(event) + .focused), but argument "
                    f"{j} is {type(wdg).__name__} ({wdg!r:.40}). Did you pass a "
                    "string or an element instead of a widget?"
                )
            wdg.focused = (j == 0)
        return widgets[0] if widgets else None

    def _focused_widget(self):
        if 0 <= self._focus_idx < len(self._focusable):
            return self._focusable[self._focus_idx]
        return None

    def _cycle_focus(self, step: int) -> None:
        n = len(self._focusable)
        if n == 0:
            return
        cur = self._focused_widget()
        if cur is not None:
            cur.focused = False
        self._focus_idx = (self._focus_idx + step) % n
        self._focusable[self._focus_idx].focused = True

    def view(self, fn):
        """Decorator: register the view function ``fn(state) -> node``."""
        self._view = fn
        return fn

    def stop(self) -> None:
        """Request the app to quit."""
        self._running = False

    # -- internals -----------------------------------------------------------
    def _matcher(self, k: str) -> Callable[[Any], bool]:
        """Compile a key spec into a predicate, or raise on a bad spec.

        Accepts modifier prefixes (``ctrl+``/``alt+``/``shift+``, any order)
        followed by a single character or a named key (``up``, ``enter``, ``f5``,
        ``space``, …). A typo or unsupported combo raises a helpful error — the
        old behavior silently built a binding that never fired.
        """
        if not isinstance(k, str) or k == "":
            raise ValueError(f"key spec must be a non-empty string, got {k!r}")

        # Split modifier prefixes off the front (but keep a lone '+' as a key).
        ctrl = alt = shift = False
        rest = k
        while True:
            low = rest.lower()
            if low.startswith("ctrl+") and len(rest) > 5:
                ctrl, rest = True, rest[5:]
            elif low.startswith("alt+") and len(rest) > 4:
                alt, rest = True, rest[4:]
            elif low.startswith("shift+") and len(rest) > 6:
                shift, rest = True, rest[6:]
            elif (low.startswith("super+") or low.startswith("cmd+")) and "+" in rest:
                raise ValueError(
                    f"key spec {k!r}: the super/cmd modifier isn't matchable from "
                    "Python yet — use ctrl/alt, or bind the bare key."
                )
            else:
                break

        base = rest.lower()

        # shift+tab is the one meaningful shift+special combo — it's BackTab.
        if shift and base == "tab":
            return lambda ev: _maya.key_special(ev, SpecialKey.BackTab)

        # shift+<letter> can't be told apart from the letter by the predicates
        # (terminals deliver an uppercase char), so map it to the upper-case key.
        if shift and len(rest) == 1 and rest.isalpha():
            shift = False
            rest = rest.upper()
            base = rest.lower()

        # A named special key.
        if base in _SPECIAL:
            sk = _SPECIAL[base]
            if sk is None:  # "space"
                if ctrl:
                    return lambda ev: _maya.ctrl(ev, " ")
                return lambda ev: _maya.key(ev, " ")
            if alt or shift:
                raise ValueError(
                    f"key spec {k!r}: modifiers on the named key {base!r} aren't "
                    "matchable — bind the plain key (e.g. 'up', 'enter', 'f5')."
                )
            return lambda ev: _maya.key_special(ev, sk)

        # A single character, optionally with ctrl/alt.
        if len(rest) == 1:
            ch = rest
            if ctrl:
                return lambda ev: _maya.ctrl(ev, ch.lower())
            if alt:
                return lambda ev: _maya.alt(ev, ch.lower())
            return lambda ev: _maya.key(ev, ch)

        # Anything else is a typo / unsupported spec — fail loudly with a hint.
        raise ValueError(_unknown_key_msg(k, base))

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

        # Paste: feed the focused widget, then notify on_paste handlers.
        paste = _maya.pasted(ev)
        if paste is not None:
            cur = self._focused_widget()
            if cur is not None:
                cur.handle(ev)
            for fn in self._pastes:
                fn(self._state, paste)
            return self._running

        # Resize: notify on_resize handlers.
        size = _maya.resize_size(ev)
        if size is not None:
            for fn in self._resizes:
                fn(self._state, size[0], size[1])
            return self._running

        # Focused interactive widget gets keys first. Tab / Shift-Tab cycle
        # focus; anything the widget doesn't consume falls through to bindings.
        if self._focusable:
            if _maya.key_special(ev, SpecialKey.Tab):
                self._cycle_focus(+1)
                return self._running
            if _maya.key_special(ev, SpecialKey.BackTab):
                self._cycle_focus(-1)
                return self._running
            cur = self._focused_widget()
            if cur is not None and cur.handle(ev):
                return self._running

        for fn in self._any:
            fn(self._state, ev)
        for match, fn in self._bindings:
            if match(ev):
                fn(self._state)
                break
        return self._running

    def _render(self) -> Element:
        if self._frames:
            now = _time.monotonic()
            dt = 0.0 if self._last_frame_t is None else now - self._last_frame_t
            self._last_frame_t = now
            for fn in self._frames:
                fn(self._state, dt)
        if self._view is None:
            return _maya.text("(no view registered)")
        return _view_element(self._view, self._state)

    def run(self) -> None:
        """Start the event loop. Blocks until a handler calls ``stop()``
        (or the user presses Ctrl-C, unless ``quit_on_ctrl_c=False``)."""
        if getattr(self, "_in_run", False):
            raise RuntimeError("App.run() is already running (cannot nest)")
        self._in_run = True
        self._running = True
        self.mouse_active = self.mouse   # reflect what maya enables at startup
        try:
            _maya.run(self._event, self._render,
                      title=self.title, inline_mode=self.inline,
                      mouse=self.mouse, fps=self.fps)
        finally:
            self._in_run = False

    # -- headless testing ----------------------------------------------------
    def test(self, *, width: int = 80) -> "Pilot":
        """Drive this app headlessly, with no terminal. Returns a :class:`Pilot`
        that feeds synthetic events through the SAME ``_event`` / ``_render``
        path the live loop uses, so tests exercise real handler + view logic.

            app = make_app()
            pilot = app.test()
            pilot.press("+", "+", "+")
            assert app.s.n == 3
            assert "Count: 3" in pilot.render()

        Use as a context manager to mirror startup/teardown::

            with app.test() as p:
                p.press("q")
                assert not p.running
        """
        return Pilot(self, width=width)


class Pilot:
    """A headless driver for an :class:`App` — the in-process test harness.

    No PTY, no real terminal: events are synthesized with the native
    ``make_*`` factories and pushed straight through ``App._event``; frames
    are rendered with :func:`to_string`. Everything an app handler can see
    (key/mouse/paste/resize, focus, frame ticks) is reachable, deterministically.

        pilot = app.test(width=60)
        pilot.press("up", "space")     # arrow then toggle
        pilot.type("hello")            # types each character
        pilot.click(10, 4)             # left-click at col,row
        pilot.scroll("down")
        pilot.paste("clip text")
        pilot.resize(120, 40)
        pilot.tick(0.5)                # advance frame handlers by dt seconds
        frame = pilot.render()         # current view as a plain string
        assert pilot.running           # False once a handler called stop()
    """

    def __init__(self, app: "App", *, width: int = 80):
        self.app = app
        self.width = width
        # Mirror App.run() startup so handlers see the same initial flags.
        app._running = True
        app.mouse_active = app.mouse
        app._last_frame_t = None

    # -- lifecycle -----------------------------------------------------------
    @property
    def running(self) -> bool:
        """False once the app requested quit (stop() / quit key / Ctrl-C)."""
        return app_running(self.app)

    def __enter__(self) -> "Pilot":
        return self

    def __exit__(self, *exc) -> None:
        return None

    # -- feeding events ------------------------------------------------------
    def send(self, ev) -> "Pilot":
        """Feed one raw maya Event (from a ``maya.make_*`` factory)."""
        self.app._event(ev)
        return self

    def press(self, *keys: str, ctrl: bool = False, alt: bool = False,
             shift: bool = False) -> "Pilot":
        """Press one or more keys. Names ("up", "enter", "esc", "tab", "space")
        or single chars ("a", "+"). Modifiers apply to every key in the call."""
        for k in keys:
            self.app._event(_maya.make_key(k, ctrl=ctrl, alt=alt, shift=shift))
        return self

    def type(self, text: str) -> "Pilot":  # noqa: A003
        """Type a string, one character event at a time (text-input friendly)."""
        for ch in text:
            self.app._event(_maya.make_key(ch))
        return self

    def click(self, col: int, row: int, button: str = "left") -> "Pilot":
        """Left/right/middle click (press then release) at a 1-based cell."""
        self.app._event(_maya.make_mouse(col, row, button, "press"))
        self.app._event(_maya.make_mouse(col, row, button, "release"))
        return self

    def scroll(self, direction: str = "down", col: int = 1, row: int = 1) -> "Pilot":
        """Scroll the wheel "up" or "down" at a cell."""
        self.app._event(_maya.make_scroll(direction, col, row))
        return self

    def paste(self, text: str) -> "Pilot":
        """Deliver a bracketed paste."""
        self.app._event(_maya.make_paste(text))
        return self

    def resize(self, cols: int, rows: int) -> "Pilot":
        """Deliver a terminal-resize event (and adopt ``cols`` as render width)."""
        self.width = cols
        self.app._event(_maya.make_resize(cols, rows))
        return self

    def tick(self, dt: float = 1.0 / 30) -> "Pilot":
        """Advance frame handlers (``@app.on_frame``) by ``dt`` seconds,
        deterministically — no wall-clock dependency."""
        for fn in self.app._frames:
            fn(self.app._state, dt)
        return self

    # -- observing -----------------------------------------------------------
    def render(self, width: int | None = None) -> str:
        """Render the current view to a plain string (one text line per row,
        trailing blanks trimmed). The thing to assert against."""
        w = self.width if width is None else width
        el = _view_element(self.app._view, self.app._state) if self.app._view \
            else _maya.text("(no view registered)")
        return _maya.render_to_string(el, w)

    @property
    def state(self):
        """The app's state object (same one handlers mutate)."""
        return self.app._state


def app_running(app: "App") -> bool:
    return getattr(app, "_running", True)


def _view_element(view_fn: Callable, state: Any) -> Element:
    """Call a view function and coerce its result, with an error that names the
    real culprit (the view) instead of a generic 'not a renderable child'."""
    result = view_fn(state)
    if result is None:
        raise TypeError(
            f"view function {getattr(view_fn, '__name__', 'view')!r} returned "
            "None — it must return a node (a string, a T, or a maya element "
            "like col(...)/card(...)). Did you forget a `return`?"
        )
    try:
        return _el(result)
    except TypeError as exc:
        raise TypeError(
            f"view function {getattr(view_fn, '__name__', 'view')!r} returned "
            f"{type(result).__name__} ({result!r:.60}), which is not renderable. "
            "Return a string, a T, or a maya element (col/row/card/box/text/...)."
        ) from exc


# ── color + formatting utilities ─────────────────────────────────────────────
def gradient_at(stops, t: float) -> tuple[int, int, int]:
    """Interpolate a color across evenly-spaced ``stops`` at position ``t``.

    ``stops`` is a list of (r, g, b) tuples; ``t`` is clamped to [0, 1]. Returns
    an (r, g, b) int tuple — pass it straight to ``.fg()`` / ``.bg()`` or
    ``halfblock``.

        WARM = [(20, 20, 60), (200, 60, 40), (255, 220, 120)]
        T("x").fg(gradient_at(WARM, heat))
    """
    n = len(stops)
    if n == 0:
        return (0, 0, 0)
    if n == 1:
        return tuple(stops[0])
    t = 0.0 if t < 0.0 else (0.999999 if t > 1.0 else t)
    seg = t * (n - 1)
    i = int(seg)
    f = seg - i
    a, b2 = stops[i], stops[i + 1]
    return tuple(int(a[k] + (b2[k] - a[k]) * f) for k in range(3))


def fmt_duration(seconds: float, *, centis: bool = False) -> str:
    """Format a duration as ``M:SS`` (or ``H:MM:SS`` past an hour).

    ``centis=True`` appends hundredths: ``M:SS.CC`` — for stopwatches.

        fmt_duration(83)            # "1:23"
        fmt_duration(3725)          # "1:02:05"
        fmt_duration(83.4, centis=True)  # "1:23.40"
    """
    seconds = max(0.0, float(seconds))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        out = f"{h}:{m:02d}:{s:02d}"
    else:
        out = f"{m}:{s:02d}"
    if centis:
        out += f".{int((seconds - total) * 100):02d}"
    return out


# ── live animation (kept simple) ─────────────────────────────────────────────
def animate(render_fn: Callable[[float], Any], *, fps: int = 30) -> None:
    """Run an inline animation. ``render_fn(dt)`` returns a node each frame.

    Call ``maya_py.quit()`` (or raise) to stop.
    """
    _maya.live(lambda dt: _el(render_fn(dt)), fps=fps)


# ── numeric DSL — the maths every live/visual app reinvents ──────────────────
# 16 of the example apps defined their own `clamp`; many also rolled `lerp`,
# `remap`, easing, sparkline strings. These are that vocabulary, once, fast,
# and consistent. All are plain functions (no allocation, no boundary cross).
import math as _math


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Constrain ``x`` to ``[lo, hi]`` (defaults to the unit interval)."""
    return lo if x < lo else hi if x > hi else x


def saturate(x: float) -> float:
    """Clamp to ``[0, 1]`` — the shader ``saturate``."""
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from ``a`` to ``b`` by ``t`` (``t`` unclamped)."""
    return a + (b - a) * t


def norm(x: float, lo: float, hi: float) -> float:
    """Inverse-lerp: where ``x`` falls in ``[lo, hi]`` as a 0..1 fraction.
    Returns 0 when the range is degenerate."""
    d = hi - lo
    return 0.0 if d == 0 else (x - lo) / d


def remap(x: float, a: float, b: float, c: float, d: float) -> float:
    """Map ``x`` from the range ``[a, b]`` into ``[c, d]`` (linear, unclamped).

        remap(temp, 0, 100, 0, 1)        # 0..100 → 0..1
    """
    if b == a:
        return c
    return c + (d - c) * ((x - a) / (b - a))


def remapc(x: float, a: float, b: float, c: float, d: float) -> float:
    """:func:`remap`, clamped to the output range ``[c, d]``."""
    lo, hi = (c, d) if c <= d else (d, c)
    return clamp(remap(x, a, b, c, d), lo, hi)


def smoothstep(t: float) -> float:
    """Hermite ease at the edges of ``[0, 1]`` (the classic ``3t²-2t³``)."""
    t = saturate(t)
    return t * t * (3.0 - 2.0 * t)


def wrap(x: float, hi: float, lo: float = 0.0) -> float:
    """Wrap ``x`` into ``[lo, hi)`` (toroidal) — angles, ring buffers, scroll."""
    span = hi - lo
    if span <= 0:
        return lo
    return lo + (x - lo) % span


def sign(x: float) -> int:
    """-1 / 0 / +1."""
    return (x > 0) - (x < 0)


def approach(cur: float, target: float, rate: float) -> float:
    """Move ``cur`` toward ``target`` by at most ``rate`` (frame-rate-free
    easing toward a goal without overshoot)."""
    if cur < target:
        return min(cur + rate, target)
    return max(cur - rate, target)


_TAU = 6.283185307179586


def oscillate(t: float, lo: float = 0.0, hi: float = 1.0,
              period: float = 1.0) -> float:
    """A smooth sine oscillation between ``lo`` and ``hi`` with the given
    ``period`` (seconds) — breathing UIs, pulsing cursors, idle bob."""
    phase = _math.sin(t / period * _TAU)
    return lo + (hi - lo) * (0.5 + 0.5 * phase)


def pulse(t: float, period: float = 1.0, duty: float = 0.5) -> bool:
    """A square wave: True for the first ``duty`` fraction of each ``period``
    — blink a cursor, flash an alert."""
    return (t % period) < period * duty


_EASES = {
    "linear": lambda t: t,
    "in": lambda t: t * t,
    "out": lambda t: 1 - (1 - t) * (1 - t),
    "inout": lambda t: 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,
    "smooth": smoothstep,
    "cubic": lambda t: t * t * t,
    "expo": lambda t: 0.0 if t <= 0 else 2 ** (10 * (t - 1)),
    "bounce": lambda t: 1 - abs(_math.cos(t * _math.pi * 1.5)) * (1 - t),
}


def ease(t: float, kind: str = "smooth") -> float:
    """Apply a named easing curve to ``t`` in ``[0, 1]``: linear / in / out /
    inout / smooth / cubic / expo / bounce."""
    fn = _EASES.get(kind)
    if fn is None:
        raise ValueError(f"unknown ease {kind!r}; valid: {', '.join(_EASES)}")
    return fn(saturate(t))


# ── colour DSL — beyond rgb_lerp ─────────────────────────────────────────────
def hsv(h: float, s: float = 1.0, v: float = 1.0) -> tuple[int, int, int]:
    """HSV → an ``(r, g, b)`` 0-255 tuple. ``h`` in turns (0..1, wraps), ``s``
    and ``v`` in 0..1. The ergonomic way to sweep hues::

        T("x").fg(hsv(t % 1.0))          # rainbow cycling on t
    """
    h = h % 1.0
    s = saturate(s)
    v = saturate(v)
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    u = v * (1 - (1 - f) * s)
    r, g, b = ((v, u, p), (q, v, p), (p, v, u),
               (p, q, v), (u, p, v), (v, p, q))[i % 6]
    return (int(r * 255), int(g * 255), int(b * 255))


def mix(a: Any, b: Any, t: float) -> tuple[int, int, int]:
    """Blend two colours (any spec) at ``t`` → an ``(r, g, b)`` tuple.
    Like :func:`rgb_lerp` but lives in the core DSL."""
    pa, pb = _rgb_int(a), _rgb_int(b)
    t = saturate(t)
    ar, ag, ab = (pa >> 16) & 0xFF, (pa >> 8) & 0xFF, pa & 0xFF
    br, bg, bb = (pb >> 16) & 0xFF, (pb >> 8) & 0xFF, pb & 0xFF
    return (int(ar + (br - ar) * t), int(ag + (bg - ag) * t),
            int(ab + (bb - ab) * t))


def lighten(c: Any, amount: float = 0.2) -> tuple[int, int, int]:
    """Blend ``c`` toward white by ``amount`` (0..1)."""
    return mix(c, (255, 255, 255), amount)


def darken(c: Any, amount: float = 0.2) -> tuple[int, int, int]:
    """Blend ``c`` toward black by ``amount`` (0..1)."""
    return mix(c, (0, 0, 0), amount)


def alpha(fg: Any, bg: Any, a: float) -> tuple[int, int, int]:
    """Composite ``fg`` over ``bg`` at opacity ``a`` (0..1) — fake translucency
    for a terminal that has no real alpha."""
    return mix(bg, fg, saturate(a))


# ── data → text helpers ──────────────────────────────────────────────────────
_SPARK = "▁▂▃▄▅▆▇█"


def spark(data: Sequence[float], width: int = 0, *,
         lo: float | None = None, hi: float | None = None) -> str:
    """A unicode sparkline STRING from a sequence of numbers — the one every
    dashboard reimplements. ``width`` 0 means "one cell per sample"; a smaller
    width subsamples. ``lo`` / ``hi`` pin the value axis (else auto-scale).

        T(spark(cpu_history, 20)).fg("lime")
    """
    n = len(data)
    if n == 0:
        return ""
    mn = min(data) if lo is None else lo
    mx = max(data) if hi is None else hi
    rng = mx - mn
    if rng < 1e-9:
        rng = 1.0
    w = n if width <= 0 else width
    step = max(1, n // w) if w < n else 1
    cnt = min(w, (n + step - 1) // step)
    sc = _SPARK
    scale = 7.0 / rng
    out = []
    ap = out.append
    for i in range(cnt):
        idx = int((data[i * step] - mn) * scale)
        ap(sc[0 if idx < 0 else 7 if idx > 7 else idx])
    return "".join(out)


_BARC = " ▏▎▍▌▋▊▉█"


def bar(value: float, width: int = 10, *, lo: float = 0.0,
        hi: float = 1.0, fill: str = "█", track: str = "░") -> str:
    """A horizontal fill-bar STRING ``width`` cells wide, filled to where
    ``value`` falls in ``[lo, hi]``. With the default block glyphs it renders a
    sub-cell-precise gradient using partial-block characters.

        T(bar(0.62, 20)).fg("sky")
    """
    if width <= 0:
        return ""
    frac = saturate(norm(value, lo, hi))
    if fill == "█" and track == "░":
        exact = frac * width
        full = int(exact)
        rem = exact - full
        out = "█" * full
        if full < width:
            out += _BARC[int(rem * 8)]
            out += "░" * (width - full - 1)
        return out[:width]
    full = int(round(frac * width))
    return (fill * full + track * (width - full))[:width]


def fixed(text: Any, width: int, align: str = "left") -> str:
    """Pad / clip ``text`` to exactly ``width`` display cells — the fixed-cell
    column helper for aligning table-ish rows byte-for-byte. ``align``:
    left / right / center.

        row(T(fixed(sym, 6)).fg("sky"), T(fixed(price, 9, "right")))
    """
    text = str(text)
    n = len(text)
    if n > width:
        return text[:width]
    pad = width - n
    if align == "right":
        return " " * pad + text
    if align == "center":
        left = pad // 2
        return " " * left + text + " " * (pad - left)
    return text + " " * pad


def human(n: float, *, prec: int = 1) -> str:
    """Compact number formatting with a magnitude suffix: 1234 → ``1.2k``,
    5_600_000 → ``5.6M``. Great for token counts, bytes, request rates."""
    n = float(n)
    neg = "-" if n < 0 else ""
    n = abs(n)
    for suffix, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= scale:
            return f"{neg}{n / scale:.{prec}f}{suffix}"
    if n == int(n):
        return f"{neg}{int(n)}"
    return f"{neg}{n:.{prec}f}"


def percent(value: float, *, prec: int = 0, sign: bool = False) -> str:
    """Format a 0..1 fraction as a percent string. ``sign=True`` prefixes ``+``
    on positive values (for deltas).

        percent(0.625)             # "62%"
        percent(0.034, sign=True)  # "+3%"
    """
    p = value * 100
    s = "+" if sign and p > 0 else ""
    return f"{s}{p:.{prec}f}%"



__all__ = [
    "T", "b", "i", "u", "dim", "c", "color",
    "col", "row", "trow", "tcol", "card", "field", "hr", "spacer", "memo",
    "center", "stack", "component", "nothing", "grow", "when", "For",
    "pct", "cells", "auto", "sides",
    "BOLD", "DIM", "ITALIC", "UNDERLINE", "STRIKE", "INVERSE",
    "show", "to_string", "App", "Pilot", "animate",
    "gradient_at", "fmt_duration",
    # numeric / animation
    "clamp", "saturate", "lerp", "norm", "remap", "remapc", "smoothstep",
    "wrap", "sign", "approach", "oscillate", "pulse", "ease",
    # colour
    "hsv", "mix", "lighten", "darken", "alpha",
    # data → text
    "spark", "bar", "fixed", "human", "percent",
    "text_input", "textarea",
]
