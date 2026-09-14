"""
A sorting plan states four things it does not supply, and each is answered by a
different faculty: the piece is looked for, where it stands is read off the world, the
hole it goes through is concluded by rules, and how to take hold of it is sampled.

What answers which is nowhere written into the plan -- every backend declares what it
can answer, and these tests pin which of them that leaves answering each slot.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import (
    DetectedMontessoriShape,
    MontessoriScene,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import BOARD_SCALE
from experiments.open_slots.choice import backends_for
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.world import WorldBackend
from krrood.entity_query_language.backends import BackendChoice, ProbabilisticBackend
from krrood.entity_query_language.exceptions import NoBackendAnswers
from krrood.entity_query_language.factories import a, an, entity, variable
from semantic_digital_twin.spatial_types.spatial_types import Pose

LID_AT = (0.8, 0.1, 0.96)
"""
Where the board's lid stands, in metres.
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


@pytest.fixture
def choice(scene: ImaginedWorld) -> BackendChoice:
    """
    The four backends a sorting plan is run with, over that world.
    """
    return backends_for(
        MontessoriPerceptionBackend(source=FixedScene(captured=MontessoriScene())),
        scene.world,
    )


def piece_of(scene: ImaginedWorld) -> MontessoriShape:
    """
    :param scene: The world the piece stands in.
    """
    return scene.world.get_semantic_annotations_by_type(MontessoriShape)[0]


def board_of(scene: ImaginedWorld) -> ShapeSortingBoard:
    """
    :param scene: The world the board stands in.
    """
    return scene.world.get_semantic_annotations_by_type(ShapeSortingBoard)[0]


# %% one slot each


def test_the_piece_to_pick_up_is_looked_for(choice: BackendChoice):
    statement = a(DetectedMontessoriShape)(category=MontessoriShapeCategory.CUBE)

    assert isinstance(choice.backend_for(statement), MontessoriPerceptionBackend)


def test_where_a_piece_the_world_holds_stands_is_read_off_the_world(
    choice: BackendChoice,
):
    assert isinstance(choice.backend_for(a(MontessoriShape)()), WorldBackend)


def test_the_hole_a_piece_goes_through_is_concluded_by_rules(
    choice: BackendChoice, scene: ImaginedWorld
):
    hole = a(ShapeSortingHole)(shape_category=...).from_(board_of(scene).apertures)
    an(InsertionAction)(object_designator=piece_of(scene).root, target=hole)

    assert isinstance(choice.backend_for(hole), HoleRulesBackend)


def test_how_to_take_hold_of_a_piece_is_sampled(choice: BackendChoice):
    statement = a(GraspDescription)(approach_direction=..., vertical_alignment=...)

    assert isinstance(choice.backend_for(statement), ProbabilisticBackend)


# %% a statement that is none of them


def test_a_statement_that_is_no_pattern_at_all_is_refused(choice: BackendChoice):
    """
    Every one of them answers a pattern and nothing else, so a query that selects from a
    domain is one this plan was given no means to answer.
    """
    with pytest.raises(NoBackendAnswers):
        choice.backend_for(entity(variable(MontessoriShape, domain=[])))
