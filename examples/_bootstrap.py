"""Path bootstrap for running examples straight from a source checkout.

Importing this (``import _bootstrap``) puts the examples directory and the
in-tree ``src/`` on ``sys.path``, so ``from maya_py import ...`` resolves
against the local build and examples can import each other. Every example
used to spell this as a two-line ``sys.path.insert`` dance; this is that, once.

No-op when maya_py is already importable (e.g. installed).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "..", "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
