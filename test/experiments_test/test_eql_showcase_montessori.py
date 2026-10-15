"""
Tests for Tracy sorting the Montessori pieces its camera saw into the holes cut for them,
leaving the arm, the grasp and the hole open for the robot to resolve.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.plans.underspecified import CandidateOutcome, UnderspecifiedNode
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from experiments.eql_showcase.montessori_demo import (
    DEFAULT_CAPTURE,
    RELEASE_CLEARANCE,
    MontessoriSorting,
    TracyMontessoriDemonstration,
)
from experiments.eql_showcase.falling import FallIntoHolesExecutable
from experiments.eql_showcase.open_slots import (
    AnsweredWhenAsked,
    Faculty,
    GraspSideModel,
    Insertion,
    SideGrasp,
)
from experiments.eql_showcase.perceived_twin import SeenPiece
from experiments.montessori.world import _HOLE_FOOTPRINTS
from krrood.entity_query_language.backends import EntityQueryLanguageGenerativeBackend
from krrood.entity_query_language.factories import a, an, variable
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.world_description.geometry import Mesh
from experiments.eql_showcase.perception_demo import PerceptionShowcase
from semantic_digital_twin.robots.tracy import Tracy

from ..conftest import SAMPLING_SEED

PLACEMENT_TOLERANCE = 0.001
"""
How far from its release point a placed piece may come to rest, in metres.
"""


@pytest.fixture(scope="module")
def looked() -> PerceptionShowcase:
    """
    Tracy's twin holding what the camera saw in the default capture.
    """
    look = PerceptionShowcase(bridge=None)
    look.commit(DEFAULT_CAPTURE)
    return look


@pytest.fixture
def sorting(looked: PerceptionShowcase) -> MontessoriSorting:
    """
    What builds sorting plans for the pieces Tracy saw.
    """
    [robot] = looked.twin.world.get_semantic_annotations_by_type(Tracy)
    return MontessoriSorting(twin=looked.twin, robot=robot)


# %% which pieces go where


def test_every_hole_seen_is_kept_with_the_kind_it_is_cut_for(
    looked: PerceptionShowcase,
):
    assert [hole.region for hole in looked.twin.holes] == looked.twin.world.regions


def test_only_pieces_with_a_hole_of_their_shape_are_sorted(
    sorting: MontessoriSorting,
):
    seen = sorting.twin.world.get_semantic_annotations_by_type(SeenPiece)
    hole_kinds = {hole.kind for hole in sorting.twin.holes}

    assert sorting.pieces() == [piece for piece in seen if piece.kind in hole_kinds]


def test_a_piece_is_released_just_above_the_lid_over_each_hole_of_its_shape(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()
    [box] = piece.root.collision.shapes
    holes = sorting.holes_for(piece)

    poses = sorting.release_poses(piece)

    assert [pose.position.to_np()[:3].tolist() for pose in poses] == [
        [
            *hole.region.global_pose.position.to_np()[:2].tolist(),
            hole.lid_height + box.scale.z / 2 + RELEASE_CLEARANCE,
        ]
        for hole in holes
    ]


# %% resolving what the plan left open


def test_inserting_a_piece_resolves_the_open_grasp_arm_and_hole(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()
    context = Context(sorting.twin.world, sorting.robot, sampling_seed=SAMPLING_SEED)
    plan = sequential([sorting.insert(piece.kind)], context=context).plan

    with kinematically_simulated_robot:
        plan.perform()

    resolved = {
        node.designator_type: node.candidate_trials[-1]
        for node in plan.plan_graph.nodes()
        if isinstance(node, UnderspecifiedNode)
    }
    [release] = [
        pose
        for pose in sorting.release_poses(piece)
        if np.allclose(
            pose.position.to_np(),
            resolved[PlaceAction].action.target_location.position.to_np(),
        )
    ]
    assert set(resolved) == {PickUpAction, PlaceAction}
    assert all(
        trial.outcome is CandidateOutcome.ACCEPTED for trial in resolved.values()
    )
    assert np.allclose(
        piece.root.global_pose.position.to_np()[:2],
        release.position.to_np()[:2],
        atol=PLACEMENT_TOLERANCE,
    )


@pytest.fixture
def unsorted() -> MontessoriSorting:
    """
    What builds sorting plans for a fresh look, whose pieces lie where the camera saw
    them.
    """
    look = PerceptionShowcase(bridge=None)
    look.commit(DEFAULT_CAPTURE)
    [robot] = look.twin.world.get_semantic_annotations_by_type(Tracy)
    return MontessoriSorting(twin=look.twin, robot=robot)


def test_taking_a_piece_out_puts_it_back_where_the_camera_saw_it(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    home = unsorted.homes[piece].position.to_np()[:2]
    context = Context(unsorted.twin.world, unsorted.robot, sampling_seed=SAMPLING_SEED)
    plan = sequential(
        [unsorted.insert(piece.kind), unsorted.take_out(piece.kind)], context=context
    ).plan

    with kinematically_simulated_robot:
        plan.perform()

    assert np.allclose(
        piece.root.global_pose.position.to_np()[:2], home, atol=PLACEMENT_TOLERANCE
    )


# %% who answers what the plan left open


@dataclass
class AnswerAskedForLater:
    """
    A thing built from an answer that is asked for only while it is being built.
    """

    answer: type
    """
    The answer.
    """


STEP = "sort a piece"
"""
The step every statement of these tests is asked in.
"""


def test_which_pieces_there_are_is_answered_by_what_the_camera_saw(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()

    answers = sorting.answerer.answer(
        STEP, "which piece", a(SeenPiece)(kind=piece.kind)
    )

    assert answers == [seen for seen in sorting.pieces() if seen.kind is piece.kind]
    assert sorting.answerer.answered[-1].faculty is Faculty.PERCEPTION


def test_whether_a_piece_rests_on_the_table_is_read_off_the_twin(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    resting = a(SeenPiece)(kind=piece.kind).from_([piece])
    resting.where(SupportedBy(resting.root, unsorted.twin.table))

    answers = unsorted.answerer.answer(STEP, "does it rest on the table", resting)

    assert answers == [piece]
    assert unsorted.answerer.answered[-1].faculty is Faculty.WORKING_MEMORY


def test_the_hole_a_piece_goes_into_is_concluded_by_the_rules(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()

    answers = sorting.answerer.answer(
        STEP, "which hole", an(Insertion)(piece=piece, hole=...)
    )

    assert [insertion.hole for insertion in answers] == sorting.holes_for(piece)
    assert sorting.answerer.answered[-1].faculty is Faculty.RULES


def test_the_rules_conclude_a_hole_while_another_query_is_being_answered(
    sorting: MontessoriSorting,
):
    """
    A plan's open part is answered while the plan's own query generates its
    candidates, so the rules are evaluated inside that query's evaluation.
    """
    [piece, *_] = sorting.pieces()
    rules = sorting.answerer.backend_for(an(Insertion)(piece=piece, hole=...))

    [concluded] = EntityQueryLanguageGenerativeBackend().evaluate(
        a(AnswerAskedForLater)(
            answer=variable(
                type,
                domain=AnsweredWhenAsked(lambda: iter([rules.concluded_kind(piece)])),
            )
        )
    )

    assert concluded.answer is piece.kind


def test_the_side_a_piece_is_taken_from_is_sampled_most_likely_first(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()
    weights = GraspSideModel(piece=piece).weights()

    answers = sorting.answerer.answer(
        STEP, "which side", a(SideGrasp)(side=..., piece=piece)
    )

    likelihoods = [weights[answer.side] for answer in answers]
    assert likelihoods == sorted(likelihoods, reverse=True)
    assert sorting.answerer.answered[-1].faculty is Faculty.PROBABILISTIC


# %% the board and its holes


def test_the_board_is_drawn_with_its_holes_cut_through(looked: PerceptionShowcase):
    [board] = [body for body in looked.twin.committed if body.name.name == "board"]

    [drawn] = board.visual.shapes

    assert isinstance(drawn, Mesh)
    assert drawn.mesh.euler_number < 2


def test_a_seen_hole_lies_where_the_board_has_a_hole_of_its_kind(
    looked: PerceptionShowcase,
):
    [board] = [body for body in looked.twin.committed if body.name.name == "board"]
    board_from_world = board.global_transform.inverse().to_np()

    for hole in looked.twin.holes:
        center = (board_from_world @ hole.region.global_transform.to_np())[:2, 3]
        assert any(
            footprint.category is hole.kind
            and footprint.boundary.bounding_box.min_x
            <= center[0] - footprint.center.to_np()[0]
            <= footprint.boundary.bounding_box.max_x
            for footprint in _HOLE_FOOTPRINTS
        )


def test_a_piece_released_over_a_hole_falls_into_it(unsorted: MontessoriSorting):
    [piece, *_] = unsorted.pieces()
    [hole, *_] = unsorted.holes_for(piece)
    connection = piece.root.parent_connection
    connection.origin = unsorted.release_pose(piece, hole).homogeneous_matrix

    FallIntoHolesExecutable(
        context=Context(unsorted.twin.world, unsorted.robot),
        twin=unsorted.twin,
        seconds=0,
    ).execute()

    assert InsideRegion(piece.root, hole.region)()


def test_a_command_keeps_the_answers_of_the_sorting_before_it():
    demonstration = TracyMontessoriDemonstration(takes_commands=False)
    world = demonstration.build_simulated_world()
    demonstration.build_context(world)
    sorting = demonstration.sorting

    demonstration.build_context(world)

    assert demonstration.sorting is sorting


def test_an_answer_is_shown_by_what_it_asks_and_where(sorting: MontessoriSorting):
    [piece, *_] = sorting.pieces()

    sorting.answerer.answer(STEP, "which piece", a(SeenPiece)(kind=piece.kind))

    assert sorting.answerer.answered[-1].name == f"which piece · {STEP}"
