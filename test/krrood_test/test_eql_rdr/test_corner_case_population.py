"""
Tests that fitting records, for every rule it inserts, the case that triggered it.

The corner case is what later lets an auto-resolver ask "what distinguishes this new
case from the one the firing rule was written for?", so each inserted rule must map to
the case being fitted at the moment of insertion, and a fit that inserts nothing must
record nothing.
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.serialization import (
    walk_rules_in_emission_order,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species, make_animal
from .expert_doubles import scripted_expert

# %% the tree these tests grow

TRAIT_CONDITIONS = {
    Species.mammal: lambda variable: variable.milk == True,
    Species.bird: lambda variable: variable.feathers == True,
    Species.fish: lambda variable: variable.fins == True,
}
"""
One discriminating trait per conclusion, so each fitted case inserts exactly one rule.
"""


def _mammal() -> Animal:
    return make_animal("corner_mammal", milk=True, hair=True, toothed=True, legs=4)


def _bird() -> Animal:
    return make_animal("corner_bird", feathers=True, eggs=True, legs=2)


def _fish() -> Animal:
    return make_animal("corner_fish", fins=True, aquatic=True, backbone=False)


def _rule_nodes(rdr: EQLSingleClassRDR):
    """
    :param rdr: The fitted RDR.
    :return: Its rule condition nodes, in the order the rules were emitted.
    """
    return walk_rules_in_emission_order(rdr.conditions_root)


# %% one entry per inserted rule


def test_the_first_rule_records_the_case_that_seeded_it():
    rdr = EQLSingleClassRDR(Animal, "species")
    mammal = _mammal()

    rdr.fit_case(mammal, Species.mammal, scripted_expert(TRAIT_CONDITIONS))

    assert len(rdr.corner_cases.cases) == 1
    assert rdr.corner_cases.get(_rule_nodes(rdr)[0]._id_) is mammal


def test_an_alternative_records_the_case_no_rule_fired_for():
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(TRAIT_CONDITIONS)
    mammal, bird = _mammal(), _bird()
    rdr.fit_case(mammal, Species.mammal, expert)

    rdr.fit_case(bird, Species.bird, expert)

    assert len(rdr.corner_cases.cases) == 2
    assert rdr.corner_cases.get(_rule_nodes(rdr)[1]._id_) is bird


def test_a_refinement_records_the_case_the_wrong_rule_fired_for():
    rdr = EQLSingleClassRDR(Animal, "species")
    # An over-general first rule: backbone -> fish, which a mammal also satisfies.
    expert = scripted_expert(
        {**TRAIT_CONDITIONS, Species.fish: lambda variable: variable.backbone == True}
    )
    fish = make_animal("corner_backboned_fish", fins=True, aquatic=True)
    mammal = _mammal()
    rdr.fit_case(fish, Species.fish, expert)
    assert rdr.classify(mammal) is Species.fish

    rdr.fit_case(mammal, Species.mammal, expert)

    assert len(rdr.corner_cases.cases) == 2
    assert rdr.corner_cases.get(_rule_nodes(rdr)[1]._id_) is mammal


def test_bulk_fitting_records_one_case_per_inserted_rule():
    rdr = EQLSingleClassRDR(Animal, "species")
    cases = [_mammal(), _bird(), _fish()]

    rdr.fit(
        cases,
        [Species.mammal, Species.bird, Species.fish],
        scripted_expert(TRAIT_CONDITIONS),
    )

    assert len(rdr.corner_cases.cases) == 3


# %% and nothing when no rule is inserted


def test_refitting_an_already_correct_case_records_nothing_new():
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(TRAIT_CONDITIONS)
    mammal = _mammal()
    rdr.fit_case(mammal, Species.mammal, expert)
    recorded_before = len(rdr.corner_cases.cases)

    rdr.fit_case(mammal, Species.mammal, expert)

    assert len(rdr.corner_cases.cases) == recorded_before


def test_recording_corner_cases_does_not_change_what_is_classified():
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(TRAIT_CONDITIONS)
    mammal, bird = _mammal(), _bird()
    rdr.fit_case(mammal, Species.mammal, expert)
    before = rdr.classify(mammal)

    rdr.fit_case(bird, Species.bird, expert)

    assert before is Species.mammal
    assert rdr.classify(mammal) is before
