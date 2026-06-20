"""agent.py — a simulated Claude-Code-style agent session.

Walks a realistic conversation flow: user prompt → thinking block → tool
calls (read / edit / bash) → a todo plan → a streaming markdown answer →
summary. Press space to advance / speed up; the whole thing showcases maya's
agent-UX widgets (thinking, todo_list, file_ref, inline_diff, markdown,
model_badge, badges).

  space advance / speed up · r restart · q/esc quit

    PYTHONPATH=src python examples/agent.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, row, card, b, dim_text, T, badge, divider,
                     thinking, todo_list, file_ref, inline_diff, markdown,
                     model_badge, spinner)

PROMPT = "Add a --json flag to the export command and update the tests."

ANSWER = """\
Done. I added the `--json` flag to `export`:

- **cli.py** — registered `--json` (mutually exclusive with `--csv`)
- **export.py** — branch to `json.dumps(rows, indent=2)` when set
- **test_export.py** — added `test_export_json` asserting valid JSON output

All **18 tests pass**. The flag defaults to off, so existing CSV behaviour is
unchanged.
"""

# phases of the simulation
PH_THINK, PH_READ, PH_EDIT, PH_PLAN, PH_BASH, PH_STREAM, PH_DONE = range(7)

app = App.inline("agent", fps=20)
app.state(phase=PH_THINK, t=0.0, reveal=0, started=0.0)
app.s.started = time.time()


def reset(st):
    st.phase = PH_THINK
    st.t = 0.0
    st.reveal = 0
    st.started = time.time()


@app.on("space")
def _adv(st):
    if st.phase == PH_STREAM:
        st.reveal = len(ANSWER)            # finish streaming instantly
    elif st.phase < PH_DONE:
        st.phase += 1
        st.t = 0.0


@app.on("r")
def _restart(st): reset(st)


app.quit_on("q", "esc")


def todo_state(phase):
    def st_for(after):
        return "completed" if phase > after else (
            "in_progress" if phase == after else "pending")
    return [
        ("read export.py + cli.py", st_for(PH_READ)),
        ("add --json flag to cli", st_for(PH_EDIT)),
        ("branch on json in export", st_for(PH_EDIT)),
        ("add test_export_json", st_for(PH_PLAN)),
        ("run the test suite", st_for(PH_BASH)),
    ]


def transcript(st):
    blocks = [
        # user turn
        card(row(T(" you ").bg("slate").fg("white"), dim_text("now"), gap=1),
             T(PROMPT).fg("white"), pad=1, border="round", border_color="sky"),
    ]
    # thinking
    active = st.phase == PH_THINK
    blocks.append(thinking(
        "The export command lives in export.py and is wired in cli.py. I'll "
        "add a --json flag, branch the formatter, then add a test.",
        active=active, expanded=True, max_lines=3))

    if st.phase >= PH_READ:
        blocks.append(card(
            row(badge("read", kind="tool"), file_ref("src/export.py"),
                T("✓").fg("lime") if st.phase > PH_READ else spinner(), gap=1),
            dim_text("42 lines · format_rows(), to_csv()"),
            pad=1, border="round", border_color="slate"))

    if st.phase >= PH_EDIT:
        blocks.append(card(
            row(badge("edit", kind="tool"), file_ref("src/cli.py", line=31),
                T("✓").fg("lime"), gap=1),
            inline_diff('parser.add_argument("--csv")',
                        'parser.add_argument("--csv")\nparser.add_argument("--json")',
                        label="cli.py"),
            pad=1, border="round", border_color="slate"))

    if st.phase >= PH_PLAN:
        blocks.append(card(
            todo_list(todo_state(st.phase), description="implementation plan",
                      status="done" if st.phase >= PH_DONE else "running",
                      elapsed=time.time() - st.started),
            pad=0, border="none"))

    if st.phase >= PH_BASH:
        ok = st.phase > PH_BASH or st.phase == PH_DONE
        blocks.append(card(
            row(badge("bash", kind="tool"), T("pytest -q").fg("white"),
                T("✓").fg("lime") if ok else spinner(), gap=1),
            T("18 passed in 0.42s").fg("lime") if ok else dim_text("running…"),
            pad=1, border="round", border_color="slate"))

    if st.phase >= PH_STREAM:
        shown = ANSWER[:st.reveal] if st.phase == PH_STREAM else ANSWER
        caret = "▏" if st.phase == PH_STREAM and st.reveal < len(ANSWER) else ""
        blocks.append(card(
            row(model_badge("Opus 4.8", compact=True),
                badge("assistant", kind="info"), gap=1),
            markdown(shown + caret),
            pad=1, border="round", border_color="sky"))

    return col(*blocks, gap=1)


@app.view
def view(st):
    st.t += 0.05
    # auto-advance phases on a timer
    if st.phase < PH_STREAM and st.t > 1.6:
        st.phase += 1
        st.t = 0.0
    if st.phase == PH_STREAM:
        st.reveal = min(len(ANSWER), st.reveal + 3)
        if st.reveal >= len(ANSWER) and st.t > 1.2:
            st.phase = PH_DONE

    names = {PH_THINK: "thinking", PH_READ: "reading", PH_EDIT: "editing",
             PH_PLAN: "planning", PH_BASH: "running tests",
             PH_STREAM: "responding", PH_DONE: "done"}
    busy = st.phase != PH_DONE
    return card(
        row(b("✦ agent session").fg("sky"),
            row(spinner() if busy else T("✓").fg("lime"),
                dim_text(names[st.phase]), gap=1),
            badge("DONE", kind="success") if not busy
            else badge("WORKING", kind="info"),
            justify="between"),
        transcript(st),
        dim_text("space advance/skip · r restart · q quit"),
        title="agent", gap=1,
    )


if __name__ == "__main__":
    app.run()
