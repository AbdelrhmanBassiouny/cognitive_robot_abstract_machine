"""
Model-side store of the last explanation produced for each classified case.

Firing provenance for an RDR conclusion lives here — on the model — never on the
concluded value (a single shared enum member is concluded for many cases, and primitives
cannot hold attributes at all) and never on the case (which the engine must not mutate).
This mirrors :class:`~krrood.entity_query_language.rdr.corner_case.CornerCaseStore`, which
already keeps creation provenance model-side.

The store is a *cache*, not the sole source of truth: a conclusion can always be
re-explained by re-tracing (see
:meth:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR.answer_why`). So it
holds both the case and its explanation *weakly* and keys by case identity — it never keeps
a case (or its bindings-heavy explanation) alive, and the last classification of a case
wins. When either the case or its explanation is collected, the entry drops.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass, field

from typing_extensions import Any, Dict, Optional

from krrood.entity_query_language.rdr.exceptions import NoRecordedExplanation
from krrood.entity_query_language.rdr.why import RDRConclusionExplanation


@dataclass
class _StoredExplanation:
    """
    One case's most recent explanation, held weakly against the case's identity.
    """

    case_reference: weakref.ReferenceType
    """A weak reference to the case, so the entry never keeps the case alive."""
    explanation_reference: weakref.ReferenceType
    """
    A weak reference to the explanation, so the entry never keeps it (or the case, whose
    bindings it holds) alive once nothing else needs it.
    """


@dataclass
class CaseExplanationStore:
    """
    Weak, identity-keyed cache mapping each case to its last conclusion explanation.
    """

    _entries: Dict[int, _StoredExplanation] = field(default_factory=dict, repr=False)
    """
    Maps ``id(case)`` to the stored explanation; entries drop when the case or its
    explanation is collected.
    """

    def record(self, case: Any, explanation: RDRConclusionExplanation) -> None:
        """
        Store ``explanation`` as the latest explanation for ``case`` (last write wins).

        :param case: The classified case the explanation is about.
        :param explanation: The explanation of the case's most recent classification.
        """
        key = id(case)
        self._entries[key] = _StoredExplanation(
            case_reference=weakref.ref(case, self._dropper(key)),
            explanation_reference=weakref.ref(explanation, self._dropper(key)),
        )

    def get(self, case: Any) -> Optional[RDRConclusionExplanation]:
        """
        Return the stored explanation for ``case``, or ``None`` if none is recorded.

        :param case: The case whose explanation to look up.
        :return: The recorded explanation, or ``None`` when the case has none (never
            recorded, overwritten by a later case reusing the identity, or collected).
        """
        entry = self._entries.get(id(case))
        if entry is None or entry.case_reference() is not case:
            return None
        return entry.explanation_reference()

    def require(self, case: Any) -> RDRConclusionExplanation:
        """
        Return the stored explanation for ``case``, or raise if none is recorded.

        :param case: The case whose explanation to look up.
        :return: The recorded explanation.
        :raises NoRecordedExplanation: When the case has no recorded explanation.
        """
        explanation = self.get(case)
        if explanation is None:
            raise NoRecordedExplanation(case)
        return explanation

    def __contains__(self, case: Any) -> bool:
        """:return: Whether ``case`` has a recorded explanation."""
        return self.get(case) is not None

    def _dropper(self, key: int):
        """
        Build a weakref callback that drops ``key``'s entry when its referent dies.

        Removes the entry only when the collected reference is still the one stored, so
        a later case that reuses the freed ``id`` is left untouched.

        :param key: The ``id(case)`` the entry is stored under.
        :return: The callback to pass to :func:`weakref.ref`.
        """

        def drop(reference: weakref.ReferenceType) -> None:
            entry = self._entries.get(key)
            if entry is not None and reference in (
                entry.case_reference,
                entry.explanation_reference,
            ):
                self._entries.pop(key, None)

        return drop
