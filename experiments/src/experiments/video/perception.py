"""
The look, watched narrowing itself on the robot's own camera, frame after frame.

The plan's statement about the piece it sorts is read one stated condition at a time
over every frame the camera took while the robot stood still, and each condition's
picture -- the plane the detectors read, with what is left to read on it -- plays live
in a tile of a grid, all conditions at once, until the statement is read whole and the
cube it found is boxed in the last tile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import Dict, List, Optional, Sequence, Tuple

from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.node import ROBOT_TABLE_PIECES
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.overlay import DetectionOverlay
from experiments.montessori.perception.recorded_setup import (
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.step_by_step import SearchNarrowing
from experiments.montessori.pieces import KnownPieceSet
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.open_slots.plan import SORTED_PIECE
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.reasoning.predicates import Colored, SupportedBy
from semantic_digital_twin.world_description.world_entity import Body
from experiments.paper.lettering import Face
from experiments.video.cache import SceneCache
from experiments.video.canvas import (
    LABEL_SIZE,
    Anchor,
    Ink,
    Area,
    Typesetting,
    filled,
    fitted,
)
from experiments.video.sources import RecordedRun
from experiments.video.stages import PANEL_VISUAL
from experiments.video.timeline import Frame, Resolution, Scene, eased

class View(StrEnum):
    """
    The four pictures the look is watched through, in the order they appear.
    """

    RECTIFIED = "rectified"
    LID = "lid"
    COLOR = "color"
    ANSWER = "answer"


TILE_LABELS = {
    View.RECTIFIED: "rectified",
    View.LID: "on lid",
    View.COLOR: "cyan",
    View.ANSWER: "cube",
}
"""
What each picture is called, under it, in a word or two.
"""


def piece_to_sort_support_first(
    lid: Body, pieces: KnownPieceSet
) -> Match[DetectedMontessoriShape]:
    """
    The plan's statement about the piece it sorts, its two conditions stated support
    first, so the look is watched narrowing to the lid before it narrows to a colour.

    :param lid: The board's lid, as the surface a look searches names it.
    :param pieces: The set on this table, which says the colour the cube wears.
    """
    piece = a(DetectedMontessoriShape)(category=SORTED_PIECE)
    return piece.where(
        SupportedBy(piece, lid), Colored(piece, pieces.by_category[SORTED_PIECE].color)
    )

LABEL_ROOM = 36
"""
Pixels under the row of pictures their labels take.
"""

# %% what one frame's narrowing comes to


@dataclass(frozen=True)
class NarrowedFrame:
    """
    One frame of the recording read through the whole statement.
    """

    pictures: Dict[View, Frame]
    """
    The four pictures, as red, green and blue.
    """

    searched_areas: Dict[View, float]
    """
    How much table was left to read at each view, in square metres.
    """

    found: int
    """
    How many pieces answered the whole statement.
    """

    found_box: Optional[Area]
    """
    Where the piece the statement found lies in the rectified picture, or None if
    nothing did.
    """


def box_in(view, detection: DetectedMontessoriShape) -> Area:
    """
    Where a detection falls in a view: the box around its outline at the surface it
    rests on and at its top.

    :param view: The view, which says where a point on a plane falls in it.
    :param detection: The detection.
    """
    body = np.vstack(
        [
            view.to_pixels(detection.outline, height)
            for height in (detection.surface_height, detection.top_height)
        ]
    )
    left, top, width, height = cv2.boundingRect(
        body.astype(np.float32).reshape(-1, 1, 2)
    )
    return Area(left, top, width, height)


# %% the reel of narrowed frames


@dataclass
class NarrowingReel:
    """
    The statement read over a stretch of the recording's frames, computed once and kept.
    """

    run: RecordedRun
    """
    The recording.
    """

    frame_indices: Sequence[int]
    """
    Which colour images of the recording are read, in the order they play.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("perception"))
    """
    Where the narrowed frames are kept between renders.
    """

    @cached_property
    def narrowing(self) -> SearchNarrowing:
        """
        What reads the statement, fitted with the robot's own table and pieces.
        """
        return SearchNarrowing(
            perception_pipeline(recorded_world(), pieces=ROBOT_TABLE_PIECES)
        )

    @property
    def frames_per_second(self) -> float:
        """
        How fast the recording's colour images came, over the stretch read.
        """
        stamps = self.run.camera.colour_stamps()
        first, last = self.frame_indices[0], self.frame_indices[-1]
        seconds = (stamps[last] - stamps[first]) / 1e9
        return (len(self.frame_indices) - 1) / seconds if seconds > 0 else 1.0

    def _key(self, index: int, part: str) -> str:
        return f"{self.run.episode_identifier}_{index:04d}_{part}"

    def narrowed(self, index: int) -> NarrowedFrame:
        """
        One frame read through the statement, from the cache where it was kept.

        :param index: Which colour image of the recording.
        """
        kept = self.cache.record(self._key(index, "readings"))
        if kept is None:
            kept = self._compute_and_keep(index)
        box = kept["found_box"]
        return NarrowedFrame(
            pictures={
                view: self.cache.picture(self._key(index, view.value)) for view in View
            },
            searched_areas={
                view: kept["searched_areas"][view.value] for view in View
            },
            found=kept["found"],
            found_box=None if box is None else Area(*box),
        )

    def _compute_and_keep(self, index: int) -> Dict[str, object]:
        """
        Read one frame through the statement and keep everything the scene draws.
        """
        frame_data = self.run.frame(index)
        pipeline = self.narrowing.pipeline
        bare, on_lid, cyan_on_lid = self.narrowing.steps(
            frame_data, piece_to_sort_support_first(pipeline.lid.entity, pipeline.pieces)
        )
        whole_plane = self.narrowing.rectified_view(bare, frame_data)
        answer = DetectionOverlay(line_width=3).draw(
            whole_plane, MontessoriScene(shapes=list(cyan_on_lid.found))
        )
        pictures = {
            View.RECTIFIED: whole_plane.to_image(),
            View.LID: self.narrowing.rectified_view(on_lid, frame_data).to_image(),
            View.COLOR: self.narrowing.rectified_view(cyan_on_lid, frame_data).to_image(),
            View.ANSWER: answer,
        }
        for view, picture in pictures.items():
            self.cache.keep_picture(
                self._key(index, view.value), cv2.cvtColor(picture, cv2.COLOR_BGR2RGB)
            )
        box = None
        if cyan_on_lid.found:
            found = box_in(whole_plane, cyan_on_lid.found[0])
            box = [found.x, found.y, found.width, found.height]
        record = {
            "searched_areas": {
                View.RECTIFIED.value: bare.searched_area,
                View.LID.value: on_lid.searched_area,
                View.COLOR.value: cyan_on_lid.searched_area,
                View.ANSWER.value: bare.searched_area,
            },
            "found": len(cyan_on_lid.found),
            "found_box": box,
        }
        self.cache.keep_record(self._key(index, "readings"), record)
        return record

    def all_narrowed(self) -> List[NarrowedFrame]:
        """
        Every frame of the stretch, read through the statement.
        """
        return [self.narrowed(index) for index in self.frame_indices]


