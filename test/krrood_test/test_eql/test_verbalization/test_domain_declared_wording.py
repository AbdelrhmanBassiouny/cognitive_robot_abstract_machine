"""
Tests for the two ways a domain class states its own wording: a value that says what it
is called, and a field that is the whole of what its owner is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Optional

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.verbalization.fragments.base import (
    RoleFragment,
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.grammar_metadata import GrammarMetadata
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.self_naming_value import SelfNamingValue

# %% a value that says what it is called


@dataclass
class _Shade(SelfNamingValue):
    """
    A measured colour, which has a word of its own however it was measured.
    """

    red: float
    green: float
    blue: float

    def _verbalization_noun_phrase_(self) -> VerbalizationFragment:
        return RoleFragment(text="cyan", role=SemanticRole.LITERAL)


@dataclass
class _Measurement:
    """
    A reading with no word of its own, so it is named by its type.
    """

    reading: float


@dataclass
class _Sample:
    """
    A thing the two kinds of value are read off.
    """

    shade: _Shade
    measurement: _Measurement


def test_a_value_that_says_what_it_is_called_is_said_by_that_name():
    """
    A value naming itself is said by that name rather than by its type.
    """
    sample = variable(_Sample, [])
    assert (
        verbalize_expression(sample.shade == _Shade(0.0, 1.0, 1.0))
        == "the shade of a _Sample is cyan"
    )


def test_a_value_with_no_name_of_its_own_is_still_said_by_its_type():
    """
    Naming itself is the exception: a value that does not is named by its identity, as
    before.
    """
    sample = variable(_Sample, [])
    assert (
        verbalize_expression(sample.measurement == _Measurement(1.0))
        == "the measurement of a _Sample is a specific _Measurement"
    )


# %% a field that is the whole of what its owner is


@dataclass
class _Label:
    """
    A word, together with the namespace telling it from an equal word elsewhere.
    """

    text: str = field(
        metadata=GrammarMetadata(stands_for_its_owner=True).as_dict(),
    )
    namespace: Optional[str] = None


@dataclass
class _Part:
    """
    A thing wearing such a label.
    """

    label: _Label


def test_the_wrapped_value_is_said_as_the_wrapper_itself():
    """
    Reading the field a wrapper stands for says the wrapper and stops, rather than
    saying the same word twice.
    """
    part = variable(_Part, [])
    assert (
        verbalize_expression(part.label.text == "handle")
        == "the label of a _Part is 'handle'"
    )


def test_the_wrapper_keeps_saying_its_other_fields():
    """
    Only the field standing for the whole is elided; the rest still name themselves.
    """
    part = variable(_Part, [])
    assert (
        verbalize_expression(part.label.namespace == "door")
        == "the namespace of the label of a _Part is 'door'"
    )


def test_a_wrapper_reached_by_nothing_still_says_its_field():
    """
    A wrapper that is itself what is being asked about has no hop to fold into, so the
    field is said.
    """
    label = variable(_Label, [])
    assert (
        verbalize_expression(label.text == "handle")
        == "the text of a _Label is 'handle'"
    )


def test_a_whole_wrapper_given_as_a_value_is_said_by_what_it_stands_for():
    """
    A wrapper given whole as a value is said by the field it stands for, the same way a
    chain reading that field says the wrapper.
    """
    part = variable(_Part, [])
    assert (
        verbalize_expression(part.label == _Label("handle", "door"))
        == "the label of a _Part is 'handle'"
    )


def test_a_restriction_on_the_wrapped_value_is_said_of_the_subject_itself():
    """
    A restriction reading one hop of the subject is said on the subject noun, and
    eliding the wrapper's field makes this one: the hop that is said is the wrapper.
    """
    part = variable(_Part, [])
    assert (
        verbalize_expression(an(entity(part).where(part.label.text == "handle")))
        == "Find a _Part whose label is 'handle'"
    )


def test_a_restriction_reaching_past_the_wrapper_is_still_said_on_its_own():
    """
    A restriction that really is two hops keeps its own clause, since the subject noun
    cannot carry it.
    """
    part = variable(_Part, [])
    assert (
        verbalize_expression(an(entity(part).where(part.label.namespace == "door")))
        == "Find a _Part such that the namespace of its label is 'door'"
    )
