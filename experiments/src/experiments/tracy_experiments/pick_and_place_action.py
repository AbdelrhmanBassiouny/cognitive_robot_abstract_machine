"""
:class:`PickUpActionMujoco`/:class:`PlaceActionMujoco`/:class:`InsertionActionMujoco`:
Mujoco-driven siblings of
:class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`/
:class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`/
:class:`~coraplex.robot_plans.actions.core.insertion.InsertionAction`, matching their
own field interface (``object_designator``, ``arm``, ``grasp_description``/
``target_location``/``target``) so a caller can compose them into a
:func:`~coraplex.plans.factories.sequential` plan the same way, but with each own leaf
motion running plain Python (see :meth:`PickUpActionMujoco._run`/
:meth:`PlaceActionMujoco._run`/:meth:`InsertionActionMujoco._run`, wrapped via
:func:`~coraplex.plans.factories.code`) rather than a Giskard motion mapping.

The real ``PickUpAction``/``PlaceAction`` build their own plan entirely from
``MoveToolCenterPointMotion``/``MoveGripperMotion`` designators, each of which ticks
Giskard's own closed loop live against the world model
(:class:`~coraplex.robot_plans.motions.gripper.MoveToolCenterPointMotion` →
:class:`~coraplex.plans.plan_node.MotionNode` →
:class:`~coraplex.plans.executables.GiskardExecutable`). That races
:class:`~semantic_digital_twin.adapters.multi_sim.MujocoSynchronizer`'s own
physics-thread state sync for a physically simulated robot -- see
:mod:`~experiments.tracy_experiments.equipment`'s own module docstring. The actions here
instead reuse :mod:`~experiments.tracy_experiments.trajectory_planning`'s own
plan-then-execute functions directly: each reach is planned by Giskard against an
isolated scratch copy of the world, then the resulting trajectory is played back by
commanding the real MuJoCo actuators.

Unlike ``PickUpAction``/``PlaceAction``, no action here kinematically attaches or
detaches the object (no ``AttachNode``/``DetachNode``): the object is held only by real
MuJoCo contact friction between the fingers throughout -- a kinematically snapped object
is not left behind by a friction hold's own continuous motion the way an instantaneous
kinematic detach would otherwise risk. They are generic over any body and arm, used the
same way for a Montessori shape being sorted into a hole and a cube being stacked onto
another.

Every action here is turned the way its own ``grasp_description`` says, so the answer a
plan resolved the grasp to is what the gripper is actually held in rather than something
the lab decided for itself. The grasp's own orientation is read in the world root frame,
which is a body's own frame for as long as the body stands square to the world -- which
is how this lab lays its pieces out; see :func:`_finger_midpoint_offset`'s own docstring
for where the fingers stand once the gripper is turned there.

:class:`ActuatorDrivenAction` is what ties the two families together: each action here
says which action of a plan it carries out, so a plan resolved in the words it was
written in can be handed to the lab that can run it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy
from typing_extensions import Callable, Dict, Generic, List, Self, Type, TypeVar

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import code
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.insertion import (
    DEFAULT_HOVER_HEIGHT,
    InsertionAction,
)
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.mixins import ManipulatesBodies
from dataclasses import dataclass
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from experiments.tracy_experiments.trajectory_planning import (
    close_gripper_around,
    follow_joint_trajectory,
    plan_cartesian_trajectory,
    set_gripper,
)
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
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

GRASP_CLOSE_SWING_CLEARANCE = 0.0435
"""
Extra height, in metres, added on top of the object's own vertical centre when reaching
the grasp pose, so the fingertip pads still clear the resting surface after closing.

The pads aren't fixed relative to the tool frame: as the Robotiq-85 knuckle closes, each
pad's own position travels ~1.35cm further out along the gripper's reach axis (measured
directly: pad centre sits at 0.1208m from the gripper mount when open, 0.1343m when
closed) -- confirmed directly, a pad that clears the table by that same ~1.35cm while
open ends up flush with the table once closed. ``0.015`` covers that swing with a small
margin.
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


