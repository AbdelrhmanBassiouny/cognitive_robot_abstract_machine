"""
Tests for querying a running Montessori sort.

Each of the three questions the buttons exist to answer gets its own test, built from a
progress record made by hand so no simulation has to run.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from coraplex.datastructures.enums import Arms, TaskStatus
from coraplex.plans.factories import sequential
from coraplex.plans.failures import BodyUnfetchable
from coraplex.plans.plan_node import ActionNode
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from segmind.datastructures.events import (
    InsertionEvent,
    LossOfContactEvent,
    PickUpEvent,
)
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from cramera.body_geometry import pose_label
from cramera.knowledge.query_runner import EqlQueryRunner
from cramera.knowledge.question_matching import QuestionMatcher
from cramera.knowledge.queryable_knowledge import QueryScope
from cramera.knowledge.replay import ReplayWindow
from experiments.montessori.insertion_diagnosis import InsertionFailureReason
from experiments.montessori.live_query_source import (
    DETECTED_EVENTS_PRESETS,
    MONTESSORI_PRESETS,
    MontessoriLiveQuerySource,
)
from experiments.montessori.scene_layout import SceneLayout
from experiments.montessori.semantics import SHAPE_NAME_SUFFIX
from experiments.montessori.sorting_progress import CompletedAttempt, SortingProgress
from experiments.montessori.sorting_results import InsertionOutcome

from .dataset.montessori_board import (
    SHAPE_KEY,
    SHAPE_OBJECT_NAME,
    board_with_one_hole,
    cube_at,
    move_shape_to,
)

DECLARED_PRESETS_PATH = (
    Path(__file__).parents[2]
    / "cramera"
    / "scenes"
    / "Franka_Montessori"
    / "presets.json"
)
"""
Where the recorded Franka Montessori bundle declares the same questions.
"""

STARTED_AT = datetime(2026, 8, 13, 12, 0, 0)
"""
When every attempt in these tests begins.
"""


@pytest.fixture()
def scene():
    """
    A board with one hole and a cube resting on top of it.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board, _ = board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))
    return world, board, shape


@pytest.fixture()
def source(scene):
    """
    A source over a sort that has made one failed attempt on one shape.
    """
    world, board, shape = scene
    progress = SortingProgress()
    progress.begin_shape(shape, board, world)
    progress.record_attempt(
        CompletedAttempt(
            shape_key=SHAPE_KEY,
            attempt_number=1,
            started_at=STARTED_AT,
            ended_at=STARTED_AT + timedelta(seconds=30),
            events=[PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT)],
            fell_through=False,
            raised_exception=BodyUnfetchable(body=shape.root, arm=None),
        )
    )
    return MontessoriLiveQuerySource(
        progress=progress, layout=SceneLayout.of_world(world)
    )


def current_state_of(source):
    """
    What a source offers about the sort in progress.

    :param source: The query source to read.
    """
    [knowledge] = [
        entry for entry in source.knowledge() if entry.scope is QueryScope.CURRENT_STATE
    ]
    return knowledge


def detected_events_of(source):
    """
    What a source offers about what its detectors saw.

    :param source: The query source to read.
    """
    [knowledge] = [
        entry
        for entry in source.knowledge()
        if entry.scope is QueryScope.DETECTED_EVENTS
    ]
    return knowledge


def ask_about_events(source, code):
    """
    Run one question about what was detected, the way the bridge does.

    :param source: The query source to ask.
    :param code: The query to run.
    """
    return EqlQueryRunner(domains=detected_events_of(source).domains).run(code)


def ask_in_scope(source, preset):
    """
    Run one preset against the body of knowledge its own scope names.

    :param source: The query source to ask.
    :param preset: The ready-made question to run.
    """
    [knowledge] = [entry for entry in source.knowledge() if entry.scope is preset.scope]
    return EqlQueryRunner(
        domains=knowledge.domains, extra_names=knowledge.extra_names
    ).run(preset.code)


def matcher_over(source):
    """
    The matcher the bridge builds for a source: everything it offers, shown or not.

    :param source: The query source whose questions may be recognized.
    """
    return QuestionMatcher(source.presets() + source.unlisted_presets())


