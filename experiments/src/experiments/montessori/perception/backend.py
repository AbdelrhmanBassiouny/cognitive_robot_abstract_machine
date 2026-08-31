"""
Answer an :mod:`entity query language <krrood.entity_query_language>` query about the
Montessori scene by looking at it.

Perception is a backend beside the native and SQLAlchemy ones, so asking and looking are
the same act::

    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece).where(piece.supporting_surface == board_lid_name))
    [seen] = query.evaluate(backend=PerceptionBackend(source=node))
    reach_for = seen.pose

The query's conditions are split the way a query planner splits them. What the look can
act on shapes the search: the kind of detection selected, and which surface to rectify
and search. What it cannot is left to the query's own evaluation over the detections that
came back, so no condition is ever quietly dropped. The two halves cannot disagree,
because the pushed-down conditions stay in the query and are checked again there -- the
search is narrowed as an economy, never as the thing that makes the answer right.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import ClassVar, Iterable, Optional

from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from krrood.entity_query_language.backends import AttributeEqualityToLiteral, SelectiveBackend
from krrood.entity_query_language.core.base_expressions import Selectable
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.exceptions import BackendCannotResolveCondition
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.verbalization.vocabulary.english import Directive
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

# %% the backend


@dataclass
class PerceptionBackend(SelectiveBackend):
    """
    Answers a query by looking at the scene rather than by recalling it.

    Selective, because a camera reports what is in front of it: it finds what is really
    there and cannot fill in an attribute nobody can see.
    """

    source: MontessoriSceneSource
    """
    Where a look at the scene comes from.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.LOOK_FOR
    """
    Going to look reads as *"Look for …"*, which is what tells it apart from recalling
    something already recorded.
    """

    SUPPORTING_SURFACE_ATTRIBUTE_NAME: ClassVar[str] = "supporting_surface"
    """
    The attribute of a detection that names the surface it was found on, and so the one
    a condition narrows the search by.
    """

    def _evaluate(self, expression: Query) -> Iterable:
        """
        Look for what the query asks about, then let the query filter what came back.

        The kind selected is applied here rather than left to the query, since a
        variable's declared type is not one of the conditions the query re-checks; every
        real condition is.

        :param expression: The query to answer.
        :raises BackendCannotResolveCondition: If a condition constrains anything other
            than the variable being selected.
        """
        [selection] = expression._selected_variables_
        request = self.read_request(expression)
        found = self.source.scene(request).detections
        selection._update_domain_(
            [detection for detection in found if request.admits(detection)]
        )
        yield from expression._evaluate_natively_()

    @classmethod
    def read_request(cls, expression: Query) -> SceneRequest:
        """
        Read what a query asks a look for.

        :param expression: The query to read.
        :raises BackendCannotResolveCondition: If a condition constrains anything other
            than the variable being selected, which a look can neither search for nor
            filter on.
        :return: The kind of detection the query selects, and the surface any of its
            conditions narrows the search to.
        """
        [selection] = expression._selected_variables_
        surface = None
        for condition in cls._conditions_of(expression):
            named = cls._surface_named_by(condition, selection)
            surface = named if named is not None else surface
        return SceneRequest(detection_type=selection._type_, supporting_surface=surface)

    @staticmethod
    def _conditions_of(expression: Query) -> Iterable[Evaluable]:
        """
        :param expression: The query to read.
        :return: Its own ``where`` conditions, empty when it states none.
        """
        builder = expression._where_builder_
        return builder.conditions if builder is not None else ()

    @classmethod
    def _surface_named_by(
        cls, condition: Evaluable, selection: Selectable
    ) -> Optional[PrefixedName]:
        """
        Read a condition as naming the surface to search.

        :param condition: The condition to read.
        :param selection: The variable the query selects.
        :raises BackendCannotResolveCondition: If the condition constrains any other
            variable, which neither the search nor a filter over the detections can
            answer.
        :return: The surface the condition asks about, or ``None`` when it asks about
            anything else -- which the query's own evaluation applies afterwards.
        """
        if condition._constrained_variables_ - {selection}:
            raise BackendCannotResolveCondition(condition, cls)
        equality = AttributeEqualityToLiteral.read_from(condition, selection)
        if equality is None:
            return None
        if equality.attribute_name != cls.SUPPORTING_SURFACE_ATTRIBUTE_NAME:
            return None
        return equality.value
