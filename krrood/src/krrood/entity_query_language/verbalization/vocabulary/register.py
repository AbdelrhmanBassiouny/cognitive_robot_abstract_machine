"""
The register a description is verbalized in.

A *register* captures the two framing choices that depend on *what is being done* with a description
rather than *what it says*: which verb opens it, and which keyword binds its fields. The query register
(the default) opens with *"Find"* / *"Generate"* by the description's specificity and binds fields with
*"given that"*; an imperative register -- a performative act applied to a description -- opens with a fixed
verb (e.g. *"Perform"*) and binds fields with *"such that"*.

Carrying this on the verbalization services (rather than patching the rendered fragment afterwards) lets a
single :class:`~krrood.entity_query_language.verbalization.grammar.match.assembler.MatchAssembler` render
either register, so a new force is a new ``Register`` value, not a new code path (Open/Closed).
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional

from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Directive,
    Keywords,
)
from krrood.entity_query_language.verbalization.vocabulary.words import VocabEnum


@dataclass(frozen=True)
class Register:
    """How a description is framed when verbalized: the opener verb and the field-binding connective."""

    binding_connective: VocabEnum = Keywords.GIVEN_THAT
    """The keyword that introduces the field bindings -- *"given that"* (query) or *"such that"* (imperative)."""

    fixed_opener: Optional[VocabEnum] = None
    """A fixed opener verb (e.g. ``PerformativeDirective.PERFORM``), or ``None`` to choose *"Find"* /
    *"Generate"* by the description's specificity."""

    imperative: bool = False
    """Whether the description is a command -- its finite verb is realised in the bare imperative
    (*"navigate to …"*, not *"navigates to …"*), and the opener is the verb itself."""

    def opener_fragment(self, underspecified: bool) -> VerbalizationFragment:
        """:return: the opener fragment -- the fixed verb, or *"Find"* / *"Generate"* by *underspecified*."""
        if self.fixed_opener is not None:
            return self.fixed_opener.as_fragment()
        return Directive.for_underspecified(underspecified).as_fragment()


QUERY_REGISTER = Register()
"""The default register: *"Find"* / *"Generate"* openers and *"given that"* field bindings."""
