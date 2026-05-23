"""
Phase 4 tests: IPythonExpert (interactive expert) with an injected shell runner.

The real expert opens an embedded IPython shell; here we inject a stub runner that
plays the expert's part — building a live EQL condition expression from the namespace
the expert is given. This exercises namespace construction, scope capture, the
live-object answer contract, and integration with fit_case.
"""

import dataclasses
import unittest

from krrood.entity_query_language.rdr.interactive import (
    ANSWER_NAME,
    IPythonExpert,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()

FEATURE_FIELDS = [
    f.name for f in dataclasses.fields(Animal) if f.name not in ("name", "species")
]

USER_SCOPE_SENTINEL = "phase4_sentinel"


def first(sp: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is sp)


def maximally_specific_runner(captured=None):
    """A stub shell runner that assigns a full-feature-vector condition.

    Builds the condition with the EQL `and_` taken *from the namespace* (proving the
    factories were injected) over the case variable, matching the case's features.
    """

    def run(namespace, header):
        if captured is not None:
            captured["namespace"] = namespace
            captured["header"] = header
        case = namespace["case"]
        animal_var = namespace["animal"]
        and_ = namespace["and_"]
        namespace[ANSWER_NAME] = and_(
            *[getattr(animal_var, f) == getattr(case, f) for f in FEATURE_FIELDS]
        )

    return run


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestIPythonExpert(unittest.TestCase):
    def test_namespace_has_factories_case_and_variable(self):
        captured = {}
        expert = IPythonExpert(shell_runner=maximally_specific_runner(captured))
        rdr = EQLSingleClassRDR(Animal, "species")
        case = first(Species.mammal)
        expert.ask_for_conditions(case, None, Species.mammal, rdr.case_variable)

        ns = captured["namespace"]
        # EQL factories present.
        for verb in ("entity", "variable", "and_", "refinement", "alternative", "add"):
            self.assertIn(verb, ns)
        # Case variable exposed under a friendly name, plus the case itself.
        self.assertIn("animal", ns)
        self.assertIs(ns["animal"], rdr.case_variable)
        self.assertIs(ns["case"], case)

    def test_header_mentions_case_target_and_answer_name(self):
        captured = {}
        expert = IPythonExpert(shell_runner=maximally_specific_runner(captured))
        rdr = EQLSingleClassRDR(Animal, "species")
        expert.ask_for_conditions(
            first(Species.bird), Species.mammal, Species.bird, rdr.case_variable
        )
        header = captured["header"]
        self.assertIn(ANSWER_NAME, header)
        self.assertIn("bird", header.lower())
        self.assertIn("animal", header)

    def test_returns_live_eql_expression(self):
        from krrood.entity_query_language.core.base_expressions import (
            SymbolicExpression,
        )

        expert = IPythonExpert(shell_runner=maximally_specific_runner())
        rdr = EQLSingleClassRDR(Animal, "species")
        cond = expert.ask_for_conditions(
            first(Species.mammal), None, Species.mammal, rdr.case_variable
        )
        # A live EQL object, not a string.
        self.assertIsInstance(cond, SymbolicExpression)
        self.assertNotIsInstance(cond, str)

    def test_missing_answer_raises(self):
        def run_without_answer(namespace, header):
            pass  # expert "forgot" to assign conditions

        expert = IPythonExpert(shell_runner=run_without_answer)
        rdr = EQLSingleClassRDR(Animal, "species")
        with self.assertRaises(NoConditionsProvided):
            expert.ask_for_conditions(
                first(Species.mammal), None, Species.mammal, rdr.case_variable
            )

    def test_captures_user_definition_scope(self):
        # A name defined where the RDR is created must reach the expert's namespace.
        phase4_sentinel = USER_SCOPE_SENTINEL  # noqa: F841
        rdr = EQLSingleClassRDR(Animal, "species")
        captured = {}
        expert = IPythonExpert(shell_runner=maximally_specific_runner(captured))
        expert.ask_for_conditions(
            first(Species.mammal), None, Species.mammal, rdr.case_variable
        )
        self.assertEqual(
            captured["namespace"].get("phase4_sentinel"), USER_SCOPE_SENTINEL
        )

    def test_fit_through_interactive_expert(self):
        # The interactive expert drives fit end to end via the injected runner.
        expert = IPythonExpert(shell_runner=maximally_specific_runner())
        rdr = EQLSingleClassRDR(Animal, "species")
        subset = list(zip(animals, targets))[:15]
        for case, target in subset:
            rdr.fit_case(case, target, expert)
        for case, target in subset:
            self.assertEqual(rdr.classify(case), target, case.name)


if __name__ == "__main__":
    unittest.main()
