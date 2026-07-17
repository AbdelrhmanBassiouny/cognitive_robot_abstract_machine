"""
Tests for rule codes: :class:`~krrood.entity_query_language.rdr.rule_tree_view.RuleCode` and the
canonical :func:`~krrood.entity_query_language.rdr.serialization.rule_code_map`.

Every rule carries a stable code — its kind letter (``R`` for base/refinement, ``A`` for
alternative) and its emission index (base = ``R0``, then in serialized-file order). The code names
the rule in a why-answer explanation and in a comment above its ``add(...)`` line in the serialized
RDR.
"""

import unittest

from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.rule_tree_view import RuleCode, RuleKindWord
from krrood.entity_query_language.rdr.serialization import rdr_to_python, rule_code_map
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(species: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is species)


def scripted_expert(rules):
    def answer(context, requests):
        return {"conditions": rules[context.target_conclusion](context.case_variable)}

    return Expert(interface=FunctionInterface(answer_fn=answer))


class TestRuleCodeValueObject(unittest.TestCase):
    """
    The code string, and its id-only identity.
    """

    def test_base_reads_r0(self):
        self.assertEqual(RuleCode(0, RuleKindWord.BASE).as_string, "R0")

    def test_refinement_reads_r_with_index(self):
        self.assertEqual(RuleCode(1, RuleKindWord.REFINEMENT).as_string, "R1")

    def test_alternative_reads_a_with_index(self):
        self.assertEqual(RuleCode(2, RuleKindWord.ALTERNATIVE).as_string, "A2")

    def test_identity_is_the_id_alone(self):
        # Same id, different kind → equal (the kind only chooses the display letter).
        self.assertEqual(
            RuleCode(1, RuleKindWord.REFINEMENT), RuleCode(1, RuleKindWord.ALTERNATIVE)
        )
        self.assertEqual(
            hash(RuleCode(1, RuleKindWord.REFINEMENT)),
            hash(RuleCode(1, RuleKindWord.ALTERNATIVE)),
        )

    def test_kind_from_rdr_kind_string(self):
        self.assertIs(RuleKindWord.from_kind("except if"), RuleKindWord.REFINEMENT)
        self.assertIs(RuleKindWord.from_kind("else if"), RuleKindWord.ALTERNATIVE)
        self.assertIs(RuleKindWord.from_kind("if"), RuleKindWord.BASE)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestRuleCodeMap(unittest.TestCase):
    """
    The canonical map: base R0, then codes in emission (serialized-file) order.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        self.fish = first(Species.fish)
        self.mammal = first(Species.mammal)
        self.bird = first(Species.bird)
        # Base fish rule; the mammal refines it; the bird refines it too.
        self.rdr.fit_case(self.fish, Species.fish, expert)
        self.rdr.fit_case(self.mammal, Species.mammal, expert)
        self.rdr.fit_case(self.bird, Species.bird, expert)
        self.codes = rule_code_map(self.rdr.query._conditions_root_)

    def test_base_rule_is_r0(self):
        base_codes = [code.as_string for code in self.codes.values() if code.id == 0]
        self.assertEqual(base_codes, ["R0"])

    def test_codes_are_unique_and_contiguous(self):
        ids = sorted(code.id for code in self.codes.values())
        self.assertEqual(ids, list(range(len(self.codes))))

    def test_the_fired_rule_code_matches_the_answer(self):
        answer = self.rdr.why(self.mammal)
        self.assertEqual(answer.rule_code, self.codes[answer.condition._id_])


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestSerializedRuleComments(unittest.TestCase):
    """
    The serialized RDR carries a code comment above each rule, in file order.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
            }
        )
        self.rdr.fit_case(first(Species.fish), Species.fish, expert)
        self.rdr.fit_case(first(Species.mammal), Species.mammal, expert)
        self.source = rdr_to_python(self.rdr)

    def test_base_comment_precedes_its_rule(self):
        lines = self.source.splitlines()
        base_index = lines.index("    # base rule R0")
        self.assertTrue(lines[base_index + 1].strip().startswith("add("))

    def test_refinement_comment_present(self):
        self.assertIn("# refinement rule R1", self.source)


if __name__ == "__main__":
    unittest.main()
