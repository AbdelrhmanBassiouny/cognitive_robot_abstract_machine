"""
A picture of a world, drawn from the geometry the world states.

Every body is drawn with the shapes it is seen with, standing where the world's
kinematics put it, so a picture can be taken of any world -- one read back from a
database, one stood at a recorded joint state, one holding a piece fixed in a gripper --
without building a simulation of it first. What is drawn in which colour is left to an
:class:`Appearance`, so a picture can single things out or soften the whole scene for
print while the world keeps the colours it states.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import trimesh
from typing_extensions import ClassVar, List, Mapping, Optional, Sequence, Tuple

from semantic_digital_twin.adapters.multi_sim import MujocoCamera, RegionAppearance
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Quaternion,
    RotationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color, Mesh, Shape
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% drawing with no window

OFFSCREEN_PLATFORM_VARIABLE = "PYOPENGL_PLATFORM"
"""
The environment variable the drawing library reads its platform from, at the moment it
is imported.
"""


class OffscreenPlatform(StrEnum):
    """
    The platforms a picture can be drawn on without a window, by the name each answers
    to.
    """

    EGL = "egl"
    """
    Draws on a machine with a graphics device but no display.
    """

    OSMESA = "osmesa"
    """
    Draws in software, on a machine with no graphics device at all.
    """


def select_offscreen_platform() -> None:
    """
    Ask the drawing library for a platform that can draw with no window, unless one was
    already asked for.

    Its own default is a windowed platform, which cannot make a context on a machine
    with no display. A platform already named is left alone, since it is the caller's
    own choice.

    ..warning:: The library reads the variable when Python first imports it and holds
        to what it read, so this only reaches a process that has not imported it yet;
        which is why it is called before this module imports the library.
    """
    already_chosen = os.environ.get(OFFSCREEN_PLATFORM_VARIABLE, "").lower()
    if already_chosen in tuple(OffscreenPlatform):
        return
    os.environ[OFFSCREEN_PLATFORM_VARIABLE] = OffscreenPlatform.EGL


select_offscreen_platform()

import pyrender  # noqa: E402

EGL_DEVICE_VARIABLE = "EGL_DEVICE_ID"
"""
The environment variable the drawing library reads the EGL device to draw on from, as an
index into the devices the machine lists.
"""


def select_egl_device() -> None:
    """
    Name the first EGL device a display can be made on, unless one was already named or
    the run draws through another platform.

    The drawing library takes the first device listed otherwise, and a machine with a
    graphics device its driver cannot open lists that device before the software one,
    so it would draw nothing where the software device draws fine.
    """
    if os.environ.get(OFFSCREEN_PLATFORM_VARIABLE, "").lower() != OffscreenPlatform.EGL:
        return
    if EGL_DEVICE_VARIABLE in os.environ:
        return
    # Only a run drawing through EGL has its library, so it is loaded here rather than
    # with the module.
    from OpenGL import EGL
    from OpenGL.error import GLError
    from pyrender.platforms import egl

    for index, device in enumerate(egl.query_devices()):
        # PyOpenGL raises for a device no display can be made on rather than answering
        # false, so trying the device means catching that.
        try:
            made = EGL.eglInitialize(device.get_display(), None, None)
        except GLError:
            continue
        if made:
            os.environ[EGL_DEVICE_VARIABLE] = str(index)
            return


class OffscreenDrawing:
    """
    The one offscreen renderer of this process, resized to each picture.

    Kept for the life of the process rather than made per picture: deleting a renderer
    terminates the EGL display it drew on, which every other renderer in the process
    drawing on the same device -- a simulator's -- shares, so the next of their renders
    would find its display gone.
    """

    _renderer: ClassVar[Optional[pyrender.OffscreenRenderer]] = None
    """
    The renderer, once a picture has been asked for.
    """

    @classmethod
    def sized(cls, width: int, height: int) -> pyrender.OffscreenRenderer:
        """
        The renderer, ready to draw a picture of the given size.

        :param width: Width of the picture, in pixels.
        :param height: Height of the picture, in pixels.
        """
        if cls._renderer is None:
            select_egl_device()
            cls._renderer = pyrender.OffscreenRenderer(width, height)
        cls._renderer.viewport_width = width
        cls._renderer.viewport_height = height
        return cls._renderer


# %% where a picture is taken from

UP = np.array([0.0, 0.0, 1.0])
"""
Which way is up in a world.
"""

SIDEWAYS = np.array([0.0, 1.0, 0.0])
"""
The way that stands in for up in a picture looking straight up or down, which has no
up of its own: the world's y, so the picture's x stays the world's x.
"""

SIDEWAYS_AT_LEAST = 1e-6
"""
How far from straight up or down a look has to be for the world's up to still give the
picture an up.
"""

CHANNEL_MAXIMUM = 255.0
"""
The most a colour channel of a written picture holds.
"""


@dataclass(frozen=True, eq=False)
class Viewpoint:
    """
    Where a picture is taken from and how much it takes in.
    """

    pose: np.ndarray
    """
    Where the camera stands and which way it looks, in the world root frame, stated the
    way a renderer states a camera: looking down its own negative z, y up the picture
    and x across it to the right.
    """

    field_of_view: float = 45.0
    """
    The angle the picture spans from its top to its bottom, in degrees.
    """

    width: int = 640
    """
    Width of the picture, in pixels.
    """

    height: int = 480
    """
    Height of the picture, in pixels.
    """

    @classmethod
    def through(cls, camera: MujocoCamera, world: World) -> Viewpoint:
        """
        The viewpoint of a camera the world states, standing where the body it hangs on
        stands right now.

        :param camera: The camera as the world states it.
        :param world: The world the camera's body stands in.
        """
        real, x, y, z = camera.quaternion
        body_T_camera = HomogeneousTransformationMatrix.from_point_rotation_matrix(
            rotation_matrix=RotationMatrix.from_quaternion(Quaternion(x, y, z, real))
        ).to_np()
        body_T_camera[:3, 3] = camera.position
        root_T_body = world.compute_forward_kinematics_np(world.root, camera.body)
        return cls(
            pose=root_T_body @ body_T_camera,
            field_of_view=camera.fovy,
            width=int(camera.resolution[0]),
            height=int(camera.resolution[1]),
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Viewpoint)
            and np.array_equal(self.pose, other.pose)
            and (self.field_of_view, self.width, self.height)
            == (other.field_of_view, other.width, other.height)
        )

    @classmethod
    def looking_from(
        cls,
        position: Sequence[float],
        at: Sequence[float],
        field_of_view: float = 45.0,
        width: int = 640,
        height: int = 480,
    ) -> Viewpoint:
        """
        A viewpoint standing at one place and looking at another, with the picture
        upright.

        :param position: Where the camera stands, in the world root frame.
        :param at: The point in the middle of the picture, in the world root frame.
        :param field_of_view: The angle the picture spans from top to bottom, in degrees.
        :param width: Width of the picture, in pixels.
        :param height: Height of the picture, in pixels.
        """
        return cls(
            pose=facing(np.asarray(position, dtype=float), np.asarray(at, dtype=float)),
            field_of_view=field_of_view,
            width=width,
            height=height,
        )

    @property
    def focal_length(self) -> float:
        """
        How far behind the picture the camera's centre stands, in pixels.
        """
        return self.height / 2.0 / np.tan(np.radians(self.field_of_view) / 2.0)

    def project(self, points: np.ndarray) -> np.ndarray:
        """
        Where points of the world fall in the picture.

        :param points: The points, in the world root frame, as an ``(n, 3)`` array.
        :return: The pixel each falls on, x across the picture and y down it, as an
            ``(n, 2)`` array.
        """
        stacked = np.hstack(
            (np.asarray(points, dtype=float), np.ones((len(points), 1)))
        )
        in_camera = (np.linalg.inv(self.pose) @ stacked.T).T[:, :3]
        depth = -in_camera[:, 2]
        x = self.width / 2.0 + self.focal_length * in_camera[:, 0] / depth
        y = self.height / 2.0 - self.focal_length * in_camera[:, 1] / depth
        return np.column_stack((x, y))

    def camera(self) -> pyrender.PerspectiveCamera:
        """
        The camera of the drawing library this viewpoint amounts to.
        """
        return pyrender.PerspectiveCamera(
            yfov=np.radians(self.field_of_view), aspectRatio=self.width / self.height
        )


def facing(position: np.ndarray, at: np.ndarray) -> np.ndarray:
    """
    The pose of something standing at one place and looking at another, upright, stated
    the way a renderer states a camera: looking down its own negative z with y up.

    :param position: Where it stands.
    :param at: What it looks at.
    """
    forward = at - position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, UP)
    if np.linalg.norm(right) < SIDEWAYS_AT_LEAST:
        right = np.cross(forward, SIDEWAYS)
    right /= np.linalg.norm(right)
    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = np.cross(right, forward)
    pose[:3, 2] = -forward
    pose[:3, 3] = position
    return pose


# %% how the picture is lit


@dataclass(frozen=True)
class DirectionalLight:
    """
    A light shining in parallel rays from one direction, the way the sun does, so a
    scene of any size is lit evenly.
    """

    coming_from: Tuple[float, float, float]
    """
    Which way the light comes from, in the world root frame; its length does not matter.
    """

    intensity: float
    """
    How strongly it shines.
    """

    def pose(self) -> np.ndarray:
        """
        The pose the drawing library hangs the light at, shining down its own negative z.
        """
        return facing(np.asarray(self.coming_from, dtype=float), np.zeros(3))


KEY_LIGHT = DirectionalLight(coming_from=(2.4, -1.0, 3.8), intensity=3.0)
"""
The main light, from high up and a little to the side, which gives every body a lit face
and a shaded one to read its shape by.
"""

FILL_LIGHT = DirectionalLight(coming_from=(-2.6, -3.0, 1.8), intensity=1.2)
"""
The weaker light from the other side, which keeps the faces the main light leaves in
shade from going black.
"""


@dataclass(frozen=True)
class Lighting:
    """
    How a picture is lit.
    """

    ambient: float = 0.35
    """
    How much light reaches a surface no light points at, so a body facing away from every
    light is still read as a shape rather than as background.
    """

    lights: Tuple[DirectionalLight, ...] = (KEY_LIGHT, FILL_LIGHT)
    """
    The lights shining on the scene.
    """


# %% what each thing is drawn in


class Appearance(ABC):
    """
    Which colour each shape of a world is drawn in, where a picture departs from what
    the world states.
    """

    @abstractmethod
    def color_of(
        self, entity: KinematicStructureEntity, shape: Shape
    ) -> Optional[Color]:
        """
        :param entity: The body or region the shape belongs to.
        :param shape: The shape to draw.
        :return: The colour to draw it in, or None to draw it as the world states it.
        """


@dataclass(frozen=True)
class AsStated(Appearance):
    """
    Every shape drawn as the world states it.
    """

    def color_of(
        self, entity: KinematicStructureEntity, shape: Shape
    ) -> Optional[Color]:
        return None


@dataclass(frozen=True)
class Softened(Appearance):
    """
    Every colour the world states softened for print, the way :meth:`Color.softened`
    softens one; a mesh that carries its file's own colours is drawn as the file has it.
    """

    toward_white: float = 0.6
    """
    How much of each colour is mixed with white.
    """

    brightness: float = 0.94
    """
    What the mix is multiplied by afterwards.
    """

    def color_of(
        self, entity: KinematicStructureEntity, shape: Shape
    ) -> Optional[Color]:
        stated = stated_color_of(shape)
        if stated is None:
            return None
        return stated.softened(self.toward_white, self.brightness)


@dataclass(frozen=True)
class Recolored(Appearance):
    """
    Some things drawn in colours of their own, everything else as another appearance
    has it.
    """

    colors: Mapping[KinematicStructureEntity, Color]
    """
    The colour each recoloured body or region is drawn in, every shape of it alike.
    """

    otherwise: Appearance = AsStated()
    """
    How everything not recoloured is drawn.
    """

    def color_of(
        self, entity: KinematicStructureEntity, shape: Shape
    ) -> Optional[Color]:
        if entity in self.colors:
            return self.colors[entity]
        return self.otherwise.color_of(entity, shape)


def stated_color_of(shape: Shape) -> Optional[Color]:
    """
    The one colour the world states for a shape, or None for a mesh drawn in the colours
    its file states.

    :param shape: The shape to read.
    """
    if isinstance(shape, Mesh) and shape.color == Color():
        return None
    return shape.color


# %% the picture that comes out

NOTHING_SHOWN = -1
"""
What a pixel of :attr:`Picture.shown` holds where the picture shows nothing.
"""


@dataclass
class Picture:
    """
    One picture of a world, with what each pixel of it shows.
    """

    colors: np.ndarray
    """
    The picture as red, green and blue in that order, shape ``(height, width, 3)`` of
    ``uint8``.
    """

    depth: np.ndarray
    """
    How far from the camera the surface each pixel shows is, in metres, shape
    ``(height, width)``; zero where the picture shows nothing.
    """

    shown: np.ndarray
    """
    Which of :attr:`entities` is in front at each pixel, counting see-through things as
    not there, as an index into :attr:`entities`; :data:`NOTHING_SHOWN` where nothing
    is.
    """

    shown_or_see_through: np.ndarray
    """
    The same with see-through things counted, so a see-through thing is found where it
    is the nearest thing, and something behind it where it is not.
    """

    entities: Tuple[KinematicStructureEntity, ...]
    """
    The bodies and regions the picture was drawn of, in the order :attr:`shown` counts
    them.
    """

    viewpoint: Viewpoint
    """
    Where the picture was taken from.
    """

    def mask_of(self, entity: KinematicStructureEntity) -> np.ndarray:
        """
        Which pixels show one thing: where it is the nearest thing that is not
        see-through, or the nearest thing at all where it is see-through itself.

        :param entity: The body or region to find.
        :return: A ``(height, width)`` array of ``bool``, all false for a thing the
            picture was not drawn of.
        """
        if entity not in self.entities:
            return np.zeros(self.shown.shape, dtype=bool)
        index = self.entities.index(entity)
        return (self.shown == index) | (self.shown_or_see_through == index)

    def write(self, path: Path) -> Path:
        """
        Leave this picture at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return: ``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.colors)
        return path


