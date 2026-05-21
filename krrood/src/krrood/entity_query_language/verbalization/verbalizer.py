from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

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
from krrood.entity_query_language.operators.comparator import Comparator
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
from krrood.entity_query_language.verbalization.context import (
    ArticleSelection,
    VerbalizationContext,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef
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
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Aggregations,
    Articles,
    Conjunctions,
    Copulas,
    ExistentialPhrase,
    FallbackNouns,
    GroupKeyPhrases,
    Keywords,
    Logicals,
    Operators,
    Prepositions,
    SortDirections,
)
from krrood.patterns.code_parsing_utils import get_accessed_attribute_name_in_return_statement_of_property

# ── Small fragment helpers ──────────────────────────────────────────────────────

def _word(text: str) -> WordFragment:
    return WordFragment(text=text)


def _role(
    text: str,
    role: SemanticRole,
    source_ref: Optional[SourceRef] = None,
) -> RoleFragment:
    return RoleFragment(text=text, role=role, source_ref=source_ref)


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


def _join_with(fragments: list[VerbFragment], separator: str) -> VerbFragment:
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


def _oxford_and(fragments: list[VerbFragment], conjunction: WordFragment) -> VerbFragment:
    """Join with Oxford comma: a, b, and c."""
    if len(fragments) == 1:
        return fragments[0]
    head = fragments[:-1]
    tail = fragments[-1]
    parts: list[VerbFragment] = []
    for f in head:
        parts.append(f)
        parts.append(_word(", "))
    parts.append(PhraseFragment(parts=[conjunction, tail], separator=" "))
    return PhraseFragment(parts=parts, separator="")


