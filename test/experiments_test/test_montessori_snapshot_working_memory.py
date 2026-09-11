"""
Tests for :mod:`experiments.montessori.perception.snapshot_working_memory`.
"""

from __future__ import annotations

import numpy as np
import pytest
from typing_extensions import List

from experiments.montessori.perception.snapshot_working_memory import (
    PerceivedPose,
    SnapshotWorkingMemory,
)
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% fixtures


@pytest.fixture
def montessori_world() -> MontessoriWorld:
    """
    A Montessori scene whose loose pieces can actually be moved, matching the convention
    :mod:`~experiments.montessori.event_monitoring` tests already use for moving a piece
    by writing its connection's own origin.
    """
    return MontessoriWorld(shapes_are_movable=True)


@pytest.fixture
def some_piece(montessori_world: MontessoriWorld) -> MontessoriShape:
    """
    Any one loose piece the scene already holds.
    """
    return montessori_world.world.get_semantic_annotations_by_type(MontessoriShape)[0]


def believed_position(
    montessori_world: MontessoriWorld, piece: MontessoriShape
) -> np.ndarray:
    """
    Where the twin currently believes ``piece`` stands, in the world root's frame.
    """
    world = montessori_world.world
    return world.compute_forward_kinematics_np(world.root, piece.root)[:3, 3]


def pose_at(montessori_world: MontessoriWorld, position: np.ndarray) -> Pose:
    """
    A pose at ``position``, in the world root's frame.
    """
    return Pose.from_xyz_rpy(
        float(position[0]),
        float(position[1]),
        float(position[2]),
        reference_frame=montessori_world.world.root,
    )


def memory_of(
    montessori_world: MontessoriWorld,
    perceived_poses: List[PerceivedPose],
    is_idle: bool = True,
    minimum_period: float = 0.5,
) -> SnapshotWorkingMemory:
    """
    A :class:`SnapshotWorkingMemory` that always reports ``perceived_poses`` for its
    look, over ``montessori_world``.
    """
    return SnapshotWorkingMemory(
        world=montessori_world.world,
        look=lambda: perceived_poses,
        is_idle=lambda: is_idle,
        minimum_period=minimum_period,
    )


# %% the idle guard


def test_tick_commits_nothing_while_not_idle(
    montessori_world: MontessoriWorld, some_piece: MontessoriShape
):
    """
    While the robot is acting, the twin already follows the gripper kinematically, so a
    tick does not even look, let alone correct anything.
    """
    original_position = believed_position(montessori_world, some_piece)
    far_away = pose_at(montessori_world, original_position + np.array([0.5, 0.0, 0.0]))
    memory = memory_of(
        montessori_world,
        [PerceivedPose(category=some_piece.shape_category, role_taker=far_away)],
        is_idle=False,
    )

    committed = memory.tick(now=0.0)

    assert committed == []
    assert np.allclose(
        believed_position(montessori_world, some_piece), original_position
    )


# %% the throttle


def test_tick_takes_at_most_one_look_per_minimum_period(
    montessori_world: MontessoriWorld,
):
    """
    Idle re-perception is throttled the same way
    :class:`~experiments.montessori.perception.node.MontessoriPerceptionNode` throttles
    its own camera-rate pipeline runs.
    """
    look_count = 0

    def counting_look() -> List[PerceivedPose]:
        nonlocal look_count
        look_count += 1
        return []

    memory = SnapshotWorkingMemory(
        world=montessori_world.world,
        look=counting_look,
        is_idle=lambda: True,
        minimum_period=0.5,
    )

    memory.tick(now=0.0)
    memory.tick(now=0.1)

    assert look_count == 1


def test_tick_looks_again_once_the_minimum_period_has_passed(
    montessori_world: MontessoriWorld,
):
    look_count = 0

    def counting_look() -> List[PerceivedPose]:
        nonlocal look_count
        look_count += 1
        return []

    memory = SnapshotWorkingMemory(
        world=montessori_world.world,
        look=counting_look,
        is_idle=lambda: True,
        minimum_period=0.5,
    )

    memory.tick(now=0.0)
    memory.tick(now=0.6)

    assert look_count == 2


