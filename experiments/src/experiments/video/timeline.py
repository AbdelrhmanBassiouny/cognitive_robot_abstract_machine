"""
A video as scenes laid end to end.

A scene is anything that can say how long it lasts and what it looks like at any moment
of that; the timeline lays scenes one after another, dissolving each into the next, and
reads the whole out as frames at one rate. Nothing here knows what a scene shows, so a
title, a chart being drawn and a recording being replayed are all laid out the same way.

A scene is written by subclassing :class:`Scene` (or :class:`HeldScene` for a slide) and
saying what it shows at each moment in :meth:`Scene.picture_at`.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Iterator, List, TypeAlias

Frame: TypeAlias = np.ndarray
"""
One picture of the video: red, green and blue bytes, rows by columns by channel.
"""

# %% the picture a video is


SUBTITLE_BAND_SHARE = 0.14
"""
The share of a frame's height, at its bottom, left clear for the captions: two rows of
them on a fixed baseline, with their margin.
"""


@dataclass(frozen=True)
class Resolution:
    """
    The size every frame of a video has.
    """

    width: int
    """
    Columns of pixels.
    """

    height: int
    """
    Rows of pixels.
    """

    @property
    def shape(self) -> tuple[int, int, int]:
        """
        The array shape of one frame this size.
        """
        return (self.height, self.width, 3)

    @property
    def stage_height(self) -> float:
        """
        How far down a scene may draw: the rows above the band left for subtitles.
        """
        return self.height * (1.0 - SUBTITLE_BAND_SHARE)

    @classmethod
    def of(cls, frame: Frame) -> Resolution:
        """
        :param frame: A frame.
        :return: Its size.
        """
        return cls(width=frame.shape[1], height=frame.shape[0])

    def blank(self, value: int = 255) -> Frame:
        """
        :param value: The grey every pixel is set to.
        :return: A frame this size of one grey.
        """
        return np.full(self.shape, value, dtype=np.uint8)


# %% one scene


@dataclass
class Scene(ABC):
    """
    One stretch of the video, read out picture by picture.
    """

    @property
    @abstractmethod
    def duration(self) -> float:
        """
        How long the scene lasts, in seconds.
        """

    @abstractmethod
    def picture_at(self, seconds: float) -> Frame:
        """
        What the scene shows at a moment of its own time.

        :param seconds: The moment, from the scene's start; never past its duration.
        """

    def frame_at(self, seconds: float) -> Frame:
        """
        What the scene shows at a moment of its own time, refusing a moment outside it.

        :param seconds: The moment, from the scene's start.
        :raises ValueError: If the moment lies before the scene starts or after it ends.
        """
        if not 0.0 <= seconds < self.duration:
            raise ValueError(
                f"{seconds:.3f} s is outside a scene lasting {self.duration:.3f} s"
            )
        return self.picture_at(seconds)

    def progress_at(self, seconds: float) -> float:
        """
        :param seconds: A moment of the scene's own time.
        :return: How far through the scene that moment is, from zero to one.
        """
        return seconds / self.duration

    @property
    def dissolves_in(self) -> bool:
        """
        Whether the scene before dissolves into this one, or this one cuts in: a cut
        where the two would write different text in one place.
        """
        return True


@dataclass
class HeldScene(Scene, ABC):
    """
    A scene that lasts as long as it is held, rather than as long as what it shows: a
    slide, which may be held longer to make room for what is said over it.
    """

    held_for: float = field(kw_only=True)
    """
    How long it is held, in seconds.
    """

    @property
    def duration(self) -> float:
        return self.held_for


@dataclass
class Still(HeldScene):
    """
    One picture held for a while.
    """

    picture: Frame
    """
    The picture.
    """

    def picture_at(self, seconds: float) -> Frame:
        return self.picture


# %% easing


def eased(progress: float) -> float:
    """
    A motion that starts and ends slowly: a cosine ramp over the given progress.

    :param progress: How far along, from zero to one; anything beyond is clamped.
    """
    clamped = min(max(progress, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * clamped)


def blended(first: Frame, second: Frame, weight: float) -> Frame:
    """
    A mix of two frames.

    :param first: The frame shown when the weight is zero.
    :param second: The frame shown when the weight is one.
    :param weight: How much of the second frame shows, from zero to one.
    """
    mixed = (
        first.astype(np.float32) * (1.0 - weight) + second.astype(np.float32) * weight
    )
    return np.clip(mixed + 0.5, 0, 255).astype(np.uint8)


# %% what is drawn over every scene


@dataclass
class Overlay(ABC):
    """
    Something drawn over every frame of a video, whatever scene plays: it knows the
    moment of the whole video rather than of one scene.
    """

    @abstractmethod
    def drawn_over(self, frame: Frame, seconds: float, runs_for: float) -> Frame:
        """
        :param frame: The frame of the scenes at that moment.
        :param seconds: The moment, from the video's start.
        :param runs_for: How long the video lasts.
        :return: A copy of the frame with this drawn over it.
        """


# %% the timeline


@dataclass
class Timeline:
    """
    Scenes laid end to end, each dissolving into the next, read out as frames.
    """

    scenes: List[Scene]
    """
    The scenes, in the order they play.
    """

    frames_per_second: int = 25
    """
    How many frames one second of the video holds.
    """

    dissolve: float = 0.5
    """
    How long each scene takes to dissolve into the next, in seconds; the two overlap by
    that much.
    """

    overlays: List[Overlay] = field(default_factory=list)
    """
    What is drawn over every frame, in order, after the scenes.
    """

    @property
    def duration(self) -> float:
        """
        How long the whole video lasts, in seconds.
        """
        overlaps = sum(
            self.dissolve_into(index) for index in range(1, len(self.scenes))
        )
        return sum(scene.duration for scene in self.scenes) - overlaps

    def dissolve_into(self, index: int) -> float:
        """
        Seconds the scene before dissolves into a scene: none where it cuts in.

        :param index: Which scene, from zero.
        """
        return self.dissolve if index > 0 and self.scenes[index].dissolves_in else 0.0

    @property
    def frame_count(self) -> int:
        """
        How many frames the video is read out as.
        """
        return round(self.duration * self.frames_per_second)

    def starts(self) -> List[float]:
        """
        When each scene starts, in seconds of the video's time.
        """
        starts = []
        start = 0.0
        for index, scene in enumerate(self.scenes):
            starts.append(start)
            start += scene.duration - (
                self.dissolve_into(index + 1) if index + 1 < len(self.scenes) else 0.0
            )
        return starts

    def frame_at(self, seconds: float) -> Frame:
        """
        What the video shows at a moment of its time: its scenes then, with every
        overlay drawn over them.

        :param seconds: The moment, from the video's start.
        """
        frame = self.scenes_at(seconds)
        runs_for = self.duration
        for overlay in self.overlays:
            frame = overlay.drawn_over(frame, seconds, runs_for)
        return frame

    def scenes_at(self, seconds: float) -> Frame:
        """
        What the scenes show at a moment of the video's time: the scene playing then,
        blended with the one before it while the two dissolve.

        :param seconds: The moment, from the video's start.
        """
        starts = self.starts()
        current = max(
            index
            for index, start in enumerate(starts)
            if start <= seconds or index == 0
        )
        scene = self.scenes[current]
        local = min(seconds - starts[current], scene.duration - 1e-9)
        frame = scene.frame_at(max(local, 0.0))
        dissolve = self.dissolve_into(current)
        if current == 0 or local >= dissolve:
            return frame
        previous = self.scenes[current - 1]
        earlier = previous.frame_at(
            min(seconds - starts[current - 1], previous.duration - 1e-9)
        )
        self._same_size(earlier, frame)
        return blended(earlier, frame, eased(local / dissolve))

    def frames(self) -> Iterator[Frame]:
        """
        Every frame of the video, in order.

        :raises ValueError: If two scenes draw frames of different sizes.
        """
        size = None
        for index in range(self.frame_count):
            frame = self.frame_at(index / self.frames_per_second)
            if size is None:
                size = Resolution.of(frame)
            self._same_size(size.blank(), frame)
            yield frame

    @staticmethod
    def _same_size(first: Frame, second: Frame) -> None:
        """
        :raises ValueError: If the two frames differ in size.
        """
        if first.shape != second.shape:
            raise ValueError(
                f"frames of {Resolution.of(first)} and {Resolution.of(second)} cannot "
                "share one video"
            )
