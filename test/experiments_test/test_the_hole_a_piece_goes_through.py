"""
Which hole a piece goes through is knowledge about this board rather than geometry
anything can be read off, so it is concluded by rules stated over the piece -- and a
piece the rules get wrong is answered by adding a rule.

Which piece is read off the statement the description of the hole is handed over by,
since that is what says what the hole is for -- and a hole described for anything but an
insertion is not these rules' to answer.
"""

from __future__ import annotations

import pytest

from coraplex.robot_plans.actions.core.insertion import InsertionAction
from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.world import BOARD_SCALE
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.open_slots.holes import HoleRulesBackend
from krrood.entity_query_language.factories import a, an
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.spatial_types.spatial_types import Pose

from .dataset.piece_as_a_look_found_it import PieceAsALookFoundIt
from .dataset.putting_a_piece_through import PuttingAPieceThrough

LID_AT = (0.8, 0.1, 0.96)
"""
Where the board's lid stands, in metres, which is a place on the table of a scene.
"""


@pytest.fixture
def scene() -> ImaginedWorld:
    """
    A world holding the board and one cube standing on its lid.
    """
    world = ImaginedWorld.copied_from(None)
    world.stand_board(
        DescribedBoard.of_layout(
            BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
        ),
        Pose.from_xyz_rpy(*LID_AT),
    )
    world.spawn(
        KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE],
        Pose.from_xyz_rpy(LID_AT[0], LID_AT[1], LID_AT[2] + 0.02),
    )
    return world


def board_of(scene: ImaginedWorld) -> ShapeSortingBoard:
    """
    :param scene: The world the board stands in.
    """
    return scene.world.get_semantic_annotations_by_type(ShapeSortingBoard)[0]


def piece_of(scene: ImaginedWorld) -> MontessoriShape:
    """
    :param scene: The world the piece stands in.
    """
    return scene.world.get_semantic_annotations_by_type(MontessoriShape)[0]


def hole_wanted_for(piece: MontessoriShape, board: ShapeSortingBoard) -> Match:
    """
    A statement asking for the hole one piece goes through, out of the ones the board
    has, with the shape of that hole left for the rules to conclude.

    The hole is stated as the target of an insertion of that piece, which is what says
    what the hole is wanted for; the description of the hole itself says nothing about
    the piece.

    :param piece: The piece being sorted.
    :param board: The board it is sorted into.
    """
    hole = a(ShapeSortingHole)(shape_category=...).from_(board.apertures)
    an(InsertionAction)(object_designator=piece.root, target=hole)
    return hole


# %% what this backend says it can answer


def test_a_statement_asking_for_the_hole_one_piece_goes_through(scene: ImaginedWorld):
    backend = HoleRulesBackend(world=scene.world)

    assert backend.capability(hole_wanted_for(piece_of(scene), board_of(scene))) is True


def test_a_statement_that_already_says_the_shape_of_the_hole(scene: ImaginedWorld):
    """
    There is nothing left for the rules to conclude, so the hole is selected out of the
    world rather than decided here.
    """
    backend = HoleRulesBackend(world=scene.world)
    board = board_of(scene)
    hole = a(ShapeSortingHole)(shape_category=MontessoriShapeCategory.CUBE).from_(
        board.apertures
    )
    an(InsertionAction)(object_designator=piece_of(scene).root, target=hole)

    assert backend.capability(hole) is False


def test_a_hole_described_for_anything_but_an_insertion(scene: ImaginedWorld):
    """
    These rules answer the hole a piece is to be put through, which is what an insertion
    states its target to; a hole described for something else is described for something
    else.
    """
    backend = HoleRulesBackend(world=scene.world)
    hole = a(ShapeSortingHole)(shape_category=...).from_(board_of(scene).apertures)
    a(PuttingAPieceThrough)(piece=piece_of(scene).root, hole=hole)

    assert backend.capability(hole) is False


def test_a_statement_naming_no_piece_at_all(scene: ImaginedWorld):
    backend = HoleRulesBackend(world=scene.world)

    statement = a(ShapeSortingHole)(shape_category=...).from_(board_of(scene).apertures)

    assert backend.capability(statement) is False


# %% what it answers with


def test_the_hole_a_piece_goes_through_is_the_one_shaped_like_it(scene: ImaginedWorld):
    backend = HoleRulesBackend(world=scene.world)
    piece = piece_of(scene)

    answers = list(backend.evaluate(hole_wanted_for(piece, board_of(scene))))

    assert [hole.shape_category for hole in answers] == [piece.shape_category]


def test_the_hole_it_answers_with_is_one_the_board_has(scene: ImaginedWorld):
    backend = HoleRulesBackend(world=scene.world)
    board = board_of(scene)

    answers = list(backend.evaluate(hole_wanted_for(piece_of(scene), board)))

    assert all(hole in board.apertures for hole in answers)


# %% correcting them


def test_a_piece_the_rules_get_wrong_is_answered_by_adding_a_rule(scene: ImaginedWorld):
    """
    Which shape of hole a piece belongs in is knowledge, so it is corrected by stating
    the case the rules got wrong rather than by rewriting the rules already stated -- and
    the statement is answered by the hole the correction names from then on.
    """
    backend = HoleRulesBackend(world=scene.world)
    piece = piece_of(scene)
    board = board_of(scene)

    backend.rules.add_rule(piece, MontessoriShapeCategory.RECTANGULAR_PRISM)

    answers = list(backend.evaluate(hole_wanted_for(piece, board)))
    assert [hole.shape_category for hole in answers] == [
        MontessoriShapeCategory.RECTANGULAR_PRISM
    ]


# %% which piece a statement is handed over for


def test_the_piece_is_read_off_the_statement_the_hole_is_stated_inside(
    scene: ImaginedWorld,
):
    """
    The description of the hole says nothing about any piece; what it is for is what the
    statement handing it over says.
    """
    backend = HoleRulesBackend(world=scene.world)
    piece = piece_of(scene)
    hole = a(ShapeSortingHole)(shape_category=...).from_(board_of(scene).apertures)
    an(InsertionAction)(object_designator=piece.root, target=hole)

    assert backend.piece_the_hole_is_wanted_for(hole) is piece


def test_a_statement_naming_the_piece_itself_says_so_just_as_well(
    scene: ImaginedWorld,
):
    """
    A statement can name the piece as the world holds it rather than the body it stands
    on, and it is the same piece either way.
    """
    backend = HoleRulesBackend(world=scene.world)
    piece = piece_of(scene)

    assert backend.piece_standing_for(piece) is piece
    assert backend.piece_standing_for(piece.root) is piece


def test_a_role_of_the_piece_stands_for_the_piece_it_is_a_role_of(
    scene: ImaginedWorld,
):
    """
    What a look answers with is a role of the piece rather than the piece, and a hole
    wanted for it is wanted for the piece behind it.
    """
    backend = HoleRulesBackend(world=scene.world)
    piece = piece_of(scene)

    assert backend.piece_standing_for(PieceAsALookFoundIt(role_taker=piece)) is piece
