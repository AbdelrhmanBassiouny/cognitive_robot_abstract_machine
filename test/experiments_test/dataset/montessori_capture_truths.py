"""
What each capture taken off the real camera shows.

Read off the picture by eye, and for the later captures measured on the table with a
tape as well, so a detection result is measured against the scene rather than against an
earlier run of the same code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Dict, Optional, Tuple

from experiments.montessori.pieces import (
    FULL_SIZE_PIECES,
    SMALLER_PIECES,
    KnownPieceSet,
)
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShapeCategory


@dataclass(frozen=True)
class TapeMeasuredPiece:
    """
    One loose piece and where a tape measure put its middle on the table.
    """

    category: MontessoriShapeCategory
    """
    Which kind of piece it is.
    """

    place: PlanarPoint
    """
    Where its middle stands, in the frame detections are reported in.
    """


@dataclass(frozen=True)
class CaptureTruth:
    """
    What one capture really holds, as a reader of the picture can see it.
    """

    pieces_on_table: Tuple[MontessoriShapeCategory, ...]
    """
    Every loose piece resting on the bare table, one entry per physical piece.
    """

    pieces_on_lid: Tuple[MontessoriShapeCategory, ...]
    """
    Every piece resting on, or standing in a hole of, the board's lid.
    """

    piece_set: KnownPieceSet = FULL_SIZE_PIECES
    """
    Which physical set the pieces in the capture belong to.
    """

    tape_measured: Tuple[TapeMeasuredPiece, ...] = ()
    """
    The pieces whose places were measured on the table with a tape, or none where only
    the picture was read.
    """

    board_front_left_corner: Optional[PlanarPoint] = None
    """
    Where a tape put the corner of the board's lid nearest the robot on the robot's
    left -- the drawers face the robot -- or None where it was not measured.
    """

    @property
    def pieces(self) -> Tuple[MontessoriShapeCategory, ...]:
        """
        Every piece in the scene, wherever it rests.
        """
        return self.pieces_on_table + self.pieces_on_lid


CAPTURE_TRUTHS: Dict[str, CaptureTruth] = {
    "objects_on_montessori": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        pieces_on_lid=(
            MontessoriShapeCategory.CUBE,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
        ),
    ),
    "stuck_cube_in_hole": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        pieces_on_lid=(MontessoriShapeCategory.CUBE,),
    ),
    "disoriented_cube_on_hole": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        pieces_on_lid=(MontessoriShapeCategory.CUBE,),
    ),
    "displaced_cube_from_hole": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        pieces_on_lid=(MontessoriShapeCategory.CUBE,),
    ),
    "non_inserted_objects": CaptureTruth(
        pieces_on_table=(),
        pieces_on_lid=(
            MontessoriShapeCategory.CUBE,
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
        ),
    ),
    "tracy_pickup_demo": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        pieces_on_lid=(
            MontessoriShapeCategory.CUBE,
            MontessoriShapeCategory.CYLINDER,
        ),
    ),
    "scaled_pieces_in_a_row": CaptureTruth(
        pieces_on_table=(
            MontessoriShapeCategory.CYLINDER,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.CUBE,
        ),
        pieces_on_lid=(),
        piece_set=SMALLER_PIECES,
        tape_measured=(
            TapeMeasuredPiece(MontessoriShapeCategory.CYLINDER, PlanarPoint(0.79, 0.0)),
            TapeMeasuredPiece(
                MontessoriShapeCategory.TRIANGULAR_PRISM, PlanarPoint(0.79, 0.10)
            ),
            TapeMeasuredPiece(
                MontessoriShapeCategory.RECTANGULAR_PRISM, PlanarPoint(0.79, 0.20)
            ),
            TapeMeasuredPiece(MontessoriShapeCategory.CUBE, PlanarPoint(0.79, 0.30)),
        ),
        board_front_left_corner=PlanarPoint(0.99, 0.30),
    ),
}
"""
What each shipped capture shows, keyed by the capture's own name.

Every one of them holds the shape-sorting board, so only the loose pieces differ. The
first six hold the full-size set; ``scaled_pieces_in_a_row`` was taken on 2026-09-11 of
the smaller set standing in a row, each piece and the board measured with a tape.
"""
