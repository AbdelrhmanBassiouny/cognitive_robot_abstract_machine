from __future__ import annotations

import ast
import linecache
import os
import textwrap
import weakref
from dataclasses import dataclass, field
from functools import cached_property
from types import ModuleType
from typing import Any, Callable, List, Optional, Type
from uuid import UUID

from ordered_set import OrderedSet
from typing_extensions import TYPE_CHECKING

# Import monitoring infrastructure from the isolated sub-module that has no
# EQL dependencies, breaking the variable.py ↔ explanation.py import cycle.
from krrood.entity_query_language._monitoring import (
    MonitoredRegistry,
    monitored,
)
from krrood.entity_query_language._stack import CallStack, StackFrame
from krrood.entity_query_language.core.base_expressions import Selectable
from krrood.entity_query_language.core.mapped_variable import (
    Attribute,
    FlatVariable,
    MappedVariable,
)
from krrood.entity_query_language.factories import (
    and_,
    attribute_owner_class,
    contains,
    entity,
    exists,
    flat_variable,
    is_class,
    issubclass_,
    node_children,
    node_descendants,
    node_id,
    node_type,
    or_,
    variable_from,
    concatenation,
    set_of,
)
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import (
    LogicalOperator,
)
from krrood.entity_query_language.predicate import HasType
from krrood.symbol_graph.symbol_graph import Symbol

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import (
        OperationResult,
        SymbolicExpression,
    )
    from krrood.entity_query_language.core.variable import (
        InstantiatedVariable,
        Variable,
    )
    from krrood.entity_query_language.query.query import Entity, Query


def _get_query_source(frame: StackFrame) -> Optional[str]:
    """Return the full source statement at frame.lineno, or frame.code_snippet as fallback."""
    if not frame or not frame.filename:
        return None
    lines = linecache.getlines(frame.filename)
    if not lines:
        return frame.code_snippet
    try:
        source = "".join(lines)
        tree = ast.parse(source)
        candidates: list = list(tree.body)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                candidates.extend(node.body)
        best = None
        for node in candidates:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is not None and end is not None and start <= frame.lineno <= end:
                if best is None or (end - start) < (best.end_lineno - best.lineno):
                    best = node
        if best is not None:
            stmt_lines = lines[best.lineno - 1 : best.end_lineno]
            return textwrap.dedent("".join(stmt_lines)).rstrip()
    except Exception:
        pass
    return frame.code_snippet


@dataclass
class ConditionAndBindings:
    """
    Represents a condition and its associated bindings in the inference process.
    """

    condition: SymbolicExpression
    """
    The condition expression.
    """
    bindings: dict[UUID, Any]
    """
    A dictionary mapping UUIDs of condition children to their corresponding bindings.
    """

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if isinstance(self.condition, Comparator):
            return f"({self.condition.left} {self.condition} {self.condition.right})"
        else:
            return f"{self.condition} ({','.join(str(child) for child in self.condition._children_)})"


