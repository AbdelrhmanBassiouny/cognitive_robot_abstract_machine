"""
Tests for notes_markers.py: reading the sections a session edits in CLAUDE.local.md.
"""

from __future__ import annotations

from basstler.notes_markers import NotesMarker

from .constants import DatasetLocation

MARKED_NOTES = (DatasetLocation.DIRECTORY / "claude-local-with-markers.md").read_text()
"""
A CLAUDE.local.md with a personal-notes section, an empty progress section, a plan
manifest section labelled with its plan, and no roadmap section.
"""


def test_a_section_is_the_text_between_its_markers():
    assert NotesMarker.PERSONAL_NOTES.section_in(MARKED_NOTES) == "- a rule\n"


def test_a_labelled_begin_marker_opens_its_section():
    assert NotesMarker.PLAN_MANIFEST.section_in(MARKED_NOTES) == (
        "id: some-plan\nitems: []\n"
    )


def test_an_empty_section_reads_as_empty_text():
    assert NotesMarker.PR_PROGRESS.section_in(MARKED_NOTES) == ""


def test_a_missing_section_reads_as_none():
    assert NotesMarker.PLAN_ROADMAP.section_in(MARKED_NOTES) is None