def preset_named(source, text):
    """
    One of the source's ready-made questions, by the label it is shown under.

    :param source: The query source to read.
    :param text: The question's label.
    """
    [preset] = [entry for entry in source.presets() if entry.text == text]
    return preset


def ask(source, code, highlightable_ids=frozenset()):
    """
    Run one query about the sort in progress, the way the bridge does.

    :param source: The query source to ask.
    :param code: The query to run.
    :param highlightable_ids: Ids the viewer is said to show, as the bridge passes its
        published objects.
    """
    return EqlQueryRunner(
        domains=current_state_of(source).domains,
        highlightable_ids=highlightable_ids,
    ).run(code)


# %% the source's own shape
class TestTheSource:
    def test_it_titles_itself_after_the_demo(self, source):
        assert "montessori" in source.title().lower()

    def test_it_offers_the_sort_and_scene_variables(self, source):
        assert [domain.name for domain in current_state_of(source).domains] == [
            "shape",
            "attempt",
            "plan_step",
            "action",
            "hole",
            "board",
            "goal",
        ]

    def test_every_preset_runs(self, source):
        for preset in source.presets():
            assert ask_in_scope(source, preset).ok, preset.text


# %% "was this shape inserted?"
class TestWhetherAShapeIsInserted:
    def test_a_shape_on_top_of_the_board_is_not_inserted(self, source):
        result = ask(source, "an(entity(shape).where(shape.is_inserted == False))")

        assert [row["__entity__"] for row in result.rows] == [SHAPE_OBJECT_NAME]

    def test_a_shape_that_fell_through_is_inserted(self, source, scene):
        world, board, shape = scene
        move_shape_to(world, shape, Point3(0.0, 0.0, -0.1))
        source.progress.refresh_world_state(board, world)

        result = ask(source, "an(entity(shape).where(shape.is_inserted == True))")

        assert [row["__entity__"] for row in result.rows] == [SHAPE_OBJECT_NAME]

    def test_the_answer_follows_the_world_without_rebuilding_the_source(
        self, source, scene
    ):
        """
        The question is asked of a demo that is still running, so the same query has to
        give a different answer once the shape moves.
        """
        world, board, shape = scene
        before = ask(source, "an(entity(shape).where(shape.is_inserted == True))").count

        move_shape_to(world, shape, Point3(0.0, 0.0, -0.1))
        source.progress.refresh_world_state(board, world)

        assert before == 0
        assert (
            ask(source, "an(entity(shape).where(shape.is_inserted == True))").count == 1
        )


# %% "where were you trying to insert it?"
class TestWhereTheShapeWasAimed:
    def test_one_row_gives_the_shape_its_hole_and_the_insertion_pose(
        self, source, scene
    ):
        world, board, shape = scene

        result = ask(source, "set_of(shape.name, shape.target_hole, shape.target_pose)")

        [row] = result.rows
        assert row["name"] == SHAPE_OBJECT_NAME
        assert row["target_hole"] == SHAPE_KEY
        assert row["target_pose"] == pose_label(
            board.insertion_target_for(shape, world)
        )

    def test_each_attempt_reports_where_it_aimed(self, source):
        result = ask(
            source, "set_of(attempt.name, attempt.target_hole, attempt.target_pose)"
        )

        [row] = result.rows
        assert row["target_hole"] == SHAPE_KEY


