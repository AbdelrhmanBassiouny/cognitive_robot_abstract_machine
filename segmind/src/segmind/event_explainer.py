from __future__ import annotations

import operator
from dataclasses import dataclass
from inspect import isclass
from typing import Optional

from graphql.pyutils import cached_property
from typing_extensions import Type, Any

from krrood.entity_query_language.core.base_expressions import SymbolicExpression, Selectable
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable, Attribute
from krrood.entity_query_language.core.variable import Variable, InstantiatedVariable, Literal
from krrood.entity_query_language.explanation import explain_inference, InferenceExplanation
from krrood.entity_query_language.factories import variable_from, entity, contains, flat_variable, node_id, \
    node_descendants
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.predicate import HasType, symbolic_function
from krrood.entity_query_language.query.query import Entity
from segmind.datastructures.events import DetectionEvent, InsertionEvent, PlacingEvent, PickUpEvent, SupportEvent, \
    LossOfSupportEvent, ContainmentEvent, LossOfContainmentEvent, TranslationEvent


@symbolic_function
def node_type(node: CanBehaveLikeAVariable) -> Optional[Type]:
    return node._type_


@symbolic_function
def node_children(node: CanBehaveLikeAVariable) -> Entity[Selectable]:
    return node._children_


@symbolic_function
def issubclass_(cls: Type, cls_or_tuple: Type) -> bool:
    return issubclass(cls, cls_or_tuple)


@symbolic_function
def is_class(obj: object) -> bool:
    return isclass(obj)


@symbolic_function
def type_(obj: Any) -> Type:
    return obj.__class__


@dataclass
class EventExplainer:
    """
    Provides explanation for a detected event in the Segmind episode.
    """

    event: DetectionEvent
    """
    The event for which the explanation is requested.
    """

    def get_satisfied_condition_expressions_for_a_detected_event(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that were satisfied during the inference of the event.
        """
        explanation = self.explanation_variable
        node = self.create_query_node_variable()
        return entity(node).where(explanation.satisfied_condition_ids != None,
                                  contains(explanation.satisfied_condition_ids, node_id(node)))

    def get_participating_events_in_detection(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing events that participated in the inference of the event.
        """
        explanation = self.explanation_variable
        node = self.get_participating_event_nodes()
        operation_result = explanation.operation_result
        return entity(operation_result[node_id(node)]).where(contains(operation_result, node_id(node))).distinct()

    def get_participating_event_nodes(self, node_variable: Optional[SymbolicExpression] = None) -> Entity[
        SymbolicExpression]:
        """
        :return: An entity containing events that participated in the inference of the event.
        """
        if node_variable is None:
            node_variable = self.create_query_node_variable()
        return entity(node_variable).where(HasType(node_variable, Selectable),
                                           node_type(node_variable) != None,
                                           is_class(node_type(node_variable)),
                                           issubclass_(node_type(node_variable), DetectionEvent)).distinct(
            node_id(node_variable))

    def get_conditions_that_relate_the_participating_events(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing condition expressions that relate the participating events in the inference of the event.
        """
        condition_node = self.get_satisfied_condition_expressions_for_a_detected_event()
        condition_node_descendant_1 = self.get_participating_event_nodes(
            flat_variable(node_descendants(condition_node)))
        condition_node_descendant_2 = self.get_participating_event_nodes(
            flat_variable(node_descendants(condition_node)))
        return entity(condition_node).where(HasType(condition_node, (Comparator, InstantiatedVariable)),
                                            node_id(condition_node_descendant_1) != node_id(
                                                condition_node_descendant_2)).distinct(node_id(condition_node))

    @cached_property
    def condition_node_variable(self) -> Variable | SymbolicExpression:
        explanation = self.explanation_variable
        node = self.query_node_variable
        return entity(node).where(explanation.satisfied_condition_ids != None,
                                  contains(explanation.satisfied_condition_ids, node_id(node)))

    @cached_property
    def query_node_variable(self) -> Variable | SymbolicExpression:
        """
        :return: The variable representing the node in the query for the participating events.
        """
        return self.create_query_node_variable()

    def create_query_node_variable(self) -> Variable:
        return flat_variable(node_descendants(self.explanation_variable.query_root))

    @cached_property
    def explanation_variable(self) -> Variable | InferenceExplanation:
        """
        :return: The variable representing the explanation in the inference process.
        """
        return variable_from(explain_inference(self.event))

    @cached_property
    def explanation(self) -> Optional[InferenceExplanation]:
        """
        :return: The full inference explanation for the event.
        """
        return explain_inference(self.event)
