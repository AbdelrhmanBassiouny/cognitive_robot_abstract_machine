"""
Montessori shape-sorting scene built directly on Tracy's own built-in table, instead of
the free-standing table :mod:`~experiments.montessori.world` lays out for a robot with
no table of its own.

Tracy (see :class:`~semantic_digital_twin.robots.tracy.Tracy`) ships a real table as a
fixed part of its own body tree (its
:meth:`~semantic_digital_twin.robots.tracy.Tracy._get_root_body_name` is literally
``"table"``), at whatever height that model actually has -- unlike a fixed-base robot
with no table of its own, which stands next to one this package builds (see
:meth:`~experiments.montessori.world.MontessoriWorld.add_robot_stand`). So this module
does not build (or need) a separate table or robot stand: it only builds the
shape-sorting board and the loose shapes' row, both placed directly on Tracy's own table
surface, reusing every position-independent piece of
:mod:`~experiments.montessori.world` (the board's mesh/hole-cutting, its collision-box
tiling, and the loose shapes' own geometry) the same way
:mod:`~experiments.montessori.world2` does for its own differently-positioned layout.

Tracy is mounted separately, after construction, via
:meth:`~experiments.montessori.world.MontessoriWorld.mount_stationary_robot` (inherited
unchanged) with the position :func:`~experiments.tracy_experiments.equipment.tracy_table_mount_position`
computes. This class needs to know the resulting height of Tracy's own table
top *before* that mounting happens (to place the board and shapes on it), so a caller
must compute it first (see :func:`~experiments.tracy_experiments.equipment.tracy_table_mount_position`)
and pass it in as :attr:`TracyMontessoriWorld.table_top_z`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List

from experiments.montessori.hole_geometry import (
    HOLE_MARKER_THICKNESS,
    HoleFootprint,
    _extrude_polygon,
)
from experiments.montessori.pieces import (
    CUBE_EDGE,
    CYLINDER_DIAMETER,
    CYLINDER_HEIGHT,
    RECTANGULAR_PRISM_HEIGHT,
    RECTANGULAR_PRISM_LENGTH,
    RECTANGULAR_PRISM_WIDTH,
    TRIANGULAR_PRISM_HEIGHT,
    TRIANGULAR_PRISM_SIDE,
    equilateral_triangle_boundary,
)
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
    _body_with_visual_only_shape,
    _drawer_body,
    _hole_marker_shape,
    _landing_region,
    _landing_region_height,
    _landing_region_position,
    _name,
)
from experiments.montessori.world2 import SPAWNED_SHAPE_CATEGORIES
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Drawer,
    Floor,
    Handle,
)
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world_description.geometry import (
    Box,
    Color,
    Cylinder,
    Mesh,
    Scale,
)
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

BOARD_POSITION_TRACY = Point3(0.85, 0.0, 0.0)
"""
X/Y of the shape-sorting board on Tracy's own table, straight ahead of it (``y=0``).

Brought in from an earlier ``1.15`` (before that, ``1.3``): with both arms starting
already parked rather than being swept there live, the board no longer has to clear a
live sweep, only the arms' own *parked-and-settled* geometry -- confirmed directly by
running MuJoCo's own narrow-phase contact check (not just a bounding-box estimate)
between the board and both parked arms at ``x`` values from ``1.15`` down to ``0.60``:
zero contacts at every value tested, since a UR10's own parked wrist links are rounded,
not box-shaped, so their real collision geometry sits well inside their axis-aligned
bounding box. ``0.85`` was chosen inside that contact-free range, roughly halfway to
:const:`SHAPE_ROW_X` rather than at the tested floor, to keep a visible margin for a
shape that overshoots slightly during a place; a full headless sorting run at this
position completes with no collision or unreachable-pose errors. Z is filled in by
:meth:`TracyMontessoriWorld._board_position` once
:attr:`TracyMontessoriWorld.table_top_z` is known.
"""

SHAPE_ROW_X = 0.55
"""
X-coordinate of the loose-shape row on Tracy's own table, nearer than
:const:`BOARD_POSITION_TRACY` so a pick is followed by a place that moves further out
onto the board.

Kept further away from the board than an earlier ``0.65``: the board's own drawer
handles project toward the shape row by :data:`~experiments.montessori.world.
_HANDLE_OFFSET`'s own x-offset, landing only a couple of centimetres from a shape row at
``0.65`` -- confirmed directly, the right arm's forearm swept into a drawer handle
reaching for a shape's hover pose. Exactly where the row sits does not matter (nothing
downstream assumes a particular pick position), only that the arm can reach it and
approach without clipping the board.
"""

SHAPE_ROW_START_Y = 0.1
"""
Y-coordinate of the first loose shape in the row, on the side Tracy's left arm's own
parked configuration rests towards, since :mod:`~experiments.tracy_experiments.

montessori_demo_mujoco` picks with :attr:`~coraplex.datastructures.enums.Arms.LEFT`.
Positive, mirroring an earlier negative value used when the right arm did the picking.
"""

SHAPE_ROW_SPACING = 0.15
"""
Distance, along y, between adjacent loose shapes in the row; positive, continuing toward
the same left-arm-reachable side :const:`SHAPE_ROW_START_Y` starts at.

