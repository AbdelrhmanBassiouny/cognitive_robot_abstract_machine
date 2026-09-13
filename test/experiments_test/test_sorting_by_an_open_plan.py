"""
A sorting run that states the hole each piece goes through rather than looking it up
sorts every piece into the same hole as before, and says so as a statement the backends
answer.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.exceptions import NoMatchingHoleError
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY, KnownPiece
from experiments.montessori.world import BOARD_SCALE
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.open_slots.choice import backends_for
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.sorting import SortingByAnOpenPlan
from experiments.tracy_experiments.pickup.perceived_sorting import (
    Insertion,
    PerceivedSorting,
    ShapeSorter,
)
from krrood.entity_query_language.backends import BackendChoice
from semantic_digital_twin.spatial_types.spatial_types import Pose

from .dataset.scene_already_stood import SceneAlreadyStood

LID_AT = (0.8, 0.1, 0.96)
"""
Where the board's lid stands, in metres.
"""

STOOD_AT = Pose.from_xyz_rpy(LID_AT[0], LID_AT[1], LID_AT[2] + 0.02)
"""
Where every piece below stands, just above the lid.
"""

SORTED_PIECES = (
    MontessoriShapeCategory.CUBE,
    MontessoriShapeCategory.CYLINDER,
    MontessoriShapeCategory.TRIANGULAR_PRISM,
)
"""
The pieces every run below sorts, one of each shape the board has a hole for.
"""


def twice_the_size_of(category: MontessoriShapeCategory) -> KnownPiece:
    """
    :param category: The shape the piece is.
    :return: A piece of that shape too big for any hole of this board.
    """
    piece = KNOWN_PIECE_BY_CATEGORY[category]
    return replace(piece, outline=piece.outline * 2.0)


class SorterThatDoesNothing(ShapeSorter):
    """
    A sorter standing in for the arm, so a run can be asked what it would do without
    anything being moved.
    """

    def sort(self, piece: MontessoriShape, insertion: Insertion) -> None:
        """
        :param piece: The piece that would be picked up.
        :param insertion: Where it would be let go.
        """


@pytest.fixture
def scene() -> SceneAlreadyStood:
    """
    A world holding the board and one piece of each sorted shape above its lid.
    """
    world = ImaginedWorld.copied_from(None)
    board = world.stand_board(
        DescribedBoard.of_layout(
            BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
        ),
        Pose.from_xyz_rpy(*LID_AT),
    )
    pieces = [
        world.spawn(
            KNOWN_PIECE_BY_CATEGORY[category],
            STOOD_AT,
        )
        for category in SORTED_PIECES
    ]
    return SceneAlreadyStood(world=world.world, board=board, pieces=pieces)


@pytest.fixture
def backends(scene: SceneAlreadyStood) -> BackendChoice:
    """
    The four backends a sorting plan is run with, over that world.
    """
    return backends_for(
        MontessoriPerceptionBackend(source=FixedScene(captured=MontessoriScene())),
        scene.world,
    )


# %% the hole each piece goes through


def test_every_piece_goes_through_the_hole_the_board_says_it_does(
    scene: SceneAlreadyStood, backends: BackendChoice
):
    """
    The statement says the same thing the board's own lookup does, so an open plan sorts
    a scene exactly as the plan that named the hole outright did.
    """
    asked = SortingByAnOpenPlan(
        scene=scene, sorter=SorterThatDoesNothing(), backends=backends
    )
    looked_up = PerceivedSorting(scene=scene, sorter=SorterThatDoesNothing())

    assert [asked.hole_for(piece) for piece in scene.pieces] == [
        looked_up.hole_for(piece) for piece in scene.pieces
    ]


def test_the_hole_is_the_one_the_rules_answered_with(
    scene: SceneAlreadyStood, backends: BackendChoice
):
    asked = SortingByAnOpenPlan(
        scene=scene, sorter=SorterThatDoesNothing(), backends=backends
    )

    asked.hole_for(scene.pieces[0])

    assert [type(answered.backend) for answered in backends.answered] == [
        HoleRulesBackend
    ]


def test_a_piece_no_hole_of_this_board_admits(
    scene: SceneAlreadyStood, backends: BackendChoice
):
    """
    The rules still say which shape of hole a piece that size belongs in, and no hole of
    that shape takes it, so the statement is answered by none -- which is the same
    refusal the board's own lookup makes.
    """
    world = ImaginedWorld(world=scene.world)
    too_big = world.spawn(twice_the_size_of(MontessoriShapeCategory.CUBE), STOOD_AT)
    asked = SortingByAnOpenPlan(
        scene=scene, sorter=SorterThatDoesNothing(), backends=backends
    )

    with pytest.raises(NoMatchingHoleError):
        asked.hole_for(too_big)


# %% where each piece is let go


def test_the_insertion_is_the_one_the_answered_hole_makes(
    scene: SceneAlreadyStood, backends: BackendChoice
):
    """
    Only which hole is meant is asked for; how far above it a piece is let go is the
    run's own arithmetic, and stays what it was.
    """
    asked = SortingByAnOpenPlan(
        scene=scene, sorter=SorterThatDoesNothing(), backends=backends
    )
    looked_up = PerceivedSorting(scene=scene, sorter=SorterThatDoesNothing())
    piece = scene.pieces[0]

    assert asked.insertion_for(piece) == looked_up.insertion_for(piece)
