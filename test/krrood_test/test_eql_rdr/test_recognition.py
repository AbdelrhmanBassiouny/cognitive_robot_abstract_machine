"""Tests for the OO recognition layer applied to the semantic-world doubles.

A candidate is an *underspecified view*: ``Drawer.candidates`` returns an underspecified
``Match`` whose construction (through a generative backend) proposes drawer candidates
from a weak structural signal (a container on a prismatic joint, handle optional). A
``Definition`` (a single-class RDR) judges which are genuine, composed as the match's
single ``where``; the ``RecognitionEngine`` constructs and judges through the backend.
Dependent view types (a ``Cabinet`` built from recognized ``Drawer``s) are recognized
after the views their definitions reference.
"""

import sys
import unittest

import pytest

from krrood.entity_query_language.backends import (
    EntityQueryLanguageGenerativeBackend,
)
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.query.match import Match
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
from krrood.entity_query_language.rdr.utils import UNSET

from ..dataset.semantic_world_like_classes import (
    Body,
    Cabinet,
    Container,
    Drawer,
    FixedConnection,
    Handle,
    PrismaticConnection,
    World,
)
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


def _construct(match) -> list:
    """Construct the candidates an underspecified-view match proposes."""
    return list(EntityQueryLanguageGenerativeBackend().evaluate(match))


def _candidates(world):
    return _construct(Drawer.candidates(world))


def _drawer_registry(candidates) -> DefinitionRegistry:
    registry = DefinitionRegistry()
    registry.register(Drawer, _fit_drawer_definition(candidates))
    return registry


def test_candidates_returns_an_underspecified_view(handles_and_containers_world):
    assert isinstance(Drawer.candidates(handles_and_containers_world), Match)


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


def test_recognition_query_is_an_evaluable(handles_and_containers_world):
    registry = _drawer_registry(_candidates(handles_and_containers_world))
    query = RecognitionEngine(registry).recognition_query(
        Drawer, handles_and_containers_world
    )
    assert isinstance(query, Evaluable)


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


def test_definition_explains_why_a_candidate_was_judged(handles_and_containers_world):
    candidates = _candidates(handles_and_containers_world)
    definition = _fit_drawer_definition(candidates)
    by_container = {candidate.container.name: candidate for candidate in candidates}

    genuine = definition.explain(by_container["Container1"])
    assert genuine.conclusion is True
    assert genuine.firing_anchor is not None

    rejected = definition.explain(by_container["Container3"])
    assert rejected.conclusion is UNSET
    assert rejected.firing_anchor is None


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


def _one_drawer_one_cabinet_world() -> World:
    """A world with one prismatic-mounted container (a drawer) inside an outer cabinet body.

    Deliberately starts with empty ``views`` so recognition, not the fixture, populates them.
    """
    world = World(id=-100)
    cabinet_body = Container("CabinetBody", world=world)
    drawer_container = Container(GENUINE_DRAWER_CONTAINER, world=world)
    shelf = Container("Shelf", world=world)
    base = Body("Base", world=world)
    world.bodies = [cabinet_body, drawer_container, shelf, base]
    world.connections = [
        PrismaticConnection(parent=cabinet_body, child=drawer_container, world=world),
        FixedConnection(parent=base, child=cabinet_body, world=world),
        FixedConnection(parent=base, child=shelf, world=world),
    ]
    return world


def _cabinet_definition_expert() -> Expert:
    """Every proposed cabinet (a container holding a recognized drawer) is genuine."""

    def answer(context, requests):
        return {"conditions": context.case_variable.container.name == "CabinetBody"}

    return Expert(interface=FunctionInterface(answer_fn=answer))


def _fit_cabinet_definition(world) -> Definition:
    classifier = EQLSingleClassRDR(Cabinet, "correct")
    # Fit against a cabinet holding the (already recognized) genuine drawer.
    drawer = next(
        candidate
        for candidate in _candidates(world)
        if candidate.container.name == GENUINE_DRAWER_CONTAINER
    )
    cabinet_body = next(b for b in world.bodies if b.name == "CabinetBody")
    genuine_cabinet = Cabinet(container=cabinet_body, drawers=[drawer], world=world)
    classifier.fit_case(
        genuine_cabinet, target=True, expert=_cabinet_definition_expert()
    )
    return Definition(classifier, referenced_conclusions=(Drawer,))


def test_engine_recognizes_dependent_view_from_referenced_conclusions():
    world = _one_drawer_one_cabinet_world()
    registry = DefinitionRegistry()
    registry.register(Cabinet, _fit_cabinet_definition(world))
    registry.register(Drawer, _fit_drawer_definition(_candidates(world)))

    recognized = list(RecognitionEngine(registry).recognize(world))

    drawers = [view for view in recognized if isinstance(view, Drawer)]
    cabinets = [view for view in recognized if isinstance(view, Cabinet)]
    # Drawer is recognized before the Cabinet whose definition references it.
    assert recognized.index(drawers[0]) < recognized.index(cabinets[0])
    # The recognized cabinet was built from the recognized drawer (the forwarded conclusion).
    assert [drawer.container.name for drawer in drawers] == [GENUINE_DRAWER_CONTAINER]
    assert [cabinet.container.name for cabinet in cabinets] == ["CabinetBody"]
    assert cabinets[0].drawers == drawers


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
        candidates = _construct(Drawer.candidates(world))
        classifier = EQLSingleClassRDR(Drawer, "correct")
        for candidate in candidates:
            classifier.fit_case(candidate, expert=Expert(interface=IPythonInterface()))
        registry = DefinitionRegistry()
        registry.register(Drawer, Definition(classifier))
        recognized = list(RecognitionEngine(registry).recognize(world))
        self.assertTrue(all(isinstance(view, Drawer) for view in recognized))
