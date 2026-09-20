"""
The figure on screen, and a backend's work brought to the front of it.

The video's spine is the framework figure, drawn a little fuller after each backend has
answered. While a backend works, its panel of the figure grows out into a close-up that
fills the screen, the work plays there, and the close-up shrinks back into the panel,
which is filled in by the time it lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import Dict, Optional

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    VIDEO_RESOLUTION,
    Anchor,
    Ink,
    Area,
    Rgb,
    Typesetting,
    dimmed,
    filled,
    fitted,
    pasted,
)
from experiments.video.figure import FrameworkFigure, Slot
from experiments.video.timeline import SUBTITLE_BAND_SHARE, Frame, Resolution, Scene, eased

CAPTION_HEIGHT = 64
"""
The strip under the figure a caption is written in, in pixels at the video's size.
"""

FIGURE_MARGIN = 12
"""
Air above the figure, in pixels.
"""

CLOSE_UP_SHARE = 0.86
"""
How much of the screen's width and height a close-up may take.
"""

TAB_HEIGHT = 36
"""
How tall the tab naming the backend over its close-up is, in pixels.
"""

# %% the figure on the canvas


@dataclass
class FigureOnCanvas:
    """
    One stage of the figure, drawn once and placed on the video's canvas with a caption
    under it.
    """

    figure: FrameworkFigure
    """
    The figure at its stage.
    """

    caption: str = ""
    """
    The line written under it.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the canvas.
    """

    @cached_property
    def placement(self) -> Area:
        """
        Where the figure lies on the canvas: as tall as the room above the caption
        allows, centred.
        """
        room = Area(
            0,
            FIGURE_MARGIN,
            self.resolution.width,
            self.resolution.stage_height - CAPTION_HEIGHT - FIGURE_MARGIN,
        )
        return room.fitting(self.figure.geometry.width / self.figure.geometry.height)

    @cached_property
    def picture(self) -> Frame:
        """
        The figure compiled at the width it is placed at.
        """
        return self.figure.drawn(width=int(round(self.placement.width)))

    @cached_property
    def frame(self) -> Frame:
        """
        The canvas with the figure and the caption on it.
        """
        frame = pasted(self.resolution.blank(255), self.picture, self.placement)
        if self.caption:
            frame = Typesetting(size=26, color=Ink.TEXT.rgb).written(
                frame,
                self.caption,
                (
                    self.resolution.width / 2,
                    self.resolution.stage_height - CAPTION_HEIGHT / 2,
                ),
                Anchor.CENTRE_MIDDLE,
            )
        return frame

    def panel(self, slot: Slot) -> Area:
        """
        Where a backend's panel lies on the canvas.

        :param slot: The slot the backend answers.
        """
        box = self.figure.geometry.panels[slot]
        scale = self.placement.width / self.figure.geometry.width
        return Area(
            self.placement.x + box.x * scale,
            self.placement.y + box.y * scale,
            box.width * scale,
            box.height * scale,
        )


@dataclass
class FigureScene(Scene):
    """
    The figure held on screen for a while.
    """

    shown: FigureOnCanvas
    """
    The figure at its stage.
    """

    held_for: float = 3.0
    """
    How long, in seconds.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    def picture_at(self, seconds: float) -> Frame:
        return self.shown.frame


# %% a backend's work brought to the front


@dataclass
class Spotlight(Scene):
    """
    A backend's work grown out of its panel to fill the screen, played, and shrunk back
    into the panel once the backend has answered.
    """

    before: FigureOnCanvas
    """
    The figure as it stands while the backend works, with its slot ringed.
    """

    after: FigureOnCanvas
    """
    The figure once the backend has answered, which the close-up shrinks back onto.
    """

    slot: Slot
    """
    The slot being answered, whose panel the close-up grows out of.
    """

    work: Scene
    """
    What plays in the close-up.
    """

    hue: Rgb
    """
    The colour the close-up is framed in.
    """

    title: str = ""
    """
    What the backend at work is called, on a tab over the close-up; nothing for no tab.
    """

    grow: float = 1.2
    """
    How long the close-up takes to grow out, in seconds.
    """

    shrink: float = 1.2
    """
    How long it takes to shrink back, in seconds.
    """

    @property
    def duration(self) -> float:
        return self.grow + self.work.duration + self.shrink

    @cached_property
    def close_up(self) -> Area:
        """
        Where the work plays when fully grown: as large as its own aspect allows
        within the screen's share, centred across, and set so that the band the work
        leaves for subtitles lies over the band the screen leaves for them.
        """
        resolution = self.before.resolution
        sample = self.work.frame_at(0.0)
        room = Area(
            resolution.width * (1 - CLOSE_UP_SHARE) / 2,
            resolution.stage_height * (1 - CLOSE_UP_SHARE) / 2,
            resolution.width * CLOSE_UP_SHARE,
            resolution.stage_height * CLOSE_UP_SHARE,
        )
        window = room.fitting(sample.shape[1] / sample.shape[0])
        works_stage = window.height * (1 - SUBTITLE_BAND_SHARE)
        top = max(resolution.stage_height - works_stage, resolution.stage_height * (1 - CLOSE_UP_SHARE) / 2)
        return Area(window.x, top, window.width, window.height)

    def picture_at(self, seconds: float) -> Frame:
        panel = self.before.panel(self.slot)
        if seconds < self.grow:
            progress = eased(seconds / self.grow)
            base = self.before.frame
            work = self.work.frame_at(0.0)
        elif seconds < self.grow + self.work.duration:
            progress = 1.0
            base = self.before.frame
            work = self.work.frame_at(seconds - self.grow)
        else:
            progress = 1.0 - eased(
                (seconds - self.grow - self.work.duration) / self.shrink
            )
            base = self.after.frame
            panel = self.after.panel(self.slot)
            work = self.work.frame_at(self.work.duration - 1e-6)
        where = panel.towards(self.close_up, progress)
        frame = dimmed(base, 0.55 * progress)
        frame = filled(frame, where.inset(-4), self.hue)
        frame = pasted(frame, work, where)
        return self._tabbed(frame, where, progress)

    def _tabbed(self, frame: Frame, where: Area, progress: float) -> Frame:
        """
        The backend's name on a tab over the close-up, there once it has grown out.

        :param frame: The frame the close-up is on.
        :param where: Where the close-up lies.
        :param progress: How far the close-up has grown, from zero to one.
        """
        if not self.title or progress < 1.0:
            return frame
        lettering = Typesetting(size=22, face=Face.BOLD, color=Ink.PAPER.rgb)
        width = lettering.width_of(self.title) + 36
        tab = Area(where.x - 4, where.y - 4 - TAB_HEIGHT, width, TAB_HEIGHT)
        frame = filled(frame, tab, self.hue)
        return lettering.written(frame, self.title, (tab.x + 18, tab.centre[1]), Anchor.LEFT_MIDDLE)


# %% a scene drawn at its own size, shown full screen


@dataclass
class OnCanvas(Scene):
    """
    A scene that draws itself at its own size, fitted onto the video's canvas.
    """

    work: Scene
    """
    The scene shown.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the canvas.
    """

    @property
    def duration(self) -> float:
        return self.work.duration

    def picture_at(self, seconds: float) -> Frame:
        return fitted(
            self.resolution.blank(255),
            self.work.frame_at(seconds),
            Area.whole(self.resolution),
        )
