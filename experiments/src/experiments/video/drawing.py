"""
Drawing an animated scene with Manim.

A video's :class:`~experiments.video.canvas.VideoTheme` is read as Manim colours, so an
animated scene and a frame built scene look like one video. Each piece a scene draws is
a builder: a dataclass naming what it shows, answering :meth:`built` with the Manim
object. A :class:`ScenePainting` says which pieces one scene draws and what it plays on
each beat, and :class:`ManimRenderer` turns that into the frames the timeline reads.

Manim needs cairo and pango on the machine, so this module is imported only where an
animated scene is drawn; :mod:`experiments.video.animation` stays free of it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import mkdtemp
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    Arrow,
    Dot,
    FadeOut,
    GrowFromEdge,
    LaggedStart,
    Line as ManimLine,
    Mobject,
    Rectangle,
    RoundedRectangle,
    Scene as ManimScene,
    Square,
    Text,
    VGroup,
    VMobject,
    always_redraw,
    tempconfig,
)
from typing_extensions import Any, List, Optional, Sequence, Tuple

from experiments.video.animation import AnimationStep, BeatSchedule
from experiments.video.cache import SceneCache
from experiments.video.canvas import NEUTRAL_THEME, Rgb, VideoTheme
from experiments.video.timeline import Frame, Resolution

# %% a theme as Manim takes it


class LetterWeight(StrEnum):
    """
    How heavy the letters of a piece of text are, as Manim names its weights.
    """

    NORMAL = "NORMAL"
    """
    The weight running text is set in.
    """

    BOLD = "BOLD"
    """
    The weight a heading is set in.
    """


@dataclass(frozen=True)
class AnimationPalette:
    """
    A video's theme read as the hexadecimal colours Manim takes.
    """

    page: str
    """
    What the frame is filled with behind everything.
    """

    text: str
    """
    What running text is written in.
    """

    muted: str
    """
    What a label beside the subject is written in.
    """

    hairline: str
    """
    What a rule or the shaft of an arrow is drawn in.
    """

    panel: str
    """
    What a card or a panel is filled with.
    """

    accent: str
    """
    The one colour a video marks what matters with.
    """

    typeface: str
    """
    The family every piece of text is set in.
    """

    monospace: str
    """
    The family a panel of code is set in.
    """

    @staticmethod
    def hex_of(colour: Rgb) -> str:
        """
        :param colour: A colour as red, green and blue bytes.
        :return: The same colour as Manim writes one.
        """
        red, green, blue = colour
        return f"#{red:02X}{green:02X}{blue:02X}"

    @classmethod
    def of(cls, theme: VideoTheme) -> AnimationPalette:
        """
        :param theme: The colours and fonts the video is drawn in.
        :return: The same colours as Manim takes them.
        """
        return cls(
            page=cls.hex_of(theme.page),
            text=cls.hex_of(theme.text),
            muted=cls.hex_of(theme.muted),
            hairline=cls.hex_of(theme.hairline),
            panel=cls.hex_of(theme.panel),
            accent=cls.hex_of(theme.accent),
            typeface=theme.typeface.regular,
            monospace=theme.typeface.mono,
        )


# %% what one piece of a scene is built from


@dataclass
class DrawingBuilder(ABC):
    """
    One piece a scene draws, named by what it shows.
    """

    @abstractmethod
    def built(self) -> Mobject:
        """
        The piece, as Manim draws it.
        """


@dataclass
class Headline(DrawingBuilder):
    """
    A piece of text, set large and scaled down so its letters are evenly spaced however
    small it ends up.
    """

    words: str
    """
    What it says.
    """

    size: float = 28.0
    """
    The height of its letters once it has been scaled down.
    """

    colour: Optional[str] = None
    """
    What it is written in; the palette's text colour where none is given.
    """

    weight: LetterWeight = LetterWeight.NORMAL
    """
    How heavy its letters are.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    short_enough_to_enlarge: int = 40
    """
    Letters up to which the text is set at the larger factor; a longer line is set at
    the smaller one so Manim does not wrap it inside its own box.
    """

    larger_factor: float = 4.0
    """
    How much larger a short line is set before being scaled down.
    """

    smaller_factor: float = 2.5
    """
    How much larger a long line is set before being scaled down.
    """

    def built(self) -> Mobject:
        factor = (
            self.larger_factor
            if len(self.words) <= self.short_enough_to_enlarge
            else self.smaller_factor
        )
        drawn = Text(
            self.words,
            font=self.palette.typeface,
            font_size=self.size * factor,
            color=self.colour or self.palette.text,
            weight=self.weight.value,
        )
        return drawn.scale(1.0 / factor)

    def fitted_to(self, width: float) -> Mobject:
        """
        :param width: The widest the text may be, in Manim's units.
        :return: The text, narrowed to that width if it is wider.
        """
        drawn = self.built()
        if drawn.width > width:
            drawn.scale_to_fit_width(width)
        return drawn


