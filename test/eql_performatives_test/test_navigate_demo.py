"""
Demo: a real plan, re-expressed as verbalizable speech acts composed across frameworks.

A coraplex ``NavigateAction`` (the *Perform* act), a giskardpy clearance goal (the *Achieve* act), and a
safety monitor (the *Observe* act) compose under one krrood ``Sequential`` and verbalize as a single
robot-spoken sentence -- the payoff of the performative layer: one description language, one composition
language, one verbalization, across perception / planning / motion frameworks.

Runs in the lean container: it builds and verbalizes the plan (and compiles the Achieve step to a giskard
constraint) without ROS; executing the motion is the ROS-CI step.
"""

from __future__ import annotations

from coraplex.robot_plans.actions.core.navigation import NavigateAction
from semantic_digital_twin.spatial_types.spatial_types import Pose

from krrood.entity_query_language.factories import a
from krrood.entity_query_language.performatives import Perform, Sequential
from giskardpy.eql.constraints import MinClearance
from giskardpy.eql.performatives import Achieve, Observe


def _keep_clear():
    return MinClearance(body_a="the gripper", body_b="the table", minimum=0.01)


def _approach_and_keep_clear() -> Sequential:
    return Sequential(
        [
            Perform(a(NavigateAction)(target_location=Pose())),
            Achieve(_keep_clear()),
            Observe(_keep_clear()),
        ]
    )


def test_a_real_navigation_plan_verbalizes_as_one_sentence():
    assert _approach_and_keep_clear().verbalize() == (
        "Perform a NavigateAction given that its target_location is a specific Pose, "
        "then Achieve that the distance between the gripper and the table is at least 0.01 metres, "
        "then Observe whether the distance between the gripper and the table is at least 0.01 metres"
    )


def test_the_perform_step_uses_the_new_idiom():
    # a(NavigateAction)(...) builds the action match; Perform reframes its "Generate" as "Perform"
    perform = Perform(a(NavigateAction)(target_location=Pose()))
    assert perform.verbalize().startswith("Perform a NavigateAction")


def test_the_achieve_step_compiles_to_a_giskard_constraint():
    collection = Achieve(_keep_clear()).perform()
    assert len(collection.inequality_constraints) == 1
    assert not collection.inequality_constraints[0].expression.is_constant()
