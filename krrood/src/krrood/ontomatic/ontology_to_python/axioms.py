from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property

import rdflib
from rdflib import URIRef, RDF, OWL
from typing_extensions import (
    List,
    Type,
    ClassVar,
    Callable,
    Any,
    TYPE_CHECKING,
    Optional,
)

from ...class_diagrams.utils import issubclass_or_role
from ...entity_query_language.entity import (
    variable,
    ConditionType,
    length,
    exists,
    variable_from,
    contains,
    for_all,
)
from ...entity_query_language.predicate import IsSubClassOrRole
from ...entity_query_language.utils import is_iterable
from ..property_descriptor.property_descriptor import HasProperty
from ..utils import AnonymousClass, NamingRegistry, PropertyType

if TYPE_CHECKING:
    from .owl_to_python import OntologyInfo


@dataclass
class AxiomInfo(ABC):
    """
    Base class for axiom information.
    """

    @abstractmethod
    def conditions_eql(self) -> List[str]:
        pass

    @abstractmethod
    def conditions_python(self) -> List[str]:
        pass


@dataclass
class SubClassAxiomInfo(AxiomInfo):
    """
    Represents a subclass axiom between two classes.
    """

    sub_class: str

    def conditions_eql(self):
        return [
            f"exists(IsSubClassOrRole(variable_from(candidate_var.types), {self.sub_class}))"
        ]

    def conditions_python(self):
        return [
            f"any(issubclass_or_role(t, {self.sub_class}) for t in candidate.types)"
        ]


@dataclass
class PropertyAxiom(ABC):
    """
    Base class for axioms associated with a class or property.
    """

    candidate: AnonymousClass
    property_name: str
    for_class: Type

    @cached_property
    def candidate_var(self):
        return variable(self.for_class, domain=[self.candidate])

    @cached_property
    def prop_var(self):
        return getattr(self.candidate_var, self.property_name)

    def conditions_eql(self) -> List[ConditionType]:
        """
        Generate EQL conditions for this axiom.
        :return: List of EQL condition strings.
        """
        pd_name = NamingRegistry.to_pascal_case(
            NamingRegistry.to_snake_case(self.property_name)
        )
        return [HasProperty(self.candidate_var, pd_name)]

    def conditions_python(self) -> List[bool]:
        """
        Generate Python conditions for this axiom.
        :return: List of Python condition strings.
        """
        return [hasattr(self.candidate, self.property_name)]


@dataclass
class QuantifiedAxiom(PropertyAxiom, ABC):
    """
    Base class for quantified axioms.
    """

    quantity: int
    comparison_operator: ClassVar[Callable]

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.append(
            self.comparison_operator(length(self.prop_var), self.quantity)
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            self.comparison_operator(
                len(getattr(self.candidate, self.property_name, [])), self.quantity
            )
        )
        return base_conditions


@dataclass
class QualifiedAxiomMixin(ABC):
    """
    A qualified cardinality axiom.
    """

    on_class: Type

    def qualification_eql(self, prop_var):
        return exists(IsSubClassOrRole(variable_from(prop_var.types), self.on_class))


@dataclass
class CardinalityAxiom(QuantifiedAxiom):
    """
    A cardinality axiom. (i.e., must have exactly N values)
    """

    comparison_operator: ClassVar[Callable] = operator.eq


@dataclass
class MaxCardinalityAxiom(QuantifiedAxiom):
    """
    A max cardinality axiom.
    """

    comparison_operator: ClassVar[Callable] = operator.le


@dataclass
class MinCardinalityAxiom(QuantifiedAxiom):
    """
    A min cardinality axiom.
    """

    comparison_operator: ClassVar[Callable] = operator.ge


