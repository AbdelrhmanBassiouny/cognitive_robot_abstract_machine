import numpy as np

from cramph.composites import Parallel
from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor
from cramph.statechart import Statechart
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointVelocityLimit,
)
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionForEndEffector,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.world import World

from ..motion_control_context import create_context_with_motion_control

# %% reading the gripper out of a world


def _left_gripper(world: World) -> EndEffector:
    """
    :return: The end effector of the left arm of the robot in ``world``.
    """
    return world.get_semantic_annotations_by_type(PR2)[0].left_arm.end_effector


def _expanded_nodes(goal: MoveGripper, world: World):
    """
    :return: The children the goal is made of, once it joined a statechart.
    """
    Statechart(context=create_context_with_motion_control(world)).add_node(goal)
    return goal.nodes


def _descendants(nodes):
    """
    :return: ``nodes`` and, recursively, the nodes any composite among them holds.
    """
    found = []
    for node in nodes:
        found.append(node)
        if isinstance(node, Parallel):
            found.extend(_descendants(node.nodes))
    return found


# %% commanding the fingers


def test_gripper_commands_the_state_the_end_effector_defines(pr2_world_copy):
    """
    The joint goal is the end effector's own joint state for the commanded gripper
    state, not a separately spelled out set of finger positions.
    """
    end_effector = _left_gripper(pr2_world_copy)
    goal = MoveGripper(end_effector=end_effector, state=GripperState.CLOSE)

    nodes = _expanded_nodes(goal, pr2_world_copy)

    joint_goal = next(node for node in nodes if isinstance(node, JointPositionList))
    assert joint_goal.goal_state == end_effector.get_joint_state_by_type(
        GripperState.CLOSE
    )


def test_gripper_commands_nothing_besides_the_fingers_by_default(pr2_world_copy):
    """
    A caller that asks for nothing in particular gets the joint goal alone: no speed
    cap, no stall alternative and no collision allowance.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy), state=GripperState.OPEN
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    assert [type(node) for node in nodes] == [JointPositionList]


# %% settling for stalled fingers


def test_gripper_without_stall_tolerance_only_ends_on_the_joint_goal(pr2_world_copy):
    """
    Stall tolerance is off unless asked for, so nothing watches the fingers for standing
    still.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy), state=GripperState.CLOSE
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    assert not any(isinstance(node, LocalMinimumReached) for node in nodes)


def test_gripper_tolerating_stall_settles_for_either_outcome(pr2_world_copy):
    """
    Fingers that close on an object stop short of their commanded position, so with
    stall tolerance the joint goal and the stall monitor sit under one goal that either
    of them can satisfy.
    """
    end_effector = _left_gripper(pr2_world_copy)
    goal = MoveGripper(
        end_effector=end_effector, state=GripperState.CLOSE, tolerate_stall=True
    )

    nodes = _expanded_nodes(goal, pr2_world_copy)

    alternative = next(node for node in nodes if isinstance(node, Parallel))
    assert alternative.minimum_success == 1
    assert {type(node) for node in alternative.nodes} == {
        JointPositionList,
        LocalMinimumReached,
    }


def test_gripper_watches_only_the_fingers_for_stalling(pr2_world_copy):
    """
    The stall monitor judges the fingers, not the whole robot, so the rest of the body
    moving cannot keep it from reporting settled fingers.
    """
    end_effector = _left_gripper(pr2_world_copy)
    goal = MoveGripper(
        end_effector=end_effector, state=GripperState.CLOSE, tolerate_stall=True
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    monitor = next(node for node in nodes if isinstance(node, LocalMinimumReached))
    goal_state = end_effector.get_joint_state_by_type(GripperState.CLOSE)
    assert monitor.degrees_of_freedom == [
        connection.raw_dof for connection in goal_state.connections
    ]
    assert monitor.measure_from_own_start


def test_gripper_keeps_the_monitors_dwell_time_when_none_is_given(pr2_world_copy):
    """
    Leaving the dwell time unset keeps whatever the monitor itself defaults to, so the
    default lives in one place.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy),
        state=GripperState.CLOSE,
        tolerate_stall=True,
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    monitor = next(node for node in nodes if isinstance(node, LocalMinimumReached))
    assert monitor.minimum_time == LocalMinimumReached.minimum_time


def test_gripper_dwells_as_long_as_asked_before_accepting_a_stall(pr2_world_copy):
    """
    A caller that wants the fingers to stand still longer before the stall counts gets
    that time on the monitor.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy),
        state=GripperState.CLOSE,
        tolerate_stall=True,
        stall_minimum_time=2.5,
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    monitor = next(node for node in nodes if isinstance(node, LocalMinimumReached))
    assert monitor.minimum_time == 2.5


