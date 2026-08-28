"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_real`: loose shapes are
spawned resting on the table, and the grasp target is lifted back to where the pick
aimed before the spawn was lowered, so moving the offset from the spawn to the grasp
leaves the reached height unchanged.
"""

from __future__ import annotations

from experiments.tracy_experiments.pickup.pickup_demo_real import (
    GRASP_HEIGHT_OFFSET,
    PICK_TARGETS,
    _add_montessori_shape,
    _grasp_target_pose,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

TABLE_TOP_Z = 0.75
"""
An arbitrary table-top height to spawn against.
"""


def _world_with_root() -> World:
    """
    A world holding only its root body, ready for a shape to be added.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(
            Body(name=PrefixedName(name="root", prefix="world"))
        )
    return world


def test_grasp_target_pose_sits_the_offset_above_the_body_origin():
    body = Body(name=PrefixedName("shape"))

    pose = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET)

    translation = pose.to_homogeneous_matrix()[:3, 3]
    assert [float(component) for component in translation] == [
        0.0,
        0.0,
        GRASP_HEIGHT_OFFSET,
    ]
    assert pose.reference_frame is body


def test_a_loose_shape_is_spawned_resting_on_the_table():
    world = _world_with_root()
    target = PICK_TARGETS[0]

    body = _add_montessori_shape(world, TABLE_TOP_Z, target)

    spawned_z = float(world.compute_forward_kinematics_np(world.root, body)[2, 3])
    assert spawned_z == TABLE_TOP_Z + target.half_height


def test_the_grasp_is_aimed_where_the_pre_offset_spawn_put_it():
    world = _world_with_root()
    target = PICK_TARGETS[0]
    body = _add_montessori_shape(world, TABLE_TOP_Z, target)

    grasp_target = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET)

    world_grasp_z = float(
        world.transform(grasp_target.to_homogeneous_matrix(), world.root)[2, 3]
    )
    assert world_grasp_z == TABLE_TOP_Z + target.half_height + GRASP_HEIGHT_OFFSET
