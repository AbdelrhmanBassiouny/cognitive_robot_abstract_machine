"""
Integration tests for backward inference on the EQL-RDR rule tree.

:func:`what_do_we_know_about` inspects the rule tree (a live EQL expression DAG) and
returns the sets of conditions that would cause a given conclusion value to fire, as
:class:`SufficientConditionSet` objects inside a :class:`ConclusionKnowledge`.

Exercises this through the full engine (:class:`EQLSingleClassRDR`, the zoo fixture
dataset); see ``test_backward_inference.py`` for the self-contained unit tests that
build rule trees directly from core EQL primitives.
"""

from __future__ import annotations

from typing_extensions import Any, List, Tuple

from krrood.entity_query_language.factories import (
    add,
    alternative,
    entity,
    refinement,
    variable,
)
from krrood.entity_query_language.rdr.backward_inference import (
    SufficientConditionSet,
    ConclusionKnowledge,
    what_do_we_know_about,
    BackwardInferenceIndex,
)
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.rdr.rule_tree_view import format_condition
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rules.conclusion_selector import ConclusionSelector

from .animal import Animal, Species

# %% Fixture helpers


def _flat_tree() -> Tuple[Any, Any, Any]:
    """milk -> mammal ; else feathers -> bird ; else fins -> fish."""
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.milk == True)
    with query:
        add(animal.species, Species.mammal)
        with alternative(animal.feathers == True):
            add(animal.species, Species.bird)
        with alternative(animal.fins == True):
            add(animal.species, Species.fish)
    query.build()
    return animal, query, query._conditions_root_


def _refinement_tree() -> Tuple[Any, Any, Any]:
    """backbone -> fish ; except if milk -> mammal."""
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.backbone == True)
    with query:
        add(animal.species, Species.fish)
        with refinement(animal.milk == True):
            add(animal.species, Species.mammal)
    query.build()
    return animal, query, query._conditions_root_


def _mixed_tree() -> Tuple[Any, Any, Any]:
    """backbone->fish ; refine milk->mammal ; alt feathers->bird on refinement's right."""
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.backbone == True)
    with query:
        add(animal.species, Species.fish)
    query.build()
    ref = insert_refinement(
        query._conditions_root_, animal.milk == True, animal.species, Species.mammal
    )
    insert_alternative(ref, animal.feathers == True, animal.species, Species.bird)
    return animal, query, query._conditions_root_


_COW = Animal(
    name="cow",
    hair=True,
    feathers=False,
    eggs=False,
    milk=True,
    airborne=False,
    aquatic=False,
    predator=False,
    toothed=True,
    backbone=True,
    breathes=True,
    venomous=False,
    fins=False,
    legs=4,
    tail=True,
    domestic=True,
    catsize=True,
    species=None,
)
_EAGLE = Animal(
    name="eagle",
    hair=False,
    feathers=True,
    eggs=True,
    milk=False,
    airborne=True,
    aquatic=False,
    predator=True,
    toothed=True,
    backbone=True,
    breathes=True,
    venomous=False,
    fins=False,
    legs=2,
    tail=True,
    domestic=False,
    catsize=False,
    species=None,
)
_TUNA = Animal(
    name="tuna",
    hair=False,
    feathers=False,
    eggs=True,
    milk=False,
    airborne=False,
    aquatic=True,
    predator=True,
    toothed=True,
    backbone=True,
    breathes=False,
    venomous=False,
    fins=True,
    legs=0,
    tail=True,
    domestic=False,
    catsize=False,
    species=None,
)
_FROG = Animal(
    name="frog",
    hair=False,
    feathers=False,
    eggs=True,
    milk=False,
    airborne=False,
    aquatic=True,
    predator=False,
    toothed=False,
    backbone=False,
    breathes=True,
    venomous=False,
    fins=False,
    legs=4,
    tail=False,
    domestic=False,
    catsize=False,
    species=None,
)


# %% ConclusionKnowledge structure


