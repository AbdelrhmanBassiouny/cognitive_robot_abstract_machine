"""
Experience data recorded from running the Montessori demo's insertion action, for
offline analysis of its success rate (see
:mod:`experiments.montessori.generate_insertion_experience`).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from experiments.montessori.semantics import MontessoriShapeCategory


@dataclass
class ShapeInsertionExperience:
    """
    Outcome of a single attempt (see
    :func:`~experiments.montessori.montessori_demo._insert_shape`) to pick up and
    insert a loose Montessori shape into its matching hole; one row of experience data.
    """

    run_index: int
    """
    Which demo run (0-based) this attempt belongs to; see
    :func:`~experiments.montessori.generate_insertion_experience.generate_insertion_experience`.
    """

    shape_category: MontessoriShapeCategory
    """
    Category of the shape that was inserted.
    """

    attempt_number: int
    """
    Which attempt (1-based) this was for :attr:`shape_category` within its run; see
    :data:`~experiments.montessori.montessori_demo.MAX_INSERTION_ATTEMPTS`.
    """

    target_horizontal_offset_x: float
    """
    X-component (m) of the horizontal offset applied to this attempt's drop point; see
    :attr:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction.target_horizontal_offset`.
    """

    target_horizontal_offset_y: float
    """
    Y-component (m) of the horizontal offset applied to this attempt's drop point.
    """

    fell_through_hole: bool
    """
    Whether the shape actually fell through its hole after settling; see
    :meth:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction.has_fallen_through_hole`.
    """

    recorded_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    """
    When this attempt was recorded.
    """
