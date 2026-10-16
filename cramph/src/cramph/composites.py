from __future__ import annotations, division

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from itertools import combinations
from typing import List

from typing_extensions import Any, Generator, Optional

from krrood.adapters.json_serializer import JSONField
from krrood.entity_query_language.backends import QueryBackend
from krrood.entity_query_language.query.match import Match
from krrood.ormatic.utils import classproperty
from krrood.patterns.field_metadata import JSONMetadata
from krrood.utils import get_full_class_name
from cramph.node import EndedByOwner, SucceedsOnObservingTrue, FailsOnObservingFalse
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import (
    LifeCyclePredicate,
    LifeCycleValues,
    ObservationStateValues,
)
from cramph.exceptions import (
    NotRunByLanguageNodeError,
    AttemptWithoutFailureMonitorsError,
    ChildCannotFailError,
    NodeAlreadyAChildError,
    NodeIsNotAChildError,
    NotHeldByLanguageNodeError,
)
from cramph.node import (
    CancelStatechart,
    CompositeNode,
    StatechartNode,
    NodeArtifacts,
    TerminalNode,
)
from krrood.exceptions import DataclassException
from krrood.symbolic_math.symbolic_math import (
    Scalar,
    trinary_if_cases,
    sum,
    trinary_logic_and,
    trinary_logic_not,
    trinary_logic_or,
    logic_and,
    logic_not,
    logic_or,
)

# %% giving a node an outcome