@dataclass
class Chip(DrawingBuilder):
    """
    A short label in a rounded outline, for a state or a name.
    """

    words: str
    """
    What the chip says.
    """

    colour: str
    """
    What its outline is drawn and its inside tinted in.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    size: float = 22.0
    """
    The height of its letters.
    """

    tint: float = 0.18
    """
    How solidly its inside is filled, from clear to opaque.
    """

    padding: Tuple[float, float] = (0.4, 0.26)
    """
    How far its outline sits beyond its label, across and down.
    """

    def built(self) -> VGroup:
        label = Headline(self.words, size=self.size, palette=self.palette).built()
        across, down = self.padding
        box = RoundedRectangle(
            corner_radius=0.14,
            width=label.width + across,
            height=label.height + down,
            stroke_color=self.colour,
            stroke_width=2,
            fill_color=self.colour,
            fill_opacity=self.tint,
        )
        return VGroup(box, label.move_to(box))


@dataclass
class Card(DrawingBuilder):
    """
    A panel with a heading and some lines under it.
    """

    heading: str
    """
    What the card is about.
    """

    body: Tuple[str, ...]
    """
    The lines under the heading, one per row.
    """

    colour: str
    """
    What its outline and heading are drawn in.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    width: float = 3.6
    """
    How wide the panel is, in Manim's units.
    """

    height: float = 2.0
    """
    How tall the panel is, in Manim's units.
    """

    heading_size: float = 26.0
    """
    The height of the heading's letters.
    """

    body_size: float = 20.0
    """
    The height of the body's letters.
    """

    def built(self) -> VGroup:
        box = RoundedRectangle(
            corner_radius=0.18,
            width=self.width,
            height=self.height,
            stroke_color=self.colour,
            stroke_width=2,
            fill_color=self.palette.panel,
            fill_opacity=1,
        )
        heading = Headline(
            self.heading,
            size=self.heading_size,
            colour=self.colour,
            weight=LetterWeight.BOLD,
            palette=self.palette,
        ).built()
        rows = VGroup(
            *[
                Headline(row, size=self.body_size, palette=self.palette).built()
                for row in self.body
            ]
        ).arrange(DOWN, buff=0.12)
        content = VGroup(heading, rows).arrange(DOWN, buff=0.22).move_to(box)
        return VGroup(box, content)


