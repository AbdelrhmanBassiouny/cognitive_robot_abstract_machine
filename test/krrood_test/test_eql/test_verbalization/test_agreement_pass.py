"""The agreement realization pass: a clause's finite verb/copula agrees in number with its subject.

Subject number is decided when the clause is built (a plural noun phrase, or the ``All`` quantifier);
this pass — not the build site — copies that number onto the finite slot, and the morphology pass
inflects it (*"is"* → *"are"*, a verb to its bare plural). A singular or absent subject is untouched.
This covers the case the build-time tagging never did: a plural subject that is NOT pronominalized.
"""

from __future__ import annotations

from krrood.entity_query_language.verbalization.fragments.base import (
    NounPhrase,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import (
    Definiteness,
    Number,
)
from krrood.entity_query_language.verbalization.rendering.agreement_processor import (
    AgreementProcessor,
)
from krrood.entity_query_language.verbalization.rendering.realization import (
    realize_subtree,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    All,
    clause,
    Copula,
    Noun,
    Verb,
)


def _plural_subject(head: str) -> NounPhrase:
    return NounPhrase(
        head=WordFragment(text=head),
        number=Number.PLURAL,
        definiteness=Definiteness.INDEFINITE,
    )


def test_plural_noun_phrase_subject_agrees_the_copula():
    # A plural subject that is neither pronominalized nor quantified still agrees the copula.
    assert (
        realize_subtree(clause(_plural_subject("element"), Copula(), Adjective("close")))
        == "elements are close"
    )


def test_plural_noun_phrase_subject_agrees_a_verb():
    assert realize_subtree(clause(_plural_subject("robot"), Verb("work"))) == "robots work"


def test_all_quantified_subject_agrees_through_the_pass():
    # The All build site only pluralizes the subject; the pass agrees the copula.
    assert (
        realize_subtree(clause(All(), Noun("element"), Copula(), Adjective("close")))
        == "all elements are close"
    )


def test_singular_subject_is_left_untouched():
    assert (
        realize_subtree(clause(Noun("robot"), Copula(), Adjective("close")))
        == "a robot is close"
    )


def test_agreement_is_idempotent():
    tree = clause(All(), Noun("element"), Copula(), Adjective("close"))
    once = AgreementProcessor().process(tree)
    twice = AgreementProcessor().process(once)
    assert once == twice
