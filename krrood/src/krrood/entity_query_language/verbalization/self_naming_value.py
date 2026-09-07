"""
The hook by which a domain value says what it is called.

A concrete object used as a value is otherwise named by its identity alone (*"a specific
Color"*), because its ``repr`` can be arbitrarily large and says nothing a reader wants.
A value that has a word of its own supplies it here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)


class SelfNamingValue(ABC):
    """
    A value that says what it is called, rather than being named by its type.

    Its counterpart for an *operation* is
    :class:`~krrood.entity_query_language.predicate.Verbalizable`, which reads a predicate
    or function from the fragments of its already-rendered fields. A value has no fields
    to render -- it is the thing being said -- so it answers for itself.
    """

    @abstractmethod
    def _verbalization_noun_phrase_(self) -> VerbalizationFragment:
        """
        :return: The noun phrase this value reads as.
        """
