"""
Asking the frozen set of a run that is over, and checking every answer against what the
run actually recorded.

One episode of two trials is recorded through the recorder a run uses, then asked back.
Ground truth is traversed off the recalled objects rather than asked for through the
query under test -- a query checked against itself proves nothing.

..note:: Every question here crosses a to-many collection the episode model holds, which
    the generated interface reaches through an association table. These tests are what
    answered whether the query language translates a join across one, and the answer is
    that it does, since each variable now ranges over an element of its own:
    ``test_membership_in_a_collection_joins_the_members`` and
    ``test_membership_across_two_collections_in_turn`` cover the two shapes in krrood's
    own suite.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from coraplex.datastructures.enums import Arms, MovementType
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import MotionNode, PlanNode
from coraplex.robot_plans.motions.base import BaseMotion
from coraplex.robot_plans.motions.gripper import MoveToolCenterPointMotion
from coraplex.robot_plans.motions.robot_body import MoveJointsMotion
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import PrismaticConnection
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List

from experiments.episodes.episode import Episode, PerformedPlan, RecordedTrial, Tick
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import open_recording
from experiments.montessori.results_database import ResultsDatabase
from experiments.questions.long_term_memory import (
    AnythingMovedInTheEpisode,
    JointRequest,
    MotionRequest,
    MotionsRequestedInTheEpisode,
    NumberOfDegreesOfFreedomInTheRecordedWorld,
    ObjectsSeenInTheEpisode,
    ObjectsThatMovedInTheEpisode,
    ObjectsTheRobotMovedInTheEpisode,
    PickedUpInTheEpisode,
    ToolCenterPointRequest,
)
from experiments.questions.question import BloomLevel, Bucket, Memory
from experiments.questions.question_set import QuestionSet, RememberedThings
from experiments.scenarios.trial import TrialOutcome

from .test_episodes import sorting_episode

MOVED_OBJECT_NAME = "cube"
"""
The object the recorded run both picked up and moved.
"""

UNTOUCHED_OBJECT_NAME = "cylinder"
"""
The object the recorded run only ever saw, so a question about it has a false to give.
"""

SHOVED_OBJECT_NAME = "shoved_cube"
"""
The object someone other than the robot moved before the run handled anything.
"""

FIRST_TICK = 1.0
"""
When the run's first tick was taken, in seconds from the start of its trial.
"""

SECOND_TICK = 2.0
"""
When the run's second tick was taken.
"""

JOINTS_THE_ROBOT_HAD = 1
"""
How many joints the world the run happened in held, so counting them has an answer that
is neither nothing nor everything.
"""

NUMBERS_OF_THE_TRIALS_OF_A_REPEATED_EPISODE = (1, 2, 3)
"""
The trials of an episode run more than once, each of which reaches the one world the
episode recorded.
"""

# %% the run every question is asked of


@pytest.fixture()
def results_database(tmp_path) -> ResultsDatabase:
    """
    A results database of this test's own, on disk so a run and a question reach it
    through sessions of their own.
    """
    return ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))


def one_jointed_world() -> World:
    """
    The world the recorded run happened in: two links joined by the one joint the robot
    of that run could move.
    """
    world = World()
    base = Body(name=PrefixedName("base"))
    arm = Body(name=PrefixedName("arm"))
    with world.modify_world():
        world.add_kinematic_structure_entity(base)
        world.add_connection(
            PrismaticConnection.create_with_dofs(
                world=world, parent=base, child=arm, axis=Vector3(0.0, 0.0, 1.0)
            )
        )
    return world


@pytest.fixture()
def recorded_episode(results_database: ResultsDatabase) -> Episode:
    """
    One run in which the robot saw two objects, picked one of them up and moved it, in a
    world with one movable joint.
    """
    episode = sorting_episode()
    episode.world = one_jointed_world()
    moved = Body(name=PrefixedName(MOVED_OBJECT_NAME))
    untouched = Body(name=PrefixedName(UNTOUCHED_OBJECT_NAME))

    trial = RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=12.5,
        ticks=[
            Tick(moment=FIRST_TICK, events=[PickUpEvent(tracked_object=moved)]),
            Tick(
                moment=SECOND_TICK,
                events=[
                    TranslationEvent(tracked_object=moved),
                    TranslationEvent(tracked_object=untouched),
                ],
            ),
        ],
    )
    recording = open_recording(results_database)
    recording.record(trial)
    recording.close()
    return episode


@pytest.fixture()
def memory(results_database: ResultsDatabase) -> LongTermMemory:
    """
    The episodes that database holds.
    """
    return LongTermMemory(results_database)


def names(bodies: List[Body]) -> List[str]:
    """
    What each of the given bodies is called, so an answer read back out of the database
    is compared with one by what it names rather than by object identity.

    :param bodies: The bodies to name.
    """
    return sorted(body.name.name for body in bodies)


# %% what a question of this kind declares about itself


def test_long_term_questions_are_remembering_questions(recorded_episode: Episode):
    for question in QuestionSet.over_long_term_memory(
        RememberedThings(
            episode_identifier=recorded_episode.identifier,
            object_name=MOVED_OBJECT_NAME,
        )
    ).questions:
        assert question.memory is Memory.LONG_TERM
        assert question.bloom_level is BloomLevel.REMEMBERING


def test_the_long_term_set_covers_the_buckets_a_recorded_run_can_be_asked_about(
    recorded_episode: Episode,
):
    question_set = QuestionSet.over_long_term_memory(
        RememberedThings(
            episode_identifier=recorded_episode.identifier,
            object_name=MOVED_OBJECT_NAME,
        )
    )
    assert question_set.buckets == [
        Bucket.SCENE,
        Bucket.TEMPORAL_AND_AGENCY,
        Bucket.SELF_MODEL,
    ]


# %% scene


def test_the_objects_seen_are_the_ones_the_recorded_events_name(
    recorded_episode: Episode, memory: LongTermMemory
):
    question = ObjectsSeenInTheEpisode(episode_identifier=recorded_episode.identifier)
    assert question.matches_ground_truth(memory)
    assert set(names(question.ask(memory))) == {
        MOVED_OBJECT_NAME,
        UNTOUCHED_OBJECT_NAME,
    }


# %% temporal and agency


def test_the_run_recorded_that_something_moved(
    recorded_episode: Episode, memory: LongTermMemory
):
    assert (
        AnythingMovedInTheEpisode(episode_identifier=recorded_episode.identifier).ask(
            memory
        )
        is True
    )


def test_the_objects_that_moved_are_the_ones_the_motions_name(
    recorded_episode: Episode, memory: LongTermMemory
):
    question = ObjectsThatMovedInTheEpisode(
        episode_identifier=recorded_episode.identifier
    )
    assert set(names(question.ask(memory))) == {
        MOVED_OBJECT_NAME,
        UNTOUCHED_OBJECT_NAME,
    }


def test_only_the_object_the_run_picked_up_and_moved_is_one_it_moved_itself(
    recorded_episode: Episode, memory: LongTermMemory
):
    question = ObjectsTheRobotMovedInTheEpisode(
        episode_identifier=recorded_episode.identifier
    )
    assert names(question.ask(memory)) == [MOVED_OBJECT_NAME]
    assert question.matches_ground_truth(memory)


def test_an_object_the_robot_handled_twice_is_named_once_among_the_ones_it_moved(
    results_database: ResultsDatabase, memory: LongTermMemory
):
    """
    The query pairs every recorded motion with every recorded pick-up of the same
    object, so an object handled twice comes back twice; the question asks which objects
    the robot moved, not how often it handled them.
    """
    episode = sorting_episode()
    moved = Body(name=PrefixedName(MOVED_OBJECT_NAME))
    recording = open_recording(results_database)
    recording.record(
        RecordedTrial(
            episode=episode,
            outcome=TrialOutcome.SUCCEEDED,
            duration=12.5,
            ticks=[
                Tick(
                    moment=FIRST_TICK,
                    events=[
                        PickUpEvent(tracked_object=moved),
                        PickUpEvent(tracked_object=moved),
                    ],
                ),
                Tick(
                    moment=SECOND_TICK,
                    events=[TranslationEvent(tracked_object=moved)],
                ),
            ],
        )
    )
    recording.close()
    question = ObjectsTheRobotMovedInTheEpisode(episode_identifier=episode.identifier)

    assert names(question.ask(memory)) == [MOVED_OBJECT_NAME]
    assert question.matches_ground_truth(memory)


def test_the_objects_the_run_moved_are_true_in_any_order(
    results_database: ResultsDatabase, memory: LongTermMemory
):
    """
    Someone else shoved one object before the run handled anything, so the recorded
    motions name it first while the run's own actions name what it picked up first.

    The answer is the objects the robot moved either way.
    """
    episode = sorting_episode()
    shoved = Body(name=PrefixedName(SHOVED_OBJECT_NAME))
    picked_up = Body(name=PrefixedName(MOVED_OBJECT_NAME))
    recording = open_recording(results_database)
    recording.record(
        RecordedTrial(
            episode=episode,
            outcome=TrialOutcome.SUCCEEDED,
            duration=12.5,
            ticks=[
                Tick(
                    moment=FIRST_TICK,
                    events=[TranslationEvent(tracked_object=shoved)],
                ),
                Tick(
                    moment=SECOND_TICK,
                    events=[
                        PickUpEvent(tracked_object=picked_up),
                        TranslationEvent(tracked_object=picked_up),
                        PickUpEvent(tracked_object=shoved),
                        TranslationEvent(tracked_object=shoved),
                    ],
                ),
            ],
        )
    )
    recording.close()
    question = ObjectsTheRobotMovedInTheEpisode(episode_identifier=episode.identifier)

    assert names(question.ask(memory)) == sorted(
        [MOVED_OBJECT_NAME, SHOVED_OBJECT_NAME]
    )
    assert question.matches_ground_truth(memory)


def test_only_the_object_with_a_recorded_pick_up_was_picked_up(
    recorded_episode: Episode, memory: LongTermMemory
):
    assert (
        PickedUpInTheEpisode(
            episode_identifier=recorded_episode.identifier,
            object_name=MOVED_OBJECT_NAME,
        ).ask(memory)
        is True
    )
    assert (
        PickedUpInTheEpisode(
            episode_identifier=recorded_episode.identifier,
            object_name=UNTOUCHED_OBJECT_NAME,
        ).ask(memory)
        is False
    )


# %% self-model


def test_the_joints_counted_are_the_ones_the_recorded_world_held(
    recorded_episode: Episode, memory: LongTermMemory
):
    question = NumberOfDegreesOfFreedomInTheRecordedWorld(
        episode_identifier=recorded_episode.identifier
    )
    assert question.ask(memory) == JOINTS_THE_ROBOT_HAD
    assert question.ask(memory) == question.ground_truth(memory)


def test_the_joints_are_counted_once_however_many_trials_the_episode_ran(
    results_database: ResultsDatabase, memory: LongTermMemory
):
    episode = sorting_episode()
    episode.world = one_jointed_world()
    recording = open_recording(results_database)
    for number in NUMBERS_OF_THE_TRIALS_OF_A_REPEATED_EPISODE:
        recording.record(
            RecordedTrial(
                episode=episode,
                outcome=TrialOutcome.SUCCEEDED,
                duration=12.5,
                number=number,
            )
        )
    recording.close()
    question = NumberOfDegreesOfFreedomInTheRecordedWorld(
        episode_identifier=episode.identifier
    )
    assert question.ask(memory) == JOINTS_THE_ROBOT_HAD

# %% control

REQUESTED_JOINT_NAME = "arm_joint"
"""
The joint the recorded plan asked to be moved.
"""

REQUESTED_JOINT_POSITION = 0.25
"""
Where the recorded plan asked that joint to go.
"""

REQUESTED_POSITION_THRESHOLD = 0.004
"""
How close to its target the recorded plan asked the tool center point to come, in
metres.
"""

REQUESTED_TARGET_HEIGHT = 0.3
"""
How high above the world's root the recorded plan asked the tool center point to go.
"""


@dataclass
class EpisodeThatRequestedMotions:
    """
    A recorded run whose plan asked the controller for motions, and the motions it asked
    for.
    """

    episode: Episode
    """
    The run.
    """

    motions: List[BaseMotion]
    """
    The motions its plan requested, in the order the plan holds them.
    """


def plan_requesting(motions: List[BaseMotion]) -> Plan:
    """
    A plan whose one root holds a motion node for each of the given motions.

    :param motions: The motions the plan requests.
    """
    plan = Plan()
    root = PlanNode()
    plan.add_node(root)
    for motion in motions:
        plan.add_edge(root, MotionNode(designator=motion))
    return plan


@pytest.fixture()
def episode_that_requested_motions(
    results_database: ResultsDatabase,
) -> EpisodeThatRequestedMotions:
    """
    One run whose plan moved a joint and then the tool center point, each under
    constraints of its own.
    """
    episode = sorting_episode()
    episode.world = one_jointed_world()
    motions = [
        MoveJointsMotion(
            names=[REQUESTED_JOINT_NAME], positions=[REQUESTED_JOINT_POSITION]
        ),
        MoveToolCenterPointMotion(
            Pose.from_xyz_rpy(
                z=REQUESTED_TARGET_HEIGHT, reference_frame=episode.world.root
            ),
            Arms.LEFT,
            movement_type=MovementType.TRANSLATION,
            allow_gripper_collision=True,
            position_threshold=REQUESTED_POSITION_THRESHOLD,
        ),
    ]
    recording = open_recording(results_database)
    recording.record(
        RecordedTrial(
            episode=episode,
            outcome=TrialOutcome.SUCCEEDED,
            duration=12.5,
            plans=[PerformedPlan(plan=plan_requesting(motions))],
        )
    )
    recording.close()
    return EpisodeThatRequestedMotions(episode=episode, motions=motions)


def test_the_motion_requests_are_the_ones_the_recorded_plan_made(
    episode_that_requested_motions: EpisodeThatRequestedMotions,
    memory: LongTermMemory,
):
    question = MotionsRequestedInTheEpisode(
        episode_identifier=episode_that_requested_motions.episode.identifier
    )
    assert question.ask(memory) == MotionRequest.over(
        episode_that_requested_motions.motions
    )
    assert question.matches_ground_truth(memory)


def test_the_answer_carries_the_constraints_the_plan_put_on_the_controller(
    episode_that_requested_motions: EpisodeThatRequestedMotions,
    memory: LongTermMemory,
):
    answered = MotionsRequestedInTheEpisode(
        episode_identifier=episode_that_requested_motions.episode.identifier
    ).ask(memory)
    [joints] = [request for request in answered if isinstance(request, JointRequest)]
    [tool_center_point] = [
        request for request in answered if isinstance(request, ToolCenterPointRequest)
    ]
    assert joints.joint_names == (REQUESTED_JOINT_NAME,)
    assert joints.positions == (REQUESTED_JOINT_POSITION,)
    assert tool_center_point.arm is Arms.LEFT
    assert tool_center_point.movement_type is MovementType.TRANSLATION
    assert tool_center_point.allow_gripper_collision is True
    assert tool_center_point.position_threshold == REQUESTED_POSITION_THRESHOLD


def test_the_long_term_set_asks_about_the_control_program_only_when_told_to(
    recorded_episode: Episode,
):
    things = RememberedThings(
        episode_identifier=recorded_episode.identifier,
        object_name=MOVED_OBJECT_NAME,
    )
    assert Bucket.CONTROL not in QuestionSet.over_long_term_memory(things).buckets
    assert (
        Bucket.CONTROL
        in QuestionSet.over_long_term_memory(
            things, asking_the_control_program=True
        ).buckets
    )


# %% every question at once


def test_every_question_of_the_long_term_set_answers_its_own_ground_truth(
    recorded_episode: Episode, memory: LongTermMemory
):
    question_set = QuestionSet.over_long_term_memory(
        RememberedThings(
            episode_identifier=recorded_episode.identifier,
            object_name=MOVED_OBJECT_NAME,
        )
    )
    for question in question_set.questions:
        assert question.matches_ground_truth(memory), question.english
