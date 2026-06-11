"""markup.py — the markdown renderer rendered inline.

maya's ``markdown()`` widget renders GFM (headings, emphasis, lists, tables,
blockquotes, fenced code, links) to a real Element tree through the same C++
engine maya uses for agent output. Here we render a four-panel document; in
inline mode it flows into the terminal's own scrollback (scroll with your
terminal). Pipe to `less -R` to page through.

    PYTHONPATH=src python examples/markup.py
    PYTHONPATH=src python examples/markup.py | less -R
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import maya_py as maya
from maya_py import col, card, b, dim_text, T, markdown, divider

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


if __name__ == "__main__":
    # Inline mode: the document flows into the terminal's own scrollback —
    # scroll with your terminal, no in-app viewport. (`--dump` is identical;
    # kept for piping to `less -R`.)
    dump()
