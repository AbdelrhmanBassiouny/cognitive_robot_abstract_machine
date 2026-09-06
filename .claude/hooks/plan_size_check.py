#!/usr/bin/env python3
"""
Report whether a plan is already full, before ``/add-plan-item`` or ``/plan-create``
writes into or as it.

Measures a manifest and roadmap exactly as ``plan_size_budget.py``'s report does, then
judges the result against :class:`plan_size_budget.SizeBudget`. Unlike
``plan_size_gate.py``, this never refuses anything - it only answers the question a
skill has to ask *before* a save is even attempted, so the routing decision (grow this
plan, or open a new one) can be made before writing anything doomed to be refused later.

Usage:
    python3 plan_size_check.py --manifest <path> --roadmap <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plan_size_budget import PlanSize, SizeBudget


def main() -> int:
    """
    Parse arguments and print whether the given manifest and roadmap are already full.

    :return: 0, always - this reports, it never refuses.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--roadmap", required=True, type=Path)
    arguments = parser.parse_args()

    size = PlanSize.measure(arguments.manifest, arguments.roadmap)
    overruns = SizeBudget().overruns(size)
    print(
        json.dumps(
            {
                "item_count": size.item_count,
                "line_count": size.line_count,
                "is_full": bool(overruns),
                "overruns": [str(overrun) for overrun in overruns],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
