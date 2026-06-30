"""
Tests for the giskardpy motion speech acts (``Achieve`` / ``Monitor``).

Both are :class:`~krrood.entity_query_language.performatives.Performative` acts over an EQL description:
``Achieve`` drives a description to satisfaction, ``Monitor`` watches one hold over time. They verbalize
through the shared EQL pipeline and compose with the framework-agnostic krrood combinators; executing them
is delegated to the giskard motion runtime (a seam that needs the ROS execution stack). Lives in its own
directory (not ``giskardpy_test``) so it runs in the lean container without the ROS conftest.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.performatives import Performable, Sequential
from semantic_digital_twin.reasoning.robot_predicates import (
    is_pose_free_for_robot,
    robot_holds_body,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body
from giskardpy.eql.performatives import Achieve, Monitor


def _holds():
    """A reach-like motion goal as an EQL description: the robot holds the body."""
    return robot_holds_body(variable(AbstractRobot, []), variable(Body, []))


def _pose_free():
    """A condition to watch as an EQL predicate: the pose is free for the robot."""
    return is_pose_free_for_robot(variable(AbstractRobot, []), variable(Pose, []))


# ── Achieve: a motion description, framed as a goal ──────────────────────────────


def test_achieve_verbalizes_its_description_as_a_goal():
    text = Achieve(_holds()).verbalize()
    assert text.startswith("Achieve that ")
    assert "hold" in text


def test_achieve_execution_is_delegated_to_the_motion_runtime():
    with pytest.raises(NotImplementedError):
        Achieve(_holds()).perform()


# ── Monitor: an EQL condition, watched at runtime ────────────────────────────────


def test_monitor_verbalizes_the_watched_condition():
    text = Monitor(_pose_free()).verbalize()
    assert text.startswith("Monitor whether ")
    assert "free" in text


def test_monitor_execution_is_delegated_to_the_runtime_monitor():
    with pytest.raises(NotImplementedError):
        Monitor(_pose_free()).perform()


# ── shared interface + cross-framework composition ───────────────────────────────


def test_motion_acts_conform_to_performable():
    assert isinstance(Achieve(_holds()), Performable)
    assert isinstance(Monitor(_pose_free()), Performable)


def test_krrood_composition_spans_giskard_acts():
    text = Sequential([Achieve(_holds()), Monitor(_pose_free())]).verbalize()
    assert text.startswith("Achieve that ")
    assert ", then Monitor whether " in text
