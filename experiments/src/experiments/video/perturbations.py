"""
The perturbation experiments, all playing at once, and long-term memory asked about them.

Each episode the robot recorded under a perturbation is one tile of a grid; every tile
plays the robot's own camera at the same speed-up, and while the robot stands still --
which is when the look is asked -- what the look finds is drawn over the picture, the
way the perception pipeline draws it. A tile whose recording has ended stands on its
last frame, and once every one has, the questions long-term memory answers about these
runs are put over the grid and the episodes each answer names are lit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage
from typing_extensions import Dict, List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame, decode_compressed_color_image
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.node import ROBOT_TABLE_PIECES
from experiments.montessori.perception.overlay import CameraView, DetectionOverlay
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.recordings import (
    RAW_DEPTH_TOPIC,
    CameraTopic,
    _decode_depth,
    open_bag,
)
from experiments.paper.lettering import Face
from experiments.video.cache import SceneCache
from experiments.video.canvas import (
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Typesetting,
    dimmed,
    filled,
    fitted,
    framed,
)
from experiments.video.footage import TABLE_FRAMING, CameraFilm, Framing
from experiments.video.long_term import RememberedQuestion
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, eased

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the grid draws itself at.
"""

IDLE_MARGIN = 0.5
"""
Seconds either side of a recorded motion the robot is not counted as standing still.
"""

BAND_HEIGHT = 224
"""
How tall the band over the grid is, in pixels, where long-term memory is named and its
questions are put.
"""

BACKEND_NAME = "LongTermMemoryBackend"
"""
What the band calls the backend that answers over the grid.
"""


# %% when the robot stood still


@dataclass(frozen=True)
class RecordingStretch:
    """
    A stretch of a recording, in seconds from its start.
    """

    start: float
    end: float

    def holds(self, seconds: float) -> bool:
        return self.start <= seconds <= self.end


@dataclass
class IdleStretches:
    """
    When, in a recording, the robot was not moving: everything outside the motions the
    episode's trials recorded, shifted from trial time to recording time.
    """

    run: RecordedRun
    """
    The run.
    """

    @cached_property
    def moving(self) -> List[RecordingStretch]:
        """
        Every stretch the robot moved through, in recording time, widened by the margin.
        """
        stretches = []
        for trial in self.run.trials:
            for motion in trial.motions:
                stretches.append(
                    RecordingStretch(
                        self.run.recording_second_of(trial, motion.start_moment) - IDLE_MARGIN,
                        self.run.recording_second_of(trial, motion.end_moment) + IDLE_MARGIN,
                    )
                )
        return stretches

    def idle_at(self, seconds: float) -> bool:
        """
        Whether the robot stood still at a moment of the recording.
        """
        return not any(stretch.holds(seconds) for stretch in self.moving)


# %% what the look found, drawn on the film