class TestConclusionKnowledge:
    """Verify the structure of ConclusionKnowledge and SufficientConditionSet.

    Only covers ground test_backward_inference.py's self-contained unit tests cannot
    reach: trees built via the *runtime* insert_refinement()/insert_alternative() API
    (as opposed to static ``with refinement(...):``/``with alternative(...):``
    construction), which goes through a different splicing code path
    (``_node_for_new_position_``).
    """

    def test_mixed_tree_mammal(self):
        _, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.mammal)
        assert knowledge.is_satisfiable()
        assert len(knowledge.sufficient_condition_sets) == 1
        # backbone (guard) + milk (leaf)
        assert len(knowledge.sufficient_condition_sets[0].conditions) == 2
        assert knowledge.sufficient_condition_sets[0].conditions[0].negated is False

    def test_mixed_tree_bird(self):
        _, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.bird)
        assert knowledge.is_satisfiable()
        assert len(knowledge.sufficient_condition_sets) == 1
        conds = knowledge.sufficient_condition_sets[0].conditions
        # backbone (positive guard) + NOT(milk) (alt guard) + feathers (leaf)
        assert len(conds) == 3
        assert conds[0].negated is False  # backbone
        assert conds[1].negated is True  # NOT(milk)

    def test_mixed_tree_fish(self):
        _, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.fish)
        assert knowledge.is_satisfiable()
        assert len(knowledge.sufficient_condition_sets) == 1
        conds = knowledge.sufficient_condition_sets[0].conditions
        # NOT(milk) + NOT(feathers) (flattened from NOT(Alternative(milk, feathers)))
        # + backbone (leaf)
        assert len(conds) == 3
        assert conds[0].negated is True
        assert conds[1].negated is True


# %% evaluate_against correctness


class TestEvaluateAgainst:
    """Verify evaluate_against() returns correct results for concrete cases.

    Only covers the runtime-insertion (_mixed_tree) path; see the class docstring
    of :class:`TestConclusionKnowledge` for why.
    """

    def test_mixed_mammal_true_for_cow(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.mammal)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _COW)
            is True
        )

    def test_mixed_mammal_false_for_eagle(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.mammal)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _EAGLE)
            is False
        )

    def test_mixed_bird_true_for_eagle(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.bird)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _EAGLE)
            is True
        )

    def test_mixed_bird_false_for_cow(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.bird)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _COW)
            is False
        )

    def test_mixed_fish_true_for_tuna(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.fish)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _TUNA)
            is True
        )

    def test_mixed_fish_false_for_cow(self):
        animal, _, root = _mixed_tree()
        knowledge = what_do_we_know_about(root, Species.fish)
        assert (
            knowledge.sufficient_condition_sets[0].evaluate_against(animal, _COW)
            is False
        )


# %% EQLSingleClassRDR integration


class TestRDRIntegration:
    """Verify EQLSingleClassRDR.what_do_we_know_about() -- the thin wrapper actually
    reads the live RDR's own conditions_root, not a manually-built one."""

    def test_rdr_method_empty(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        knowledge = rdr.what_do_we_know_about(Species.molusc)
        assert isinstance(knowledge, ConclusionKnowledge)
        assert not knowledge.is_satisfiable()


# %% Cache invalidation


class TestCacheInvalidation:
    """Verify BackwardInferenceIndex invalidates and rebuilds on demand."""

    def test_index_invalidates_after_refinement(self):
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)
        query.build()

        root = query._conditions_root_

        index = BackwardInferenceIndex()

        # Query before refinement — fish backbone only
        before = index.query(root, Species.fish)
        assert before.is_satisfiable()
        before_count = len(before.sufficient_condition_sets[0].conditions)

        # Insert a refinement
        insert_refinement(root, animal.milk == True, animal.species, Species.mammal)
        index.invalidate()

        # The root now has a parent (Refinement); get the actual new root
        actual_root = query._conditions_root_

        # Query after — fish path should now have one more guard (NOT milk)
        after = index.query(actual_root, Species.fish)
        assert after.is_satisfiable()
        after_count = len(after.sufficient_condition_sets[0].conditions)
        assert after_count > before_count

    def test_index_uncached_query_is_empty_after_mutation(self):
        """After invalidate() and refreshing the root, the index returns the new rule's results."""
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
        query.build()

        root = query._conditions_root_
        index = BackwardInferenceIndex()

        assert index.query(root, Species.mammal).is_satisfiable()
        assert not index.query(root, Species.bird).is_satisfiable()

        insert_alternative(root, animal.feathers == True, animal.species, Species.bird)
        index.invalidate()

        # Now get the actual root (may have changed after insert_alternative)
        actual_root = query._conditions_root_
        assert index.query(actual_root, Species.bird).is_satisfiable()

    def test_invalidates_on_fit_case(self):
        """EQLSingleClassRDR fit_case calls _backward_index.invalidate()."""
        from krrood.entity_query_language.rdr.expert import Expert
        from krrood.entity_query_language.rdr.interface import (
            AnswerRequest,
            CaseContext,
            FunctionInterface,
        )

        def expert_fn(
            ctx: CaseContext, requests: List[AnswerRequest]
        ) -> dict[str, Any]:
            answers: dict[str, Any] = {}
            for req in requests:
                if req.name == "conditions":
                    answers["conditions"] = ctx.case_variable.milk == True
            return answers

        rdr = EQLSingleClassRDR(Animal, "species")
        assert not rdr.what_do_we_know_about(Species.mammal).is_satisfiable()

        expert = Expert(FunctionInterface(expert_fn))
        rdr.fit_case(_COW, Species.mammal, expert)

        assert rdr.what_do_we_know_about(Species.mammal).is_satisfiable()


