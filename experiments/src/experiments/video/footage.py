"""
Film played back in a video: a recording read from its file, framed, filling the frame,
sped up and saying by how much, with a second view of the same stretch small in its
corner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Optional, Protocol, Tuple

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
from experiments.video.lettering import Face
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

# %% what of a picture is shown


@dataclass(frozen=True)
class Framing:
    """
    The margins cut off a camera picture before it is shown, in the picture's pixels.

    It is applied to the drawn picture, after any findings are drawn on it, so nothing
    drawn in the camera's pixel coordinates has to move.
    """

    top: int = 0
    """
    Rows cut off the top.
    """

    left: int = 0
    """
    Columns cut off the left.
    """

    right: int = 0
    """
    Columns cut off the right.
    """

    bottom: int = 0
    """
    Rows cut off the bottom.
    """

    def of(self, picture: Frame) -> Frame:
        """
        :param picture: A picture.
        :return: What is left of it inside the margins.
        """
        height, width = picture.shape[:2]
        return picture[self.top : height - self.bottom, self.left : width - self.right]


# %% a film


class Film(Protocol):
    """
    What a film is to a scene that shows it: an image for any moment of it, and how long
    it runs.
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


@dataclass
class VideoFilm:
    """
    A film read from a video file: a camera's recording, or a simulation filmed as it
    ran.
    """

    video: VideoFile
    """
    The file.
    """

    @property
    def length(self) -> float:
        return self.video.duration

    def image_at(self, seconds: float) -> Frame:
        last = self.length - 1.0 / self.video.frames_per_second
        return self.video.frame_at(min(seconds, last))


# %% a stretch of a film


@dataclass
class ViewOfTheRun:
    """
    One camera's view of a stretch of a run.
    """

    film: Film
    """
    What the camera recorded.
    """

    from_second: float
    """
    Where in the film the stretch starts: the moment that matches the stretch's start in
    every other viewpoint of it.
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
Pixels wide the second view is in the corner of the footage, at the video's size.
"""

BADGE_HEIGHT = 36
"""
Pixels a badge on the footage is tall: the speed-up, or a label.
"""

BADGE_PADDING = 14
"""
Pixels between a badge's edge and its text.
"""


def badged(
    frame: Frame, text: str, at: Tuple[float, float], anchor: Anchor = Anchor.LEFT_TOP
) -> Frame:
    """
    A copy of the frame with a dark badge carrying a short text, its top left, top right
    or bottom right corner at a point.

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
    return badged(
        frame, f"×{speed:g}", (resolution.width - MARGIN, MARGIN), Anchor.RIGHT_TOP
    )


@dataclass(frozen=True)
class HeldInset:
    """
    A picture the inset holds before it runs, such as what a camera saw at one moment
    with what was found on it drawn, and for how long it is held.
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
    speed-up badged in the top right corner, and optionally a second view of the same
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
    The second view, or None to show the one camera.
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
        Where the inset lies: the bottom right corner of the footage, above the band the
        captions are read on.
        """
        sample = self.inset.image_at(0.0)
        height = INSET_WIDTH * sample.shape[0] / sample.shape[1]
        return Area(
            self.resolution.width - MARGIN - INSET_WIDTH,
            self.resolution.stage_height - MARGIN / 2 - height,
            INSET_WIDTH,
            height,
        )

    def inset_picture_at(self, seconds: float) -> Frame:
        """
        What the inset shows at a moment: what it holds first, else the second view.
        """
        if self.inset_held is not None and seconds < self.inset_held.held_for:
            return self.inset_held.picture
        return self.inset.image_at(seconds * self.speed)

    def picture_at(self, seconds: float) -> Frame:
        frame = pasted(
            self.resolution.blank(0),
            self.main.image_at(seconds * self.speed),
            Area.whole(self.resolution),
        )
        if self.inset is not None:
            panel = self.inset_panel
            frame = filled(frame, panel.inset(-3), Ink.PAPER.rgb)
            frame = pasted(frame, self.inset_picture_at(seconds), panel)
        # footage at its own pace carries no badge
        return speed_badged(frame, self.speed) if self.speed != 1.0 else frame


@dataclass
class TitleOverFootage(Scene):
    """
    A title over footage, the footage shaded so the title is what is read; the title
    fades out at the end.
    """

    footage: Scene
    """
    What plays under the title, for the scene's whole duration.
    """

    title: str
    """
    The title.
    """

    line: str
    """
    What stands under the title, in smaller letters.
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
        shaded = np.clip(
            frame.astype(np.float32) * (1.0 - self.shade) + 0.5, 0, 255
        ).astype(np.uint8)
        heading = Typesetting(size=CLAIM_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb)
        text = heading.wrapped(self.title, resolution.width - 2 * MARGIN - 120)
        rows = text.count("\n") + 1
        middle = resolution.stage_height / 2 - 20
        written = heading.written(
            shaded, text, (resolution.width / 2, middle), Anchor.CENTRE_MIDDLE
        )
        written = Typesetting(size=BODY_SIZE, color=Ink.PAPER.rgb).written(
            written,
            self.line,
            (resolution.width / 2, middle + rows * CLAIM_SIZE * 0.7 + 44),
            Anchor.CENTRE_MIDDLE,
        )
        return blended(frame, written, weight)
