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
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from plan_size_budget import PlanSize, SizeBudget


class PlanSizeCheckField(StrEnum):
    """
    The keys this script's JSON output carries, named once so a producer or reader never
    spells one as a bare string.
    """

    ITEM_COUNT = "item_count"
    """
    How many items the measured manifest declares.
    """

    LINE_COUNT = "line_count"
    """
    How many lines the measured manifest and roadmap hold together.
    """

    IS_FULL = "is_full"
    """
    Whether the measured plan blows either half of the size budget.
    """

    OVERRUNS = "overruns"
    """
    Every blown half, rendered as its own string - empty when the plan is within budget.
    """


@dataclass(frozen=True)
class PlanSizeCheckResult:
    """
    Whether one plan is already full, as this script reports it.
    """

    item_count: int
    """
    How many items the measured manifest declares.
    """

    line_count: int
    """
    How many lines the measured manifest and roadmap hold together.
    """

    is_full: bool
    """
    Whether the measured plan blows either half of the size budget.
    """

    overruns: tuple[str, ...]
    """
    Every blown half, rendered as its own string - empty when the plan is within budget.
    """

    @classmethod
    def measure(cls, manifest_path: Path, roadmap_path: Path) -> PlanSizeCheckResult:
        """
        Measure a plan and judge it against the size budget.

        :param manifest_path: The manifest to measure.
        :param roadmap_path: The roadmap to measure.
        :return: Whether that plan is already full.
        """
        size = PlanSize.measure(manifest_path, roadmap_path)
        overruns = SizeBudget().overruns(size)
        return cls(
            item_count=size.item_count,
            line_count=size.line_count,
            is_full=bool(overruns),
            overruns=tuple(str(overrun) for overrun in overruns),
        )

    def to_json(self) -> dict[str, Any]:
        """
        :return: This result as the mapping this script prints as JSON.
        """
        return {
            PlanSizeCheckField.ITEM_COUNT: self.item_count,
            PlanSizeCheckField.LINE_COUNT: self.line_count,
            PlanSizeCheckField.IS_FULL: self.is_full,
            PlanSizeCheckField.OVERRUNS: list(self.overruns),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PlanSizeCheckResult:
        """
        Build a result from this script's own parsed JSON output.

        :param data: The parsed JSON mapping.
        :return: The result it describes.
        """
        return cls(
            item_count=data[PlanSizeCheckField.ITEM_COUNT],
            line_count=data[PlanSizeCheckField.LINE_COUNT],
            is_full=data[PlanSizeCheckField.IS_FULL],
            overruns=tuple(data[PlanSizeCheckField.OVERRUNS]),
        )


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

    result = PlanSizeCheckResult.measure(arguments.manifest, arguments.roadmap)
    print(json.dumps(result.to_json()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
