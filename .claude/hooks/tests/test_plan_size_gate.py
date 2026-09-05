"""
Tests for plan_size_gate.py: the command save-plan.sh runs to refuse a save that would
leave a plan over its size budget.
"""

import sys
from pathlib import Path

import pytest

from plan_size_budget import PlanOverBudgetError, PlanSize, SizeBudget
from plan_size_gate import main


def write_plan(
    tmp_path: Path, item_count: int, roadmap_line_count: int
) -> tuple[Path, Path]:
    """
    Write a manifest and roadmap of the given sizes to *tmp_path*.

    :param tmp_path: Where to write the two files.
    :param item_count: How many items the manifest declares.
    :param roadmap_line_count: How many lines the roadmap holds.
    :return: The manifest and roadmap paths.
    """
    manifest_path = tmp_path / "plan.yaml"
    manifest_path.write_text(
        "id: a-plan\n"
        "items:\n" + "".join(f"  - id: item-{number}\n" for number in range(item_count))
    )
    roadmap_path = tmp_path / "roadmap.md"
    roadmap_path.write_text(
        "".join(f"roadmap line {number}\n" for number in range(roadmap_line_count))
    )
    return manifest_path, roadmap_path


def run_gate(monkeypatch, manifest_path: Path, roadmap_path: Path) -> int:
    """
    Run the gate's CLI against the given files.

    :param monkeypatch: pytest's monkeypatch fixture.
    :param manifest_path: The manifest to measure.
    :param roadmap_path: The roadmap to measure.
    :return: The process exit code.
    """
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_size_gate.py",
            "--manifest",
            str(manifest_path),
            "--roadmap",
            str(roadmap_path),
        ],
    )
    return main()


def test_a_plan_within_budget_exits_zero_and_prints_nothing(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=SizeBudget().maximum_items, roadmap_line_count=0
    )
    exit_code = run_gate(monkeypatch, manifest_path, roadmap_path)
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_a_plan_over_the_item_budget_exits_nonzero_naming_the_overrun(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=SizeBudget().maximum_items + 3, roadmap_line_count=0
    )
    exit_code = run_gate(monkeypatch, manifest_path, roadmap_path)
    assert exit_code == 1
    size = PlanSize.measure(manifest_path, roadmap_path)
    (overrun,) = SizeBudget().overruns(size)
    assert str(overrun) in capsys.readouterr().err


def test_a_plan_over_the_line_budget_exits_nonzero_naming_the_overrun(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path,
        item_count=0,
        roadmap_line_count=SizeBudget().maximum_lines + 5,
    )
    exit_code = run_gate(monkeypatch, manifest_path, roadmap_path)
    assert exit_code == 1
    size = PlanSize.measure(manifest_path, roadmap_path)
    (overrun,) = SizeBudget().overruns(size)
    assert str(overrun) in capsys.readouterr().err


def test_reports_a_plan_over_budget_error_as_its_own_message(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=SizeBudget().maximum_items + 1, roadmap_line_count=0
    )
    size = PlanSize.measure(manifest_path, roadmap_path)
    expected = PlanOverBudgetError(plan_size=size, overruns=SizeBudget().overruns(size))
    run_gate(monkeypatch, manifest_path, roadmap_path)
    assert str(expected) in capsys.readouterr().err
