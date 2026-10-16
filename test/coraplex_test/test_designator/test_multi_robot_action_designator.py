from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np
import pytest
from rustworkx.rustworkx import NoEdgeBetweenNodes
from typing_extensions import Generator, Iterable, List, Tuple

from coraplex.datastructures.enums import (
    AxisIdentifier,
    DetectionTechnique,
)
from coraplex.datastructures.trajectory import PoseTrajectory
from coraplex.exceptions import NoFloorBelowRobot
from coraplex.plans.plan_transformation import PlanRewriting
from cramph.statechart import Statechart
from cramph.composites import Parallel, Sequence, TryAll, TryInOrder
from cramph.threaded_nodes import FunctionCall
from cramph.data_types import LifeCycleValues
from coraplex.robot_plans.plan_transformations import (
    OpenDrawerBeforeMoveAndPickUp,
    ParkArmsBeforeFirstAction,
)
from coraplex.robot_plans.actions.composite.searching import (
    SearchAction,
    SweepRegion,
    SweepRegionPlacement,
)
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from coraplex.robot_plans.actions.core.container import OpenAction, CloseAction
from coraplex.robot_plans.actions.core.misc import DetectAction, MoveToReach
from coraplex.robot_plans.actions.core.navigation import (
    FaceAtAction,
    NavigateAction,
    LookAtAction,
    ElevatorNavigation,
)
from coraplex.robot_plans.actions.core.navigation import (
    PathPlanningNavigateAction,
)
from coraplex.robot_plans.actions.core.pick_up import (
    ReachAction,
    GraspingAction,
    PickUpAction,
)
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import (
    MoveTorsoAction,
    SetGripperAction,
    ParkArmsAction,
    FollowToolCenterPointPathAction,
    MoveFingersToWidthAction,
    MoveManipulatorAction,
)
from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.composite.carrying import CarryAction
from coraplex.robot_plans.actions.composite.facing import FaceAndLookAtAction
from coraplex.robot_plans.actions.composite.transporting import MoveAndPlaceAction
from coraplex.robot_plans.actions.core.exceptions import WidthBeyondGripperOpening
from cramph.node import StatechartNode
from cramph.world_modification_nodes import MoveBranch
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import SetOdometry
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    DistanceAlongAxis,
    HoldPose,
)
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointState,
    JointVelocityLimit,
)
from giskardpy.motion_statechart.tasks.pointing import Pointing
from giskardpy.utils.utils_for_tests import compare_axis_angle, compare_orientations
from semantic_digital_twin.callbacks.callback import ModelChangeCallback
from semantic_digital_twin.datastructures.definitions import (
    TorsoState,
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.reasoning.robot_predicates import get_visible_bodies
from semantic_digital_twin.robots.robot_part_mixins import HasMobileBase
from semantic_digital_twin.robots.robot_parts import AbstractRobot, EndEffector
from ..conftest import (
    grasp_point_of,
    left_or_only_arm,
    motion_nodes_in_physics_of,
    motion_nodes_of,
    nodes_of_type,
    physically_simulated_executor,
    right_or_only_arm,
)
from ..world_snapshot import WorldSnapshot

from semantic_digital_twin.robots.garmi import Garmi
from semantic_digital_twin.robots.hsrb import HSRB
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.stretch import Stretch
from semantic_digital_twin.robots.tiago import Tiago
from semantic_digital_twin.specifications.connections import (
    PrismaticConnectionSpecification,
)
from semantic_digital_twin.exceptions import MissingMovableJointError
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Door,
    Elevator,
    FirstFloor,
    Floor,
    GroundFloor,
    Handle,
    Level,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Cup,
    Milk,
    Spoon,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Quaternion,
    Vector3,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose, Pose2D
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Cylinder, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ...conftest import SAMPLING_SEED
from ...plan_running import (
    context_of,
    expand,
    robot_executor,
    robot_extensions,
    run_plan,
    simulated_executor,
    statechart_of,
)
from cramph.context import ContextExtension

# %% standing a robot next to something


def attach_to_statechart(action, extensions) -> None:
    """
    Puts `action` into a statechart without running it, which is what gives it the world
    and the robot it reads its path out of.

    :param action: The action to attach.
    :param extensions: The context extensions of the plan the statechart is built for.
    """
    statechart_of(simulated_executor(extensions), action)


def heading_towards(
    world_P_stand: Iterable[float], world_P_target: Iterable[float], world: World
) -> Pose:
    """
    A pose at ``world_P_stand`` whose x-axis points at ``world_P_target``.

    This is the form
    :class:`~coraplex.robot_plans.actions.core.navigation.NavigateAction` and
    :meth:`~semantic_digital_twin.robots.robot_parts.MobileBase.pose_facing` read a
    heading in: they turn it into a base orientation using the base's own forward axis,
    so a test says where the robot should look rather than how far each base has to turn
    to look there.
    """
    world_V_heading = np.asarray(world_P_target)[:2] - np.asarray(world_P_stand)[:2]
    return Pose.from_xyz_rpy(
        *np.asarray(world_P_stand)[:3],
        yaw=float(np.arctan2(world_V_heading[1], world_V_heading[0])),
        reference_frame=world.root,
    )


def _handle_annotation(world, body_name: str):
    """
    :return: The handle annotation of the named body, registering one when the world
        carries none for it.
    """
    body = world.get_body_by_name(body_name)
    existing = [
        handle
        for handle in world.get_semantic_annotations_by_type(Handle)
        if handle.root is body
    ]
    if existing:
        return existing[0]
    with world.modify_world():
        world.add_semantic_annotation_recursively(handle := Handle(root=body))
    return handle


def stand_facing(
    robot: AbstractRobot,
    world_P_stand: Iterable[float],
    world_P_target: Iterable[float],
    world: World,
) -> HomogeneousTransformationMatrix:
    """
    The base pose from which ``robot`` works on ``world_P_target``, standing at
    ``world_P_stand``.

    A robot reaches along its base's forward axis rather than along the direction it
    drives in, so where a test drops it decides whether the target is in front of the
    arm or off to its side.
    """
    return robot.mobile_base.pose_facing(
        heading_towards(world_P_stand, world_P_target, world)
    ).homogeneous_matrix


@pytest.fixture(
    scope="session",
    params=["hsrb", "stretch", "tiago", "pr2", "garmi"],
)
def setup_multi_robot_apartment(
    request,
    _hsr_world_setup,
    _stretch_world_setup,
    _tiago_world_setup,
    _pr2_world_setup,
    _apartment_world_setup,
    multi_story_building,
):
    apartment_copy = deepcopy(_apartment_world_setup)
    apartment_copy.merge_world_at_pose(
        deepcopy(multi_story_building),
        HomogeneousTransformationMatrix.from_xyz_rpy(0, -5, 0),
    )

    if request.param == "hsrb":
        hsr_copy = deepcopy(_hsr_world_setup)
        apartment_copy.merge_world(hsr_copy)
        view = apartment_copy.get_semantic_annotations_by_type(HSRB)
        if not view:
            view = HSRB.from_world(apartment_copy)
        else:
            view = view[0]
        view.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(1.5, 2, 0)
        )
        return apartment_copy, view
    elif request.param == "stretch":
        stretch_copy = deepcopy(_stretch_world_setup)
        apartment_copy.merge_world(
            stretch_copy,
        )
        view = apartment_copy.get_semantic_annotations_by_type(Stretch)
        if not view:
            view = Stretch.from_world(stretch_copy)
        else:
            view = view[0]
        view.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(1.5, 2, 0)
        )
        return apartment_copy, view

    elif request.param == "tiago":
        tiago_copy = deepcopy(_tiago_world_setup)
        apartment_copy.merge_world(
            tiago_copy,
        )
        view = apartment_copy.get_semantic_annotations_by_type(Tiago)
        if not view:
            view = Tiago.from_world(tiago_copy)
        else:
            view = view[0]
        view.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(1.5, 2, 0)
        )
        return apartment_copy, view

    elif request.param == "pr2":
        pr2_copy = deepcopy(_pr2_world_setup)
        apartment_copy.merge_world(
            pr2_copy,
        )
        view = apartment_copy.get_semantic_annotations_by_type(PR2)
        if not view:
            view = PR2.from_world(pr2_copy)
        else:
            view = view[0]
        view.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(1.5, 2, 0)
        )
        return apartment_copy, view

    elif request.param == "garmi":
        garmi_copy = deepcopy(request.getfixturevalue("_garmi_world_setup"))
        apartment_copy.merge_world(
            garmi_copy,
        )
        view = apartment_copy.get_semantic_annotations_by_type(Garmi)[0]
        view.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(1.5, 2, 0)
        )
        for arm in view.all_arms:
            joint_state = arm.get_joint_state_by_type(StaticJointState.PARK)
            joint_state.apply_to(apartment_copy)

        return apartment_copy, view


