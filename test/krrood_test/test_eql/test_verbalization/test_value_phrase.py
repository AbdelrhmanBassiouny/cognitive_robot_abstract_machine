"""
A value :class:`SymbolicFunction` whose noun is not its class name builds its surface
from :func:`phrase`, the value counterpart of :func:`clause`.

:class:`FunctionVerbalizationTemplates` covers the two readings a value takes *from its
class name* -- the possessive *"the length of …"* and a custom relating word. A value
whose noun is a phrase of its own (*"the bodies visible to a camera"* for a class named
``GetVisibleBodies``) is neither, and must not fall back to assembling raw fragments.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.predicate import SymbolicFunction
from krrood.entity_query_language.verbalization.fragments.base import Clause
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.english import Prepositions
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    Noun,
    Verb,
    phrase,
)

from ...dataset.semantic_world_like_classes import Body


@dataclass(eq=False)
class VisibleBodies(SymbolicFunction):
    """
    A value whose noun is a phrase rather than its class name.
    """

    viewer: Body
    """
    The body the visibility is judged from.
    """

    def __call__(self) -> list:
        return []

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return phrase(
            Noun.the("bodies"),
            Adjective("visible"),
            Prepositions.TO,
            Noun(fields["viewer"]),
        )


@dataclass(eq=False)
class BlockingBodies(SymbolicFunction):
    """
    A value whose phrase reads as a participial modifier over its operand.
    """

    goal: Body
    """
    The body the blocked path leads to.
    """

    def __call__(self) -> list:
        return []

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return phrase(
            Noun.the("bodies"),
            Adjective("blocking"),
            Noun.the("path"),
            Prepositions.TO,
            Noun(fields["goal"]),
        )


@dataclass(eq=False)
class VerbHeadedValue(SymbolicFunction):
    """
    A value that wrongly reaches for :class:`Verb` where a participle is meant.
    """

    goal: Body
    """
    The body the blocked path leads to.
    """

    def __call__(self) -> list:
        return []

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return phrase(Noun.the("bodies"), Verb("blocking"), Noun.the("path"))


# %% a value phrase reads as a noun phrase, not a clause


def test_value_phrase_renders_its_constituents_in_order():
    """
    The chosen head noun, its modifiers and the operand read in the order written.
    """
    rendered = verbalize_expression(VisibleBodies(variable(Body, [])))

    assert rendered == "the bodies visible to a Body"


def test_value_phrase_reads_a_participial_modifier_bare():
    """
    A participle modifying the head is an ordinary word constituent, so a value needs no
    separate template for it.
    """
    rendered = verbalize_expression(BlockingBodies(variable(Body, [])))

    assert rendered == "the bodies blocking the path to a Body"


def test_a_verb_in_a_value_phrase_still_inflects():
    """
    :class:`Verb` means a finite verb and the morphology pass inflects it wherever it
    appears, so a participial modifier is an :class:`Adjective`, not a ``Verb`` --
    pinned here because the wrong choice reads as *"the bodies blockings the path"*.
    """
    rendered = verbalize_expression(VerbHeadedValue(variable(Body, [])))

    assert rendered == "the bodies blockings the path"


def test_value_phrase_is_not_a_clause():
    """
    A value is a referring expression, so it must not be marked as a subject-led clause
    the way :func:`clause` marks a predicate -- coreference would otherwise read its
    first constituent as a grammatical subject.
    """
    fragment = phrase(Noun.the("bodies"), Prepositions.OF, Noun.the("world"))

    assert not isinstance(fragment, Clause)
