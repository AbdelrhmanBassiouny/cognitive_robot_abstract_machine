"""
The plan the framework figure shows, run as it is written: every slot it leaves open
closed by the backend that can answer it.

The look is taken at a rendered scene rather than through a camera, so what the plan
resolves to can be asserted without a robot or a simulation.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import (
    DetectedMontessoriShape,
    MontessoriScene,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import BOARD_SCALE
from experiments.open_slots.choice import backends_for
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.plan import PIECE_COLOR, SORTED_PIECE, sorting_plan
from krrood.entity_query_language.backends import BackendChoice, ProbabilisticBackend
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

from .dataset import montessori_scene_fixtures

pytest_plugins = [montessori_scene_fixtures.__name__]
"""
The rendered scene and the pipeline that reads it.
"""

BOARD_STANDS_AT = Pose.from_xyz_rpy(0.8, 0.1, 0.96)
"""
Where the board's lid stands, in metres.
"""

PICK_ARM = Arms.LEFT
"""
The arm the plan below picks the piece up with.
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
def grounded(board: ShapeSortingBoard, lid: Body, backends: BackendChoice) -> list:
    """
    The plan's actions, with everything it leaves open answered.
    """
    plan = sorting_plan(board, lid, PICK_ARM, end_effector=None)
    return next(plan.grounded_by(backends))


# %% what the plan leaves open


def test_it_leaves_open_the_piece_the_grasp_and_the_hole(
    board: ShapeSortingBoard, lid: Body
):
    """
    Whether the piece is where the plan needs it is stated as a condition on the piece
    rather than as a fourth description, so the look reads it in the world it stood the
    piece in.
    """
    plan = sorting_plan(board, lid, PICK_ARM, end_effector=None)

    assert [open_slot._type_ for open_slot in plan.open_descriptions] == [
        DetectedMontessoriShape,
        GraspDescription,
        ShapeSortingHole,
    ]


# %% what answers each of them


def test_the_piece_it_picks_up_is_the_one_the_look_found(grounded: list):
    [picking_up, _] = grounded

    assert isinstance(picking_up, PickUpAction)
    assert picking_up.object_designator.category is SORTED_PIECE
    assert picking_up.object_designator.role_taker.root.visual[0].color == PIECE_COLOR


def test_the_piece_it_puts_through_is_the_piece_it_picked_up(grounded: list):
    """
    Both actions state the one description, so the piece put through the hole is the
    piece picked up rather than a second answer to the same question.
    """
    [picking_up, putting_through] = grounded

    assert isinstance(putting_through, InsertionAction)
    assert putting_through.object_designator is picking_up.object_designator


def test_the_hole_it_puts_the_piece_through_is_the_one_shaped_like_it(grounded: list):
    [_, putting_through] = grounded

    assert putting_through.target.shape_category is SORTED_PIECE


def test_the_grasp_it_takes_hold_with_is_one_of_the_arm_it_uses(grounded: list):
    [picking_up, _] = grounded

    assert isinstance(picking_up.grasp_description, GraspDescription)
    assert picking_up.arm is PICK_ARM


def test_each_slot_is_answered_by_the_backend_that_can(
    grounded: list, backends: BackendChoice
):
    assert [
        (type(answered.backend), answered.statement._type_)
        for answered in backends.answered
    ] == [
        (MontessoriPerceptionBackend, DetectedMontessoriShape),
        (ProbabilisticBackend, GraspDescription),
        (HoleRulesBackend, ShapeSortingHole),
    ]
