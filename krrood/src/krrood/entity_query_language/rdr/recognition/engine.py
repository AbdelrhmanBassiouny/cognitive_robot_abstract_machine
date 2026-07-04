"""The recognition engine: hypothesise-and-test over registered view recognizers."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Iterator, Type

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.rdr.recognition.has_candidates import HasCandidates
from krrood.entity_query_language.rdr.recognition.predicates import JudgedGenuine
from krrood.entity_query_language.rdr.recognition.registry import DefinitionRegistry


@dataclass
class RecognitionEngine:
    """Recognizes views in a world by hypothesise-and-test (:cite:t:`erman1980hearsay`).

    For each registered view type, in dependency order, it composes the view's candidates
    with its definition's judgment (a
    :class:`~krrood.entity_query_language.rdr.recognition.predicates.JudgedGenuine` filter)
    into a single query whose solutions are the genuine views. Definitions reference other
    views' conclusions but never invoke their definitions: the engine supplies recognized
    views bottom-up (inversion of control), mirroring subsumption classification down a
    taxonomy (:cite:t:`brachman1985overview`).
    """

    registry: DefinitionRegistry
    """The recognizers, one per view type."""

    def recognition_query(self, view_type: Type[HasCandidates], world: Any) -> Query:
        """Compose ``view_type``'s candidates with its definition into one query.

        The recall-oriented candidate query is materialized (it is cheap and structural);
        the returned query lazily applies the precision-oriented definition judgment.

        :param view_type: A registered view type that proposes its own candidates.
        :param world: The structure to recognize the view in.
        :return: A query whose solutions are the candidates the definition judges genuine.
        """
        entry = self.registry.get(view_type)
        candidates = list(view_type.candidates(world).evaluate())
        judged = variable(view_type, domain=candidates)
        return an(entity(judged).where(JudgedGenuine(judged, entry.definition)))

    def recognize(self, world: Any) -> Iterator[Any]:
        """Lazily yield the recognized views across all registered types, in dependency order.

        :param world: The structure to recognize views in.
        :return: An iterator over the recognized view instances.
        """
        for entry in self.registry.in_dependency_order():
            yield from self.recognition_query(entry.view_type, world).evaluate()
