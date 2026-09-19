"""
Working memory checking the relation the plan states, in the twin.

The cube the look found is spawned into the world the robot plans in, the view flies
down onto it, and the relation is read off the geometry the way the predicate reads it:
the two bodies' bounding boxes, how far they overlap vertically, and whether that is
little enough to be resting rather than clipping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import cv2
import numpy as np
from typing_extensions import List, Optional, Tuple

from experiments.paper.lettering import Face
from experiments.video.cache import SceneCache
from experiments.video.canvas import Anchor, Area, Ink, Typesetting, filled, fitted
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, eased
from semantic_digital_twin.adapters.picture import Viewpoint, WorldPicture
from semantic_digital_twin.datastructures.variables import SpatialVariables
from semantic_digital_twin.reasoning.predicates import SupportedBy
from semantic_digital_twin.spatial_types.numeric import NumericTransform
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.world_entity import Body

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the scene draws itself at.
"""

INPAINT_RADIUS = 5
"""
How far around a painted-out pixel the picture is read to fill it, in pixels.
"""

# %% what the predicate reads


@dataclass(frozen=True)
class BoxCorners:
    """
    An axis-aligned box in the world root frame.
    """

    lower: np.ndarray
    """
    Its lowest corner.
    """

    upper: np.ndarray
    """
    Its highest corner.
    """

    @classmethod
    def around(cls, body: Body, world: World) -> BoxCorners:
        """
        The box around a body's collision shapes, in the world root frame.
        """
        bounds = body.collision.as_bounding_box_collection_at_origin(
            NumericTransform.identity(world.root)
        ).enclosing_bounds
        return cls(lower=np.asarray(bounds.lower, dtype=float), upper=np.asarray(bounds.upper, dtype=float))

    def intersected(self, other: BoxCorners) -> Optional[BoxCorners]:
        """
        Where this box and another overlap, or None where they do not.
        """
        lower = np.maximum(self.lower, other.lower)
        upper = np.minimum(self.upper, other.upper)
        if np.any(upper <= lower):
            return None
        return BoxCorners(lower=lower, upper=upper)

    @property
    def corners(self) -> np.ndarray:
        """
        All eight corners, as an ``(8, 3)`` array.
        """
        return np.array(
            [
                [x, y, z]
                for x in (self.lower[0], self.upper[0])
                for y in (self.lower[1], self.upper[1])
                for z in (self.lower[2], self.upper[2])
            ]
        )

    @property
    def edges(self) -> List[Tuple[int, int]]:
        """
        Which corners each of the twelve edges joins.
        """
        return [
            (a, b)
            for a in range(8)
            for b in range(a + 1, 8)
            if bin(a ^ b).count("1") == 1
        ]


@dataclass(frozen=True)
class SupportReading:
    """
    What the predicate read off the two bodies.
    """

    supported: BoxCorners
    """
    The box around the body that may be resting.
    """

    supporting: BoxCorners
    """
    The box around the body that may be holding it up.
    """

    vertical_overlap: float
    """
    How far the two boxes overlap vertically, in metres, as the predicate measures it
    in the supported body's own frame.
    """

    maximum: float
    """
    The overlap past which the reading is refused as clipping, in metres.
    """

    holds: bool
    """
    What the predicate answered.
    """

    @classmethod
    def taken(cls, supported: Body, supporting: Body, world: World) -> SupportReading:
        """
        Read the relation the way the predicate does, keeping the numbers it read.
        """
        predicate = SupportedBy(supported, supporting)
        origin = NumericTransform.identity(supported)
        intersection = (
            supported.collision.as_bounding_box_collection_at_origin(origin).event
            & supporting.collision.as_bounding_box_collection_at_origin(origin).event
        ).bounding_box()
        overlap = 0.0
        if not intersection.is_empty():
            overlap = sum(
                simple.upper - simple.lower
                for simple in intersection[SpatialVariables.z.value].simple_sets
            )
        return cls(
            supported=BoxCorners.around(supported, world),
            supporting=BoxCorners.around(supporting, world),
            vertical_overlap=float(overlap),
            maximum=predicate.maximum_intersection_height,
            holds=predicate(),
        )

    @property
    def reading_line(self) -> str:
        """
        The comparison the predicate makes, as text.
        """
        sign = "<" if self.vertical_overlap < self.maximum else "≥"
        millimetres = self.vertical_overlap * 1000
        shown = f"{millimetres:.1f}" if millimetres < 1 else f"{millimetres:.0f}"
        return f"vertical overlap {shown} mm {sign} {self.maximum:.1f} m"


