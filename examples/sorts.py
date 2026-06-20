"""sorts.py — Sorting Algorithm Visualizer.

A faithful port of maya's `examples/sorts.cpp`. Eight sorting algorithms race
side-by-side with half-block bars for double vertical resolution, drawn through
maya's native half-block surface. Each algorithm is run to completion up front,
recording a flat op-list (COMPARE / SWAP / SET / MARK_SORTED); the visualizer
replays N ops per frame — so the sort logic and the animation are decoupled,
exactly like the C++ original.

  Keys: q/Esc quit · space restart · p pattern · k pause
        +/- or ←/→ speed · ↑/↓ double/halve · 1-8 solo · 0 show all

    PYTHONPATH=src python examples/sorts.py
"""

from __future__ import annotations

import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import App, T, col, row, component, halfblock, clamp as clampi  # noqa: E402

NUM_ALGOS = 8
ARRAY_SIZE = 80
CELEBRATION_FRAMES = 50
NUM_PATTERNS = 5
CELEB_HUES = 72

# HighlightKind
H_NONE, H_COMPARE, H_SWAP, H_SORTED, H_ACTIVE = range(5)

# Op types
COMPARE, SWAP, MARK_SORTED, SET = range(4)

PATTERN_NAMES = ["Random", "Reversed", "Nearly Sorted", "Few Unique", "Pipe Organ"]

# Highlight colors (C++ S_COMPARE/S_SWAP/S_ACTIVE/S_SORTED)
C_COMPARE = (40, 200, 100)   # green
C_SWAP = (255, 50, 50)       # red
C_ACTIVE = (80, 160, 255)    # blue
C_SORTED = (255, 200, 40)    # amber


# ── HSV value colours ───────────────────────────────────────────

def value_color(val, max_val):
    t = val / max_val if max_val > 0 else 0.0
    hue = t * 300.0
    h = math.fmod(hue, 360.0) / 60.0
    c = 0.9
    x = c * (1.0 - abs(math.fmod(h, 2.0) - 1.0))
    if h < 1:
        r, g, b = c, x, 0.0
    elif h < 2:
        r, g, b = x, c, 0.0
    elif h < 3:
        r, g, b = 0.0, c, x
    elif h < 4:
        r, g, b = 0.0, x, c
    elif h < 5:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (int(r * 235 + 20), int(g * 235 + 20), int(b * 235 + 20))


VAL_BAR = [value_color(i + 1, ARRAY_SIZE) for i in range(ARRAY_SIZE)]


def celeb_color(i):
    hue = i * 360.0 / CELEB_HUES
    h = math.fmod(hue, 360.0) / 60.0
    c = 1.0
    x = c * (1.0 - abs(math.fmod(h, 2.0) - 1.0))
    if h < 1:
        r, g, b = c, x, 0.0
    elif h < 2:
        r, g, b = x, c, 0.0
    elif h < 3:
        r, g, b = 0.0, c, x
    elif h < 4:
        r, g, b = 0.0, x, c
    elif h < 5:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (int(r * 255), int(g * 255), int(b * 255))


CELEB = [celeb_color(i) for i in range(CELEB_HUES)]


# ── Sort state + op replay engine ────────────────────────────────────────────

class SortState:
    __slots__ = ("name", "arr", "comparisons", "swaps", "done",
                 "celebration_frame", "highlight", "ops", "op_idx")

    def __init__(self):
        self.name = ""
        self.arr = []
        self.comparisons = 0
        self.swaps = 0
        self.done = False
        self.celebration_frame = 0
        self.highlight = []
        self.ops = []
        self.op_idx = 0

    def reset(self, base):
        self.arr = base[:]
        self.comparisons = 0
        self.swaps = 0
        self.done = False
        self.celebration_frame = 0
        self.highlight = [H_NONE] * len(base)
        self.ops = []
        self.op_idx = 0

    def step(self):
        hl = self.highlight
        for k in range(len(hl)):
            if hl[k] != H_SORTED:
                hl[k] = H_NONE
        if self.op_idx >= len(self.ops):
            if not self.done:
                self.done = True
                self.celebration_frame = 0
                for k in range(len(hl)):
                    hl[k] = H_SORTED
            return
        typ, i, j = self.ops[self.op_idx]
        self.op_idx += 1
        n = len(self.arr)
        if typ == COMPARE:
            self.comparisons += 1
            if 0 <= i < n:
                hl[i] = H_COMPARE
            if 0 <= j < n:
                hl[j] = H_COMPARE
        elif typ == SWAP:
            self.swaps += 1
            self.arr[i], self.arr[j] = self.arr[j], self.arr[i]
            hl[i] = H_SWAP
            hl[j] = H_SWAP
        elif typ == SET:
            self.arr[i] = j
            hl[i] = H_ACTIVE
        elif typ == MARK_SORTED:
            hl[i] = H_SORTED

    def progress(self):
        if self.done:
            return 1.0
        if not self.ops:
            return 0.0
        return self.op_idx / len(self.ops)


