"""
Tests for plan_manifest_tools.py: reading a plan.yaml's id and regenerating the
branch->plan-id reverse index, used by save-plan.sh.
"""

import sys
from pathlib import Path

import pytest
import yaml

from basstler.plan_item_bootstrap import PlanDocument
from basstler.plan_manifest_tools import (
    ItemSummaryKey,
    ManifestToolCommand,
    ManifestToolOption,
    YamlBooleanCoercionError,
    item_summary,
    main,
    read_manifest_id,
    regenerate_branch_index,
)
from basstler.plan_model import ItemNotTrackedError, ItemStatus, ManifestField

from .constants import DatasetLocation
from .plan_dataset import LandedItemsPlan


def write_manifest(directory: Path, plan_id: str, name: str = "plan.yaml") -> Path:
    """
    Write a minimal plan.yaml with just an ``id`` field.

    :param directory: Where to write the manifest.
    :param plan_id: The manifest's ``id`` field, written verbatim (unquoted) - callers
        wanting a quoted value should write the file themselves instead.
    :param name: The manifest's filename.
    :return: The written file's path.
    """
    manifest_path = directory / name
    manifest_path.write_text(f"id: {plan_id}\n")
    return manifest_path


# %% read_manifest_id


def test_reads_the_id_field(tmp_path):
    manifest_path = write_manifest(tmp_path, "rdr-refactor")
    assert read_manifest_id(manifest_path) == "rdr-refactor"


def test_defaults_to_empty_string_when_id_is_missing(tmp_path):
    manifest_path = tmp_path / "plan.yaml"
    manifest_path.write_text("title: No id here\n")
    assert read_manifest_id(manifest_path) == ""


def test_raises_when_id_is_coerced_to_a_boolean(tmp_path):
    manifest_path = write_manifest(tmp_path, "no")
    with pytest.raises(YamlBooleanCoercionError, match="'id'"):
        read_manifest_id(manifest_path)


# %% regenerate_branch_index


def _write_plan(plans_directory: Path, plan_id: str, items_yaml: str) -> None:
    plan_directory = plans_directory / plan_id
    plan_directory.mkdir(parents=True)
    (plan_directory / "plan.yaml").write_text(f"id: {plan_id}\nitems:\n{items_yaml}")


def test_indexes_every_item_branch(tmp_path):
    plans_directory = tmp_path / "plans"
    _write_plan(
        plans_directory,
        "plan-a",
        "  - branch: branch-1\n  - branch: branch-2\n",
    )
    content = regenerate_branch_index(tmp_path, "plans", "plan.yaml")
    assert content == "branch-1\tplan-a\nbranch-2\tplan-a\n"


def test_skips_items_with_no_branch(tmp_path):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "plan-a", "  - title: no branch here\n")
    assert regenerate_branch_index(tmp_path, "plans", "plan.yaml") == ""


def test_empty_when_no_plans_exist(tmp_path):
    (tmp_path / "plans").mkdir()
    assert regenerate_branch_index(tmp_path, "plans", "plan.yaml") == ""


def test_first_plan_wins_on_a_duplicate_branch(tmp_path):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "plan-a", "  - branch: shared\n")
    _write_plan(plans_directory, "plan-b", "  - branch: shared\n")
    content = regenerate_branch_index(tmp_path, "plans", "plan.yaml")
    # plans are scanned in sorted glob order, so plan-a wins over plan-b.
    assert content == "shared\tplan-a\n"


def test_warns_on_stderr_when_a_duplicate_branch_is_dropped(tmp_path, capsys):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "plan-a", "  - branch: shared\n")
    _write_plan(plans_directory, "plan-b", "  - branch: shared\n")
    regenerate_branch_index(tmp_path, "plans", "plan.yaml")
    duplicate_manifest_path = plans_directory / "plan-b" / "plan.yaml"
    assert capsys.readouterr().err == (
        f"plan_manifest_tools.py: duplicate branch 'shared' in "
        f"{duplicate_manifest_path} - keeping the first plan it was seen "
        "under, dropping this one.\n"
    )