@dataclass
class InferenceExplanation(Symbol):
    """
    Explanation of how an instance was created through inference.

    Inherits from :class:`~krrood.symbol_graph.symbol_graph.Symbol` so that every
    explanation is a first-class entity in the SymbolGraph and therefore queryable
    via EQL like any other domain object.

    Lifecycle is tied to the inferred instance: the instance stores a strong reference
    to this object via its ``_inference_explanation_`` attribute (see
    :func:`register_inference`), while this object stores only a *weak* reference back
    to the instance.  This means the explanation is part of the same reference cluster
    as the instance and is collected together with it — no global registry required.
    """

    query_node: SymbolicExpression
    """
    The query node that was used to create the instance.
    """
    stack: CallStack
    """
    The call stack at the point of creation, as a :class:`~krrood.entity_query_language._stack.CallStack`.
    """
    query_root: Query | InstantiatedVariable
    """
    The root of the query that was used to create the instance.
    """
    satisfied_condition_ids: Optional[OrderedSet[UUID]] = None
    """
    An ordered set of UUIDs of condition expressions that were satisfied (truth value = True)
    during the evaluation that produced this instance. None if no condition information is available.
    """
    operation_result: Optional[OperationResult] = None
    """
    The full :class:`OperationResult` from the evaluation iteration that produced this instance.
    Contains bindings, all_bindings, is_false, operand, previous_operation_result, and
    satisfied_condition_ids. None if no result information is available.
    """

    # Internal weak reference to the inferred instance.  Not part of the public
    # constructor — populated by __post_init__.
    _instance_ref: Optional[weakref.ref] = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def instance(self) -> Any:
        """The inferred instance, or ``None`` if it has been garbage-collected."""
        if self._instance_ref is None:
            return None
        return self._instance_ref()

    def get_satisfied_conditions_as_string(self) -> str:
        """
        Returns a string representation of the satisfied conditions, joined by ' AND '.
        """
        return "\nAND ".join(
            str(c) for c in self.get_satisfied_conditions_and_their_bindings()
        )

    def get_satisfied_conditions_and_their_bindings(self) -> List[ConditionAndBindings]:
        """
        Retrieve the list of satisfied condition expressions along with their bindings.

        :return: A list of :class:`ConditionAndBindings` objects, each containing a satisfied condition expression and
        its corresponding bindings. Returns an empty list if no satisfaction data is available.
        """
        if (
            self.operation_result is None
            or not self.operation_result.satisfied_condition_ids
        ):
            return []

        satisfied_conditions = []
        for condition_id in self.operation_result.satisfied_condition_ids:
            condition_expr = self.query_root._get_expression_by_id_(condition_id)
            if isinstance(condition_expr, (LogicalOperator,)):
                continue
            if condition_expr is not None:
                satisfied_conditions.append(
                    ConditionAndBindings(
                        condition_expr, self.operation_result.all_bindings
                    )
                )
        return satisfied_conditions

    def condition_graph(self):
        """
        Build a QueryGraph of the full query tree with satisfaction data overlaid.

        Each ``QueryNode`` carries an ``is_satisfied`` flag grounded directly on
        the satisfied condition IDs.  Unsatisfied condition subtrees are also
        marked as *faded* for visualization purposes.

        :return: A :class:`QueryGraph` instance, or None if no conditions exist
            or no satisfaction data is available.
        """
        if self.query_root is None or not self.satisfied_condition_ids:
            return None
        from krrood.entity_query_language.query_graph import QueryGraph

        return QueryGraph(
            self.query_root,
            satisfied_condition_ids=self.satisfied_condition_ids,
        )

    def as_string(self, focus_package: Optional[str | ModuleType] = None, show_trace: bool = False) -> str:
        """
        Convert an InferenceExplanation into a human-readable string.

        :param focus_package: Optional package name; only applies when ``show_trace=True``.
        :param show_trace: When ``True``, append the call stack recorded at query-definition time.
        :return: A formatted string explaining the inference.
        """
        filtered_frames = self.stack.filter().frames

        def _is_krrood_internal(f: StackFrame) -> bool:
            if f.module_name and (f.module_name == "krrood" or f.module_name.startswith("krrood.")):
                return True
            return "/krrood/src/krrood/" in f.filename or "\\krrood\\src\\krrood\\" in f.filename

        # Prefer frames from real source files (skip synthetic "<string>", "<frozen ...>", etc.)
        real_user_frames = [
            f for f in filtered_frames
            if not f.filename.startswith("<") and not _is_krrood_internal(f)
        ]
        if real_user_frames:
            source_frame = real_user_frames[0]
        else:
            # Notebook / eval context: fall back to innermost non-krrood frame
            fallback = [f for f in filtered_frames if not _is_krrood_internal(f)]
            source_frame = fallback[0] if fallback else (filtered_frames[0] if filtered_frames else None)

        query_source = _get_query_source(source_frame) if source_frame else None
        if source_frame:
            basename = os.path.basename(source_frame.filename)
            source_context = f"({source_frame.function_name}, {basename}:{source_frame.lineno})"
        else:
            source_context = ""

        if query_source:
            indented_source = "\n".join(f"  {line}" for line in query_source.splitlines())
        else:
            indented_source = "  (unavailable)"

        conditions = self.get_satisfied_conditions_and_their_bindings()
        conds_str = "\n  AND ".join(str(c) for c in conditions) if conditions else "(none)"

        result = (
            f"Instance: {self.instance}\n"
            f"Produced by inference variable: {self.query_node}\n"
            f"Query source {source_context}:\n{indented_source}\n"
            f"Satisfied conditions:\n  {conds_str}"
        )

        if show_trace:
            if isinstance(focus_package, ModuleType):
                focus_package = focus_package.__name__
            display_stack = self.stack.filter(package=focus_package)
            formatted_stack = []
            for frame in display_stack:
                formatted_stack.append(
                    f'  File "{frame.filename}", line {frame.lineno}, in {frame.function_name}\n'
                    f"    {frame.code_snippet if frame.code_snippet else '???'}\n"
                )
            result += f"\nCall stack at definition:\n{''.join(formatted_stack[:10])}"

        return result

    # ------------------------------------------------------------------
    # Stack query methods
    # ------------------------------------------------------------------

    @property
    def frame_count(self) -> int:
        """Number of frames in the captured call stack."""
        return len(self.stack)

    def is_triggered_from_method(self) -> bool:
        """
        Return ``True`` if any frame in the call stack is inside a class method
        or classmethod (i.e. at least one frame has a non-``None`` ``class_object``).
        """
        return self.stack.is_from_method()

    def triggering_classes(self) -> List[type]:
        """
        Return the distinct class objects that appear in the call stack,
        in order of first occurrence (innermost first).

        Useful for answering "from which class was this inference triggered?"
        """
        return self.stack.classes()

    def triggering_functions(self) -> List[Callable]:
        """
        Return the distinct function objects that appear in the call stack,
        in order of first occurrence (innermost first).

        Note: nested functions defined inside other functions may not be
        resolvable and will be absent from this list.
        """
        return self.stack.functions()

    def root_frame_in(self, package: str) -> Optional[StackFrame]:
        """
        Return the outermost :class:`~krrood.entity_query_language._stack.StackFrame`
        whose ``module_name`` contains *package*.

        This identifies the highest-level entry point into *package* that
        triggered the inference, which is useful for understanding where inside
        your own library the query was constructed.

        :param package: Substring matched against ``StackFrame.module_name``.
        :return: The outermost matching frame, or ``None`` if no frame matches.
        """
        return self.stack.root_frame_in(package)

    def get_satisfied_condition_expressions_for_the_instance(
        self,
    ) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that were satisfied during the inference of the instance.
        """
        explanation = self.create_explanation_variable()
        node = self.create_query_node_variable(explanation)
        return entity(node).where(
            explanation.satisfied_condition_ids != None,
            contains(explanation.satisfied_condition_ids, node_id(node)),
        ).distinct()

    def get_values_of_variable_nodes_of_given_type(
        self, type_: Type
    ) -> Entity[SymbolicExpression]:
        """
        :param type_: The type of the variable nodes to retrieve.
        :return: An entity containing variable nodes of the specified type that participated in the inference of the instance.
        """
        explanation = self.create_explanation_variable()
        node = self.get_variable_nodes_of_given_type(
            type_, self.create_query_node_variable(explanation)
        )
        operation_result = explanation.operation_result
        return (
            entity(operation_result.all_bindings[node_id_ := node_id(node)])
            .where(contains(operation_result.all_bindings, node_id_))
            .distinct()
        )

    def get_variable_nodes_of_given_type(
        self, type_: Type, node_variable: Optional[SymbolicExpression] = None
    ) -> Entity[SymbolicExpression] | SymbolicExpression:
        """
        :return: An entity containing instances that participated in the inference of this instance.
        """
        if node_variable is None:
            node_variable = self.create_query_node_variable(self.create_explanation_variable())
        return (
            entity(node_variable)
            .where(
                HasType(node_variable, Selectable),
                (node_type_ := node_type(node_variable)) != None,
                is_class(node_type_),
                issubclass_(node_type_, type_),
            )
            .distinct(node_variable)
        )

    def get_satisfied_comparator_conditions(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that are comparators and were satisfied during the
         inference of the instance.
        """
        condition_node = self.get_satisfied_condition_expressions_for_the_instance()
        return (
            entity(condition_node).where(HasType(condition_node, Comparator)).distinct()
        )

    def get_satisfied_comparator_conditions_between_attributes(
        self,
    ) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that are comparators and were satisfied during the
         inference of the instance and have Attribute nodes as both their left and right children.
        """
        condition_node = self.get_satisfied_condition_expressions_for_the_instance()
        return (
            entity(condition_node)
            .where(
                HasType(condition_node, Comparator),
                HasType(condition_node.left, Attribute),
                HasType(condition_node.right, Attribute),
            )
            .distinct()
        )

    def get_conditions_that_relate_the_variables_of_type(
        self, type_: Type
    ) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that relate the participating instances in the inference of this instance.
        """
        from krrood.entity_query_language.core.variable import InstantiatedVariable

        condition_node = self.get_satisfied_condition_expressions_for_the_instance()
        child1 = flat_variable(node_children(condition_node))
        child2 = flat_variable(node_children(condition_node))

        def make_type_checker(child):
            # Use exists(node, conditions) directly — avoids the _expression_/An-quantifier
            # problem that arises when passing a built entity to exists().  When .build() is
            # called on an entity, _expression_ is set to an An quantifier; _update_children_
            # then passes that An to Exists.left, and An._evaluate__ ignores sources entirely.
            node = concatenation(child, flat_variable(node_descendants(child)))
            node_type_ = node_type(node)
            return exists(node, and_(
                HasType(node, Selectable),
                node_type_ != None,
                is_class(node_type_),
                issubclass_(node_type_, type_),
            ))

        return (
            entity(condition_node)
            .where(
                HasType(condition_node, (Comparator, InstantiatedVariable)),
                node_id(child1) != node_id(child2),
                make_type_checker(child1),
                make_type_checker(child2),
            )
            .distinct()
        )

    def get_conditions_that_relate_variables_of_types(
        self, type_a: Type, type_b: Type
    ) -> Entity[SymbolicExpression]:
        """
        Generalisation of :meth:`get_conditions_that_relate_the_variables_of_type` for two
        potentially different types.  Returns satisfied condition expressions that have at least one
        descendant variable node whose ``_type_`` is a subclass of *type_a* and at least one
        (different) descendant variable node whose ``_type_`` is a subclass of *type_b*.

        When ``type_a == type_b`` the semantics reduce to
        :meth:`get_conditions_that_relate_the_variables_of_type`.

        :param type_a: First participant type.
        :param type_b: Second participant type.
        :return: An entity containing the matching condition expressions.
        """
        from krrood.entity_query_language.core.variable import InstantiatedVariable

        condition_node = self.get_satisfied_condition_expressions_for_the_instance()
        desc_a = flat_variable(node_descendants(condition_node))
        desc_b = flat_variable(node_descendants(condition_node))

        def make_type_exists(node_var, type_):
            node_type_ = node_type(node_var)
            return exists(node_var, and_(
                HasType(node_var, Selectable),
                node_type_ != None,
                is_class(node_type_),
                issubclass_(node_type_, type_),
            ))

        return (
            entity(condition_node)
            .where(
                HasType(condition_node, (Comparator, InstantiatedVariable)),
                node_id(desc_a) != node_id(desc_b),
                make_type_exists(desc_a, type_a),
                make_type_exists(desc_b, type_b),
            )
            .distinct(node_id(condition_node))
        )

    @staticmethod
    def create_query_node_variable(
        explanation_variable: Selectable[InferenceExplanation] | InferenceExplanation,
    ) -> FlatVariable[SymbolicExpression] | SymbolicExpression:
        return flat_variable(node_descendants(explanation_variable.query_root))

    def create_explanation_variable(
        self,
    ) -> Selectable[InferenceExplanation] | InferenceExplanation:
        """
        :return: A variable representing the explanation in the inference process.
        """
        return variable_from(self)


