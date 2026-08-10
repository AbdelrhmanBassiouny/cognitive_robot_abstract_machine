"""
Per-shape sorting results recorded by :mod:`experiments.montessori.franka_montessori_demo`,
for offline analysis of a repeated (``--iterations``) run's success rate.

Kept in their own module, separate from the executable demo script: a class defined in
a script that is itself run via ``python -m ...`` is loaded twice, once as
``__main__`` and once under its real dotted path (e.g. by the generated
``experiments.orm.ormatic_interface``, which needs that real path to map the class),
leaving two distinct, unrelated class objects of the same name and breaking ORMatic's
DAO lookup for whichever one the running script actually instantiates. Mirrors
:mod:`experiments.montessori.insertion_experience`'s own reasoning for
``ShapeInsertionExperience``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from coraplex.plans.plan import Plan


class InsertionOutcome(StrEnum):
    """
    How a single shape's insertion attempts within
    :func:`~experiments.montessori.franka_montessori_demo._insert_all_shapes` ended,
    for tallying results across one or more
    :func:`~experiments.montessori.franka_montessori_demo._build_world_and_sort` runs.
    """

    FELL_THROUGH = "fell_through"
    DID_NOT_FALL_THROUGH = "did_not_fall_through"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"


@dataclass
class ShapeInsertionResult:
    """
    A single shape's insertion outcome from one
    :func:`~experiments.montessori.franka_montessori_demo._build_world_and_sort` run.
    """

    shape_key: str
    """
    This shape's name (see :meth:`~experiments.montessori.semantics.ShapeSortingBoard.hole_for`),
    with its trailing ``"_shape"`` suffix removed.
    """

    outcome: InsertionOutcome
    """
    How this shape's insertion attempts ended.
    """

    plan: Plan
    """
    The entire realized plan tree of the last insertion attempt made for this shape --
    every sub-action and motion :func:`~coraplex.plans.factories.execute_single` and
    :meth:`~coraplex.plans.plan_node.PlanNode.perform` expanded it into, not just its
    top-level :class:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction`
    node -- that produced :attr:`outcome`, whether or not it raised (see
    :func:`~experiments.montessori.franka_montessori_demo._insert_shape_or_none`).
    """


@dataclass
class SortingIterationResult:
    """
    Every attempted shape's :class:`ShapeInsertionResult` from one full
    :func:`~experiments.montessori.franka_montessori_demo._build_world_and_sort` run.
    """

    iteration: int
    """
    This run's 1-based index among the iterations
    :func:`~experiments.montessori.franka_montessori_demo.main` was asked to repeat.
    """

    shape_results: list[ShapeInsertionResult] = field(default_factory=list)
    """
    Every attempted shape's own outcome from this iteration.
    """
