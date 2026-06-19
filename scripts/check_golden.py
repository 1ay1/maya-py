"""check_golden.py — byte-exact render regression gate.

Renders every example's entry element at several widths (same logic as
scripts/golden_snapshot.py) and compares the concatenated bytes against the
committed golden at tests/golden.txt.

    python scripts/check_golden.py            # verify (CI gate; exit 1 on diff)
    python scripts/check_golden.py --update   # regenerate the golden

A diff means a layout/render change altered output. If intended, re-run with
--update and commit tests/golden.txt in the same change so reviewers see the
visual delta.
"""
import sys
import os
import importlib
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
EX = os.path.join(ROOT, "examples")
GOLDEN = os.path.join(ROOT, "tests", "golden.txt")

_UPDATE = "--update" in sys.argv
sys.argv = ["golden"]
sys.path.insert(0, EX)
sys.path.insert(0, os.path.join(ROOT, "src"))

import maya_py as maya  # noqa: E402

# Some examples are meant to be run as scripts and call a BLOCKING entry point
# (show / live / animate / App.run / run / run_program) at module top level.
# Importing them for a snapshot must not take over the terminal or block, so
# neutralize those entry points into no-ops before any example is imported.
_NOOP = lambda *a, **k: None  # noqa: E731
for _name in ("show", "live", "animate", "run", "run_program"):
    if hasattr(maya, _name):
        setattr(maya, _name, _NOOP)
try:
    maya.App.run = _NOOP  # type: ignore[assignment]
except Exception:  # noqa: BLE001
    pass
try:
    maya.Program.run = _NOOP  # type: ignore[assignment]
except Exception:  # noqa: BLE001
    pass

# Skip non-renderable helpers and anything whose output is intentionally
# nondeterministic (time/random-driven frames).
SKIP = {
    "smoke_all", "_halfblock", "bench", "bench_live",
    # nondeterministic: wall-clock / RNG in their entry render
    "clock", "matrix", "hacker", "doom_fire", "fluid", "particles",
    "space", "space3d", "raymarch", "fps", "mandelbrot", "boids",
    "gravity", "life", "sorts", "spectrum",
    # animated/spinner or time-driven view state
    "deploy", "messenger", "agent", "agent_session", "chat", "music",
    # RNG-driven view state
    "snake", "stocks", "sysmon", "breakout", "maze", "paint",
}
WIDTHS = (40, 60, 80, 100, 110, 132)


def build_snapshot() -> str:
    mods = sorted(
        f[:-3] for f in os.listdir(EX)
        if f.endswith(".py") and f[:-3] not in SKIP
    )
    out = []
    for name in mods:
        try:
            m = importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            out.append(f"### {name}: IMPORT-FAIL {type(e).__name__}\n")
            continue
        el = None
        try:
            if hasattr(m, "app") and hasattr(m, "view"):
                for _ in range(3):
                    el = m.view(m.app.s)
            elif hasattr(m, "showcase"):
                el = m.showcase()
            elif hasattr(m, "document"):
                el = m.document()
            elif hasattr(m, "summary"):
                el = m.summary()
            elif hasattr(m, "gallery"):
                el = m.gallery()
            else:
                continue
        except Exception as e:  # noqa: BLE001
            out.append(f"### {name}: BUILD-FAIL {type(e).__name__}\n")
            continue
        for w in WIDTHS:
            try:
                s = maya.to_string(el, w)
            except Exception as e:  # noqa: BLE001
                s = f"RENDER-FAIL {type(e).__name__}"
            out.append(f"### {name} @ {w}\n{s}\n")
    return "".join(out)


def main() -> int:
    snap = build_snapshot()

    if _UPDATE:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w", encoding="utf-8") as f:
            f.write(snap)
        print(f"updated {GOLDEN}: {len(snap)} bytes")
        return 0

    if not os.path.exists(GOLDEN):
        print(f"ERROR: no golden at {GOLDEN}. Run: python scripts/check_golden.py --update")
        return 1

    with open(GOLDEN, encoding="utf-8") as f:
        want = f.read()

    if snap == want:
        print(f"golden OK: {len(snap)} bytes match")
        return 0

    print("GOLDEN MISMATCH — render output changed:\n")
    diff = difflib.unified_diff(
        want.splitlines(keepends=True),
        snap.splitlines(keepends=True),
        fromfile="golden.txt", tofile="current", n=1,
    )
    # Cap the diff so a wholesale change doesn't flood the log.
    shown = 0
    for line in diff:
        sys.stdout.write(line)
        shown += 1
        if shown > 400:
            sys.stdout.write("\n... (diff truncated) ...\n")
            break
    print("\nIf this change is intended: python scripts/check_golden.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