# %% "why couldn't you insert it?"
class TestWhyAnAttemptFailed:
    def test_an_informative_plan_failure_is_reported(self, source):
        result = ask(
            source,
            "set_of(attempt.name, attempt.failure_reason, attempt.failure_detail)"
            ".where(attempt.succeeded == False)",
        )

        [row] = result.rows
        assert row["failure_reason"] == InsertionFailureReason.PLAN_FAILED
        assert "BodyUnfetchable" in row["failure_detail"]

    def test_a_shape_that_was_never_picked_up_is_named(self, scene):
        world, board, shape = scene
        progress = SortingProgress()
        progress.begin_shape(shape, board, world)
        progress.record_attempt(
            CompletedAttempt(
                shape_key=SHAPE_KEY,
                attempt_number=1,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=5),
                events=[
                    LossOfContactEvent(tracked_object=shape.root, timestamp=STARTED_AT)
                ],
                fell_through=False,
            )
        )
        source = MontessoriLiveQuerySource(progress=progress)

        result = ask(
            source,
            "an(entity(attempt).where(attempt.failure_reason == 'not_picked_up'))",
        )

        assert result.count == 1

    def test_a_shape_wedged_in_its_hole_is_named(self, scene):
        world, board, shape = scene
        progress = SortingProgress()
        progress.begin_shape(shape, board, world)
        progress.record_attempt(
            CompletedAttempt(
                shape_key=SHAPE_KEY,
                attempt_number=1,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=5),
                events=[
                    PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT),
                    InsertionEvent(tracked_object=shape.root, timestamp=STARTED_AT),
                ],
                fell_through=False,
            )
        )
        source = MontessoriLiveQuerySource(progress=progress)

        result = ask(
            source,
            "an(entity(attempt).where(attempt.failure_reason == 'wedged_in_hole'))",
        )

        assert result.count == 1

    def test_what_segmind_saw_for_a_shape_is_queryable(self, source):
        result = ask_about_events(
            source, "an(entity(event).where(event.shape_key == '%s'))" % SHAPE_KEY
        )

        assert [row["event_type"] for row in result.rows] == ["PickUpEvent"]


# %% "where is ...?" — answered by highlighting what it names
class TestWhereSomethingIs:
    """
    The scene's own layout answers "where is" questions, each lighting up what it names
    in the viewer.
    """

    def test_the_square_hole_is_found_and_highlighted(self, source):
        result = ask(source, "the(entity(hole).where(hole.name == '%s'))" % SHAPE_KEY)

        assert [row["__entity__"] for row in result.rows] == [SHAPE_KEY]
        assert result.highlight == [SHAPE_KEY]

    def test_every_hole_is_highlighted_at_once(self, source):
        result = ask(source, "an(entity(hole))")

        assert result.highlight == [SHAPE_KEY]

    def test_the_montessori_box_is_found_and_highlighted(self, source):
        result = ask(source, "the(entity(board))")

        assert [row["__entity__"] for row in result.rows] == ["board"]
        assert result.highlight == ["board"]

    def test_the_goal_for_the_cube_highlights_its_hole(self, source):
        result = ask(
            source,
            "the(entity(goal).where(goal.shape == '%s'))" % SHAPE_OBJECT_NAME,
        )

        [row] = result.rows
        assert row["hole"] == SHAPE_KEY
        assert result.highlight == ["%s goal" % SHAPE_OBJECT_NAME, SHAPE_KEY]

    def test_a_shape_row_lights_up_its_published_body(self, source):
        """
        The shape record is named after what the piece is (``"cube"``) while the viewer
        shows its body under the name it was built with, so the row has to say both.
        """
        result = ask(source, "an(entity(shape).where(shape.is_inserted == False))")

        assert result.highlight == [
            SHAPE_OBJECT_NAME,
            SHAPE_KEY + SHAPE_NAME_SUFFIX,
        ]

    def test_an_answer_naming_a_published_object_highlights_it(self, source):
        """
        Highlighting is not tied to any particular query: an answer value that names
        something the viewer shows glows, here the hole a shape is aimed at.
        """
        result = ask(
            source,
            "set_of(shape.name, shape.target_hole)",
            highlightable_ids=frozenset({SHAPE_KEY}),
        )

        assert result.highlight == [SHAPE_KEY]