def register_inference(
    instance: Any,
    variable_node: SymbolicExpression,
    result: Optional[OperationResult] = None,
) -> None:
    """
    Register an instance created via inference by attaching an :class:`InferenceExplanation`
    directly to the instance.

    Only :class:`~krrood.symbol_graph.symbol_graph.Symbol` instances are supported.
    Non-Symbol values (plain ints, strings, frozen third-party objects) are silently
    ignored so that callers need no special-casing.

    The explanation is stored directly as the ``_inference_explanation_`` field on
    the instance (declared in :class:`~krrood.symbol_graph.symbol_graph.Symbol`),
    keeping the explanation's lifecycle identical to the instance's lifecycle — no
    separate global registry is needed.

    :param instance: The instance to record.
    :param variable_node: The variable node that produced the instance.
    :param result: The OperationResult from the evaluation, carrying satisfied condition IDs.
    """
    if not isinstance(instance, Symbol):
        return
    if not monitored.is_monitored(type(variable_node)):
        return

    satisfied_ids = result.satisfied_condition_ids if result else None
    explanation = InferenceExplanation(
        query_node=variable_node,
        stack=monitored.get_stack(variable_node) or CallStack([]),
        query_root=variable_node._root_,
        satisfied_condition_ids=satisfied_ids,
        operation_result=result,
    )
    try:
        explanation._instance_ref = weakref.ref(instance)
    except TypeError:
        explanation._instance_ref = lambda: instance  # type: ignore[assignment]
    instance._inference_explanation_ = explanation


def explain_inference(instance: Any) -> Optional[InferenceExplanation]:
    """
    Retrieve the explanation of how the given instance was created through inference.

    Returns ``None`` for non-:class:`~krrood.symbol_graph.symbol_graph.Symbol` values
    or for Symbol instances that were not produced by an inference variable.

    :param instance: The instance to explain.
    :return: An :class:`InferenceExplanation` if the instance was inferred, otherwise ``None``.
    """
    if not isinstance(instance, Symbol):
        return None
    return instance._inference_explanation_
