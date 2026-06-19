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


def _split(result: Any) -> "tuple[Any, list]":
    """Normalize an init()/update() return into ``(model, [Cmd, ...])``.

    A hook may return a bare ``model`` or a ``(model, Cmd)`` pair — the same
    contract the native runtime accepts. The pilot threads the model and
    collects the commands.
    """
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], Cmd):
        return result[0], [result[1]]
    return result, []


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

    # -- headless testing ----------------------------------------------------

    def test(self) -> "ProgramPilot":
        """Drive this Program headlessly — no terminal. Returns a
        :class:`ProgramPilot` that runs the SAME pure ``init``/``update``/
        ``view`` your live app uses, so the whole architecture is unit-testable
        with zero ceremony::

            p = Counter().test()
            p.send("inc", "inc")
            assert p.model["count"] == 2
            assert "count: 2" in p.view_string()
        """
        return ProgramPilot(self.init, self.update, self.view)


def program_test(
    init: Callable[[], Any],
    update: Callable[[Model, Msg], Any],
    view: Optional[Callable[[Model], Any]] = None,
) -> "ProgramPilot":
    """Headless driver for a plain-function Program — the function-form twin of
    :meth:`Program.test`. ``view`` is optional (omit it to test pure
    ``update`` transitions without rendering).
    """
    return ProgramPilot(init, update, view)


class ProgramPilot:
    """A headless driver for an MVU Program — the pure-architecture test harness.

    The Elm Architecture's whole promise is that ``update`` is a pure function
    you can test in isolation: ``new_model = update(model, msg)``. This pilot
    threads that for you — it holds the model, dispatches messages through
    ``update`` (immutably), collects every emitted ``Cmd``, and renders ``view``
    on demand. No terminal, no event loop, fully deterministic::

        p = Counter().test()
        p.send("inc")              # dispatch a message
        p.send("inc", "dec")       # several, in order
        assert p.model["count"] == 1
        assert p.cmds                # a Cmd was emitted somewhere
        assert "count: 1" in p.view_string(width=40)

    Because messages are dispatched directly (not synthesized from keystrokes),
    tests target the pure core exactly the way ``elm-test`` does — the view's
    ``Sub`` event-routing is the native runtime's job and stays out of the way.
    """

    def __init__(
        self,
        init: Callable[[], Any],
        update: Callable[[Model, Msg], Any],
        view: Optional[Callable[[Model], Any]] = None,
    ):
        self._update = update
        self._view = view
        self._model, self.cmds = _split(init())

    # -- driving -------------------------------------------------------------

    def send(self, *msgs: Msg) -> "ProgramPilot":
        """Dispatch one or more messages through ``update`` in order, threading
        the model and appending any emitted ``Cmd`` to :attr:`cmds`. Chainable.
        """
        for msg in msgs:
            model, cmds = _split(self._update(self._model, msg))
            self._model = model
            self.cmds.extend(cmds)
        return self

    # -- observing -----------------------------------------------------------

    @property
    def model(self) -> Any:
        """The current model (after every message sent so far)."""
        return self._model

    @property
    def last_cmd(self):
        """The most recently emitted ``Cmd``, or ``None`` if none yet."""
        return self.cmds[-1] if self.cmds else None

    def view_string(self, width: int = 80) -> str:
        """Render the current model's ``view`` to a plain string. Requires a
        ``view`` (raises if the Program/pilot was built without one)."""
        if self._view is None:
            raise RuntimeError("this ProgramPilot has no view to render")
        return _maya.render_to_string(self._view(self._model), width)

    def view(self):
        """The current model's ``view`` element (un-rendered)."""
        if self._view is None:
            raise RuntimeError("this ProgramPilot has no view to render")
        return self._view(self._model)


__all__ = ["Cmd", "Sub", "Program", "run_program", "ProgramPilot", "program_test"]
