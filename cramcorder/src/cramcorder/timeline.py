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
from datetime import timedelta

from typing_extensions import Iterator, List, Optional

from cramcorder.exceptions import FramesOfDifferentSizes, MomentOutsideScene
from cramcorder.frame import Frame, Resolution

# %% fading


@dataclass(frozen=True)
class Fade:
    """
    A change that starts and ends slowly over a while.
    """

    duration: timedelta
    """
    How long the change takes.
    """

    def weight_at(self, elapsed: timedelta) -> float:
        """
        :param elapsed: How long the change has been going on; before it starts counts
            as its start and after it ends as its end.
        :return: How far along the change is, from zero to one, along a cosine ramp.
        """
        clamped = min(max(elapsed / self.duration, 0.0), 1.0)
        return 0.5 - 0.5 * math.cos(math.pi * clamped)


# %% one scene


@dataclass
class Scene(ABC):
    """
    One stretch of the video, read out picture by picture.
    """

    @property
    @abstractmethod
    def duration(self) -> timedelta:
        """
        How long the scene lasts.
        """

    @abstractmethod
    def picture_at(self, moment: timedelta) -> Frame:
        """
        :param moment: A moment of the scene's own time, from its start; never past its
            duration.
        :return: What the scene shows then.
        """

    def frame_at(self, moment: timedelta) -> Frame:
        """
        What the scene shows at a moment of its own time, refusing a moment outside it.

        :param moment: The moment, from the scene's start.
        :return: What the scene shows then.
        :raises MomentOutsideScene: If the moment lies before the scene starts or after
            it ends.
        """
        if not timedelta(0) <= moment < self.duration:
            raise MomentOutsideScene(moment=moment, duration=self.duration)
        return self.picture_at(moment)

    def progress_at(self, moment: timedelta) -> float:
        """
        :param moment: A moment of the scene's own time.
        :return: How far through the scene that moment is, from zero to one.
        """
        return moment / self.duration

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

    held_for: timedelta = field(kw_only=True)
    """
    How long it is held.
    """

    @property
    def duration(self) -> timedelta:
        """
        How long the scene is held.
        """
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

    def picture_at(self, moment: timedelta) -> Frame:
        """
        :param moment: A moment of the scene, from its start.
        :return: The picture, the same at every moment.
        """
        return self.picture


# %% what is drawn over every scene


@dataclass
class Overlay(ABC):
    """
    Something drawn over every frame of a video, whatever scene plays: it knows the
    moment of the whole video rather than of one scene.
    """

    @abstractmethod
    def drawn_over(self, frame: Frame, moment: timedelta, runs_for: timedelta) -> Frame:
        """
        :param frame: The frame of the scenes at that moment.
        :param moment: The moment, from the video's start.
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

    dissolve: timedelta = timedelta(seconds=0.5)
    """
    How long each scene takes to dissolve into the next; the two overlap by that much.
    """

    overlays: List[Overlay] = field(default_factory=list)
    """
    What is drawn over every frame, in order, after the scenes.
    """

    @property
    def duration(self) -> timedelta:
        """
        How long the whole video lasts.
        """
        overlaps = sum(
            (self.dissolve_into(index) for index in range(1, len(self.scenes))),
            timedelta(0),
        )
        return sum((scene.duration for scene in self.scenes), timedelta(0)) - overlaps

    def dissolve_into(self, index: int) -> timedelta:
        """
        :param index: Which scene, from zero.
        :return: How long the scene before dissolves into it: no time where it cuts in.
        """
        if index > 0 and self.scenes[index].dissolves_in:
            return self.dissolve
        return timedelta(0)

    @property
    def frame_count(self) -> int:
        """
        How many frames the video is read out as.
        """
        return round(self.duration.total_seconds() * self.frames_per_second)

    def starts(self) -> List[timedelta]:
        """
        :return: When each scene starts, from the video's start.
        """
        starts = []
        start = timedelta(0)
        for index, scene in enumerate(self.scenes):
            starts.append(start)
            start += scene.duration - (
                self.dissolve_into(index + 1)
                if index + 1 < len(self.scenes)
                else timedelta(0)
            )
        return starts

    def frame_at(self, moment: timedelta) -> Frame:
        """
        :param moment: The moment, from the video's start.
        :return: What the video shows then: its scenes, with every overlay drawn over
            them.
        """
        frame = self.scenes_at(moment)
        runs_for = self.duration
        for overlay in self.overlays:
            frame = overlay.drawn_over(frame, moment, runs_for)
        return frame

    def scenes_at(self, moment: timedelta) -> Frame:
        """
        :param moment: The moment, from the video's start.
        :return: What the scenes show then: the scene playing blended with the one
            before it while the two dissolve.
        """
        starts = self.starts()
        current = max(
            index for index, start in enumerate(starts) if start <= moment or index == 0
        )
        scene = self.scenes[current]
        last_moment = scene.duration - timedelta(microseconds=1)
        local = min(moment - starts[current], last_moment)
        frame = scene.frame_at(max(local, timedelta(0)))
        dissolve = self.dissolve_into(current)
        if current == 0 or local >= dissolve:
            return frame
        previous = self.scenes[current - 1]
        earlier = previous.frame_at(
            min(
                moment - starts[current - 1],
                previous.duration - timedelta(microseconds=1),
            )
        )
        self._same_size(earlier, frame)
        return earlier.blended(frame, Fade(dissolve).weight_at(local))

    def frames(self) -> Iterator[Frame]:
        """
        Every frame of the video, in order.

        :return: The frames.
        :raises FramesOfDifferentSizes: If two scenes draw frames of different sizes.
        """
        size: Optional[Resolution] = None
        for index in range(self.frame_count):
            frame = self.frame_at(timedelta(seconds=index / self.frames_per_second))
            if size is None:
                size = frame.resolution
            self._same_size(size.blank(), frame)
            yield frame

    @staticmethod
    def _same_size(first: Frame, second: Frame) -> None:
        """
        :param first: A frame.
        :param second: Another.
        :raises FramesOfDifferentSizes: If the two frames differ in size.
        """
        if first.resolution != second.resolution:
            raise FramesOfDifferentSizes(
                first=first.resolution, second=second.resolution
            )
