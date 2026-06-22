"""Regression test for the compat-repaint (Zed) diff path.

maya redraws *changed* rows in full (col 0 .. W-1, using only `\\r` + content)
when MAYA_COMPAT_REPAINT=1 or TERM_PROGRAM=zed, because Zed's terminal
mis-tracks the mid-row cursor moves a sub-span update needs. The bug this
guards: that full-row mode also re-emitted UNCHANGED rows every frame, turning
a one-cell change into a whole-frame repaint (bench_live on Zed measured
3137 B/frame vs 96 B/frame normally — *worse* than a naive full re-emit).

The fix gates the whole-row span on the row actually having changed, so an
unchanged row is skipped (the per-row `\\r\\n` advance still steps the cursor,
so vertical tracking — and Zed-safety — is unaffected).

`full_row` is a function-local `static` initialised once per process from the
environment, so each mode must run in its OWN subprocess.
"""

import os
import subprocess
import sys
import tempfile

SRC = os.path.join(os.path.dirname(__file__), "..", "src")

# Renders `frames` live frames: a card whose top line is a changing counter
# above `rows` CONSTANT "service-NN  OK" rows. Only the counter changes each
# frame, so a correct diff never re-touches the service rows after frame 1.
CHILD = r"""
import os, sys
sys.path.insert(0, %r)
import maya_py as maya
from maya_py import col, row, card, b, T, memo
from maya_py.easy import _el
from maya_py import _maya

outpath, frames, rows = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fd = os.open(outpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
saved = os.dup(1); sys.stdout.flush(); os.dup2(fd, 1)
try:
    n = [0]
    @memo
    def body(nr):
        return col(*[row(T(f"service-{i:02d}").fg("sky"), T("OK").fg("green"), gap=2)
                     for i in range(nr)], gap=0)
    def render(dt):
        n[0] += 1
        if n[0] >= frames:
            maya.quit()
        return _el(card(b(f"frame {n[0]}").fg("gold"), body(rows), title="live"))
    _maya.live(render, fps=100000, max_width=80)
    sys.stdout.flush()
finally:
    os.dup2(saved, 1); os.close(saved); os.close(fd)
"""


def _capture(frames, rows, compat):
    """Run the child in a fresh process; return its raw wire bytes."""
    env = dict(os.environ)
    env.pop("MAYA_COMPAT_REPAINT", None)
    env.pop("TERM_PROGRAM", None)
    if compat:
        env["MAYA_COMPAT_REPAINT"] = "1"
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        path = tf.name
    try:
        subprocess.run(
            [sys.executable, "-c", CHILD % SRC, path, str(frames), str(rows)],
            env=env, check=True, timeout=60,
        )
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def _steady_frame(stream):
    """The last sync-bracketed frame — pure steady-state (no initial paint)."""
    parts = [p for p in stream.split(b"\x1b[?2026h") if p]
    assert len(parts) >= 4, f"expected several frames, got {len(parts)}"
    return parts[-2]  # -1 can carry teardown; -2 is a clean mid-stream frame


def test_compat_repaint_skips_unchanged_rows():
    """A steady compat frame re-emits the changed counter, NOT the static rows."""
    frames, rows = 8, 20
    stream = _capture(frames, rows, compat=True)
    frame = _steady_frame(stream)

    # The counter line changed this frame -> its new value must be on the wire.
    # (frames-1 is the last rendered counter; the steady frame we picked is a
    # few before that, but every steady frame re-emits *some* counter digit.)
    assert b"frame" in frame or any(str(d).encode() in frame for d in range(frames)), \
        "changed counter row should be re-emitted"

    # The regression: unchanged service rows must NOT be repainted. Under the
    # bug, full-row mode re-emitted every row, so the bottom rows' text leaked
    # into every frame's bytes.
    for marker in (b"service-19", b"service-15", b"service-10"):
        assert marker not in frame, (
            f"compat repaint re-emitted unchanged row {marker!r} "
            f"(steady frame is {len(frame)} B; this is the whole-frame-repaint bug)"
        )


def test_compat_steady_frame_is_small():
    """Steady compat frame is a few hundred bytes, not a full-frame repaint."""
    stream = _capture(8, 20, compat=True)
    frame = _steady_frame(stream)
    # One full-width row + cursor moves + sync brackets is well under 1 KB;
    # the bug produced ~3 KB (a whole 24-row card).
    assert len(frame) < 1000, f"steady compat frame too big ({len(frame)} B): full-frame repaint regressed"


def test_compat_and_normal_emit_same_service_rows_once():
    """Both modes paint the static rows on frame 1 and never again."""
    for compat in (False, True):
        stream = _capture(8, 20, compat=compat)
        parts = [p for p in stream.split(b"\x1b[?2026h") if p]
        first, rest = parts[0], parts[1:]
        assert b"service-19" in first, f"compat={compat}: first frame must paint static rows"
        for i, fr in enumerate(rest, 1):
            assert b"service-19" not in fr, (
                f"compat={compat}: frame {i} re-emitted an unchanged static row"
            )