@dataclass(repr=False, eq=False)
class Attempt(SucceedsOnObservingTrue, FailsOnObservingFalse, CompositeNode):
    """
    Runs a node that would never end on its own and decides it, one way or the other.

    A node that keeps holding its goal observes only whether it is at that goal right
    now, so nothing about it ever concludes. This goal concludes instead: it
    observes True once the task is at its goal, which ends it as a success, and False
    once one of :attr:`failure_monitors` fires, which is what it declares its own
    failure on. That is what lets a maintained node be one step of a plan.

    It declares that failure as well once the task ended without succeeding, which is the
    task having concluded on its own and nothing else here would notice.

    .. note:: The task is never ended from here. It keeps exerting itself after first
        reaching its goal and comes down only with this goal, so a task that was pushed
        off its goal again is still being held.
    """

    task: StatechartNode = field(kw_only=True)
    """
    The node run until this goal is decided.
    """

    failure_monitors: List[StatechartNode] = field(kw_only=True)
    """
    The nodes whose observing True gives up on the task, any one of which is enough, so
    there has to be at least one.

    A monitor is read the way it is written, so one that observes being *well* has to be
    negated before it can be passed here.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.failure_monitors:
            raise AttemptWithoutFailureMonitorsError(node=self)

    @property
    def any_failure_monitor_fired(self) -> Scalar:
        """
        :return: True once a failure monitor fired, and false while none has.
        """
        return trinary_logic_or(
            *[monitor.last_observed_true for monitor in self.failure_monitors]
        )

    @property
    def failure_reasons(self) -> List[StatechartNode]:
        """
        Which monitors gave up on the task, which is what turns a failure into a reason.

        They are read through their last observation, because ending this goal ends them
        too and a node that ended observes nothing any more.

        :return: The failure monitors that fired, in the order they were given, and
            nothing at all unless this goal declared itself failed. Empty as well for a
            failure the task reached on its own, which no monitor is the reason for.
        """
        if self.life_cycle_state != LifeCycleValues.FAILED:
            return []
        return [
            monitor
            for monitor in self.failure_monitors
            if monitor.last_observation_state == ObservationStateValues.TRUE
        ]

    def expand(self, context: StatechartContext) -> None:
        """
        Add the task and the monitors.

        A monitor that fires fails this goal on the same tick, which interrupts the
        monitor and so keeps the observation it fired on as its last observation.
        """
        self._add_child_to_statechart(self.task)
        self._add_children_to_statechart(self.failure_monitors)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report reaching the goal, being given up on, or neither.

        Reaching the goal outranks a monitor firing on the same tick: a task
        that arrived did what it was asked, whatever else was true at that moment. The
        task is read through its last observation, which is what it observes for as long
        as this goal holds it open, and what it arrived at if it ended itself.

        A task that ended without succeeding is reported the same way a monitor giving up
        is: nothing will move it any more, and an attempt still waiting for it would never
        end. What it observed when it ended does not count as reaching its goal.
        """
        task_at_its_goal = logic_and(
            self.task.last_observed_true,
            logic_not(self.task.is_failed_or_interrupted),
        )
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (task_at_its_goal, Scalar.const_true()),
                    (self.any_failure_monitor_fired, Scalar.const_false()),
                    (self.task.is_failed_or_interrupted, Scalar.const_false()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


# %% goals that decide when their children end


@dataclass(repr=False, eq=False)
class CompositeNodeEndingItsChildren(
    SucceedsOnObservingTrue, FailsOnObservingFalse, CompositeNode, ABC
):
    """
    Base for the goals that order or choose between children, which only works if each
    child reaches a terminal state.

    Such a goal reads its children's outcomes and never their observations, and it owns
    their life cycles: what starts and ends a child is this goal's to decide. A child
    whose owner decides its success is ended by this goal once it observes True. What
    comes out decides itself in turn, which is what lets one be a step of another.
    """

    def _check_can_decide(self, node: StatechartNode) -> None:
        """
        Rejects a child whose life cycle is not this goal's to decide.

        :param node: The child the caller passed.
        :raises NodeAlreadyBelongsToDifferentNodeError: If another node runs `node`.
        :raises ChildTransitionAlreadyWiredError: If the caller already wired one of the
            transitions of `node`.
        """
        self._check_node_doesnt_belong_to_different_parent(node)
        self._check_caller_wired_no_transitions(node)

    def _succeed_children_at_their_goals(self) -> None:
        """
        Ends every child whose owner decides its success once it observes True, see
        :meth:`~cramph.node.CompositeNode._succeed_at_its_goal`.

        A node that ends the statechart decides nothing and is left alone.
        """
        for child in self.nodes:
            if not isinstance(child, TerminalNode):
                self._succeed_at_its_goal(child)

    def _check_child_can_fail(self, child: StatechartNode) -> None:
        """
        Rejects a child this goal only moves on from once it failed, if it has no way to
        fail.

        :param child: The child this goal waits on to fail.
        :raises ChildCannotFailError: If `child` cannot fail on its own.
        """
        if not child.can_fail_on_its_own:
            raise ChildCannotFailError(node=self, child=child)


# %% the plan language: running a list of nodes


@dataclass(repr=False, eq=False)
class CramLanguageNode(CompositeNode, ABC):  # ControlStructureNode?
    """
    A construct of the plan language, which runs the list of nodes it is handed.

    Its children can be changed after it joined a statechart, up to the moment the
    statechart is compiled: :meth:`insert_before`, :meth:`insert_after` and
    :meth:`replace` rewire the conditions of the current children accordingly.

    Wherever it is handed a node, it also takes an underspecified `a(...)` statement,
    which it runs through a :class:`StatementNode`.
    """

    nodes: List[StatechartNode] = field(default_factory=list, init=True)
    """
    The nodes this goal runs, in order.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.nodes = [self._as_node(node) for node in self.nodes]

    @staticmethod
    def _as_node(node: StatechartNode | Match) -> StatechartNode:
        """
        :param node: A node this goal was handed, or a statement of one.
        :return: `node` itself, or a :class:`StatementNode` running the statement.
        """
        if isinstance(node, Match):
            return StatementNode(statement=node)
        return node

    def add_node(self, node: StatechartNode) -> None:
        """
        Hands this goal one more node to run, after all the others.

        A node it already runs is not added again.

        :param node: The node to run as a child of this goal.
        """
        node = self._as_node(node)
        if self._runs(node):
            return
        self._add_node_sanity_check(node)
        self._insert_at(len(self.nodes), node)

    def insert_before(self, reference: StatechartNode, node: StatechartNode) -> None:
        """
        Hands this goal a node to run right before `reference`, or before the child
        holding it.

        :param reference: A node this goal runs, or a node below one.
        :param node: The node to insert.
        :raises NodeIsNotAChildError: If `reference` is not below this goal.
        :raises NodeAlreadyAChildError: If this goal already runs `node`.
        """
        self._insert_at(self._position_of(reference), node)

    def insert_after(self, reference: StatechartNode, node: StatechartNode) -> None:
        """
        Hands this goal a node to run right after `reference`, or after the child
        holding it.

        :param reference: A node this goal runs, or a node below one.
        :param node: The node to insert.
        :raises NodeIsNotAChildError: If `reference` is not below this goal.
        :raises NodeAlreadyAChildError: If this goal already runs `node`.
        """
        self._insert_at(self._position_of(reference) + 1, node)

    def replace(self, reference: StatechartNode, node: StatechartNode) -> None:
        """
        Runs `node` in place of `reference`, which leaves the statechart together with
        everything below it.

        :param reference: A node this goal runs.
        :param node: The node to run in its place.
        :raises NodeIsNotAChildError: If this goal does not run `reference`.
        :raises NodeAlreadyAChildError: If this goal already runs `node`.
        """
        position = self._position_of(reference)
        node = self._as_node(node)
        self._check_does_not_run(node)
        if not self.belongs_to_statechart():
            self.nodes[position] = node
            return
        replaced = self.nodes[position]
        self._check_can_run(node)
        self.nodes[position] = node
        self._place_child_in_statechart(node)
        self._wire_children()
        self.statechart.remove_node(replaced)

    def take_place_of(self, node: StatechartNode) -> None:
        """
        Runs this node where `node` ran, with `node` as one of the nodes this node runs:
        the plan language node that held `node` holds this node instead, and a top-level
        `node` leaves the top level to it.

        :param node: A node of a statechart, held by a plan language node or on the top
            level, and one of :attr:`nodes`.
        :raises NodeIsNotAChildError: If this node does not run `node`.
        :raises NotHeldByLanguageNodeError: If a node other than a plan language node
            holds `node`.
        :raises StatechartAlreadyCompiledError: If the latest compile covers `node`.
        """
        if not self._runs(node):
            raise NodeIsNotAChildError(node=self, child=node)
        holder = node.parent_node
        if holder is None:
            node.statechart.add_node_above(node, self)
            return
        if not isinstance(holder, CramLanguageNode):
            raise NotHeldByLanguageNodeError(node=node, parent=holder)
        with node.statechart.modify():
            node.statechart.add_node_above(node, self)
            holder._wire_children()

    @staticmethod
    def running(node: StatechartNode) -> CramLanguageNode:
        """
        :param node: A node of a statechart.
        :return: The first plan language node on the path from `node` up to the root,
            which can hold a neighbour of whatever holds `node` below it.
        :raises NotRunByLanguageNodeError: If no plan language node is above `node`.
        """
        for ancestor in node.path:
            if isinstance(ancestor, CramLanguageNode):
                return ancestor
        raise NotRunByLanguageNodeError(node=node)

    def expand(self, context: StatechartContext) -> None:
        """
        Adopt every node this goal was handed and wire them.
        """
        for node in list(self.nodes):
            self._check_can_run(node)
            self._place_child_in_statechart(node)
        self._wire_children()

    def check_children(self) -> None:
        """
        Rejects this goal if it was never handed a node to run.
        """
        self._check_has_children()

    def _check_can_run(self, node: StatechartNode) -> None:
        """
        Rejects a node this goal cannot run as its child, before it joins the
        statechart.

        :param node: The node the caller handed over.
        """

    def _wire_children(self) -> None:
        """
        Wires the conditions of the current children to each other.
        """

    def _runs(self, node: StatechartNode) -> bool:
        """
        :return: Whether `node` itself is one of the children, whatever other child it
            compares equal to.
        """
        return any(child is node for child in self.nodes)

    def _position_of(self, reference: StatechartNode) -> int:
        """
        :return: The position of the child that is `reference` or holds it.
        :raises NodeIsNotAChildError: If no child is or holds `reference`.
        """
        for holder in [reference, *reference.path]:
            if holder in self.nodes:
                return self.nodes.index(holder)
        raise NodeIsNotAChildError(node=self, child=reference)

    def _check_does_not_run(self, node: StatechartNode) -> None:
        """
        :raises NodeAlreadyAChildError: If this goal already runs `node`.
        """
        if self._runs(node):
            raise NodeAlreadyAChildError(node=self, child=node)

    def _insert_at(self, position: int, node: StatechartNode) -> None:
        """
        Runs `node` at `position` among the children.
        """
        node = self._as_node(node)
        self._check_does_not_run(node)
        if not self.belongs_to_statechart():
            self.nodes.insert(position, node)
            return
        self._check_can_run(node)
        self.nodes.insert(position, node)
        self._place_child_in_statechart(node)
        self._wire_children()


@dataclass(repr=False, eq=False)
class CramLanguageNodeRunningItsChildrenInTurn(
    CramLanguageNode, CompositeNodeEndingItsChildren, ABC
):
    """
    A plan language construct that starts each child only once the one before it ended
    in a way it defines.
    """

    def _check_can_run(self, node: StatechartNode) -> None:
        self._check_can_decide(node)

    def _wire_children(self) -> None:
        """
        Starts the first child right away, and every other one once the child before it
        ended the way :meth:`_start_condition_after` asks for.

        A child whose owner decides its success ends once it observes True.
        """
        self._succeed_children_at_their_goals()
        previous: Optional[StatechartNode] = None
        for child in self.nodes:
            child.start_condition = (
                Scalar.const_true()
                if previous is None
                else self._start_condition_after(previous)
            )
            previous = child

    @abstractmethod
    def _start_condition_after(self, previous: StatechartNode) -> Scalar:
        """
        :param previous: The child that runs before the next one.
        :return: The condition that starts the child after `previous`.
        """


@dataclass(repr=False, eq=False)
class Sequence(CramLanguageNodeRunningItsChildrenInTurn):
    """
    Runs a list of nodes one after another.

    Its observation turns True once the last step succeeded, and False as soon as a step
    ended without succeeding, so a step that was given up on fails the sequence rather
    than leaving it waiting forever.

    .. note:: corresponds to the RPL's SEQ. (McDermott, Drew. A reactive plan language, 1991)
    """

    def _check_can_run(self, node: StatechartNode) -> None:
        """
        A node that ends the statechart may be a step although it belongs to no other
        node's life cycle, see :meth:`CramLanguageNode._check_can_run`.
        """
        if isinstance(node, TerminalNode):
            self._check_caller_wired_no_transitions(node)
            return
        super()._check_can_run(node)

    def _start_condition_after(self, previous: StatechartNode) -> Scalar:
        """
        The next step waits for the outcome the previous one earned, because only an
        outcome outlasts the step that reached it.
        """
        return previous.is_succeeded

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report success, a failed step, or neither, all read off the steps' outcomes.

        A step that is still running has not failed, it has not arrived yet, so only a
        step that ended decides anything.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (
                        trinary_logic_or(
                            *[step.is_failed_or_interrupted for step in self.nodes]
                        ),
                        Scalar.const_false(),
                    ),
                    (self.nodes[-1].is_succeeded, Scalar.const_true()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


@dataclass(repr=False, eq=False)
class Parallel(EndedByOwner, CramLanguageNode):
    """
    Holds a list of nodes at once until enough of them are at their goals together.

    Its observation turns True once at least :attr:`minimum_success` of them are at
    their goals on the same tick.

    Unlike the goals that run steps, this one ends none of its nodes and reads what they
    observe now, because releasing a node that reached its goal would let a sibling undo
    what it reached. For the same reason its own owner decides when it succeeded.
    """

    minimum_success: Optional[int] = field(default=None, kw_only=True)
    """
    How many nodes must have reached their goals for this goal to be achieved.

    Defaults to None, which means all of them.
    """

    @property
    def required_successes(self) -> int:
        """
        :return: How many nodes have to reach their goals, which is all of them unless
            :attr:`minimum_success` says otherwise.
        """
        if self.minimum_success is None:
            return len(self.nodes)
        return self.minimum_success

    @property
    def inherent_fail_condition(self) -> Scalar:
        """
        Fails as well once too few of its nodes can still reach their goals, see
        :meth:`~cramph.node.StatechartNode.inherent_fail_condition`.

        Observing False means the nodes are not at their goals, which is not a failure
        and is left to whoever runs this goal. A node that ended without
        succeeding is different: nothing brings it back, so once too few are left this
        goal can no longer arrive and says so rather than holding its owner open forever.
        """
        return logic_or(super().inherent_fail_condition, self._cannot_arrive_any_more)

    @property
    def _cannot_arrive_any_more(self) -> Scalar:
        """
        Asks whether so many nodes ended without succeeding that
        :attr:`required_successes` is out of reach.

        Counting would say this in one line, but a transition condition has to render
        back into the expression it was written as, which only leaves the logic
        operators: the question becomes which groups of nodes ending without succeeding
        are enough, one term per group.

        :return: True once too few nodes are left to reach :attr:`required_successes`.
        """
        nodes_that_must_end_without_succeeding = (
            len(self.nodes) - self.required_successes + 1
        )
        if nodes_that_must_end_without_succeeding <= 0:
            return Scalar.const_true()
        if nodes_that_must_end_without_succeeding > len(self.nodes):
            return Scalar.const_false()
        return logic_or(
            *[
                logic_and(*[node.is_failed_or_interrupted for node in group])
                for group in combinations(
                    self.nodes, nodes_that_must_end_without_succeeding
                )
            ]
        )

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Count the nodes that are at their goals against :attr:`required_successes`.

        This goal ends none of its nodes, so a node that keeps running is counted by
        what it observes now and stops counting once it observes False again. A node that
        succeeded on its own is counted by the last observation it took, which outlasts
        it; one that ended without succeeding stops counting, because the reading it kept
        says where it was cut off rather than where it is.

        Observing False means the nodes are not at their goals, not that anything went
        wrong: whether that is worth giving up on is decided outside, by whoever runs
        this goal.
        """
        nodes_at_their_goals = [
            trinary_logic_and(
                node.last_observed_true,
                trinary_logic_not(node.is_failed_or_interrupted),
            )
            for node in self.nodes
        ]
        return NodeArtifacts(
            observation=self.required_successes <= sum(*nodes_at_their_goals)
        )


# %% repeating a task


@dataclass(repr=False, eq=False)
class RepeatUntil(CompositeNodeEndingItsChildren):
    """
    Runs a task again from the start whenever an attempt at it fails.

    Its observation turns True once the task succeeds and False once
    :attr:`stop_retry_monitor` calls the retrying off, so a caller can tell "eventually
    worked" from "gave up".

    What counts as a failed attempt is stated on the task itself: hand it an
    :class:`Attempt` carrying the failure monitors that decide it, or see
    :class:`RepeatOnStall`, which derives that decision from the task's own progress. A
    task that cannot fail on its own is rejected, since it would never be retried.
    """

    task: StatechartNode = field(kw_only=True)
    """
    The node to run, and to run again after every failed attempt.

    Resetting a goal resets everything below it, so a composite task starts over as a
    unit.
    """

    stop_retry_monitor: StatechartNode = field(kw_only=True)
    """
    Stops the retrying once it observes True, which makes this goal observe False.
    """

    exception: Optional[DataclassException] = field(default=None, kw_only=True)
    """
    The failure that ends the statechart once :attr:`stop_retry_monitor` calls the
    retrying off, or None to only observe False then.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Wire the retry loop.

        The task declares its own failure, and that outcome is what starts the next
        try: a node takes at most one transition triggered by its own conditions per
        tick, so the reset lands the tick after the failure rather than on it.

        The stop monitor is asked whether its last observation is True, which outlasts a
        monitor that ends itself on reaching what it counts, and which a monitor that has
        not observed anything yet has not reached either.
        """
        self._check_can_decide(self.task)
        self._add_child_to_statechart(self.task)
        self._succeed_at_its_goal(self.task)
        self._add_child_to_statechart(self.stop_retry_monitor)

        retrying_stopped = self._retrying_stopped
        still_trying = logic_not(retrying_stopped)
        # Starting is gated as well as ending, because a reset task is not started and
        # ending is not considered while it is not.
        self.task.start_condition = still_trying
        self.task.reset_condition = logic_and(self.task.is_failed, still_trying)
        self.task.interrupt_condition = retrying_stopped
        self._end_statechart_once_retrying_stops()

    def check_children(self) -> None:
        """
        Rejects a task that cannot fail, since it would never be retried.
        """
        self._check_child_can_fail(self.task)

    @property
    def _retrying_stopped(self) -> Scalar:
        """
        :return: True once :attr:`stop_retry_monitor` observed True, even if it ended
            since; false while it has not.
        """
        return self.stop_retry_monitor.last_observed_true

    def _end_statechart_once_retrying_stops(self) -> None:
        """
        Add the node that ends the statechart with :attr:`exception` once
        :attr:`stop_retry_monitor` calls the retrying off.
        """
        if self.exception is None:
            return
        exhausted = CancelStatechart(
            name=f"{self.name}/exhausted", exception=self.exception
        )
        self._add_child_to_statechart(exhausted)
        exhausted.start_condition = self._retrying_stopped

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report success, giving up, or neither.

        Both children are read through something that outlasts them: the task through
        its outcome, which the reset that starts the next try clears again, and the stop
        monitor through its last observation.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (self.task.is_succeeded, Scalar.const_true()),
                    (self._retrying_stopped, Scalar.const_false()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


# %% trying alternatives


@dataclass(repr=False, eq=False)
class TryAll(CramLanguageNode, CompositeNodeEndingItsChildren):
    """
    Runs a list of alternatives at once and takes the first one that works.

    Its observation turns True as soon as an alternative succeeded, and False only once
    every one of them ended without doing so.
    """

    def _check_can_run(self, node: StatechartNode) -> None:
        self._check_can_decide(node)

    def _wire_children(self) -> None:
        """
        Every alternative runs side by side with the others, and one whose owner decides
        its success ends once it observes True.
        """
        self._succeed_children_at_their_goals()

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report the first alternative that worked, or that none of them did.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (
                        trinary_logic_or(
                            *[alternative.is_succeeded for alternative in self.nodes]
                        ),
                        Scalar.const_true(),
                    ),
                    (
                        trinary_logic_and(
                            *[
                                alternative.is_failed_or_interrupted
                                for alternative in self.nodes
                            ]
                        ),
                        Scalar.const_false(),
                    ),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


@dataclass(repr=False, eq=False)
class TryInOrder(CramLanguageNodeRunningItsChildrenInTurn):
    """
    Tries a list of alternatives one after another, short-circuiting on the first
    success.

    The next alternative only starts once the previous one has ended without
    succeeding. Its observation turns True as soon as an alternative succeeds and False
    only once every one of them is over, so it stays unknown while any is still running.

    Each alternative decides for itself when to give up, which is why this goal reduces
    to ordering: wrap one in an :class:`Attempt` carrying the monitors that decide it.
    An alternative that cannot fail is rejected anywhere but last, since the
    alternatives after it could never start.

    .. note:: corresponds to the RPL's TRY-IN-ORDER. (McDermott, Drew. A reactive plan language, 1991)
    """

    def _start_condition_after(self, previous: StatechartNode) -> Scalar:
        """
        The next alternative starts once the previous one ended without succeeding,
        which short-circuits on the first success.
        """
        return previous.is_failed_or_interrupted

    def check_children(self) -> None:
        """
        Rejects an alternative that cannot fail before the last one, since the
        alternatives after it could never start.
        """
        super().check_children()
        for alternative in self.nodes[:-1]:
            self._check_child_can_fail(alternative)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report the alternative that worked, or that none of them did.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (
                        trinary_logic_or(
                            *[alternative.is_succeeded for alternative in self.nodes]
                        ),
                        Scalar.const_true(),
                    ),
                    (
                        trinary_logic_and(
                            *[
                                alternative.is_failed_or_interrupted
                                for alternative in self.nodes
                            ]
                        ),
                        Scalar.const_false(),
                    ),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


# %% monitored subtrees


@dataclass(repr=False, eq=False)
class MonitoredCompositeNode(EndedByOwner, CompositeNode, ABC):
    """
    Runs a monitored node next to the monitor observing it.

    What it observes is what the monitored node has reached, so nothing here ever
    concludes either: a plan step built from one is an attempt wrapping it.

    The two are siblings, which is what lets the monitor's observation drive the
    monitored node's life cycle: a transition condition may only reference the owning
    node or a sibling of it. Neither node is chained to the other, so the monitor
    observes from the moment this goal starts.
    """

    monitor: StatechartNode = field(kw_only=True)
    """
    The node whose observation controls the monitored node.
    """

    monitored_node: Optional[StatechartNode] = field(default=None, kw_only=True)
    """
    The node placed under the monitor's control.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Add the monitor and the monitored node, and wire the monitor.
        """
        self._add_child_to_statechart(self.monitor)
        self._add_child_to_statechart(self.monitored_node)
        self.wire_monitor()

    @property
    def inherent_fail_condition(self) -> Scalar:
        """
        Fails as well once the monitored node ended without succeeding, because it can
        no longer arrive, see
        :meth:`~cramph.node.StatechartNode.inherent_fail_condition`.
        """
        return logic_or(
            super().inherent_fail_condition,
            self.monitored_node.is_failed_or_interrupted,
        )

    @abstractmethod
    def wire_monitor(self) -> None:
        """
        Connect the monitor's observation to the monitored node's life cycle.
        """

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        The monitored node is read through its last observation, which outlasts it,
        because a node that ended observes nothing any more.
        """
        return NodeArtifacts(observation=Scalar(self.monitored_node.last_observation))


@dataclass(repr=False, eq=False)
class PausedWhileTrue(MonitoredCompositeNode):
    """
    Holds the monitored node for as long as the monitor observes True, and lets it
    continue once the monitor turns False again.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.pause_condition = logic_or(
            self.monitor.observes_true,
            self.monitored_node.pause_condition,
        )


@dataclass(repr=False, eq=False)
class PausedUntilTrue(MonitoredCompositeNode):
    """
    Holds the monitored node until the monitor observes True, and lets it continue from
    then on.

    A monitor that has not observed anything yet has not turned True either, so it holds
    the monitored node as well.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.pause_condition = logic_or(
            self.monitored_node.pause_condition,
            logic_not(self.monitor.observes_true),
        )


@dataclass(repr=False, eq=False)
class StoppedWhenTrue(MonitoredCompositeNode):
    """
    Interrupts the monitored node as soon as the monitor observes True.

    It observes True while the monitored node observes True or once it succeeded, False
    once the monitor stopped it, whatever it observed, and Unknown otherwise. Stopping
    the monitored node interrupts it, so this goal fails the way every monitored
    composite node does once its monitored node ended without succeeding.

    The monitor is read through its last observation, which outlasts a monitor that ends
    itself on firing, unlike the pausing goals, which need the reading it takes right
    now.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.interrupt_condition = logic_or(
            self.monitored_node.interrupt_condition,
            self.monitor.last_observed_true,
        )

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        The monitored node's observation counts only while it has not ended; after that,
        only its success does.

        A node that ended keeps the observation it ended on until the next tick, so a
        node the monitor stopped is told apart from one that succeeded by its life cycle
        rather than by that observation.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                [
                    (
                        self._monitored_node_observing_true_or_succeeded,
                        Scalar.const_true(),
                    ),
                    (self.monitor.last_observed_true, Scalar.const_false()),
                ],
                Scalar.const_trinary_unknown(),
            )
        )

    @property
    def _monitored_node_observing_true_or_succeeded(self) -> Scalar:
        """
        :return: True while the monitored node has not ended and observes True, and once
            it succeeded; false otherwise.
        """
        has_ended = LifeCyclePredicate.IS_TERMINATED.expression(
            self.monitored_node.life_cycle_variable
        )
        observing_true_while_running = trinary_logic_and(
            trinary_logic_not(has_ended),
            self.monitored_node.observes_true,
        )
        return trinary_logic_or(
            observing_true_while_running, self.monitored_node.is_succeeded
        )


