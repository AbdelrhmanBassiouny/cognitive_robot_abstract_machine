"""
Alternate layout for the Montessori shape-sorting scene: the shape-sorting board sits
directly in front of the mounted robot, and the loose shapes sit off to its side on
their own stand, instead of both sharing the single table :mod:`~experiments.montessori.world`
lays them out on.

:mod:`~experiments.montessori.world` is left untouched (this is a separate, parallel
layout to compare against it, not a replacement); :class:`MontessoriWorld2` subclasses
its :class:`~experiments.montessori.world.MontessoriWorld`, reusing every
position-independent piece (the board's mesh/hole-cutting, its collision-box tiling, the
loose shapes' own geometry, and the base class's spawning/robot-mounting machinery) and
only overriding the three methods that place things on the scene.

Whether separating the two regions actually helps was itself the open question this
layout exists to test: :mod:`~experiments.montessori.world`'s single table packs the
loose-shape row and the board into the same, fairly narrow strip in front of the robot,
so a pick and the following place can both sit near the edge of a comfortable reach
envelope at once. Here the board sits on its own stand straight ahead of the robot, and
the loose shapes sit tangentially arranged (same distance from the robot, varying
side-to-side rather than near/far) on a separate stand off to the robot's side, so a
pick mostly turns the robot's base joint while a place mostly extends its arm, rather
than needing a bit of both at every step.
"""

from __future__ import annotations

from typing_extensions import List

