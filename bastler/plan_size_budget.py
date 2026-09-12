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
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

import yaml

from bastler.plan_item_bootstrap import PlanDocument
from bastler.plan_manifest_tools import read_manifest_id

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

    @classmethod
    def measure(cls, manifest_path: Path, roadmap_path: Path) -> PlanSize:
        """
        Measure one plan from its two files.

        :param manifest_path: The plan's manifest.
        :param roadmap_path: The plan's roadmap.
        :return: Its measured size.
        """
        return cls(
            plan_id=read_manifest_id(manifest_path),
            item_count=cls.count_items(manifest_path),
            manifest_line_count=cls.count_lines(manifest_path),
            roadmap_line_count=cls.count_lines(roadmap_path),
        )

    @staticmethod
    def count_items(manifest_path: Path) -> int:
        """
        Count the items a manifest declares.

        Parses the YAML rather than matching item lines, because manifests differ in how
        deeply they indent a sequence under its key - a rewritten manifest puts its
        entries flush with ``items:``, which a line match written for the indented style
        reads as no items at all.

        :param manifest_path: The manifest to read.
        :return: How many items it declares.
        """
        with manifest_path.open() as manifest_file:
            manifest = yaml.safe_load(manifest_file)
        return len(manifest.get("items") or [])

    @staticmethod
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

    Built with no arguments, this is the budget every plan is held to; the fields are
    there so a test can measure against a budget of its own.
    """

    MAXIMUM_ITEMS: ClassVar[int] = 15
    """
    The most items a plan's manifest may declare.

    Set against the live measurement of 2026-08-28, where the largest plan nobody wanted
    split held 13 items and the two outliers held 49 and 55.
    """

    MAXIMUM_LINES: ClassVar[int] = 2000
    """
    The most lines a plan's manifest and roadmap may hold together.

    Set against the same measurement, where that largest healthy plan held 1,634 lines
    and the two outliers held 3,676 and 14,259.
    """

    maximum_items: int = MAXIMUM_ITEMS
    """
    The most items this budget allows a manifest to declare.
    """

    maximum_lines: int = MAXIMUM_LINES
    """
    The most lines this budget allows a manifest and roadmap to hold together.
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


# %% measuring the plans on disk


@dataclass(frozen=True)
class PlansDirectory:
    """
    A directory each plan has its own directory under, and the two filenames every plan
    is measured from.
    """

    path: Path
    """
    The directory to walk.
    """

    manifest_filename: str
    """
    The manifest's fixed filename (e.g. ``plan.yaml``).
    """

    roadmap_filename: str
    """
    The roadmap's fixed filename (e.g. ``roadmap.md``).
    """

    def measure(self) -> list[PlanSize]:
        """
        Measure every plan laid out under this directory.

        A directory holding no manifest is not a plan and is passed over, which is how
        the generated index and dashboard-URL cache stay out of the report.

        :return: One size per plan, in plan-directory order.
        """
        return [
            PlanSize.measure(
                manifest_path, manifest_path.parent / self.roadmap_filename
            )
            for manifest_path in sorted(self.path.glob(f"*/{self.manifest_filename}"))
        ]


# %% reporting


@dataclass(frozen=True)
class SizeReport:
    """
    Every measured plan, judged against one budget and rendered as a table.
    """

    WITHIN_BUDGET: ClassVar[str] = "within budget"
    """
    What the report says of a plan that blows neither half of the budget.
    """

    COLUMN_HEADINGS: ClassVar[tuple[str, ...]] = (
        "plan",
        "items",
        "manifest",
        "roadmap",
        "total",
        "status",
    )
    """
    The table's columns, in the order every row states them.
    """

    sizes: list[PlanSize]
    """
    The measured plans, in the order they are reported.
    """

    budget: SizeBudget = field(default_factory=SizeBudget)
    """
    The budget they are judged against.
    """

    def status_of(self, size: PlanSize) -> str:
        """
        State what one plan's overruns amount to.

        :param size: The measured plan.
        :return: Every overrun it has, or :data:`WITHIN_BUDGET` when it has none.
        """
        overruns = self.budget.overruns(size)
        return ", ".join(str(overrun) for overrun in overruns) or self.WITHIN_BUDGET

    def over_budget_count(self) -> int:
        """
        :return: How many of the measured plans blow either half of the budget.
        """
        return sum(1 for size in self.sizes if self.budget.overruns(size))

    def render(self) -> str:
        """
        Render every measured plan against the budget as a table.

        :return: The report, ready to print.
        """
        header = list(self.COLUMN_HEADINGS)
        rows = [
            [
                size.plan_id,
                str(size.item_count),
                str(size.manifest_line_count),
                str(size.roadmap_line_count),
                str(size.line_count),
                self.status_of(size),
            ]
            for size in self.sizes
        ]
        widths = [
            max(len(row[column]) for row in [header, *rows])
            for column in range(len(header))
        ]
        return "\n".join(
            [
                f"Budget: {self.budget.maximum_items} items, "
                f"{self.budget.maximum_lines} lines "
                f"({PlanDocument.MANIFEST} and {PlanDocument.ROADMAP} together).",
                "",
                self.render_row(header, widths),
                *(self.render_row(row, widths) for row in rows),
                "",
                self.render_summary(),
            ]
        )

    def render_summary(self) -> str:
        """
        :return: The one-line verdict closing the report.
        """
        over_budget_count = self.over_budget_count()
        if not over_budget_count:
            return f"All {len(self.sizes)} plans are within budget."
        return f"{over_budget_count} of {len(self.sizes)} plans are over budget."

    @staticmethod
    def render_row(cells: list[str], widths: list[int]) -> str:
        """
        Render one report row: the plan id left-aligned, every count right-aligned, and
        the status left unpadded at the end of the line.

        :param cells: The row's cells, in header order.
        :param widths: Each column's width.
        :return: The rendered row.
        """
        padded = [cells[0].ljust(widths[0])]
        padded += [
            cell.rjust(width)
            for cell, width in zip(cells[1:-1], widths[1:-1], strict=True)
        ]
        padded.append(cells[-1])
        return " ".join(padded)


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

    plans = PlansDirectory(
        arguments.plans_dir, arguments.manifest_filename, arguments.roadmap_filename
    )
    print(SizeReport(plans.measure()).render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
