"""
The figure on screen, and a backend's work brought to the front of it.

The video's spine is the framework figure, drawn a little fuller after each backend has
answered. While a backend works, its panel of the figure grows out into a close-up that
fills the screen, the work plays there, and the close-up shrinks back into the panel,
which is filled in by the time it lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property

import numpy as np
from typing_extensions import Dict, Optional, Sequence, Tuple

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    VIDEO_RESOLUTION,
    Anchor,
    Ink,
    Area,
    Rgb,
    Typesetting,
    arrowed,
    dimmed,
    filled,
    fitted,
    framed,
    pasted,
)
from experiments.video.figure import FigureBox, FrameworkFigure, Slot
from experiments.video.timeline import SUBTITLE_BAND_SHARE, Frame, Resolution, Scene, blended, eased

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

    @property
    def pixels_per_centimetre(self) -> float:
        """
        The scale the figure is placed at.
        """
        return self.placement.width / self.figure.geometry.width

    def area_of(self, box: FigureBox) -> Area:
        """
        Where a stretch of the figure lies on the canvas.

        :param box: The stretch, in the figure's centimetres.
        """
        scale = self.pixels_per_centimetre
        return Area(
            self.placement.x + box.x * scale,
            self.placement.y + box.y * scale,
            box.width * scale,
            box.height * scale,
        )

    def panel(self, slot: Slot) -> Area:
        """
        Where a backend's panel lies on the canvas.

        :param slot: The slot the backend answers.
        """
        return self.area_of(self.figure.geometry.panels[slot])

    def cut_out(self, box: FigureBox, pixels_per_centimetre: float) -> Frame:
        """
        A stretch of the figure compiled crisp at a larger scale.

        :param box: The stretch, in the figure's centimetres.
        :param pixels_per_centimetre: The scale it is compiled at.
        """
        whole = self.figure.drawn(width=int(round(self.figure.geometry.width * pixels_per_centimetre)))
        scale = whole.shape[1] / self.figure.geometry.width
        left, top = int(round(box.x * scale)), int(round(box.y * scale))
        right, bottom = int(round((box.x + box.width) * scale)), int(round((box.y + box.height) * scale))
        return whole[top:bottom, left:right]


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
        Where the work plays when fully grown: within the screen's share, centred.
        """
        resolution = self.before.resolution
        room = Area(
            resolution.width * (1 - CLOSE_UP_SHARE) / 2,
            resolution.stage_height * (1 - CLOSE_UP_SHARE) / 2,
            resolution.width * CLOSE_UP_SHARE,
            resolution.stage_height * CLOSE_UP_SHARE,
        )
        return close_up_window(room, self.work.frame_at(0.0), resolution)

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
        return tabbed(frame, where, self.title, self.hue)


def close_up_window(room: Area, sample: Frame, resolution: Resolution) -> Area:
    """
    Where a close-up plays fully grown: as large as its own aspect allows within the
    room, centred across it, and set so that the band the work leaves for subtitles
    lies over the band the screen leaves for them.

    :param room: The most of the screen the close-up may take.
    :param sample: A frame of the work, for its aspect.
    :param resolution: The size of the screen.
    """
    window = room.fitting(sample.shape[1] / sample.shape[0])
    works_stage = window.height * (1 - SUBTITLE_BAND_SHARE)
    top = max(resolution.stage_height - works_stage, room.y)
    return Area(window.x, top, window.width, window.height)


def tabbed(frame: Frame, where: Area, title: str, hue: Rgb) -> Frame:
    """
    A backend's name on a tab over its close-up.

    :param frame: The frame the close-up is on.
    :param where: Where the close-up lies.
    :param title: The name.
    :param hue: What the tab is filled in.
    """
    lettering = Typesetting(size=22, face=Face.BOLD, color=Ink.PAPER.rgb)
    # a long name is set smaller, so the tab is no wider than the close-up
    while lettering.width_of(title) + 36 > where.width + 8 and lettering.size > 14:
        lettering = replace(lettering, size=lettering.size - 1)
    width = lettering.width_of(title) + 36
    tab = Area(where.x - 4, where.y - 4 - TAB_HEIGHT, width, TAB_HEIGHT)
    frame = filled(frame, tab, hue)
    return lettering.written(frame, title, (tab.x + 18, tab.centre[1]), Anchor.LEFT_MIDDLE)


