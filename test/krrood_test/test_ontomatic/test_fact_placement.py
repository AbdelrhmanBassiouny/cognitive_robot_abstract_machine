from __future__ import annotations

from krrood.entity_query_language.symbol_graph import SymbolGraph
from krrood.ontomatic.property_descriptor.property_descriptor_relation import (
    PropertyDescriptorRelation,
)

from ..dataset.university_ontology_like_classes import (
    BasketBall,
    BasketBallLover,
    Loves,
    PersonOnto,
    Sports,
    SportsLover,
    VideoGames,
)


def make_individual():
    SymbolGraph().clear()
    SymbolGraph()
    person = PersonOnto(name="Bass")
    basketball_lover = BasketBallLover(person=person)
    sports_lover = SportsLover(person=person)
    return person, basketball_lover, sports_lover


def test_objects_of_individual_lists_the_root_first_and_tells_roles_apart():
    person, basketball_lover, sports_lover = make_individual()
    for individual_object in (person, basketball_lover, sports_lover):
        objects = PropertyDescriptorRelation.objects_of_individual(individual_object)
        assert [id(o) for o in objects] == [
            id(person),
            id(basketball_lover),
            id(sports_lover),
        ]


def test_declaring_object_chooses_the_first_declaration_whose_range_admits_the_value():
    person, basketball_lover, sports_lover = make_individual()
    football = Sports(name="Football")
    basketball = BasketBall(name="BasketBall")
    for individual_object in (person, basketball_lover, sports_lover):
        holder, descriptor = PropertyDescriptorRelation.declaring_object(
            individual_object, Loves, football
        )
        assert holder is sports_lover and descriptor.domain is SportsLover
        holder, descriptor = PropertyDescriptorRelation.declaring_object(
            individual_object, Loves, basketball
        )
        assert holder is basketball_lover and descriptor.domain is BasketBallLover


def test_declaring_object_falls_back_to_the_first_declaration():
    person, basketball_lover, _ = make_individual()
    game = VideoGames(name="Tetris")
    holder, descriptor = PropertyDescriptorRelation.declaring_object(
        person, Loves, game
    )
    assert holder is basketball_lover and descriptor.domain is BasketBallLover


def test_declaring_object_is_none_without_a_declaration():
    SymbolGraph().clear()
    SymbolGraph()
    person = PersonOnto(name="Bass")
    assert (
        PropertyDescriptorRelation.declaring_object(
            person, Loves, Sports(name="Football")
        )
        is None
    )