@pytest.fixture
def multiple_robot_apartment_context(
    setup_multi_robot_apartment,
) -> Generator[Tuple[World, AbstractRobot, List[ContextExtension]]]:
    """
    The shared apartment world with one robot, the robot and the context extensions of
    its plans, returned to its initial model, state and full body control setting after
    the test.
    """
    world, view = setup_multi_robot_apartment
    snapshot = WorldSnapshot.capture(world)
    full_body_controlled = (
        view.mobile_base.full_body_controlled
        if isinstance(view, HasMobileBase)
        else False
    )
    yield world, view, robot_extensions(view)
    view.mobile_base.full_body_controlled = full_body_controlled
    snapshot.restore()


def test_move_torso_multi(multiple_robot_apartment_context):
    world, view, extensions = multiple_robot_apartment_context
    plan = MoveTorsoAction(TorsoState.HIGH)
    run_plan(plan, extensions)
    joint_state = view.get_torso().get_joint_state_by_type(TorsoState.HIGH)

    for connection, target in joint_state.items():
        assert connection.position == pytest.approx(target, abs=0.01)


def test_navigate_multi(multiple_robot_apartment_context, rclpy_node):
    world, view, extensions = multiple_robot_apartment_context
    target_position = [5, 2, 0]

    plan = NavigateAction(
        Pose(Point3.from_iterable(target_position), reference_frame=world.root)
    )

    run_plan(plan, extensions)
    robot_base_position = view.root.global_transform.position.to_np()
    # An identity heading points the robot's front along the world's x-axis, whatever
    # the axes its own base happens to be modelled with.
    world_R_base = view.mobile_base.root.global_transform.rotation_matrix
    world_V_forward = world_R_base @ view.mobile_base.forward_axis

    assert robot_base_position[:3] == pytest.approx(target_position, abs=0.01)
    assert world_V_forward.to_np()[:3].flatten() == pytest.approx([1, 0, 0], abs=0.01)


def test_move_gripper_multi(multiple_robot_apartment_context):
    world, view, extensions = multiple_robot_apartment_context

    plan = SetGripperAction(left_or_only_arm(view).end_effector, GripperState.OPEN)

    executor = run_plan(plan, extensions)
    arm = view.all_arms[0]
    open_state = arm.end_effector.get_joint_state_by_type(GripperState.OPEN)
    close_state = arm.end_effector.get_joint_state_by_type(GripperState.CLOSE)

    for connection, target in open_state.items():
        assert connection.position == pytest.approx(target, abs=0.02)

    plan = SetGripperAction(left_or_only_arm(view).end_effector, GripperState.CLOSE)

    run_plan(plan, extensions)
    for connection, target in close_state.items():
        assert connection.position == pytest.approx(target, abs=0.02)


def test_park_arms_multi(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context
    description = ParkArmsAction(robot.all_arms)
    plan = description
    assert description.arms == robot.all_arms
    run_plan(plan, extensions)
    joints = []
    states = []
    for arm in robot.all_arms:
        joint_state = arm.get_joint_state_by_type(StaticJointState.PARK)
        joints.extend(joint_state.connections)
        states.extend(joint_state.target_values)
    for connection, value in zip(joints, states):
        compare_axis_angle(
            connection.position,
            np.array([1, 0, 0]),
            value,
            np.array([1, 0, 0]),
            decimal=1,
        )


def test_reach_action_multi(multiple_robot_apartment_context):
    world, view, extensions = multiple_robot_apartment_context

    left_arm = left_or_only_arm(view)

    milk = world.get_semantic_annotations_by_type(Milk)[0]
    grasp_pose = Pose(reference_frame=milk.root)
    milk_body = milk.root
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        1, -2, 0.8, reference_frame=world.root
    )
    view.root.parent_connection.origin = stand_facing(
        view, (0.3, -2.4, 0), milk_body.global_pose.position.to_np(), world
    )
    world.notify_state_change()

    plan = Sequence(
        [
            ParkArmsAction(view.all_arms),
            ReachAction(
                grasp=GraspCandidate(milk, grasp_pose),
                arm=left_or_only_arm(view),
            ),
        ]
    )

    run_plan(plan, extensions)
    end_effector_pose = left_arm.end_effector.tool_frame.global_transform
    end_effector_orientation = end_effector_pose.quaternion.to_np()

    target_orientation = left_arm.end_effector.tool_frame_goal(grasp_pose).quaternion

    assert grasp_point_of(left_arm) == pytest.approx([1, -2, 0.8], abs=0.01)
    compare_orientations(
        end_effector_orientation, target_orientation.to_np(), decimal=2
    )


def test_follow_tcp_path_multi(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context

    if isinstance(robot, (Tiago)):
        # do not allow since
        robot.mobile_base.full_body_controlled = False
        robot.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(
                1.7, 1.7, 0, reference_frame=world.root
            )
        )
        world.notify_state_change()

    if isinstance(robot, (Stretch)):
        # do not allow since
        robot.mobile_base.full_body_controlled = False
        robot.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(
                2.12, 2.2, 0, reference_frame=world.root
            )
        )
        world.notify_state_change()
    # robot.full_body_controlled = True
    left_arm = left_or_only_arm(robot)
    front_axis = tuple(int(v) for v in left_arm.end_effector.approach_axis.to_np()[:3])
    grasp_axis = AxisIdentifier.from_tuple(front_axis)

    pose_T = world.get_body_by_name("milk.stl").global_transform
    pose = pose_T.pose
    if grasp_axis == AxisIdentifier.X:
        target_pose = pose
    elif grasp_axis == AxisIdentifier.Z:
        offset_T = HomogeneousTransformationMatrix.from_xyz_axis_angle(
            axis=AxisIdentifier.Y.value,
            angle=np.pi / 2,
            reference_frame=world.root,
        )
        target_pose = (pose_T @ offset_T).pose
    else:
        target_pose = pose

    waypoints = PoseTrajectory([target_pose])
    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            ParkArmsAction(robot.all_arms),
            FollowToolCenterPointPathAction(
                arm=left_or_only_arm(robot), target_locations=waypoints
            ),
        ]
    )
    run_plan(plan, extensions)
    tip_pose = left_arm.end_effector.tool_frame.global_transform
    dist = np.linalg.norm(tip_pose.position - np.array(target_pose.position))
    assert dist < 0.01


