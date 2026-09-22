"""
What the robot's camera recorded, played back as film, and what a camera held by hand
recorded of the same run, filling the frame with the robot's own view small in its
corner.

A recording keeps one colour image in ten, so played at its own pace it would be a
slide show; a stretch of it is played faster instead, and says by how much.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import List, Optional, Protocol, Tuple

from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import CameraTopic, open_bag
from experiments.paper.lettering import Face
from experiments.episodes.artifacts import EpisodeArtifact
from experiments.video.cache import SceneCache
from experiments.video.canvas import (
    BODY_SIZE,
    CLAIM_SIZE,
    LABEL_SIZE,
    MARGIN,
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    Ink,
    Typesetting,
    filled,
    pasted,
)
from experiments.video.encoding import VideoFile
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage

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

FULL_BLEED_FRAMING = Framing(top=730, bottom=583)
"""
What of the hand-held film fills the frame: it stands upright, 1080 by 1920, and the
widest sixteen-by-nine window of it, 1080 by 607, is laid over the gripper, the pieces
and the board.
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

    def image_at(self, seconds: float) -> Frame:
        """
        The image taken at or last before a moment of the recording, itself.
        """
        return self.at(seconds).image


# %% a film taken by hand


class Film(Protocol):
    """
    What a film is to a scene that shows it: an image for any moment of it, and how
    long it runs.
    """

    @property
    def length(self) -> float:
        """
        Seconds from the film's first image to its last.
        """

    def image_at(self, seconds: float) -> Frame:
        """
        The image at a moment of the film, as red, green and blue.
        """


HAND_HELD_RECORDING = "hand_held_camera.mp4"
"""
What a film someone took of a run by hand from beside the table is kept as among the
run's files, when someone took one.
"""


@dataclass
class HandHeldFilm:
    """
    A film someone took of a run by hand from beside the table, read from its file.
    """

    video: VideoFile
    """
    The file.
    """

    @classmethod
    def beside(cls, run: RecordedRun) -> Optional[HandHeldFilm]:
        """
        The film taken of a run, if one was kept among its files.

        :param run: The run.
        """
        path = run.kept.directory / EpisodeArtifact.RUN_FILES / HAND_HELD_RECORDING
        return cls(VideoFile(path)) if path.is_file() else None

    @property
    def length(self) -> float:
        return self.video.duration

    def image_at(self, seconds: float) -> Frame:
        return self.video.frame_at(min(seconds, self.length))


# %% the run seen from beside the table, with the robot's own view


@dataclass
class ViewOfTheRun:
    """
    One camera's view of a stretch of the run.
    """

    film: Film
    """
    What the camera recorded.
    """

    from_second: float
    """
    Where in the film the stretch starts: the moment that matches the stretch's start
    in every other viewpoint of it.
    """

    framing: Framing = field(default_factory=Framing)
    """
    What of each picture is shown.
    """

    def image_at(self, into: float) -> Frame:
        """
        :param into: Seconds into the stretch.
        :return: What the camera saw then, framed.
        """
        return self.framing.of(self.film.image_at(self.from_second + into))


# %% the frame filled with footage


INSET_WIDTH = 300
"""
Pixels wide the robot's own view is in the corner of the footage, at the video's size.
"""

BADGE_HEIGHT = 36
"""
Pixels a badge on the footage is tall: the speed-up, and a label of an inset.
"""

BADGE_PADDING = 14
"""
Pixels between a badge's edge and its text.
"""


def badged(frame: Frame, text: str, at: Tuple[float, float], anchor: Anchor = Anchor.LEFT_TOP) -> Frame:
    """
    A copy of the frame with a dark badge carrying a short text, its top left, top
    right or bottom right corner at a point.

    :param frame: The frame.
    :param text: What the badge says.
    :param at: Where its corner goes.
    :param anchor: Which corner: the left top, the right top or the right middle
        standing for the right bottom.
    """
    lettering = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb)
    width = lettering.width_of(text) + 2 * BADGE_PADDING
    if anchor is Anchor.LEFT_TOP:
        badge = Area(at[0], at[1], width, BADGE_HEIGHT)
    elif anchor is Anchor.RIGHT_TOP:
        badge = Area(at[0] - width, at[1], width, BADGE_HEIGHT)
    else:
        badge = Area(at[0] - width, at[1] - BADGE_HEIGHT, width, BADGE_HEIGHT)
    frame = filled(frame, badge, Ink.TEXT.rgb)
    return lettering.written(frame, text, badge.centre, Anchor.CENTRE_MIDDLE)


