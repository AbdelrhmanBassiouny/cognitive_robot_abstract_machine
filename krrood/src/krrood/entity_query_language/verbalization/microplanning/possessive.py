from __future__ import annotations

from typing_extensions import List

from krrood.entity_query_language.verbalization.navigation_path import PathStep
from krrood.entity_query_language.verbalization.fragments.base import (
    NounPhrase,
    oxford_comma,
    PhraseFragment,
    RoleFragment,
    Fragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import (
    Definiteness,
    Number,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.grammatical_gender import (
    grammatical_gender,
    PronounFeatures,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Conjunctions,
    Copulas,
    Prepositions,
    Pronouns,
    Relativizers,
)


def attribute_fragment(
    step: PathStep, number: Number = Number.SINGULAR
) -> RoleFragment:
    """:return: A role-tagged attribute fragment for *step*, tagged with *number* for inflection
    (a single-hop possessive of a plural subject distributes — *"their salaries"*).

    >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text
    >>> flatten_fragment_to_plain_text(attribute_fragment(PathStep("salary")))
    'salary'
    """
    return RoleFragment(
        text=step.name,
        role=SemanticRole.ATTRIBUTE,
        source_reference=step.source_reference,
        number=number,
    )


def _genitive_step(step: PathStep, owner_fragment: Fragment) -> Fragment:
    """:return: *"the <attribute> of <owner>"* — one plain (noun) hop wrapping its owner.

    This is the genitive case specifically: it lays down *the … of …* around the owner, so the
    *battery* hop on *Robot* reads *the battery of Robot* (a relational hop would instead route
    through :func:`_relative_clause`).

    >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text, WordFragment
    >>> flatten_fragment_to_plain_text(_genitive_step(PathStep("battery"), WordFragment(text="Robot")))
    'the battery of Robot'
    """
    return PhraseFragment(
        parts=[
            Articles.THE.as_fragment(),
            attribute_fragment(step),
            Prepositions.OF.as_fragment(),
            owner_fragment,
        ]
    )


def _relative_clause(
    step: PathStep, owner_fragment: Fragment, owner_number: Number = Number.SINGULAR
) -> Fragment:
    """:return: *"the <Type> <preposition> which <owner> is <participle>"* — one relational hop
    wrapping its owner as a relative clause (the preposition pied-piped before *which*: *"the Robot
    to which a Mission is assigned"*). Keeping the owner the verb's subject means the meaning never
    flips for agentive relations (*"the Person by which a Book is owned"*); the copula agrees with
    the owner's *owner_number* (*"it is"* / *"they are"*).

    The clause is a *referring* noun phrase headed by the related type, so a repeat mention of the
    same navigation reduces to a bare *"the <Type>"* during coreference (the relative clause is a
    first-mention modifier).

    The relativiser agrees with the head's animacy — *which* for an inanimate type, *whom* for a
    gendered (animate) one (*"the Queen to whom a Knight is assigned"*).

    >>> verbalize_expression(variable(Mission, []).assigned_to)
    'the Robot to which a Mission is assigned'
    """
    relation = step.relation
    return NounPhrase(
        head=RoleFragment.for_type(relation.value_type),
        definiteness=Definiteness.DEFINITE,
        modifiers=[
            WordFragment(text=relation.preposition),
            Relativizers.for_gender(grammatical_gender(relation.value_type)).as_fragment(),
            owner_fragment,
            Copulas.for_number(owner_number),
            RoleFragment.for_attribute(
                relation.owner_class, step.name, text=relation.participle
            ),
        ],
        referent_id=relation.referent_id,
    )


def coordinated_genitive(
    attribute_fragments: List[Fragment], owner_fragment: Fragment
) -> Fragment:
    """:return: *"the <a, b, and c> of <owner>"* — several attributes sharing one genitive owner,
    coordinated under it (right-node raising: *"the department and salary of an Employee"*) rather
    than repeated owner by owner (*"the department of an Employee and its salary"*).

    >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text, WordFragment
    >>> attributes = [attribute_fragment(PathStep("department")), attribute_fragment(PathStep("salary"))]
    >>> flatten_fragment_to_plain_text(coordinated_genitive(attributes, WordFragment(text="Employee")))
    'the department and salary of Employee'
    """
    return PhraseFragment(
        parts=[
            Articles.THE.as_fragment(),
            oxford_comma(attribute_fragments, Conjunctions.AND.as_fragment()),
            Prepositions.OF.as_fragment(),
            owner_fragment,
        ]
    )


def _extend_hop(step: PathStep, owner_fragment: Fragment) -> Fragment:
    """:return: *owner_fragment* wrapped by one more hop — the relative clause for a relational hop,
    else the genitive. The shared hop builder both path readouts extend their owner with.

    Its contribution is the per-hop choice: *battery* is a plain noun hop, so it dispatches to
    :func:`_genitive_step` and the result is *the battery of Robot*; a relational hop (e.g.
    *assigned_to*) would instead become a *"… to which … is assigned"* relative clause.

    >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text, WordFragment
    >>> flatten_fragment_to_plain_text(_extend_hop(PathStep("battery"), WordFragment(text="Robot")))
    'the battery of Robot'
    """
    return (
        _relative_clause(step, owner_fragment)
        if step.is_relation
        else _genitive_step(step, owner_fragment)
    )


def possessive_path(parts: List[PathStep], root_fragment: Fragment) -> Fragment:
    """:return: the navigation read out from the root, hop by hop (parts innermost-first) — a plain
    hop as the genitive *"the <attribute> of <owner>"*, a relational hop as the relative clause
    *"the <Type> <prep> which <owner> is <participle>"*. With only plain hops this is the familiar
    *"the <outer> of the <inner> of <root>"*.

    >>> verbalize_expression(variable(Robot, []).battery)
    'the battery of a Robot'
    >>> verbalize_expression(variable(BankTransaction, []).amount_details.amount)
    'the amount of the amount_details of a BankTransaction'
    """
    owner = root_fragment
    for step in parts:
        owner = _extend_hop(step, owner)
    return owner


def chain_head_number(parts: List[PathStep], subject_number: Number) -> Number:
    """:return: The grammatical number the chain's head noun is realised with once its root is
    pronominalised — *subject_number* only when a single scalar hop distributes over the subject
    (*"their batteries"*), else singular: a deeper or relational chain heads on an inner genitive
    that does not distribute (*"the priority of their missions"*).

    This is the head-agreement counterpart of :func:`pronominal_path` (which distributes the
    *innermost* hop): a finite verb agrees with the head, so its copula reads *"are"* exactly when
    this returns plural.

    >>> from krrood.entity_query_language.verbalization.fragments.features import Number
    >>> chain_head_number([PathStep("battery", is_scalar_value=True)], Number.PLURAL)
    <Number.PLURAL: 'plural'>
    >>> chain_head_number(
    ...     [PathStep("assigned_to"), PathStep("battery", is_scalar_value=True)], Number.PLURAL
    ... )
    <Number.SINGULAR: 'singular'>
    """
    if len(parts) == 1 and parts[0].is_scalar_value:
        return subject_number
    return Number.SINGULAR


def pronominal_path(parts: List[PathStep], subject: PronounFeatures) -> Fragment:
    """:return: the navigation read out with the (elided) root pronominalised — *"its attribute"* /
    *"the attribute of its foo"* for plain hops, and the relative clause *"the <Type> <prep> which
    it is <participle>"* for a relational hop (the innermost hop, adjacent to the elided root, takes
    the pronoun: the possessive *its/his/her/their* for a genitive, the nominative *it/he/she/they*
    as the verb's subject for a relation). Reuses the same hop builders as :func:`possessive_path`.

    :param parts: The chain hops, innermost-first.
    :param subject: The discourse subject's agreement features — its number and gender select the
        pronoun (*its/his/her* singular by gender, *their* plural).

    >>> from krrood.entity_query_language.verbalization.fragments.base import flatten_fragment_to_plain_text
    >>> from krrood.entity_query_language.verbalization.grammatical_gender import PronounFeatures, GrammaticalGender
    >>> from krrood.entity_query_language.verbalization.fragments.features import Number
    >>> flatten_fragment_to_plain_text(pronominal_path([], PronounFeatures(Number.SINGULAR)))
    'its'
    >>> flatten_fragment_to_plain_text(pronominal_path([], PronounFeatures(Number.SINGULAR, GrammaticalGender.MASCULINE)))
    'his'
    """
    possessive_pronoun = Pronouns.possessive(subject).as_fragment()
    if not parts:
        return possessive_pronoun
    nominative_pronoun = Pronouns.nominative(subject).as_fragment()
    # The innermost hop, adjacent to the elided root, takes the pronoun; the rest extend it exactly
    # as :func:`possessive_path` does.
    first, rest = parts[0], parts[1:]
    # A scalar leaf possessed by a plural subject distributes ("their salaries"); an entity owner of
    # further structure stays singular ("the begin and end of their period").
    attribute_number = subject.number if first.is_scalar_value else Number.SINGULAR
    owner: Fragment = (
        _relative_clause(first, nominative_pronoun, subject.number)
        if first.is_relation
        else PhraseFragment(
            parts=[possessive_pronoun, attribute_fragment(first, attribute_number)]
        )
    )
    for step in rest:
        owner = _extend_hop(step, owner)
    return owner
