"""
The slides of plain text: a table of results, and a card of a heading and a line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from semantic_digital_twin.spatial_types.spatial_types import Point2
from typing_extensions import Tuple

from experiments.video.frame import Frame, Resolution
from experiments.video.lettering import Face
from experiments.video.theme import VideoTheme
from experiments.video.timeline import HeldScene
from experiments.video.typesetting import Anchor, TextSize

# %% the results table


@dataclass(frozen=True)
class ResultRow:
    """
    One row of a results table: what was measured and its value with its unit.
    """

    measure: str
    """
    What was measured.
    """

    value: str
    """
    Its value, written with its unit.
    """


@dataclass
class ResultsTable(HeldScene):
    """
    Results as a table: a plain title over it, one hairline over each row, the values
    bold and right-aligned with their units, centred on the page with nothing else on
    it.
    """

    title: str
    """
    What the table is of, over it.
    """

    rows: Tuple[ResultRow, ...]
    """
    The rows.
    """

    held_for: timedelta = field(default=timedelta(seconds=4), kw_only=True)
    """
    How long the table is held.
    """

    resolution: Resolution = field(default_factory=Resolution.standard)
    """
    The size of the slide.
    """

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
    """
    The colours and fonts it is drawn in.
    """

    table_width: int = 900
    """
    Pixels the table is wide.
    """

    row_pitch: int = 64
    """
    Pixels from one row of the table to the next.
    """

    title_above_table: int = 50
    """
    Pixels the table's title stands above its first rule.
    """

    cell_inset: int = 8
    """
    Pixels between a cell's text and the table's edge.
    """

    @property
    def dissolves_in(self) -> bool:
        """
        Whether the scene before dissolves into this one: it does not, since that scene
        writes text where this one does, so this one cuts in.
        """
        return False

    def picture_at(self, moment: timedelta) -> Frame:
        """
        :param moment: A moment of the slide, from its start.
        :return: The table, the same at every moment.
        """
        frame = self.theme.page_of(self.resolution)
        left = self.resolution.width / 2 - self.table_width / 2
        right = left + self.table_width
        height = self.row_pitch * len(self.rows)
        top = (self.resolution.stage_height - height) / 2 + self.title_above_table / 2
        frame = self.theme.typesetting(TextSize.BODY, Face.BOLD).written(
            frame,
            self.title,
            Point2(self.resolution.width / 2, top - self.title_above_table),
            Anchor.CENTRE_MIDDLE,
        )
        measure = self.theme.typesetting(TextSize.BODY)
        value = self.theme.typesetting(TextSize.BODY, Face.BOLD)
        for number, row in enumerate(self.rows):
            y = top + number * self.row_pitch
            frame = frame.lined(
                Point2(left, y), Point2(right, y), self.theme.hairline, thickness=2
            )
            middle = y + self.row_pitch / 2
            frame = measure.written(
                frame,
                row.measure,
                Point2(left + self.cell_inset, middle),
                Anchor.LEFT_MIDDLE,
            )
            frame = value.written(
                frame,
                row.value,
                Point2(right - self.cell_inset, middle),
                Anchor.RIGHT_MIDDLE,
            )
        return frame.lined(
            Point2(left, top + height),
            Point2(right, top + height),
            self.theme.hairline,
            thickness=2,
        )


# %% a card of text


@dataclass
class TextCard(HeldScene):
    """
    A heading in bold with one line under it, centred on the page: a title card, or an
    end card with a link.
    """

    heading: str
    """
    What is written in bold.
    """

    line: str
    """
    What is written under it.
    """

    held_for: timedelta = field(default=timedelta(seconds=5), kw_only=True)
    """
    How long the card is held.
    """

    resolution: Resolution = field(default_factory=Resolution.standard)
    """
    The size of the slide.
    """

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
    """
    The colours and fonts it is drawn in.
    """

    line_gap: int = 54
    """
    Pixels from the heading's middle to the line's middle.
    """

    @property
    def dissolves_in(self) -> bool:
        """
        Whether the scene before dissolves into this one: it does not, since that scene
        writes text where this one does, so this one cuts in.
        """
        return False

    def picture_at(self, moment: timedelta) -> Frame:
        """
        :param moment: A moment of the slide, from its start.
        :return: The card, the same at every moment.
        """
        frame = self.theme.page_of(self.resolution)
        centre = self.resolution.width / 2
        middle = self.resolution.stage_height / 2
        frame = self.theme.typesetting(TextSize.BODY, Face.BOLD).written(
            frame,
            self.heading,
            Point2(centre, middle - self.line_gap / 2),
            Anchor.CENTRE_MIDDLE,
        )
        return self.theme.typesetting(TextSize.BODY).written(
            frame,
            self.line,
            Point2(centre, middle + self.line_gap / 2),
            Anchor.CENTRE_MIDDLE,
        )
