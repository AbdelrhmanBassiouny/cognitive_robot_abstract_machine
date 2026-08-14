"""
Notebooks whose cells are tagged for Jupyter Book.

Those tags hide a cell only in the book Jupyter Book renders. A reader who opens the
notebook itself instead -- in JupyterLab, or on Binder -- gets a live session, which
ignores the tags and shows every cell. What a live session does collapse is the
``jupyter`` metadata of a cell, so the tags have to be written into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import reduce
from operator import or_
from pathlib import Path

import nbformat
from nbformat import NotebookNode
from typing_extensions import Iterable, List, Mapping

# %% the vocabulary of a tagged cell


class CellVisibilityTag(StrEnum):
    """
    The Jupyter Book tags that hide part of a cell.
    """

    HIDE_CELL = "hide-cell"
    """
    Hides the source and the outputs.
    """

    HIDE_INPUT = "hide-input"
    """
    Hides the source.
    """

    HIDE_OUTPUT = "hide-output"
    """
    Hides the outputs.
    """


class CellMetadataKey(StrEnum):
    """
    The cell metadata a notebook file stores the tags and the collapsed state under.
    """

    TAGS = "tags"
    """
    The tags of a cell.
    """

    JUPYTER = "jupyter"
    """
    The collapsed state a live session reads.
    """

    SOURCE_HIDDEN = "source_hidden"
    """
    Whether a live session collapses the source, within :attr:`JUPYTER`.
    """

    OUTPUTS_HIDDEN = "outputs_hidden"
    """
    Whether a live session collapses the outputs, within :attr:`JUPYTER`.
    """


# %% what a tag hides


@dataclass(frozen=True)
class HiddenParts:
    """
    The parts of a cell that are collapsed behind a toggle rather than shown.
    """

    source: bool = False
    """
    Whether the source is collapsed.
    """

    outputs: bool = False
    """
    Whether the outputs are collapsed.
    """

    def __or__(self, other: HiddenParts) -> HiddenParts:
        """
        Combine two hidings into the one that hides whatever either of them hides.

        :param other: The hiding to combine this one with.
        :return: The combined hiding.
        """
        return HiddenParts(self.source or other.source, self.outputs or other.outputs)

    @classmethod
    def of_tags(cls, tags: Iterable[str]) -> HiddenParts:
        """
        Read what the visibility tags among a cell's tags hide.

        :param tags: All tags of the cell, visibility tags and others alike.
        :return: What the visibility tags hide, nothing when there are none.
        """
        return reduce(
            or_,
            (HIDDEN_PARTS_BY_TAG[tag] for tag in tags if tag in HIDDEN_PARTS_BY_TAG),
            cls(),
        )

    def write_to(self, cell_metadata: NotebookNode) -> bool:
        """
        Make a cell's metadata collapse exactly these parts in a live session.

        :param cell_metadata: Metadata of the cell, updated in place.
        :return: Whether the metadata said something else before.
        """
        collapsed = {
            CellMetadataKey.SOURCE_HIDDEN: self.source,
            CellMetadataKey.OUTPUTS_HIDDEN: self.outputs,
        }
        current = dict(cell_metadata.get(CellMetadataKey.JUPYTER, {}))
        updated = {key: value for key, value in current.items() if key not in collapsed}
        updated.update({key: True for key, hidden in collapsed.items() if hidden})

        if updated == current:
            return False

        if updated:
            cell_metadata[CellMetadataKey.JUPYTER] = updated
        else:
            cell_metadata.pop(CellMetadataKey.JUPYTER)
        return True


HIDDEN_PARTS_BY_TAG: Mapping[CellVisibilityTag, HiddenParts] = {
    CellVisibilityTag.HIDE_CELL: HiddenParts(source=True, outputs=True),
    CellVisibilityTag.HIDE_INPUT: HiddenParts(source=True),
    CellVisibilityTag.HIDE_OUTPUT: HiddenParts(outputs=True),
}
"""
What each visibility tag hides.
"""


# %% a notebook file


@dataclass
class Notebook:
    """
    A notebook file on disk.
    """

    path: Path
    """
    Location of the ``.ipynb`` file.
    """

    def hide_tagged_cells(self) -> List[int]:
        """
        Collapse in a live session what the visibility tags hide in the book.

        Cells that carry no visibility tag are expanded again, so that the file always
        says what its tags say, and the notebook is only rewritten when something
        actually changed.

        :return: Positions of the cells whose collapsed state changed.
        """
        notebook = nbformat.read(self.path, as_version=nbformat.NO_CONVERT)
        changed = [
            position
            for position, cell in enumerate(notebook.cells)
            if HiddenParts.of_tags(
                cell.metadata.get(CellMetadataKey.TAGS, ())
            ).write_to(cell.metadata)
        ]

        if changed:
            nbformat.write(notebook, self.path)
        return changed