# %% a stretch of the figure magnified


MAGNIFIED_SHARE = 0.8
"""
How much of the screen's width and height a magnified stretch of the figure may take.
"""


def grown(seconds: float, grow: float, held_for: float, shrink: float) -> float:
    """
    How far something that grows out, is held and shrinks back has grown at a moment,
    from zero to one.

    :param seconds: The moment, into the growing.
    :param grow: Seconds the growing out takes; none to start fully grown.
    :param held_for: Seconds it is held fully grown.
    :param shrink: Seconds the shrinking back takes; none to end fully grown.
    """
    if grow and seconds < grow:
        return eased(seconds / grow)
    if shrink and seconds > grow + held_for:
        return 1.0 - eased((seconds - grow - held_for) / shrink)
    return 1.0


def magnifying_room(resolution: Resolution) -> Area:
    """
    The room a magnified stretch of the figure may take: its share of the stage, centred.

    :param resolution: The size of the canvas.
    """
    return Area(
        resolution.width * (1 - MAGNIFIED_SHARE) / 2,
        resolution.stage_height * (1 - MAGNIFIED_SHARE) / 2,
        resolution.width * MAGNIFIED_SHARE,
        resolution.stage_height * MAGNIFIED_SHARE,
    )


@dataclass
class Magnified(Scene):
    """
    A stretch of the figure grown out of its place to where it can be read, held, and
    shrunk back; the rest of the figure dims behind it.
    """

    shown: FigureOnCanvas
    """
    The figure at its stage.
    """

    box: FigureBox
    """
    The stretch magnified, in the figure's centimetres.
    """

    hue: Rgb
    """
    The colour the magnified stretch is framed in.
    """

    held_for: float = 3.0
    """
    Seconds the stretch is held fully grown.
    """

    grow: float = 0.8
    """
    Seconds it takes to grow out; none to start fully grown.
    """

    shrink: float = 0.6
    """
    Seconds it takes to shrink back; none to end fully grown.
    """

    magnification_up_to: float = 4.0
    """
    The most the stretch grows by, over the scale the figure is placed at, where the
    screen's share would allow more.
    """

    pixels_per_centimetre: Optional[float] = None
    """
    The scale the stretch is read at, or None for as large as the screen's share and
    the magnification allow; stated so that stretches read one after the other read at
    one scale.
    """

    marks: Tuple[Mark, ...] = ()
    """
    The parts of the stretch pointed to while it is read, if any.
    """

    @property
    def duration(self) -> float:
        return self.grow + self.held_for + self.shrink

    @cached_property
    def window(self) -> Area:
        """
        Where the stretch lies fully grown: at its scale, centred on the stage.
        """
        room = magnifying_room(self.shown.resolution).fitting(self.box.width / self.box.height)
        scale = self.pixels_per_centimetre
        if scale is None:
            scale = min(room.width / self.box.width, self.shown.pixels_per_centimetre * self.magnification_up_to)
        width, height = self.box.width * scale, self.box.height * scale
        return Area(room.centre[0] - width / 2, room.centre[1] - height / 2, width, height)

    @property
    def scale(self) -> float:
        """
        The pixels per centimetre the stretch is read at.
        """
        return self.window.width / self.box.width

    @cached_property
    def picture(self) -> Frame:
        return self.shown.cut_out(self.box, self.scale)

    def grown_at(self, seconds: float) -> float:
        """
        How far the stretch has grown at a moment, from zero to one.
        """
        return grown(seconds, self.grow, self.held_for, self.shrink)

    def picture_at(self, seconds: float) -> Frame:
        progress = self.grown_at(seconds)
        where = self.shown.area_of(self.box).towards(self.window, progress)
        frame = dimmed(self.shown.frame, 0.55 * progress)
        frame = filled(frame, where.inset(-4), self.hue)
        picture = marked(self.picture, (self.box.x, self.box.y), self.scale, self.marks, seconds)
        return pasted(frame, picture, where)


# %% a part of a magnified stretch pointed to


MARK_FADE = 0.3
"""
Seconds a mark takes to appear.
"""

MARK_AIR = 0.04
"""
Centimetres of the figure a mark's ring stands off what it rings, on every side.
"""


