"""
The simulated Montessori rig: where the camera stands over the table, and the pipeline
that reads what it sees.

The counterpart of :mod:`~experiments.montessori.perception.recorded_setup`, which
describes the real table the six captures were taken over. The real one has to restate
what a recording carries no world for; this one reads the same things off the twin that
built the scene, so a surface is measured of the very body a statement names.
"""

from __future__ import annotations

from dataclasses import replace

from experiments.montessori.perception.pipeline import (
    BoardDetector,
    BoardHoleLayout,
    MontessoriPerceptionPipeline,
    default_look_rules,
)
from experiments.montessori.perception.simulated_camera import SimulatedCamera
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import ShapeSortingBoard
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    RotationMatrix,
    Vector3,
)
from semantic_digital_twin.world import World

# %% the camera, as the real one stands

CAMERA_NAME = "camera"
"""
What this setup calls the camera it puts over the table.
"""

CAMERA_HEIGHT_ABOVE_THE_TABLE = 0.935
"""
How high above the table top the camera stands, in metres.

Read off the shipped captures rather than chosen: the real camera stands this far above
the table :mod:`~experiments.montessori.perception.recorded_setup` measures, and a
simulated look is worth no more than the real one it stands in for. Rounded to the
millimetre, which is finer than the rig was ever placed to.
"""

CAMERA_FIELD_OF_VIEW = 51.6
"""
The angle the camera sees from the top of its picture to its bottom, in degrees.

The captures' own, read back out of the intrinsics they carry.
"""

CAMERA_PICTURE_WIDTH = 1920
"""
Width of the picture the camera takes, in pixels: the captures' own.
"""

CAMERA_PICTURE_HEIGHT = 1080
"""
Height of the picture the camera takes, in pixels: the captures' own.
"""

BOARD_SCALE_AGAINST_THE_MESH = 1.0
"""
How large the board in a simulated scene is against the mesh it is modelled by.

A simulated board *is* the mesh, so it reads as the mesh's own size. The real board is
smaller than the mesh that models it, which is why
:mod:`~experiments.montessori.perception.recorded_setup` states a different number for
the same thing.
"""


def camera_over_the_table(world: World) -> SimulatedCamera:
    """
    A camera looking down at the middle of the table this world sets its scene on.

    Placed where the real one stands rather than where the whole scene happens to fit:
    the point of a simulated look is that a backend answers it the way it answers a
    real one, which a viewpoint nothing was ever measured from would not test.

    :param world: The world the camera is added to and looks at.
    :return: The camera, already attached to the world and ready to be started.
    """
    table = table_surface(world)
    looking_at = Point3(
        x=(table.region.minimum_x + table.region.maximum_x) / 2.0,
        y=(table.region.minimum_y + table.region.maximum_y) / 2.0,
        z=table.height,
    )
    return looking_down_at(world, looking_at)


def looking_down_at(
    world: World,
    target: Point3,
    height_above_the_target: float = CAMERA_HEIGHT_ABOVE_THE_TABLE,
) -> SimulatedCamera:
    """
    A camera hung over a spot in the world, looking straight down at it.

    The picture is turned the way the real camera's is: its right is the world's
    negative y and its downward direction the world's negative x, so a relation read off
    a simulated look reads the way the same relation reads off a capture.

    :param world: The world the camera is added to.
    :param target: The spot the camera looks at, in the world root's frame.
    :param height_above_the_target: How far above that spot the camera hangs, in metres.
    :return: The camera, already attached to the world.
    """
    root_R_camera = RotationMatrix.from_vectors(
        x=Vector3(0.0, -1.0, 0.0), z=Vector3(0.0, 0.0, 1.0)
    )
    quaternion_x, quaternion_y, quaternion_z, quaternion_real = (
        HomogeneousTransformationMatrix.from_point_rotation_matrix(
            rotation_matrix=root_R_camera
        )
        .to_quaternion()
        .to_np()
        .tolist()
    )
    camera = MujocoCamera(
        name=CAMERA_NAME,
        body=world.root,
        position=[
            float(target.x),
            float(target.y),
            float(target.z) + height_above_the_target,
        ],
        quaternion=[quaternion_real, quaternion_x, quaternion_y, quaternion_z],
        fovy=CAMERA_FIELD_OF_VIEW,
        resolution=[float(CAMERA_PICTURE_WIDTH), float(CAMERA_PICTURE_HEIGHT)],
    )
    world.root.simulator_additional_properties.append(camera)
    return SimulatedCamera(world=world, camera=camera)


# %% the surfaces a look is answered over


def table_surface(world: World) -> WorkspaceSurface:
    """
    The table the scene is set on, measured of the world's own body for it.

    :param world: The world the scene stands in.
    """
    return WorkspaceSurface.of(
        world.get_semantic_annotations_by_type(Table)[0],
        world.root,
    )


def lid_surface(world: World) -> WorkspaceSurface:
    """
    The board's lid, the second surface pieces rest on.

    Searched over the same stretch as the table, since a look at the scene rectifies the
    one picture onto both planes and is bounded by where the camera can see rather than
    by how far the board reaches.

    :param world: The world the scene stands in.
    """
    board = world.get_semantic_annotations_by_type(ShapeSortingBoard)[0]
    measured = WorkspaceSurface.of(board, world.root)
    return replace(measured, region=table_surface(world).region)


def board_detector() -> BoardDetector:
    """
    :return: The detector that looks for a simulated board, at the size such a board is.
    """
    return BoardDetector(
        layout=BoardHoleLayout.of_board_mesh(BOARD_SCALE_AGAINST_THE_MESH)
    )


def perception_pipeline(world: World) -> MontessoriPerceptionPipeline:
    """
    The pipeline that reads a look at this simulated scene.

    :param world: The world the look is taken of and reported in.
    """
    return MontessoriPerceptionPipeline(
        table=table_surface(world),
        lid=lid_surface(world),
        look_rules=default_look_rules(board_detector=board_detector()),
        reference_frame=world.root,
        world=world,
    )
