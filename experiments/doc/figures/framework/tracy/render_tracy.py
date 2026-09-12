"""Render Tracy at its table, with the Montessori board and pieces, to a PNG with a
transparent background.

Two shots are defined in :data:`SHOTS`: ``idle`` (both arms raised over the table, every
piece loose) and ``inserting`` (the left gripper holding the cube over the square hole).
Run ``python render_tracy.py idle`` or ``python render_tracy.py inserting``; the joint
angles come from the pose files :mod:`pose_search` writes.

The robot's description packages (``iai_tracy_description``, ``ur_description`` and
``robotiq_2f_85_gripper_visualization``) are looked up on ``ROS_PACKAGE_PATH``, the way
ROS finds them; see the README for where to clone them from.

Needs: yourdfpy, trimesh, pyrender (with ``PYOPENGL_PLATFORM=osmesa`` on a machine
without a display), numpy, pillow.
"""

from __future__ import annotations

import colorsys
import json
import math
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "osmesa")

import numpy as np
import pyrender
import trimesh
import yourdfpy
from PIL import Image

# %% where things are

HERE = Path(__file__).parent
URDF = HERE / "tracy.urdf"
BOARD_MESH = (
    HERE.parents[3] / "src" / "experiments" / "montessori" / "resources" / "board.stl"
)
PACKAGE_URL_PREFIX = "package://"
PACKAGE_PATH_VARIABLE = "ROS_PACKAGE_PATH"


class PackageNotOnPath(LookupError):
    """
    A description package the URDF refers to is not under any directory of
    ``ROS_PACKAGE_PATH``.
    """


def find_package(name: str) -> Path:
    """
    The directory of a description package, searched one and two levels below every
    directory on ``ROS_PACKAGE_PATH``.

    :param name: The package name, as it appears after ``package://``.
    """
    for root in os.environ.get(PACKAGE_PATH_VARIABLE, "").split(os.pathsep):
        if not root:
            continue
        for candidate in (Path(root) / name, *Path(root).glob(f"*/{name}")):
            if (candidate / "package.xml").exists():
                return candidate
    raise PackageNotOnPath(
        f"{name} is not under any directory of {PACKAGE_PATH_VARIABLE}"
    )


def resolve_mesh_path(fname: str) -> str:
    """
    Turn a ``package://`` mesh reference of the URDF into a path on this machine.

    :param fname: The reference as written in the URDF.
    """
    if not fname.startswith(PACKAGE_URL_PREFIX):
        return fname
    package, _, rest = fname[len(PACKAGE_URL_PREFIX) :].partition("/")
    return str(find_package(package) / rest)


# %% colours


HUE_RANGE_DEGREES = 360.0


def pastel(
    hue_degrees: float, saturation: float = 0.38, value: float = 0.94
) -> list[int]:
    """
    An RGBA colour of the given hue, softened for print.

    :param hue_degrees: The hue on the colour circle.
    :param saturation: How far from grey.
    :param value: How far from black.
    """
    red, green, blue = colorsys.hsv_to_rgb(
        hue_degrees / HUE_RANGE_DEGREES, saturation, value
    )
    return [int(255 * red), int(255 * green), int(255 * blue), 255]


# %% the scene: the board and the pieces, in Tracy's frame (its table top is z = 0)

TABLE_TOP_Z = 0.0
BOARD_HEIGHT = 0.08
GREY = [150, 150, 150, 255]


class PieceKind(StrEnum):
    """
    The solids the loose pieces are.
    """

    BOX = "box"
    CYLINDER = "cylinder"
    TRIANGULAR_PRISM = "triangular_prism"


@dataclass(frozen=True)
class Board:
    """
    The shape-sorting board on the table.
    """

    position: tuple[float, float, float]
    """
    Its centre, in Tracy's frame.
    """

    yaw: float
    """
    Its turn about the vertical, in radians.
    """

    hue: float
    """
    The hue it is drawn in.
    """

    square_hole: tuple[float, float]
    """
    The square hole's centre on the lid, in the board's own frame, as measured on the mesh.
    """

    def transform(self) -> np.ndarray:
        """
        The board's pose as a homogeneous transform.
        """
        transform = trimesh.transformations.rotation_matrix(self.yaw, [0, 0, 1])
        transform[:3, 3] = self.position
        return transform

    def lid_z(self) -> float:
        """
        The height of the lid's top surface.
        """
        return self.position[2] + BOARD_HEIGHT / 2

    def square_hole_position(self) -> np.ndarray:
        """
        The square hole's centre on the lid, in Tracy's frame.
        """
        world = self.transform() @ np.array([*self.square_hole, 0.0, 1.0])
        return np.array([world[0], world[1], self.lid_z()])

    def mesh(self) -> trimesh.Trimesh:
        mesh = trimesh.load(str(BOARD_MESH))
        mesh.visual.face_colors = pastel(self.hue, saturation=0.3, value=0.9)
        mesh.apply_transform(self.transform())
        return mesh


