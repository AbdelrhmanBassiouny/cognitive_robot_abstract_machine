"""
What a running Montessori sort offers the viewer's entity query language console.

The questions the buttons exist to answer are: was this shape inserted, where was it
being inserted, and why could it not be. Everything here is in service of those three.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.live.query import LiveQuerySource
from typing_extensions import List

from experiments.montessori.sorting_progress import (
    InsertionAttemptRecord,
    PlanStep,
    SegmindEventRecord,
    ShapeUnderTest,
    SortingProgress,
)

MONTESSORI_PRESETS: List[Preset] = [
    # was this shape inserted?
    Preset(
        "which shapes are inserted?",
        "an(entity(shape).where(shape.is_inserted == True))",
    ),
    Preset(
        "which shapes are still out?",
        "an(entity(shape).where(shape.is_inserted == False))",
    ),
    Preset(
        "outcome per shape",
        "set_of(shape.name, shape.outcome, shape.attempt_count)",
    ),
    Preset(
        "how many of each outcome?",
        "set_of(shape.outcome, count(shape)).grouped_by(shape.outcome)",
    ),
    # where was it being inserted?
    Preset(
        "where is each shape aimed?",
        "set_of(shape.name, shape.target_hole, shape.target_pose)",
    ),
    Preset(
        "where did each attempt aim?",
        "set_of(attempt.name, attempt.target_hole, attempt.target_pose)",
    ),
    # why could it not be inserted?
    Preset(
        "why did each shape fail?",
        "set_of(shape.name, shape.failure_reason, shape.failure_detail)"
        ".where(shape.is_inserted == False)",
    ),
    Preset(
        "why did each attempt fail?",
        "set_of(attempt.name, attempt.failure_reason, attempt.failure_detail)"
        ".where(attempt.succeeded == False)",
    ),
    Preset(
        "never picked up",
        "an(entity(attempt).where(attempt.failure_reason == 'not_picked_up'))",
    ),
    Preset(
        "dropped before insertion",
        "an(entity(attempt)"
        ".where(attempt.failure_reason == 'dropped_before_insertion'))",
    ),
    Preset(
        "wedged in the hole",
        "an(entity(attempt).where(attempt.failure_reason == 'wedged_in_hole'))",
    ),
    Preset(
        "which plan steps failed?",
        "an(entity(plan_step).where(plan_step.status == 'FAILED'))",
    ),
    # what perception saw
    Preset(
        "what was detected, and when?",
        "set_of(event.shape_key, event.event_type, event.timestamp)"
        ".ordered_by(event.timestamp)",
    ),
    Preset(
        "insertions and the hole they went through",
        "set_of(event.shape_key, event.through_hole)"
        ".where(event.event_type == 'InsertionEvent')",
    ),
    # what the board looks like now
    Preset(
        "what is on the board?",
        "set_of(shape.name, shape.shape_category, shape.target_hole)",
    ),
    # how the plans ran
    Preset(
        "steps of every attempt",
        "set_of(plan_step.name, plan_step.status, plan_step.duration)"
        ".ordered_by(plan_step.started_at)",
    ),
    Preset(
        "slowest steps",
        "set_of(plan_step.name, plan_step.duration)"
        ".ordered_by(plan_step.duration, descending=True).limit(10)",
    ),
]
"""
The ready-made questions the viewer offers as buttons for this demo.

The recorded Franka Montessori bundle declares the same list in its ``presets.json``, so
the same questions are shown whether or not a demo is attached; a test keeps the two in
step.
"""


@dataclass
class MontessoriLiveQuerySource(LiveQuerySource):
    """
    A running Montessori sort, as something the viewer can ask questions of.
    """

    progress: SortingProgress = field(default_factory=SortingProgress)
    """
    The record the running sort keeps of itself.
    """

    def title(self) -> str:
        """
        What the panel names this source.
        """
        return "Montessori sorting"

    def domains(self) -> List[QueryDomain]:
        """
        The four things a question about this demo is about.

        Read fresh on every call, so an answer describes the sort as it stands now.
        """
        return [
            QueryDomain("shape", ShapeUnderTest, self.progress.shapes),
            QueryDomain("attempt", InsertionAttemptRecord, self.progress.attempts),
            QueryDomain("plan_step", PlanStep, self.progress.plan_steps),
            QueryDomain("event", SegmindEventRecord, self.progress.events),
        ]

    def presets(self) -> List[Preset]:
        """
        The ready-made questions the panel offers as buttons.
        """
        return list(MONTESSORI_PRESETS)
