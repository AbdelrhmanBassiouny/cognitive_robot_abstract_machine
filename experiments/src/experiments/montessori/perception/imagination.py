"""
The world a look's own findings stand in.

A look reports sightings, and a relation of the world's vocabulary is written over the
things themselves: a body, and whatever the world says about it. So what a look finds is
spawned into a copy of the world it was taken in, where every finding is a body standing
where it was seen and a relation asked about it has something real to be evaluated
against. The world the look was taken in is left as it was, and what a statement rejects
is removed from the copy again, so what the copy holds at the end is the answer.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Optional

from experiments.montessori.hole_geometry import extrude_polygon
from experiments.montessori.pieces import KnownPiece
from experiments.montessori.semantics import MONTESSORI_SHAPE_CLASSES, MontessoriShape
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Mesh
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

IMAGINATION_PREFIX = "imagined"
"""
What every body a look brings into the world of its own is named under, which is what
tells one apart from a body the world already held.
"""

# %% the world a look's findings stand in


@dataclass
class ImaginedWorld:
    """
    A copy of the world a look was taken in, holding what the look found as bodies.
    """

    world: World
    """
    The copy.

    Nothing here ever reaches the world it was copied from.
    """

    reference_frame: Optional[KinematicStructureEntity] = None
    """
    The frame the look reports its findings in, as the world the look was taken in names
    it, or None where the look reports them in none.

    A finding's pose keeps naming this frame rather than the copy's own counterpart, so
    what a caller reads off a detection is what it always was.
    """

    spawned: int = field(init=False, default=0)
    """
    How many findings have been spawned, which is what gives each its own name.
    """

    @classmethod
    def copied_from(
        cls,
        world: Optional[World],
        reference_frame: Optional[KinematicStructureEntity] = None,
    ) -> ImaginedWorld:
        """
        Take a copy of the world a look is about to be taken in.

        :param world: The world the look is taken in, or None where the look is taken in
            none -- a recording read without one -- in which case the copy holds only
            what the look finds.
        :param reference_frame: The frame the look reports its findings in.
        """
        if world is None:
            return cls(world=cls._world_of_its_own(), reference_frame=reference_frame)
        return cls(world=deepcopy(world), reference_frame=reference_frame)

    @staticmethod
    def _world_of_its_own() -> World:
        """
        :return: A world holding nothing but the ground a finding is hung from, for a
            look taken in no world at all.
        """
        world = World()
        with world.modify_world():
            world.add_body(Body(name=PrefixedName("ground", IMAGINATION_PREFIX)))
        return world

    def spawn(self, piece: KnownPiece, pose: Pose) -> MontessoriShape:
        """
        Stand a piece in this world where it was seen.

        A finding is welded where the look measured it, with no degree of freedom of its
        own: a look reports one placement, and nothing in this world moves what it found.
        A piece is instead given a free (:class:`Connection6DoF`) joint in the world the
        robot acts in, where gravity or a gripper can move it.

        :param piece: The piece that was recognised, whose own measured outline and
            height the body standing for it is built from.
        :param pose: Where it was seen, in :attr:`reference_frame`.
        :return: The piece as the world holds it, ready to be a detection's role taker.
        """
        name = PrefixedName(
            f"{piece.category}_{self.spawned}",
            IMAGINATION_PREFIX,
        )
        self.spawned += 1
        body = Body.from_shape_collection(name, ShapeCollection([self._mesh_of(piece)]))
        parent = self._frame_of(pose)
        with self.world.modify_world():
            self.world.add_connection(
                FixedConnection(
                    parent=parent,
                    child=body,
                    parent_T_connection_expression=self._transform_to(pose, parent),
                )
            )
            shape = MONTESSORI_SHAPE_CLASSES[piece.category](name=name, root=body)
            self.world.add_semantic_annotation(shape)
        return shape

    def remove(self, shape: MontessoriShape) -> None:
        """
        Take a piece out of this world again, because the statement rejected it.

        :param shape: The piece as this world holds it.
        """
        with self.world.modify_world():
            self.world.remove_semantic_annotation(shape)
            self.world.remove_branch_from_world(shape.root)

    @staticmethod
    def _mesh_of(piece: KnownPiece) -> Mesh:
        """
        :param piece: The piece that was recognised.
        :return: Its measured outline standing as tall as it was measured to stand.
        """
        solid = extrude_polygon(piece.outline, piece.height)
        mesh = Mesh.from_trimesh(mesh=solid)
        mesh.color = piece.color
        return mesh

    def _frame_of(self, pose: Pose) -> KinematicStructureEntity:
        """
        The entity of this world a finding seen at a pose hangs from.

        A pose names a frame of the world the look was taken in, so the copy's own
        counterpart is found by the name they share; a look reporting its findings in no
        frame, or in one this world does not hold, hangs them from its root.

        :param pose: Where the finding was seen.
        """
        frame = pose.reference_frame
        if frame is None:
            return self.world.root
        held = [
            entity
            for entity in self.world.kinematic_structure_entities
            if entity.name == frame.name
        ]
        return held[0] if held else self.world.root

    @staticmethod
    def _transform_to(
        pose: Pose, parent: KinematicStructureEntity
    ) -> HomogeneousTransformationMatrix:
        """
        :param pose: Where the finding was seen.
        :param parent: The entity of this world it hangs from.
        :return: The same place, said as the transform a connection is built from.
        """
        position = pose.to_position().to_np()
        roll, pitch, yaw = (
            np.asarray(angle).item() for angle in pose.to_rotation_matrix().to_rpy()
        )
        return HomogeneousTransformationMatrix.from_xyz_rpy(
            x=float(position[0]),
            y=float(position[1]),
            z=float(position[2]),
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            reference_frame=parent,
        )
