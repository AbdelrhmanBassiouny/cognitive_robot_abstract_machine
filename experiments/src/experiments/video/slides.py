"""
The slides of plain text: a table of results, and a card of a heading and a line.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Tuple

from experiments.video.canvas import (
    BODY_SIZE,
    NEUTRAL_THEME,
    VIDEO_RESOLUTION,
    Anchor,
    Theme,
    lined,
)
from experiments.video.lettering import Face
from experiments.video.timeline import Frame, HeldScene, Resolution

TABLE_WIDTH = 900
"""
Pixels the results table is wide.
"""

ROW_PITCH = 64
"""
Pixels from one row of the table to the next.
"""

TITLE_ABOVE_TABLE = 50
"""
Pixels the table's title stands above its first rule.
"""

CELL_INSET = 8
"""
Pixels between a cell's text and the table's edge.
"""

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

    held_for: float = field(default=4.0, kw_only=True)

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    theme: Theme = NEUTRAL_THEME
    """
    The colours and fonts it is drawn in.
    """

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    def picture_at(self, seconds: float) -> Frame:
        frame = self.theme.page_of(self.resolution)
        left = self.resolution.width / 2 - TABLE_WIDTH / 2
        right = left + TABLE_WIDTH
        height = ROW_PITCH * len(self.rows)
        top = (self.resolution.stage_height - height) / 2 + TITLE_ABOVE_TABLE / 2
        frame = self.theme.typesetting(BODY_SIZE, Face.BOLD).written(
            frame,
            self.title,
            (self.resolution.width / 2, top - TITLE_ABOVE_TABLE),
            Anchor.CENTRE_MIDDLE,
        )
        measure = self.theme.typesetting(BODY_SIZE)
        value = self.theme.typesetting(BODY_SIZE, Face.BOLD)
        for number, row in enumerate(self.rows):
            y = top + number * ROW_PITCH
            frame = lined(
                frame, (left, y), (right, y), self.theme.hairline, thickness=2
            )
            frame = measure.written(
                frame,
                row.measure,
                (left + CELL_INSET, y + ROW_PITCH / 2),
                Anchor.LEFT_MIDDLE,
            )
            frame = value.written(
                frame,
                row.value,
                (right - CELL_INSET, y + ROW_PITCH / 2),
                Anchor.RIGHT_MIDDLE,
            )
        return lined(
            frame,
            (left, top + height),
            (right, top + height),
            self.theme.hairline,
            thickness=2,
        )


# %% a card of text


LINE_GAP = 54
"""
Pixels from the heading's middle to the line's middle.
"""


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

    held_for: float = field(default=5.0, kw_only=True)

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    theme: Theme = NEUTRAL_THEME
    """
    The colours and fonts it is drawn in.
    """

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    def picture_at(self, seconds: float) -> Frame:
        frame = self.theme.page_of(self.resolution)
        centre = self.resolution.width / 2
        middle = self.resolution.stage_height / 2
        frame = self.theme.typesetting(BODY_SIZE, Face.BOLD).written(
            frame, self.heading, (centre, middle - LINE_GAP / 2), Anchor.CENTRE_MIDDLE
        )
        return self.theme.typesetting(BODY_SIZE).written(
            frame, self.line, (centre, middle + LINE_GAP / 2), Anchor.CENTRE_MIDDLE
        )
