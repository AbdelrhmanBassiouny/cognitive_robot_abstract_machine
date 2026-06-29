from __future__ import annotations

from typing_extensions import Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.dialogue.speech_act import (
    Ask,
    Explain,
    Inform,
    SpeechAct,
    Warn,
)
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.engine import fold
from krrood.entity_query_language.verbalization.grammar.framework.registry import RULES
from krrood.entity_query_language.verbalization.pipeline import VerbalizationPipeline
from krrood.entity_query_language.verbalization.rendering.discourse import DiscourseModel
from krrood.entity_query_language.verbalization.rendering.realization import realize_tree


def _scan_target(act: SpeechAct) -> Optional[SymbolicExpression]:
    """:return: The embedded expression whose referents seed coreference, or ``None`` when the act
    carries no expression."""
    if isinstance(act, Ask):
        return act.question
    if isinstance(act, Inform):
        return act.answer.query
    if isinstance(act, Warn):
        return act.proposition
    if isinstance(act, Explain):
        causes = act.answer.cause_set.causes
        return causes[0].condition if causes else None
    return None


def verbalize_speech_act(act: SpeechAct) -> str:
    """Render a speech act to faithful English.

    The act is folded through the same deterministic grammar, and lowered through the same
    realisation passes, as any entity-query-language expression; only the microplanning services and
    discourse model are seeded from the act's embedded expression rather than from the act itself
    (which is not an expression).

    :param act: The speech act to verbalize.
    :return: The rendered sentence.
    """
    scan_target = _scan_target(act)
    services = (
        MicroplanningServices.from_expression(scan_target)
        if scan_target is not None
        else MicroplanningServices()
    )
    previously_introduced_referents = set(services.referring.seen)
    fragment = fold(act, services, RULES)
    discourse = (
        DiscourseModel.from_expression(scan_target, services.microplan)
        if scan_target is not None
        else DiscourseModel({}, frozenset())
    )
    lowered = realize_tree(
        fragment,
        previously_introduced_referents=previously_introduced_referents,
        discourse=discourse,
        numbered_labels=services.referring.numbered_labels,
    )
    sentence = VerbalizationPipeline.plain().verbalize_fragment(lowered)
    return sentence[:1].upper() + sentence[1:]
