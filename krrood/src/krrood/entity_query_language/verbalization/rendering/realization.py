from __future__ import annotations

import uuid
from typing_extensions import Iterable, Optional

from krrood.entity_query_language.verbalization.field_metadata import (
    FieldMetadataRegistry,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    flatten_fragment_to_plain_text,
    Fragment,
)
from krrood.entity_query_language.verbalization.rendering.coreference_processor import (
    CoreferenceProcessor,
)
from krrood.entity_query_language.verbalization.rendering.field_metadata_processor import (
    FieldMetadataProcessor,
)
from krrood.entity_query_language.verbalization.rendering.discourse import (
    DiscourseView,
    EMPTY_DISCOURSE,
)
from krrood.entity_query_language.verbalization.rendering.determiner_processor import (
    DeterminerProcessor,
)
from krrood.entity_query_language.verbalization.rendering.morphology_processor import (
    MorphologyProcessor,
)
from krrood.entity_query_language.verbalization.rendering.orthography_processor import (
    OrthographyProcessor,
)

# The stateless passes are shared module-level instances; the coreference pass is
# stateful per walk and is therefore created fresh inside realize_tree.
_DETERMINER = DeterminerProcessor()
_MORPHOLOGY = MorphologyProcessor()
_ORTHOGRAPHY = OrthographyProcessor()


def realize_tree(
    fragment: Fragment,
    already_seen: Optional[Iterable[uuid.UUID]] = None,
    discourse: DiscourseView = EMPTY_DISCOURSE,
    field_metadata: Optional[FieldMetadataRegistry] = None,
) -> Fragment:
    """
    Run the ordered realisation passes over *fragment* — the one place the lowering passes and
    their order are defined: coreference resolution → determiner lowering → field-metadata
    (display-name) → morphology → orthography (punctuation spacing). Both the whole-expression
    build and the local realisation of an opaque template need this same ordered sequence.

    The field-metadata pass runs after determiner lowering (so ``NounPhrase`` / ``PossessiveChain``
    are already lowered to reachable attribute leaves) and before morphology (so pluralisation
    inflects the chosen display word). It is a no-op for an empty / omitted registry.

    Reference: Gatt & Reiter (2009), SimpleNLG — the ordered realisation stages.

    :param fragment: Root of the fragment tree.
    :param already_seen: Referents introduced by prior builds on a shared context.
    :param discourse: The focus-per-scope view the coreference pass consults (empty for a local
        sub-tree, which has no query scope of its own).
    :param field_metadata: Per-field display-name overrides; an empty registry (the default) keeps
        every attribute's raw identifier.
    :return: The fully realised fragment tree.
    """
    resolved = CoreferenceProcessor(discourse=discourse).process(
        fragment, already_seen=already_seen
    )
    registry = field_metadata if field_metadata is not None else FieldMetadataRegistry()
    renamed = FieldMetadataProcessor(registry).process(_DETERMINER.process(resolved))
    inflected = _MORPHOLOGY.process(renamed)
    return _ORTHOGRAPHY.process(inflected)


def realize_subtree(fragment: Fragment) -> str:
    """
    Fully realise a sub-tree to plain text — the realisation passes, then flatten.

    For an opaque leaf (a user template that string-formats its children), the children must be
    realised here, locally, rather than deferred to the global passes.

    :param fragment: Root of the sub-tree.
    :return: The realised plain-text string.
    """
    return flatten_fragment_to_plain_text(realize_tree(fragment))
