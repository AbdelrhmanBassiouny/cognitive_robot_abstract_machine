"""
Tests for the EQL showcase: the questions it offers the viewer, the knowledge they are
asked of, and the record of what the robot did that its questions about the past range
over.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import VisualizationBackend
from coraplex.demonstrations import RobotDemonstration
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import ActionNode
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from cramera.knowledge.presets import Preset
from cramera.live.bridge import Bridge
from cramera.knowledge.queryable_knowledge import QueryScope
from experiments.eql_showcase.performed_actions import (
    ActedOnObject,
    PerformedAction,
    PerformedActions,
    RecordedRun,
)
from experiments.orm.ormatic_interface import RecordedRunDAO
from experiments.eql_showcase.demo import (
    PLACE_SETTING_LABEL,
    RUN_DATABASE_FILE,
    ShowcasedDemonstration,
)
from experiments.eql_showcase.episodic_memory import SQL_LANGUAGE, RunDatabase
from experiments.eql_showcase.showcase import EqlShowcase, ShowcaseQuestions
from segmind.event_logger import EventLogger
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.world import World
from typing_extensions import List

from ..conftest import SAMPLING_SEED

WHAT_DID_YOU_DO = "What did you do?"
"""
The showcase's question about the run in progress's own steps.
"""

RUNS_WITH_THE_MILK = "In which runs did you handle the milk?"
"""
The showcase's question about which finished runs acted on the milk.
"""

# %% the questions file


@pytest.fixture
def run_database(tmp_path) -> RunDatabase:
    """
    An empty database of finished runs, in a file of its own.
    """
    return RunDatabase(tmp_path / RUN_DATABASE_FILE)


def test_every_question_is_asked_of_a_scope_the_showcase_offers(
    pr2_apartment_world, run_database
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    showcase.observe_events(EventLogger())

    assert {question.scope for question in showcase.questions.questions} == {
        item.scope for item in showcase.knowledge()
    }


def test_questions_are_offered_only_for_the_given_scopes():
    questions = ShowcaseQuestions.from_file()

    presets = questions.presets([QueryScope.EPISODIC_MEMORY])

    assert [preset.text for preset in presets] == [
        question.text
        for question in questions.questions
        if question.scope is QueryScope.EPISODIC_MEMORY
    ]


def question_about(showcase: EqlShowcase, text: str) -> Preset:
    """
    The preset the showcase offers for one of its questions.

    :param showcase: The showcase offering the question.
    :param text: The question, as its button reads.
    """
    return next(preset for preset in showcase.presets() if preset.text == text)


# %% the knowledge offered to the viewer


def test_detected_events_are_offered_once_events_are_segmented(pr2_apartment_world):
    showcase = EqlShowcase(pr2_apartment_world)
    before = [item.scope for item in showcase.knowledge()]

    showcase.observe_events(EventLogger())

    assert before == [QueryScope.CURRENT_STATE]
    assert [item.scope for item in showcase.knowledge()] == [
        QueryScope.CURRENT_STATE,
        QueryScope.DETECTED_EVENTS,
    ]


def test_finished_runs_are_offered_only_while_a_database_keeps_them(
    pr2_apartment_world, run_database
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)

    assert [item.scope for item in showcase.knowledge()] == [
        QueryScope.CURRENT_STATE,
        QueryScope.EPISODIC_MEMORY,
    ]


def test_no_question_about_events_is_offered_before_events_are_segmented(
    pr2_apartment_world,
):
    showcase = EqlShowcase(pr2_apartment_world)

    assert QueryScope.DETECTED_EVENTS not in {
        preset.scope for preset in showcase.presets()
    }


def test_registering_offers_the_showcases_questions_to_the_viewer(
    pr2_apartment_world, run_database
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    showcase.observe_events(EventLogger())
    bridge = Bridge()

    showcase.register_with(bridge)

    assert bridge.query_scopes() == [item.scope for item in showcase.knowledge()]
    assert [preset.text for preset in bridge.query_presets()] == [
        preset.text for preset in showcase.presets()
    ]


def test_every_offered_question_is_answered(pr2_apartment_world, run_database):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    showcase.observe_events(EventLogger())
    bridge = Bridge()
    showcase.register_with(bridge)

    failed = [
        preset.text
        for preset in showcase.presets()
        if not bridge.run_query(preset.code, preset.scope).ok
    ]

    assert failed == []


# %% what the robot did


def place_setting_context(world: World) -> Context:
    """
    A context for the PR2 in the apartment world.

    :param world: The apartment world the PR2 stands in.
    """
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    return Context(world, robot, sampling_seed=SAMPLING_SEED)


@pytest.fixture
def performed_body_motions(pr2_apartment_world) -> Plan:
    """
    The PR2 parking its arms and then raising its torso, performed in simulation.
    """
    context = place_setting_context(pr2_apartment_world)
    plan = sequential(
        [
            ParkArmsAction(context.robot.all_arms),
            MoveTorsoAction(TorsoState.HIGH),
        ],
        context=context,
    ).plan
    with kinematically_simulated_robot:
        plan.perform()
    return plan


def test_performed_actions_are_recorded_in_the_order_they_began(
    performed_body_motions,
):
    records = list(PerformedActions([performed_body_motions]))

    assert [record.action_type for record in records] == [
        ParkArmsAction.__name__,
        MoveTorsoAction.__name__,
    ]
    assert records[0].timestamp <= records[1].timestamp


def test_an_action_about_no_object_records_none(performed_body_motions):
    park, _ = PerformedActions([performed_body_motions])

    assert park.acted_on is None
    assert park.related_highlight_ids() == []


def test_a_plan_not_yet_performed_records_no_action(pr2_apartment_world):
    context = place_setting_context(pr2_apartment_world)
    plan = sequential([ParkArmsAction(context.robot.all_arms)], context=context).plan

    assert list(PerformedActions([plan])) == []


def test_a_question_about_the_past_sees_a_plan_performed_after_registering(
    pr2_apartment_world, performed_body_motions
):
    showcase = EqlShowcase(pr2_apartment_world)
    bridge = Bridge()
    showcase.register_with(bridge)

    showcase.observe_plan(performed_body_motions)
    what_did_you_do = question_about(showcase, WHAT_DID_YOU_DO)
    answer = bridge.run_query(what_did_you_do.code, what_did_you_do.scope)

    assert [row["action_type"] for row in answer.rows] == [
        ParkArmsAction.__name__,
        MoveTorsoAction.__name__,
    ]


# %% the finished runs, asked about in SQL


def recorded_run(started: datetime, objects: List[str]) -> RecordedRun:
    """
    A finished run that picked up the given objects one after another.

    :param started: When the run's first pick up began.
    :param objects: The names of the objects picked up, in order.
    """
    return RecordedRun.of_actions(
        PLACE_SETTING_LABEL,
        [
            PerformedAction(
                name=f"{name} {PickUpAction.__name__}",
                action_type=PickUpAction.__name__,
                timestamp=started + timedelta(minutes=index),
                seconds=10.0,
                acted_on=name,
            )
            for index, name in enumerate(objects)
        ],
    )


def test_a_question_about_finished_runs_ranges_over_each_runs_own_actions(
    pr2_apartment_world, run_database
):
    with_milk = recorded_run(datetime(2026, 10, 14, 15), ["Milk", "Bowl"])
    without_milk = recorded_run(datetime(2026, 10, 14, 16), ["Bowl"])
    run_database.remember(with_milk)
    run_database.remember(without_milk)
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    bridge = Bridge()
    showcase.register_with(bridge)

    question = question_about(showcase, RUNS_WITH_THE_MILK)
    answer = bridge.run_query(question.code, question.scope)

    assert [row["__entity__"] for row in answer.rows] == [with_milk.name]


def test_a_question_about_finished_runs_shows_the_sql_it_was_answered_by(
    pr2_apartment_world, run_database
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    bridge = Bridge()
    showcase.register_with(bridge)

    question = question_about(showcase, RUNS_WITH_THE_MILK)
    answer = bridge.run_query(question.code, question.scope)

    assert answer.translation.language == SQL_LANGUAGE
    assert RecordedRunDAO.__tablename__ in answer.translation.statement


def test_a_finished_run_is_remembered_with_the_actions_it_performed(
    pr2_apartment_world, run_database, performed_body_motions
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)
    showcase.observe_plan(performed_body_motions)

    showcase.remember_run(PLACE_SETTING_LABEL)

    with run_database.session() as session:
        [stored] = [dao.from_dao() for dao in session.query(RecordedRunDAO).all()]
    assert stored.demonstration == PLACE_SETTING_LABEL
    assert [action.action_type for action in stored.actions] == [
        ParkArmsAction.__name__,
        MoveTorsoAction.__name__,
    ]


def test_a_run_in_which_the_robot_did_nothing_is_not_remembered(
    pr2_apartment_world, run_database
):
    showcase = EqlShowcase(pr2_apartment_world, database=run_database)

    showcase.remember_run(PLACE_SETTING_LABEL)

    with run_database.session() as session:
        assert session.query(RecordedRunDAO).count() == 0


# %% the object an action is about


def test_an_action_is_about_the_object_it_grasps(pr2_apartment_world):
    context = place_setting_context(pr2_apartment_world)
    milk = pr2_apartment_world.get_semantic_annotations_by_type(Milk)[0]
    plan = sequential(
        [
            ReachAction(
                grasp=GraspCandidate.from_body_origin(milk),
                arm=context.robot.left_arm,
            )
        ],
        context=context,
    ).plan
    [reach] = [node for node in plan.plan_graph.nodes() if isinstance(node, ActionNode)]

    assert ActedOnObject(reach).body() is milk.root


def test_an_action_about_the_robot_alone_is_about_no_object(pr2_apartment_world):
    context = place_setting_context(pr2_apartment_world)
    plan = sequential([ParkArmsAction(context.robot.all_arms)], context=context).plan
    [park] = [node for node in plan.plan_graph.nodes() if isinstance(node, ActionNode)]

    assert ActedOnObject(park).body() is None


# %% the showcase listening in on a demonstration


@dataclass(kw_only=True)
class ArmParkingDemonstration(RobotDemonstration):
    """
    A demonstration whose plan only parks the PR2's arms, in a world handed to it.
    """

    world: World
    """
    The world the demonstration acts in instead of one it builds itself.
    """

    def build_simulated_world(self) -> World:
        return self.world

    def is_scene_populated(self, world: World) -> bool:
        return True

    def populate_scene(self, world: World) -> None:
        pass

    def build_context(self, world: World) -> Context:
        return place_setting_context(world)

    def build_plan(self, context: Context) -> Plan:
        return sequential(
            [ParkArmsAction(context.robot.all_arms)], context=context
        ).plan


@dataclass(kw_only=True)
class ShowcasedArmParking(ShowcasedDemonstration, ArmParkingDemonstration):
    """
    The arm parking demonstration with the EQL showcase listening in.
    """


def test_a_showcased_demonstration_offers_the_plan_it_performed(pr2_apartment_world):
    demonstration = ShowcasedArmParking(
        used_robot=PR2,
        world=pr2_apartment_world,
        event_segmentation=False,
        default_visualization_backend=VisualizationBackend.NONE,
    )

    demonstration.run()

    assert demonstration.showcase.world is pr2_apartment_world
    assert [
        record.action_type for record in demonstration.showcase.performed_actions
    ] == [ParkArmsAction.__name__]
