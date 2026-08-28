"""
Tests for plan_size_budget.py: measuring one plan's size, judging it against the budget,
and reporting every plan in a plans directory against it.
"""

import sys
from pathlib import Path

import yaml

from plan_size_budget import (
    PLAN_SIZE_BUDGET,
    WITHIN_BUDGET,
    BudgetLimit,
    PlanSize,
    SizeBudget,
    main,
    measure_plan,
    measure_plans,
    render_report,
)

FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures"

UNINDENTED_ITEMS_MANIFEST = FIXTURES_DIRECTORY / "unindented-items-plan.yaml"
"""
A manifest whose item entries sit flush with the ``items:`` key holding them, the shape
a line-matching count misses.
"""

MANIFEST_FILENAME = "plan.yaml"
"""
The manifest filename the scratch plans in these tests are laid out under.
"""

ROADMAP_FILENAME = "roadmap.md"
"""
The roadmap filename the scratch plans in these tests are laid out under.
"""


def write_plan(
    plans_directory: Path,
    plan_id: str,
    item_count: int = 0,
    roadmap_line_count: int = 0,
) -> Path:
    """
    Lay out one plan directory holding a manifest with *item_count* items and a roadmap
    of *roadmap_line_count* lines.

    :param plans_directory: The directory plans are laid out under.
    :param plan_id: The plan's id, used as its directory name and its ``id`` field.
    :param item_count: How many items the manifest declares.
    :param roadmap_line_count: How many lines the roadmap holds.
    :return: The plan's directory.
    """
    plan_directory = plans_directory / plan_id
    plan_directory.mkdir(parents=True)
    manifest = {
        "id": plan_id,
        "items": [{"id": f"item-{number}"} for number in range(item_count)],
    }
    (plan_directory / MANIFEST_FILENAME).write_text(yaml.safe_dump(manifest))
    (plan_directory / ROADMAP_FILENAME).write_text(
        "".join(f"roadmap line {number}\n" for number in range(roadmap_line_count))
    )
    return plan_directory


def measure(plan_directory: Path) -> PlanSize:
    """
    Measure a plan laid out by :func:`write_plan`.

    :param plan_directory: The plan's directory.
    :return: Its measured size.
    """
    return measure_plan(
        plan_directory / MANIFEST_FILENAME, plan_directory / ROADMAP_FILENAME
    )


def report_line_for(report: str, plan_id: str) -> str:
    """
    Pick one plan's row out of a rendered report.

    :param report: The rendered report.
    :param plan_id: The plan whose row to return.
    :return: That row, with its trailing padding stripped.
    """
    rows = [line for line in report.splitlines() if line.startswith(f"{plan_id} ")]
    assert len(rows) == 1, f"expected exactly one row for {plan_id!r} in:\n{report}"
    return rows[0].rstrip()


# %% measuring one plan


