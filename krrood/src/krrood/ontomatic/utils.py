from __future__ import annotations

import re
from dataclasses import fields, dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Set, Iterable, List, Type, Optional
import rdflib
from rdflib import OWL

from ..class_diagrams.utils import issubclass_or_role, Role
from ..entity_query_language.entity import variable
from ..entity_query_language.symbolic import Variable
from ..utils import inheritance_path_length


@lru_cache
def get_non_class_attribute_names_of_instance(instance: Any) -> Set[str]:
    """Get non-class fields of an instance."""
    return {f for f in dir(instance) if not f.startswith("_")} - set(
        [f for f in dir(type(instance)) if not f.startswith("_")]
        + [f.name for f in fields(type(instance))]
    )


def get_most_specific_types(types: Iterable[type]) -> List[type]:
    ts = list(dict.fromkeys(types))  # stable unique
    keep = []
    for t in ts:
        # drop t if there exists u that is a strict subtype of t
        if not any(u is not t and issubclass_or_role(u, t) for u in ts):
            keep.append(t)
    return keep


@lru_cache(maxsize=None)
def not_none_inheritance_path_length(child: Type, parent: Type) -> int:
    length = inheritance_path_length(child, parent)
    if length is None:
        return float("inf")
    return length


@dataclass
class AnonymousClass:
    """Represents an anonymous class that is yet to be identified"""

    uri: URIRef
    types: Set[Type] = field(default_factory=set)
    final_sorted_types: List[Type] = field(default_factory=list)

    def add_type(self, cls: Type):
        self.types.add(cls)

    def __hash__(self):
        return hash(self.uri)

    def __eq__(self, other):
        return hash(self) == hash(other)


def get_super_axiom_and_candidate_var(
    owner: Type, cls: Type, candidate
) -> tuple[list, Variable]:
    candidate_var = (
        candidate
        if isinstance(candidate, Variable)
        else variable(AnonymousClass, [candidate])
    )

    sup = (
        super(owner, cls)
        if not issubclass(owner, Role)
        else owner.get_role_taker_type()
    )
    axiom = getattr(sup, "axiom", None)
    super_axiom = axiom(candidate_var) if axiom else ()

    return super_axiom, candidate_var


class NamingRegistry:
    """Registry for converting OWL URIs and names to Python-compatible identifiers."""

    @staticmethod
    def uri_to_python_name(uri: Any, graph: Optional[rdflib.Graph] = None) -> str:
        """Convert URI to valid Python identifier"""
        if isinstance(uri, rdflib.URIRef):
            # Extract local name from URI
            uri_str = str(uri)
            if "#" in uri_str:
                local_name = uri_str.split("#")[-1]
            else:
                local_name = uri_str.split("/")[-1]

            # Convert to PascalCase for classes, camelCase for properties
            local_name = re.sub(r"[^a-zA-Z0-9_]", "_", local_name)
            return local_name
        elif isinstance(uri, rdflib.BNode) and graph is not None:
            return NamingRegistry.bnode_to_name(graph, uri)
        return str(uri)

    @staticmethod
    def bnode_to_name(graph: rdflib.Graph, bnode: rdflib.BNode) -> Optional[str]:
        """Generate a meaningful name for a BNode based on its description."""
        # Intersection
        intersections = list(graph.objects(bnode, OWL.intersectionOf))
        if intersections:
            items = NamingRegistry._get_rdf_list(graph, intersections[0])
            return "AND".join([NamingRegistry._get_node_name(graph, i) for i in items])

        # Union
        unions = list(graph.objects(bnode, OWL.unionOf))
        if unions:
            items = NamingRegistry._get_rdf_list(graph, unions[0])
            return "OR".join([NamingRegistry._get_node_name(graph, i) for i in items])

        # Restrictions
        on_prop = graph.value(bnode, OWL.onProperty)
        if on_prop:
            prop_name = NamingRegistry.uri_to_python_name(on_prop)
            if graph.value(bnode, OWL.someValuesFrom):
                target = graph.value(bnode, OWL.someValuesFrom)
                return f"{prop_name}SOME{NamingRegistry._get_node_name(graph, target)}"
            if graph.value(bnode, OWL.allValuesFrom):
                target = graph.value(bnode, OWL.allValuesFrom)
                target_name = NamingRegistry._get_node_name(graph, target)
                return f"{prop_name}ALL{target_name}"
            if graph.value(bnode, OWL.hasValue):
                target = graph.value(bnode, OWL.hasValue)
                return f"{prop_name}HAS{NamingRegistry._get_node_name(graph, target)}"
            if graph.value(bnode, OWL.maxQualifiedCardinality):
                target = NamingRegistry.uri_to_python_name(
                    graph.value(bnode, OWL.maxQualifiedCardinality)
                )
                on_class = NamingRegistry.uri_to_python_name(
                    graph.value(bnode, OWL.onClass)
                )
                return f"{prop_name}MAX{target}{on_class}"
            if graph.value(bnode, OWL.complementOf):
                target = NamingRegistry.uri_to_python_name(
                    graph.value(bnode, OWL.complementOf)
                )
                return f"Not{target}"
        elif graph.value(bnode, OWL.complementOf):
            complement_of = graph.value(bnode, OWL.complementOf)
            possible_complements = map(
                NamingRegistry.uri_to_python_name,
                list(graph.objects(complement_of, OWL.disjointWith)),
            )
            return "OR".join(possible_complements)
        return None

    @staticmethod
    def _get_node_name(graph, node):
        if isinstance(node, rdflib.URIRef):
            return NamingRegistry.uri_to_python_name(node)
        if isinstance(node, rdflib.BNode):
            return NamingRegistry.bnode_to_name(graph, node)
        return str(node)

    @staticmethod
    def _get_rdf_list(graph, head):
        items = []
        while head != rdflib.RDF.nil:
            items.append(graph.value(head, rdflib.RDF.first))
            head = graph.value(head, rdflib.RDF.rest)
        return [i for i in items if i is not None]

    @staticmethod
    def to_snake_case(name: str) -> str:
        """Convert a name like 'worksFor' or 'WorksFor' to 'works_for'"""
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()

    @staticmethod
    def to_pascal_case(name: str) -> str:
        """Convert a name like 'worksFor' or 'works_for' to 'WorksFor'"""
        # If it contains underscores or hyphens, split and capitalize parts
        parts = re.split(r"[_\-\s]+", name)
        if len(parts) > 1:
            return "".join(p.capitalize() for p in parts if p)
        # Otherwise just capitalize first char
        return name[:1].upper() + name[1:]


class PropertyType(str, Enum):
    """Enumeration of OWL property types."""

    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
