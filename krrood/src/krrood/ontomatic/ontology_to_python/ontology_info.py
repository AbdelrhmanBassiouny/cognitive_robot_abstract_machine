from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property, lru_cache

import rdflib
from rdflib import URIRef
from typing_extensions import List, Optional, Dict, Any, Set, Type, TYPE_CHECKING

from ..utils import NamingRegistry, topological_order
from ...class_diagrams.utils import Role
if TYPE_CHECKING:
    from .axioms import PropertyAxiomInfo


class SubsumptionType(Enum):
    SUBTYPE = "subtype"
    """
    It is a subtype of the given class (e.g. Math is a subtype of Course). This is the equivalent to OOP 
    inheritance..
    """
    ROLE = "role"
    """
    It is a role that a persistent identifier can take on in a certain context 
    (e.g. Student is a role that a Person can take on in the context of taking a course).
    Thi is the equivalent to OOP composition.
    """


@dataclass
class RoleTakerInfo:
    """
    Information about a class that acts as a role taker.
    Used when a class is determined to be a 'role' of another class.
    """

    class_name: str
    field_name: str


@dataclass
class ClassInfo:
    """
    Maintains all metadata, inheritance, and property associations for an OWL class.
    Used during the code generation process to represent a Python class.
    """

    name: str
    uri: str
    superclasses: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    all_base_classes: List[str] = field(default_factory=list)
    all_base_classes_including_role_takers: List[str] = field(default_factory=list)
    base_classes_for_topological_sort: List[str] = field(default_factory=list)
    disjoint_with: List[str] = field(default_factory=list)
    complement_of: Optional[str] = None
    one_of: List[str] = field(default_factory=list)
    equivalent_classes: List[str] = field(default_factory=list)
    is_description_for: Optional[str] = None
    has_descriptions: List[str] = field(default_factory=list)
    label: Optional[str] = None
    comment: Optional[str] = None
    add_role_taker: bool = True
    role_taker: Optional[RoleTakerInfo] = None
    declared_properties: List[str] = field(default_factory=list)
    axioms: List[str] = field(default_factory=list)
    axioms_python: List[str] = field(default_factory=list)
    axioms_setup: List[str] = field(default_factory=list)
    property_axioms_info: Dict[str, PropertyAxiomInfo] = field(default_factory=dict)
    onto: Optional[OntologyInfo] = field(default=None, repr=False)
    disjoint_union: List[str] = field(default_factory=list)
    union: List[str] = field(default_factory=list)

    def __deepcopy__(self, memo):
        # Custom deepcopy to avoid copying the ontology reference
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "onto":
                setattr(result, k, self.onto)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result

    def __hash__(self):
        return hash(id(self))


@dataclass
class PropertyInfo:
    """
    Maintains metadata, domains, ranges, and inheritance for an OWL property.
    Used during the code generation process to represent a Python property or descriptor.
    """

    name: str
    uri: str
    type: PropertyType
    domains: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    range_uris: List[Any] = field(default_factory=list)
    label: Optional[str] = None
    comment: Optional[str] = None
    field_name: str = ""
    descriptor_name: str = ""
    equivalent_properties: List[str] = field(default_factory=list)
    disjoint_properties: List[str] = field(default_factory=list)
    is_symmetric: bool = False
    is_reflexive: bool = False
    is_asymmetric: bool = False
    is_irreflexive: bool = False
    superproperties: List[str] = field(default_factory=list)
    all_superproperties: List[str] = field(default_factory=list)
    inverses: List[str] = field(default_factory=list)
    inverse_of: Optional[str] = None
    inverse_target_is_prior: bool = False
    is_transitive: bool = False
    is_functional: bool = False
    declared_domains: List[str] = field(default_factory=list)
    _overrides_for: List[str] = field(default_factory=list)
    _predefined_data_type: bool = False
    data_type_hint_inner: Optional[str] = None
    object_range_hint: Optional[str] = None
    base_descriptors: List[str] = field(default_factory=list)
    equivalent_properties_descriptor_names: List[str] = field(default_factory=list)
    disjoint_properties_descriptor_names: List[str] = field(default_factory=list)
    chain_axioms: List[List[str]] = field(default_factory=list)
    onto: Optional[OntologyInfo] = field(default=None, repr=False)
    _sorted_superproperties: List[str] = field(default_factory=list, init=False)
    _all_superproperties: List[str] = field(default_factory=list, init=False)

    @property
    def sorted_superproperties(self):
        """
        Get superproperties sorted by inheritance path length (shortest first).
        """
        if not self._sorted_superproperties and self.onto:
            self._sorted_superproperties = topological_order(
                {sp: self.onto.properties[sp] for sp in self.ancestors},
                dep_key="superproperties",
            )
        return self._sorted_superproperties

    @property
    def ancestors(self):
        """
        Compute full ancestor sets for each class (transitive closure).
        """
        if self._all_superproperties:
            return self._all_superproperties
        if not self.onto:
            return []
        # Compute full ancestor sets for each class (transitive closure)
        name_to_bases = {
            name: set(info.superproperties)
            for name, info in self.onto.properties.items()
        }
        ancestors = set()
        stack = list(self.superproperties)
        while stack:
            base = stack.pop()
            if base in ancestors:
                continue
            ancestors.add(base)
            stack.extend(name_to_bases.get(base, []))
        self._all_superproperties = sorted(ancestors)
        return self._all_superproperties

    def __deepcopy__(self, memo):
        # Custom deepcopy to avoid copying the ontology reference
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "onto":
                setattr(result, k, self.onto)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result

    def __hash__(self):
        return hash(id(self))


