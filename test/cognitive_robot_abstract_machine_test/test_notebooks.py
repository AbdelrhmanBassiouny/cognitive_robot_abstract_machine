"""
Tests for carrying a notebook's Jupyter Book visibility tags into a live session.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import nbformat
import pytest
from nbformat import NotebookNode

from cognitive_robot_abstract_machine.notebooks import (
    CellMetadataKey,
    CellVisibilityTag,
    Notebook,
)

# %% a notebook holding one cell per visibility tag

DATASET_NOTEBOOK = Path(__file__).parent / "dataset" / "tagged_cells.ipynb"
"""
The notebook the tests work on, one cell per case its tags can produce.
"""

SOLUTION_CELL = 0
"""
Position of the cell tagged to hide both its source and its outputs.
"""

SETUP_CELL = 1
"""
Position of the cell tagged to hide its source only.
"""

NOISY_CELL = 2
"""
Position of the cell tagged to hide its outputs only.
"""

EXERCISE_CELL = 3
"""
Position of the cell that carries no visibility tag but was left collapsed by an earlier
run.
"""

PROSE_CELL = 4
"""
Position of the cell that carries neither a visibility tag nor a collapsed state.
"""


@pytest.fixture
def notebook(tmp_path: Path) -> Notebook:
    """
    A writable copy of the tagged notebook.
    """
    path = tmp_path / DATASET_NOTEBOOK.name
    shutil.copy(DATASET_NOTEBOOK, path)
    return Notebook(path)


def cell_of(notebook: Notebook, position: int) -> NotebookNode:
    """
    Read a cell back from the notebook file.

    :param notebook: Notebook to read.
    :param position: Position of the cell in the notebook.
    :return: The cell as it is stored on disk.
    """
    return nbformat.read(notebook.path, as_version=nbformat.NO_CONVERT).cells[position]


def collapsed_state_of(notebook: Notebook, position: int) -> dict:
    """
    Read the collapsed state a live session applies to a cell.

    :param notebook: Notebook to read.
    :param position: Position of the cell in the notebook.
    :return: The cell's ``jupyter`` metadata, empty when it carries none.
    """
    return cell_of(notebook, position).metadata.get(CellMetadataKey.JUPYTER, {})


# %% what each tag hides


def test_hide_cell_tag_collapses_source_and_outputs(notebook: Notebook) -> None:
    notebook.hide_tagged_cells()
    assert collapsed_state_of(notebook, SOLUTION_CELL) == {
        CellMetadataKey.SOURCE_HIDDEN: True,
        CellMetadataKey.OUTPUTS_HIDDEN: True,
    }


def test_hide_input_tag_collapses_the_source_only(notebook: Notebook) -> None:
    notebook.hide_tagged_cells()
    assert collapsed_state_of(notebook, SETUP_CELL) == {
        CellMetadataKey.SOURCE_HIDDEN: True
    }


def test_hide_output_tag_collapses_the_outputs_only(notebook: Notebook) -> None:
    notebook.hide_tagged_cells()
    assert collapsed_state_of(notebook, NOISY_CELL) == {
        CellMetadataKey.OUTPUTS_HIDDEN: True
    }


def test_tags_of_a_hidden_cell_are_kept(notebook: Notebook) -> None:
    notebook.hide_tagged_cells()
    assert cell_of(notebook, SOLUTION_CELL).metadata[CellMetadataKey.TAGS] == [
        CellVisibilityTag.HIDE_CELL,
        "example-solution",
    ]


# %% cells no tag hides


def test_cell_without_a_visibility_tag_is_expanded_again(notebook: Notebook) -> None:
    notebook.hide_tagged_cells()
    assert collapsed_state_of(notebook, EXERCISE_CELL) == {}


def test_untagged_cell_is_left_unchanged(notebook: Notebook) -> None:
    changed = notebook.hide_tagged_cells()
    assert PROSE_CELL not in changed
    assert collapsed_state_of(notebook, PROSE_CELL) == {}


# %% repeated runs


def test_positions_of_the_cells_it_changed_are_reported(notebook: Notebook) -> None:
    assert notebook.hide_tagged_cells() == [
        SOLUTION_CELL,
        SETUP_CELL,
        NOISY_CELL,
        EXERCISE_CELL,
    ]


def test_hiding_an_already_hidden_notebook_changes_nothing(
    notebook: Notebook,
) -> None:
    notebook.hide_tagged_cells()
    content = notebook.path.read_text(encoding="utf-8")

    assert notebook.hide_tagged_cells() == []
    assert notebook.path.read_text(encoding="utf-8") == content
