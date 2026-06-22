"""
Grammatical gender of a domain noun — the opt-in that lets the verbaliser say *he/his*, *she/her*
(and *who/whom*) instead of the *it/its* (and *which*) it uses by default.

A domain class declares its gender by inheriting a marker — :class:`Masculine` or :class:`Feminine`.
Inheriting neither leaves it :attr:`GrammaticalGender.NEUTER` (the default), so existing code is
untouched.  English natural gender is overwhelmingly *referent*-specific (a *worker* is freely he,
she, or they), so it cannot be looked up from the noun and must be declared where it is known —
hence an explicit marker rather than an inferred one.

Animacy rides along: a gendered noun is animate (it takes *who/whom* in a relative clause), a neuter
one is not (*which*).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from krrood.entity_query_language.verbalization.fragments.features import Number


class GrammaticalGender(StrEnum):
    """The grammatical gender a referent's pronouns and relativiser agree with."""

    MASCULINE = "masculine"
    """*he* / *his*, and *who/whom* in a relative clause."""
    FEMININE = "feminine"
    """*she* / *her*, and *who/whom* in a relative clause."""
    NEUTER = "neuter"
    """*it* / *its*, and *which* in a relative clause — the default for an unmarked type."""

    @property
    def is_animate(self) -> bool:
        """:return: ``True`` for a gendered (masculine/feminine) referent, which takes *who/whom*
        rather than *which*.

        >>> GrammaticalGender.FEMININE.is_animate
        True
        >>> GrammaticalGender.NEUTER.is_animate
        False
        """
        return self is not GrammaticalGender.NEUTER


class Gendered:
    """Base marker for the grammatical-gender mixins.

    A domain class inherits :class:`Masculine` or :class:`Feminine` (never this base directly) to
    declare its gender; the verbaliser then pronominalises it as *he/his* or *she/her*.
    """


class Masculine(Gendered):
    """Mixin marking a domain class as masculine — its referents read *he* / *his* (and *who/whom*).

    >>> class Knight(Masculine):
    ...     pass
    >>> grammatical_gender(Knight)
    <GrammaticalGender.MASCULINE: 'masculine'>
    """


class Feminine(Gendered):
    """Mixin marking a domain class as feminine — its referents read *she* / *her* (and *who/whom*).

    >>> class Queen(Feminine):
    ...     pass
    >>> grammatical_gender(Queen)
    <GrammaticalGender.FEMININE: 'feminine'>
    """


class AmbiguousGrammaticalGenderError(Exception):
    """Raised when a type declares conflicting gender markers (both masculine and feminine)."""

    def __init__(self, type_: type) -> None:
        super().__init__(
            f"{type_.__name__} inherits both Masculine and Feminine; a type has one grammatical "
            f"gender. Inherit exactly one marker."
        )


def grammatical_gender(type_: object) -> GrammaticalGender:
    """Resolve a type's grammatical gender — the single place a marker is read.

    :param type_: A candidate type (any value; a non-type, or an unmarked type, yields ``NEUTER``).
    :return: The declared gender, or :attr:`GrammaticalGender.NEUTER` when no marker is inherited.
    :raises AmbiguousGrammaticalGenderError: when *type_* inherits both markers.

    >>> class Knight(Masculine):
    ...     pass
    >>> grammatical_gender(Knight)
    <GrammaticalGender.MASCULINE: 'masculine'>
    >>> grammatical_gender(int)
    <GrammaticalGender.NEUTER: 'neuter'>
    """
    if not isinstance(type_, type):
        return GrammaticalGender.NEUTER
    masculine = issubclass(type_, Masculine)
    feminine = issubclass(type_, Feminine)
    if masculine and feminine:
        raise AmbiguousGrammaticalGenderError(type_)
    if masculine:
        return GrammaticalGender.MASCULINE
    if feminine:
        return GrammaticalGender.FEMININE
    return GrammaticalGender.NEUTER


@dataclass(frozen=True)
class PronounFeatures:
    """The agreement features a coreference pronoun is chosen from — its number and gender together.

    Bundling the two keeps every pronoun-selection signature to a single argument and makes the
    plural-is-gender-neutral rule (*they/their* regardless of gender) live in one place.
    """

    number: Number
    """Singular vs. plural — the dominant axis (a plural referent is *they/their* whatever its
    gender)."""

    gender: GrammaticalGender = GrammaticalGender.NEUTER
    """The referent's grammatical gender, selecting *he/his* vs *she/her* vs *it/its* in the
    singular."""
