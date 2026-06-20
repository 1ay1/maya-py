"""agent_session.py — an auto-piloted, multi-scenario agent session demo.

Like agent.py but it drives itself end-to-end with NO input, cycling through
several Claude-Code-style scenarios forever (great for recordings). Each
scenario streams thinking → tool calls → a todo plan → a markdown answer, then
resets to the next. Type nothing; just watch. Press q/Esc/Ctrl-C to quit.

  space skip current stream · n next scenario · q/esc quit

    PYTHONPATH=src python examples/agent_session.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, divider,
                     thinking, todo_list, file_ref, inline_diff, markdown,
                     model_badge, spinner)

SCENARIOS = [
    {
        "prompt": "Add a --json flag to the export command and update tests.",
        "think": "export lives in export.py, wired in cli.py. Add the flag, "
                 "branch the formatter, add a test.",
        "tool": ("edit", "src/cli.py", 31,
                 'parser.add_argument("--csv")',
                 'parser.add_argument("--csv")\nparser.add_argument("--json")'),
        "todos": ["read export.py", "add --json flag", "branch formatter",
                  "add test_export_json", "run tests"],
        "answer": "Done — added `--json` to `export`. **18 tests pass**, CSV "
                  "behaviour unchanged.",
    },
    {
        "prompt": "The dashboard gauge shows the wrong colour above 80%.",
        "think": "gauge() colour is hard-coded. I'll thread a threshold so it "
                 "turns red past 0.8.",
        "tool": ("edit", "src/widgets.py", 88,
                 'color = "green"',
                 'color = "red" if v > 0.8 else "green"'),
        "todos": ["locate gauge render", "add threshold branch",
                  "snapshot test the colour"],
        "answer": "Fixed. The gauge now flips to **red** above 80%. Added a "
                  "snapshot test covering 0.79 / 0.81.",
    },
    {
        "prompt": "Cache the expensive layout pass; it's re-running every frame.",
        "think": "layout() is pure in (w, content). Memoise on a content hash "
                 "so unchanged frames are a cache hit.",
        "tool": ("edit", "src/render.py", 142,
                 'tree = layout(w, content)',
                 'tree = _cache.get(key) or layout(w, content)'),
        "todos": ["profile the hot path", "add an LRU keyed on (w, hash)",
                  "verify flat per-frame cost"],
        "answer": "Cached. Per-frame layout went from **~9 ms to ~0.1 ms** on "
                  "the bench; the cache is keyed on `(width, content_hash)`.",
    },
]

PH_THINK, PH_TOOL, PH_PLAN, PH_STREAM, PH_HOLD = range(5)

app = App.inline("agent_session", fps=20)
app.state(sc=0, phase=PH_THINK, t=0.0, reveal=0, started=0.0)
app.s.started = time.time()


def _begin(st):
    st.phase = PH_THINK
    st.t = 0.0
    st.reveal = 0
    st.started = time.time()


@app.on("space")
def _skip(st):
    if st.phase == PH_STREAM:
        st.reveal = len(SCENARIOS[st.sc]["answer"])


@app.on("n")
def _next(st):
    st.sc = (st.sc + 1) % len(SCENARIOS)
    _begin(st)


@app.on("q", "esc")
def _quit(st): app.stop()


def todo_state(sc, phase):
    items = SCENARIOS[sc]["todos"]
    out = []
    for i, label in enumerate(items):
        if phase > PH_PLAN:
            st = "completed"
        elif phase == PH_PLAN:
            st = "in_progress" if i == 0 else "pending"
        else:
            st = "pending"
        out.append((label, st))
    return out


def transcript(st):
    sc = SCENARIOS[st.sc]
    blocks = [
        card(row(T(" you ").bg("slate").fg("white"), dim_text("now"), gap=1),
             T(sc["prompt"]).fg("white"), pad=1, border="round",
             border_color="sky"),
        thinking(sc["think"], active=st.phase == PH_THINK, expanded=True,
                 max_lines=3),
    ]
    if st.phase >= PH_TOOL:
        kind, path, line, before, after = sc["tool"]
        done = st.phase > PH_TOOL
        blocks.append(card(
            row(badge(kind, kind="tool"), file_ref(path, line=line),
                T("✓").fg("lime") if done else spinner(), gap=1),
            inline_diff(before, after, label=os.path.basename(path)),
            pad=1, border="round", border_color="slate"))
    if st.phase >= PH_PLAN:
        blocks.append(todo_list(
            todo_state(st.sc, st.phase), description="plan",
            status="done" if st.phase > PH_PLAN else "running",
            elapsed=time.time() - st.started))
    if st.phase >= PH_STREAM:
        ans = sc["answer"]
        shown = ans[:st.reveal] if st.phase == PH_STREAM else ans
        caret = "▏" if st.phase == PH_STREAM and st.reveal < len(ans) else ""
        blocks.append(card(
            row(model_badge("Opus 4.8", compact=True),
                badge("assistant", kind="info"), gap=1),
            markdown(shown + caret), pad=1, border="round",
            border_color="sky"))
    return col(*blocks, gap=1)


@app.view
def view(st):
    st.t += 0.05
    sc = SCENARIOS[st.sc]
    # auto-pilot
    if st.phase < PH_STREAM and st.t > 1.4:
        st.phase += 1
        st.t = 0.0
    elif st.phase == PH_STREAM:
        st.reveal = min(len(sc["answer"]), st.reveal + 2)
        if st.reveal >= len(sc["answer"]) and st.t > 1.5:
            st.phase = PH_HOLD
            st.t = 0.0
    elif st.phase == PH_HOLD and st.t > 1.8:
        st.sc = (st.sc + 1) % len(SCENARIOS)
        _begin(st)

    busy = st.phase != PH_HOLD
    names = {PH_THINK: "thinking", PH_TOOL: "editing", PH_PLAN: "planning",
             PH_STREAM: "responding", PH_HOLD: "done"}
    return card(
        row(b("✦ agent session").fg("sky"),
            dim_text(f"scenario {st.sc + 1}/{len(SCENARIOS)} · auto-pilot"),
            row(spinner() if busy else T("✓").fg("lime"),
                dim_text(names[st.phase]), gap=1),
            justify="between"),
        transcript(st),
        dim_text("auto-cycling · space skip · n next · q quit"),
        title="agent_session", gap=1,
    )


if __name__ == "__main__":
    app.run()
