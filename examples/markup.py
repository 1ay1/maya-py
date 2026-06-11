"""markup.py — the markdown renderer + scrollable viewer.

maya's ``markdown()`` widget renders GFM (headings, emphasis, lists, tables,
blockquotes, fenced code, links) to a real Element tree through the same C++
engine maya uses for agent output. Here we render a four-panel document and
let you scroll it.

  --dump   one-shot colored dump to stdout (pipe to `less -R`)
  default  interactive scrollable viewer · ↑↓/PgUp/PgDn/Home/End · q quit

    PYTHONPATH=src python examples/markup.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import (App, col, card, b, dim_text, T, markdown, divider,
                     scroll_state, viewport, scrollbar)

DOC1 = """\
# maya markdown

A **fast** CommonMark + GFM renderer. *Emphasis*, **strong**, `inline code`,
and [links](https://example.com) all render inline.

## Lists

- nested
  - loose and tight
  - with `code`
- ordered too:

1. first
2. second
3. third

> Blockquotes carry a left rule and a dim tint, and they can span
> multiple lines without losing the bar.
"""

DOC2 = """\
## Tables

| Service | Status   | p99 ms |
|---------|:--------:|-------:|
| api     | ok       |     42 |
| worker  | ok       |    118 |
| cache   | degraded |      7 |

## Code

```python
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

That fenced block keeps its own background and monospaced run styling.
"""

DOC3 = """\
## Headings cascade

### Level three
#### Level four

Each level steps the colour + weight. Horizontal rules:

---

Mix **bold _and italic_** runs, ~~strikethrough~~, and `code` in one line to
prove the inline parser composes styles correctly.
"""


def document():
    return col(
        card(markdown(DOC1), title="commonmark + gfm", pad=1),
        card(markdown(DOC2), title="tables + code", pad=1),
        card(markdown(DOC3), title="headings + inline", pad=1),
        gap=1,
    )


def dump():
    maya.print(document())


app = App("markup", inline=True)
s = scroll_state()
app.state(s=s)


@app.on("q", "esc")
def _quit(st): app.stop()


@app.view
def view(st):
    return card(
        col(b("markdown viewer").fg("sky"),
            dim_text("↑↓ scroll · PgUp/PgDn page · Home/End jump · q quit")),
        maya.row(
            viewport(document(), st.s, height=20, grow=1),
            scrollbar(st.s, 20, style="neon", thumb_color="sky"),
            gap=1,
        ),
        title="markup", gap=1,
    )


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    else:
        app.run()
