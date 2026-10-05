"""
Subclass and role relations of the generated classes must only come from the ontology (rdfs:subClassOf,
owl:equivalentClass and roleFor restrictions), never from properties that two classes happen to share.

In the OWL2Bench RL ontology, ``SportsLover`` and ``PeopleWithHobby`` are both roles of ``Person`` and unrelated
otherwise; ``loves`` is a sub-property of ``likes``. Ontomatic used to make ``SportsLover`` a subclass of
``PeopleWithHobby`` because of the shared (super-)property, which OWL 2 RL does not entail.
"""

from __future__ import annotations

import re

from krrood.ontomatic.ontology_to_python.owl_to_python import OwlToPythonConverter

ONTOLOGY = """
@prefix : <http://benchmark/OWL2Bench#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://benchmark/OWL2Bench> a owl:Ontology .

:roleFor a owl:ObjectProperty , owl:TransitiveProperty ; rdfs:domain :Role .
:likes a owl:ObjectProperty ; rdfs:domain :Person ; rdfs:range :Interest .
:loves a owl:ObjectProperty ; rdfs:subPropertyOf :likes ; rdfs:domain :Person ; rdfs:range :Interest .

:Role a owl:Class .
:Person a owl:Class .
:Interest a owl:Class .
:Sports a owl:Class ; rdfs:subClassOf :Interest .

:PeopleWithHobby a owl:Class ; rdfs:subClassOf :Person , :Role ,
    [ a owl:Restriction ; owl:onProperty :roleFor ; owl:someValuesFrom :Person ] .
:SportsLover a owl:Class ; rdfs:subClassOf :Person , :Role ,
    [ a owl:Restriction ; owl:onProperty :roleFor ; owl:someValuesFrom :Person ] .

[ a owl:Class ;
  owl:intersectionOf ( :Person [ a owl:Restriction ; owl:onProperty :likes ; owl:someValuesFrom :Interest ] ) ;
  rdfs:subClassOf :PeopleWithHobby ] .
[ a owl:Class ;
  owl:intersectionOf ( :Person [ a owl:Restriction ; owl:onProperty :loves ; owl:someValuesFrom :Sports ] ) ;
  rdfs:subClassOf :SportsLover ] .
"""


def test_shared_properties_do_not_create_subclasses(tmp_path):
    path = tmp_path / "ontology.ttl"
    path.write_text(ONTOLOGY)
    converter = OwlToPythonConverter()
    converter.load_ontology(str(path))
    source = converter.generate_python_code_external("model")["model.py"]
    header = re.search(r"^class SportsLover\((.*?)\):", source, re.M).group(1)
    assert "PeopleWithHobby" not in header
    assert "Role[Person]" in header
