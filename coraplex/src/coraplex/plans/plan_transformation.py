from __future__ import annotations

import logging
from abc import abstractmethod, ABC
from dataclasses import dataclass, field

from typing_extensions import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

from coraplex.datastructures.enums import InsertionPosition
from coraplex.exceptions import CannotMatchOnType
from cramph.composites import CramLanguageNode
from cramph.context import ContextExtension
from cramph.node import StatechartNode
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

logger = logging.getLogger(__name__)

MatchedType = TypeVar("MatchedType", bound=StatechartNode)


# %% transformations


@dataclass
class PlanTransformation(Generic[MatchedType], SubClassSafeGeneric, ABC):
    """
    Rewrites the part of a plan around a node, before the statechart running the plan is
    compiled.

    The bound type says which nodes it rewrites: the nodes of that type. Every node of
    a plan is offered to a transformation once, after it has been expanded, see
    :class:`PlanRewriting`.
    """

    @property
    def matched_type(self) -> Type[MatchedType]:
        """
        :return: The type this selects its nodes by.
        """
        return type(self).get_type_of_generic_parameter(MatchedType)

    def matches_node(self, plan_node: StatechartNode) -> bool:
        """
        :param plan_node: The node that was just expanded
        :return: Whether the given node is one this rewrites.
        :raises CannotMatchOnType: If the bound type is not a statechart node type
        """
        if not issubclass(self.matched_type, StatechartNode):
            raise CannotMatchOnType(type(self), self.matched_type)
        return isinstance(plan_node, self.matched_type)

    @abstractmethod
    def is_applicable(self, plan_node: MatchedType) -> bool:
        """
        Reports whether the case the node describes needs this transformation.

        It is asked only about nodes :meth:`matches_node` selected, so the node can be
        read as the type this is bound to.

        :param plan_node: A node this matches
        :return: Whether the transformation is needed here.
        """

    @abstractmethod
    def apply(self, plan_node: MatchedType) -> None:
        """
        Rewrites the plan around the given node.

        :param plan_node: The node this transformation is applied to
        """


# %% inserting


@dataclass
class InsertionTransformation(
    PlanTransformation[MatchedType], Generic[MatchedType], SubClassSafeGeneric, ABC
):
    """
    Rewrites a plan by inserting freshly built nodes next to an anchor node.

    The nodes are built anew on every application, since a node belongs to the one
    statechart it was inserted into.
    """

    @property
    @abstractmethod
    def position(self) -> InsertionPosition:
        """
        :return: Where the inserted nodes are placed relative to the anchor node.
        """

    @abstractmethod
    def anchor(self, plan_node: MatchedType) -> StatechartNode:
        """
        :param plan_node: The node this transformation is applied to
        :return: The node the new nodes are inserted next to.
        """

    @abstractmethod
    def nodes_to_insert(self, plan_node: MatchedType) -> List[StatechartNode]:
        """
        :param plan_node: The node this transformation is applied to
        :return: The nodes to insert, in the order they take.
        """

    def apply(self, plan_node: MatchedType) -> None:
        anchor = self.anchor(plan_node)
        for node in self.nodes_to_insert(plan_node):
            self._insert(anchor, node)
            if self.position is InsertionPosition.AFTER:
                # each further node goes behind the one before it, keeping their order
                anchor = node

    def _insert(self, anchor: StatechartNode, node: StatechartNode) -> None:
        """
        Inserts a node at :attr:`position` relative to the anchor node.

        :param anchor: The node the given node is placed relative to; a neighbour goes
            into the plan language node running it, and a last child below the anchor
            itself.
        :param node: The node to insert
        """
        match self.position:
            case InsertionPosition.BEFORE:
                CramLanguageNode.running(anchor).insert_before(anchor, node)
            case InsertionPosition.AFTER:
                CramLanguageNode.running(anchor).insert_after(anchor, node)
            case InsertionPosition.LAST_CHILD:
                anchor.add_node(node)


# %% rewriting a plan


@dataclass
class PlanRewriting(ContextExtension):
    """
    Offers the nodes of a plan to the transformations that may rewrite it.

    A node is offered once it and everything below it has been expanded, in the order
    the plan runs its nodes, and the nodes a transformation inserts are offered in turn.
    Carried in the context of the statechart running the plan, so that a part of the
    plan that joins it later can be rewritten too.
    """

    transformations: List[PlanTransformation] = field(default_factory=list)
    """
    The transformations the nodes are offered to.
    """

    _offered: Set[StatechartNode] = field(default_factory=set, init=False, repr=False)
    """
    The nodes offered already, so that rewriting a part of the plan again offers only
    what is new.
    """

    def __deepcopy__(self, memo: Dict[int, Any]) -> PlanRewriting:
        """
        :return: A rewriting by the same transformations that has offered nothing yet,
            since the nodes offered so far belong to the statechart this one rewrites.
        """
        return PlanRewriting(transformations=list(self.transformations))

    def rewrite(self, root: StatechartNode) -> None:
        """
        Applies every transformation to every node below and including `root` that it
        matches and applies to.

        :param root: The part of the plan to rewrite.
        """
        if not self.transformations:
            return
        while (node := self._next_node_to_offer(root)) is not None:
            self._offered.add(node)
            self._apply_to(node)

    def _next_node_to_offer(self, root: StatechartNode) -> Optional[StatechartNode]:
        """
        :param root: The part of the plan being rewritten.
        :return: The first node of `root` in the order the plan runs its nodes that has
            not been offered yet, or None if there is none.
        """
        for node in [root, *root.descendants]:
            if node not in self._offered:
                return node
        return None

    def _apply_to(self, node: StatechartNode) -> None:
        """
        Rewrites the plan with every transformation that applies to `node`.

        Each of them rewrites what the ones before it left, so more than one of them on
        the same node is reported.

        :param node: The node offered to the transformations.
        """
        transformations = [
            transformation
            for transformation in self.transformations
            if transformation.matches_node(node) and transformation.is_applicable(node)
        ]
        if len(transformations) > 1:
            logger.warning(
                f"{len(transformations)} plan transformations are applied to {node}: "
                f"{transformations}"
            )
        for transformation in transformations:
            transformation.apply(node)
