"""
Self-contained tests for backward inference (:mod:`krrood.entity_query_language.rdr.backward_inference`).

These build rule trees directly from core EQL primitives (``variable``, ``refinement``,
``alternative``, ``next_rule``, ``add``) rather than through :class:`EQLSingleClassRDR`, so
this test module -- and the backward-inference slice it covers -- stays testable
independently of the rest of the RDR engine.
"""

from dataclasses import dataclass
from enum import Enum

from krrood.entity_query_language.factories import (
    add,
    alternative,
    next_rule,
    refinement,
    variable,
)
from krrood.entity_query_language.operators.core_logical_operators import Not
from krrood.entity_query_language.rdr.backward_inference import (
    BackwardInferenceIndex,
    GuardCondition,
    SufficientConditionSet,
    what_do_we_know_about,
    _leaf_guards,
)
from krrood.entity_query_language.rules.conclusion_selector import Refinement


@dataclass(unsafe_hash=True)
class Animal:
    """Minimal RDR classification target used only by this test module."""

    name: str
    has_fur: bool = False
    can_fly: bool = False
    lays_eggs: bool = False


class Species(Enum):
    MAMMAL = "mammal"
    BIRD = "bird"
    REPTILE = "reptile"


# ---------------------------------------------------------------------------
# Guard/SufficientConditionSet/ConclusionKnowledge primitives
# ---------------------------------------------------------------------------


def test_guard_condition_holds_for_a_true_case():
    animal = variable(Animal, domain=[])
    guard = GuardCondition(animal.has_fur, negated=False)

    assert guard.holds_for(animal, Animal("cat", has_fur=True)) is True
    assert guard.holds_for(animal, Animal("snake", has_fur=False)) is False


def test_guard_condition_negated_inverts_the_result():
    animal = variable(Animal, domain=[])
    guard = GuardCondition(animal.has_fur, negated=True)

    assert guard.holds_for(animal, Animal("cat", has_fur=True)) is False
    assert guard.holds_for(animal, Animal("snake", has_fur=False)) is True


def test_sufficient_condition_set_requires_every_guard_to_hold():
    animal = variable(Animal, domain=[])
    scs = SufficientConditionSet(
        conditions=(
            GuardCondition(animal.has_fur, negated=False),
            GuardCondition(animal.can_fly, negated=False),
        )
    )

    assert scs.evaluate_against(animal, Animal("bat", has_fur=True, can_fly=True)) is True
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True, can_fly=False)) is False
    assert scs.evaluate_against(animal, Animal("eagle", has_fur=False, can_fly=True)) is False


def test_conclusion_knowledge_is_satisfiable_only_with_at_least_one_path():
    animal = variable(Animal, domain=[])
    unsatisfiable = what_do_we_know_about(None, Species.MAMMAL)
    assert unsatisfiable.is_satisfiable() is False
    assert unsatisfiable.sufficient_condition_sets == ()

    condition = animal.has_fur
    with condition:
        add(animal.species, Species.MAMMAL)
    satisfiable = what_do_we_know_about(condition._conditions_root_, Species.MAMMAL)
    assert satisfiable.is_satisfiable() is True


# ---------------------------------------------------------------------------
# what_do_we_know_about over real rule trees
# ---------------------------------------------------------------------------


def test_bare_condition_rule_is_its_own_sufficient_guard():
    animal = variable(Animal, domain=[])
    condition = animal.has_fur
    with condition:
        add(animal.species, Species.MAMMAL)

    knowledge = what_do_we_know_about(condition._conditions_root_, Species.MAMMAL)

    assert len(knowledge.sufficient_condition_sets) == 1
    scs = knowledge.sufficient_condition_sets[0]
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True)) is True
    assert scs.evaluate_against(animal, Animal("snake", has_fur=False)) is False


def test_conclusion_value_with_no_rule_path_is_unsatisfiable():
    animal = variable(Animal, domain=[])
    condition = animal.has_fur
    with condition:
        add(animal.species, Species.MAMMAL)

    knowledge = what_do_we_know_about(condition._conditions_root_, Species.REPTILE)

    assert knowledge.is_satisfiable() is False


def test_refinement_child_guard_requires_both_parent_and_refinement_conditions():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with refinement(animal.can_fly):
            add(animal.species, Species.BIRD)

    root = base_condition._conditions_root_
    knowledge = what_do_we_know_about(root, Species.BIRD)

    assert len(knowledge.sufficient_condition_sets) == 1
    scs = knowledge.sufficient_condition_sets[0]
    assert scs.evaluate_against(animal, Animal("bat", has_fur=True, can_fly=True)) is True
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True, can_fly=False)) is False
    assert scs.evaluate_against(animal, Animal("eagle", has_fur=False, can_fly=True)) is False


