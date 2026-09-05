#!/usr/bin/env python3
"""
Refuse a save that would leave a plan over its size budget.

Measures a manifest and roadmap exactly as ``plan_size_budget.py``'s report does, then
judges the result against :class:`plan_size_budget.SizeBudget` and prints the resulting
:class:`plan_size_budget.PlanOverBudgetError` to standard error when it is over. Kept
separate from ``plan_size_budget.py``'s own command, which only ever reports and never
refuses.

Usage:
    python3 plan_size_gate.py --manifest <path> --roadmap <path>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plan_size_budget import PlanOverBudgetError, PlanSize, SizeBudget


def main() -> int:
    """
    Parse arguments and refuse the given manifest and roadmap if they are over budget.

    :return: 0 when the plan is within budget, 1 when it is over.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--roadmap", required=True, type=Path)
    arguments = parser.parse_args()

    size = PlanSize.measure(arguments.manifest, arguments.roadmap)
    try:
        SizeBudget().enforce(size)
    except PlanOverBudgetError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
