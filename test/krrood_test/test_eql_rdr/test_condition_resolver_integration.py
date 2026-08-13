"""
Tests for automatic condition resolution driven through the live engine.

``test_condition_resolver.py`` covers each resolver against hand-built knowledge
fixtures. What only the engine can show is that the expression a resolver picks out of a
*real* rule tree evaluates the way the resolver claimed, that it is never a conclusion
selector (inserting one would close a cycle in the DAG), and that inserting it leaves
the rules sharing its anchor intact.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.exceptions import ConditionsNotInsertable
from krrood.entity_query_language.rdr.condition_resolver import (
    ChainConditionResolver,
    ResolutionMode,
    TargetSufficientConditionsBasedResolver,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import CaseContext, FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rules.conclusion_selector import ConclusionSelector

from .animal import Animal, Species, make_animal, make_bird, make_mammal
from .expert_doubles import scripted_expert

# %% helpers


def _holds_for(expression: SymbolicExpression, case_variable, case: Animal) -> bool:
    """
    Evaluate a resolved condition against one concrete case.

    :param expression: The condition expression the resolver returned.
    :param case_variable: The RDR's shared EQL variable the expression is built over.
    :param case: The case to evaluate it for.
    :return: Whether the condition holds for ``case``.
    """
    case_variable._update_domain_([case])
    return any(bool(result) for result in expression.evaluate())


def _mammal_then_bird_rdr():
    """
    Build an RDR holding exactly two rules: ``milk`` -> mammal, then ``feathers`` ->
    bird as its alternative.

    :return:``(rdr, mammal_corner_case)``, the mammal being the case the first rule was
        written for.
    """
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(
        {
            Species.mammal: lambda variable: variable.milk == True,
            Species.bird: lambda variable: variable.feathers == True,
        }
    )
    mammal = make_mammal("resolver_mammal")
    rdr.fit_case(mammal, Species.mammal, expert)
    rdr.fit_case(make_bird("resolver_bird"), Species.bird, expert)
    return rdr, mammal


def _resolve_against_live_tree(
    rdr: EQLSingleClassRDR, case, corner_case, target, current
):
    """
    Run the target-knowledge resolver against the RDR's real backward-inference
    knowledge.

    :param rdr: The fitted RDR whose rule tree supplies the knowledge.
    :param case: The new case needing a condition.
    :param corner_case: The case the firing rule was written for.
    :param target: The correct conclusion.
    :param current: The conclusion that wrongly fired.
    :return: The resolved condition, or ``None``.
    """
    return TargetSufficientConditionsBasedResolver().resolve(
        CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=current,
            target_conclusion=target,
            corner_case=corner_case,
        ),
        rdr.sufficient_conditions_for(target),
        rdr.sufficient_conditions_for(current),
    )


# %% the resolved expression really discriminates


def test_the_resolved_expression_holds_for_the_new_case():
    rdr, mammal = _mammal_then_bird_rdr()
    new_bird = make_bird("resolver_bird_two")

    resolved = _resolve_against_live_tree(
        rdr, new_bird, mammal, Species.bird, Species.mammal
    )

    assert resolved is not None
    assert _holds_for(resolved.expression, rdr.case_variable, new_bird) is True


def test_the_resolved_expression_does_not_hold_for_the_corner_case():
    rdr, mammal = _mammal_then_bird_rdr()
    new_bird = make_bird("resolver_bird_two")

    resolved = _resolve_against_live_tree(
        rdr, new_bird, mammal, Species.bird, Species.mammal
    )

    assert resolved is not None
    assert _holds_for(resolved.expression, rdr.case_variable, mammal) is False


def test_a_negated_guard_resolves_to_an_expression_that_inverts_it():
    """
    The bird branch's own guard is ``not milk``, since it only applies when the mammal
    rule did not fire.

    Resolving it must yield an expression true of a milkless case and false of a milk-
    bearing one.
    """
    rdr, mammal = _mammal_then_bird_rdr()
    # A bird with no feathers, so the only bird guard that can discriminate is ``not milk``.
    featherless = make_animal("resolver_featherless", eggs=True, legs=2)

    resolved = _resolve_against_live_tree(
        rdr, featherless, mammal, Species.bird, Species.mammal
    )

    assert resolved is not None
    assert _holds_for(resolved.expression, rdr.case_variable, featherless) is True
    assert _holds_for(resolved.expression, rdr.case_variable, mammal) is False


# %% never a conclusion selector


def test_a_resolved_expression_is_never_a_conclusion_selector():
    """
    A conclusion selector used as a rule condition closes a cycle in the rule-tree DAG,
    so the guard decomposition must never hand one to the resolver.
    """
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(
        {
            Species.mammal: lambda variable: variable.milk == True,
            Species.bird: lambda variable: variable.feathers == True,
            Species.fish: lambda variable: variable.fins == True,
        }
    )
    mammal = make_mammal("selector_mammal")
    rdr.fit_case(mammal, Species.mammal, expert)
    rdr.fit_case(make_bird("selector_bird"), Species.bird, expert)
    # A fish that also has milk refines the mammal rule, putting an Alternative on the
    # refinement's guard path.
    rdr.fit_case(
        make_animal("selector_fish", milk=True, fins=True, aquatic=True),
        Species.fish,
        expert,
    )

    guards = [
        guard
        for conclusion in (Species.mammal, Species.bird, Species.fish)
        for condition_set in rdr.sufficient_conditions_for(
            conclusion
        ).sufficient_condition_sets
        for guard in condition_set.conditions
    ]

    assert guards, "the tree must produce guards for the assertion below to constrain"
    for guard in guards:
        assert not isinstance(guard.as_expression, ConclusionSelector)


# %% a condition that cannot be spliced


def _mammal_rdr_a_reptile_misfires_for(resolution_mode: ResolutionMode):
    """
    Build an RDR whose only rule is ``backbone`` -> mammal, plus a backboned reptile it
    therefore misclassifies.

    :param resolution_mode: The mode to construct the RDR with.
    :return:``(rdr, reptile)``.
    """
    rdr = EQLSingleClassRDR(Animal, "species", resolution_mode=resolution_mode)
    rdr.fit_case(
        make_animal("splice_mammal", backbone=True, milk=True),
        Species.mammal,
        scripted_expert({Species.mammal: lambda variable: variable.backbone}),
    )
    return rdr, make_animal("splice_reptile", backbone=True, venomous=True)


def _answer_with_the_anchor_then_a_real_condition():
    """
    Build an answer function that first hands back the firing rule's own anchor — which
    cannot be spliced — and then a genuine condition.

    :return:``(answer_function, attempts)``, ``attempts`` growing by one per call.
    """
    attempts = []

    def answer(context, requests):
        attempts.append(context.case_instance)
        if len(attempts) == 1:
            return {AnswerName.CONDITIONS: context.trace.firing_anchor}
        return {AnswerName.CONDITIONS: context.case_variable.venomous == True}

    return answer, attempts


def test_hint_mode_asks_again_when_the_condition_cannot_be_spliced():
    rdr, reptile = _mammal_rdr_a_reptile_misfires_for(ResolutionMode.HINT)
    answer, attempts = _answer_with_the_anchor_then_a_real_condition()

    rdr.fit_case(
        reptile,
        Species.reptile,
        Expert(interface=FunctionInterface(answer_function=answer)),
    )

    assert len(attempts) == 2
    assert rdr.classify(reptile) is Species.reptile


def test_automatic_mode_surfaces_a_condition_that_cannot_be_spliced():
    rdr, reptile = _mammal_rdr_a_reptile_misfires_for(ResolutionMode.AUTOMATIC)
    answer, _ = _answer_with_the_anchor_then_a_real_condition()

    with pytest.raises(ConditionsNotInsertable):
        rdr.fit_case(
            reptile,
            Species.reptile,
            Expert(interface=FunctionInterface(answer_function=answer)),
        )


# %% inserting at a shared anchor


def test_resolving_at_a_shared_anchor_leaves_the_sibling_rule_intact():
    """
    Regression: the ``backbone`` comparator is the anchor of the first rule *and* a sub-
    expression of the molusc alternative's ``backbone == False``.

    Inserting a resolved refinement at that anchor must splice below the rule, not
    rewrite the sibling condition into ``(backbone except if venomous) == False``.
    """
    rdr = EQLSingleClassRDR(
        Animal,
        "species",
        condition_resolver=ChainConditionResolver.backward_inference_default(),
        resolution_mode=ResolutionMode.AUTOMATIC,
    )
    expert = scripted_expert(
        {
            Species.mammal: lambda variable: variable.backbone,
            Species.fish: lambda variable: variable.eggs,
            Species.molusc: lambda variable: variable.backbone == False,
            Species.reptile: lambda variable: variable.venomous,
        }
    )
    molusc = make_animal("anchor_molusc", backbone=False, eggs=True)
    rdr.fit_case(
        make_animal("anchor_mammal", backbone=True, milk=True), Species.mammal, expert
    )
    rdr.fit_case(
        make_animal("anchor_fish", backbone=True, eggs=True, fins=True),
        Species.fish,
        expert,
    )
    rdr.fit_case(molusc, Species.molusc, expert)
    rdr.fit_case(
        make_animal("anchor_reptile", backbone=True, eggs=True, venomous=True),
        Species.reptile,
        expert,
    )
    # backbone fires (mammal) but eggs does not, so the resolver supplies the condition.
    reptile_without_eggs = make_animal(
        "anchor_reptile_no_eggs", backbone=True, eggs=False, venomous=True
    )

    rdr.fit_case(reptile_without_eggs, Species.reptile, expert)

    assert rdr.classify(molusc) is Species.molusc
    assert rdr.classify(reptile_without_eggs) is Species.reptile


def test_resolving_at_a_shared_anchor_leaves_the_sibling_guards_free_of_selectors():
    rdr = EQLSingleClassRDR(
        Animal,
        "species",
        condition_resolver=ChainConditionResolver.backward_inference_default(),
        resolution_mode=ResolutionMode.AUTOMATIC,
    )
    expert = scripted_expert(
        {
            Species.mammal: lambda variable: variable.backbone,
            Species.fish: lambda variable: variable.eggs,
            Species.molusc: lambda variable: variable.backbone == False,
            Species.reptile: lambda variable: variable.venomous,
        }
    )
    rdr.fit_case(
        make_animal("guard_mammal", backbone=True, milk=True), Species.mammal, expert
    )
    rdr.fit_case(
        make_animal("guard_fish", backbone=True, eggs=True, fins=True),
        Species.fish,
        expert,
    )
    rdr.fit_case(
        make_animal("guard_molusc", backbone=False, eggs=True), Species.molusc, expert
    )
    rdr.fit_case(
        make_animal("guard_reptile", backbone=True, eggs=True, venomous=True),
        Species.reptile,
        expert,
    )

    rdr.fit_case(
        make_animal("guard_reptile_no_eggs", backbone=True, eggs=False, venomous=True),
        Species.reptile,
        expert,
    )

    molusc_guards = [
        guard
        for condition_set in rdr.sufficient_conditions_for(
            Species.molusc
        ).sufficient_condition_sets
        for guard in condition_set.conditions
    ]

    assert (
        molusc_guards
    ), "molusc must still be reachable for the assertion to constrain"
    for guard in molusc_guards:
        assert not isinstance(guard.as_expression, ConclusionSelector)
