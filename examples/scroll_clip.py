"""scroll_clip.py — first-class vertical scrolling via the framework primitive.

`viewport(content, state, height=)` wraps any element into an overflow-hidden
window; the renderer translates it by -scroll_y at paint and writes max_y back
so clamping is automatic. Scrolling "just works" with no handler code — the run
loop auto-forwards ↑↓/PgUp/PgDn/Home/End and the wheel to every scroll state.

  ↑↓ row · PgUp/PgDn page · Home/End jump · q quit

    PYTHONPATH=src python examples/scroll_clip.py
"""


import _bootstrap  # noqa: F401,E402

import maya_py as maya
from maya_py import (App, col, row, card, b, T, dim_text,
                     scroll_state, viewport, scrollbar)

LANG = ["python", "rust", "go", "zig", "ocaml", "haskell", "elixir", "c++",
        "typescript", "lua", "ruby", "swift", "kotlin", "scala", "clojure",
        "nim", "crystal", "julia", "erlang", "fsharp", "dart", "perl"]


def content():
    rows = []
    for i in range(80):
        lang = LANG[i % len(LANG)]
        rows.append(row(
            T(f"{i:>3}").fg("slate"),
            T(f"line of {lang}").fg("sky" if i % 5 else "lime"),
            dim_text(f"· entry #{i}"),
            gap=1,
        ))
    return col(*rows, gap=0)


app = App.inline("scroll_clip", mouse=True)
s = scroll_state()
app.state(s=s)


app.quit_on("q", "esc")


@app.view
def view(st):
    return card(
        b("vertical clip-scroll").fg("sky"),
        row(
            viewport(content(), st.s, height=18, grow=1),
            scrollbar(st.s, 18, style="neon", thumb_color="sky"),
            gap=1,
        ),
        dim_text(f"y {st.s.y}/{st.s.max_y} · ↑↓ scroll · q quit"),
        title="scroll_clip", gap=1,
    )


if __name__ == "__main__":
    app.run()
