"""Static styled output — the easy API. Run: python examples/hello.py"""
import maya_py as maya
from maya_py import card, row, field, b, c, hr, T

dashboard = card(
    b("maya-py").fg("sky"),
    hr(34),
    field("Status", "Online", value_color="green"),
    field("Region", T("us-east-1").fg("gold")),
    field("Uptime", "14d 6h"),
    hr(34),
    row(c("● ok", "green"), "   ", c("▲ warn", "orange"), "   ", c("✕ err", "red")),
    title="service",
)

maya.show(dashboard)