def test_grasping(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context
    left_arm = left_or_only_arm(robot)

    milk = world.get_semantic_annotations_by_type(Milk)[0]
    grasping_action = GraspingAction(
        GraspCandidate.from_body_origin(milk),
        left_or_only_arm(robot),
    )

    milk_body = milk.root
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        1, -2, 0.8, reference_frame=world.root
    )
    robot.root.parent_connection.origin = stand_facing(
        robot, (0.3, -2.4, 0), milk_body.global_pose.position.to_np(), world
    )
    world.notify_state_change()

    plan = Sequence(
        [
            ParkArmsAction(robot.all_arms),
            grasping_action,
        ]
    )
    run_plan(plan, extensions)
    # The grasp is the milk's own origin, so that is where the fingers end up.
    assert np.allclose(
        milk_body.global_pose.position.to_np().flatten()[:3],
        grasp_point_of(left_arm),
        atol=0.01,
    )


def test_pick_up_multi(multiple_robot_apartment_context, rclpy_node):
    world, view, extensions = multiple_robot_apartment_context

    left_arm = left_or_only_arm(view)
    milk_body = world.get_body_by_name("milk.stl")
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        1, -2, 0.6, reference_frame=world.root
    )
    view.root.parent_connection.origin = stand_facing(
        view, (0.3, -2.4, 0), milk_body.global_pose.position.to_np(), world
    )
    world.notify_state_change()

    root = Sequence(
        [
            ParkArmsAction(view.all_arms),
            PickUpAction(
                world.get_semantic_annotations_by_type(Milk)[0].grasp_candidates()[0],
                left_or_only_arm(view),
            ),
        ]
    )

    run_plan(root, extensions)
    assert (
        world.get_connection(
            left_arm.end_effector.tool_frame,
            world.get_body_by_name("milk.stl"),
        )
        is not None
    )

    assert np.allclose(
        world.get_body_by_name("milk.stl").global_pose.position.to_np().flatten()[:3],
        grasp_point_of(left_arm),
        atol=0.01,
    )


def test_place_multi(multiple_robot_apartment_context):
    world, view, extensions = multiple_robot_apartment_context

    left_arm = left_or_only_arm(view)
    milk_body = world.get_body_by_name("milk.stl")
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        1, -2, 0.6, reference_frame=world.root
    )
    view.root.parent_connection.origin = stand_facing(
        view, (0.3, -2.4, 0), milk_body.global_pose.position.to_np(), world
    )
    world.notify_state_change()

    root = Sequence(
        [
            ParkArmsAction(view.all_arms),
            PickUpAction(
                world.get_semantic_annotations_by_type(Milk)[0].grasp_candidates()[0],
                left_or_only_arm(view),
            ),
            PlaceAction(
                world.get_semantic_annotations_by_type(Milk)[0],
                Pose(Point3.from_iterable([1, -2.2, 0.6]), reference_frame=world.root),
            ),
        ]
    )

    run_plan(root, extensions)
    with pytest.raises(NoEdgeBetweenNodes):
        world.get_connection(
            left_arm.end_effector.tool_frame,
            world.get_body_by_name("milk.stl"),
        )

    milk_position = milk_body.global_transform.position.to_np()

    assert milk_position[:3] == pytest.approx([1, -2.2, 0.6], abs=0.01)


def test_look_at(multiple_robot_apartment_context):
    world, robot_view, extensions = multiple_robot_apartment_context
    description = LookAtAction(
        Pose(Point3.from_iterable([3, 0, 1]), reference_frame=world.root)
    )
    assert np.allclose(
        description.target.to_np(),
        Pose(Point3.from_iterable([3, 0, 1]), reference_frame=world.root).to_np(),
        atol=1e-3,
    )

    plan = description
    run_plan(plan, extensions)


def test_detect(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context
    milk_body = world.get_body_by_name("milk.stl")

    # East of the multi-storey building the fixture merges in, so that the robot looks
    # at the milk rather than at one of the building's room walls.
    robot.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        5, -2, 0
    )
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        6, -2, 1.2, reference_frame=world.root
    )

    description = DetectAction(
        technique=DetectionTechnique.TYPES,
        object_sem_annotation=Milk,
    )
    plan = description
    run_plan(plan, extensions)
    # Detection returns no value; it writes what it saw into the world by moving the
    # perceived annotation's body to the detected pose.
    milk_annotations = world.get_semantic_annotations_by_type(Milk)
    assert milk_annotations
    perceived = milk_annotations[0]
    assert milk_body in perceived.bodies
    np.testing.assert_allclose(
        milk_body.global_pose.position.to_np().flatten()[:3],
        (6, -2, 1.2),
        atol=1e-9,
    )


def test_open(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context
    if isinstance(robot, Garmi):
        return

    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            ParkArmsAction(robot.all_arms),
            NavigateAction(
                Pose(
                    Point3.from_iterable([1.6, 1.9, 0]),
                    Quaternion.from_iterable([0, 0, 0.3, 1]),
                    reference_frame=world.root,
                )
            ),
            OpenAction.from_handle(
                _handle_annotation(world, "handle_cab10_m"),
                left_or_only_arm(robot),
            ),
        ]
    )
    run_plan(plan, extensions)
    assert world.get_connection_by_name(
        "cabinet10_drawer_middle_joint"
    ).position == pytest.approx(0.45, abs=0.1)


def test_close(multiple_robot_apartment_context, rclpy_node):
    world, robot, extensions = multiple_robot_apartment_context

    world.get_connection_by_name("cabinet10_drawer_middle_joint").position = 0.3
    world.notify_state_change()

    handle = _handle_annotation(world, "handle_cab10_m")
    navigate_position = (
        [1.5, 1.85, 0] if isinstance(robot, (Tiago, Stretch)) else [1.65, 2.0, 0]
    )

    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            ParkArmsAction(robot.all_arms),
            NavigateAction(
                heading_towards(
                    navigate_position,
                    handle.root.global_pose.position.to_np(),
                    world,
                )
            ),
            CloseAction.from_handle(handle, left_or_only_arm(robot)),
        ]
    )
    run_plan(plan, extensions)
    assert world.get_connection_by_name(
        "cabinet10_drawer_middle_joint"
    ).position == pytest.approx(0, abs=0.1)


def test_facing(multiple_robot_apartment_context):
    world, robot, extensions = multiple_robot_apartment_context

    milk_pose = world.get_body_by_name("milk.stl").global_pose
    plan = FaceAtAction(milk_pose)
    run_plan(plan, extensions)
    milk_in_base_frame = world.transform(
        world.get_body_by_name("milk.stl").global_transform,
        robot.mobile_base.root,
    )
    # Facing the milk means it lies along the base's forward axis, which is the
    # x-axis only for a base modelled that way. The base turns about the vertical,
    # so only the horizontal direction to the milk is under test.
    base_P_milk = milk_in_base_frame.position.to_np()[:2].flatten()
    base_V_milk = base_P_milk / np.linalg.norm(base_P_milk)

    assert base_V_milk == pytest.approx(
        robot.mobile_base.forward_axis.to_np()[:2].flatten(), abs=0.01
    )