def _grasp_pose_builder(
    world: World, robot: Tracy, arm: Arms, grasp: GraspDescription
) -> Callable[[float, float, float], Pose]:
    """
    Build a ``pose(x, y, z) -> Pose`` closure that places the gripper's own finger
    midpoint (not its tool frame) at the given world-frame point, with the gripper
    turned the way ``grasp`` describes.

    :param world: The world the returned poses are expressed in.
    :param robot: The robot whose gripper geometry corrects the target.
    :param arm: Which arm's gripper geometry to use.
    :param grasp: How the body is taken hold of, which says how the gripper is turned.
    """
    orientation = grasp.grasp_orientation()
    tool_frame_rotation = numpy.array(
        orientation.to_rotation_matrix().evaluate()[:3, :3], dtype=float
    )
    finger_midpoint_offset = _finger_midpoint_offset(robot, arm)

    def pose(x: float, y: float, z: float) -> Pose:
        finger_target = numpy.array([x, y, z])
        tool_frame_target = finger_target - tool_frame_rotation @ finger_midpoint_offset
        return Pose(Point3(*tool_frame_target), orientation, reference_frame=world.root)

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


# %% the plan on one side, the actuators on the other


ActionT = TypeVar("ActionT", bound=ActionDescription)


class NoActionCarriesItOut(LookupError):
    """
    Raised when a plan states an action no member of :class:`ActuatorDrivenAction`
    carries out, so the lab cannot run it.
    """

    def __init__(self, action: ActionDescription):
        super().__init__(
            f"No action driving the actuators carries out {type(action).__name__}."
        )
        self.action = action
        """
        The action of the plan that nothing here carries out.
        """


@dataclass
class ActuatorDrivenAction(Generic[ActionT], SubClassSafeGeneric, ABC):
    """
    An action that carries one a plan states out by commanding a running simulation's
    actuators.

    Each member binds the action of a plan it carries out, so a plan resolved in the
    words it was written in can be run in a lab whose robot is a simulated one without
    anything having to say, action by action, which class stands for which.
    """

    @classmethod
    def action_it_carries_out(cls) -> Type[ActionT]:
        """
        The action of a plan this one carries out, read off the type parameter it binds.
        """
        return cls.get_generic_type_parameters()[0]

    @classmethod
    @abstractmethod
    def carrying_out(
        cls,
        action: ActionT,
        simulation: RealTimeSimulation,
        actuators: Dict[str, Actuator],
    ) -> Self:
        """
        Build this action from the one it carries out.

        :param action: The action of the plan, with everything it left open answered.
        :param simulation: The running simulation whose actuators are driven.
        :param actuators: Every joint's own actuator, keyed by joint name.
        """

    @classmethod
    def performing(
        cls,
        plan: List[ActionDescription],
        simulation: RealTimeSimulation,
        actuators: Dict[str, Actuator],
    ) -> List[ActuatorDrivenAction]:
        """
        Say how a resolved plan is run here: for every action it states, the one that
        carries that action out.

        :param plan: The actions the plan came to, in the order it runs them.
        :param simulation: The running simulation whose actuators are driven.
        :param actuators: Every joint's own actuator, keyed by joint name.
        :return: The actions carrying them out, in the same order.
        :raises NoActionCarriesItOut: Where nothing here carries one of them out.
        """
        return [
            cls._carrier_of(action).carrying_out(action, simulation, actuators)
            for action in plan
        ]

    @classmethod
    def _carrier_of(cls, action: ActionDescription) -> Type[ActuatorDrivenAction]:
        """
        :param action: An action of a plan.
        :return: The member of this family that carries it out.
        :raises NoActionCarriesItOut: Where no member does.
        """
        carriers = [
            member
            for member in cls.__subclasses__()
            if isinstance(action, member.action_it_carries_out())
        ]
        if not carriers:
            raise NoActionCarriesItOut(action)
        [carrier] = carriers
        return carrier


