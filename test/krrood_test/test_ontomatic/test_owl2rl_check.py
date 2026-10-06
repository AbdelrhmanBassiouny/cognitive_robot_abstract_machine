from __future__ import annotations

from dataclasses import dataclass, field
from typing_extensions import List, Optional

import pytest
import rdflib
from rdflib import URIRef

from krrood.ontomatic.ontology_to_python.owl2rl_check import Owl2RlCheck, Owl2RlRule
from krrood.ontomatic.ontology_to_python.owl2rl_tbox import (
    AllValuesFrom,
    ComplementOf,
    HasValue,
    IntersectionOf,
    MaxCardinality,
    NamedClass,
    Owl2RlTerminology,
    OutsideOwl2Rl,
)

NAMESPACE = "http://example.org/test#"

ONTOLOGY = """
@prefix : <http://example.org/test#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Person a owl:Class .
:Man a owl:Class ; rdfs:subClassOf :Person ; owl:disjointWith :Woman .
:Woman a owl:Class ; rdfs:subClassOf :Person .
:Course a owl:Class .
:Interest a owl:Class .
:College a owl:Class .
:Student a owl:Class ; rdfs:subClassOf :Person ; owl:hasKey ( :hasId ) .
:WomanCollege a owl:Class ; rdfs:subClassOf [ owl:intersectionOf ( :College
    [ a owl:Restriction ; owl:onProperty :hasStudent ; owl:allValuesFrom [ owl:complementOf :Man ] ] ) ] .
:FootballFan a owl:Class ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :likes ; owl:hasValue :Football ] .
:LeisureStudent a owl:Class ; rdfs:subClassOf [ owl:intersectionOf ( :Student
    [ a owl:Restriction ; owl:onProperty :takesCourse ; owl:maxQualifiedCardinality "1"^^xsd:nonNegativeInteger ;
      owl:onClass :Course ] ) ] .
:Role a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :roleFor ; owl:someValuesFrom :Person ] .

:enrollIn a owl:ObjectProperty, owl:FunctionalProperty .
:isHeadOf a owl:ObjectProperty, owl:InverseFunctionalProperty .
:likes a owl:ObjectProperty, owl:IrreflexiveProperty ; owl:propertyDisjointWith :dislikes .
:dislikes a owl:ObjectProperty .
:affiliatedWith a owl:ObjectProperty, owl:AsymmetricProperty .
:hasStudent a owl:ObjectProperty .
:takesCourse a owl:ObjectProperty .
:roleFor a owl:ObjectProperty .
:hasId a owl:DatatypeProperty .
:hasAge a owl:DatatypeProperty, owl:FunctionalProperty .

:alice a owl:NamedIndividual ; :hasId "7" ; :hasAge 30, 31 .
:bob a owl:NamedIndividual ; :hasId "7" .
:carol a owl:NamedIndividual .
:Football a owl:NamedIndividual .
[] a owl:AllDifferent ; owl:distinctMembers ( :d1 :d2 ) .
[] a owl:NegativePropertyAssertion ; owl:sourceIndividual :carol ; owl:assertionProperty :likes ;
   owl:targetIndividual :Football .
"""


@dataclass(eq=False)
class Thing:
    uri: str
    enroll_in: List[Thing] = field(default_factory=list)
    is_head_of: List[Thing] = field(default_factory=list)
    likes: List[Thing] = field(default_factory=list)
    dislikes: List[Thing] = field(default_factory=list)
    affiliated_with: List[Thing] = field(default_factory=list)
    has_student: List[Thing] = field(default_factory=list)
    takes_course: List[Thing] = field(default_factory=list)


@dataclass(eq=False)
class Person(Thing):
    pass


@dataclass(eq=False)
class Man(Person):
    pass


@dataclass(eq=False)
class Woman(Person):
    pass


@dataclass(eq=False)
class Student(Person):
    pass


@dataclass(eq=False)
class LeisureStudent(Student):
    pass


@dataclass(eq=False)
class Course(Thing):
    pass


@dataclass(eq=False)
class College(Thing):
    pass


@dataclass(eq=False)
class WomanCollege(College):
    pass


@dataclass(eq=False)
class FootballFan(Person):
    pass


@dataclass(eq=False)
class Interest(Thing):
    pass


@dataclass(eq=False)
class Role(Thing):
    pass


CLASSES = {
    cls.__name__: cls
    for cls in (Person, Man, Woman, Student, LeisureStudent, Course, College, WomanCollege)
    + (FootballFan, Interest, Role)
}


@pytest.fixture
def terminology() -> Owl2RlTerminology:
    graph = rdflib.Graph()
    graph.parse(data=ONTOLOGY, format="turtle")
    return Owl2RlTerminology(graph, CLASSES)


def individual(cls, name: str, **values) -> Thing:
    return cls(uri=NAMESPACE + name, **values)


