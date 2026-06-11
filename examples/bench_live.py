"""bench_live.py — measure maya's real strength: the cell-diff on redraw.

A string renderer (maya's render_to_string, or any pure-Python lib) must
re-emit the WHOLE frame every time, even if one character changed. maya's
inline renderer composes a cell grid, diffs it against the previous frame,
and writes ONLY the changed cells to the terminal.

This bench drives maya's real `live()` loop and a pure-Python re-emitter,
both writing to an OS pipe (so there's a real fd but no visible terminal),
across N frames where only a small part changes each frame. We measure:
  - wall-clock per frame
  - bytes written to the wire per frame

The bytes-on-wire number is the one a string renderer can't win: on a
1-cell change maya emits a cursor-move + a few cells; a re-emitter emits
the entire frame.

Run:  PYTHONPATH=src python examples/bench_live.py [--frames N]
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import maya_py as maya
from maya_py import col, row, card, b, T, memo


def parse_args():
    frames = 400
    rows = 20
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--frames":
            frames = int(args[i + 1])
        elif a == "--rows":
            rows = int(args[i + 1])
    return frames, rows


def with_captured_stdout(fn):
    """Run fn() with stdout redirected to a temp file; return (elapsed, bytes_out)."""
    tmp = tempfile.TemporaryFile()
    saved = os.dup(1)
    sys.stdout.flush()
    os.dup2(tmp.fileno(), 1)
    try:
        start = time.perf_counter()
        fn()
        sys.stdout.flush()
        elapsed = time.perf_counter() - start
    finally:
        os.dup2(saved, 1)
        os.close(saved)
    nbytes = tmp.tell()
    tmp.close()
    return elapsed, nbytes


# ── maya: real live() loop with the cell-diff ───────────────────────────────
def _coerce(node):
    from maya_py.easy import _el
    return _el(node)


# ── pure-python: re-emit the whole frame each tick ──────────────────────────
def run_pyui(frames, rows):
    static_rows = "\n".join(
        f"\x1b[38;2;100;180;255mservice-{i:02d}\x1b[0m  \x1b[38;2;80;220;120mOK\x1b[0m"
        for i in range(rows)
    )
    out = sys.stdout
    for n in range(1, frames + 1):
        # cursor home + clear is the cheap version of a re-emit
        frame = f"\x1b[H\x1b[J\x1b[38;2;255;200;60mframe {n}\x1b[0m\n{static_rows}\n"
        out.write(frame)
    out.flush()


def main():
    frames, rows = parse_args()
    print(f"live-redraw benchmark — {frames} frames, {rows}-row body, "
          f"only the counter line changes each frame\n")

    m_time, m_bytes = with_captured_stdout(lambda: _maya_live_entry(frames, rows))
    p_time, p_bytes = with_captured_stdout(lambda: run_pyui(frames, rows))

    print("  per-frame wall-clock:")
    print(f"    maya-py (diff)   {m_time / frames * 1e6:8.1f} µs")
    print(f"    pure-python      {p_time / frames * 1e6:8.1f} µs\n")

    print("  bytes written to the wire (total / per frame):")
    print(f"    maya-py (diff)   {m_bytes:>9} B   {m_bytes / frames:8.1f} B/frame")
    print(f"    pure-python      {p_bytes:>9} B   {p_bytes / frames:8.1f} B/frame\n")

    if m_bytes < p_bytes:
        print(f"  →  maya writes {p_bytes / max(1, m_bytes):.1f}× fewer bytes "
              f"(the diff only emits what changed)")


def _maya_live_entry(frames, rows):
    n = [0]

    @memo
    def body(nrows):
        return col(*[row(T(f"service-{i:02d}").fg("sky"), T("OK").fg("green"), gap=2)
                     for i in range(nrows)], gap=0)

    def render(dt):
        n[0] += 1
        if n[0] >= frames:
            maya.quit()
        return _coerce(card(b(f"frame {n[0]}").fg("gold"), body(rows), title="live"))

    from maya_py import _maya
    _maya.live(render, fps=100000, max_width=80)


if __name__ == "__main__":
    main()