def test_transport(multiple_robot_apartment_context, rclpy_node):
    world, robot, extensions = multiple_robot_apartment_context

    description = TransportAction.from_graspable_by_closest_grasps(
        world.get_semantic_annotations_by_type(Milk)[0],
        Pose(
            Point3.from_iterable([3.1, 2.2, 0.95]),
            Quaternion.from_iterable([0.0, 0.0, 1.0, 0.0]),
            reference_frame=world.root,
        ),
        right_or_only_arm(robot),
        context_of(extensions),
        seed=SAMPLING_SEED,
    )
    plan = Sequence([MoveTorsoAction(TorsoState.HIGH), description])
    run_plan(plan, extensions)
    milk_position = world.get_body_by_name("milk.stl").global_transform.to_np()[:3, 3]
    dist = np.linalg.norm(milk_position - np.array([3.1, 2.2, 0.95]))
    assert dist <= 0.02


def test_move_to_reach(multiple_robot_apartment_context, rclpy_node):
    world, robot, extensions = multiple_robot_apartment_context
    move_to_reach = MoveToReach(
        target_pose_offset_robot=Pose2D(0.2, -0.55),
        reference_T_grasp=Pose.from_xyz_rpy(
            x=0.7, y=-1.3, z=0.9, reference_frame=world.root
        ),
        hip_rotation=0.0,
        end_effector=world.get_semantic_annotations_by_type(EndEffector)[0],
    )

    plan = move_to_reach
    run_plan(plan, extensions)


def test_transport_open_container(multiple_robot_apartment_context, rclpy_node):
    world, robot, extensions = multiple_robot_apartment_context

    if isinstance(robot, HSRB):
        return
    target_pose = Pose.from_xyz_rpy(
        5.1, 3.25, 0.75, yaw=1.57, reference_frame=world.root
    )
    plan_transformations = [OpenDrawerBeforeMoveAndPickUp()]
    description = TransportAction.from_graspable_by_closest_grasps(
        world.get_semantic_annotations_by_type(Spoon)[0],
        target_pose,
        right_or_only_arm(robot),
        context_of(extensions),
        seed=SAMPLING_SEED,
    )
    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            ParkArmsAction(robot.all_arms),
            description,
        ]
    )
    run_plan(plan, [*extensions, PlanRewriting(transformations=plan_transformations)])
    spoon_position = world.get_body_by_name("spoon.stl").global_pose
    np.testing.assert_allclose(spoon_position, target_pose, atol=0.02)


def test_multi_robot_gcs_navigation(multiple_robot_apartment_context, rclpy_node):
    """
    The robot ends up at the target, having driven around the furniture between it and
    where it started rather than through it.
    """
    world, robot, extensions = multiple_robot_apartment_context
    target_position = [5, 1]

    plan = PathPlanningNavigateAction(
        Pose.from_xyz_rpy(*target_position, 0, reference_frame=world.root)
    )

    run_plan(plan, extensions)
    robot_base_position = robot.global_transform.position.to_np().flatten()

    assert robot_base_position[:2] == pytest.approx(target_position, abs=0.01)


def test_gcs_navigation_arrives_at_each_waypoint_facing_the_next_one(
    multiple_robot_apartment_context,
):
    """
    Lining a waypoint's orientation up with the leg leaving it saves the next leg the
    turn it would otherwise start with, which is what a differential drive pays for.
    """
    world, robot, extensions = multiple_robot_apartment_context

    action = PathPlanningNavigateAction(
        Pose.from_xyz_rpy(5, 1, 0, reference_frame=world.root)
    )
    attach_to_statechart(action, extensions)

    waypoints = action._waypoints()
    path = action._path()

    # The path starts at the first waypoint the robot has to travel to, not at the
    # waypoint it is already standing on.
    assert len(path) == len(waypoints) - 1

    for pose, waypoint, next_waypoint in zip(path, waypoints[1:], waypoints[2:]):
        world_V_travel = np.array(
            [float(next_waypoint.x - waypoint.x), float(next_waypoint.y - waypoint.y)]
        )
        world_V_facing = pose.rotation_matrix.to_np()[:2, 0]

        assert world_V_facing == pytest.approx(
            world_V_travel / np.linalg.norm(world_V_travel), abs=0.01
        )


def test_gcs_navigation_plans_on_the_floor_the_robot_stands_on(
    multiple_robot_apartment_context,
):
    """
    The free space the robot drives through is the one above the floor it stands on, so
    the multi-storey building standing next to the apartment contributes obstacles but
    not the surface the path is laid out on.
    """
    world, robot, extensions = multiple_robot_apartment_context

    action = PathPlanningNavigateAction(
        Pose.from_xyz_rpy(5, 1, 0, reference_frame=world.root)
    )
    attach_to_statechart(action, extensions)

    floor = action._floor
    assert floor in world.get_semantic_annotations_by_type(Floor)

    base_pose = robot.root.global_pose
    floor_box = floor.as_bounding_box_collection_at_origin(
        HomogeneousTransformationMatrix(reference_frame=world.root)
    ).bounding_box()
    assert floor_box.min_x <= float(base_pose.x) <= floor_box.max_x
    assert floor_box.min_y <= float(base_pose.y) <= floor_box.max_y
    assert floor_box.max_z == pytest.approx(float(base_pose.z))

    waypoints = action._waypoints()
    assert [waypoint.reference_frame for waypoint in waypoints] == [floor.root] * len(
        waypoints
    )


def test_gcs_navigation_takes_a_waypoints_height_from_that_waypoints_frame(
    multiple_robot_apartment_context,
):
    """
    A waypoint is expressed in the floor's frame, so the height the robot keeps while
    driving to it has to be read in that same frame rather than in the world's.
    """
    world, robot, extensions = multiple_robot_apartment_context

    action = PathPlanningNavigateAction(
        Pose.from_xyz_rpy(5, 1, 0, reference_frame=world.root)
    )
    attach_to_statechart(action, extensions)

    # The last pose is the requested target, which carries the caller's own height.
    for pose in action._path()[:-1]:
        base_in_pose_frame = world.transform(
            robot.root.global_transform, pose.reference_frame
        )
        assert float(pose.z) == pytest.approx(float(base_in_pose_frame.z))


def test_gcs_navigation_needs_a_floor_below_the_robot(
    multiple_robot_apartment_context,
):
    """
    Without a floor there is no surface to lay a path out on, which is a broken world
    rather than an unreachable target.
    """
    world, robot, extensions = multiple_robot_apartment_context
    robot.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -50, -50, 0
    )
    world.notify_state_change()

    action = PathPlanningNavigateAction(
        Pose.from_xyz_rpy(5, 1, 0, reference_frame=world.root)
    )

    with pytest.raises(NoFloorBelowRobot) as raised:
        attach_to_statechart(action, extensions)

    assert raised.value.robot is robot


# %% riding an elevator


@dataclass(eq=False)
class ElevatorOperator(ModelChangeCallback):
    """
    Drives an elevator to a floor as soon as a robot boards it, standing in for whatever
    operates the elevator in the real world.

    Reacting to the model change that boards the robot rather than polling for it matters
    here: the plan runs on simulated time that advances as fast as the machine allows, so
    every control cycle spent waiting is taken from the same budget the motions afterwards
    need.
    """

    elevator: Elevator = field(kw_only=True)
    """
    The elevator this operator drives.
    """

    floor: Level = field(kw_only=True)
    """
    The floor the elevator is sent to once the robot is aboard.
    """

    robot: AbstractRobot = field(kw_only=True)
    """
    The robot whose boarding sets the elevator off.
    """

    robot_boarded: bool = field(default=False, init=False)
    """
    Whether the robot was ever observed aboard the elevator.
    """

    def on_model_change(self, **kwargs):
        if self.robot.root.parent_kinematic_structure_entity is not self.elevator.root:
            return
        self.robot_boarded = True
        self.elevator.close()
        self.elevator.drive_to_floor(self.floor)
        self.elevator.open()