def speed_badged(frame: Frame, speed: float) -> Frame:
    """
    A copy of the frame with the speed-up in its top right corner.
    """
    resolution = Resolution.of(frame)
    return badged(frame, f"×{speed:g}", (resolution.width - MARGIN, MARGIN), Anchor.RIGHT_TOP)


@dataclass(frozen=True)
class HeldInset:
    """
    A picture the inset holds before it runs: what the robot's camera saw at one
    moment, with what was found on it drawn, and for how long it is held.
    """

    picture: Frame
    """
    The picture.
    """

    held_for: float
    """
    Seconds it is held, from the scene's start.
    """


@dataclass
class FullBleedFootage(Scene):
    """
    A stretch of a run filling the whole frame, played faster than recorded with the
    speed-up badged in the top right corner, and the robot's own view of the same
    stretch small in the bottom right corner, in step.
    """

    main: ViewOfTheRun
    """
    The camera that fills the frame.
    """

    length: float
    """
    Seconds of the recording the stretch runs for.
    """

    speed: float = 2.0
    """
    How many recorded seconds pass per second played.
    """

    inset: Optional[ViewOfTheRun] = None
    """
    The robot's own view, or None to show the one camera.
    """

    inset_held: Optional[HeldInset] = None
    """
    What the inset holds before it runs, if anything.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size the scene draws itself at: the video's own, the footage filling it.
    """

    @property
    def duration(self) -> float:
        return self.length / self.speed

    @property
    def inset_panel(self) -> Area:
        """
        Where the inset lies: the bottom right corner of the footage, above the band
        the captions are read on.
        """
        sample = self.inset.image_at(0.0)
        height = INSET_WIDTH * sample.shape[0] / sample.shape[1]
        return Area(self.resolution.width - MARGIN - INSET_WIDTH, self.resolution.stage_height - MARGIN / 2 - height, INSET_WIDTH, height)

    def inset_picture_at(self, seconds: float) -> Frame:
        """
        What the inset shows at a moment: what it holds first, else the robot's view.
        """
        if self.inset_held is not None and seconds < self.inset_held.held_for:
            return self.inset_held.picture
        return self.inset.image_at(seconds * self.speed)

    def picture_at(self, seconds: float) -> Frame:
        frame = pasted(self.resolution.blank(0), self.main.image_at(seconds * self.speed), Area.whole(self.resolution))
        if self.inset is not None:
            panel = self.inset_panel
            frame = filled(frame, panel.inset(-3), Ink.PAPER.rgb)
            frame = pasted(frame, self.inset_picture_at(seconds), panel)
        # footage at its own pace carries no badge
        return speed_badged(frame, self.speed) if self.speed != 1.0 else frame


@dataclass
class TitleOverFootage(Scene):
    """
    The paper's title over footage of the robot, the footage shaded so the title is
    what is read; the title fades out at the end.
    """

    footage: Scene
    """
    What plays under the title, for the scene's whole duration.
    """

    title: str
    """
    The paper's title.
    """

    line: str
    """
    What stands under the title: what the video is, and for which conference.
    """

    title_for: float
    """
    Seconds the title stands, before it fades out.
    """

    fade: float = 0.25
    """
    Seconds the title takes to fade out.
    """

    shade: float = 0.55
    """
    How far the footage is shaded under the title.
    """

    @property
    def duration(self) -> float:
        return self.footage.duration

    def title_at(self, seconds: float) -> float:
        """
        How far the title is up at a moment, from zero to one.
        """
        return 1.0 - eased((seconds - self.title_for) / self.fade)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.footage.picture_at(seconds)
        weight = self.title_at(seconds)
        if weight <= 0.0:
            return frame
        resolution = Resolution.of(frame)
        shaded = np.clip(frame.astype(np.float32) * (1.0 - self.shade) + 0.5, 0, 255).astype(np.uint8)
        heading = Typesetting(size=CLAIM_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb)
        text = heading.wrapped(self.title, resolution.width - 2 * MARGIN - 120)
        rows = text.count("\n") + 1
        middle = resolution.stage_height / 2 - 20
        written = heading.written(shaded, text, (resolution.width / 2, middle), Anchor.CENTRE_MIDDLE)
        written = Typesetting(size=BODY_SIZE, color=Ink.PAPER.rgb).written(
            written, self.line, (resolution.width / 2, middle + rows * CLAIM_SIZE * 0.7 + 44), Anchor.CENTRE_MIDDLE
        )
        return blended(frame, written, weight)
