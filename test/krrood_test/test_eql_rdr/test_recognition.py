"""Tests for the OO recognition layer applied to the semantic-world doubles.

``Drawer.candidates`` over-generates drawer candidates from a weak structural signal
(a container on a prismatic joint, handle optional); a ``Definition`` (a single-class
RDR) judges which are genuine; the ``RecognitionEngine`` composes them into one query.
"""

import sys
import unittest

import pytest

from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.rdr.corner_case import CornerCaseStore
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.recognition.definition import Definition
from krrood.entity_query_language.rdr.recognition.engine import RecognitionEngine
from krrood.entity_query_language.rdr.recognition.exceptions import (
    CyclicDefinitionDependency,
)
from krrood.entity_query_language.rdr.recognition.registry import DefinitionRegistry
from krrood.entity_query_language.rdr.serialization import load_rdr, save_rdr
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from ..dataset.semantic_world_like_classes import Cabinet, Drawer
from ..test_eql.conf.world.handles_and_containers import HandlesAndContainersWorld

GENUINE_DRAWER_CONTAINER = "Container1"
"""Container name of the candidate treated as the genuine drawer in these tests."""


def _drawer_definition_expert() -> Expert:
    """Expert that recognizes the genuine drawer by its container name."""

    def answer(context, requests):
        case_variable = context.case_variable
        return {"conditions": case_variable.container.name == GENUINE_DRAWER_CONTAINER}

    return Expert(interface=FunctionInterface(answer_fn=answer))


def _fit_drawer_definition(candidates) -> Definition:
    classifier = EQLSingleClassRDR(Drawer, "correct")
    genuine = next(
        candidate
        for candidate in candidates
        if candidate.container.name == GENUINE_DRAWER_CONTAINER
    )
    classifier.fit_case(genuine, target=True, expert=_drawer_definition_expert())
    return Definition(classifier)


def _candidates(world):
    return list(Drawer.candidates(world).evaluate())


def _drawer_registry(candidates) -> DefinitionRegistry:
    registry = DefinitionRegistry()
    registry.register(Drawer, _fit_drawer_definition(candidates))
    return registry


def test_candidates_returns_query_not_results(handles_and_containers_world):
    assert isinstance(Drawer.candidates(handles_and_containers_world), Query)


def test_candidates_over_generate_handle_less_drawers(handles_and_containers_world):
    candidates = _candidates(handles_and_containers_world)
    assert all(isinstance(candidate, Drawer) for candidate in candidates)
    # Broadened recall: proposed from the prismatic joint alone, so handles are absent.
    assert all(candidate.handle is None for candidate in candidates)
    assert {candidate.container.name for candidate in candidates} == {
        "Container1",
        "Container3",
    }


def test_definition_judges_only_the_genuine_candidate(handles_and_containers_world):
    candidates = _candidates(handles_and_containers_world)
    definition = _fit_drawer_definition(candidates)
    by_container = {candidate.container.name: candidate for candidate in candidates}
    assert definition.judge(by_container["Container1"]) is True
    assert definition.judge(by_container["Container3"]) is False


def test_recognition_query_is_a_query(handles_and_containers_world):
    registry = _drawer_registry(_candidates(handles_and_containers_world))
    query = RecognitionEngine(registry).recognition_query(
        Drawer, handles_and_containers_world
    )
    assert isinstance(query, Query)


def test_engine_recognizes_only_positively_judged(handles_and_containers_world):
    registry = _drawer_registry(_candidates(handles_and_containers_world))
    recognized = list(
        RecognitionEngine(registry).recognize(handles_and_containers_world)
    )
    assert [drawer.container.name for drawer in recognized] == ["Container1"]


def test_registry_rejects_dependency_cycle():
    drawer_definition = Definition(
        EQLSingleClassRDR(Drawer, "correct"),
        referenced_conclusions=(Cabinet,),
    )
    cabinet_definition = Definition(
        EQLSingleClassRDR(Cabinet, "container"),
        referenced_conclusions=(Drawer,),
    )
    registry = DefinitionRegistry()
    registry.register(Drawer, drawer_definition)
    registry.register(Cabinet, cabinet_definition)
    with pytest.raises(CyclicDefinitionDependency):
        registry.in_dependency_order()


def test_definition_survives_serialization_round_trip(
    handles_and_containers_world, tmp_path
):
    candidates = _candidates(handles_and_containers_world)
    definition = _fit_drawer_definition(candidates)
    # Corner cases are knowledge-acquisition provenance, not needed for inference, and
    # the default serializer cannot emit Symbol-based domain objects (they carry a UUID).
    # Persist only the rule tree; provenance serialization for Symbol domains is future work.
    definition.classifier.corner_cases = CornerCaseStore()
    path = str(tmp_path / "drawer_definition_rdr.py")
    save_rdr(definition.classifier, path)
    reloaded = Definition(load_rdr(path))
    by_container = {candidate.container.name: candidate for candidate in candidates}
    assert reloaded.judge(by_container["Container1"]) is True
    assert reloaded.judge(by_container["Container3"]) is False


def _ipython_available() -> bool:
    try:
        import IPython  # noqa: F401

        return True
    except ImportError:
        return False


@unittest.skipUnless(
    sys.stdin.isatty(),
    "human-interactive: only runs with a real user at a terminal (`pytest -s` in a TTY)",
)
@unittest.skipUnless(_ipython_available(), "IPython not installed")
class TestFitDrawerDefinitionAsHumanExpert(unittest.TestCase):
    """A human expert fits the drawer definition through the real IPython shell.

    The deterministic twin is the ``FunctionInterface``-based tests above; this class
    only runs with a real user at a TTY.
    """

    def test_fit_and_recognize_interactively(self):
        world = HandlesAndContainersWorld().create()
        candidates = list(Drawer.candidates(world).evaluate())
        classifier = EQLSingleClassRDR(Drawer, "correct")
        for candidate in candidates:
            classifier.fit_case(candidate, expert=Expert(interface=IPythonInterface()))
        registry = DefinitionRegistry()
        registry.register(Drawer, Definition(classifier))
        recognized = list(RecognitionEngine(registry).recognize(world))
        self.assertTrue(all(isinstance(view, Drawer) for view in recognized))
