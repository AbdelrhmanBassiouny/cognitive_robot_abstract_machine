"""
Makes the plan-dashboard scripts importable as plain modules.

They are single-file scripts run via ``python3 build_dashboard.py ...``, not
an installed package - so their directory is added to ``sys.path`` here
rather than requiring an ``__init__.py``/packaging setup just for tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
# .claude/hooks: some dashboard tests cite HookScript/PlanDocument from
# plan_item_bootstrap.py instead of spelling a filename it already defines.
sys.path.insert(0, str(Path(__file__).parents[3] / "hooks"))