@dataclass
class QualifiedCardinalityAxiom(CardinalityAxiom, QualifiedAxiomMixin):
    """
    A qualified cardinality axiom. (i.e., must have exactly N values of a certain class)
    """

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.insert(
            1,
            self.qualification_eql(self.prop_var),
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions[1] = self.comparison_operator(
            len(
                [
                    v
                    for v in getattr(self.candidate, self.property_name)
                    if any(issubclass_or_role(t, self.on_class) for t in v.types)
                ]
            ),
            self.quantity,
        )
        return base_conditions


@dataclass
class MaxQualifiedCardinalityAxiom(MaxCardinalityAxiom, QualifiedAxiomMixin):
    """
    A qualified max cardinality axiom.
    """


@dataclass
class MinQualifiedCardinalityAxiom(MinCardinalityAxiom, QualifiedAxiomMixin):
    """
    A qualified min cardinality axiom.
    """


@dataclass
class HasValueAxiom(PropertyAxiom):
    """
    A has value axiom.
    """

    value: Any

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        attr = getattr(self.candidate, self.property_name)
        if is_iterable(attr):
            base_conditions.append(contains(self.prop_var, self.value))
        else:
            base_conditions.append(exists(self.prop_var == self.value))
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        attr = getattr(self.candidate, self.property_name)
        if is_iterable(attr):
            base_conditions.append(
                self.value in getattr(self.candidate, self.property_name)
            )
        else:
            base_conditions.append(
                getattr(self.candidate, self.property_name) == self.value
            )
        return base_conditions


@dataclass
class SomeValuesFromAxiom(PropertyAxiom, QualifiedAxiomMixin):
    """
    A SomeValuesFrom axiom.
    """

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.append(
            self.qualification_eql(self.prop_var),
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            any(
                issubclass_or_role(t, self.on_class)
                for attr in getattr(self.candidate, self.property_name)
                for t in attr.types
            )
        )
        return base_conditions


@dataclass
class AllValuesFromAxiom(PropertyAxiom, QualifiedAxiomMixin):
    """
    An AllValuesFrom axiom.
    """

    def conditions_eql(self):
        prop_value = variable_from(self.prop_var)
        base_conditions = super().conditions_eql()
        base_conditions.append(
            for_all(
                prop_value,
                exists(
                    IsSubClassOrRole(variable_from(prop_value.types), self.on_class),
                ),
            )
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            all(
                any(issubclass_or_role(t, self.on_class) for t in attr.types)
                for attr in getattr(self.candidate, self.property_name)
            )
        )
        return base_conditions


@dataclass
class PropertyAxiomInfo(AxiomInfo):
    """
    Information about a property axiom.
    """

    property_name: str
    for_class: str
    onto: OntologyInfo

    @property
    def snake_property_name(self):
        return NamingRegistry.to_snake_case(self.property_name)

    def setup_statements(self):
        return []

    def conditions_eql(self):
        pd_name = NamingRegistry.to_pascal_case(self.snake_property_name)
        return [f"{HasProperty.__name__}(candidate_var, {pd_name})"]

    def conditions_python(self):
        return [self.conditions_eql()[0].replace("candidate_var", "candidate")]


@dataclass
class QuantifiedAxiomInfo(PropertyAxiomInfo, ABC):
    """
    Information about a quantified axiom.
    """

    quantity: int
    comparison_operator: ClassVar[str]

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.append(
            f"length(candidate_var.{self.snake_property_name}) {self.comparison_operator} {self.quantity}"
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            f"(len(candidate.{self.snake_property_name}) {self.comparison_operator} {self.quantity})"
        )
        return base_conditions


@dataclass
class QualifiedAxiomInfoMixin:
    """
    Information about a qualified cardinality axiom.
    """

    on_class: str

    def qualification_eql(self, snake_property_name, existential: bool = True):
        subclass_cond = f"IsSubClassOrRole(variable_from(candidate_var.{snake_property_name}.types), {self.on_class})"
        if existential:
            return f"exists({subclass_cond})"
        else:
            return subclass_cond


@dataclass
class CardinalityAxiomInfo(QuantifiedAxiomInfo):
    """
    Information about a cardinality axiom. (i.e., must have exactly N values)
    """

    comparison_operator: ClassVar[str] = "=="


@dataclass
class MaxCardinalityAxiomInfo(QuantifiedAxiomInfo):
    """
    Information about a max cardinality axiom.
    """

    comparison_operator: ClassVar[str] = "<="


@dataclass
class MinCardinalityAxiomInfo(QuantifiedAxiomInfo):
    """
    Information about a min cardinality axiom.
    """

    comparison_operator: ClassVar[str] = ">="


@dataclass
class QuantifiedQualifiedAxiomInfo(QuantifiedAxiomInfo, QualifiedAxiomInfoMixin):
    """
    Information about a qualified cardinality axiom. (i.e., must have exactly N values of a certain class)
    """

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions[-1] = (
            f"count({self.qualification_eql(self.snake_property_name, existential=False)}) {self.comparison_operator} "
            f"{self.quantity}"
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions[-1] = (
            f"(len([v for v in candidate.{self.snake_property_name} if any(issubclass_or_role(t, {self.on_class}) for t in v.types) ]) {self.comparison_operator} {self.quantity})"
        )
        return base_conditions


@dataclass
class QualifiedCardinalityAxiomInfo(QuantifiedQualifiedAxiomInfo):
    """
    Information about a qualified cardinality axiom. (i.e., must have exactly N values of a certain class)
    """

    comparison_operator = "=="


@dataclass
class MaxQualifiedCardinalityAxiomInfo(QuantifiedQualifiedAxiomInfo):
    """
    Information about a qualified max cardinality axiom.
    """

    comparison_operator = "<="


@dataclass
class MinQualifiedCardinalityAxiomInfo(QuantifiedQualifiedAxiomInfo):
    """
    Information about a qualified min cardinality axiom.
    """

    comparison_operator = ">="


@dataclass
class HasValueAxiomInfo(PropertyAxiomInfo, QualifiedAxiomInfoMixin):
    """
    Information about a has value axiom.
    """

    value: Any
    value_str: str = field(init=False)
    on_class: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        self.value_str = self.value
        if isinstance(self.value, str):
            self.value_str = f'"{self.value}"'
        self.on_class = self.value_type

    @cached_property
    def value_type(self) -> Optional[str]:
        value_type = [
            v
            for v in self.onto.graph.objects(self.value, RDF.type)
            if v != OWL.NamedIndividual
        ][0]
        value_type = NamingRegistry.uri_to_python_name(value_type, self.onto.graph)
        return value_type

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        prop_info = self.onto.properties[self.property_name]
        prop = f"candidate_var.{self.snake_property_name}"
        if isinstance(self.value, rdflib.URIRef):
            prop = f"to_str({prop}.uri)"
            self.value_str = f"'{str(self.value)}'"
        if (
            not isinstance(self.value, URIRef)
            and prop_info.type == PropertyType.OBJECT_PROPERTY
            and not prop_info.is_functional
        ):
            base_conditions.append(f"contains({prop}, {self.value_str})")
        else:
            base_conditions.append(f"exists({prop} == {self.value_str})")
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        prop_info = self.onto.properties[self.property_name]
        prop = f"candidate.{self.snake_property_name}"
        if isinstance(self.value, URIRef):
            self.value_str = f"'{str(self.value)}'"
        if (
            prop_info.type == PropertyType.OBJECT_PROPERTY
            and not prop_info.is_functional
        ):
            if isinstance(self.value, URIRef):
                prop = f"map(lambda x: str(x.uri), {prop})"
            base_conditions.append(f"({self.value_str} in {prop})")
        else:
            if isinstance(self.value, URIRef):
                prop = f"str({prop}.uri)"
            base_conditions.append(f"({prop} == {self.value_str})")
        return base_conditions


@dataclass
class SomeValuesFromAxiomInfo(PropertyAxiomInfo, QualifiedAxiomInfoMixin):
    """
    Information about a some values from axiom.
    """

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.append(
            self.qualification_eql(self.snake_property_name),
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            f"any(issubclass_or_role(t, {self.on_class}) for attr in candidate.{self.snake_property_name} for t in attr.types)"
        )
        return base_conditions


@dataclass
class AllValuesFromAxiomInfo(PropertyAxiomInfo, QualifiedAxiomInfoMixin):
    """
    Information about an all values from axiom.
    """

    def setup_statements(self):
        base_setup = super().setup_statements()
        base_setup.append(
            f"candidate_{self.snake_property_name} = variable_from(candidate_var.{self.snake_property_name})"
        )
        return base_setup

    def conditions_eql(self):
        base_conditions = super().conditions_eql()
        base_conditions.append(
            f"for_all(candidate_{self.snake_property_name}, exists(IsSubClassOrRole(variable_from(candidate_{self.snake_property_name}.types), {self.on_class})))"
        )
        return base_conditions

    def conditions_python(self):
        base_conditions = super().conditions_python()
        base_conditions.append(
            f"all(any(issubclass(t, {self.on_class}) for t in attr.types) for attr in candidate.{self.snake_property_name})"
        )
        return base_conditions
