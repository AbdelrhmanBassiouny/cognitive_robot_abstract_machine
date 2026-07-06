"""
Tests for the textual rule-tree visualization (``rdr/rule_tree_view.py``).

Covers the four independent pieces — model walk, status resolution, compact formatting,
and elided rendering — plus the end-to-end render off a real classification trace and the
interactive header integration.
"""

import unittest
from pathlib import Path

from colorama import Fore

from krrood.entity_query_language.factories import (
    add,
    alternative,
    entity,
    not_,
    refinement,
    variable,
    and_,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.observer import trace_case
from krrood.entity_query_language.rdr.serialization import load_rdr
from krrood.entity_query_language.rdr.utils import UNSET, _conclusions_of
from krrood.entity_query_language.rules.conclusion_selector import Alternative
from krrood.entity_query_language.rdr.rule_tree_view import (
    RuleStatus,
    RuleTreeRenderer,
    RuleView,
    enforce_parent_consistency,
    format_condition,
    format_conclusion,
    render_rule_tree,
    resolve_status,
    walk_rules,
)

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(sp: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is sp)


def _flat_tree():
    """milk -> mammal ; else feathers -> bird ; else fins -> fish."""
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.milk == True)
    with query:
        add(animal.species, Species.mammal)
        with alternative(animal.feathers == True):
            add(animal.species, Species.bird)
        with alternative(animal.fins == True):
            add(animal.species, Species.fish)
    query.build()
    return animal, query


