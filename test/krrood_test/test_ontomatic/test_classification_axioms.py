"""
Only sufficient conditions of a class may become classification axioms (``axiom_python``) in the generated code.

The ontology below is a reduced version of the OWL2Bench OWL 2 RL ontology:

* ``LeisureStudent SubClassOf (Student and takesCourse max 1 Course)`` and
  ``WomanCollege SubClassOf (College and hasStudent only (not Man))`` are necessary conditions.
* ``T20CricketFan EquivalentTo isCrazyAbout value T20Cricket`` is a definition (sufficient).
* ``Student and (hasMajor some Science) SubClassOf ScienceStudent`` is a general class axiom (sufficient), whose named
  conjunct ``Student`` must be kept.
"""

from __future__ import annotations

import re

import pytest

from krrood.ontomatic.ontology_to_python.owl_to_python import OwlToPythonConverter

ONTOLOGY = """
@prefix : <http://benchmark/OWL2Bench#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://benchmark/OWL2Bench> a owl:Ontology .

:takesCourse a owl:ObjectProperty ; rdfs:domain :Student ; rdfs:range :Course .
:hasStudent a owl:ObjectProperty ; rdfs:domain :College ; rdfs:range :Student .
:hasMajor a owl:ObjectProperty ; rdfs:domain :Student ; rdfs:range :Discipline .
:isCrazyAbout a owl:ObjectProperty ; rdfs:domain :Person ; rdfs:range :Interest .

:Person a owl:Class .
:Man a owl:Class ; rdfs:subClassOf :Person .
:Woman a owl:Class ; rdfs:subClassOf :Person .
:Student a owl:Class ; rdfs:subClassOf :Person .
:Course a owl:Class .
:College a owl:Class .
:Discipline a owl:Class .
:Science a owl:Class ; rdfs:subClassOf :Discipline .
:Interest a owl:Class .
:Cricket a owl:Class ; rdfs:subClassOf :Interest .
:ScienceStudent a owl:Class ; rdfs:subClassOf :Student .

:LeisureStudent a owl:Class ;
    rdfs:subClassOf :Student ;
    rdfs:subClassOf [ a owl:Class ;
        owl:intersectionOf ( :Student
            [ a owl:Restriction ; owl:onProperty :takesCourse ;
              owl:maxQualifiedCardinality "1"^^xsd:nonNegativeInteger ; owl:onClass :Course ] ) ] .

:WomanCollege a owl:Class ;
    rdfs:subClassOf :College ;
    rdfs:subClassOf [ a owl:Class ;
        owl:intersectionOf ( :College
            [ a owl:Restriction ; owl:onProperty :hasStudent ;
              owl:allValuesFrom [ a owl:Class ; owl:complementOf :Man ] ] ) ] .

:T20Cricket a owl:NamedIndividual , :Cricket .
:T20CricketFan a owl:Class ;
    rdfs:subClassOf :Person ;
    owl:equivalentClass [ a owl:Restriction ; owl:onProperty :isCrazyAbout ; owl:hasValue :T20Cricket ] .

[ a owl:Class ;
  owl:intersectionOf ( :Student [ a owl:Restriction ; owl:onProperty :hasMajor ; owl:someValuesFrom :Science ] ) ;
  rdfs:subClassOf :ScienceStudent ] .
"""


@pytest.fixture(scope="module")
def generated_classes(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("ontology") / "ontology.ttl"
    path.write_text(ONTOLOGY)
    converter = OwlToPythonConverter()
    converter.load_ontology(str(path))
    files = converter.generate_python_code_external("model")
    return files["model.py"]


def class_body(source: str, class_name: str) -> str:
    match = re.search(
        rf"^class {class_name}\(.*?(?=^@dataclass|^class |\Z)", source, re.S | re.M
    )
    assert match, f"class {class_name} not generated"
    return match.group(0)


def test_necessary_conditions_are_not_classification_axioms(generated_classes):
    for class_name in ["LeisureStudent", "WomanCollege"]:
        body = class_body(generated_classes, class_name)
        assert "def axiom_python" not in body
        assert "def axiom(" not in body
        assert "def necessary_conditions_python" in body


def test_equivalent_class_definition_is_a_classification_axiom(generated_classes):
    body = class_body(generated_classes, "T20CricketFan")
    assert "def axiom_python" in body
    assert "http://benchmark/OWL2Bench#T20Cricket" in body


def test_general_class_axiom_keeps_named_conjunct(generated_classes):
    body = class_body(generated_classes, "ScienceStudent")
    axiom_python = body[body.index("def axiom_python") :]
    assert "issubclass_or_role(t, Student) for t in candidate.types" in axiom_python
    assert "Science" in axiom_python
