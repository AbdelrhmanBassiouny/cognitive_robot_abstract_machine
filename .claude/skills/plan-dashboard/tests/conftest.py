"""
Makes the plan-dashboard scripts importable as plain modules.

They are single-file scripts run via ``python3 build_dashboard.py ...``, not
an installed package - so their directory is added to ``sys.path`` here
rather than requiring an ``__init__.py``/packaging setup just for tests.
The repository root is added too, for the ``development_tooling`` package
the chip semantics come from.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
