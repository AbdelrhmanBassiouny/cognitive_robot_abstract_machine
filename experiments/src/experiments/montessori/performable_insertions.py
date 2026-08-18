"""
The insertions a running Montessori sort can be asked to carry out, in the shape
questions are asked of them.

Kept alongside :mod:`experiments.montessori.scene_layout`: that module records what the
scene *is*, this one records what the robot can be asked to *do* in it. Every entity
here is plain data with a ``name``, read once from the world when the demo attaches, so
answering with them never reaches into the world.
"""

from __future__ import annotations

from dataclasses import dataclass

from cramera.knowledge.performable_action import PerformableAction
from cramera.loose_objects import LooseObjects
from krrood.exceptions import DataclassException
from semantic_digital_twin.world import World
from typing_extensions import List

from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard


@dataclass
class InsertableShapeMissing(DataclassException):
    """
    Raised when an insertion is carried out in a world that holds no such piece.
    """

    shape_key: str
    """
    Key of the piece that was looked for.
    """

    def error_message(self) -> str:
        return "no shape '%s' is in this world" % self.shape_key

    def suggest_correction(self) -> str:
        return "Read the insertions off the world the sort is running in."


@dataclass
class PerformableInsertion:
    """
    One shape of the scene going through the hole it fits, as something the robot can be
    asked to do.
    """

    name: str
    """
    What the insertion is called, e.g. ``"insert cube"``, and the name the viewer asks
    for it back by.
    """

    shape: str
    """
    What the piece is, e.g. ``"cube"`` (see
    :attr:`~experiments.montessori.semantics.MontessoriShape.object_name`).
    """

    shape_key: str
    """
    The key pairing the shape with its hole, e.g. ``"square_hole"``, which is how the
    world names the piece this insertion picks up.
    """

    hole: str
    """
    Key of the hole the shape is meant to be dropped through, and the id the viewer
    shows that hole under.
    """

    def performable_action(self) -> PerformableAction:
        """
        This insertion as the action an answer row offers to perform.
        """
        return PerformableAction(
            name=self.name,
            description="insert the %s through the %s"
            % (self.shape.replace("_", " "), self.hole.replace("_", " ")),
        )

    def shape_in(self, world: World) -> MontessoriShape:
        """
        The piece this insertion picks up, found in a built world.

        Reads the world, so it must be called from the thread that owns it.

        :param world: The world this insertion was read from.
        :raises InsertableShapeMissing: When that world holds no such piece.
        """
        for shape in world.get_semantic_annotations_by_type(MontessoriShape):
            if shape.shape_key == self.shape_key:
                return shape
        raise InsertableShapeMissing(shape_key=self.shape_key)

    @classmethod
    def of_world(cls, world: World) -> List[PerformableInsertion]:
        """
        One insertion per shape of the world that fits through a hole of one of its
        boards.

        Reads the world, so it must be called from the thread that owns it — once, when
        the demo attaches — never from the one answering queries.

        :param world: The world the scene was built into.
        """
        return [
            cls(
                name="insert %s" % shape.object_name,
                shape=shape.object_name,
                shape_key=shape.shape_key,
                hole=LooseObjects.key_of(board.hole_for(shape).root),
            )
            for board in world.get_semantic_annotations_by_type(ShapeSortingBoard)
            for shape in world.get_semantic_annotations_by_type(MontessoriShape)
            if board.fitting_holes(shape)
        ]
