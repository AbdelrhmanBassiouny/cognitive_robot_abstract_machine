from __future__ import annotations

import datetime as _dt
import operator
import re
from dataclasses import dataclass
from typing import Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import (
    Attribute,
    Call,
    FlatVariable,
    Index,
    MappedVariable,
)
from krrood.entity_query_language.core.variable import (
    InstantiatedVariable,
    Literal,
    Variable,
)
from krrood.entity_query_language.operators.aggregators import (
    Average,
    Count,
    CountAll,
    Max,
    Min,
    Mode,
    MultiMode,
    Sum,
)
from krrood.entity_query_language.operators.comparator import Comparator, not_contains
from krrood.entity_query_language.operators.core_logical_operators import AND, OR, Not
from krrood.entity_query_language.operators.logical_quantifiers import Exists, ForAll
from krrood.entity_query_language.predicate import Verbalizable, Triple
from krrood.entity_query_language.query.operations import (
    GroupedBy,
    Having,
    OrderedBy,
    Where,
)
from krrood.entity_query_language.query.quantifiers import An, ResultQuantifier, The
from krrood.entity_query_language.query.query import Entity, SetOf, Query
from krrood.entity_query_language.verbalization.context import VerbalizationContext, _article
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.rule_analysis import (
    AggregationStatus,
    AntecedentInfo,
    ConsequentBinding,
    RuleAnalyzer,
    RuleStructure,
)
from krrood.entity_query_language.verbalization.utils import (
    _apply_binding_aliases,
    _camel_to_words,
    _ensure_plural,
    _ordinal,
    inflect_engine,
)
from krrood.patterns.code_parsing_utils import get_accessed_attribute_name_in_return_statement_of_property
from krrood.singleton import SingletonMeta

_OP_WORDS = {
    operator.eq: "is",
    operator.ne: "is not",
    operator.lt: "is less than",
    operator.le: "is at most",
    operator.gt: "is greater than",
    operator.ge: "is at least",
    operator.contains: "contains",
    not_contains: "does not contain",
}

_OP_WORDS_COMPACT = {
    operator.eq: "equals",
    operator.ne: "does not equal",
    operator.lt: "less than",
    operator.le: "at most",
    operator.gt: "greater than",
    operator.ge: "at least",
    operator.contains: "contains",
    not_contains: "does not contain",
}

_NEGATED_OP_WORDS = {
    operator.gt: "is not greater than",
    operator.lt: "is not less than",
    operator.ge: "is not at least",
    operator.le: "is not at most",
    operator.eq: "is not",
    operator.ne: "is",
    operator.contains: "does not contain",
    not_contains: "contains",
}

_NEGATED_OP_WORDS_COMPACT = {
    operator.gt: "not greater than",
    operator.lt: "not less than",
    operator.ge: "not at least",
    operator.le: "not at most",
    operator.eq: "does not equal",
    operator.ne: "equals",
    operator.contains: "does not contain",
    not_contains: "contains",
}

_OP_WORDS_TEMPORAL = {
    operator.lt: "is before",
    operator.gt: "is after",
    operator.le: "is no later than",
    operator.ge: "is no earlier than",
    operator.eq: "is at",
    operator.ne: "is not at",
}

_OP_WORDS_TEMPORAL_COMPACT = {
    operator.lt: "before",
    operator.gt: "after",
    operator.le: "no later than",
    operator.ge: "no earlier than",
    operator.eq: "at",
    operator.ne: "not at",
}

_NEGATED_OP_WORDS_TEMPORAL = {
    operator.lt: "is no earlier than",
    operator.gt: "is no later than",
    operator.le: "is after",
    operator.ge: "is before",
    operator.eq: "is not at",
    operator.ne: "is at",
}

_NEGATED_OP_WORDS_TEMPORAL_COMPACT = {
    operator.lt: "no earlier than",
    operator.gt: "no later than",
    operator.le: "after",
    operator.ge: "before",
    operator.eq: "not at",
    operator.ne: "at",
}

# ── Small fragment helpers ──────────────────────────────────────────────────────

def _word(text: str) -> WordFragment:
    return WordFragment(text=text)


def _role(text: str, role: SemanticRole) -> RoleFragment:
    return RoleFragment(text=text, role=role)


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


def _join_with(fragments: list[VerbFragment], separator: str) -> VerbFragment:
    """Join a list of fragments with a plain-text separator."""
    if not fragments:
        return _word("")
    if len(fragments) == 1:
        return fragments[0]
    result: list[VerbFragment] = []
    for i, frag in enumerate(fragments):
        result.append(frag)
        if i < len(fragments) - 1:
            result.append(_word(separator))
    return PhraseFragment(parts=result, separator="")