@dataclass(frozen=True)
class Mark:
    """
    A part of a magnified stretch a reader is pointed to: highlighted and ringed from a
    moment on.
    """

    box: FigureBox
    """
    The part, in the figure's centimetres.
    """

    hue: Rgb
    """
    The colour it is ringed in.
    """

    from_second: float = 0.0
    """
    Seconds into the scene it appears; before, nothing marks the part.
    """

    def appeared_at(self, seconds: float) -> float:
        """
        How far the mark has appeared at a moment, from zero to one.
        """
        return eased((seconds - self.from_second) / MARK_FADE)


def marked(picture: Frame, origin: Tuple[float, float], scale: float, marks: Sequence[Mark], seconds: float) -> Frame:
    """
    A picture of a stretch of the figure with every mark that has appeared by a moment
    drawn onto it: a highlighter's yellow over the part, ringed in the mark's hue.

    :param picture: The stretch, compiled crisp.
    :param origin: The figure's x and y, in centimetres, at the picture's top left corner.
    :param scale: The picture's pixels per centimetre.
    :param marks: What is pointed to, anywhere in the figure; a mark outside the picture
        leaves it as it is.
    :param seconds: The moment.
    """
    for mark in marks:
        weight = mark.appeared_at(seconds)
        if weight <= 0.0:
            continue
        around = Area(
            (mark.box.x - origin[0] - MARK_AIR) * scale,
            (mark.box.y - origin[1] - MARK_AIR) * scale,
            (mark.box.width + 2 * MARK_AIR) * scale,
            (mark.box.height + 2 * MARK_AIR) * scale,
        )
        drawn = highlighted(picture, around)
        drawn = framed(drawn, around, mark.hue, thickness=max(2, int(round(scale * 0.02))))
        picture = blended(picture, drawn, weight)
    return picture


def highlighted(picture: Frame, around: Area) -> Frame:
    """
    A copy of the picture with a highlighter drawn over a rectangle of it: the paper
    turns the highlighter's yellow and the ink stays.
    """
    left, top, width, height = around.rounded()
    result = picture.copy()
    frame_height, frame_width = picture.shape[:2]
    x0, y0 = max(left, 0), max(top, 0)
    x1, y1 = min(left + width, frame_width), min(top + height, frame_height)
    if x1 <= x0 or y1 <= y0:
        return result
    tint = np.asarray(Ink.MARKER.rgb, dtype=np.float32) / 255.0
    result[y0:y1, x0:x1] = (result[y0:y1, x0:x1].astype(np.float32) * tint + 0.5).astype(np.uint8)
    return result


# %% a backend answering its sub-query beside it


QUERY_COLUMN_WIDTH = 380
"""
Pixels wide the column is that holds a sub-query beside the close-up answering it.
"""

COLUMN_GAP = 24
"""
Pixels between the screen's edges and the sub-query's column or the close-up.
"""

ARROW_ROOM = 64
"""
Pixels between the sub-query's column and the close-up: room for the arrow from the
work to what it answered.
"""

QUERY_MAGNIFICATION_UP_TO = 4.0
"""
The most a held sub-query grows by over the scale the figure is placed at, where its
column would allow more.
"""

ARROW_FADE = 0.3
"""
Seconds the arrow from the work to what it answered takes to appear.
"""

ARROW_AIR = 10
"""
Pixels the arrow's head stops short of the sub-query's edge.
"""


