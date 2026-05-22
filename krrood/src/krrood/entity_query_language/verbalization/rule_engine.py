from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.fragments.base import VerbFragment
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


class VerbalizationRule(ABC):
    """
    Abstract base for a declarative verbalization rule.

    Subclass to declare when a rule applies (:meth:`applies`) and what fragment
    it produces (:meth:`transform`).  The
    :class:`RuleEngine` sorts registered rule classes by MRO depth so that
    more-specific subclasses are always tried before their parents — no priority
    integers are needed.

    All methods are class methods; rules are stateless.
    """

    @classmethod
    @abstractmethod
    def applies(cls, expr: "SymbolicExpression", ctx: "VerbalizationContext") -> bool:
        """
        Return ``True`` if this rule can handle *expr*.

        :param expr: EQL expression to test.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param ctx: Current verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :returns: ``True`` when this rule should be applied to *expr*.
        :rtype: bool
        """

    @classmethod
    @abstractmethod
    def transform(
        cls,
        expr: "SymbolicExpression",
        ctx: "VerbalizationContext",
        delegate: "EQLVerbalizer",
    ) -> "VerbFragment":
        """
        Build and return the :class:`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment`
        for *expr*.

        :param expr: EQL expression to verbalize.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param ctx: Shared verbalization state (coreference, bindings).
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :param delegate: The top-level verbalizer used for recursive sub-expression verbalization.
        :type delegate: ~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer
        :returns: Fragment tree representing *expr* in natural language.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """


def _inheritance_depth(cls: type) -> int:
    try:
        return cls.__mro__.index(VerbalizationRule)
    except ValueError:
        return 0


class RuleEngine:
    """
    Applies the first matching :class:`VerbalizationRule` to an expression,
    deepest subclass first.

    On construction the supplied rule classes are sorted by MRO depth
    (``__mro__.index(VerbalizationRule)``, descending) so that subclasses always
    shadow their parents without the caller having to manage ordering.

    :param rule_classes: Concrete :class:`VerbalizationRule` subclasses to register.
    :type rule_classes: list[type[VerbalizationRule]]
    """

    def __init__(self, rule_classes: list[type[VerbalizationRule]]) -> None:
        self._rules = sorted(rule_classes, key=_inheritance_depth, reverse=True)

    def build(
        self,
        expr: "SymbolicExpression",
        ctx: "VerbalizationContext",
        delegate: "EQLVerbalizer",
    ) -> "VerbFragment":
        """
        Dispatch *expr* to the first matching rule and return its fragment.

        Before consulting any rule, checks whether *expr*'s ``_id_`` appears in
        :attr:`~krrood.entity_query_language.verbalization.context.VerbalizationContext.binding_overrides`;
        if so the override fragment is returned immediately.

        Falls back to a plain :class:`~krrood.entity_query_language.verbalization.fragments.base.WordFragment`
        bearing ``expr._name_`` when no rule matches.

        :param expr: EQL expression to verbalize.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param ctx: Shared verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :param delegate: Top-level verbalizer for recursive calls.
        :type delegate: ~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer
        :returns: Fragment tree for *expr*.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        var_id = getattr(expr, "_id_", None)
        if var_id is not None and var_id in ctx.binding_overrides:
            return ctx.binding_overrides[var_id]
        for rule_cls in self._rules:
            if rule_cls.applies(expr, ctx):
                return rule_cls.transform(expr, ctx, delegate)
        from krrood.entity_query_language.verbalization.fragments.base import WordFragment
        return WordFragment(text=expr._name_)
