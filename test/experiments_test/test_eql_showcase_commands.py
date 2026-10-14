"""
Tests for commanding the robot from the viewer and asking how it resolved what a command
left open.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.plan import Plan
from coraplex.plans.underspecified import CandidateOutcome
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from cramera.live.bridge import Bridge
from experiments.eql_showcase.commands import (
    APPROACH_DIRECTIONS,
    PUT_BACK,
    CandidateChoice,
    CommandState,
    ResolutionSteps,
    RobotCommander,
)
from experiments.eql_showcase.showcase import EqlShowcase
from krrood.entity_query_language.factories import a, variable_from
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types.spatial_types import Pose

from ..conftest import SAMPLING_SEED

WHAT_HAVE_I_ASKED = "What have I asked you to do?"
"""
The showcase's question listing the commands given so far.
"""


@pytest.fixture
def commander(pr2_apartment_world) -> RobotCommander:
    """
    A commander for the PR2 in the apartment, recording the plans its commands become.
    """
    robot = pr2_apartment_world.get_semantic_annotations_by_type(PR2)[0]
    observed: list[Plan] = []
    return RobotCommander(
        context=Context(pr2_apartment_world, robot, sampling_seed=SAMPLING_SEED),
        execution_environment=lambda: kinematically_simulated_robot,
        observe_plan=observed.append,
    )


# %% giving commands


def test_a_command_given_waits_its_turn(commander: RobotCommander):
    command = commander.do(ParkArmsAction(commander.context.robot.all_arms), "park")

    assert commander.commands == [command]
    assert command.state is CommandState.QUEUED


def test_putting_an_object_back_is_a_command_named_after_it(
    commander: RobotCommander,
):
    commander.remember_homes([Milk])

    command = commander.put_back(Milk)

    assert command.name == PUT_BACK.format(Milk.__name__.lower())


def test_pausing_holds_the_robot_and_resuming_lets_it_go(commander: RobotCommander):
    commander.pause()
    paused = commander.context.execution_gate.is_paused
    commander.resume()

    assert paused
    assert not commander.context.execution_gate.is_paused


def test_a_command_carried_out_is_done(commander: RobotCommander):
    command = commander.do(ParkArmsAction(commander.context.robot.all_arms), "park")

    commander.carry_out(command, ParkArmsAction(commander.context.robot.all_arms))

    assert command.state is CommandState.DONE


# %% how what was left open got resolved


def test_every_candidate_considered_is_a_resolution_step(commander: RobotCommander):
    plans: list[Plan] = []
    commander.observe_plan = plans.append
    open_torso = a(MoveTorsoAction)(
        torso_state=variable_from([TorsoState.HIGH, TorsoState.LOW])
    )
    command = commander.do(open_torso, "raise the torso")

    commander.carry_out(command, open_torso)

    [step] = list(ResolutionSteps(plans))
    assert step.open_part == MoveTorsoAction.__name__
    assert step.outcome == CandidateOutcome.ACCEPTED
    assert step.candidate == 1


@pytest.mark.parametrize("axis_and_sign", sorted(APPROACH_DIRECTIONS))
def test_a_grasp_is_described_by_the_side_it_approaches_from(axis_and_sign):
    axis, sign = axis_and_sign
    rotations = {
        (0, 1): dict(),
        (0, -1): dict(yaw=3.14159),
        (1, 1): dict(yaw=1.5708),
        (1, -1): dict(yaw=-1.5708),
        (2, 1): dict(pitch=-1.5708),
        (2, -1): dict(pitch=1.5708),
    }
    grasp_pose = Pose.from_xyz_rpy(0, 0, 0, **rotations[axis_and_sign])

    assert CandidateChoice.approach_of(grasp_pose) == APPROACH_DIRECTIONS[axis_and_sign]


# %% the commands offered to the viewer


def test_the_commands_given_can_be_asked_about(pr2_apartment_world, commander):
    showcase = EqlShowcase(pr2_apartment_world, commander=commander)
    bridge = Bridge()
    showcase.register_with(bridge)
    command = commander.do(ParkArmsAction(commander.context.robot.all_arms), "park")

    question = next(
        preset for preset in showcase.presets() if preset.text == WHAT_HAVE_I_ASKED
    )
    answer = bridge.run_query(question.code, question.scope)

    assert [row["__entity__"] for row in answer.rows] == [command.name]


def test_commands_are_offered_only_while_the_robot_takes_them(pr2_apartment_world):
    showcase = EqlShowcase(pr2_apartment_world)

    assert WHAT_HAVE_I_ASKED not in [preset.text for preset in showcase.presets()]


def test_offering_the_commands_gives_none_of_them(pr2_apartment_world, commander):
    commander.remember_homes([Milk])
    showcase = EqlShowcase(pr2_apartment_world, commander=commander)
    bridge = Bridge()
    showcase.register_with(bridge)

    bridge.query_presets()

    assert commander.commands == []
