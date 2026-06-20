"""markup.py — the markdown engine + an HTML-flavoured viewer, scrollable.

A faithful port of maya's ``examples/markup.cpp``. An interactive, scrollable
viewer of four full-width panels:

  1. CommonMark + GFM: headings, emphasis, nested loose/tight lists, a table,
     a blockquote, a fenced code block, links/autolinks.
  2. Inline HTML in markdown: <b>/<i>/<kbd>/<mark>/<sub>/<sup>/<code>/<a>/<br>
     styled runs.
  3. A raw HTML *block* in markdown — a table and a details/summary.
  4. A standalone HTML fragment: heading, phrasing, lists, blockquote, pre,
     rule and a table.

ADAPTATION NOTE: maya-py exports a native ``markdown(source)`` widget but does
NOT export a standalone ``html()`` widget (maya's C++ has ``html::render``).
Per the project rule never to hand-roll a widget renderer in Python, panels 2-4
— which in the C++ exercise maya's HTML paths — are rendered here through the
native ``markdown()`` widget using equivalent markdown/HTML-in-markdown source.
maya's markdown engine itself interprets inline HTML and raw HTML blocks, so
panels 2 and 3 still drive the HTML code paths faithfully; panel 4's standalone
fragment is expressed as its closest markdown equivalent.

Scrolling uses maya-py's native scroll: the four panels are composed once into
a single content column and shown through a ``viewport`` with a live
``scrollbar``. Arrow keys / PgUp / PgDn / Home / End and the mouse wheel are
auto-dispatched by maya to the on-screen scroll state.

  Keys: ↑/↓ scroll · PgUp/PgDn page · Home/End jump · q/Esc quit.

    PYTHONPATH=src python examples/markup.py
    PYTHONPATH=src python examples/markup.py --dump   # one-shot dump to stdout
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, markdown, viewport, scrollbar, scroll_state,
    to_string,
)


# ── content ──────────────────────────────────────────────────────────────────

K_MARKDOWN = """\
# maya markdown

Supports **bold**, *italic*, ***both***, `inline code`,
[links](https://example.com) and autolinks <https://maya.dev>.

Tight list:
- alpha
- beta
  - nested gamma
  - nested delta

Loose list (blank lines between items):

1. first paragraph

2. second paragraph

> Block quotes nest and stay tight,
> across soft-wrapped lines.

| Feature   | State |
|-----------|:-----:|
| CommonMark| 100%  |
| GFM tables| yes   |

```cpp
auto ui = maya::markdown(source);
```
"""

# Inline HTML interpreted by maya's markdown engine.
K_INLINE_HTML = (
    "Inline HTML is interpreted: <b>bold</b>, <i>italic</i>, "
    "<u>underline</u>, <mark>highlight</mark>, <code>code()</code>, "
    "press <kbd>Ctrl</kbd>+<kbd>C</kbd>, H<sub>2</sub>O, e=mc<sup>2</sup>, "
    'a <a href="https://maya.dev">styled link</a>.<br>'
    "A &lt;br&gt; above forced this new line &mdash; entities decode too."
)

# A raw HTML *block* inside markdown — parsed and rendered, not literal tags.
K_BLOCK_HTML = """\
A raw HTML block in markdown:

<table>
  <tr><th>Lang</th><th>Speed</th></tr>
  <tr><td>C++</td><td>fast</td></tr>
  <tr><td>maya</td><td>faster</td></tr>
</table>

<details>
  <summary>Click to expand</summary>
  <p>Hidden content rendered inline, with a <b>bold</b> word.</p>
</details>
"""

# Panel 4: in maya's C++ this is the standalone ``html::render`` widget. maya-py
# has no standalone html() widget, so we express the same fragment as its
# closest markdown equivalent fed through the native markdown() widget.
K_HTML_DOC = """\
# maya::html

A standalone widget: tokenizer → DOM → Element, built on the maya DSL.
Whitespace collapses like a browser.

## Phrasing

**bold**, *em*, ~~strike~~, `code`, <kbd>Esc</kbd>,
[link](/x).

- unordered one
- unordered two
  5. nested five
  6. nested six

> Block quotes get a gutter bar.

```
preformatted
  whitespace   preserved
```

---

| Col A | Col B |
|-------|-------|
| 1     | two   |
| three | 4     |
"""


def panel(title, body):
    """A titled, round-bordered panel that stretches to full width."""
    return card(
        T(title).bold.fg((0x7D, 0xCF, 0xFF)),
        body,
        border_color=(0x3B, 0x42, 0x61),
        pad=(0, 1),
        gap=1,
    )


def build_doc():
    return col(
        panel("1 · CommonMark + GFM", markdown(K_MARKDOWN)),
        panel("2 · Inline HTML in markdown", markdown(K_INLINE_HTML)),
        panel("3 · HTML block in markdown", markdown(K_BLOCK_HTML)),
        panel("4 · Standalone html::render (markdown equivalent)",
              markdown(K_HTML_DOC)),
        gap=1,
    )


def dump():
    """One-shot colored dump to stdout (pipe to ``less -R``)."""
    width = 80
    try:
        width = max(40, os.get_terminal_size().columns)
    except OSError:
        width = 80
    sys.stdout.write(to_string(build_doc(), width))
    sys.stdout.write("\n")
    sys.stdout.flush()


# ── viewer ───────────────────────────────────────────────────────────────────

DOC = build_doc()

app = App.fullscreen("markup", mouse=True)
s = scroll_state()            # auto_dispatch on — wheel + arrows just work
s.step_y = 1
app.state(s=s, vh=20)


@app.on("q", "esc")
def _quit(st):
    app.stop()


@app.view
def view(st):
    vh = st.vh
    total = st.s.max_y + vh
    start = st.s.y
    status = f"lines {start + 1}–{min(start + vh, total)} / {total}"
    return col(
        T("maya markup — CommonMark + GFM + HTML widget").bold.fg((125, 207, 255)),
        T("↑/↓ PgUp/PgDn Home/End scroll · q quit").dim,
        row(
            viewport(DOC, st.s, height=vh, grow=1),
            scrollbar(st.s, vh, thumb_color=(0xE0, 0xAF, 0x68)),
            gap=0,
        ),
        T(status).fg((0xE0, 0xAF, 0x68)),
        gap=0,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        dump()
    else:
        app.run()
