"""smoke_all.py — headless render-one-frame test for every example.

Imports each example module, drives its view (or showcase / render) a few
frames, and asserts a non-empty string comes out. Catches import errors,
missing names, and renderer crashes WITHOUT opening a TUI.

    PYTHONPATH=src python examples/smoke_all.py
"""

import sys
import os
import importlib
import traceback

HERE = os.path.dirname(__file__)
sys.argv = ["smoke"]
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import maya_py as maya

SKIP = {"smoke_all", "_halfblock", "bench", "bench_live"}

mods = sorted(
    f[:-3] for f in os.listdir(HERE)
    if f.endswith(".py") and f[:-3] not in SKIP
)

ok, fail = 0, []
for name in mods:
    try:
        m = importlib.import_module(name)
        el = None
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
            print(f"·· {name}: no render entry (skipped)")
            continue
        out = maya.to_string(el, 110)
        assert isinstance(out, str) and out.strip(), "empty render"
        print(f"ok  {name:<18} {out.count(chr(10)):>3} lines")
        ok += 1
    except Exception:
        fail.append((name, traceback.format_exc().splitlines()[-1]))
        print(f"XX  {name}")

print(f"\n{ok} examples rendered OK, {len(fail)} failed")
for n, e in fail:
    print(f"   FAIL {n}: {e}")
sys.exit(1 if fail else 0)
