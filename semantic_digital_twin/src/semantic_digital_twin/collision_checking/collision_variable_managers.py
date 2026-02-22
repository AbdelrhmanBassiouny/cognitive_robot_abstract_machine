from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from giskardpy.utils.decorators import memoize
from krrood.symbolic_math.float_variable_data import (
    FloatVariableData,
)
from krrood.symbolic_math.symbolic_math import FloatVariable
from .collision_detector import CollisionCheckingResult, ClosestPoints
from .collision_groups import CollisionGroupConsumer, CollisionGroup
from ..spatial_types import Vector3, Point3
from ..world_description.world_entity import Body


@dataclass
class ExternalCollisionVariableManager(CollisionGroupConsumer):
    """
    Transforms collision results for registered groups into local frames convenient for external (registered vs non-registered groups) collision avoidance,
    saves the data in a FloatVariableManager,
    and provides spatial objects that refer to them.

    For each registered group, the closest collisions are stored, depending on their maximum number of avoided collisions.
    """

    float_variable_data: FloatVariableData = field(default_factory=FloatVariableData)
    """
    Reference to the FloatVariableManager that stores the collision data.
    """

    registered_groups: dict[CollisionGroup, int] = field(
        default_factory=dict, init=False
    )
    """
    Maps bodies to the index of point_on_body_a in the collision buffer.
    """

    _block_size: int = field(default=9, init=False)
    """
    The block size in the `float_variable_manager` of all float variables belonging to a collision.
    block layout:
        9 per collision
        point_on_body_a,  (3)
        contact_normal,  (3)
        contact_distance, (1)
        buffer_distance,  (1)
        violated_distance (1)
    """
    _point_on_a_offset: int = field(init=False, default=0)
    """
    Offset of the point_on_body_a variable in the block.
    """
    _contact_normal_offset: int = field(init=False, default=3)
    """
    Offset of the contact_normal variable in the block.
    """
    _contact_distance_offset: int = field(init=False, default=6)
    """
    Offset of the contact_distance variable in the block.
    """
    _buffer_distance_offset: int = field(init=False, default=7)
    """
    Offset of the buffer_distance variable in the block.
    """
    _violated_distance_offset: int = field(init=False, default=8)
    """
    Offset of the violated_distance variable in the block.
    """

    _collision_data_start_index: int = field(init=False, default=None)
    """
    The index of the first collision data block in the `float_variable_manager`.
    """
    _single_reset_block: np.ndarray = field(init=False)
    """
    A block that is used to reset the collision data.
    """
    _reset_data: np.ndarray = field(init=False, default_factory=lambda: np.array([]))
    """
    The data that is used to reset the whole collision data.
    """

    def __post_init__(self):
        self._single_reset_block = np.zeros(self._block_size)
        self._single_reset_block[self._contact_distance_offset] = 100

    def __hash__(self):
        return hash(id(self))

    def on_collision_matrix_update(self):
        pass

    def on_compute_collisions(self, collision: CollisionCheckingResult):
        """
        Takes collisions, checks if they are external, and inserts them
        into the buffer at the right place.
        """
        self.reset_collision_data()
        closest_contacts: dict[CollisionGroup, list[ClosestPoints]] = defaultdict(list)
        for collision in collision.contacts:
            group_a = self.get_collision_group(collision.body_a)
            group_b = self.get_collision_group(collision.body_b)
            if (group_a in self.registered_groups) == (
                group_b in self.registered_groups
            ):
                continue
            if group_a not in self.registered_groups:
                # swap group_a and group_b, such that group_a is the registered group
                collision = collision.reverse()
                group_a, group_b = group_b, group_a
            closest_contacts[group_a].append(collision)

        for group_a, collisions in closest_contacts.items():
            collisions = sorted(collisions, key=lambda c: c.distance)
            for i in range(
                min(
                    len(collisions),
                    group_a.get_max_avoided_bodies(self.collision_manager),
                )
            ):
                collision = collisions[i]
                group_a_T_root = group_a.root.global_pose.inverse().to_np()
                group_a_P_pa = group_a_T_root @ collision.root_P_point_on_body_a
                self.insert_data_block(
                    group=group_a,
                    idx=i,
                    group_a_P_point_on_a=group_a_P_pa,
                    root_V_contact_normal=collision.root_V_contact_normal_from_b_to_a,
                    contact_distance=collision.distance,
                    buffer_distance=self.collision_manager.get_buffer_zone_distance(
                        collision.body_a, collision.body_b
                    ),
                    violated_distance=self.collision_manager.get_violated_distance(
                        collision.body_a, collision.body_b
                    ),
                )

    def insert_data_block(
        self,
        group: CollisionGroup,
        idx: int,
        group_a_P_point_on_a: np.ndarray,
        root_V_contact_normal: np.ndarray,
        contact_distance: float,
        buffer_distance: float,
        violated_distance: float,
    ):
        """
        Inserts a data block into the collision buffer.
        :param group: Registered collision group of the external collision.
        :param idx: Index of the collision in the collision buffer.
        :param group_a_P_point_on_a: Point on body A in the contact frame.
        :param root_V_contact_normal: Contact normal in the root frame.
        :param contact_distance: Distance between the bodies at the contact point.
        :param buffer_distance: Buffer distance for collision detection.
        :param violated_distance: Violated distance for collision detection.
        """
        start_idx = self.registered_groups[group] + idx * self._block_size
        self.float_variable_data.data[
            start_idx : start_idx + self._contact_normal_offset
        ] = group_a_P_point_on_a[:3]
        self.float_variable_data.data[
            start_idx
            + self._contact_normal_offset : start_idx
            + self._contact_distance_offset
        ] = root_V_contact_normal[:3]
        self.float_variable_data.data[start_idx + self._contact_distance_offset] = (
            contact_distance
        )
        self.float_variable_data.data[start_idx + self._buffer_distance_offset] = (
            buffer_distance
        )
        self.float_variable_data.data[start_idx + self._violated_distance_offset] = (
            violated_distance
        )

    def reset_collision_data(self):
        start_index = self._collision_data_start_index
        end_index = start_index + self._reset_data.size
        self.float_variable_data.data[start_index:end_index] = self._reset_data

    def register_group_of_body(self, body: Body):
        """
        Register the collision group associated with a body.
        """
        group = self.get_collision_group(body)
        if group in self.registered_groups:
            return
        self.registered_groups[group] = len(self.float_variable_data.data)
        if self._collision_data_start_index is None:
            self._collision_data_start_index = self.registered_groups[group]
        for index in range(group.get_max_avoided_bodies(self.collision_manager)):
            self.get_group_a_P_point_on_a_symbol(group, index)
            self.get_root_V_contact_normal_symbol(group, index)
            self.get_contact_distance_symbol(group, index)
            self.get_buffer_distance_symbol(group, index)
            self.get_violated_distance_symbol(group, index)
            self._reset_data = np.append(self._reset_data, self._single_reset_block)

    @lru_cache
    def get_group_a_P_point_on_a_symbol(
        self, group: CollisionGroup, idx: int
    ) -> Point3:
        point = Point3.create_with_variables(
            name=f"group_a_P_point_on_a({group.root.name}, {idx})",
        )
        self.float_variable_data.add_variables_of_expression(point)
        return point

    @lru_cache
    def get_root_V_contact_normal_symbol(
        self, group: CollisionGroup, idx: int
    ) -> Vector3:
        vector = Vector3.create_with_variables(
            f"root_V_contact_normal({group.root.name}, {idx})",
        )
        self.float_variable_data.add_variables_of_expression(vector)
        return vector

    @lru_cache
    def get_contact_distance_symbol(
        self, group: CollisionGroup, idx: int
    ) -> FloatVariable:
        variable = FloatVariable(f"contact_distance({group.root.name}, {idx})")
        self.float_variable_data.add_variable(variable)
        return variable

    @lru_cache
    def get_buffer_distance_symbol(
        self, group: CollisionGroup, idx: int
    ) -> FloatVariable:
        variable = FloatVariable(f"buffer_distance({group.root.name}, {idx})")
        self.float_variable_data.add_variable(variable)
        return variable

    @lru_cache
    def get_violated_distance_symbol(
        self, group: CollisionGroup, idx: int
    ) -> FloatVariable:
        variable = FloatVariable(f"violated_distance({group.root.name}, {idx})")
        self.float_variable_data.add_variable(variable)
        return variable


