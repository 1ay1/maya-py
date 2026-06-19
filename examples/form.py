"""form — the declarative trio: For, bind, and @app.derive.

A tiny shopping cart. Nothing here is plumbing:

  • @app.derive   exposes `total` as a computed field — the view reads s.total
                  like any attribute; it's recomputed on access, never stale.
  • bind=(s, ...) wires the name field straight to state — the view reads
                  s.name directly, never widget.value.
  • For(...)      maps the item list into rows declaratively (SwiftUI ForEach
                  / JSX map), and a two-param renderer gets (index, item).

  type  edit name    q/Esc  quit
"""
from maya_py import App, text_input, card, col, row, For, T

app = App(
    "form", inline=True, quit_keys=("esc",),
    items=[("Pen", 2.0), ("Notebook", 4.5), ("Mug", 9.5)],
    name="",
)


# A computed field — no recompute boilerplate, no cache to invalidate.
@app.derive
def total(s):
    return sum(price for _, price in s.items)


# Two-way binding: keystrokes flow into s.name; the view reads s.name.
name = text_input("your name…", bind=(app.s, "name"))
app.focus(name)


def line(i, item):
    label, price = item
    return row(
        T(f"{i + 1}.").dim,
        T(label).fg("sky"),
        T(f"${price:.2f}").fg("green"),
        gap=2,
    )


@app.view
def view(s):
    greet = f"hello {s.name}" if s.name else "who's shopping?"
    return card(
        T("Cart").bold.fg("gold"),
        For(s.items, line),                       # declarative list
        T("─" * 22).fg("slate"),
        row(T("Total").dim, T(f"${s.total:.2f}").bold.fg("green"), gap=2),
        col(T("Name").dim, name),
        T(greet).fg("pink"),
        title="form",
        gap=1,
    )


app.run()
