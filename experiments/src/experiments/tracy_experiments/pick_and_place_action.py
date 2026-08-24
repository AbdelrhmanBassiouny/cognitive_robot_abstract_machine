"""
:class:`PickUpActionMujoco`/:class:`PlaceActionMujoco`: Mujoco-driven siblings of
:class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`/
:class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`, matching their own
field interface (``object_designator``, ``arm``, ``grasp_description``/
``target_location``) so a caller can compose them into a
:func:`~coraplex.plans.factories.sequential` plan the same way, but with each own leaf
motion running plain Python (see :meth:`PickUpActionMujoco._run`/
:meth:`PlaceActionMujoco._run`, wrapped via :func:`~coraplex.plans.factories.code`)
rather than a Giskard motion mapping.

The real ``PickUpAction``/``PlaceAction`` build their own plan entirely from
``MoveToolCenterPointMotion``/``MoveGripperMotion`` designators, each of which ticks
Giskard's own closed loop live against the world model
(:class:`~coraplex.robot_plans.motions.gripper.MoveToolCenterPointMotion` →
:class:`~coraplex.plans.plan_node.MotionNode` →
:class:`~coraplex.plans.executables.GiskardExecutable`). That races
:class:`~semantic_digital_twin.adapters.multi_sim.MujocoSynchronizer`'s own
physics-thread state sync for a physically simulated robot -- see
:mod:`~experiments.tracy_experiments.equipment`'s own module docstring. These two
actions instead reuse :mod:`~experiments.tracy_experiments.trajectory_planning`'s own
plan-then-execute functions directly: each reach is planned by Giskard against an
isolated scratch copy of the world, then the resulting trajectory is played back by
commanding the real MuJoCo actuators.

Unlike ``PickUpAction``/``PlaceAction``, neither action here kinematically attaches or
detaches the object (no ``AttachNode``/``DetachNode``): the object is held only by real
MuJoCo contact friction between the fingers throughout -- a kinematically snapped object
is not left behind by a friction hold's own continuous motion the way an instantaneous
kinematic detach would otherwise risk. Both actions are generic over any body and arm,
used the same way for a Montessori shape being sorted into a hole and a cube being
stacked onto another.

Both actions currently support only a fixed top-down grasp (``grasp_description`` is
accepted for interface parity with ``PickUpAction``, but its own approach direction and
vertical alignment are not yet read); see :func:`_finger_midpoint_offset`'s own
docstring for the geometry this fixed orientation assumes.
"""

from __future__ import annotations

import math

