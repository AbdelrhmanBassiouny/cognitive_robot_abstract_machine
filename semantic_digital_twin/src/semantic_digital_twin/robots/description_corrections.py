"""
Corrections to a robot's kinematic structure, for what its description gets wrong or
cannot express, made once the description is parsed and before the robot is set up on
it, see
:attr:`~semantic_digital_twin.robots.robot_parts.AbstractRobot.description_corrections`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from krrood.patterns.caching import clear_memoization_cache
from semantic_digital_twin.specifications.connections import ConnectionSpecification
from semantic_digital_twin.specifications.kinematic_structure_entities import (
    KinematicStructureEntitySpecification,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)


@dataclass
class DescriptionCorrection(ABC):
    """
    A change to a robot's kinematic structure.

    It is made inside the world modification block that sets the robot up, so copies of
    the world replay it, and it finds what it changes by name within the robot's branch,
    so several robots of one kind in a world are each corrected on their own.
    """

    @abstractmethod
    def apply(self, world: World, branch_root: KinematicStructureEntity) -> None:
        """
        Make the change.

        :param world: The world holding the robot.
        :param branch_root: The root of the branch the robot is in.
        """


@dataclass
class ReplaceConnection(DescriptionCorrection):
    """
    Replaces one connection with one built from :attr:`replacement`, keeping both bodies,
    and the child with everything below it where it is.

    For a joint that does not move the way the description says, such as one that is
    stuck on the real robot and becomes a fixed connection.
    """

    connection_name: str
    """
    The name of the replaced connection, without its prefix.
    """

    replacement: ConnectionSpecification
    """
    The connection put in its place, named like the replaced one unless it is given a
    name of its own.
    """

    def apply(self, world: World, branch_root: KinematicStructureEntity) -> None:
        connection = world.get_connection_in_branch_by_name(
            branch_root, self.connection_name
        )
        replacement = (
            self.replacement
            if self.replacement.name is not None
            else replace(self.replacement, name=self.connection_name)
        )
        replacement.reconnect(world, connection.child)


@dataclass
class SectionAttachment:
    """
    A body below a replaced section that stays, and the body of the replacement it hangs
    from afterwards.
    """

    body_name: str
    """
    The name of the body that stays, together with everything below it.
    """

    new_parent_name: str
    """
    The name of the body of the replacement it hangs from.
    """


@dataclass
class ReplaceSection(DescriptionCorrection):
    """
    Replaces a section of the kinematic tree with :attr:`replacement`, for structure the
    description cannot express.

    The section is the branch of :attr:`section_root`, down to but without the bodies of
    :attr:`attachments`. Its replacement hangs where the section root did, from the same
    parent, and each attached body hangs from its new parent afterwards, together with
    everything below it and where it was.
    """

    section_root_name: str
    """
    The name of the first body of the section, removed with the connection it hangs
    from.
    """

    replacement: KinematicStructureEntitySpecification
    """
    The bodies and connections put in place of the section, its root where the section
    root was.
    """

    attachments: list[SectionAttachment] = field(default_factory=list)
    """
    The bodies below the section that stay.
    """

    def apply(self, world: World, branch_root: KinematicStructureEntity) -> None:
        section_root = world.get_body_in_branch_by_name(
            branch_root, self.section_root_name
        )
        parent = section_root.parent_connection.parent
        parent_T_section_root = world.compute_forward_kinematics(
            parent, section_root, enable_unsafe_inside_world_block=True
        )
        staying = [
            (
                world.get_body_in_branch_by_name(section_root, attachment.body_name),
                attachment.new_parent_name,
            )
            for attachment in self.attachments
        ]
        # The world forgets the branches it looked up only once its outermost
        # modification block ends, so every lookup after a change to the tree, here and
        # in whatever sets the robot up after this, would see the tree as it was.
        with world.modify_world():
            # Out of the section first, so removing it leaves them in place.
            for body, _ in staying:
                world.move_branch(body, parent, enable_unsafe_inside_world_block=True)
            clear_memoization_cache(world)
            world.remove_branch_from_world(section_root)
            replacement_root = self.replacement.spawn(
                world, parent=parent, parent_T_self=parent_T_section_root
            )
            clear_memoization_cache(world)
            for body, new_parent_name in staying:
                world.move_branch(
                    body,
                    world.get_body_in_branch_by_name(replacement_root, new_parent_name),
                    enable_unsafe_inside_world_block=True,
                )
            clear_memoization_cache(world)
