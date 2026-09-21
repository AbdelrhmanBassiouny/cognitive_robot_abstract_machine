"""
The slides of plain text: the results table, and the end card with the link to the
code.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Sequence

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    BODY_SIZE,
    VIDEO_RESOLUTION,
    Anchor,
    Ink,
    Typesetting,
    lined,
)
from experiments.video.script import ResultRow, VideoScript
from experiments.video.timeline import Frame, Resolution, Scene

TABLE_WIDTH = 900
"""
Pixels the results table is wide.
"""

ROW_PITCH = 64
"""
Pixels from one row of the table to the next.
"""


@dataclass
class ResultsTable(Scene):
    """
    The results on the real robot as a table: a plain title over it, one hairline over
    each row, the values bold and right-aligned with their units, centred on a white
    frame with nothing else on it.
    """

    title: str
    """
    What the table is of, over it.
    """

    rows: Sequence[ResultRow]
    """
    The rows.
    """

    held_for: float = 4.0
    """
    How long the table is shown, in seconds.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        left = self.resolution.width / 2 - TABLE_WIDTH / 2
        right = left + TABLE_WIDTH
        height = ROW_PITCH * len(self.rows)
        top = (self.resolution.stage_height - height) / 2 + 30
        frame = Typesetting(size=BODY_SIZE, face=Face.BOLD).written(frame, self.title, (self.resolution.width / 2, top - 50), Anchor.CENTRE_MIDDLE)
        measure = Typesetting(size=BODY_SIZE)
        value = Typesetting(size=BODY_SIZE, face=Face.BOLD)
        for number, row in enumerate(self.rows):
            y = top + number * ROW_PITCH
            frame = lined(frame, (left, y), (right, y), Ink.HAIRLINE.rgb, thickness=2)
            frame = measure.written(frame, row.measure, (left + 8, y + ROW_PITCH / 2), Anchor.LEFT_MIDDLE)
            frame = value.written(frame, row.value, (right - 8, y + ROW_PITCH / 2), Anchor.RIGHT_MIDDLE)
        return lined(frame, (left, top + height), (right, top + height), Ink.HAIRLINE.rgb, thickness=2)


@dataclass
class EndCard(Scene):
    """
    The link to the code and the recorded episodes.
    """

    script: VideoScript
    """
    The words.
    """

    held_for: float = 5.0
    """
    How long the card is shown, in seconds.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        middle = self.resolution.stage_height / 2
        frame = Typesetting(size=BODY_SIZE, face=Face.BOLD).written(
            frame, self.script.code_label, (self.resolution.width / 2, middle - 30), Anchor.CENTRE_MIDDLE
        )
        return Typesetting(size=BODY_SIZE).written(
            frame, self.script.repository_link, (self.resolution.width / 2, middle + 24), Anchor.CENTRE_MIDDLE
        )
