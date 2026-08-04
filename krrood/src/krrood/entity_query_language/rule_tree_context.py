"""
Construction-time context for the rule-tree ``with`` blocks of the Entity Query
Language.

Extracted into its own module, like :mod:`evaluation_context`, so that
:mod:`core.base_expressions` can import the context infrastructure without pulling in
the modules that build rule trees and the circular dependency chain they carry.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

from typing_extensions import List, Optional, TYPE_CHECKING, Type

from krrood.entity_query_language.exceptions import (
    RuleTreeEditWithoutEnclosingBlock,
    UnbalancedRuleTreeBlockExit,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression


@dataclass
class RuleTreeContext:
    """
    A ``with``-block anchor together with the parent edge its rule tree reaches it by.

    A shared node has several parents, so which parent a rule-tree edit must happen
    above is only defined relative to the branch that is asking. Recording that edge
    when the block is entered keeps the answer independent of which parent happened to
    be attached first.
    """

    condition: SymbolicExpression
    """
    The condition node the ``with`` block anchors on.
    """

    owning_parent: Optional[SymbolicExpression]
    """
    The parent through which the asking rule tree reaches :attr:`condition`, kept
    current by whoever splices a new node into that edge.
    """


@dataclass
class RuleTreeBlock:
    """
    One open rule-tree ``with`` block.
    """

    context: RuleTreeContext
    """
    The anchor and owning parent edge this block contributes to the stack.
    """

    entered_expression: SymbolicExpression
    """
    The expression whose ``__enter__`` opened this block, which is not always
    :attr:`context`'s condition — a query anchors on its conditions root instead.
    """


_rule_tree_context_stack_var: ContextVar[Optional[RuleTreeContextStack]] = ContextVar(
    "_rule_tree_context_stack", default=None
)


@dataclass
class RuleTreeContextStack:
    """
    The open ``with`` blocks of the rule tree currently under construction.

    Created by the outermost block and discarded when that block closes, so an active
    stack means a rule tree is being built and no state survives between builds. Holding
    it in a :class:`contextvars.ContextVar` additionally keeps rule trees built in
    different threads apart.

    ..note:: A task started *inside* a block inherits a copy of the context and therefore
        shares this stack, and a suspended generator that abandoned an open block is never
        unwound.
    """

    blocks: List[RuleTreeBlock] = field(default_factory=list)
    """
    The open blocks, outermost first.
    """

    activation_token: Optional[Token] = None
    """
    The token restoring whatever was active before this stack was installed.
    """

    @classmethod
    def active(cls) -> Optional[RuleTreeContextStack]:
        """
        :return: The stack of the rule tree currently under construction, or ``None`` when
            no ``with`` block is open.
        """
        return _rule_tree_context_stack_var.get()

    @classmethod
    def require_active(
        cls, expression_type: Type[SymbolicExpression]
    ) -> RuleTreeContextStack:
        """
        :param expression_type: The expression type the caller is about to create.
        :return: The stack of the rule tree currently under construction.
        :raises RuleTreeEditWithoutEnclosingBlock: When no ``with`` block is open.
        """
        stack = cls.active()
        if stack is None:
            raise RuleTreeEditWithoutEnclosingBlock(expression_type)
        return stack

    @classmethod
    def enter_block(
        cls, context: RuleTreeContext, entered_expression: SymbolicExpression
    ) -> None:
        """
        Open a block, creating and installing a stack when it is the outermost one.

        :param context: The anchor and owning parent edge the block contributes.
        :param entered_expression: The expression whose ``__enter__`` opens the block.
        """
        stack = cls.active()
        if stack is None:
            stack = cls()
            stack.activation_token = _rule_tree_context_stack_var.set(stack)
        stack.blocks.append(RuleTreeBlock(context, entered_expression))

    @classmethod
    def exit_block(cls, entered_expression: SymbolicExpression) -> None:
        """
        Close the innermost block, discarding the stack once the outermost one closes.

        :param entered_expression: The expression whose ``__exit__`` closes the block.
        :raises UnbalancedRuleTreeBlockExit: When the block being closed is not the
            innermost open one.
        """
        stack = cls.active()
        if stack is None:
            raise UnbalancedRuleTreeBlockExit(entered_expression, None)
        innermost_block = stack.blocks[-1]
        if innermost_block.entered_expression is not entered_expression:
            raise UnbalancedRuleTreeBlockExit(entered_expression, innermost_block)
        stack.blocks.pop()
        if stack.is_empty:
            _rule_tree_context_stack_var.reset(stack.activation_token)

    @property
    def innermost(self) -> RuleTreeContext:
        """
        :return: The context of the innermost open block.
        """
        return self.blocks[-1].context

    @property
    def is_empty(self) -> bool:
        """
        :return: Whether every block opened on this stack has been closed.
        """
        return not self.blocks

    def anchored_on(self, condition: SymbolicExpression) -> Optional[RuleTreeContext]:
        """
        :param condition: The condition an edit is about to be made relative to.
        :return: The context of the innermost open block that anchors on the given
            condition, or ``None`` when no open block does. The context is the live one
            the block holds, so a caller that splices a node into that edge updates
            :attr:`RuleTreeContext.owning_parent` on it in place.
        """
        return next(
            (
                block.context
                for block in reversed(self.blocks)
                if block.context.condition._id_ == condition._id_
            ),
            None,
        )
