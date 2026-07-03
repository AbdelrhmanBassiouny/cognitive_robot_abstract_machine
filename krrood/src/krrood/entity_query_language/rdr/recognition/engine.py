"""The recognition engine: hypothesise-and-test over registered view recognizers."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, List

from krrood.entity_query_language.rdr.recognition.registry import DefinitionRegistry


@dataclass
class RecognitionEngine:
    """Recognizes views in a world by hypothesise-and-test (:cite:t:`erman1980hearsay`).

    For each registered view type, in dependency order, the engine evaluates the
    candidate generator's query and keeps the candidates its definition judges
    positively. Definitions reference other views' conclusions but never invoke their
    definitions: the engine supplies recognized views bottom-up (inversion of control),
    mirroring subsumption classification down a taxonomy (:cite:t:`brachman1985overview`).
    """

    registry: DefinitionRegistry
    """The recognizers, one per view type."""

    def recognize(self, world: Any) -> List[Any]:
        """Recognize every registered view type in ``world``.

        :param world: The structure to recognize views in.
        :return: The candidate views their definitions judged positively.
        """
        recognized: List[Any] = []
        for entry in self.registry.in_dependency_order():
            candidates = entry.generator.generate(world).evaluate()
            recognized.extend(
                candidate
                for candidate in candidates
                if entry.definition.judge(candidate)
            )
        return recognized
