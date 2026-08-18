"""
What a running Montessori sort offers the viewer's entity query language console.

Three things are on offer. About the sort in progress, the questions the buttons exist
to answer are: was this shape inserted, where was it being inserted, and why could it
not be. About the runs that already finished, they are how often each shape was sorted
and how its attempts ended -- read back out of the results database rather than out of
this process. About what the demo could do, they are the insertions it can carry out on
the shapes it is sorting, built rather than looked up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.factories import sum as eql_sum
from cramera.knowledge.database_evaluation import DatabaseEvaluation
from cramera.knowledge.generative_evaluation import GenerativeEvaluation
from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.knowledge.queryable_knowledge import QueryableKnowledge, QueryScope
from cramera.live.query import LiveQuerySource
from typing_extensions import List, Optional

from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.montessori.sorting_progress import (
    InsertionAttemptRecord,
    PlanStep,
    SegmindEventRecord,
    ShapeUnderTest,
    SortingProgress,
)
from experiments.montessori.sorting_results import (
    InsertionOutcome,
    ShapeInsertionResult,
)

CURRENT_STATE_PRESETS: List[Preset] = [
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
The ready-made questions about the sort in progress.
"""

GROUPED_BY_SHAPE_KEY = "shape_key = shape_result.shape_key\n"
"""
Preamble naming the column recorded questions group and order their answers by.

``shape_key`` identifies a hole instance rather than a category: ``circular_hole_1`` and
``circular_hole_2`` are both cylinders, and are counted apart.
"""

EPISODIC_MEMORY_PRESETS: List[Preset] = [
    Preset(
        "success rate per shape",
        GROUPED_BY_SHAPE_KEY + "set_of(\n"
        "    shape_key,\n"
        "    sum(case_when("
        "shape_result.outcome == InsertionOutcome.FELL_THROUGH, 1, 0)),\n"
        "    count(shape_result),\n"
        ").grouped_by(shape_key).ordered_by(shape_key)",
        scope=QueryScope.EPISODIC_MEMORY,
    ),
    Preset(
        "how did each shape's runs end?",
        GROUPED_BY_SHAPE_KEY + "outcome = shape_result.outcome\n"
        "set_of(shape_key, outcome, count(shape_result))"
        ".grouped_by(shape_key, outcome).ordered_by(shape_key)",
        scope=QueryScope.EPISODIC_MEMORY,
    ),
    Preset(
        "every recorded run",
        "set_of(shape_result.shape_key, shape_result.outcome)",
        scope=QueryScope.EPISODIC_MEMORY,
    ),
]
"""
The ready-made questions about the runs that already finished.

Deliberately without a "most likely failure" column: expressing it needs ``mode``, which
krrood's EQL-to-SQL translation does not cover, and there is no portable SQL aggregate
behind it. The per-outcome breakdown answers the same thing by reading a column instead.
"""

EVERY_INSERTION = (
    "an(InsertMontessoriShapeAction)(\n"
    "    montessori_shape=montessori_shape, board=board, arm=...\n"
    ")"
)
"""
The pattern the questions about what could be done are asked around.

Every field but the arm is filled in from the sort itself, so what is left open is which
arm carries the insertion out.
"""

ARM_OF_EVERY_INSERTION = (
    "insertions = generate(%s)\n"
    "set_of(insertions.montessori_shape, insertions.arm)" % EVERY_INSERTION
)
"""
The arm each built insertion was filled in with, beside the shape it inserts.
"""

SINGLE_ARM_INSERTIONS = (
    "insertion = %s\n"
    "insertion.where(insertion.variable.arm != Arms.BOTH)" % EVERY_INSERTION
)
"""
The insertions one arm can carry out on its own.
"""

