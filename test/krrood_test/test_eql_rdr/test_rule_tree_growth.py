"""
Phase 3 tests: live rule-tree growth via insert_at / insert_refinement / insert_alternative.

Growing a tree dynamically (outside any ``with`` block) must produce the same
classifications as building the equivalent tree statically with ``with`` blocks.
"""

import unittest

from krrood.entity_query_language.factories import (
    add,
    alternative,
    entity,
    not_,
    variable,
)
from krrood.entity_query_language.rules.conclusion_selector import ConclusionSelector
from krrood.entity_query_language.rdr.observer import classify_case
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.rdr.utils import UNSET
from krrood.entity_query_language.exceptions import SelfReferentialInsertionError

from krrood.entity_query_language.rules.conclusion_selector import _fresh_expression

from .animal import Animal, Species, make_animal
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(sp: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is sp)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestRuleTreeGrowth(unittest.TestCase):
    def test_dynamic_alternative_insertion(self):
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
        query.build()

        # Bird does not fire yet.
        self.assertTrue(
            classify_case(query, animal, animal.species, first(Species.bird)).conclusion
            is UNSET
        )

        insert_alternative(
            query._conditions_root_,
            animal.feathers == True,
            animal.species,
            Species.bird,
        )

        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.bird)
            ).conclusion,
            Species.bird,
        )
        # Existing rule unaffected.
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.mammal)
            ).conclusion,
            Species.mammal,
        )

    def test_dynamic_refinement_override(self):
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)  # default guess for vertebrates
        query.build()

        # Before refinement, a mammal is misclassified as fish.
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.mammal)
            ).conclusion,
            Species.fish,
        )

        insert_refinement(
            query._conditions_root_,
            animal.milk == True,
            animal.species,
            Species.mammal,
        )

        # Refinement overrides for mammals; fish still classified as fish.
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.mammal)
            ).conclusion,
            Species.mammal,
        )
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.fish)
            ).conclusion,
            Species.fish,
        )

    def test_dynamic_growth_matches_static_tree(self):
        # Static tree: milk->mammal ; alt feathers->bird ; alt fins->fish
        s_animal = variable(Animal, domain=[])
        s_query = entity(s_animal).where(s_animal.milk == True)
        with s_query:
            add(s_animal.species, Species.mammal)
            with alternative(s_animal.feathers == True):
                add(s_animal.species, Species.bird)
            with alternative(s_animal.fins == True):
                add(s_animal.species, Species.fish)
        s_query.build()

        # Dynamic tree: same rules grown one at a time.
        d_animal = variable(Animal, domain=[])
        d_query = entity(d_animal).where(d_animal.milk == True)
        with d_query:
            add(d_animal.species, Species.mammal)
        d_query.build()
        insert_alternative(
            d_query._conditions_root_,
            d_animal.feathers == True,
            d_animal.species,
            Species.bird,
        )
        insert_alternative(
            d_query._conditions_root_,
            d_animal.fins == True,
            d_animal.species,
            Species.fish,
        )

        for case, target in zip(animals, targets):
            static = classify_case(s_query, s_animal, s_animal.species, case).conclusion
            dynamic = classify_case(
                d_query, d_animal, d_animal.species, case
            ).conclusion
            self.assertEqual(
                static,
                dynamic,
                f"{case.name}: static={static} dynamic={dynamic}",
            )

    def test_refinement_then_alternative_nested(self):
        # Grow: backbone->fish ; refine milk->mammal ; alt(of refinement) aquatic->(stay mammal? no)
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)
        query.build()

        ref = insert_refinement(
            query._conditions_root_,
            animal.milk == True,
            animal.species,
            Species.mammal,
        )
        # Alternative to the refinement: backbone & feathers -> bird
        insert_alternative(ref, animal.feathers == True, animal.species, Species.bird)

        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.mammal)
            ).conclusion,
            Species.mammal,
        )
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.bird)
            ).conclusion,
            Species.bird,
        )
        self.assertEqual(
            classify_case(
                query, animal, animal.species, first(Species.fish)
            ).conclusion,
            Species.fish,
        )


    def test_fresh_expression_does_not_corrupt_original_parents(self):
        """
        Regression test: _fresh_expression must NOT mutate the original expression's
        ``_parents_`` list.  The bug was that ``copy(expr)`` does a shallow copy, so
        ``clone._parents_`` was the **same list** as ``expr._parents_``.  Then
        ``clone._parent_ = None`` (the old code) would go through the setter and
        wrench ``expr._parent__`` out of the **shared** ``_parents_`` list, leaving
        the original with an inconsistent ``_parent__`` that wasn't tracked in
        ``_parents_``.  Later ``_remove_parent_`` would crash with ``ValueError``.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
        query.build()

        # Create a Comparator and insert it as a refinement (giving it a parent).
        condition = animal.backbone == False
        insert_refinement(
            query._conditions_root_,
            condition,
            animal.species,
            Species.reptile,
        )

        # condition now has a parent (the Refinement node).
        assert condition._parent__ is not None
        orig_parent = condition._parent__
        orig_parents_before = list(condition._parents_)

        # Clone via _fresh_expression — the path that used to corrupt.
        clone = _fresh_expression(condition)

        # The original must be untouched.
        self.assertIs(
            condition._parent__, orig_parent,
            "Original _parent__ must not change",
        )
        self.assertEqual(
            condition._parents_, orig_parents_before,
            "Original _parents_ must not change",
        )
        # Clone must have its own independent lists and no parent.
        self.assertIsNone(clone._parent__, "Clone must not have a parent")
        self.assertEqual(len(clone._parents_), 0, "Clone must have empty _parents_")
        self.assertEqual(len(clone._children_), 0, "Clone must have empty _children_")
        self.assertIsNot(
            clone._parents_, condition._parents_,
            "Clone must NOT share _parents_ list with original",
        )
        self.assertIsNot(
            clone._children_, condition._children_,
            "Clone must NOT share _children_ list with original",
        )


    def test_shared_anchor_refinement_does_not_corrupt_sibling_alternative(self):
        """Regression test: inserting a refinement at a MappedVariable anchor that also
        appears as a sub-expression inside a sibling alternative condition must not
        corrupt that sibling condition.

        Bug: ``backbone`` is used both as the mammal-rule anchor (inside a Refinement)
        AND as the left operand of the molusc condition ``backbone == False``.  When
        ``backbone == False`` was created its ``_parent_`` overwrote the Refinement
        pointer.  ``insert_at`` then called ``_replace_child_`` on the Comparator
        instead of the Refinement, turning the molusc condition into
        ``(backbone except if not_eggs) == False``.

        Fix: ``insert_at`` scans ``anchor._parents_`` for the most recent
        ConclusionSelector rather than relying on ``anchor._parent_``.
        """
        animal = variable(Animal, domain=[])

        # Rule 1: backbone → mammal (backbone is the conditions root)
        query = entity(animal).where(animal.backbone)
        with query:
            add(animal.species, Species.mammal)
        query.build()
        backbone_anchor = query._conditions_root_  # the backbone MappedVariable

        # Rule 2: eggs → fish (refinement on backbone)
        insert_refinement(
            backbone_anchor,
            animal.eggs,
            animal.species,
            Species.fish,
        )

        # Rule 3: backbone == False → molusc (alternative at the conditions root).
        # Uses the SAME backbone MappedVariable singleton in a Comparator.
        # This overwrites backbone._parent_ from Refinement to Comparator —
        # reproducing the exact condition for the bug.
        molusc_condition = animal.backbone == False
        insert_alternative(
            query._conditions_root_,
            molusc_condition,
            animal.species,
            Species.molusc,
        )

        # Rule 4: insert a refinement at backbone (not_(eggs) → reptile).
        # Before the fix, this called _replace_child_ on the Comparator, corrupting it.
        insert_refinement(
            backbone_anchor,
            not_(animal.eggs),
            animal.species,
            Species.reptile,
        )

        # The molusc comparator must still have backbone (not a Refinement) as its left child.
        self.assertIs(
            molusc_condition.left,
            backbone_anchor,
            "molusc condition's left child was corrupted by the backbone refinement",
        )
        self.assertNotIsInstance(
            molusc_condition.left,
            ConclusionSelector,
            "molusc condition must not embed a ConclusionSelector as its left child",
        )

        # Classification sanity: molusc case (backbone=False) must still classify as
        # molusc.  Without the fix the corrupted condition "(backbone except if
        # not_eggs) == False" does not evaluate the same as "backbone == False",
        # so this fails.
        molusc_case = make_animal("test_molusc", backbone=False, eggs=True)
        self.assertEqual(
            classify_case(query, animal, animal.species, molusc_case).conclusion,
            Species.molusc,
        )

        # The reptile refinement (not_eggs at backbone) must fire for a case with
        # backbone=True and eggs=False.
        reptile_case = make_animal("test_reptile", backbone=True, eggs=False)
        self.assertEqual(
            classify_case(query, animal, animal.species, reptile_case).conclusion,
            Species.reptile,
        )


    def test_insert_at_with_anchor_as_condition_raises(self):
        """Regression: insert_at(anchor, anchor) must raise SelfReferentialInsertionError
        before touching the tree, not silently create Refinement(backbone, backbone)."""
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone)
        with query:
            add(animal.species, Species.mammal)
        query.build()
        backbone = query._conditions_root_

        original_conclusions = set(backbone._conclusions_)

        with self.assertRaises(SelfReferentialInsertionError):
            insert_refinement(backbone, backbone, animal.species, Species.reptile)

        # Tree must be untouched: backbone's conclusions must not have grown.
        self.assertEqual(
            backbone._conclusions_,
            original_conclusions,
            "backbone._conclusions_ must not change after a failed self-referential insert",
        )

    def test_fresh_expression_resets_conclusions(self):
        """Regression: _fresh_expression must reset _conclusions_ so cloned nodes do not
        share the original's conclusion set."""
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone)
        with query:
            add(animal.species, Species.mammal)
        query.build()
        backbone = query._conditions_root_

        # Give backbone a conclusion (it already has one from the query).
        self.assertTrue(len(backbone._conclusions_) > 0)

        # Clone a non-MappedVariable expression that has a conclusion attached.
        not_eggs = not_(animal.eggs)
        insert_refinement(backbone, not_eggs, animal.species, Species.reptile)
        # not_eggs now has a parent and no direct conclusions, but we test the set isolation.
        clone = _fresh_expression(not_eggs)

        self.assertIsNot(
            clone._conclusions_,
            not_eggs._conclusions_,
            "Clone must not share _conclusions_ set with the original",
        )
        self.assertEqual(
            len(clone._conclusions_),
            0,
            "Clone's _conclusions_ must be empty after _fresh_expression",
        )


if __name__ == "__main__":
    unittest.main()
