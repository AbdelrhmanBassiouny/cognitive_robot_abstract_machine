"""
This module provides functionality to convert OWL ontologies into Python source code.
It includes classes for extracting information from RDF graphs, performing inference,
and generating Python code using Jinja2 templates.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from copy import deepcopy, copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import cached_property, lru_cache

from krrood.ontomatic.ontology_to_python.axioms import PropertyAxiomInfo

from .axioms import (
    SubClassAxiomInfo,
    QualifiedAxiomInfoMixin,
    QualifiedCardinalityAxiomInfo,
    MaxQualifiedCardinalityAxiomInfo,
    MinQualifiedCardinalityAxiomInfo,
    HasValueAxiomInfo,
    SomeValuesFromAxiomInfo,
    AllValuesFromAxiomInfo,
)

from ...entity_query_language.entity import Symbol
from typing_extensions import Dict, List, Optional, Any, Set, ClassVar

import rdflib
from ..utils import NamingRegistry, PropertyType

from ripple_down_rules import CaseQuery
from jinja2 import Environment, FileSystemLoader
from jinja2.ext import loopcontrols
from ... import logger
from ...class_diagrams.utils import Role
from ..property_descriptor.mixins import (
    TransitiveProperty,
    HasInverseProperty,
    HasEquivalentProperties,
    HasDisjointProperties,
    SymmetricProperty,
    ASymmetricProperty,
    ReflexiveProperty,
    IrreflexiveProperty,
    HasChainAxioms,
)
from ..property_descriptor.property_descriptor import (
    PropertyDescriptor,
)
from rdflib.namespace import RDF, RDFS, OWL, XSD
from ripple_down_rules import GeneralRDR
from ordered_set import OrderedSet
from typing_extensions import Tuple


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
            self._sorted_superproperties = InferenceEngine.topological_order(
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


class MetadataExtractor:
    """Helper for extracting metadata (labels, comments) from an RDF graph."""

    def __init__(self, graph: rdflib.Graph):
        """
        Initialize the metadata extractor.
        :param graph: The rdflib graph to extract metadata from.
        """
        self.graph = graph

    def get_label(self, uri: Any) -> Optional[str]:
        """Get rdfs:label for a URI"""
        for label in self.graph.objects(uri, RDFS.label):
            return str(label)
        return None

    def get_comment(self, uri: Any) -> Optional[str]:
        """Get rdfs:comment for a URI"""
        for comment in self.graph.objects(uri, RDFS.comment):
            return str(comment)
        return None


class ClassExtractor:
    """Extractor for OWL Class information from an RDF graph."""

    def __init__(self, graph: rdflib.Graph, metadata_extractor: MetadataExtractor):
        """
        Initialize the class extractor.
        :param graph: The rdflib graph.
        :param metadata_extractor: Extractor for labels and comments.
        """
        self.graph = graph
        self.metadata_extractor = metadata_extractor

    def extract_info(self, class_uri: Any) -> ClassInfo:
        """Extract information about a class"""
        is_b_node = False
        if isinstance(class_uri, rdflib.BNode):
            is_b_node = True
            class_name = NamingRegistry.bnode_to_name(self.graph, class_uri)
        else:
            class_name = NamingRegistry.uri_to_python_name(class_uri)

        # Get superclasses from explicit rdfs:subClassOf
        superclasses: List[str] = []
        has_descriptions = []
        for superclass in self.graph.objects(class_uri, RDFS.subClassOf):
            if isinstance(superclass, rdflib.URIRef):
                superclasses.append(NamingRegistry.uri_to_python_name(superclass))
            elif isinstance(superclass, rdflib.BNode):
                # Only include BNode superclasses if they are intersections or unions
                if list(self.graph.objects(superclass, OWL.intersectionOf)) or list(
                    self.graph.objects(superclass, OWL.unionOf)
                ):
                    has_descriptions.append(
                        NamingRegistry.uri_to_python_name(superclass, self.graph)
                    )

        # De-duplicate while preserving order
        seen = set()
        unique_superclasses: List[str] = []
        for sc in superclasses:
            if sc not in seen:
                unique_superclasses.append(sc)
                seen.add(sc)

        # disjoint with
        disjoint_with: List[str] = []
        for disjoint_class in self.graph.objects(class_uri, OWL.disjointWith):
            if isinstance(disjoint_class, rdflib.URIRef):
                disjoint_with.append(NamingRegistry.uri_to_python_name(disjoint_class))

        # equivalent classes
        equivalent_classes: List[str] = []
        for eq_class in self.graph.objects(class_uri, OWL.equivalentClass):
            if isinstance(eq_class, rdflib.URIRef):
                equivalent_classes.append(NamingRegistry.uri_to_python_name(eq_class))

        # Get label
        label = self.metadata_extractor.get_label(class_uri)
        is_description_for = None
        if is_b_node and unique_superclasses:
            if len(unique_superclasses) > 1:
                raise NotImplemented(
                    f"BNode class {class_name} has multiple superclasses: {unique_superclasses}"
                )
            is_description_for = unique_superclasses[0]
        elif is_b_node and not unique_superclasses:
            subclasses = list(self.graph.subjects(RDFS.subClassOf, class_uri))
            if len(subclasses) > 1:
                raise NotImplemented(
                    f"BNode class {class_name} has multiple subclasses: {subclasses}"
                )
            is_description_for = NamingRegistry.uri_to_python_name(subclasses[0])

        return ClassInfo(
            name=class_name,
            uri=str(class_uri),
            superclasses=unique_superclasses or [Symbol.__name__],
            disjoint_with=disjoint_with,
            equivalent_classes=equivalent_classes,
            is_description_for=is_description_for,
            has_descriptions=has_descriptions,
            label=label,
            comment=self.metadata_extractor.get_comment(class_uri),
            add_role_taker=True,
        )


class PropertyExtractor:
    """Extractor for OWL Property information from an RDF graph."""

    def __init__(self, graph: rdflib.Graph, metadata_extractor: MetadataExtractor):
        """
        Initialize the property extractor.
        :param graph: The rdflib graph.
        :param metadata_extractor: Extractor for labels and comments.
        """
        self.graph = graph
        self.metadata_extractor = metadata_extractor

    def extract_info(self, property_uri: Any) -> PropertyInfo:
        """Extract information about a property"""
        prop_local = NamingRegistry.uri_to_python_name(property_uri)

        # Get domain and range
        domains: List[str] = []
        ranges: List[str] = []
        superproperties: List[str] = []
        inverses: List[str] = []
        is_transitive = False
        equivalent_properties: List[str] = []
        disjoint_properties: List[str] = []
        is_symmetric = False
        is_asymmetric = False
        is_reflexive = False
        is_irreflexive = False
        is_functional = False

        for domain in self.graph.objects(property_uri, RDFS.domain):
            domains.append(NamingRegistry.uri_to_python_name(domain))

        range_uris: List[rdflib.term.Identifier] = []
        for range_val in self.graph.objects(property_uri, RDFS.range):
            ranges.append(NamingRegistry.uri_to_python_name(range_val))
            range_uris.append(range_val)

        # Inheritance between properties
        for super_prop in self.graph.objects(property_uri, RDFS.subPropertyOf):
            if isinstance(super_prop, rdflib.URIRef):
                superproperties.append(NamingRegistry.uri_to_python_name(super_prop))

        # Inverses
        for inv in self.graph.objects(property_uri, OWL.inverseOf):
            if isinstance(inv, rdflib.URIRef):
                inverses.append(NamingRegistry.uri_to_python_name(inv))
        # Also collect when current property is the object of inverseOf
        for inv_subj in self.graph.subjects(OWL.inverseOf, property_uri):
            if isinstance(inv_subj, rdflib.URIRef):
                inverses.append(NamingRegistry.uri_to_python_name(inv_subj))

        # Equivalent properties
        for eq_prop in self.graph.objects(property_uri, OWL.equivalentProperty):
            if isinstance(eq_prop, rdflib.URIRef):
                equivalent_properties.append(NamingRegistry.uri_to_python_name(eq_prop))
        for eq_prop_subj in self.graph.subjects(OWL.equivalentProperty, property_uri):
            if isinstance(eq_prop_subj, rdflib.URIRef):
                equivalent_properties.append(
                    NamingRegistry.uri_to_python_name(eq_prop_subj)
                )

        # Disjoint properties
        for dis_prop in self.graph.objects(property_uri, OWL.propertyDisjointWith):
            if isinstance(dis_prop, rdflib.URIRef):
                disjoint_properties.append(NamingRegistry.uri_to_python_name(dis_prop))
        for dis_prop_subj in self.graph.subjects(
            OWL.propertyDisjointWith, property_uri
        ):
            if isinstance(dis_prop_subj, rdflib.URIRef):
                disjoint_properties.append(
                    NamingRegistry.uri_to_python_name(dis_prop_subj)
                )

        # Determine property type
        prop_type = PropertyType.OBJECT_PROPERTY
        for prop_type_uri in self.graph.objects(property_uri, RDF.type):
            if prop_type_uri == OWL.DatatypeProperty:
                prop_type = PropertyType.DATA_PROPERTY
            if prop_type_uri == OWL.TransitiveProperty:
                is_transitive = True
            if prop_type_uri == OWL.SymmetricProperty:
                is_symmetric = True
            if prop_type_uri == OWL.AsymmetricProperty:
                is_asymmetric = True
            if prop_type_uri == OWL.ReflexiveProperty:
                is_reflexive = True
            if prop_type_uri == OWL.IrreflexiveProperty:
                is_irreflexive = True
            if prop_type == OWL.FunctionalProperty:
                is_functional = True

        # Choose a single inverse if any (stable order)
        inverse_of = None
        if inverses:
            inverse_of = sorted(set(inverses))[0]

        return PropertyInfo(
            name=prop_local,
            uri=str(property_uri),
            type=prop_type,
            domains=domains,
            ranges=ranges,
            range_uris=range_uris,
            equivalent_properties=equivalent_properties,
            disjoint_properties=disjoint_properties,
            label=self.metadata_extractor.get_label(property_uri),
            comment=self.metadata_extractor.get_comment(property_uri),
            field_name=NamingRegistry.to_snake_case(prop_local),
            descriptor_name=NamingRegistry.to_pascal_case(prop_local),
            superproperties=superproperties,
            inverses=sorted(set(inverses)),
            inverse_of=inverse_of,
            is_transitive=is_transitive,
            is_symmetric=is_symmetric,
            is_asymmetric=is_asymmetric,
            is_reflexive=is_reflexive,
            is_irreflexive=is_irreflexive,
            is_functional=is_functional,
        )


@dataclass
class InferenceEngine:
    """Engine for performing ontological inference and computing class/property relationships."""

    onto: OntologyInfo
    XSD_TO_PYTHON_TYPES: ClassVar[Dict[rdflib.term.URIRef, str]] = {
        XSD.string: "str",
        XSD.normalizedString: "str",
        XSD.token: "str",
        XSD.language: "str",
        XSD.boolean: "bool",
        XSD.decimal: "float",
        XSD.float: "float",
        XSD.double: "float",
        XSD.integer: "int",
        XSD.nonPositiveInteger: "int",
        XSD.negativeInteger: "int",
        XSD.long: "int",
        XSD.int: "int",
        XSD.short: "int",
        XSD.byte: "int",
        XSD.nonNegativeInteger: "int",
        XSD.unsignedLong: "int",
        XSD.unsignedInt: "int",
        XSD.unsignedShort: "int",
        XSD.unsignedByte: "int",
        XSD.positiveInteger: "int",
        XSD.date: "str",
        XSD.dateTime: "str",
        XSD.time: "str",
        XSD.anyURI: "str",
    }

    @staticmethod
    def topological_order(items: Dict[str, Any], dep_key: str) -> List[str]:
        """Return a topological order based on dependency names in dep_key; if cycles, append remaining alphabetically."""

        def get_deps(item):
            if hasattr(item, dep_key):
                return getattr(item, dep_key, [])
            return item.get(dep_key, [])

        remaining = {
            name: set(get_deps(items[name])) & set(items.keys()) for name in items
        }
        ordered: List[str] = []
        while remaining:
            ready = sorted([name for name, deps in remaining.items() if not deps])
            if not ready:
                ordered.extend(sorted(remaining.keys()))
                break
            for name in ready:
                ordered.append(name)
                del remaining[name]
            for deps in remaining.values():
                deps.difference_update(ready)
        return ordered

    def compute_ancestors(self):
        """
        Compute full ancestor sets for each class (transitive closure).
        """
        # Compute full ancestor sets for each class (transitive closure)
        name_to_bases = {
            name: set(info.base_classes) for name, info in self.onto.classes.items()
        }
        for info in self.onto.classes.values():
            ancestors = set()
            stack = list(info.base_classes)
            while stack:
                base = stack.pop()
                if base in ancestors:
                    continue
                ancestors.add(base)
                stack.extend(name_to_bases.get(base, []))
            info.all_base_classes = sorted(ancestors)
        for info in self.onto.classes.values():
            info.all_base_classes_including_role_takers = copy(info.all_base_classes)
            if info.role_taker:
                info.all_base_classes_including_role_takers.append(
                    info.role_taker.class_name
                )

    def infer_properties(
        self,
    ):
        """
        Main entry point for property inference.
        Propagates domains, ranges, and handles restrictions and inverses.
        """
        self._infer_properties_data_from_restrictions()

        # self.fit_property_rdr()

        for prop_name, prop_info in self.onto.properties.items():
            if prop_name == "roleFor":
                continue
            if prop_info.type == PropertyType.DATA_PROPERTY:
                continue
            self.property_rdr.classify(prop_info, modify_case=True)

        self._finalize_properties()
        self._add_property_chain_axioms()

    @cached_property
    def property_rdr(self):
        return GeneralRDR(
            save_dir=os.path.join(os.path.dirname(__file__), "rdrs"),
            model_name="property_inference",
        )

    def fit_property_rdr(self):
        def ask_now_domain(case: PropertyInfo):
            return case.name == "isHeadOf"
            return False

        def ask_now_range(case: PropertyInfo):
            return case.name == "isHeadOf"
            return False

        for prop_name, prop_info in self.onto.properties.items():
            if prop_name == "roleFor":
                continue
            if prop_info.type == PropertyType.DATA_PROPERTY:
                continue
            domain_case_query = CaseQuery(prop_info, "domains", (str,), False)
            prop_info.onto = self.onto
            domains = self.property_rdr.fit_case(
                domain_case_query, update_existing_rules=False, ask_now=ask_now_domain
            )
            prop_info.domains = list(domains["domains"])
        for prop_name, prop_info in self.onto.properties.items():
            if prop_name == "roleFor":
                continue
            if prop_info.type == PropertyType.DATA_PROPERTY:
                continue
            range_case_query = CaseQuery(prop_info, "ranges", (str,), False)
            ranges = self.property_rdr.fit_case(
                range_case_query, update_existing_rules=False, ask_now=ask_now_range
            )
            prop_info.ranges = list(ranges["ranges"])

    def _add_property_chain_axioms(self):
        """
        Add property chain axioms to properties based on owl:propertyChainAxiom.
        """
        for prop_name, prop_info in self.onto.properties.items():
            prop_uri = rdflib.URIRef(prop_info.uri)
            for chain in self.onto.graph.objects(prop_uri, OWL.propertyChainAxiom):
                items = []
                node = chain
                while node and node != RDF.nil:
                    first = self.onto.graph.value(node, RDF.first)
                    if first:
                        name = NamingRegistry.uri_to_python_name(first)
                        if name not in self.onto.properties:
                            raise ValueError(
                                f"Property chain axiom references unknown property {name}"
                            )
                        items.append(self.onto.properties[name].descriptor_name)
                    node = self.onto.graph.value(node, RDF.rest)
                if items:
                    prop_info.chain_axioms.append(items)

    def _infer_properties_data_from_restrictions(self):
        """
        Walk through all classes and their restrictions in the graph and update properties data accordingly.
        """
        covered_restrictions = set()
        # Walk class restrictions
        for cls_uri in self.onto.graph.subjects(RDF.type, OWL.Class):
            cls_name = NamingRegistry.uri_to_python_name(cls_uri, self.onto.graph)
            for_class = self.onto.description_for(cls_name) or cls_name

            # direct subclass restrictions
            for restr in self.onto.graph.objects(cls_uri, RDFS.subClassOf):
                self._restrictions_handler(cls_name, restr)
                # If restriction mentions a property, count this class as declared domain for that property
                covered_restrictions.add(restr)

            # restrictions inside intersectionOf
            intersection = []
            for coll in self.onto.graph.objects(cls_uri, OWL.intersectionOf):
                node = coll
                while node and node != RDF.nil:
                    first = self.onto.graph.value(node, RDF.first)
                    self._restrictions_handler(cls_name, first)
                    covered_restrictions.add(first)
                    on_prop = (
                        self.onto.graph.value(first, OWL.onProperty) if first else None
                    )
                    if (
                        on_prop
                        and intersection
                        and intersection[0] in self.onto.classes
                        and self.onto.classes[for_class].axioms
                    ):
                        subclass_axiom = SubClassAxiomInfo(intersection[0])
                        self.onto.classes[for_class].axioms.insert(
                            0,
                            subclass_axiom.conditions_eql()[0],
                        )
                        self.onto.classes[for_class].axioms_python.insert(
                            0,
                            subclass_axiom.conditions_python()[0],
                        )
                    else:
                        first_name = NamingRegistry.uri_to_python_name(
                            first, self.onto.graph
                        )
                        intersection.append(first_name)
                    node = self.onto.graph.value(node, RDF.rest)
        # Standalone Restrictions
        for restr in self.onto.graph.subjects(RDF.type, OWL.Restriction):
            if restr in covered_restrictions:
                continue
            covered_restrictions.add(restr)
            on_prop = self.onto.graph.value(restr, OWL.onProperty)
            if on_prop is None:
                continue
            for_class = None
            for subj, pred in self.onto.graph.subject_predicates(restr):
                if pred == OWL.equivalentClass:
                    for_class = NamingRegistry.uri_to_python_name(subj, self.onto.graph)
                    break
            if not for_class:
                for_class = self.onto.graph.value(restr, RDFS.subClassOf)
                if for_class:
                    for_class = NamingRegistry.uri_to_python_name(
                        for_class, self.onto.graph
                    )
            if not for_class:
                raise ValueError(f"Could not determine class for restriction {restr}")
            self._restrictions_handler(for_class, restr)
            prop_name = NamingRegistry.uri_to_python_name(on_prop, self.onto.graph)
            for_class = self.onto.description_for(for_class) or for_class

    def _restrictions_handler(self, for_class: str, node: rdflib.term.Node):
        """
        Handle restrictions for a given class and node in the ontology graph.

        :param for_class: The class name.
        :param node: The restriction node.
        """
        if not node:
            return
        on_prop = self.onto.graph.value(node, OWL.onProperty)
        if not on_prop:
            return
        description_for = self.onto.description_for(for_class)
        for_class = description_for or for_class
        prop_name = NamingRegistry.uri_to_python_name(on_prop, self.onto.graph)
        axiom = None
        value_type = None
        if self.onto.graph.value(node, OWL.hasValue):
            has_value = self.onto.graph.value(node, OWL.hasValue)
            axiom = HasValueAxiomInfo(
                property_name=prop_name,
                value=has_value,
                for_class=for_class,
                onto=self.onto,
            )
            value_type = axiom.value_type
        elif self.onto.graph.value(node, OWL.maxQualifiedCardinality):
            literal_value = self.onto.graph.value(node, OWL.maxQualifiedCardinality)
            max_value = literal_value.toPython()
            clazz_uri = self.onto.graph.value(node, OWL.onClass)
            value_type = NamingRegistry.uri_to_python_name(clazz_uri, self.onto.graph)
            axiom = MaxQualifiedCardinalityAxiomInfo(
                property_name=prop_name,
                quantity=max_value,
                on_class=value_type,
                for_class=for_class,
                onto=self.onto,
            )
        elif self.onto.graph.value(node, OWL.minQualifiedCardinality):
            literal_value = self.onto.graph.value(node, OWL.minQualifiedCardinality)
            min_value = literal_value.toPython()
            clazz_uri = self.onto.graph.value(node, OWL.onClass)
            value_type = NamingRegistry.uri_to_python_name(clazz_uri, self.onto.graph)
            axiom = MinQualifiedCardinalityAxiomInfo(
                property_name=prop_name,
                quantity=min_value,
                on_class=value_type,
                for_class=for_class,
                onto=self.onto,
            )
        elif self.onto.graph.value(node, OWL.qualifiedCardinality):
            literal_value = self.onto.graph.value(node, OWL.qualifiedCardinality)
            exact_value = literal_value.toPython()
            clazz_uri = self.onto.graph.value(node, OWL.onClass)
            value_type = NamingRegistry.uri_to_python_name(clazz_uri, self.onto.graph)
            axiom = QualifiedCardinalityAxiomInfo(
                property_name=prop_name,
                quantity=exact_value,
                on_class=value_type,
                for_class=for_class,
                onto=self.onto,
            )
        elif self.onto.graph.value(node, OWL.someValuesFrom):
            value_type = self.onto.graph.value(node, OWL.someValuesFrom)
            value_type = NamingRegistry.uri_to_python_name(value_type, self.onto.graph)
            axiom = SomeValuesFromAxiomInfo(
                property_name=prop_name,
                on_class=NamingRegistry.uri_to_python_name(value_type, self.onto.graph),
                for_class=for_class,
                onto=self.onto,
            )
        elif self.onto.graph.value(node, OWL.allValuesFrom):
            value_type = self.onto.graph.value(node, OWL.allValuesFrom)
            value_type = NamingRegistry.uri_to_python_name(value_type, self.onto.graph)
            axiom = AllValuesFromAxiomInfo(
                property_name=prop_name,
                on_class=value_type,
                for_class=for_class,
                onto=self.onto,
            )
        if not axiom:
            return
        rng_name = value_type
        if prop_name == "roleFor":
            cls_info = self.onto.classes.get(for_class)
            if cls_info:
                cls_info.role_taker = RoleTakerInfo(
                    rng_name, NamingRegistry.to_snake_case(rng_name)
                )
                cls_info.all_base_classes_including_role_takers.append(rng_name)
            return
        self.onto.classes[for_class].axioms_setup.extend(axiom.setup_statements())
        self.onto.classes[for_class].axioms.extend(axiom.conditions_eql())
        self.onto.classes[for_class].axioms_python.extend(axiom.conditions_python())
        self.onto.classes[for_class].property_axioms_info[prop_name] = axiom
        return

    def _remove_rng_from_property_ranges_if_not_subclass_of_explicit_domains(self): ...

    def _finalize_properties(self):
        """
        Update PropertyInfo objects with inferred domain and range information.
        """
        for name, info in self.onto.properties.items():
            info.domains = sorted(info.domains)
            info.ranges = sorted(info.ranges)
            info.range_uris = [
                self.onto.classes[r].uri for r in info.ranges if r in self.onto.classes
            ]
            info.declared_domains = copy(info.domains)

    def apply_predefined_overrides(
        self,
    ):
        """
        Apply manual type overrides for specific class properties.
        """
        for cls_name, overrides in (self.onto.predefined_data_types or {}).items():
            if cls_name == "Thing":
                cls_name = self.onto.base_cls_name
            for field_snake, py_type in overrides.items():
                target_prop_name = next(
                    (
                        n
                        for n, p in self.onto.properties.items()
                        if p.field_name == field_snake
                    ),
                    None,
                )
                if not target_prop_name:
                    logger.info(
                        f"[owl_to_python] Override not applied: property '{field_snake}' not found"
                    )
                    continue
                p = self.onto.properties[target_prop_name]
                if p.type is None:
                    p.type = PropertyType.DATA_PROPERTY
                if p.type == PropertyType.DATA_PROPERTY:
                    p.data_type_hint_inner = py_type
                else:
                    p.object_range_hint = py_type
                p._predefined_data_type = True
                ov = set(p._overrides_for)
                ov.add(cls_name)
                p._overrides_for = sorted(ov)
                if cls_name not in p.declared_domains:
                    p.declared_domains.append(cls_name)
                logger.info(
                    f"[owl_to_python] Applied override: {cls_name}.{field_snake} -> {py_type}"
                )

    def compute_type_hints(self):
        """
        Compute Python type hints for all properties.
        Handles both object properties (referencing classes) and data properties (XSD types).
        """
        for info in self.onto.properties.values():
            self._set_base_descriptors(info)
            if info.type == PropertyType.OBJECT_PROPERTY:
                self._set_object_range_hint(info)
            elif not (info._predefined_data_type and info.data_type_hint_inner):
                self._set_data_type_hint(info)

    def _set_base_descriptors(self, info: PropertyInfo):
        """
        Determine the base descriptor classes for a property.
        :param info: The PropertyInfo to update.
        """
        bases = [
            self.onto.properties[sp].descriptor_name
            for sp in info.superproperties
            if sp in self.onto.properties
        ] or [PropertyDescriptor.__name__]
        if info.is_transitive:
            bases.append(TransitiveProperty.__name__)
        if info.inverse_of:
            bases.append(HasInverseProperty.__name__)
        if info.equivalent_properties:
            bases.append(HasEquivalentProperties.__name__)
        if info.disjoint_properties:
            bases.append(HasDisjointProperties.__name__)
        if info.is_symmetric:
            bases.append(SymmetricProperty.__name__)
        if info.is_asymmetric:
            bases.append(ASymmetricProperty.__name__)
        if info.is_reflexive:
            bases.append(ReflexiveProperty.__name__)
        if info.is_irreflexive:
            bases.append(IrreflexiveProperty.__name__)
        info.base_descriptors = bases

    def _set_object_range_hint(self, info: PropertyInfo):
        """
        Compute and set the object_range_hint for an ObjectProperty.
        :param info: The PropertyInfo to update.
        """
        ranges = list(info.ranges)
        if ranges:
            rng_set = set(ranges)
            simplified = [
                r
                for r in sorted(rng_set)
                if not any(
                    a in rng_set for a in self.onto.class_ancestors.get(r, set())
                )
            ]
            ranges = simplified or ranges

        if len(ranges) > 1:
            for i, r in enumerate(ranges[:-1]):
                for r2 in ranges[i + 1 :]:
                    if r2 in self.onto.classes[r].all_base_classes:
                        try:
                            ranges.remove(r2)
                        except ValueError:
                            pass
                    elif r in self.onto.classes[r2].all_base_classes:
                        try:
                            ranges.remove(r)
                        except ValueError:
                            pass
        if len(ranges) > 1:
            info.object_range_hint = f"Union[{', '.join(sorted(ranges))}]"
        elif len(ranges) == 1:
            info.object_range_hint = ranges[0]
        else:
            logger.warning(
                f"[owl_to_python]: Could not infer object range type for property '{info.name}'. Using {self.onto.base_cls_name} instead."
            )
            info.object_range_hint = self.onto.base_cls_name

    def _set_data_type_hint(self, info: PropertyInfo):
        """
        Compute and set the data_type_hint_inner for a DataProperty.
        :param info: The PropertyInfo to update.
        """
        py_types: List[str] = []
        # 1. Try mapping from XSD URIs
        for uri in info.range_uris:
            try:
                if isinstance(uri, rdflib.URIRef) and uri in self.XSD_TO_PYTHON_TYPES:
                    py_types.append(self.XSD_TO_PYTHON_TYPES[uri])
            except Exception:
                pass

        # 2. Try mapping from range names if URI mapping failed
        if not py_types:
            py_types = self._map_range_names_to_python_types(info.ranges)

        if not py_types:
            logger.warning(
                f"[owl_to_python]: Could not infer data type for property '{info.name}'. Using str."
            )
            py_types.append("str")

        unique_types = list(OrderedSet(py_types))
        info.data_type_hint_inner = (
            f"Union[{', '.join(unique_types)}]"
            if len(unique_types) > 1
            else unique_types[0]
        )

    @staticmethod
    def _map_range_names_to_python_types(range_names: List[str]) -> List[str]:
        """Map OWL range names (as strings) to Python types."""
        py_types = []
        textual = [r.lower() for r in range_names]
        for t in textual:
            if t in (
                "string",
                "normalizedstring",
                "token",
                "language",
                "anyuri",
                "datetime",
                "date",
                "time",
            ):
                py_types.append("str")
            elif t in (
                "integer",
                "int",
                "long",
                "short",
                "byte",
                "nonnegativeinteger",
                "positiveinteger",
                "unsignedlong",
                "unsignedint",
                "unsignedshort",
                "unsignedbyte",
            ):
                py_types.append("int")
            elif t in ("float", "double", "decimal"):
                py_types.append("float")
            elif t == "boolean":
                py_types.append("bool")
        return py_types

    def find_implicit_subtypes(self, props_order: List[str]):
        """
        Identify implicit subtype or role relationships between classes based on property commonality.
        """
        candidate_parents: Dict[
            str,
            Dict[Tuple[str, ...], List[Tuple[str, SubsumptionType, Dict[str, str]]]],
        ] = defaultdict(lambda: defaultdict(list))
        child_max_matched_props: Dict[str, int] = {n: 0 for n in self.onto.classes}
        for parent_name, parent_info in self.onto.classes.items():
            for child_name, child_info in self.onto.classes.items():
                if not self._is_subsumption_candidate(
                    parent_name, parent_info, child_name, child_info
                ):
                    continue

                matched_props, child_matched_props = self._get_matched_properties(
                    parent_info, child_info
                )
                if not matched_props or not child_matched_props:
                    continue

                subsumption_type = self._determine_subsumption_type(
                    matched_props, parent_info, child_info
                )
                if subsumption_type:
                    matched_props = tuple(sorted(matched_props))
                    if len(matched_props) >= child_max_matched_props[child_name]:
                        child_max_matched_props[child_name] = len(matched_props)
                        candidate_parents[child_name][matched_props].append(
                            (parent_name, subsumption_type, child_matched_props)
                        )
                    continue
        for child_name, candidates in candidate_parents.items():
            if len(candidates) == 1:
                parent_name, subsumption_type, _ = next(iter(candidates.values()))[0]
                self._apply_implicit_subsumption(
                    parent_name,
                    child_name,
                    subsumption_type,
                )
                continue
            min_mro = float("inf")
            selected = None
            for matched_props, subsumption_data in candidates.items():
                for (
                    parent_name,
                    subsumption_type,
                    child_matched_props,
                ) in subsumption_data:
                    parent_prop_name = list(child_matched_props.keys())[0]
                    child_prop_name = child_matched_props[parent_prop_name]
                    length = self.onto.properties_inheritance_path_length(
                        child_prop_name, parent_prop_name
                    )
                    if length < min_mro:
                        min_mro = length
                        selected = (parent_name, subsumption_type)
            if selected:
                parent_name, subsumption_type = selected
                self._apply_implicit_subsumption(
                    parent_name,
                    child_name,
                    subsumption_type,
                )
                continue

    def _is_subsumption_candidate(
        self,
        parent_name: str,
        parent_info: ClassInfo,
        child_name: str,
        child_info: ClassInfo,
    ) -> bool:
        """Check if parent and child are candidates for implicit subsumption."""
        if parent_name == child_name:
            return False
        if parent_name in child_info.all_base_classes_including_role_takers:
            return False
        if child_name in parent_info.all_base_classes_including_role_takers:
            return False
        base_classes = [
            bc
            for bc in child_info.base_classes
            if bc != self.onto.base_cls_name
            and bc != Symbol.__name__
            and bc != self.onto.role_cls_name
        ]
        if len(base_classes) >= 1:
            return False
        return True

    def _get_matched_properties(
        self,
        parent_info: ClassInfo,
        child_info: ClassInfo,
    ) -> Tuple[Set[str], Dict[str, str]]:
        """
        Find property base names that are compatible between parent and child.
        """

        parent_props = self.get_declared_and_restricted_properties_of_cls(
            parent_info.name
        )
        child_props = self.get_declared_and_restricted_properties_of_cls(
            child_info.name
        )

        matched_prop_names = set(parent_props).intersection(set(child_props))

        # Re-verify based on original logic: check all combinations of parent/child properties
        # and remove/add base name based on range and superproperty compatibility.
        child_matched_prop_names = {}
        for parent_p_name in parent_props:
            for child_p_name in child_props:
                child_p_info, parent_p_info = self.onto.properties.get(
                    child_p_name
                ), self.onto.properties.get(parent_p_name)
                if not child_p_info or not parent_p_info:
                    continue
                if (
                    child_p_info.type == PropertyType.DATA_PROPERTY
                    or parent_p_info.type == PropertyType.DATA_PROPERTY
                ):
                    continue
                if parent_p_name not in child_p_info.all_superproperties + [
                    child_p_name
                ]:
                    continue
                child_rng = self.get_cls_property_rng(child_info.name, child_p_name)
                parent_rng = self.get_cls_property_rng(parent_info.name, parent_p_name)
                if parent_rng not in self.onto.classes[
                    child_rng
                ].all_base_classes_including_role_takers + [child_rng]:
                    if parent_p_name in matched_prop_names:
                        matched_prop_names.remove(parent_p_name)
                    continue

                child_prop_range, parent_prop_range = (
                    child_p_info.object_range_hint,
                    parent_p_info.object_range_hint,
                )
                if parent_prop_range not in self.onto.class_ancestors.get(
                    child_prop_range, set()
                ).union({child_prop_range}):
                    if parent_p_name in matched_prop_names:
                        matched_prop_names.remove(parent_p_name)
                    continue
                matched_prop_names.add(parent_p_name)
                child_matched_prop_names[parent_p_name] = [
                    pname for pname in child_props if child_p_name in pname
                ][0]

        return matched_prop_names, child_matched_prop_names

    @lru_cache
    def get_cls_property_rng(self, cls_name: str, prop_name: str) -> Optional[str]:
        """Get the range of a property for a given class, considering restrictions."""
        cls_info = self.onto.classes[cls_name]
        if prop_name in cls_info.property_axioms_info:
            axiom = cls_info.property_axioms_info[prop_name]
            if isinstance(axiom, QualifiedAxiomInfoMixin) and axiom.on_class:
                return axiom.on_class
        prop_info = self.onto.properties.get(prop_name)
        if prop_info and prop_info.object_range_hint:
            return prop_info.object_range_hint
        return None

    @lru_cache
    def get_declared_and_restricted_properties_of_cls(self, cls_name: str) -> List[str]:
        """Get declared properties of a class, including those from restrictions."""
        cls_info = self.onto.classes[cls_name]
        cls_props = copy(cls_info.declared_properties)
        for prop_name, axiom in cls_info.property_axioms_info.items():
            if not isinstance(axiom, QualifiedAxiomInfoMixin) or not axiom.on_class:
                continue
            prop_name = axiom.property_name
            if prop_name in cls_props:
                continue
            cls_props.append(prop_name)
        return cls_props

    def _determine_subsumption_type(
        self, matched_props: Set[str], parent_info: ClassInfo, child_info: ClassInfo
    ) -> Optional[SubsumptionType]:
        """Determine if the relationship is a SUBTYPE or a ROLE."""
        parent_props = self.get_declared_and_restricted_properties_of_cls(
            parent_info.name
        )
        parent_props_filtered = {p.split("{")[0] for p in parent_props}

        if matched_props == parent_props_filtered:
            if parent_info.role_taker:
                if (
                    not child_info.role_taker
                    or child_info.role_taker.class_name
                    != parent_info.role_taker.class_name
                ):
                    return None
            return SubsumptionType.SUBTYPE
        return SubsumptionType.ROLE

    def _apply_implicit_subsumption(
        self,
        parent_name: str,
        child_name: str,
        subsumption_type: SubsumptionType,
    ):
        """Apply the determined subsumption to the child class."""
        child_info = self.onto.classes[child_name]
        parent_info = self.onto.classes[parent_name]
        if self.onto.base_cls_name in child_info.base_classes:
            child_info.base_classes.remove(self.onto.base_cls_name)

        if subsumption_type == SubsumptionType.ROLE:
            self._apply_role_subsumption(child_info, parent_name)
        else:
            self._apply_subtype_subsumption(child_info, parent_name, parent_info)

    def _apply_role_subsumption(self, child_info: ClassInfo, parent_name: str):
        """Add a role taker relationship to the class."""
        child_info.role_taker = RoleTakerInfo(
            parent_name, NamingRegistry.to_snake_case(parent_name)
        )
        if self.onto.role_cls_name not in child_info.all_base_classes:
            child_info.base_classes = [
                self.onto.role_cls_name
            ] + child_info.base_classes
            child_info.all_base_classes = [
                self.onto.role_cls_name
            ] + child_info.all_base_classes
            if Symbol.__name__ not in child_info.base_classes:
                child_info.base_classes.append(Symbol.__name__)
                child_info.all_base_classes.append(Symbol.__name__)
                child_info.all_base_classes_including_role_takers.append(
                    Symbol.__name__
                )
        child_info.all_base_classes_including_role_takers.append(parent_name)

    @staticmethod
    def _apply_subtype_subsumption(
        child_info: ClassInfo, parent_name: str, parent_info: ClassInfo
    ):
        """Make the class a subtype of another class."""
        child_info.base_classes = []
        if parent_name not in child_info.base_classes:
            child_info.base_classes.append(parent_name)
            child_info.all_base_classes.append(parent_name)
            child_info.all_base_classes_including_role_takers.append(parent_name)

        # Remove redundant properties already declared in the parent
        parent_props = set(parent_info.declared_properties)
        child_info.declared_properties = [
            p for p in child_info.declared_properties if p not in parent_props
        ]

    def __hash__(self):
        return hash(id(self))


class JinjaRenderer:
    """Renderer for generating Python code using Jinja2 templates."""

    def __init__(self, template_dir: str):
        """
        Initialize the renderer.
        :param template_dir: Directory containing Jinja2 templates.
        """
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=[loopcontrols],
        )

    def render(self, template_name: str, **context) -> str:
        """
        Render a template with the given context.
        :param template_name: Name of the template file.
        :param context: Keyword arguments for the template context.
        :return: Rendered string.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)


