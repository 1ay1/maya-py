"""suspend — hand the real terminal to an interactive child (Cmd.suspend).

A faithful port of maya's Cmd::suspend demo. The TUI stays inline; pressing a
key returns a Cmd.suspend(fn) that tears the TUI down to a clean cooked tty,
runs an interactive child that OWNS the terminal (an editor, a pager, a shell),
then restores the TUI and folds the child's exit code back into the model via
the message fn() returns.

Run it::

    python examples/suspend.py

    e   $EDITOR on a scratch file       s   drop to a shell ($SHELL -i)
    l   page this file through less     q   quit

Because fn() runs SYNCHRONOUSLY on the UI thread, you interact with the child
directly (type in vim, scroll in less); when it exits the TUI comes back and
the reducer records what happened.
"""

import os
import subprocess
import tempfile

import _bootstrap  # noqa: F401

import maya_py as maya
from maya_py import Cmd, Sub, Program


def _run_editor():
    editor = os.environ.get("EDITOR", "vi")
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="maya_suspend_")
    os.close(fd)
    with open(path, "w") as f:
        f.write("edit me, then :wq — maya restores the TUI when you exit\n")
    rc = subprocess.call([editor, path])
    try:
        with open(path) as f:
            n = sum(1 for _ in f)
    finally:
        os.unlink(path)
    return ("child_done", f"{editor} (exit {rc}, {n} lines)")


def _run_pager():
    less = os.environ.get("PAGER", "less")
    rc = subprocess.call([less, __file__])
    return ("child_done", f"{less} (exit {rc})")


def _run_shell():
    shell = os.environ.get("SHELL", "/bin/sh")
    rc = subprocess.call([shell, "-i"])
    return ("child_done", f"{shell} (exit {rc})")


class SuspendDemo(Program):
    title = "suspend"
    inline = True

    def init(self):
        return {"last": "—", "runs": 0}, Cmd.set_title("maya suspend")

    def update(self, m, msg):
        if msg == "edit":
            return m, Cmd.suspend(_run_editor)
        if msg == "pager":
            return m, Cmd.suspend(_run_pager)
        if msg == "shell":
            return m, Cmd.suspend(_run_shell)
        if isinstance(msg, tuple) and msg[0] == "child_done":
            # fn() returned this AFTER the TUI was restored — fold it in.
            return {**m, "last": msg[1], "runs": m["runs"] + 1}
        if msg == "quit":
            return m, Cmd.quit()
        return m

    def view(self, m):
        return maya.box(
            maya.text("Cmd.suspend", maya.bold | maya.fg(120, 180, 255)),
            maya.blank(),
            maya.text("hand the terminal to an interactive child, then come back",
                      maya.dim),
            maya.blank(),
            maya.text(f"last child:  {m['last']}", maya.bold),
            maya.text(f"total runs:  {m['runs']}", maya.dim),
            maya.blank(),
            maya.text("e  editor      l  pager      s  shell      q  quit",
                      maya.dim),
            direction=maya.Column,
            border=maya.Round, padding=2,
        )

    def subscribe(self, m):
        def on_key(ev):
            if maya.key(ev, "e"):
                return "edit"
            if maya.key(ev, "l"):
                return "pager"
            if maya.key(ev, "s"):
                return "shell"
            if maya.key(ev, "q") or maya.key_special(ev, maya.SpecialKey.Escape):
                return "quit"
            return None
        return Sub.on_key(on_key)


if __name__ == "__main__":
    SuspendDemo().run()
