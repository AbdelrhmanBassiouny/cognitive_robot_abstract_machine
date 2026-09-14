"""
The plan the framework figure shows, run as it is written: every slot it leaves open
closed by the backend that can answer it.

The look is taken at a rendered scene rather than through a camera, and at a shipped
capture of the lab table for the run that has the robot's own world hold what was found,
so what the plan resolves to can be asserted without a robot or a simulation.
"""

from __future__ import annotations

import itertools

import pytest

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    DetectedMontessoriShape,
    MontessoriScene,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    lab_board,
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.perception.scene_source import FixedScene, RecordedFrame
from experiments.montessori.pieces import KnownPieceSet
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import BOARD_SCALE
from experiments.open_slots.choice import backends_for
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.plan import FROM_ABOVE, SORTED_PIECE, sorting_plan
from experiments.tracy_experiments.pick_and_place_action import (
    ActuatorDrivenAction,
    InsertionActionMujoco,
    NoActionCarriesItOut,
    PickUpActionMujoco,
)
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

GRASPS_LOOKED_AT = 12
"""
How many of the ways the plan can be grounded the grasp is read off, which is enough
for every side of the piece to have been sampled several times over.
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
def pieces(pipeline: MontessoriPerceptionPipeline) -> KnownPieceSet:
    """
    The set of loose pieces the look this plan is run against was fitted with.
    """
    return pipeline.pieces


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


# %% what the plan leaves open


def test_it_leaves_open_the_piece_the_grasp_and_the_hole(
    board: ShapeSortingBoard, lid: Body, pieces: KnownPieceSet
):
    """
    Whether the piece is where the plan needs it is stated as a condition on the piece
    rather than as a fourth description, so the look reads it in the world it stood the
    piece in.
    """
    plan = sorting_plan(board, lid, pieces, PICK_ARM, end_effector=None)

    assert [open_slot._type_ for open_slot in plan.open_descriptions] == [
        DetectedMontessoriShape,
        GraspDescription,
        ShapeSortingHole,
    ]


# %% what answers each of them


def test_the_piece_it_picks_up_is_the_one_the_look_found(
    grounded: list, pieces: KnownPieceSet
):
    [picking_up, _] = grounded

    assert isinstance(picking_up, PickUpAction)
    assert picking_up.object_designator.category is SORTED_PIECE
    assert (
        picking_up.object_designator.role_taker.root.visual[0].color
        == pieces.by_category[SORTED_PIECE].color
    )


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


# %% the piece it picks up is one the robot's own world holds


CAPTURE_OF_THE_LAB_TABLE = "displaced_cube_from_hole"
"""
A capture of the lab table with loose pieces on it and the cube on the board's lid, the
way the sorting demo starts them.
"""


@pytest.fixture
def perceived_lab() -> PerceivedScene:
    """
    The lab as one look at that capture leaves it: the board and the loose pieces stood
    in the world the robot plans in.
    """
    world = recorded_world()
    scene = PerceivedScene(
        world=world,
        look=RecordedFrame(
            pipeline=perception_pipeline(world=world),
            frame=SceneCapture.load(CAPTURE_OF_THE_LAB_TABLE).to_frame(),
        ),
        described_board=lab_board(),
    )
    scene.perceive()
    return scene


def test_the_piece_it_picks_up_is_one_the_world_the_robot_plans_in_holds(
    perceived_lab: PerceivedScene,
) -> None:
    """
    A plan that grounds to a body standing only in a world of the look's own is a plan
    no arm can be driven by, so the piece both actions act on is the piece the world the
    robot plans in holds.
    """
    plan = sorting_plan(
        perceived_lab.board,
        perceived_lab.look.pipeline.lid.entity,
        perceived_lab.look.pipeline.pieces,
        PICK_ARM,
        end_effector=None,
    )
    backends = backends_for(
        MontessoriPerceptionBackend(source=perceived_lab.last_look),
        perceived_lab.world,
    )

    [picking_up, putting_through] = next(plan.grounded_by(backends))

    picked_up = picking_up.object_designator
    assert picked_up is putting_through.object_designator
    assert any(piece is picked_up.role_taker for piece in perceived_lab.pieces)
    assert picked_up.role_taker.shape_category is SORTED_PIECE
    assert picked_up.root in perceived_lab.world.bodies


# %% what carries the resolved plan out


def test_every_grasp_it_grounds_to_comes_down_on_the_piece(
    board: ShapeSortingBoard,
    lid: Body,
    pieces: KnownPieceSet,
    backends: BackendChoice,
) -> None:
    """
    A piece resting on a surface offers the fingers nothing but its top, so a grasp the
    plan grounds to that came at it from the side or from underneath is one no arm could
    carry out.
    """
    plan = sorting_plan(board, lid, pieces, PICK_ARM, end_effector=None)

    grounded = itertools.islice(plan.grounded_by(backends), GRASPS_LOOKED_AT)

    assert [
        picking_up.grasp_description.vertical_alignment for picking_up, _ in grounded
    ] == [FROM_ABOVE] * GRASPS_LOOKED_AT


def test_the_grasp_it_puts_the_piece_through_the_hole_with_is_the_one_it_took_hold_with(
    grounded: list,
) -> None:
    """
    Both actions state the one grasp, so the piece is let go of held the way it was
    picked up rather than turned on the way.
    """
    [picking_up, putting_through] = grounded

    assert putting_through.grasp_description is picking_up.grasp_description


def test_the_resolved_plan_is_carried_out_by_the_actions_that_drive_the_actuators(
    grounded: list,
) -> None:
    """
    The plan is written in the words a plan is written in; what runs it here is the
    family that commands the lab's own actuators, and it is found from the plan rather
    than named by it.
    """
    [picking_up, putting_through] = grounded

    [takes_hold, puts_through] = ActuatorDrivenAction.performing(
        grounded, simulation=None, actuators={}
    )

    assert isinstance(takes_hold, PickUpActionMujoco)
    assert isinstance(puts_through, InsertionActionMujoco)
    assert takes_hold.object_designator is picking_up.object_designator.root
    assert puts_through.object_designator is takes_hold.object_designator
    assert takes_hold.grasp_description is picking_up.grasp_description
    assert puts_through.target is putting_through.target


def test_an_action_nothing_here_carries_out_is_refused(grounded: list) -> None:
    """
    A plan stating an action the lab cannot run says so, rather than running the rest of
    it and leaving that one out.
    """
    [picking_up, _] = grounded
    reaching = ReachAction(
        target_pose=Pose(),
        arm=PICK_ARM,
        grasp_description=picking_up.grasp_description,
    )

    with pytest.raises(NoActionCarriesItOut):
        ActuatorDrivenAction.performing([reaching], simulation=None, actuators={})
