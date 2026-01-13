from __future__ import annotations

from abc import abstractmethod, ABC
from collections import defaultdict
from dataclasses import dataclass, field, fields
from functools import cached_property, lru_cache

from line_profiler import profile

from . import logger
from typing_extensions import (
    ClassVar,
    Set,
    Type,
    Optional,
    Any,
    Iterable,
    Dict,
    Union,
    Tuple,
    DefaultDict,
)

from .mixins import TransitiveProperty, HasChainAxioms, SymmetricProperty
from .monitored_container import (
    MonitoredContainer,
    monitored_type_map,
)
from .property_descriptor_relation import PropertyDescriptorRelation
from ..failures import UnMonitoredContainerTypeForDescriptor
from ...class_diagrams.class_diagram import (
    WrappedClass,
    Association,
    AssociationThroughRoleTaker,
)
from ...class_diagrams.wrapped_field import WrappedField
from ...entity_query_language.predicate import Symbol, Predicate
from ...entity_query_language.symbol_graph import (
    SymbolGraph,
)
from ...entity_query_language.utils import make_set

SymbolType = Type[Symbol]
"""
Type alias for symbol types.
"""
DomainRangeMap = Dict[SymbolType, SymbolType]
"""
Type alias for the domain-range map.
"""


@dataclass(eq=False)
class PropertyDescriptor(Symbol):
    """Descriptor managing a data class field while giving it metadata like superproperties,
    sub-properties, inverse, transitivity, ...etc.

    The descriptor injects a hidden dataclass-managed attribute (backing storage) into the owner class
    and collects domain and range types for introspection.

    The way this should be used is after defining your dataclasses you declare either in the same file or in a separate
    file the descriptors for each field that is considered a relation between two symbol types.

    Example:
        >>> from krrood.ontomatic.property_descriptor.mixins import HasInverseProperty
        >>> from dataclasses import dataclass
        >>> from krrood.ontomatic.property_descriptor.property_descriptor import PropertyDescriptor
        >>> @dataclass
        ... class Company(Symbol):
        ...     name: str
        ...     members: Set[Person] = field(default_factory=set)
        ...
        >>> @dataclass
        ... class Person(Symbol):
        ...     name: str
        ...     works_for: Set[Company] = field(default_factory=set)
        ...
        >>> @dataclass
        >>> class Member(PropertyDescriptor):
        ...     pass
        ...
        >>> @dataclass
        ... class MemberOf(PropertyDescriptor, HasInverseProperty):
        ...     @classmethod
        ...     def get_inverse(cls) -> Type[PropertyDescriptor]:
        ...         return Member
        ...
        >>> @dataclass
        >>> class WorksFor(MemberOf):
        ...     pass
        ...
        >>> Person.works_for = WorksFor(Person, "works_for")
        >>> Company.members = Member(Company, "members")
    """

    domain: SymbolType
    """
    The domain type for this descriptor instance.
    """
    field_name: str
    """
    The name of the field on the domain type that this descriptor instance manages.
    """
    wrapped_field: WrappedField = field(init=False)
    """
    The wrapped field instance that this descriptor instance manages.
    """
    obj_attr_map: Dict[Symbol, Any] = field(default_factory=dict)
    """
    A mapping from owner instances to the managed attribute values.
    """
    domain_range_map: ClassVar[
        DefaultDict[Type[PropertyDescriptor], DomainRangeMap]
    ] = defaultdict(dict)
    """
    A mapping from descriptor class to the mapping from domain types to range types for that descriptor class.
    """
    all_domains: ClassVar[Dict[Type[PropertyDescriptor], Set[SymbolType]]] = (
        defaultdict(set)
    )
    """
    A set of all domain types for this descriptor class.
    """
    all_ranges: ClassVar[Dict[Type[PropertyDescriptor], Set[SymbolType]]] = defaultdict(
        set
    )
    """
    A set of all range types for this descriptor class.
    """
    chain_axioms: ClassVar[
        Dict[
            Type[PropertyDescriptor],  # Participant Descriptor
            Dict[
                Tuple[Type[PropertyDescriptor], Tuple[Type[PropertyDescriptor], ...]],
                Set[int],
            ],
        ]
    ] = defaultdict(lambda: defaultdict(set))

    def __post_init__(self):
        self._validate_non_redundant_domain()
        self._update_wrapped_field()
        self._update_domain_and_range()
        if HasChainAxioms in self.__class__.__bases__:
            self.register_chain_axioms_for_target(self.__class__)

    @classmethod
    def register_chain_axioms_for_target(
        cls,
        target: Type[HasChainAxioms],
    ):
        """
        Register a chain axiom.
        """
        for chain in target.get_chain_axioms():
            for i, descriptor in enumerate(chain):
                cls.chain_axioms[descriptor][(target, chain)].add(i)

    def _validate_non_redundant_domain(self):
        """
        Validate that this exact descriptor type has not already been defined for this domain type.
        """
        if self.domain in self.domain_range_map[self.__class__]:
            raise ValueError(
                f"Domain {self.domain} already exists, cannot define same descriptor more than once in "
                f"the same class"
            )

    def _update_wrapped_field(self):
        """
        Set the wrapped field attribute using the domain type and field name.
        """
        field_ = [f for f in fields(self.domain) if f.name == self.field_name][0]
        self.wrapped_field = WrappedField(
            WrappedClass(self.domain), field_, property_descriptor=self
        )

    @cached_property
    def is_iterable(self):
        """Whether the field is iterable or not"""
        return self.wrapped_field.is_iterable

    def _update_domain_and_range(self):
        """
        Update the domain and range sets and the domain-range map for this descriptor type.
        """
        range_type = self.wrapped_field.type_endpoint
        # assert issubclass(range_type, Symbol)
        self.domain_range_map[self.__class__][self.domain] = range_type
        self.all_domains[self.__class__].add(self.domain)
        self.all_ranges[self.__class__].add(range_type)
        for super_class in self.__class__.__mro__:
            if (super_class is PropertyDescriptor) or not issubclass(
                super_class, PropertyDescriptor
            ):
                continue
            self.all_domains[super_class].add(self.domain)
            self.all_ranges[super_class].add(range_type)

    @cached_property
    def range(self) -> SymbolType:
        """
        The range type for this descriptor instance.
        """
        return self.domain_range_map[self.__class__][self.domain]

    def add_relation_to_the_graph_and_apply_implications(
        self, domain_value: Symbol, range_value: Symbol, inferred: bool = False
    ) -> None:
        """
        Add the relation between the domain_value and the range_value to the symbol graph and apply all implications of
        the relation.

        :param domain_value: The domain value (i.e., the instance that this descriptor is attached to).
        :param range_value: The range value (i.e., the value to set on the managed attribute, and is the target of the
         relation).
        :param inferred: Whether the relation is inferred or not.
        """
        if domain_value is not None and range_value is not None:
            for v in make_set(range_value):
                PropertyDescriptorRelation(
                    domain_value, v, self.wrapped_field, inferred=inferred
                ).add_to_graph_and_apply_implications()

    def __get__(self, obj, objtype=None):
        """
        Get the value of the managed attribute. In addition, ensure that the value is a monitored container type if
        it is an iterable and that the owner instance is bound to the monitored container.

        :param obj: The owner instance (i.e., the instance that this descriptor is attached to).
        :param objtype: The owner type.
        """
        if obj is None:
            return self
        value = self.obj_attr_map.get(obj, None)
        self._bind_owner_if_container_type(value, owner=obj)
        return value

    @staticmethod
    def _bind_owner_if_container_type(
        value: Union[Iterable[Symbol], Symbol], owner: Optional[Any] = None
    ):
        """
        Bind the owner instance to the monitored container if the value is a MonitoredContainer type.

        :param value: The value to check and bind the owner to if it is a MonitoredContainer type.
        :param owner: The owner instance.
        """
        if (
            isinstance(value, MonitoredContainer)
            and getattr(value, "owner", None) is not owner
        ):
            value._bind_owner(owner)

    def _ensure_monitored_type(
        self, value: Union[Iterable[Symbol], Symbol], obj: Optional[Any] = None
    ) -> Union[MonitoredContainer[Symbol], Symbol]:
        """
        Ensure that the value is a monitored container type or is not iterable.

        :param value: The value to ensure its type.
        :param obj: The owner instance.
        :return: The value with a monitored container-type if it is iterable, otherwise the value itself.
        """
        if self.is_iterable and not isinstance(value, MonitoredContainer):
            try:
                monitored_type = monitored_type_map[type(value)]
            except KeyError:
                raise UnMonitoredContainerTypeForDescriptor(
                    self.domain, self.wrapped_field.name, type(value)
                )
            monitored_value = monitored_type(descriptor=self)
            for v in make_set(value):
                monitored_value._add_item(v, inferred=False)
            value = monitored_value
        return value

    def __set__(self, obj, value):
        """
        Set the value of the managed attribute and add it to the symbol graph.

        :param obj: The owner instance.
        :param value: The value to set.
        """
        if isinstance(value, PropertyDescriptor):
            return
        attr = self.obj_attr_map.get(obj, None)
        if self.is_iterable and not isinstance(attr, MonitoredContainer):
            attr = self._ensure_monitored_type(value, obj)
            self._bind_owner_if_container_type(attr, owner=obj)
            self.obj_attr_map[obj] = attr
        if isinstance(attr, MonitoredContainer):
            attr._clear()
            for v in make_set(value):
                attr._add_item(v, inferred=False)
        else:
            if (
                issubclass(self.__class__, SymmetricProperty)
                and self.__class__.__name__ == "HasCollaborationWith"
            ):
                logger.info(
                    f"Setting symmetric property {self.__class__.__name__} on {type(obj).__name__} to {type(value).__name__}"
                )
            self.obj_attr_map[obj] = value
            self.add_relation_to_the_graph_and_apply_implications(obj, value)

    @profile
    def update_value(
        self,
        domain_value: Symbol,
        range_value: Symbol,
        inferred: bool = False,
    ) -> bool:
        """Update the value of the managed attribute

        :param domain_value: The domain value to update (i.e., the instance that this descriptor is attached to).
        :param range_value: The range value to update (i.e., the value to set on the managed attribute).
        """
        v = getattr(domain_value, self.field_name)
        updated = False
        if isinstance(v, MonitoredContainer):
            updated = v._update(
                range_value, add_relation_to_the_graph=False, inferred=inferred
            )
        elif v != range_value:
            self.obj_attr_map[domain_value] = range_value
            updated = True
        return updated

    @classmethod
    @lru_cache(maxsize=None)
    def get_association_of_source_type(
        cls,
        domain_type: Union[Type[Symbol], WrappedClass],
    ) -> Optional[Union[Association, AssociationThroughRoleTaker]]:
        """
        Get the association that has as a source the given domain type and as a field type this descriptor class.

        :param domain_type: The domain type that has an associated field with this descriptor class.
        """
        class_diagram = SymbolGraph().class_diagram
        association_condition = (
            lambda association: type(association.field.property_descriptor) is cls
        )
        result = next(
            class_diagram.get_outgoing_associations_with_condition(
                domain_type, association_condition
            ),
            None,
        )
        return result

    @classmethod
    @lru_cache(maxsize=None)
    def get_association_of_target_type(
        cls,
        target_type: Union[Type[Symbol], WrappedClass],
    ) -> Optional[Union[Association, AssociationThroughRoleTaker]]:
        """
        Get the association that has the given target type and as a field type this descriptor class.

        :param target_type: The target type that is associated by a field with this descriptor class.
        """
        class_diagram = SymbolGraph().class_diagram
        association_condition = (
            lambda association: type(association.field.property_descriptor) is cls
        )
        result = next(
            class_diagram.get_incoming_associations_with_condition(
                target_type, association_condition
            ),
            None,
        )
        return result

    @classmethod
    @lru_cache(maxsize=None)
    def get_superproperties_associations(
        cls,
        domain_type: Union[SymbolType, WrappedClass],
        direct: bool = True,
    ) -> Tuple[Association, ...]:
        """
        :param domain_type: The domain type that has the required association(s).
        :param direct: Whether to get only direct superproperties or all superproperties.
        :return: The associations that have the given domain type as a source and have a descriptor type that
         is a super class of this descriptor class.
        """

        def association_condition(association: Association) -> bool:
            if direct:
                sub_class_condition = (
                    type(association.field.property_descriptor) in cls.__bases__
                )
            else:
                sub_class_condition = (
                    issubclass(type(association.field.property_descriptor), cls)
                    and type(association.field.property_descriptor) is not cls
                )
            return sub_class_condition

        class_diagram = SymbolGraph().class_diagram

        associations_generator = class_diagram.get_outgoing_associations_with_condition(
            domain_type, association_condition
        )
        return tuple(associations_generator)

    def __hash__(self):
        return hash(id(self))

    def __eq__(self, other):
        return id(self) == id(other)
