from __future__ import annotations

import inspect
import weakref
from dataclasses import dataclass, field
from functools import cached_property
from types import ModuleType
from typing import Any, List, Optional, Type, Union
from uuid import UUID

from ordered_set import OrderedSet
from typing_extensions import TYPE_CHECKING

# Import monitoring infrastructure from the isolated sub-module that has no
# EQL dependencies, breaking the variable.py ↔ explanation.py import cycle.
from krrood.entity_query_language._monitoring import (
    filter_stack,
    MonitoredRegistry,
    monitored,
)

from krrood.entity_query_language.predicate import HasType
from krrood.entity_query_language.factories import (
    entity, contains, node_id, node_type, is_class, issubclass_,
    node_descendants, flat_variable, variable_from,
)
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import LogicalOperator
from krrood.entity_query_language.core.base_expressions import Selectable

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import (
        OperationResult, SymbolicExpression,
    )
    from krrood.entity_query_language.core.variable import Variable, InstantiatedVariable
    from krrood.entity_query_language.query.query import Query, Entity


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
class InferenceExplanation:
    """
    Explanation of how an instance was created through inference.
    """

    instance: Any
    """
    The instance that was created.
    """
    query_node: SymbolicExpression
    """
    The query node that was used to create the instance.
    """
    stack: List[inspect.FrameInfo]
    """
    The stack trace at the point of creation.
    """
    query_root: Optional[Query] = None
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

    def get_satisfied_conditions_as_string(self) -> str:
        """
        Returns a string representation of the satisfied conditions, joined by ' AND '.
        """
        return '\nAND '.join(str(c) for c in self.get_satisfied_conditions_and_their_bindings())

    def get_satisfied_conditions_and_their_bindings(self) -> List[ConditionAndBindings]:
        """
        Retrieve the list of satisfied condition expressions along with their bindings.

        :return: A list of :class:`ConditionAndBindings` objects, each containing a satisfied condition expression and
        its corresponding bindings. Returns an empty list if no satisfaction data is available.
        """
        if self.operation_result is None or not self.operation_result.satisfied_condition_ids:
            return []

        satisfied_conditions = []
        for condition_id in self.operation_result.satisfied_condition_ids:
            condition_expr = self.query_root._get_expression_by_id_(condition_id)
            if isinstance(condition_expr, (LogicalOperator, )):
                continue
            if condition_expr is not None:
                satisfied_conditions.append(ConditionAndBindings(condition_expr, self.operation_result.all_bindings))
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

    def as_string(
            self, focus_package: Optional[str | ModuleType] = None
    ) -> str:
        """
        Convert an InferenceExplanation into a human-readable string.

        :param focus_package: Optional package name to filter the stack further.
        :return: A formatted string explaining the inference.
        """
        if isinstance(focus_package, ModuleType):
            focus_package = focus_package.__name__
        display_stack = filter_stack(self.stack, internal_package=focus_package)

        formatted_stack = []
        for frame_info in display_stack:
            formatted_stack.append(
                f'  File "{frame_info.filename}", line {frame_info.lineno}, in {frame_info.function}\n'
                f'    {frame_info.code_context[0].strip() if frame_info.code_context else "???"}\n'
            )

        stack_str = "".join(formatted_stack[:10])  # Limit to 10 frames

        return (
            f"Instance {self.instance} was created by inference variable: {self.query_node}\n"
            f"Part of query: {self.query_root}\n"
            f"Call stack at definition:\n{stack_str}"
        )

    def get_satisfied_condition_expressions_for_the_instance(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that were satisfied during the inference of the instance.
        """
        explanation = self.explanation_variable
        node = self.create_query_node_variable()
        return entity(node).where(explanation.satisfied_condition_ids != None,
                                  contains(explanation.satisfied_condition_ids, node_id(node)))

    def get_values_of_variable_nodes_of_given_type(self, type_: Type) -> Entity[SymbolicExpression]:
        """
        :param type_: The type of the variable nodes to retrieve.
        :return: An entity containing variable nodes of the specified type that participated in the inference of the instance.
        """
        explanation = self.explanation_variable
        node = self.get_variable_nodes_of_given_type(type_)
        operation_result = explanation.operation_result
        return entity(operation_result.all_bindings[node_id(node)]).where(contains(operation_result.all_bindings, node_id(node))).distinct()

    def get_variable_nodes_of_given_type(self, type_: Type, node_variable: Optional[SymbolicExpression] = None) -> Entity[
        SymbolicExpression]:
        """
        :return: An entity containing instances that participated in the inference of this instance.
        """
        if node_variable is None:
            node_variable = self.create_query_node_variable()
        return entity(node_variable).where(HasType(node_variable, Selectable),
                                           node_type(node_variable) != None,
                                           is_class(node_type(node_variable)),
                                           issubclass_(node_type(node_variable), type_)).distinct(
            node_id(node_variable))

    def get_conditions_that_relate_the_variables_of_type(self, type_: Type) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that relate the participating instances in the inference of this instance.
        """
        from krrood.entity_query_language.core.variable import InstantiatedVariable
        condition_node = self.get_satisfied_condition_expressions_for_the_instance()
        condition_node_descendant_1 = self.get_variable_nodes_of_given_type(
            type_, flat_variable(node_descendants(condition_node)))
        condition_node_descendant_2 = self.get_variable_nodes_of_given_type(
            type_, flat_variable(node_descendants(condition_node)))
        return entity(condition_node).where(HasType(condition_node, (Comparator, InstantiatedVariable)),
                                            node_id(condition_node_descendant_1) != node_id(
                                                condition_node_descendant_2)).distinct(node_id(condition_node))

    def get_conditions_that_relate_variables_of_types(self, type_a: Type, type_b: Type) -> Entity[SymbolicExpression]:
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
        descendant_a = self.get_variable_nodes_of_given_type(
            type_a, flat_variable(node_descendants(condition_node)))
        descendant_b = self.get_variable_nodes_of_given_type(
            type_b, flat_variable(node_descendants(condition_node)))
        return entity(condition_node).where(
            HasType(condition_node, (Comparator, InstantiatedVariable)),
            node_id(descendant_a) != node_id(descendant_b),
        ).distinct(node_id(condition_node))

    @cached_property
    def condition_node_variable(self) -> Variable | SymbolicExpression:
        explanation = self.explanation_variable
        node = self.query_node_variable
        return entity(node).where(explanation.satisfied_condition_ids != None,
                                  contains(explanation.satisfied_condition_ids, node_id(node)))

    @cached_property
    def query_node_variable(self) -> Variable | SymbolicExpression:
        """
        :return: The variable representing the node in the query for the participating instances.
        """
        return self.create_query_node_variable()

    def create_query_node_variable(self) -> Variable:
        return flat_variable(node_descendants(self.explanation_variable.query_root))

    @cached_property
    def explanation_variable(self) -> Variable | InferenceExplanation:
        """
        :return: The variable representing the explanation in the inference process.
        """
        return variable_from(self)


# Dictionary to store inference explanations for instances.
# Uses weak references to allow instances to be garbage collected.
INFERENCE_RECORD: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def register_inference(
        instance: Any, variable_node: SymbolicExpression, result: Optional[OperationResult] = None
) -> None:
    """
    Register an instance created via inference into the internal records.

    :param instance: The instance to record.
    :param variable_node: The variable node that produced the instance.
    :param result: The OperationResult from the evaluation, carrying satisfied condition IDs.
    """
    if not monitored.is_monitored(type(variable_node)):
        return

    satisfied_ids = result.satisfied_condition_ids if result else None
    explanation = InferenceExplanation(
        instance=instance,
        query_node=variable_node,
        stack=monitored.get_stack(variable_node) or [],
        query_root=variable_node._root_,
        satisfied_condition_ids=satisfied_ids,
        operation_result=result,
    )
    try:
        INFERENCE_RECORD[instance] = explanation
    except TypeError:
        pass


def explain_inference(instance: Any) -> Optional[InferenceExplanation]:
    """
    Retrieve the explanation of how the given instance was created through inference.

    :param instance: The instance to explain.
    :return: An InferenceExplanation object if found, otherwise None.
    """
    try:
        return INFERENCE_RECORD.get(instance)
    except TypeError:
        return None
