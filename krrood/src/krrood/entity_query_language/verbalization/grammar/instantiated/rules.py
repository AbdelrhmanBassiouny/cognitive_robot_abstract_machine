from __future__ import annotations

from krrood.entity_query_language.core.variable import InstantiatedVariable
from krrood.entity_query_language.predicate import RenderedFields, Verbalizable
from krrood.entity_query_language.verbalization.exceptions import (
    NonFragmentPredicateError,
    PredicateFragmentRequiredError,
)
from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)
from krrood.entity_query_language.verbalization.grammar.instantiated.assembler import (
    InstantiatedAssembler,
)
from krrood.entity_query_language.verbalization.grammar.instantiated.planner import (
    InstantiatedPlanner,
)
from krrood.entity_query_language.utils import camel_case_to_words
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Noun,
    predicate_clause,
)


class InstantiatedVariableRule(PhraseRule):
    """*"a TypeName where the field of the TypeName is … such that …"*."""

    construct = InstantiatedVariable
    name = "instantiated-variable"

    def build(self, node: InstantiatedVariable, context: RuleContext) -> Fragment:
        """:return: The instantiated variable's *"a TypeName, where the field of the TypeName is …"*
        noun phrase, built by the :class:`InstantiatedAssembler`.

        Its contribution is selecting the generic decomposed surface for a *non-predicate*
        constructed entity: with no verbalization fragment on ``Drawer``, this fallback rule fires
        and delegates to the assembler, which is why the result is the long *"a Drawer, where …"*
        form. A :class:`Verbalizable` predicate, by contrast, is *required* to supply a fragment —
        reaching this rule without one is an error, not a name-based fallback.

        >>> connection = variable(FixedConnection, [])
        >>> verbalize_expression(inference(Drawer)(container=connection.parent, handle=connection.child))
        'a Drawer, where the container of the Drawer is the parent of a FixedConnection, and the handle of the Drawer is the child of the FixedConnection'
        """
        type_ = node._type_
        if isinstance(type_, type) and issubclass(type_, Verbalizable):
            raise PredicateFragmentRequiredError(node=node)
        return InstantiatedAssembler(context).assemble(node)


class InstantiatedVerbalizableRule(PhraseRule):
    """An InstantiatedVariable whose type builds its own verbalization :class:`Fragment`."""

    construct = InstantiatedVariable
    name = "instantiated-verbalizable"

    def when(self, node: InstantiatedVariable, context: RuleContext) -> bool:
        """:return: ``True`` when *node*'s type supplies a verbalization fragment, selecting this rule
        over the generic *"a TypeName, where …"* form.

        Its contribution is the guard that admits this rule: ``IsReachable`` supplies a fragment, so
        this rule wins and the example renders as *"a Robot is reachable"* instead of the generic
        decomposed phrase. :meth:`build` then assembles that fragment.

        >>> verbalize_expression(inference(IsReachable)(body=variable(Robot, [])))
        'a Robot is reachable'
        """
        return InstantiatedPlanner.has_fragment(node)

    def build(self, node: InstantiatedVariable, context: RuleContext) -> Fragment:
        """:return: the type's verbalization fragment, built from its rendered field fragments
        (*"a Robot is reachable"*).

        The type composes the surface from the shared vocabulary, so the result is a structured
        fragment that flows through the remaining passes (coreference, determiner, morphology) — not
        an opaque string blob — which is why a wrapping ``Not`` can negate it inline.

        >>> verbalize_expression(inference(IsReachable)(body=variable(Robot, [])))
        'a Robot is reachable'
        """
        fields = RenderedFields(
            fragments={
                name: context.child(child)
                for name, child in node._child_vars_.items()
            },
            raw=node._child_vars_,
        )
        fragment = node._type_._verbalization_fragment_(fields)
        if not isinstance(fragment, Fragment):
            raise NonFragmentPredicateError(
                predicate_type=node._type_, returned=fragment
            )
        return fragment


class SymbolicFunctionRule(PhraseRule):
    """A boolean ``@symbolic_function`` reads as a predicate clause — ``is_one_month(period)`` →
    *"the period is one month"* — instead of the generic decomposition.

    Its type is a plain function (not a :class:`Verbalizable` class), so its guard is disjoint from
    :class:`InstantiatedVerbalizableRule`'s; both are guarded, so each still wins over the unguarded
    :class:`InstantiatedVariableRule` fallback when it applies.
    """

    construct = InstantiatedVariable
    name = "symbolic-function"

    def when(self, node: InstantiatedVariable, context: RuleContext) -> bool:
        """:return: ``True`` when *node* wraps a boolean symbolic function, selecting the
        predicate-clause surface over the generic *"a TypeName, where …"* form.

        >>> from krrood.entity_query_language.predicate import symbolic_function
        >>> @symbolic_function
        ... def is_one_month(period: int) -> bool:
        ...     return True
        >>> verbalize_expression(is_one_month(variable(int, [])))
        'an int is one month'
        """
        return InstantiatedPlanner.is_boolean_symbolic_function(node)

    def build(self, node: InstantiatedVariable, context: RuleContext) -> Fragment:
        """:return: the predicate clause *"<first operand> <name as words> <remaining operands>"*,
        each operand recursed through the fold so coreference and determiners still apply.

        >>> from krrood.entity_query_language.predicate import symbolic_function
        >>> @symbolic_function
        ... def is_even(number: int) -> bool:
        ...     return number % 2 == 0
        >>> verbalize_expression(is_even(variable(int, [])))
        'an int is even'
        """
        operands = [context.child(child) for child in node._child_vars_.values()]
        subject, *objects = operands
        return predicate_clause(node._type_.__name__, subject, *objects)


class SymbolicFunctionNounRule(PhraseRule):
    """A non-boolean ``@symbolic_function`` reads as a *noun* naming the value it computes —
    ``quarter(month)`` → *"a quarter"* — not a predicate clause (its output is not a truth value) and
    not the generic *"a TypeName, where the field of the TypeName is …"* decomposition. So a grouped
    report selecting it reads *"For each year and quarter, report …"*.

    Its guard is disjoint from :class:`SymbolicFunctionRule`'s (boolean) and
    :class:`InstantiatedVerbalizableRule`'s (a :class:`Verbalizable` class), so each guarded rule
    still wins over the unguarded :class:`InstantiatedVariableRule` fallback when it applies.
    """

    construct = InstantiatedVariable
    name = "symbolic-function-noun"

    def when(self, node: InstantiatedVariable, context: RuleContext) -> bool:
        """:return: ``True`` when *node* wraps a non-boolean symbolic function, selecting the
        noun surface over the generic decomposition.

        >>> from krrood.entity_query_language.predicate import symbolic_function
        >>> @symbolic_function
        ... def quarter(month: int) -> int:
        ...     return (month - 1) // 3 + 1
        >>> verbalize_expression(quarter(variable(int, [])))
        'a quarter'
        """
        return InstantiatedPlanner.is_value_symbolic_function(node)

    def build(self, node: InstantiatedVariable, context: RuleContext) -> Fragment:
        """:return: the function's name as an indefinite noun phrase — the computed value named, its
        operands suppressed (a value, like a variable, is referred to, not decomposed).

        >>> from krrood.entity_query_language.predicate import symbolic_function
        >>> @symbolic_function
        ... def quarter_number(month: int) -> int:
        ...     return (month - 1) // 3 + 1
        >>> verbalize_expression(quarter_number(variable(int, [])))
        'a quarter number'
        """
        return Noun(camel_case_to_words(node._type_.__name__)).as_fragment()
