"""golden_snapshot.py — dump a byte-exact render snapshot of every example.

Renders each example module's entry element at several widths and writes the
concatenated bytes to the path given as argv[1]. Used to prove a maya-src
layout change is output-identical: snapshot before, snapshot after, diff.

    PYTHONPATH=src python scripts/golden_snapshot.py /tmp/snap.txt
"""
import sys
import os
import importlib

HERE = os.path.dirname(__file__)
EX = os.path.join(HERE, "..", "examples")
sys.argv = ["golden"]
sys.path.insert(0, EX)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import maya_py as maya

SKIP = {"smoke_all", "_halfblock", "bench", "bench_live"}
WIDTHS = (40, 60, 80, 100, 110, 132)

mods = sorted(
    f[:-3] for f in os.listdir(EX)
    if f.endswith(".py") and f[:-3] not in SKIP
)

out = []
for name in mods:
    try:
        m = importlib.import_module(name)
    except Exception as e:
        out.append(f"### {name}: IMPORT-FAIL {e}\n")
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
            prog_cls = next(
                (v for v in vars(m).values()
                 if isinstance(v, type) and issubclass(v, maya.Program)
                 and v is not maya.Program),
                None,
            )
            if prog_cls is not None:
                el = prog_cls().test().view()
            else:
                continue
    except Exception as e:
        out.append(f"### {name}: BUILD-FAIL {e}\n")
        continue
    for w in WIDTHS:
        try:
            s = maya.to_string(el, w)
        except Exception as e:
            s = f"RENDER-FAIL {e}"
        out.append(f"### {name} @ {w}\n{s}\n")

dst = os.environ.get("SNAP_DST", "/tmp/snap.txt")
with open(dst, "w") as f:
    f.write("".join(out))
print(f"wrote {dst}: {sum(len(x) for x in out)} bytes, {len(mods)} modules")
