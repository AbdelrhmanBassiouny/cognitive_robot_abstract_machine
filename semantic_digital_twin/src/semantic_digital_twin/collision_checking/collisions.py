from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set

import numpy as np
from line_profiler import profile

from semantic_digital_twin.collision_checking.collision_detector import (
    CollisionDetector,
    CollisionCheck,
)
from semantic_digital_twin.robots.abstract_robot import AbstractRobot
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class SortedCollisionResults:
    data: List[GiskardCollision] = field(default_factory=list)
    default_result: GiskardCollision = field(
        default_factory=lambda: GiskardCollision(contact_distance_input=100)
    )

    def _sort(self, x: GiskardCollision):
        return x.contact_distance

    def add(self, element: GiskardCollision):
        self.data.append(element)
        self.data = list(sorted(self.data, key=self._sort))

    def __getitem__(self, item: int) -> GiskardCollision:
        try:
            return self.data[item]
        except (KeyError, IndexError) as e:
            return self.default_result


@dataclass
class Collisions:
    collision_list_size: int
    self_collisions: Dict[Tuple[Body, Body], SortedCollisionResults] = field(
        default_factory=lambda: defaultdict(SortedCollisionResults)
    )
    external_collisions: Dict[Body, SortedCollisionResults] = field(
        default_factory=lambda: defaultdict(SortedCollisionResults)
    )
    external_collision_long_key: Dict[Tuple[Body, Body], GiskardCollision] = field(
        default_factory=lambda: defaultdict(
            lambda: SortedCollisionResults.default_result
        )
    )
    all_collisions: List[GiskardCollision] = field(default_factory=list)
    number_of_self_collisions: Dict[Tuple[Body, Body], int] = field(
        default_factory=lambda: defaultdict(int)
    )
    number_of_external_collisions: Dict[Body, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def get_robot_from_self_collision(
        self, collision: GiskardCollision, robots: List[AbstractRobot]
    ) -> Optional[AbstractRobot]:
        body_a, body_b = collision.body_a, collision.body_b
        for robot in robots:
            if body_a in robot.bodies and body_b in robot.bodies:
                return robot

    @classmethod
    def from_collision_list(
        cls,
        collision_list: List[GiskardCollision],
        collision_list_size: int,
        robots: List[AbstractRobot],
    ):
        collisions = cls(collision_list_size)
        for collision in collision_list:
            collisions.add(collision, robots=robots)
        return collisions

    @profile
    def add(self, collision: GiskardCollision, robots: List[AbstractRobot]):
        robot = self.get_robot_from_self_collision(collision, robots=robots)
        collision.is_external = robot is None
        if collision.is_external:
            collision = self.transform_external_collision(
                collision, world=robots[0]._world
            )
            key = collision.body_a
            self.external_collisions[key].add(collision)
            self.number_of_external_collisions[key] = min(
                self.collision_list_size, self.number_of_external_collisions[key] + 1
            )
            key_long = (collision.original_body_a, collision.original_body_b)
            if key_long not in self.external_collision_long_key:
                self.external_collision_long_key[key_long] = collision
            else:
                self.external_collision_long_key[key_long] = min(
                    collision,
                    self.external_collision_long_key[key_long],
                    key=lambda x: x.contact_distance,
                )
        else:
            collision = self.transform_self_collision(collision, robot)
            key = collision.body_a, collision.body_b
            self.self_collisions[key].add(collision)
            try:
                self.number_of_self_collisions[key] = min(
                    self.collision_list_size, self.number_of_self_collisions[key] + 1
                )
            except Exception as e:
                pass
        self.all_collisions.append(collision)

    @profile
    def transform_self_collision(
        self, collision: GiskardCollision, robot: AbstractRobot
    ) -> GiskardCollision:
        world = robot._world
        link_a = collision.original_body_a
        link_b = collision.original_body_b
        new_link_a, new_link_b = world.compute_chain_reduced_to_controlled_connections(
            link_a, link_b
        )
        if new_link_a.id > new_link_b.id:
            collision = collision.reverse()
            new_link_a, new_link_b = new_link_b, new_link_a
        collision.body_a = new_link_a
        collision.body_b = new_link_b

        new_b_T_r = world.compute_forward_kinematics_np(new_link_b, robot.root)
        root_T_map = world.compute_forward_kinematics_np(robot.root, world.root)
        new_b_T_map = new_b_T_r @ root_T_map
        collision.fixed_parent_of_b_V_n = new_b_T_map @ collision.map_V_n

        if collision.map_P_pa is not None:
            new_a_T_r = world.compute_forward_kinematics_np(new_link_a, robot.root)
            collision.fixed_parent_of_a_P_pa = (
                new_a_T_r @ root_T_map @ collision.map_P_pa
            )
            collision.fixed_parent_of_b_P_pb = new_b_T_map @ collision.map_P_pb
        else:
            new_a_T_a = world.compute_forward_kinematics_np(
                new_link_a, collision.original_body_a
            )
            collision.fixed_parent_of_a_P_pa = new_a_T_a @ collision.a_P_pa
            new_b_T_b = world.compute_forward_kinematics_np(
                new_link_b, collision.original_body_b
            )
            collision.fixed_parent_of_b_P_pb = new_b_T_b @ collision.b_P_pb
        return collision

    @profile
    def transform_external_collision(
        self, collision: GiskardCollision, world: World
    ) -> GiskardCollision:
        body_a = collision.original_body_a
        movable_joint = body_a.parent_connection

        def is_joint_movable(connection: ActiveConnection):
            return (
                isinstance(connection, ActiveConnection)
                and connection.has_hardware_interface
            )

        while movable_joint != world.root:
            if is_joint_movable(movable_joint):
                break
            movable_joint = movable_joint.parent.parent_connection
        else:
            raise Exception(
                f"{body_a.name} has no movable parent connection "
                f"and should't have collision checking enabled."
            )
        new_a = movable_joint.child
        collision.body_a = new_a
        if collision.map_P_pa is not None:
            new_a_T_map = world.compute_forward_kinematics_np(new_a, world.root)
            collision.fixed_parent_of_a_P_pa = new_a_T_map @ collision.map_P_pa
        else:
            new_a_T_a = world.compute_forward_kinematics_np(
                new_a, collision.original_body_a
            )
            collision.fixed_parent_of_a_P_pa = new_a_T_a @ collision.a_P_pa

        return collision

    @profile
    def get_external_collisions(self, link_name: Body) -> SortedCollisionResults:
        """
        Collisions are saved as a list for each movable robot joint, sorted by contact distance
        """
        if link_name in self.external_collisions:
            return self.external_collisions[link_name]
        return SortedCollisionResults()

    def get_external_collisions_long_key(
        self, link_a: Body, link_b: Body
    ) -> GiskardCollision:
        return self.external_collision_long_key[link_a, link_b]

    @profile
    def get_number_of_external_collisions(self, joint_name: Body) -> int:
        return self.number_of_external_collisions[joint_name]

    def get_self_collisions(self, link_a: Body, link_b: Body) -> SortedCollisionResults:
        """
        Make sure that link_a < link_b, the reverse collision is not saved.
        """
        if (link_a, link_b) in self.self_collisions:
            return self.self_collisions[link_a, link_b]
        return SortedCollisionResults()

    def get_number_of_self_collisions(self, link_a, link_b):
        return self.number_of_self_collisions[link_a, link_b]

    def __contains__(self, item):
        return item in self.self_collisions or item in self.external_collisions
