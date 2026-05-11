from __future__ import annotations

from dataclasses import dataclass
from inspect import isclass
from typing import Optional

from graphql.pyutils import cached_property
from typing_extensions import TYPE_CHECKING, Type

from krrood.entity_query_language.core.base_expressions import SymbolicExpression, Selectable
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.explanation import explain_inference, InferenceExplanation
from krrood.entity_query_language.factories import variable_from, entity, contains, flat_variable, node_id, \
    node_descendants, variable
from krrood.entity_query_language.predicate import HasType, symbolic_function
from krrood.entity_query_language.query.query import Entity

if TYPE_CHECKING:
    from segmind.datastructures.events import DetectionEvent


@symbolic_function
def node_type(node: CanBehaveLikeAVariable) -> Optional[Type]:
    return node._type_


@symbolic_function
def issubclass_(cls: Type, cls_or_tuple: Type) -> bool:
    return issubclass(cls, cls_or_tuple)


@symbolic_function
def is_class(obj: object) -> bool:
    return isclass(obj)


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
        explanation = variable_from(explain_inference(self.event))
        node = flat_variable(node_descendants(explanation.query_root))
        return entity(node).where(explanation.satisfied_condition_ids != None,
                                  contains(explanation.satisfied_condition_ids, node_id(node)))

    def get_participating_events_in_detection(self) -> Entity[SymbolicExpression]:
        """
        :return: An entity containing events that participated in the inference of the event.
        """
        from segmind.datastructures.events import DetectionEvent
        explanation = variable_from(explain_inference(self.event))
        node = flat_variable(node_descendants(explanation.query_root))
        operation_result = explanation.operation_result
        return entity(operation_result[node_id(node)]).where(HasType(node, Selectable),
                                                                         node_type(node) != None,
                                                                         is_class(node_type(node)),
                                                                         issubclass_(node_type(node), DetectionEvent),
                                                                         contains(operation_result, node_id(node))).distinct()

    @cached_property
    def explanation(self) -> Optional[InferenceExplanation]:
        """
        :return: The full inference explanation for the event.
        """
        return explain_inference(self.event)