@dataclass
class PickUpActionMujoco(
    ActionDescription, ManipulatesBodies, ActuatorDrivenAction[PickUpAction]
):
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
    How the body is taken hold of, which says how the gripper is turned to reach it.
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

    @classmethod
    def carrying_out(
        cls,
        action: PickUpAction,
        simulation: RealTimeSimulation,
        actuators: Dict[str, Actuator],
    ) -> Self:
        return cls(
            object_designator=action.object_designator.root,
            arm=action.arm,
            grasp_description=action.grasp_description,
            sim=simulation,
            actuators=actuators,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        world = self.world
        robot = self.robot
        pose = _grasp_pose_builder(world, robot, self.arm, self.grasp_description)

        body_center = _bounding_box_center_world(world, self.object_designator)
        pick_hover = pose(
            body_center[0], body_center[1], body_center[2] + self.hover_clearance
        )
        pick_grasp = pose(
            body_center[0],
            body_center[1],
            body_center[2] + GRASP_CLOSE_SWING_CLEARANCE,
        )

        _reach(world, self.sim, self.actuators, self.arm, pick_hover)
        _reach(world, self.sim, self.actuators, self.arm, pick_grasp)
        close_gripper_around(
            self.sim, self.actuators, robot, self.arm, self.object_designator
        )
        _reach(world, self.sim, self.actuators, self.arm, pick_hover)


@dataclass
class PlaceActionMujoco(
    ActionDescription, ManipulatesBodies, ActuatorDrivenAction[PlaceAction]
):
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

    grasp_description: GraspDescription
    """
    How the body is held, which says how the gripper is turned to carry and release it.
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

    @classmethod
    def carrying_out(
        cls,
        action: PlaceAction,
        simulation: RealTimeSimulation,
        actuators: Dict[str, Actuator],
    ) -> Self:
        return cls(
            object_designator=action.object_designator.root,
            target_location=action.target_location,
            arm=action.arm,
            grasp_description=action.grasp_description,
            sim=simulation,
            actuators=actuators,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        world = self.world
        robot = self.robot
        pose = _grasp_pose_builder(world, robot, self.arm, self.grasp_description)

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


@dataclass
class InsertionActionMujoco(
    ActionDescription, ManipulatesBodies, ActuatorDrivenAction[InsertionAction]
):
    """
    :class:`~coraplex.robot_plans.actions.core.insertion.InsertionAction`'s own field
    interface, but driven by direct MuJoCo actuator control; see this module's own
    docstring.

    What a place and an insertion do with the actuators is the same reach, descend, open
    and retreat; what differs is where the release pose comes from. A place is handed
    one, and this works it out from the opening the body goes through, so the body is
    released over that opening however the opening stands.
    """

    object_designator: Body
    """
    The body to put through :attr:`target`.
    """

    target: Aperture
    """
    The opening the body goes through, which the release pose is stated in the frame of.
    """

    arm: Arms
    """
    Which arm carries it.
    """

    grasp_description: GraspDescription
    """
    How the body is held, which says how the gripper is turned to carry and release it.
    """

    sim: RealTimeSimulation
    """
    The running real-time simulation to drive.
    """

    actuators: Dict[str, Actuator]
    """
    Every joint's own actuator, keyed by joint name.
    """

    hover_height: float = DEFAULT_HOVER_HEIGHT
    """
    How far above :attr:`target`'s own origin, along its own axis, the body's own centre
    is let go of.
    """

    hover_clearance: float = HOVER_CLEARANCE
    """
    See :data:`HOVER_CLEARANCE`.
    """

    finger_hold_clearance: float = GRASP_CLOSE_SWING_CLEARANCE
    """
    How far below the fingers' own midpoint a held body's centre sits, so opening with
    the midpoint that far above the release pose lets the body go with its centre there;
    see :data:`GRASP_CLOSE_SWING_CLEARANCE`.
    """

    @classmethod
    def carrying_out(
        cls,
        action: InsertionAction,
        simulation: RealTimeSimulation,
        actuators: Dict[str, Actuator],
    ) -> Self:
        return cls(
            object_designator=action.object_designator.root,
            target=action.target,
            arm=action.arm,
            grasp_description=action.grasp_description,
            sim=simulation,
            actuators=actuators,
            hover_height=action.hover_height,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def release_pose(self) -> Pose:
        """
        Where the body's own centre is let go, in the world root frame.
        """
        return self.world.transform(
            Pose.from_xyz_rpy(
                0.0, 0.0, self.hover_height, reference_frame=self.target.root
            ),
            self.world.root,
        )

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)

    def _run(self) -> None:
        world = self.world
        pose = _grasp_pose_builder(world, self.robot, self.arm, self.grasp_description)

        released_at = self.release_pose.to_position()
        insertion_hover = pose(
            float(released_at.x),
            float(released_at.y),
            float(released_at.z) + self.hover_clearance,
        )
        release = pose(
            float(released_at.x),
            float(released_at.y),
            float(released_at.z) + self.finger_hold_clearance,
        )

        _reach(world, self.sim, self.actuators, self.arm, insertion_hover)
        _reach(world, self.sim, self.actuators, self.arm, release)
        set_gripper(self.sim, self.actuators, self.robot, self.arm, GripperState.OPEN)
        _reach(world, self.sim, self.actuators, self.arm, insertion_hover)
