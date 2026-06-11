"""Static styled output — render a card to the terminal and exit."""
import maya_py as maya

card = maya.box(
    maya.vstack(
        maya.text("maya-py", maya.bold | maya.fg(100, 180, 255)),
        maya.blank(),
        maya.hstack(
            maya.text("Status:", maya.dim),
            maya.text("Online", maya.bold | maya.fg(80, 220, 120)),
            gap=1,
        ),
        maya.hstack(
            maya.text("Region:", maya.dim),
            maya.text("us-east-1", maya.fg(0xFFAA33)),
            gap=1,
        ),
    ),
    border=maya.Round,
    border_color=maya.rgb(80, 90, 110),
    border_text=" service ",
    padding=(1, 2),
)

maya.print(card)