@dataclass(repr=False, eq=False)
class CancelledWhenTrue(StoppedWhenTrue):
    """
    Interrupts the monitored node as soon as the monitor observes True, and ends the
    statechart with it.

    Nothing in a plan waits for a node that failed, so a monitor that gives up on its
    subtree has to end the statechart rather than leave the rest of the plan waiting for
    a subtree that will never succeed.
    """

    exception: DataclassException = field(kw_only=True)
    """
    The failure reported once the monitor ends the statechart.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Add the monitor and the monitored node, and the node that ends the statechart
        once the monitor observes True.
        """
        super().expand(context)
        cancelled = CancelStatechart(
            name=f"{self.name}/cancelled", exception=self.exception
        )
        self._add_child_to_statechart(cancelled)
        cancelled.start_condition = self.monitor.last_observed_true


# %% choosing a child while running


@dataclass
class ChildChooser(ABC):
    """
    Decides which child a :class:`CompositeNodeChoosingItsChild` runs next.
    """

    def has_choice_for(self, node: CompositeNodeChoosingItsChild) -> bool:
        """
        :param node: The node asking for its next child.
        :return: Whether :meth:`choose_child` can answer `node` now; if not, `node`
            asks again on the next tick.
        """
        return True

    @abstractmethod
    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context: StatechartContext
    ) -> Optional[StatechartNode]:
        """
        :param node: The node asking for its next child.
        :param context: The context the statechart runs in.
        :return: The child `node` runs next, or None if no child is left.
        """

    def cleanup(self) -> None:
        """
        Releases what the chooser acquired to choose children, once the statechart
        stopped running.
        """


