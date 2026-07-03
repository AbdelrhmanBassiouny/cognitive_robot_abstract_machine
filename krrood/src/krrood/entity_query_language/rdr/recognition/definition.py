"""Definition: the precision-oriented recognizer for a view type."""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import FrozenSet, Generic, Type, TypeVar

from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

ViewType = TypeVar("ViewType")


@dataclass
class Definition(Generic[ViewType]):
    """Judges whether a candidate view is a genuine instance of its type.

    The recognizer is separated from, while remaining colocated with, the domain
    class (Specification pattern, :cite:t:`evans2003domain`) and is refined by
    exception via its underlying Ripple Down Rules tree
    (:cite:t:`compton1990philosophical`). Judging is a pure function of the candidate
    and performs no mutation.
    """

    classifier: EQLSingleClassRDR
    """The single-class RDR that classifies the candidate's judgment attribute."""

    referenced_conclusions: FrozenSet[Type] = field(default_factory=frozenset)
    """View types whose conclusions this definition reads.

    The engine supplies these bottom-up (inversion of control): a definition
    *references* another view's conclusion but never invokes its definition directly.
    """

    def judge(self, candidate: ViewType) -> bool:
        """Decide whether ``candidate`` is a genuine instance of the view type.

        :param candidate: The candidate view to judge.
        :return: ``True`` when the underlying RDR concludes ``True`` for ``candidate``;
            ``False`` when it concludes otherwise or no rule fires.
        """
        return self.classifier.classify(candidate) is True
