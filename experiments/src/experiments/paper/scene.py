"""
What an answer looks like in the twin: the things it names picked out of the scene,
which is otherwise drawn as the twin states it.

The picture half of a query card. A reader shown a query and a table of numbers has to
take on trust that the answer means anything in the world; shown the same answer drawn
into the scene it was asked of, they can see that it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import Dict, List, Optional, Sequence, Tuple

from experiments.paper.labels import LIFTED_ABOVE, Label, Labelling, PlacedLabel
from experiments.paper.lettering import drawn
from experiments.paper.panel import ANSWER_COLOR, CardPanel
from semantic_digital_twin.adapters.multi_sim import RegionAppearance
from semantic_digital_twin.adapters.picture import (
    UP,
    Appearance,
    Lighting,
    Picture,
    Recolored,
    Softened,
    Viewpoint,
    WorldPicture,
)
from semantic_digital_twin.spatial_computations.raytracer import RayTracer
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

# %% the picture a render takes

PICTURE_WIDTH = 1600
"""
Width of the picture a render takes when it places the camera itself, in pixels: wide
enough for a piece a few centimetres across to be drawn sharp.
"""

PICTURE_HEIGHT = 1200
"""
Height of the picture a render takes when it places the camera itself, in pixels.
"""

OVERVIEW_FROM = (1.0, -1.0, 1.0)
"""
Which way from a scene's centre the overview viewpoint stands: diagonally off it and
above, so the whole scene is seen at once.
"""

STANDING_OFF_THE_SCENE_AT_LEAST = 1.0
"""
How far from the centre of what it frames the overview viewpoint stands at the least, in
metres.
"""

OVERVIEW_DISTANCE_FACTOR = 1.5
"""
How many times the diagonal of what it frames the overview viewpoint stands off.
"""

# %% something the picture singles out


@dataclass(frozen=True)
class PickedOut:
    """
    One thing a picture singles out, and what it is drawn in.
    """

    entity: KinematicStructureEntity
    """
    The body or region to draw.
    """

    color: Color
    """
    What to draw it in.

    An opacity below one leaves it see-through, so whatever stands behind it still
    shows.
    """


# %% asking for a picture of nothing


@dataclass
class NothingToDrawError(DataclassException):
    """
    Raised when a picture is asked of a world holding no geometry to frame a camera
    around.
    """

    world: World
    """
    The world that holds nothing to draw.
    """

    def error_message(self) -> str:
        return "The world holds no geometry, so there is no scene to frame a camera on."

    def suggest_correction(self) -> str:
        return (
            "Render an episode whose world was kept, or hand SceneRender a camera of "
            "its own so it does not have to place one around what the world holds."
        )


# %% where a scene is looked at from


VIEW_T_CAMERA = HomogeneousTransformationMatrix.from_xyz_rpy().to_np()
VIEW_T_CAMERA[:3, :3] = np.array([[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
"""
The turn from the way the twin states where something looks from to the way a renderer
states a camera's own frame.

The twin faces a looker down its x-axis with y to its left and z up; a renderer points a
camera down its own negative z with y up the picture and x across it. Getting this wrong
leaves every picture facing somewhere the question was not asked from.
"""

LOOKING_DOWN_BY = np.radians(80.0)
"""
How steeply a point of view stood behind what it is asked about looks down on it, in
radians: steep enough to see over the arm the robot reaches across the table with, since
the question is asked from the robot's side and the arm is between the two; shallow
enough that left and right still read as sides rather than as up and down the picture.
"""

STANDING_BACK_AT_LEAST = 0.8
"""
How far back from what it is asked about a point of view stands at the least, in metres:

