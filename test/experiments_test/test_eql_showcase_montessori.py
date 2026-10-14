"""
Tests for Tracy sorting the Montessori pieces its camera saw into the holes cut for them,
leaving the arm, the grasp and the hole open for the robot to resolve.
"""

from __future__ import annotations

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
)
from experiments.eql_showcase.perceived_twin import SeenPiece
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
