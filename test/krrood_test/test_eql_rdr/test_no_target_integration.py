"""
Phase 6 integration tests for no-ground-truth (ask-for-rule) fitting.

Exercises the conclusion-asking path end-to-end across the three domain shapes the
resolver distinguishes — an enumerable Enum (zoo ``Species``), an enumerable ``bool``,
and an open ``str`` — through both the programmatic :class:`FunctionInterface` and a
stubbed :class:`IPythonInterface` shell, and confirms a tree grown entirely in this mode
serialises and round-trips.
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
    NamespaceName,
)
import dataclasses
import os
import tempfile
import unittest

from dataclasses import dataclass

from typing_extensions import Optional

from krrood.entity_query_language.factories import and_
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.interface import (
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import load_rdr, save_rdr
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()

FEATURE_FIELDS = [
    f.name for f in dataclasses.fields(Animal) if f.name not in ("name", "species")
]


def first(species: Species) -> Animal:
    """
    :param species: The species to find a case for.
    :return: The first zoo animal whose target species is ``species``.
    """
    return next(animal for animal, target in zip(animals, targets) if target is species)


# %% synthetic case types exercising the bool and open conclusion domains


@dataclass
class Door:
    """A case whose conclusion attribute is a bool, an enumerable domain of two."""

    open_sensor: bool
    """Whether the door's sensor reads open."""

    locked: bool
    """Whether the door is locked."""

    state: Optional[bool] = None
    """The conclusion the RDR predicts."""


@dataclass
class Shape:
    """A case whose conclusion attribute is a string, an open domain."""

    sides: int
    """How many sides the shape has."""

    rounded: bool
    """Whether its corners are rounded."""

    kind: Optional[str] = None
    """The conclusion the RDR predicts."""


def _match_features(case_variable, case, fields):
    """
    :param case_variable: The shared EQL variable to build the condition over.
    :param case: The concrete case whose feature values to match.
    :param fields: The field names to include in the condition.
    :return: A conjunction pinning every named field to the case's own value.
    """
    return and_(*[getattr(case_variable, f) == getattr(case, f) for f in fields])


def _labelling_function_expert(label_of, fields) -> Expert:
    """
    A FunctionInterface expert that labels each case and justifies it by its full
    vector.
    """

    def answer(context, requests):
        """Label the case, and justify the label with its full feature vector."""
        result = {
            AnswerName.CONDITIONS: _match_features(
                context.case_variable, context.case_instance, fields
            )
        }
        if any(r.name == AnswerName.CONCLUSION for r in requests):
            result[AnswerName.CONCLUSION] = label_of(context.case_instance)
        return result

    return Expert(interface=FunctionInterface(answer_function=answer))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestNoTargetEnumEndToEnd(unittest.TestCase):
    """Labelling a case whose conclusion is an enum, end to end."""

    def test_zoo_no_target_fit_classifies_every_species(self):
        """Every zoo case is classified as the expert labelled it."""
        label_of = {a.name: t for a, t in zip(animals, targets)}
        subset = list(zip(animals, targets))[:20]
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = _labelling_function_expert(
            lambda case: label_of[case.name], FEATURE_FIELDS
        )
        for case, _ in subset:
            rdr.fit_case(case, expert=expert)
        for case, target in subset:
            self.assertEqual(rdr.classify(case), target, case.name)


class TestNoTargetBoolEndToEnd(unittest.TestCase):
    """Labelling a case whose conclusion is a bool, end to end."""

    def test_bool_conclusion_no_target_fit(self):
        """A bool conclusion is labelled and reproduced."""
        doors = [
            Door(open_sensor=True, locked=False),
            Door(open_sensor=False, locked=True),
        ]
        rdr = EQLSingleClassRDR(Door, "state")
        # The domain resolves to an enumerable bool, allowing True / False.
        self.assertTrue(rdr.conclusion_domain.is_enumerable)
        self.assertEqual(set(rdr.conclusion_domain.members), {True, False})

        expert = _labelling_function_expert(
            lambda door: door.open_sensor, ["open_sensor", "locked"]
        )
        for door in doors:
            rdr.fit_case(door, expert=expert)
        self.assertEqual(rdr.classify(doors[0]), True)
        self.assertEqual(rdr.classify(doors[1]), False)


class TestNoTargetOpenStrEndToEnd(unittest.TestCase):
    """Labelling a case whose conclusion is an open string, end to end."""

    def test_str_conclusion_no_target_fit(self):
        """An open string conclusion is labelled and reproduced."""
        shapes = [Shape(sides=3, rounded=False), Shape(sides=0, rounded=True)]
        kind_of = {id(shapes[0]): "triangle", id(shapes[1]): "circle"}
        rdr = EQLSingleClassRDR(Shape, "kind")
        # The open (str) domain is not enumerable; the validator type-checks instead.
        self.assertFalse(rdr.conclusion_domain.is_enumerable)
        self.assertEqual(rdr.conclusion_domain.expected_types, (str,))

        expert = _labelling_function_expert(
            lambda shape: kind_of[id(shape)], ["sides", "rounded"]
        )
        for shape in shapes:
            rdr.fit_case(shape, expert=expert)
        self.assertEqual(rdr.classify(shapes[0]), "triangle")
        self.assertEqual(rdr.classify(shapes[1]), "circle")


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestNoTargetSerializationRoundTrip(unittest.TestCase):
    """A tree grown by labelling survives being written out and read back."""

    def test_mode2_grown_tree_roundtrips(self):
        """A round-tripped tree classifies exactly as the original did."""
        label_of = {a.name: t for a, t in zip(animals, targets)}
        subset = list(zip(animals, targets))[:12]
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = _labelling_function_expert(
            lambda case: label_of[case.name], FEATURE_FIELDS
        )
        for case, _ in subset:
            rdr.fit_case(case, expert=expert)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mode2_model.py")
            save_rdr(rdr, path)
            loaded = load_rdr(path)
        for case, _ in subset:
            self.assertEqual(rdr.classify(case), loaded.classify(case), case.name)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestNoTargetThroughInteractiveShell(unittest.TestCase):
    """The two-question labelling flow driven through the shell itself."""

    def test_stubbed_ipython_shell_drives_no_target_fit(self):
        """
        The two sequential questions (conclusion, then conditions) are answered via the
        injected shell runner, proving the interactive mechanism works for the no-target
        path.
        """
        label_of = {a.name: t for a, t in zip(animals, targets)}

        def runner(namespace, header):
            """Answer whichever of the two questions the namespace is posing."""
            if AnswerName.CONCLUSION in namespace:
                case = namespace[NamespaceName.CASE_INSTANCE]
                namespace[AnswerName.CONCLUSION] = label_of[case.name]
            if AnswerName.CONDITIONS in namespace:
                case = namespace[NamespaceName.CASE_INSTANCE]
                case_variable = namespace[NamespaceName.CASE_VARIABLE]
                build_and = namespace[and_.__name__]
                namespace[AnswerName.CONDITIONS] = build_and(
                    *[
                        getattr(case_variable, f) == getattr(case, f)
                        for f in FEATURE_FIELDS
                    ]
                )

        expert = Expert(interface=IPythonInterface(shell_runner=runner))
        rdr = EQLSingleClassRDR(Animal, "species")
        subset = list(zip(animals, targets))[:10]
        for case, _ in subset:
            rdr.fit_case(case, expert=expert)
        for case, target in subset:
            self.assertEqual(rdr.classify(case), target, case.name)


if __name__ == "__main__":
    unittest.main()
