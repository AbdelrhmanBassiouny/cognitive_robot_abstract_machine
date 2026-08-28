#!/usr/bin/env python3
"""
The size budget a plan is held to, and the report measuring every plan against it.

A plan's size is its ``plan.yaml`` and ``roadmap.md`` together: how many items it
declares, and how many lines the two files hold. Nothing here refuses anything - it
measures and reports, so a plan already over the budget can still be read about and
saved.

Usage:
    python3 plan_size_budget.py --plans-dir <dir> \\
        --manifest-filename <name> --roadmap-filename <name>
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from plan_manifest_tools import read_manifest_id

WITHIN_BUDGET = "within budget"
"""
What the report says of a plan that blows neither half of the budget.
"""


# %% the budget


class BudgetLimit(StrEnum):
    """
    The two halves of the budget a plan is measured against.
    """

    ITEMS = "items"
    """
    How many items the manifest declares.
    """

    LINES = "lines"
    """
    How many lines the manifest and the roadmap hold together.
    """


@dataclass(frozen=True)
class PlanSize:
    """
    One plan's measured size.
    """

    plan_id: str
    """
    The plan this was measured from.
    """

    item_count: int
    """
    How many items its manifest declares.
    """

    manifest_line_count: int
    """
    How many lines its manifest holds.
    """

    roadmap_line_count: int
    """
    How many lines its roadmap holds.
    """

    @property
    def line_count(self) -> int:
        """
        :return: The manifest and roadmap line counts together, which is what the
            budget's line limit is spent on.
        """
        return self.manifest_line_count + self.roadmap_line_count

    def count(self, limit: BudgetLimit) -> int:
        """
        Read back whichever count *limit* governs.

        :param limit: The half of the budget to read.
        :return: This plan's measurement of it.
        """
        if limit is BudgetLimit.ITEMS:
            return self.item_count
        return self.line_count


@dataclass(frozen=True)
class BudgetOverrun:
    """
    One half of the budget, blown by how much.
    """

    limit: BudgetLimit
    """
    The half that was blown.
    """

    measured: int
    """
    What the plan actually measures against it.
    """

    allowed: int
    """
    The most the budget allows.
    """

    @property
    def excess(self) -> int:
        """
        :return: How far past the allowance the plan is.
        """
        return self.measured - self.allowed

    def __str__(self) -> str:
        """
        :return: The overrun stated as its excess against what was allowed, e.g. ``5
            items over 10``.
        """
        return f"{self.excess} {self.limit} over {self.allowed}"


@dataclass(frozen=True)
class SizeBudget:
    """
    The most one plan may hold before it has to be split into several.
    """

    maximum_items: int
    """
    The most items a plan's manifest may declare.
    """

    maximum_lines: int
    """
    The most lines its manifest and roadmap may hold together.
    """

    def allowance(self, limit: BudgetLimit) -> int:
        """
        Read back whichever allowance *limit* names.

        :param limit: The half of the budget to read.
        :return: The most it allows.
        """
        if limit is BudgetLimit.ITEMS:
            return self.maximum_items
        return self.maximum_lines

    def overruns(self, size: PlanSize) -> tuple[BudgetOverrun, ...]:
        """
        Judge one plan's size against this budget.

        :param size: The measured plan.
        :return: One overrun per blown half, in :class:`BudgetLimit` order - empty when
            the plan is within budget.
        """
        return tuple(
            BudgetOverrun(limit, size.count(limit), self.allowance(limit))
            for limit in BudgetLimit
            if size.count(limit) > self.allowance(limit)
        )


PLAN_SIZE_BUDGET = SizeBudget(maximum_items=15, maximum_lines=2000)
"""
The budget every plan is held to.

