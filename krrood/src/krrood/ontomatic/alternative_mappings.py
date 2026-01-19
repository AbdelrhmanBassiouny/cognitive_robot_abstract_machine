from dataclasses import dataclass

from krrood.ontomatic.property_descriptor.property_descriptor import (
    PropertyDescriptor,
)
from krrood.entity_query_language.predicate import Symbol
from krrood.ontomatic.property_descriptor.monitored_container import MonitoredSet
from typing_extensions import Type, Self, List

from ..ormatic.dao import AlternativeMapping


@dataclass
class MonitoredSetMapping(AlternativeMapping[MonitoredSet]):
    """
    Alternative mapping for functions.
    """

    descriptor_type: Type[PropertyDescriptor]
    """
    The type of the property descriptor.
    """
    domain_class: Type
    """
    The domain class where the property descriptor is defined.
    """
    range_class: Type
    """
    The range class of the property descriptor.
    """
    data: List[Symbol]
    """
    The data contained in the monitored set.
    """

    @classmethod
    def from_domain_object(cls, obj: MonitoredSet) -> Self:

        dao = cls(
            descriptor_type=type(obj._descriptor),
            domain_class=obj._descriptor.domain,
            range_class=obj._descriptor.range,
            data=list(obj),
        )
        return dao

    def to_domain_object(self) -> MonitoredSet:

        return MonitoredSet(self.data)