# %% every look is committed unconditionally


def test_a_barely_different_perceived_pose_is_still_committed(
    montessori_world: MontessoriWorld, some_piece: MontessoriShape
):
    """
    Deciding whether a piece actually moved is not this class's job -- it writes
    whatever a look reports, however small the difference from the believed pose, and
    leaves telling a real move from perception noise to the event system watching the
    twin over time.
    """
    original_position = believed_position(montessori_world, some_piece)
    offset = np.array([1e-9, 0.0, 0.0])
    barely_moved = pose_at(montessori_world, original_position + offset)
    memory = memory_of(
        montessori_world,
        [PerceivedPose(category=some_piece.shape_category, role_taker=barely_moved)],
    )

    committed = memory.tick(now=0.0)

    assert committed == [some_piece]
    assert np.allclose(
        believed_position(montessori_world, some_piece), original_position + offset
    )


def test_a_clearly_different_perceived_pose_is_committed(
    montessori_world: MontessoriWorld, some_piece: MontessoriShape
):
    original_position = believed_position(montessori_world, some_piece)
    offset = np.array([0.05, 0.0, 0.0])
    moved = pose_at(montessori_world, original_position + offset)
    memory = memory_of(
        montessori_world,
        [PerceivedPose(category=some_piece.shape_category, role_taker=moved)],
    )

    committed = memory.tick(now=0.0)

    assert committed == [some_piece]
    assert np.allclose(
        believed_position(montessori_world, some_piece), original_position + offset
    )


# %% matching a detection to the piece it belongs to


def test_a_detection_is_committed_to_the_nearest_piece_of_its_own_kind(
    montessori_world: MontessoriWorld,
):
    """
    A Montessori scene holds two cylinders (one cylindrical hole's own piece, and the
    sphere's stand-in), so this is the one category with a real disambiguation to make.
    """
    world = montessori_world.world
    pieces_by_category: dict = {}
    for piece in world.get_semantic_annotations_by_type(MontessoriShape):
        pieces_by_category.setdefault(piece.shape_category, []).append(piece)
    category, pieces = next(
        (category, pieces)
        for category, pieces in pieces_by_category.items()
        if len(pieces) >= 2
    )
    near_piece, far_piece = pieces[0], pieces[1]
    near_position = believed_position(montessori_world, near_piece)
    far_position = believed_position(montessori_world, far_piece)
    detected_position = near_position + np.array([0.02, 0.0, 0.0])
    assert np.linalg.norm(far_position - detected_position) > np.linalg.norm(
        near_position - detected_position
    )
    memory = memory_of(
        montessori_world,
        [
            PerceivedPose(
                category=category,
                role_taker=pose_at(montessori_world, detected_position),
            )
        ],
    )

    committed = memory.tick(now=0.0)

    assert committed == [near_piece]


def test_two_detections_of_the_same_kind_each_match_a_different_piece(
    montessori_world: MontessoriWorld,
):
    world = montessori_world.world
    pieces_by_category: dict = {}
    for piece in world.get_semantic_annotations_by_type(MontessoriShape):
        pieces_by_category.setdefault(piece.shape_category, []).append(piece)
    category, pieces = next(
        (category, pieces)
        for category, pieces in pieces_by_category.items()
        if len(pieces) >= 2
    )
    first_piece, second_piece = pieces[0], pieces[1]
    first_offset = believed_position(montessori_world, first_piece) + np.array(
        [0.02, 0.0, 0.0]
    )
    second_offset = believed_position(montessori_world, second_piece) + np.array(
        [0.0, 0.02, 0.0]
    )
    memory = memory_of(
        montessori_world,
        [
            PerceivedPose(
                category=category, role_taker=pose_at(montessori_world, first_offset)
            ),
            PerceivedPose(
                category=category, role_taker=pose_at(montessori_world, second_offset)
            ),
        ],
    )

    committed = memory.tick(now=0.0)

    assert set(committed) == {first_piece, second_piece}
