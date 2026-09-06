"""
Detect the Montessori shape-sorting board's hole footprints directly from its mesh
(``resources/board.stl``), instead of hand-authoring their positions and sizes as
constants.

The six holes are also read as one rigid layout, which is how they are found in a
picture: their positions relative to one another are cut into the board and cannot vary,
so the whole set has three degrees of freedom between them rather than three each.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import trimesh
from typing_extensions import List, Self, Tuple

from experiments.montessori.planar_geometry import (
    KnownOutline,
    PlanarPoint,
    PlanarSize,
    points_along,
    turned,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.world_description.geometry import Scale

BOARD_MESH_PATH = Path(__file__).parent / "resources" / "board.stl"
"""
Path to the shape-sorting board's mesh, cut with its six real shape holes.
"""

HOLE_MARKER_THICKNESS = 0.005
"""
Thickness (along the board's z-axis) of the thin box used to mark each hole's footprint;
the marker's top face sits flush with the board's top surface.
"""

_CIRCLE_VERTEX_COUNT_THRESHOLD = 20
"""
Circular hole boundaries are tessellated into far more polygon vertices than the
straight-edged holes (~65 vs.

9-13 in the source mesh); above this count a loop is classified as circular.
"""

_TRIANGLE_FILL_RATIO_THRESHOLD = 0.7
"""
A polygon's area divided by its bounding box's area.

A triangle inscribed in its bounding box fills at most half of it; the box-shaped holes
fill all of it.
"""

_DISK_ASPECT_RATIO_THRESHOLD = 5.0
"""
Ratio of a polygon's bounding box's longer side to its shorter side.

The disk hole is a narrow slot (~10:1); the square and rectangular holes are much closer
to square.
"""

_RECTANGLE_ASPECT_RATIO_THRESHOLD = 1.3
"""
Bounding-box aspect ratio above which a box-shaped hole is classified as rectangular
rather than square.
"""


@dataclass(frozen=True)
class PolygonMeasurement:
    """
    How much of the plane a simple polygon covers, and where that area balances.
    """

    area: float
    """
    The area the polygon encloses, in square metres, however its vertices are wound.
    """

    centroid: PlanarPoint
    """
    The point the enclosed area is balanced about, which for an asymmetric outline is
    not the middle of its bounding box.
    """

    @classmethod
    def of(cls, points_xy: np.ndarray) -> PolygonMeasurement:
        """
        Measure a simple polygon with the shoelace formula.

        :param points_xy: Ordered boundary vertices, shape ``(n, 2)``.
        """
        x, y = points_xy[:, 0], points_xy[:, 1]
        x_next, y_next = np.roll(x, -1), np.roll(y, -1)
        cross = x * y_next - x_next * y
        signed_area = cross.sum() / 2.0
        return cls(
            area=abs(signed_area),
            centroid=PlanarPoint(
                float(((x + x_next) * cross).sum() / (6 * signed_area)),
                float(((y + y_next) * cross).sum() / (6 * signed_area)),
            ),
        )


@dataclass(frozen=True)
class HoleFootprint:
    """
    A single hole's position and 2D footprint, detected from the board mesh.
    """

    category: MontessoriShapeCategory
    """
    The geometric shape of the hole.
    """

    center: PlanarPoint
    """
    The hole's center, in the board mesh's local ``(x, y)`` frame.
    """

    size: PlanarSize
    """
    The hole's axis-aligned bounding box size, along the board mesh's local ``(x, y)``
    axes.
    """

    boundary: Tuple[PlanarPoint, ...]
    """
    The hole's true cross-section outline: an ordered, closed polygon of ``(x, y)``
    points relative to :attr:`center` (as opposed to its bounding box).
    """

    def extrude(self, thickness: float) -> trimesh.Trimesh:
        """
        Extrude this hole's true boundary polygon into a solid of the given thickness,
        centered on its own local origin (i.e. on :attr:`center`, once translated
        there).

        :param thickness: Extrusion depth along z.
        """
        return extrude_polygon(
            np.asarray([(point.x, point.y) for point in self.boundary]), thickness
        )


def extrude_polygon(boundary: np.ndarray, thickness: float) -> trimesh.Trimesh:
    """
    Extrude a closed 2D polygon that is star-shaped with respect to its own centroid
    (true of every hole shape on this board) into a solid, via fan triangulation from
    that centroid.

    :param boundary: Ordered polygon vertices, shape ``(n, 2)``; a closing vertex that
        duplicates the first is dropped if present.
    :param thickness: Extrusion depth along z.
    """
    if np.allclose(boundary[0], boundary[-1]):
        boundary = boundary[:-1]
    centroid = boundary.mean(axis=0)
    vertices = np.vstack([boundary, centroid])
    center_index = len(boundary)
    faces = np.array(
        [[i, (i + 1) % len(boundary), center_index] for i in range(len(boundary))]
    )
    mesh = trimesh.creation.extrude_triangulation(
        vertices=vertices, faces=faces, height=thickness
    )
    mesh.apply_translation([0.0, 0.0, -thickness / 2])
    return mesh


def cut_board_mesh(
    board_scale: Scale, footprints: List[HoleFootprint]
) -> trimesh.Trimesh:
    """
    Cut every hole in ``footprints`` all the way through a solid board blank, using each
    hole's true cross-section shape rather than its bounding box.

    :param board_scale: Size of the uncut board blank.
    :param footprints: The holes to cut, as detected by :func:`detect_hole_footprints`.
    :return: The board blank with all holes cut clean through it.
    """
    board = trimesh.creation.box(extents=(board_scale.x, board_scale.y, board_scale.z))
    cut_depth = board_scale.z * 2
    for footprint in footprints:
        cutter = footprint.extrude(cut_depth)
        cutter.apply_translation([footprint.center.x, footprint.center.y, 0.0])
        board = board.difference(cutter, engine=None)
    return board


def _classify_hole_shape(
    vertex_count: int, fill_ratio: float, aspect_ratio: float
) -> MontessoriShapeCategory:
    """
    Classify a hole's :class:`MontessoriShapeCategory` from its cross-section polygon's
    signature.
    """
    if vertex_count > _CIRCLE_VERTEX_COUNT_THRESHOLD:
        return MontessoriShapeCategory.CYLINDER
    if fill_ratio < _TRIANGLE_FILL_RATIO_THRESHOLD:
        return MontessoriShapeCategory.TRIANGULAR_PRISM
    if aspect_ratio > _DISK_ASPECT_RATIO_THRESHOLD:
        return MontessoriShapeCategory.DISK
    if aspect_ratio > _RECTANGLE_ASPECT_RATIO_THRESHOLD:
        return MontessoriShapeCategory.RECTANGULAR_PRISM
    return MontessoriShapeCategory.CUBE


def _find_perforated_body(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Find the connected part of ``mesh`` that has through-holes cut into it (the board's
    lid), identified as the watertight part with negative genus.

    :raises ValueError: If no such part exists.
    """
    for body in mesh.split(only_watertight=False):
        if body.is_watertight and body.euler_number < 2:
            return body
    raise ValueError("No part of the board mesh has holes cut into it.")


HOLE_NAME_BY_CATEGORY = {
    MontessoriShapeCategory.CUBE: "square_hole",
    MontessoriShapeCategory.TRIANGULAR_PRISM: "triangle_hole",
    MontessoriShapeCategory.RECTANGULAR_PRISM: "rectangular_hole",
    MontessoriShapeCategory.DISK: "disk_hole",
}
"""
What a hole of a given shape is called, for the shapes the board carries at most one
hole of.

The :attr:`~experiments.montessori.semantics.MontessoriShapeCategory.CYLINDER` category
occurs twice and is numbered instead (``circular_hole_1``, ``circular_hole_2``).
"""


def hole_names(footprints: List[HoleFootprint]) -> List[str]:
    """
    What each of the board's holes is called, in the order they were detected.

    :param footprints: The board's holes, as cut into its mesh.
    """
    circular_hole_count = 0
    names = []
    for footprint in footprints:
        if footprint.category is MontessoriShapeCategory.CYLINDER:
            circular_hole_count += 1
            names.append(f"circular_hole_{circular_hole_count}")
        else:
            names.append(HOLE_NAME_BY_CATEGORY[footprint.category])
    return names


def detect_hole_footprints() -> List[HoleFootprint]:
    """
    Detect the shape-sorting board's holes by slicing its mesh horizontally through the
    lid and analyzing each interior boundary loop's polygon.

    :return: One :class:`HoleFootprint` per hole cut into the board, ordered by
        ascending y-position.
    """
    mesh = trimesh.load(BOARD_MESH_PATH)
    lid = _find_perforated_body(mesh)

    mid_z = (lid.bounds[0][2] + lid.bounds[1][2]) / 2
    section = lid.section(plane_origin=[0.0, 0.0, mid_z], plane_normal=[0.0, 0.0, 1.0])
    loops = [np.asarray(loop)[:, :2] for loop in section.discrete]
    outer_boundary_index = max(
        range(len(loops)),
        key=lambda index: np.prod(loops[index].max(axis=0) - loops[index].min(axis=0)),
    )

    footprints = []
    for index, loop in enumerate(loops):
        if index == outer_boundary_index:
            continue
        minimum, maximum = loop.min(axis=0), loop.max(axis=0)
        size_x, size_y = maximum - minimum
        measurement = PolygonMeasurement.of(loop)
        aspect_ratio = max(size_x, size_y) / min(size_x, size_y)
        fill_ratio = measurement.area / (size_x * size_y)
        category = _classify_hole_shape(len(loop), fill_ratio, aspect_ratio)
        boundary = loop[:-1] if np.allclose(loop[0], loop[-1]) else loop
        footprints.append(
            HoleFootprint(
                category=category,
                center=measurement.centroid,
                size=PlanarSize(float(size_x), float(size_y)),
                boundary=tuple(
                    PlanarPoint(
                        float(x - measurement.centroid.x),
                        float(y - measurement.centroid.y),
                    )
                    for x, y in boundary
                ),
            )
        )

    return sorted(footprints, key=lambda footprint: footprint.center.y)


# %% the holes as one rigid layout


@dataclass(frozen=True, eq=False)
class PlacedHole:
    """
    One of the board's holes, put where the board was found to stand.
    """

    footprint: HoleFootprint
    """
    The hole the board mesh is cut with, which says what shape it is.
    """

    center: PlanarPoint
    """
    Where the hole's centre falls, in world-frame coordinates on the lid's plane.
    """

    outline: np.ndarray
    """
    Its boundary there, as ``(n, 2)`` world-frame ``(x, y)`` points.
    """


@dataclass(frozen=True, eq=False)
class BoardHoleLayout(KnownOutline):
    """
    Every hole cut through the board's lid, as one outline about the board's own origin.

    A hole searched for on its own has three degrees of freedom and takes whichever
    placement the picture happens to agree with; the six of them together have three
    between them, which is what the mesh actually says. Fitting the layout therefore
    cannot invent a hole, put two of them in one place, or land on the drawer fronts
    below the lid -- and it settles where the board itself stands, since six outlines
    constrain that where one does not.
    """

    holes: Tuple[HoleFootprint, ...]
    """
    The holes, in the order :func:`detect_hole_footprints` reports them.
    """

    size: PlanarSize
    """
    How far the lid reaches along the board's own axes, in metres.
    """

    scale: float = 1.0
    """
    How large the board this layout describes is, against the mesh it was read from.

    One is the mesh itself, which is what a scene built from that mesh shows. A real
    board is whatever size it is, and :meth:`~BoardScale.of_look` measures that rather
    than assuming the mesh was cut to it.
    """

    @classmethod
    @lru_cache(maxsize=8)
    def of_board_mesh(cls, scale: float = 1.0) -> Self:
        """
        Read the layout out of the board's own mesh, at the size a board of that mesh's
        shape is known to be.

        Cached, since finding the holes slices that mesh and a look is taken every frame.

        :param scale: How large the board is against the mesh.
        """
        lid = _find_perforated_body(trimesh.load(BOARD_MESH_PATH))
        reach = (lid.bounds[1] - lid.bounds[0]) * scale
        return cls(
            holes=tuple(
                _scaled_footprint(footprint, scale)
                for footprint in detect_hole_footprints()
            ),
            size=PlanarSize(float(reach[0]), float(reach[1])),
            scale=scale,
        )

    def outline_points(self, angle: float, spacing: float) -> np.ndarray:
        """
        The points every hole's boundary covers, turned together about the board's own
        origin.

        :param angle: How far the board is turned, in radians about the world frame's
            z-axis.
        :param spacing: How far apart, in metres, the points stand.
        """
        return turned(
            np.vstack(
                [
                    points_along(_boundary_about_the_board(hole), spacing)
                    for hole in self.holes
                ]
            ),
            angle,
        )

    def smallest_equivalent_turn(self, angle: float) -> float:
        """
        The smallest turn that leaves the layout looking the way the given one does.

        Six holes of five different shapes look alike under no turn but a whole one, so
        this only brings a turn within half a circle of zero.

        :param angle: A turn about the world frame's z-axis, in radians.
        """
        return (angle + math.pi) % (2 * math.pi) - math.pi

    def placed(self, center: PlanarPoint, yaw: float) -> List[PlacedHole]:
        """
        Where each hole falls with the board standing at one placement.

        :param center: Where the board's own origin stands, on the lid's plane.
        :param yaw: How far it is turned, in radians about the world frame's z-axis.
        """
        board = np.array([center.x, center.y])
        placed = []
        for hole in self.holes:
            at = turned(np.array([[hole.center.x, hole.center.y]]), yaw)[0] + board
            placed.append(
                PlacedHole(
                    footprint=hole,
                    center=PlanarPoint(float(at[0]), float(at[1])),
                    outline=turned(
                        np.array([(point.x, point.y) for point in hole.boundary]), yaw
                    )
                    + at,
                )
            )
        return placed


def _boundary_about_the_board(hole: HoleFootprint) -> np.ndarray:
    """
    One hole's boundary measured from the board's own origin rather than from the hole's
    centre, which is what makes the six of them one rigid outline.

    :param hole: The hole to read.
    """
    return np.array([(point.x, point.y) for point in hole.boundary]) + np.array(
        [hole.center.x, hole.center.y]
    )


def _scaled_footprint(footprint: HoleFootprint, scale: float) -> HoleFootprint:
    """
    The same hole on a board of a different size.

    :param footprint: The hole as the mesh cuts it.
    :param scale: How large the board is against the mesh.
    """
    if scale == 1.0:
        return footprint
    return HoleFootprint(
        category=footprint.category,
        center=PlanarPoint(footprint.center.x * scale, footprint.center.y * scale),
        size=PlanarSize(footprint.size.x * scale, footprint.size.y * scale),
        boundary=tuple(
            PlanarPoint(point.x * scale, point.y * scale)
            for point in footprint.boundary
        ),
    )
