"""
Check a loaded knowledge base against the OWL 2 RL/RDF rules that Ontomatic does not apply while loading: the rules that
derive the equality of two individuals (prp-fp, prp-ifp, prp-key, cls-maxc2, cls-maxqc3, cls-maxqc4, and asserted
``owl:sameAs``) and the rules that derive an inconsistency (eq-diff1-3, prp-irp, prp-asyp, prp-pdw, prp-adp,
prp-npa1/2, cls-com, cls-maxc1, cls-maxqc1/2, cax-dw, cax-adc, and dt-diff for functional data properties).

Ontomatic assumes that different IRIs denote different individuals. If no equality rule fires, the OWL 2 RL/RDF closure
of the ontology relates no two different individuals by ``owl:sameAs``, so the equality rules (eq-*) derive nothing
either, and the unique-name assumption is entailed rather than assumed. If no inconsistency rule fires, the ontology is
consistent under these rules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing_extensions import Any, Dict, Iterable, List, Set, Tuple, Type

from rdflib import Literal, OWL, RDFS, URIRef

from ...class_diagrams.utils import issubclass_or_role
from .owl2rl_tbox import (
    AllValuesFrom,
    ClassExpression,
    ComplementOf,
    HasValue,
    IntersectionOf,
    MaxCardinality,
    NamedClass,
    Owl2RlTerminology,
)


class Owl2RlRule(Enum):
    """
    The OWL 2 RL/RDF rules checked by :class:`Owl2RlCheck`, named as in the specification (OWL 2 Profiles, Section 4.3).
    """

    SAME_AS = "owl:sameAs"
    PRP_FP = "prp-fp"
    PRP_IFP = "prp-ifp"
    PRP_KEY = "prp-key"
    CLS_MAXC = "cls-maxc1/2, cls-maxqc1-4"
    PRP_FP_DATA = "prp-fp with dt-diff"
    EQ_DIFF = "eq-diff1-3"
    PRP_IRP = "prp-irp"
    PRP_ASYP = "prp-asyp"
    PRP_PDW = "prp-pdw, prp-adp"
    PRP_NPA = "prp-npa1/2"
    CLS_COM = "cls-com"
    CAX_DW = "cax-dw, cax-adc"
    MISSING = "missing conclusion"
    """
    Not a rule: a conclusion of cax-sco, cls-int2, cls-hv1 or cls-avf that the knowledge base lacks (should not
    happen, Ontomatic applies these rules while loading).
    """


@dataclass(frozen=True)
class Owl2RlFinding:
    """
    One application of a checked rule.
    """

    rule: Owl2RlRule
    """
    The rule.
    """
    individuals: Tuple[str, ...]
    """
    The individuals the rule concludes to be equal, or that make the knowledge base inconsistent.
    """
    detail: str
    """
    The premises, in words.
    """


@dataclass
class Owl2RlReport:
    """
    The result of :class:`Owl2RlCheck`.
    """

    equalities: List[Owl2RlFinding] = field(default_factory=list)
    """
    Rule applications that conclude ``owl:sameAs`` between two different individuals.
    """
    inconsistencies: List[Owl2RlFinding] = field(default_factory=list)
    """
    Rule applications that conclude ``false``, and missing conclusions.
    """
    outside_owl2_rl: List[str] = field(default_factory=list)
    """
    Superclass expressions that OWL 2 RL does not allow; the OWL 2 RL/RDF rules derive nothing from them.
    """

    @property
    def passed(self) -> bool:
        """
        :return: True if no rule derives an equality of different individuals or an inconsistency.
        """
        return not self.equalities and not self.inconsistencies

    def summary(self) -> Dict[str, Any]:
        """
        :return: The number of findings per rule, and the expressions outside OWL 2 RL.
        """
        counts: Dict[str, int] = defaultdict(int)
        for finding in self.equalities + self.inconsistencies:
            counts[finding.rule.value] += 1
        return {
            "passed": self.passed,
            "equalities": len(self.equalities),
            "inconsistencies": len(self.inconsistencies),
            "findings_per_rule": dict(counts),
            "outside_owl2_rl": self.outside_owl2_rl,
        }


@dataclass
class Owl2RlCheck:
    """
    Check the objects created by :class:`~krrood.ontomatic.ontology_to_python.owl_instances_loader.OwlLoader` against
    the equality and inconsistency rules of OWL 2 RL (see the module documentation).
    """

    terminology: Owl2RlTerminology
    """
    The terminology of the ontology.
    """
    objects_by_uri: Dict[URIRef, List[Any]]
    """
    The objects of every individual, as in ``OwlInstancesRegistry._by_uri``.
    """
    report: Owl2RlReport = field(default_factory=Owl2RlReport)
    _values: Dict[Tuple[URIRef, str], Set[str]] = field(default_factory=dict)
    _data_values: Dict[Tuple[URIRef, str], Set[Any]] = field(init=False)

    def __post_init__(self):
        self._data_values = self._asserted_data_values()

    def run(self) -> Owl2RlReport:
        """
        :return: The report of all checked rules.
        """
        self.report.outside_owl2_rl = sorted(
            {
                f"{python_class.__name__} SubClassOf {expression.description}"
                for python_class, expression in self.terminology.outside_owl2_rl()
            }
        )
        self._check_same_as()
        self._check_functional_properties()
        self._check_inverse_functional_properties()
        self._check_keys()
        self._check_superclass_expressions()
        self._check_disjoint_classes()
        self._check_property_characteristics()
        self._check_negative_property_assertions()
        self._check_different_individuals()
        return self.report

    def individuals(self) -> Iterable[URIRef]:
        return self.objects_by_uri.keys()

    def is_member(self, uri: URIRef, python_class: Type) -> bool:
        """
        :return: True if an object of the individual is an instance or role of the class.
        """
        return any(
            issubclass_or_role(type(individual_object), python_class)
            for individual_object in self.objects_by_uri.get(uri, ())
        )

    def values(self, uri: URIRef, field_name: str) -> Set[str]:
        """
        :return: The IRIs of the values of the object property of the individual, on any of its objects.
        """
        key = (uri, field_name)
        if key not in self._values:
            found = set()
            for individual_object in self.objects_by_uri.get(uri, ()):
                value = getattr(individual_object, field_name, None)
                if value is None or isinstance(value, (str, int, float, bool)):
                    continue
                for member in value if isinstance(value, (set, list, tuple)) else (value,):
                    member_uri = getattr(member, "uri", None)
                    if member_uri is not None:
                        found.add(str(member_uri))
            self._values[key] = found
        return self._values[key]

    def _asserted_data_values(self) -> Dict[Tuple[URIRef, str], Set[Any]]:
        """
        :return: The values of the data properties of every individual, from the assertions and the sub-properties
         and equivalent properties of the asserted properties (rules prp-spo1, prp-eqp1/2).
        """
        graph = self.terminology.graph
        data_properties = set(self.terminology.data_properties)
        implied: Dict[str, Set[str]] = defaultdict(set)
        for first, second in graph.subject_objects(RDFS.subPropertyOf):
            implied[self.terminology.field_name(first)].add(self.terminology.field_name(second))
        for first, second in graph.subject_objects(OWL.equivalentProperty):
            implied[self.terminology.field_name(first)].add(self.terminology.field_name(second))
            implied[self.terminology.field_name(second)].add(self.terminology.field_name(first))
        values: Dict[Tuple[URIRef, str], Set[Any]] = defaultdict(set)
        for subject, predicate, literal in graph:
            if not isinstance(literal, Literal) or subject not in self.objects_by_uri:
                continue
            field_name = self.terminology.field_name(predicate)
            if field_name not in data_properties:
                continue
            closure, frontier = {field_name}, [field_name]
            while frontier:
                for parent in implied.get(frontier.pop(), ()):
                    if parent not in closure:
                        closure.add(parent)
                        frontier.append(parent)
            data_value = literal.toPython()
            for implied_field in closure:
                values[(subject, implied_field)].add(data_value)
        return values

    def _equality(self, rule: Owl2RlRule, individuals: Iterable[Any], detail: str):
        self.report.equalities.append(
            Owl2RlFinding(rule, tuple(sorted(map(str, individuals))), detail)
        )

    def _inconsistency(self, rule: Owl2RlRule, individuals: Iterable[Any], detail: str):
        self.report.inconsistencies.append(
            Owl2RlFinding(rule, tuple(sorted(map(str, individuals))), detail)
        )

    def _check_same_as(self):
        for first, second in self.terminology.same_individuals:
            self._equality(Owl2RlRule.SAME_AS, (first, second), "asserted")

    def _check_functional_properties(self):
        data_properties = set(self.terminology.data_properties)
        for field_name in self.terminology.functional_properties:
            for uri in self.individuals():
                if field_name in data_properties:
                    data_values = self._data_values.get((uri, field_name), set())
                    if len(data_values) > 1:
                        self._inconsistency(
                            Owl2RlRule.PRP_FP_DATA,
                            (uri,),
                            f"{field_name} has the different values {sorted(map(str, data_values))}",
                        )
                    continue
                values = self.values(uri, field_name)
                if len(values) > 1:
                    self._equality(
                        Owl2RlRule.PRP_FP, values, f"values of {field_name} of {uri}"
                    )

    def _check_inverse_functional_properties(self):
        for field_name in self.terminology.inverse_functional_properties:
            subjects_by_value: Dict[str, Set[str]] = defaultdict(set)
            for uri in self.individuals():
                for value in self.values(uri, field_name):
                    subjects_by_value[value].add(str(uri))
            for value, subjects in subjects_by_value.items():
                if len(subjects) > 1:
                    self._equality(
                        Owl2RlRule.PRP_IFP, subjects, f"subjects of {field_name} {value}"
                    )

    def _key_values(self, uri: URIRef, field_name: str) -> Set[Any]:
        if field_name in self.terminology.data_properties:
            return self._data_values.get((uri, field_name), set())
        return self.values(uri, field_name)

    def _check_keys(self):
        for key in self.terminology.keys:
            members = [uri for uri in self.individuals() if self.is_member(uri, key.python_class)]
            by_first_value: Dict[Any, List[URIRef]] = defaultdict(list)
            first, *others = key.field_names
            for uri in members:
                for value in self._key_values(uri, first):
                    by_first_value[value].append(uri)
            found = set()
            for value, candidates in by_first_value.items():
                for left, right in combinations(sorted(set(candidates)), 2):
                    if (left, right) in found:
                        continue
                    if all(
                        self._key_values(left, other) & self._key_values(right, other)
                        for other in others
                    ):
                        found.add((left, right))
                        self._equality(
                            Owl2RlRule.PRP_KEY,
                            (left, right),
                            f"same key {key.field_names} of {key.python_class.__name__}",
                        )

    def _check_superclass_expressions(self):
        for python_class, expressions in self.terminology.superclass_expressions.items():
            for uri in self.individuals():
                if not self.is_member(uri, python_class):
                    continue
                for expression in expressions:
                    self._check_expression(uri, expression, python_class)

    def _check_expression(self, uri: URIRef, expression: ClassExpression, python_class: Type):
        """
        Check that an individual of ``python_class`` satisfies a superclass expression of the class.
        """
        if isinstance(expression, NamedClass):
            if not self.is_member(uri, expression.python_class):
                self._inconsistency(
                    Owl2RlRule.MISSING,
                    (uri,),
                    f"{python_class.__name__} implies {expression.python_class.__name__}",
                )
        elif isinstance(expression, IntersectionOf):
            for operand in expression.operands:
                self._check_expression(uri, operand, python_class)
        elif isinstance(expression, ComplementOf):
            operand = expression.operand
            if isinstance(operand, NamedClass) and self.is_member(uri, operand.python_class):
                self._inconsistency(
                    Owl2RlRule.CLS_COM,
                    (uri,),
                    f"{python_class.__name__} implies not {operand.python_class.__name__}",
                )
        elif isinstance(expression, HasValue):
            if isinstance(expression.value, Literal):
                present = str(expression.value.toPython()) in {
                    str(getattr(individual_object, expression.field_name, None))
                    for individual_object in self.objects_by_uri.get(uri, ())
                }
            else:
                present = str(expression.value) in self.values(uri, expression.field_name)
            if not present:
                self._inconsistency(
                    Owl2RlRule.MISSING,
                    (uri,),
                    f"{python_class.__name__} implies {expression.field_name} {expression.value}",
                )
        elif isinstance(expression, AllValuesFrom):
            for value in self.values(uri, expression.field_name):
                self._check_expression(URIRef(value), expression.filler, python_class)
        elif isinstance(expression, MaxCardinality):
            values = [
                value
                for value in self.values(uri, expression.field_name)
                if not isinstance(expression.on_class, NamedClass)
                or self.is_member(URIRef(value), expression.on_class.python_class)
            ]
            detail = (
                f"{python_class.__name__} has at most {expression.cardinality} {expression.field_name} "
                f"values, {uri} has {len(values)}"
            )
            if expression.cardinality == 0 and values:
                self._inconsistency(Owl2RlRule.CLS_MAXC, (uri,), detail)
            elif expression.cardinality == 1 and len(values) > 1:
                self._equality(Owl2RlRule.CLS_MAXC, values, detail)

    def _check_disjoint_classes(self):
        for group in self.terminology.disjoint_class_groups:
            for uri in self.individuals():
                classes = [python_class for python_class in group if self.is_member(uri, python_class)]
                if len(classes) > 1:
                    self._inconsistency(
                        Owl2RlRule.CAX_DW,
                        (uri,),
                        f"member of the disjoint classes {[c.__name__ for c in classes]}",
                    )

    def _check_property_characteristics(self):
        for field_name in self.terminology.irreflexive_properties:
            for uri in self.individuals():
                if str(uri) in self.values(uri, field_name):
                    self._inconsistency(
                        Owl2RlRule.PRP_IRP, (uri,), f"{field_name} relates it to itself"
                    )
        for field_name in self.terminology.asymmetric_properties:
            for uri in self.individuals():
                for value in self.values(uri, field_name):
                    if str(uri) in self.values(URIRef(value), field_name) and str(uri) <= value:
                        self._inconsistency(
                            Owl2RlRule.PRP_ASYP, (uri, value), f"{field_name} in both directions"
                        )
        for group in self.terminology.disjoint_property_groups:
            for first, second in combinations(group, 2):
                for uri in self.individuals():
                    shared = self.values(uri, first) & self.values(uri, second)
                    if shared:
                        self._inconsistency(
                            Owl2RlRule.PRP_PDW,
                            (uri, *shared),
                            f"related by the disjoint properties {first} and {second}",
                        )

    def _check_negative_property_assertions(self):
        for assertion in self.terminology.negative_property_assertions:
            if isinstance(assertion.target, Literal):
                violated = assertion.target.toPython() in self._data_values.get(
                    (assertion.source, assertion.field_name), set()
                )
            else:
                violated = str(assertion.target) in self.values(
                    assertion.source, assertion.field_name
                )
            if violated:
                self._inconsistency(
                    Owl2RlRule.PRP_NPA,
                    (assertion.source,),
                    f"negative assertion of {assertion.field_name} {assertion.target}",
                )

    def _check_different_individuals(self):
        equal_pairs = {
            frozenset(pair)
            for finding in self.report.equalities
            for pair in combinations(finding.individuals, 2)
        }
        for group in self.terminology.different_individual_groups:
            for pair in combinations(sorted(map(str, group)), 2):
                if frozenset(pair) in equal_pairs:
                    self._inconsistency(
                        Owl2RlRule.EQ_DIFF, pair, "equal but asserted to be different"
                    )