@dataclass(frozen=True)
class Drawer:
    """
    One of the board's drawers with its handle, placed as the montessori world places it.
    """

    offset: tuple[float, float, float]
    """
    The drawer's centre, in the board's frame.
    """

    hue: float
    """
    The hue its front is drawn in.
    """

    size: tuple[float, float, float] = (0.09, 0.08, 0.06)
    """
    The drawer's extents.
    """

    handle_size: tuple[float, float, float] = (0.03, 0.015, 0.015)
    """
    The handle's extents.
    """

    handle_offset: tuple[float, float, float] = (-0.061, 0.0, 0.001)
    """
    The handle's centre, relative to the drawer's.
    """

    def meshes(self, board: Board) -> list[trimesh.Trimesh]:
        drawer = trimesh.creation.box(extents=self.size)
        drawer.visual.face_colors = pastel(self.hue, saturation=0.18, value=0.97)
        drawer.apply_translation(self.offset)
        handle = trimesh.creation.box(extents=self.handle_size)
        handle.visual.face_colors = GREY
        handle.apply_translation(np.add(self.offset, self.handle_offset))
        for mesh in (drawer, handle):
            mesh.apply_transform(board.transform())
        return [drawer, handle]


@dataclass(frozen=True)
class Piece:
    """
    A loose piece, sized as in :mod:`experiments.montessori.pieces`.
    """

    kind: PieceKind
    """
    The solid it is.
    """

    size: tuple[float, ...]
    """
    Its extents: edges of a box, diameter and height of a cylinder, side and height of a
    triangular prism. The last entry is always its height.
    """

    hue: float
    """
    The hue it is drawn in, a pastel version of the measured one.
    """

    position: tuple[float, float]
    """
    Where it rests on the table, in Tracy's frame.
    """

    @property
    def height(self) -> float:
        return self.size[-1]

    def mesh(self) -> trimesh.Trimesh:
        if self.kind is PieceKind.BOX:
            mesh = trimesh.creation.box(extents=self.size)
        elif self.kind is PieceKind.CYLINDER:
            diameter, height = self.size
            mesh = trimesh.creation.cylinder(
                radius=diameter / 2, height=height, sections=48
            )
        else:
            side, height = self.size
            radius = side / math.sqrt(3)
            corners = [
                [radius * math.cos(angle), radius * math.sin(angle)]
                for angle in (
                    math.pi / 2,
                    math.pi / 2 + 2 * math.pi / 3,
                    math.pi / 2 + 4 * math.pi / 3,
                )
            ]
            mesh = trimesh.creation.extrude_polygon(
                trimesh.path.polygons.Polygon(corners), height
            )
            mesh.apply_translation([0, 0, -height / 2])
        mesh.visual.face_colors = pastel(self.hue)
        return mesh

    def resting_transform(self) -> np.ndarray:
        transform = np.eye(4)
        transform[:3, 3] = [*self.position, TABLE_TOP_Z + self.height / 2]
        return transform


BOARD = Board(
    position=(0.72, 0.0, TABLE_TOP_Z + BOARD_HEIGHT / 2),
    yaw=0.0,
    hue=38,
    square_hole=(0.0332, -0.0908),
)
DRAWERS = (
    Drawer(offset=(-0.003, 0.087, 0.0), hue=200),
    Drawer(offset=(-0.003, 0.0, 0.0), hue=45),
    Drawer(offset=(-0.003, -0.087, 0.0), hue=38),
)
PIECES = {
    "cube": Piece(PieceKind.BOX, (0.03, 0.03, 0.03), hue=172, position=(0.52, 0.17)),
    "cylinder": Piece(
        PieceKind.CYLINDER, (0.028, 0.03), hue=172, position=(0.55, -0.14)
    ),
    "rectangular_prism": Piece(
        PieceKind.BOX, (0.02, 0.04, 0.03), hue=42, position=(0.48, 0.34)
    ),
    "triangular_prism": Piece(
        PieceKind.TRIANGULAR_PRISM, (0.037, 0.03), hue=42, position=(0.50, -0.32)
    ),
}


# %% the shots


@dataclass(frozen=True)
class Camera:
    """
    Where the camera stands and what it looks at, in Tracy's frame.
    """

    eye: tuple[float, float, float]
    """
    The camera's position.
    """

    target: tuple[float, float, float]
    """
    The point in the middle of the picture.
    """

    field_of_view_degrees: float
    """
    The vertical field of view.
    """

    def pose(self) -> np.ndarray:
        return look_at(self.eye, self.target)


@dataclass(frozen=True)
class HeldPiece:
    """
    A piece carried in a gripper rather than resting on the table.
    """

    piece: str
    """
    Which piece, by its key in :data:`PIECES`.
    """

    frame: str
    """
    The tool frame it is carried at.
    """


@dataclass(frozen=True)
class Shot:
    """
    One rendered picture.
    """

    pose_file: str
    """
    The JSON file of joint angles, next to this script.
    """

    camera: Camera
    """
    The view.
    """

    size: tuple[int, int]
    """
    The picture's width and height in pixels.
    """

    held: HeldPiece | None = None
    """
    The piece a gripper carries, if any.
    """

    keep_from_top: float = 1.0
    """
    The fraction of the rendered robot kept from the top, so the table's legs can be left
    out of a picture.
    """


