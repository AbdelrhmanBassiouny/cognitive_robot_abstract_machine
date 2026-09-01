"""
Tests for the construction-time rule-tree context stack owned by the outermost ``with``
block.
"""

import pytest

from krrood.entity_query_language.exceptions import (
    RuleTreeEditWithoutEnclosingBlock,
    UnbalancedRuleTreeBlockExit,
)
from krrood.entity_query_language.factories import (
    add,
    alternative,
    next_rule,
    refinement,
    variable,
)
from krrood.entity_query_language.rule_tree_context import RuleTreeContextStack
from krrood.entity_query_language.rules.conclusion import Add
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    Next,
    Refinement,
)

from ...dataset.minimal_symbolic_expression import MinimalSymbolicExpression
from ...dataset.semantic_world_like_classes import Body, Drawer

# %% rule-tree edits attempted outside any with block


def test_add_outside_a_with_block_names_the_expression_that_needed_a_block():
    drawers = variable(Drawer, domain=[])

    with pytest.raises(RuleTreeEditWithoutEnclosingBlock) as raised:
        add(drawers, 1)

    assert raised.value.expression_type is Add


def test_refinement_outside_a_with_block_names_the_expression_that_needed_a_block():
    body = variable(Body, domain=[])

    with pytest.raises(RuleTreeEditWithoutEnclosingBlock) as raised:
        refinement(body.size > 1)

    assert raised.value.expression_type is Refinement


def test_alternative_outside_a_with_block_names_the_expression_that_needed_a_block():
    body = variable(Body, domain=[])

    with pytest.raises(RuleTreeEditWithoutEnclosingBlock) as raised:
        alternative(body.size > 1)

    assert raised.value.expression_type is Alternative


def test_next_rule_outside_a_with_block_names_the_expression_that_needed_a_block():
    body = variable(Body, domain=[])

    with pytest.raises(RuleTreeEditWithoutEnclosingBlock) as raised:
        next_rule(body.size > 1)

    assert raised.value.expression_type is Next


# %% unbalanced block exits


def test_exiting_a_block_that_was_never_entered_is_reported_as_unbalanced():
    condition = MinimalSymbolicExpression()

    with pytest.raises(UnbalancedRuleTreeBlockExit) as raised:
        condition.__exit__()

    assert raised.value.exiting_expression is condition
    assert raised.value.innermost_block is None


def test_exiting_an_expression_that_is_not_the_innermost_block_is_reported_as_unbalanced():
    outer_condition = MinimalSymbolicExpression()
    inner_condition = MinimalSymbolicExpression()
    outer_condition.__enter__()
    inner_condition.__enter__()

    with pytest.raises(UnbalancedRuleTreeBlockExit) as raised:
        outer_condition.__exit__()

    assert raised.value.innermost_block.entered_expression is inner_condition

    inner_condition.__exit__()
    outer_condition.__exit__()


# %% stack ownership and lifetime


def test_the_stack_only_exists_while_the_outermost_block_is_open():
    condition = MinimalSymbolicExpression()

    assert RuleTreeContextStack.active() is None
    with condition:
        assert RuleTreeContextStack.active() is not None
    assert RuleTreeContextStack.active() is None


def test_nested_blocks_push_onto_the_stack_the_outermost_block_created():
    outer_condition = MinimalSymbolicExpression()
    inner_condition = MinimalSymbolicExpression()

    with outer_condition:
        outermost_stack = RuleTreeContextStack.active()
        with inner_condition:
            assert RuleTreeContextStack.active() is outermost_stack
            assert outermost_stack.innermost.condition is inner_condition
        assert outermost_stack.innermost.condition is outer_condition


def test_each_outermost_block_gets_a_stack_of_its_own():
    first_condition = MinimalSymbolicExpression()
    second_condition = MinimalSymbolicExpression()

    with first_condition:
        first_stack = RuleTreeContextStack.active()
    with second_condition:
        assert RuleTreeContextStack.active() is not first_stack
