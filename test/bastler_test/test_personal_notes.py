"""
Tests for :mod:`bastler.personal_notes`.

Fetching the notes branch through the shell's own resolution, and reading plan data off
the fetched reference. Run against scratch git repositories - no network.
"""

from __future__ import annotations

import pytest

from bastler.personal_notes import PersonalNotesBranch
from bastler.plan_item_bootstrap import HookScript, PlanDocument

from .scratch_repository import ScratchRepository

PLAN_IDENTIFIERS = ("beta-plan", "alpha-plan")
"""
Two plans, deliberately out of order so the listing's sorting shows.
"""

NOTES_FILES = {
    PlanDocument.MANIFEST.path_within_notes_branch(identifier): f"id: {identifier}\n"
    for identifier in PLAN_IDENTIFIERS
} | {PlanDocument.ROADMAP.path_within_notes_branch("alpha-plan"): "# Alpha\n"}
"""
What the published notes branch carries: a manifest per plan, a roadmap for one of them.
"""


@pytest.fixture
def notes(
    scratch_repository: ScratchRepository, scrubbed_environment
) -> PersonalNotesBranch:
    """
    The notes branch of a scratch clone whose configuration points at its own notes
    remote - nothing published on it yet.
    """
    scratch_repository.install_hook_scripts(HookScript.CONFIGURATION)
    scratch_repository.resolve_notes_remote_to()
    return PersonalNotesBranch(scratch_repository.project_root)


@pytest.fixture
def published_notes(
    scratch_repository: ScratchRepository, notes: PersonalNotesBranch
) -> PersonalNotesBranch:
    """
    The same notes branch once :data:`NOTES_FILES` are published and fetched.
    """
    scratch_repository.publish_notes_branch(NOTES_FILES)
    assert notes.fetch()
    return notes


# %% fetching


def test_a_published_branch_fetches(scratch_repository, notes):
    scratch_repository.publish_notes_branch(NOTES_FILES)
    assert notes.fetch() is True


def test_a_missing_branch_does_not_fetch(notes):
    assert notes.fetch() is False


# %% reading


def test_a_plan_document_reads_back_what_was_published(published_notes):
    manifest_path = PlanDocument.MANIFEST.path_within_notes_branch("alpha-plan")
    assert (
        published_notes.read_plan_document("alpha-plan", PlanDocument.MANIFEST)
        == NOTES_FILES[manifest_path]
    )


def test_a_missing_document_reads_as_none(published_notes):
    assert published_notes.read_plan_document("beta-plan", PlanDocument.ROADMAP) is None


def test_plan_identifiers_list_every_plan_with_a_manifest_in_order(published_notes):
    assert published_notes.plan_identifiers() == sorted(PLAN_IDENTIFIERS)