@dataclass
class SelfCollisionVariableManager(CollisionGroupConsumer):
    """
    Transforms collision results for registered groups into local frames convenient for self (registered vs registered groups) collision avoidance,
    saves the data in a FloatVariableManager,
    and provides spatial objects that refer to them.

    For each combination of registered group, the closest collision is stored.
    """

    float_variable_data: FloatVariableData = field(default_factory=FloatVariableData)
    """
    The FloatVariableData that stores the collision data.
    """

    registered_group_combinations: dict[tuple[CollisionGroup, CollisionGroup], int] = (
        field(default_factory=dict, init=False)
    )
    """
    Maps body combinations to the index of point_on_body_a in the collision buffer.
    """

    block_size: int = field(default=12, init=False)
    """
    The block size in the `float_variable_manager` of all float variables belonging to a collision.
    block layout:
        12 per collision
        point_on_body_a,  (3)
        point_on_body_b,  (3)
        contact_normal,  (3)
        contact_distance, (1)
        buffer_distance,  (1)
        violated_distance (1)
    """
    _point_on_a_offset: int = field(init=False, default=0)
    """
    Offset of the point_on_body_a variable in the block.
    """
    _point_on_b_offset: int = field(init=False, default=3)
    """
    Offset of the point_on_body_b variable in the block.
    """
    _contact_normal_offset: int = field(init=False, default=6)
    """
    Offset of the contact_normal variable in the block.
    """
    _contact_distance_offset: int = field(init=False, default=9)
    """
    Offset of the contact_distance variable in the block.
    """
    _buffer_distance_offset: int = field(init=False, default=10)
    """
    Offset of the buffer_distance variable in the block.
    """
    _violated_distance_offset: int = field(init=False, default=11)
    """
    Offset of the violated_distance variable in the block.
    """

    _collision_data_start_index: int = field(init=False, default=None)
    """
    The start index of the collision data in the `float_variable_manager`.
    """
    _single_reset_block: np.ndarray = field(init=False)
    """
    A block of reset data that is inserted at the beginning of each collision data block.
    """
    _reset_data: np.ndarray = field(init=False, default_factory=lambda: np.array([]))
    """
    The reset data that is inserted at the beginning of each collision data block.
    """

    def __post_init__(self):
        self._single_reset_block = np.zeros(self.block_size)
        self._single_reset_block[self._contact_distance_offset] = 100

    def __hash__(self):
        return hash(id(self))

    def on_collision_matrix_update(self):
        pass

    def on_compute_collisions(self, collision_result: CollisionCheckingResult):
        """
        Takes collisions, checks if they are external, and inserts them
        into the buffer at the right place.
        """
        self.reset_collision_data()
        closest_contacts: dict[
            tuple[CollisionGroup, CollisionGroup], list[ClosestPoints]
        ] = defaultdict(list)
        for collision in collision_result.contacts:
            key = (
                self.get_collision_group(collision.body_b),
                self.get_collision_group(collision.body_a),
            )
            # 1. check if collision is external
            if key in self.registered_group_combinations:
                collision = collision.reverse()
            else:
                key = tuple(reversed(key))
            if key not in self.registered_group_combinations:
                continue
            closest_contacts[key].append(collision)

        for (group_a, group_b), collisions in closest_contacts.items():
            closest_contact = sorted(collisions, key=lambda c: c.distance)[0]
            group_a_T_root = group_a.root.global_pose.inverse().to_np()
            group_a_P_pa = group_a_T_root @ closest_contact.root_P_point_on_body_a

            group_b_T_root = group_b.root.global_pose.inverse().to_np()
            group_b_P_pb = group_b_T_root @ closest_contact.root_P_point_on_body_b

            group_b_V_contact_normal = (
                group_b_T_root @ closest_contact.root_V_contact_normal_from_b_to_a
            )

            self.insert_data_block(
                group_a=group_a,
                group_b=group_b,
                group_a_P_point_on_a=group_a_P_pa,
                group_b_P_point_on_b=group_b_P_pb,
                group_b_V_contact_normal=group_b_V_contact_normal,
                contact_distance=closest_contact.distance,
                buffer_distance=self.collision_manager.get_buffer_zone_distance(
                    closest_contact.body_a, closest_contact.body_b
                ),
                violated_distance=self.collision_manager.get_violated_distance(
                    closest_contact.body_a, closest_contact.body_b
                ),
            )

    def insert_data_block(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
        group_a_P_point_on_a: np.ndarray,
        group_b_P_point_on_b: np.ndarray,
        group_b_V_contact_normal: np.ndarray,
        contact_distance: float,
        buffer_distance: float,
        violated_distance: float,
    ):
        """
        Inserts a data block into the collision buffer.
        :param group_a: Registered collision group of body A.
        :param group_b: Registered collision group of body B.
        :param group_a_P_point_on_a: Point on body A in the contact frame.
        :param group_b_P_point_on_b: Point on body B in the contact frame.
        :param group_b_V_contact_normal: Contact normal in the root frame.
        :param contact_distance: Distance between the bodies at the contact point.
        :param buffer_distance: Buffer distance for collision detection.
        :param violated_distance: Violated distance for collision detection.
        """
        block_start_idx = self.registered_group_combinations[group_a, group_b]

        start_idx = block_start_idx + self._point_on_a_offset
        end_idx = block_start_idx + self._point_on_b_offset
        self.float_variable_data.data[start_idx:end_idx] = group_a_P_point_on_a[:3]

        start_idx = end_idx
        end_idx = block_start_idx + self._contact_normal_offset
        self.float_variable_data.data[start_idx:end_idx] = group_b_P_point_on_b[:3]

        start_idx = end_idx
        end_idx = block_start_idx + self._contact_distance_offset
        self.float_variable_data.data[start_idx:end_idx] = group_b_V_contact_normal[:3]

        self.float_variable_data.data[
            block_start_idx + self._contact_distance_offset
        ] = contact_distance
        self.float_variable_data.data[
            block_start_idx + self._buffer_distance_offset
        ] = buffer_distance
        self.float_variable_data.data[
            block_start_idx + self._violated_distance_offset
        ] = violated_distance

    def reset_collision_data(self):
        start_index = self._collision_data_start_index
        end_index = start_index + self._reset_data.size
        self.float_variable_data.data[start_index:end_index] = self._reset_data

    def body_pair_to_group_pair(
        self, body_a: Body, body_b: Body
    ) -> tuple[CollisionGroup, CollisionGroup]:
        group_a = self.get_collision_group(body_a)
        group_b = self.get_collision_group(body_b)
        if group_a.root.id < group_b.root.id:
            return group_a, group_b
        else:
            return group_b, group_a

    def register_groups_of_body_combination(self, body_a: Body, body_b: Body):
        """
        Register a combination of bodies for self collision avoidance.
        """
        key = self.body_pair_to_group_pair(body_a, body_b)
        if key in self.registered_group_combinations:
            return

        self.registered_group_combinations[key] = len(self.float_variable_data.data)
        if self._collision_data_start_index is None:
            self._collision_data_start_index = self.registered_group_combinations[key]
        self.get_group_a_P_point_on_a_symbol(*key)
        self.get_group_b_P_point_on_b_symbol(*key)
        self.get_group_b_V_contact_normal_symbol(*key)
        self.get_contact_distance_symbol(*key)
        self.get_buffer_distance_symbol(*key)
        self.get_violated_distance_symbol(*key)
        self._reset_data = np.append(self._reset_data, self._single_reset_block)

    @lru_cache
    def get_group_a_P_point_on_a_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> Point3:
        point = Point3.create_with_variables(
            name=f"group_a_P_point_on_a({group_a}, {group_b})",
        )
        self.float_variable_data.add_variables_of_expression(point)
        return point

    @lru_cache
    def get_group_b_P_point_on_b_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> Point3:
        point = Point3.create_with_variables(
            name=f"group_b_P_point_on_b({group_a}, {group_b})",
        )
        self.float_variable_data.add_variables_of_expression(point)
        return point

    @lru_cache
    def get_group_b_V_contact_normal_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> Vector3:
        vector = Vector3.create_with_variables(
            f"group_b_V_contact_normal({group_a}, {group_b})",
        )
        self.float_variable_data.add_variables_of_expression(vector)
        return vector

    @lru_cache
    def get_contact_distance_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> FloatVariable:
        variable = FloatVariable(f"contact_distance({group_a}, {group_b})")
        self.float_variable_data.add_variable(variable)
        return variable

    @lru_cache
    def get_buffer_distance_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> FloatVariable:
        variable = FloatVariable(f"buffer_distance({group_a}, {group_b})")
        self.float_variable_data.add_variable(variable)
        return variable

    @lru_cache
    def get_violated_distance_symbol(
        self,
        group_a: CollisionGroup,
        group_b: CollisionGroup,
    ) -> FloatVariable:
        variable = FloatVariable(f"violated_distance({group_a}, {group_b})")
        self.float_variable_data.add_variable(variable)
        return variable