# ── Op-list generators (sort for real on a local copy, record the work) ──────

def gen_bubble(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            ops.append((COMPARE, j, j + 1))
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                ops.append((SWAP, j, j + 1))
                swapped = True
        ops.append((MARK_SORTED, n - 1 - i, 0))
        if not swapped:
            for k in range(n - 1 - i):
                ops.append((MARK_SORTED, k, 0))
            break
    if ops and ops[-1][0] != MARK_SORTED:
        ops.append((MARK_SORTED, 0, 0))
    return ops


def gen_selection(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    for i in range(n - 1):
        min_idx = i
        for j in range(i + 1, n):
            ops.append((COMPARE, min_idx, j))
            if a[j] < a[min_idx]:
                min_idx = j
        if min_idx != i:
            a[i], a[min_idx] = a[min_idx], a[i]
            ops.append((SWAP, i, min_idx))
        ops.append((MARK_SORTED, i, 0))
    ops.append((MARK_SORTED, n - 1, 0))
    return ops


def gen_insertion(s):
    a = s.arr[:]
    n = len(a)
    ops = [(MARK_SORTED, 0, 0)]
    for i in range(1, n):
        j = i
        while j > 0:
            ops.append((COMPARE, j - 1, j))
            if a[j - 1] > a[j]:
                a[j - 1], a[j] = a[j], a[j - 1]
                ops.append((SWAP, j - 1, j))
                j -= 1
            else:
                break
        ops.append((MARK_SORTED, i, 0))
    return ops


def gen_shell(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    for gap in (301, 132, 57, 23, 10, 4, 1):
        if gap >= n:
            continue
        for i in range(gap, n):
            j = i
            while j >= gap:
                ops.append((COMPARE, j - gap, j))
                if a[j - gap] > a[j]:
                    a[j - gap], a[j] = a[j], a[j - gap]
                    ops.append((SWAP, j - gap, j))
                    j -= gap
                else:
                    break
    for i in range(n):
        ops.append((MARK_SORTED, i, 0))
    return ops


def gen_quick(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo >= hi:
            if 0 <= lo < n:
                ops.append((MARK_SORTED, lo, 0))
            continue
        mid = lo + (hi - lo) // 2
        ops.append((COMPARE, lo, mid))
        if a[lo] > a[mid]:
            a[lo], a[mid] = a[mid], a[lo]
            ops.append((SWAP, lo, mid))
        ops.append((COMPARE, lo, hi))
        if a[lo] > a[hi]:
            a[lo], a[hi] = a[hi], a[lo]
            ops.append((SWAP, lo, hi))
        ops.append((COMPARE, mid, hi))
        if a[mid] > a[hi]:
            a[mid], a[hi] = a[hi], a[mid]
            ops.append((SWAP, mid, hi))
        pivot = a[hi]
        i = lo
        for j in range(lo, hi):
            ops.append((COMPARE, j, hi))
            if a[j] <= pivot:
                if i != j:
                    a[i], a[j] = a[j], a[i]
                    ops.append((SWAP, i, j))
                i += 1
        if i != hi:
            a[i], a[hi] = a[hi], a[i]
            ops.append((SWAP, i, hi))
        ops.append((MARK_SORTED, i, 0))
        if (i - 1 - lo) > (hi - i - 1):
            stack.append((lo, i - 1))
            stack.append((i + 1, hi))
        else:
            stack.append((i + 1, hi))
            stack.append((lo, i - 1))
    return ops


def gen_merge(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    width = 1
    while width < n:
        lo = 0
        while lo < n:
            mid = min(lo + width, n)
            hi = min(lo + 2 * width, n)
            tmp = []
            i, j = lo, mid
            while i < mid and j < hi:
                ops.append((COMPARE, i, j))
                if a[i] <= a[j]:
                    tmp.append(a[i]); i += 1
                else:
                    tmp.append(a[j]); j += 1
            while i < mid:
                tmp.append(a[i]); i += 1
            while j < hi:
                tmp.append(a[j]); j += 1
            for k in range(len(tmp)):
                if a[lo + k] != tmp[k]:
                    a[lo + k] = tmp[k]
                    ops.append((SET, lo + k, tmp[k]))
            lo += 2 * width
        width *= 2
    for i in range(n):
        ops.append((MARK_SORTED, i, 0))
    return ops


def gen_heap(s):
    a = s.arr[:]
    n = len(a)
    ops = []

    def sift_down(start, end):
        root = start
        while 2 * root + 1 <= end:
            child = 2 * root + 1
            sw = root
            ops.append((COMPARE, sw, child))
            if a[sw] < a[child]:
                sw = child
            if child + 1 <= end:
                ops.append((COMPARE, sw, child + 1))
                if a[sw] < a[child + 1]:
                    sw = child + 1
            if sw == root:
                break
            a[root], a[sw] = a[sw], a[root]
            ops.append((SWAP, root, sw))
            root = sw

    for start in range((n - 2) // 2, -1, -1):
        sift_down(start, n - 1)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        ops.append((SWAP, 0, end))
        ops.append((MARK_SORTED, end, 0))
        sift_down(0, end - 1)
    ops.append((MARK_SORTED, 0, 0))
    return ops


def gen_radix(s):
    a = s.arr[:]
    n = len(a)
    ops = []
    max_val = max(a) if a else 0
    exp = 1
    while max_val // exp > 0:
        output = [0] * n
        count = [0] * 10
        for i in range(n):
            ops.append((COMPARE, i, i))
            count[(a[i] // exp) % 10] += 1
        for i in range(1, 10):
            count[i] += count[i - 1]
        for i in range(n - 1, -1, -1):
            digit = (a[i] // exp) % 10
            output[count[digit] - 1] = a[i]
            count[digit] -= 1
        for i in range(n):
            if a[i] != output[i]:
                a[i] = output[i]
                ops.append((SET, i, output[i]))
        exp *= 10
    for i in range(n):
        ops.append((MARK_SORTED, i, 0))
    return ops


ALGOS = [
    ("Bubble Sort", gen_bubble),
    ("Selection Sort", gen_selection),
    ("Insertion Sort", gen_insertion),
    ("Shell Sort", gen_shell),
    ("Quick Sort", gen_quick),
    ("Merge Sort", gen_merge),
    ("Heap Sort", gen_heap),
    ("Radix Sort", gen_radix),
]


# ── Pattern generation ───────────────────────────────────────────────────────

def gen_pattern(pattern, size):
    base = list(range(1, size + 1))
    if pattern == 0:
        random.shuffle(base)
    elif pattern == 1:
        base.reverse()
    elif pattern == 2:
        for _ in range(size // 10):
            x = random.randrange(size)
            y = random.randrange(size)
            base[x], base[y] = base[y], base[x]
    elif pattern == 3:
        for i in range(size):
            base[i] = (i * 6 // size) * (size // 6) + size // 12
        random.shuffle(base)
    elif pattern == 4:
        for i in range(size):
            base[i] = (i * 2 + 1) if i < size // 2 else ((size - 1 - i) * 2 + 2)
    return base


class World:
    def __init__(self):
        self.sorts = [SortState() for _ in range(NUM_ALGOS)]
        self.solo = -1
        self.frame = 0
        self.ops_per_frame = 4
        self.pattern = 0
        self.paused = False
        self.start_time = time.monotonic()
        self.init_data()

    def init_data(self):
        base = gen_pattern(self.pattern, ARRAY_SIZE)
        for idx, (name, gen) in enumerate(ALGOS):
            st = self.sorts[idx]
            st.name = name
            st.reset(base)
            st.ops = gen(st)
        self.frame = 0
        self.start_time = time.monotonic()


W = World()


# ── Rendering ────────────────────────────────────────────────────────────────

def style_for_bar(val, hl, done, celeb_frame, bar_index):
    if done and 0 < celeb_frame <= CELEBRATION_FRAMES:
        wave = math.sin(bar_index * 0.2 - celeb_frame * 0.3)
        if wave > -0.3:
            hue_idx = (bar_index * 5 + celeb_frame * 7) % 360
            ci = hue_idx * CELEB_HUES // 360
            return CELEB[clampi(ci, 0, CELEB_HUES - 1)]
    if hl == H_COMPARE:
        return C_COMPARE
    if hl == H_SWAP:
        return C_SWAP
    if hl == H_ACTIVE:
        return C_ACTIVE
    if hl == H_SORTED:
        return C_SORTED
    return VAL_BAR[clampi(val - 1, 0, ARRAY_SIZE - 1)]


def panel_grid(st, pw, ph, max_val):
    """Half-block pixel grid (pw cells wide, ph cells tall) of the bars."""
    rows = ph
    bar_height = rows * 2
    px_h = bar_height
    n = len(st.arr)
    grid = [[None] * pw for _ in range(px_h)]
    bar_w_f = pw / n
    for i in range(n):
        bx = int(i * bar_w_f)
        bw = max(1, int((i + 1) * bar_w_f) - bx)
        val = st.arr[i]
        bh = max(1, int(val / max_val * bar_height))
        color = style_for_bar(val, st.highlight[i], st.done,
                              st.celebration_frame, i)
        for sub in range(bh):
            y = px_h - 1 - sub
            if 0 <= y < px_h:
                for dx in range(bw):
                    x = bx + dx
                    if x < pw:
                        grid[y][x] = color
    return halfblock(grid)


def panel(st, pw, ph, max_val):
    name = st.name
    title = (T(f" {name} ").fg((80, 255, 130)).bold if st.done
             else T(f" {name}").fg((170, 200, 255)).bold)
    if st.done:
        title = row(title, T("✔").fg((80, 255, 130)), gap=0)
    stats = T(f" cmp:{st.comparisons:<5} swp:{st.swaps:<5}").fg((90, 90, 110))
    pct = st.progress()
    bar_w = max(1, pw - 6)
    filled = int(pct * bar_w)
    prog = row(
        T("█" * filled).fg((80, 180, 255)),
        T("░" * (bar_w - filled)).fg((35, 35, 50)),
        T(f"{int(pct * 100):3d}%").fg((90, 90, 110)),
        gap=0,
    )
    body_h = max(1, ph)
    return col(
        title,
        stats,
        prog,
        component(lambda w, h: panel_grid(st, max(4, w), max(2, body_h), max_val),
                  grow=1),
        gap=0,
    )


# ── App ──────────────────────────────────────────────────────────────────────

app = App.fullscreen("sorting visualizer", fps=30)
app.state(_t=0.0)


@app.on("space")
def _restart(s):
    W.init_data()


@app.on("p")
def _pattern(s):
    W.pattern = (W.pattern + 1) % NUM_PATTERNS
    W.init_data()


@app.on("k")
def _pause(s):
    W.paused = not W.paused


@app.on("+", "=")
def _faster(s):
    W.ops_per_frame = min(50, W.ops_per_frame + 1)


@app.on("-")
def _slower(s):
    W.ops_per_frame = max(1, W.ops_per_frame - 1)


@app.on("right")
def _faster3(s):
    W.ops_per_frame = min(50, W.ops_per_frame + 3)


@app.on("left")
def _slower3(s):
    W.ops_per_frame = max(1, W.ops_per_frame - 3)


@app.on("up")
def _double(s):
    W.ops_per_frame = min(50, W.ops_per_frame * 2)


@app.on("down")
def _halve(s):
    W.ops_per_frame = max(1, W.ops_per_frame // 2)


for _d in range(1, 9):
    def _mk(d):
        def _solo(s):
            W.solo = -1 if W.solo == d - 1 else d - 1
        return _solo
    app.on(str(_d))(_mk(_d))


@app.on("0")
def _showall(s):
    W.solo = -1


app.quit_on("q", "esc")


@app.on_frame
def _frame(s, dt):
    W.frame += 1
    if not W.paused:
        for st in W.sorts:
            if not st.done:
                for _ in range(W.ops_per_frame):
                    st.step()
            elif st.celebration_frame <= CELEBRATION_FRAMES:
                st.celebration_frame += 1


@app.view
def view(s):
    max_val = ARRAY_SIZE
    if W.solo >= 0:
        st = W.sorts[W.solo]
        body = panel(st, 80, 24, max_val)
    else:
        # 4 columns x 2 rows
        cells = [panel(W.sorts[i], 20, 10, max_val) for i in range(NUM_ALGOS)]
        top = row(*[col(c) for c in cells[:4]], gap=1)
        bottom = row(*[col(c) for c in cells[4:]], gap=1)
        body = col(top, bottom, gap=1)

    elapsed = time.monotonic() - W.start_time
    mins = int(elapsed) // 60
    secs = int(elapsed) % 60
    status = row(
        T(" [space] restart  [p] pattern  [←→] speed  "
          f"[k] {'resume' if W.paused else 'pause'}  [1-8] solo  [q] quit")
        .fg((130, 130, 160)),
        T("  SORTING VISUALIZER ").fg((255, 180, 60)).bold,
        gap=0,
    )
    status2 = row(
        T(f" Speed: {W.ops_per_frame}x").fg((100, 220, 255)).bold,
        T(f"  Pattern: {PATTERN_NAMES[W.pattern]}").fg((200, 200, 220)),
        T("  ⏸ PAUSED" if W.paused else "").fg((255, 180, 60)).bold,
        T(f"   {mins}:{secs:02d}").fg((90, 90, 110)),
        gap=0,
    )
    return col(body, status, status2, gap=0)


if __name__ == "__main__":
    app.run()
