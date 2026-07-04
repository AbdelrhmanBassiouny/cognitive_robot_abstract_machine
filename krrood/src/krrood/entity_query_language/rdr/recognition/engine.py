"""The recognition engine: hypothesise-and-test over registered view recognizers."""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, Iterator, Type

from krrood.entity_query_language.backends import (
    EntityQueryLanguageGenerativeBackend,
    GenerativeBackend,
)
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.rdr.recognition.has_candidates import HasCandidates
from krrood.entity_query_language.rdr.recognition.predicates import JudgedGenuine
from krrood.entity_query_language.rdr.recognition.registry import DefinitionRegistry


@dataclass
class RecognitionEngine:
    """Recognizes views in a world by hypothesise-and-test (:cite:t:`erman1980hearsay`).

    For each registered view type, in dependency order, it constructs the view's candidates
    (a generative backend building an underspecified view) and keeps those its definition
    judges genuine (a
    :class:`~krrood.entity_query_language.rdr.recognition.predicates.JudgedGenuine` filter
    composed as the candidates' single ``where``). Recognized views are added back to the
    world so dependent definitions can reference them bottom-up (inversion of control),
    mirroring subsumption classification down a taxonomy (:cite:t:`brachman1985overview`).

    .. note::
        ``recognize`` writes each recognized view into the world (via ``add_view``) as it goes,
        so a view type whose definition references another is recognized only after that other
        type's instances are available — the "conclusions as case attributes" loop of GRDR.
    """

    registry: DefinitionRegistry
    """The recognizers, one per view type."""

    backend: GenerativeBackend = field(
        default_factory=EntityQueryLanguageGenerativeBackend
    )
    """Constructs candidate instances from their underspecified view; swappable per context."""

    def recognition_query(self, view_type: Type[HasCandidates], world: Any) -> Match:
        """Compose ``view_type``'s underspecified candidate view with its definition's judgment.

        The recall-oriented candidate view is filtered by the precision-oriented definition
        judgment as its single ``where``; nothing is constructed until the returned match is
        evaluated through a generative backend.

        :param view_type: A registered view type that proposes its own candidates.
        :param world: The structure to recognize the view in.
        :return: The underspecified candidate ``Match`` whose genuine constructions the
            definition accepts.
        """
        entry = self.registry.get(view_type)
        candidate = view_type.candidates(world)
        candidate.where(JudgedGenuine(candidate.variable, entry.definition))
        return candidate

    def recognize(self, world: Any) -> Iterator[Any]:
        """Lazily yield the recognized views across all registered types, in dependency order.

        Each type is fully recognized and its instances added to the world before the next
        type runs, so a dependent type's candidates can query the views it references.

        :param world: The structure to recognize views in; must accept recognized views via
            ``add_view``.
        :return: An iterator over the recognized view instances.
        """
        for entry in self.registry.in_dependency_order():
            recognized = list(
                self.backend.evaluate(self.recognition_query(entry.view_type, world))
            )
            for view in recognized:
                world.add_view(view)
            yield from recognized
