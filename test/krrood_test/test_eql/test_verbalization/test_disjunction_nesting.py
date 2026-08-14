"""
A disjunction is a *level* of the condition outline, not one flat line: an ``OR`` heads
its own *"either"* block and each disjunct becomes a point under it, so ``OR(AND(A, B),
AND(C, D))`` reads as two points rather than one run-on sentence.

A conjunct inside a disjunct stays inline (one point per ``AND``), and a disjunction
that factors to a shared subject (*"its battery is greater than 50 or less than 10"*)
stays the single clause it already was.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.factories import a, and_, or_, variable
from krrood.entity_query_language.verbalization.pipeline import (
    VerbalizationPipeline,
    verbalize_expression,
)
from krrood.entity_query_language.verbalization.rendering.formatter import (
    PlainFormatter,
)
from krrood.entity_query_language.verbalization.rendering.renderer import (
    HierarchicalRenderer,
)


@dataclass
class Point:
    """
    A 2-D point — the free-space shape whose disjunction of boxes motivates the nesting.
    """

    x: float
    y: float


def _hierarchical(expression) -> str:
    """:return: *expression* rendered as a plain-text indented bullet list."""
    return VerbalizationPipeline(HierarchicalRenderer(PlainFormatter())).verbalize(
        expression
    )


def _boxes_condition(point: Point) -> object:
    """:return: *"either (x and y in box one) or (x and y in box two)"* over *point*."""
    return or_(
        and_(point.x > 1.0, point.x < 2.0, point.y > 3.0, point.y < 4.0),
        and_(point.x > 5.0, point.x < 6.0, point.y > 7.0, point.y < 8.0),
    )


def test_disjunction_prose_is_fronted_with_either():
    point = variable(Point, [])
    assert verbalize_expression(_boxes_condition(point)).startswith("either ")


def test_each_disjunct_is_its_own_point_under_the_either_header():
    match = a(Point)(x=..., y=...)
    match.where(_boxes_condition(match.variable))
    assert _hierarchical(match) == (
        "Generate a Point and predict its x and y values\n"
        "  where\n"
        "    - either\n"
        "      - its x is between 1.0 and 2.0, and its y is between 3.0 and 4.0\n"
        "      - its x is between 5.0 and 6.0, and its y is between 7.0 and 8.0"
    )


def test_shared_subject_disjunction_stays_one_clause():
    point = variable(Point, [])
    assert (
        verbalize_expression(or_(point.x > 5.0, point.x < 1.0))
        == "the x of a Point is greater than 5.0 or less than 1.0"
    )