def _str(fragment: VerbFragment) -> str:
    """Flatten a VerbFragment to a plain string (no colours) for internal string ops."""
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
class EQLVerbalizer:
    """
    Visitor-based verbalizer: maps an EQL expression tree to a VerbFragment tree.

    Use verbalize_expression() for the simple string API, or build a
    VerbalizationPipeline to choose format and colour scheme.

    Each _v_<ClassName>_ method handles one node type. Unknown types fall back
    to _v_default_.  The dispatch table is built in __post_init__ from bound
    method references so no getattr is needed in the hot path.
    """

    _dispatch: dict[type, Callable] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._dispatch = {
            Variable:             self._v_Variable_,
            Literal:              self._v_Literal_,
            Attribute:            self._v_Attribute_,
            Index:                self._v_Index_,
            Call:                 self._v_Call_,
            FlatVariable:         self._v_FlatVariable_,
            InstantiatedVariable: self._v_InstantiatedVariable_,
            AND:                  self._v_AND_,
            OR:                   self._v_OR_,
            Not:                  self._v_Not_,
            ForAll:               self._v_ForAll_,
            Exists:               self._v_Exists_,
            Comparator:           self._v_Comparator_,
            Count:                self._v_Count_,
            CountAll:             self._v_CountAll_,
            Sum:                  self._v_Sum_,
            Average:              self._v_Average_,
            Max:                  self._v_Max_,
            Min:                  self._v_Min_,
            Mode:                 self._v_Mode_,
            MultiMode:            self._v_MultiMode_,
            Entity:               self._v_Entity_,
            SetOf:                self._v_SetOf_,
            An:                   self._v_An_,
            The:                  self._v_The_,
            ResultQuantifier:     self._v_ResultQuantifier_,
            Where:                self._v_Where_,
            Having:               self._v_Having_,
            GroupedBy:            self._v_GroupedBy_,
            OrderedBy:            self._v_OrderedBy_,
        }

    # ── Dispatcher ─────────────────────────────────────────────────────────────

    def build(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> VerbFragment:
        if ctx is None:
            ctx = VerbalizationContext.from_expression(expr)
        return self._dispatch.get(type(expr), self._v_default_)(expr, ctx)

    def verbalize(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> str:
        return _str(self.build(expr, ctx))

    # ── Leaves ─────────────────────────────────────────────────────────────────

    def _v_Variable_(self, expr: Variable, ctx: VerbalizationContext) -> VerbFragment:
        article, label = ctx.noun_for_parts(expr)
        ref = SourceRef(cls=expr._type_) if isinstance(expr._type_, type) else None
        label_frag = _role(label, SemanticRole.VARIABLE, ref)
        if article == ArticleSelection.NONE:
            return label_frag
        if article == ArticleSelection.DEFINITE:
            return _phrase(Articles.THE.as_fragment(), label_frag)
        return _phrase(Articles.indefinite(label), label_frag)

    def _v_Literal_(self, expr: Literal, ctx: VerbalizationContext) -> VerbFragment:
        return _role(ctx.type_name_of_value(expr._value_), SemanticRole.LITERAL)

    def _v_ExternallySetVariable_(self, expr, ctx: VerbalizationContext) -> VerbFragment:
        type_name = expr._type_.__name__ if getattr(expr, "_type_", None) else "variable"
        return _phrase(Articles.indefinite(type_name), _role(type_name, SemanticRole.VARIABLE))

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
        match expr:
            case FlatVariable():
                return self._verbalize_plural_(expr._child_, ctx)

            case Variable():
                type_name = expr._type_.__name__
                label = ctx.disambiguation_map.get(expr._id_, type_name)
                ctx.seen[expr._id_] = label
                plural = label if label != type_name else inflect_engine.plural(type_name)
                ref = SourceRef(cls=expr._type_) if isinstance(expr._type_, type) else None
                return _role(plural, SemanticRole.VARIABLE, ref)

            case Attribute():
                chain: list = []
                current = expr
                while isinstance(current, MappedVariable):
                    chain.append(current)
                    current = current._child_
                root = current
                if isinstance(root, Variable) and len(chain) == 1:
                    type_name = root._type_.__name__
                    label = ctx.disambiguation_map.get(root._id_, type_name)
                    ctx.seen[root._id_] = label
                    root_plural = label if label != type_name else inflect_engine.plural(type_name)
                    attr_name = chain[0]._attribute_name_
                    attr_plural = _ensure_plural(attr_name)
                    owner = chain[0]._owner_class_
                    attr_ref = SourceRef(cls=owner, attribute=attr_name) if isinstance(owner, type) else None
                    root_ref = SourceRef(cls=root._type_) if isinstance(root._type_, type) else None
                    return _phrase(
                        _role(attr_plural, SemanticRole.ATTRIBUTE, attr_ref),
                        Prepositions.OF.as_fragment(),
                        _role(root_plural, SemanticRole.VARIABLE, root_ref),
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

    def _render_path_(self, parts: list[tuple[str, Optional[SourceRef]]], root_text: str) -> str:
        if not parts:
            return root_text
        of_the = Prepositions.OF_THE.text
        of_ = Prepositions.OF.text
        the = Articles.THE.text
        inner = f" {of_the} ".join(reversed([name for name, _ in parts]))
        return f"{the} {inner} {of_} {root_text}"

    def _render_path_fragment_(
        self, parts: list[tuple[str, Optional[SourceRef]]], root_frag: VerbFragment
    ) -> VerbFragment:
        if not parts:
            return root_frag
        reversed_parts = list(reversed(parts))
        first_name, first_ref = reversed_parts[0]
        frag_parts: list[VerbFragment] = [
            Articles.THE.as_fragment(),
            _role(first_name, SemanticRole.ATTRIBUTE, first_ref),
        ]
        for attr_name, attr_ref in reversed_parts[1:]:
            frag_parts.extend([
                Prepositions.OF_THE.as_fragment(),
                _role(attr_name, SemanticRole.ATTRIBUTE, attr_ref),
            ])
        frag_parts.extend([Prepositions.OF.as_fragment(), root_frag])
        return PhraseFragment(parts=frag_parts, separator=" ")

    def _verbalize_chain_root_(self, leaf, ctx: VerbalizationContext) -> str:
        inner = leaf
        while isinstance(inner, ResultQuantifier):
            inner = inner._child_
        if isinstance(inner, Entity):
            return _str(self._verbalize_entity_as_inline_noun_(inner, ctx))
        return self.verbalize(leaf, ctx)

    def _verbalize_chain_root_fragment_(self, leaf, ctx: VerbalizationContext) -> VerbFragment:
        """
        Return a :class:`VerbFragment` noun phrase for the root of an attribute chain.

        Unwraps any :class:`ResultQuantifier` wrappers, then delegates to
        :meth:`_verbalize_entity_as_inline_noun_` for :class:`Entity` roots or
        :meth:`build` for plain variables.

        This is the canonical entry point for the non-boolean attribute path in
        :meth:`_verbalize_mapped_chain_`. It must be the *first* call that touches
        *leaf* via :meth:`~VerbalizationContext.noun_for` so that the indefinite article
        (``"a"`` / ``"an"``) is used on first mention.

        :param leaf: The root expression at the bottom of the MappedVariable chain.
        :param ctx: The active verbalization context.
        :return: A :class:`VerbFragment` noun phrase for *leaf*.
        """
        inner = leaf
        while isinstance(inner, ResultQuantifier):
            inner = inner._child_
        if isinstance(inner, Entity):
            return self._verbalize_entity_as_inline_noun_(inner, ctx)
        return self.build(leaf, ctx)

    def _verbalize_bool_attribute_chain_(
        self, chain: list, leaf, ctx: VerbalizationContext, negated: bool
    ) -> VerbFragment:
        """
        Verbalize an attribute chain whose terminal attribute has type :class:`bool`.

        Produces predicative sentences of the form ``"<navigation path> is <attr>"``
        or ``"<navigation path> is not <attr>"`` rather than the possessive
        ``"the <attr> of <root>"`` form used for non-boolean attributes.

        :param chain: The full attribute chain (outermost node first) as returned by
            :meth:`_walk_chain_`.  The last element is the terminal boolean
            :class:`Attribute`.
        :param leaf: The root expression at the bottom of the chain (the variable being
            navigated from).
        :param ctx: The active verbalization context.  *leaf* will be registered in
            ``ctx.seen`` as a side-effect of this call.
        :param negated: When ``True`` the copula is rendered as ``"is not"`` instead
            of ``"is"``.
        :return: A :class:`VerbFragment` of the form
            ``"<nav-path> is [not] <attribute-name>"``.
        """
        root_text = self._verbalize_chain_root_(leaf, ctx)
        nav_text = self._verbalize_navigation_chain_(chain[:-1], root_text)
        copula = Copulas.IS_NOT.as_fragment() if negated else Copulas.IS.as_fragment()
        terminal = chain[-1]
        attr_name = terminal._attribute_name_
        owner = terminal._owner_class_
        ref = SourceRef(cls=owner, attribute=attr_name) if isinstance(owner, type) else None
        return _phrase(_word(nav_text), copula, _role(attr_name, SemanticRole.ATTRIBUTE, ref))

    def _verbalize_mapped_chain_(
        self, expr: MappedVariable, ctx: VerbalizationContext, negated: bool = False
    ) -> VerbFragment:
        """
        Verbalize a :class:`MappedVariable` attribute chain into a :class:`VerbFragment`.

        Dispatches to one of two sub-paths depending on the terminal node type:

        - **Boolean terminal** — delegates to :meth:`_verbalize_bool_attribute_chain_`,
          which produces ``"<path> is [not] <attr>"``.
        - **Non-boolean terminal** — calls :meth:`_verbalize_chain_root_fragment_` once
          to obtain the root noun phrase (with the correct indefinite article on first
          mention) and then wraps it with the possessive path via
          :meth:`_render_path_fragment_`.

        .. important::
            :meth:`_verbalize_chain_root_` must **not** be called in the non-boolean
            path.  It would register *leaf* in ``ctx.seen`` before
            :meth:`_verbalize_chain_root_fragment_` runs, causing the root to receive
            the definite article ``"the"`` on what is actually its first mention.

        :param expr: The outermost :class:`MappedVariable` of the chain.
        :param ctx: The active verbalization context.
        :param negated: Passed through to :meth:`_verbalize_bool_attribute_chain_` when
            the terminal attribute is boolean.
        :return: A :class:`VerbFragment` representing the full chain.
        """
        chain, leaf = self._walk_chain_(expr)
        terminal = chain[-1]
        if isinstance(terminal, Attribute) and terminal._type_ is bool:
            return self._verbalize_bool_attribute_chain_(chain, leaf, ctx, negated)
        root_frag = self._verbalize_chain_root_fragment_(leaf, ctx)
        return self._render_path_fragment_(self._build_path_parts_(chain), root_frag)

    def _verbalize_navigation_chain_(self, nav_chain: list, root_text: str) -> str:
        if not nav_chain:
            return root_text
        if isinstance(nav_chain[-1], Index) and isinstance(nav_chain[-1]._key_, int):
            ordinal = _ordinal(nav_chain[-1]._key_)
            pre_text = self._render_path_(self._build_path_parts_(nav_chain[:-1]), root_text)
            the = Articles.THE.text
            of_ = Prepositions.OF.text
            return f"{the} {ordinal} {of_} {pre_text}"
        return self._render_path_(self._build_path_parts_(nav_chain), root_text)

    def _build_path_parts_(self, chain: list) -> list[tuple[str, Optional[SourceRef]]]:
        parts: list[tuple[str, Optional[SourceRef]]] = []
        i = 0
        while i < len(chain):
            node = chain[i]
            match node:
                case Attribute():
                    name = node._attribute_name_
                    owner = node._owner_class_
                    ref: Optional[SourceRef] = (
                        SourceRef(cls=owner, attribute=name) if isinstance(owner, type) else None
                    )
                    while i + 1 < len(chain) and isinstance(chain[i + 1], Index):
                        i += 1
                        name += f"[{repr(chain[i]._key_)}]"
                        ref = None  # composite indexed access has no clean single-line anchor
                    parts.append((name, ref))
                case Index():
                    parts.append((f"[{repr(node._key_)}]", None))
                case Call():
                    parts.append(("()", None))
                case FlatVariable():
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
        kwargs = {name: self.verbalize(child, ctx) for name, child in expr._child_vars_.items()}
        return _word(template.format(**kwargs))

    def _verbalize_predicate_no_template_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext
    ) -> VerbFragment:
        type_name = getattr(expr._type_, "__name__", str(expr._type_))
        ref = SourceRef(cls=expr._type_) if isinstance(expr._type_, type) else None
        if len(expr._child_vars_) == 2:
            items = list(expr._child_vars_.items())
            left, right = items[0][1], items[1][1]
            predicate_text = _camel_to_words(type_name)
            return _phrase(self.build(left, ctx), _word(predicate_text), self.build(right, ctx))
        if expr._child_vars_:
            args_str = ", ".join(
                f"{name}={self.verbalize(child, ctx)}" for name, child in expr._child_vars_.items()
            )
            return _phrase(
                Articles.indefinite(type_name),
                _role(type_name, SemanticRole.VARIABLE, ref),
                _word(f"({args_str})"),
            )
        return _phrase(Articles.indefinite(type_name), _role(type_name, SemanticRole.VARIABLE, ref))

    def _verbalize_instantiated_natural_(
        self, expr: InstantiatedVariable, ctx: VerbalizationContext
    ) -> VerbFragment:
        type_name = getattr(expr._type_, "__name__", str(expr._type_))

        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))
        ctx.seen[expr._id_] = type_name

        ctx.push_constraint_frame()

        _the = Articles.THE.text
        _is = Copulas.IS.text
        _are = Copulas.ARE.text
        _where = Keywords.WHERE.text
        _such_that = Keywords.SUCH_THAT.text
        _and = Conjunctions.AND.text
        _of = Prepositions.OF.text

        binding_parts: list[str] = []
        binding_alias_map: dict[str, str] = {}
        for field_name, child_expr in expr._child_vars_.items():
            field_ref = f"{_the} {field_name} {_of} {_the} {type_name}"
            if inflect_engine.singular_noun(field_name):
                plural_value = _str(self._verbalize_plural_(child_expr, ctx))
                binding_parts.append(f"{field_ref} {_are} {plural_value}")
            else:
                value_text = self.verbalize(child_expr, ctx)
                binding_parts.append(f"{field_ref} {_is} {value_text}")
                _the_pat = re.escape(_the)
                definite_value = re.sub(r"\b(a|an) ([A-Z])", rf"{_the} \2", value_text)
                if re.search(rf"\b{_the_pat} [A-Z]", definite_value) and definite_value not in binding_alias_map:
                    binding_alias_map[definite_value] = field_ref

        constraints = ctx.pop_constraint_frame()
        ctx.binding_aliases.update(binding_alias_map)
        if constraints and binding_alias_map:
            constraints = [_apply_binding_aliases(c, binding_alias_map) for c in constraints]

        inst_ref = SourceRef(cls=expr._type_) if isinstance(expr._type_, type) else None
        result_parts: list[VerbFragment] = [
            _phrase(Articles.indefinite(type_name), _role(type_name, SemanticRole.VARIABLE, inst_ref))
        ]
        if binding_parts:
            result_parts.append(_word(f", {_where} " + f" {_and} ".join(binding_parts)))
        if constraints:
            result_parts.append(_word(f", {_such_that} " + f" {_and} ".join(constraints)))
        return PhraseFragment(parts=result_parts, separator="")

    # ── Logical operators ──────────────────────────────────────────────────────

    def _v_AND_(self, expr: AND, ctx: VerbalizationContext) -> VerbFragment:
        parts = [self.build(c, ctx) for c in ctx.flatten_same_type(expr, AND)]
        if len(parts) == 1:
            return parts[0]
        return _oxford_and(parts, Conjunctions.AND.as_fragment())

    def _v_OR_(self, expr: OR, ctx: VerbalizationContext) -> VerbFragment:
        parts = [self.build(c, ctx) for c in ctx.flatten_same_type(expr, OR)]
        if len(parts) == 1:
            return parts[0]
        head = ", ".join(_str(p) for p in parts[:-1])
        return _phrase(
            Logicals.EITHER.as_fragment(),
            _word(f"{head},"),
            Conjunctions.OR.as_fragment(),
            parts[-1],
        )

    def _v_Not_(self, expr: Not, ctx: VerbalizationContext) -> VerbFragment:
        child = expr._child_
        if isinstance(child, Comparator):
            left = self.verbalize(child.left, ctx)
            right = self.build(child.right, ctx)
            is_temporal = self._is_temporal_(child.left) or self._is_temporal_(child.right)
            try:
                op_frag = Operators.from_callable(child.operation).select(
                    negated=True, compact=ctx.compact_predicates, temporal=is_temporal
                ).as_fragment()
            except KeyError:
                op_frag = _role(f"not {child._name_}", SemanticRole.OPERATOR)
            return _phrase(_word(left), op_frag, right)
        if isinstance(child, MappedVariable):
            chain, _ = self._walk_chain_(child)
            if isinstance(chain[-1], Attribute) and chain[-1]._type_ is bool:
                return self._verbalize_mapped_chain_(child, ctx, negated=True)
        return _phrase(Logicals.NOT.as_fragment(), _word(f"({self.verbalize(child, ctx)})"))

    # ── Quantifiers ────────────────────────────────────────────────────────────

    def _v_ForAll_(self, expr: ForAll, ctx: VerbalizationContext) -> VerbFragment:
        var_frag = self._verbalize_plural_(expr.variable, ctx)
        cond_frag = self.build(expr.condition, ctx)
        return _phrase(Logicals.FOR_ALL.as_fragment(), var_frag, _word(","), cond_frag)

    def _v_Exists_(self, expr: Exists, ctx: VerbalizationContext) -> VerbFragment:
        var_frag = self.build(expr.variable, ctx)
        cond_frag = self.build(expr.condition, ctx)
        return _phrase(
            Logicals.THERE_EXISTS.as_fragment(),
            var_frag,
            Keywords.SUCH_THAT.as_fragment(),
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
        is_temporal = self._is_temporal_(expr.left) or self._is_temporal_(expr.right)
        try:
            op_frag = Operators.from_callable(expr.operation).select(
                compact=ctx.compact_predicates, temporal=is_temporal
            ).as_fragment()
        except KeyError:
            op_frag = _role(expr._name_, SemanticRole.OPERATOR)
        return _phrase(left, op_frag, right)

    # ── Aggregators ────────────────────────────────────────────────────────────

    def _v_Count_(self, expr: Count, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.COUNT)

    def _v_CountAll_(self, expr: CountAll, ctx: VerbalizationContext) -> VerbFragment:
        return Aggregations.COUNT_ALL.as_fragment()

    def _v_Sum_(self, expr: Sum, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.SUM)

    def _v_Average_(self, expr: Average, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.AVERAGE)

    def _v_Max_(self, expr: Max, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.MAX)

    def _v_Min_(self, expr: Min, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.MIN)

    def _v_Mode_(self, expr: Mode, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.MODE)

    def _v_MultiMode_(self, expr: MultiMode, ctx: VerbalizationContext) -> VerbFragment:
        return self._verbalize_aggregator_(expr, ctx, Aggregations.MULTI_MODE)

    def _verbalize_aggregator_(self, expr, ctx: VerbalizationContext, agg: Aggregations) -> VerbFragment:
        child_frag = self._verbalize_plural_(expr._child_, ctx)
        agg_frag = agg.as_fragment()
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), agg_frag, child_frag)
        ctx.seen[expr._id_] = _str(_phrase(agg_frag, child_frag))
        return _phrase(agg_frag, child_frag)

    # ── Rule (If … then …) verbalization ──────────────────────────────────────

    _rule_analyzer = RuleAnalyzer()

    def _verbalize_rule_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        structure = self._rule_analyzer.analyze(expr)
        if_frag = self._verbalize_rule_if_(structure, ctx)
        then_frag = self._verbalize_rule_then_(structure, ctx)
        return BlockFragment(
            header=None,
            items=[
                BlockFragment(header=Keywords.IF.as_fragment(), items=if_frag),
                BlockFragment(header=Keywords.THEN.as_fragment(), items=then_frag),
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

        return items or [Keywords.TRUE.as_fragment()]

    def _verbalize_rule_then_(self, s: RuleStructure, ctx: VerbalizationContext) -> list[VerbFragment]:
        type_name = s.consequent_type
        intro: VerbFragment = ExistentialPhrase.THERE_IS_A.build_phrase(type_name)
        binding_frags = [self._verbalize_binding_frag_(b, ctx) for b in s.consequent_bindings]
        if not binding_frags:
            return [intro]
        return [BlockFragment(header=intro, items=binding_frags)]

    def _antecedent_intro_frag_(self, ant: AntecedentInfo) -> VerbFragment:
        if ant.aggregation_status == AggregationStatus.AGGREGATED:
            return ExistentialPhrase.THERE_ARE.build_phrase(ant.type_name)
        return ExistentialPhrase.THERE_IS_A.build_phrase(ant.type_name)

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
        import operator
        if not isinstance(cond, Comparator) or cond.operation is not operator.eq:
            return None
        if not isinstance(cond.left, Attribute):
            return None
        attr_names = self._extract_attr_names_(cond.left)
        if not attr_names:
            return None
        aggregated = ant.aggregation_status == AggregationStatus.AGGREGATED
        attr_word = _ensure_plural(attr_names[-1]) if aggregated else attr_names[-1]
        right_frag = (
            self._verbalize_plural_(cond.right, ctx) if aggregated else self.build(cond.right, ctx)
        )
        return _phrase(
            Keywords.WHOSE.as_fragment(),
            _role(attr_word, SemanticRole.ATTRIBUTE),
            Copulas.ARE.as_fragment() if aggregated else Copulas.IS.as_fragment(),
            right_frag,
        )

    @staticmethod
    def _extract_attr_names_(left: Attribute) -> list[str]:
        attr_names: list[str] = []
        current = left
        while isinstance(current, MappedVariable):
            if isinstance(current, Attribute):
                attr_names.append(current._attribute_name_)
            current = current._child_
        return attr_names

    def _verbalize_binding_frag_(
        self, binding: ConsequentBinding, ctx: VerbalizationContext
    ) -> VerbFragment:
        field_text = _ensure_plural(binding.field_name) if binding.is_plural_field else binding.field_name
        return _phrase(
            Keywords.WHOSE.as_fragment(),
            _role(field_text, SemanticRole.ATTRIBUTE),
            Copulas.ARE.as_fragment() if binding.is_plural_field else Copulas.IS.as_fragment(),
            self._binding_value_frag_(binding, ctx),
        )

    def _binding_value_frag_(
        self, binding: ConsequentBinding, ctx: VerbalizationContext
    ) -> VerbFragment:
        if binding.is_plural_field and binding.aggregation_status == AggregationStatus.AGGREGATED:
            return _phrase(Articles.THE.as_fragment(), self._verbalize_plural_(binding.value_expr, ctx))
        if binding.is_plural_field:
            return self._verbalize_plural_(binding.value_expr, ctx)
        if binding.aggregation_status == AggregationStatus.GROUP_KEY:
            return _word(self._verbalize_group_key_value_(binding.value_expr, ctx))
        return self.build(binding.value_expr, ctx)

    def _verbalize_group_key_value_(self, expr, ctx: VerbalizationContext) -> str:
        chain: list = []
        current = expr
        while isinstance(current, MappedVariable):
            chain.append(current)
            current = current._child_
        chain.reverse()

        if not chain or not isinstance(current, Variable):
            return self.verbalize(expr, ctx)

        root_type = current._type_.__name__ if getattr(current, "_type_", None) else FallbackNouns.ENTITY.text
        root_plural = inflect_engine.plural(root_type)
        ctx.seen[current._id_] = root_type

        parts = self._build_path_parts_(chain)
        field = list(reversed(parts))[0][0] if parts else root_type
        return _str(GroupKeyPhrases.COMMON_OF.build_phrase(field, root_plural))

    # ── Query: Entity and SetOf ────────────────────────────────────────────────

    def _v_Entity_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

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
            selected_type = FallbackNouns.ENTITY.text
            ctx.seen[expr._id_] = selected_type
            selected = FallbackNouns.ENTITY.plural_fragment()
        elif is_the:
            selected_type = var._type_.__name__ if getattr(var, "_type_", None) else FallbackNouns.ENTITY.text
            ctx.seen[var._id_] = selected_type
            ctx.seen[expr._id_] = selected_type
            selected = _phrase(Articles.THE_UNIQUE.as_fragment(), _role(selected_type, SemanticRole.VARIABLE))
        else:
            selected = self.build(var, ctx)
            selected_type = ctx.seen.get(getattr(var, "_id_", None), FallbackNouns.ENTITY.text)
            ctx.seen[expr._id_] = selected_type

        return self._verbalize_query_body_(expr, ctx, selected)

    def _verbalize_entity_as_noun_(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

        expr.build()
        is_the = (
            expr._quantifier_builder_ is not None
            and expr._quantifier_builder_.type is The
        )
        var = expr.selected_variable
        selected_type = var._type_.__name__ if var and getattr(var, "_type_", None) else FallbackNouns.ENTITY.text
        var_type = getattr(var, "_type_", None)
        ref = SourceRef(cls=var_type) if isinstance(var_type, type) else None

        ctx.seen[expr._id_] = selected_type
        if var is not None:
            ctx.seen[var._id_] = selected_type

        if is_the:
            article_noun: VerbFragment = _phrase(
                Articles.THE_UNIQUE.as_fragment(), _role(selected_type, SemanticRole.VARIABLE, ref)
            )
        else:
            article_noun = _phrase(
                Articles.indefinite(selected_type),
                _role(selected_type, SemanticRole.VARIABLE, ref),
            )

        where_expr = expr._where_expression_
        if where_expr is not None:
            cond = self.verbalize(where_expr.condition, ctx)
            return _phrase(article_noun, Keywords.WHERE.as_fragment(), _word(cond))
        return article_noun

    def _verbalize_entity_as_inline_noun_(self, entity: Entity, ctx: VerbalizationContext) -> VerbFragment:
        if entity._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[entity._id_], SemanticRole.VARIABLE))

        entity.build()
        var = entity.selected_variable
        type_name = var._type_.__name__ if var and getattr(var, "_type_", None) else FallbackNouns.ENTITY.text

        ctx.seen[entity._id_] = type_name
        if var is not None and hasattr(var, "_id_"):
            ctx.seen[var._id_] = type_name

        where_expr = entity._where_expression_
        if where_expr is not None:
            cond_text = self.verbalize(where_expr.condition, ctx)
            ctx.add_constraint(cond_text)

        var_type = getattr(var, "_type_", None)
        ref = SourceRef(cls=var_type) if isinstance(var_type, type) else None
        return _phrase(Articles.indefinite(type_name), _role(type_name, SemanticRole.VARIABLE, ref))

    def _v_SetOf_(self, expr: SetOf, ctx: VerbalizationContext) -> VerbFragment:
        expr.build()
        vars_str = ", ".join(self.verbalize(v, ctx) for v in expr._selected_variables_)
        prefix = _phrase(Keywords.FIND_SETS_OF.as_fragment(), _word(f"({vars_str})"))
        return self._verbalize_query_body_(expr, ctx, prefix)

    def _verbalize_query_body_(self, expr, ctx: VerbalizationContext, selection: VerbFragment) -> VerbFragment:
        find_header = _phrase(Keywords.FIND.as_fragment(), selection)

        where_expr = expr._where_expression_
        grouped_expr = expr._grouped_by_expression_
        having_expr = expr._having_expression_
        aliases = ctx.binding_aliases

        clauses: list[VerbFragment] = []

        if where_expr is not None:
            where_text = _apply_binding_aliases(self.verbalize(where_expr.condition, ctx), aliases)
            clauses.append(_phrase(Keywords.SUCH_THAT.as_fragment(), _word(where_text)))

        if grouped_expr is not None and grouped_expr.variables_to_group_by:
            group_key_root_ids = self._root_var_ids_(grouped_expr.variables_to_group_by)
            groups = [
                _apply_binding_aliases(self.verbalize(v, ctx), aliases)
                for v in grouped_expr.variables_to_group_by
            ]
            aggregated = self._aggregated_noun_phrases_(expr, group_key_root_ids, ctx)
            groups_str = self._join_groups_(groups)
            _the = Articles.THE.text
            _are = Copulas.ARE.text
            if aggregated:
                aggregated_str = self._join_plain_(aggregated)
                clauses.append(_phrase(
                    Conjunctions.AND.as_fragment(),
                    _word(f"{_the} {aggregated_str} {_are}"),
                    Keywords.GROUPED_BY.as_fragment(),
                    _word(groups_str),
                ))
            else:
                clauses.append(_phrase(Keywords.GROUPED_BY.as_fragment(), _word(groups_str)))

        if having_expr is not None:
            ctx.compact_predicates = True
            having_text = _apply_binding_aliases(self.verbalize(having_expr.condition, ctx), aliases)
            ctx.compact_predicates = False
            clauses.append(_phrase(Keywords.HAVING.as_fragment(), _word(having_text)))

        ob = expr._ordered_by_builder_
        if ob is not None:
            direction = SortDirections.DESCENDING.text if ob.descending else SortDirections.ASCENDING.text
            ordered_text = _apply_binding_aliases(self.verbalize(ob.variable, ctx), aliases)
            clauses.append(_phrase(
                Keywords.ORDERED_BY.as_fragment(),
                _word(f"{ordered_text} ({direction})"),
            ))

        return BlockFragment(header=find_header, items=clauses)

    @staticmethod
    def _join_groups_(groups: list[str]) -> str:
        if len(groups) == 1:
            return groups[0]
        conj = f", {Conjunctions.AND.text} "
        return f"({', '.join(groups[:-1])}{conj}{groups[-1]})"

    @staticmethod
    def _join_plain_(parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " " + parts[-1]

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
            return _phrase(Keywords.GROUPED_BY.as_fragment(), _word(", ".join(groups)))
        return Keywords.GROUPED.as_fragment()

    def _v_OrderedBy_(self, expr: OrderedBy, ctx: VerbalizationContext) -> VerbFragment:
        direction = SortDirections.DESCENDING.text if expr.descending else SortDirections.ASCENDING.text
        return _phrase(
            Keywords.ORDERED_BY.as_fragment(),
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
    """Verbalize any EQL expression into a human-readable English phrase (plain text)."""
    if isinstance(expr, Query):
        expr.build()
    return _default_verbalizer.verbalize(expr)
