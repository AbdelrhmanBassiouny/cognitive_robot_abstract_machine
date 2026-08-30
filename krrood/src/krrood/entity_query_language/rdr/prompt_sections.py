"""
Declarative prompt sections for the EQL-RDR interactive expert shell.

Each :class:`PromptSection` decides whether it applies to the interaction at hand and
produces the lines it contributes. The full prompt is assembled by iterating
:data:`PROMPT_SECTIONS` and collecting the output of every applicable section — a
*Composite / Pipeline of Specifications* rather than a nested ``if``-cascade.

New prompt situations become new :class:`PromptSection` subclasses appended to
:data:`PROMPT_SECTIONS`; existing sections are never modified to accommodate new cases
(open/closed principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from typing_extensions import TYPE_CHECKING, ClassVar, List

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.conclusion_helper import (
    ConclusionSupportPresenter,
)
from krrood.entity_query_language.rdr.interface import AnswerRequest, CaseContext
from krrood.entity_query_language.rdr.magics import MagicName
from krrood.entity_query_language.rdr.prompt_examples import (
    build_conclusion_example,
    build_conditions_example,
)
from krrood.entity_query_language.rdr.rule_tree_view import format_condition

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.interactive import Palette


def supporting_material_presenters(
    context: CaseContext,
) -> List[ConclusionSupportPresenter]:
    """
    Narrow a case's helpers to the ones that have supporting material to show.

    :param context: The case context whose helpers to narrow.
    :return: The helpers that present supporting material, in configured order.
    """
    return [
        helper
        for helper in context.helpers
        if isinstance(helper, ConclusionSupportPresenter)
    ]


# %% What a section is given, and how it is identified


@dataclass
class RenderContext:
    """
    Everything a :class:`PromptSection` needs to decide applicability and produce lines.
    """

    case: CaseContext
    """
    The case context for the current interaction.
    """

    requests: List[AnswerRequest]
    """
    The answer requests for the current interaction.
    """

    palette: Palette
    """
    The colour/styling palette for the current shell.
    """

    is_first_prompt: bool = True
    """
    True only on the very first :meth:`~ExpertInterface.interact` call of a session; used
    to suppress one-time hints on subsequent prompts.
    """

    @property
    def has_target(self) -> bool:
        """:return: True when a ground-truth target conclusion was supplied."""
        return self.case.has_target

    @property
    def has_current_conclusion(self) -> bool:
        """:return: True when the RDR currently concludes something for this case."""
        return self.case.has_current_conclusion

    @property
    def is_conclusion_request(self) -> bool:
        """:return: True when the interaction is asking for a conclusion (no-target path)."""
        return any(request.name == AnswerName.CONCLUSION for request in self.requests)

    @property
    def is_conditions_request(self) -> bool:
        """:return: True when the interaction is asking for conditions."""
        return any(request.name == AnswerName.CONDITIONS for request in self.requests)

    @property
    def has_suggested_condition(self) -> bool:
        """:return: True when a suggested condition hint is available from the resolver."""
        return self.case.suggested_condition is not None


class PromptSectionName(StrEnum):
    """
    The situation each prompt section speaks to, and the identifier it is looked up by.
    """

    GROUND_TRUTH_CONCLUSION = "ground_truth_conclusion"
    """
    The conclusion the case is known to deserve.
    """

    CURRENT_CONCLUSION_VS_TARGET = "current_conclusion_vs_target"
    """
    What the tree concludes today, against that known conclusion.
    """

    NO_RULE_FIRED_KNOWN_TARGET = "no_rule_fired_known_target"
    """
    Nothing fired, and the conclusion the case deserves is known.
    """

    CONFLICT_RESOLUTION = "conflict_resolution"
    """
    A rule fired and concluded something other than the known conclusion.
    """

    LABELLING_HAS_CURRENT = "labelling_has_current"
    """
    No conclusion is known and the tree already offers one to confirm.
    """

    LABELLING_FIRED_ANCHOR = "labelling_fired_anchor"
    """
    The condition that standing conclusion came from.
    """

    LABELLING_NO_RULE = "labelling_no_rule"
    """
    No conclusion is known and nothing fired to suggest one.
    """

    ALLOWED_VALUES = "allowed_values"
    """
    What the conclusion is allowed to be.
    """

    CONTEXTUAL_EXAMPLE = "contextual_example"
    """
    A copy-pasteable example of the answer being asked for.
    """

    HELP_HINT = "help_hint"
    """
    The one-time pointer at the magics that explain the case.
    """

    AUTO_RESOLUTION_HINT = "auto_resolution_hint"
    """
    The condition a resolver suggested, and how to accept it.
    """


@dataclass(frozen=True)
class PromptSection(ABC):
    """
    One declarative, open-closed unit of prompt content.
    """

    name: ClassVar[PromptSectionName]
    """
    The situation this section speaks to.
    """

    @abstractmethod
    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when this section should appear in the prompt.
        """

    @abstractmethod
    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """


# %% The sections themselves — one class per prompt situation


@dataclass(frozen=True)
class GroundTruthConclusion(PromptSection):
    """
    States the conclusion the case is known to deserve.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.GROUND_TRUTH_CONCLUSION

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when a ground-truth conclusion was supplied.
        """
        return context.has_target

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        return [
            context.palette.label("Ground-truth conclusion: ")
            + context.palette.good(repr(context.case.target_conclusion))
        ]


@dataclass(frozen=True)
class CurrentConclusionVersusTarget(PromptSection):
    """
    States what the tree concludes today, coloured by whether it already matches the
    known conclusion.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.CURRENT_CONCLUSION_VS_TARGET

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when a ground-truth conclusion was supplied.
        """
        return context.has_target

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        value = repr(context.case.current_conclusion)
        styled = (
            context.palette.good(value)
            if context.case.current_conclusion == context.case.target_conclusion
            else context.palette.wrong(value)
        )
        return [context.palette.label("Current conclusion: ") + styled]


@dataclass(frozen=True)
class NoRuleFiredKnownTarget(PromptSection):
    """
    Says that nothing fired and asks for a condition that would.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when the conclusion is known and nothing concludes it yet.
        """
        return context.has_target and not context.has_current_conclusion

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        return [
            context.palette.label("No rule fired for this case."),
            context.palette.label("Write a ")
            + context.palette.keyword("condition")
            + context.palette.label(" that fires for it."),
        ]


@dataclass(frozen=True)
class ConflictResolution(PromptSection):
    """
    Names the condition that concluded wrongly and asks for one that separates this case
    from it.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.CONFLICT_RESOLUTION

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when a rule concluded something other than the known
            conclusion.
        """
        return (
            context.has_target
            and context.has_current_conclusion
            and context.case.current_conclusion != context.case.target_conclusion
        )

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        target = repr(context.case.target_conclusion)
        current = repr(context.case.current_conclusion)
        lines: List[str] = []
        if context.case.trace is not None:
            lines.append(
                context.palette.label("The condition ")
                + context.palette.code(
                    format_condition(context.case.trace.firing_anchor)
                )
                + context.palette.label(" concluded ")
                + context.palette.strong_wrong(current)
                + context.palette.label(" for this case while it should be ")
                + context.palette.good(target)
                + context.palette.label(".")
            )
        else:
            lines.append(
                context.palette.label("The RDR concluded ")
                + context.palette.strong_wrong(current)
                + context.palette.label(" while it should be ")
                + context.palette.good(target)
                + context.palette.label(".")
            )
        lines.append(
            context.palette.label(
                "Provide a condition that helps us detect this exceptional case"
            )
            + context.palette.label(" (and similar ones) such that we conclude ")
            + context.palette.good(target)
            + context.palette.label(" instead.")
        )
        return lines


@dataclass(frozen=True)
class LabellingHasCurrent(PromptSection):
    """
    Offers the standing conclusion for confirmation, so an unchanged case costs one
    keystroke.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.LABELLING_HAS_CURRENT

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when no conclusion is known and the tree offers one.
        """
        return not context.has_target and context.has_current_conclusion

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        return [
            context.palette.label("The RDR currently concludes ")
            + context.palette.neutral(repr(context.case.current_conclusion))
            + context.palette.label(" — is that correct?")
            + context.palette.label(
                " If so, skip (press CTRL+D), else provide the correct conclusion."
            )
        ]


@dataclass(frozen=True)
class LabellingFiredAnchor(PromptSection):
    """
    Names the condition the standing conclusion came from.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.LABELLING_FIRED_ANCHOR

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when a traced rule produced the standing conclusion.
        """
        return (
            not context.has_target
            and context.has_current_conclusion
            and context.case.trace is not None
            and context.case.trace.firing_anchor is not None
        )

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        return [
            context.palette.label("It fired on ")
            + context.palette.code(format_condition(context.case.trace.firing_anchor))
            + context.palette.label(".")
        ]


@dataclass(frozen=True)
class LabellingNoRule(PromptSection):
    """
    Asks for a label outright, since nothing fired to suggest one.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.LABELLING_NO_RULE

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when no conclusion is known and nothing fired.
        """
        return not context.has_target and not context.has_current_conclusion

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        return [
            context.palette.label("No rule fired — what should this case conclude?")
        ]


@dataclass(frozen=True)
class AllowedValues(PromptSection):
    """
    Shows what the conclusion may be — the values themselves when they enumerate, the
    type otherwise.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.ALLOWED_VALUES

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when a conclusion is being asked for and its domain is known.
        """
        return not context.has_target and context.case.conclusion_domain is not None

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        domain = context.case.conclusion_domain
        if domain.is_enumerable:
            return [
                context.palette.label("Choose one of: ")
                + context.palette.code(domain.display())
            ]
        return [
            context.palette.label("Conclusion type: ")
            + context.palette.code(domain.type_display)
        ]


@dataclass(frozen=True)
class ContextualExample(PromptSection):
    """
    Shows a copy-pasteable example of the answer being asked for.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.CONTEXTUAL_EXAMPLE

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` always — every interaction is worth an example.
        """
        return True

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        if context.is_conclusion_request:
            example = build_conclusion_example(context)
        else:
            example = build_conditions_example(context)
        return [context.palette.hint(example)]


@dataclass(frozen=True)
class HelpHint(PromptSection):
    """
    Points at the magics that explain the case, naming the helper magic only when a
    helper has something to show.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.HELP_HINT

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` on the first prompt of a session only.
        """
        return context.is_first_prompt

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        magics = f"%{MagicName.HELP}"
        if supporting_material_presenters(context.case):
            magics += f" / %{MagicName.HELPER}"
        return [context.palette.hint(f"Type {magics} for help with this case.")]


@dataclass(frozen=True)
class AutoResolutionHint(PromptSection):
    """
    Shows the resolver-suggested condition and how to accept it unchanged.
    """

    name: ClassVar[PromptSectionName] = PromptSectionName.AUTO_RESOLUTION_HINT

    def applicable(self, context: RenderContext) -> bool:
        """
        :param context: The render context for the current interaction.
        :return: ``True`` when the resolver suggested a condition.
        """
        return context.has_suggested_condition

    def lines(self, context: RenderContext) -> List[str]:
        """
        :param context: The render context for the current interaction.
        :return: The lines this section contributes to the header.
        """
        resolved = context.case.suggested_condition
        return [
            context.palette.suggestion(
                f"Suggested condition (resolved by {resolved.resolver_type.__name__}): "
            )
            + context.palette.code(format_condition(resolved.expression)),
            context.palette.suggestion("Press CTRL+D to accept this suggestion."),
        ]


# %% Registry — the single extension point for new prompt situations.
# New prompt situations = append a PromptSection subclass; never modify existing ones.

PROMPT_SECTIONS: List[PromptSection] = [
    GroundTruthConclusion(),
    CurrentConclusionVersusTarget(),
    NoRuleFiredKnownTarget(),
    ConflictResolution(),
    LabellingHasCurrent(),
    LabellingFiredAnchor(),
    LabellingNoRule(),
    AllowedValues(),
    ContextualExample(),
    HelpHint(),
    AutoResolutionHint(),
]
