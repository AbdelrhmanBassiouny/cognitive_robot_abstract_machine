from __future__ import annotations

from abc import abstractmethod, ABC
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field, fields
from functools import cached_property, lru_cache
from types import ModuleType

from krrood.ontomatic.property_descriptor.mixins import IrreflexiveProperty
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
    List,
)

from .mixins import TransitiveProperty, HasChainAxioms, SymmetricProperty
from .monitored_container import (
    MonitoredContainer,
    monitored_type_map,
)
from .property_descriptor_relation import PropertyDescriptorRelation
from ..failures import UnMonitoredContainerTypeForDescriptor
from ..utils import NamingRegistry
from ...class_diagrams import ClassDiagram
from ...class_diagrams.class_diagram import (
    WrappedClass,
    Association,
    AssociationThroughRoleTaker,
)
from ...class_diagrams.utils import Role
from ...class_diagrams.wrapped_field import WrappedField
from ...class_diagrams.utils import issubclass_or_role
from ...entity_query_language.entity import and_, variable
from ...entity_query_language.enums import PredicateType
from ...entity_query_language.predicate import Symbol, Predicate
from ...entity_query_language.symbol_graph import (
    SymbolGraph,
)
from ...entity_query_language.symbolic import Variable
from ...entity_query_language.utils import make_set
from ...ormatic.utils import classes_of_module
from ...utils import recursive_subclasses

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
    descriptor_instances_by_domain_type: ClassVar[
        Dict[Type[PropertyDescriptor], Dict[SymbolType, PropertyDescriptor]]
    ] = defaultdict(dict)
    """
    A mapping from domain types to the descriptor instances that manage attributes of that type.
    """
    descriptor_instances_by_range_type: ClassVar[
        Dict[Type[PropertyDescriptor], Dict[SymbolType, PropertyDescriptor]]
    ] = defaultdict(dict)
    """
    A mapping from range types to the descriptor instances that manage attributes of that type.
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
    """
    A mapping from participant descriptor classes to a mapping from chain of participant descriptor classes to the
    indices of the participant descriptors in the chain that are chain axiom participants."""

    def __post_init__(self):
        self._validate_non_redundant_domain()
        self._update_wrapped_field()
        self._update_domain_and_range()
        if HasChainAxioms in self.__class__.__bases__:
            self.register_chain_axioms_for_target(self.__class__)

    @classmethod
    def super_classes(cls) -> Tuple[Type[PropertyDescriptor], ...]:
        return tuple(
            b
            for b in cls.__bases__
            if b is not PropertyDescriptor and issubclass(b, PropertyDescriptor)
        )

    @classmethod
    def get_field_name(cls) -> str:
        return NamingRegistry.to_snake_case(cls.__name__)

    @classmethod
    def get_descriptor_instance_for_domain_type(
        cls, domain_type: SymbolType
    ) -> PropertyDescriptor:
        mro = list(domain_type.__mro__)
        if Role in mro:
            for i, t in enumerate(copy(mro)):
                if t is Role:
                    mro.insert(i, domain_type.get_role_taker_type())
                    mro.remove(Role)
        for d_type in mro:
            if d_type in cls.descriptor_instances_by_domain_type[cls]:
                return cls.descriptor_instances_by_domain_type[cls][d_type]
        raise ValueError(
            f"No descriptor instances found for domain type {domain_type} and descriptor type {cls}"
        )

    @classmethod
    def get_descriptor_instance_for_range_type(
        cls, range_type: SymbolType
    ) -> PropertyDescriptor:
        for r_type in range_type.__mro__:
            if r_type in cls.descriptor_instances_by_domain_type[cls]:
                return cls.descriptor_instances_by_range_type[cls][r_type]
        raise ValueError(f"No descriptor instances found for range type {range_type}")

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
        self._update_domain_and_range_of_descriptor(self, self.domain)

    @classmethod
    def update_domains_that_are_axiomatized_on_properties(
        cls, module: Optional[ModuleType] = None
    ):
        """
        Update the domain and range sets and the domain-range map for all descriptor types
        for all classes that are axiomatized on a property descriptor.
        """
        if module is not None:
            class_diagram = ClassDiagram(classes_of_module(module))
        else:
            class_diagram = SymbolGraph().class_diagram
        for domain_type, axiom in class_diagram.cls_axiom_map.items():
            for desc_type in class_axiomatized_properties(domain_type):
                cls._update_domain_and_range_of_descriptor(
                    desc_type.get_descriptor_instance_for_domain_type(domain_type),
                    domain_type,
                )

    @staticmethod
    def _update_domain_and_range_of_descriptor(
        descriptor: PropertyDescriptor, domain: SymbolType
    ):
        """
        Update the domain and range sets and the domain-range map for this descriptor type.
        """
        range_type = descriptor.wrapped_field.type_endpoint
        descriptor.domain_range_map[descriptor.__class__][domain] = range_type
        descriptor.all_ranges[descriptor.__class__].add(range_type)
        descriptor.all_domains[descriptor.__class__].add(domain)
        descriptor.descriptor_instances_by_domain_type[descriptor.__class__][
            domain
        ] = descriptor

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
        try:
            v = getattr(domain_value, self.field_name)
        except AttributeError:
            if domain_value in Role._role_taker_roles:
                for role in Role._role_taker_roles[domain_value]:
                    if hasattr(role, self.field_name):
                        domain_value = role
                        v = getattr(role, self.field_name)
                        break
            else:
                raise
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


@dataclass(eq=False)
class HasProperty(Predicate):
    """
    Represents a predicate to check if a given instance has a specified property.

    This class is used to evaluate whether the provided instance contains the specified
    property by leveraging Python's built-in `hasattr` functionality. It provides methods
    to retrieve the instance and property name and perform direct checks.
    """

    instance: Any
    """
    The instance whose property presence is being checked.
    """
    property_descriptor_type: Type[PropertyDescriptor]
    """
    The type of the property descriptor to check for in the `instance`.
    """

    def __call__(self) -> bool:
        return hasattr(self.instance, self.property_descriptor_type.get_field_name())


@lru_cache
def class_axiomatized_properties(cls: Type) -> List[Type[PropertyDescriptor]]:
    properties = []
    eql_axiom_conditions = (
        and_(*cls.axiom(variable(type, domain=None))) if hasattr(cls, "axiom") else None
    )
    if eql_axiom_conditions is None:
        return properties
    for uv in eql_axiom_conditions._unique_variables_:
        if (
            isinstance(uv, Variable)
            and uv._predicate_type_ == PredicateType.SubClassOfPredicate
            and issubclass(uv._type_, HasProperty)
        ):
            desc = uv._kwargs_["property_descriptor_type"]
            properties.append(desc)
    return properties


@lru_cache
def is_class_axiomatized_on_property(
    cls: Type, property_descriptor_type: Type[PropertyDescriptor]
) -> bool:
    return property_descriptor_type in class_axiomatized_properties(cls)
