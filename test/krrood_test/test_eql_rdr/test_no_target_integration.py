"""
Phase 6 integration tests for no-ground-truth (ask-for-rule) fitting.

Exercises the conclusion-asking path end-to-end across the three domain shapes the resolver
distinguishes — an enumerable Enum (zoo ``Species``), an enumerable ``bool``, and an open
``str`` — through both the programmatic :class:`FunctionInterface` and a stubbed
:class:`IPythonInterface` shell, and confirms a tree grown entirely in this mode serialises
and round-trips.
"""

from __future__ import annotations

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
    CASE_INSTANCE_NAME,
    CASE_VARIABLE_NAME,
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


def first(sp: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is sp)


# --- synthetic case types exercising the bool and open (str) conclusion domains -----------


@dataclass
class Door:
    open_sensor: bool
    locked: bool
    state: Optional[bool] = None  # enumerable bool conclusion


@dataclass
class Shape:
    sides: int
    rounded: bool
    kind: Optional[str] = None  # open (str) conclusion


def _match_features(case_variable, case, fields):
    return and_(*[getattr(case_variable, f) == getattr(case, f) for f in fields])


def _labelling_function_expert(label_of, fields) -> Expert:
    """A FunctionInterface expert that labels each case and justifies it by its full vector."""

    def answer(context, requests):
        result = {
            "conditions": _match_features(
                context.case_variable, context.case_instance, fields
            )
        }
        if any(r.name == "conclusion" for r in requests):
            result["conclusion"] = label_of(context.case_instance)
        return result

    return Expert(interface=FunctionInterface(answer_fn=answer))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestNoTargetEnumEndToEnd(unittest.TestCase):
    def test_zoo_no_target_fit_classifies_every_species(self):
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
    def test_bool_conclusion_no_target_fit(self):
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
    def test_str_conclusion_no_target_fit(self):
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
    def test_mode2_grown_tree_roundtrips(self):
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
    def test_stubbed_ipython_shell_drives_no_target_fit(self):
        """The two sequential questions (conclusion, then conditions) are answered via the
        injected shell runner, proving the interactive mechanism works for the no-target path.
        """
        label_of = {a.name: t for a, t in zip(animals, targets)}

        def runner(namespace, header):
            # Separate namespaces per question: only the asked answer name is present.
            if "conclusion" in namespace:
                case = namespace[CASE_INSTANCE_NAME]
                namespace["conclusion"] = label_of[case.name]
            if "conditions" in namespace:
                case = namespace[CASE_INSTANCE_NAME]
                case_variable = namespace[CASE_VARIABLE_NAME]
                build_and = namespace["and_"]
                namespace["conditions"] = build_and(
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