far enough that, looking down by :data:`LOOKING_DOWN_BY`, it stands above the elbow of
an arm reaching across the table.
"""

LOOKING_CLOSELY = 40.0
"""
The angle a point of view stood back that far spans from the top of its picture to the
bottom, in degrees: the pieces a question relates are a few centimetres across, and at a
wider view from that far off they are a few pixels each.
"""

UNCOLORED = Color(0.792156862745098, 0.819607843137255, 0.933333333333333)
"""
What a body the twin states no colour for is drawn in: the light grey Tracy's
description gives its table (its ``grey`` material), which the twin's reader of the
description keeps for boxes and cylinders but not for meshes, so the table would
otherwise be drawn white.
"""


@dataclass(frozen=True)
class PointOfView:
    """
    A scene looked at from somewhere standing in it, which is what a question about one
    object being to a side of another is asked from.
    """

    body: Body
    """
    The body the picture hangs on, in whose frame :attr:`pose` is given.
    """

    pose: HomogeneousTransformationMatrix = field(
        default_factory=HomogeneousTransformationMatrix.from_xyz_rpy
    )
    """
    Where in that body's frame the looker stands and which way it faces, stated the way
    the twin states a point of view: x the way it faces, y to its left, z up. The body's
    own frame by default.
    """

    field_of_view: float = 60.0
    """
    The angle the picture spans from its top to its bottom, in degrees.
    """

    width: int = PICTURE_WIDTH
    """
    Width of the picture taken from here, in pixels.
    """

    height: int = PICTURE_HEIGHT
    """
    Height of the picture taken from here, in pixels.
    """

    def viewpoint(self) -> Viewpoint:
        """
        A viewpoint standing where this point of view is and facing the way it faces, in
        the world root frame, as :attr:`body` stands right now.
        """
        world = self.body._world
        root_T_body = world.compute_forward_kinematics_np(world.root, self.body)
        return Viewpoint(
            pose=root_T_body @ self.pose.to_np() @ VIEW_T_CAMERA,
            field_of_view=self.field_of_view,
            width=self.width,
            height=self.height,
        )

    def stood_behind(
        self,
        bounds: np.ndarray,
        looking_down_by: float = LOOKING_DOWN_BY,
        minimum_distance: float = STANDING_BACK_AT_LEAST,
        distance_factor: float = 1.5,
        field_of_view: float = LOOKING_CLOSELY,
    ) -> PointOfView:
        """
        This point of view moved to where the given box fills the picture, still facing
        the way it faces: stood back from the box's centre along its own heading, raised
        to look down on the box, and narrowed to the box, so what the box holds is seen
        with its left and right where the question had them.

        A question is asked from wherever the robot happens to stand, which is as often
        as not inside its own table; the picture is taken from where the two things it
        relates can be seen.

        :param bounds: The lowest and highest corner of the box, in the frame of
            :attr:`body`, as a ``(2, 3)`` array.
        :param looking_down_by: The angle the picture looks down on the box by, in
            radians.
        :param minimum_distance: How far back the looker stands at the least, in metres.
        :param distance_factor: How many times the box's diagonal the looker stands back.
        :param field_of_view: The angle the picture spans from its top to its bottom
            from there, in degrees.
        """
        stood = self.pose.to_np()
        heading = stood[:3, 0] * np.array([1.0, 1.0, 0.0])
        heading /= np.linalg.norm(heading)
        centre = bounds.mean(axis=0)
        distance = (
            max(float(np.linalg.norm(bounds[1] - bounds[0])), minimum_distance)
            * distance_factor
        )
        position = (
            centre
            - heading * distance * np.cos(looking_down_by)
            + UP * distance * np.sin(looking_down_by)
        )
        facing = centre - position
        facing /= np.linalg.norm(facing)
        left = np.cross(UP, facing)
        left /= np.linalg.norm(left)
        pose = np.eye(4)
        pose[:3, 0] = facing
        pose[:3, 1] = left
        pose[:3, 2] = np.cross(facing, left)
        pose[:3, 3] = position
        return replace(
            self,
            pose=HomogeneousTransformationMatrix(pose),
            field_of_view=field_of_view,
        )


# %% the picture that comes out


@dataclass
class RenderedScene(CardPanel):
    """
    One picture of a scene with an answer picked out of it.
    """

    image: np.ndarray
    """
    The picture as red, green and blue in that order, shape ``(height, width, 3)`` of
    ``uint8``.
    """

    answer_mask: np.ndarray
    """
    Which pixels of the picture the answer covers, shape ``(height, width)`` of
    ``bool``.
    """

    labels: Tuple[PlacedLabel, ...] = ()
    """
    The names written on the picture and where each ended up, or none when the render
    was asked not to write any.
    """

    def pixels_of(self, color: Color) -> np.ndarray:
        """
        Where exactly the given colour was drawn, as a mask over the picture.

        :param color: The colour the twin states.
        """
        return np.all(self.image[:, :, :3] == drawn(color), axis=-1)

    def holds(self, color: Color) -> bool:
        """
        Whether the given colour was drawn anywhere in the picture.

        :param color: The colour the twin states.
        """
        return bool(np.any(self.pixels_of(color)))

    def write(self, path: Path) -> Path:
        """
        Leave this picture at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.image)
        return path


# %% the render itself


