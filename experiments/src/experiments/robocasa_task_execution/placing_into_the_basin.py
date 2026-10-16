"""
Placing an object a robot holds into the basin of a sink, along a path a graph of convex
sets plans through the free space around the sink.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, radians

import numpy as np
from typing_extensions import TYPE_CHECKING, Self

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.attachment_nodes import ReAttachNode
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.motions.gripper import (
    MoveGripperMotion,
    MoveTCPWaypointsAlignedMotion,
)
from experiments.robocasa_task_execution.exceptions import (
    NoFreeSpotInTheBasin,
    NoPathIntoTheBasin,
    NoStandingPoseInFrontOfTheBasin,
)
from semantic_digital_twin.datastructures.alignment import AlignmentPair
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
    TorsoState,
)
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Pose,
    Vector3,
)
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.graph_of_convex_sets.boxes import (
    VolumetricGraphOfBoundingBoxes,
)
from semantic_digital_twin.world_description.shape_collection import (
    BoundingBoxCollection,
)
from semantic_digital_twin.world_description.world_entity import Body

if TYPE_CHECKING:
    from robocasa.models.fixtures.sink import Sink

# %% the basin of a sink


@dataclass
class SinkBasin:
    """
    The inside of a basin of a sink: the box RoboCasa's interior site of the basin
    spans, in world coordinates.
    """

    floor_corner: np.ndarray
    """
    The front corner of the basin floor the other corners are spanned from.
    """

    x_corner: np.ndarray
    """
    The corner of the basin floor across the width of the sink from
    :attr:`floor_corner`.
    """

    y_corner: np.ndarray
    """
    The corner of the basin floor towards the back of the sink from
    :attr:`floor_corner`.
    """

    rim_corner: np.ndarray
    """
    The corner at the height of the rim above :attr:`floor_corner`.
    """

    @classmethod
    def first_of(cls, sink: Sink) -> Self:
        """
        :param sink: RoboCasa's sink fixture.
        :return: The first basin of the sink.
        """
        floor_corner, x_corner, y_corner, rim_corner = next(
            iter(sink.get_int_sites(relative=False).values())
        )
        return cls(floor_corner, x_corner, y_corner, rim_corner)

    @property
    def floor_center(self) -> np.ndarray:
        """
        The centre of the basin floor.
        """
        return (self.x_corner + self.y_corner) / 2

    @property
    def floor_height(self) -> float:
        """
        The height of the basin floor.
        """
        return float(self.floor_corner[2])

    @property
    def rim_height(self) -> float:
        """
        The height of the rim of the basin.
        """
        return float(self.rim_corner[2])

    @property
    def front_direction(self) -> np.ndarray:
        """
        The horizontal unit vector pointing out of the front of the basin, towards where
        a robot stands to reach into it.
        """
        direction = (self.floor_corner - self.y_corner)[:2]
        return direction / np.linalg.norm(direction)


# %% placing into the basin


@dataclass
class PlacingIntoTheBasin:
    """
    A PR2 stands in front of a basin, lowers the object it holds into the basin along a
    path through the free space around the sink, lets go of the object just above the
    basin floor and backs out the same way.
    """

    basin: SinkBasin
    """
    The basin the object is placed into.
    """

    held_object: Body
    """
    The object the robot holds.
    """

    arm: Arm
    """
    The arm holding the object.
    """

    context: Context
    """
    The context the plan is performed in.
    """

    release_height: float = 0.03
    """
    How far above the basin floor the lowest point of the object is let go of.
    """

    approach_tilt: float = radians(60)
    """
    How far the gripper points down from the horizontal while it moves along the path.
    """

    obstacle_clearance: float = 0.08
    """
    How far the path keeps sideways off the kitchen.
    """

    obstacle_height_clearance: float = 0.08
    """
    How far the path keeps above and below the kitchen.
    """

    lowering_height: float = 0.1
    """
    How far above the release position the planned path ends, from where the object is
    lowered straight down.
    """

    entry_height: float = 0.15
    """
    How far above the rim the path planned into the basin starts at least.
    """

    search_margin: float = 0.45
    """
    How far around the basin the path is searched for.
    """

    waypoint_spacing: float = 0.02
    """
    The largest distance between consecutive waypoints of the path.
    """

    standing_step: float = 0.025
    """
    How far apart the distances in front of the basin are that the robot is tried at.
    """

    maximum_standing_distance: float = 1.2
    """
    How far in front of the basin the robot stands at most.
    """

    @property
    def robot(self) -> PR2:
        """
        The robot placing the object.
        """
        return self.context.robot

    @property
    def approach_direction(self) -> np.ndarray:
        """
        The direction the gripper points in while it moves along the path: into the
        basin, tilted down by :attr:`approach_tilt`.
        """
        horizontal = -self.basin.front_direction * np.cos(self.approach_tilt)
        return np.array([horizontal[0], horizontal[1], -np.sin(self.approach_tilt)])

    @property
    def facing_yaw(self) -> float:
        """
        The yaw the robot faces the basin with.
        """
        x, y = -self.basin.front_direction
        return float(np.arctan2(y, x))

    def plan(self) -> PlanNode:
        """
        :return: The plan placing the held object into the basin, from wherever the
            robot stands with its arms parked.
        :raises NoStandingPoseInFrontOfTheBasin: If the robot comes too close to the
            kitchen wherever it stands in front of the basin.
        :raises NoPathIntoTheBasin: If no path leads through the free space into the
            basin.
        """
        world = self.context.world
        standing_pose = self.standing_pose()
        path_into_the_basin = self.path_into_the_basin(standing_pose)
        gripper_pointing_into_the_basin = [
            AlignmentPair(
                tip_normal=Vector3.X(self.arm.end_effector.tool_frame),
                goal_normal=Vector3(
                    *self.approach_direction, reference_frame=world.root
                ),
            )
        ]
        return sequential(
            [
                NavigateAction(standing_pose),
                MoveTCPWaypointsAlignedMotion(
                    path_into_the_basin,
                    self.arm,
                    gripper_pointing_into_the_basin,
                    allow_gripper_collision=True,
                ),
                MoveGripperMotion(
                    GripperState.OPEN,
                    self.arm.end_effector,
                    allow_gripper_collision=True,
                ),
                ReAttachNode(body=self.held_object, new_parent=world.root),
                MoveTCPWaypointsAlignedMotion(
                    list(reversed(path_into_the_basin)),
                    self.arm,
                    gripper_pointing_into_the_basin,
                    allow_gripper_collision=True,
                ),
                ParkArmsAction(self.robot.all_arms),
            ],
            self.context,
        )

    def standing_pose(self) -> Pose:
        """
        :return: The pose closest to the basin at which the robot, with its torso up
            and its arms parked, faces the basin with the shoulder of :attr:`arm` in
            line with the basin's centre, and none of its bodies comes closer to the
            kitchen than collision avoidance keeps it.
        :raises NoStandingPoseInFrontOfTheBasin: If no such pose lies within
            :attr:`maximum_standing_distance` of the basin.
        """
        world = self.context.world
        world.collision_manager.update_collision_matrix()
        with world.reset_state_context():
            self._park(HomogeneousTransformationMatrix(reference_frame=world.root))
            shoulder = self.arm.connections[0].child
            shoulder_offset = world.compute_forward_kinematics_np(
                self.robot.root, shoulder
            )[1, 3]
            left = np.array([-np.sin(self.facing_yaw), np.cos(self.facing_yaw)])
            shoulder_line = self.basin.floor_center[:2] - left * shoulder_offset
            for distance in np.arange(
                0.0,
                self.maximum_standing_distance + self.standing_step / 2,
                self.standing_step,
            ):
                x, y = shoulder_line + self.basin.front_direction * distance
                world_T_base = HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=x, y=y, yaw=self.facing_yaw, reference_frame=world.root
                )
                self._park(world_T_base)
                if self._keeps_clear_of_the_kitchen():
                    return world_T_base.pose
        raise NoStandingPoseInFrontOfTheBasin(
            basin_center=Point3(*self.basin.floor_center, reference_frame=world.root),
            maximum_distance=self.maximum_standing_distance,
        )

    def path_into_the_basin(self, standing_pose: Pose) -> list[Point3]:
        """
        :param standing_pose: Where the robot stands in front of the basin.
        :return: The waypoints the tool frame of :attr:`arm` follows from where it is
            parked at ``standing_pose`` through the free space to above where it lets go
            of the object, and down to there, no farther apart than
            :attr:`waypoint_spacing`.
        :raises NoPathIntoTheBasin: If no path leads through the free space into the
            basin.
        """
        world = self.context.world
        tool_frame = self.arm.end_effector.tool_frame
        with world.reset_state_context():
            self._park(standing_pose.homogeneous_matrix)
            parked = world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]
        entry = parked.copy()
        entry[2] = max(parked[2], self.basin.rim_height + self.entry_height)
        release = self._release_position(
            world.compute_forward_kinematics_np(tool_frame, self.held_object)
        )
        graph = VolumetricGraphOfBoundingBoxes.free_space_from_world(
            world,
            self._search_space(parked),
            bloat_obstacles=self.obstacle_clearance,
            obstacle_height_clearance=self.obstacle_height_clearance,
        )
        entry_point = Point3(*entry, reference_frame=world.root)
        above_release_point = Point3(
            *(release + [0.0, 0.0, self.lowering_height]), reference_frame=world.root
        )
        path = graph.path_from_to(entry_point, above_release_point)
        if path is None:
            raise NoPathIntoTheBasin(entry=entry_point, release=above_release_point)
        corners = [parked, *(point.to_np()[:3] for point in path), release]
        return [
            Point3(*position, reference_frame=world.root)
            for position in self._densified(corners)
        ]

    def _park(self, world_T_base: HomogeneousTransformationMatrix) -> None:
        """
        Put the robot at ``world_T_base`` with its torso up and its arms parked.

        :param world_T_base: Where the base of the robot stands.
        """
        world = self.context.world
        self.robot.torso.get_joint_state_by_type(TorsoState.HIGH).apply_to(world)
        for arm in self.robot.all_arms:
            arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
        self.robot.root.parent_connection.origin = world_T_base

    def _keeps_clear_of_the_kitchen(self) -> bool:
        """
        :return: Whether every body of the robot keeps at least the buffer zone
            distance collision avoidance keeps it at from everything but the robot.
        """
        collision_manager = self.context.world.collision_manager
        robot_bodies = set(self.robot.bodies_with_collision)
        return all(
            contact.distance
            >= collision_manager.get_buffer_zone_distance(
                contact.body_a, contact.body_b
            )
            for contact in collision_manager.compute_collisions().contacts
            if (contact.body_a in robot_bodies) != (contact.body_b in robot_bodies)
        )

    def _release_position(self, tool_T_object: np.ndarray) -> np.ndarray:
        """
        :param tool_T_object: Where the held object sits relative to the tool frame.
        :return: Where the tool frame lets go of the object: pointing in
            :attr:`approach_direction`, with the lowest point of the object
            :attr:`release_height` above the basin floor and the object as close to the
            centre of the basin as it fits without touching anything in the kitchen.
        :raises NoFreeSpotInTheBasin: If the object fits nowhere on the basin floor.
        """
        world_R_tool = HomogeneousTransformationMatrix.from_xyz_rpy(
            pitch=self.approach_tilt, yaw=self.facing_yaw
        ).to_np()[:3, :3]
        object_box = self.held_object.collision.as_bounding_box_collection_in_frame(
            self.held_object
        ).bounding_box()
        corners_in_object = np.array(
            [
                [x, y, z, 1.0]
                for x in (object_box.min_x, object_box.max_x)
                for y in (object_box.min_y, object_box.max_y)
                for z in (object_box.min_z, object_box.max_z)
            ]
        )
        corners_from_tool = (world_R_tool @ (tool_T_object @ corners_in_object.T)[:3]).T
        tool_height = (
            self.basin.floor_height
            + self.release_height
            - corners_from_tool[:, 2].min()
        )
        obstacles = self._obstacle_boxes()
        for object_center in self._spots_on_the_basin_floor():
            tool = np.array(
                [
                    *(object_center - corners_from_tool.mean(axis=0)[:2]),
                    tool_height,
                ]
            )
            corners = corners_from_tool + tool
            lower, upper = corners.min(axis=0), corners.max(axis=0)
            if not any(
                np.all(lower < obstacle_upper) and np.all(obstacle_lower < upper)
                for obstacle_lower, obstacle_upper in obstacles
            ):
                return tool
        raise NoFreeSpotInTheBasin(
            held_object=self.held_object,
            basin_center=Point3(
                *self.basin.floor_center, reference_frame=self.context.world.root
            ),
        )

    def _spots_on_the_basin_floor(self) -> list[np.ndarray]:
        """
        :return: Horizontal positions on the basin floor, :attr:`waypoint_spacing` apart
            along both sides of the basin, closest to the centre of the basin first.
        """
        floor_corner = self.basin.floor_corner[:2]
        across = self.basin.x_corner[:2] - floor_corner
        towards_the_back = self.basin.y_corner[:2] - floor_corner
        spots = [
            floor_corner + across * u + towards_the_back * v
            for u in np.linspace(
                0.0, 1.0, ceil(np.linalg.norm(across) / self.waypoint_spacing) + 1
            )
            for v in np.linspace(
                0.0,
                1.0,
                ceil(np.linalg.norm(towards_the_back) / self.waypoint_spacing) + 1,
            )
        ]
        center = self.basin.floor_center[:2]
        return sorted(spots, key=lambda spot: float(np.linalg.norm(spot - center)))

    def _obstacle_boxes(self) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        :return: The lower and upper corners of the world aligned bounding boxes of
            every collision shape in the kitchen, leaving out the robot and the held
            object.
        """
        world = self.context.world
        robot_bodies = set(world.robot_bodies_with_collision)
        return [
            (
                np.array([box.min_x, box.min_y, box.min_z]),
                np.array([box.max_x, box.max_y, box.max_z]),
            )
            for body in world.bodies_with_collision
            if body not in robot_bodies and body is not self.held_object
            for box in body.collision.as_bounding_box_collection_in_frame(world.root)
        ]

    def _search_space(
        self, parked: np.ndarray
    ) -> BoundingBoxCollection[VolumetricBoundingBox, Point3]:
        """
        :param parked: Where the tool frame is parked at the standing pose.
        :return: The box around the basin and the parked tool frame the path is
            searched in.
        """
        root = self.context.world.root
        floor_center = self.basin.floor_center
        lower = np.minimum(
            [
                floor_center[0] - self.search_margin,
                floor_center[1] - self.search_margin,
                self.basin.floor_height - self.obstacle_height_clearance,
            ],
            parked - self.waypoint_spacing,
        )
        upper = np.maximum(
            [
                floor_center[0] + self.search_margin,
                floor_center[1] + self.search_margin,
                self.basin.rim_height + self.entry_height + self.search_margin,
            ],
            parked + self.waypoint_spacing,
        )
        return BoundingBoxCollection(
            [
                VolumetricBoundingBox(
                    *lower,
                    *upper,
                    origin=HomogeneousTransformationMatrix(reference_frame=root),
                )
            ],
            reference_frame=root,
        )

    def _densified(self, corners: list[np.ndarray]) -> list[np.ndarray]:
        """
        :param corners: The corners of a polyline.
        :return: Points along the polyline, from its first corner to its last, no
            farther apart than :attr:`waypoint_spacing`.
        """
        points = [corners[0]]
        for start, end in zip(corners, corners[1:]):
            steps = ceil(np.linalg.norm(end - start) / self.waypoint_spacing)
            points.extend(
                start + (end - start) * step / steps for step in range(1, steps + 1)
            )
        return points