@dataclass
class BoxNode(DrawingBuilder):
    """
    A label in a rounded box, for one step of a diagram.
    """

    words: str
    """
    What the node says.
    """

    colour: str
    """
    What its outline is drawn and its inside tinted in.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    width: Optional[float] = None
    """
    How wide the box is; as wide as its label needs where none is given.
    """

    size: float = 24.0
    """
    The height of its letters.
    """

    height: float = 0.62
    """
    How tall the box is, in Manim's units.
    """

    tint: float = 0.16
    """
    How solidly its inside is filled.
    """

    def built(self) -> VGroup:
        label = Headline(self.words, size=self.size, palette=self.palette).built()
        box = RoundedRectangle(
            corner_radius=0.14,
            width=self.width if self.width is not None else label.width + 0.5,
            height=self.height,
            stroke_color=self.colour,
            stroke_width=2.5,
            fill_color=self.colour,
            fill_opacity=self.tint,
        )
        return VGroup(box, label.move_to(box))


@dataclass
class TickMark(DrawingBuilder):
    """
    A tick, for something that held.
    """

    colour: str
    """
    What it is drawn in.
    """

    size: float = 0.32
    """
    How tall it is, in Manim's units.
    """

    thickness: float = 5.0
    """
    How thick its stroke is.
    """

    def built(self) -> VMobject:
        mark = VMobject(stroke_color=self.colour, stroke_width=self.thickness)
        mark.set_points_as_corners(
            [[-0.5, 0.0, 0.0], [-0.15, -0.38, 0.0], [0.55, 0.45, 0.0]]
        )
        return mark.scale(self.size / 0.9)


@dataclass
class CrossMark(DrawingBuilder):
    """
    A cross, for something that did not hold.
    """

    colour: str
    """
    What it is drawn in.
    """

    size: float = 0.3
    """
    How tall it is, in Manim's units.
    """

    thickness: float = 5.0
    """
    How thick its strokes are.
    """

    def built(self) -> VGroup:
        first = ManimLine(
            [-0.5, -0.5, 0.0],
            [0.5, 0.5, 0.0],
            stroke_color=self.colour,
            stroke_width=self.thickness,
        )
        second = ManimLine(
            [-0.5, 0.5, 0.0],
            [0.5, -0.5, 0.0],
            stroke_color=self.colour,
            stroke_width=self.thickness,
        )
        return VGroup(first, second).scale(self.size)


@dataclass
class Glow(DrawingBuilder):
    """
    Layers of widening stroke around a piece, so it reads as lit rather than outlined.
    """

    around: Mobject
    """
    The piece the glow surrounds.
    """

    colour: str
    """
    What the glow is drawn in.
    """

    layers: int = 6
    """
    How many strokes are laid over each other.
    """

    widest: float = 14.0
    """
    How thick the outermost stroke is.
    """

    opacity: float = 0.08
    """
    How solid each stroke is.
    """

    def built(self) -> VGroup:
        return VGroup(
            *[
                self.around.copy()
                .set_fill(opacity=0)
                .set_stroke(
                    self.colour,
                    width=self.widest * (layer + 1) / self.layers,
                    opacity=self.opacity,
                )
                for layer in range(self.layers)
            ]
        )


# %% an arrow between two pieces


@dataclass(frozen=True)
class BoundaryPoint:
    """
    Where a line leaving one piece towards another crosses that piece's edge.
    """

    piece: Mobject
    """
    The piece the line leaves.
    """

    toward: Any
    """
    The point it heads for.
    """

    clearance: float = 0.08
    """
    How far beyond the edge the point sits, in Manim's units.
    """

    def found(self) -> np.ndarray:
        """
        The point on the piece's edge.
        """
        centre = self.piece.get_center()
        direction = np.array(self.toward, dtype=float) - centre
        direction[2] = 0.0
        if float(np.linalg.norm(direction)) < 1e-6:
            return centre
        half_width = self.piece.width / 2 + self.clearance
        half_height = self.piece.height / 2 + self.clearance
        across = half_width / abs(direction[0]) if abs(direction[0]) > 1e-6 else np.inf
        down = half_height / abs(direction[1]) if abs(direction[1]) > 1e-6 else np.inf
        return centre + direction * min(across, down)


@dataclass
class ArrowBetween(DrawingBuilder):
    """
    An arrow from the edge of one piece to the edge of another.
    """

    start: Mobject
    """
    The piece it leaves.
    """

    end: Mobject
    """
    The piece it points at.
    """

    colour: str
    """
    What it is drawn in.
    """

    clearance: float = 0.08
    """
    How far off each piece's edge it begins and ends.
    """

    thickness: float = 3.0
    """
    How thick its shaft is.
    """

    tip: float = 0.2
    """
    How long its head is, in Manim's units.
    """

    def built(self) -> Arrow:
        return Arrow(
            BoundaryPoint(self.start, self.end.get_center(), self.clearance).found(),
            BoundaryPoint(
                self.end, self.start.get_center(), self.clearance + 0.02
            ).found(),
            buff=0,
            color=self.colour,
            stroke_width=self.thickness,
            tip_length=self.tip,
            max_tip_length_to_length_ratio=0.35,
            max_stroke_width_to_length_ratio=20,
        )


# %% charts


@dataclass
class DrawnChart:
    """
    A chart once it has been drawn: its bars and the labels placed against them, so a
    caller grows the same bars it shows.
    """

    bars: VGroup
    """
    The bars, in the order their values were given.
    """

    names: VGroup
    """
    The label beside each bar.
    """

    readings: VGroup
    """
    The value beside each bar.
    """

    axis: Optional[ManimLine] = None
    """
    The rule the bars stand on, where the chart draws one.
    """

    @property
    def whole(self) -> VGroup:
        """
        Everything the chart draws, as one piece.
        """
        parts = [self.bars, self.names, self.readings]
        if self.axis is not None:
            parts.insert(0, self.axis)
        return VGroup(*parts)

    def grown(self, edge: Any, lag: float = 0.15) -> LaggedStart:
        """
        :param edge: Which edge the bars grow from, as Manim names directions.
        :param lag: How far one bar's growth trails the one before, as a share.
        :return: The bars growing one after another.
        """
        return LaggedStart(
            *[GrowFromEdge(bar, edge) for bar in self.bars], lag_ratio=lag
        )


@dataclass
class BarChart(DrawingBuilder):
    """
    Upright bars on an axis, each labelled under it and valued over it.
    """

    values: Tuple[float, ...]
    """
    What each bar stands for, as a share of the chart's height.
    """

    labels: Tuple[str, ...]
    """
    What each bar is called.
    """

    colours: Tuple[str, ...]
    """
    What each bar is filled with.
    """

    origin: Tuple[float, float]
    """
    Where the first bar stands, in Manim's units.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    bar_width: float = 0.55
    """
    How wide one bar is.
    """

    gap: float = 0.3
    """
    How far apart two bars stand.
    """

    height: float = 2.4
    """
    How tall a bar standing for one is.
    """

    reading: str = "{:.2f}"
    """
    How a bar's value is written over it.
    """

    label_size: float = 22.0
    """
    The height of the labels' letters.
    """

    value_size: float = 22.0
    """
    The height of the values' letters.
    """

    def built(self) -> VGroup:
        return self.drawn().whole

    def drawn(self) -> DrawnChart:
        """
        The chart, its labels and values placed against the bars it draws.
        """
        bars = VGroup()
        for index, (value, colour) in enumerate(zip(self.values, self.colours)):
            bar = Rectangle(
                width=self.bar_width,
                height=max(value * self.height, 0.02),
                stroke_width=0,
                fill_color=colour,
                fill_opacity=0.92,
            )
            bar.move_to([self._x_of(index), self.origin[1], 0.0], aligned_edge=DOWN)
            bars.add(bar)
        names = VGroup(
            *[
                Headline(
                    label,
                    size=self.label_size,
                    colour=self.palette.muted,
                    palette=self.palette,
                )
                .built()
                .next_to([self._x_of(index), self.origin[1], 0.0], DOWN, buff=0.15)
                for index, label in enumerate(self.labels)
            ]
        )
        readings = VGroup(
            *[
                Headline(
                    self.reading.format(value),
                    size=self.value_size,
                    palette=self.palette,
                )
                .built()
                .next_to(bars[index], UP, buff=0.1)
                for index, value in enumerate(self.values)
            ]
        )
        return DrawnChart(bars=bars, names=names, readings=readings, axis=self._axis())

    def _axis(self) -> ManimLine:
        """
        The rule the bars stand on.
        """
        left = self.origin[0] - self.bar_width / 2 - 0.15
        right = self._x_of(len(self.values) - 1) + self.bar_width / 2 + 0.15
        return ManimLine(
            [left, self.origin[1], 0.0],
            [right, self.origin[1], 0.0],
            stroke_color=self.palette.hairline,
            stroke_width=2,
        )

    def _x_of(self, index: int) -> float:
        """
        :param index: Which bar, from zero.
        :return: Where it stands across the frame.
        """
        return self.origin[0] + index * (self.bar_width + self.gap)