@dataclass
class SceneRender:
    """
    Draws one world with the things an answer names picked out of it.

    The twin is left exactly as it was: what is drawn in which colour is worked out for
    the picture alone, so the same world answers the next query the way it answered this
    one.
    """

    world: World
    """
    The twin the picture is drawn of.
    """

    viewpoint: Optional[Viewpoint] = None
    """
    Where the picture is taken from, or None to frame the whole scene from the overview
    viewpoint.
    """

    highlight: Color = ANSWER_COLOR
    """
    What the things the answer names are drawn in.
    """

    faded: Optional[Color] = None
    """
    What everything else is drawn in, or None to draw it in the colours the twin states.
    """

    palette: Appearance = Softened(uncolored=UNCOLORED)
    """
    What everything the picture leaves in the colours the twin states is drawn in:
    those colours softened for print, so that the answer picked out in a full colour
    stands out of the scene, and :data:`UNCOLORED` where the twin states none.
    """

    lighting: Lighting = Lighting()
    """
    How the picture is lit.
    """

    region_appearance: RegionAppearance = RegionAppearance.TRANSPARENT
    """
    How much of the regions the twin holds is drawn, since an answer naming a region has
    to be visible to be picked out.
    """

    label_answers: bool = True
    """
    Whether each thing the answer names is written over in the picture.
    """

    framed_on: Tuple[KinematicStructureEntity, ...] = ()
    """
    What the picture is framed on when it places its own camera, or nothing to frame the
    whole world.

    A real scene stands on a floor far wider than the table its work happens on, and a
    camera placed around all of it leaves the answer a few pixels across.
    """

    picked_out: Tuple[PickedOut, ...] = ()
    """
    Anything else drawn in a colour of its own rather than in the highlight or the fade.

    What lets a picture single out something beside the answer -- a ghost of where the
    answer used to stand -- without that thing having to be an answer itself.
    """

    line_width: int = 2
    """
    Thickness of the outline drawn around the answer, in pixels.
    """

    label_height: float = 0.6
    """
    Size a name is written at, as OpenCV's own multiple of its base font.
    """

    def of(self, answers: Sequence[KinematicStructureEntity]) -> RenderedScene:
        """
        Draw the world with the given things picked out of it.

        :param answers: The bodies and regions the answer names, which may be none where
            the query answered nothing.
        :raises NothingToDrawError: If the picture has to place its own viewpoint and
            the world holds no geometry to place it around.
        """
        viewpoint = self.viewpoint
        if viewpoint is None:
            viewpoint = self.overview(self.bounds())
        picture = WorldPicture(
            world=self.world,
            appearance=self.picked_out_of(answers),
            lighting=self.lighting,
            region_appearance=self.region_appearance,
        ).taken_from(viewpoint)
        return self._marked(picture, answers)

    def picked_out_of(self, answers: Sequence[KinematicStructureEntity]) -> Recolored:
        """
        What each thing of the world is drawn in so that the answer stands out of it:
        the answer in the highlight, anything singled out in its own colour, and the
        rest in the fade where one is asked for or in the palette otherwise.

        :param answers: The bodies and regions the answer names.
        """
        colors: Dict[KinematicStructureEntity, Color] = {}
        if self.faded is not None:
            colors.update(
                (entity, self.faded)
                for entity in self.world.kinematic_structure_entities
            )
        colors.update((answer, self.highlight) for answer in answers)
        colors.update(
            (singled_out.entity, singled_out.color) for singled_out in self.picked_out
        )
        return Recolored(colors=colors, otherwise=self.palette)

    # %% placing the viewpoint

    def overview(self, bounds: np.ndarray) -> Viewpoint:
        """
        A viewpoint looking diagonally down on the whole of a box from
        :data:`OVERVIEW_FROM`, far enough off to take it all in.

        :param bounds: The lowest and highest corner of the box, in the world root
            frame, as a ``(2, 3)`` array.
        """
        centre = bounds.mean(axis=0)
        distance = (
            max(
                float(np.linalg.norm(bounds[1] - bounds[0])),
                STANDING_OFF_THE_SCENE_AT_LEAST,
            )
            * OVERVIEW_DISTANCE_FACTOR
        )
        away = np.array(OVERVIEW_FROM, dtype=float)
        return Viewpoint.looking_from(
            position=centre + away / np.linalg.norm(away) * distance,
            at=centre,
            width=PICTURE_WIDTH,
            height=PICTURE_HEIGHT,
        )

    def bounds(self) -> np.ndarray:
        """
        The corners of the box the picture is framed around: what :attr:`framed_on`
        names, or the whole world's geometry where it names nothing.

        :raises NothingToDrawError: If there is no geometry to frame.
        """
        if self.framed_on:
            return self._bounds_of(self.framed_on)
        bounds = RayTracer(self.world).scene.bounds
        if bounds is None:
            raise NothingToDrawError(world=self.world)
        return np.asarray(bounds)

    def _bounds_of(self, entities: Sequence[KinematicStructureEntity]) -> np.ndarray:
        """
        The corners of the box the given things stand in, in the world root frame.

        :param entities: What to frame around.
        :raises NothingToDrawError: If none of them states any geometry.
        """
        corners = [corner for entity in entities for corner in self._corners_of(entity)]
        if not corners:
            raise NothingToDrawError(world=self.world)
        standing_in = np.vstack(corners)
        return np.vstack((standing_in.min(axis=0), standing_in.max(axis=0)))

    def _corners_of(self, entity: KinematicStructureEntity) -> List[np.ndarray]:
        """
        The eight corners of one thing's own box, placed in the world root frame.

        :param entity: The thing to measure.
        """
        mesh = entity.combined_mesh
        if mesh is None:
            return []
        lowest, highest = np.asarray(mesh.bounds)
        root_T_entity = self.world.compute_forward_kinematics_np(
            self.world.root, entity
        )
        return [
            (root_T_entity @ np.array([x, y, z, 1.0]))[:3]
            for x in (lowest[0], highest[0])
            for y in (lowest[1], highest[1])
            for z in (lowest[2], highest[2])
        ]

    # %% marking the answer

    def _marked(
        self, picture: Picture, answers: Sequence[KinematicStructureEntity]
    ) -> RenderedScene:
        """
        Mark the answer on the picture: an edge around it and around anything singled
        out, and the answer's names.

        :param picture: The picture as taken.
        :param answers: The bodies and regions the answer names.
        """
        image = picture.colors
        covered = self._covered_by(picture, answers)
        self._outline(image, covered, self.highlight)
        for singled_out in self.picked_out:
            self._outline(
                image,
                self._covered_by(picture, [singled_out.entity]),
                singled_out.color,
            )
        labels = (
            self._label(image, picture.viewpoint, answers) if self.label_answers else []
        )
        return RenderedScene(image=image, answer_mask=covered, labels=tuple(labels))

    @staticmethod
    def _covered_by(
        picture: Picture, answers: Sequence[KinematicStructureEntity]
    ) -> np.ndarray:
        """
        Which pixels of the picture show the answer: what is actually visible of it
        rather than everywhere it would be if nothing stood in front of it.

        :param picture: The picture as taken.
        :param answers: The bodies and regions the answer names.
        """
        covered = np.zeros(picture.shown.shape, dtype=bool)
        for answer in answers:
            covered |= picture.mask_of(answer)
        return covered

    def _outline(self, picture: np.ndarray, covered: np.ndarray, color: Color) -> None:
        """
        Draw the edge of every pixel one of the things the picture singles out covers.

        The recolouring alone leaves something standing behind another body with no edge
        to read it by, and a lit surface is never exactly the colour it was given, so
        the edge is also what states that colour plainly.

        :param picture: The picture to draw on, changed in place.
        :param covered: Which pixels the thing covers.
        :param color: What to draw the edge in.
        """
        edges, _ = cv2.findContours(
            covered.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(picture, edges, -1, drawn(color), self.line_width)

    def _label(
        self,
        picture: np.ndarray,
        viewpoint: Viewpoint,
        answers: Sequence[KinematicStructureEntity],
    ) -> List[PlacedLabel]:
        """
        Write each thing's name a little above where it stands in the picture, clear of
        the other names.

        :param picture: The picture to write on, changed in place.
        :param viewpoint: Where the picture was taken from, which is what says where a
            place in the world falls in it.
        :param answers: The bodies and regions the answer names.
        :return: Where each name was written.
        """
        if not answers:
            return []
        things = viewpoint.project(np.vstack([self._place_of(one) for one in answers]))
        anchors = viewpoint.project(np.vstack([self._above(one) for one in answers]))
        labels = [
            Label(text=answer.name.name, anchor=tuple(anchor), thing=tuple(thing))
            for answer, anchor, thing in zip(answers, anchors, things)
        ]
        return Labelling(height=self.label_height, line_width=self.line_width).write_on(
            picture, labels
        )

    def _place_of(self, entity: KinematicStructureEntity) -> np.ndarray:
        """
        Where one thing stands, in the world root frame.

        :param entity: The thing to place.
        :return: Its position as ``(x, y, z)`` in metres.
        """
        return self.world.compute_forward_kinematics_np(self.world.root, entity)[:3, 3]

    def _above(self, entity: KinematicStructureEntity) -> np.ndarray:
        """
        The point a little above one thing, where its name is anchored: over where it
        stands, :data:`LIFTED_ABOVE` higher than the top of its geometry, or than the
        thing itself where it states none.

        :param entity: The thing to write over.
        :return: The point as ``(x, y, z)`` in metres, in the world root frame.
        """
        place = self._place_of(entity)
        corners = self._corners_of(entity)
        top = max(corner[2] for corner in corners) if corners else place[2]
        return np.array([place[0], place[1], top + LIFTED_ABOVE])
