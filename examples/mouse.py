"""Mouse input + the runtime capture toggle.

maya gives you mouse events in *frame-relative* coordinates — a click on the
top-left of this card reports near (1, 1) whether the app is inline (drawn
partway down the terminal) or fullscreen, and clicks outside the card are
ignored.

The catch: while mouse capture is ON, the terminal hands the scroll wheel to
the app, so you can't scroll the terminal's own scrollback. Press `m` to toggle
capture off (wheel goes back to the terminal) and on again.

    click / drag   → reported below (when capture is ON)
    m              → toggle mouse capture
    r              → reset
    q / Esc        → quit
"""
from maya_py import (
    App, card, col, row, b, c, dim_text, badge, mouse_pos, mouse_button, mouse_kind,
)

app = App("mouse", pos="—", btn="—", kind="—", clicks=0, quit_keys=("q", "esc"))


@app.on("m")
def toggle(s):
    app.set_mouse(not app.mouse_active)


@app.on("r")
def reset(s):
    s.pos, s.btn, s.kind, s.clicks = "—", "—", "—", 0


@app.on_mouse
def on_mouse(s, ev):
    p = mouse_pos(ev)
    if p:
        s.pos = f"col {p[0]}, row {p[1]}"
    bt, kd = mouse_button(ev), mouse_kind(ev)
    if bt is not None:
        s.btn = str(bt).split(".")[-1]      # "MouseButton.Left" -> "Left"
    if kd is not None:
        s.kind = str(kd).split(".")[-1]


@app.on_click()
def on_click(s, col_, row_):
    s.clicks += 1


@app.view
def view(s):
    on = app.mouse_active
    chip = badge("CAPTURE ON", kind="success") if on else badge("CAPTURE OFF", kind="warning")
    note = (dim_text("terminal scroll is disabled — press m to release the wheel")
            if on else
            c("terminal scrollback works now — press m to capture clicks again", "lime"))
    return card(
        col(
            row(b("Mouse").fg("sky"), chip, gap=2),
            dim_text(""),
            row("position:", c(s.pos, "gold"), gap=1),
            row("button:  ", c(s.btn, "gold"), gap=1),
            row("kind:    ", c(s.kind, "gold"), gap=1),
            row("clicks:  ", c(str(s.clicks), "gold"), gap=1),
            dim_text(""),
            note,
            dim_text("m toggle · r reset · q quit"),
            gap=0,
        ),
        title="mouse",
        pad=1,
    )


if __name__ == "__main__":
    app.run()