Widened from an earlier ``-0.09``: with shapes that close together, an empty-gripper
reach for one shape's own hover pose could sweep the arm into its neighbour. Exactly how
far apart they sit does not matter, only that neighbouring shapes stay clear of each
other's own approach path.
"""

SKIPPED_HOLE_KEYS = frozenset({"circular_hole_2"})
"""
Hole keys with no matching loose piece in this scene, even though their
:class:`~experiments.montessori.semantics.MontessoriShapeCategory` is otherwise spawned
(see :data:`~experiments.montessori.world2.SPAWNED_SHAPE_CATEGORIES`): this scene's
physical set has only one cylindrical piece, sized to :const:`CYLINDER_DIAMETER`, so the
board's second, differently-sized circular hole is left without a matching piece.
"""

_BOARD_POSITION_DELTA_X = float(BOARD_POSITION_TRACY.x) - float(BOARD_POSITION.x)
_BOARD_POSITION_DELTA_Y = float(BOARD_POSITION_TRACY.y) - float(BOARD_POSITION.y)
_DRAWER_XY_TRACY: List[tuple[float, float]] = [
    (
        float(position.x) + _BOARD_POSITION_DELTA_X,
        float(position.y) + _BOARD_POSITION_DELTA_Y,
    )
    for position in _DRAWER_POSITIONS
]
"""
X/Y of :const:`~experiments.montessori.world._DRAWER_POSITIONS` (hand-placed relative to
:const:`~experiments.montessori.world.BOARD_POSITION`), carried over to
:const:`BOARD_POSITION_TRACY` by the same x/y offset -- mirrors
:mod:`~experiments.montessori.world2`'s own ``_DRAWER_POSITIONS_2``.