def test_reads_the_plan_id_from_the_manifest(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan")
    assert measure(plan_directory).plan_id == "a-plan"


def test_counts_the_items_the_manifest_declares(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan", item_count=3)
    assert measure(plan_directory).item_count == 3


def test_counts_no_items_when_the_manifest_declares_none(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan")
    assert measure(plan_directory).item_count == 0


def test_counts_items_that_are_not_indented_under_their_key(tmp_path):
    expected_item_count = len(
        yaml.safe_load(UNINDENTED_ITEMS_MANIFEST.read_text())["items"]
    )
    size = measure_plan(UNINDENTED_ITEMS_MANIFEST, tmp_path / "absent-roadmap.md")
    assert size.item_count == expected_item_count


def test_counts_the_manifest_lines(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan", item_count=4)
    manifest_path = plan_directory / MANIFEST_FILENAME
    assert measure(plan_directory).manifest_line_count == len(
        manifest_path.read_text().splitlines()
    )


def test_counts_the_roadmap_lines(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan", roadmap_line_count=7)
    assert measure(plan_directory).roadmap_line_count == 7


def test_counts_a_last_line_that_has_no_trailing_newline(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan")
    (plan_directory / ROADMAP_FILENAME).write_text("first\nsecond")
    assert measure(plan_directory).roadmap_line_count == 2


def test_counts_no_roadmap_lines_when_the_plan_has_no_roadmap(tmp_path):
    plan_directory = write_plan(tmp_path, "a-plan")
    (plan_directory / ROADMAP_FILENAME).unlink()
    assert measure(plan_directory).roadmap_line_count == 0


def test_the_line_count_is_both_files_together():
    size = PlanSize(
        plan_id="a-plan", item_count=0, manifest_line_count=40, roadmap_line_count=60
    )
    assert size.line_count == 100


# %% judging a plan against the budget


def test_a_plan_at_the_budget_is_within_it():
    size = PlanSize(
        plan_id="a-plan",
        item_count=PLAN_SIZE_BUDGET.maximum_items,
        manifest_line_count=PLAN_SIZE_BUDGET.maximum_lines,
        roadmap_line_count=0,
    )
    assert PLAN_SIZE_BUDGET.overruns(size) == ()


def test_one_item_over_the_budget_is_an_overrun():
    size = PlanSize(
        plan_id="a-plan",
        item_count=PLAN_SIZE_BUDGET.maximum_items + 1,
        manifest_line_count=0,
        roadmap_line_count=0,
    )
    (overrun,) = PLAN_SIZE_BUDGET.overruns(size)
    assert overrun.limit is BudgetLimit.ITEMS
    assert overrun.excess == 1
    assert overrun.allowed == PLAN_SIZE_BUDGET.maximum_items


def test_one_line_over_the_budget_is_an_overrun():
    size = PlanSize(
        plan_id="a-plan",
        item_count=0,
        manifest_line_count=PLAN_SIZE_BUDGET.maximum_lines,
        roadmap_line_count=1,
    )
    (overrun,) = PLAN_SIZE_BUDGET.overruns(size)
    assert overrun.limit is BudgetLimit.LINES
    assert overrun.excess == 1
    assert overrun.allowed == PLAN_SIZE_BUDGET.maximum_lines


def test_the_line_limit_is_blown_by_both_files_together():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="a-plan", item_count=0, manifest_line_count=60, roadmap_line_count=60
    )
    (overrun,) = budget.overruns(size)
    assert overrun.limit is BudgetLimit.LINES
    assert overrun.measured == 120


def test_both_limits_can_be_over_at_once():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="a-plan", item_count=11, manifest_line_count=101, roadmap_line_count=0
    )
    assert [overrun.limit for overrun in budget.overruns(size)] == [
        BudgetLimit.ITEMS,
        BudgetLimit.LINES,
    ]


def test_an_overrun_states_the_excess_against_what_was_allowed():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="a-plan", item_count=15, manifest_line_count=0, roadmap_line_count=0
    )
    (overrun,) = budget.overruns(size)
    assert str(overrun) == "5 items over 10"


# %% measuring every plan


def test_measures_every_plan_in_the_directory(tmp_path):
    write_plan(tmp_path, "plan-a", item_count=1)
    write_plan(tmp_path, "plan-b", item_count=2)
    sizes = measure_plans(tmp_path, MANIFEST_FILENAME, ROADMAP_FILENAME)
    assert [(size.plan_id, size.item_count) for size in sizes] == [
        ("plan-a", 1),
        ("plan-b", 2),
    ]


def test_skips_a_directory_that_holds_no_manifest(tmp_path):
    write_plan(tmp_path, "plan-a")
    (tmp_path / "_generated").mkdir()
    (tmp_path / "_generated" / "branch-index.tsv").write_text("a-branch\tplan-a\n")
    sizes = measure_plans(tmp_path, MANIFEST_FILENAME, ROADMAP_FILENAME)
    assert [size.plan_id for size in sizes] == ["plan-a"]


def test_measures_nothing_when_there_are_no_plans(tmp_path):
    assert measure_plans(tmp_path, MANIFEST_FILENAME, ROADMAP_FILENAME) == []


# %% the rendered report


def test_a_plan_within_the_budget_is_reported_as_within_it():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="small-plan", item_count=2, manifest_line_count=10, roadmap_line_count=5
    )
    assert report_line_for(render_report([size], budget), "small-plan").endswith(
        WITHIN_BUDGET
    )


def test_a_plan_over_the_budget_is_reported_with_every_overrun():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="big-plan", item_count=12, manifest_line_count=90, roadmap_line_count=60
    )
    expected = ", ".join(str(overrun) for overrun in budget.overruns(size))
    assert report_line_for(render_report([size], budget), "big-plan").endswith(expected)


def test_a_reported_row_carries_the_measured_numbers():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="a-plan", item_count=2, manifest_line_count=10, roadmap_line_count=5
    )
    row = report_line_for(render_report([size], budget), "a-plan")
    assert row.split()[1:5] == ["2", "10", "5", "15"]


def test_the_report_names_the_budget_it_measured_against():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    assert "10 items" in render_report([], budget)
    assert "100 lines" in render_report([], budget)


def test_the_report_counts_how_many_plans_are_over_budget():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    sizes = [
        PlanSize(
            plan_id="plan-a", item_count=1, manifest_line_count=1, roadmap_line_count=0
        ),
        PlanSize(
            plan_id="plan-b", item_count=11, manifest_line_count=1, roadmap_line_count=0
        ),
        PlanSize(
            plan_id="plan-c", item_count=12, manifest_line_count=1, roadmap_line_count=0
        ),
    ]
    assert "2 of 3 plans are over budget." in render_report(sizes, budget)


def test_the_report_says_so_when_every_plan_is_within_budget():
    budget = SizeBudget(maximum_items=10, maximum_lines=100)
    size = PlanSize(
        plan_id="plan-a", item_count=1, manifest_line_count=1, roadmap_line_count=0
    )
    assert "All 1 plans are within budget." in render_report([size], budget)


# %% the command


def test_main_reports_every_plan_against_the_budget(tmp_path, monkeypatch, capsys):
    write_plan(tmp_path, "plan-a", item_count=1, roadmap_line_count=3)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_size_budget.py",
            "--plans-dir",
            str(tmp_path),
            "--manifest-filename",
            MANIFEST_FILENAME,
            "--roadmap-filename",
            ROADMAP_FILENAME,
        ],
    )
    exit_code = main()
    assert exit_code == 0
    printed = capsys.readouterr().out
    assert report_line_for(printed, "plan-a").endswith(WITHIN_BUDGET)


def test_main_measures_against_the_plan_size_budget(tmp_path, monkeypatch, capsys):
    write_plan(tmp_path, "plan-a", item_count=PLAN_SIZE_BUDGET.maximum_items + 1)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_size_budget.py",
            "--plans-dir",
            str(tmp_path),
            "--manifest-filename",
            MANIFEST_FILENAME,
            "--roadmap-filename",
            ROADMAP_FILENAME,
        ],
    )
    main()
    size = measure(tmp_path / "plan-a")
    (overrun,) = PLAN_SIZE_BUDGET.overruns(size)
    assert report_line_for(capsys.readouterr().out, "plan-a").endswith(str(overrun))