# %% pictures of the twin


def stood_at(world: World, body: Body, pose: np.ndarray) -> None:
    """
    Stand a fixed body somewhere else, by replacing the connection that holds it.

    :param world: The world the body stands in.
    :param body: The body, held by a fixed connection.
    :param pose: Where it goes, in its parent's frame, as a four by four matrix.
    """
    held_by = body.parent_connection
    with world.modify_world():
        world.remove_connection(held_by)
        world.add_connection(
            FixedConnection.create_with_dofs(
                world,
                held_by.parent,
                body,
                parent_T_connection_expression=HomogeneousTransformationMatrix(
                    pose, reference_frame=held_by.parent, child_frame=body
                ),
            )
        )


@dataclass
class TwinPictures:
    """
    Pictures of the run's world along a flight from an overview down onto the cube,
    drawn once and kept.
    """

    run: RecordedRun
    """
    The run whose world is drawn.
    """

    cube_name: str = "perceived/cube_3"
    """
    The body the look spawned.
    """

    board_name: str = "perceived/board"
    """
    The body it rests on.
    """

    flight_pictures: int = 60
    """
    How many pictures the flight is drawn as.
    """

    overview_from: Tuple[float, float, float] = (1.25, -0.95, 0.85)
    """
    Where the flight starts, in metres from the cube: beyond the board, so the robot
    stands in the background rather than in the way.
    """

    close_from: Tuple[float, float, float] = (0.26, 0.16, 0.17)
    """
    Where the flight ends, in metres from the cube.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size each picture is drawn at.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("twin"))
    """
    Where the pictures are kept between renders.
    """

    @cached_property
    def world(self) -> World:
        """
        The run's world, stood as it was when the look was taken.
        """
        world = self.run.world
        self.run.kept.trial(self.run.trial.number).joint_trace.at(0.0).restore_into(world)
        cube = self.run.body(self.cube_name)
        stood_at(world, cube, self.run.pose_before_it_moved(cube))
        return world

    @cached_property
    def cube(self) -> Body:
        self.world
        return self.run.body(self.cube_name)

    @cached_property
    def board(self) -> Body:
        self.world
        return self.run.body(self.board_name)

    @cached_property
    def reading(self) -> SupportReading:
        """
        What the predicate reads off the cube and the board.
        """
        return SupportReading.taken(self.cube, self.board, self.world)

    @cached_property
    def cube_at(self) -> np.ndarray:
        """
        Where the cube stands, in the world root frame.
        """
        return self.world.compute_forward_kinematics_np(self.world.root, self.cube)[:3, 3]

    def viewpoint(self, progress: float) -> Viewpoint:
        """
        Where the view stands part of the way along its flight, from the overview to
        close over the cube.

        :param progress: How far along, from zero to one.
        """
        far = self.cube_at + np.array(self.overview_from)
        near = self.cube_at + np.array(self.close_from)
        at_far = self.cube_at + np.array([-0.15, 0.0, -0.08])
        eased_progress = eased(progress)
        return Viewpoint.looking_from(
            far + (near - far) * eased_progress,
            at_far + (self.cube_at - at_far) * eased_progress,
            field_of_view=42.0,
            width=self.resolution.width,
            height=self.resolution.height,
        )

    @cached_property
    def drawing(self) -> WorldPicture:
        """
        What draws the world, kept for every picture since it holds the meshes it
        loaded.
        """
        return WorldPicture(world=self.world)

    def _key(self, part: str) -> str:
        flight = "_".join(
            f"{value:+.2f}" for value in (*self.overview_from, *self.close_from)
        )
        return f"{self.run.episode_identifier}_{self.resolution.width}_{flight}_{part}"

    def _drawn(self, key: str, viewpoint: Viewpoint) -> Frame:
        kept = self.cache.picture(key)
        if kept is None:
            kept = self.drawing.taken_from(viewpoint).colors
            self.cache.keep_picture(key, kept)
        return kept

    def before_the_spawn(self) -> Frame:
        """
        The overview without the cube in it.
        """
        key = self._key("before")
        kept = self.cache.picture(key)
        if kept is None:
            picture = self.drawing.taken_from(self.viewpoint(0.0))
            mask = cv2.dilate(
                picture.mask_of(self.cube).astype(np.uint8), np.ones((5, 5), np.uint8)
            )
            kept = cv2.inpaint(picture.colors, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)
            self.cache.keep_picture(key, kept)
        return kept

    def along_the_flight(self, progress: float) -> Frame:
        """
        The picture nearest a point of the flight.
        """
        number = int(round(min(max(progress, 0.0), 1.0) * (self.flight_pictures - 1)))
        return self._drawn(
            self._key(f"flight_{number:03d}"),
            self.viewpoint(number / (self.flight_pictures - 1)),
        )


# %% the scene


@dataclass
class WorkingMemoryCheck(Scene):
    """
    The cube spawned into the twin, the view flying onto it, and the relation read off
    the two boxes.
    """

    pictures: TwinPictures
    """
    The twin, drawn.
    """

    spawn_at: float = 1.5
    """
    When the cube appears, in seconds.
    """

    flight_from: float = 3.5
    """
    When the view starts flying, in seconds.
    """

    flight_for: float = 5.0
    """
    How long the flight takes, in seconds.
    """

    boxes_for: float = 8.0
    """
    How long the boxes and the reading are shown once the view has landed.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    @property
    def duration(self) -> float:
        return self.flight_from + self.flight_for + self.boxes_for

    def picture_at(self, seconds: float) -> Frame:
        if seconds < self.flight_from:
            return self._spawning(seconds)
        progress = (seconds - self.flight_from) / self.flight_for
        frame = self.pictures.along_the_flight(progress)
        if progress < 1.0:
            return self._captioned(frame, "the cube the look found, spawned into working memory")
        return self._read(frame, seconds - self.flight_from - self.flight_for)

    def _spawning(self, seconds: float) -> Frame:
        before = self.pictures.before_the_spawn()
        after = self.pictures.along_the_flight(0.0)
        weight = eased((seconds - self.spawn_at) / 0.8) if seconds >= self.spawn_at else 0.0
        frame = (before * (1 - weight) + after * weight + 0.5).astype(np.uint8)
        caption = "working memory, as the robot believes the table stands"
        if weight > 0.5:
            caption = "the cube the look found, spawned into working memory"
        return self._captioned(frame, caption)

    def _read(self, frame: Frame, seconds: float) -> Frame:
        reading = self.pictures.reading
        viewpoint = self.pictures.viewpoint(1.0)
        drawn = frame.copy()
        if seconds > 0.5:
            self._draw_box(drawn, reading.supporting, viewpoint, Ink.SIMULATION.rgb, eased((seconds - 0.5) / 0.6))
        if seconds > 1.2:
            self._draw_box(drawn, reading.supported, viewpoint, Ink.PERCEPTION.rgb, eased((seconds - 1.2) / 0.6))
        overlap = reading.supported.intersected(reading.supporting)
        if seconds > 2.4 and overlap is not None:
            self._draw_band(drawn, overlap, viewpoint)
        caption = "SupportedBy(cube, lid): the two bounding boxes"
        if seconds > 2.4:
            caption = reading.reading_line
        if seconds > 4.5:
            caption = f"SupportedBy(cube, lid) → {reading.holds}"
        return self._captioned(drawn, caption, verdict=seconds > 4.5)

    @staticmethod
    def _draw_box(frame: Frame, box: BoxCorners, viewpoint: Viewpoint, color, weight: float) -> None:
        corners = viewpoint.project(box.corners)
        overlay = frame.copy()
        for a, b in box.edges:
            cv2.line(overlay, tuple(corners[a].round().astype(int)), tuple(corners[b].round().astype(int)), color, 3, cv2.LINE_AA)
        cv2.addWeighted(overlay, weight, frame, 1 - weight, 0, frame)

    @staticmethod
    def _draw_band(frame: Frame, band: BoxCorners, viewpoint: Viewpoint) -> None:
        # the band is thin; draw it as its own box, filled, so the overlap is seen at all
        thick = BoxCorners(lower=band.lower - np.array([0.0, 0.0, 0.004]), upper=band.upper + np.array([0.0, 0.0, 0.004]))
        corners = viewpoint.project(thick.corners)
        overlay = frame.copy()
        hull = cv2.convexHull(corners.astype(np.float32).reshape(-1, 1, 2)).astype(int)
        cv2.fillPoly(overlay, [hull], Ink.SIMULATION.rgb)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    def _captioned(self, frame: Frame, caption: str, verdict: bool = False) -> Frame:
        canvas = self.resolution.blank(255)
        canvas = fitted(canvas, frame, Area(0, 0, self.resolution.width, self.resolution.height - 80))
        colour = Ink.FIRED.rgb if verdict else Ink.SIMULATION.rgb
        return Typesetting(size=30, face=Face.BOLD if verdict else Face.REGULAR, color=colour).written(
            canvas, caption, (self.resolution.width / 2, self.resolution.height - 40), Anchor.CENTRE_MIDDLE
        )