Z is filled in by
:meth:`TracyMontessoriWorld._build_shape_sorting_board` once :attr:`TracyMontessoriWorld.table_top_z`
is known.
"""


def _hole_spec_from_footprint_tracy(
    footprint: HoleFootprint, key: str, board_position: Point3, board_top_z: float
) -> _HoleSpec:
    """
    Place a mesh-detected :class:`~experiments.montessori.hole_geometry.HoleFootprint`
    onto ``board_position``, flush with the board's top surface, and pair it with a
    semantic key.

    Mirrors :func:`experiments.montessori.world._hole_spec_from_footprint`, which bakes
    in that module's own board position/height at import time and so cannot be reused
    directly for a board whose height is only known once Tracy is mounted.
    """
    position = Point3(
        float(board_position.x) + footprint.center[0],
        float(board_position.y) + footprint.center[1],
        board_top_z - HOLE_MARKER_THICKNESS / 2,
    )
    return _HoleSpec(key, footprint.category, position, footprint)


def _build_hole_specs_tracy(
    footprints: List[HoleFootprint], board_position: Point3, board_top_z: float
) -> List[_HoleSpec]:
    """
    Mirrors :func:`experiments.montessori.world._build_hole_specs`; see
    :func:`_hole_spec_from_footprint_tracy` for why it cannot be reused directly.
    """
    circular_hole_count = 0
    hole_specs = []
    for footprint in footprints:
        if footprint.category is MontessoriShapeCategory.CYLINDER:
            circular_hole_count += 1
            key = f"circular_hole_{circular_hole_count}"
        else:
            key = _HOLE_KEY_BY_CATEGORY[footprint.category]
        hole_specs.append(
            _hole_spec_from_footprint_tracy(footprint, key, board_position, board_top_z)
        )
    return hole_specs


def _measured_shape_body(name: PrefixedName, category: MontessoriShapeCategory) -> Body:
    """
    Build the :class:`Body` of a loose Montessori shape from this scene's own measured
    physical dimensions, rather than :func:`~experiments.montessori.world._shape_body`'s
    scaled-down copy of the board's own hole footprint.

    :param category: Which measured shape to build; must be one of
        :attr:`~MontessoriShapeCategory.CUBE`, :attr:`~MontessoriShapeCategory.CYLINDER`,
        :attr:`~MontessoriShapeCategory.RECTANGULAR_PRISM`, or
        :attr:`~MontessoriShapeCategory.TRIANGULAR_PRISM`.
    """
    color = _SHAPE_COLORS[category]
    match category:
        case MontessoriShapeCategory.CUBE:
            shape = Box(scale=Scale(CUBE_EDGE, CUBE_EDGE, CUBE_EDGE), color=color)
        case MontessoriShapeCategory.CYLINDER:
            shape = Cylinder(
                width=CYLINDER_DIAMETER, height=CYLINDER_HEIGHT, color=color
            )
        case MontessoriShapeCategory.RECTANGULAR_PRISM:
            shape = Box(
                scale=Scale(
                    RECTANGULAR_PRISM_WIDTH,
                    RECTANGULAR_PRISM_LENGTH,
                    RECTANGULAR_PRISM_HEIGHT,
                ),
                color=color,
            )
        case MontessoriShapeCategory.TRIANGULAR_PRISM:
            boundary = equilateral_triangle_boundary(TRIANGULAR_PRISM_SIDE)
            solid = _extrude_polygon(boundary, TRIANGULAR_PRISM_HEIGHT)
            shape = Mesh.from_trimesh(mesh=solid)
            shape.color = color
    return _body_with_shape(name, shape)


@dataclass(eq=False)
class TracyMontessoriWorld(MontessoriWorld):
    """
    :class:`~experiments.montessori.world.MontessoriWorld` with the board and loose
    shapes placed directly on Tracy's own built-in table (see this module's own
    docstring) instead of a table this class builds itself.
    """

    table_top_z: float = field(kw_only=True)
    """
    Height, in the world root frame, Tracy's own table's top surface ends up at once
    mounted (see
    :func:`~experiments.tracy_experiments.equipment.tracy_table_mount_position`),
    computed by the caller before constructing this class since Tracy is mounted only
    afterward.
    """

    _hole_specs: List[_HoleSpec] = field(init=False, default_factory=list)
    """
    This scene's holes, computed by :meth:`_build_shape_sorting_board` and read back by
    :meth:`_build_shapes` to place each spawned loose shape's matching hole footprint.
    """

    def _build_floor_and_table(self) -> None:
        floor = Floor(
            name=_name("floor"),
            root=_body_with_visual_only_shape(
                _name("floor"), Box(scale=FLOOR_SCALE, color=Color.GREY())
            ),
        )
        self._spawn(floor, Point3(0.0, 0.0, FLOOR_Z - FLOOR_SCALE.z / 2))

    def _build_shape_sorting_board(self) -> ShapeSortingBoard:
        board_position = Point3(
            BOARD_POSITION_TRACY.x,
            BOARD_POSITION_TRACY.y,
            self.table_top_z + BOARD_SCALE.z / 2,
        )
        board_top_z = float(board_position.z) + BOARD_SCALE.z / 2

        board_shape = Mesh.from_trimesh(mesh=_BOARD_MESH)
        board_shape.color = BOARD_COLOR
        board = ShapeSortingBoard(
            name=_name("board"),
            root=_board_body(_name("board"), board_shape, _HOLE_FOOTPRINTS),
        )
        self._spawn(board, board_position)

        self._hole_specs = _build_hole_specs_tracy(
            _HOLE_FOOTPRINTS, board_position, board_top_z
        )
        landing_region_height = _landing_region_height(self.table_top_z, board_top_z)
        for hole_spec in self._hole_specs:
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
                    hole_spec.position, self.table_top_z, landing_region_height
                ),
            )
            self.landing_regions[hole_spec.key] = landing_region

        for index, (drawer_x, drawer_y) in enumerate(_DRAWER_XY_TRACY, start=1):
            drawer_position = Point3(drawer_x, drawer_y, board_position.z)
            drawer = Drawer(
                name=_name(f"drawer_{index}"),
                root=_drawer_body(
                    _name(f"drawer_{index}"),
                    DRAWER_SCALE,
                    BOARD_COLOR,
                    drawer_position,
                    board_position,
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
            for hole_spec in self._hole_specs
            if hole_spec.category in SPAWNED_SHAPE_CATEGORIES
            and hole_spec.key not in SKIPPED_HOLE_KEYS
        ]
        for index, hole_spec in enumerate(spawned_holes):
            shape_key = f"{hole_spec.key}_shape"
            body = _measured_shape_body(_name(shape_key), hole_spec.category)
            shape_class = MONTESSORI_SHAPE_CLASSES[hole_spec.category]
            shape = shape_class(name=_name(shape_key), root=body)
            y = SHAPE_ROW_START_Y + index * SHAPE_ROW_SPACING
            spawn = self._spawn_free_body if self.shapes_are_movable else self._spawn
            spawn(shape, self._resting_position_on_table(body, y))

    def _resting_position_on_table(self, body: Body, y: float) -> Point3:
        """
        Position, at ``y`` along :const:`SHAPE_ROW_X`, at which ``body`` rests exactly
        on Tracy's own table surface, given its own local geometry.

        Mirrors :meth:`experiments.montessori.world.MontessoriWorld._resting_position_on_table`,
        parametrized by :attr:`table_top_z` instead of that module's fixed table height
        (and is an instance method rather than a ``@staticmethod`` for that reason).
        """
        lowest_local_z = body.collision.combined_mesh.bounds[0][2]
        return Point3(SHAPE_ROW_X, y, self.table_top_z - lowest_local_z)
