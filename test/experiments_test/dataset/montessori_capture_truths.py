"""
What each capture taken off the real camera shows.

Read off the picture by eye, so a detection result is measured against the scene rather
than against an earlier run of the same code.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Dict, Tuple, Type

from experiments.montessori.semantics import (
    CubeShape,
    CylinderShape,
    MontessoriShape,
    RectangularPrismShape,
    TriangularPrismShape,
)


@dataclass(frozen=True)
class CaptureTruth:
    """
    What one capture really holds, as a reader of the picture can see it.
    """

    pieces_on_table: Tuple[Type[MontessoriShape], ...]
    """
    Every loose piece resting on the bare table, one entry per physical piece.
    """

    pieces_on_lid: Tuple[Type[MontessoriShape], ...]
    """
    Every piece resting on, or standing in a hole of, the board's lid.
    """

    @property
    def pieces(self) -> Tuple[Type[MontessoriShape], ...]:
        """
        Every piece in the scene, wherever it rests.
        """
        return self.pieces_on_table + self.pieces_on_lid


CAPTURE_TRUTHS: Dict[str, CaptureTruth] = {
    "objects_on_montessori": CaptureTruth(
        pieces_on_table=(
            CylinderShape,
            TriangularPrismShape,
        ),
        pieces_on_lid=(
            CubeShape,
            RectangularPrismShape,
        ),
    ),
    "stuck_cube_in_hole": CaptureTruth(
        pieces_on_table=(
            CylinderShape,
            RectangularPrismShape,
            TriangularPrismShape,
        ),
        pieces_on_lid=(CubeShape,),
    ),
    "disoriented_cube_on_hole": CaptureTruth(
        pieces_on_table=(
            CylinderShape,
            RectangularPrismShape,
            TriangularPrismShape,
        ),
        pieces_on_lid=(CubeShape,),
    ),
    "displaced_cube_from_hole": CaptureTruth(
        pieces_on_table=(
            CylinderShape,
            RectangularPrismShape,
            TriangularPrismShape,
        ),
        pieces_on_lid=(CubeShape,),
    ),
    "non_inserted_objects": CaptureTruth(
        pieces_on_table=(),
        pieces_on_lid=(
            CubeShape,
            CylinderShape,
            RectangularPrismShape,
        ),
    ),
    "tracy_pickup_demo": CaptureTruth(
        pieces_on_table=(
            RectangularPrismShape,
            TriangularPrismShape,
        ),
        pieces_on_lid=(
            CubeShape,
            CylinderShape,
        ),
    ),
}
"""
What each shipped capture shows, keyed by the capture's own name.

Every one of them holds the shape-sorting board, so only the loose pieces differ.
"""
