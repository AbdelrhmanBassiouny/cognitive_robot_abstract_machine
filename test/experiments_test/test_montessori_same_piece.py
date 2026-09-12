"""
When two bodies are the same Montessori piece: the plan names the piece as the world the
robot believes holds it, the monitor as the world it watched holds it.
"""

from __future__ import annotations

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.world_entity import Body

from experiments.montessori.same_piece import SamePiece, kind_of
from experiments.montessori.semantics import (
    CubeShape,
    CylinderShape,
    MontessoriShape,
    MontessoriShapeCategory,
)

# %% worlds holding one piece each

BELIEVED_NAME = PrefixedName("cube_0", "perceived")
"""
What the world the robot believes calls the piece it perceived.
"""

WATCHED_NAME = PrefixedName("cube", "montessori")
"""
What the world the monitor watched calls the same piece.
"""


def a_world_holding(name: PrefixedName, kind: type[MontessoriShape] | None) -> Body:
    """
    A world of its own holding one body of the given name, held as a piece of the given
    kind or as no piece at all.

    :param name: What the body is called.
    :param kind: The kind of piece the world holds it as, or None for a bare body.
    :return: The body, standing in its world.
    """
    world = World()
    root = Body(name=PrefixedName("root", name.prefix))
    body = Body(name=name)
    with world.modify_world():
        world.add_body(root)
        world.add_connection(FixedConnection(parent=root, child=body))
        if kind is not None:
            world.add_semantic_annotation(kind(name=name, root=body))
    return body


# %% what kind of piece a body is


def test_a_body_its_world_holds_as_a_piece_has_that_kind() -> None:
    assert kind_of(a_world_holding(WATCHED_NAME, CubeShape)) is (
        MontessoriShapeCategory.CUBE
    )


def test_a_body_its_world_holds_as_no_piece_has_no_kind() -> None:
    assert kind_of(a_world_holding(WATCHED_NAME, None)) is None


# %% whether two bodies are one piece


def test_the_same_name_is_the_same_piece_whatever_the_worlds_hold() -> None:
    assert SamePiece().same(
        a_world_holding(WATCHED_NAME, None), a_world_holding(WATCHED_NAME, None)
    )


def test_pieces_of_one_kind_under_different_names_are_the_same_piece() -> None:
    assert SamePiece().same(
        a_world_holding(BELIEVED_NAME, CubeShape),
        a_world_holding(WATCHED_NAME, CubeShape),
    )


def test_pieces_of_different_kinds_are_not_the_same_piece() -> None:
    assert not SamePiece().same(
        a_world_holding(BELIEVED_NAME, CubeShape),
        a_world_holding(WATCHED_NAME, CylinderShape),
    )


def test_a_bare_body_is_not_the_same_piece_as_any_piece() -> None:
    assert not SamePiece().same(
        a_world_holding(BELIEVED_NAME, None),
        a_world_holding(WATCHED_NAME, CubeShape),
    )
