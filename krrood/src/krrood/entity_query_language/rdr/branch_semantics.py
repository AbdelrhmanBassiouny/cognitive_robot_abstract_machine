"""
Per-selector branch semantics for backward inference over EQL-RDR rule trees.

Each :class:`~krrood.entity_query_language.rules.conclusion_selector.ConclusionSelector`
answers two questions when a rule tree is traversed backwards, and this module holds one
class per selector answering both:

* *As a competing sibling branch, what leaf predicates capture whether that branch was
  taken?* — :meth:`SelectorBranchSemantics.sibling_guards`.
* *Descending into this selector, which children continue the walk and what does entering
  each one add to the accumulated guards?* — :meth:`SelectorBranchSemantics.branches`.

Keeping both on one class per selector is what makes them impossible to change apart, and
lets a new selector participate by defining a class here rather than by editing the
traversal.

The dispatch mirrors the grammar's
:class:`~krrood.entity_query_language.verbalization.grammar.framework.specificity.SpecificityRule`
families: alternatives self-register as concrete subclasses and are ranked by how specific
their :attr:`SelectorBranchSemantics.selector` is, over the shared
:mod:`krrood.patterns.specificity_ranking` primitives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import (
    TYPE_CHECKING,
    Callable,
    ClassVar,
    List,
    Optional,
    Tuple,
    Type,
)

from krrood.entity_query_language.rdr.exceptions import AmbiguousBranchSemanticsError
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    ConclusionSelector,
    Next,
    Refinement,
)
from krrood.patterns.specificity_ranking import (
    concrete_subclasses,
    mro_depth,
    sole_maximum,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.rdr.backward_inference import GuardCondition


LeafGuardDecomposition = Callable[["SymbolicExpression", bool], List["GuardCondition"]]
"""
The recursion continuation: decompose an expression into leaf guards at a given
polarity.

Threaded in as a parameter, the same way the grammar's ``RuleContext.recurse`` hands a
rule its fold continuation, so a semantics class never recurses through the traversal
module.
"""

# %% branch value object


@dataclass(frozen=True)
class GuardedBranch:
    """
    One child of a conclusion selector, paired with what entering it implies.
    """

    node: SymbolicExpression
    """
    The child expression the traversal continues into.
    """

    entry_guards: Tuple[GuardCondition, ...]
    """
    The guards that reaching *node* through this selector adds to the path.
    """


# %% the family


@dataclass(frozen=True)
class SelectorBranchSemantics(ABC):
    """
    One conclusion selector's branch-choice semantics, as seen by backward inference.

    A concrete subclass declares the selector it handles via :attr:`selector` and
    implements both halves; it is discovered automatically, so adding a selector needs
    no edit to the traversal.
    """

    selector: ClassVar[Type[ConclusionSelector]]
    """
    The conclusion-selector class this semantics handles (the ``isinstance`` gate).
    """

    @classmethod
    def most_specific_for(
        cls,
        expression: SymbolicExpression,
    ) -> Optional[SelectorBranchSemantics]:
        """
        Find the semantics governing *expression*.

        Ranks by the specificity of each candidate's :attr:`selector`, so a semantics
        for a subclass of some selector outranks the one it refines.

        :param expression: Any rule-tree node.
        :return: The matching semantics, or ``None`` when *expression* is not a
            conclusion selector.
        :raises AmbiguousBranchSemanticsError: Two candidates are equally specific.
        """
        applicable = [
            candidate
            for candidate in concrete_subclasses(cls)
            if isinstance(expression, candidate.selector)
        ]
        winner = sole_maximum(
            applicable,
            key=lambda candidate: mro_depth(candidate.selector),
            collision_error=lambda tied: AmbiguousBranchSemanticsError(
                selector=expression, candidates=tied
            ),
        )
        return winner() if winner is not None else None

    @abstractmethod
    def sibling_guards(
        self,
        selector: SymbolicExpression,
        negated: bool,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardCondition]:
        """
        Decompose *selector*, standing as a competing sibling branch, into leaf guards.

        The result is always leaf-level, never a selector, so guards stay readable and
        directly evaluable.

        ..note:: The returned guards are conjoined by the caller, so a selector whose
            positive reading is a disjunction cannot be represented exactly; see
            :class:`AlternativeBranchSemantics`.

        :param selector: The selector node to decompose.
        :param negated: Whether the guard polarity is negated.
        :param decompose: The recursion continuation for child expressions.
        :return: The flat list of leaf guards.
        """

    @abstractmethod
    def branches(
        self,
        selector: SymbolicExpression,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardedBranch]:
        """
        Enumerate the children the traversal continues into, with their entry guards.

        :param selector: The selector node being descended into.
        :param decompose: The recursion continuation for child expressions.
        :return: One :class:`GuardedBranch` per child, in traversal order.
        """


# %% concrete selectors


@dataclass(frozen=True)
class RefinementBranchSemantics(SelectorBranchSemantics):
    """
    ``Refinement(left, right)`` — *right* refines *left*, overriding it when it applies.

    As a sibling, the refinement branch was taken exactly when *left* passed; *right* is
    a separate rule subtree rather than a condition on *left* having been reached.
    """

    selector: ClassVar[Type[ConclusionSelector]] = Refinement

    def sibling_guards(
        self,
        selector: Refinement,
        negated: bool,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardCondition]:
        return decompose(selector.left, negated)

    def branches(
        self,
        selector: Refinement,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardedBranch]:
        return [
            GuardedBranch(selector.left, tuple(decompose(selector.right, True))),
            GuardedBranch(selector.right, tuple(decompose(selector.left, False))),
        ]


@dataclass(frozen=True)
class AlternativeBranchSemantics(SelectorBranchSemantics):
    """
    ``Alternative(left, right)`` — an "else if": *right* applies only when *left* did
    not.

    Negated, the branch was not taken when neither side passed, which De Morgan turns into
    the conjunction ``NOT(left) AND NOT(right)`` the caller expects.

    ..warning:: Positively, the branch was taken when ``left OR right`` passed, which the
        caller's conjunction cannot express. The traversal never asks for that reading — a
        positive decomposition is only requested for a ``Refinement``'s left child, and an
        ``Alternative`` is always spliced above the conditions root rather than under a
        refinement — so the two sides are returned unchanged rather than approximated.
    """

    selector: ClassVar[Type[ConclusionSelector]] = Alternative

    def sibling_guards(
        self,
        selector: Alternative,
        negated: bool,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardCondition]:
        return decompose(selector.left, negated) + decompose(selector.right, negated)

    def branches(
        self,
        selector: Alternative,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardedBranch]:
        return [
            GuardedBranch(selector.left, ()),
            GuardedBranch(selector.right, tuple(decompose(selector.left, True))),
        ]


@dataclass(frozen=True)
class NextBranchSemantics(SelectorBranchSemantics):
    """
    ``Next(...)`` — independent rules at the same depth, evaluated without cross-guards.
    """

    selector: ClassVar[Type[ConclusionSelector]] = Next

    def sibling_guards(
        self,
        selector: Next,
        negated: bool,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardCondition]:
        guards: List[GuardCondition] = []
        for child in selector._operation_children_:
            guards.extend(decompose(child, negated))
        return guards

    def branches(
        self,
        selector: Next,
        decompose: LeafGuardDecomposition,
    ) -> List[GuardedBranch]:
        return [GuardedBranch(child, ()) for child in selector._operation_children_]
