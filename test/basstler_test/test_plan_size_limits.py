"""
Tests for plan_size_limits.py: the limits every plan document and every pull request's
progress notes are held to.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.plan_model import ManifestField, PlanManifest
from basstler.plan_size_limits import (
    DocumentOverLimitError,
    LimitedDocument,
    Measure,
    PlanFiles,
    Roadmap,
    RoadmapFormatViolation,
    SizeViolation,
    StagedPlan,
    check_progress_file,
    manifest_violations,
    progress_violations,
    read_manifest,
)

from .constants import DatasetLocation

PLAN_WITH_LANDED_ITEMS = DatasetLocation.DIRECTORY / "plan-with-landed-items.yaml"
"""
A plan whose first item has landed and whose other two depend on it.
"""

PLAN_ALL_LANDED = DatasetLocation.DIRECTORY / "plan-all-landed.yaml"
"""
A plan every item of which has landed.
"""

ROADMAP_OF_STANDING_RULES = DatasetLocation.DIRECTORY / "roadmap-of-standing-rules.md"
"""
A roadmap in the shape the limits accept.
"""

ROADMAP_WITH_DATED_SECTION = DatasetLocation.DIRECTORY / "roadmap-with-dated-section.md"
"""
A roadmap a session appended a dated section to.
"""


def destination_in(directory: Path) -> PlanFiles:
    """
    :return: Where a staged plan lands inside *directory*.
    """
    plan_directory = directory / "plan"
    return PlanFiles(plan_directory / "plan.yaml", plan_directory / "roadmap.md")


def manifest_with_item_fields(**fields: object) -> PlanManifest:
    """
    :return: The landed-items plan with *fields* set on its open item.
    """
    manifest = read_manifest(PLAN_WITH_LANDED_ITEMS)
    items = [
        {**item.content, **fields} if item.identifier == "open" else item.content
        for item in manifest.items
    ]
    return PlanManifest({**manifest.content, ManifestField.ITEMS.value: items})


# %% pruning landed items


def test_pruning_removes_only_the_landed_items():
    pruned = read_manifest(PLAN_WITH_LANDED_ITEMS).without_landed_items()
    assert [item.identifier for item in pruned.items] == ["open", "queued"]


def test_pruning_drops_every_dependency_on_a_landed_item():
    pruned = read_manifest(PLAN_WITH_LANDED_ITEMS).without_landed_items()
    assert [item.dependencies for item in pruned.items] == [[], ["open"]]


def test_pruning_keeps_every_other_field_of_a_remaining_item():
    original = read_manifest(PLAN_WITH_LANDED_ITEMS).item_named("open")
    pruned = read_manifest(PLAN_WITH_LANDED_ITEMS).without_landed_items()
    remaining = pruned.item_named("open")
    assert {**remaining.content, ManifestField.DEPENDS_ON.value: None} == {
        **original.content,
        ManifestField.DEPENDS_ON.value: None,
    }


def test_staging_writes_the_plan_without_its_landed_items(tmp_path):
    destination = destination_in(tmp_path)
    staged = PlanFiles(PLAN_WITH_LANDED_ITEMS, ROADMAP_OF_STANDING_RULES).stage(
        destination
    )
    assert staged == StagedPlan.SAVED
    assert read_manifest(destination.manifest).content == (
        read_manifest(PLAN_WITH_LANDED_ITEMS).without_landed_items().content
    )
    assert destination.roadmap.read_text() == ROADMAP_OF_STANDING_RULES.read_text()


def test_staging_a_plan_with_nothing_landed_copies_its_text_unchanged(tmp_path):
    first = destination_in(tmp_path / "first")
    PlanFiles(PLAN_WITH_LANDED_ITEMS, ROADMAP_OF_STANDING_RULES).stage(first)
    second = destination_in(tmp_path / "second")
    PlanFiles(first.manifest, first.roadmap).stage(second)
    assert second.manifest.read_text() == first.manifest.read_text()


def test_staging_a_plan_with_every_item_landed_removes_its_directory(tmp_path):
    destination = destination_in(tmp_path)
    destination.manifest.parent.mkdir()
    destination.manifest.write_text("stale\n")
    staged = PlanFiles(PLAN_ALL_LANDED, ROADMAP_OF_STANDING_RULES).stage(destination)
    assert staged == StagedPlan.REMOVED
    assert not destination.manifest.parent.exists()


def test_staging_refuses_a_plan_over_its_limits_and_writes_nothing(tmp_path):
    destination = destination_in(tmp_path)
    with pytest.raises(DocumentOverLimitError) as raised:
        PlanFiles(PLAN_WITH_LANDED_ITEMS, ROADMAP_WITH_DATED_SECTION).stage(destination)
    assert raised.value.document == LimitedDocument.PLAN
    assert not destination.manifest.parent.exists()


# %% manifest limits


def test_a_manifest_within_every_limit_has_no_violations():
    assert manifest_violations(read_manifest(PLAN_WITH_LANDED_ITEMS)) == []


def test_notes_one_character_over_the_limit_are_a_violation():
    measured = Measure.NOTE_LENGTH.maximum + 1
    manifest = manifest_with_item_fields(notes="x" * measured)
    assert manifest_violations(manifest) == [
        SizeViolation(Measure.NOTE_LENGTH, "item 'open'", measured)
    ]


def test_notes_are_measured_with_their_line_folding_undone():
    words = "word " * (Measure.NOTE_LENGTH.maximum // len("word "))
    manifest = manifest_with_item_fields(notes=words.replace(" ", "\n   "))
    assert manifest_violations(manifest) == []


def test_too_many_blockers_are_a_violation():
    measured = Measure.BLOCKER_COUNT.maximum + 1
    manifest = manifest_with_item_fields(blockers=["waits"] * measured)
    assert manifest_violations(manifest) == [
        SizeViolation(Measure.BLOCKER_COUNT, "item 'open'", measured)
    ]


def test_a_long_blocker_is_a_violation():
    measured = Measure.BLOCKER_LENGTH.maximum + 1
    manifest = manifest_with_item_fields(blockers=["x" * measured])
    assert manifest_violations(manifest) == [
        SizeViolation(Measure.BLOCKER_LENGTH, "item 'open'", measured)
    ]


def test_too_many_items_are_a_violation():
    manifest = read_manifest(PLAN_WITH_LANDED_ITEMS)
    template = manifest.item_named("queued").content
    measured = Measure.ITEM_COUNT.maximum + 1
    items = [
        {**template, ManifestField.IDENTIFIER.value: f"item-{number}"}
        for number in range(measured)
    ]
    oversized = PlanManifest({**manifest.content, ManifestField.ITEMS.value: items})
    assert manifest_violations(oversized) == [
        SizeViolation(Measure.ITEM_COUNT, "plan", measured)
    ]


# %% roadmap shape


def test_a_roadmap_of_entries_reads_each_entry_whole():
    roadmap = Roadmap.from_text(ROADMAP_OF_STANDING_RULES.read_text())
    assert len(roadmap.entries) == 2
    assert roadmap.violations() == []


def test_a_continuation_line_joins_the_entry_above_it():
    roadmap = Roadmap.from_text(ROADMAP_OF_STANDING_RULES.read_text())
    assert "\n" not in roadmap.entries[1]
    assert roadmap.entries[1].endswith("items of this plan only.")


def test_a_dated_section_is_refused_as_a_format_violation():
    roadmap = Roadmap.from_text(ROADMAP_WITH_DATED_SECTION.read_text())
    assert [type(violation) for violation in roadmap.violations()] == [
        RoadmapFormatViolation
    ]


def test_too_many_roadmap_entries_are_a_violation():
    measured = Measure.ROADMAP_ENTRY_COUNT.maximum + 1
    roadmap = Roadmap.from_text("# plan\n" + "- a rule\n" * measured)
    assert roadmap.violations() == [
        SizeViolation(Measure.ROADMAP_ENTRY_COUNT, "roadmap", measured)
    ]


def test_a_long_roadmap_entry_is_a_violation():
    measured = Measure.ROADMAP_ENTRY_LENGTH.maximum + 1
    roadmap = Roadmap.from_text("# plan\n- " + "x" * measured + "\n")
    assert roadmap.violations() == [
        SizeViolation(Measure.ROADMAP_ENTRY_LENGTH, "roadmap entry 1", measured)
    ]


# %% progress notes


def test_progress_notes_within_the_limit_have_no_violations():
    assert progress_violations("x" * Measure.PROGRESS_LENGTH.maximum) == []


def test_progress_notes_over_the_limit_are_a_violation(tmp_path):
    measured = Measure.PROGRESS_LENGTH.maximum + 1
    progress_path = tmp_path / "progress.md"
    progress_path.write_text("x" * measured)
    with pytest.raises(DocumentOverLimitError) as raised:
        check_progress_file(progress_path)
    assert raised.value == DocumentOverLimitError(
        LimitedDocument.PROGRESS_NOTES,
        [SizeViolation(Measure.PROGRESS_LENGTH, "progress notes", measured)],
    )
