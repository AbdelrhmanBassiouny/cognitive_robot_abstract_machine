"""
Tests for compiling and executing a plan with a
:class:`~coraplex.plans.executors.PlanExecutor`.
"""

from dataclasses import dataclass
from datetime import timedelta

import pytest

from cramph.exceptions import EmptyStatechartError

from coraplex.exceptions import (
    MotionDidNotFinish,
    PlanNotCompiled,
)
from coraplex.plans.executors import (
    RealRobotPlanExecutor,
    SimulatedPlanExecutor,
)
from coraplex.plans.failures import (
    MotionExceededSimulationTimeLimit,
    MotionMadeNoProgress,
    MotionViolatedCollisionAvoidance,
)
from coraplex.robot_plans.actions.core.pick_up import ReachAction
from coraplex.robot_plans.actions.core.robot_body import (
    MoveTorsoAction,
    ParkArmsAction,
)
from cramph.exceptions import StatechartOfDifferentContextError
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.executor import Pacer, StatechartExecutor
from cramph.node import CancelStatechart
from cramph.nodes_for_testing import NodeFailingOnObservingFalse
from giskardpy.motion_statechart.exceptions import CollisionViolatedError
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.monitors.progress_monitors import StillProgressing
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.pr2 import PR2Joint
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from ...plan_running import simulated_executor, statechart_of

# %% counting the waits between ticks


@dataclass
class WaitCountingPacer(Pacer):
    """
    Counts how often a loop waited for its next cycle, without waiting.
    """

    wait_count: int = 0
    """
    How often the loop waited so far.
    """

    def sleep(self) -> None:
        self.wait_count += 1


# %% compiling


def test_compiling_puts_the_plan_and_its_end_in_one_statechart(
    pr2_apartment_context,
):
    world, robot_view, extensions = pr2_apartment_context
    plan = MoveTorsoAction(TorsoState.HIGH)
    executor = simulated_executor(extensions)

    executor.compile(statechart_of(executor, plan))

    statechart = plan.statechart
    assert plan in statechart.top_level_nodes
    assert len(statechart.get_nodes_by_type(EndMotion)) == 1


