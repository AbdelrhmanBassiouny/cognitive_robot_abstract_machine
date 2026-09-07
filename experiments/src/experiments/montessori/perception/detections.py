"""
What one look at the Montessori scene found.

These are the values an :mod:`entity query language <krrood.entity_query_language>`
query ranges over, so they carry the pose a caller asks for together with the
measurements that let a query pick one detection out of several.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import cv2
import numpy as np
from typing_extensions import List, Optional

from experiments.montessori.perception.explanations import BoardOutlines, Explanation
from experiments.montessori.perception.footprint import Footprint
from experiments.montessori.perception.hypotheses import PieceHypothesis
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% detections


@dataclass(eq=False)
class MontessoriDetection(ABC):
    """
    Something perception recognised, and where it is.
    """

    pose: Pose
    """
    Where it was seen, in the frame the camera's pose was given in.
    """

    footprint: Footprint
    """
    Its outline as measured from the rectified image.
    """

    outline: np.ndarray
    """
    The outline itself, as ``(n, 2)`` world-frame ``(x, y)`` points on the surface it
    was seen on.
    """

    @property
    def surface_height(self) -> float:
        """
        Height of the surface this was seen lying on, in metres.

        A detection sits on the plane it was rectified from, so its pose already names
        that height.
        """
        return float(self.pose.to_position().to_np()[2])

    @property
    def yaw(self) -> float:
        """
        How far it is turned about the world frame's z-axis, in radians.
        """
        return float(self.pose.to_rotation_matrix().to_rpy()[2])

    @property
    def top_height(self) -> float:
        """
        Height of this detection's own topmost surface, in metres.

        A detection with no measured thickness lies flat in the surface it was found in,
        so its top is that surface.
        """
        return self.surface_height

    @property
    @abstractmethod
    def label(self) -> str:
        """
        A short name for what was recognised, for reporting and for drawing alongside
        it.
        """

    def encloses(self, x: float, y: float) -> bool:
        """
        Whether a world-frame position lies within this detection's outline.

        :param x: Position along the world frame's x-axis, in metres.
        :param y: Position along the world frame's y-axis, in metres.
        """
        polygon = np.asarray(self.outline, dtype=np.float32).reshape(-1, 1, 2)
        return cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0


@dataclass(eq=False)
class MontessoriShapeDetection(MontessoriDetection):
    """
    A loose Montessori piece lying on the table.
    """

    category: MontessoriShapeCategory = field(kw_only=True)
    """
    The geometric shape it was recognised as, matched against a hole's own category to
    decide which hole it belongs in.
    """

    supporting_surface: PrefixedName = field(kw_only=True)
    """
    What the world calls the surface it was found resting on.

    A piece is looked for on each of the scene's surfaces in turn, so which one it
    stands on is something the look established rather than something a reader has to
    infer from how high it sits.
    """

    height: float = field(kw_only=True)
    """
    How far its top surface stands above the surface it rests on, in metres.

    Read from the depth image where that image resolves the piece, and otherwise the
    height :attr:`~experiments.montessori.perception.pipeline.LoosePieceDetector.piece_height`
    says a loose piece stands: a depth sensor that cannot tell a two centimetre piece
    from the surface under it says nothing about how tall the piece is, and reporting
    zero would place it in the surface itself.

    :attr:`pose` places the piece's centre half this height above the resting surface.
    """

    explanation: Explanation = field(kw_only=True)
    """
    How well this piece accounts for the edges seen where it was found.

    The evidence for :attr:`hypothesis`, and what a rival account of the same place is
    compared against, which is how a piece is told apart from its own reflection in the
    table and from an edge the board itself produces.
    """

    @property
    def outline_agreement(self) -> float:
        """
        How much of the recognised piece's own outline lay along an edge the camera saw.

        One is a perfect fit. A low value says no placement of this piece follows what
        is in the picture. On its own it says nothing about what put those edges there,
        which is why it is one side of :attr:`explanation` rather than the whole of it.
        """
        return self.explanation.outline_followed

    hypothesis: PieceHypothesis = field(kw_only=True)
    """
    What was expected here and what suggested it, which is what this detection answers.

    A result carries what it was looked for and why, so it can be explained rather than
    only checked.
    """

    @property
    def surface_height(self) -> float:
        """
        Height of the surface this piece rests on, in metres.

        Its pose stands half its own height above that surface, unlike a detection that
        lies flat in the plane it was found in.
        """
        return float(self.pose.to_position().to_np()[2]) - self.height / 2

    @property
    def top_height(self) -> float:
        """
        Height of this piece's own top face, in metres.
        """
        return self.surface_height + self.height

    @property
    def label(self) -> str:
        return str(self.category)


@dataclass(eq=False)
class ShapeSortingHoleDetection(MontessoriDetection):
    """
    One hole cut into the board's lid, and the point at its centre a matching piece is
    dropped through.
    """

    category: MontessoriShapeCategory = field(kw_only=True)
    """
    The geometric shape of the hole, matched against a piece's own category to decide
    which pieces fit through it.
    """

    @property
    def label(self) -> str:
        return str(self.category)


@dataclass(eq=False)
class MontessoriBoardDetection(MontessoriDetection):
    """
    The shape-sorting board, and the holes found in its lid.
    """

    holes: List[ShapeSortingHoleDetection] = field(kw_only=True, default_factory=list)
    """
    The holes found in this board's lid.
    """

    lid_height: float = field(kw_only=True, default=0.0)
    """
    Height of the lid the holes were found on, above the world frame's origin, in
    metres.
    """

    @property
    def label(self) -> str:
        return "board"

    def outlines_in(self, plane_height: float, seen_from: np.ndarray) -> BoardOutlines:
        """
        Where this board's own edges fall in a rectification onto one plane.

        Its lid's border and every hole cut through it are in the picture whether or not
        anything rests on it, so they are what a piece found there has to explain better
        than.

        :param plane_height: Height of the plane they are wanted in, in metres.
        :param seen_from: Where the camera stands, as world-frame ``(x, y, z)``.
        """
        return BoardOutlines.cast_onto(
            [self.outline, *(hole.outline for hole in self.holes)],
            lying_at=self.lid_height,
            plane_height=plane_height,
            seen_from=seen_from,
        )


# %% one look at the scene


@dataclass(eq=False)
class MontessoriScene:
    """
    Everything one pass of the pipeline recognised.
    """

    shapes: List[MontessoriShapeDetection] = field(default_factory=list)
    """
    The loose pieces found on the table.
    """

    board: Optional[MontessoriBoardDetection] = None
    """
    The shape-sorting board, or None if it was not in view.
    """

    @property
    def holes(self) -> List[ShapeSortingHoleDetection]:
        """
        The holes found in the board's lid, empty when no board was in view.
        """
        return list(self.board.holes) if self.board is not None else []

    @property
    def detections(self) -> List[MontessoriDetection]:
        """
        Everything recognised, flattened: the pieces, the board, and its holes.
        """
        board = [self.board] if self.board is not None else []
        return [*self.shapes, *board, *self.holes]
