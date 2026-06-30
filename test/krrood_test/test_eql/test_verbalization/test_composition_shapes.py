from __future__ import annotations

from krrood.entity_query_language.verbalization.composition import (
    concurrent,
    coordinate,
    interleave,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    WordFragment,
    flatten_fragment_to_plain_text,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Adverbs,
    Conjunctions,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import Verb


def _render(fragment) -> str:
    return flatten_fragment_to_plain_text(fragment)


def _leaves(*texts: str):
    return [WordFragment(text=text) for text in texts]


def test_interleave_places_connective_before_each_later_child():
    text = _render(interleave(_leaves("a", "b", "c"), Adverbs.THEN))
    assert text == "a, then b, then c"


def test_interleave_with_lead_opens_with_the_lead_word():
    text = _render(
        interleave(_leaves("a", "b"), Adverbs.OTHERWISE, lead=Verb("try").as_fragment())
    )
    assert text == "try a, otherwise b"


def test_coordinate_joins_with_oxford_comma_lead_and_tail():
    text = _render(
        coordinate(
            _leaves("a", "b", "c"),
            Conjunctions.OR,
            lead=Verb("try").as_fragment(),
            tail=Adverbs.SIMULTANEOUSLY.as_fragment(),
        )
    )
    assert text == "try a, b, or c simultaneously"


def test_concurrent_states_the_rest_as_while_simultaneously_clauses():
    text = _render(concurrent(_leaves("a", "b")))
    assert text == "a, while simultaneously b"


def test_concurrent_of_a_single_child_is_just_that_child():
    text = _render(concurrent(_leaves("a")))
    assert text == "a"