def _oxford_and(fragments: list[VerbFragment]) -> VerbFragment:
    """Join with Oxford comma: ``a, b, and c``."""
    if len(fragments) == 1:
        return fragments[0]
    head = fragments[:-1]
    tail = fragments[-1]
    parts: list[VerbFragment] = []
    for i, f in enumerate(head):
        parts.append(f)
        parts.append(_word(", "))
    parts.append(_word("and "))
    parts.append(tail)
    return PhraseFragment(parts=parts, separator="")


def _comma_and(fragments: list[VerbFragment]) -> VerbFragment:
    """Join with ``, and `` separator (no Oxford comma)."""
    if len(fragments) == 1:
        return fragments[0]
    parts: list[VerbFragment] = []
    for i, f in enumerate(fragments):
        parts.append(f)
        if i < len(fragments) - 1:
            parts.append(_word(", and "))
    return PhraseFragment(parts=parts, separator="")


def _str(fragment: VerbFragment) -> str:
    """Flatten a VerbFragment to a plain string (no colors) for internal string ops."""
    match fragment:
        case WordFragment(text=t):
            return t
        case RoleFragment(text=t):
            return t
        case PhraseFragment(parts=parts, separator=sep):
            return sep.join(_str(p) for p in parts)
        case BlockFragment(header=header, items=items):
            parts_text = ", ".join(_str(i) for i in items)
            if header is None:
                return parts_text
            return f"{_str(header)} {parts_text}" if parts_text else _str(header)
        case _:
            return ""