from experiments.montessori.hole_geometry import HOLE_MARKER_THICKNESS, HoleFootprint
from experiments.montessori.semantics import (
    MONTESSORI_SHAPE_CLASSES,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import (
    BOARD_COLOR,
    BOARD_POSITION,
    BOARD_SCALE,
    DRAWER_SCALE,
    FLOOR_SCALE,
    FLOOR_Z,
    HANDLE_SCALE,
    TABLE_LEG_FOOTPRINT,
    MontessoriWorld,
    _BOARD_MESH,
    _DRAWER_POSITIONS,
    _HANDLE_OFFSET,
    _HOLE_FOOTPRINTS,
    _HOLE_KEY_BY_CATEGORY,
    _SHAPE_COLORS,
    _HoleSpec,
    _board_body,
    _body_with_shape,
    _body_with_shapes,
    _body_with_visual_only_shape,
    _drawer_body,
    _hole_marker_shape,
    _landing_region,
    _landing_region_height,
    _landing_region_position,
    _name,
    _shape_body,
    _table_shapes,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Drawer,
    Floor,
    Handle,
    Table,
)
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world_description.geometry import Box, Color, Mesh, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

BOARD_TABLE_SCALE = Scale(0.35, 0.35, 0.025)
"""
Size of the stand carrying just the shape-sorting board, roomy enough for
:const:`~experiments.montessori.world.BOARD_SCALE` (0.13 x 0.30) with clearance on every
side.
"""

BOARD_TABLE_POSITION = Point3(-0.50, 0.0, 0.5)
"""
Center of the board's stand, directly ahead of :const:`ROBOT_MOUNT_POSITION` (same y),
0.5m away -- comfortably mid-workspace for the mounted Panda's ~0.855m reach, matching
:const:`SHAPE_STAND_POSITION`'s own distance so neither region sits nearer the edge of
the reach envelope than the other.
"""

BOARD_POSITION_2 = Point3(-0.4225, 0.0, 0.553)
"""
Where the board itself sits on :const:`BOARD_TABLE_POSITION`, preserving the same
height-above-its-stand offset (0.053m) as
:const:`~experiments.montessori.world.BOARD_POSITION` does above its own table.
"""

SHAPE_STAND_SCALE = Scale(0.5, 0.4, 0.025)
"""
Size of the stand carrying the row of loose shapes, wide enough (x) to fit
:const:`SPAWNED_SHAPE_CATEGORIES` side by side with margin (see
:const:`SHAPE_ROW_START_X`/:const:`SHAPE_ROW_SPACING`).
"""

SHAPE_STAND_POSITION = Point3(0.0, -0.5, 0.553)
"""
Center of the loose shapes' stand, off to :const:`ROBOT_MOUNT_POSITION`'s side (-y,
mirrored from the +y side this layout originally used) rather than ahead of it, 0.5m
away -- see :const:`BOARD_TABLE_POSITION`.
"""

SHAPE_ROW_Y = -0.4
"""
Y-coordinate, in the world frame, of the row of loose shapes -- matching
:const:`SHAPE_STAND_POSITION`'s own y so every shape sits the same distance from the
robot regardless of where it falls in the row (see :const:`SHAPE_ROW_START_X`); only x
varies along the row.
"""

SHAPE_ROW_START_X = -0.18
"""
X-coordinate of the first loose shape in the row.
"""

SHAPE_ROW_SPACING = 0.09
"""
Distance, along x, between adjacent loose shapes in the row.

Widened from :const:`~experiments.montessori.world.TABLE_SHAPE_ROW_SPACING`'s 0.06/0.07:
reaching into this row from the side (see this module's own docstring) put the gripper
at risk of clipping a shape next to the one it was actually reaching for.
"""

SPAWNED_SHAPE_CATEGORIES = frozenset(
    {
        MontessoriShapeCategory.CYLINDER,
        MontessoriShapeCategory.CUBE,
        MontessoriShapeCategory.TRIANGULAR_PRISM,
        MontessoriShapeCategory.RECTANGULAR_PRISM,
    }
)
"""
Categories whose loose shape actually gets spawned into the row (see
:meth:`MontessoriWorld2._build_shapes`).

Unlike :mod:`~experiments.montessori.world`, this layout does not spawn a disk or a
sphere at all: :data:`~experiments.montessori.franka_montessori_demo.SKIPPED_SHAPE_CATEGORIES`
already leaves the disk untouched and the sphere has no matching hole to begin with (see
:const:`~experiments.montessori.world._HOLES`'s own docstring), so neither is ever picked
-- but both still sat in the row, within clipping range of whichever neighbor the
gripper actually reached for.
"""

ROBOT_MOUNT_POSITION = Point3(0.0, 0.0, 0.5125)
"""
Where the robot is bolted -- the world origin's (x, y), at the same height
(0.5125 = table center 0.5 + half its 0.025 thickness) both stands share, so a robot
stand built under it (see :meth:`~experiments.montessori.world.MontessoriWorld.add_robot_stand`)
lines up flush with them.
"""

_BOARD_POSITION_DELTA_X = float(BOARD_POSITION_2.x) - float(BOARD_POSITION.x)
_BOARD_POSITION_DELTA_Y = float(BOARD_POSITION_2.y) - float(BOARD_POSITION.y)
_BOARD_POSITION_DELTA_Z = float(BOARD_POSITION_2.z) - float(BOARD_POSITION.z)
"""
Offset from :const:`~experiments.montessori.world.BOARD_POSITION` to
:const:`BOARD_POSITION_2`, used to carry :const:`~experiments.montessori.world._DRAWER_POSITIONS`
(hand-placed relative to the original board position) over to this layout without
re-deriving them from scratch.
"""

_DRAWER_POSITIONS_2: List[Point3] = [
    Point3(
        float(position.x) + _BOARD_POSITION_DELTA_X,
        float(position.y) + _BOARD_POSITION_DELTA_Y,
        float(position.z) + _BOARD_POSITION_DELTA_Z,
    )
    for position in _DRAWER_POSITIONS
]


def _hole_spec_from_footprint_2(footprint: HoleFootprint, key: str) -> _HoleSpec:
    """
    Place a mesh-detected :class:`~experiments.montessori.hole_geometry.HoleFootprint`
    onto :const:`BOARD_POSITION_2`, flush with the board's top surface, and pair it with
    a semantic key.

    Mirrors :func:`experiments.montessori.world._hole_spec_from_footprint`, which bakes
    in that module's own :const:`~experiments.montessori.world.BOARD_POSITION` at import
    time and so cannot be reused directly for a differently-positioned board.
    """
    position = Point3(
        BOARD_POSITION_2.x + footprint.center[0],
        BOARD_POSITION_2.y + footprint.center[1],
        BOARD_POSITION_2.z + BOARD_SCALE.z / 2 - HOLE_MARKER_THICKNESS / 2,
    )
    return _HoleSpec(key, footprint.category, position, footprint)


def _build_hole_specs_2(footprints: List[HoleFootprint]) -> List[_HoleSpec]:
    """
    Mirrors :func:`experiments.montessori.world._build_hole_specs`; see
    :func:`_hole_spec_from_footprint_2` for why it cannot be reused directly.
    """
    circular_hole_count = 0
    hole_specs = []
    for footprint in footprints:
        if footprint.category is MontessoriShapeCategory.CYLINDER:
            circular_hole_count += 1
            key = f"circular_hole_{circular_hole_count}"
        else:
            key = _HOLE_KEY_BY_CATEGORY[footprint.category]
        hole_specs.append(_hole_spec_from_footprint_2(footprint, key))
    return hole_specs


_HOLES_2: List[_HoleSpec] = _build_hole_specs_2(_HOLE_FOOTPRINTS)
"""
Same one-hole-per-category layout as :const:`experiments.montessori.world._HOLES`,
repositioned onto :const:`BOARD_POSITION_2`.
"""


class MontessoriWorld2(MontessoriWorld):
    """
    :class:`~experiments.montessori.world.MontessoriWorld` with the board and loose
    shapes laid out on separate stands (see this module's own docstring) instead of
    sharing one table.

    Reuses :class:`~experiments.montessori.world.MontessoriWorld`'s construction,
    spawning, and robot-mounting machinery as-is; only the placement of the floor's
    furniture and the loose shapes differs.
    """

    def _build_floor_and_table(self) -> None:
        floor = Floor(
            name=_name("floor"),
            root=_body_with_visual_only_shape(
                _name("floor"), Box(scale=FLOOR_SCALE, color=Color.GREY())
            ),
        )
        self._spawn(floor, Point3(0.0, 0.0, FLOOR_Z - FLOOR_SCALE.z / 2))

        board_table = Table(
            name=_name("board_table"),
            root=_body_with_shapes(
                _name("board_table"),
                _table_shapes(
                    BOARD_TABLE_SCALE,
                    float(BOARD_TABLE_POSITION.z),
                    TABLE_LEG_FOOTPRINT,
                    FLOOR_Z,
                    BOARD_COLOR,
                ),
            ),
        )
        self._spawn(board_table, BOARD_TABLE_POSITION)

        shape_stand = Table(
            name=_name("shape_stand"),
            root=_body_with_shapes(
                _name("shape_stand"),
                _table_shapes(
                    SHAPE_STAND_SCALE,
                    float(SHAPE_STAND_POSITION.z),
                    TABLE_LEG_FOOTPRINT,
                    FLOOR_Z,
                    BOARD_COLOR,
                ),
            ),
        )
        self._spawn(shape_stand, SHAPE_STAND_POSITION)

    def _build_shape_sorting_board(self) -> ShapeSortingBoard:
        board_shape = Mesh.from_trimesh(mesh=_BOARD_MESH)
        board_shape.color = BOARD_COLOR
        board = ShapeSortingBoard(
            name=_name("board"),
            root=_board_body(_name("board"), board_shape, _HOLE_FOOTPRINTS),
        )
        self._spawn(board, BOARD_POSITION_2)

        table_top_z = float(BOARD_TABLE_POSITION.z) + BOARD_TABLE_SCALE.z / 2
        board_top_z = float(BOARD_POSITION_2.z) + BOARD_SCALE.z / 2
        landing_region_height = _landing_region_height(table_top_z, board_top_z)
        for hole_spec in _HOLES_2:
            hole = ShapeSortingHole(
                name=_name(hole_spec.key),
                root=Region(
                    name=_name(hole_spec.key),
                    area=ShapeCollection(
                        [
                            _hole_marker_shape(
                                hole_spec.shape, _SHAPE_COLORS[hole_spec.category]
                            )
                        ]
                    ),
                ),
                shape_category=hole_spec.category,
            )
            self._spawn(hole, hole_spec.position)
            board.add(hole)

            landing_region = _landing_region(
                _name(f"{hole_spec.key}_landing_region"),
                hole_spec.shape,
                landing_region_height,
            )
            self._spawn_region(
                landing_region,
                _landing_region_position(
                    hole_spec.position, table_top_z, landing_region_height
                ),
            )
            self.landing_regions[hole_spec.key] = landing_region

        for index, drawer_position in enumerate(_DRAWER_POSITIONS_2, start=1):
            drawer = Drawer(
                name=_name(f"drawer_{index}"),
                root=_drawer_body(
                    _name(f"drawer_{index}"),
                    DRAWER_SCALE,
                    BOARD_COLOR,
                    drawer_position,
                    BOARD_POSITION_2,
                    _HOLE_FOOTPRINTS,
                ),
            )
            self._spawn(drawer, drawer_position)
            board.add(drawer)

            handle = Handle(
                name=_name(f"drawer_{index}_handle"),
                root=_body_with_shape(
                    _name(f"drawer_{index}_handle"),
                    Box(scale=HANDLE_SCALE, color=Color.GREY()),
                ),
            )
            handle_position = Point3(
                drawer_position.x + _HANDLE_OFFSET.x,
                drawer_position.y + _HANDLE_OFFSET.y,
                drawer_position.z + _HANDLE_OFFSET.z,
            )
            self._spawn(handle, handle_position)
            drawer.add(handle)

        return board

    def _build_shapes(self) -> None:
        spawned_holes = [
            hole_spec
            for hole_spec in _HOLES_2
            if hole_spec.category in SPAWNED_SHAPE_CATEGORIES
        ]
        categories = [hole_spec.category for hole_spec in spawned_holes]
        keys = [hole_spec.key for hole_spec in spawned_holes]
        footprints = [hole_spec.shape for hole_spec in spawned_holes]

        for index, (key, category, footprint) in enumerate(
            zip(keys, categories, footprints)
        ):
            shape_key = f"{key}_shape"
            body = _shape_body(_name(shape_key), category, footprint)
            shape_class = MONTESSORI_SHAPE_CLASSES[category]
            shape = shape_class(name=_name(shape_key), root=body)
            x = SHAPE_ROW_START_X + index * SHAPE_ROW_SPACING
            spawn = self._spawn_free_body if self.shapes_are_movable else self._spawn
            spawn(shape, self._resting_position_on_stand(body, x))

    @staticmethod
    def _resting_position_on_stand(body: Body, x: float) -> Point3:
        """
        Position, at ``x`` along :const:`SHAPE_ROW_Y`, at which ``body`` rests exactly
        on the shape stand's surface, given its own local geometry.

        Mirrors :meth:`experiments.montessori.world.MontessoriWorld._resting_position_on_table`,
        with x and y swapped since here the row varies along x at a fixed y instead of
        the other way around.
        """
        lowest_local_z = body.collision.combined_mesh.bounds[0][2]
        stand_top_z = float(SHAPE_STAND_POSITION.z) + SHAPE_STAND_SCALE.z / 2
        return Point3(x, SHAPE_ROW_Y, stand_top_z - lowest_local_z)