# %% what was detected is its own body of knowledge
class TestAskingWhatWasDetected:
    """
    A detection is answered under its own heading: unlike the shapes and attempts it is
    read back as a moment of the run, with the recording to replay around it.
    """

    def test_the_detections_are_offered_between_the_present_and_the_recorded_past(
        self, source
    ):
        assert [knowledge.scope for knowledge in source.knowledge()] == [
            QueryScope.CURRENT_STATE,
            QueryScope.DETECTED_EVENTS,
        ]

    def test_the_detections_are_the_only_thing_it_ranges_over(self, source):
        assert [domain.name for domain in detected_events_of(source).domains] == [
            "event"
        ]

    def test_the_event_questions_are_offered_under_that_heading(self, source):
        assert [
            preset.text
            for preset in source.presets()
            if preset.scope is QueryScope.DETECTED_EVENTS
        ] == [preset.text for preset in DETECTED_EVENTS_PRESETS]

    def test_every_event_question_runs(self, source):
        for preset in DETECTED_EVENTS_PRESETS:
            assert ask_about_events(source, preset.code).ok, preset.text

    def test_a_detection_answers_with_what_was_seen_and_when(self, source):
        result = ask_about_events(
            source, "set_of(event.shape_key, event.event_type, event.timestamp)"
        )

        assert result.rows == [
            {
                "shape_key": SHAPE_KEY,
                "event_type": "PickUpEvent",
                "timestamp": STARTED_AT.isoformat(sep=" ", timespec="seconds"),
            }
        ]


# %% "show me what happened" — a detected event replays the demo around itself
class TestReplayingADetectedEvent:
    """
    An answer row naming a segmind detection carries the recording window to replay
    around it, leading and trailing the detection by the fixed shifts.
    """

    def test_an_event_row_carries_the_window_around_its_detection(self, source):
        result = ask_about_events(source, "an(entity(event))")

        assert result.replay == [ReplayWindow.around(STARTED_AT)]

    def test_the_what_was_detected_preset_offers_a_replay_per_detection(self, source):
        [preset] = [
            offered
            for offered in source.presets()
            if offered.text == "what was detected, and when?"
        ]

        result = ask_about_events(source, preset.code)

        assert result.replay == [ReplayWindow.around(STARTED_AT)]


# %% "what are you doing?" — the goal and the action of the moment
class TestWhatTheRobotIsDoingNow:
    """
    The sort is asked about itself while it runs, so the shape it is on and the action
    it is carrying out are answered from records that keep changing.
    """

    def test_the_current_goal_is_the_shape_being_sorted_and_where_it_is_aimed(
        self, source, scene
    ):
        world, board, shape = scene

        result = ask(source, preset_named(source, "what is your current goal?").code)

        [row] = result.rows
        assert row["__entity__"] == SHAPE_OBJECT_NAME
        assert row["target_hole"] == SHAPE_KEY

    def test_a_finished_shape_is_no_longer_the_goal(self, source):
        source.progress.finish_shape(SHAPE_KEY, InsertionOutcome.FELL_THROUGH)

        result = ask(source, preset_named(source, "what is your current goal?").code)

        assert result.count == 0

    def test_the_current_action_is_the_one_the_plan_is_running(self, source):
        parking = ParkArmsAction(Arms.BOTH)
        performing = sequential([parking, MoveTorsoAction(TorsoState.HIGH)]).plan
        [node] = [
            node
            for node in performing.nodes
            if isinstance(node, ActionNode) and node.designator is parking
        ]
        node.status = TaskStatus.RUNNING
        source.progress.follow_plan(performing, SHAPE_KEY, 2)

        result = ask(source, preset_named(source, "what is your current action?").code)

        assert [row["action_type"] for row in result.rows] == [ParkArmsAction.__name__]

    def test_every_action_performed_is_answered_with_how_it_went(self, source, scene):
        _, _, shape = scene
        source.progress.record_attempt(
            CompletedAttempt(
                shape_key=SHAPE_KEY,
                attempt_number=2,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=30),
                plan=sequential([ParkArmsAction(Arms.BOTH)]).plan,
                fell_through=True,
            )
        )

        result = ask(source, preset_named(source, "what actions did you perform?").code)

        [row] = result.rows
        assert row["action_type"] == ParkArmsAction.__name__
        assert row["status"] == TaskStatus.CREATED.name