# %% one shape as it is drawn


@dataclass
class DrawnShape:
    """
    One shape of the world as it stands in the picture.
    """

    entity: KinematicStructureEntity
    """
    The body or region the shape belongs to.
    """

    mesh: trimesh.Trimesh
    """
    The shape's mesh in the world root frame, coloured as it is drawn.
    """

    see_through: bool
    """
    Whether anything behind the shape shows through it.
    """


# %% taking the picture


@dataclass
class WorldPicture:
    """
    Takes pictures of one world from wherever it is asked to.

    The world is read, never changed: what is drawn in which colour is worked out for the
    picture alone, so the world answers the next question in the colours it states.
    """

    world: World
    """
    The world the pictures are of.
    """

    appearance: Appearance = AsStated()
    """
    What each shape is drawn in.
    """

    lighting: Lighting = Lighting()
    """
    How the pictures are lit.
    """

    background: Color = field(default_factory=Color.WHITE)
    """
    What the picture shows where nothing stands.
    """

    region_appearance: RegionAppearance = RegionAppearance.HIDDEN
    """
    How much of the regions the world holds is drawn.
    """

    def taken_from(self, viewpoint: Viewpoint) -> Picture:
        """
        Take a picture from the given viewpoint.

        :param viewpoint: Where the picture is taken from.
        """
        drawn = self.drawn_shapes()
        scene = pyrender.Scene(
            bg_color=self.background.to_rgba(),
            ambient_light=np.full(3, self.lighting.ambient),
        )
        nodes = [
            scene.add(pyrender.Mesh.from_trimesh(shape.mesh, smooth=False))
            for shape in drawn
        ]
        scene.add(viewpoint.camera(), pose=viewpoint.pose)
        for light in self.lighting.lights:
            scene.add(
                pyrender.DirectionalLight(color=np.ones(3), intensity=light.intensity),
                pose=light.pose(),
            )
        entities = tuple(dict.fromkeys(shape.entity for shape in drawn))
        renderer = OffscreenDrawing.sized(viewpoint.width, viewpoint.height)
        colors, depth = renderer.render(scene)
        shown = self._shown(renderer, scene, drawn, nodes, entities, False)
        shown_or_see_through = (
            self._shown(renderer, scene, drawn, nodes, entities, True)
            if any(shape.see_through for shape in drawn)
            else shown
        )
        return Picture(
            colors=np.ascontiguousarray(colors[:, :, :3]),
            depth=depth,
            shown=shown,
            shown_or_see_through=shown_or_see_through,
            entities=entities,
            viewpoint=viewpoint,
        )

    @staticmethod
    def _shown(
        renderer: pyrender.OffscreenRenderer,
        scene: pyrender.Scene,
        drawn: Sequence[DrawnShape],
        nodes: Sequence[pyrender.Node],
        entities: Sequence[KinematicStructureEntity],
        see_through_counted: bool,
    ) -> np.ndarray:
        """
        Which entity is in front at each pixel, read off a drawing in which every shape
        is painted flat in a colour that encodes its entity's index.

        :param renderer: The renderer the picture is drawn with.
        :param scene: The scene the picture is drawn of.
        :param drawn: The shapes in the scene.
        :param nodes: The scene's node of each of them.
        :param entities: The entities the indices count.
        :param see_through_counted: Whether see-through shapes are drawn too.
        """
        paint = IndexPaint(count=len(entities))
        painted = {
            node: paint.color_of(entities.index(shape.entity) + 1)
            for shape, node in zip(drawn, nodes)
            if see_through_counted or not shape.see_through
        }
        flat, _ = renderer.render(
            scene, flags=pyrender.RenderFlags.SEG, seg_node_map=painted
        )
        return paint.indices_of(flat) - 1

    def drawn_shapes(self) -> List[DrawnShape]:
        """
        Every shape the picture is drawn of, in the world root frame and in the colour
        it is drawn in: what each body is seen with, or what it takes up space with
        where it is seen with nothing, and the area of each region as much as
        :attr:`region_appearance` shows it.
        """
        drawn = []
        for body in self.world.bodies:
            for shape in body.visual.shapes or body.collision.shapes:
                drawn.append(self._drawn(body, shape, 1.0))
        if self.region_appearance is RegionAppearance.HIDDEN:
            return drawn
        for region in self.world.regions:
            for shape in region.area.shapes:
                drawn.append(self._drawn(region, shape, self.region_appearance.opacity))
        return drawn

    def _drawn(
        self, entity: KinematicStructureEntity, shape: Shape, opacity: float
    ) -> DrawnShape:
        """
        One shape as it is drawn.

        :param entity: The body or region the shape belongs to.
        :param shape: The shape.
        :param opacity: How much of its own opacity the shape keeps.
        """
        mesh = shape.mesh.copy()
        mesh.apply_transform(
            self.world.compute_forward_kinematics_np(self.world.root, entity)
            @ shape.origin.to_np()
        )
        color = self.appearance.color_of(entity, shape)
        if color is None and not mesh.visual.defined:
            color = shape.color
        if color is None:
            colors = face_colors_of(mesh).astype(float)
        else:
            colors = np.tile(
                np.array(color.to_rgba()) * CHANNEL_MAXIMUM, (len(mesh.faces), 1)
            )
        colors[:, 3] *= opacity
        mesh.visual = trimesh.visual.ColorVisuals(
            mesh=mesh, face_colors=np.round(colors).astype(np.uint8)
        )
        return DrawnShape(
            entity=entity,
            mesh=mesh,
            see_through=bool(np.any(colors[:, 3] < CHANNEL_MAXIMUM)),
        )


