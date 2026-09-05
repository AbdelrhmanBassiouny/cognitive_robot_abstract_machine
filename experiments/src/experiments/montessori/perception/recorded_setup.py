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
from experiments.montessori.perception.camera import RgbdFrame
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

CAMERA_NAME = "camera"
"""
What the world calls the camera these recordings were taken with.
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


TABLE_NAME = PrefixedName("table", SETUP_NAME)
"""
What this setup calls the bare steel table the scene is set up on.
"""

LID_NAME = PrefixedName("board_lid", SETUP_NAME)
"""
What this setup calls the board's lid, the second surface pieces rest on.
"""

LID_HEIGHT = TABLE_HEIGHT + float(BOARD_SCALE.z)
"""
How high the board's lid stands above the world frame's origin, in metres.
"""


def table_surface(world: Optional[World] = None) -> WorkspaceSurface:
    """
    :param world: The world the recordings are read against, from
        :func:`recorded_world`, or None for a run that only reads the pictures.
    :return: The bare steel table the scene is set up on, measured of that world's own
        body for it.
    """
    return WorkspaceSurface(
        entity=_slab_in(world, TABLE_NAME, TABLE_HEIGHT),
        region=searched_workspace(),
        height=TABLE_HEIGHT,
    )


def lid_surface(world: Optional[World] = None) -> WorkspaceSurface:
    """
    :param world: The world the recordings are read against, from
        :func:`recorded_world`, or None for a run that only reads the pictures.
    :return: The board's lid, the second surface pieces rest on.
    """
    return WorkspaceSurface(
        entity=_slab_in(world, LID_NAME, LID_HEIGHT),
        region=searched_workspace(),
        height=LID_HEIGHT,
    )


def recorded_world() -> World:
    """
    A world holding the two surfaces this setup's recordings were taken over.

    A relation is stated between entities, and a recording carries no world to name any,
    so a statement about a capture has nothing to be written over. These are the same
    two surfaces :func:`table_surface` and :func:`lid_surface` are measured of, as
    bodies a statement can relate a detection to.

    It holds no pieces: what a look finds on this table is what the picture says, not
    what a world places there.
    """
    world = World()
    root = Body(name=PrefixedName("root", SETUP_NAME))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        for name, height in ((TABLE_NAME, TABLE_HEIGHT), (LID_NAME, LID_HEIGHT)):
            world.add_connection(
                FixedConnection(
                    parent=root,
                    child=_slab(name, height),
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(),
                )
            )
    world.update_forward_kinematics()
    return world


def _slab_in(world: Optional[World], name: PrefixedName, height: float) -> Body:
    """
    The body a surface of this setup is measured of.

    :param world: The world holding it, or None where there is no world to hold one, so
        that a surface still has a body to answer for it.
    :param name: What this setup calls the surface.
    :param height: How high its top face stands, in metres.
    """
    if world is None:
        return _slab(name, height)
    return world.get_body_by_name(name)


def _slab(name: PrefixedName, height: float) -> Body:
    """
    A surface of this setup as a body: a slab filling the stretch of table searched,
    with its top face at the surface's own height.

    :param name: What this setup calls the surface.
    :param height: How high its top face stands, in metres.
    """
    region = searched_workspace()
    return Body(
        name=name,
        collision=ShapeCollection(
            [
                Box(
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=(region.minimum_x + region.maximum_x) / 2,
                        y=(region.minimum_y + region.maximum_y) / 2,
                        z=height - SURFACE_THICKNESS / 2,
                    ),
                    scale=Scale(
                        region.maximum_x - region.minimum_x,
                        region.maximum_y - region.minimum_y,
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


def camera_in(world: World, frame: RgbdFrame) -> Body:
    """
    The camera, placed in the world where the look it took was taken from.

    A direction like *left of* holds from where it is read rather than of the world, so
    a statement saying one has to name that spot. A recording carries no camera, only
    the pose the look was taken at, so the camera is put in the world from the look
    itself -- the same move :func:`board_holes_in` makes for the board's holes.

    :param world: The world to place it in, from :func:`recorded_world`.
    :param frame: The camera data of the look, which is what says where it stood.
    :return: The camera, as a body a statement can say it was seen from.
    """
    camera = Body(name=PrefixedName(CAMERA_NAME, SETUP_NAME))
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=camera,
                parent_T_connection_expression=frame.point_of_view(world.root, camera),
            )
        )
    world.update_forward_kinematics()
    return camera


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
        table=table_surface(world),
        lid=lid_surface(world),
        reference_frame=None if world is None else world.root,
        world=world,
    )
