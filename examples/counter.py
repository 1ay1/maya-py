"""Interactive counter — the App API. No event-loop boilerplate.

  +/=  increment    -  decrement    r  reset    q/Esc  quit
"""
from maya_py import App, card, b, dim_text

app = App("counter", inline=True)
app.state(n=0)


@app.on("+", "=")
def inc(s):
    s.n += 1


@app.on("-")
def dec(s):
    s.n -= 1


@app.on("r")
def reset(s):
    s.n = 0


@app.on("q", "esc")
def quit_(s):
    app.stop()


@app.view
def view(s):
    return card(
        b(f"Count: {s.n}").fg("sky"),
        dim_text("+/- change   r reset   q quit"),
        title="counter",
    )


app.run()