def test_elevator_navigation_needs_doors_that_can_open():
    world = World.create_with_root_body("root")
    with world.modify_world():
        elevator = Elevator.create_with_new_body_in_world(
            name="elevator", world=world, scale=Scale(2, 2, 2)
        )
        door = Door.create_with_new_body_in_world(
            name="door", world=world, scale=Scale(0.05, 1, 2)
        )
        elevator.add(door)
        ground_floor = GroundFloor.create_with_new_region_in_world(
            name="ground_floor", world=world, scale=Scale(4, 4, 0.1)
        )
    navigation = ElevatorNavigation(elevator, ground_floor)

    with pytest.raises(MissingMovableJointError):
        navigation._elevator_open_at_floor(ground_floor)


def test_elevator_navigation_needs_a_cabin_that_can_move():
    world = World.create_with_root_body("root")
    with world.modify_world():
        elevator = Elevator.create_with_new_body_in_world(
            name="elevator", world=world, scale=Scale(2, 2, 2)
        )
        door = Door.create_with_new_body_in_world(
            name="door",
            world=world,
            scale=Scale(0.05, 1, 2),
            parent_connection_specification=PrismaticConnectionSpecification(
                axis=Vector3.Y()
            ),
        )
        elevator.add(door)
        ground_floor = GroundFloor.create_with_new_region_in_world(
            name="ground_floor", world=world, scale=Scale(4, 4, 0.1)
        )
    navigation = ElevatorNavigation(elevator, ground_floor)

    with pytest.raises(MissingMovableJointError):
        navigation._elevator_open_at_floor(ground_floor)


def test_elevator_navigation(multiple_robot_apartment_context, rclpy_node):
    world, robot, extensions = multiple_robot_apartment_context

    elevator = world.get_semantic_annotations_by_type(Elevator)[0]
    elevator.open()

    first_floor = world.get_semantic_annotations_by_type(FirstFloor)[0]
    starting_height = float(robot.root.global_pose.position.z)
    elevator_travel = float(elevator.drive_position_for_floor(first_floor)) - float(
        elevator.movable_joint.position
    )

    operator = ElevatorOperator(
        _world=world, elevator=elevator, floor=first_floor, robot=robot
    )
    action = ElevatorNavigation(elevator, first_floor)
    plan = action

    robot.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        1, -5, 0, reference_frame=world.root
    )

    # The operator watches every model change of the shared world, so it has to stop
    # before the next test runs on it, whether or not the ride succeeds.
    try:
        run_plan(plan, extensions)
    finally:
        operator.stop()

    cabin_position = elevator.root.global_transform.position.to_np().flatten()

    # The robot ends up in front of the elevator's opening, a floor higher.
    distance_from_cabin_center = float(elevator.scale.x) / 2 + action.exit_clearance
    expected_position = (
        cabin_position[:3]
        + elevator.hole_direction.to_np().flatten()[:3]
        * -1
        * distance_from_cabin_center
    )
    expected_position[2] = starting_height + elevator_travel

    assert operator.robot_boarded
    assert robot.root.global_transform.position.to_np().flatten()[:3] == pytest.approx(
        expected_position, abs=0.01
    )


# %% searching for an object


def test_search_action(multiple_robot_apartment_context):
    """
    Searching where the object stands ends with the robot standing where it can see the
    object, having detected it on the first look.
    """
    world, robot, extensions = multiple_robot_apartment_context
    milk_body = world.get_body_by_name("milk.stl")
    # East of the multi-storey building the fixture merges in, where every robot has the
    # clearance to stand somewhere the milk is visible from.
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        6, -2, 1.2, reference_frame=world.root
    )
    search = SearchAction(milk_body.global_pose, object_semantic_annotation=Milk)

    run_plan(search, extensions)

    assert milk_body in get_visible_bodies(robot.get_default_camera())
    first_detection = next(
        node for node in search.descendants if isinstance(node, DetectAction)
    )
    assert first_detection.life_cycle_state == LifeCycleValues.SUCCEEDED


def search_target_in_front_of(robot: AbstractRobot) -> Pose:
    """
    Stands `robot` east of the multi-storey building, facing a target in front of it.

    :param robot: The robot that searches.
    :return: The target, in the world frame.
    """
    world = robot._world
    target = Pose.from_xyz_rpy(6, -2, 1.2, reference_frame=world.root)
    robot.root.parent_connection.origin = stand_facing(
        robot, (5, -2, 0), target.position.to_np(), world
    )
    world.notify_state_change()
    return target


def world_V_left_of_base(robot: AbstractRobot) -> np.ndarray:
    """
    :param robot: A robot with a mobile base.
    :return: The direction to the left of where its base faces, in the world frame.
    """
    world_R_base = robot.mobile_base.root.global_transform.rotation_matrix.to_np()
    world_V_forward = world_R_base[:3, :3] @ robot.mobile_base.forward_axis.to_np()[:3]
    return np.cross([0.0, 0.0, 1.0], world_V_forward)


