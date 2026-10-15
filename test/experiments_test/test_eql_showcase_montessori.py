"""
Tests for Tracy sorting the Montessori pieces its camera saw into the holes cut for them,
the piece, side, arm and hole each resolved by a backend before the robot moves.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from experiments.eql_showcase.insertion import FallIntoHoleExecutable
from experiments.eql_showcase.montessori_demo import (
    DEFAULT_CAPTURE,
    MontessoriSorting,
    SortPieceAction,
    TracyMontessoriDemonstration,
)
from experiments.eql_showcase.open_slots import (
    Faculty,
    GraspSide,
    GraspSideModel,
    Insertion,
    PlanResolution,
    SideGrasp,
)
from experiments.eql_showcase.perceived_twin import SeenPiece
from experiments.montessori.world import _HOLE_FOOTPRINTS
from krrood.entity_query_language.backends import EntityQueryLanguageGenerativeBackend
from krrood.entity_query_language.factories import a, an, variable
from semantic_digital_twin.datastructures.definitions import StaticJointState
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
    return MontessoriSorting(twin=looked.twin, robot=robot, perception_view=looked.view)


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


def holes_for(sorting: MontessoriSorting, piece: SeenPiece) -> list:
    """
    The holes seen that are cut for a piece's kind.
    """
    return [hole for hole in sorting.twin.holes if hole.kind is piece.kind]


@pytest.fixture
def unsorted() -> MontessoriSorting:
    """
    What resolves sorting plans for a fresh look, whose pieces lie where the camera saw
    them, with Tracy's arms parked as the demonstration starts them.
    """
    demonstration = TracyMontessoriDemonstration(takes_commands=False)
    world = demonstration.build_simulated_world()
    [robot] = world.get_semantic_annotations_by_type(Tracy)
    return MontessoriSorting(
        twin=demonstration.look.twin,
        robot=robot,
        perception_view=demonstration.look.view,
    )


def test_a_piece_is_released_with_its_bottom_just_over_the_lid_above_its_hole(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    [box] = piece.root.collision.shapes
    action = unsorted.insert(piece.kind)

    released = action.release_pose().position.to_np()[:3]

    assert np.allclose(
        released,
        [
            *action.hole.region.global_pose.position.to_np()[:2],
            action.hole.lid_height + box.scale.z / 2 + action.release_clearance,
        ],
    )


# %% resolving before the robot moves


def test_a_sorting_plan_is_resolved_part_by_part_before_the_robot_moves(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    resting = piece.root.global_pose.position.to_np()

    action = unsorted.insert(piece.kind)

    [resolution] = unsorted.answerer.resolutions
    assert [part.faculty for part in resolution.parts] == [
        Faculty.PERCEPTION,
        Faculty.WORKING_MEMORY,
        Faculty.PROBABILISTIC,
        Faculty.WORKING_MEMORY,
        Faculty.RULES,
    ]
    assert resolution.done and resolution.plan is action
    assert np.allclose(piece.root.global_pose.position.to_np(), resting)


def test_a_resolved_sorting_puts_the_piece_into_its_hole(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    action = unsorted.insert(piece.kind)
    context = Context(unsorted.twin.world, unsorted.robot, sampling_seed=SAMPLING_SEED)
    plan = sequential([action], context=context).plan

    with kinematically_simulated_robot:
        plan.perform()

    assert action.piece is piece
    assert InsideRegion(piece.root, action.hole.region)()


def test_a_sorting_whose_piece_no_longer_rests_on_the_table_is_left_unresolved(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    [hole, *_] = holes_for(unsorted, piece)
    piece.root.parent_connection.origin = (
        SortPieceAction(
            piece=piece, side=..., arm=unsorted.robot.all_arms[0], hole=hole
        )
        .release_pose()
        .homogeneous_matrix
    )

    action = unsorted.insert(piece.kind)

    [resolution] = unsorted.answerer.resolutions
    assert action is None
    assert not resolution.executable
    assert resolution.parts[-1].answers == []


def test_any_statement_is_resolved_its_nested_statements_first(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()

    answers = unsorted.resolve(
        an(Insertion)(piece=a(SeenPiece)(kind=piece.kind), hole=...)
    )

    [resolution] = unsorted.answerer.resolutions
    assert [answer.hole for answer in answers] == holes_for(unsorted, piece)
    assert [part.faculty for part in resolution.parts] == [
        Faculty.PERCEPTION,
        Faculty.RULES,
    ]


def test_a_sorting_plan_stated_in_a_query_is_resolved_to_one_the_robot_can_do(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()

    [action] = unsorted.resolve(unsorted.statement_to_sort(piece.kind))

    assert isinstance(action, SortPieceAction)
    assert action.piece is piece
    assert unsorted.answerer.resolutions[-1].executable


def test_the_hand_comes_down_onto_a_piece_from_above(sorting: MontessoriSorting):
    [piece, *_] = sorting.pieces()

    grasp = SideGrasp(side=GraspSide.FRONT).candidate_on(piece)

    approach = grasp.grasp_pose.homogeneous_matrix.to_np()[:3, 0]
    assert np.allclose(approach, [0.0, 0.0, -1.0], atol=1e-6)


# %% who answers what the plan left open


@dataclass
class AnsweredLater:
    """
    Values produced only once a query iterates over them.
    """

    answers: object
    """
    Produces the values.
    """

    def __iter__(self):
        yield from self.answers()


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
What the resolution every statement of these tests is asked in is called.
"""