def test_refinement_parent_guard_excludes_the_refined_case():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with refinement(animal.can_fly):
            add(animal.species, Species.BIRD)

    root = base_condition._conditions_root_
    knowledge = what_do_we_know_about(root, Species.MAMMAL)

    assert len(knowledge.sufficient_condition_sets) == 1
    scs = knowledge.sufficient_condition_sets[0]
    # Refined away: has_fur AND can_fly no longer satisfies the parent's own guard.
    assert scs.evaluate_against(animal, Animal("bat", has_fur=True, can_fly=True)) is False
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True, can_fly=False)) is True
    assert scs.evaluate_against(animal, Animal("eagle", has_fur=False, can_fly=True)) is False


def test_alternative_first_branch_guard_is_unconditional_on_the_second():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with alternative(animal.lays_eggs):
            add(animal.species, Species.REPTILE)

    root = base_condition._conditions_root_
    knowledge = what_do_we_know_about(root, Species.MAMMAL)

    assert len(knowledge.sufficient_condition_sets) == 1
    scs = knowledge.sufficient_condition_sets[0]
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True, lays_eggs=True)) is True
    assert scs.evaluate_against(animal, Animal("cat", has_fur=True, lays_eggs=False)) is True
    assert scs.evaluate_against(animal, Animal("snake", has_fur=False, lays_eggs=True)) is False


def test_alternative_second_branch_guard_requires_the_first_to_be_false():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with alternative(animal.lays_eggs):
            add(animal.species, Species.REPTILE)

    root = base_condition._conditions_root_
    knowledge = what_do_we_know_about(root, Species.REPTILE)

    assert len(knowledge.sufficient_condition_sets) == 1
    scs = knowledge.sufficient_condition_sets[0]
    assert scs.evaluate_against(animal, Animal("snake", has_fur=False, lays_eggs=True)) is True
    # has_fur is True (first branch would have fired) -> alternative guard must fail.
    assert scs.evaluate_against(animal, Animal("platypus", has_fur=True, lays_eggs=True)) is False
    assert scs.evaluate_against(animal, Animal("cat", has_fur=False, lays_eggs=False)) is False


def test_next_branches_are_independent_disjuncts_with_no_cross_guards():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with next_rule(animal.lays_eggs):
            add(animal.species, Species.REPTILE)

    root = base_condition._conditions_root_
    mammal_knowledge = what_do_we_know_about(root, Species.MAMMAL)
    reptile_knowledge = what_do_we_know_about(root, Species.REPTILE)

    assert len(mammal_knowledge.sufficient_condition_sets) == 1
    assert len(reptile_knowledge.sufficient_condition_sets) == 1
    mammal_scs = mammal_knowledge.sufficient_condition_sets[0]
    reptile_scs = reptile_knowledge.sufficient_condition_sets[0]

    # A case satisfying the REPTILE branch's own condition alone does not need to
    # also satisfy (or avoid) the MAMMAL branch's condition, and vice versa.
    both = Animal("weird", has_fur=True, lays_eggs=True)
    assert mammal_scs.evaluate_against(animal, both) is True
    assert reptile_scs.evaluate_against(animal, both) is True

    neither = Animal("plain", has_fur=False, lays_eggs=False)
    assert mammal_scs.evaluate_against(animal, neither) is False
    assert reptile_scs.evaluate_against(animal, neither) is False


def test_ambiguous_value_produces_one_sufficient_condition_set_per_path():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with next_rule(animal.lays_eggs):
            add(animal.species, Species.MAMMAL)

    knowledge = what_do_we_know_about(base_condition._conditions_root_, Species.MAMMAL)

    assert len(knowledge.sufficient_condition_sets) == 2


# ---------------------------------------------------------------------------
# _leaf_guards: Not(ConclusionSelector) decomposition
# ---------------------------------------------------------------------------


def test_not_of_refinement_decomposes_to_the_negated_base_condition():
    animal = variable(Animal, domain=[])
    refinement_condition = Refinement(animal.has_fur, animal.can_fly == False)

    guards = _leaf_guards(Not(refinement_condition), negated=False)

    assert len(guards) == 1
    assert guards[0].expression is animal.has_fur
    assert guards[0].negated is True


# ---------------------------------------------------------------------------
# BackwardInferenceIndex caching
# ---------------------------------------------------------------------------


def test_index_builds_once_and_serves_every_conclusion_value_from_cache():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)
        with next_rule(animal.lays_eggs):
            add(animal.species, Species.REPTILE)

    index = BackwardInferenceIndex()
    assert index._cache is None

    mammal_knowledge = index.query(base_condition._conditions_root_, Species.MAMMAL)
    assert index._cache is not None
    cache_after_first_query = index._cache

    reptile_knowledge = index.query(base_condition._conditions_root_, Species.REPTILE)
    assert index._cache is cache_after_first_query, "Second query must reuse the cached index"

    assert mammal_knowledge.is_satisfiable() is True
    assert reptile_knowledge.is_satisfiable() is True


def test_invalidate_forces_the_next_query_to_rebuild():
    animal = variable(Animal, domain=[])
    base_condition = animal.has_fur
    with base_condition:
        add(animal.species, Species.MAMMAL)

    index = BackwardInferenceIndex()
    index.query(base_condition._conditions_root_, Species.MAMMAL)
    assert index._cache is not None

    index.invalidate()

    assert index._cache is None
