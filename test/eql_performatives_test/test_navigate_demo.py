"""
Demo: a real robot plan, re-expressed as verbalizable speech acts composed across frameworks.

Two real coraplex actions (``NavigateAction``, ``MoveTorsoAction``) as *Perform* acts, with a real
semantic_digital_twin predicate (``is_pose_free_for_robot``) watched by a *Monitor*, all composed under one
krrood ``Sequential`` -- the payoff of the performative layer: one description language, one composition
language, one verbalization, across planning / perception / motion frameworks.

Uses existing predicates and actions so the demo reads as a real plan. Runs in the lean container (builds
and verbalizes the plan without ROS); executing the motion is the ROS-CI step.
"""

from __future__ import annotations

from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.reasoning.robot_predicates import is_pose_free_for_robot
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose

from krrood.entity_query_language.factories import a, variable
from krrood.entity_query_language.performatives import Perform, Sequential
from giskardpy.eql.performatives import Monitor


def _navigate_and_raise_torso() -> Sequential:
    robot = variable(AbstractRobot, [])
    target = variable(Pose, [])   # the target is a bound pose, shared across the navigate and the monitor
    return Sequential(
        [
            Perform(a(NavigateAction)(target_location=target)),
            Monitor(is_pose_free_for_robot(robot, target)),
            Perform(a(MoveTorsoAction)(torso_state=TorsoState.HIGH)),
        ]
    )


def test_the_plan_composes_real_actions_a_predicate_monitor_across_frameworks():
    # Perform (coraplex actions) verbalizes in the imperative register ("such that"); the sdt
    # SymbolicFunction predicate is_pose_free_for_robot -> Monitor, reading as a clean clause; and the pose
    # shared between the navigate and the monitor corefers ("a Pose" then "the Pose").
    assert _navigate_and_raise_torso().verbalize() == (
        "Perform a NavigateAction such that its target_location is a Pose, "
        "then Monitor whether the Pose is free for an AbstractRobot, "
        "then Perform a MoveTorsoAction such that its torso_state is HIGH"
    )


def test_each_step_uses_the_act_that_fits_it():
    robot = variable(AbstractRobot, [])
    target = Pose()
    assert Perform(a(NavigateAction)(target_location=target)).verbalize().startswith(
        "Perform a NavigateAction"
    )
    assert Monitor(is_pose_free_for_robot(robot, target)).verbalize().startswith(
        "Monitor whether "
    )
