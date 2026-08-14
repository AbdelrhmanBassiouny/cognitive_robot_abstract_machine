"""
The opening verb (performative) of a verbalized query depends on the *backend* it would
be evaluated with, not only on the query type: a generative backend reads *"Generate"*,
a selective backend reads *"Find"*.

With no backend the verb falls back to the query-type default (a match generates, a
plain query finds), so all existing output is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.backends import (
    EntityQueryLanguageBackend,
    ProbabilisticBackend,
)
from typing_extensions import Optional

from krrood.entity_query_language.factories import entity, a, an, the, variable
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.pipeline import (
    directive_for_backend,
    verbalize_expression,
    VerbalizationPipeline,
)
from krrood.entity_query_language.verbalization.vocabulary.english import Directive


@dataclass
class Position:
    """
    A minimal structural type to build a match over.
    """

    x: float
    y: float
    z: float


def test_match_without_backend_defaults_to_generate():
    """
    With no backend the query-type default holds: a match reads *"Generate"*.
    """
    assert verbalize_expression(a(Position)(x=1)).startswith("Generate")


def test_match_with_selective_backend_reads_find():
    """
    A selective backend turns the match's verb into *"Find"* (it searches existing
    data).
    """
    text = verbalize_expression(a(Position)(x=1), backend=EntityQueryLanguageBackend())
    assert text.startswith("Find")


def test_match_with_generative_backend_reads_generate():
    """
    A generative backend keeps the match's verb as *"Generate"*.
    """
    text = verbalize_expression(a(Position)(x=1), backend=ProbabilisticBackend())
    assert text.startswith("Generate")


def test_query_without_backend_defaults_to_find():
    """
    With no backend a plain query reads *"Find"* as before.
    """
    robot = variable(Position, [])
    assert verbalize_expression(entity(robot)).startswith("Find")


def test_query_with_generative_backend_reads_generate():
    """
    A generative backend turns a plain query's verb into *"Generate"*.
    """
    robot = variable(Position, [])
    text = verbalize_expression(entity(robot), backend=ProbabilisticBackend())
    assert text.startswith("Generate")


def test_query_with_selective_backend_reads_find():
    """
    A selective backend keeps a plain query's verb as *"Find"*.
    """
    robot = variable(Position, [])
    text = verbalize_expression(entity(robot), backend=EntityQueryLanguageBackend())
    assert text.startswith("Find")


# ── every entry point takes the backend ──────────────────────────────────────


@dataclass
class DisplayRecordingPipeline(VerbalizationPipeline):
    """
    A pipeline that records what it would show instead of showing it, so the display
    entry point can be exercised without a browser or a notebook.
    """

    displayed: Optional[str] = None
    """
    The text the last ``display`` call produced, or ``None`` before the first one.
    """

    def display_fragment(self, fragment: VerbalizationFragment) -> None:
        self.displayed = self.verbalize_fragment(fragment)


def test_display_honours_the_backend():
    """
    ``display`` resolves the opening verb from the backend, exactly as ``verbalize``
    does.
    """
    pipeline = DisplayRecordingPipeline()
    pipeline.display(a(Position)(x=1), backend=EntityQueryLanguageBackend())
    assert pipeline.displayed.startswith("Find")


def test_display_says_the_same_thing_as_verbalize():
    """
    The two entry points differ only in where the text goes, so a match reads the same
    through either — including the query-building ``verbalize`` performs.
    """
    backend = EntityQueryLanguageBackend()
    pipeline = DisplayRecordingPipeline()
    pipeline.display(the(Position), backend=backend)
    assert pipeline.displayed == VerbalizationPipeline.plain().verbalize(
        the(Position), backend=backend
    )


def test_display_shares_services_across_calls():
    """
    Passing the same services to ``display`` makes a repeat mention corefer, as it does
    for ``verbalize``.
    """
    services = MicroplanningServices()
    pipeline = DisplayRecordingPipeline()
    position = variable(Position, [])
    pipeline.display(position, services)
    first = pipeline.displayed
    pipeline.display(position, services)
    assert (first, pipeline.displayed) == ("a Position", "the Position")


def test_directive_for_backend_maps_backend_kind_to_verb():
    """
    The resolver maps backend kind to a directive, and ``None`` to no override.
    """
    assert directive_for_backend(None) is None
    assert directive_for_backend(ProbabilisticBackend()) is Directive.GENERATE
    assert directive_for_backend(EntityQueryLanguageBackend()) is Directive.FIND