@dataclass
class CodeGenerator:
    """Orchestrates the generation of Python code from extracted ontology information."""

    onto: OntologyInfo
    engine: InferenceEngine = field(init=False)
    renderer: JinjaRenderer = field(init=False)

    def __post_init__(self):
        """
        Initialize the code generator.
        """
        self._ensure_ontology_base_class_in_classes()

        self._ensure_uri_in_ontology_properties()

        self._replace_ontology_role_class_with_current_role_class_name()

        self._update_base_classes()

        self.engine, self.renderer = InferenceEngine(self.onto), JinjaRenderer(
            os.path.join(os.path.dirname(__file__), "jinja")
        )

    def generate(self, base_file_name: str) -> Dict[str, str]:
        """
        Execute the full generation pipeline.
        :param base_file_name: Base name for generated files.
        :return: Dictionary mapping filenames to their rendered content.
        """

        self._execute_inference_pipeline()

        self._determine_class_properties()

        self.attach_domainless_properties_to_ontology_base_class()

        classes_order, props_order = self._finalize_and_sort()

        return self._perform_rendering(
            base_file_name,
            classes_order,
            props_order,
        )

    def attach_domainless_properties_to_ontology_base_class(self):
        """
        Attach properties without declared domains to the ontology base class.
        """
        for p in self.onto.properties.values():
            if p.declared_domains or p.domains:
                continue
            p.declared_domains = [self.onto.base_cls_name]
            base_class_info = self.onto.classes[self.onto.base_cls_name]
            if p.name not in base_class_info.declared_properties:
                base_class_info.declared_properties.append(p.name)

    def _replace_ontology_role_class_with_current_role_class_name(self):
        """
        Replace ontology role class name with current role class name.
        """
        for info in self.onto.classes.values():
            if Role.__name__ not in info.base_classes:
                continue
            info.base_classes.remove(Role.__name__)
            info.base_classes.append(self.onto.role_cls_name)

    def _ensure_uri_in_ontology_properties(self):
        """
        Ensures that the 'uri' property is present in the ontology properties.
        If not present, adds it with appropriate configuration.
        """
        if "uri" in self.onto.properties:
            return
        self.onto.properties["uri"] = PropertyInfo(
            "uri",
            "",
            PropertyType.DATA_PROPERTY,
            domains=[self.onto.base_cls_name],
            ranges=["str"],
            range_uris=[XSD.anyURI],
            label="URI of the ontology element",
            comment="The unique resource identifier (URI) of the ontology element.",
            field_name="uri",
            descriptor_name="Uri",
            declared_domains=[self.onto.base_cls_name],
        )

    def _update_base_classes(self):
        for n, info in self.onto.classes.items():
            if n == self.onto.base_cls_name:
                continue
            info.base_classes = [
                b for b in info.superclasses if b != Symbol.__name__
            ] or [self.onto.base_cls_name]
            if self.onto.role_cls_name in info.base_classes:
                for cls in copy(info.base_classes):
                    if cls not in [self.onto.role_cls_name]:
                        info.base_classes.remove(cls)
                        info.superclasses.remove(cls)
                info.base_classes.append(Symbol.__name__)

    def _ensure_ontology_base_class_in_classes(self):
        if self.onto.base_cls_name in self.onto.classes:
            return
        self.onto.classes[self.onto.base_cls_name] = ClassInfo(
            self.onto.base_cls_name,
            "",
            [Symbol.__name__],
            [Symbol.__name__],
            label=f"Base class for {self.onto.ontology_label}",
        )

    def _execute_inference_pipeline(self):
        """
        Run the inference engine to propagate types.
        """
        self.engine.compute_ancestors()

        self.engine.infer_properties()

        self.engine.apply_predefined_overrides()

        self.attach_domainless_data_properties_to_ontology_base_class()

        self.engine.compute_type_hints()

    def attach_domainless_data_properties_to_ontology_base_class(self):
        """
        Attach properties without declared domains to the ontology base class.
        """
        for p in self.onto.properties.values():
            if p.type == PropertyType.DATA_PROPERTY and not p.declared_domains:
                p.declared_domains = [self.onto.base_cls_name]

    def _determine_class_properties(self):
        """
        Decide which properties belong to which class based on inheritance and overrides.
        """
        for cls_name, info in self.onto.classes.items():
            ancestors = set(info.all_base_classes_including_role_takers)
            declared: List[str] = []
            for pn, p in self.onto.properties.items():
                if pn == "roleFor":
                    continue
                if cls_name not in set(p.declared_domains):
                    continue
                if (
                    ancestors
                    and cls_name not in p._overrides_for
                    and any(
                        a in (set(p.declared_domains) | set(p.domains))
                        for a in ancestors
                    )
                ):
                    continue
                declared.append(pn)
            info.declared_properties = sorted(set(declared))

    def _finalize_and_sort(self):
        """
        Compute transitive closures and determine final topological order for classes and properties.
        """
        for p in self.onto.properties.values():
            p.all_superproperties = self._compute_closure(
                p.superproperties, self.onto.properties, "superproperties"
            )

        for info in self.onto.classes.values():
            initial = set(info.all_base_classes)
            if info.role_taker:
                initial.add(info.role_taker.class_name)
            info.all_base_classes_including_role_takers = self._compute_closure(
                list(initial), self.onto.classes, "all_base_classes", "role_taker"
            )

        if "roleFor" in self.onto.properties:
            del self.onto.properties["roleFor"]

        prop_classes = {k: v for k, v in self.onto.properties.items()}
        props_order = self.engine.topological_order(prop_classes, "superproperties")

        self.engine.find_implicit_subtypes(props_order)

        for info in self.onto.classes.values():
            info.base_classes_for_topological_sort = info.base_classes[:]
            if info.role_taker:
                info.base_classes_for_topological_sort.append(
                    info.role_taker.class_name
                )

        for info in prop_classes.values():
            if not info.object_range_hint or "Union" not in info.object_range_hint:
                continue
            contesting_types = [
                t.strip() for t in info.object_range_hint[6:-1].split(",")
            ]
            for i, r in enumerate(contesting_types[:-1]):
                for r2 in contesting_types[i + 1 :]:
                    if (
                        r2
                        in self.onto.classes[r].all_base_classes_including_role_takers
                    ):
                        try:
                            contesting_types.remove(r)
                        except ValueError:
                            pass
                    elif (
                        r
                        in self.onto.classes[r2].all_base_classes_including_role_takers
                    ):
                        try:
                            contesting_types.remove(r2)
                        except ValueError:
                            pass
            if len(contesting_types) == 1:
                info.object_range_hint = contesting_types[0]

        removed_cls = []
        for cls_name, cls_info in self.onto.classes.items():
            if cls_name in removed_cls:
                continue
            for eq_cls in cls_info.equivalent_classes:
                removed_cls.append(eq_cls)
                initial_base_classes = copy(cls_info.base_classes)
                for base_cls in self.onto.classes[eq_cls].base_classes:
                    if base_cls not in cls_info.base_classes:
                        cls_info.base_classes.append(base_cls)
                        cls_info.all_base_classes.append(base_cls)
                        cls_info.all_base_classes_including_role_takers.append(base_cls)
                        cls_info.base_classes_for_topological_sort.append(base_cls)
                if (
                    len(initial_base_classes) == 1
                    and initial_base_classes[0] == self.onto.base_cls_name
                    and len(cls_info.base_classes) > 1
                ):
                    cls_info.base_classes.remove(self.onto.base_cls_name)
                for prop in self.onto.classes[eq_cls].declared_properties:
                    if prop not in cls_info.declared_properties:
                        cls_info.declared_properties.append(prop)
                for axiom in self.onto.classes[eq_cls].axioms:
                    if axiom not in cls_info.axioms:
                        cls_info.axioms.append(axiom)
                for python_axiom in self.onto.classes[eq_cls].axioms_python:
                    if python_axiom not in cls_info.axioms_python:
                        cls_info.axioms_python.append(python_axiom)
                for axiom_setup in self.onto.classes[eq_cls].axioms_setup:
                    if axiom_setup not in cls_info.axioms_setup:
                        cls_info.axioms_setup.append(axiom_setup)
        for rc in removed_cls:
            if rc in self.onto.classes:
                del self.onto.classes[rc]
        classes_order = self.engine.topological_order(
            self.onto.classes, "base_classes_for_topological_sort"
        )

        idx_map = {n: i for i, n in enumerate(props_order)}
        for info in prop_classes.values():
            if info.inverse_of in prop_classes:
                info.inverse_target_is_prior = idx_map.get(
                    info.inverse_of, 1e9
                ) < idx_map.get(info.name, 1e9)

        return classes_order, props_order

    def _perform_rendering(
        self,
        base_file_name,
        classes_order,
        props_order,
    ):
        """
        Render all templates and produce the final Python files and stubs.
        """
        stubs_classes = deepcopy(self.onto.classes)
        for cls_name, info in self.onto.classes.items():
            if self.onto.role_cls_name in info.base_classes:
                info.base_classes.remove(self.onto.role_cls_name)
                info.base_classes.insert(
                    0, f"{self.onto.role_cls_name}[{info.role_taker.class_name}]"
                )
                stubs_classes[cls_name].base_classes.remove(self.onto.role_cls_name)
            else:
                info.add_role_taker = stubs_classes[cls_name].add_role_taker = False

        if Role.__name__ in self.onto.classes:
            del self.onto.classes[Role.__name__]

        # topological_order might still have 'Role' name if it was in the items keys
        # We need to filter the order as well
        classes_order = [c for c in classes_order if c != Role.__name__]
        for cls_info in self.onto.classes.values():
            cls_info.onto = None
            cls_info.property_axioms_info = {}
        render_classes = {k: asdict(v) for k, v in self.onto.classes.items()}
        for c in render_classes.values():
            if c["role_taker"] is None:
                c["role_taker"] = {}

        for p_name, p_info in self.onto.properties.items():
            for eq_prop_name in p_info.equivalent_properties:
                p_info.equivalent_properties_descriptor_names.append(
                    self.onto.properties[eq_prop_name].descriptor_name
                )
            for dj_prop_name in p_info.disjoint_properties:
                p_info.disjoint_properties_descriptor_names.append(
                    self.onto.properties[dj_prop_name].descriptor_name
                )

        for prop_name, prop_info in self.onto.properties.items():
            if prop_info.chain_axioms:
                prop_info.base_descriptors.append(HasChainAxioms.__name__)

        for prop_info in self.onto.properties.values():
            prop_info.onto = None
        for stubs_info in stubs_classes.values():
            stubs_info.onto = None
            stubs_info.property_axioms_info = {}
        render_props = {k: asdict(v) for k, v in self.onto.properties.items()}
        render_stubs = {k: asdict(v) for k, v in stubs_classes.items()}
        for c in render_stubs.values():
            if c["role_taker"] is None:
                c["role_taker"] = {}

        p_mod, b_mod = f"{base_file_name}_properties", f"{base_file_name}_base"
        return {
            f"{p_mod}.py": self.renderer.render(
                "onto_properties.j2",
                properties=render_props,
                properties_order=props_order,
            ),
            f"{b_mod}.py": self.renderer.render(
                "onto_base.j2",
                cls=render_classes[self.onto.base_cls_name],
                properties=render_props,
            ),
            f"{base_file_name}.py": self.renderer.render(
                "onto_classes.j2",
                ontology_base_module_name=b_mod,
                properties_module_name=p_mod,
                classes=render_classes,
                properties=render_props,
                classes_order=classes_order,
                properties_order=props_order,
                ontology_base_class_name=self.onto.base_cls_name,
            ),
            f"{base_file_name}.pyi": self.renderer.render(
                "onto_stubs.j2",
                ontology_base_module_name=b_mod,
                properties_module_name=p_mod,
                role_takers=list(
                    OrderedSet(
                        c["role_taker"]["class_name"]
                        for c in render_classes.values()
                        if c["role_taker"]
                    )
                ),
                classes=render_stubs,
                properties=render_props,
                classes_order=classes_order,
                ontology_base_class_name=self.onto.base_cls_name,
            ),
        }

    @staticmethod
    def _compute_closure(
        initial: List[str],
        items: Dict[str, Any],
        key: str,
        role_key: Optional[str] = None,
    ) -> List[str]:
        """
        Compute the transitive closure of a relationship.
        """
        res, stack = set(), list(initial)
        while stack:
            curr = stack.pop()
            if curr not in res:
                res.add(curr)
                if curr in items:
                    item = items[curr]
                    stack.extend(
                        getattr(item, key, [])
                        if hasattr(item, key)
                        else item.get(key, [])
                    )
                    rt = (
                        getattr(item, role_key, None)
                        if role_key and hasattr(item, role_key)
                        else (item.get(role_key) if role_key else None)
                    )
                    if rt:
                        stack.append(
                            rt.class_name
                            if hasattr(rt, "class_name")
                            else rt["class_name"]
                        )
        return sorted(res)


