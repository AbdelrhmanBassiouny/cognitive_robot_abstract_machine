"""
Which bodies of a world are loose objects, as opposed to furniture or the robot.

The recorder and the live bridge both need this answered the same way: a live attach
overlays the running world's poses onto the keys a recording filed its objects under, so
the two must agree on both the selection and the key.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.world_description.connections import Connection6DoF
from typing_extensions import Dict, List, Optional, TYPE_CHECKING

from cramera.mesh_format import MeshFormat

if TYPE_CHECKING:
    from semantic_digital_twin.robots.robot_parts import AbstractRobot
    from semantic_digital_twin.world import World
    from semantic_digital_twin.world_description.world_entity import (
        Body,
        KinematicStructureEntity,
    )


@dataclass(frozen=True)
class LooseObjects:
    """
    The objects of one world: what a demo puts on the table, rather than the table.
    """

    world: World
    """
    The world whose bodies are classified.
    """

    robot: Optional[AbstractRobot] = None
    """
    The robot of :attr:`world`, whose own bodies are never objects; None without one.
    """

    @staticmethod
    def key_of(entity: KinematicStructureEntity) -> str:
        """
        The key an entity's geometry and poses are published under: its local name,
        without the prefix a composed world gives it.

        :param entity: The body or region to key.
        """
        return str(entity.name).split("/")[-1]

    def keyed_bodies(self) -> Dict[str, Body]:
        """
        Every loose object of :attr:`world`, by the key it is published under.
        """
        bodies = {self.key_of(body): body for body in self.mesh_named_bodies()}
        for body in self.free_floating_bodies():
            bodies.setdefault(self.key_of(body), body)
        return bodies

    def mesh_named_bodies(self) -> List[Body]:
        """
        Bodies a mesh-loading demo named after the file their geometry came from.

        That name is how such a world says the body is one of its objects, whether or
        not it also lets it move.
        """
        return [
            body
            for body in self._candidate_bodies()
            if MeshFormat.of_path(self.key_of(body)) is not None
        ]

    def free_floating_bodies(self) -> List[Body]:
        """
        Bodies the world lets move freely, which is how a world built in code says a
        body is loose rather than part of the furniture.
        """
        return [
            body
            for body in self._candidate_bodies()
            if isinstance(body.parent_connection, Connection6DoF)
        ]

    def _candidate_bodies(self) -> List[Body]:
        """
        The bodies of :attr:`world` that are not part of :attr:`robot`.
        """
        robot_body_names = (
            {str(body.name) for body in self.robot.bodies}
            if self.robot is not None
            else set()
        )
        return [
            body for body in self.world.bodies if str(body.name) not in robot_body_names
        ]
