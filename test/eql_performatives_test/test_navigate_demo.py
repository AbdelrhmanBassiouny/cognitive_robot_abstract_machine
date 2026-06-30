"""
Demo: a real robot plan that is one tree -- executable *and* verbalizable -- composed across frameworks.

Two real coraplex actions (``NavigateAction``, ``MoveTorsoAction``) and a real semantic_digital_twin
predicate (``is_pose_free_for_robot``) watched by a giskardpy ``Monitor``, composed with coraplex's own
plan combinators (``sequential`` / ``parallel``). Each plan node is a krrood ``Performable``, so the *same*
tree the plan layer executes also verbalizes -- through the shared verbalization shapes, not a second
verbalizer. The payoff of the unified performative layer: one description language, one composition
language, one verbalization, across planning / perception / motion.

Runs in the lean container (builds and verbalizes the plan without ROS); executing the motion is the
ROS-CI step.
"""

from __future__ import annotations

from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.reasoning.robot_predicates import is_pose_free_for_robot
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose

from krrood.entity_query_language.factories import a, variable
from giskardpy.eql.performatives import Monitor
from coraplex.plans.factories import make_node, parallel, sequential
from coraplex.plans.plan_node import PlanNode


def _navigate_and_raise_torso() -> PlanNode:
    robot = variable(AbstractRobot, [])
    target = variable(Pose, [])   # the target is a bound pose, shared across the navigate and the monitor
    return sequential(
        [
            parallel(
                [
                    a(NavigateAction)(target_location=target),
                    Monitor(is_pose_free_for_robot(robot, target)),
                ]
            ),
            a(MoveTorsoAction)(torso_state=TorsoState.HIGH),
        ]
    )


def test_the_plan_tree_verbalizes_as_one_sentence():
    # The action nodes are Verbalizable, so each states itself as an imperative verb phrase (NavigateAction
    # -> "navigate to …", MoveTorsoAction -> "move the torso to a … state"); the navigate and the monitor
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
    # an action node states itself as an imperative verb phrase, not "Perform a NavigateAction"
    assert (
        make_node(a(NavigateAction)(target_location=target))
        .verbalize()
        .startswith("Navigate")
    )
    assert Monitor(is_pose_free_for_robot(robot, target)).verbalize().startswith(
        "Monitor whether "
    )