def test_executing_before_compiling_is_refused(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context

    with pytest.raises(PlanNotCompiled):
        simulated_executor(extensions).execute()


# %% executing


def test_executing_runs_the_plan_until_it_succeeded(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context
    plan = MoveTorsoAction(TorsoState.HIGH)
    executor = simulated_executor(extensions)

    executor.compile(statechart_of(executor, plan))
    executor.execute()

    assert plan.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_plan_that_fails_raises_motion_did_not_finish(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context
    plan = NodeFailingOnObservingFalse(observation=ObservationStateValues.FALSE)
    executor = simulated_executor(extensions)

    with pytest.raises(MotionDidNotFinish):
        executor.compile(statechart_of(executor, plan))
        executor.execute()


def test_preparing_a_plan_does_not_move_the_robot(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context
    torso = world.get_degree_of_freedom_by_name(PR2Joint.TORSO_LIFT).id
    position_before = world.state[torso].position
    executor = simulated_executor(extensions)

    executor.prepare(statechart_of(executor, MoveTorsoAction(TorsoState.HIGH)))

    assert world.state[torso].position == position_before


def test_a_plan_of_several_top_level_nodes_ends_once_all_of_them_succeeded(
    pr2_apartment_context,
):
    """
    A statechart has no root node, so every node the caller puts at its top level is
    part of the plan.
    """
    world, robot_view, extensions = pr2_apartment_context
    torso = MoveTorsoAction(TorsoState.HIGH)
    arms = ParkArmsAction(robot_view.all_arms)
    executor = simulated_executor(extensions)

    executor.compile(statechart_of(executor, torso, arms))
    executor.execute()

    assert executor.plan_nodes == [torso, arms]
    assert torso.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert arms.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_statechart_without_a_plan_is_refused(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context
    executor = simulated_executor(extensions)

    with pytest.raises(EmptyStatechartError):
        executor.compile(statechart_of(executor))


def test_a_statechart_of_another_context_is_refused(pr2_apartment_context):
    world, robot_view, extensions = pr2_apartment_context
    statechart = statechart_of(
        simulated_executor(extensions), MoveTorsoAction(TorsoState.HIGH)
    )

    with pytest.raises(StatechartOfDifferentContextError):
        simulated_executor(extensions).compile(statechart)


@pytest.mark.parametrize(
    "executor_type, drives_a_simulated_robot",
    [(SimulatedPlanExecutor, True), (RealRobotPlanExecutor, False)],
)
def test_an_executor_says_whether_it_drives_a_simulated_robot(
    executor_type, drives_a_simulated_robot
):
    assert executor_type.simulated is drives_a_simulated_robot


# %% how long a plan may take


def test_compiling_watches_the_plan_for_progress(pr2_apartment_context):
    """
    A stalled run has to end by itself, so the statechart carries a monitor watching the
    plan and an abort path wired to it.
    """
    world, robot_view, extensions = pr2_apartment_context
    plan = MoveTorsoAction(TorsoState.HIGH)
    executor = simulated_executor(extensions)

    executor.compile(statechart_of(executor, plan))

    [progress_monitor] = plan.statechart.get_nodes_by_type(StillProgressing)
    assert progress_monitor.monitored_node is plan
    assert len(plan.statechart.get_nodes_by_type(CancelStatechart)) == 1


def test_a_plan_that_stops_approaching_its_goal_is_given_up_on(
    pr2_apartment_context,
):
    """
    Nothing bounds the tick loop but the monitor, so a reach the arm cannot close on has
    to end the run rather than tick forever.
    """
    world, robot_view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    milk.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        2, 1.5, 50, reference_frame=milk.root.parent_connection.parent
    )
    plan = ReachAction(
        grasp=GraspCandidate.from_body_origin(milk), arm=robot_view.right_arm
    )
    executor = simulated_executor(extensions)

    with pytest.raises(MotionMadeNoProgress):
        executor.compile(statechart_of(executor, plan))
        executor.execute()


def test_a_plan_that_outlasts_the_simulation_time_limit_is_given_up_on(
    pr2_apartment_context,
):
    """
    A simulated plan is given up on once it exceeds the simulation time limit.
    """
    world, robot_view, extensions = pr2_apartment_context
    executor = simulated_executor(extensions, simulation_time_limit=timedelta(0))

    with pytest.raises(MotionExceededSimulationTimeLimit):
        executor.compile(statechart_of(executor, MoveTorsoAction(TorsoState.HIGH)))
        executor.execute()


def test_a_plan_is_given_up_on_at_the_simulation_time_limit_of_its_own_executor(
    pr2_apartment_context,
):
    world, robot_view, extensions = pr2_apartment_context
    executor = simulated_executor(
        extensions, simulation_time_limit=timedelta(milliseconds=100)
    )

    with pytest.raises(MotionExceededSimulationTimeLimit) as error:
        executor.compile(statechart_of(executor, MoveTorsoAction(TorsoState.HIGH)))
        executor.execute()

    assert error.value.time_limit == executor.simulation_time_limit


def test_a_simulated_plan_waits_for_its_pacer_after_every_tick(
    pr2_apartment_context,
):
    world, robot_view, extensions = pr2_apartment_context
    pacer = WaitCountingPacer()
    executor = simulated_executor(extensions, pacer=pacer)

    executor.compile(statechart_of(executor, MoveTorsoAction(TorsoState.HIGH)))
    executor.execute()

    assert pacer.wait_count == executor.tick_count


def test_a_plan_that_violates_collision_avoidance_fails_as_a_plan_failure(
    pr2_apartment_context, monkeypatch
):
    """
    A plan that brings the robot closer to something than collision avoidance allows did
    not work from where it started, so a surrounding plan can try another candidate
    instead of stopping.
    """
    world, robot_view, extensions = pr2_apartment_context
    violation = CollisionViolatedError(violated_collisions=[], thresholds=[])

    def violate_collision_avoidance(executor: StatechartExecutor) -> None:
        raise violation

    executor = simulated_executor(extensions)
    executor.compile(statechart_of(executor, MoveTorsoAction(TorsoState.HIGH)))
    monkeypatch.setattr(StatechartExecutor, "tick", violate_collision_avoidance)
    with pytest.raises(MotionViolatedCollisionAvoidance) as failure:
        executor.execute()

    assert failure.value.violation is violation
