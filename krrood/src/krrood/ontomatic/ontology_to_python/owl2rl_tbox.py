"""
The parts of an OWL 2 RL terminology that the generated Python model does not encode, read from the ontology's RDF
graph: the class expressions in superclass position (necessary conditions) and the axioms that constrain individuals
(functional and inverse-functional properties, keys, disjointness, irreflexive and asymmetric properties, negative
property assertions, equality and inequality of individuals).

The loader uses the superclass expressions to derive types and facts (OWL 2 RL/RDF rules cax-sco, cls-int2, cls-hv1 and
cls-avf), and :mod:`krrood.ontomatic.ontology_to_python.owl2rl_check` uses the rest to check the rules that derive
equality between individuals or inconsistency.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing_extensions import Dict, List, Optional, Tuple, Type, Union

import rdflib
from rdflib import OWL, RDF, RDFS, BNode, Literal, URIRef
from rdflib.collection import Collection

from ..utils import local_name, to_snake


class ClassExpression(ABC):
    """
    A class expression in superclass position, as allowed by OWL 2 RL.
    """


@dataclass(frozen=True)
class NamedClass(ClassExpression):
    """
    A named class of the model.
    """

    python_class: Type
    """
    The generated class.
    """


@dataclass(frozen=True)
class IntersectionOf(ClassExpression):
    """
    ``ObjectIntersectionOf``: an individual of the expression is an individual of every operand (rule cls-int2).
    """

    operands: Tuple[ClassExpression, ...]
    """
    The operands.
    """


@dataclass(frozen=True)
class ComplementOf(ClassExpression):
    """
    ``ObjectComplementOf``: an individual of the expression is not an individual of the operand (rule cls-com).
    """

    operand: ClassExpression
    """
    The complemented class expression.
    """


@dataclass(frozen=True)
class HasValue(ClassExpression):
    """
    ``ObjectHasValue``: an individual of the expression has the value for the property (rule cls-hv1).
    """

    field_name: str
    """
    The attribute name of the property.
    """
    value: Union[URIRef, Literal]
    """
    The value, an individual or a literal.
    """


@dataclass(frozen=True)
class AllValuesFrom(ClassExpression):
    """
    ``ObjectAllValuesFrom``: every value of the property of an individual of the expression is an individual of the
    filler (rule cls-avf).
    """

    field_name: str
    """
    The attribute name of the property.
    """
    filler: ClassExpression
    """
    The class expression of the values.
    """


@dataclass(frozen=True)
class MaxCardinality(ClassExpression):
    """
    ``ObjectMaxCardinality`` 0 or 1, optionally qualified: an individual of the expression has at most ``cardinality``
    distinct values of the property in the qualifying class (rules cls-maxc1/2, cls-maxqc1-4).
    """

    field_name: str
    """
    The attribute name of the property.
    """
    cardinality: int
    """
    0 or 1.
    """
    on_class: Optional[ClassExpression] = None
    """
    The qualifying class, None for an unqualified restriction or ``owl:Thing``.
    """


@dataclass(frozen=True)
class OutsideOwl2Rl(ClassExpression):
    """
    A class expression that OWL 2 RL does not allow in superclass position (for example ``ObjectSomeValuesFrom``), or
    that the model cannot represent. The OWL 2 RL/RDF rules derive nothing from it.
    """

    description: str
    """
    What the expression is.
    """


@dataclass(frozen=True)
class Key:
    """
    ``HasKey``: two individuals of the class with the same values of all key properties are equal (rule prp-key).
    """

    python_class: Type
    """
    The class that has the key.
    """
    field_names: Tuple[str, ...]
    """
    The attribute names of the key properties.
    """


@dataclass(frozen=True)
class NegativePropertyAssertion:
    """
    ``NegativeObjectPropertyAssertion`` or ``NegativeDataPropertyAssertion`` (rules prp-npa1/2).
    """

    source: URIRef
    """
    The subject individual.
    """
    field_name: str
    """
    The attribute name of the property.
    """
    target: Union[URIRef, Literal]
    """
    The value that the subject must not have.
    """


@dataclass
class Owl2RlTerminology:
    """
    The superclass expressions and the constraint axioms of an ontology, with classes resolved to the generated model
    classes and properties to their attribute names.
    """

    graph: rdflib.Graph
    """
    The RDF graph of the ontology.
    """
    class_by_name: Dict[str, Type]
    """
    The generated classes by their name (the local name of the class IRI).
    """
    superclass_expressions: Dict[Type, List[ClassExpression]] = field(
        default_factory=dict
    )
    """
    For every class, the anonymous class expressions it is a subclass of or equivalent to.
    """
    functional_properties: List[str] = field(default_factory=list)
    """
    The attribute names of the functional object and data properties (rule prp-fp).
    """
    inverse_functional_properties: List[str] = field(default_factory=list)
    """
    The attribute names of the inverse-functional properties (rule prp-ifp).
    """
    irreflexive_properties: List[str] = field(default_factory=list)
    """
    The attribute names of the irreflexive properties (rule prp-irp).
    """
    asymmetric_properties: List[str] = field(default_factory=list)
    """
    The attribute names of the asymmetric properties (rule prp-asyp).
    """
    disjoint_property_groups: List[Tuple[str, ...]] = field(default_factory=list)
    """
    Groups of pairwise disjoint properties (``propertyDisjointWith`` and ``AllDisjointProperties``).
    """
    disjoint_class_groups: List[Tuple[Type, ...]] = field(default_factory=list)
    """
    Groups of pairwise disjoint classes (``disjointWith`` and ``AllDisjointClasses``).
    """
    keys: List[Key] = field(default_factory=list)
    """
    The keys of the classes (rule prp-key).
    """
    negative_property_assertions: List[NegativePropertyAssertion] = field(
        default_factory=list
    )
    """
    The negative property assertions (rules prp-npa1/2).
    """
    same_individuals: List[Tuple[URIRef, URIRef]] = field(default_factory=list)
    """
    Asserted ``owl:sameAs`` between two different IRIs.
    """
    different_individual_groups: List[Tuple[URIRef, ...]] = field(default_factory=list)
    """
    Groups of pairwise different individuals (``differentFrom`` and ``AllDifferent``).
    """
    data_properties: List[str] = field(default_factory=list)
    """
    The attribute names of the data properties.
    """
    implied_data_properties: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    """
    For every data property, the data properties a value of it is also a value of: its super-properties and
    equivalent properties, transitively (rules prp-spo1, prp-eqp1/2).
    """
    data_property_domains: Dict[str, Tuple[Type, ...]] = field(default_factory=dict)
    """
    For every data property, the declared domains of the property and of the properties it implies (rule prp-dom).
    """

    def __post_init__(self):
        self._read_superclass_expressions()
        self._read_property_characteristics()
        self._read_disjointness()
        self._read_keys()
        self._read_negative_property_assertions()
        self._read_equality_and_inequality()
        self._read_data_property_implications_and_domains()

    def python_class(self, node: rdflib.term.Node) -> Optional[Type]:
        """
        :param node: A class IRI.
        :return: The generated class of the IRI, or None.
        """
        if not isinstance(node, URIRef):
            return None
        return self.class_by_name.get(local_name(node))

    @staticmethod
    def field_name(property_node: rdflib.term.Node) -> str:
        """
        :param property_node: A property IRI.
        :return: The attribute name of the property in the generated model.
        """
        return to_snake(local_name(property_node))

    def members(self, list_node: rdflib.term.Node) -> List[rdflib.term.Node]:
        """
        :param list_node: The head of an RDF list.
        :return: The members of the list.
        """
        return list(Collection(self.graph, list_node))

    def superclass_expression(self, node: rdflib.term.Node) -> Optional[ClassExpression]:
        """
        Read a class expression in superclass position.

        :param node: The IRI or blank node of the expression.
        :return: The expression; None for owl:Thing and for named classes without a generated class.
        """
        graph = self.graph
        if isinstance(node, URIRef):
            python_class = self.python_class(node)
            return NamedClass(python_class) if python_class is not None else None
        operands = graph.value(node, OWL.intersectionOf)
        if operands is not None:
            return IntersectionOf(
                tuple(
                    expression
                    for expression in map(self.superclass_expression, self.members(operands))
                    if expression is not None
                )
            )
        complemented = graph.value(node, OWL.complementOf)
        if complemented is not None:
            operand = self.superclass_expression(complemented)
            return ComplementOf(operand) if operand is not None else None
        property_node = graph.value(node, OWL.onProperty)
        if property_node is None:
            return OutsideOwl2Rl(f"class expression {node} is not supported")
        field_name = self.field_name(property_node)
        value = graph.value(node, OWL.hasValue)
        if value is not None:
            return HasValue(field_name, value)
        filler = graph.value(node, OWL.allValuesFrom)
        if filler is not None:
            filler_expression = self.superclass_expression(filler)
            return (
                AllValuesFrom(field_name, filler_expression)
                if filler_expression is not None
                else None
            )
        for predicate in (OWL.maxCardinality, OWL.maxQualifiedCardinality):
            cardinality = graph.value(node, predicate)
            if cardinality is not None:
                qualifying_class = graph.value(node, OWL.onClass)
                return MaxCardinality(
                    field_name,
                    int(cardinality),
                    (
                        self.superclass_expression(qualifying_class)
                        if qualifying_class is not None
                        else None
                    ),
                )
        if graph.value(node, OWL.someValuesFrom) is not None:
            return OutsideOwl2Rl(
                f"ObjectSomeValuesFrom on {local_name(property_node)} in superclass position"
            )
        return OutsideOwl2Rl(f"restriction on {local_name(property_node)} is not supported")

    def _read_superclass_expressions(self):
        """
        Read the anonymous class expressions that a named class is a subclass of or equivalent to; an equivalence is
        read in both directions of the triple.
        """
        pairs = list(self.graph.subject_objects(RDFS.subClassOf))
        for first, second in self.graph.subject_objects(OWL.equivalentClass):
            pairs += [(first, second), (second, first)]
        for subclass_node, superclass_node in pairs:
            python_class = self.python_class(subclass_node)
            if python_class is None or not isinstance(superclass_node, BNode):
                continue
            expression = self.superclass_expression(superclass_node)
            if expression is not None:
                self.superclass_expressions.setdefault(python_class, []).append(
                    expression
                )

    def _properties_of_type(self, property_type: URIRef) -> List[str]:
        return [
            self.field_name(node)
            for node in self.graph.subjects(RDF.type, property_type)
            if isinstance(node, URIRef)
        ]

    def _read_property_characteristics(self):
        self.functional_properties = self._properties_of_type(OWL.FunctionalProperty)
        self.inverse_functional_properties = self._properties_of_type(
            OWL.InverseFunctionalProperty
        )
        self.irreflexive_properties = self._properties_of_type(OWL.IrreflexiveProperty)
        self.asymmetric_properties = self._properties_of_type(OWL.AsymmetricProperty)
        self.data_properties = self._properties_of_type(OWL.DatatypeProperty)

    def _read_disjointness(self):
        for first, second in self.graph.subject_objects(OWL.propertyDisjointWith):
            self.disjoint_property_groups.append(
                (self.field_name(first), self.field_name(second))
            )
        for group in self.graph.subjects(RDF.type, OWL.AllDisjointProperties):
            self.disjoint_property_groups.append(
                tuple(
                    map(self.field_name, self.members(self.graph.value(group, OWL.members)))
                )
            )
        for first, second in self.graph.subject_objects(OWL.disjointWith):
            classes = (self.python_class(first), self.python_class(second))
            if None not in classes:
                self.disjoint_class_groups.append(classes)
        for group in self.graph.subjects(RDF.type, OWL.AllDisjointClasses):
            classes = tuple(
                python_class
                for python_class in map(
                    self.python_class, self.members(self.graph.value(group, OWL.members))
                )
                if python_class is not None
            )
            if len(classes) > 1:
                self.disjoint_class_groups.append(classes)

    def _read_keys(self):
        for class_node, key_list in self.graph.subject_objects(OWL.hasKey):
            python_class = self.python_class(class_node)
            if python_class is not None:
                self.keys.append(
                    Key(python_class, tuple(map(self.field_name, self.members(key_list))))
                )

    def _read_negative_property_assertions(self):
        for assertion in self.graph.subjects(RDF.type, OWL.NegativePropertyAssertion):
            target = self.graph.value(assertion, OWL.targetIndividual)
            if target is None:
                target = self.graph.value(assertion, OWL.targetValue)
            self.negative_property_assertions.append(
                NegativePropertyAssertion(
                    self.graph.value(assertion, OWL.sourceIndividual),
                    self.field_name(self.graph.value(assertion, OWL.assertionProperty)),
                    target,
                )
            )

    def _read_equality_and_inequality(self):
        self.same_individuals = [
            (first, second)
            for first, second in self.graph.subject_objects(OWL.sameAs)
            if first != second
        ]
        for first, second in self.graph.subject_objects(OWL.differentFrom):
            self.different_individual_groups.append((first, second))
        for group in self.graph.subjects(RDF.type, OWL.AllDifferent):
            members = self.graph.value(group, OWL.members)
            if members is None:
                members = self.graph.value(group, OWL.distinctMembers)
            self.different_individual_groups.append(tuple(self.members(members)))

    def _read_data_property_implications_and_domains(self):
        data_properties = set(self.data_properties)
        neighbours: Dict[str, set] = {name: set() for name in data_properties}
        for first, second in self.graph.subject_objects(RDFS.subPropertyOf):
            if self.field_name(first) in data_properties:
                neighbours[self.field_name(first)].add(self.field_name(second))
        for first, second in self.graph.subject_objects(OWL.equivalentProperty):
            if self.field_name(first) in data_properties:
                neighbours[self.field_name(first)].add(self.field_name(second))
                neighbours.setdefault(self.field_name(second), set()).add(
                    self.field_name(first)
                )
        declared_domains: Dict[str, List[Type]] = {}
        for property_node, domain_node in self.graph.subject_objects(RDFS.domain):
            python_class = self.python_class(domain_node)
            if python_class is not None:
                declared_domains.setdefault(self.field_name(property_node), []).append(
                    python_class
                )
        for name in data_properties:
            implied, frontier = set(), [name]
            while frontier:
                for neighbour in neighbours.get(frontier.pop(), ()):
                    if neighbour not in implied and neighbour != name:
                        implied.add(neighbour)
                        frontier.append(neighbour)
            self.implied_data_properties[name] = tuple(sorted(implied))
            self.data_property_domains[name] = tuple(
                domain
                for implied_name in (name, *sorted(implied))
                for domain in declared_domains.get(implied_name, ())
            )

    def outside_owl2_rl(self) -> List[Tuple[Type, OutsideOwl2Rl]]:
        """
        :return: The superclass expressions that OWL 2 RL does not allow, with the class that uses each.
        """
        found = []

        def collect(python_class: Type, expression: ClassExpression):
            if isinstance(expression, OutsideOwl2Rl):
                found.append((python_class, expression))
            elif isinstance(expression, IntersectionOf):
                for operand in expression.operands:
                    collect(python_class, operand)
            elif isinstance(expression, AllValuesFrom):
                collect(python_class, expression.filler)

        for python_class, expressions in self.superclass_expressions.items():
            for expression in expressions:
                collect(python_class, expression)
        return found
