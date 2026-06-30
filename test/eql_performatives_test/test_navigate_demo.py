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

from krrood.entity_query_language.factories import match, variable
from krrood.entity_query_language.performatives import Parallel, Sequential
from giskardpy.eql.performatives import Monitor
from coraplex.eql.performatives import Perform


def _navigate_and_raise_torso() -> Sequential:
    robot = variable(AbstractRobot, [])
    target = variable(Pose, [])   # the target is a bound pose, shared across the navigate and the monitor
    return Sequential(
        [
            Parallel(
                [
                    Perform(match(NavigateAction)(target_location=target)),
                    Monitor(is_pose_free_for_robot(robot, target)),
                ]
            ),
            Perform(match(MoveTorsoAction)(torso_state=TorsoState.HIGH)),
        ]
    )


def test_actions_verbalize_as_their_own_verb_phrases():
    # Each action is Verbalizable, so it states itself as an imperative verb phrase (NavigateAction ->
    # "navigate to …", MoveTorsoAction -> "move the torso to a … state"); the navigate and the monitor
    # run in parallel ("… while simultaneously monitoring …"); the shared pose corefers ("a Pose" / "the
    # Pose").
    assert _navigate_and_raise_torso().verbalize() == (
        "Navigate to a Pose, "
        "while simultaneously monitoring whether the Pose is free for an AbstractRobot, "
        "then move the torso to a high state"
    )
    assert "NavigateAction" not in _navigate_and_raise_torso().verbalize()


def test_each_step_uses_the_act_that_fits_it():
    robot = variable(AbstractRobot, [])
    target = variable(Pose, [])
    # the performed action states itself as an imperative verb phrase, not "Perform a NavigateAction"
    assert Perform(match(NavigateAction)(target_location=target)).verbalize().startswith(
        "Navigate"
    )
    assert Monitor(is_pose_free_for_robot(robot, target)).verbalize().startswith(
        "Monitor whether "
    )
