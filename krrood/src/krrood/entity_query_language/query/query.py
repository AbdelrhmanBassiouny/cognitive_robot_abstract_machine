"""
Query abstractions for the Entity Query Language.

This module implements query composition and evaluation, including selection, filtering, grouping, ordering,
distinct handling, and quantification over symbolic expressions.
"""

from __future__ import annotations

from abc import ABC
from copy import copy
from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import (
    Iterable,
    Any,
    Optional,
    Type,
    Dict,
    Union as TypingUnion,
    TYPE_CHECKING,
    List,
    Tuple,
    Callable,
    Self,
    Iterator,
)

from krrood.entity_query_language.core.mapped_variable import (
    CanBehaveLikeAVariable,
    MappedVariable,
)
from krrood.entity_query_language.query.builders import (
    WhereBuilder,
    HavingBuilder,
    GroupedByBuilder,
    QuantifierBuilder,
    OrderedByBuilder,
)
from krrood.entity_query_language.query.operations import (
    Where,
    Having,
    GroupedBy,
)
from krrood.entity_query_language.query.quantifiers import (
    ResultQuantificationConstraint,
    ResultQuantifier,
    An,
)
from krrood.entity_query_language.core.base_expressions import (
    Bindings,
    OperationResult,
    SymbolicExpression,
    UnaryExpression,
    Selectable,
    UnificationDict,
)
from krrood.entity_query_language.cache_data import (
    SeenSet,
)
from krrood.entity_query_language.core.variable import (
    InstantiatedVariable,
    Variable,
    ExternallySetVariable,
)
from krrood.entity_query_language.enums import DomainSource
from krrood.entity_query_language.exceptions import (
    UnsupportedNegation,
    NonPositiveLimitValue,
)
from krrood.entity_query_language.operators.aggregators import Aggregator
from krrood.entity_query_language.operators.set_operations import (
    MultiArityExpressionThatPerformsACartesianProduct,
)
from krrood.entity_query_language._monitoring import (
    monitored,
)
from krrood.entity_query_language.utils import (
    T,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.factories import ConditionType

ResultMapping = Callable[[Iterator[OperationResult]], Iterator[OperationResult]]
"""
A function that maps the results of a query to a new set of results.
"""


@monitored
@dataclass(eq=False, repr=False)
class Query(
    MultiArityExpressionThatPerformsACartesianProduct, CanBehaveLikeAVariable[T], ABC
):
    """
    Describes the queried object(s), could be a query over a single variable or a set of variables,
    also describes the condition(s)/properties of the queried object(s).
    """

    _selected_variables_: Tuple[Selectable, ...] = field(
        default_factory=tuple, kw_only=True
    )
    """
    The variables that are selected by the query.
    """
    _distinct_on: Tuple[Selectable, ...] = field(default_factory=tuple, init=False)
    """
    Parameters for distinct results of the query.
    """
    _results_mapping: List[ResultMapping] = field(init=False, default_factory=list)
    """
    Mapping functions that map the results of the query to a new set of results.
    """
    _seen_results: Optional[SeenSet] = field(init=False, default=None)
    """
    A set of seen results, used when distinct is called in the query.
    """
    _where_builder_: Optional[WhereBuilder] = field(init=False, default=None)
    """
    The builder for the `Where` expression of the query.
    """
    _grouped_by_builder_: Optional[GroupedByBuilder] = field(init=False, default=None)
    """
    The builder for the `GroupedBy` expression of the query.
    """
    _having_builder_: Optional[HavingBuilder] = field(init=False, default=None)
    """
    The builder for the `Having` expression of the query.
    """
    _ordered_by_builder_: Optional[OrderedByBuilder] = field(default=None, init=False)
    """
    The builder for the `OrderedBy` expression if present.
    """
    _quantifier_builder_: Optional[QuantifierBuilder] = field(default=None, init=False)
    """
    The builder for the `ResultQuantifier` expression of the query. The default quantifier is `An`
     which yields all results.
    """
    _dirty_: bool = field(default=True, init=False)
    """
    Whether anything needs (re)building. Any modifier method marks the query dirty; :meth:`build`
    is a no-op while clean and otherwise applies only the parts flagged below. The query is never
    frozen, so it can always be modified, even after being built or embedded as a child.
    """
    _inner_dirty_: bool = field(default=True, init=False)
    """
    Whether the data-source chain (Where / GroupedBy / Having + selected variables) needs rewiring,
    set by :meth:`where`, :meth:`having` and :meth:`grouped_by`.
    """
    _building_: bool = field(default=False, init=False)
    """
    Re-entrancy guard set while :meth:`build` wires the wrapper layers, so that parenting the query
    to its own wrappers does not recursively trigger another build.
    """
    _is_compiled_product_: bool = field(default=False, init=False)
    """
    Whether this instance is a compiled product (wired as the cartesian-product node) rather than a
    spec. A spec delegates evaluation to the product it compiles, so that the spec behaves like its
    product while never being the mutated, embedded node itself.
    """
    _compiled_product_node_: Optional[Query] = field(default=None, init=False)
    """
    The inner cartesian-product node of the last compiled product (the node sharing this query's
    identifier, beneath the ordering/quantification wrappers). Derived references such as
    ``query.name`` embed this node so that, evaluated against a result that already binds the query's
    identifier, they resolve to that result rather than re-running the whole subquery.
    """
    _compiled_inner_head_: Optional[SymbolicExpression] = field(
        default=None, init=False
    )
    """
    The data-source head (Where / GroupedBy / Having) wired by the last build, tracked so it can be
    detached cleanly when the chain is rewired.
    """

    def __post_init__(self):
        self._operation_children_ = tuple(self._selected_variables_)
        MultiArityExpressionThatPerformsACartesianProduct.__post_init__(self)

        self._var_ = self
        Selectable.__post_init__(self)

        self._quantifier_builder_ = QuantifierBuilder(self)

    def _mark_dirty_(self) -> None:
        """
        Flag the compiled expression as stale and drop caches that depend on modifier state, so the
        next :meth:`build` recomputes them. Called by every modifier method.
        """
        self._dirty_ = True
        self.__dict__.pop("_group_", None)
        self.__dict__.pop("_distinct_on_ids_", None)

    def evaluate(self) -> Iterator:
        """
        Wrap the query in a ResultQuantifier expression and evaluate it,
         returning an iterator over the results.
        """
        self.build()
        if self._expression_ is not self:
            return self._expression_.evaluate()
        else:
            return MultiArityExpressionThatPerformsACartesianProduct.evaluate(self)

    def where(self, *conditions: ConditionType) -> Self:
        """
        Set the conditions that describe the query object. The conditions are chained using AND.

        :param conditions: The conditions that describe the query object.
        :return: This query.
        """
        if self._where_builder_ is None:
            self._where_builder_ = WhereBuilder(conditions=conditions, query=self)
        else:
            self._where_builder_.conditions += conditions
        self._inner_dirty_ = True
        self._mark_dirty_()
        return self

    def having(self, *conditions: ConditionType) -> Self:
        """
        Set the conditions that describe the query object. The conditions are chained using AND.

        :param conditions: The conditions that describe the query object.
        :return: This query.
        """
        if self._having_builder_ is None:
            self._having_builder_ = HavingBuilder(conditions=conditions, query=self)
        else:
            self._having_builder_.conditions += conditions
        self._inner_dirty_ = True
        self._mark_dirty_()
        return self

    def ordered_by(
        self,
        variable: TypingUnion[Selectable[T], Any],
        descending: bool = False,
        key: Optional[Callable] = None,
    ) -> Self:
        """
        Order the results by the given variable, using the given key function in descending or ascending order.

        :param variable: The variable to order by.
        :param descending: Whether to order the results in descending order.
        :param key: A function to extract the key from the variable value.
        """
        self._ordered_by_builder_ = OrderedByBuilder(
            self, variable, descending=descending, key=key
        )
        self._mark_dirty_()
        return self

    def distinct(
        self,
        *on: TypingUnion[Selectable, Any],
    ) -> TypingUnion[Self, T]:
        """
        Apply distinctness constraint to the query results.

        :param on: The variables to be used for distinctness.
        :return: This query.
        """
        self._distinct_on = on if on else self._selected_variables_
        self._mark_dirty_()
        self._seen_results = SeenSet(keys=self._distinct_on_ids_)
        self._results_mapping.append(self._get_distinct_results_)
        return self

    def grouped_by(
        self, *variables_to_group_by: TypingUnion[Selectable, Any]
    ) -> TypingUnion[Self, T]:
        """
        Specify the variables to group the results by.

        :param variables_to_group_by: The variables to group the results by.
        :return: This query.
        """
        self._grouped_by_builder_ = GroupedByBuilder(self, variables_to_group_by)
        self._inner_dirty_ = True
        self._mark_dirty_()
        return self

    def limit(self, n: int) -> Self:
        """
        Limit the number of results to n.

        :param n: The maximum number of results to return.
        :return: This query.
        """
        self._limit_ = n
        if not isinstance(self._limit_, int) or self._limit_ <= 0:
            raise NonPositiveLimitValue(self._limit_)
        # The quantifier wrapper keeps its identity across rebuilds, so update it in place when it
        # already exists; otherwise the first build picks the limit up.
        if isinstance(self._expression_, ResultQuantifier):
            self._expression_._limit_ = self._limit_
        return self

    def _quantify_(
        self,
        quantifier_type: Type[ResultQuantifier] = An,
        quantification_constraint: Optional[ResultQuantificationConstraint] = None,
    ) -> Self:
        """
        Specify the quantifier type and constraint for the query results, also build the query.

        :param quantifier_type: The type of the quantifier to be used.
        :param quantification_constraint: The constraint to apply to the quantifier.
        :return: This query.
        """
        self._quantifier_builder_ = QuantifierBuilder(
            self, quantifier_type, quantification_constraint
        )
        self._mark_dirty_()
        return self

    def __enter__(self):
        """
        Make sure the query is built before entering the context manager for rule trees.
        """
        self.build()
        expression = self._conditions_root_
        SymbolicExpression._symbolic_expression_stack_.append(expression)
        return expression

    def build(self) -> Self:
        """
        Build (or rebuild) the query, caching a freshly compiled product expression.

        This query is a stable spec: it holds the modifiers and a stable identity that derived
        references and rules point at, but it is never itself the evaluated node. Each build compiles
        a fresh product tree from the current spec via :meth:`_compile_` and stores it in
        :attr:`_expression_`; the spec is never frozen, so any modifier marks it dirty and the next
        build produces a new product. Because every build yields a new tree (rather than mutating the
        previous one in place), a product already embedded elsewhere stays frozen against later edits.

        :return: This query.
        """
        if not self._dirty_:
            return self
        self._compiled_product_node_ = self._compile_()
        self._expression_ = self._compiled_product_node_._expression_
        self._dirty_ = False
        return self

    def _compile_(self) -> SymbolicExpression:
        """
        Compile a fresh, independent product expression from this spec — the single compile path.

        The product is a separate node graph that shares this query's identifier and selected
        variables, so it evaluates identically and co-references the same variables, while later
        edits that rebuild the spec cannot reach it. It is produced by replaying the spec's modifiers
        onto a fresh instance and wiring that instance as the cartesian-product node, rather than by
        cloning a live graph, so grouping, distinct, and self-referential ordering all compile
        correctly.

        :return: The compiled inner product node (its ordering/quantification wrappers are reachable
            through its :attr:`_expression_`).
        """
        product = type(self)(_selected_variables_=self._selected_variables_)
        product._id_ = self._id_
        product._expression_id_cache_ = {}
        if self._where_builder_ is not None:
            product.where(*self._where_builder_.conditions)
        if self._grouped_by_builder_ is not None:
            product.grouped_by(*self._grouped_by_builder_.variables_to_group_by)
        if self._having_builder_ is not None:
            product.having(*self._having_builder_.conditions)
        if self._ordered_by_builder_ is not None:
            ordering = self._ordered_by_builder_
            product.ordered_by(
                ordering.variable, descending=ordering.descending, key=ordering.key
            )
        if self._distinct_on:
            product.distinct(*self._distinct_on)
        if self._limit_ is not None:
            product.limit(self._limit_)
        quantifier = self._quantifier_builder_
        product._quantify_(quantifier.type, quantifier.quantification_constraint)
        product._wire_in_place_()
        return product

    def _wire_in_place_(self) -> Self:
        """
        Wire this instance as the cartesian-product node: build the data-source chain (Where /
        GroupedBy / Having) and selected variables as its children, then apply the ordering and
        quantification wrappers around it. Called once on a freshly compiled product instance.

        :return: This instance.
        """
        self._building_ = True
        self._is_compiled_product_ = True
        self._rewire_data_source_chain_()
        self._inner_dirty_ = False
        self._apply_wrapping_modifiers_()
        self._dirty_ = False
        self._building_ = False
        return self

    def _rewire_data_source_chain_(self) -> None:
        """
        (Re)wire the data-source chain (Where / GroupedBy / Having) and the selected variables as the
        children of this query node. Safe to call repeatedly: the previous chain head is detached and
        modifier caches discarded so a fresh head reflecting the current conditions is built. The
        ordering/quantification wrappers keep pointing at this query node, so they pick up the change.
        """
        # Detach the head built last time and discard cached metadata on the chain modifiers, which
        # may have been mutated in place (e.g. extra ``where``/``having`` conditions appended).
        if self._compiled_inner_head_ is not None:
            self._compiled_inner_head_._parent_ = None
            self._compiled_inner_head_ = None
        for modifier in (
            self._where_builder_,
            self._grouped_by_builder_,
            self._having_builder_,
        ):
            if modifier is not None:
                modifier.reset()

        children = self._data_source_chain_head_()
        self._compiled_inner_head_ = children[0] if children else None

        children.extend(self._selected_variables_)
        self.update_children(*children)

    def _data_source_chain_head_(self) -> List[SymbolicExpression]:
        """
        Build the head of the data-source chain that feeds the selected variables. At most one of
        Having / GroupedBy / Where heads the chain, with precedence ``Having > GroupedBy > Where``
        since each already incorporates the previous one.

        :return: A list containing the chain head, or empty if the query is unfiltered/ungrouped.
        """
        if self._group_ and self._grouped_by_builder_ is None:
            self._grouped_by_builder_ = GroupedByBuilder(self)

        if self._having_builder_ is not None:
            self._having_builder_.grouped_by = self._grouped_by_builder_.expression
            return [self._having_builder_.expression]
        if self._grouped_by_builder_ is not None:
            return [self._grouped_by_builder_.expression]
        if self._where_builder_ is not None:
            return [self._where_builder_.expression]
        return []

    def _apply_wrapping_modifiers_(self) -> None:
        """
        Apply the ordering and quantification wrappers, innermost first, around the current compiled
        expression. Each modifier is applied only when it needs (re)applying; an already-applied
        wrapper keeps its identity across rebuilds, so a reference captured by an expression derived
        from the query stays valid. ``OrderedBy`` nests inside the ``ResultQuantifier``.
        """
        for modifier in (self._ordered_by_builder_, self._quantifier_builder_):
            if modifier is None or not modifier._needs_apply_:
                continue
            self._expression_ = modifier.rewrap(self._expression_)
            modifier._needs_apply_ = False

    def _evaluate__(
        self,
        sources: OperationResult,
    ) -> Iterable[OperationResult]:
        """
        Evaluate the query by constraining values, updating conclusions,
        and selecting variables.

        A spec delegates to its compiled product so that evaluating the spec as an expression behaves
        exactly like evaluating the product; only the compiled product runs the real evaluation.
        """
        if not self._is_compiled_product_:
            self.build()
            yield from self._compiled_product_node_._evaluate__(sources)
            return

        yield from (
            self._get_operation_result_(result)
            for result in self._apply_results_mapping_(
                self._evaluate_product_(sources),
            )
        )

        if self._seen_results is not None:
            self._seen_results.clear()

    def _get_operation_result_(self, child_result: OperationResult) -> OperationResult:
        """
        :param child_result: The child result to construct the operation result from.
        :return: The operation result.
        """
        return OperationResult(
            {v._id_: child_result[v._id_] for v in self._selected_variables_},
            child_result.is_false,
            self,
            child_result,
        )

    @property
    def _where_expression_(self) -> Optional[Where]:
        """
        The built `Where` expression.
        """
        return self._where_builder_.expression if self._where_builder_ else None

    @property
    def _having_expression_(self) -> Optional[Having]:
        """
        The built `Having` expression.
        """
        return self._having_builder_.expression if self._having_builder_ else None

    @property
    def _grouped_by_expression_(self) -> Optional[GroupedBy]:
        """
        The built `GroupedDataSource` expression.
        """
        return (
            self._grouped_by_builder_.expression if self._grouped_by_builder_ else None
        )

    @property
    def _quantifier_expression_(self) -> Optional[ResultQuantifier]:
        """
        :return: The compiled result quantifier at the root of the built expression, if any.
        """
        self.build()
        return (
            self._expression_
            if isinstance(self._expression_, ResultQuantifier)
            else None
        )

    @cached_property
    def _distinct_on_ids_(self) -> Tuple[int, ...]:
        """
        Get the IDs of variables used for distinctness.
        """
        return tuple(k._id_ for k in self._distinct_on)

    def _get_distinct_results_(
        self, results_gen: Iterator[OperationResult]
    ) -> Iterator[OperationResult]:
        """
        Apply distinctness constraint to the query results.

        :param results_gen: Generator of results.
        :return: Generator of distinct results.
        """
        for result in results_gen:
            bindings = copy(result.bindings)
            self._update_res_with_distinct_on_variables_(bindings)
            if self._seen_results.check(bindings):
                continue
            self._seen_results.add(bindings)
            yield result

    def _update_res_with_distinct_on_variables_(self, res: Dict[int, Any]):
        """
        Update the result dictionary with values from distinct-on variables if not already present.

        :param res: The result dictionary to update.
        """
        for i, id_ in enumerate(self._distinct_on_ids_):
            if id_ in res:
                continue
            var_value = self._distinct_on[i]._evaluate_(OperationResult(copy(res)))
            res[id_] = next(var_value).value

    @cached_property
    def _group_(self) -> bool:
        """
        :return: Whether the results should be grouped or not. Is true when an aggregator is selected.
        """
        return (len(self._aggregators_and_non_aggregators_in_selection_[0]) > 0) or (
            self._grouped_by_builder_ is not None
        )

    @cached_property
    def _aggregators_and_non_aggregators_in_selection_(
        self,
    ) -> Tuple[List[Aggregator], List[Selectable]]:
        """
        :return: The aggregated and non-aggregated variables from the selected variables.
        """
        aggregated_variables = []
        non_aggregated_variables = []

        def _update_aggregated_and_non_aggregated_variables(
            variable_: SymbolicExpression,
        ):
            if isinstance(variable_, Aggregator):
                aggregated_variables.append(variable_)
            elif isinstance(variable_, InstantiatedVariable):
                for child in variable_._operation_children_:
                    _update_aggregated_and_non_aggregated_variables(child)
            elif (
                isinstance(variable_, ExternallySetVariable)
                and variable_._domain_source_ == DomainSource.DEDUCTION
            ):
                pass
            else:
                non_aggregated_variables.append(variable_)

        for variable in self._selected_variables_:
            _update_aggregated_and_non_aggregated_variables(variable)
        return aggregated_variables, non_aggregated_variables

    def _apply_results_mapping_(
        self, results: Iterator[OperationResult]
    ) -> Iterable[OperationResult]:
        """
        Process and transform an iterable of results based on predefined mappings and ordering.

        This method applies a sequence of result transformations defined in the instance,
        using a series of mappings to modify the results.

        :param results: An iterable containing dictionaries that represent the initial result set to be transformed.
        :return: An iterable containing dictionaries that represent the transformed data.
        """
        for result_mapping in self._results_mapping:
            results = result_mapping(results)
        return results

    def _as_embeddable_child_(self, parent: SymbolicExpression) -> SymbolicExpression:
        """
        Embed this query's compiled product when it becomes an operand of another expression.

        The product is captured as it stands at embed time; because each rebuild produces a new
        product rather than mutating the previous one, a later edit to this query cannot change the
        already-embedded copy. While a product instance wires its own wrapper layers during
        :meth:`_wire_in_place_` (``_building_``), the wrappers must wrap that instance itself, so its
        own (partial) expression is returned.

        :param parent: The expression about to take this query as a child.
        :return: The compiled product to embed; the inner product node for a derived reference (a
            :class:`MappedVariable` such as ``query.name``) so it resolves against the query's own
            bindings; or the in-place node during self-wrapping.
        """
        if self._building_:
            return self._expression_
        self.build()
        if isinstance(parent, MappedVariable):
            return self._compiled_product_node_
        return self._expression_

    @property
    def _conditions_root_(self) -> Optional[SymbolicExpression]:
        """
        Resolve the conditions root within the compiled product, so rule definition (:meth:`__enter__`)
        and conclusions attach to the node that is actually evaluated.

        :return: The conditions root of the compiled product.
        """
        self.build()
        return self._expression_._conditions_root_

    @UnaryExpression._parent_.setter
    def _parent_(self, parent: SymbolicExpression):
        """
        Route parenting to the compiled product (its outer wrapper) rather than to the spec node,
        building it first. The ``_building_`` re-entrancy guard prevents recursion while a product
        instance wires its own wrapper layers during :meth:`_wire_in_place_`.
        """
        if not self._building_:
            self.build()
        if self._expression_ is not self:
            self._expression_._parent_ = parent
        else:
            UnaryExpression._parent_.__set__(self, parent)

    def _invert_(self):
        raise UnsupportedNegation(self.__class__)

    @property
    def _name_(self) -> str:
        return f"({', '.join(var._name_ for var in self._selected_variables_)})"


@dataclass(eq=False, repr=False)
class SetOf(Query):
    """
    A query over a set of variables.
    """

    def _get_operation_result_(self, child_result: OperationResult) -> OperationResult:
        """
        Update the result bindings with this operation's bindings.
        """
        operation_result = super()._get_operation_result_(child_result)
        operation_result.bindings = {
            self._id_: UnificationDict(
                {var: operation_result[var._id_] for var in self._selected_variables_}
            )
        }
        return operation_result


@dataclass(eq=False, repr=False)
class Entity(Query[T]):
    """
    A query over a single variable.
    """

    def _get_operation_result_(self, child_result: OperationResult) -> OperationResult:
        """
        Update the result bindings with this operation's bindings.
        """
        operation_result = super()._get_operation_result_(child_result)
        operation_result.bindings = {
            self._id_: operation_result[self.selected_variable._id_]
        }
        return operation_result

    @property
    def selected_variable(self):
        return self._selected_variables_[0] if self._selected_variables_ else None