@dataclass
class EQLVerbalizer(metaclass=SingletonMeta):
    """
    Visitor-based verbalizer: maps an EQL expression tree to a VerbFragment tree.

    Use :func:`verbalize_expression` for the simple string API, or build a
    :class:`VerbalizationPipeline` to choose format and colour scheme.

    Each ``_v_<ClassName>_`` method handles one node type and returns a
    ``VerbFragment``.  Unknown types fall back to :meth:`_v_default_`.
    """

    # ── Dispatcher ─────────────────────────────────────────────────────────────

    def build(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> VerbFragment:
        if ctx is None:
            ctx = VerbalizationContext.from_expression(expr)
        method = getattr(self, f"_v_{type(expr).__name__}_", self._v_default_)
        return method(expr, ctx)

    def verbalize(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> str:
        """Convenience wrapper — returns a plain string (no colors)."""
        return _str(self.build(expr, ctx))

    # ── Leaves ─────────────────────────────────────────────────────────────────

    def _v_Variable_(self, expr: Variable, ctx: VerbalizationContext) -> VerbFragment:
        noun = ctx.noun_for(expr)
        # noun_for() returns e.g. "a Robot", "the Robot", or "Robot 1"
        # The type name part should carry VARIABLE role; articles are PLAIN.
        parts = noun.split()
        if len(parts) >= 2 and parts[0] in ("a", "an", "the"):
            return _phrase(_word(parts[0]), _role(" ".join(parts[1:]), SemanticRole.VARIABLE))
        return _role(noun, SemanticRole.VARIABLE)

    def _v_Literal_(self, expr: Literal, ctx: VerbalizationContext) -> VerbFragment:
        return _role(ctx.type_name_of_value(expr._value_), SemanticRole.LITERAL)

    def _v_ExternallySetVariable_(self, expr, ctx: VerbalizationContext) -> VerbFragment:
        type_name = expr._type_.__name__ if getattr(expr, "_type_", None) else "variable"
        return _phrase(_word(_article(type_name)), _role(type_name, SemanticRole.VARIABLE))

    # ── MappedVariables ────────────────────────────────────────────────────────

    def _v_Attribute_(self, expr: Attribute, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_mapped_chain_(expr, ctx)

    def _v_Index_(self, expr: Index, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_mapped_chain_(expr, ctx)

    def _v_Call_(self, expr: Call, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_mapped_chain_(expr, ctx)

    def _v_FlatVariable_(self, expr: FlatVariable, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr._child_, ctx)

    def _verbalize_plural_(self, expr, ctx: VerbalizationContext) -> VerbFragment:
        """Return a plural noun VerbFragment for *expr* — used by ForAll and aggregators."""
        if isinstance(expr, FlatVariable):
            return self._verbalize_plural_(expr._child_, ctx)

        if isinstance(expr, Variable):
            type_name = expr._type_.__name__
            label = ctx.disambiguation_map.get(expr._id_, type_name)
            ctx.seen[expr._id_] = label
            plural = label if label != type_name else inflect_engine.plural(type_name)
            return _role(plural, SemanticRole.VARIABLE)

        if isinstance(expr, Attribute):
            chain: list = []
            current = expr
            while isinstance(current, MappedVariable):
                chain.append(current)
                current = current._child_
            root = current
            if isinstance(root, Variable) and len(chain) == 1 and isinstance(chain[0], Attribute):
                type_name = root._type_.__name__
                label = ctx.disambiguation_map.get(root._id_, type_name)
                ctx.seen[root._id_] = label
                root_plural = label if label != type_name else inflect_engine.plural(type_name)
                attr_plural = _ensure_plural(chain[0]._attribute_name_)
                return _phrase(
                    _role(attr_plural, SemanticRole.ATTRIBUTE),
                    _word("of"),
                    _role(root_plural, SemanticRole.VARIABLE),
                )

        return self.build(expr, ctx)

    @staticmethod
    def _walk_chain_(expr: MappedVariable) -> tuple:
        chain: list[MappedVariable] = []
        current = expr
        while isinstance(current, MappedVariable):
            chain.append(current)
            current = current._child_
        chain.reverse()
        return chain, current

    @staticmethod
    def _render_path_(parts: list[str], root_text: str) -> str:
        if not parts:
            return root_text
        inner = " of the ".join(reversed(parts))
        return f"the {inner} of {root_text}"

    def _verbalize_chain_root_(self, leaf, ctx: VerbalizationContext) -> str:
        inner = leaf
        while isinstance(inner, ResultQuantifier):
            inner = inner._child_
        if isinstance(inner, Entity):
            return self._verbalize_entity_as_inline_noun_str_(inner, ctx)
        return self.verbalize(leaf, ctx)

    def _verbalize_chain_root_fragment_(self, leaf, ctx: VerbalizationContext) -> VerbFragment:
        inner = leaf
        while isinstance(inner, ResultQuantifier):
            inner = inner._child_
        if isinstance(inner, Entity):
            return self._verbalize_entity_as_inline_noun_(inner, ctx)
        return self.build(leaf, ctx)

    def _verbalize_mapped_chain_(
        self, expr: MappedVariable, ctx: VerbalizationContext, negated: bool = False
    ) -> VerbFragment:
        chain, leaf = self._walk_chain_(expr)
        root_text = self._verbalize_chain_root_(leaf, ctx)
        terminal = chain[-1]
        if isinstance(terminal, Attribute) and terminal._type_ is bool:
            nav_text = self._verbalize_navigation_chain_(chain[:-1], root_text)
            verb = "is not" if negated else "is"
            attr_name = terminal._attribute_name_
            return _phrase(
                _word(nav_text),
                _role(verb, SemanticRole.OPERATOR),
                _role(attr_name, SemanticRole.ATTRIBUTE),
            )
        path_str = self._render_path_(self._build_path_parts_(chain), root_text)
        # Render the whole path as ATTRIBUTE role — it represents an attribute access chain
        return _role(path_str, SemanticRole.ATTRIBUTE)

    def _verbalize_navigation_chain_(self, nav_chain: list, root_text: str) -> str:
        if not nav_chain:
            return root_text
        if isinstance(nav_chain[-1], Index) and isinstance(nav_chain[-1]._key_, int):
            ordinal = _ordinal(nav_chain[-1]._key_)
            pre_text = self._render_path_(self._build_path_parts_(nav_chain[:-1]), root_text)
            return f"the {ordinal} of {pre_text}"
        return self._render_path_(self._build_path_parts_(nav_chain), root_text)

    def _build_path_parts_(self, chain: list) -> list[str]:
        parts: list[str] = []
        i = 0
        while i < len(chain):
            node = chain[i]
            if isinstance(node, Attribute):
                name = node._attribute_name_
                while i + 1 < len(chain) and isinstance(chain[i + 1], Index):
                    i += 1
                    name += f"[{repr(chain[i]._key_)}]"
                parts.append(name)
            elif isinstance(node, Index):
                parts.append(f"[{repr(node._key_)}]")
            elif isinstance(node, Call):
                parts.append("()")
            elif isinstance(node, FlatVariable):
                pass
            i += 1
        return parts

    # ── Instantiated (predicates / inference variables) ────────────────────────

    def _v_InstantiatedVariable_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext
    ) -> VerbFragment:
        try:
            if isinstance(expr._type_, type) and issubclass(expr._type_, Verbalizable):
                template = expr._type_._verbalization_template_()
                return self._verbalize_template_(expr, ctx, template)
        except NotImplementedError:
            pass
        return self._verbalize_instantiated_natural_(expr, ctx)

    def _verbalize_template_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext, template: str
    ) -> VerbFragment:
        kwargs = {
            name: self.verbalize(child, ctx)
            for name, child in expr._child_vars_.items()
        }
        return _word(template.format(**kwargs))

    def _verbalize_predicate_no_template_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext
    ) -> VerbFragment:
        type_name = getattr(expr._type_, "__name__", str(expr._type_))
        if len(expr._child_vars_) == 2:
            items = list(expr._child_vars_.items())
            left, right = items[0][1], items[1][1]
            predicate_text = _camel_to_words(type_name)
            left_frag = self.build(left, ctx)
            right_frag = self.build(right, ctx)
            return _phrase(left_frag, _word(predicate_text), right_frag)
        if expr._child_vars_:
            args_str = ", ".join(
                f"{name}={self.verbalize(child, ctx)}"
                for name, child in expr._child_vars_.items()
            )
            return _phrase(
                _word(f"{_article(type_name)}"),
                _role(type_name, SemanticRole.VARIABLE),
                _word(f"({args_str})"),
            )
        return _phrase(_word(_article(type_name)), _role(type_name, SemanticRole.VARIABLE))

    def _verbalize_instantiated_natural_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext
    ) -> VerbFragment:
        type_name = getattr(expr._type_, "__name__", str(expr._type_))

        if expr._id_ in ctx.seen:
            return _phrase(_word("the"), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))
        ctx.seen[expr._id_] = type_name

        ctx.push_constraint_frame()

        binding_parts: list[str] = []
        binding_alias_map: dict[str, str] = {}
        for field_name, child_expr in expr._child_vars_.items():
            field_ref = f"the {field_name} of the {type_name}"
            if inflect_engine.singular_noun(field_name):
                plural_value = _str(self._verbalize_plural_(child_expr, ctx))
                binding_parts.append(f"{field_ref} are {plural_value}")
            else:
                value_text = self.verbalize(child_expr, ctx)
                binding_parts.append(f"{field_ref} is {value_text}")
                definite_value = re.sub(r"\b(a|an) ([A-Z])", r"the \2", value_text)
                if re.search(r"\bthe [A-Z]", definite_value) and definite_value not in binding_alias_map:
                    binding_alias_map[definite_value] = field_ref

        constraints = ctx.pop_constraint_frame()
        ctx.binding_aliases.update(binding_alias_map)
        if constraints and binding_alias_map:
            constraints = [_apply_binding_aliases(c, binding_alias_map) for c in constraints]

        result_parts: list[VerbFragment] = [
            _phrase(_word(_article(type_name)), _role(type_name, SemanticRole.VARIABLE))
        ]
        if binding_parts:
            result_parts.append(_word(", where " + " and ".join(binding_parts)))
        if constraints:
            result_parts.append(_word(", such that " + " and ".join(constraints)))
        return PhraseFragment(parts=result_parts, separator="")

    # ── Logical operators ──────────────────────────────────────────────────────

    def _v_AND_(self, expr: AND, ctx: VerbalizationContext) -> VerbFragment:
        parts = [self.build(c, ctx) for c in ctx.flatten_same_type(expr, AND)]
        if len(parts) == 1:
            return parts[0]
        return _oxford_and(parts)

    def _v_OR_(self, expr: OR, ctx: VerbalizationContext) -> VerbFragment:
        parts = [self.build(c, ctx) for c in ctx.flatten_same_type(expr, OR)]
        if len(parts) == 1:
            return parts[0]
        head = ", ".join(_str(p) for p in parts[:-1])
        return _phrase(
            _role("either", SemanticRole.LOGICAL),
            _word(f"{head}, or"),
            parts[-1],
        )

    def _v_Not_(self, expr: Not, ctx: VerbalizationContext) -> VerbFragment:
        child = expr._child_
        if isinstance(child, Comparator):
            left = self.verbalize(child.left, ctx)
            right = self.build(child.right, ctx)
            is_temporal = self._is_temporal_(child.left) or self._is_temporal_(child.right)
            if is_temporal:
                neg_table = _NEGATED_OP_WORDS_TEMPORAL_COMPACT if ctx.compact_predicates else _NEGATED_OP_WORDS_TEMPORAL
                fallback_table = _OP_WORDS_TEMPORAL_COMPACT if ctx.compact_predicates else _OP_WORDS_TEMPORAL
            else:
                neg_table = _NEGATED_OP_WORDS_COMPACT if ctx.compact_predicates else _NEGATED_OP_WORDS
                fallback_table = _OP_WORDS_COMPACT if ctx.compact_predicates else _OP_WORDS
            op_word = neg_table.get(
                child.operation, f"not {fallback_table.get(child.operation, child._name_)}"
            )
            return _phrase(_word(left), _role(op_word, SemanticRole.OPERATOR), right)
        if isinstance(child, MappedVariable):
            chain, _ = self._walk_chain_(child)
            if isinstance(chain[-1], Attribute) and chain[-1]._type_ is bool:
                return self._verbalize_mapped_chain_(child, ctx, negated=True)
        return _phrase(_role("not", SemanticRole.LOGICAL), _word(f"({self.verbalize(child, ctx)})"))

    # ── Quantifiers ────────────────────────────────────────────────────────────

    def _v_ForAll_(self, expr: ForAll, ctx: VerbalizationContext) -> VerbFragment:
        var_frag = self._verbalize_plural_(expr.variable, ctx)
        cond_frag = self.build(expr.condition, ctx)
        return _phrase(_role("for all", SemanticRole.LOGICAL), var_frag, _word(","), cond_frag)

    def _v_Exists_(self, expr: Exists, ctx: VerbalizationContext) -> VerbFragment:
        var_frag = self.build(expr.variable, ctx)
        cond_frag = self.build(expr.condition, ctx)
        return _phrase(
            _role("there exists", SemanticRole.LOGICAL),
            var_frag,
            _word("such that"),
            cond_frag,
        )

    # ── Comparators ────────────────────────────────────────────────────────────

    def _is_temporal_(self, expr) -> bool:
        if isinstance(expr, Literal):
            return isinstance(expr._value_, _dt.datetime)
        if isinstance(expr, Variable):
            return getattr(expr, "_type_", None) is _dt.datetime
        if isinstance(expr, MappedVariable):
            chain, current = [], expr
            while isinstance(current, MappedVariable):
                chain.append(current)
                current = current._child_
            return bool(chain) and getattr(chain[-1], "_type_", None) is _dt.datetime
        return False

    def _v_Comparator_(self, expr: Comparator, ctx: VerbalizationContext) -> VerbFragment:
        left = self.build(expr.left, ctx)
        right = self.build(expr.right, ctx)
        if self._is_temporal_(expr.left) or self._is_temporal_(expr.right):
            table = _OP_WORDS_TEMPORAL_COMPACT if ctx.compact_predicates else _OP_WORDS_TEMPORAL
        else:
            table = _OP_WORDS_COMPACT if ctx.compact_predicates else _OP_WORDS
        op_word = table.get(expr.operation, expr._name_)
        return _phrase(left, _role(op_word, SemanticRole.OPERATOR), right)

    # ── Aggregators ────────────────────────────────────────────────────────────

    def _v_Count_(self, expr: Count, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "number of {}")

    def _v_CountAll_(self, expr: CountAll, ctx: VerbalizationContext) -> VerbFragment:
        return _role("count of all", SemanticRole.AGGREGATION)

    def _v_Sum_(self, expr: Sum, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "sum of {}")

    def _v_Average_(self, expr: Average, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "average of {}")

    def _v_Max_(self, expr: Max, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "maximum {}")

    def _v_Min_(self, expr: Min, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "minimum {}")

    def _v_Mode_(self, expr: Mode, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "mode of {}")

    def _v_MultiMode_(self, expr: MultiMode, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, "all modes of {}")

    def _verbalize_aggregator_(self, expr, ctx: VerbalizationContext, template: str) -> VerbFragment:
        child_frag = self._verbalize_plural_(expr._child_, ctx)
        child_text = _str(child_frag)
        phrase_text = template.format(child_text)
        keyword = phrase_text[: phrase_text.index(child_text)].rstrip()
        if expr._id_ in ctx.seen:
            return _phrase(
                _word("the"),
                _role(keyword, SemanticRole.AGGREGATION),
                child_frag,
            )
        ctx.seen[expr._id_] = phrase_text
        return _phrase(_role(keyword, SemanticRole.AGGREGATION), child_frag)

    # ── Rule (If … then …) verbalization ─────────────────────────────────────

    _rule_analyzer = RuleAnalyzer()

    def _verbalize_rule_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        structure = self._rule_analyzer.analyze(expr)
        if_frag = self._verbalize_rule_if_(structure, ctx)
        then_frag = self._verbalize_rule_then_(structure, ctx)
        return BlockFragment(
            header=None,
            items=[
                BlockFragment(header=_role("If", SemanticRole.KEYWORD), items=if_frag),
                BlockFragment(header=_role("then", SemanticRole.KEYWORD), items=then_frag),
            ],
        )

    def _verbalize_rule_if_(self, s: RuleStructure, ctx: VerbalizationContext) -> list[VerbFragment]:
        for ant in s.secondary_antecedents:
            self._register_antecedent_(ant, ctx)

        items: list[VerbFragment] = []
        for ant in s.primary_antecedents:
            intro = self._antecedent_intro_frag_(ant)
            self._register_antecedent_(ant, ctx)
            cond_frags = self._condition_frags_(ant.conditions, ant, ctx)
            items.append(BlockFragment(header=intro, items=cond_frags) if cond_frags else intro)

        for cond in s.unmatched_conditions:
            items.append(self.build(cond, ctx))

        return items or [_word("true")]

    def _verbalize_rule_then_(self, s: RuleStructure, ctx: VerbalizationContext) -> list[VerbFragment]:
        type_name = s.consequent_type
        intro: VerbFragment = _phrase(
            _word(f"there's {_article(type_name)}"),
            _role(type_name, SemanticRole.VARIABLE),
        )
        binding_frags = [self._verbalize_binding_frag_(b, ctx) for b in s.consequent_bindings]
        if not binding_frags:
            return [intro]
        return [BlockFragment(header=intro, items=binding_frags)]

    def _antecedent_intro_frag_(self, ant: AntecedentInfo) -> VerbFragment:
        if ant.aggregation_status == AggregationStatus.AGGREGATED:
            return _phrase(
                _word("there are"),
                _role(inflect_engine.plural(ant.type_name), SemanticRole.VARIABLE),
            )
        return _phrase(
            _word(f"there's {_article(ant.type_name)}"),
            _role(ant.type_name, SemanticRole.VARIABLE),
        )

    def _register_antecedent_(self, ant: AntecedentInfo, ctx: VerbalizationContext) -> None:
        from krrood.entity_query_language.query.query import Entity as _Entity
        root = ant.root
        ctx.seen[root._id_] = ant.type_name
        if isinstance(root, _Entity):
            root.build()
            sel = root.selected_variable
            if sel is not None and hasattr(sel, "_id_"):
                ctx.seen[sel._id_] = ant.type_name

    def _condition_frags_(
        self, conditions: list, ant: AntecedentInfo, ctx: VerbalizationContext
    ) -> list[VerbFragment]:
        return [
            self._try_whose_from_condition_(cond, ant, ctx) or self.build(cond, ctx)
            for cond in conditions
        ]

    def _try_whose_from_condition_(
        self, cond, ant: AntecedentInfo, ctx: VerbalizationContext
    ) -> Optional[VerbFragment]:
        if not isinstance(cond, Comparator) or cond.operation is not operator.eq:
            return None
        if not isinstance(cond.left, Attribute):
            return None
        attr_names = self._extract_attr_names_(cond.left)
        if not attr_names:
            return None
        aggregated = ant.aggregation_status == AggregationStatus.AGGREGATED
        copula = "are" if aggregated else "is"
        attr_word = _ensure_plural(attr_names[-1]) if aggregated else attr_names[-1]
        right_frag = (
            self._verbalize_plural_(cond.right, ctx) if aggregated else self.build(cond.right, ctx)
        )
        return _phrase(
            _role("whose", SemanticRole.KEYWORD),
            _role(attr_word, SemanticRole.ATTRIBUTE),
            _role(copula, SemanticRole.OPERATOR),
            right_frag,
        )

    @staticmethod
    def _extract_attr_names_(left: Attribute) -> list[str]:
        attr_names: list[str] = []
        current = left
        while isinstance(current, MappedVariable):
            if hasattr(current, "_attribute_name_"):
                attr_names.append(current._attribute_name_)
            current = current._child_
        return attr_names

    def _verbalize_binding_frag_(
        self, binding: ConsequentBinding, ctx: VerbalizationContext
    ) -> VerbFragment:
        copula = "are" if binding.is_plural_field else "is"
        field_text = _ensure_plural(binding.field_name) if binding.is_plural_field else binding.field_name
        return _phrase(
            _role("whose", SemanticRole.KEYWORD),
            _role(field_text, SemanticRole.ATTRIBUTE),
            _role(copula, SemanticRole.OPERATOR),
            self._binding_value_frag_(binding, ctx),
        )

    def _binding_value_frag_(
        self, binding: ConsequentBinding, ctx: VerbalizationContext
    ) -> VerbFragment:
        if binding.is_plural_field and binding.aggregation_status == AggregationStatus.AGGREGATED:
            return _phrase(_word("the"), self._verbalize_plural_(binding.value_expr, ctx))
        if binding.is_plural_field:
            return self._verbalize_plural_(binding.value_expr, ctx)
        if binding.aggregation_status == AggregationStatus.GROUP_KEY:
            return _word(self._verbalize_group_key_value_(binding.value_expr, ctx))
        return self.build(binding.value_expr, ctx)

    def _verbalize_group_key_value_(self, expr, ctx: VerbalizationContext) -> str:
        from krrood.entity_query_language.core.mapped_variable import MappedVariable
        from krrood.entity_query_language.core.variable import Variable

        chain: list = []
        current = expr
        while isinstance(current, MappedVariable):
            chain.append(current)
            current = current._child_
        chain.reverse()

        if not chain or not isinstance(current, Variable):
            return self.verbalize(expr, ctx)

        root_type = current._type_.__name__ if getattr(current, "_type_", None) else "entity"
        root_plural = inflect_engine.plural(root_type)
        ctx.seen[current._id_] = root_type

        parts = self._build_path_parts_(chain)
        if not parts:
            return f"the common {root_type} of the {root_plural}"

        outermost = list(reversed(parts))[0]
        return f"the common {outermost} of the {root_plural}"

    # ── Query: Entity and SetOf ────────────────────────────────────────────────

    def _v_Entity_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if expr._id_ in ctx.seen:
            return _phrase(_word("the"), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

        expr.build()

        if self._rule_analyzer.can_handle(expr):
            return self._verbalize_rule_(expr, ctx)

        is_the = (
            expr._quantifier_builder_ is not None
            and expr._quantifier_builder_.type is The
        )
        var = expr.selected_variable

        if isinstance(var, Entity):
            selected = self._verbalize_entity_as_noun_(var, ctx)
        elif var is None:
            selected_type = "entity"
            ctx.seen[expr._id_] = selected_type
            selected = _word("entities")
        elif is_the:
            selected_type = var._type_.__name__ if getattr(var, "_type_", None) else "entity"
            ctx.seen[var._id_] = selected_type
            ctx.seen[expr._id_] = selected_type
            selected = _phrase(_word("the unique"), _role(selected_type, SemanticRole.VARIABLE))
        else:
            selected = self.build(var, ctx)
            selected_type = ctx.seen.get(getattr(var, "_id_", None), "entity")
            ctx.seen[expr._id_] = selected_type

        return self._verbalize_query_body_(expr, ctx, selected)

    def _verbalize_entity_as_noun_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if expr._id_ in ctx.seen:
            return _phrase(_word("the"), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

        expr.build()
        is_the = (
            expr._quantifier_builder_ is not None
            and expr._quantifier_builder_.type is The
        )
        var = expr.selected_variable
        selected_type = var._type_.__name__ if var and getattr(var, "_type_", None) else "entity"

        ctx.seen[expr._id_] = selected_type
        if var is not None:
            ctx.seen[var._id_] = selected_type

        if is_the:
            article_noun: VerbFragment = _phrase(
                _word("the unique"), _role(selected_type, SemanticRole.VARIABLE)
            )
        else:
            article_noun = _phrase(
                _word(_article(selected_type)), _role(selected_type, SemanticRole.VARIABLE)
            )

        where_expr = expr._where_expression_
        if where_expr is not None:
            cond = self.verbalize(where_expr.condition, ctx)
            return _phrase(article_noun, _role("where", SemanticRole.KEYWORD), _word(cond))
        return article_noun

    def _verbalize_entity_as_inline_noun_str_(self, entity: Entity, ctx: VerbalizationContext) -> str:
        return _str(self._verbalize_entity_as_inline_noun_(entity, ctx))

    def _verbalize_entity_as_inline_noun_(self, entity: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if entity._id_ in ctx.seen:
            return _phrase(_word("the"), _role(ctx.seen[entity._id_], SemanticRole.VARIABLE))

        entity.build()
        var = entity.selected_variable
        type_name = var._type_.__name__ if var and getattr(var, "_type_", None) else "entity"

        ctx.seen[entity._id_] = type_name
        if var is not None and hasattr(var, "_id_"):
            ctx.seen[var._id_] = type_name

        where_expr = entity._where_expression_
        if where_expr is not None:
            cond_text = self.verbalize(where_expr.condition, ctx)
            ctx.add_constraint(cond_text)

        return _phrase(_word(_article(type_name)), _role(type_name, SemanticRole.VARIABLE))

    def _v_SetOf_(self, expr: SetOf, ctx: VerbalizationContext) -> VerbFragment:
        expr.build()
        vars_str = ", ".join(self.verbalize(v, ctx) for v in expr._selected_variables_)
        prefix = _word(f"Find sets of ({vars_str})")
        return self._verbalize_query_body_(expr, ctx, prefix)

    @staticmethod
    def combine_in_a_bracket(parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return f"({EQLVerbalizer.combine(parts, 'and')})"

    @staticmethod
    def combine(parts: list[str], conjunction: str = "and") -> str:
        if len(parts) == 1:
            return parts[0]
        conjunction = f" {conjunction} " if conjunction else " "
        return ", ".join(parts[:-1]) + f",{conjunction}{parts[-1]}"

    def _verbalize_query_body_(self, expr, ctx: VerbalizationContext, selection: VerbFragment) -> VerbFragment:
        """Build a BlockFragment for a query: Find … | Where … | Grouped by … | Having … | Ordered by …"""
        find_header = _phrase(_role("Find", SemanticRole.KEYWORD), selection)

        where_expr = expr._where_expression_
        grouped_expr = expr._grouped_by_expression_
        having_expr = expr._having_expression_
        aliases = ctx.binding_aliases

        clauses: list[VerbFragment] = []

        if where_expr is not None:
            where_text = _apply_binding_aliases(self.verbalize(where_expr.condition, ctx), aliases)
            clauses.append(_phrase(
                _role("such that", SemanticRole.KEYWORD),
                _word(where_text),
            ))

        if grouped_expr is not None and grouped_expr.variables_to_group_by:
            group_key_root_ids = self._root_var_ids_(grouped_expr.variables_to_group_by)
            groups = [
                _apply_binding_aliases(self.verbalize(v, ctx), aliases)
                for v in grouped_expr.variables_to_group_by
            ]
            aggregated = self._aggregated_noun_phrases_(expr, group_key_root_ids, ctx)
            groups_str = self.combine_in_a_bracket(groups)
            if aggregated:
                aggregated_str = self.combine(aggregated, "")
                clauses.append(_phrase(
                    _word(f"and the {aggregated_str} are"),
                    _role("grouped by", SemanticRole.KEYWORD),
                    _word(groups_str),
                ))
            else:
                clauses.append(_phrase(
                    _role("grouped by", SemanticRole.KEYWORD),
                    _word(groups_str),
                ))

        if having_expr is not None:
            ctx.compact_predicates = True
            having_text = _apply_binding_aliases(self.verbalize(having_expr.condition, ctx), aliases)
            ctx.compact_predicates = False
            clauses.append(_phrase(
                _role("having", SemanticRole.KEYWORD),
                _word(having_text),
            ))

        ob = expr._ordered_by_builder_
        if ob is not None:
            direction = "descending" if ob.descending else "ascending"
            ordered_text = _apply_binding_aliases(self.verbalize(ob.variable, ctx), aliases)
            clauses.append(_phrase(
                _role("ordered by", SemanticRole.KEYWORD),
                _word(f"{ordered_text} ({direction})"),
            ))

        return BlockFragment(header=find_header, items=clauses)

    # ── Result quantifiers (transparent wrappers) ──────────────────────────────

    def _v_An_(self, expr: An, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr._child_, ctx)

    def _v_The_(self, expr: The, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr._child_, ctx)

    def _v_ResultQuantifier_(self, expr: ResultQuantifier, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr._child_, ctx)

    # ── Filter wrappers ────────────────────────────────────────────────────────

    def _v_Where_(self, expr: Where, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr.condition, ctx)

    def _v_Having_(self, expr: Having, ctx: VerbalizationContext) -> VerbFragment:
        return self.build(expr.condition, ctx)

    def _v_GroupedBy_(self, expr: GroupedBy, ctx: VerbalizationContext) -> VerbFragment:
        if expr.variables_to_group_by:
            groups = [self.verbalize(v, ctx) for v in expr.variables_to_group_by]
            return _phrase(_role("grouped by", SemanticRole.KEYWORD), _word(", ".join(groups)))
        return _role("grouped", SemanticRole.KEYWORD)

    def _v_OrderedBy_(self, expr: OrderedBy, ctx: VerbalizationContext) -> VerbFragment:
        direction = "descending" if expr.descending else "ascending"
        return _phrase(
            _role("ordered by", SemanticRole.KEYWORD),
            _word(f"{self.verbalize(expr.variable, ctx)} ({direction})"),
        )

    # ── Grouped-by helpers ─────────────────────────────────────────────────────

    def _root_var_ids_(self, exprs) -> set:
        ids: set = set()
        for e in exprs:
            current = e
            while isinstance(current, MappedVariable):
                current = current._child_
            if isinstance(current, Variable):
                ids.add(current._id_)
        return ids

    def _aggregated_noun_phrases_(
        self, query_expr, group_key_root_ids: set, ctx: VerbalizationContext
    ) -> list[str]:
        from krrood.entity_query_language.query.query import Entity
        from krrood.entity_query_language.core.variable import InstantiatedVariable

        texts: list[str] = []
        selected_var = query_expr.selected_variable if isinstance(query_expr, Entity) else None

        if isinstance(selected_var, InstantiatedVariable):
            for child_expr in selected_var._child_vars_.values():
                root = child_expr
                while isinstance(root, MappedVariable):
                    root = root._child_
                if isinstance(root, Variable) and root._id_ in group_key_root_ids:
                    continue
                texts.append(_str(self._verbalize_plural_(child_expr, ctx)))
        elif isinstance(query_expr, Query):
            for var in query_expr._selected_variables_:
                if var._id_ not in group_key_root_ids:
                    texts.append(_str(self._verbalize_plural_(var, ctx)))

        return texts

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _v_default_(self, expr: SymbolicExpression, ctx: VerbalizationContext) -> VerbFragment:
        return _word(expr._name_)


_default_verbalizer = EQLVerbalizer()


def verbalize_expression(expr) -> str:
    """
    Verbalize any EQL expression into a human-readable English phrase (plain text).

    For colored or hierarchical output use :class:`VerbalizationPipeline`.
    """
    if isinstance(expr, Query):
        expr.build()
    return _default_verbalizer.verbalize(expr)