def _refined_tree():
    """backbone -> fish (default); except if milk -> mammal."""
    animal = variable(Animal, domain=[])
    query = entity(animal).where(animal.backbone == True)
    with query:
        add(animal.species, Species.fish)
        with refinement(animal.milk == True):
            add(animal.species, Species.mammal)
    query.build()
    return animal, query


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWalkRules(unittest.TestCase):
    def test_alternatives_are_siblings_at_depth_zero(self):
        _, query = _flat_tree()
        rules = walk_rules(query._conditions_root_)
        self.assertEqual([r.depth for r in rules], [0, 0, 0])
        self.assertEqual([r.kind for r in rules], ["if", "else if", "else if"])
        self.assertEqual(
            [format_conclusion(r.conclusions[0]) for r in rules],
            ["species = mammal", "species = bird", "species = fish"],
        )

    def test_refinement_nests_one_level_deeper(self):
        _, query = _refined_tree()
        rules = walk_rules(query._conditions_root_)
        self.assertEqual([r.depth for r in rules], [0, 1])
        self.assertEqual([r.kind for r in rules], ["if", "except if"])


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestFormatting(unittest.TestCase):
    def test_condition_is_compact_and_prefix_stripped(self):
        _, query = _refined_tree()
        rules = walk_rules(query._conditions_root_)
        self.assertEqual(format_condition(rules[0].condition), "backbone == true")
        self.assertEqual(format_condition(rules[1].condition), "milk == true")

    def test_conjunction_joined_with_and(self):
        animal = variable(Animal, domain=[])
        cond = and_(animal.milk == True, animal.legs == 4)
        self.assertEqual(format_condition(cond), "milk == true and legs == 4")

    def test_conclusion_renders_attribute_and_enum_value(self):
        _, query = _refined_tree()
        rules = walk_rules(query._conditions_root_)
        self.assertEqual(format_conclusion(rules[0].conclusions[0]), "species = fish")
        self.assertEqual(format_conclusion(rules[1].conclusions[0]), "species = mammal")


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestConclusionDeduplication(unittest.TestCase):
    """Phase 1: semantic equality on Conclusion prevents duplicates in _conclusions_ sets."""

    def test_same_attribute_same_value_deduplicates(self):
        """Same cached Attribute in two branches → only one Add in _conclusions_."""
        animal = variable(Animal, domain=[])
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
            with alternative(animal.feathers):
                add(animal.species, Species.bird)
            with alternative(animal.feathers):
                add(animal.species, Species.bird)
        query.build()

        # Both alternatives use the same cached feathers node → _conclusions_of should
        # return exactly one Add per semantic conclusion.
        rules = walk_rules(query._conditions_root_)
        for r in rules:
            self.assertEqual(
                len(r.conclusions),
                1,
                f"{format_condition(r.condition)} has {len(r.conclusions)} conclusions: "
                f"{[format_conclusion(c) for c in r.conclusions]}",
            )

    def test_same_node_clone_branches(self):
        """Simulate a node appearing as both a refinement and an alternative
        (shared node scenario). The clone should have distinct Add objects, but
        _conclusions_of on the original node should have only one Add if the same
        conclusion was added twice to it."""
        animal = variable(Animal, domain=[])
        feathers = animal.feathers  # Same cached node
        tree = entity(animal).where(animal.milk == True)
        with tree:
            add(animal.species, Species.mammal)
            with alternative(feathers == True):
                add(animal.species, Species.bird)
        tree.build()

        rules = walk_rules(tree._conditions_root_)
        for r in rules:
            self.assertEqual(
                len(r.conclusions),
                1,
                f"{format_condition(r.condition)} has {len(r.conclusions)} conclusions",
            )


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestInsertAtCloning(unittest.TestCase):
    """Phase 2: ``insert_at`` clones parented condition nodes to prevent node-sharing."""

    def test_fresh_expression_clones_with_new_id_and_no_parent(self):
        from krrood.entity_query_language.rules.conclusion_selector import _fresh_expression

        animal = variable(Animal, domain=[])
        cond = animal.milk == True
        original_id = cond._id_

        clone = _fresh_expression(cond)
        self.assertNotEqual(clone._id_, original_id)
        self.assertIsNone(clone._parent_)
        # Children are shared shallowly (same object references)
        self.assertIs(clone.left, cond.left)
        self.assertIs(clone.right, cond.right)

    def test_insert_at_clones_condition_that_already_has_parent(self):
        """insert_at clones the *condition* (not anchor) when it already lives in the tree."""
        animal = variable(Animal, domain=[])

        # Build: milk → mammal ; alternative(feathers) → bird
        query = entity(animal).where(animal.milk == True)
        with query:
            add(animal.species, Species.mammal)
            with alternative(animal.feathers == True):
                add(animal.species, Species.bird)
        query.build()

        rules = walk_rules(query._conditions_root_)
        milk = [r for r in rules if 'milk' in format_condition(r.condition)][0].condition
        feathers = [r for r in rules if 'feathers' in format_condition(r.condition)][0].condition

        # The feathers condition is a non-root tree node — it has a parent.
        original_id = feathers._id_
        original_parent = feathers._parent_
        self.assertIsNotNone(original_parent)

        # insert_at with milk as anchor, feathers as the "resolver-suggested" condition.
        # feathers has a parent → should be cloned.
        new_cond = Alternative.insert_at(milk, feathers)

        # The original feathers node must be untouched (the clone is what's used).
        self.assertEqual(feathers._id_, original_id)
        self.assertIs(feathers._parent_, original_parent)

        # The returned condition is the clone — different identity.
        self.assertNotEqual(new_cond._id_, original_id)

        # walk_rules must not contain duplicate condition IDs.
        rules = walk_rules(query._conditions_root_)
        ids = [r.condition._id_ for r in rules]
        self.assertEqual(len(ids), len(set(ids)),
                         f"duplicate condition IDs: {ids}")


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestStatusResolution(unittest.TestCase):
    def _statuses(self, query, animal, case):
        rules = walk_rules(query._conditions_root_)
        trace = trace_case(query, animal, animal.species, case, query._conditions_root_)
        return trace, {
            format_conclusion(r.conclusions[0]): resolve_status(
                r, trace.satisfied_condition_ids, trace.evaluated_expression_ids
            )
            for r in rules
        }

    def test_fired_rule_is_green_status(self):
        animal, query = _refined_tree()
        trace, status = self._statuses(query, animal, first(Species.mammal))
        self.assertEqual(trace.conclusion, Species.mammal)
        # The mammal refinement fired; its backbone parent was satisfied too.
        self.assertEqual(status["species = mammal"], RuleStatus.FIRED)
        self.assertEqual(status["species = fish"], RuleStatus.FIRED)

    def test_evaluated_but_not_fired_is_red_status(self):
        animal, query = _refined_tree()
        # A fish: backbone holds (fires) but milk does not (evaluated, not fired).
        _, status = self._statuses(query, animal, first(Species.fish))
        self.assertEqual(status["species = fish"], RuleStatus.FIRED)
        self.assertEqual(status["species = mammal"], RuleStatus.EVALUATED_NOT_FIRED)

    def test_short_circuited_branch_is_grey_status(self):
        animal, query = _refined_tree()
        # An insect lacks a backbone: the parent is evaluated-false, so the milk
        # refinement is never evaluated at all.
        _, status = self._statuses(query, animal, first(Species.insect))
        self.assertEqual(status["species = fish"], RuleStatus.EVALUATED_NOT_FIRED)
        self.assertEqual(status["species = mammal"], RuleStatus.NOT_EVALUATED)

    def test_refinement_with_not_condition_parent_is_green(self):
        """``not_(x)`` as a refinement condition must propagate the parent rule's green status.

        ``Not._evaluate__`` passes its child result as the ``previous_operation_result``
        so the satisfaction-tracking chain reaches ancestor conditions.
        """
        # backbone → fish (base rule); except if not_(milk) → molusc (refinement).
        # For a fish (backbone=True, milk=False): backbone fires (green), not_(milk)=True so
        # molusc refinement also fires.  Both rules must be green.
        animal_var = variable(Animal, domain=[])
        query = entity(animal_var).where(animal_var.backbone == True)
        with query:
            add(animal_var.species, Species.fish)
            with refinement(not_(animal_var.milk)):
                add(animal_var.species, Species.molusc)
        query.build()

        fish_case = first(Species.fish)  # backbone=True, milk=False
        rules = walk_rules(query._conditions_root_)
        trace = trace_case(
            query, animal_var, animal_var.species, fish_case, query._conditions_root_
        )
        status = {
            format_conclusion(r.conclusions[0]): resolve_status(
                r, trace.satisfied_condition_ids, trace.evaluated_expression_ids
            )
            for r in rules
        }
        self.assertEqual(trace.conclusion, Species.molusc)
        # The not_(milk) refinement fired; its backbone parent must also be green.
        self.assertEqual(status["species = molusc"], RuleStatus.FIRED)
        self.assertEqual(status["species = fish"], RuleStatus.FIRED)

    def test_no_green_child_with_red_visual_parent_in_full_zoo_model(self):
        """Integration: every fired except-if in the zoo model has a green visual parent.

        A green "except if" with a red "if/else if" immediately above it at the next
        shallower depth would be a visual lie (Refinement can only evaluate its right
        branch when its left branch already fired).
        """
        model_path = Path(__file__).parent / "fitted_models" / "zoo_species_rdr.py"
        if not model_path.exists():
            self.skipTest("human-fitted zoo model not yet committed")

        rdr = load_rdr(str(model_path))
        for animal_case, _ in zip(animals, targets):
            trace = rdr._trace(animal_case)
            rules = walk_rules(trace.rule_tree_root)
            statuses = [
                resolve_status(
                    r, trace.satisfied_condition_ids, trace.evaluated_expression_ids
                )
                for r in rules
            ]
            # Phase 3: correct display for shared-node models — a refinement whose
            # visual parent didn't fire is shown as NOT_EVALUATED.
            statuses = enforce_parent_consistency(statuses, rules)
            for i, rule in enumerate(rules):
                if rule.depth == 0 or statuses[i] != RuleStatus.FIRED:
                    continue
                parent_idx = next(
                    (
                        j
                        for j in range(i - 1, -1, -1)
                        if rules[j].depth == rule.depth - 1
                    ),
                    None,
                )
                if parent_idx is not None:
                    self.assertNotEqual(
                        statuses[parent_idx],
                        RuleStatus.EVALUATED_NOT_FIRED,
                        f"{animal_case.name}: 'except if {format_condition(rule.condition)}' "
                        f"is green but its visual parent "
                        f"'{format_condition(rules[parent_idx].condition)}' is red",
                    )


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestRenderer(unittest.TestCase):
    def _many_rules(self, n):
        animal = variable(Animal, domain=[])
        fields = [
            "hair",
            "feathers",
            "eggs",
            "milk",
            "aquatic",
            "predator",
            "toothed",
            "backbone",
        ][:n]
        return [
            RuleView(
                condition=(getattr(animal, f) == True),
                conclusions=[],
                depth=0,
                kind="if",
            )
            for f in fields
        ]

    def test_elision_keeps_first_head_and_tail_ending_on_fired(self):
        rules = self._many_rules(8)
        renderer = RuleTreeRenderer(head=3, tail=3, use_color=False)
        out = renderer.render(rules, None, None, fired_index=7)
        lines = out.splitlines()
        # 3 head rows + 1 marker + 3 tail rows.
        self.assertEqual(len(lines), 7)
        self.assertIn("⋮", out)
        self.assertIn("2 hidden", out)
        # The fired row (index 7 -> 'backbone') is the last visible row.
        self.assertIn("backbone", lines[-1])
        self.assertIn("predator", lines[4])  # first tail row (index 5)

    def test_no_elision_when_fired_row_is_close_to_head(self):
        rules = self._many_rules(8)
        renderer = RuleTreeRenderer(head=3, tail=3, use_color=False)
        out = renderer.render(rules, None, None, fired_index=4)
        self.assertNotIn("⋮", out)
        self.assertEqual(len(out.splitlines()), 5)  # rows 0..4, ending on fired

    def test_connectors_and_kind_labels(self):
        _, query = _refined_tree()
        rules = walk_rules(query._conditions_root_)
        out = RuleTreeRenderer(use_color=False).render(rules, None, None, None)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("if backbone == true"))
        self.assertIn("species = fish", lines[0])
        self.assertTrue(lines[1].startswith("└─ except if milk == true"))
        self.assertIn("species = mammal", lines[1])

    def test_render_rule_tree_colours_fired_rule(self):
        animal, query = _refined_tree()
        trace = trace_case(
            query,
            animal,
            animal.species,
            first(Species.mammal),
            query._conditions_root_,
        )
        out = render_rule_tree(trace, use_color=True)
        self.assertIn("milk == true", out)
        self.assertIn("species = mammal", out)
        self.assertIn(Fore.GREEN, out)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestInteractiveHeaderIntegration(unittest.TestCase):
    def test_header_shows_tree_and_wrong_conclusion_framing(self):
        animal, query = _refined_tree()
        trace = trace_case(
            query, animal, animal.species, first(Species.fish), query._conditions_root_
        )
        captured = {}

        def runner(namespace, header):
            captured["header"] = header
            namespace["conditions"] = namespace["case_variable"].milk == True

        expert = Expert(interface=IPythonInterface(shell_runner=runner))
        expert.ask_for_conditions(
            first(Species.fish), animal, Species.mammal, Species.fish, trace
        )
        header = captured["header"]
        self.assertIn("fish", header)
        self.assertIn("mammal", header)
        self.assertIn("backbone == true", header)

    def test_no_tree_block_without_trace(self):
        animal = variable(Animal, domain=[])
        captured = {}

        def runner(namespace, header):
            captured["header"] = header
            namespace["conditions"] = namespace["case_variable"].milk == True

        expert = Expert(interface=IPythonInterface(shell_runner=runner))
        expert.ask_for_conditions(first(Species.fish), animal, Species.mammal)
        self.assertNotIn("rule tree", captured["header"])


if __name__ == "__main__":
    unittest.main()