UNDERSPECIFIED_PRESETS: List[Preset] = [
    Preset(
        "how could each shape be inserted?",
        EVERY_INSERTION,
        scope=QueryScope.UNDERSPECIFIED,
    ),
    Preset(
        "which arm could insert which shape?",
        ARM_OF_EVERY_INSERTION,
        scope=QueryScope.UNDERSPECIFIED,
    ),
    Preset(
        "which insertions need one arm only?",
        SINGLE_ARM_INSERTIONS,
        scope=QueryScope.UNDERSPECIFIED,
    ),
]
"""
The ready-made questions about what the demo could do.

Answered by building an insertion per value the arm could take rather than by looking
one up, so they are about the shapes being sorted right now: a recording has none.
"""

MONTESSORI_PRESETS: List[Preset] = CURRENT_STATE_PRESETS + EPISODIC_MEMORY_PRESETS
"""
The ready-made questions the recorded Franka Montessori bundle declares in its
``presets.json``; a test keeps the two in step.

The live demo offers these plus the questions about what it could do (see
:meth:`MontessoriLiveQuerySource.presets`), which range over the shapes it is sorting
and so have nothing to be asked of in a recording.
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

    results_database: Optional[ResultsDatabase] = None
    """
    Where finished runs were recorded, or None when nothing is asking about them.
    """

    board: Optional[ShapeSortingBoard] = None
    """
    The board being sorted into, or None before a scene has been built.
    """

    def title(self) -> str:
        """
        What the panel names this source.
        """
        return "Montessori sorting"

    def knowledge(self) -> List[QueryableKnowledge]:
        """
        The sort in progress, what it could do once there is a board to do it on, and
        the runs that already finished when there are any.
        """
        offered = [self._current_state()]
        if self.board is not None:
            offered.append(self._underspecified())
        if self.results_database is not None:
            offered.append(self._episodic_memory())
        return offered

    def _current_state(self) -> QueryableKnowledge:
        """
        The four things a question about the sort in progress is about.

        Read fresh on every call, so an answer describes the sort as it stands now.
        """
        return QueryableKnowledge(
            scope=QueryScope.CURRENT_STATE,
            domains=[
                QueryDomain("shape", ShapeUnderTest, self.progress.shapes),
                QueryDomain("attempt", InsertionAttemptRecord, self.progress.attempts),
                QueryDomain("plan_step", PlanStep, self.progress.plan_steps),
                QueryDomain("event", SegmindEventRecord, self.progress.events),
            ],
        )

    def _underspecified(self) -> QueryableKnowledge:
        """
        The insertions the demo could carry out on the shapes it is sorting.

        The shapes and the board are what an insertion is built from, so both are ranged
        over; which arm carries it out is what a question leaves open.
        """
        return QueryableKnowledge(
            scope=QueryScope.UNDERSPECIFIED,
            domains=[
                QueryDomain(
                    "montessori_shape", MontessoriShape, self.progress.tracked_shapes
                ),
                QueryDomain("board", ShapeSortingBoard, [self.board]),
            ],
            evaluation=GenerativeEvaluation(),
        )

    def _episodic_memory(self) -> QueryableKnowledge:
        """
        The per-shape outcomes every finished run recorded.

        ``sum`` and the outcome vocabulary are put in reach by hand: the first shadows a
        builtin and so is left out of the EQL factory namespace, and the second is what
        the recorded outcomes are written in.
        """
        return QueryableKnowledge(
            scope=QueryScope.EPISODIC_MEMORY,
            domains=[QueryDomain("shape_result", ShapeInsertionResult)],
            evaluation=DatabaseEvaluation(
                open_session=self.results_database.open_session
            ),
            extra_names={"sum": eql_sum, "InsertionOutcome": InsertionOutcome},
        )

    def presets(self) -> List[Preset]:
        """
        The ready-made questions the panel offers as buttons, in the groups they belong
        to.
        """
        offered = list(CURRENT_STATE_PRESETS)
        if self.board is not None:
            offered += UNDERSPECIFIED_PRESETS
        if self.results_database is not None:
            offered += EPISODIC_MEMORY_PRESETS
        return offered
