from __future__ import annotations

from dataclasses import dataclass, replace

from krrood.entity_query_language.verbalization.field_metadata import (
    FieldMetadataRegistry,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    Fragment,
    RoleFragment,
    map_fragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole


@dataclass
class FieldMetadataProcessor:
    """
    Apply per-field display-name overrides to every attribute leaf — the single realisation pass
    that swaps a raw attribute identifier for its preferred surface word (e.g. ``begin`` →
    *"beginning"*).

    Every attribute, however it was built (a comparator modifier, a possessive chain hop, an
    aggregation leaf, a ranking key), reaches the finished tree as a ``RoleFragment`` carrying the
    ``ATTRIBUTE`` role and a :class:`SourceReference` to its ``(owner type, attribute)``. So one
    pass keyed on that reference covers them all, and the decision stays deterministic: it reads
    only the committed :class:`FieldMetadataRegistry`.

    Runs after the determiner pass (so ``NounPhrase`` / ``PossessiveChain`` are already lowered to
    reachable leaves) and before morphology (so pluralisation inflects the chosen display form).
    An empty registry leaves every leaf untouched — the no-op default.

    Reference: Gatt & Reiter (2009), SimpleNLG — a lexical realisation stage over the phrase spec.
    """

    registry: FieldMetadataRegistry
    """The committed per-field metadata this pass consults."""

    def process(self, fragment: Fragment) -> Fragment:
        """
        :param fragment: Root of the (coreference- and determiner-lowered) fragment tree.
        :return: A new tree with every attribute leaf rewritten to its display name (idempotent;
            unchanged when no entry applies).
        """
        return map_fragment(fragment, self._rename)

    def _rename(self, leaf: Fragment) -> Fragment:
        if (
            not isinstance(leaf, RoleFragment)
            or leaf.role is not SemanticRole.ATTRIBUTE
        ):
            return leaf
        reference = leaf.source_reference
        if reference is None or reference.attribute is None:
            return leaf
        display = self.registry.display_name(reference.owner_type, reference.attribute)
        if display is None or display == leaf.text:
            return leaf
        return replace(leaf, text=display)
