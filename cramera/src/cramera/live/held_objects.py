"""
What the robot of a running demo is carrying right now.

An object is carried when the world's kinematic tree hangs it off the robot: grasping
reparents it onto a gripper body, releasing it puts it back under the world. Read on the
simulation thread, because it walks the executing world rather than a snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Dict, List, Optional, TYPE_CHECKING

from semantic_digital_twin.robots.robot_parts import AbstractRobot

from cramera.knowledge.entity import NamedEntity
from cramera.robot_parts import ArmSide, RobotPartAnnotation, RobotPartRole

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import (
        Body,
        KinematicStructureEntity,
    )


@dataclass
class HeldObject(NamedEntity):
    """
    One object the robot is holding at this moment.
    """

    attached_to: str
    """
    Name of the robot body the object hangs from.
    """

    arm: Optional[str] = None
    """
    Name of the arm annotation carrying the object, or None when it hangs off a robot
    body that belongs to no annotated arm.
    """

    side: Optional[ArmSide] = None
    """
    Which arm carries the object, or None for a robot that names no left and right arm.
    """

    @classmethod
    def of_bodies(
        cls, robot: Optional[AbstractRobot], bodies: Dict[str, Body]
    ) -> List[HeldObject]:
        """
        The objects among ``bodies`` that currently hang off ``robot``.

        :param robot: The robot annotation of the executing world, or None while none is
            bound.
        :param bodies: The published loose objects, keyed as the viewer shows them.
        """
        if robot is None:
            return []
        parts = cls._parts_by_body_name(robot)
        root_name = RobotPartAnnotation.body_name(robot.root)
        held = [
            cls._of_body(key, body, parts, root_name) for key, body in bodies.items()
        ]
        return [entry for entry in held if entry is not None]

    @classmethod
    def _of_body(
        cls,
        key: str,
        body: Body,
        parts: Dict[str, RobotPartAnnotation],
        root_name: str,
    ) -> Optional[HeldObject]:
        """
        One object as a held one, or None when it does not hang off the robot.

        The nearest robot body above the object is what carries it, even when the object
        hangs off another object that is itself held.

        :param key: The object's published key.
        :param body: The object's body in the executing world.
        :param parts: The robot's arm and end-effector bodies (see
            :meth:`_parts_by_body_name`).
        :param root_name: Name of the robot's root body.
        """
        holder = cls._robot_ancestor(body, parts, root_name)
        if holder is None:
            return None
        part = parts.get(holder)
        if part is None:
            return cls(name=key, attached_to=holder)
        return cls(name=key, attached_to=holder, arm=cls._arm(part), side=part.side)

    @staticmethod
    def _parts_by_body_name(robot: AbstractRobot) -> Dict[str, RobotPartAnnotation]:
        """
        The arm or end effector each of the robot's annotated bodies belongs to, keyed
        by body name.

        :param robot: The robot annotation whose parts are indexed.
        """
        return {
            body_name: part
            for part in RobotPartAnnotation.of_robot(robot)
            for body_name in part.links
        }

    @staticmethod
    def _robot_ancestor(
        body: Body, parts: Dict[str, RobotPartAnnotation], root_name: str
    ) -> Optional[str]:
        """
        Name of the nearest robot body above ``body``, or None when it hangs from the
        world rather than the robot.

        :param body: The object body to trace up the kinematic tree.
        :param parts: The robot's annotated bodies by name.
        :param root_name: Name of the robot's root body.
        """
        ancestor: Optional[KinematicStructureEntity] = (
            body.parent_kinematic_structure_entity
        )
        while ancestor is not None:
            name = RobotPartAnnotation.body_name(ancestor)
            if name in parts or name == root_name:
                return name
            ancestor = ancestor.parent_kinematic_structure_entity
        return None

    @staticmethod
    def _arm(part: RobotPartAnnotation) -> str:
        """
        Name of the arm a robot part belongs to: an end effector names the arm it is
        mounted on, an arm names itself.

        :param part: The arm or end effector an object hangs from.
        """
        if part.role is RobotPartRole.END_EFFECTOR:
            return part.attached_to
        return part.name