def resolution_of(sorting: MontessoriSorting) -> PlanResolution:
    """
    A resolution to ask the statements of a test in.
    """
    return sorting.answerer.begin(STEP, [], [])


def test_which_pieces_there_are_is_answered_by_what_the_camera_saw(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()

    answers = sorting.answerer.answer(
        resolution_of(sorting), "piece", "which piece", a(SeenPiece)(kind=piece.kind)
    )

    assert answers == [seen for seen in sorting.pieces() if seen.kind is piece.kind]
    assert sorting.answerer.answered[-1].faculty is Faculty.PERCEPTION


def test_whether_a_piece_rests_on_the_table_is_read_off_the_twin(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    resting = a(SeenPiece)(kind=piece.kind).from_([piece])
    resting.where(SupportedBy(resting.root, unsorted.twin.table))

    answers = unsorted.answerer.answer(
        resolution_of(unsorted), "piece-where", "does it rest on the table", resting
    )

    assert answers == [piece]
    assert unsorted.answerer.answered[-1].faculty is Faculty.WORKING_MEMORY


def test_the_hole_a_piece_goes_into_is_concluded_by_the_rules(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()

    answers = sorting.answerer.answer(
        resolution_of(sorting),
        "hole",
        "which hole",
        an(Insertion)(piece=piece, hole=...),
    )

    assert [insertion.hole for insertion in answers] == holes_for(sorting, piece)
    assert sorting.answerer.answered[-1].faculty is Faculty.RULES


def test_the_rules_conclude_a_hole_while_another_query_is_being_answered(
    sorting: MontessoriSorting,
):
    """
    A statement can be resolved while a query of the viewer's is being evaluated, so
    the rules are evaluated inside that query's evaluation.
    """
    [piece, *_] = sorting.pieces()
    rules = sorting.answerer.backend_for(an(Insertion)(piece=piece, hole=...))

    [concluded] = EntityQueryLanguageGenerativeBackend().evaluate(
        a(AnswerAskedForLater)(
            answer=variable(
                type,
                domain=AnsweredLater(lambda: iter([rules.concluded_kind(piece)])),
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
        resolution_of(sorting),
        "side",
        "which side",
        a(SideGrasp)(side=..., piece=piece),
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


def test_a_piece_let_go_over_its_hole_falls_into_it(unsorted: MontessoriSorting):
    [piece, *_] = unsorted.pieces()
    [hole, *_] = holes_for(unsorted, piece)
    piece.root.parent_connection.origin = (
        SortPieceAction(
            piece=piece, side=..., arm=unsorted.robot.all_arms[0], hole=hole
        )
        .release_pose()
        .homogeneous_matrix
    )

    FallIntoHoleExecutable(
        context=Context(unsorted.twin.world, unsorted.robot),
        piece=piece,
        hole=hole,
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

    sorting.answerer.answer(
        resolution_of(sorting), "piece", "which piece", a(SeenPiece)(kind=piece.kind)
    )

    assert sorting.answerer.answered[-1].name == f"which piece · {STEP}"


def test_perception_shows_the_pieces_it_found_on_the_camera_view(
    sorting: MontessoriSorting,
):
    [piece, *_] = sorting.pieces()

    sorting.answerer.answer(
        resolution_of(sorting), "piece", "which piece", a(SeenPiece)(kind=piece.kind)
    )

    drawn = sorting.answerer.answered[-1].reasoning.to_payload()
    assert drawn["foundView"].startswith("data:image/jpeg;base64,")
    assert [shown["name"] for shown in drawn["pieces"] if shown["selected"]] == [
        seen.name.name for seen in sorting.pieces() if seen.kind is piece.kind
    ]


def test_an_answer_lights_up_the_bodies_it_is_about(sorting: MontessoriSorting):
    [piece, *_] = sorting.pieces()

    sorting.answerer.answer(
        resolution_of(sorting), "piece", "which piece", a(SeenPiece)(kind=piece.kind)
    )

    assert sorting.answerer.answered[-1].to_payload()["highlight"] == [
        str(seen.root.name) for seen in sorting.pieces() if seen.kind is piece.kind
    ]


def test_tracy_starts_with_its_arms_parked():
    demonstration = TracyMontessoriDemonstration(takes_commands=False)

    world = demonstration.build_simulated_world()

    [robot] = world.get_semantic_annotations_by_type(Tracy)
    assert all(
        arm.get_joint_state_by_type(StaticJointState.PARK).is_achieved()
        for arm in robot.all_arms
    )
