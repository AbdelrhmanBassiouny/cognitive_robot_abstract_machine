"""
The pouring demo raises the torso only on robots that define a high torso state.
"""

from __future__ import annotations

import pytest

from experiments.tool_based_actions.simple_demo.demo_pouring import pouring_actions
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.exceptions import ParsingError
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.unitree_g1 import UnitreeG1
from semantic_digital_twin.spatial_types.spatial_types import Pose

from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction

from ..conftest import world_with_urdf_factory


def robot_with_world(robot_type):
    """
    Parse a robot's description and return its semantic annotation.

    :param robot_type: Robot to build.
    """
    try:
        world = world_with_urdf_factory(robot_type)
    except ParsingError as error:
        pytest.skip(f"{robot_type.__name__} description not available: {error}")
    return world.get_semantic_annotations_by_type(robot_type)[0]


def pouring_actions_for(robot):
    """
    Build the pouring action sequence for a robot, pouring into its own root body.

    :param robot: Robot performing the pour.
    """
    world = robot._world
    return pouring_actions(
        robot,
        world.root,
        None,
        Pose.from_xyz_rpy(reference_frame=world.root),
    )


def test_torso_step_included_for_robot_with_high_torso_state():
    robot = robot_with_world(PR2)
    assert robot.get_torso_if_specified().has_joint_state_of_type(TorsoState.HIGH)
    torso_actions = [
        action
        for action in pouring_actions_for(robot)
        if isinstance(action, MoveTorsoAction)
    ]
    assert [action.torso_state for action in torso_actions] == [TorsoState.HIGH]


def test_torso_step_omitted_for_robot_without_high_torso_state():
    robot = robot_with_world(UnitreeG1)
    assert not robot.get_torso_if_specified().has_joint_state_of_type(TorsoState.HIGH)
    assert not [
        action
        for action in pouring_actions_for(robot)
        if isinstance(action, MoveTorsoAction)
    ]