SHOTS = {
    "idle": Shot(
        pose_file="pose_idle.json",
        camera=Camera(
            eye=(4.6, -1.3, 2.1), target=(0.5, 0.0, 0.45), field_of_view_degrees=27.0
        ),
        size=(2400, 2000),
        keep_from_top=0.74,
    ),
    "inserting": Shot(
        pose_file="pose_inserting.json",
        camera=Camera(
            eye=(1.7, -0.8, 0.95), target=(0.7, -0.04, 0.12), field_of_view_degrees=25.0
        ),
        size=(2400, 1350),
        held=HeldPiece(piece="cube", frame="l_gripper_tool_frame"),
    ),
}

KEY_LIGHT = Camera(
    eye=(3.0, -1.0, 4.0), target=(0.6, 0.0, 0.2), field_of_view_degrees=0.0
)
FILL_LIGHT = Camera(
    eye=(-2.0, -3.0, 2.0), target=(0.6, 0.0, 0.2), field_of_view_degrees=0.0
)
AMBIENT_LIGHT = (0.35, 0.35, 0.35)


# %% building the scene


def look_at(eye, target, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """
    The pose of something standing at ``eye`` and facing ``target``, with ``up`` above it.
    """
    eye, target, up = (np.asarray(v, dtype=float) for v in (eye, target, up))
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)
    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = true_up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye
    return pose


def load_robot() -> yourdfpy.URDF:
    """
    Tracy, with its meshes found on ``ROS_PACKAGE_PATH``.
    """
    return yourdfpy.URDF.load(
        str(URDF), filename_handler=resolve_mesh_path, load_collision_meshes=False
    )


def robot_meshes(robot: yourdfpy.URDF) -> list[trimesh.Trimesh]:
    """
    Every visual mesh of the robot, in Tracy's frame, at its current joint angles.
    """
    meshes = []
    for name, geometry in robot.scene.geometry.items():
        node = robot.scene.graph.geometry_nodes[name][0]
        transform = robot.scene.graph.get(node)[0]
        mesh = geometry.copy()
        mesh.apply_transform(transform)
        meshes.append(mesh)
    return meshes


def scene_meshes(held: HeldPiece | None, robot: yourdfpy.URDF) -> list[trimesh.Trimesh]:
    """
    The board, its drawers and the pieces; the held piece is carried at its tool frame,
    turned square to the board the way the fingers hold it.
    """
    meshes = [BOARD.mesh()]
    for drawer in DRAWERS:
        meshes.extend(drawer.meshes(BOARD))
    for name, piece in PIECES.items():
        mesh = piece.mesh()
        if held is not None and held.piece == name:
            carried = BOARD.transform()
            carried[:3, 3] = robot.get_transform(held.frame, "world")[:3, 3]
            mesh.apply_transform(carried)
        else:
            mesh.apply_transform(piece.resting_transform())
        meshes.append(mesh)
    return meshes


# %% rendering


def render(
    shot: Shot, robot: yourdfpy.URDF, pose: dict[str, float], output: Path
) -> None:
    """
    Render one shot and write it as a PNG whose background is transparent.

    :param shot: What to render.
    :param robot: The robot; its joint angles are set from ``pose``.
    :param pose: Joint angles by joint name; joints not named stand at zero.
    :param output: Where the PNG goes.
    """
    robot.update_cfg({name: pose.get(name, 0.0) for name in robot.actuated_joint_names})
    scene = pyrender.Scene(bg_color=(0, 0, 0, 0), ambient_light=AMBIENT_LIGHT)
    for mesh in robot_meshes(robot) + scene_meshes(shot.held, robot):
        scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
    scene.add(
        pyrender.PerspectiveCamera(yfov=np.radians(shot.camera.field_of_view_degrees)),
        pose=shot.camera.pose(),
    )
    scene.add(
        pyrender.DirectionalLight(color=np.ones(3), intensity=3.0),
        pose=KEY_LIGHT.pose(),
    )
    scene.add(
        pyrender.DirectionalLight(color=np.ones(3), intensity=1.2),
        pose=FILL_LIGHT.pose(),
    )
    renderer = pyrender.OffscreenRenderer(*shot.size)
    color, depth = renderer.render(
        scene,
        flags=pyrender.RenderFlags.RGBA | pyrender.RenderFlags.SHADOWS_DIRECTIONAL,
    )
    renderer.delete()
    alpha = ((depth > 0) * 255).astype(np.uint8)
    image = Image.fromarray(
        np.dstack([color[:, :, :3].astype(np.uint8), alpha]), "RGBA"
    )
    left, top, right, bottom = image.getbbox()
    bottom = top + int((bottom - top) * shot.keep_from_top)
    cropped = image.crop((left, top, right, bottom))
    cropped.save(output)
    print(output, cropped.size)


def main(shot_name: str) -> None:
    shot = SHOTS[shot_name]
    pose = json.loads((HERE / shot.pose_file).read_text())
    render(shot, load_robot(), pose, HERE.parent / f"tracy_{shot_name}.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "idle")
