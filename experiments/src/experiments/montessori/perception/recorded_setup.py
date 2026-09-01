"""
The Montessori setup the shipped captures and the recordings they come from were made
on.

Perception reads which stretch of table to search, and how high each surface lies, from
the world the robot publishes -- see
:meth:`~experiments.montessori.perception.pipeline.MontessoriPerceptionPipeline.of_world`.
A recording carries no world, so the two surfaces it was taken over are written down
here, measured off the transform tree those same recordings publish. Nothing that runs
against the live robot reads this.
"""

from __future__ import annotations

import math
from pathlib import Path

from experiments.montessori.hole_geometry import detect_hole_footprints, hole_names
from experiments.montessori.perception.detections import MontessoriBoardDetection
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region
from typing_extensions import Dict, Optional, Tuple

SETUP_NAME = "tracy"
"""
Prefix naming the physical setup these surfaces were measured on.
"""

TABLE_HEIGHT = 0.88
"""
Height of Tracy's own table top above the reference frame, in metres.

Read off the ``map`` to ``table`` transform the robot publishes into every recording.
"""

WIDEST_WORKSPACE = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
The whole stretch of that table the camera looks over, and the widest a run may search.

A workspace tuned for this setup is cut out of this one, so an edge brought in by
:mod:`~experiments.montessori.perception.tune_workspace` can always be pushed back out
to where it started.
"""

SURFACE_THICKNESS = 0.02
"""
How thick, in metres, a surface of this setup is drawn as in :func:`recorded_world`.

Nothing measures it: a surface is read from the top face of the body that carries it, so
a slab needs a thickness only to have a top at all.
"""

REGION_HEADROOM = 0.15
"""
How far, in metres, a region built by :func:`region_over` reaches above the table.

