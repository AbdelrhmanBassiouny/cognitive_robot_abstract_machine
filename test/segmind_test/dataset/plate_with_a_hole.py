"""
A small world an expectation can be stated over: a plate with one square hole cut
through it, and a cube standing in the hole, on the plate over it, or lifted clear of
it.

It stands in for any surface a hole is cut through -- a board's lid, a wall -- so what
is tested here is the pattern, not the Montessori board.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

SETUP = "plate_with_a_hole"
"""
The prefix every entity of this world is named under.
"""

PLATE_TOP = 0.96
"""
Height of the plate's upper face above the world's origin, in metres.
"""

PLATE_THICKNESS = 0.02
"""
How thick the plate is, in metres.
"""

HOLE_AT = (0.8, 0.1)
"""
Where the hole's centre lies along the world's x and y axes, in metres.
"""

HOLE_WIDTH = 0.04
"""
How wide the square hole is, in metres, along either side.
"""

HOLE_DEPTH = 0.03
"""
How far below the plate's upper face the hole's region reaches, in metres.
"""

CUBE_SIDE = 0.03
"""
How long the cube's sides are, in metres.
"""

CUBE_COLOR = Color(R=0.0, G=0.8, B=0.8)
"""
The one colour the cube is drawn in.
"""


@dataclass
class HoleScene:
    """
    The world, and the entities of it an expectation names.
    """

    world: World
    """
    The world holding the plate, the hole and the cube.
    """

    plate: Body
    """
    The body the hole is cut through.
    """

    hole: Region
    """
    The hole's own region, reaching from the plate's upper face down into it.
    """

    cube: Body
    """
    The cube something acted on.
    """


def named(name: str) -> PrefixedName:
    """
    :param name: What the world calls a thing of this setup.
    """
    return PrefixedName(name, SETUP)


def cube_standing_at(height: float) -> Body:
    """
    A cube drawn in one colour, standing with its centre at a height.

    :param height: Height of the cube's centre above the world's origin, in metres.
    """
    return Body.from_shape_collection(
        named("cube"),
        ShapeCollection(
            [Box(scale=Scale(CUBE_SIDE, CUBE_SIDE, CUBE_SIDE), color=CUBE_COLOR)]
        ),
    )


def plate_with_a_hole(cube_center_height: float) -> HoleScene:
    """
    Build the world with the cube's centre at a height, directly over the hole.

    :param cube_center_height: Height of the cube's centre above the world's origin,
        in metres.
    """
    world = World()
    plate = Body.from_shape_collection(
        named("plate"), ShapeCollection([Box(scale=Scale(0.3, 0.3, PLATE_THICKNESS))])
    )
    hole = Region(
        name=named("square_hole"),
        area=ShapeCollection(
            [
                Box(
                    scale=Scale(HOLE_WIDTH, HOLE_WIDTH, HOLE_DEPTH),
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        z=-HOLE_DEPTH / 2
                    ),
                )
            ]
        ),
    )
    cube = cube_standing_at(cube_center_height)
    x, y = HOLE_AT
    with world.modify_world():
        world.add_body(Body(name=named("ground")))
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=plate,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=x,
                    y=y,
                    z=PLATE_TOP - PLATE_THICKNESS / 2,
                    reference_frame=world.root,
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=plate,
                child=hole,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=PLATE_THICKNESS / 2, reference_frame=plate
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=cube,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=x, y=y, z=cube_center_height, reference_frame=world.root
                ),
            )
        )
    return HoleScene(world=world, plate=plate, hole=hole, cube=cube)


def cube_in_the_hole() -> HoleScene:
    """
    The cube sunk into the hole, its top flush with the plate's upper face.
    """
    return plate_with_a_hole(PLATE_TOP - CUBE_SIDE / 2)


def cube_on_the_plate_over_the_hole() -> HoleScene:
    """
    The cube lying on the plate directly over the hole, not in it.
    """
    return plate_with_a_hole(PLATE_TOP + CUBE_SIDE / 2)


def cube_lifted_clear_of_the_hole() -> HoleScene:
    """
    The cube held well above the plate, as a gripper would hold it.
    """
    return plate_with_a_hole(PLATE_TOP + 0.1)
