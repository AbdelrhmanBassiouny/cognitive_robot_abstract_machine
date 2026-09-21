"""
The plan on screen, and each backend at work on the sub-query it answers.

The plan is shown twice, written out: as stated, with what it leaves open emphasised,
and resolved. Between the two, every backend works in one fixed layout: the sub-query
in a box on the left, the backend's panel on the right, and the answer as a chip that
moves from the panel into the open slot of the sub-query.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from typing_extensions import Optional, Sequence, Tuple

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    BODY_SIZE,
    DIM,
    LABEL_SIZE,
    MARGIN,
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Rgb,
    Typesetting,
    dimmed,
    filled,
    fitted,
    framed,
)
from experiments.video.plan import PlanText
from experiments.video.statements import SlotStatement
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

HEADER_CLEAR = 96
"""
Pixels from the top kept clear for the chapter's pill.
"""

FADE = 0.25
"""
Seconds a change takes: the emphasis coming up, the chip and the answer giving way.
"""

MOVE = 0.3
"""
Seconds the chip takes to move into the open slot.
"""

# %% the plan, as stated and resolved


PLAN_CODE_SIZE = 22
"""
The letters of the plan.
"""

PLAN_PITCH = 30
"""
Pixels from one line of the plan to the next.
"""

PLAN_COLUMN_GAP = 80
"""
Pixels between the plan's two columns.
"""


@dataclass
class PlanOverview(Scene):
    """
    The plan -- as stated, or resolved -- written out in two columns, with parts of it
    emphasised from a moment on by dimming the rest, and a footnote under it where one
    is due.
    """

    plan: PlanText
    """
    The plan's lines, and what of them is emphasised.
    """

    held_for: float = 4.0
    """
    How long the plan is shown, in seconds.
    """

    emphasis_from: float = 0.0
    """
    Seconds into the scene the emphasis comes up.
    """

    footnote: str = ""
    """
    What is written small under the plan, if anything.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the canvas.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    @cached_property
    def column_width(self) -> float:
        code = CodeTypesetting(size=PLAN_CODE_SIZE)
        return max(code.width_of(line) for line in self.plan.lines)

    def line_at(self, row: int) -> Tuple[float, float]:
        """
        The left middle of one row of the plan, in its column.
        """
        columns = self.plan.columns()
        number = next(index for index, (first, after) in enumerate(columns) if first <= row < after)
        rows = max(after - first for first, after in columns)
        width = len(columns) * self.column_width + (len(columns) - 1) * PLAN_COLUMN_GAP
        left = self.resolution.width / 2 - width / 2 + number * (self.column_width + PLAN_COLUMN_GAP)
        top = (HEADER_CLEAR + self.resolution.stage_height - (52 if self.footnote else 16)) / 2 - rows * PLAN_PITCH / 2
        return left, top + (row - columns[number][0] + 0.5) * PLAN_PITCH

    @cached_property
    def picture(self) -> Frame:
        return self._written(emphasised=False)

    @cached_property
    def emphasised_picture(self) -> Frame:
        return self._written(emphasised=True)

    def _written(self, emphasised: bool) -> Frame:
        """
        The plan on the canvas; with everything but the emphasised parts dimmed, when
        asked.
        """
        code = CodeTypesetting(size=PLAN_CODE_SIZE)
        frame = self.resolution.blank(255)
        for row, line in enumerate(self.plan.lines):
            frame = code.written(frame, line, self.line_at(row))
        if not emphasised:
            return frame
        faded = dimmed(frame, DIM)
        # the emphasised columns of each row keep their full ink
        for row, line in enumerate(self.plan.lines):
            at = self.line_at(row)
            top, bottom = int(at[1] - PLAN_PITCH / 2), int(at[1] + PLAN_PITCH / 2)
            for column in range(len(line)):
                if any(part.covers(row, column) for part in self.plan.emphasised):
                    left = int(at[0] + code.width_of(line[:column]))
                    right = int(at[0] + code.width_of(line[: column + 1])) + 1
                    faded[top:bottom, left:right] = frame[top:bottom, left:right]
        return faded

    def picture_at(self, seconds: float) -> Frame:
        picture = self.picture
        weight = eased((seconds - self.emphasis_from) / FADE) if self.plan.emphasised else 0.0
        if weight > 0.0:
            picture = blended(picture, self.emphasised_picture, weight)
        if self.footnote:
            picture = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb).written(
                picture, self.footnote, (self.resolution.width / 2, self.resolution.stage_height - 26), Anchor.CENTRE_MIDDLE
            )
        return picture