def test_a_sweep_region_is_placed_at_the_target_turned_like_the_base(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    target = search_target_in_front_of(robot)
    sweep_region = SweepRegion.for_robot(robot, half_width=0.5, speed=0.5)

    run_plan(
        SweepRegionPlacement(sweep_region=sweep_region, target=target, robot=robot),
        extensions,
    )

    world_T_region = sweep_region.sweep.child.global_transform.to_np()
    np.testing.assert_allclose(
        world_T_region[:3, 3], target.position.to_np()[:3], atol=1e-6
    )
    np.testing.assert_allclose(
        world_T_region[:3, 1], world_V_left_of_base(robot), atol=1e-6
    )


def test_looking_at_a_sweep_region_slid_sideways_looks_beside_the_target(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    target = search_target_in_front_of(robot)
    sweep_region = SweepRegion.for_robot(robot, half_width=0.5, speed=0.5)
    region = sweep_region.sweep.child
    look = LookAtAction(Pose(reference_frame=region))
    slide = JointPositionList(
        goal_state=JointState.from_mapping({sweep_region.sweep: 0.5})
    )

    run_plan(
        Sequence(
            [
                SweepRegionPlacement(
                    sweep_region=sweep_region, target=target, robot=robot
                ),
                Parallel([look, slide]),
            ]
        ),
        extensions,
    )

    assert sweep_region.sweep.position == pytest.approx(0.5, abs=slide.threshold)
    world_P_aim = target.position.to_np()[:3] + 0.5 * world_V_left_of_base(robot)
    camera = robot.get_default_camera()
    world_T_camera = camera.root.global_transform.to_np()
    world_V_looking = world_T_camera[:3, :3] @ camera.forward_facing_axis.to_np()[:3]
    world_V_to_aim = world_P_aim - world_T_camera[:3, 3]
    angle = np.arccos(
        np.dot(world_V_looking, world_V_to_aim)
        / (np.linalg.norm(world_V_looking) * np.linalg.norm(world_V_to_aim))
    )
    [pointing] = nodes_of_type(look, Pointing)
    assert angle <= pointing.threshold


def test_a_search_places_its_sweep_region_and_slides_it_to_each_look(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    search = SearchAction(
        search_target_in_front_of(robot), object_semantic_annotation=Milk
    )

    expand(search, extensions)

    [placement] = nodes_of_type(search, SweepRegionPlacement)
    slides = nodes_of_type(search, JointPositionList)
    assert placement.target is search.target_location
    assert [
        target
        for slide in slides
        for connection, target in slide.goal_state.items()
        if connection is placement.sweep_region.sweep
    ] == list(search.sideways_look_offsets)


def test_the_searches_of_one_robot_share_its_sweep_region(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    target = search_target_in_front_of(robot)
    searches = [
        SearchAction(target, object_semantic_annotation=Milk),
        SearchAction(target, object_semantic_annotation=Milk),
    ]

    expand(Sequence(searches), extensions)

    [first, second] = [
        placement
        for search in searches
        for placement in nodes_of_type(search, SweepRegionPlacement)
    ]
    assert first.sweep_region == second.sweep_region


def test_a_search_removes_the_sweep_region_once_the_plan_ended(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    milk_body = world.get_body_by_name("milk.stl")
    milk_body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        6, -2, 1.2, reference_frame=world.root
    )
    search = SearchAction(milk_body.global_pose, object_semantic_annotation=Milk)

    run_plan(search, extensions)

    [placement] = nodes_of_type(search, SweepRegionPlacement)
    sweep_region = placement.sweep_region
    assert sweep_region.sweep.child not in world.kinematic_structure_entities
    assert sweep_region.placement.child not in world.kinematic_structure_entities


# %% what an action expands into


def test_move_torso_runs_the_joint_goal_of_the_requested_state(
    multiple_robot_apartment_context,
):
    """
    Moving the torso drives it to the joint state that torso state stands for.
    """
    _, robot, extensions = multiple_robot_apartment_context
    action = MoveTorsoAction(TorsoState.HIGH)

    expand(action, extensions)

    [joint_goal] = nodes_of_type(action, JointPositionList)
    assert joint_goal.goal_state == robot.get_torso().get_joint_state_by_type(
        TorsoState.HIGH
    )


def test_set_gripper_drives_the_gripper_it_names(multiple_robot_apartment_context):
    """
    Setting a gripper drives that gripper, with one goal.
    """
    _, robot, extensions = multiple_robot_apartment_context
    end_effector = left_or_only_arm(robot).end_effector
    action = SetGripperAction(end_effector, GripperState.OPEN)

    expand(action, extensions)

    [goal] = nodes_of_type(action, MoveGripper)
    assert goal.end_effector is end_effector


def test_park_arms_caps_joint_velocity_only_when_asked(
    multiple_robot_apartment_context,
):
    """
    The velocity cap is a limit run alongside the park goal, not always present.
    """
    _, robot, extensions = multiple_robot_apartment_context
    capped = ParkArmsAction(robot.all_arms, max_joint_velocity=0.1)
    uncapped = ParkArmsAction(robot.all_arms)

    expand(capped, extensions)
    expand(uncapped, extensions)

    [limit] = nodes_of_type(capped, JointVelocityLimit)
    assert limit.max_velocity == capped.max_joint_velocity
    assert nodes_of_type(capped, Parallel) != []
    assert nodes_of_type(uncapped, JointVelocityLimit) == []


def test_look_at_points_the_default_camera(multiple_robot_apartment_context):
    """
    Looking somewhere aims the robot's own camera, and runs nothing else.
    """
    _, robot, extensions = multiple_robot_apartment_context
    action = LookAtAction(Pose())

    expand(action, extensions)

    [pointing] = nodes_of_type(action, Pointing)
    assert pointing.tip_link == robot.get_default_camera().root


def test_following_a_path_runs_one_goal_per_waypoint(
    multiple_robot_apartment_context,
):
    """
    Every waypoint of the path becomes a goal of its own, in order.
    """
    _, robot, extensions = multiple_robot_apartment_context
    waypoints = [Pose(), Pose(), Pose()]
    action = FollowToolCenterPointPathAction(
        PoseTrajectory(waypoints), left_or_only_arm(robot)
    )

    expand(action, extensions)

    assert len(nodes_of_type(action, CartesianPose)) == len(waypoints)


def test_moving_the_manipulator_relaxes_collisions_only_when_allowed(
    multiple_robot_apartment_context,
):
    """
    The gripper is only let through its surroundings when the caller asks.
    """
    _, robot, extensions = multiple_robot_apartment_context
    end_effector = left_or_only_arm(robot).end_effector
    allowed = MoveManipulatorAction(Pose(), end_effector, True)
    forbidden = MoveManipulatorAction(Pose(), end_effector, False)

    expand(allowed, extensions)
    expand(forbidden, extensions)

    assert len(nodes_of_type(allowed, UpdateTemporaryCollisionRules)) == 1
    assert nodes_of_type(forbidden, UpdateTemporaryCollisionRules) == []
    assert len(nodes_of_type(forbidden, CartesianPose)) == 1


def test_navigating_drives_the_base_towards_what_it_should_face(
    multiple_robot_apartment_context,
):
    """
    Navigating commands the base pose, and runs nothing else.
    """
    _, robot, extensions = multiple_robot_apartment_context
    action = NavigateAction(Pose())

    statechart_of(robot_executor(extensions), action)

    [drive] = nodes_of_type(action, CartesianPose)
    assert drive.tip_link == robot.root


def test_navigating_writes_the_odometry_when_simulated(
    multiple_robot_apartment_context,
):
    """
    A simulated run has no drive to follow a pose, so it sets the odometry itself.
    """
    _, _, extensions = multiple_robot_apartment_context
    action = NavigateAction(Pose())

    expand(action, extensions)

    assert len(nodes_of_type(action, SetOdometry)) == 1
    assert nodes_of_type(action, CartesianPose) == []


def test_navigating_drives_the_base_when_physically_simulated(
    multiple_robot_apartment_context,
):
    """
    A robot whose wheels have to carry it cannot be put at a pose by saying so, which is
    why performing in physics is told apart from performing kinematically.
    """
    _, robot, extensions = multiple_robot_apartment_context
    action = NavigateAction(Pose())

    statechart_of(physically_simulated_executor(extensions), action)

    assert nodes_of_type(action, SetOdometry) == []
    [drive] = nodes_of_type(action, CartesianPose)
    assert drive.tip_link == robot.root


# %% a robot that does not move its whole body stands still while it moves an arm


def arm_and_look_actions(robot: AbstractRobot) -> List[Action]:
    """
    :return: One of every action that moves an arm or the head while the base is meant
        to stand.
    """
    arm = left_or_only_arm(robot)
    return [
        MoveManipulatorAction(Pose(), arm.end_effector, False),
        FollowToolCenterPointPathAction(PoseTrajectory([Pose()]), arm),
        LookAtAction(Pose()),
    ]


def test_moving_an_arm_or_looking_holds_the_base_of_a_robot_that_stands_still(
    multiple_robot_apartment_context,
):
    """
    A goal relative to the robot is bound when it starts, so a base that collision
    avoidance pushes afterwards carries the goal away from its target.
    """
    world, robot, extensions = multiple_robot_apartment_context
    with world.modify_world():
        robot.mobile_base.full_body_controlled = False

    for action in arm_and_look_actions(robot):
        expand(action, extensions)

        [hold_base] = nodes_of_type(action, HoldPose)
        assert hold_base.root_link == world.root
        assert hold_base.tip_link == robot.root
        assert hold_base.weight == DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE


def test_moving_an_arm_or_looking_leaves_a_full_body_controlled_base_free(
    multiple_robot_apartment_context,
):
    """
    A robot that may move its whole body drives while it reaches, so its base is not
    held.
    """
    world, robot, extensions = multiple_robot_apartment_context
    with world.modify_world():
        robot.mobile_base.full_body_controlled = True

    for action in arm_and_look_actions(robot):
        expand(action, extensions)

        assert nodes_of_type(action, HoldPose) == []


# %% sending the fingers to a width


def test_fingers_sent_to_a_width_are_given_the_distance_between_their_facing_points(
    multiple_robot_apartment_context,
):
    """
    The distance between the fingertips is what Giskard is given, so it finds the joint
    positions that realise it rather than being told them.
    """
    _, robot, extensions = multiple_robot_apartment_context
    gripper = left_or_only_arm(robot).end_effector
    action = MoveFingersToWidthAction(gripper=gripper, width=0.04)

    statechart_of(physically_simulated_executor(extensions), action)

    goal = action.action_body
    assert isinstance(goal, DistanceAlongAxis)
    assert goal.reference_point.reference_frame is gripper.finger.tip
    assert goal.tip_point.reference_frame is gripper.thumb.tip
    assert goal.distance == action.width


def test_a_squeeze_sends_the_fingers_past_the_width(multiple_robot_apartment_context):
    _, robot, extensions = multiple_robot_apartment_context
    gripper = left_or_only_arm(robot).end_effector
    width = 0.04
    squeeze = 0.001
    touching = MoveFingersToWidthAction(gripper=gripper, width=width)
    pressing = MoveFingersToWidthAction(gripper=gripper, width=width, squeeze=squeeze)

    statechart_of(physically_simulated_executor(extensions), touching)
    statechart_of(physically_simulated_executor(extensions), pressing)

    assert pressing.action_body.distance == pytest.approx(
        touching.action_body.distance - 2 * squeeze
    )


def test_fingers_sent_to_a_width_stand_that_far_apart(
    multiple_robot_apartment_context,
):
    """
    The fingertips end up the width apart, whether the fingers slide or swing on hinges.
    """
    _, robot, extensions = multiple_robot_apartment_context
    gripper = left_or_only_arm(robot).end_effector
    action = MoveFingersToWidthAction(gripper=gripper, width=0.04)

    run_plan(action, extensions)

    assert gripper.fingertips.separation == pytest.approx(
        action.width, abs=action.threshold
    )


def test_fingers_are_not_sent_wider_than_their_gripper_opens(
    multiple_robot_apartment_context,
):
    _, robot, extensions = multiple_robot_apartment_context
    gripper = left_or_only_arm(robot).end_effector
    action = MoveFingersToWidthAction(
        gripper=gripper, width=gripper.separation_when_open + 0.01
    )

    with pytest.raises(WidthBeyondGripperOpening):
        statechart_of(physically_simulated_executor(extensions), action)


def test_fingers_may_be_sent_as_wide_as_their_gripper_opens(
    multiple_robot_apartment_context,
):
    _, robot, extensions = multiple_robot_apartment_context
    gripper = left_or_only_arm(robot).end_effector
    action = MoveFingersToWidthAction(
        gripper=gripper, width=gripper.separation_when_open
    )

    statechart_of(physically_simulated_executor(extensions), action)

    assert isinstance(action.action_body, DistanceAlongAxis)


# %% what holds a picked object


def branch_moves_of(nodes: List[StatechartNode]) -> List[MoveBranch]:
    """
    :return: The nodes among `nodes` that move a body under a new parent.
    """
    return [node for node in nodes if isinstance(node, MoveBranch)]


def test_a_kinematically_simulated_pick_is_held_by_the_world(
    multiple_robot_apartment_context,
):
    """
    Nothing in a world moved kinematically holds an object, so the object is put under
    the gripper for it to be held at all.
    """
    world, robot, extensions = multiple_robot_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    arm = right_or_only_arm(robot)
    pick_up = PickUpAction(milk.grasp_candidates()[0], arm)

    [attaching] = branch_moves_of(motion_nodes_of(pick_up, extensions))

    assert attaching.body is milk.root
    assert attaching.new_parent is arm.end_effector.tool_frame


def test_a_physically_simulated_pick_is_held_by_its_own_grip(
    multiple_robot_apartment_context,
):
    """
    The pads hold the object in physics, so putting it under the gripper as well would
    hold it whether or not the grasp did.
    """
    world, robot, extensions = multiple_robot_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(milk.grasp_candidates()[0], right_or_only_arm(robot))

    assert branch_moves_of(motion_nodes_in_physics_of(pick_up, extensions)) == []


def test_a_physically_simulated_place_is_released_by_its_own_grip(
    multiple_robot_apartment_context,
):
    """
    Releasing is the same move the other way, and in physics the pads opening is what
    lets the object go, so the model is left alone here too.
    """
    world, robot, extensions = multiple_robot_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan = Sequence(
        [
            PickUpAction(milk.grasp_candidates()[0], right_or_only_arm(robot)),
            PlaceAction(milk, Pose.from_xyz_rpy(1, 1, 0.8, reference_frame=world.root)),
        ]
    )

    assert branch_moves_of(motion_nodes_in_physics_of(plan, extensions)) == []


# %% cups to pick up and carry


def add_cup(
    world: World, name: str, world_T_cup: HomogeneousTransformationMatrix
) -> Cup:
    """
    :param world: The world the cup is added to.
    :param name: The name of the body of the cup.
    :param world_T_cup: Where the cup hovers.
    :return: The annotation of a cup fixed to the root of `world`.
    """
    shapes = ShapeCollection([Cylinder(width=0.08, height=0.07)])
    body = Body(name=PrefixedName(name), collision=shapes, visual=shapes)
    cup = Cup(root=body)
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=body,
                parent_T_connection_expression=world_T_cup,
            )
        )
        world.add_semantic_annotation(cup)
    return cup


def cup_in_reach(robot: AbstractRobot, name: str, roll: float = 0.0) -> Cup:
    """
    Stands `robot` facing along the world's x-axis, with a new cup ahead of it and to
    its left.

    :param robot: The robot that is to reach the cup.
    :param name: The name of the body of the cup.
    :param roll: How far the cup is tilted about the world's x-axis.
    :return: The cup.
    """
    world = robot._world
    cup = add_cup(
        world,
        name,
        HomogeneousTransformationMatrix.from_xyz_rpy(
            1, -2, 0.8, roll=roll, reference_frame=world.root
        ),
    )
    robot.root.parent_connection.origin = stand_facing(
        robot, (0.3, -2.3, 0), (1.3, -2.3, 0), world
    )
    world.notify_state_change()
    return cup


def test_a_pick_up_from_above_comes_down_onto_the_objects_origin(
    multiple_robot_apartment_context,
):
    world, robot, extensions = multiple_robot_apartment_context
    cup = cup_in_reach(robot, "cup")
    arm = left_or_only_arm(robot)

    pick_up = PickUpAction.from_above(cup, arm)

    cup_T_grasp = pick_up.grasp.grasp_pose
    assert pick_up.grasp.graspable is cup
    assert pick_up.arm is arm
    assert cup_T_grasp.reference_frame is cup.root
    np.testing.assert_allclose(cup_T_grasp.position.to_np()[:3], [0, 0, 0])
    np.testing.assert_allclose(
        cup_T_grasp.rotation_matrix.to_np()[:3, 0], [0, 0, -1], atol=1e-9
    )


# %% carrying held objects upright


def tilt_from_upright(body: Body) -> float:
    """
    :param body: The body to measure.
    :return: The angle in radians between the z-axis of `body` and the world's z-axis.
    """
    up_in_world = body.global_pose.to_np()[:3, 2]
    return float(np.arccos(np.clip(up_in_world[2], -1.0, 1.0)))


def cup_held_tilted(robot: AbstractRobot) -> Cup:
    """
    :param robot: The robot that holds the cup.
    :return: A cup fixed below the tool frame of the left or only gripper of `robot`,
        its z-axis tilted away from the world's z-axis.
    """
    world = robot._world
    tool_frame = left_or_only_arm(robot).end_effector.tool_frame
    shapes = ShapeCollection([Cylinder(width=0.08, height=0.07)])
    body = Body(name=PrefixedName("held_cup"), collision=shapes, visual=shapes)
    cup = Cup(root=body)
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection(
                parent=tool_frame,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    roll=0.4, pitch=0.3, reference_frame=tool_frame
                ),
            )
        )
        world.add_semantic_annotation(cup)
    return cup


