"""
The framework figure's plan, grounded against a look at a rendered scene.

No robot and no simulation: the look is taken at a rendered picture, so what the plan
comes to can be asserted anywhere, and the same grounding serves both the tests about
what the plan resolves to and the tests about what carries it out.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.enums import Arms
from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.pieces import KnownPieceSet
from experiments.montessori.semantics import ShapeSortingBoard
from experiments.montessori.world import BOARD_SCALE
from experiments.open_slots.choice import backends_for
from experiments.open_slots.plan import sorting_plan
from krrood.entity_query_language.backends import BackendChoice
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

BOARD_STANDS_AT = Pose.from_xyz_rpy(0.8, 0.1, 0.96)
"""
Where the board's lid stands, in metres.
"""

PICK_ARM = Arms.LEFT
"""
The arm the plan picks the piece up with.
"""


@pytest.fixture
def board() -> ShapeSortingBoard:
    """
    The board the plan puts its piece into, with one hole per shape.
    """
    return ImaginedWorld.copied_from(None).stand_board(
        DescribedBoard.of_layout(
            BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
        ),
        BOARD_STANDS_AT,
    )


@pytest.fixture
def lid(pipeline: MontessoriPerceptionPipeline) -> Body:
    """
    The board's lid, as the surface the look searches names it.
    """
    return pipeline.lid.entity


@pytest.fixture
def pieces(pipeline: MontessoriPerceptionPipeline) -> KnownPieceSet:
    """
    The set of loose pieces the look this plan is run against was fitted with.
    """
    return pipeline.pieces


@pytest.fixture
def backends(scene_with_a_piece_on_the_lid: MontessoriScene) -> BackendChoice:
    """
    The four backends the plan is run with, over the world the look stood its findings
    in.
    """
    return backends_for(
        MontessoriPerceptionBackend(
            source=FixedScene(captured=scene_with_a_piece_on_the_lid)
        ),
        scene_with_a_piece_on_the_lid.imagined.world,
    )


@pytest.fixture
def grounded(
    board: ShapeSortingBoard,
    lid: Body,
    pieces: KnownPieceSet,
    backends: BackendChoice,
) -> list:
    """
    The plan's actions, with everything it leaves open answered.
    """
    plan = sorting_plan(board, lid, pieces, PICK_ARM, end_effector=None)
    return next(plan.grounded_by(backends))