@dataclass
class Answering(Scene):
    """
    A backend answering its sub-query: the sub-query grows out of the plan into a
    column on the left and is held there while the work grows out of the backend's
    panel beside it and plays; then an arrow from the work points to what it answered
    and the answer is written into the sub-query as written, its ``...`` replaced,
    which shrinks back into its place in the plan as the work shrinks back into its
    panel, both filled in by the time they land.
    """

    before: FigureOnCanvas
    """
    The figure as it stands while the backend works, with its slot ringed.
    """

    after: FigureOnCanvas
    """
    The figure once the backend has answered, which everything shrinks back onto.
    """

    slot: Slot
    """
    The slot being answered.
    """

    work: Scene
    """
    What plays in the close-up.
    """

    hue: Rgb
    """
    The colour the sub-query, the close-up and the arrow are drawn in.
    """

    title: str = ""
    """
    What the backend at work is called, on a tab over the close-up; nothing for no tab.
    """

    marks: Tuple[Mark, ...] = ()
    """
    The parts of the sub-query pointed to while it is held: its open field, if it has
    one, which the arrow then aims at.
    """

    filled_hue: Rgb = Ink.ASKED.rgb
    """
    The colour what was filled in is ringed in, once written.
    """

    query_for: float = 1.5
    """
    Seconds the sub-query is held alone, grown out, before the close-up grows out.
    """

    grow: float = 0.8
    """
    Seconds the sub-query takes to grow out.
    """

    close_up_grow: float = 1.2
    """
    Seconds the close-up takes to grow out.
    """

    fill_for: float = 0.8
    """
    Seconds the answer takes to be written into the sub-query.
    """

    filled_for: float = 0.6
    """
    Seconds the answer is held, written in.
    """

    shrink: float = 0.6
    """
    Seconds the answer and the close-up take to shrink back.
    """

    # %% when things happen

    @property
    def close_up_from(self) -> float:
        """
        Seconds into the scene the close-up starts growing out.
        """
        return self.grow + self.query_for

    @property
    def work_from(self) -> float:
        """
        Seconds into the scene the work starts playing, the close-up fully grown.
        """
        return self.close_up_from + self.close_up_grow

    @property
    def fill_from(self) -> float:
        """
        Seconds into the scene the answer starts being written in, the work over.
        """
        return self.work_from + self.work.duration

    @property
    def shrink_from(self) -> float:
        """
        Seconds into the scene everything starts shrinking back.
        """
        return self.fill_from + self.fill_for + self.filled_for

    @property
    def duration(self) -> float:
        return self.shrink_from + self.shrink

    # %% where things lie

    @cached_property
    def close_up(self) -> Area:
        """
        Where the work plays fully grown: right of the sub-query's column, as large as
        the work's stage allows there, centred; the band the work leaves clear for
        subtitles is cut off, since the close-up stays above the screen's.
        """
        resolution = self.before.resolution
        left = COLUMN_GAP + QUERY_COLUMN_WIDTH + ARROW_ROOM
        room = Area(
            left,
            resolution.stage_height * (1 - CLOSE_UP_SHARE) / 2,
            resolution.width - left - COLUMN_GAP,
            resolution.stage_height * CLOSE_UP_SHARE,
        )
        sample = self._works_stage(self.work.frame_at(0.0))
        return room.fitting(sample.shape[1] / sample.shape[0])

    @staticmethod
    def _works_stage(frame: Frame) -> Frame:
        """
        A frame of the work without the band it leaves clear for subtitles.
        """
        return frame[: int(round(frame.shape[0] * (1 - SUBTITLE_BAND_SHARE)))]

    @property
    def query_box(self) -> FigureBox:
        """
        The sub-query, in the figure's centimetres.
        """
        return self.before.figure.geometry.slots[self.slot]

    @property
    def filled_box(self) -> FigureBox:
        """
        The sub-query with its answer written in, where it lies in the plan once its
        backend has answered, in the figure's centimetres.
        """
        return self.after.figure.geometry.slots[self.slot]

    @cached_property
    def scale(self) -> float:
        """
        The pixels per centimetre the sub-query and its answer are read at.
        """
        return min(QUERY_COLUMN_WIDTH / self.query_box.width, self.before.pixels_per_centimetre * QUERY_MAGNIFICATION_UP_TO)

    @cached_property
    def query_window(self) -> Area:
        """
        Where the sub-query lies fully grown: in its column, level with the middle of
        the close-up.
        """
        width, height = self.query_box.width * self.scale, self.query_box.height * self.scale
        return Area(COLUMN_GAP + (QUERY_COLUMN_WIDTH - width) / 2, self.close_up.centre[1] - height / 2, width, height)

    @cached_property
    def filled_window(self) -> Area:
        """
        Where the sub-query lies with its answer written in: from its own top left
        corner.
        """
        query = self.query_window
        return Area(query.x, query.y, self.filled_box.width * self.scale, self.filled_box.height * self.scale)

    @property
    def aimed_at(self) -> Tuple[float, float]:
        """
        Where the arrow from the work points: just outside the sub-query's right edge,
        level with its open field if it has one, else with its middle, so that the
        arrow never lies over the writing.
        """
        window = self.query_window
        x = max(window.right, self.filled_window.right) + ARROW_AIR
        if not self.marks:
            return x, window.centre[1]
        field = self.marks[0].box
        return x, window.y + (field.y + field.height / 2 - self.query_box.y) * self.scale

    # %% drawing

    @cached_property
    def query_picture(self) -> Frame:
        return self.before.cut_out(self.query_box, self.scale)

    @cached_property
    def filled_picture(self) -> Frame:
        return self.after.cut_out(self.filled_box, self.scale)

    @property
    def filled_marks(self) -> Tuple[Mark, ...]:
        """
        What was filled in, marked as the answer is written: the value that took the
        ``...``, or the lines that took the whole description.
        """
        fields = self.after.figure.geometry.filled_fields
        if self.slot not in fields:
            return ()
        return (Mark(fields[self.slot], self.filled_hue, from_second=self.fill_from),)

    def filled_picture_at(self, seconds: float) -> Frame:
        """
        The sub-query with its answer written in, what was filled in marked.
        """
        return marked(self.filled_picture, (self.filled_box.x, self.filled_box.y), self.scale, self.filled_marks, seconds)

    def query_grown_at(self, seconds: float) -> float:
        """
        How far the sub-query's column has grown at a moment, from zero to one.
        """
        return grown(seconds, self.grow, self.shrink_from - self.grow, self.shrink)

    def close_up_grown_at(self, seconds: float) -> float:
        """
        How far the close-up has grown at a moment, from zero to one.
        """
        return grown(seconds - self.close_up_from, self.close_up_grow, self.shrink_from - self.work_from, self.shrink)

    def filled_at(self, seconds: float) -> float:
        """
        How far the answer has been written in at a moment, from zero to one.
        """
        return eased((seconds - self.fill_from) / self.fill_for)

    def picture_at(self, seconds: float) -> Frame:
        shrinking = seconds >= self.shrink_from
        shown = self.after if shrinking else self.before
        query_progress = self.query_grown_at(seconds)
        close_up_progress = self.close_up_grown_at(seconds) if seconds >= self.close_up_from else 0.0
        frame = dimmed(shown.frame, 0.55 * max(query_progress, close_up_progress))
        frame = self._column_drawn(frame, shown, seconds, query_progress, shrinking)
        if close_up_progress > 0.0:
            frame = self._close_up_drawn(frame, shown, seconds, close_up_progress)
        return self._arrow_drawn(frame, seconds)

    def _column_drawn(self, frame: Frame, shown: FigureOnCanvas, seconds: float, progress: float, shrinking: bool) -> Frame:
        """
        The sub-query, or the answer written into it, where it lies at a moment.
        """
        filled_in = self.filled_at(seconds)
        if shrinking:
            where = shown.area_of(self.filled_box).towards(self.filled_window, progress)
            return self._pasted(frame, self.filled_picture_at(seconds), where)
        where = shown.area_of(self.query_box).towards(self.query_window, progress)
        picture = marked(self.query_picture, (self.query_box.x, self.query_box.y), self.scale, self.marks, seconds)
        with_query = self._pasted(frame, picture, where)
        if filled_in <= 0.0:
            return with_query
        return blended(with_query, self._pasted(frame, self.filled_picture_at(seconds), self.filled_window), filled_in)

    def _close_up_drawn(self, frame: Frame, shown: FigureOnCanvas, seconds: float, progress: float) -> Frame:
        """
        The work, where it lies at a moment, with its tab once fully grown.
        """
        where = shown.panel(self.slot).towards(self.close_up, progress)
        played = min(max(seconds - self.work_from, 0.0), self.work.duration - 1e-6)
        frame = self._pasted(frame, self._works_stage(self.work.frame_at(played)), where)
        if self.title and progress >= 1.0:
            frame = tabbed(frame, where, self.title, self.hue)
        return frame

    def _arrow_drawn(self, frame: Frame, seconds: float) -> Frame:
        """
        The arrow from the work's left middle to what it answered, from the moment the
        answer is written in until everything shrinks back.
        """
        if seconds < self.fill_from or seconds >= self.shrink_from:
            return frame
        weight = eased((seconds - self.fill_from) / ARROW_FADE)
        start = (self.close_up.x - 8, self.close_up.centre[1])
        return blended(frame, arrowed(frame, start, self.aimed_at, self.hue, thickness=4), weight)

    def _pasted(self, frame: Frame, picture: Frame, where: Area) -> Frame:
        """
        A picture framed in the hue and pasted where it lies.
        """
        frame = filled(frame, where.inset(-4), self.hue)
        return pasted(frame, picture, where)