Enough to hold the board and anything standing on it, which is what a statement naming a
stretch of this table means to reach over.
"""

TUNED_WORKSPACE_FILE = (
    Path(__file__).parent.parent / "resources" / f"{SETUP_NAME}_workspace.json"
)
"""
Where the stretch of table tuned for this setup is kept.
"""


def searched_workspace(path: Path = TUNED_WORKSPACE_FILE) -> WorkspaceRegion:
    """
    The stretch of table a run over this setup's recordings searches.

    :param path: The file a tuned workspace was written to.
    :return: That workspace, or the whole of :data:`WIDEST_WORKSPACE` where none has
        been tuned.
    """
    if not path.is_file():
        return WIDEST_WORKSPACE
    return WorkspaceRegion.load(path)


def table_surface() -> WorkspaceSurface:
    """
    :return: The bare steel table the scene is set up on.
    """
    return WorkspaceSurface(
        name=PrefixedName("table", SETUP_NAME),
        region=searched_workspace(),
        height=TABLE_HEIGHT,
    )


def lid_surface() -> WorkspaceSurface:
    """
    :return: The board's lid, the second surface pieces rest on.
    """
    return WorkspaceSurface(
        name=PrefixedName("board_lid", SETUP_NAME),
        region=searched_workspace(),
        height=TABLE_HEIGHT + float(BOARD_SCALE.z),
    )


def recorded_world() -> World:
    """
    A world holding the two surfaces this setup's recordings were taken over.

    A relation is stated between entities, and a recording carries no world to name any,
    so a statement about a capture has nothing to be written over. These are the same
    two surfaces :func:`table_surface` and :func:`lid_surface` describe, by the very
    names those record, as bodies a statement can relate a detection to.

    It holds no pieces: what a look finds on this table is what the picture says, not
    what a world places there.
    """
    world = World()
    root = Body(name=PrefixedName("root", SETUP_NAME))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        for surface in (table_surface(), lid_surface()):
            world.add_connection(
                FixedConnection(
                    parent=root,
                    child=_body_of(surface),
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(),
                )
            )
    world.update_forward_kinematics()
    return world


def _body_of(surface: WorkspaceSurface) -> Body:
    """
    The body a measured surface stands for, as a slab filling its own extent.

    :param surface: The surface to describe.
    """
    return Body(
        name=surface.name,
        collision=ShapeCollection(
            [
                Box(
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=(surface.region.minimum_x + surface.region.maximum_x) / 2,
                        y=(surface.region.minimum_y + surface.region.maximum_y) / 2,
                        z=surface.height - SURFACE_THICKNESS / 2,
                    ),
                    scale=Scale(
                        surface.region.maximum_x - surface.region.minimum_x,
                        surface.region.maximum_y - surface.region.minimum_y,
                        SURFACE_THICKNESS,
                    ),
                )
            ]
        ),
    )


def region_over(world: World, patch: WorkspaceRegion, name: str) -> Region:
    """
    A stretch of this setup's table, as a region a statement can say a thing lies in.

    :param world: The world to add it to, from :func:`recorded_world`.
    :param patch: The stretch of table it covers.
    :param name: What to call it.
    :return: The region, standing on the table and reaching up to the room above it.
    """
    region = Region(
        name=PrefixedName(name, SETUP_NAME),
        area=ShapeCollection(
            [
                Box(
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        z=REGION_HEADROOM / 2
                    ),
                    scale=Scale(
                        patch.maximum_x - patch.minimum_x,
                        patch.maximum_y - patch.minimum_y,
                        REGION_HEADROOM,
                    ),
                )
            ]
        ),
    )
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=region,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=(patch.minimum_x + patch.maximum_x) / 2,
                    y=(patch.minimum_y + patch.maximum_y) / 2,
                    z=TABLE_HEIGHT,
                ),
            )
        )
    world.update_forward_kinematics()
    return region


def board_holes_in(world: World, board: MontessoriBoardDetection) -> Dict[str, Body]:
    """
    The board's holes, placed in the world where a look found the board.

    Which holes the board has and where each lies on it is knowledge, cut into the mesh
    the board is modelled from; where the board itself stands is what the look says. A
    statement about one particular hole needs both, which is why the holes are placed
    from a detection rather than written down here: where this board stands has been
    measured to drift from where the world models it.

    :param world: The world to place them in, from :func:`recorded_world`.
    :param board: The board as a look found it.
    :return: One body per hole, by the name the board's own mesh gives it.
    """
    footprints = detect_hole_footprints()
    stands_at = board.pose.to_position().to_np()
    placed = {}
    with world.modify_world():
        for footprint, name in zip(footprints, hole_names(footprints)):
            hole = Body(name=PrefixedName(name, SETUP_NAME))
            across, along = _turned(footprint.center, board.yaw)
            world.add_connection(
                FixedConnection(
                    parent=world.root,
                    child=hole,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=float(stands_at[0]) + across,
                        y=float(stands_at[1]) + along,
                        z=board.lid_height,
                        reference_frame=world.root,
                    ),
                )
            )
            placed[name] = hole
    world.update_forward_kinematics()
    return placed


def _turned(center: PlanarPoint, yaw: float) -> Tuple[float, float]:
    """
    Where a place on the board lies once the board itself is turned.

    :param center: The place, in the board mesh's own frame, in metres.
    :param yaw: How far the board is turned about the world frame's z-axis, in radians.
    """
    turn, tilt = math.cos(yaw), math.sin(yaw)
    return (
        center.x * turn - center.y * tilt,
        center.x * tilt + center.y * turn,
    )


def perception_pipeline(world: Optional[World] = None) -> MontessoriPerceptionPipeline:
    """
    :param world: The world to place the detections in, or None to report them in no
        frame, which is what a run that only reads the pictures needs.
    :return: The pipeline that reads a recording of this setup.
    """
    return MontessoriPerceptionPipeline(
        table=table_surface(),
        lid=lid_surface(),
        reference_frame=None if world is None else world.root,
        world=world,
    )
