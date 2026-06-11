"""sorts.py — a sorting-algorithm visualizer racing several algorithms at once.

Each algorithm sorts its own copy of a shuffled array, one comparison/swap
step per frame, drawn as coloured vertical bars. Bars light up green when in
final position. Bubble, insertion, selection, quick, and merge run side by
side so you can watch their different rhythms.

  space pause · r reshuffle · q/esc quit

    PYTHONPATH=src python examples/sorts.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import App, col, row, card, b, dim_text, T, component

N = 32
H = 12
BLOCKS = "▁▂▃▄▅▆▇█"


# Each sorter is a generator yielding (array, active_indices, done) per step.
def bubble(a):
    a = a[:]
    n = len(a)
    for i in range(n):
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
            yield a, (j, j + 1), n - i
    yield a, (), 0


def insertion(a):
    a = a[:]
    for i in range(1, len(a)):
        j = i
        while j > 0 and a[j - 1] > a[j]:
            a[j - 1], a[j] = a[j], a[j - 1]
            j -= 1
            yield a, (j, j + 1), -1
    yield a, (), 0


def selection(a):
    a = a[:]
    n = len(a)
    for i in range(n):
        m = i
        for j in range(i + 1, n):
            if a[j] < a[m]:
                m = j
            yield a, (i, j), i
        a[i], a[m] = a[m], a[i]
    yield a, (), 0


def quick(a):
    a = a[:]

    def qs(lo, hi):
        if lo >= hi:
            return
        pivot = a[hi]
        i = lo
        for j in range(lo, hi):
            if a[j] < pivot:
                a[i], a[j] = a[j], a[i]
                i += 1
            yield a, (j, hi), -1
        a[i], a[hi] = a[hi], a[i]
        yield a, (i, hi), -1
        yield from qs(lo, i - 1)
        yield from qs(i + 1, hi)
    yield from qs(0, len(a) - 1)
    yield a, (), 0


def merge(a):
    a = a[:]

    def ms(lo, hi):
        if hi - lo <= 1:
            return
        mid = (lo + hi) // 2
        yield from ms(lo, mid)
        yield from ms(mid, hi)
        left = a[lo:mid]
        right = a[mid:hi]
        i = j = 0
        k = lo
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                a[k] = left[i]; i += 1
            else:
                a[k] = right[j]; j += 1
            yield a, (k,), -1
            k += 1
        while i < len(left):
            a[k] = left[i]; i += 1; k += 1
            yield a, (k - 1,), -1
        while j < len(right):
            a[k] = right[j]; j += 1; k += 1
            yield a, (k - 1,), -1
    yield from ms(0, len(a))
    yield a, (), 0


ALGOS = [("bubble", bubble), ("insertion", insertion),
         ("selection", selection), ("quick", quick), ("merge", merge)]

app = App("sorts", inline=True, fps=30)
app.state(gens={}, frames={}, paused=False, src=[])


def reshuffle(s):
    base = list(range(1, N + 1))
    random.shuffle(base)
    s.src = base
    s.gens = {name: fn(base) for name, fn in ALGOS}
    s.frames = {name: (base[:], (), N) for name, _ in ALGOS}


reshuffle(app.s)


@app.on("space")
def _pause(s): s.paused = not s.paused


@app.on("r")
def _reshuffle(s): reshuffle(s)


@app.on("q", "esc")
def _quit(s): app.stop()


def step(s):
    for name, _ in ALGOS:
        try:
            s.frames[name] = next(s.gens[name])
        except StopIteration:
            arr = s.frames[name][0]
            s.frames[name] = (arr, (), 0)


def bars(arr, active, sorted_from):
    def draw(w, h):
        lines = []
        for rowi in range(H):
            lo = (H - 1 - rowi) / H
            segs = []
            for i, v in enumerate(arr):
                frac = v / N
                if i in active:
                    clr = (255, 255, 255)
                elif sorted_from == 0:
                    clr = (90, 230, 110)
                else:
                    clr = (90, 150, 250)
                if frac > lo:
                    sub = min(1.0, (frac - lo) * H)
                    ch = BLOCKS[min(7, int(sub * 7))] if sub < 1 else "█"
                    segs.append(T(ch).fg(maya.rgb(*clr)))
                else:
                    segs.append(T(" "))
            lines.append(row(*segs, gap=0))
        return col(*lines, gap=0)
    return component(draw, height=H, width=N)


@app.view
def view(s):
    if not s.paused:
        step(s)
    panels = []
    for name, _ in ALGOS:
        arr, active, sf = s.frames[name]
        done = sf == 0
        title = T(name).fg("lime" if done else "gold")
        panels.append(card(title, bars(arr, active, sf), pad=1,
                           border="round",
                           border_color="lime" if done else "slate"))
    return card(
        row(b("⇅ sort race").fg("sky"),
            dim_text(f"n={N} · {'paused' if s.paused else 'racing'}"),
            justify="between"),
        row(*panels, gap=1),
        dim_text("space pause · r reshuffle · q quit"),
        title="sorts", gap=1,
    )


if __name__ == "__main__":
    app.run()
