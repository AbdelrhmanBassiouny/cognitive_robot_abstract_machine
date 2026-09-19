"""
The perturbation experiments, all playing at once.

Each episode the robot recorded under a perturbation is one tile of a grid; every tile
plays the robot's own camera at the same speed-up, and while the robot stands still --
which is when the look is asked -- what the look finds is drawn over the picture, the
way the perception pipeline draws it.
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
from experiments.video.canvas import Anchor, Area, Ink, Typesetting, filled, fitted
from experiments.video.footage import CameraFilm
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the grid draws itself at.
"""

IDLE_MARGIN = 0.5
"""
Seconds either side of a recorded motion the robot is not counted as standing still.
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

    def __post_init__(self) -> None:
        self.film = CameraFilm(self.run)
        self.detections = DetectionsOnTheFilm(self.run, IdleStretches(self.run))

    def picture_at(self, seconds: float) -> Tuple[Frame, bool]:
        """
        The film at a moment, with the look's findings drawn where it ran near then.

        :param seconds: The moment of the recording, wrapped round its length.
        :return: The picture, and whether findings are drawn on it.
        """
        wrapped = seconds % self.film.length if self.film.length else 0.0
        image = self.film.at(wrapped)
        drawn = self.detections.picture_at(image.seconds)
        if drawn is not None:
            return drawn, True
        # the look ran on one idle frame in a few; the frame before carries its findings on
        earlier = [moment for moment in self.detections.drawn_at if 0 <= image.seconds - moment < 0.7]
        if earlier:
            return self.detections.picture_at(earlier[-1]), True
        return image.image, False


# %% the grid


@dataclass(frozen=True)
class GridLabels:
    """
    The words the grid carries: one per column and one per row, as few as will do.
    """

    columns: Sequence[str] = ("no perturbation", "piece shoved", "board moved")
    rows: Sequence[str] = ("scene stands still", "robot sorts")


@dataclass
class PerturbationMatrix(Scene):
    """
    The six episodes playing together at one speed-up, the look's findings drawn on
    each while its robot stands still.
    """

    tiles: List[List[PerturbationTile]]
    """
    The tiles, row by row, matching the labels.
    """

    labels: GridLabels = GridLabels()
    """
    What the rows and columns are called.
    """

    speed: float = 6.0
    """
    How many recorded seconds pass per second played.
    """

    played_for: float = 40.0
    """
    How long the grid plays, in seconds.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the grid draws itself at.
    """

    @property
    def duration(self) -> float:
        return self.played_for

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        margin, header, row_label, gap, footer = 16, 54, 160, 12, 44
        columns, rows = len(self.labels.columns), len(self.labels.rows)
        width = (self.resolution.width - margin - row_label - (columns - 1) * gap - margin) / columns
        # every tile keeps the camera's own aspect, so none is letterboxed
        height = width * 9 / 16
        room = self.resolution.height - margin - header - footer
        margin_top = margin + header + (room - rows * height - (rows - 1) * gap) / 2
        heading = Typesetting(size=28, face=Face.BOLD, color=Ink.TEXT.rgb)
        for column, name in enumerate(self.labels.columns):
            x = margin + row_label + column * (width + gap) + width / 2
            frame = heading.written(frame, name, (x, margin + header / 2), Anchor.CENTRE_MIDDLE)
        for row, name in enumerate(self.labels.rows):
            y = margin_top + row * (height + gap) + height / 2
            frame = heading.written(frame, name.replace(" ", "\n", 1), (margin + row_label / 2, y), Anchor.CENTRE_MIDDLE)
            for column, tile in enumerate(self.tiles[row]):
                cell = Area(margin + row_label + column * (width + gap), margin_top + row * (height + gap), width, height)
                picture, perceiving = tile.picture_at(seconds * self.speed)
                frame = filled(frame, cell, Ink.TEXT.rgb)
                frame = fitted(frame, picture, cell)
                if perceiving:
                    badge = Area(cell.x + 8, cell.y + 8, 132, 34)
                    frame = filled(frame, badge, Ink.PERCEPTION.rgb)
                    frame = Typesetting(size=20, face=Face.BOLD, color=Ink.PAPER.rgb).written(
                        frame, "perceiving", badge.centre, Anchor.CENTRE_MIDDLE
                    )
        badge = Area(self.resolution.width - 150, self.resolution.height - 52, 130, 40)
        frame = filled(frame, badge, Ink.TEXT.rgb)
        frame = Typesetting(size=26, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, f"×{self.speed:g}", badge.centre, Anchor.CENTRE_MIDDLE
        )
        return Typesetting(size=24, color=Ink.MUTED.rgb).written(
            frame, "the robot's own camera; what the look finds is drawn while the robot stands still",
            (margin + row_label, self.resolution.height - 32), Anchor.LEFT_MIDDLE,
        )
