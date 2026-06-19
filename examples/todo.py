"""A tiny todo app — the whole thing is the UI, nothing is plumbing.

State is a plain object with methods; keys bind straight to them; the view is
one declarative expression. Conditional styling lives inline (`.opt`, `.fg(...
if ... else None)`), so there's no breaking out into `if` branches.

  ↑/↓  move    space  toggle    q/Esc  quit
"""
from maya_py import App, card, For, row, T, memo


class Todo:
    def __init__(self):
        self.items = [("Buy milk", False), ("Write code", True),
                      ("Ship it", False), ("Sleep", False)]
        self.cursor = 0

    def move(self, d):
        self.cursor = (self.cursor + d) % len(self.items)

    def toggle(self):
        text, done = self.items[self.cursor]
        self.items[self.cursor] = (text, not done)


@memo
def todo_row(text, done, focused):
    return row(
        T("›" if focused else " ").fg("sky"),
        T("[x]" if done else "[ ]").fg("green" if done else "slate"),
        T(text).fg("sky" if focused else None).opt(dim=done, strike=done),
        gap=1,
    )


app = App(
    "todo", inline=True, quit_keys=("q", "esc"), model=Todo(),
    keys={
        "up":    lambda s: s.move(-1),
        "down":  lambda s: s.move(+1),
        "space": lambda s: s.toggle(),
        "enter": lambda s: s.toggle(),
    },
)


@app.view
def view(s):
    # For(...) maps the list into rows declaratively — note the two-param
    # renderer gets (index, item) so it can highlight the cursor row.
    return card(
        T("Todo").bold.fg("gold"),
        For(s.items, lambda i, it: todo_row(it[0], it[1], i == s.cursor)),
        T("↑/↓ move · space toggle · q quit").dim,
        title="todo",
        gap=0,
    )


app.run()
