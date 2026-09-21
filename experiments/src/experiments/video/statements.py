"""
The plan's sub-queries, one per backend: each as the plan states it, with what it
leaves open, and as it reads once its backend has answered.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Dict, Optional, Tuple

from experiments.video.figure import RunReadings, Slot

OPEN_FIELD = "..."
"""
How a field left for the answering backend to fill is written.
"""


@dataclass(frozen=True)
class SlotStatement:
    """
    One sub-query of the plan: its lines as stated, which of them the answer lands on,
    and its lines once answered.
    """

    slot: Slot
    """
    The slot the statement leaves open.
    """

    lines: Tuple[str, ...]
    """
    The statement as the plan states it, line by line.
    """

    answered: Tuple[str, ...]
    """
    The statement once its backend has answered, line by line.
    """

    answer: str
    """
    What the backend answered, as the chip reads it.
    """

    open_row: int = 0
    """
    Which line the answer lands on: the one written with ``...``, or the first line of a
    description left open as a whole.
    """

    @property
    def open_span(self) -> Optional[Tuple[int, int]]:
        """
        Where on its line the open field is written, or None where the whole
        description is what is open.
        """
        line = self.lines[self.open_row]
        if OPEN_FIELD not in line:
            return None
        first = line.index(OPEN_FIELD)
        return first, first + len(OPEN_FIELD)


def statements_of(readings: RunReadings) -> Dict[Slot, SlotStatement]:
    """
    The plan's four sub-queries, answered with what the run read.

    :param readings: What the run read, as the figure shows it.
    """
    found = readings.filled_lines[Slot.PERCEPTION]
    found_name = found[0].split()[0]
    approach = readings.filled_values[Slot.PROBABILISTIC]
    hole = readings.filled_values[Slot.RULES]
    holds = readings.support_verdict.endswith("True")
    return {
        Slot.PERCEPTION: SlotStatement(
            Slot.PERCEPTION,
            (
                "a(DetectedMontessoriShape)(",
                "  category=CUBE)",
                ".where(",
                "  Colored(shape, CYAN),",
                "  SupportedBy(shape, lid))",
            ),
            tuple(found),
            found_name,
        ),
        Slot.SIMULATION: SlotStatement(
            Slot.SIMULATION,
            (f"SupportedBy({found_name}, lid)",),
            (f"SupportedBy({found_name}, lid)  {'✓' if holds else '✗'}",),
            str(holds),
        ),
        Slot.PROBABILISTIC: SlotStatement(
            Slot.PROBABILISTIC,
            (
                "a(GraspDescription)(",
                "  approach_direction=...,",
                "  vertical_alignment=TOP,",
                "  end_effector=LEFT_HAND)",
            ),
            (
                "a(GraspDescription)(",
                f"  approach_direction={approach},",
                "  vertical_alignment=TOP,",
                "  end_effector=LEFT_HAND)",
            ),
            approach,
            open_row=1,
        ),
        Slot.RULES: SlotStatement(
            Slot.RULES,
            (
                "a(ShapeSortingHole)(",
                "  shape_category=...)",
                ".from_(board.apertures)",
            ),
            (
                "a(ShapeSortingHole)(",
                f"  shape_category={hole})",
                ".from_(board.apertures)",
            ),
            hole,
            open_row=1,
        ),
    }
