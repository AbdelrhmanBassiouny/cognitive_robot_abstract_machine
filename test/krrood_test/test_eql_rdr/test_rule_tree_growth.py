"""
Tests for live rule-tree growth via insert_at / insert_refinement / insert_alternative.

Growing a tree dynamically (outside any ``with`` block) must produce the same
classifications as building the equivalent tree statically with ``with`` blocks.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import (
    add,
    alternative,
    entity,
    not_,
    refinement,
    variable,
)
from krrood.entity_query_language.query.operations import Where
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    ConclusionSelector,
    Refinement as RefinementClass,
)
from krrood.entity_query_language.rdr.observer import classify_case
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.exceptions import SelfReferentialInsertionError

from .animal import Animal, Species, make_animal
from .zoo_loader import ZooDataset

zoo = ZooDataset.load()


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestRuleTreeGrowth:
    """
    Splicing refinements and alternatives into a rule tree after it was built.
    """

    def test_dynamic_alternative_insertion(self):
        """
        A case that fires no rule starts to be classified once an alternative covering
        it is inserted.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
        query.build()

        # Bird does not fire yet.
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.bird)
            ).conclusion
            is ...
        )

        insert_alternative(
            query._conditions_root_,
            animal.feathers == True,
            animal.species,
            Species.bird,
        )

        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.bird)
            ).conclusion
            == Species.bird
        )
        # Existing rule unaffected.
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.mammal)
            ).conclusion
            == Species.mammal
        )

    def test_dynamic_refinement_override(self):
        """
        A refinement inserted under a rule overrides that rule's conclusion for the
        cases it covers.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)  # default guess for vertebrates
        query.build()

        # Before refinement, a mammal is misclassified as fish.
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.mammal)
            ).conclusion
            == Species.fish
        )

        insert_refinement(
            query._conditions_root_,
            animal.milk == True,
            animal.species,
            Species.mammal,
        )

        # Refinement overrides for mammals; fish still classified as fish.
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.mammal)
            ).conclusion
            == Species.mammal
        )
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.fish)
            ).conclusion
            == Species.fish
        )

    def test_dynamic_growth_matches_static_tree(self):
        # Static tree: milk->mammal ; alt feathers->bird ; alt fins->fish
        """
        A tree grown by insertion classifies like the same tree written out statically.
        """
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

        for case, target in zip(zoo.animals, zoo.targets):
            static = classify_case(s_query, s_animal, s_animal.species, case).conclusion
            dynamic = classify_case(
                d_query, d_animal, d_animal.species, case
            ).conclusion
            assert static == dynamic

    def test_refinement_then_alternative_nested(self):
        # Grow: backbone->fish ; refine milk->mammal ; alt(of refinement) aquatic->(stay mammal? no)
        """
        An alternative can be inserted under a refinement that was itself inserted.
        """
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

        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.mammal)
            ).conclusion
            == Species.mammal
        )
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.bird)
            ).conclusion
            == Species.bird
        )
        assert (
            classify_case(
                query, animal, animal.species, zoo.first(Species.fish)
            ).conclusion
            == Species.fish
        )

    def test_clone_expression_does_not_corrupt_original_parents(self):
        """
        Cloning an expression for a new position leaves the original's ``_parents_``
        untouched.
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

        # Clone via _node_for_new_position_() — the path that used to corrupt.
        clone = condition._node_for_new_position_()

        # The original must be untouched.
        assert condition._parent__ is orig_parent
        assert condition._parents_ == orig_parents_before
        # Clone must have its own independent lists and no parent.
        assert clone._parent__ is None
        assert len(clone._parents_) == 0
        assert len(clone._children_) == 0
        assert clone._parents_ is not condition._parents_
        assert clone._children_ is not condition._children_

    def test_shared_anchor_refinement_does_not_corrupt_sibling_alternative(self):
        """
        A refinement inserted at an anchor that also appears inside a sibling
        alternative's condition leaves that condition intact.
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

        # Rule 3: backbone == False → molusc (alternative at the conditions root),
        # built on the same backbone variable the refinement anchors on.
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
        assert molusc_condition.left is backbone_anchor
        # A ConclusionSelector as the left child would mean the splice went in above
        # the anchor rather than beside it.
        assert not isinstance(molusc_condition.left, ConclusionSelector)

        # The molusc case (backbone=False) must still classify as molusc.
        molusc_case = make_animal("test_molusc", backbone=False, eggs=True)
        assert (
            classify_case(query, animal, animal.species, molusc_case).conclusion
            == Species.molusc
        )

        # The reptile refinement (not_eggs at backbone) must fire for a case with
        # backbone=True and eggs=False.
        reptile_case = make_animal("test_reptile", backbone=True, eggs=False)
        assert (
            classify_case(query, animal, animal.species, reptile_case).conclusion
            == Species.reptile
        )

    def test_insert_at_with_anchor_as_condition_raises(self):
        """
        Regression: insert_at(anchor, anchor) must raise SelfReferentialInsertionError
        before touching the tree, not silently create Refinement(backbone, backbone).
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone)
        with query:
            add(animal.species, Species.mammal)
        query.build()
        backbone = query._conditions_root_

        original_conclusions = set(backbone._conclusions_)

        with pytest.raises(SelfReferentialInsertionError):
            insert_refinement(backbone, backbone, animal.species, Species.reptile)

        # Tree must be untouched: backbone's conclusions must not have grown.
        assert backbone._conclusions_ == original_conclusions

    def test_clone_expression_resets_conclusions(self):
        """
        Regression: _node_for_new_position_() must reset _conclusions_ so cloned nodes
        do not share the original's conclusion set.
        """
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone)
        with query:
            add(animal.species, Species.mammal)
        query.build()
        backbone = query._conditions_root_

        # Give backbone a conclusion (it already has one from the query).
        assert len(backbone._conclusions_) > 0

        # Clone a non-MappedVariable expression that has a conclusion attached.
        not_eggs = not_(animal.eggs)
        insert_refinement(backbone, not_eggs, animal.species, Species.reptile)
        # not_eggs now has a parent and no direct conclusions, but we test the set isolation.
        clone = not_eggs._node_for_new_position_()

        assert clone._conclusions_ is not not_eggs._conclusions_
        assert len(clone._conclusions_) == 0


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestBareAttributeWhereCondition:
    """
    Alternatives and refinements added when the ``where`` condition is a bare attribute
    rather than a comparison.
    """

    def test_alternative_with_bare_attr_where_condition(self):
        """
        DSL: where(backbone) then alternative(backbone == False) must connect to Where.
        """
        animal_var = variable(Animal, domain=[])
        query = entity(animal_var).where(animal_var.backbone)
        with query:
            add(animal_var.species, Species.mammal)
            with alternative(animal_var.backbone == False):
                add(animal_var.species, Species.molusc)
        query.build()

        where_node = next(
            (
                expression
                for expression in query._root_._all_expressions_
                if isinstance(expression, Where)
            ),
            None,
        )
        assert where_node is not None
        assert isinstance(where_node.condition, Alternative)

        vertebrate = zoo.first(Species.mammal)
        invertebrate = zoo.first(Species.molusc)
        assert (
            classify_case(query, animal_var, animal_var.species, vertebrate).conclusion
            == Species.mammal
        )
        assert (
            classify_case(
                query, animal_var, animal_var.species, invertebrate
            ).conclusion
            == Species.molusc
        )

    def test_refinement_with_bare_attr_where_condition(self):
        """
        A refinement added under a bare-attribute ``where`` condition stays connected to
        that condition.
        """
        animal_var = variable(Animal, domain=[])
        query = entity(animal_var).where(animal_var.backbone)
        with query:
            add(animal_var.species, Species.mammal)
            with refinement(animal_var.backbone == False):
                add(animal_var.species, Species.molusc)
        query.build()

        where_node = next(
            (
                expression
                for expression in query._root_._all_expressions_
                if isinstance(expression, Where)
            ),
            None,
        )
        assert where_node is not None
        assert isinstance(where_node.condition, RefinementClass)
        # The Refinement's left operand must still be the bare backbone MappedVariable
        # (not the Comparator, which the old code would splice in by mistake).
        assert where_node.condition.left is animal_var.backbone

        # backbone=True + (backbone==False is False) → right not yielded → mammal
        vertebrate = zoo.first(Species.mammal)
        assert (
            classify_case(query, animal_var, animal_var.species, vertebrate).conclusion
            == Species.mammal
        )
