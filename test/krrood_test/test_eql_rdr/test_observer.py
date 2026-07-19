"""
Tests for ConclusionObserver reading RDR conclusions out of pure EQL evaluation.

Rule trees here are hand-built to exercise the observer directly, independent of
incremental fitting.
"""

import unittest

from krrood.entity_query_language.factories import (
    add,
    alternative,
    entity,
    refinement,
    variable,
)
from krrood.entity_query_language.rdr.observer import classify_case
from krrood.entity_query_language.rdr.utils import UNSET

from .animal import Animal, Species, make_animal
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def _first_with_target(species: Species) -> Animal:
    return next(animal for animal, target in zip(animals, targets) if target is species)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestConclusionObserver(unittest.TestCase):
    def _build_flat_tree(self):
        """
        Milk -> mammal ; else feathers -> bird ; else fins -> fish.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
            with alternative(animal.feathers == True):
                add(animal.species, Species.bird)
            with alternative(animal.fins == True):
                add(animal.species, Species.fish)
        return animal, animal.species, query

    def test_classifies_mammal(self):
        animal, species, query = self._build_flat_tree()
        observer = classify_case(
            query, animal, species, _first_with_target(Species.mammal)
        )
        self.assertEqual(observer.conclusion, Species.mammal)

    def test_classifies_bird_via_alternative(self):
        animal, species, query = self._build_flat_tree()
        observer = classify_case(
            query, animal, species, _first_with_target(Species.bird)
        )
        self.assertEqual(observer.conclusion, Species.bird)

    def test_classifies_fish_via_second_alternative(self):
        animal, species, query = self._build_flat_tree()
        observer = classify_case(
            query, animal, species, _first_with_target(Species.fish)
        )
        self.assertEqual(observer.conclusion, Species.fish)

    def test_no_rule_fires_returns_none(self):
        animal, species, query = self._build_flat_tree()
        # An insect has no milk, feathers, or fins → no rule fires.
        observer = classify_case(
            query, animal, species, _first_with_target(Species.insect)
        )
        self.assertTrue(observer.conclusion is UNSET)
        self.assertEqual(observer.fired, [])

    def test_refinement_overrides_parent_conclusion(self):
        """
        Backbone -> fish (default); refine: backbone & milk -> mammal.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)
            with refinement(animal.milk == True):
                add(animal.species, Species.mammal)

        mammal = _first_with_target(Species.mammal)
        fish = _first_with_target(Species.fish)

        mammal_observer = classify_case(query, animal, animal.species, mammal)
        self.assertEqual(mammal_observer.conclusion, Species.mammal)

        fish_observer = classify_case(query, animal, animal.species, fish)
        self.assertEqual(fish_observer.conclusion, Species.fish)

    def test_observer_captures_satisfied_condition_ids(self):
        animal, species, query = self._build_flat_tree()
        observer = classify_case(
            query, animal, species, _first_with_target(Species.mammal)
        )
        self.assertTrue(observer.fired)
        satisfied_condition_ids = observer.fired[-1].result.satisfied_condition_ids
        self.assertIsNotNone(satisfied_condition_ids)
        self.assertGreater(len(satisfied_condition_ids), 0)

    def test_distinct_conclusion_is_single_for_mutually_exclusive(self):
        animal, species, query = self._build_flat_tree()
        observer = classify_case(
            query, animal, species, _first_with_target(Species.mammal)
        )
        self.assertEqual(observer.distinct_conclusions, [Species.mammal])

    def test_repeated_classification_does_not_accumulate(self):
        # Guards the ReEnterableLazyIterable.set_iterable reset: classifying many
        # cases in sequence must not leak prior cases into the domain.
        animal, species, query = self._build_flat_tree()
        mammal = _first_with_target(Species.mammal)
        bird = _first_with_target(Species.bird)
        self.assertEqual(
            classify_case(query, animal, species, mammal).conclusion, Species.mammal
        )
        self.assertEqual(
            classify_case(query, animal, species, bird).conclusion, Species.bird
        )
        # Re-classify the mammal again — must still be mammal, not polluted.
        self.assertEqual(
            classify_case(query, animal, species, mammal).conclusion, Species.mammal
        )


class TestAttributeConditionTruthiness(unittest.TestCase):
    """
    Regression: a plain Attribute condition must respect its value's truthiness.

    Before the fix, ``entity(a).where(a.milk)`` fired even when ``milk=False`` because
    ``_evaluate_conclusions_and_update_bindings_`` checked ``is_false`` (always False
    for Attributes) instead of the value itself.
    """

    def setUp(self):
        self.has_milk = make_animal("aardvark", milk=True)
        self.has_no_milk = make_animal("bass", milk=False)

    def _build_attribute_query(self):
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk)  # plain Attribute, no == True
        with query:
            add(animal.species, Species.mammal)
        return animal, animal.species, query

    def _build_comparator_query(self):
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
        return animal, animal.species, query

    def test_attribute_condition_fires_when_true(self):
        animal, species, query = self._build_attribute_query()
        observer = classify_case(query, animal, species, self.has_milk)
        self.assertEqual(observer.conclusion, Species.mammal)

    def test_attribute_condition_does_not_fire_when_false(self):
        animal, species, query = self._build_attribute_query()
        observer = classify_case(query, animal, species, self.has_no_milk)
        self.assertIs(observer.conclusion, UNSET)

    def test_comparator_condition_fires_when_true(self):
        animal, species, query = self._build_comparator_query()
        observer = classify_case(query, animal, species, self.has_milk)
        self.assertEqual(observer.conclusion, Species.mammal)

    def test_comparator_condition_does_not_fire_when_false(self):
        animal, species, query = self._build_comparator_query()
        observer = classify_case(query, animal, species, self.has_no_milk)
        self.assertIs(observer.conclusion, UNSET)
