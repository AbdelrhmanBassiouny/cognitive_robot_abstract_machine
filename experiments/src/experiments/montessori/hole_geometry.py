"""
Detect the Montessori shape-sorting board's hole footprints directly from its mesh
(``resources/board.stl``), instead of hand-authoring their positions and sizes as
constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from typing_extensions import List, Tuple

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
class HoleFootprint:
    """
    A single hole's position and 2D footprint, detected from the board mesh.
    """

    category: MontessoriShapeCategory
    """
    The geometric shape of the hole.
    """

    center: Tuple[float, float]
    """
    The hole's center, in the board mesh's local ``(x, y)`` frame.
    """

    size: Tuple[float, float]
    """
    The hole's axis-aligned bounding box size, along the board mesh's local ``(x, y)``
    axes.
    """

    boundary: Tuple[Tuple[float, float], ...]
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
        return _extrude_polygon(np.asarray(self.boundary), thickness)


def _extrude_polygon(boundary: np.ndarray, thickness: float) -> trimesh.Trimesh:
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
    board = trimesh.creation.box(
        extents=(board_scale.x, board_scale.y, board_scale.z)
    )
    cut_depth = board_scale.z * 2
    for footprint in footprints:
        cutter = footprint.extrude(cut_depth)
        cutter.apply_translation([footprint.center[0], footprint.center[1], 0.0])
        board = board.difference(cutter, engine=None)
    return board


def _polygon_area_and_centroid(
    points_xy: np.ndarray,
) -> Tuple[float, Tuple[float, float]]:
    """
    Compute a simple polygon's area and centroid with the shoelace formula.

    :param points_xy: Ordered boundary vertices, shape ``(n, 2)``.
    :return: The polygon's unsigned area and its ``(x, y)`` centroid.
    """
    x, y = points_xy[:, 0], points_xy[:, 1]
    x_next, y_next = np.roll(x, -1), np.roll(y, -1)
    cross = x * y_next - x_next * y
    signed_area = cross.sum() / 2.0
    centroid_x = ((x + x_next) * cross).sum() / (6 * signed_area)
    centroid_y = ((y + y_next) * cross).sum() / (6 * signed_area)
    return abs(signed_area), (centroid_x, centroid_y)


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
        area, centroid = _polygon_area_and_centroid(loop)
        aspect_ratio = max(size_x, size_y) / min(size_x, size_y)
        fill_ratio = area / (size_x * size_y)
        category = _classify_hole_shape(len(loop), fill_ratio, aspect_ratio)
        boundary = loop[:-1] if np.allclose(loop[0], loop[-1]) else loop
        footprints.append(
            HoleFootprint(
                category=category,
                center=(float(centroid[0]), float(centroid[1])),
                size=(float(size_x), float(size_y)),
                boundary=tuple(
                    (float(x - centroid[0]), float(y - centroid[1]))
                    for x, y in boundary
                ),
            )
        )

    return sorted(footprints, key=lambda footprint: footprint.center[1])
