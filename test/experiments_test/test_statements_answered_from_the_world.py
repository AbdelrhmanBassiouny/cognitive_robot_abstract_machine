"""
A statement about the things one world holds -- the pieces a look brought into it among
them -- is answered by selecting among them, and what it says about them is decided
against the world's own geometry.

Which world is the point: a world entity is a symbol, and the symbol graph a statement
over one falls back to is one per process, holding every entity ever made in it.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import (
    CubeShape,
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.open_slots.world import WorldBackend
from krrood.entity_query_language.factories import a
from semantic_digital_twin.reasoning.predicates import SupportedBy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

CUBE = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
"""
The piece standing on another below.
"""

CYLINDER = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CYLINDER]
"""
The piece it stands on.
"""

STANDS_AT = (0.58, 0.15)
"""
Where the two stand, in metres along the world frame's x and y axes.
"""

OVERLAP = 0.001
"""
How far the two are made to overlap vertically, in metres.

:class:`SupportedBy` reads support off boxes that meet, so two stood exactly face to
face touch without meeting at all.
"""


@pytest.fixture
def world_with_one_piece_on_another() -> ImaginedWorld:
    """
    A world holding a cylinder standing on the ground and a cube standing on it.
    """
    world = ImaginedWorld.copied_from(None)
    world.spawn(CYLINDER, stood_at(CYLINDER.height / 2))
    world.spawn(CUBE, stood_at(CYLINDER.height + CUBE.height / 2 - OVERLAP))
    return world


def stood_at(height: float) -> Pose:
    """
    :param height: How far the piece's centre stands above the ground, in metres.
    :return: Where it stands.
    """
    return Pose.from_xyz_rpy(*STANDS_AT, height)


# %% what this backend says it can answer


def test_a_statement_about_a_kind_of_thing_the_world_holds(
    world_with_one_piece_on_another: ImaginedWorld,
):
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    assert backend.capability(a(MontessoriShape)()) is True


def test_a_statement_about_a_kind_of_thing_the_world_holds_none_of(
    world_with_one_piece_on_another: ImaginedWorld,
):
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    assert backend.capability(a(ShapeSortingBoard)()) is False


def test_a_statement_about_a_kind_of_thing_that_is_no_annotation_at_all(
    world_with_one_piece_on_another: ImaginedWorld,
):
    """
    A world is more than what it is annotated with, and a statement about any of the
    rest of it is answered here too.
    """
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    assert backend.capability(a(Body)()) is True


def test_a_statement_left_open_is_refused_as_it_is_by_any_selective_backend(
    world_with_one_piece_on_another: ImaginedWorld,
):
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    assert backend.capability(a(MontessoriShape)(name=...)) is False


# %% what it answers with


def test_the_things_the_world_holds_of_that_kind_answer(
    world_with_one_piece_on_another: ImaginedWorld,
):
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    answers = list(backend.evaluate(a(MontessoriShape)()))

    assert [shape.shape_category for shape in answers] == [
        MontessoriShapeCategory.CYLINDER,
        MontessoriShapeCategory.CUBE,
    ]


def test_the_bodies_the_world_holds_answer_a_statement_about_bodies(
    world_with_one_piece_on_another: ImaginedWorld,
):
    backend = WorldBackend(world=world_with_one_piece_on_another.world)

    assert (
        list(backend.evaluate(a(Body)()))
        == world_with_one_piece_on_another.world.bodies
    )


def test_a_thing_standing_in_another_world_is_not_among_the_answers(
    world_with_one_piece_on_another: ImaginedWorld,
):
    """
    Both worlds' pieces are symbols of one process, so the symbol graph a statement over
    a world entity otherwise falls back to holds them both; this backend answers out of
    the world it was given.
    """
    backend = WorldBackend(world=world_with_one_piece_on_another.world)
    elsewhere = ImaginedWorld.copied_from(None)
    standing_in_another_world = elsewhere.spawn(CUBE, stood_at(CUBE.height / 2))

    answers = list(backend.evaluate(a(MontessoriShape)()))

    assert standing_in_another_world not in answers
    assert (
        answers
        == world_with_one_piece_on_another.world.get_semantic_annotations_by_type(
            MontessoriShape
        )
    )


def test_a_relation_the_world_decides_narrows_the_answer(
    world_with_one_piece_on_another: ImaginedWorld,
):
    """
    Which of the two rests on the other is read off their geometry, which is what makes
    this the world's answer to give rather than the look's.
    """
    backend = WorldBackend(world=world_with_one_piece_on_another.world)
    resting = a(MontessoriShape)()
    standing_on_it = a(MontessoriShape)()
    resting = resting.where(
        SupportedBy(resting.root, standing_on_it.root),
        standing_on_it.shape_category == MontessoriShapeCategory.CYLINDER,
    )

    assert [type(shape) for shape in backend.evaluate(resting)] == [CubeShape]
