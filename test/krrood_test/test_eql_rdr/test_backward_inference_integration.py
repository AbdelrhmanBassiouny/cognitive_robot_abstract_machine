"""
Tests for the RDR's own backward-inference surface: the wrapper that reads the live rule
tree, and the cache invalidation that keeps it honest as fitting grows that tree.

``test_backward_inference.py`` covers the traversal itself against hand-built rule
trees; what only the engine can show is that the wrapper reads the RDR's *current*
conditions root and that a fit invalidates what was cached before it.
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.backward_inference import (
    ConclusionSufficientConditionSets,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species, make_mammal
from .expert_doubles import scripted_expert

# %% the wrapper reads the live tree


def test_an_empty_rule_tree_knows_nothing_about_any_conclusion():
    rdr = EQLSingleClassRDR(Animal, "species")

    knowledge = rdr.sufficient_conditions_for(Species.molusc)

    assert isinstance(knowledge, ConclusionSufficientConditionSets)
    assert not knowledge.is_satisfiable()


def test_a_conclusion_no_rule_produces_stays_unsatisfiable_after_fitting():
    rdr = EQLSingleClassRDR(Animal, "species")
    rdr.fit_case(
        make_mammal("known_mammal"),
        Species.mammal,
        scripted_expert({Species.mammal: lambda variable: variable.milk == True}),
    )

    assert not rdr.sufficient_conditions_for(Species.molusc).is_satisfiable()


# %% fitting invalidates what was cached


def test_fitting_makes_the_new_rules_conclusion_knowable():
    rdr = EQLSingleClassRDR(Animal, "species")
    # Read the index before fitting, so a stale cache would survive into the assertion.
    assert not rdr.sufficient_conditions_for(Species.mammal).is_satisfiable()

    rdr.fit_case(
        make_mammal("cache_mammal"),
        Species.mammal,
        Expert(
            interface=FunctionInterface(
                answer_function=lambda context, requests: {
                    AnswerName.CONDITIONS: context.case_variable.milk == True
                }
            )
        ),
    )

    assert rdr.sufficient_conditions_for(Species.mammal).is_satisfiable()


def test_a_second_fit_widens_the_guards_of_the_first_rules_conclusion():
    """
    An alternative added below a rule puts that rule's condition into the new branch's
    guards, so the earlier conclusion's condition set must grow rather than stay cached.
    """
    rdr = EQLSingleClassRDR(Animal, "species")
    expert = scripted_expert(
        {
            Species.mammal: lambda variable: variable.milk == True,
            Species.bird: lambda variable: variable.feathers == True,
        }
    )
    rdr.fit_case(make_mammal("widen_mammal"), Species.mammal, expert)
    bird_knowledge_before = rdr.sufficient_conditions_for(Species.bird)

    rdr.fit_case(
        make_mammal("widen_bird", milk=False, hair=False, feathers=True),
        Species.bird,
        expert,
    )

    assert not bird_knowledge_before.is_satisfiable()
    assert rdr.sufficient_conditions_for(Species.bird).is_satisfiable()