# %% a backend at work


QUERY_ZONE_SHARE = 0.3
"""
The share of the frame's width the sub-query's zone takes, on the left.
"""

ZONE_GAP = 16
"""
Pixels between the two zones.
"""

CODE_SIZE = LABEL_SIZE
"""
The letters of the sub-query.
"""

CODE_PITCH = 28
"""
Pixels from one line of the sub-query to the next.
"""

QUERY_ROWS = 5
"""
Rows the sub-query's box holds: the longest sub-query's, so every box is one size.
"""

TITLE_BAR = 44
"""
Pixels the panel's title bar is tall.
"""

CHIP_HEIGHT = 40
"""
Pixels the answer chip is tall.
"""

CHIP_PADDING = 16
"""
Pixels between the chip's edge and its text.
"""

PANEL_VISUAL = Resolution(width=856, height=400)
"""
The size a backend's visual is drawn at: its room on the panel, so that what it writes
is written at the video's own sizes.
"""


@dataclass
class BackendAtWork(Scene):
    """
    One backend answering its sub-query: the sub-query held in its box on the left, the
    backend's panel on the right with its title bar, its one visual and, once the
    backend has answered, its answer chip, which moves into the open slot of the
    sub-query; the sub-query then reads answered.
    """

    statement: SlotStatement
    """
    The sub-query, as stated and as answered.
    """

    title: str
    """
    What the backend is called, on the panel's title bar.
    """

    hue: Rgb
    """
    The backend's colour: the title bar's.
    """

    work: Scene
    """
    The panel's visual, drawn at :data:`PANEL_VISUAL`.
    """

    answered_at: float
    """
    Seconds into the scene the chip comes up.
    """

    held_for: float = 10.0
    """
    How long the scene lasts, in seconds.
    """

    chip_for: float = 0.5
    """
    Seconds the chip stands on the panel before it moves.
    """

    landed_for: float = 0.3
    """
    Seconds the chip stands in the slot before the sub-query reads answered.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the canvas.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    @property
    def dissolves_in(self) -> bool:
        # the box holds different text from one backend to the next: a cut, not a fade
        return False

    # %% where things lie

    @property
    def query_box(self) -> Area:
        width = self.resolution.width * QUERY_ZONE_SHARE - MARGIN - ZONE_GAP / 2
        return Area(MARGIN, HEADER_CLEAR, width, QUERY_ROWS * CODE_PITCH + 2 * CHIP_PADDING)

    @property
    def panel(self) -> Area:
        left = self.resolution.width * QUERY_ZONE_SHARE + ZONE_GAP / 2
        return Area(left, HEADER_CLEAR, self.resolution.width - MARGIN - left, self.resolution.stage_height - MARGIN / 2 - HEADER_CLEAR)

    @property
    def title_bar(self) -> Area:
        panel = self.panel
        return Area(panel.x, panel.y, panel.width, TITLE_BAR)

    @property
    def visual(self) -> Area:
        panel = self.panel
        return Area(panel.x, panel.y + TITLE_BAR + 12, panel.width, PANEL_VISUAL.height)

    @property
    def chip_text(self) -> str:
        return f"→ {self.statement.answer}"

    @property
    def chip_width(self) -> float:
        return Typesetting(size=BODY_SIZE, face=Face.BOLD).width_of(self.chip_text) + 2 * CHIP_PADDING

    @property
    def chip_on_panel(self) -> Area:
        panel = self.panel
        return Area(panel.right - self.chip_width, panel.bottom - CHIP_HEIGHT, self.chip_width, CHIP_HEIGHT)

    def line_at(self, row: int) -> Tuple[float, float]:
        """
        The left middle of one row of the sub-query.
        """
        box = self.query_box
        return box.x + CHIP_PADDING, box.y + CHIP_PADDING + CODE_PITCH * (row + 0.5)

    @property
    def chip_in_slot(self) -> Area:
        """
        Where the chip lands: over the open field of its row, or at the start of the
        row where the whole description is what is open.
        """
        statement = self.statement
        left, middle = self.line_at(statement.open_row)
        if statement.open_span is not None:
            left += CodeTypesetting(size=CODE_SIZE).width_of(statement.lines[statement.open_row][: statement.open_span[0]])
        return Area(left - 6, middle - CHIP_HEIGHT / 2, self.chip_width, CHIP_HEIGHT)

    # %% when things happen

    @property
    def moves_at(self) -> float:
        return self.answered_at + self.chip_for

    @property
    def lands_at(self) -> float:
        return self.moves_at + MOVE

    @property
    def answered_read_at(self) -> float:
        return self.lands_at + self.landed_for

    # %% drawing

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        frame = self._query_drawn(frame, seconds)
        frame = self._panel_drawn(frame, seconds)
        return self._chip_drawn(frame, seconds)

    def _query_drawn(self, frame: Frame, seconds: float) -> Frame:
        """
        The sub-query in its box, as stated, giving way to it as answered once the chip
        has landed.
        """
        box = self.query_box
        frame = filled(frame, box, Ink.BUBBLE.rgb)
        frame = framed(frame, box, Ink.HAIRLINE.rgb, thickness=2)
        stated = self._lines_written(frame, self.statement.lines, marked=seconds < self.lands_at)
        read = eased((seconds - self.answered_read_at) / FADE)
        if read <= 0.0:
            return stated
        return blended(stated, self._lines_written(frame, self.statement.answered, marked=False), read)

    def _lines_written(self, frame: Frame, lines: Sequence[str], marked: bool) -> Frame:
        code = CodeTypesetting(size=CODE_SIZE)
        statement = self.statement
        for row, line in enumerate(lines):
            spans = (statement.open_span,) if marked and row == statement.open_row and statement.open_span else ()
            frame = code.written(frame, line, self.line_at(row), marked=spans)
        return frame

    def _panel_drawn(self, frame: Frame, seconds: float) -> Frame:
        """
        The title bar in the backend's colour, and the visual under it.
        """
        bar = self.title_bar
        frame = filled(frame, bar, self.hue)
        frame = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, self.title, (bar.x + CHIP_PADDING, bar.centre[1]), Anchor.LEFT_MIDDLE
        )
        played = min(max(seconds, 0.0), self.work.duration - 1e-6)
        return fitted(frame, self.work.frame_at(played), self.visual)

    def _chip_drawn(self, frame: Frame, seconds: float) -> Frame:
        """
        The answer chip: up on the panel from the answer, moving into the slot, and
        giving way once the sub-query reads answered.
        """
        up = eased((seconds - self.answered_at) / FADE)
        gone = eased((seconds - self.answered_read_at) / FADE)
        weight = min(up, 1.0 - gone)
        if weight <= 0.0:
            return frame
        moved = eased((seconds - self.moves_at) / MOVE)
        chip = self.chip_on_panel.towards(self.chip_in_slot, moved)
        drawn = filled(frame, chip, Ink.ANSWER.rgb)
        drawn = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            drawn, self.chip_text, chip.centre, Anchor.CENTRE_MIDDLE
        )
        return blended(frame, drawn, weight)


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

    @property
    def dissolves_in(self) -> bool:
        return self.work.dissolves_in

    def picture_at(self, seconds: float) -> Frame:
        return fitted(
            self.resolution.blank(255),
            self.work.frame_at(seconds),
            Area.whole(self.resolution),
        )
