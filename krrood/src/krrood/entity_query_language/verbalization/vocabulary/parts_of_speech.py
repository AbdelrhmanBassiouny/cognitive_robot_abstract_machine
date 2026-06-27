from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from typing_extensions import Any, Iterable, List, Protocol, Union, runtime_checkable

from krrood.entity_query_language.predicate import Field, Operand
from krrood.entity_query_language.utils import camel_case_to_words
from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.fragments.base import (
    Clause,
    Fragment,
    NounPhrase,
    oxford_comma,
    PhraseFragment,
    RoleFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import (
    Definiteness,
    Number,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.microplanning.coordination import (
    MAX_SET_MEMBERS,
    one_of,
)
from krrood.entity_query_language.verbalization.microplanning.possessive import (
    possessive_path,
)
from krrood.entity_query_language.verbalization.navigation_path import PathStep
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Conjunctions,
    Copulas,
    ENGLISH_PREPOSITIONS,
    GroupingPhrases,
    SetMembership,
)
from krrood.entity_query_language.verbalization.vocabulary.words import (
    PlainWord,
    VocabEnum,
)


class ClauseElement(ABC):
    """One typed part-of-speech constituent of a predicate clause.

    A predicate's ``_verbalization_fragment_`` builds its clause from these elements rather than raw
    fragments, so the author writes the affirmative, present-tense form once and the realisation
    passes inflect it (verb agreement, copula suppletion) and negate it (do-support). The element
    only declares *what part of speech* a word is; how it is realised is the morphology pass's job.
    """

    @abstractmethod
    def as_fragment(self) -> Fragment:
        """:return: the fragment this element contributes to the clause."""


@dataclass(frozen=True)
class Noun(ClauseElement):
    """A noun constituent — a predicate :class:`~krrood.entity_query_language.predicate.Field`, an
    already-rendered fragment, or a literal noun given by its *head word only*."""

    content: Any
    """A literal noun *head* (the article is a feature, not part of the text — write ``"instance"``,
    not ``"an instance"``), or any constituent rendered as-is — a rendered fragment, or an
    :class:`~krrood.entity_query_language.predicate.Operand` (``operands.body`` / ``operands.tip.name``).
    Typed :class:`~typing.Any` because an operand is statically the field's declared type (so the IDE
    resolves its attributes), not a constituent type."""

    definiteness: Definiteness = Definiteness.INDEFINITE
    """For a literal-head noun, the article to realise — *"an instance"* (indefinite, the default) vs
    *"the instance"*. Ignored when *content* is already a rendered constituent."""

    def as_fragment(self) -> Fragment:
        """:return: an indefinite (or definite) noun phrase for a literal head — so the article is
        chosen by the determiner pass (*"a"* / *"an"*) and the head pluralises and reduces with
        coreference — else the constituent's own fragment.

        >>> Noun("instance").as_fragment().definiteness
        <Definiteness.INDEFINITE: 'indefinite'>
        """
        if isinstance(self.content, str):
            return NounPhrase(
                head=WordFragment(text=self.content), definiteness=self.definiteness
            )
        return self.content.as_fragment()

    @classmethod
    def the(cls, head: str) -> "Noun":
        """:return: a definite literal noun (*"the name"*).

        >>> Noun.the("name").as_fragment().definiteness
        <Definiteness.DEFINITE: 'definite'>
        """
        return cls(head, definiteness=Definiteness.DEFINITE)


@dataclass(frozen=True)
class Verb(ClauseElement):
    """A lexical verb given as its lemma. The morphology pass realises it present-tense
    (*"work"* → *"works"*) and negates it with do-support (*"does not work"*)."""

    lemma: str
    """The verb's base form (*"work"*, *"contain"*, *"love"*)."""

    number: Number = Number.SINGULAR
    """The subject number the verb agrees with — ``PLURAL`` reads the bare *"work"* / *"have"* for a
    coordinated or plural subject."""

    def as_fragment(self) -> RoleFragment:
        """:return: a ``VERB``-role leaf carrying the lemma for the morphology pass to inflect.

        >>> Verb("work").as_fragment().role
        <SemanticRole.VERB: 'verb'>
        """
        return RoleFragment(text=self.lemma, role=SemanticRole.VERB, number=self.number)


@dataclass(frozen=True)
class Adjective(ClauseElement):
    """A predicative adjective complement after a copula (*"is **reachable**"*)."""

    word: str
    """The adjective's surface word."""

    def as_fragment(self) -> WordFragment:
        """:return: a plain word leaf for the adjective.

        >>> Adjective("reachable").as_fragment().text
        'reachable'
        """
        return WordFragment(text=self.word)


@dataclass(frozen=True)
class All(ClauseElement):
    """The universal quantifier *"all"* fronting a clause's subject.

    In a :func:`clause` it both reads as *"all"* and tells the builder to make the quantified subject
    — the first noun phrase after it — plural and to agree the clause's verb / copula, so
    ``clause(All(), Noun("element"), Copula(), Adjective("close"))`` reads *"all elements are close"*.
    Only the number features are set here; the morphology pass does the inflection (*"element"* →
    *"elements"*, *"is"* → *"are"*)."""

    def as_fragment(self) -> Fragment:
        """:return: the *"all"* quantifier word leaf.

        >>> All().as_fragment().text
        'all'
        """
        return GroupingPhrases.ALL.as_fragment()


@dataclass(frozen=True)
class Copula(ClauseElement):
    """The copula *"is"* of a predicative clause — realised for number (*"is"* / *"are"*) and
    negation (*"is not"*) by the morphology pass."""

    def as_fragment(self) -> RoleFragment:
        """:return: the affirmative singular copula leaf the morphology pass inflects.

        >>> Copula().as_fragment().text
        'is'
        """
        return Copulas.IS.as_fragment()


@dataclass(frozen=True)
class OneOf(ClauseElement):
    """A bounded membership set — *"one of A, B, or C"* — over a collection of admissible values.

    This is the high-level element for a "the subject is one of these" clause (a tuple of admissible
    types, a small value domain), so an author never re-implements the listing: each member renders
    as a linked type reference when it is a class, else as a literal value, and a set larger than the
    cap is summarised by count (*"one of seven types"*) rather than spelled out — the same bounded
    surface a domain-constrained variable uses.
    """

    members: Union[Iterable, Field, Operand, Any]
    """The admissible values — an :class:`~krrood.entity_query_language.predicate.Operand`
    (``operands.types_``) or :class:`~krrood.entity_query_language.predicate.Field` bound to a
    collection, or a collection directly. Classes render as linked type references, other values as
    literals."""

    def as_fragment(self) -> Fragment:
        """:return: the membership phrase, or a count summary past the cap.

        >>> from krrood.entity_query_language.verbalization.fragments.base import (
        ...     flatten_fragment_to_plain_text,
        ... )
        >>> flatten_fragment_to_plain_text(OneOf((int, str)).as_fragment())
        'one of int or str'
        """
        if isinstance(self.members, Operand):
            collection = self.members._value_of_operand_
        elif isinstance(self.members, Field):
            collection = self.members.value
        else:
            collection = self.members
        members = list(collection)
        are_types = bool(members) and all(
            isinstance(member, type) for member in members
        )
        render = RoleFragment.for_type if are_types else RoleFragment.for_literal
        listed = one_of([render(member) for member in members[: MAX_SET_MEMBERS + 1]])
        if listed is not None:
            return listed
        return PhraseFragment(
            parts=[
                SetMembership.ONE_OF.as_fragment(),
                WordFragment(text=morphology.cardinal(len(members))),
                WordFragment(text="types" if are_types else "values"),
            ]
        )


class Preposition(VocabEnum):
    """The prepositions a clause links its constituents with (*"works **in** a department"*)."""

    IN = PlainWord("in")
    ON = PlainWord("on")
    OF = PlainWord("of")
    TO = PlainWord("to")
    BY = PlainWord("by")
    AT = PlainWord("at")
    WITH = PlainWord("with")
    FROM = PlainWord("from")
    FOR = PlainWord("for")


@runtime_checkable
class ClauseConstituent(Protocol):
    """The one contract every clause constituent satisfies: it renders itself to a :class:`Fragment`.

    A typed part-of-speech element (:class:`ClauseElement` — :class:`Noun` / :class:`Verb` / …), a
    :class:`Preposition`, a predicate :class:`~krrood.entity_query_language.predicate.Field`, and a
    raw :class:`Fragment` all satisfy it structurally (each defines ``as_fragment``), so
    :func:`clause` depends on this single abstraction rather than enumerating concrete types — a new
    kind of constituent only has to implement the method (open/closed).

    This is a :class:`~typing.Protocol`, not a base class, because the constituents are
    deliberately heterogeneous: ``Preposition`` is an ``Enum`` (it cannot also inherit an ABC) and
    ``Field`` is a core type (it must not depend on this verbalization layer). Structural typing
    unifies them without forcing inheritance.
    """

    def as_fragment(self) -> Fragment:
        """:return: the fragment this constituent contributes to a clause."""


def clause(*constituents: ClauseConstituent) -> Clause:
    """
    Build a predicate clause from typed part-of-speech constituents.

    A predicate states its affirmative form once — *"<subject> works in <object>"* —
    ``clause(Noun(subject), Verb("work"), Preposition.IN, Noun(object))`` — and the realisation
    passes handle agreement and negation. A raw :class:`Fragment` is accepted too, so a rendered
    field fragment can be dropped in directly. The result is a :class:`Clause`, so coreference
    treats the first constituent as the clause's subject (pronominalisation, verb agreement).

    :param constituents: The clause's elements in surface order.
    :return: The clause fragment.

    >>> from krrood.entity_query_language.verbalization.fragments.base import (
    ...     flatten_fragment_to_plain_text, WordFragment,
    ... )
    >>> flatten_fragment_to_plain_text(
    ...     clause(Noun(WordFragment(text="an Employee")), Verb("work"), Preposition.IN,
    ...            Noun(WordFragment(text="a Department")))
    ... )
    'an Employee work in a Department'

    An :class:`All` quantifier makes the clause read a universal: the subject it fronts becomes plural
    and the verb / copula agrees.

    >>> flatten_fragment_to_plain_text(
    ...     clause(All(), Noun("element"), Copula(), Adjective("close"))
    ... )
    'all elements are close'
    """
    parts = [(constituent, constituent.as_fragment()) for constituent in constituents]
    if any(isinstance(constituent, All) for constituent, _ in parts):
        return Clause(parts=_agree_with_universal_quantifier(parts))
    return Clause(parts=[fragment for _, fragment in parts])


def _agree_with_universal_quantifier(
    parts: List[tuple],
) -> List[Fragment]:
    """:return: the clause fragments with universal-quantifier agreement applied — the quantified
    subject (the first noun phrase after the :class:`All` word) is made plural and the clause's
    copula / verb agrees. Only the number features are set; the morphology pass inflects them.
    """
    fragments: List[Fragment] = []
    seen_all = False
    subject_pluralized = False
    for constituent, fragment in parts:
        if isinstance(constituent, All):
            seen_all = True
            fragments.append(fragment)
        elif seen_all and not subject_pluralized and isinstance(fragment, NounPhrase):
            fragments.append(replace(fragment, number=Number.PLURAL))
            subject_pluralized = True
        elif isinstance(fragment, RoleFragment) and fragment.role in (
            SemanticRole.OPERATOR,
            SemanticRole.VERB,
        ):
            fragments.append(replace(fragment, number=Number.PLURAL))
        else:
            fragments.append(fragment)
    return fragments


_COPULA_LEMMA = "be"
"""The lemma every copular form (*"is"*, *"are"*, *"was"*) shares — used to recognise a copular name."""

_VALUE_GETTER_PREFIX = "get"
"""The leading imperative dropped from a value function's name so a stray getter still reads as a
noun (``get_quarter`` → *"quarter"*); verb-named value functions are discouraged upstream."""


def value_function_noun(name: str) -> str:
    """:return: a value (non-boolean) symbolic function's name as noun words, dropping a leading
    imperative ``get`` so ``get_quarter`` reads as *"quarter"* and ``get_year`` as *"year"*; a name
    that is already a noun is returned unchanged.

    >>> value_function_noun("get_quarter")
    'quarter'
    >>> value_function_noun("remaining_load")
    'remaining load'
    """
    words = camel_case_to_words(name).split()
    if len(words) > 1 and words[0].lower() == _VALUE_GETTER_PREFIX:
        words = words[1:]
    return " ".join(words)


def value_function_phrase(name: str, *operands: ClauseConstituent) -> Fragment:
    """Build *"the &lt;noun&gt; of &lt;operands&gt;"* for a value function — the counterpart of
    :func:`predicate_clause` for an operation that computes a value rather than a truth.

    The *name* is read as the value's noun (a leading ``get`` dropped), and the operands are read out
    as a genitive over it. A nullary function is just the noun. This is the default, name-based surface
    a value :class:`~krrood.entity_query_language.predicate.SymbolicFunction` reuses, so the reading
    lives in one place.

    :param name: The function's identifier.
    :param operands: The function's already-rendered arguments.
    :return: The value noun phrase.

    >>> from krrood.entity_query_language.verbalization.fragments.base import (
    ...     flatten_fragment_to_plain_text, WordFragment,
    ... )
    >>> flatten_fragment_to_plain_text(value_function_phrase("get_quarter"))
    'quarter'
    >>> flatten_fragment_to_plain_text(
    ...     value_function_phrase("remaining_load", WordFragment(text="the capacity"))
    ... )
    'the remaining load of the capacity'
    """
    noun = value_function_noun(name)
    if not operands:
        return Noun(WordFragment(text=noun)).as_fragment()
    owner = oxford_comma(
        [operand.as_fragment() for operand in operands], Conjunctions.AND.as_fragment()
    )
    return possessive_path([PathStep(noun)], owner)


def predicate_clause(
    name: str,
    subject: ClauseConstituent,
    *objects: ClauseConstituent,
) -> Clause:
    """Build a predicate clause from a predicate's *name* and its operands.

    The name (CamelCase or snake_case) is read as the predicate. A copular name — its leading word a
    form of *"be"* (*"is_one_month"*, *"IsReachable"*) — uses the copula with the remaining words as
    the complement (*"<subject> is one month"*). Any other name reads verb-first, so a wrapping
    ``Not`` negates it with do-support (*"<subject> connects to <object>"*, *"does not connect to"*).
    The first operand is the subject; any further operands are trailing objects.

    A copular complement attaches trailing operands only through a final preposition
    (*"is_supported_by"* → *"… is supported by <object>"*). When it has none, an adjective/noun
    complement cannot take them as objects — *"the begin is one month the end"* is nonsense — and
    naming any one operand as the subject is a false claim (the *period* is one month, not the
    *begin*). So the named condition is stated to *hold for* all operands, asserting nothing false:
    *"one month holds for the begin and the end"*.

    Shared by :class:`~krrood.entity_query_language.predicate.Triple` (a class-name relation) and the
    symbolic-function rule (a function-name predicate), so the name-to-clause reading lives in one
    place.

    :param name: The predicate's identifier — a class or function name.
    :param subject: The first operand, rendered as the clause's subject.
    :param objects: Any further operands, rendered as trailing objects.
    :return: The predicate clause.

    >>> from krrood.entity_query_language.verbalization.fragments.base import (
    ...     flatten_fragment_to_plain_text, WordFragment,
    ... )
    >>> flatten_fragment_to_plain_text(
    ...     predicate_clause("is_one_month", WordFragment(text="the period"))
    ... )
    'the period is one month'
    >>> flatten_fragment_to_plain_text(
    ...     predicate_clause("connects_to", WordFragment(text="a body"),
    ...                      WordFragment(text="another body"))
    ... )
    'a body connect to another body'
    >>> flatten_fragment_to_plain_text(
    ...     predicate_clause("is_one_month", WordFragment(text="the begin"),
    ...                      WordFragment(text="the end"))
    ... )
    'one month hold for the begin and the end'
    """
    head, *rest = camel_case_to_words(name).split()
    complement = [WordFragment(text=word) for word in rest]
    is_copular = morphology.verb_lemma(head) == _COPULA_LEMMA
    if is_copular and objects and (not rest or rest[-1] not in ENGLISH_PREPOSITIONS):
        # A copular complement attaches trailing operands only through a final preposition
        # (``is_supported_by`` → *"… is supported by <object>"*). Without one, an adjective/noun
        # complement cannot take them as objects — *"the begin is one month the end"* is nonsense — and
        # naming any single operand as the subject (*"the begin is one month"*) is a FALSE claim (the
        # period is, not the begin). State only what is certain: the named condition holds for ALL the
        # operands. *"one month holds for the begin and the end of its period"*.
        operands = oxford_comma(
            [Noun(subject).as_fragment(), *(Noun(obj).as_fragment() for obj in objects)],
            Conjunctions.AND.as_fragment(),
        )
        return clause(
            Noun(PhraseFragment(parts=complement)),
            Verb("hold"),
            WordFragment(text="for"),
            operands,
        )
    predicate = (
        [Copula(), *complement]
        if is_copular
        else [Verb(morphology.verb_lemma(head)), *complement]
    )
    return clause(Noun(subject), *predicate, *(Noun(obj) for obj in objects))
