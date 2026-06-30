"""
Tests for the giskardpy motion speech acts (``Achieve`` / ``Monitor``) and their composition, as plan
nodes, with the coraplex plan combinators.

``Achieve`` drives a motion goal/task (it compiles to QP constraints); ``Monitor`` watches a predicate or
constraint (a runtime monitor). Lives in its own directory (not ``giskardpy_test``) so it runs in the lean
container without the ``giskardpy_test`` conftest that requires real ROS.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.performatives import Performable
from semantic_digital_twin.reasoning.robot_predicates import is_pose_free_for_robot
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose
from giskardpy.eql.constraints import MinClearance, ReachPosition
from giskardpy.eql.performatives import Achieve, Monitor
from coraplex.plans.factories import sequential


def _reach():
    return ReachPosition(tip="the gripper tip", target="the target pose")


def _keep_clear():
    return MinClearance(body_a="the gripper", body_b="the table", minimum=0.01)


# ── Achieve: a motion goal that compiles to a QP constraint ──────────────────────


def test_achieve_verbalizes_the_motion_goal():
    assert Achieve(_reach()).verbalize() == (
        "Achieve that the gripper tip is at the target pose"
    )


def test_achieve_compiles_its_goal_into_a_giskard_inequality():
    collection = Achieve(_reach()).perform()
    inequalities = collection.inequality_constraints
    assert len(inequalities) == 1
    assert not inequalities[0].expression.is_constant()   # the symbolic distance flows into the QP


# ── Monitor: a constraint or predicate, watched at runtime ───────────────────────


def test_monitor_watches_a_constraint():
    assert Monitor(_keep_clear()).verbalize() == (
        "Monitor whether the distance between the gripper and the table is at least 0.01 metres"
    )


def test_monitor_watches_an_eql_predicate():
    condition = is_pose_free_for_robot(variable(AbstractRobot, []), variable(Pose, []))
    assert Monitor(condition).verbalize().startswith("Monitor whether ")


def test_monitor_execution_is_delegated_to_the_runtime_monitor():
    with pytest.raises(NotImplementedError):
        Monitor(_keep_clear()).perform()


# ── shared interface + cross-framework composition ───────────────────────────────


def test_motion_acts_conform_to_performable():
    assert isinstance(Achieve(_reach()), Performable)
    assert isinstance(Monitor(_keep_clear()), Performable)


def test_plan_composition_spans_giskard_acts():
    # the giskard acts compose, as plan nodes, in a coraplex plan and verbalize through the shared shapes
    plan = sequential([Achieve(_reach()), Monitor(_keep_clear())])
    assert plan.verbalize() == (
        "Achieve that the gripper tip is at the target pose, "
        "then Monitor whether the distance between the gripper and the table is at least 0.01 metres"
    )
