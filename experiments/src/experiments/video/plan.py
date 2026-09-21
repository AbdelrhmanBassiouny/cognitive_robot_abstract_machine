"""
The plan written out as code, as stated and as resolved: the same lines the paper's
figure carries, laid out in two columns so that they read at the video's own size.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Sequence, Tuple

from experiments.video.figure import RunReadings, Slot
from experiments.video.statements import OPEN_FIELD


@dataclass(frozen=True)
class Emphasis:
    """
    A stretch of the plan's lines that is emphasised: whole lines, or one span of one
    line.
    """

    first_row: int
    last_row: int
    span: Tuple[int, int] | None = None
    """
    The columns emphasised on the one row, or None for the whole rows.
    """

    def covers(self, row: int, column: int) -> bool:
        if not self.first_row <= row <= self.last_row:
            return False
        return self.span is None or self.span[0] <= column < self.span[1]


@dataclass(frozen=True)
class PlanText:
    """
    The plan's lines, and what of them is emphasised.
    """

    lines: Tuple[str, ...]
    emphasised: Tuple[Emphasis, ...] = ()
    second_column_from: int = 0
    """
    The row the second column starts at: where the insertion action starts, so that
    neither action is cut in two.
    """

    def columns(self) -> Tuple[Tuple[int, int], ...]:
        """
        The rows each column holds: the first and the one after its last.
        """
        return ((0, self.second_column_from), (self.second_column_from, len(self.lines)))


STATED_LINES = (
    "sequential([",
    "  a(PickUpAction)(",
    "    arm=LEFT,",
    "    object_designator=",
    "      a(DetectedMontessoriShape)(",
    "        category=CUBE)",
    "      .where(",
    "        Colored(shape, CYAN),",
    "        SupportedBy(shape, lid)),",
    "    grasp_description=",
    "      a(GraspDescription)(",
    "        approach_direction=...,",
    "        vertical_alignment=TOP,",
    "        end_effector=LEFT_HAND)",
    "  ),",
    "  an(InsertionAction)(",
    "    arm=LEFT,",
    "    object_designator=shape,",
    "    grasp_description=grasp,",
    "    target=",
    "      a(ShapeSortingHole)(",
    "        shape_category=...)",
    "      .from_(board.apertures)",
    "  )",
    "])",
)
"""
The plan as stated, line by line, as the paper's figure writes it.
"""


def _open_field_span(line: str) -> Tuple[int, int]:
    first = line.index(OPEN_FIELD)
    return first, first + len(OPEN_FIELD)


def stated_plan() -> PlanText:
    """
    The plan as stated, its three open parts emphasised: the description of the cube,
    the approach direction and the hole's shape.
    """
    lines = STATED_LINES
    return PlanText(
        lines,
        emphasised=(
            Emphasis(4, 8),
            Emphasis(11, 11, _open_field_span(lines[11])),
            Emphasis(21, 21, _open_field_span(lines[21])),
        ),
        second_column_from=lines.index("  an(InsertionAction)("),
    )


def resolved_plan(readings: RunReadings) -> PlanText:
    """
    The plan resolved with what the run read.

    :param readings: What the run read, as the figure shows it.
    """
    found = readings.filled_lines[Slot.PERCEPTION]
    found_name = found[0].split()[0]
    grasp = readings.resolved_lines[Slot.PROBABILISTIC]
    hole = readings.resolved_lines[Slot.RULES]
    holds = readings.support_verdict.endswith("True")
    lines: Sequence[str] = (
        "sequential([",
        "  PickUpAction(",
        "    arm=LEFT,",
        "    object_designator=",
        f"      {found[0]}",
        f"      {found[1]}",
        f"      SupportedBy({found_name}, lid) {'✓' if holds else '✗'}",
        "    grasp_description=",
        *(f"      {line}" for line in grasp),
        "  ),",
        "  InsertionAction(",
        "    arm=LEFT,",
        f"    object_designator={found_name},",
        f"    grasp_description={grasp[0].split(' = ')[0]},",
        "    target=",
        *(f"      {line}" for line in hole),
        "  )",
        "])",
    )
    return PlanText(tuple(lines), second_column_from=lines.index("  InsertionAction("))
