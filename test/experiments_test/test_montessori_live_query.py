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
from coraplex.plans.failures import BodyUnfetchable
from segmind.datastructures.events import (
    InsertionEvent,
    LossOfContactEvent,
    PickUpEvent,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from cramera.body_geometry import pose_label
from cramera.knowledge.query_runner import EqlQueryRunner
from cramera.knowledge.queryable_knowledge import QueryScope
from cramera.knowledge.replay import ReplayWindow
from experiments.montessori.insertion_diagnosis import InsertionFailureReason
from experiments.montessori.live_query_source import (
    MONTESSORI_PRESETS,
    MontessoriLiveQuerySource,
)
from experiments.montessori.scene_layout import SceneLayout
from experiments.montessori.semantics import SHAPE_NAME_SUFFIX
from experiments.montessori.sorting_progress import CompletedAttempt, SortingProgress

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
            "event",
            "hole",
            "board",
            "goal",
        ]

    def test_every_preset_runs(self, source):
        for preset in source.presets():
            assert ask(source, preset.code).ok, preset.text


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
        result = ask(
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


# %% "show me what happened" — a detected event replays the demo around itself
class TestReplayingADetectedEvent:
    """
    An answer row naming a segmind detection carries the recording window to replay
    around it, leading and trailing the detection by the fixed shifts.
    """

    def test_an_event_row_carries_the_window_around_its_detection(self, source):
        result = ask(source, "an(entity(event))")

        assert result.replay == [ReplayWindow.around(STARTED_AT)]

    def test_the_what_was_detected_preset_offers_a_replay_per_detection(self, source):
        [preset] = [
            offered
            for offered in source.presets()
            if offered.text == "what was detected, and when?"
        ]

        result = ask(source, preset.code)

        assert result.replay == [ReplayWindow.around(STARTED_AT)]


# %% the recorded bundle offers the same questions
class TestDeclaredBundlePresets:
    def test_the_bundle_declares_exactly_these_presets(self):
        """
        The bundle's ``presets.json`` is what the viewer shows for the recorded scene, so
        it must not drift from the set the live demo answers.
        """
        declared = json.loads(DECLARED_PRESETS_PATH.read_text())["presets"]

        assert declared == [
            {"text": preset.text, "code": preset.code, "scope": preset.scope.value}
            for preset in MONTESSORI_PRESETS
        ]