def check(terminology: Owl2RlTerminology, *objects: Thing):
    return Owl2RlCheck(terminology, {URIRef(o.uri): [o] for o in objects}).run()


def test_terminology_reads_superclass_expressions_and_constraints(terminology):
    assert terminology.superclass_expressions[WomanCollege] == [
        IntersectionOf(
            (
                NamedClass(College),
                AllValuesFrom("has_student", ComplementOf(NamedClass(Man))),
            )
        )
    ]
    assert terminology.superclass_expressions[FootballFan] == [
        HasValue("likes", URIRef(NAMESPACE + "Football"))
    ]
    assert terminology.superclass_expressions[LeisureStudent] == [
        IntersectionOf(
            (NamedClass(Student), MaxCardinality("takes_course", 1, NamedClass(Course)))
        )
    ]
    assert terminology.functional_properties == ["enroll_in", "has_age"]
    assert terminology.inverse_functional_properties == ["is_head_of"]
    assert terminology.disjoint_property_groups == [("likes", "dislikes")]
    assert terminology.disjoint_class_groups == [(Man, Woman)]
    assert [
        (key.python_class, key.field_names) for key in terminology.keys
    ] == [(Student, ("has_id",))]
    assert [type(e) for _, e in terminology.outside_owl2_rl()] == [OutsideOwl2Rl]


def test_a_knowledge_base_without_violations_passes(terminology):
    football = individual(Interest, "Football")
    fan = individual(FootballFan, "fan", likes=[football])
    report = check(terminology, football, fan)
    assert report.passed
    assert report.outside_owl2_rl == [
        "Role SubClassOf ObjectSomeValuesFrom on roleFor in superclass position"
    ]


def rules(findings) -> set:
    return {finding.rule for finding in findings}


def test_equality_rules(terminology):
    first, second = individual(College, "c1"), individual(College, "c2")
    student = individual(Student, "s", enroll_in=[first, second])
    head_one = individual(Person, "h1", is_head_of=[first])
    head_two = individual(Person, "h2", is_head_of=[first])
    course_one, course_two = individual(Course, "k1"), individual(Course, "k2")
    leisure = individual(LeisureStudent, "l", takes_course=[course_one, course_two])
    alice, bob = individual(Student, "alice"), individual(Student, "bob")
    report = check(
        terminology,
        first,
        second,
        student,
        head_one,
        head_two,
        course_one,
        course_two,
        leisure,
        alice,
        bob,
    )
    assert rules(report.equalities) == {
        Owl2RlRule.PRP_FP,
        Owl2RlRule.PRP_IFP,
        Owl2RlRule.CLS_MAXC,
        Owl2RlRule.PRP_KEY,
    }
    assert any(
        f.rule == Owl2RlRule.PRP_KEY
        and f.individuals == (NAMESPACE + "alice", NAMESPACE + "bob")
        for f in report.equalities
    )


def test_inconsistency_rules(terminology):
    man = individual(Man, "m")
    both = individual(Man, "both")
    both_as_woman = Woman(uri=both.uri)
    college = individual(WomanCollege, "wc", has_student=[man])
    football = individual(Interest, "Football")
    carol = individual(Person, "carol", likes=[football])
    selfish = individual(Person, "selfish")
    selfish.likes.append(selfish)
    torn = individual(Person, "torn", likes=[football], dislikes=[football])
    left, right = individual(College, "left"), individual(College, "right")
    left.affiliated_with.append(right)
    right.affiliated_with.append(left)
    report = Owl2RlCheck(
        terminology,
        {
            URIRef(o.uri): objects
            for o, objects in [
                (man, [man]),
                (both, [both, both_as_woman]),
                (college, [college]),
                (football, [football]),
                (carol, [carol]),
                (selfish, [selfish]),
                (torn, [torn]),
                (left, [left]),
                (right, [right]),
                (individual(Person, "alice"), [individual(Person, "alice")]),
            ]
        },
    ).run()
    assert rules(report.inconsistencies) == {
        Owl2RlRule.CAX_DW,
        Owl2RlRule.CLS_COM,
        Owl2RlRule.PRP_NPA,
        Owl2RlRule.PRP_IRP,
        Owl2RlRule.PRP_PDW,
        Owl2RlRule.PRP_ASYP,
        Owl2RlRule.PRP_FP_DATA,
    }


def test_missing_conclusions_are_reported(terminology):
    fan = individual(FootballFan, "fan")
    report = check(terminology, fan, individual(Interest, "Football"))
    assert rules(report.inconsistencies) == {Owl2RlRule.MISSING}


def test_equal_individuals_asserted_to_be_different_are_inconsistent(terminology):
    college = individual(College, "d0")
    first, second = individual(Course, "d1"), individual(Course, "d2")
    student = individual(Student, "s", enroll_in=[first, second])
    report = check(terminology, college, first, second, student)
    assert Owl2RlRule.EQ_DIFF in rules(report.inconsistencies)
