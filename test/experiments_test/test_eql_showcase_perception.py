"""
Tests for the perception part of the EQL showcase: committing what the camera saw into a
digital twin, and asking the twin about it.
"""

from __future__ import annotations

import pytest

from cramera.knowledge.queryable_knowledge import QueryScope
from cramera.live.bridge import Bridge
from experiments.eql_showcase.perceived_twin import PerceivedTwin
from experiments.eql_showcase.perception_demo import (
    PerceptionShowcase,
    capture_names,
)
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.semantics import MontessoriShape
from semantic_digital_twin.world_description.connections import Connection6DoF

from .dataset import montessori_scene_fixtures
from .dataset.montessori_capture_truths import CAPTURE_TRUTHS

pytest_plugins = [montessori_scene_fixtures.__name__]
"""
The rendered scene and pipeline fixtures the tests below ask for by name.
"""

WHAT_DOES_THE_CAMERA_SEE = "What does the camera see?"
"""
The showcase's question naming every piece the look found.
"""

WHICH_PIECES_ON_THE_TABLE = "Which pieces did it find on the table?"
"""
The showcase's question naming the pieces the look found resting on the table.
"""


@pytest.fixture
def twin(pipeline: MontessoriPerceptionPipeline) -> PerceivedTwin:
    """
    An empty twin over the stretch of table the pipeline looks at.
    """
    return PerceivedTwin.on_bare_table(pipeline.region, pipeline.table_height)


def seen_pieces(twin: PerceivedTwin) -> list[MontessoriShape]:
    """
    The pieces the twin holds.

    :param twin: The twin to read.
    """
    return twin.world.get_semantic_annotations_by_type(MontessoriShape)


# %% committing a look


def test_every_piece_seen_becomes_a_body_of_its_kind(
    twin: PerceivedTwin, scene: MontessoriScene
):
    twin.commit(scene)

    assert sorted(type(piece).__name__ for piece in seen_pieces(twin)) == sorted(
        shape.category.__name__ for shape in scene.shapes
    )


def test_every_hole_seen_becomes_a_region(twin: PerceivedTwin, scene: MontessoriScene):
    twin.commit(scene)

    assert len(twin.world.regions) == len(scene.board.holes)


def test_a_new_look_replaces_the_previous_one(
    twin: PerceivedTwin, scene: MontessoriScene
):
    twin.commit(scene)

    twin.commit(MontessoriScene())

    assert seen_pieces(twin) == []
    assert twin.world.regions == []
    assert [body.name for body in twin.world.bodies] == [
        twin.root.name,
        twin.table.name,
    ]


def test_every_piece_seen_is_free_to_be_moved(
    twin: PerceivedTwin, scene: MontessoriScene
):
    twin.commit(scene)

    assert all(
        isinstance(piece.root.parent_connection, Connection6DoF)
        for piece in seen_pieces(twin)
    )


def test_a_piece_seen_on_the_table_rests_on_it(
    twin: PerceivedTwin, scene: MontessoriScene
):
    twin.commit(scene)
    bridge = Bridge()
    showcase = PerceptionShowcase(bridge=bridge, twin=twin)
    bridge.register_query_source([showcase.knowledge()], "", [])

    on_table = next(
        preset
        for preset in showcase.questions.presets([QueryScope.CURRENT_STATE])
        if preset.text == WHICH_PIECES_ON_THE_TABLE
    )
    answer = bridge.run_query(on_table.code, on_table.scope)

    assert sorted(row["__entity__"] for row in answer.rows) == sorted(
        str(piece.root.name) for piece in seen_pieces(twin)
    )


# %% the shipped captures


def test_every_shipped_capture_is_offered():
    assert capture_names() == sorted(CAPTURE_TRUTHS)


@pytest.mark.parametrize("capture_name", sorted(CAPTURE_TRUTHS))
def test_every_question_is_answered_about_every_capture(capture_name: str):
    bridge = Bridge()
    showcase = PerceptionShowcase(bridge=bridge)

    showcase.look_at(capture_name)

    failed = [
        preset.text
        for preset in bridge.query_presets()
        if not bridge.run_query(preset.code, preset.scope).ok
    ]
    assert failed == []


def test_the_camera_question_names_every_piece_of_the_look():
    bridge = Bridge()
    showcase = PerceptionShowcase(bridge=bridge)
    [capture_name, *_] = capture_names()
    showcase.look_at(capture_name)

    question = next(
        preset
        for preset in bridge.query_presets()
        if preset.text == WHAT_DOES_THE_CAMERA_SEE
    )
    answer = bridge.run_query(question.code, question.scope)

    assert sorted(row["__entity__"] for row in answer.rows) == sorted(
        str(piece.root.name) for piece in seen_pieces(showcase.twin)
    )