# %% format_condition handles ConclusionSelector guards


class TestGuardFlattening:
    """ConclusionSelector guard expressions are flattened to leaf conditions.

    The _collect_rule_paths traversal decomposes Alternative/Refinement nodes
    into their constituent conditions so guards are precise and human-readable:
    NOT(Alternative(A,B)) → NOT(A), NOT(B); Refinement(A,B) → A.
    """

    def test_no_guard_is_ever_a_conclusion_selector(self):
        """No guard expression in any test tree is a ConclusionSelector."""
        for _, _, root in [_flat_tree(), _refinement_tree(), _mixed_tree()]:
            for value in (Species.mammal, Species.bird, Species.fish):
                knowledge = what_do_we_know_about(root, value)
                for scs in knowledge.sufficient_condition_sets:
                    for gc in scs.conditions:
                        assert not isinstance(gc.expression, ConclusionSelector), (
                            f"Guard for {value} in {_tree_name(root)}"
                            f" is unflattened: {gc.expression}"
                        )

    def test_flattened_guards_are_readable(self):
        """format_condition on flattened guards never shows dataclass fields."""
        _, _, root = _flat_tree()
        knowledge = what_do_we_know_about(root, Species.fish)
        for scs in knowledge.sufficient_condition_sets:
            for gc in scs.conditions:
                rendered = format_condition(gc.expression)
                assert "_conclusions_=" not in rendered
                assert "right_yielded" not in rendered

    def test_no_guard_is_ever_a_conclusion_selector_deeply_nested_alternative(self):
        """Even deeply nested Alternative trees produce leaf-only guard expressions."""
        animal = variable(Animal, domain=[])
        # Build: backbone → fish ; alternative(milk → mammal) ; alternative(feathers → bird)
        # Tests Alternative(Alternative(A, B), C) guard decomposition.
        query = entity(animal).where(animal.backbone == True)
        with query:
            add(animal.species, Species.fish)
            with alternative(animal.milk == True):
                add(animal.species, Species.mammal)
            with alternative(animal.feathers == True):
                add(animal.species, Species.bird)
        query.build()

        # backbone-fish should have two guard paths: NOT(milk) AND NOT(feathers)
        for value in (Species.fish, Species.mammal, Species.bird):
            knowledge = what_do_we_know_about(query._conditions_root_, value)
            for scs in knowledge.sufficient_condition_sets:
                for gc in scs.conditions:
                    assert not isinstance(
                        gc.expression, ConclusionSelector
                    ), f"Guard for {value} is unflattened: {gc.expression}"


def _tree_name(root):
    """Helper to identify which test tree we're in."""
    return getattr(root, "_name_", str(type(root).__name__))


# %% is_satisfiable edge cases


class TestIsSatisfiable:
    """Edge cases for the is_satisfiable property."""

    def test_with_empty_condition_set(self):
        knowledge = ConclusionKnowledge(
            Species.molusc,
            (SufficientConditionSet(()),),
        )
        assert knowledge.is_satisfiable()

    def test_evaluate_empty_condition_set(self):
        """A SufficientConditionSet with no conditions is vacuously true."""
        animal = variable(Animal, domain=[])
        cond_set = SufficientConditionSet(())
        assert cond_set.evaluate_against(animal, _COW) is True


