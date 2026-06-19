"""login — interactive text input with focus.

Two real maya `Input` widgets hosted in Python: type into them, Tab between
them, Enter on the password submits. This is the keystone 0.2.0 feature —
interactive widgets compose in Python exactly like in C++.

  Tab / Shift-Tab  switch field    Enter  submit    Esc  quit
"""
from maya_py import App, text_input, card, col, row, b, dim_text, T

app = App("login", submitted=None, user="", passwd="")

# bind=(state, field) wires each input straight to a state field — the view
# reads s.user / s.passwd directly and never touches widget.value.
user = text_input("username", bind=(app.s, "user"))
pw = text_input("password", password=True, bind=(app.s, "passwd"))
app.focus(user, pw)          # user is focused first; Tab moves to pw


@pw.on_submit
def submit(_text):
    app.s.submitted = app.s.user


@app.on("esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    if s.submitted is not None:
        return card(b(f"Welcome, {s.submitted}!").fg("green"), title="login")
    return card(
        col(
            row(T("user ").fg("slate"), user),
            row(T("pass ").fg("slate"), pw),
            dim_text("Tab to switch · Enter to submit · Esc to quit"),
            gap=1,
        ),
        title="login",
    )


app.run()