@dataclass
class HorizontalBarChart(DrawingBuilder):
    """
    Bars running right from a shared left edge, each named to its left and valued to its
    right.
    """

    values: Tuple[float, ...]
    """
    What each bar stands for, in the units the scale reads them at.
    """

    labels: Tuple[str, ...]
    """
    What each bar is called.
    """

    colours: Tuple[str, ...]
    """
    What each bar is filled with.
    """

    origin: Tuple[float, float]
    """
    Where the topmost bar begins, in Manim's units.
    """

    scale: float
    """
    How many of Manim's units one unit of value is drawn as.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    bar_height: float = 0.38
    """
    How tall one bar is.
    """

    gap: float = 0.22
    """
    How far apart two bars sit.
    """

    reading: str = "{:.2f}"
    """
    How a bar's value is written beside it.
    """

    label_size: float = 20.0
    """
    The height of the labels' letters.
    """

    value_size: float = 20.0
    """
    The height of the values' letters.
    """

    def built(self) -> VGroup:
        return self.drawn().whole

    def drawn(self) -> DrawnChart:
        """
        The chart, its names and values placed against the bars it draws.
        """
        bars = VGroup()
        for index, (value, colour) in enumerate(zip(self.values, self.colours)):
            bar = Rectangle(
                width=max(abs(value) * self.scale, 0.02),
                height=self.bar_height,
                stroke_width=0,
                fill_color=colour,
                fill_opacity=0.92,
            )
            bar.move_to(
                [self.origin[0], self._y_of(index), 0.0],
                aligned_edge=LEFT if value >= 0 else RIGHT,
            )
            bars.add(bar)
        names = VGroup(
            *[
                Headline(label, size=self.label_size, palette=self.palette)
                .built()
                .next_to(bars[index], LEFT, buff=0.2)
                for index, label in enumerate(self.labels)
            ]
        )
        readings = VGroup(
            *[
                Headline(
                    self.reading.format(value),
                    size=self.value_size,
                    palette=self.palette,
                )
                .built()
                .next_to(bars[index], RIGHT, buff=0.15)
                for index, value in enumerate(self.values)
            ]
        )
        return DrawnChart(bars=bars, names=names, readings=readings)

    def _y_of(self, index: int) -> float:
        """
        :param index: Which bar, from zero.
        :return: Where it sits down the frame.
        """
        return self.origin[1] - index * (self.bar_height + self.gap)


@dataclass
class WaffleChart(DrawingBuilder):
    """
    A hundred squares in a square, as many of them coloured as the share asks for,
    filling from the bottom row upwards.
    """

    share: float
    """
    How much of the grid is coloured, from none to all.
    """

    colour: str
    """
    What the coloured squares are filled with.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    cell: float = 0.17
    """
    How wide one square is, in Manim's units.
    """

    gap: float = 0.045
    """
    How far apart two squares sit.
    """

    side: int = 10
    """
    How many squares one row holds.
    """

    def built(self) -> VGroup:
        squares = VGroup(
            *[
                Square(
                    self.cell,
                    stroke_width=0,
                    fill_color=self.palette.hairline,
                    fill_opacity=0.22,
                )
                for _ in range(self.side * self.side)
            ]
        )
        return squares.arrange_in_grid(self.side, self.side, buff=self.gap)

    def coloured_of(self, grid: VGroup) -> VGroup:
        """
        :param grid: The squares, as :meth:`built` arranged them.
        :return: Those of them this share colours, bottom row first.
        """
        count = self.side * self.side
        order = sorted(
            range(count), key=lambda index: (-(index // self.side), index % self.side)
        )
        return VGroup(*[grid[index] for index in order[: round(self.share * count)]])

    def filled(self, coloured: VGroup, lag: float = 0.02) -> LaggedStart:
        """
        :param coloured: The squares to colour, as :meth:`coloured_of` chose them.
        :param lag: How far one square's filling trails the one before, as a share.
        :return: Those squares filling one after another.
        """
        return LaggedStart(
            *[square.animate.set_fill(self.colour, 0.95) for square in coloured],
            lag_ratio=lag,
        )


@dataclass
class IconRow(DrawingBuilder):
    """
    A row of small squares, the first of them coloured, for a count out of a total.
    """

    coloured: int
    """
    How many squares are coloured.
    """

    total: int
    """
    How many squares the row holds.
    """

    colour: str
    """
    What the coloured squares are filled with.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    size: float = 0.26
    """
    How wide one square is, in Manim's units.
    """

    gap: float = 0.08
    """
    How far apart two squares sit.
    """

    def built(self) -> VGroup:
        row = VGroup(
            *[
                Square(
                    self.size,
                    stroke_width=0,
                    fill_color=(
                        self.colour if index < self.coloured else self.palette.hairline
                    ),
                    fill_opacity=0.95 if index < self.coloured else 0.25,
                )
                for index in range(self.total)
            ]
        )
        return row.arrange(RIGHT, buff=self.gap)


@dataclass
class RunningCount(DrawingBuilder):
    """
    A number redrawn every frame from a value that is being animated.
    """

    tracker: Any
    """
    What holds the value, as Manim's value tracker does.
    """

    reading: str
    """
    How the value is written, taking it as a whole number.
    """

    anchor: Any
    """
    Where the number sits, in Manim's units.
    """

    colour: str
    """
    What it is written in.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    size: float = 28.0
    """
    The height of its letters.
    """

    def built(self) -> Mobject:
        return always_redraw(
            lambda: Headline(
                self.reading.format(round(self.tracker.get_value())),
                size=self.size,
                colour=self.colour,
                weight=LetterWeight.BOLD,
                palette=self.palette,
            )
            .built()
            .move_to(self.anchor)
        )


# %% backgrounds and panels


@dataclass
class DriftingConstellation(DrawingBuilder):
    """
    A faint network of dots joined by lines, turning slowly behind everything else.
    """

    colour: str
    """
    What its dots and lines are drawn in.
    """

    dots: int = 46
    """
    How many dots it holds.
    """

    seed: int = 5
    """
    Which arrangement of dots is drawn, so a rendering repeats.
    """

    joined_within: float = 1.6
    """
    How close two dots must be for a line to join them, in Manim's units.
    """

    turns_at: float = 0.012
    """
    Radians a second it turns by.
    """

    spread: Tuple[float, float] = (7.4, 4.2)
    """
    How far the dots scatter across and down from the middle.
    """

    depth: int = -5
    """
    Where it sits in the stack, below everything a scene draws over it.
    """

    def built(self) -> VGroup:
        random_state = np.random.default_rng(self.seed)
        across, down = self.spread
        points = [
            np.array(
                [
                    random_state.uniform(-across, across),
                    random_state.uniform(-down, down),
                    0.0,
                ]
            )
            for _ in range(self.dots)
        ]
        drawn_dots = VGroup(
            *[
                Dot(point, radius=0.035, color=self.colour, fill_opacity=0.45)
                for point in points
            ]
        )
        lines = VGroup()
        for first in range(self.dots):
            for second in range(first + 1, self.dots):
                apart = float(np.linalg.norm(points[first] - points[second]))
                if apart >= self.joined_within:
                    continue
                lines.add(
                    ManimLine(
                        points[first],
                        points[second],
                        stroke_color=self.colour,
                        stroke_width=1.2,
                        stroke_opacity=0.04
                        + 0.16 * (self.joined_within - apart) / self.joined_within,
                    )
                )
        whole = VGroup(lines, drawn_dots)
        whole.set_z_index(self.depth)
        whole.add_updater(self._turning)
        return whole

    def _turning(self, piece: Mobject, dt: float) -> None:
        """
        Turn the network on by one frame's worth.

        :param piece: The network.
        :param dt: Seconds since the frame before; Manim reads this parameter's name to
            decide whether an updater is given the elapsed time, so it keeps Manim's.
        """
        piece.rotate(self.turns_at * dt, about_point=ORIGIN)


@dataclass
class CodePanel(DrawingBuilder):
    """
    Lines of code set in one width, each indented as it was written.
    """

    lines: Tuple[str, ...]
    """
    The lines, their leading spaces kept.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    size: float = 22.0
    """
    The height of its letters.
    """

    line_gap: float = 0.52
    """
    How far apart two lines sit, in Manim's units.
    """

    top_left: Tuple[float, float] = (-5.6, 2.35)
    """
    Where the first line begins, in Manim's units.
    """

    factor: float = 4.0
    """
    How much larger the text is set before being scaled down.
    """

    def built(self) -> VGroup:
        scale = 1.0 / self.factor
        probe = Text(
            "M" * 20, font=self.palette.monospace, font_size=self.size * self.factor
        ).scale(scale)
        letter_width = probe.width / 20
        left, top = self.top_left
        drawn = VGroup()
        for index, line in enumerate(self.lines):
            text = Text(
                line.strip(),
                font=self.palette.monospace,
                font_size=self.size * self.factor,
                color=self.palette.text,
            ).scale(scale)
            indent = len(line) - len(line.lstrip())
            text.move_to(
                [left + indent * letter_width, top - index * self.line_gap, 0.0],
                aligned_edge=LEFT,
            )
            drawn.add(text)
        return drawn


@dataclass
class ChapterHeader(DrawingBuilder):
    """
    A chapter's number and title, small, in the frame's top left corner.
    """

    number: str
    """
    Which chapter it is.
    """

    title: str
    """
    What the chapter is about.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it is drawn in.
    """

    size: float = 20.0
    """
    The height of its letters.
    """

    inset: float = 0.38
    """
    How far in from the corner it sits, in Manim's units.
    """

    def built(self) -> VGroup:
        label = VGroup(
            Headline(
                self.number,
                size=self.size,
                colour=self.palette.accent,
                weight=LetterWeight.BOLD,
                palette=self.palette,
            ).built(),
            Headline(
                self.title,
                size=self.size,
                colour=self.palette.muted,
                palette=self.palette,
            ).built(),
        ).arrange(RIGHT, buff=0.18)
        return label.to_corner(UP + LEFT, buff=self.inset)


# %% what a scene draws


@dataclass
class ScenePainting(ABC):
    """
    What one animated scene draws, and what it plays on each of its beats.
    """

    @abstractmethod
    def beats_of(
        self, painter: ScenePainter, palette: AnimationPalette
    ) -> List[Tuple[AnimationStep, ...]]:
        """
        The steps to play on each beat, one tuple per beat.

        :param painter: The Manim scene the steps are played on.
        :param palette: The colours and fonts to draw in.
        """


@dataclass
class ScenePainter(ManimScene):
    """
    The Manim scene an animated scene's steps are played on: it plays one beat at a
    time, scaling its steps down to fit the beat and waiting out whatever is left.

    It adds no sound and no captions; the production does both.
    """

    painting: ScenePainting = field(kw_only=True)
    """
    What the scene draws.
    """

    schedule: BeatSchedule = field(kw_only=True)
    """
    The beats it plays against.
    """

    palette: AnimationPalette = field(kw_only=True)
    """
    The colours and fonts it draws in.
    """

    def __post_init__(self) -> None:
        ManimScene.__init__(self)
        self.played = 0

    @property
    def schedule_beats(self) -> int:
        """
        How many beats the scene plays against.
        """
        return len(self.schedule.beats)

    def construct(self) -> None:
        """
        Play every beat the painting asks for, then check that it played one per line.

        :raises BeatMiscount: If it played a different number of beats than there are
            lines.
        """
        for steps in self.painting.beats_of(self, self.palette):
            self.play_beat(steps)
        self.schedule.check_played(self.played)

    def play_beat(self, steps: Sequence[AnimationStep]) -> None:
        """
        Play one beat's steps, then wait out the rest of the beat.

        :param steps: The steps of that beat, in order.
        """
        beat = self.schedule.beats[min(self.played, len(self.schedule.beats) - 1)]
        self.played += 1
        for step, length in zip(steps, beat.lengths_of(steps)):
            drawn = self._resolved(step)
            if drawn:
                self.play(*drawn, run_time=length)
                continue
            self.wait(length)
        waiting = beat.waits_after(steps)
        if waiting > 0.0:
            self.wait(waiting)

    @staticmethod
    def _resolved(step: AnimationStep) -> List[Any]:
        """
        :param step: One step of a beat.
        :return: What it plays, building whatever it left until the steps before had
            run.
        """
        drawn: List[Any] = []
        for item in step.drawn:
            if not callable(item) or isinstance(item, Mobject):
                drawn.append(item)
                continue
            made = item()
            drawn.extend(made if isinstance(made, (list, tuple)) else [made])
        return drawn

    def faded_out(self, keeping: Sequence[Mobject] = ()) -> List[Any]:
        """
        :param keeping: What stays on the frame.
        :return: Everything else on the frame fading out.
        """
        return [
            FadeOut(piece) for piece in self.mobjects if piece not in tuple(keeping)
        ]


# %% rendering a painting to frames


class RenderQuality(StrEnum):
    """
    How finely Manim draws, as it names its qualities.
    """

    LOW = "low_quality"
    """
    Quick, for a test or a draft.
    """

    HIGH = "high_quality"
    """
    For the video handed on.
    """


@dataclass
class ManimRenderer:
    """
    Draws a painting's beats to frames, keeping them so a second rendering of the same
    beats reads them back instead of drawing again.
    """

    painting: ScenePainting
    """
    What the scene draws.
    """

    palette: AnimationPalette = field(
        default_factory=lambda: AnimationPalette.of(NEUTRAL_THEME)
    )
    """
    The colours and fonts it draws in.
    """

    cache: Optional[SceneCache] = None
    """
    Where the drawn frames are kept; they are drawn afresh every time where none is
    given.
    """

    quality: RenderQuality = RenderQuality.HIGH
    """
    How finely Manim draws.
    """

    def frames_of(
        self, schedule: BeatSchedule, resolution: Resolution, frames_per_second: int
    ) -> List[Frame]:
        """
        Every frame of the scene, drawn once for a set of beats and read back after.

        :param schedule: The beats the scene plays against.
        :param resolution: The size every frame has.
        :param frames_per_second: The rate the frames are drawn at.
        """
        kept = self._kept(schedule, resolution, frames_per_second)
        if kept is not None:
            return kept
        drawn = self._drawn(schedule, resolution, frames_per_second)
        self._keep(drawn, schedule, resolution, frames_per_second)
        return drawn

    def key_for(
        self, schedule: BeatSchedule, resolution: Resolution, frames_per_second: int
    ) -> str:
        """
        :param schedule: The beats the scene plays against.
        :param resolution: The size every frame has.
        :param frames_per_second: The rate the frames are drawn at.
        :return: What a drawing of those beats at that size is kept under.
        """
        lengths = "-".join(f"{length:.3f}" for length in schedule.lengths)
        return (
            f"{type(self.painting).__name__}"
            f"_{resolution.width}x{resolution.height}"
            f"_{frames_per_second}fps_{lengths}"
        )

    def _drawn(
        self, schedule: BeatSchedule, resolution: Resolution, frames_per_second: int
    ) -> List[Frame]:
        """
        The frames, drawn by Manim to a lossless clip and read back.

        Manim writes the clip and its working files into a directory of its own, removed
        once the frames have been read, so a rendering leaves nothing behind it.
        """
        working = Path(mkdtemp(prefix="experiments-video-"))
        settings = {
            "quality": self.quality.value,
            "pixel_width": resolution.width,
            "pixel_height": resolution.height,
            "frame_rate": frames_per_second,
            "background_color": self.palette.page,
            "format": "mov",
            "movie_file_extension": ".mov",
            "write_to_movie": True,
            "disable_caching": True,
            "verbosity": "ERROR",
            "media_dir": str(working),
        }
        with tempconfig(settings):
            painter = ScenePainter(
                painting=self.painting, schedule=schedule, palette=self.palette
            )
            painter.render()
            clip = painter.renderer.file_writer.movie_file_path
            frames = self._read(clip)
        shutil.rmtree(working, ignore_errors=True)
        return frames

    @staticmethod
    def _read(clip) -> List[Frame]:
        """
        :param clip: A clip Manim wrote.
        :return: Its frames, as red, green and blue.
        """
        reader = cv2.VideoCapture(str(clip))
        frames: List[Frame] = []
        while True:
            read, frame = reader.read()
            if not read:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        reader.release()
        return frames

    def _kept(
        self, schedule: BeatSchedule, resolution: Resolution, frames_per_second: int
    ) -> Optional[List[Frame]]:
        """
        The frames kept for those beats, or None where none were kept.
        """
        if self.cache is None:
            return None
        key = self.key_for(schedule, resolution, frames_per_second)
        counted = self.cache.record(key)
        if counted is None:
            return None
        frames = [
            self.cache.picture(f"{key}_{index:05d}")
            for index in range(counted["frames"])
        ]
        if any(frame is None for frame in frames):
            return None
        return frames

    def _keep(
        self,
        frames: Sequence[Frame],
        schedule: BeatSchedule,
        resolution: Resolution,
        frames_per_second: int,
    ) -> None:
        """
        Keep the drawn frames under the key for those beats.
        """
        if self.cache is None:
            return
        key = self.key_for(schedule, resolution, frames_per_second)
        for index, frame in enumerate(frames):
            self.cache.keep_picture(f"{key}_{index:05d}", frame)
        self.cache.keep_record(key, {"frames": len(frames)})