# %% the scene


@dataclass
class PerceptionNarrowing(Scene):
    """
    The four views of the look playing live over the recording in one row, appearing
    one after another, ending on the cube the statement found.
    """

    reel: NarrowingReel
    """
    The narrowed frames that play.
    """

    appears_at: Tuple[float, ...] = (0.0, 3.0, 6.0, 9.0)
    """
    Seconds into the scene each view appears, in their order: set from the narration,
    so each view comes up as it is spoken of.
    """

    run_for: float = 10.0
    """
    Seconds all four views play once every one is up.
    """

    resolution: Resolution = PANEL_VISUAL
    """
    The size the scene draws itself at.
    """

    gap: int = 12
    """
    Pixels between two pictures.
    """

    @cached_property
    def frames(self) -> List[NarrowedFrame]:
        return self.reel.all_narrowed()

    @property
    def duration(self) -> float:
        """
        Seconds the row is on screen, views appearing and then all running.
        """
        return self.appears_at[-1] + self.run_for

    def frame_index_at(self, seconds: float) -> int:
        """
        Which narrowed frame plays at a moment, the recording running at its own pace
        and starting over when it runs out.
        """
        return int(seconds * self.reel.frames_per_second) % len(self.frames)

    def tile(self, view: View) -> Area:
        """
        Where a view's picture lies in the row: four equal pictures, the row centred
        with its labels under it.
        """
        count = len(View)
        width = (self.resolution.width - (count - 1) * self.gap) / count
        sample = self.frames[0].pictures[view]
        height = width * sample.shape[0] / sample.shape[1]
        top = (self.resolution.height - height - LABEL_ROOM) / 2
        return Area(list(View).index(view) * (width + self.gap), top, width, height)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        narrowed = self.frames[self.frame_index_at(seconds)]
        label = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.PERCEPTION.rgb)
        for number, view in enumerate(View):
            appeared = seconds - self.appears_at[number]
            if appeared < 0:
                continue
            weight = eased(appeared / 0.25)
            tile = self.tile(view)
            frame = filled(frame, tile, Ink.TEXT.rgb)
            frame = fitted(frame, self._faded(narrowed.pictures[view], weight), tile)
            frame = label.written(frame, TILE_LABELS[view], (tile.centre[0], tile.bottom + LABEL_ROOM / 2), Anchor.CENTRE_MIDDLE)
        return frame

    @staticmethod
    def _faded(picture: Frame, weight: float) -> Frame:
        """
        The picture faded up from black.
        """
        return (picture.astype(np.float32) * weight + 0.5).astype(np.uint8)
