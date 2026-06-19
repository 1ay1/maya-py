"""``python -m maya_py`` — a tiny CLI to get you from zero to a running app.

Commands
--------
    python -m maya_py new <name>     scaffold a runnable app file
    python -m maya_py demo           run a built-in counter (sanity check)
    python -m maya_py version        print the installed version
"""

from __future__ import annotations

import sys
from pathlib import Path

_TEMPLATE = '''\
"""{name} — a maya-py app. Run: python {filename}"""
from maya_py import App, card, col, b, dim_text


# State lives in the constructor; quit_keys auto-binds q/Esc to quit.
app = App("{name}", n=0, quit_keys=("q", "esc"))


@app.on("+", "=")
def inc(s):
    s.n += 1


@app.on("-")
def dec(s):
    s.n -= 1


@app.on("r")
def reset(s):
    s.n = 0


@app.view
def view(s):
    return card(
        b(f"Count: {{s.n}}").fg("sky"),
        col(
            dim_text("+/-  change"),
            dim_text("r    reset"),
            dim_text("q    quit"),
        ),
        title="{name}",
    )


if __name__ == "__main__":
    app.run()
'''


def _cmd_new(args: list[str]) -> int:
    if not args:
        print("usage: python -m maya_py new <name>", file=sys.stderr)
        return 2
    name = args[0]
    # Derive a safe filename from the app name.
    slug = "".join(c if (c.isalnum() or c in "_-") else "_" for c in name).strip("_-")
    if not slug:
        slug = "app"
    filename = f"{slug}.py"
    path = Path(filename)
    if path.exists():
        print(f"refusing to overwrite existing {filename!r}", file=sys.stderr)
        return 1
    path.write_text(_TEMPLATE.format(name=name, filename=filename))
    print(f"created {filename}")
    print(f"  run it:  python {filename}")
    return 0


def _cmd_demo(_args: list[str]) -> int:
    from maya_py import App, card, b, dim_text

    app = App("demo", n=0, quit_keys=("q", "esc"))
    app.on("+", "=")(lambda s: setattr(s, "n", s.n + 1))
    app.on("-")(lambda s: setattr(s, "n", s.n - 1))
    app.view(lambda s: card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("+/- change   q quit"),
        title="demo",
    ))
    app.run()
    return 0


def _cmd_version(_args: list[str]) -> int:
    import maya_py
    print(maya_py.__version__)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    table = {"new": _cmd_new, "demo": _cmd_demo,
             "version": _cmd_version, "--version": _cmd_version}
    fn = table.get(cmd)
    if fn is None:
        print(f"unknown command {cmd!r}\n", file=sys.stderr)
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