# %% a stretch of the figure read through, scrolling


@dataclass(frozen=True)
class ReadingStop:
    """
    Where a reading of a scrolled stretch of the figure has got to at a moment.
    """

    seconds: float
    """
    The moment, into the scene.
    """

    top: float
    """
    The figure's y, in centimetres, that lies at the window's top edge then.
    """


@dataclass
class Scrolled(Scene):
    """
    A stretch of the figure too tall to read at once, grown out of its place into a
    window it is read through, scrolled down as it is read, and shrunk back; the rest
    of the figure dims behind it.
    """

    shown: FigureOnCanvas
    """
    The figure at its stage.
    """

    box: FigureBox
    """
    The stretch read, in the figure's centimetres.
    """

    hue: Rgb
    """
    The colour the window is framed in.
    """

    stops: Tuple[ReadingStop, ...] = ()
    """
    Where the reading has got to at some moments, in order: the window's top moves
    evenly from each to the next and rests before the first and after the last; none
    to rest at the top of the stretch throughout.
    """

    held_for: float = 6.0
    """
    Seconds the window is held fully grown.
    """

    grow: float = 0.8
    """
    Seconds it takes to grow out.
    """

    shrink: float = 0.6
    """
    Seconds it takes to shrink back.
    """

    magnification_up_to: float = 2.5
    """
    The most the stretch grows by, over the scale the figure is placed at, where the
    screen's width would allow more.
    """

    marks: Tuple[Mark, ...] = ()
    """
    The parts of the stretch pointed to while it is read, if any.
    """

    @property
    def duration(self) -> float:
        return self.grow + self.held_for + self.shrink

    @cached_property
    def scale(self) -> float:
        """
        The pixels per centimetre the stretch is read at: as wide as the room allows,
        up to the magnification.
        """
        room = magnifying_room(self.shown.resolution)
        return min(room.width / self.box.width, self.shown.pixels_per_centimetre * self.magnification_up_to)

    @cached_property
    def window(self) -> Area:
        """
        Where the stretch is read fully grown: at its scale, as tall as the room allows
        or the stretch is, centred on the stage.
        """
        room = magnifying_room(self.shown.resolution)
        width = self.box.width * self.scale
        height = min(room.height, self.box.height * self.scale)
        return Area(room.centre[0] - width / 2, room.centre[1] - height / 2, width, height)

    @cached_property
    def picture(self) -> Frame:
        return self.shown.cut_out(self.box, self.scale)

    @property
    def lowest_top(self) -> float:
        """
        The figure's y at the window's top when the stretch's bottom edge lies at its
        bottom: as far as the reading can scroll.
        """
        return self.box.y + self.box.height - self.window.height / self.scale

    def top_at(self, seconds: float) -> float:
        """
        The figure's y at the window's top at a moment, fully grown.
        """
        top = self.box.y
        for earlier, later in zip(self.stops, self.stops[1:]):
            if seconds >= later.seconds:
                continue
            if seconds > earlier.seconds:
                share = (seconds - earlier.seconds) / (later.seconds - earlier.seconds)
                top = earlier.top + (later.top - earlier.top) * share
            else:
                top = earlier.top
            break
        else:
            if self.stops:
                top = self.stops[-1].top
        return min(max(top, self.box.y), self.lowest_top)

    def grown_at(self, seconds: float) -> float:
        """
        How far the window has grown at a moment, from zero to one.
        """
        return grown(seconds, self.grow, self.held_for, self.shrink)

    def picture_at(self, seconds: float) -> Frame:
        progress = self.grown_at(seconds)
        placed = self.shown.area_of(self.box)
        where = placed.towards(self.window, progress)
        # the window opens from the whole stretch at its place to its share of it, read at its scale
        scale = self.shown.pixels_per_centimetre + (self.scale - self.shown.pixels_per_centimetre) * progress
        top = self.box.y + (self.top_at(seconds) - self.box.y) * progress
        first = int(round((top - self.box.y) * self.scale))
        last = int(round((top - self.box.y + where.height / scale) * self.scale))
        frame = dimmed(self.shown.frame, 0.55 * progress)
        frame = filled(frame, where.inset(-4), self.hue)
        picture = marked(self.picture[first:last], (self.box.x, self.box.y + first / self.scale), self.scale, self.marks, seconds)
        return pasted(frame, picture, where)


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
