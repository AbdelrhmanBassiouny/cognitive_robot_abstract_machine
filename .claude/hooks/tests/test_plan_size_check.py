"""
Tests for plan_size_check.py: the command ``/add-plan-item`` and ``/plan-create`` run to
learn whether a plan is already full, before writing anything into or as it.
"""

import json
import sys
from pathlib import Path

import pytest

import plan_size_check
from plan_size_budget import PlanSize, SizeBudget
from plan_size_check import PlanSizeCheckResult, main

SCRIPT_NAME = Path(plan_size_check.__file__).name
"""
This script's own filename, read from the module rather than spelled again here.
"""


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


def run_check(
    monkeypatch, capsys, manifest_path: Path, roadmap_path: Path
) -> PlanSizeCheckResult:
    """
    Run the check's CLI against the given files and parse its printed result.

    :param monkeypatch: pytest's monkeypatch fixture.
    :param capsys: pytest's stdout/stderr capture fixture.
    :param manifest_path: The manifest to measure.
    :param roadmap_path: The roadmap to measure.
    :return: The result it printed.
    """
    monkeypatch.setattr(
        sys,
        "argv",
        [
            SCRIPT_NAME,
            "--manifest",
            str(manifest_path),
            "--roadmap",
            str(roadmap_path),
        ],
    )
    exit_code = main()
    assert exit_code == 0
    return PlanSizeCheckResult.from_mapping(json.loads(capsys.readouterr().out))


def test_a_plan_within_budget_is_not_full(tmp_path, monkeypatch, capsys):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=SizeBudget().maximum_items, roadmap_line_count=0
    )
    result = run_check(monkeypatch, capsys, manifest_path, roadmap_path)
    assert result.is_full is False
    assert result.overruns == ()


def test_a_plan_over_the_item_budget_is_full_and_names_the_overrun(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=SizeBudget().maximum_items + 3, roadmap_line_count=0
    )
    result = run_check(monkeypatch, capsys, manifest_path, roadmap_path)
    size = PlanSize.measure(manifest_path, roadmap_path)
    (overrun,) = SizeBudget().overruns(size)
    assert result.is_full is True
    assert result.overruns == (str(overrun),)


def test_a_plan_over_the_line_budget_is_full_and_names_the_overrun(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path,
        item_count=0,
        roadmap_line_count=SizeBudget().maximum_lines + 5,
    )
    result = run_check(monkeypatch, capsys, manifest_path, roadmap_path)
    size = PlanSize.measure(manifest_path, roadmap_path)
    (overrun,) = SizeBudget().overruns(size)
    assert result.is_full is True
    assert result.overruns == (str(overrun),)


def test_reports_the_measured_item_and_line_counts(tmp_path, monkeypatch, capsys):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=4, roadmap_line_count=6
    )
    result = run_check(monkeypatch, capsys, manifest_path, roadmap_path)
    assert result.item_count == 4
    assert result.line_count == manifest_path.read_text().count("\n") + 6


def test_a_missing_roadmap_measures_as_zero_lines_and_never_raises(
    tmp_path, monkeypatch, capsys
):
    manifest_path, roadmap_path = write_plan(
        tmp_path, item_count=0, roadmap_line_count=0
    )
    roadmap_path.unlink()
    result = run_check(monkeypatch, capsys, manifest_path, roadmap_path)
    assert result.is_full is False
