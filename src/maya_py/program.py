"""maya MVU runtime — the same Program model as maya's C++ ``run<P>``.

A maya application is a *Program*: pure functions over an immutable Model and
a closed set of Messages. Side effects are described as ``Cmd`` data and event
sources as ``Sub`` data — the runtime performs them. update() never touches
the terminal, so it stays a pure, testable state transition.

Two ways to write one:

1. Plain functions::

       import maya_py as maya
       from maya_py import Cmd, Sub, run_program

       def init():
           return {"count": 0}                      # model | (model, Cmd)

       def update(model, msg):
           if msg == "inc": model = {**model, "count": model["count"] + 1}
           if msg == "dec": model = {**model, "count": model["count"] - 1}
           if msg == "quit": return model, Cmd.quit()
           return model

       def view(model):
           return maya.card(maya.text(f"count: {model['count']}"))

       def subscribe(model):
           return Sub.on_key(lambda ev: (
               "inc" if maya.key(ev, "+") else
               "dec" if maya.key(ev, "-") else
               "quit" if maya.key(ev, "q") else None))

       run_program(init, update, view, subscribe, title="counter")

2. A ``Program`` subclass — override init/update/view/subscribe and call
   ``.run()``. Same semantics, OO ergonomics.

Cmd and Sub are the native maya value types (built by the same smart
constructors the C++ side uses), so an effect or subscription returned from
Python is interpreted by maya's real runtime — not a Python reimplementation.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import _maya

# Native MVU value types — re-exported verbatim.
Cmd = _maya.Cmd
Sub = _maya.Sub

Model = Any
Msg = Any


def run_program(
    init: Callable[[], Any],
    update: Callable[[Model, Msg], Any],
    view: Callable[[Model], Any],
    subscribe: Optional[Callable[[Model], Any]] = None,
    *,
    title: str = "",
    inline: bool = False,
    mouse: bool = False,
    fps: int = 0,
) -> None:
    """Run a Program with maya's full MVU loop.

    - ``init()``              -> ``model`` or ``(model, Cmd)``
    - ``update(model, msg)``  -> ``model`` or ``(model, Cmd)``
    - ``view(model)``         -> ``Element``
    - ``subscribe(model)``    -> ``Sub`` (optional; default no subscriptions)

    ``inline=True`` renders into the terminal's own scrollback (no alt screen);
    ``fps>0`` drives continuous rendering. Blocks until ``Cmd.quit()`` or
    Ctrl-C.
    """
    _maya.run_program(
        init, update, view, subscribe,
        title, inline, mouse, fps,
    )


class Program:
    """Base class for an MVU application.

    Override the four hooks and call ``.run()``::

        class Counter(Program):
            def init(self):              return {"n": 0}
            def update(self, m, msg):    ...
            def view(self, m):           return maya.card(...)
            def subscribe(self, m):      return Sub.on_key(...)

        Counter().run(title="counter")

    The default ``init`` returns ``{}``, ``update`` is identity, and
    ``subscribe`` returns no sources — override what you need.
    """

    title: str = ""
    inline: bool = False
    mouse: bool = False
    fps: int = 0

    # -- hooks (override) ----------------------------------------------------

    def init(self) -> Any:
        """Initial model, optionally paired with a startup ``Cmd``."""
        return {}

    def update(self, model: Model, msg: Msg) -> Any:
        """Pure transition: return the next model (and an optional ``Cmd``)."""
        return model

    def view(self, model: Model) -> Any:
        """Render the model to an ``Element``. Must be overridden."""
        raise NotImplementedError("Program.view must be overridden")

    def subscribe(self, model: Model) -> Any:
        """Declare event sources for this model. Default: none."""
        return Sub.none()

    # -- driver --------------------------------------------------------------

    def run(
        self,
        *,
        title: Optional[str] = None,
        inline: Optional[bool] = None,
        mouse: Optional[bool] = None,
        fps: Optional[int] = None,
    ) -> None:
        """Start the runtime. Keyword args override the class attributes."""
        run_program(
            self.init,
            self.update,
            self.view,
            self.subscribe,
            title=self.title if title is None else title,
            inline=self.inline if inline is None else inline,
            mouse=self.mouse if mouse is None else mouse,
            fps=self.fps if fps is None else fps,
        )


__all__ = ["Cmd", "Sub", "Program", "run_program"]