def test_raises_when_plan_id_is_coerced_to_a_boolean(tmp_path):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "no", "  - branch: branch-1\n")
    with pytest.raises(YamlBooleanCoercionError, match="'id'"):
        regenerate_branch_index(tmp_path, "plans", "plan.yaml")


def test_raises_when_a_branch_is_coerced_to_a_boolean(tmp_path):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "plan-a", "  - branch: no\n")
    with pytest.raises(YamlBooleanCoercionError, match="'branch'"):
        regenerate_branch_index(tmp_path, "plans", "plan.yaml")


# %% main - subcommand dispatch


def test_main_dispatches_read_id(tmp_path, monkeypatch, capsys):
    manifest_path = write_manifest(tmp_path, "rdr-refactor")
    monkeypatch.setattr(
        sys,
        "argv",
        ["plan_manifest_tools.py", ManifestToolCommand.READ_ID, str(manifest_path)],
    )
    exit_code = main()
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "rdr-refactor"


def test_main_dispatches_regenerate_branch_index(tmp_path, monkeypatch):
    plans_directory = tmp_path / "plans"
    _write_plan(plans_directory, "plan-a", "  - branch: branch-1\n")
    output_path = tmp_path / "branch-index.tsv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_manifest_tools.py",
            ManifestToolCommand.REGENERATE_BRANCH_INDEX,
            ManifestToolOption.SCRATCH_DIRECTORY,
            str(tmp_path),
            ManifestToolOption.PLANS_DIRECTORY,
            "plans",
            ManifestToolOption.MANIFEST_FILENAME,
            PlanDocument.MANIFEST,
            ManifestToolOption.OUTPUT,
            str(output_path),
        ],
    )
    exit_code = main()
    assert exit_code == 0
    assert output_path.read_text() == "branch-1\tplan-a\n"


# %% item - one item's slice of a plan


def test_item_summary_holds_the_one_item_and_the_plan_header():
    plan = LandedItemsPlan.read()
    item = plan.item_with_status(ItemStatus.IN_PROGRESS)
    summary = yaml.safe_load(item_summary(plan.manifest, item))
    assert summary == {
        ManifestField.IDENTIFIER.value: plan.manifest.identifier,
        ManifestField.TITLE.value: plan.manifest.content[ManifestField.TITLE],
        ManifestField.TRACKING_ISSUE.value: plan.manifest.content[
            ManifestField.TRACKING_ISSUE
        ],
        ItemSummaryKey.ITEM.value: item.content,
    }


def test_an_item_the_plan_does_not_track_is_refused():
    with pytest.raises(ItemNotTrackedError):
        LandedItemsPlan.read().manifest.item_named("missing")


def test_a_branch_no_item_is_worked_on_is_refused():
    with pytest.raises(ItemNotTrackedError):
        LandedItemsPlan.read().manifest.item_on_branch("missing")


def test_main_dispatches_item_by_id(monkeypatch, capsys):
    plan = LandedItemsPlan.read()
    item = plan.item_with_status(ItemStatus.NOT_STARTED)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_manifest_tools.py",
            ManifestToolCommand.ITEM,
            str(DatasetLocation.PLAN_WITH_LANDED_ITEMS),
            ManifestToolOption.ITEM_IDENTIFIER,
            item.identifier,
        ],
    )
    assert main() == 0
    assert capsys.readouterr().out == item_summary(plan.manifest, item)


def test_main_dispatches_item_by_branch(monkeypatch, capsys):
    plan = LandedItemsPlan.read()
    item = plan.item_with_status(ItemStatus.IN_PROGRESS)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_manifest_tools.py",
            ManifestToolCommand.ITEM,
            str(DatasetLocation.PLAN_WITH_LANDED_ITEMS),
            ManifestToolOption.BRANCH,
            item.content[ManifestField.BRANCH],
        ],
    )
    assert main() == 0
    assert capsys.readouterr().out == item_summary(plan.manifest, item)