# %% "give me all pick up events" — one question per type, recognized but not shown
class TestAskingForOneTypeOfThing:
    def test_a_question_is_written_out_for_every_event_a_record_is_written_for(
        self, source
    ):
        asked = [preset.text for preset in source.unlisted_presets()]

        assert "give me all pick up events" in asked
        assert "give me all insertion events" in asked

    def test_a_question_is_written_out_for_every_action_the_robot_carries_out(
        self, source
    ):
        asked = [preset.text for preset in source.unlisted_presets()]

        assert "give me all park arms actions" in asked

    def test_asking_for_one_kind_of_event_answers_with_only_that_kind(self, source):
        [preset] = [
            preset
            for preset in source.unlisted_presets()
            if preset.text == "give me all pick up events"
        ]

        result = ask_about_events(source, preset.code)

        assert [row["event_type"] for row in result.rows] == [PickUpEvent.__name__]

    def test_asking_for_a_kind_of_event_nothing_was_detected_of_answers_with_nothing(
        self, source
    ):
        [preset] = [
            preset
            for preset in source.unlisted_presets()
            if preset.text == "give me all containment events"
        ]

        assert ask_about_events(source, preset.code).count == 0

    def test_asking_for_one_kind_of_action_answers_with_only_that_kind(
        self, source, scene
    ):
        _, _, shape = scene
        source.progress.record_attempt(
            CompletedAttempt(
                shape_key=SHAPE_KEY,
                attempt_number=2,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=30),
                plan=sequential(
                    [ParkArmsAction(Arms.BOTH), MoveTorsoAction(TorsoState.HIGH)]
                ).plan,
                fell_through=True,
            )
        )
        [preset] = [
            preset
            for preset in source.unlisted_presets()
            if preset.text == "give me all park arms actions"
        ]

        result = ask(source, preset.code)

        assert [row["action_type"] for row in result.rows] == [ParkArmsAction.__name__]

    def test_a_written_out_question_is_about_the_knowledge_it_ranges_over(self, source):
        by_text = {preset.text: preset for preset in source.unlisted_presets()}

        assert by_text["give me all pick up events"].scope is QueryScope.DETECTED_EVENTS
        assert (
            by_text["give me all park arms actions"].scope is QueryScope.CURRENT_STATE
        )

    def test_none_of_them_crowds_the_buttons(self, source):
        shown = {preset.text for preset in source.presets()}

        assert shown.isdisjoint(preset.text for preset in source.unlisted_presets())


# %% asking these questions out loud
class TestRecognizingASpokenQuestion:
    """
    A spoken question is matched against every ready-made query the demo offers, the
    ones the panel shows and the ones it writes out per type alike, which is what the
    bridge hands the matcher.
    """

    @pytest.mark.parametrize(
        "asked, recognized",
        [
            ("what is your current goal", "what is your current goal?"),
            ("what is your current action", "what is your current action?"),
            ("what actions did you perform", "what actions did you perform?"),
            ("give me all pick up events", "give me all pick up events"),
            ("show me all insertion events", "give me all insertion events"),
            ("give me all pick up actions", "give me all pick up actions"),
            ("give me all park arms actions", "give me all park arms actions"),
        ],
    )
    def test_the_question_asked_is_the_question_run(self, source, asked, recognized):
        result = matcher_over(source).match(asked)

        assert result.matched
        assert result.preset.text == recognized


# %% the recorded bundle offers the same questions
class TestDeclaredBundlePresets:
    @pytest.mark.skipif(
        not DECLARED_PRESETS_PATH.exists(),
        reason="the checked-out cram-scenes submodule has no Franka_Montessori bundle",
    )
    def test_the_bundle_declares_exactly_these_presets(self):
        """
        The bundle's ``presets.json`` is what the viewer shows for the recorded scene, so
        it must not drift from the set the live demo answers.

        Skipped while the checked-out scenes submodule carries no Franka Montessori
        bundle; once one is published there, the sync is enforced again.
        """
        declared = json.loads(DECLARED_PRESETS_PATH.read_text())["presets"]

        assert declared == [
            {"text": preset.text, "code": preset.code, "scope": preset.scope.value}
            for preset in MONTESSORI_PRESETS
        ]
