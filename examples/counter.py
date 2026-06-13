"""Interactive counter — the App API. No event-loop boilerplate.

  +/=  increment    -  decrement    r  reset    q/Esc  quit
"""
from maya_py import App, card, b, dim_text

# State goes straight in the constructor; quit_keys auto-binds q/Esc to quit.
app = App("counter", n=0, quit_keys=("q", "esc"))


@app.on("+", "=")
def inc(s):
    s.n += 1


@app.on("-")
def dec(s):
    s.n -= 1


@app.on("r")
def reset(s):
    s.n = 0


@app.view
def view(s):
    return card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("+/- change   r reset   q quit"),
        title="counter",
    )


app.run()
