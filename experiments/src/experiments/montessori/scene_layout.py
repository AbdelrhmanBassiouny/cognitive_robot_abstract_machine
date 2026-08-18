"""
The Montessori scene's fixed layout, in the shape questions are asked of it.

Kept alongside :mod:`experiments.montessori.sorting_progress`: that module records what
the sort *does*, this one records what the scene *is* — the board, the holes cut into
it, and where each shape's insertion goal lies. Every entity here is plain data with a
``name``, read once from the world when the demo attaches, so answering a "where is"
question never reaches into the world.

Each record is named by the key the viewer publishes the underlying world entity under,
so an answer row for it lights that entity up in the scene.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cramera.body_geometry import NumericPose
from cramera.loose_objects import LooseObjects
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from typing_extensions import List

from experiments.montessori.semantics import (
    MontessoriShape,
    ShapeSortingBoard,
    ShapeSortingHole,
)


@dataclass
class HoleRecord:
    """
    One hole cut into the board, and where it is.
    """

    name: str
    """
    The hole's key, e.g. ``"square_hole"``, which is also the id the viewer shows it
    under.
    """

    shape_category: str
    """
    The geometric category of shape this hole accepts.
    """

    pose: NumericPose
    """
    The hole's pose in the world root frame.
    """


@dataclass
class BoardRecord:
    """
    The shape-sorting board — the montessori box — and where it is.
    """

    name: str
    """
    The board's key, e.g. ``"board"``, which is also the id the viewer shows it under.
    """

    pose: NumericPose
    """
    The board's pose in the world root frame.
    """


@dataclass
class InsertionGoalRecord:
    """
    Where one shape is meant to end up: its matching hole and the release pose above it.
    """

    name: str
    """
    The goal's label, e.g. ``"cube goal"``.
    """

    shape: str
    """
    What the piece is, e.g. ``"cube"`` (see
    :attr:`~experiments.montessori.semantics.MontessoriShape.object_name`).
    """

    hole: str
    """
    Key of the hole the shape is meant to be dropped through.
    """

    pose: NumericPose
    """
    The pose, in the world root frame, the shape must be released at to drop through its
    hole.
    """

    def related_highlight_ids(self) -> List[str]:
        """
        The hole this goal names, so an answer row for the goal lights the hole up.
        """
        return [self.hole]


@dataclass
class SceneLayout:
    """
    Everything fixed about the scene a "where is" question asks about.
    """

    holes: List[HoleRecord] = field(default_factory=list)
    """
    One entry per hole cut into a board of the scene.
    """

    boards: List[BoardRecord] = field(default_factory=list)
    """
    One entry per shape-sorting board of the scene.
    """

    goals: List[InsertionGoalRecord] = field(default_factory=list)
    """
    One entry per shape that has a matching hole to be dropped through.
    """

    @classmethod
    def of_world(cls, world: World) -> SceneLayout:
        """
        Read the scene's boards, holes and insertion goals out of a built world.

        Reads the world, so it must be called from the thread that owns it — once, when
        the demo attaches — never from the one answering queries.

        :param world: The world the scene was built into.
        """
        layout = cls()
        for board in world.get_semantic_annotations_by_type(ShapeSortingBoard):
            layout.boards.append(
                BoardRecord(
                    name=LooseObjects.key_of(board.root),
                    pose=NumericPose.of_pose(board.root.global_pose),
                )
            )
            layout.holes.extend(cls._hole_records(board))
            layout.goals.extend(cls._goal_records(board, world))
        return layout

    @staticmethod
    def _hole_records(board: ShapeSortingBoard) -> List[HoleRecord]:
        """
        One record per hole of ``board``.

        :param board: The board whose holes are read.
        """
        return [
            HoleRecord(
                name=LooseObjects.key_of(hole.root),
                shape_category=str(hole.shape_category),
                pose=NumericPose.of_pose(hole.root.global_pose),
            )
            for hole in board.holes
        ]

    @staticmethod
    def _goal_records(
        board: ShapeSortingBoard, world: World
    ) -> List[InsertionGoalRecord]:
        """
        One record per shape of the world that fits through a hole of ``board``.

        :param board: The board the shapes are meant to be sorted into.
        :param world: The world the shapes live in.
        """
        return [
            InsertionGoalRecord(
                name="%s goal" % shape.object_name,
                shape=shape.object_name,
                hole=LooseObjects.key_of(board.hole_for(shape).root),
                pose=NumericPose.of_pose(board.insertion_target_for(shape, world)),
            )
            for shape in world.get_semantic_annotations_by_type(MontessoriShape)
            if board.fitting_holes(shape)
        ]


def scene_entities_of(world: World) -> List[KinematicStructureEntity]:
    """
    The fixed world entities the viewer should show for this scene: every board and
    every hole (see :meth:`~cramera.live.bridge.Bridge.register_scene_entities`).

    :param world: The world the scene was built into.
    """
    entities: List[KinematicStructureEntity] = []
    for board in world.get_semantic_annotations_by_type(ShapeSortingBoard):
        entities.append(board.root)
        entities.extend(hole.root for hole in board.holes)
    return entities