@dataclass
class OntologyInfo:
    """Information about the ontology."""

    graph: rdflib.Graph
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    class_descriptions: Dict[str, ClassInfo] = field(default_factory=dict)
    original_properties: Dict[str, PropertyInfo] = field(default_factory=dict)
    predefined_data_types: Optional[Dict[str, Dict[str, str]]] = None
    ontology_label: str = "Thing"
    role_cls_name: str = Role.__name__
    _properties: Optional[Dict[str, PropertyInfo]] = None
    property_restrictions: Dict[str, Dict[str, set]] = field(default_factory=dict)

    def __post_init__(self):
        for prop_info in self.original_properties.values():
            prop_info.onto = self
        for cls_info in self.classes.values():
            cls_info.onto = self

    def description_for(self, description_name: str) -> Optional[str]:
        for cls_name, cls_info in self.class_descriptions.items():
            if cls_info.name == description_name:
                return cls_name
        return None

    @property
    def properties(self):
        if not self._properties:
            self._properties = {
                n: deepcopy(info) for n, info in self.original_properties.items()
            }
        return self._properties

    @cached_property
    def base_cls_name(self):
        base_cls_name = NamingRegistry.to_pascal_case(
            re.sub(r"\W+", " ", self.ontology_label).strip()
        )
        if not base_cls_name.endswith("Thing"):
            base_cls_name += "Thing"
        return base_cls_name

    @cached_property
    def class_ancestors(self) -> Dict[str, Set[str]]:
        """
        The class ancestors map as a dictionary mapping class names to their ancestors.
        """
        return {name: set(info.all_base_classes) for name, info in self.classes.items()}

    @lru_cache
    def properties_inheritance_path_length(
            self,
            child_class: str,
            parent_class: str,
    ) -> Optional[int]:
        """
        Calculate the inheritance path length between two classes.
        Every inheritance level that lies between `child_class` and `parent_class` increases the length by one.
        In case of multiple inheritance, the path length is calculated for each branch and the minimum is returned.

        :param child_class: The child class.
        :param parent_class: The parent class.
        :return: The minimum path length between `child_class` and `parent_class` or None if no path exists.
        """
        if parent_class not in self.properties[child_class].all_superproperties + [
            child_class
        ]:
            return None

        return self._properties_inheritance_path_length(child_class, parent_class, 0)

    def _properties_inheritance_path_length(
            self, child_class: str, parent_class: str, current_length: int = 0
    ) -> int:
        """
        Helper function for :func:`inheritance_path_length`.

        :param child_class: The child class.
        :param parent_class: The parent class.
        :param current_length: The current length of the inheritance path.
        :return: The minimum path length between `child_class` and `parent_class`.
        """

        if child_class == parent_class:
            return current_length
        else:
            return min(
                self._properties_inheritance_path_length(
                    base, parent_class, current_length + 1
                )
                for base in self.properties[child_class].superproperties
                if parent_class in self.properties[base].all_superproperties + [base]
            )

    @lru_cache
    def classes_inheritance_path_length(
            self,
            child_class: str,
            parent_class: str,
    ) -> Optional[int]:
        """
        Calculate the inheritance path length between two classes.
        Every inheritance level that lies between `child_class` and `parent_class` increases the length by one.
        In case of multiple inheritance, the path length is calculated for each branch and the minimum is returned.

        :param child_class: The child class.
        :param parent_class: The parent class.
        :return: The minimum path length between `child_class` and `parent_class` or None if no path exists.
        """
        if (
                parent_class
                not in self.classes[child_class].all_base_classes_including_role_takers
        ):
            return None

        return self._classes_inheritance_path_length(child_class, parent_class, 0)

    def _classes_inheritance_path_length(
            self, child_class: str, parent_class: str, current_length: int = 0
    ) -> int:
        """
        Helper function for :func:`inheritance_path_length`.

        :param child_class: The child class.
        :param parent_class: The parent class.
        :param current_length: The current length of the inheritance path.
        :return: The minimum path length between `child_class` and `parent_class`.
        """

        if child_class == parent_class:
            return current_length
        else:
            return min(
                self._classes_inheritance_path_length(
                    base, parent_class, current_length + 1
                )
                for base in self.classes[child_class].base_classes
                if parent_class
                in self.classes[base].all_base_classes_including_role_takers
            )

    def __hash__(self):
        return hash(id(self))


class PropertyType(str, Enum):
    """Enumeration of OWL property types."""

    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"


@dataclass
class AnonymousClass:
    """Represents an anonymous class that is yet to be identified"""

    uri: URIRef
    types: Set[Type] = field(default_factory=set)
    final_sorted_types: List[Type] = field(default_factory=list)
    onto: Optional[OntologyInfo] = None

    def add_type(self, cls: Type):
        self.types.add(cls)

    def __hash__(self):
        return hash(self.uri)

    def __eq__(self, other):
        return hash(self) == hash(other)
