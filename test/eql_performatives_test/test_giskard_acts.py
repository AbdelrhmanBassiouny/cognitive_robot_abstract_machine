"""
Tests for the giskardpy motion speech acts (``Achieve`` / ``Observe``) and their composition with the
framework-agnostic krrood combinators.

Lives in its own directory (not ``giskardpy_test``) so it runs in the lean container: it imports the
giskardpy *library* (rclpy mocked) without the ``giskardpy_test`` conftest that requires real ROS.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.performatives import Performable, Sequential
from giskardpy.eql.constraints import MinClearance
from giskardpy.eql.performatives import Achieve, Observe


def _keep_clear():
    return MinClearance(body_a="the gripper", body_b="the table", minimum=0.01)


def test_achieve_verbalizes_the_goal():
    assert Achieve(_keep_clear()).verbalize() == (
        "Achieve that the distance between the gripper and the table is at least 0.01 metres"
    )


def test_observe_verbalizes_the_condition():
    assert Observe(_keep_clear()).verbalize() == (
        "Observe whether the distance between the gripper and the table is at least 0.01 metres"
    )


def test_achieve_compiles_its_goal_into_a_giskard_inequality():
    collection = Achieve(_keep_clear()).perform()
    inequalities = collection.inequality_constraints
    assert len(inequalities) == 1
    assert not inequalities[0].expression.is_constant()   # the symbolic distance flows into the QP


def test_observe_execution_is_delegated_to_the_runtime_monitor():
    with pytest.raises(NotImplementedError):
        Observe(_keep_clear()).perform()


def test_motion_acts_conform_to_performable():
    assert isinstance(Achieve(_keep_clear()), Performable)
    assert isinstance(Observe(_keep_clear()), Performable)


def test_krrood_composition_spans_giskard_acts():
    """The cross-framework payoff: a krrood combinator composes giskardpy acts into one verbalizable plan."""
    plan = Sequential([Achieve(_keep_clear()), Observe(_keep_clear())])
    assert plan.verbalize() == (
        "Achieve that the distance between the gripper and the table is at least 0.01 metres, "
        "then Observe whether the distance between the gripper and the table is at least 0.01 metres"
    )
