"""A tiny menu app — arrow keys + enter, built with the App API.

  ↑/↓  move    space  toggle    q  quit
"""
from maya_py import App, card, row, col, T, b, dim_text, c

app = App("todo", inline=True)
app.state(
    items=["Buy milk", "Write code", "Ship it", "Sleep"],
    done=[False, True, False, False],
    cursor=0,
)


@app.on("up")
def up(s):
    s.cursor = (s.cursor - 1) % len(s.items)


@app.on("down")
def down(s):
    s.cursor = (s.cursor + 1) % len(s.items)


@app.on("space", "enter")
def toggle(s):
    s.done[s.cursor] = not s.done[s.cursor]


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    rows = []
    for idx, (text, done) in enumerate(zip(s.items, s.done)):
        mark = c("[x]", "green") if done else dim_text("[ ]")
        label = T(text)
        if done:
            label = label.dim.strike
        if idx == s.cursor:
            label = T(text).fg("sky").bold
            rows.append(row(c("›", "sky"), mark, label, gap=1))
        else:
            rows.append(row(" ", mark, label, gap=1))
    return card(
        b("Todo").fg("gold"),
        col(*rows),
        dim_text("↑/↓ move   space toggle   q quit"),
        title="todo",
        gap=0,
    )


app.run()
