"""Type stubs for the native ``maya_py._maya`` extension module.

Hand-maintained to back the PEP 561 ``py.typed`` marker: these signatures give
editors (pyright / mypy / Pylance) completion and type-checking for the native
surface that pybind11 builds at runtime. Keep in sync with src/_maya.cpp.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional

# ── enums ────────────────────────────────────────────────────────────────────

class FlexDirection(Enum):
    Row: int
    Column: int
    RowReverse: int
    ColumnReverse: int

class FlexWrap(Enum):
    NoWrap: int
    Wrap: int
    WrapReverse: int

class Align(Enum):
    Start: int
    Center: int
    End: int
    Stretch: int
    Baseline: int

class Justify(Enum):
    Start: int
    Center: int
    End: int
    SpaceBetween: int
    SpaceAround: int
    SpaceEvenly: int

class BorderStyle(Enum):
    None_: int
    Single: int
    Double: int
    Round: int
    Bold: int
    SingleDouble: int
    DoubleSingle: int
    Classic: int
    Arrow: int
    Dashed: int

class BorderTextPos(Enum):
    Top: int
    Bottom: int

class BorderTextAlign(Enum):
    Start: int
    Center: int
    End: int

class Overflow(Enum):
    Visible: int
    Hidden: int
    Scroll: int

class TextWrap(Enum):
    Wrap: int
    TruncateEnd: int
    TruncateMiddle: int
    TruncateStart: int
    NoWrap: int

class SpecialKey(Enum):
    Up: int
    Down: int
    Left: int
    Right: int
    Home: int
    End: int
    PageUp: int
    PageDown: int
    Tab: int
    BackTab: int
    Backspace: int
    Delete: int
    Insert: int
    Enter: int
    Escape: int
    F1: int
    F2: int
    F3: int
    F4: int
    F5: int
    F6: int
    F7: int
    F8: int
    F9: int
    F10: int
    F11: int
    F12: int

class MouseButton(Enum):
    Left: int
    Right: int
    Middle: int
    ScrollUp: int
    ScrollDown: int
    ScrollLeft: int
    ScrollRight: int
    None_: int

class MouseEventKind(Enum):
    Press: int
    Release: int
    Move: int

# ── core value types ─────────────────────────────────────────────────────────

class Color:
    @staticmethod
    def rgb(r: int, g: int, b: int) -> Color: ...
    @staticmethod
    def hex(value: int) -> Color: ...
    @staticmethod
    def indexed(i: int) -> Color: ...
    @staticmethod
    def default_color() -> Color: ...
    @staticmethod
    def black() -> Color: ...
    @staticmethod
    def red() -> Color: ...
    @staticmethod
    def green() -> Color: ...
    @staticmethod
    def yellow() -> Color: ...
    @staticmethod
    def blue() -> Color: ...
    @staticmethod
    def magenta() -> Color: ...
    @staticmethod
    def cyan() -> Color: ...
    @staticmethod
    def white() -> Color: ...
    @staticmethod
    def gray() -> Color: ...
    @staticmethod
    def grey() -> Color: ...
    @staticmethod
    def bright_black() -> Color: ...
    @staticmethod
    def bright_red() -> Color: ...
    @staticmethod
    def bright_green() -> Color: ...
    @staticmethod
    def bright_yellow() -> Color: ...
    @staticmethod
    def bright_blue() -> Color: ...
    @staticmethod
    def bright_magenta() -> Color: ...
    @staticmethod
    def bright_cyan() -> Color: ...
    @staticmethod
    def bright_white() -> Color: ...

class Style:
    def __init__(self) -> None: ...
    @staticmethod
    def empty() -> Style: ...
    def with_fg(self, c: Color) -> Style: ...
    def with_bg(self, c: Color) -> Style: ...
    def with_bold(self) -> Style: ...
    def with_dim(self) -> Style: ...
    def with_italic(self) -> Style: ...
    def with_underline(self) -> Style: ...
    def with_strikethrough(self) -> Style: ...
    def with_inverse(self) -> Style: ...
    def merge(self, other: Style) -> Style: ...
    def to_sgr(self) -> str: ...
    def __or__(self, other: Style) -> Style: ...

class Dimension:
    @staticmethod
    def fixed(cells: int) -> Dimension: ...
    @staticmethod
    def percent(value: float) -> Dimension: ...
    @staticmethod
    def auto() -> Dimension: ...
    def is_fixed(self) -> bool: ...
    def is_percent(self) -> bool: ...
    def is_auto(self) -> bool: ...

class BorderSides:
    @staticmethod
    def all() -> BorderSides: ...
    @staticmethod
    def none() -> BorderSides: ...
    @staticmethod
    def top() -> BorderSides: ...
    @staticmethod
    def bottom() -> BorderSides: ...
    @staticmethod
    def left() -> BorderSides: ...
    @staticmethod
    def right() -> BorderSides: ...
    @staticmethod
    def horizontal() -> BorderSides: ...
    @staticmethod
    def vertical() -> BorderSides: ...

class Element:
    """An opaque, immutable renderable node produced by the builders."""
    ...

class Event:
    """An opaque input event. Inspect it with the ``key`` / ``mouse_*`` /
    ``pasted`` / ``resize_size`` predicates; never constructed directly except
    via the ``make_*`` factories (for headless tests)."""
    ...

# MVU runtime command/subscription handles (see maya_py.program).
class Cmd: ...
class Sub: ...

# ── element factories ────────────────────────────────────────────────────────

def text(
    content: str,
    style: Optional[Style] = None,
    wrap: TextWrap = ...,
) -> Element: ...
def styled_text(
    content: str,
    fg: int = -1,
    bg: int = -1,
    attrs: int = 0,
    wrap: TextWrap = ...,
) -> Element: ...
def styled_text_row(
    flat: list,
    n: int,
    direction: int,
    gap: int = -1,
    grow: float = -1.0,
) -> Element: ...
def styled_grid(
    flat: list,
    row_lens: list,
    inner_dir: int,
    outer_gap: int = -1,
    inner_gap: int = -1,
) -> Element: ...
def cell_grid(grid: list, w: int, h: int, gap: int = 0) -> Element: ...
def box(*args: Any, **kwargs: Any) -> Element: ...
def box_simple(
    children: list[Element],
    direction: int,
    gap: int = -1,
    grow: float = -1.0,
) -> Element: ...
def box_titled(
    children: list[Element],
    direction: int,
    gap: int,
    grow: float,
    border: int,
    pad: int,
    title: str,
    border_color: int = -1,
) -> Element: ...
def vstack(*args: Any, **kwargs: Any) -> Element: ...
def hstack(*args: Any, **kwargs: Any) -> Element: ...
def zstack(*args: Any, **kwargs: Any) -> Element: ...
def center(*args: Any, **kwargs: Any) -> Element: ...
def component(*args: Any, **kwargs: Any) -> Element: ...
def blank() -> Element: ...
def nothing() -> Element: ...

# ── rendering ────────────────────────────────────────────────────────────────

def render_to_string(element: Element, width: int = 80) -> str: ...
def print_element(element: Element, width: Optional[int] = None) -> None: ...
def live(
    render_fn: Callable[[float], Element],
    fps: int = 30,
    max_width: int = 0,
    cursor: bool = False,
) -> None: ...
def run(
    event_fn: Callable[[Event], bool],
    render_fn: Callable[[], Element],
    title: str = "",
    inline_mode: bool = False,
    mouse: bool = False,
    fps: int = 0,
) -> None: ...
def run_program(
    init: object,
    update: object,
    view: object,
    subscribe: object = None,
    title: str = "",
    inline_mode: bool = False,
    mouse: bool = False,
    fps: int = 0,
) -> None: ...
def quit() -> None: ...
def set_mouse(on: bool) -> None: ...
def string_width(s: str) -> int: ...

# ── key event predicates ─────────────────────────────────────────────────────

def key(ev: Event, ch: str) -> bool: ...
def key_special(ev: Event, sk: SpecialKey) -> bool: ...
def ctrl(ev: Event, ch: str) -> bool: ...
def alt(ev: Event, ch: str) -> bool: ...
def any_key(ev: Event) -> bool: ...
def resized(ev: Event) -> bool: ...
def event_char(ev: Event) -> Optional[str]: ...
def pasted(ev: Event) -> Optional[str]: ...
def resize_size(ev: Event) -> Optional[tuple[int, int]]: ...

# ── mouse event predicates ───────────────────────────────────────────────────

def is_mouse(ev: Event) -> bool: ...
def mouse_clicked(ev: Event, button: MouseButton = ...) -> bool: ...
def mouse_released(ev: Event, button: MouseButton = ...) -> bool: ...
def mouse_moved(ev: Event) -> bool: ...
def scrolled_up(ev: Event) -> bool: ...
def scrolled_down(ev: Event) -> bool: ...
def mouse_pos(ev: Event) -> Optional[tuple[int, int]]: ...
def mouse_button(ev: Event) -> Optional[MouseButton]: ...
def mouse_kind(ev: Event) -> Optional[MouseEventKind]: ...
def scroll_handle(state: Any, ev: Event) -> bool: ...

# ── synthetic event factories (headless driving / testing) ───────────────────

def make_key(
    key: str,
    ctrl: bool = False,
    alt: bool = False,
    shift: bool = False,
    super: bool = False,
) -> Event: ...
def make_mouse(
    col: int,
    row: int,
    button: str = "left",
    kind: str = "press",
    ctrl: bool = False,
    alt: bool = False,
    shift: bool = False,
) -> Event: ...
def make_scroll(direction: str, col: int = 1, row: int = 1) -> Event: ...
def make_paste(text: str) -> Event: ...
def make_resize(cols: int, rows: int) -> Event: ...