@dataclass
class DetectionsOnTheFilm:
    """
    The look run over the frames the robot stood still for, every so many of them, and
    its findings drawn on those frames, computed once and kept.
    """

    run: RecordedRun
    """
    The run.
    """

    idle: IdleStretches
    """
    When the robot stood still.
    """

    every_nth: int = 2
    """
    The look runs on one idle frame in this many.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("perturbations"))
    """
    Where the drawn frames are kept between renders.
    """

    @cached_property
    def pipeline(self) -> MontessoriPerceptionPipeline:
        return perception_pipeline(recorded_world(), pieces=ROBOT_TABLE_PIECES)

    def _key(self, part: str) -> str:
        return f"{self.run.episode_identifier}_{part}"

    @cached_property
    def drawn_at(self) -> List[float]:
        """
        The moments of the recording a drawn frame was kept for, in order.
        """
        kept = self.cache.record(self._key("drawn"))
        if kept is None:
            kept = self._detect_and_keep()
        return kept["seconds"]

    def picture_at(self, seconds: float) -> Optional[Frame]:
        """
        The drawn frame kept for a moment, or None where the look was not run then.
        """
        matches = [moment for moment in self.drawn_at if abs(moment - seconds) < 1e-3]
        if not matches:
            return None
        return self.cache.picture(self._key(f"{matches[0]:09.3f}"))

    def _detect_and_keep(self) -> dict:
        camera = self.run.camera
        intrinsics = camera.intrinsics
        reference_frame_T_camera = camera.reference_frame_T_camera
        reader = open_bag(
            self.run.bag, [str(CameraTopic.COLOR), str(CameraTopic.DEPTH), RAW_DEPTH_TOPIC]
        )
        depth = None
        first = None
        index = 0
        seconds: List[float] = []
        while reader.has_next():
            topic, payload, stamp = reader.read_next()
            if topic != str(CameraTopic.COLOR):
                depth = _decode_depth(topic, payload)
                continue
            first = stamp if first is None else first
            moment = (stamp - first) / 1e9
            index += 1
            if depth is None or index % self.every_nth or not self.idle.idle_at(moment):
                continue
            message = deserialize_message(payload, CompressedImage)
            frame = RgbdFrame(
                color=decode_compressed_color_image(bytes(message.data), message.format),
                depth=depth,
                intrinsics=intrinsics,
                reference_frame_T_camera=reference_frame_T_camera,
            )
            scene = self.pipeline.detect(frame)
            drawn = DetectionOverlay(line_width=3).draw(CameraView(frame=frame), scene)
            self.cache.keep_picture(
                self._key(f"{moment:09.3f}"), cv2.cvtColor(drawn, cv2.COLOR_BGR2RGB)
            )
            seconds.append(moment)
        record = {"seconds": seconds}
        self.cache.keep_record(self._key("drawn"), record)
        return record


# %% one tile


@dataclass
class PerturbationTile:
    """
    One episode of the grid: its film, and the look's findings over it.
    """

    run: RecordedRun
    """
    The episode.
    """

    film: CameraFilm = field(init=False)
    """
    The robot's camera, decoded.
    """

    detections: DetectionsOnTheFilm = field(init=False)
    """
    What the look found while the robot stood still.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each picture is shown.
    """

    def __post_init__(self) -> None:
        self.film = CameraFilm(self.run)
        self.detections = DetectionsOnTheFilm(self.run, IdleStretches(self.run))

    def picture_at(self, seconds: float) -> Tuple[Frame, bool]:
        """
        The film at a moment, with the look's findings drawn where it ran near then.

        :param seconds: The moment of the recording; past its end, the last frame stands.
        :return: The picture, and whether findings are drawn on it.
        """
        image = self.film.at(seconds)
        drawn = self.detections.picture_at(image.seconds)
        if drawn is not None:
            return self.framing.of(drawn), True
        # the look ran on one idle frame in a few; the frame before carries its findings on
        earlier = [moment for moment in self.detections.drawn_at if 0 <= image.seconds - moment < 0.7]
        if earlier:
            return self.framing.of(self.detections.picture_at(earlier[-1])), True
        return self.framing.of(image.image), False


# %% the grid


@dataclass(frozen=True)
class GridLabels:
    """
    The words the grid carries: one per column and one per row, as few as will do.
    """

    columns: Sequence[str] = ("no perturbation", "piece shoved", "board moved")
    rows: Sequence[str] = ("scene stands still", "robot sorts")


@dataclass(frozen=True)
class GridLayout:
    """
    Where everything of the grid lies, at the size it draws itself.
    """

    resolution: Resolution
    """
    The size the grid draws itself at.
    """

    rows: int
    """
    How many rows of tiles.
    """

    columns: int
    """
    How many columns of tiles.
    """

    margin: int = 16
    header: int = 54
    row_label: int = 200
    gap: int = 12

    @property
    def band(self) -> Area:
        """
        The band over the grid, where long-term memory is named and asked.
        """
        return Area(self.margin, self.margin, self.resolution.width - 2 * self.margin, BAND_HEIGHT)

    @property
    def room(self) -> Area:
        """
        Where the tiles may lie: right of the row labels, under the header, above the
        band left for subtitles.
        """
        left = self.margin + self.row_label
        return Area(left, self.rows_top, self.resolution.width - self.margin - left, self.resolution.stage_height - self.margin - self.rows_top)

    @property
    def tile_height(self) -> float:
        # every tile keeps the camera's own aspect, so none is letterboxed; the room's
        # width or its height sets the size, whichever runs out first
        by_width = (self.room.width - (self.columns - 1) * self.gap) / self.columns * 9 / 16
        by_height = (self.room.height - (self.rows - 1) * self.gap) / self.rows
        return min(by_width, by_height)

    @property
    def tile_width(self) -> float:
        return self.tile_height * 16 / 9

    @property
    def header_y(self) -> float:
        """
        The middle of the line the column names are written on.
        """
        return self.band.bottom + self.header / 2

    @property
    def rows_top(self) -> float:
        return self.band.bottom + self.header

    def tile(self, row: int, column: int) -> Area:
        # the tiles sit together in the middle of the room's width
        across = self.columns * self.tile_width + (self.columns - 1) * self.gap
        left = self.room.x + (self.room.width - across) / 2
        return Area(
            left + column * (self.tile_width + self.gap),
            self.rows_top + row * (self.tile_height + self.gap),
            self.tile_width,
            self.tile_height,
        )


@dataclass
class PerturbationMatrix(Scene):
    """
    The six episodes playing together at one speed-up, the look's findings drawn on
    each while its robot stands still; then, every recording ended, long-term memory
    asked which of them the cube moved in and which the robot picked it up in.
    """

    tiles: List[List[PerturbationTile]]
    """
    The tiles, row by row, matching the labels.
    """

    labels: GridLabels = GridLabels()
    """
    What the rows and columns are called.
    """

    questions: List[RememberedQuestion] = field(default_factory=list)
    """
    What long-term memory is asked once the recordings have ended, in order.
    """

    speed: float = 10.0
    """
    How many recorded seconds pass per second played.
    """

    question_for: float = 6.0
    """
    Seconds each question takes, from arriving to its answer having been read.
    """

    settle_for: float = 1.0
    """
    Seconds the grid stands still after the last recording ends, before the first
    question, where the questions wait for the recordings.
    """

    asked_from: Optional[float] = None
    """
    Seconds into the scene the first question comes, the recordings still playing under
    it and to the scene's end; None for the questions to wait until the longest
    recording has ended and the grid has settled.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the grid draws itself at.
    """

    @property
    def layout(self) -> GridLayout:
        return GridLayout(self.resolution, rows=len(self.tiles), columns=len(self.labels.columns))

    @cached_property
    def longest(self) -> float:
        """
        Seconds the longest recording plays for at the grid's speed.
        """
        return max(tile.film.length for row in self.tiles for tile in row) / self.speed

    @property
    def runs_for(self) -> float:
        """
        Seconds the recordings play: until the longest has ended, or to the scene's end
        where the questions do not wait for them.
        """
        return self.longest if self.asked_from is None else self.duration

    @property
    def asked_at(self) -> float:
        """
        Seconds into the scene the first question comes.
        """
        return self.longest + self.settle_for if self.asked_from is None else self.asked_from

    @property
    def duration(self) -> float:
        return self.asked_at + self.question_for * len(self.questions)

    def question_at(self, seconds: float) -> Optional[Tuple[RememberedQuestion, float]]:
        """
        The question up at a moment and how far along it is, or None before the first.
        """
        since = seconds - self.asked_at
        if since < 0 or not self.questions:
            return None
        index = min(int(since / self.question_for), len(self.questions) - 1)
        return self.questions[index], min((since - index * self.question_for) / self.question_for, 1.0)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        asked = self.question_at(seconds)
        lit = eased((asked[1] - 0.55) / 0.2) if asked else 0.0
        frame = self._band(frame, asked)
        frame = self._grid(frame, seconds, asked[0] if asked else None, lit)
        return self._speed_badge(frame)

    # %% the grid itself

    def _grid(self, frame: Frame, seconds: float, question: Optional[RememberedQuestion], lit: float) -> Frame:
        """
        The tiles, each named by row and column, the look's findings badged where they
        are drawn, and the episodes a question's answer names lit.

        :param frame: The frame drawn on.
        :param seconds: The moment of the scene.
        :param question: The question whose answer lights tiles, or None.
        :param lit: How far the answer has lit its tiles, from zero to one.
        """
        layout = self.layout
        heading = Typesetting(size=28, face=Face.BOLD, color=Ink.TEXT.rgb)
        for column, name in enumerate(self.labels.columns):
            frame = heading.written(frame, name, (layout.tile(0, column).centre[0], layout.header_y), Anchor.CENTRE_MIDDLE)
        for row, name in enumerate(self.labels.rows):
            cell = layout.tile(row, 0)
            frame = heading.written(frame, name.replace(" ", "\n", 1), (layout.margin + layout.row_label / 2, cell.centre[1]), Anchor.CENTRE_MIDDLE)
            for column, tile in enumerate(self.tiles[row]):
                cell = layout.tile(row, column)
                picture, perceiving = tile.picture_at(min(seconds, self.runs_for) * self.speed)
                named = question is not None and question.names(tile.run.episode_identifier)
                if lit > 0 and not named:
                    picture = dimmed(picture, 0.55 * lit)
                frame = filled(frame, cell, Ink.TEXT.rgb)
                frame = fitted(frame, picture, cell)
                if perceiving:
                    frame = self._badge(frame, cell, "perceiving", Ink.PERCEPTION.rgb)
                if lit > 0 and named:
                    frame = framed(frame, cell.inset(-3), Ink.ANSWER.rgb, thickness=6)
                    frame = self._badge(frame, cell, question.lit_as, Ink.ANSWER.rgb)
        return frame

    @staticmethod
    def _badge(frame: Frame, cell: Area, text: str, color) -> Frame:
        lettering = Typesetting(size=20, face=Face.BOLD, color=Ink.PAPER.rgb)
        # low in the tile: the board lies along its top edge
        badge = Area(cell.x + 8, cell.bottom - 8 - 34, lettering.width_of(text) + 24, 34)
        frame = filled(frame, badge, color)
        return lettering.written(frame, text, badge.centre, Anchor.CENTRE_MIDDLE)

    # %% the band over it

    def _band(self, frame: Frame, asked: Optional[Tuple[RememberedQuestion, float]]) -> Frame:
        """
        Long-term memory named over the grid, and while a question is up, the question,
        the query behind it and, in its turn, the answer.

        :param frame: The frame drawn on.
        :param asked: The question up and how far along it is, or None.
        """
        band = self.layout.band
        name = Typesetting(size=26, face=Face.BOLD, color=Ink.MEMORY.rgb)
        if asked is None:
            frame = name.written(frame, BACKEND_NAME, (band.x + 4, band.y + 24), Anchor.LEFT_MIDDLE)
            return Typesetting(size=24, color=Ink.MUTED.rgb).written(
                frame,
                "every run is recorded to the results database as it happens, and asked about",
                (band.x + 4, band.y + 62),
                Anchor.LEFT_MIDDLE,
            )
        question, progress = asked
        card = band
        frame = filled(frame, card, Ink.PAPER.rgb)
        frame = framed(frame, card, Ink.ASKED.rgb, thickness=3)
        frame = name.written(frame, BACKEND_NAME, (card.x + 24, card.y + 28), Anchor.LEFT_MIDDLE)
        frame = Typesetting(size=30, face=Face.BOLD).written(
            frame, question.english, (card.x + 24, card.y + 68), Anchor.LEFT_MIDDLE
        )
        code = CodeTypesetting(size=20)
        for number, line in enumerate(question.statement):
            frame = code.written(frame, line, (card.x + 24, card.y + 108 + number * 27))
        if eased((progress - 0.45) / 0.15) > 0:
            on_screen = sum(question.names(tile.run.episode_identifier) for row in self.tiles for tile in row)
            answer = f"→ {len(question.episodes)} episodes; {on_screen} of them are on screen"
            frame = Typesetting(size=28, face=Face.BOLD, color=Ink.ANSWER.rgb).written(
                frame, answer, (card.right - 24, card.y + 68), Anchor.RIGHT_MIDDLE
            )
        return frame

    def _speed_badge(self, frame: Frame) -> Frame:
        """
        The speed-up, in the band's top right corner.
        """
        layout = self.layout
        # the band's top right corner is free whether or not a question is up
        badge = Area(layout.band.right - 12 - 130, layout.band.y + 12, 130, 40)
        frame = filled(frame, badge, Ink.TEXT.rgb)
        return Typesetting(size=26, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, f"×{self.speed:g}", badge.centre, Anchor.CENTRE_MIDDLE
        )
