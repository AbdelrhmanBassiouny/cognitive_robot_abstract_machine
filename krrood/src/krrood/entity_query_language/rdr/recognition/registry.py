"""Registry of view recognizers, ordered by their conclusion dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Dict, List, Set, Type

from krrood.entity_query_language.rdr.recognition.definition import Definition
from krrood.entity_query_language.rdr.recognition.exceptions import (
    CyclicDefinitionDependency,
    UnregisteredView,
)
from krrood.entity_query_language.rdr.recognition.has_candidates import HasCandidates


@dataclass
class RecognizableView:
    """A recognizable view type together with the definition that judges its candidates."""

    view_type: Type[HasCandidates]
    """The view type recognized by this entry; it proposes its own candidates."""

    definition: Definition
    """Judges which of the view's candidates are genuine instances."""


@dataclass
class DefinitionRegistry:
    """Holds the recognizer for each view type and orders them by dependency.

    Owned by a :class:`~krrood.entity_query_language.rdr.recognition.engine.RecognitionEngine`
    rather than kept global, so recognition never depends on shared mutable state.
    """

    _entries: Dict[Type, RecognizableView] = field(default_factory=dict)

    def register(
        self,
        view_type: Type[HasCandidates],
        definition: Definition,
    ) -> None:
        """Register the definition that judges ``view_type``'s candidates.

        :param view_type: A view type that provides its own candidates (``HasCandidates``).
        :param definition: The definition that judges which candidates are genuine.
        """
        self._entries[view_type] = RecognizableView(view_type, definition)

    def get(self, view_type: Type) -> RecognizableView:
        """Look up the recognizer for ``view_type``.

        :raises UnregisteredView: If ``view_type`` has no registered recognizer.
        """
        if view_type not in self._entries:
            raise UnregisteredView(view_type)
        return self._entries[view_type]

    def in_dependency_order(self) -> List[RecognizableView]:
        """Order recognizers so each runs after the views its definition references.

        Realizes subsumption-style classification down a taxonomy
        (:cite:t:`brachman1985overview`): a dependent view is recognized only after
        the views it references.

        :raises CyclicDefinitionDependency: If the referenced-conclusion edges form a cycle.
        """
        ordered: List[RecognizableView] = []
        visited: Set[Type] = set()
        for view_type in self._entries:
            self._visit(view_type, [], ordered, visited)
        return ordered

    def _visit(
        self,
        view_type: Type,
        path: List[Type],
        ordered: List[RecognizableView],
        visited: Set[Type],
    ) -> None:
        """Post-order depth-first visit that appends ``view_type`` after its references.

        :param view_type: The view type currently being visited.
        :param path: The referencing chain leading here, used to detect cycles.
        :param ordered: The accumulating dependency-ordered result.
        :param visited: View types already appended, so each is emitted once.
        :raises CyclicDefinitionDependency: If ``view_type`` is already on ``path``.
        """
        if view_type in visited:
            return
        if view_type in path:
            raise CyclicDefinitionDependency(path + [view_type])
        entry = self._entries.get(view_type)
        if entry is None:
            return
        for referenced in entry.definition.referenced_conclusions:
            self._visit(referenced, path + [view_type], ordered, visited)
        visited.add(view_type)
        ordered.append(entry)