import numpy
from typing_extensions import Dict

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import code
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from dataclasses import dataclass
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from experiments.tracy_experiments.trajectory_planning import (
    close_gripper_around,
    follow_joint_trajectory,
    plan_cartesian_trajectory,
    set_gripper,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Actuator, Body

HOVER_CLEARANCE = 0.3
"""
Height, in metres, above a body's own top face the TCP moves to before descending onto
it -- clears obstacles during the horizontal part of each approach.

``0.3`` clears the Montessori board plus its three drawers with a wide margin --
confirmed directly, a smaller hover height left Giskard's own collision-avoidance
solver too little vertical room to route the arm above the board at all.
"""

PLACE_HOVER_CLEARANCE = 0.05
"""
Height, in metres, above ``target_location`` a body is released at, rather than
descending onto it exactly.
"""

FINGER_PAD_TABLE_CLEARANCE = 0.002
"""
Height, in metres, :func:`_grasp_target_z` keeps the gripper's own fingertip pads above
the surface a shape rests on.

Not zero: MuJoCo's own contact solver tolerates a little penetration before its
restoring force fully engages, so a pad aimed exactly at the resting surface's own
height would still dip into it slightly.
"""


def _bounding_box_center_world(world: World, body: Body) -> numpy.ndarray:
    """
    A body's own collision bounding box centre, in the world root frame.

    :param world: The world ``body`` belongs to.
    :param body: The body to measure.
    """
    bounding_box = body.collision[0].local_frame_bounding_box
    center_local = numpy.array(
        [
            (bounding_box.min_x + bounding_box.max_x) / 2,
            (bounding_box.min_y + bounding_box.max_y) / 2,
            (bounding_box.min_z + bounding_box.max_z) / 2,
        ]
    )
    root_transform_body = world.compute_forward_kinematics_np(world.root, body)
    return root_transform_body[:3, :3] @ center_local + root_transform_body[:3, 3]


def _fingertip_pad_half_height(world: World, robot: Tracy, arm_side: Arms) -> float:
    """
    Half the vertical extent of one of an arm's own gripper's fingertip pads.

    Both pads on one gripper share this height by construction, so either one stands in
    for the pair.

    :param world: The world ``robot`` belongs to.
    :param robot: The robot whose gripper pad is measured.
    :param arm_side: Which arm's gripper to measure.
    """
    prefix = "right_" if arm_side == Arms.RIGHT else "left_"
    bounding_box = (
        world.get_body_by_name(f"{prefix}robotiq_85_left_finger_tip_link")
        .collision[0]
        .local_frame_bounding_box
    )
    return (bounding_box.max_z - bounding_box.min_z) / 2


def _grasp_target_z(
    world: World,
    robot: Tracy,
    arm_side: Arms,
    body: Body,
    table_clearance: float = FINGER_PAD_TABLE_CLEARANCE,
) -> float:
    """
    Height, in the world root frame, to place the gripper's own finger midpoint at so
    its pads clear the surface ``body`` rests on while still closing around ``body``.

    A Robotiq-85 fingertip pad's own vertical extent is taller than any of this demo's
    thin Montessori shapes, so centering the pad on a shape's own vertical centre -- the
    previous approach -- puts the pad's own lower edge below the table: confirmed
    directly, contact-checking during a close showed the pad touching the table on every
    tick, never the target shape. Anchoring the pad's own lower edge just above the
    shape's resting surface instead keeps the pad clear of the table while its own,
    taller extent still reaches up past the shape's own top, so it still closes around
    the shape's sides.

    :param world: The world ``body`` belongs to.
    :param robot: The robot whose gripper reaches for ``body``.
    :param arm_side: Which arm's gripper reaches for ``body``.
    :param body: The body to be grasped.
    :param table_clearance: See :data:`FINGER_PAD_TABLE_CLEARANCE`.
    """
    bounding_box = body.collision[0].local_frame_bounding_box
    shape_bottom_z = (
        _bounding_box_center_world(world, body)[2]
        - (bounding_box.max_z - bounding_box.min_z) / 2
    )
    pad_half_height = _fingertip_pad_half_height(world, robot, arm_side)
    return shape_bottom_z + pad_half_height + table_clearance


def _finger_midpoint_offset(robot: Tracy, arm_side: Arms) -> numpy.ndarray:
    """
    Fixed offset from an arm's own tool frame to its gripper's own finger-tip midpoint,
    expressed in the tool frame's own local axes.

    :func:`~experiments.tracy_experiments.trajectory_planning.plan_cartesian_trajectory`
    places the tool frame itself at a Cartesian goal, not where the fingers actually
    meet -- confirmed directly, targeting a shape's own centre this way put the tool
    frame there but left the fingers several centimetres away, closing on open air.
    Each fingertip's own collision bounding box centre (not its link origin) stands in
    for where that finger actually is, since the link origin sits at one edge of the
    fingertip mesh, not its geometric centre.

    :param robot: The robot whose gripper this offset is measured on.
    :param arm_side: Which arm's gripper to measure.
    """
    arm = robot.right_arm if arm_side == Arms.RIGHT else robot.left_arm
    prefix = "right_" if arm_side == Arms.RIGHT else "left_"
    tool_frame = arm.end_effector.tool_frame
    root_transform_tool = robot._world.compute_forward_kinematics_np(
        robot._world.root, tool_frame
    )
    left_center = _bounding_box_center_world(
        robot._world,
        robot._world.get_body_by_name(f"{prefix}robotiq_85_left_finger_tip_link"),
    )
    right_center = _bounding_box_center_world(
        robot._world,
        robot._world.get_body_by_name(f"{prefix}robotiq_85_right_finger_tip_link"),
    )
    finger_midpoint = (left_center + right_center) / 2
    offset_in_root_frame = finger_midpoint - root_transform_tool[:3, 3]
    return root_transform_tool[:3, :3].T @ offset_in_root_frame


def _top_down_pose_builder(world: World, robot: Tracy, arm: Arms):
    """
    Build a ``pose(x, y, z) -> Pose`` closure that places the gripper's own finger
    midpoint (not its tool frame) at the given world-frame point, fixed top-down.

    :param world: The world the returned poses are expressed in.
    :param robot: The robot whose gripper geometry corrects the target.
    :param arm: Which arm's gripper geometry to use.
    """
    orientation = Pose.from_xyz_rpy(0, 0, 0, pitch=math.pi, reference_frame=world.root)
    tool_frame_rotation = orientation.to_rotation_matrix().evaluate()[:3, :3]
    finger_midpoint_offset = _finger_midpoint_offset(robot, arm)

    def pose(x: float, y: float, z: float) -> Pose:
        finger_target = numpy.array([x, y, z])
        tool_frame_target = finger_target - tool_frame_rotation @ finger_midpoint_offset
        return Pose.from_xyz_rpy(
            *tool_frame_target, pitch=math.pi, reference_frame=world.root
        )

    return pose


def _reach(
    world: World,
    sim: RealTimeSimulation,
    actuators: Dict[str, Actuator],
    arm: Arms,
    goal_pose: Pose,
) -> None:
    """
    Plan a Cartesian reach against an isolated scratch copy of ``world`` and play it
    back on the real, physically simulated ``sim``.

    Collision avoidance is off: a much more crowded scene than an open table (e.g. the
    Montessori board plus its three drawers) can make Giskard's own collision-avoidance
    solver repeatedly raise ``CollisionViolatedError`` even after widening clearances --
    confirmed directly, still colliding with the board, a drawer, and even the target
    shape itself. Orientation is still constrained (``translation_only=False``): every
    pose here shares the same fixed top-down orientation, and leaving it unconstrained
    let Giskard's own IK redundancy resolution drift the achieved orientation slightly
    on each leg.

    :param world: The live world to clone for planning; never itself modified.
    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name.
    :param arm: Which arm's tool centre point should reach ``goal_pose``.
    :param goal_pose: Target pose for the gripper's own finger midpoint.
    """
    trajectory = plan_cartesian_trajectory(
        world, arm, goal_pose, translation_only=False, avoid_collisions=False
    )
    follow_joint_trajectory(sim, actuators, trajectory)


@dataclass
class PickUpActionMujoco(ActionDescription):
    """
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`'s own field
    interface, but driven by direct MuJoCo actuator control; see this module's own
    docstring.
    """

    object_designator: Body
    """
    The body to pick up.
    """

    arm: Arms
    """
    Which arm picks it up.
    """

    grasp_description: GraspDescription
    """
    Accepted for interface parity with ``PickUpAction``; not yet read (see this module's
    own docstring) -- every grasp is currently a fixed top-down approach.
    """

    sim: RealTimeSimulation
    """
    The running real-time simulation to drive.
    """

    actuators: Dict[str, Actuator]
    """
    Every joint's own actuator, keyed by joint name.
    """

    hover_clearance: float = HOVER_CLEARANCE
    """
    See :data:`HOVER_CLEARANCE`.
    """

    finger_pad_table_clearance: float = FINGER_PAD_TABLE_CLEARANCE
    """
    See :data:`FINGER_PAD_TABLE_CLEARANCE`.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        world = self.world
        robot = self.robot
        pose = _top_down_pose_builder(world, robot, self.arm)

        body_center = _bounding_box_center_world(world, self.object_designator)
        grasp_z = _grasp_target_z(
            world,
            robot,
            self.arm,
            self.object_designator,
            self.finger_pad_table_clearance,
        )
        pick_hover = pose(
            body_center[0], body_center[1], body_center[2] + self.hover_clearance
        )
        pick_grasp = pose(body_center[0], body_center[1], grasp_z)

        _reach(world, self.sim, self.actuators, self.arm, pick_hover)
        _reach(world, self.sim, self.actuators, self.arm, pick_grasp)
        close_gripper_around(
            self.sim, self.actuators, robot, self.arm, self.object_designator
        )
        _reach(world, self.sim, self.actuators, self.arm, pick_hover)


@dataclass
class PlaceActionMujoco(ActionDescription):
    """
    :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`'s own field
    interface, but driven by direct MuJoCo actuator control; see this module's own
    docstring.
    """

    object_designator: Body
    """
    The body to place; only used to release it, since this action does not kinematically
    attach it in the first place (see this module's own docstring).
    """

    target_location: Pose
    """
    Where to place :attr:`object_designator`.
    """

    arm: Arms
    """
    Which arm places it.
    """

    sim: RealTimeSimulation
    """
    The running real-time simulation to drive.
    """

    actuators: Dict[str, Actuator]
    """
    Every joint's own actuator, keyed by joint name.
    """

    hover_clearance: float = HOVER_CLEARANCE
    """
    See :data:`HOVER_CLEARANCE`.
    """

    place_hover_clearance: float = PLACE_HOVER_CLEARANCE
    """
    See :data:`PLACE_HOVER_CLEARANCE`.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        world = self.world
        robot = self.robot
        pose = _top_down_pose_builder(world, robot, self.arm)

        target_position = self.target_location.to_position()
        place_hover = pose(
            float(target_position.x),
            float(target_position.y),
            float(target_position.z) + self.hover_clearance,
        )
        place_pose = pose(
            float(target_position.x),
            float(target_position.y),
            float(target_position.z) + self.place_hover_clearance,
        )

        _reach(world, self.sim, self.actuators, self.arm, place_hover)
        _reach(world, self.sim, self.actuators, self.arm, place_pose)
        set_gripper(self.sim, self.actuators, robot, self.arm, GripperState.OPEN)
        _reach(world, self.sim, self.actuators, self.arm, place_hover)
