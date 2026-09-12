"""
Precompute every cube's own target pose in the stack up front, rather than measuring the
stack's own current height after each place: shared between
:mod:`~experiments.tracy_experiments.stacking.stacking_demo_mujoco` (MuJoCo stands in as the real
robot) and :mod:`~experiments.tracy_experiments.stacking.stacking_demo_real` (the physical robot
is the real robot).
"""

from __future__ import annotations

from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)


def stack_target_pose(
    index: int,
    stack_x: float,
    stack_y: float,
    table_top_z: float,
    cube_size: float,
    reference_frame: KinematicStructureEntity,
) -> Pose:
    """
    The pose the ``index``-th cube in the stack rests at once every cube up to it is in
    place, fixed top-down.

    ``index=0`` is the already-placed base cube, resting directly on the table; each
    following index adds exactly one more cube's own height on top of it, so a caller
    that only ever places cubes in order (never skipping one) does not need to measure
    the stack's own current height after each place.

    :param index: Position in the stack, ``0`` for the base cube.
    :param stack_x: X-coordinate every cube in the stack shares.
    :param stack_y: Y-coordinate every cube in the stack shares.
    :param table_top_z: Height of the table surface the base cube rests on.
    :param cube_size: Edge length of every cube, in metres.
    :param reference_frame: The frame the returned pose is expressed in.
    """
    center_z = table_top_z + cube_size / 2 + index * cube_size
    return Pose.from_xyz_rpy(
        stack_x, stack_y, center_z, yaw=0, reference_frame=reference_frame
    )
