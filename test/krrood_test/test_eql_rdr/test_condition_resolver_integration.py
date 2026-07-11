"""
Integration tests for the auto-condition resolution system (``condition_resolver.py``):
``ResolvedCondition``, ``ConditionResolver`` ABC, ``ChainConditionResolver``,
and the two concrete strategy resolvers.

Each test class pins exactly one contract; each test method verifies one
observable guarantee. Exercises this through the full engine (:class:`EQLSingleClassRDR`,
:class:`Expert`, the zoo fixture dataset); see ``test_condition_resolver.py`` for the
self-contained unit tests built against hand-constructed knowledge fixtures.
"""

from __future__ import annotations

import dataclasses

import pytest
from typing_extensions import Any, Optional, Type

from .animal import Animal, Species, make_animal
from krrood.entity_query_language.core.base_expressions import OperationResult
from krrood.entity_query_language.factories import add, alternative, entity, variable
from krrood.entity_query_language.rdr.backward_inference import (
    ConclusionKnowledge,
    GuardCondition,
    SufficientConditionSet,
    what_do_we_know_about,
)
from krrood.entity_query_language.rdr.condition_resolver import (
    ChainConditionResolver,
    ConditionResolver,
    CornerCaseKnowledgeResolver,
    ResolvedCondition,
    ResolutionMode,
    TargetKnowledgeResolver,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.rule_tree import (
    insert_refinement,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rules.conclusion_selector import ConclusionSelector

# ---------------------------------------------------------------------------
# Minimal stub helpers — named after the pattern they exercise, not "Mock"
# ---------------------------------------------------------------------------

# A sentinel SymbolicExpression stand-in.  The resolver tests do not execute
# EQL expressions; they only inspect the *returned object*.  Using a plain
# sentinel avoids pulling in the full EQL machinery for structural tests.
_SENTINEL_EXPR = object()


class _AlwaysNoneResolver(ConditionResolver):
    """A resolver that never succeeds — always returns None."""

    def resolve(self, *args: Any, **kwargs: Any) -> Optional[ResolvedCondition]:
        return None


class _AlwaysSucceedingResolver(ConditionResolver):
    """Stub base: always returns a ResolvedCondition reporting its own concrete class."""

    def __init__(self) -> None:
        self.call_count = 0

    def resolve(self, *args: Any, **kwargs: Any) -> Optional[ResolvedCondition]:
        self.call_count += 1
        return ResolvedCondition(_SENTINEL_EXPR, type(self))


class _AlwaysTargetResolver(_AlwaysSucceedingResolver):
    """Stub whose class identity represents the target-knowledge resolver in chain tests."""


class _AlwaysCornerResolver(_AlwaysSucceedingResolver):
    """Stub whose class identity represents the corner-case-knowledge resolver in chain tests."""


# Convenience: call a resolver / chain with dummy arguments.
_DUMMY_ARGS = (None, None, None, None, None, None, None)


# ---------------------------------------------------------------------------
# ResolvedCondition dataclass
# ---------------------------------------------------------------------------


class TestResolvedCondition:
    """ResolvedCondition is a frozen dataclass with expression and resolver_type fields.

    Basic field-storage coverage lives in test_condition_resolver.py's
    self-contained test_resolved_condition_carries_expression_and_resolver_type;
    this class covers the frozen/equality dataclass mechanics that mocked test
    does not.
    """

    def test_is_frozen_expression_field(self):
        """Mutating the expression field of a ResolvedCondition raises an error.

        Guarantee: frozen=True is in effect — callers cannot accidentally overwrite
        a resolved condition's expression after creation.
        """
        rc = ResolvedCondition(_SENTINEL_EXPR, TargetKnowledgeResolver)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            rc.expression = object()  # type: ignore[misc]

    def test_is_frozen_resolver_type_field(self):
        """Mutating the resolver_type field of a ResolvedCondition raises an error.

        Guarantee: frozen=True applies to every field, not just expression.
        """
        rc = ResolvedCondition(_SENTINEL_EXPR, TargetKnowledgeResolver)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            rc.resolver_type = CornerCaseKnowledgeResolver  # type: ignore[misc]

    def test_equality_based_on_field_values(self):
        """Two ResolvedConditions with the same fields compare as equal.

        Guarantee: frozen dataclass equality semantics are in place (structural equality).
        """
        expr = object()
        rc1 = ResolvedCondition(expr, TargetKnowledgeResolver)
        rc2 = ResolvedCondition(expr, TargetKnowledgeResolver)
        assert rc1 == rc2

    def test_inequality_on_different_resolver_type(self):
        """Two ResolvedConditions with different resolver types are not equal.

        Guarantee: resolver_type is part of the equality contract.
        """
        rc1 = ResolvedCondition(_SENTINEL_EXPR, TargetKnowledgeResolver)
        rc2 = ResolvedCondition(_SENTINEL_EXPR, CornerCaseKnowledgeResolver)
        assert rc1 != rc2


# ---------------------------------------------------------------------------
# ChainConditionResolver structural tests
# ---------------------------------------------------------------------------


class TestChainConditionResolver:
    """ChainConditionResolver implements chain-of-responsibility correctly.

    Basic fall-through/short-circuit/default-ordering coverage lives in
    test_condition_resolver.py's self-contained ChainConditionResolver tests;
    this class keeps only the call-count and structural-edge-case guarantees
    those do not exercise.
    """

    def test_short_circuits_when_first_resolver_returns_non_none(self):
        """When the first resolver returns a result, the second is never called.

        Guarantee: chain short-circuits at the first non-None result — O(1) in
        the best case and prevents unexpected side effects from later resolvers.
        """
        first = _AlwaysTargetResolver()
        second = _AlwaysCornerResolver()
        chain = ChainConditionResolver([first, second])

        result = chain.resolve(*_DUMMY_ARGS)

        assert result is not None
        assert result.resolver_type is _AlwaysTargetResolver
        assert second.call_count == 0

    def test_empty_chain_returns_none(self):
        """A chain with no resolvers returns None without error.

        Guarantee: zero-length resolver list is a valid (though degenerate) configuration.
        """
        chain = ChainConditionResolver([])

        result = chain.resolve(*_DUMMY_ARGS)

        assert result is None

    def test_backward_inference_default_returns_chain_condition_resolver(self):
        """backward_inference_default() produces a ChainConditionResolver instance.

        Guarantee: the factory method returns the correct type for downstream isinstance
        checks and duck-typing.
        """
        result = ChainConditionResolver.backward_inference_default()

        assert isinstance(result, ChainConditionResolver)

    def test_all_resolvers_are_tried_when_none_succeed(self):
        """Every resolver is invoked when none of them return a result.

        Guarantee: the chain does not bail out early on None — it exhausts all options
        before giving up.
        """
        first = _AlwaysTargetResolver()
        second = _AlwaysCornerResolver()

        # Wrap each in a counting None-always resolver to observe call counts.
        class _CountingNone(ConditionResolver):
            def __init__(self) -> None:
                self.call_count = 0

            def resolve(self, *args: Any, **kwargs: Any) -> Optional[ResolvedCondition]:
                self.call_count += 1
                return None

        counting_resolver_1 = _CountingNone()
        counting_resolver_2 = _CountingNone()
        counting_resolver_3 = _CountingNone()
        chain = ChainConditionResolver(
            [counting_resolver_1, counting_resolver_2, counting_resolver_3]
        )
        chain.resolve(*_DUMMY_ARGS)

        assert counting_resolver_1.call_count == 1
        assert counting_resolver_2.call_count == 1
        assert counting_resolver_3.call_count == 1


# ---------------------------------------------------------------------------
# ConditionResolver ABC contract
# ---------------------------------------------------------------------------


class TestConditionResolverABC:
    """ConditionResolver is an abstract base class that cannot be instantiated directly."""

    def test_cannot_instantiate_abstract_resolver(self):
        """Instantiating ConditionResolver directly must raise TypeError.

        Guarantee: the ABC contract is enforced — concrete subclasses must implement
        resolve() or they cannot be constructed.
        """
        with pytest.raises(TypeError):
            ConditionResolver()  # type: ignore[abstract]

    def test_concrete_subclass_without_resolve_cannot_instantiate(self):
        """A subclass that does not implement resolve() also raises TypeError.

        Guarantee: the @abstractmethod decorator is not accidentally omitted or
        bypassed by a partial implementation.
        """

        class _IncompleteResolver(ConditionResolver):
            pass  # resolve() not implemented

        with pytest.raises(TypeError):
            _IncompleteResolver()  # type: ignore[abstract]

    def test_concrete_subclass_with_resolve_can_instantiate(self):
        """A subclass that implements resolve() can be constructed without error.

        Guarantee: the ABC permits any concrete implementation, not just the two
        built-in strategies.
        """
        # _AlwaysNoneResolver implements resolve(); construction must succeed.
        resolver = _AlwaysNoneResolver()
        assert isinstance(resolver, ConditionResolver)


# ---------------------------------------------------------------------------
# Animal helpers shared by TestTargetKnowledgeResolver
# ---------------------------------------------------------------------------


def _make_mammal(**overrides) -> Animal:
    """Return a canonical mammal (milk-bearing, no feathers)."""
    defaults = dict(
        name="test_mammal",
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
        domestic=False,
        catsize=True,
    )
    defaults.update(overrides)
    return Animal(**defaults)


def _make_bird(**overrides) -> Animal:
    """Return a canonical bird (feathers, no milk)."""
    defaults = dict(
        name="test_bird",
        hair=False,
        feathers=True,
        eggs=True,
        milk=False,
        airborne=True,
        aquatic=False,
        predator=False,
        toothed=False,
        backbone=True,
        breathes=True,
        venomous=False,
        fins=False,
        legs=2,
        tail=True,
        domestic=False,
        catsize=False,
    )
    defaults.update(overrides)
    return Animal(**defaults)


def _two_rule_rdr():
    """Build a minimal RDR with exactly two rules:

    Rule 1 (root):      milk == True  → mammal
    Rule 2 (alternative): feathers == True → bird

    Returns ``(rdr, mammal_case, bird_case)`` where each case is the concrete
    ``Animal`` that was used to fit the rule.
    """
    mammal = _make_mammal()
    bird = _make_bird()

    rdr = EQLSingleClassRDR(Animal, "species")

    def answer(context, _requests):
        v = context.case_variable
        target = context.target_conclusion
        if target is Species.mammal:
            return {"conditions": v.milk == True}
        return {"conditions": v.feathers == True}

    expert = Expert(interface=FunctionInterface(answer_fn=answer))
    rdr.fit_case(mammal, Species.mammal, expert)
    rdr.fit_case(bird, Species.bird, expert)
    return rdr, mammal, bird


# ---------------------------------------------------------------------------
# TestTargetKnowledgeResolver — live animal-fixture discrimination tests
# ---------------------------------------------------------------------------


class TestTargetKnowledgeResolver:
    """TargetKnowledgeResolver correctly discriminates using backward-inference knowledge.

    The fixture uses a two-rule animal RDR:
      - Rule 1: milk == True → mammal
      - Rule 2: feathers == True → bird   (alternative)

    Each test exercises one logical path through TargetKnowledgeResolver.resolve().

    Basic discrimination and no-known-paths coverage lives in
    test_condition_resolver.py's self-contained TargetKnowledgeResolver tests;
    this class keeps only the live-evaluation and negated-guard guarantees
    those do not exercise.
    """

    def test_resolved_expression_evaluates_true_for_new_case(self):
        """The resolved expression is True when evaluated against the new case.

        Guarantee: _materialize(guard) produces an expression that correctly
        identifies the new (target) case — not the corner case.
        """
        rdr, mammal, _bird = _two_rule_rdr()
        bird2 = _make_bird(name="bird2")

        bird_knowledge = rdr.what_do_we_know_about(Species.bird)
        mammal_knowledge = rdr.what_do_we_know_about(Species.mammal)

        resolver = TargetKnowledgeResolver()
        result = resolver.resolve(
            bird2,
            rdr.case_variable,
            Species.bird,
            Species.mammal,
            mammal,
            bird_knowledge,
            mammal_knowledge,
        )

        assert result is not None
        # Evaluate the resolved expression against the new bird case.
        assert _eval_expr(result.expression, rdr.case_variable, bird2) is True

    def test_resolved_expression_evaluates_false_for_corner_case(self):
        """The resolved expression is False when evaluated against the corner case.

        Guarantee: the discriminating guard fails for the corner case — confirming
        that the condition truly separates new case from corner case.
        """
        rdr, mammal, _bird = _two_rule_rdr()
        bird2 = _make_bird(name="bird2")

        bird_knowledge = rdr.what_do_we_know_about(Species.bird)
        mammal_knowledge = rdr.what_do_we_know_about(Species.mammal)

        resolver = TargetKnowledgeResolver()
        result = resolver.resolve(
            bird2,
            rdr.case_variable,
            Species.bird,
            Species.mammal,
            mammal,
            bird_knowledge,
            mammal_knowledge,
        )

        assert result is not None
        # Evaluate the resolved expression against the corner case (mammal).
        assert _eval_expr(result.expression, rdr.case_variable, mammal) is False

    def test_handles_negated_guard_materialize_wraps_with_not(self):
        """_materialize produces not_(expr) for a negated guard, yielding a correct expression.

        Guarantee: when a discriminating guard in the tree has ``negated=True``
        (meaning the rule fires when the expression is False), _materialize wraps
        it with not_() — so the resulting expression evaluates to True when the
        original expression is False, and False when it is True.

        Scenario: We build a tree where the bird path has a negated guard:
          backbone->fish; refine milk==True->mammal; alt NOT(milk)==True->bird is
          equivalent to the Alternative path where the guard for the second branch
          is NOT(milk==True).  We use the flat_tree pattern from test_backward_inference
          where the bird path's first guard is negated (NOT milk==True).

        We use the flat-tree structure directly: mammal (milk), bird (NOT milk + feathers).
        The bird SCS has its first guard negated=True.  We feed that knowledge into the
        resolver with a case that has milk=False (passes NOT milk) and a corner case
        that has milk=True (fails NOT milk) — so the negated guard discriminates.
        """
        animal_var = variable(Animal, domain=[])
        query = entity(animal_var).where(animal_var.milk == True)
        with query:
            add(animal_var.species, Species.mammal)
            with alternative(animal_var.feathers == True):
                add(animal_var.species, Species.bird)
        query.build()

        root = query._conditions_root_
        bird_knowledge = what_do_we_know_about(root, Species.bird)
        mammal_knowledge = what_do_we_know_about(root, Species.mammal)

        # Confirm the first guard in the bird SCS is negated (NOT milk==True).
        bird_scs = bird_knowledge.sufficient_condition_sets[0]
        assert (
            bird_scs.conditions[0].negated is True
        ), "Test pre-condition: bird path first guard must be negated"

        # New case: a bird (feathers=True, milk=False) — passes NOT(milk) guard.
        bird_new = _make_bird(name="negated_test_bird")
        # Corner case: a mammal (milk=True) — fails NOT(milk) guard.
        mammal_corner = _make_mammal(name="negated_test_mammal")

        resolver = TargetKnowledgeResolver()
        result = resolver.resolve(
            bird_new,
            animal_var,
            Species.bird,
            Species.mammal,
            mammal_corner,
            bird_knowledge,
            mammal_knowledge,
        )

        assert (
            result is not None
        ), "Resolver must find the negated guard as discriminating"
        assert result.resolver_type is TargetKnowledgeResolver

        # The materialized expression is not_(milk==True), i.e. milk==False.
        # Evaluate it against the new bird (milk=False) → should be True.
        assert _eval_expr(result.expression, animal_var, bird_new) is True

        # Evaluate against the corner mammal (milk=True) → should be False.
        assert _eval_expr(result.expression, animal_var, mammal_corner) is False


# ---------------------------------------------------------------------------
# TestCornerCaseKnowledgeResolver — positive-condition, non-active-path semantics tests
#
# The algorithm searches non-active paths to the wrong conclusion for a
# POSITIVE guard (no negation) that holds for the new case and does not hold
# for the corner case.  The active path is the sufficient condition set whose
# guard expression is identical (by identity) to firing_anchor.
#
# Strategy: synthesize ConclusionKnowledge directly with two SufficientConditionSets
# built from live EQL variable expressions so GuardCondition.holds_for() evaluates
# correctly.
#   Active path:     fins == True   (guard expression serves as firing_anchor)
#   Non-active path: aquatic == True (the search target)
# ---------------------------------------------------------------------------


def _two_path_wrong_knowledge():
    """Build live ConclusionKnowledge with two independent sufficient condition sets for Species.fish.

    Active path (fins guard):     fins == True   (negated=False)
    Non-active path (aquatic guard): aquatic == True (negated=False)

    Returns ``(case_variable, fins_expr, aquatic_expr, current_knowledge)`` so
    callers can supply ``fins_expr`` as ``firing_anchor`` to mark the fins-guard path
    as active and leave the aquatic-guard path as the search target.

    Named pattern: TwoPathWrongKnowledge — a minimal two-path ConclusionKnowledge
    fixture that provides the resolver exactly one non-active path to search.
    """

    case_variable = variable(Animal, domain=[])
    fins_expr = case_variable.fins == True  # noqa: E712
    aquatic_expr = case_variable.aquatic == True  # noqa: E712

    scs_active = SufficientConditionSet(
        conditions=(GuardCondition(fins_expr, negated=False),)
    )
    scs_non_active = SufficientConditionSet(
        conditions=(GuardCondition(aquatic_expr, negated=False),)
    )
    current_knowledge = ConclusionKnowledge(
        conclusion_value=Species.fish,
        sufficient_condition_sets=(scs_active, scs_non_active),
    )
    return case_variable, fins_expr, aquatic_expr, current_knowledge


def _eval_expr(expr, case_variable, case):
    """Evaluate a live EQL expression against *case*, returning a bool.

    Binds *case_variable* to [*case*] then collects all OperationResult/bool values
    from expr.evaluate(), returning True only when at least one is true.
    """
    case_variable._update_domain_([case])
    results = list(expr.evaluate())
    return any(
        r.is_true if isinstance(r, OperationResult) else bool(r) for r in results
    )


class TestCornerCaseKnowledgeResolver:
    """CornerCaseKnowledgeResolver finds a positive discriminating condition from
    a non-active path to the wrong conclusion, without applying negation.

    Basic discrimination and active-path-exclusion coverage lives in
    test_condition_resolver.py's self-contained CornerCaseKnowledgeResolver tests;
    this class keeps only the white-box (_active_path) and structural-edge-case
    guarantees those do not exercise.
    """

    def test_active_path_identified_by_firing_anchor(self):
        """_active_path() returns the sufficient condition set whose guard expression is firing_anchor.

        Guarantee: identity comparison on guard.expression selects precisely the sufficient
        condition set that contains the firing anchor and excludes the sibling set.

        The fins-guard path contains fins_expr as its guard.expression; the aquatic-guard path
        contains aquatic_expr.  _active_path(fins_expr, ...) must return the fins-guard path
        and not the aquatic-guard path.
        """
        case_variable, fins_expr, _aquatic_expr, current_knowledge = (
            _two_path_wrong_knowledge()
        )
        scs_fins = current_knowledge.sufficient_condition_sets[0]
        scs_aquatic = current_knowledge.sufficient_condition_sets[1]

        resolver = CornerCaseKnowledgeResolver()
        active = resolver._active_path(fins_expr, current_knowledge)

        assert active is scs_fins
        assert active is not scs_aquatic

    def test_returns_none_when_no_sufficient_condition_sets(self):
        """Resolver returns None immediately when current_knowledge has no condition sets.

        Guarantee: an empty ConclusionKnowledge causes the outer loop to be a no-op
        and the resolver returns None without error — no AttributeError or crash.
        """
        case_variable = variable(Animal, domain=[])

        empty_current = ConclusionKnowledge(Species.fish, ())
        empty_target = ConclusionKnowledge(Species.bird, ())

        case = _make_mammal(name="some_case", fins=False, aquatic=True)
        corner_case = _make_mammal(name="some_corner", fins=True, aquatic=False)

        resolver = CornerCaseKnowledgeResolver()
        result = resolver.resolve(
            case=case,
            case_variable=case_variable,
            target_conclusion=Species.bird,
            current_conclusion=Species.fish,
            corner_case=corner_case,
            target_knowledge=empty_target,
            current_knowledge=empty_current,
            firing_anchor=None,
        )

        assert result is None

    def test_returns_none_when_only_active_path_exists(self):
        """Resolver returns None when the only sufficient condition set is the active path.

        Guarantee: with a single sufficient condition set that is excluded as the active path,
        the non-active loop body never executes and the result is None.
        """
        case_variable = variable(Animal, domain=[])
        fins_expr = case_variable.fins == True  # noqa: E712

        scs_only = SufficientConditionSet(
            conditions=(GuardCondition(fins_expr, negated=False),)
        )
        current_knowledge = ConclusionKnowledge(
            conclusion_value=Species.fish,
            sufficient_condition_sets=(scs_only,),
        )
        empty_target = ConclusionKnowledge(Species.bird, ())

        # case has fins=True so the guard would discriminate if it were searched
        case = _make_mammal(name="fins_case", fins=True, aquatic=False)
        corner_case = _make_mammal(name="no_fins_corner", fins=False, aquatic=False)

        resolver = CornerCaseKnowledgeResolver()
        result = resolver.resolve(
            case=case,
            case_variable=case_variable,
            target_conclusion=Species.bird,
            current_conclusion=Species.fish,
            corner_case=corner_case,
            target_knowledge=empty_target,
            current_knowledge=current_knowledge,
            firing_anchor=fins_expr,  # marks the only SCS as active
        )

        assert result is None

    def test_no_negation_applied_to_returned_expression(self):
        """The returned expression is the raw guard expression — not wrapped in not_().

        Guarantee: _materialize(guard) for a non-negated guard returns guard.expression
        directly.  The resolved expression evaluates True for case (positive condition),
        confirming no negation wrapper was applied.

        Scenario: non-active guard is aquatic==True; case has aquatic=True;
        the resolved expression must evaluate True for case (confirming it is positive).
        """
        case_variable, fins_expr, _aquatic_expr, current_knowledge = (
            _two_path_wrong_knowledge()
        )

        case = _make_mammal(name="aquatic_case", fins=False, aquatic=True)
        corner_case = _make_mammal(name="fins_corner", fins=True, aquatic=False)

        empty_target = ConclusionKnowledge(Species.bird, ())
        resolver = CornerCaseKnowledgeResolver()

        result = resolver.resolve(
            case=case,
            case_variable=case_variable,
            target_conclusion=Species.bird,
            current_conclusion=Species.fish,
            corner_case=corner_case,
            target_knowledge=empty_target,
            current_knowledge=current_knowledge,
            firing_anchor=fins_expr,
        )

        assert result is not None
        # The expression must evaluate True for case (aquatic=True) — positive, not negated.
        truth_for_case = _eval_expr(result.expression, case_variable, case)
        assert truth_for_case is True


# ---------------------------------------------------------------------------
# TestResolverWithAlternativeGuard
# (Test 5: resolver must never return a ConclusionSelector expression)
# ---------------------------------------------------------------------------


def _alt_refinement_tree_for_resolver():
    """Build ``Refinement(Alternative(milk->mammal, feathers->bird), fins->fish)``.

    This is the minimal tree whose ``Refinement`` right-path guard is a positive
    ``Alternative``, making it the smallest tree that exercises the resolver's
    interaction with the ``_positive_guards_dnf`` expansion.

    Returns ``(animal_variable, conditions_root)``.
    """
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.milk == True)
    with query:
        add(animal.species, Species.mammal)
        with alternative(animal.feathers == True):
            add(animal.species, Species.bird)
    query.build()
    insert_refinement(
        query._conditions_root_,
        animal.fins == True,
        animal.species,
        Species.fish,
    )
    return animal, query._conditions_root_


class TestResolverWithAlternativeGuard:
    """TargetKnowledgeResolver must never return a ConclusionSelector as its expression.

    When ``_positive_guards_dnf`` expands a positive ``Alternative`` into plain-comparator
    conjunctions, no ``ConclusionSelector`` node ever appears as a guard expression in the
    ``SufficientConditionSet``, so the resolver can never select and return one.
    """

    def test_resolver_never_returns_conclusion_selector_expression(self):
        """TargetKnowledgeResolver.resolve returns None or a non-ConclusionSelector expression.

        Guarantee: the ``expression`` field of any ``ResolvedCondition`` returned by
        ``TargetKnowledgeResolver`` is never an instance of ``ConclusionSelector``.
        Inserting a ``ConclusionSelector`` as a rule condition creates a DAG cycle and
        produces increasingly nested suggestions — it must never happen.

        Scenario:
          Tree:  Refinement(Alternative(milk->mammal, feathers->bird), fins->fish)
          new case:    milk=True,  feathers=False, fins=True
          corner_case: milk=False, feathers=False, fins=True
        """
        animal, root = _alt_refinement_tree_for_resolver()

        fish_knowledge = what_do_we_know_about(root, Species.fish)
        mammal_knowledge = what_do_we_know_about(root, Species.mammal)

        # new case: milk=True (Alternative fires), fins=True (refinement fires)
        new_case = _make_mammal(
            name="milk_and_fins", milk=True, feathers=False, fins=True
        )
        # corner case: milk=False, feathers=False (Alternative does NOT fire), fins=True
        corner_case = _make_mammal(
            name="no_milk_no_feathers", milk=False, feathers=False, fins=True
        )

        resolver = TargetKnowledgeResolver()
        result = resolver.resolve(
            new_case,
            animal,
            Species.fish,
            Species.mammal,
            corner_case,
            fish_knowledge,
            mammal_knowledge,
        )

        # The result is either None (no discrimination found — acceptable after fix)
        # or a ResolvedCondition whose expression is NOT a ConclusionSelector.
        if result is not None:
            assert not isinstance(result.expression, ConclusionSelector), (
                f"Resolver must not return a ConclusionSelector expression; "
                f"got {type(result.expression).__name__}: {result.expression!r}"
            )


class TestSharedAnchorDoesNotCorruptSiblingCondition:
    """Regression test for the shared-MappedVariable anchor corruption bug.

    Scenario that triggered the bug during interactive zoo fitting:

      1. ``backbone`` → mammal           (first rule, backbone is conditions root)
      2. ``eggs``     → fish             (refinement at backbone)
      3. ``backbone == False`` → molusc  (alternative — SAME backbone singleton in Comparator)
      4. ``venomous`` → reptile          (refinement at eggs)
      5. Fit a reptile case where backbone fires (eggs=False):
         TargetKnowledgeResolver finds ``venomous`` from reptile knowledge and calls
         ``insert_refinement(backbone_anchor, venomous, ..., reptile)``.
         Before the fix: ``backbone._parent_`` pointed to the molusc Comparator, so
         ``_replace_child_`` corrupted it to ``(backbone except if venomous) == False``.
         After the fix: ``insert_at`` scans ``backbone._parents_`` for the most recent
         ConclusionSelector and uses the correct Refinement instead.
    """

    def test_target_knowledge_resolver_does_not_corrupt_sibling_condition_after_insertion(
        self,
    ):
        """Inserting a resolver-suggested condition at a shared anchor must not
        corrupt the sibling alternative condition that also uses that anchor.

        Guarantee: after TargetKnowledgeResolver inserts a refinement at the
        backbone anchor, ``what_do_we_know_about(molusc)`` must contain no
        ConclusionSelector guard expressions, and molusc cases must still
        classify correctly.
        """
        mammal_case = make_animal("mammal", backbone=True, eggs=False, venomous=False, milk=True)
        fish_case = make_animal("fish", backbone=True, eggs=True, fins=True, venomous=False)
        molusc_case = make_animal("molusc", backbone=False, eggs=True)
        reptile_via_eggs = make_animal("reptile_eggs", backbone=True, eggs=True, venomous=True)
        # backbone=True, eggs=False: backbone fires (mammal), target=reptile → resolver triggers
        reptile_no_eggs = make_animal("reptile_no_eggs", backbone=True, eggs=False, venomous=True)

        conditions_map = {
            Species.mammal: lambda v: v.backbone,
            Species.fish: lambda v: v.eggs,
            Species.molusc: lambda v: v.backbone == False,
            Species.reptile: lambda v: v.venomous,
        }

        def answer(context, _requests):
            fn = conditions_map[context.target_conclusion]
            return {"conditions": fn(context.case_variable)}

        resolver = ChainConditionResolver.backward_inference_default()
        rdr = EQLSingleClassRDR(
            Animal,
            "species",
            condition_resolver=resolver,
            resolution_mode=ResolutionMode.SILENT,
        )
        expert = Expert(interface=FunctionInterface(answer_fn=answer))

        # Steps 1–4: build the base tree via explicit expert answers.
        rdr.fit_case(mammal_case, Species.mammal, expert)   # backbone → mammal
        rdr.fit_case(fish_case, Species.fish, expert)       # eggs → fish (refinement at backbone)
        rdr.fit_case(molusc_case, Species.molusc, expert)  # backbone==False → molusc (alternative)
        rdr.fit_case(reptile_via_eggs, Species.reptile, expert)  # venomous → reptile (refinement at eggs)

        # Step 5: backbone fires for reptile_no_eggs (eggs=False, so eggs rule doesn't apply).
        # TargetKnowledgeResolver finds 'venomous' from reptile backward-inference knowledge
        # (holds for reptile_no_eggs, not for the mammal corner case) and calls
        # insert_refinement(backbone_anchor, venomous_clone, ..., reptile).
        # This is the insertion that previously corrupted the molusc condition.
        rdr.fit_case(reptile_no_eggs, Species.reptile, expert)

        # --- Invariant 1: no ConclusionSelector embedded in molusc backward-inference ---
        molusc_knowledge = rdr.what_do_we_know_about(Species.molusc)
        assert molusc_knowledge.is_satisfiable(), "molusc knowledge must be satisfiable"
        for scs in molusc_knowledge.sufficient_condition_sets:
            for guard in scs.conditions:
                assert not isinstance(guard.expression, ConclusionSelector), (
                    f"molusc guard expression must not be a ConclusionSelector; "
                    f"got {type(guard.expression).__name__}: {guard.expression!r}"
                )

        # --- Invariant 2: molusc case is still classified correctly ---
        assert rdr.classify(molusc_case) is Species.molusc, (
            "molusc case must still classify as molusc after the backbone refinement"
        )

        # --- Invariant 3: the resolver-triggered reptile rule fires correctly ---
        assert rdr.classify(reptile_no_eggs) is Species.reptile, (
            "reptile case must now classify as reptile"
        )
