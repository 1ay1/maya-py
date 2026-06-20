"""scroll_slice.py — Pattern 2: slice-based scrolling (no clip, no overflow).

The opposite trade-off from scroll_clip: instead of building all rows and
letting the renderer drop off-screen ones, we emit ONLY the visible rows into
the tree. Nothing off-screen is ever constructed or laid out — this is how
maya's list/log widgets scale to million-row data sets. The trade-off: the
data must be indexable, and we maintain the offset + key routing ourselves.

  ↑↓ scroll · PgUp/PgDn page · Home/End jump · q quit

    PYTHONPATH=src python examples/scroll_slice.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, T, dim_text

TOTAL = 1_000_000          # a million rows — only ~VH are ever built
VH = 18                    # viewport height in rows

LEVELS = [("INFO", "sky"), ("WARN", "gold"), ("DEBUG", "slate"),
          ("ERROR", "red"), ("OK", "lime")]


def line(i):
    lvl, clr = LEVELS[i % len(LEVELS)]
    return row(
        T(f"{i:>7}").fg("slate"),
        T(f"[{lvl}]").fg(clr),
        T(f"event {i} processed in {(i * 7) % 900 + 10}ms").fg("white"),
        gap=1,
    )


app = App.inline("scroll_slice")
app.state(off=0)


def _clamp(st):
    st.off = max(0, min(TOTAL - VH, st.off))


@app.on("up", "k")
def _u(st): st.off -= 1; _clamp(st)


@app.on("down", "j")
def _d(st): st.off += 1; _clamp(st)


@app.on("pageup")
def _pu(st): st.off -= VH; _clamp(st)


@app.on("pagedown")
def _pd(st): st.off += VH; _clamp(st)


@app.on("home")
def _home(st): st.off = 0


@app.on("end")
def _end(st): st.off = TOTAL - VH


app.quit_on("q", "esc")


@app.view
def view(st):
    # build ONLY the visible window
    rows = [line(st.off + i) for i in range(VH)]
    pct = st.off / (TOTAL - VH) * 100
    return card(
        row(b("slice-scroll").fg("sky"),
            dim_text(f"{TOTAL:,} rows · only {VH} built/frame"),
            justify="between"),
        col(*rows, gap=0),
        dim_text(f"row {st.off:,} · {pct:4.1f}% · ↑↓ scroll · PgUp/Dn · "
                 "Home/End · q quit"),
        title="scroll_slice", gap=1,
    )


if __name__ == "__main__":
    app.run()