class OwlToPythonConverter:
    """High-level converter for transforming an OWL ontology into Python source code."""

    def __init__(
        self, predefined_data_types: Optional[Dict[str, Dict[str, str]]] = None
    ):
        """
        Initialize the converter.
        :param predefined_data_types: Manual type overrides for properties.
        """
        self.graph = rdflib.Graph()
        self.classes: Dict[str, ClassInfo] = {}
        self.class_descriptions: Dict[str, ClassInfo] = {}
        self.properties: Dict[str, PropertyInfo] = {}
        self.predefined_data_types = predefined_data_types or {}
        self.metadata = MetadataExtractor(self.graph)
        self.class_ext = ClassExtractor(self.graph, self.metadata)
        self.prop_ext = PropertyExtractor(self.graph, self.metadata)
        self.ontology_label = None
        self.ontology_info: Optional[OntologyInfo] = None

    def load_ontology(self, path: str):
        """
        Load an OWL ontology from a file.
        :param path: Path to the .owl file.
        """
        self.graph.parse(path)
        self._extract_ontology_info()

    def _register_class(self, info: ClassInfo):
        """Register or update class information."""
        if info.name in self.classes:
            existing = self.classes[info.name]
            # Merge superclasses
            for sc in info.superclasses:
                if sc not in existing.superclasses:
                    existing.superclasses.append(sc)

            # Special handling for "Symbol"
            if (
                Symbol.__name__ in existing.superclasses
                and len(existing.superclasses) > 1
            ):
                existing.superclasses.remove(Symbol.__name__)

            # Merge declared properties
            for dp in info.declared_properties:
                if dp not in existing.declared_properties:
                    existing.declared_properties.append(dp)

            # Merge other metadata
            if not existing.label:
                existing.label = info.label
            if not existing.comment:
                existing.comment = info.comment
        elif info.is_description_for:
            self.class_descriptions[info.is_description_for] = info
        else:
            self.classes[info.name] = info

    def _extract_ontology_info(self):
        """
        Extract classes and properties from the loaded graph.
        """
        for s in self.graph.subjects(RDF.type, OWL.Ontology):
            self.ontology_label = self.metadata.get_label(s)
            if not self.ontology_label:
                self.ontology_label = NamingRegistry.uri_to_python_name(s)
            break

        if not self.ontology_label:
            self.ontology_label = "Thing"

        all_class_subjects = set(self.graph.subjects(RDF.type, OWL.Class))

        for cls_uri in all_class_subjects:
            # Skip BNodes that are not intersections or unions
            if isinstance(cls_uri, rdflib.BNode):
                if not (
                    list(self.graph.objects(cls_uri, OWL.intersectionOf))
                    or list(self.graph.objects(cls_uri, OWL.unionOf))
                ):
                    continue

            unions = list(self.graph.objects(cls_uri, OWL.unionOf))
            if unions:
                # 2. Register the parent class
                info = self.class_ext.extract_info(cls_uri)
                super_classes = info.superclasses[:]

                # 3. Process members and make them inherit from the parent union class
                members = NamingRegistry._get_rdf_list(self.graph, unions[0])
                for member in members:
                    member_info = self.class_ext.extract_info(member)
                    # Ensure member inherits from the union parent
                    for sc in super_classes:
                        if sc not in member_info.superclasses:
                            member_info.superclasses.append(sc)

                    # Update/Register member
                    self._register_class(member_info)
                continue

            # Handle regular classes and other BNodes (Intersections, Restrictions)
            info = self.class_ext.extract_info(cls_uri)
            if not info:
                continue
            self._register_class(info)

        for p_type in [
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.TransitiveProperty,
        ]:
            for p_uri in self.graph.subjects(RDF.type, p_type):
                if isinstance(p_uri, rdflib.term.BNode):
                    continue
                info = self.prop_ext.extract_info(p_uri)
                if info.name in self.properties:
                    existing = self.properties[info.name]
                    if p_type == OWL.TransitiveProperty:
                        existing.is_transitive = True
                    existing.domains = sorted(set(existing.domains) | set(info.domains))
                    existing.ranges = sorted(set(existing.ranges) | set(info.ranges))
                    if not existing.inverse_of:
                        existing.inverse_of = info.inverse_of
                else:
                    self.properties[info.name] = info

        self.ontology_info = OntologyInfo(
            self.graph,
            self.classes,
            self.class_descriptions,
            self.properties,
            self.predefined_data_types,
            self.ontology_label,
        )

    def generate_python_code_external(self, base_file_name: str) -> Dict[str, str]:
        """
        Generate Python code without saving to disk.
        :param base_file_name: Base name for the generated files.
        :return: Dictionary of filename to content.
        """
        gen = CodeGenerator(self.ontology_info)
        return gen.generate(base_file_name)

    def save_to_file(self, output_path: str):
        """
        Generate Python code and save it to the specified output path.
        :param output_path: Base path (filename) for the main output file.
        """
        base = os.path.splitext(os.path.basename(output_path))[0]
        for name, content in self.generate_python_code_external(base).items():
            with open(
                os.path.join(os.path.dirname(output_path), name), "w", encoding="utf-8"
            ) as f:
                f.write(content)
