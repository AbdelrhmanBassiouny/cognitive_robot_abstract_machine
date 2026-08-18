"""
A minimal shape-sorting scene: one board, one hole, one cube that fits it.

Built body by body rather than through
:class:`~experiments.montessori.world.MontessoriWorld`, so tests that only need
somewhere for a shape to be inserted do not pay for the full scene.
"""

from __future__ import annotations

from experiments.montessori.semantics import (
    CubeShape,
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
    SphereShape,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import Box, Scale, Sphere
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

SHAPE_KEY = "square_hole"
"""
The name both the hole and (suffixed with ``_shape``) the cube are built under.
"""

SHAPE_OBJECT_NAME = "cube"
"""
What the cube built under :data:`SHAPE_KEY` calls itself (see
:attr:`~experiments.montessori.semantics.MontessoriShape.object_name`).
"""


def board_with_one_hole(world: World, hole_position: Point3):
    """
    A board and the single hole a cube fits through, both at known positions.

    Names are plain strings, as ``create_with_new_*_in_world`` declares them: a
    :class:`PrefixedName` here would be wrapped in a second one, which no longer renders
    as a string.

    :param world: The world to build them in.
    :param hole_position: Where the hole sits, in the world root frame.
    """
    board = ShapeSortingBoard.create_with_new_body_in_world(
        name="board", world=world, scale=Scale(0.3, 0.3, 0.1)
    )
    hole = ShapeSortingHole.create_with_new_region_in_world(
        name=SHAPE_KEY,
        world=world,
        scale=Scale(0.05, 0.05, 0.001),
        world_root_T_self=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=hole_position.x, y=hole_position.y, z=hole_position.z
        ),
    )
    hole.shape_category = MontessoriShapeCategory.CUBE
    board.add(hole)
    return board, hole


def cube_at(
    world: World, position: Point3, shape_key: str = SHAPE_KEY
) -> MontessoriShape:
    """
    A cube small enough to pass the hole, spawned at ``position``.

    :param world: The world to build it in.
    :param position: Where the cube sits, in the world root frame.
    :param shape_key: The key pairing the cube with its hole, which a second cube in the
        same world needs its own of.
    """
    name = shape_key + "_shape"
    body = Body.from_shape_collection(
        PrefixedName(name), ShapeCollection([Box(scale=Scale(0.03, 0.03, 0.03))])
    )
    world.add_body(body)
    # a movable connection, as a loose shape has in the real scene: a fixed one cannot
    # be re-posed, and these tests are about a shape that moves
    degrees_of_freedom = {
        component: DegreeOfFreedom(name=PrefixedName("%s_%s" % (name, component)))
        for component in ("x", "y", "z", "qx", "qy", "qz", "qw")
    }
    for degree_of_freedom in degrees_of_freedom.values():
        world.add_degree_of_freedom(degree_of_freedom)
    world.add_connection(
        Connection6DoF(parent=world.root, child=body, **degrees_of_freedom)
    )
    world.state[degrees_of_freedom["qw"].id].position = 1.0
    shape = CubeShape(name=PrefixedName(name), root=body)
    world.add_semantic_annotation(shape)
    _place(world, shape, position)
    return shape


def sphere_at(world: World, position: Point3) -> MontessoriShape:
    """
    A sphere, the one shape category the board has no hole for.

    :param world: The world to build it in.
    :param position: Where the sphere sits, in the world root frame.
    """
    body = Body.from_shape_collection(
        PrefixedName("sphere_shape"), ShapeCollection([Sphere(radius=0.02)])
    )
    world.add_connection(
        FixedConnection(
            parent=world.root,
            child=body,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=position.x, y=position.y, z=position.z
            ),
        )
    )
    shape = SphereShape(name=PrefixedName("sphere_shape"), root=body)
    world.add_semantic_annotation(shape)
    return shape


def move_shape_to(world: World, shape: MontessoriShape, position: Point3) -> None:
    """
    Move a shape once the world is built, so a world read after it sees somewhere new.

    :param world: The world the shape lives in.
    :param shape: The shape to move.
    :param position: Where to move it, in the world root frame.
    """
    _place(world, shape, position)
    world.notify_state_change()


def _place(world: World, shape: MontessoriShape, position: Point3) -> None:
    """
    Write a shape's position into the world state.

    :param world: The world the shape lives in.
    :param shape: The shape to place.
    :param position: Where to place it, in the world root frame.
    """
    connection = shape.root.parent_connection
    for component, value in (
        ("x", position.x),
        ("y", position.y),
        ("z", position.z),
    ):
        world.state[vars(connection)[component].id].position = float(value)