@dataclass
class ChildChooserAccess(ContextExtension):
    """
    Gives every :class:`CompositeNodeChoosingItsChild` of a statechart the chooser it
    asks.
    """

    chooser: ChildChooser
    """
    The chooser every node choosing its child asks.
    """

    def cleanup(self) -> None:
        self.chooser.cleanup()


@dataclass(eq=False, repr=False)
class CompositeNodeChoosingItsChild(SucceedsOnObservingTrue, CompositeNode):
    """
    Runs a child that is only chosen once this node runs, against the world as the nodes
    before it left it.

    It asks the :class:`ChildChooser` of its context when it starts, and again whenever
    its latest child ended without succeeding. It succeeds with the first child that
    succeeds, and fails once the chooser has no child left.

    A reset puts it back to choosing: the children it chose before never run again, and
    it asks the chooser anew once it starts again.

    .. note:: A chosen child joins the statechart after it compiled, which compiles it
        again, see :meth:`~cramph.statechart.Statechart.modify`. So does a reset of a
        node that had chosen a child or had none left.
    """

    accepts_children_after_compile: bool = field(init=False, default=True)

    _out_of_children: bool = field(default=False, init=False, repr=False)
    """
    Whether the chooser said that no child is left.
    """

    _children_of_earlier_runs: int = field(default=0, init=False, repr=False)
    """
    How many of :attr:`nodes` were chosen before the latest reset.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (ChildChooserAccess,)

    @property
    def ran_out_of_children(self) -> bool:
        """
        :return: Whether the chooser said that no child is left, since the latest
            reset.
        """
        return self._out_of_children

    @property
    def inherent_fail_condition(self) -> Scalar:
        """
        Fails as well once the chooser has no child left, see
        :meth:`~cramph.node.StatechartNode.inherent_fail_condition`.
        """
        if self._out_of_children:
            return Scalar.const_true()
        return super().inherent_fail_condition

    @property
    def can_fail_on_its_own(self) -> bool:
        """
        Always, because the chooser may run out of children at any choice, which no
        condition says before it happens, see
        :meth:`~cramph.node.StatechartNode.can_fail_on_its_own`.
        """
        return True

    @property
    def latest_child(self) -> Optional[StatechartNode]:
        """
        :return: The child chosen last since the latest reset, or None before the first
            such choice.
        """
        if len(self.nodes) == self._children_of_earlier_runs:
            return None
        return self.nodes[-1]

    @property
    def is_waiting_for_a_child(self) -> bool:
        """
        :return: Whether this node runs without a child that could still succeed.
        """
        if self._out_of_children:
            return False
        if self.life_cycle_state != LifeCycleValues.RUNNING:
            return False
        latest_child = self.latest_child
        return latest_child is None or latest_child.life_cycle_state in (
            LifeCycleValues.FAILED,
            LifeCycleValues.INTERRUPTED,
        )

    def choose_child(self, context: StatechartContext) -> None:
        """
        Ask the chooser of `context` for the next child and follow its answer.
        """
        self.choose_child_with(
            context.require_extension(ChildChooserAccess).chooser, context
        )

    def choose_child_with(
        self, chooser: ChildChooser, context: StatechartContext
    ) -> bool:
        """
        Run the child `chooser` chooses next, or fail if it has no child left.

        :param chooser: The chooser to ask.
        :param context: The context the statechart runs in.
        :return: Whether `chooser` answered, rather than having no choice yet.
        """
        if not chooser.has_choice_for(self):
            return False
        child = chooser.choose_child(self, context)
        if child is None:
            self.give_up()
            return True
        self.adopt_chosen_child(child)
        return True

    def adopt_chosen_child(self, child: StatechartNode) -> None:
        """
        Run `child` next, succeeding once it succeeds.
        """
        self._add_child_to_statechart(child)
        self.success_condition = logic_or(self.success_condition, child.is_succeeded)
        self.statechart.request_rebuild(self)

    def give_up(self) -> None:
        """
        Fail, because no child is left to run.
        """
        self._out_of_children = True
        self.statechart.request_rebuild(self)

    def on_reset(self, context: StatechartContext) -> None:
        """
        Go back to choosing: the children chosen so far never start again, and a node
        that had no child left may be given one again.

        .. warning:: Unlike :meth:`~cramph.node.StatechartNode.on_reset` this compiles
            the statechart again, unless nothing was chosen since the latest reset.
        """
        children_of_this_run = self.nodes[self._children_of_earlier_runs :]
        if not children_of_this_run and not self._out_of_children:
            return
        with self.statechart.modify():
            for child in children_of_this_run:
                child.start_condition = Scalar.const_false()
            self._children_of_earlier_runs = len(self.nodes)
            self._out_of_children = False
            self.statechart.request_rebuild(self)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report what the latest child observed last, which outlasts it, because a node
        that ended observes nothing any more.
        """
        latest_child = self.latest_child
        if latest_child is None:
            return NodeArtifacts(
                observation=Scalar(float(ObservationStateValues.UNKNOWN))
            )
        return NodeArtifacts(observation=Scalar(latest_child.last_observation))