def drive_ahead(robot: AbstractRobot) -> NavigateAction:
    """
    :param robot: The robot that drives.
    :return: The drive moving `robot` a short way.
    """
    return NavigateAction(Pose.from_xyz_rpy(x=0.3, reference_frame=robot.root))


def test_a_tilted_cup_in_a_gripper_ends_upright(multiple_robot_apartment_context):
    _, robot, extensions = multiple_robot_apartment_context
    cup = cup_held_tilted(robot)
    carry = CarryAction(drive_ahead(robot))

    run_plan(carry, extensions)

    assert tilt_from_upright(cup.root) <= carry.upright_threshold


def test_a_cup_picked_up_earlier_in_the_plan_ends_upright(
    multiple_robot_apartment_context,
):
    _, robot, extensions = multiple_robot_apartment_context
    cup = cup_in_reach(robot, "tilted_cup", roll=0.3)
    carry = CarryAction(drive_ahead(robot))

    run_plan(
        Sequence([PickUpAction.from_above(cup, left_or_only_arm(robot)), carry]),
        [*extensions, PlanRewriting(transformations=[ParkArmsBeforeFirstAction()])],
    )

    # The cup is held with the orientation error the gripper reached its grasp with.
    assert (
        tilt_from_upright(cup.root)
        <= carry.upright_threshold + MotionToleranceConfig().tool_orientation_threshold
    )