# %% capping the finger speed


def test_gripper_speed_cap_limits_the_finger_joints(pr2_world_copy):
    """
    A finger speed applies to the joints the goal commands, and to no others.
    """
    end_effector = _left_gripper(pr2_world_copy)
    goal = MoveGripper(
        end_effector=end_effector, state=GripperState.CLOSE, finger_velocity=0.01
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    limit = next(node for node in nodes if isinstance(node, JointVelocityLimit))
    goal_state = end_effector.get_joint_state_by_type(GripperState.CLOSE)
    assert limit.max_velocity == 0.01
    assert limit.connections == list(goal_state.connections)


def test_gripper_speed_cap_holds_whichever_way_the_goal_ends(pr2_world_copy):
    """
    The stall alternative decides when the goal is done; the speed cap is not one of the
    things that can satisfy it, so it stays outside that alternative and keeps holding
    while the fingers move.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy),
        state=GripperState.CLOSE,
        tolerate_stall=True,
        finger_velocity=0.01,
    )

    nodes = _expanded_nodes(goal, pr2_world_copy)

    alternative = next(node for node in nodes if isinstance(node, Parallel))
    assert not any(isinstance(node, JointVelocityLimit) for node in alternative.nodes)
    assert any(isinstance(node, JointVelocityLimit) for node in nodes)


# %% letting the gripper touch things


def test_gripper_may_touch_what_it_grasps_when_asked(pr2_world_copy):
    """
    Closing on an object means touching it, so the goal can free its own end effector
    from collision avoidance.
    """
    end_effector = _left_gripper(pr2_world_copy)
    goal = MoveGripper(
        end_effector=end_effector,
        state=GripperState.CLOSE,
        allow_gripper_collision=True,
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    rules_node = next(
        node for node in nodes if isinstance(node, UpdateTemporaryCollisionRules)
    )
    assert [type(rule) for rule in rules_node.temporary_rules] == [
        AllowCollisionForEndEffector
    ]
    assert rules_node.temporary_rules[0].end_effector is end_effector


def test_gripper_keeps_clear_of_its_surroundings_by_default(pr2_world_copy):
    """
    Without being asked, the goal leaves collision avoidance alone.
    """
    goal = MoveGripper(
        end_effector=_left_gripper(pr2_world_copy), state=GripperState.CLOSE
    )

    nodes = _descendants(_expanded_nodes(goal, pr2_world_copy))

    assert not any(isinstance(node, UpdateTemporaryCollisionRules) for node in nodes)


# %% running it


def test_gripper_reaches_the_commanded_state(pr2_world_state_reset):
    """
    Ticking the goal drives the fingers to the positions the commanded state holds.
    """
    world = pr2_world_state_reset
    end_effector = _left_gripper(world)
    goal_state = end_effector.get_joint_state_by_type(GripperState.OPEN)
    goal = MoveGripper(end_effector=end_effector, state=GripperState.OPEN)

    executor = StatechartExecutor(
        context=StatechartContext(world=world), extensions=[MotionControl()]
    )
    statechart = Statechart(context=executor.context)
    statechart.add_node(goal)
    statechart.add_node(EndMotion.when_true(goal))

    executor.compile(statechart)
    executor.tick_until_end(timeout=500)

    reached = [connection.position for connection in goal_state.connections]
    np.testing.assert_allclose(reached, goal_state.target_values, atol=1e-3)