# %% running a child grounded from a statement


@dataclass(eq=False, repr=False)
class StatementNode(CompositeNodeChoosingItsChild):
    """
    Runs a node described by an underspecified `a(...)` / `an(...)` statement.

    The statement is grounded only when this node starts, against the world the nodes
    before it left behind; the chooser of the context decides which of its candidates
    run. A plan language node handed a statement runs it through such a node.
    """

    statement: Match = field(
        kw_only=True, metadata=JSONMetadata(serialize=False).as_dict()
    )
    """
    The underspecified statement the children are grounded from.

    Not serialized: a process ticking the statechart elsewhere receives the chosen
    children rather than grounding them itself.
    """

    candidate_limit: int | None = field(default=None, init=False, repr=False)
    """
    How many candidates the current run through the statement yields at most, None
    before the first run.
    """

    _candidates: Generator[Any, None, None] | None = field(
        default=None, init=False, repr=False
    )
    """
    The candidates of the statement, open from the first pull until they are exhausted
    or released by :meth:`stop_grounding`.
    """

    _candidates_pulled: int = field(default=0, init=False, repr=False)
    """
    How many candidates the current run through the statement has yielded.
    """

    @property
    def reached_candidate_limit(self) -> bool:
        """
        :return: Whether the last run through the statement stopped because it yielded
            :attr:`candidate_limit` candidates.
        """
        return self._candidates_pulled == self.candidate_limit

    def next_candidate(
        self, query_backend: QueryBackend, default_candidate_limit: int
    ) -> Any | None:
        """
        Grounds the statement into its next candidate, against the world as it is now.

        The statement is left suspended in between, so the next call resumes where this
        one stopped.

        :param query_backend: The backend answering the statement.
        :param default_candidate_limit: How many candidates a run through a statement
            without a limit of its own yields.
        :return: The next candidate, or None once the statement is exhausted or
            :attr:`candidate_limit` candidates were yielded.
        """
        if self._candidates is None:
            self._candidates_pulled = 0
            self.candidate_limit = self.statement._limit_ or default_candidate_limit
            self._candidates = query_backend.evaluate(self.statement)
        if self.reached_candidate_limit:
            self.stop_grounding()
            return None
        candidate = next(self._candidates, None)
        if candidate is None:
            self._candidates = None
            return None
        self._candidates_pulled += 1
        return candidate

    def stop_grounding(self) -> None:
        """
        Releases the candidates of the statement once no further child will be asked
        for.

        A suspended generator keeps every value its frame holds alive, so closing it
        frees whatever the statement only holds to ground candidates with. The next
        :meth:`next_candidate` grounds the statement anew.
        """
        if self._candidates is None:
            return
        self._candidates.close()
        self._candidates = None

    def cleanup(self, context: StatechartContext) -> None:
        self.stop_grounding()

    @property
    def grounded_nodes(self) -> list[StatechartNode]:
        """
        :return: The node of the statement's type every child chosen so far runs, in
            the order they were chosen, each found below whatever runs it.
        """
        return [
            next(
                node
                for node in [child, *child.descendants]
                if isinstance(node, self.statement._type_)
            )
            for child in self.children
        ]

    def to_json(self, **kwargs) -> dict[str, Any]:
        """
        :return: The JSON representation of the node choosing its child that this is,
            since the statement is not sent.
        """
        return {
            **super().to_json(**kwargs),
            JSONField.TYPE: get_full_class_name(CompositeNodeChoosingItsChild),
        }

    def __repr__(self) -> str:
        return f"{self.statement._type_.__name__}"
