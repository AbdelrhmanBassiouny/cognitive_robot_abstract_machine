from __future__ import annotations

import uuid
from typing_extensions import Iterable, List, Mapping, Optional

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
from krrood.entity_query_language.verbalization.rendering.passes import RealizationPass

# The stateless lowering passes are shared module-level instances. The coreference pass is stateful
# per walk (parameterised by discourse, numbered labels, and prior-build referents) and the
# field-metadata pass is parameterised by the per-run registry, so both are created fresh per call
# and assembled into the pipeline in realize_tree.
_DETERMINER = DeterminerProcessor()
_MORPHOLOGY = MorphologyProcessor()
_ORTHOGRAPHY = OrthographyProcessor()


def realize_tree(
    fragment: Fragment,
    previously_introduced_referents: Optional[Iterable[uuid.UUID]] = None,
    discourse: DiscourseView = EMPTY_DISCOURSE,
    numbered_labels: Optional[Mapping[uuid.UUID, str]] = None,
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
    :param previously_introduced_referents: Referents introduced by prior builds on a shared context.
    :param discourse: The focus-per-scope view the coreference pass consults (empty for a local
        sub-tree, which has no query scope of its own).
    :param numbered_labels: Disambiguation numbers for referents the rules cannot label themselves
        (relational referents) — applied by the coreference pass.
    :param field_metadata: Per-field display-name overrides; an empty registry (the default) keeps
        every attribute's raw identifier.
    :return: The fully realised fragment tree.

    This is the pass-running step: it returns a lowered fragment *tree*, so the example wraps it in
    :func:`flatten_fragment_to_plain_text` to read the text out; :func:`realize_subtree` runs the
    same passes and returns that plain string directly.

    >>> from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
    >>> tree = EQLVerbalizer().build(a(entity(variable(Robot, []))))
    >>> flatten_fragment_to_plain_text(realize_tree(tree))
    'Find a Robot'
    """
    registry = field_metadata if field_metadata is not None else FieldMetadataRegistry()
    pipeline: List[RealizationPass] = [
        CoreferenceProcessor(
            discourse=discourse,
            numbered_labels=dict(numbered_labels or {}),
            previously_introduced_referents=tuple(previously_introduced_referents or ()),
        ),
        _DETERMINER,
        FieldMetadataProcessor(registry),
        _MORPHOLOGY,
        _ORTHOGRAPHY,
    ]
    realised = fragment
    for realisation_pass in pipeline:
        realised = realisation_pass.process(realised)
    return realised


def realize_subtree(fragment: Fragment) -> str:
    """
    Fully realise a sub-tree to plain text — the realisation passes, then flatten.

    For an opaque leaf (a user template that string-formats its children), the children must be
    realised here, locally, rather than deferred to the global passes.

    :param fragment: Root of the sub-tree.
    :return: The realised plain-text string.

    Its contribution over :func:`realize_tree` is the final flatten: it returns the plain *string*
    *Find a Robot*, not a fragment tree — the form an opaque template needs for its locally realised
    children.

    >>> from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
    >>> realize_subtree(EQLVerbalizer().build(a(entity(variable(Robot, [])))))
    'Find a Robot'
    """
    return flatten_fragment_to_plain_text(realize_tree(fragment))
