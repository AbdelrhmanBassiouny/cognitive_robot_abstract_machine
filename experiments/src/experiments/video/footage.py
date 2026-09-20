"""
What the robot's camera recorded, played back as film.

A recording keeps one colour image in ten, so played at its own pace it would be a
slide show; a stretch of it is played faster instead, and says by how much.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import List, Optional, Sequence

from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import CameraTopic, open_bag
from experiments.paper.lettering import Face
from experiments.video.cache import SceneCache
from experiments.video.canvas import Anchor, Area, Ink, Typesetting, fitted, filled
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size a film draws itself at.
"""

# %% what of a picture is shown


@dataclass(frozen=True)
class Framing:
    """
    The margins cut off a camera picture before it is shown, in the picture's pixels.

    It is applied to the drawn picture, after any findings are drawn on it, so nothing
    drawn in the camera's pixel coordinates has to move.
    """

    top: int = 0
    left: int = 0
    right: int = 0
    bottom: int = 0

    def of(self, picture: Frame) -> Frame:
        """
        :param picture: A picture.
        :return: What is left of it inside the margins.
        """
        height, width = picture.shape[:2]
        return picture[self.top : height - self.bottom, self.left : width - self.right]


TABLE_FRAMING = Framing(top=170, left=100, right=202)
"""
The framing of the robot's camera that shows the table alone, the floor and the stand
around it cut off: the table's near edge lies 170 pixels down a full HD picture, and
the right margin keeps the picture at sixteen by nine.
"""

# %% the colour images of a recording


@dataclass(frozen=True)
class TimedImage:
    """
    One colour image of a recording and when it was taken.

    The image itself is read from the cache when asked for, so a film of thousands of
    images does not hold them all at once.
    """

    seconds: float
    """
    Seconds since the recording began.
    """

    cache: SceneCache
    """
    Where the image is kept.
    """

    key: str
    """
    What it is kept as.
    """

    @property
    def image(self) -> Frame:
        """
        The image, as red, green and blue.
        """
        return self.cache.picture(self.key)


@dataclass
class CameraFilm:
    """
    Every colour image a recording holds, decoded once and kept.
    """

    run: RecordedRun
    """
    The recording's run.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("footage"))
    """
    Where the decoded images are kept between renders.
    """

    @cached_property
    def images(self) -> List[TimedImage]:
        """
        The recording's colour images, in order.
        """
        key = f"{self.run.episode_identifier}_stamps"
        stamps = self.cache.record(key)
        if stamps is None:
            stamps = self._decode_and_keep(key)
        return [
            TimedImage(seconds=seconds, cache=self.cache, key=self._image_key(index))
            for index, seconds in enumerate(stamps["seconds"])
        ]

    def _image_key(self, index: int) -> str:
        return f"{self.run.episode_identifier}_{index:04d}"

    def _decode_and_keep(self, key: str) -> dict:
        reader = open_bag(self.run.bag, [str(CameraTopic.COLOR)])
        seconds: List[float] = []
        first: Optional[int] = None
        while reader.has_next():
            _, payload, stamp = reader.read_next()
            first = stamp if first is None else first
            message = deserialize_message(payload, CompressedImage)
            image = decode_compressed_color_image(bytes(message.data), message.format)
            self.cache.keep_picture(
                self._image_key(len(seconds)), cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            )
            seconds.append((stamp - first) / 1e9)
        record = {"seconds": seconds}
        self.cache.keep_record(key, record)
        return record

    @property
    def length(self) -> float:
        """
        Seconds from the first image to the last.
        """
        return self.images[-1].seconds if self.images else 0.0

    def at(self, seconds: float) -> TimedImage:
        """
        The image taken at or last before a moment of the recording.
        """
        taken = [image for image in self.images if image.seconds <= seconds]
        return taken[-1] if taken else self.images[0]


# %% the scene


@dataclass
class ExecutionFootage(Scene):
    """
    A stretch of the robot's own camera played faster than it was recorded, with the
    speed-up written on it.
    """

    film: CameraFilm
    """
    The recording.
    """

    from_second: float = 0.0
    """
    Where in the recording the stretch starts.
    """

    to_second: Optional[float] = None
    """
    Where it ends, or None for the recording's end.
    """

    speed: float = 4.0
    """
    How many recorded seconds pass per second played.
    """

    caption: str = "executes the resolved plan"
    """
    The line written under the film.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each picture is shown.
    """

    @property
    def end(self) -> float:
        return self.film.length if self.to_second is None else self.to_second

    @property
    def duration(self) -> float:
        return (self.end - self.from_second) / self.speed

    def picture_at(self, seconds: float) -> Frame:
        image = self.framing.of(self.film.at(self.from_second + seconds * self.speed).image)
        frame = self.resolution.blank(255)
        stage = self.resolution.stage_height
        frame = fitted(frame, image, Area(0, 0, self.resolution.width, stage - 80))
        badge = Area(self.resolution.width - 150, 20, 130, 48)
        frame = filled(frame, badge, Ink.TEXT.rgb)
        frame = Typesetting(size=28, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, f"×{self.speed:g}", badge.centre, Anchor.CENTRE_MIDDLE
        )
        return Typesetting(size=28, color=Ink.TEXT.rgb).written(
            frame, self.caption, (self.resolution.width / 2, stage - 40), Anchor.CENTRE_MIDDLE
        )