Set against the live measurement of 2026-08-28, where the largest plan nobody wanted
split held 13 items and 1,634 lines and the two outliers held 3,676 and 14,259 lines.
"""


# %% measuring a plan


def count_items(manifest_path: Path) -> int:
    """
    Count the items a manifest declares.

    Parses the YAML rather than matching item lines, because manifests differ in how
    deeply they indent a sequence under its key - a rewritten manifest puts its entries
    flush with ``items:``, which a line match written for the indented style reads as no
    items at all.

    :param manifest_path: The manifest to read.
    :return: How many items it declares.
    """
    with manifest_path.open() as manifest_file:
        manifest = yaml.safe_load(manifest_file)
    return len(manifest.get("items") or [])


def count_lines(path: Path) -> int:
    """
    Count a file's lines, counting a last line that has no trailing newline.

    :param path: The file to count, which need not exist - a plan carrying no roadmap
        spends none of the budget on one.
    :return: How many lines it holds.
    """
    if not path.exists():
        return 0
    return len(path.read_text().splitlines())


def measure_plan(manifest_path: Path, roadmap_path: Path) -> PlanSize:
    """
    Measure one plan from its two files.

    :param manifest_path: The plan's manifest.
    :param roadmap_path: The plan's roadmap.
    :return: Its measured size.
    """
    return PlanSize(
        plan_id=read_manifest_id(manifest_path),
        item_count=count_items(manifest_path),
        manifest_line_count=count_lines(manifest_path),
        roadmap_line_count=count_lines(roadmap_path),
    )


def measure_plans(
    plans_directory: Path, manifest_filename: str, roadmap_filename: str
) -> list[PlanSize]:
    """
    Measure every plan laid out under a plans directory.

    A directory holding no manifest is not a plan and is passed over, which is how the
    generated index and dashboard-URL cache stay out of the report.

    :param plans_directory: The directory each plan has its own directory under.
    :param manifest_filename: The manifest's fixed filename (e.g. ``plan.yaml``).
    :param roadmap_filename: The roadmap's fixed filename (e.g. ``roadmap.md``).
    :return: One size per plan, in plan-directory order.
    """
    return [
        measure_plan(manifest_path, manifest_path.parent / roadmap_filename)
        for manifest_path in sorted(plans_directory.glob(f"*/{manifest_filename}"))
    ]


# %% reporting


def render_row(cells: list[str], widths: list[int]) -> str:
    """
    Render one report row: the plan id left-aligned, every count right-aligned, and the
    status left unpadded at the end of the line.

    :param cells: The row's cells, in header order.
    :param widths: Each column's width.
    :return: The rendered row.
    """
    padded = [cells[0].ljust(widths[0])]
    padded += [
        cell.rjust(width) for cell, width in zip(cells[1:-1], widths[1:-1], strict=True)
    ]
    padded.append(cells[-1])
    return " ".join(padded)


def render_status(overruns: tuple[BudgetOverrun, ...]) -> str:
    """
    State what one plan's overruns amount to.

    :param overruns: The plan's overruns, possibly none.
    :return: Every overrun, or :data:`WITHIN_BUDGET` when there are none.
    """
    return ", ".join(str(overrun) for overrun in overruns) or WITHIN_BUDGET


def render_report(sizes: list[PlanSize], budget: SizeBudget) -> str:
    """
    Render every measured plan against the budget as a table.

    :param sizes: The measured plans.
    :param budget: The budget to measure them against.
    :return: The report, ready to print.
    """
    header = ["plan", "items", "manifest", "roadmap", "total", "status"]
    overruns_per_plan = [budget.overruns(size) for size in sizes]
    rows = [
        [
            size.plan_id,
            str(size.item_count),
            str(size.manifest_line_count),
            str(size.roadmap_line_count),
            str(size.line_count),
            render_status(overruns),
        ]
        for size, overruns in zip(sizes, overruns_per_plan, strict=True)
    ]
    widths = [
        max(len(row[column]) for row in [header, *rows])
        for column in range(len(header))
    ]

    over_budget_count = sum(1 for overruns in overruns_per_plan if overruns)
    summary = (
        f"{over_budget_count} of {len(sizes)} plans are over budget."
        if over_budget_count
        else f"All {len(sizes)} plans are within budget."
    )
    return "\n".join(
        [
            f"Budget: {budget.maximum_items} items, {budget.maximum_lines} lines "
            "(plan.yaml and roadmap.md together).",
            "",
            render_row(header, widths),
            *(render_row(row, widths) for row in rows),
            "",
            summary,
        ]
    )


def main() -> int:
    """
    Parse arguments and print the report.

    :return: The process exit code, always zero - this reports, it never refuses.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--plans-dir", required=True, type=Path)
    parser.add_argument("--manifest-filename", required=True)
    parser.add_argument("--roadmap-filename", required=True)
    arguments = parser.parse_args()

    sizes = measure_plans(
        arguments.plans_dir, arguments.manifest_filename, arguments.roadmap_filename
    )
    print(render_report(sizes, PLAN_SIZE_BUDGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