def test_a_robot_holding_nothing_only_drives(multiple_robot_apartment_context):
    _, robot, extensions = multiple_robot_apartment_context
    carry = CarryAction(drive_ahead(robot))

    expand(carry, extensions)

    assert carry.action_body is carry.navigate


def test_a_cup_put_down_earlier_in_the_plan_is_not_carried(
    multiple_robot_apartment_context,
):
    _, robot, extensions = multiple_robot_apartment_context
    cup = cup_in_reach(robot, "cup")
    carry = CarryAction(drive_ahead(robot))

    expand(
        Sequence(
            [
                PickUpAction.from_above(cup, left_or_only_arm(robot)),
                PlaceAction(cup, Pose.from_xyz_rpy(y=0.1, reference_frame=cup.root)),
                carry,
            ]
        ),
        extensions,
    )

    assert carry.action_body is carry.navigate


def test_a_placing_carries_its_object_to_where_it_stands(
    multiple_robot_apartment_context,
):
    _, robot, extensions = multiple_robot_apartment_context
    cup = cup_held_tilted(robot)
    target = Pose.from_xyz_rpy(x=0.8, z=0.8, reference_frame=robot.root)
    move_and_place = MoveAndPlaceAction(
        navigate=drive_ahead(robot),
        face_and_look_at=FaceAndLookAtAction(
            face_at=FaceAtAction(target), look_at=LookAtAction(target)
        ),
        place=PlaceAction(cup, target),
    )

    expand(move_and_place, extensions)

    carry = move_and_place.action_body.nodes[0]
    assert isinstance(carry, CarryAction)
    assert carry.navigate is move_and_place.navigate


# %% both arms handling objects at once


@dataclass
class CupForEachArm:
    """
    A two-armed robot whose base moves with its arms, with one cup for each arm to pick
    up.
    """

    world: World
    """
    The world holding the robot and the cups.
    """

    context_extensions: List[ContextExtension]
    """
    The context extensions the plans of the robot read.
    """

    pick_ups: List[PickUpAction]
    """
    The pick-up of each cup, the nearer cup with the left arm and the farther one with
    the right arm.
    """

    def extensions_parking_first(self) -> List[ContextExtension]:
        """
        :return: The context extensions of the plans of the robot, parking its arms
            before the first action of a plan.
        """
        return [
            *self.context_extensions,
            PlanRewriting(transformations=[ParkArmsBeforeFirstAction()]),
        ]

    def places(self) -> List[PlaceAction]:
        """
        :return: The actions that set each cup down to the side of where it is now, the
            first far away and the second close by, so that one gripper opens while the
            other arm is still on its way.
        """
        return [
            PlaceAction(
                pick_up.grasp.graspable,
                self.world.transform(
                    Pose.from_xyz_rpy(
                        y=sideways_distance,
                        reference_frame=pick_up.grasp.graspable.root,
                    ),
                    self.world.root,
                ),
            )
            for pick_up, sideways_distance in zip(self.pick_ups, [0.3, -0.02])
        ]


@pytest.fixture
def cup_for_each_arm(multiple_robot_apartment_context) -> CupForEachArm:
    world, robot, extensions = multiple_robot_apartment_context
    left_arm = robot.get_left_arm_if_specified()
    right_arm = robot.get_right_arm_if_specified()
    if left_arm is None or right_arm is None:
        pytest.skip(f"{type(robot).__name__} has no left and right arm")
    robot.mobile_base.full_body_controlled = True
    robot.root.parent_connection.origin = stand_facing(
        robot, (0.3, -2, 0), (1.3, -2, 0), world
    )
    world.notify_state_change()
    # The cups are out of reach and at different distances, so the base has to move
    # and one arm is done before the other.
    near_cup = add_cup(
        world,
        "near_cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.2, y=-1.8, z=0.8, reference_frame=world.root
        ),
    )
    far_cup = add_cup(
        world,
        "far_cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.5, y=-2.2, z=0.8, reference_frame=world.root
        ),
    )
    return CupForEachArm(
        world=world,
        context_extensions=extensions,
        pick_ups=[
            PickUpAction.from_above(near_cup, left_arm),
            PickUpAction.from_above(far_cup, right_arm),
        ],
    )


def test_a_gripper_closes_at_its_grasp_although_the_other_arm_is_moving(
    cup_for_each_arm: CupForEachArm,
):
    run_plan(
        Parallel(cup_for_each_arm.pick_ups),
        cup_for_each_arm.extensions_parking_first(),
    )

    world = cup_for_each_arm.world
    for pick_up in cup_for_each_arm.pick_ups:
        # A goal puts the point the fingers meet at on the grasp, not the tool frame.
        np.testing.assert_allclose(
            grasp_point_of(pick_up.arm),
            world.transform(pick_up.grasp.grasp_pose, world.root)
            .position.to_np()
            .flatten()[:3],
            atol=MotionToleranceConfig().default_tcp_position_threshold,
        )


def test_a_gripper_opens_at_its_place_target_although_the_other_arm_is_moving(
    cup_for_each_arm: CupForEachArm,
):
    # One after the other, so that both cups sit in their grippers at their grasps.
    run_plan(
        Sequence(cup_for_each_arm.pick_ups),
        cup_for_each_arm.extensions_parking_first(),
    )
    places = cup_for_each_arm.places()

    run_plan(Parallel(places), cup_for_each_arm.context_extensions)

    for place in places:
        np.testing.assert_allclose(
            place.object_designator.root.global_pose.position.to_np()[:3],
            place.target_location.position.to_np()[:3],
            atol=2 * MotionToleranceConfig().default_tcp_position_threshold,
        )