def face_colors_of(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    The colour of each face of a mesh as its file states it, one row of red, green,
    blue and opacity per face, out of the mesh's own colours or out of its material.

    :param mesh: The mesh to read.
    """
    visual = mesh.visual
    if isinstance(visual, trimesh.visual.TextureVisuals):
        visual = trimesh.visual.ColorVisuals(
            mesh=mesh, vertex_colors=visual.to_color().vertex_colors
        )
    return visual.face_colors


# %% indices painted as colours

CHECK_BYTES = np.random.default_rng(seed=0).permutation(256)
"""
A fixed shuffle of the bytes, which turns one byte of an index into a check byte that
no average of two other indices' bytes is likely to reproduce.
"""

SECOND_CHECK_BYTES = np.random.default_rng(seed=1).permutation(256)
"""
A second, independent shuffle, for a second check byte.
"""

BYTE = 0xFF
"""
The mask of one byte.
"""

BYTE_WIDTH = 8
"""
How many bits a byte holds.
"""


@dataclass(frozen=True)
class IndexPaint:
    """
    How an index is painted as a colour and read back off a flat drawing.

    The drawing is resolved from several samples per pixel, so a pixel on the edge
    between two things holds the average of their two colours rather than either.
    Each colour therefore carries a check computed from the index in a way no average
    of two colours reproduces: an index read back off a colour whose check does not
    hold is nobody's, and such a pixel reads as showing nothing. An index fitting one
    byte carries two check bytes; a longer one, one.
    """

    count: int
    """
    How many indices are painted, one upward.
    """

    @property
    def fits_one_byte(self) -> bool:
        """
        Whether every index fits one channel, leaving two for the checks.
        """
        return self.count <= BYTE

    def color_of(self, index: int) -> Tuple[int, int, int]:
        """
        The colour an index is painted in.

        :param index: The index, from one to :attr:`count`; zero is the colour of the
            background.
        """
        low = index & BYTE
        if self.fits_one_byte:
            return (low, int(CHECK_BYTES[low]), int(SECOND_CHECK_BYTES[low]))
        high = (index >> BYTE_WIDTH) & BYTE
        return (low, high, int(CHECK_BYTES[low ^ high]))

    def indices_of(self, painted: np.ndarray) -> np.ndarray:
        """
        The index each pixel of a flat drawing was painted in, or zero where its
        colour is nobody's.

        :param painted: The drawing, shape ``(height, width, 3)`` of ``uint8``.
        """
        red, green, blue = (
            painted[:, :, channel].astype(np.int64) for channel in range(3)
        )
        if self.fits_one_byte:
            index = red
            held = (green == CHECK_BYTES[red]) & (blue == SECOND_CHECK_BYTES[red])
        else:
            index = red + (green << BYTE_WIDTH)
            held = blue == CHECK_BYTES[red ^ green]
        return np.where(held, index, 0)
