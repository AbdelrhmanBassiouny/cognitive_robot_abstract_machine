from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import rustworkx as rx
from typing_extensions import (
    Any,
    Callable,
    ClassVar,
    List,
    MutableMapping,
    Optional,
    Self,
    Tuple,
    Type,
)

import krrood.symbolic_math.symbolic_math as sm
from cramph.plotters.gantt_chart_plotter import HistoryGanttChartPlotter
from krrood.adapters.json_serializer import SubclassJSONSerializer, from_json, to_json
from krrood.rustworkx_utils.graph_visualizer_base import (
    GraphLayout,
    GraphVisualizerBackend,
    GraphVisualizerBase,
)
from krrood.symbolic_math.symbolic_math import VariableParameters
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import (
    StatechartJSONKey,
    TransitionKind,
    LifeCycleValues,
    LifeCyclePredicate,
    ObservationStateValues,
)
from cramph.exceptions import (
    EmptyStatechartError,
    ConditionScopeError,
    TickDoesNotSettleError,
    CyclicNodeDependencyError,
    NodesMissingContextExtensionsError,
    PrerequisiteNotExpandedError,
    StatechartAlreadyCompiledError,
    NotInStatechartError,
    RemovedNodeStillReferencedError,
)
from cramph.node import (
    CancelStatechart,
    CompositeNode,
    DerivedConditionVariable,
    DeserializedNodeTracker,
    EndStatechart,
    GenericStatechartNode,
    LastObservationVariable,
    LifeCycleVariable,
    ObservationVariable,
    StatechartNode,
    TransitionCondition,
)
from cramph.composites import CompositeNodeChoosingItsChild
from cramph.plotters.graphviz import StatechartGraphviz
from cramph.plotters.interactive_graph import StatechartGraphVisualizer
from semantic_digital_twin.world import ModelRevision
from semantic_digital_twin.world_description.world_entity import (
    WorldEntityReferenceWriter,
)

logger = logging.getLogger(__name__)


@dataclass(repr=False, eq=False)
class State(MutableMapping[StatechartNode, float], SubclassJSONSerializer):
    """
    Maps every node of a statechart to a scalar value, backed by a single
    contiguous array indexed by :attr:`~StatechartNode.index`.
    """

    statechart: Statechart
    """
    The statechart whose nodes are the keys of this mapping.
    """

    default_value: ClassVar[float] = field(init=False)
    """
    The value that :meth:`grow` appends for a newly added node.
    """

    data: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    """
    One entry per node, ordered by :attr:`~StatechartNode.index`.
    """

    def grow(self) -> None:
        """
        Appends the default value to :attr:`data`, keeping it in sync with a newly added
        node.
        """
        self.data = np.append(self.data, self.default_value)

    def life_cycle_symbols(self) -> List[LifeCycleVariable]:
        """
        :return: The life cycle variable of every node, in node order.
        """
        return [node.life_cycle_variable for node in self.statechart.nodes]

    def observation_symbols(self) -> List[ObservationVariable]:
        """
        :return: The observation variable of every node, in node order.
        """
        return [node.observation_variable for node in self.statechart.nodes]

    def last_observation_symbols(self) -> List[LastObservationVariable]:
        """
        :return: The last observation variable of every node, in node order.
        """
        return [node.last_observation for node in self.statechart.nodes]

    def __getitem__(self, node: StatechartNode) -> float:
        """
        :param node: The node to look up.
        :return: The value stored for `node`, read from :attr:`data` at :attr:`~StatechartNode.index`.
        """
        return float(self.data[node.index])

    def __setitem__(self, node: StatechartNode, value: float) -> None:
        """
        Writes `value` into :attr:`data` at `node`'s
        :attr:`~StatechartNode.index`.

        :param node: The node to write the value for.
        :param value: The value to store.
        """
        self.data[node.index] = value

    def __delitem__(self, node: StatechartNode) -> None:
        """
        Removes the entry for `node` from :attr:`data`.

        .. warning:: This shifts the indices of all nodes after `node`, but does not update
            their :attr:`~StatechartNode.index`, so the state and the nodes fall out of sync.

        :param node: The node whose entry to remove.
        """
        self.data = np.delete(self.data, node.index)

    def __iter__(self):
        return iter(self.statechart.nodes)

    def __len__(self) -> int:
        return self.data.shape[0]

    def keys(self) -> List[StatechartNode]:
        """
        :return: All nodes of the statechart, i.e. the keys of this mapping.
        """
        return self.statechart.nodes

    def items(self) -> List[tuple[StatechartNode, float]]:
        """
        :return: (node, value) pairs for every node of the statechart.
        """
        return [(node, self[node]) for node in self.statechart.nodes]

    def values(self) -> List[float]:
        """
        :return: The value of every node, in node order.
        """
        return [self[node] for node in self.keys()]

    def __contains__(self, node: StatechartNode) -> bool:
        return node in self.statechart.nodes

    def __deepcopy__(self, memo) -> Self:
        """
        Create a deep copy of the state.

        :param memo: The memo dict used by :func:`copy.deepcopy` to track already-copied
            objects.
        :return: The deep copy.
        """
        return self.__class__(
            statechart=self.statechart,
            data=self.data.copy(),
        )

    def to_json(self, **kwargs) -> dict[str, Any]:
        """
        :return: The JSON representation of the base class, extended with the raw :attr:`data` array.
        """
        return {**super().to_json(**kwargs), "data": self.data.tolist()}

    @classmethod
    def _from_json(cls, data: dict[str, Any], **kwargs) -> Self:
        """
        Reconstruct a state from its JSON representation.

        :param data: The JSON dict, as produced by :meth:`to_json`.
        :param kwargs: Must contain the owning `statechart`.
        :return: The deserialized state.
        """
        statechart = kwargs["statechart"]
        return cls(
            statechart=statechart,
            data=np.array(data["data"], dtype=np.float64),
        )

    def __str__(self) -> str:
        return str({str(symbol.name): value for symbol, value in self.items()})

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: Self) -> bool:
        """
        :param other: The object to compare against.
        :return: True if `other` is a :class:`State` with the same :attr:`data`.
        .. note:: The owning :attr:`statechart` is not compared.
        """
        if not isinstance(other, State):
            return NotImplemented
        return np.array_equal(self.data, other.data)


@dataclass(repr=False, eq=False)
class LifeCycleState(State):
    """
    The life cycle state of every node in a statechart, see
    :class:`Statechart`.
    """

    default_value: ClassVar[float] = LifeCycleValues.NOT_STARTED
    """
    Every node starts out as not started.
    """

    def __getitem__(self, node: StatechartNode) -> LifeCycleValues:
        """
        :param node: The node to look up.
        :return: The life cycle state of `node`, as a :class:`LifeCycleValues` member.
        """
        return LifeCycleValues(super().__getitem__(node))

    def __str__(self) -> str:
        return str(
            {
                str(symbol.name): LifeCycleValues(value).name
                for symbol, value in self.items()
            }
        )


@dataclass(repr=False, eq=False)
class ObservationState(State):
    """
    The observation state of every node in a statechart, see
    :class:`Statechart`.
    """

    default_value: ClassVar[ObservationStateValues] = ObservationStateValues.UNKNOWN
    """
    A node that is not running is not observing.
    """

    def __getitem__(self, node: StatechartNode) -> ObservationStateValues:
        """
        :param node: The node to look up.
        :return: What `node` observes, as an :class:`ObservationStateValues` member.
        """
        return ObservationStateValues(super().__getitem__(node))


@dataclass(repr=False, eq=False)
class LastObservationState(State):
    """
    The observation every node of a statechart took most recently.

    .. seealso:: :attr:`~cramph.node.StatechartNode.last_observation`
    """

    default_value: ClassVar[ObservationStateValues] = ObservationStateValues.UNKNOWN
    """
    A node that has not started has not observed anything.
    """

    def __getitem__(self, node: StatechartNode) -> ObservationStateValues:
        """
        :param node: The node to look up.
        :return: What `node` observed most recently, as an
            :class:`ObservationStateValues` member.
        """
        return ObservationStateValues(super().__getitem__(node))


# %% settling one tick


class PassInputKind(StrEnum):
    """
    A value per node that a pass through the statechart reads on top of the life
    cycle, observation and last observation states.
    """

    LIFE_CYCLE_AT_CYCLE_START = "life_cycle_at_cycle_start"
    """
    The life cycle state the node entered the tick with.
    """

    TICK_OBSERVATION = "tick_observation"
    """
    What :meth:`~cramph.node.StatechartNode.on_tick`
    returned for the node this tick.
    """

    HAS_TICK_OBSERVATION = "has_tick_observation"
    """
    Whether :meth:`~cramph.node.StatechartNode.on_tick`
    returned an observation for the node this tick.
    """

    OWN_TRANSITION_TAKEN = "own_transition_taken"
    """
    Whether the node already took a transition triggered by its own conditions this
    tick.
    """


@dataclass
class PassInput:
    """
    One value per node of a statechart that a pass reads, together with the
    variables standing for it in the compiled pass.
    """

    variables: List[sm.FloatVariable]
    """
    The variable of every node, in node order.
    """

    data: np.ndarray
    """
    The value of every node, in node order.
    """

    @classmethod
    def create(cls, kind: PassInputKind, nodes: List[StatechartNode]) -> Self:
        """
        :param kind: What the values stand for.
        :param nodes: The nodes to hold a value for, in node order.
        :return: An input holding zero for every node.
        """
        return cls(
            variables=[
                sm.FloatVariable(name=f"{node.life_cycle_variable.name}/{kind}")
                for node in nodes
            ],
            data=np.zeros(len(nodes)),
        )


@dataclass
class LifeCycleChange:
    """
    One node changing its life cycle state during a pass.
    """

    node: StatechartNode
    """
    The node whose life cycle state changed.
    """

    previous_state: LifeCycleValues
    """
    The life cycle state before the change.
    """

    new_state: LifeCycleValues
    """
    The life cycle state after the change.
    """

    def run_callback(self, context: StatechartContext) -> None:
        """
        Calls the callback of :attr:`node` that matches this change, e.g.
        :meth:`~StatechartNode.on_start`. A node that starts paused gets
        :meth:`~StatechartNode.on_start` and then
        :meth:`~StatechartNode.on_pause`. A change with no dedicated callback calls
        nothing.

        :param context: The context passed to the callback.
        """
        match (self.previous_state, self.new_state):
            case (_, LifeCycleValues.NOT_STARTED):
                self.node.on_reset(context=context)
            case (LifeCycleValues.NOT_STARTED, LifeCycleValues.RUNNING):
                self.node.on_start(context=context)
            case (LifeCycleValues.NOT_STARTED, LifeCycleValues.PAUSED):
                self.node.on_start(context=context)
                self.node.on_pause(context=context)
            case (LifeCycleValues.RUNNING, LifeCycleValues.PAUSED):
                self.node.on_pause(context=context)
            case (LifeCycleValues.PAUSED, LifeCycleValues.RUNNING):
                self.node.on_unpause(context=context)
            case (
                (LifeCycleValues.RUNNING | LifeCycleValues.PAUSED),
                _,
            ) if self.new_state.is_terminal:
                self.node.on_end(context=context)


@dataclass
class CompiledTick:
    """
    Brings every node of a statechart to the state it reaches in one tick.

    One compiled pass updates every node at once, reading the states the previous pass
    left. Passes repeat until no state changes, so how deeply nodes are nested does not
    change when they react to each other. Within a pass:

    1. A node observes if it was running when the tick started and is still
       running or paused. Its observation expression reads the states of the previous
       pass. A node that was paused when the tick started and is still running
       or paused keeps its observation. A node that stopped running during this tick keeps
       the observation it stopped on until the next one. Every other node
       observes Unknown.
    2. A node that has neither ended nor started the tick ended takes over its
       observation as its last observation.
    3. Every node takes its next life cycle transition, reading the observations of this
       pass and the life cycle state its parent reaches in this pass. A node takes at
       most one transition triggered by its own conditions per tick;
       transitions its parent forces on it always happen.

    .. note:: Life cycle callbacks run afterwards, once per change and in the order the
        changes happened, so no Python code runs between passes.
    """

    statechart: Statechart
    """
    The statechart whose nodes are updated.
    """

    _pass_budget: int = field(init=False)
    """
    The most passes that may change :attr:`statechart` within one tick,
    :attr:`Statechart.pass_limit` extended by
    :attr:`Statechart.passes_per_nesting_level` for every nesting level it has.
    """

    _nodes: List[StatechartNode] = field(init=False)
    """
    Every node of :attr:`statechart`, in node order.
    """

    _life_cycle_at_cycle_start: PassInput = field(init=False)
    """
    See :attr:`PassInputKind.LIFE_CYCLE_AT_CYCLE_START`.
    """

    _tick_observation: PassInput = field(init=False)
    """
    See :attr:`PassInputKind.TICK_OBSERVATION`.
    """

    _has_tick_observation: PassInput = field(init=False)
    """
    See :attr:`PassInputKind.HAS_TICK_OBSERVATION`.
    """

    _own_transition_taken: PassInput = field(init=False)
    """
    See :attr:`PassInputKind.OWN_TRANSITION_TAKEN`.
    """

    _compiled_pass: sm.CompiledFunction = field(init=False)
    """
    One pass, compiled into one function by :meth:`compile`.
    """

    _next_observation: np.ndarray = field(init=False)
    """
    The observation of every node after the latest pass, a view on the pass output.
    """

    _next_last_observation: np.ndarray = field(init=False)
    """
    The last observation of every node after the latest pass, a view on the pass output.
    """

    _next_life_cycle: np.ndarray = field(init=False)
    """
    The life cycle state of every node after the latest pass, a view on the pass output.
    """

    _next_own_transition_taken: np.ndarray = field(init=False)
    """
    Whether every node took a transition triggered by its own conditions this tick,
    after the latest pass, a view on the pass output.
    """

    def compile(self, context: StatechartContext) -> None:
        """
        Builds one pass through the statechart, compiles it and binds its inputs
        to the state arrays it reads.

        :param context: The context whose world and float variable data a pass reads.
        """
        self._nodes = self.statechart.nodes
        deepest_nesting = max(node.depth for node in self._nodes)
        self._pass_budget = (
            self.statechart.pass_limit
            + self.statechart.passes_per_nesting_level * deepest_nesting
        )
        self._life_cycle_at_cycle_start = PassInput.create(
            PassInputKind.LIFE_CYCLE_AT_CYCLE_START, self._nodes
        )
        self._tick_observation = PassInput.create(
            PassInputKind.TICK_OBSERVATION, self._nodes
        )
        self._has_tick_observation = PassInput.create(
            PassInputKind.HAS_TICK_OBSERVATION, self._nodes
        )
        self._own_transition_taken = PassInput.create(
            PassInputKind.OWN_TRANSITION_TAKEN, self._nodes
        )
        self._compile_pass(context)

    def _compile_pass(self, context: StatechartContext) -> None:
        """
        Compiles :meth:`_create_pass` and binds every input and output.

        :param context: The context whose world and float variable data a pass reads.
        """
        inputs = [
            (
                [node.life_cycle_variable for node in self._nodes],
                self.statechart.life_cycle_state.data,
            ),
            (
                [node.observation_variable for node in self._nodes],
                self.statechart.observation_state.data,
            ),
            (
                [node.last_observation for node in self._nodes],
                self.statechart.last_observation_state.data,
            ),
            *[
                (pass_input.variables, pass_input.data)
                for pass_input in [
                    self._life_cycle_at_cycle_start,
                    self._tick_observation,
                    self._has_tick_observation,
                    self._own_transition_taken,
                ]
            ],
            (context.world.state.get_variables(), context.world.state._data),
            (
                context.float_variable_data.variables,
                context.float_variable_data.data,
            ),
        ]
        self._compiled_pass = self._create_pass().compile(
            parameters=VariableParameters.from_lists(
                *[variables for variables, _ in inputs]
            ),
            sparse=False,
        )
        for argument_index, (_, data) in enumerate(inputs):
            self._compiled_pass.bind_args_to_memory_view(
                arg_idx=argument_index, numpy_array=data
            )
        (
            self._next_observation,
            self._next_last_observation,
            self._next_life_cycle,
            self._next_own_transition_taken,
        ) = np.split(self._compiled_pass.evaluate(), 4)

    def _create_pass(self) -> sm.Vector:
        """
        :return: The observation, last observation, life cycle state and whether an own
            transition was taken of every node after one pass, concatenated in that
            order.
        """
        observations = [
            self._create_observation(node, index)
            for index, node in enumerate(self._nodes)
        ]
        last_observations = [
            sm.if_else(
                condition=sm.logic_or(
                    node.life_cycle_predicate_expression(
                        LifeCyclePredicate.IS_TERMINATED
                    ),
                    LifeCyclePredicate.IS_TERMINATED.expression(
                        self._life_cycle_at_cycle_start.variables[index]
                    ),
                ),
                if_result=node.last_observation,
                else_result=observations[index],
            )
            for index, node in enumerate(self._nodes)
        ]
        next_life_cycles, forced_life_cycles = self._create_next_life_cycles()
        life_cycles = self._read_this_pass_observations(
            sm.Vector(next_life_cycles + forced_life_cycles),
            observations=observations,
            last_observations=last_observations,
        )
        next_life_cycles = list(life_cycles)[: len(self._nodes)]
        forced_life_cycles = list(life_cycles)[len(self._nodes) :]
        own_transitions_taken = [
            sm.logic_or(own_transition_taken, next_life_cycle != forced_life_cycle)
            for next_life_cycle, forced_life_cycle, own_transition_taken in zip(
                next_life_cycles,
                forced_life_cycles,
                self._own_transition_taken.variables,
            )
        ]
        return sm.Vector(
            observations + last_observations + next_life_cycles + own_transitions_taken
        )

    def _create_observation(self, node: StatechartNode, index: int) -> sm.Scalar:
        """
        :param node: The node to build the observation for.
        :param index: The index of `node`.
        :return: What `node` observes after a pass.
        """
        observed = sm.if_else(
            condition=self._has_tick_observation.variables[index],
            if_result=self._tick_observation.variables[index],
            else_result=DerivedConditionVariable.substitute_in(
                node._observation_expression
            ),
        )
        life_cycle_at_cycle_start = self._life_cycle_at_cycle_start.variables[index]
        ran_at_cycle_start = LifeCyclePredicate.IS_RUNNING.expression(
            life_cycle_at_cycle_start
        )
        paused_at_cycle_start = LifeCyclePredicate.IS_PAUSED.expression(
            life_cycle_at_cycle_start
        )
        still_running_or_paused = sm.logic_or(
            node.life_cycle_predicate_expression(LifeCyclePredicate.IS_RUNNING),
            node.life_cycle_predicate_expression(LifeCyclePredicate.IS_PAUSED),
        )
        return sm.if_cases(
            cases=[
                (sm.logic_and(ran_at_cycle_start, still_running_or_paused), observed),
                (
                    sm.logic_and(paused_at_cycle_start, still_running_or_paused),
                    node.observation_variable,
                ),
                (
                    sm.logic_or(ran_at_cycle_start, paused_at_cycle_start),
                    node.last_observation,
                ),
            ],
            else_result=sm.Scalar.const_trinary_unknown(),
        )

    def _create_next_life_cycles(
        self,
    ) -> Tuple[List[sm.Scalar], List[sm.Scalar]]:
        """
        Builds the life cycle state every node reaches in a pass, reading the state its
        parent reaches in the same pass, so a node never starts under a parent that stops
        running in that pass.

        :return: The life cycle state of every node, and the one its parent alone
            forces it into, see
            :meth:`~cramph.node.StatechartNode.create_life_cycle_forced_by_parent`, both
            in node order.
        """
        next_life_cycles: List[Optional[sm.Scalar]] = [None] * len(self._nodes)
        forced_life_cycles: List[Optional[sm.Scalar]] = [None] * len(self._nodes)
        for node in sorted(self._nodes, key=lambda node: node.depth):
            life_cycles = sm.Vector(
                [
                    self._create_next_life_cycle(
                        node,
                        own_transitions_allowed=sm.logic_not(
                            self._own_transition_taken.variables[node.index]
                        ),
                    ),
                    node.create_life_cycle_forced_by_parent(),
                ]
            )
            if node.parent_node is not None:
                life_cycles = life_cycles.substitute(
                    [node.parent_node.life_cycle_variable],
                    [next_life_cycles[node.parent_node_index]],
                )
            next_life_cycles[node.index], forced_life_cycles[node.index] = life_cycles
        return next_life_cycles, forced_life_cycles

    @staticmethod
    def _create_next_life_cycle(
        node: StatechartNode, own_transitions_allowed: sm.Scalar
    ) -> sm.Scalar:
        """
        :param node: The node to build the life cycle state for.
        :param own_transitions_allowed: Whether `node` may still take a transition
            triggered by its own conditions.
        :return: The life cycle state `node` reaches in a pass.
        """
        return sm.if_eq_cases(
            a=node.life_cycle_variable,
            b_result_cases=node.create_lifecycle_transitions(
                own_transitions_allowed
            ).as_cases(),
            else_result=node.life_cycle_variable,
        )

    def _read_this_pass_observations(
        self,
        life_cycles: sm.Vector,
        observations: List[sm.Scalar],
        last_observations: List[sm.Scalar],
    ) -> sm.Vector:
        """
        :param life_cycles: Life cycle transitions whose conditions still read predicates.
        :param observations: The observation of every node after the pass.
        :param last_observations: The last observation of every node after the pass.
        :return: `life_cycles` with every predicate replaced by what it reads, and every
            observation read in the state this pass computes.
        """
        life_cycles = DerivedConditionVariable.substitute_in(life_cycles)
        return life_cycles.substitute(
            [node.observation_variable for node in self._nodes]
            + [node.last_observation for node in self._nodes],
            observations + last_observations,
        )

    def settle(self, context: StatechartContext) -> List[LifeCycleChange]:
        """
        Runs passes until neither a life cycle state nor an observation changes, writing
        the result of every pass into the statechart.

        :param context: The context passed to every
            :meth:`~cramph.node.StatechartNode.on_tick`.
        :return: Every life cycle change, in the order it happened.
        :raises TickDoesNotSettleError: If a pass returns the statechart
            to a state it already had in this tick, which it would then never
            leave, or if more passes than :attr:`_pass_budget` change it.
        """
        np.copyto(
            self._life_cycle_at_cycle_start.data,
            self.statechart.life_cycle_state.data,
        )
        self._own_transition_taken.data.fill(0)
        self._collect_tick_observations(context)
        changes: List[LifeCycleChange] = []
        visited_states = set()
        self._compiled_pass.evaluate()
        for passes_taken in range(self._pass_budget):
            if not self._latest_pass_changed_anything():
                return changes
            visited_states.add(self._current_state())
            if self._state_after_latest_pass() in visited_states:
                self._raise_does_not_settle(passes_taken + 1)
            changes.extend(self._life_cycle_changes_of_latest_pass())
            self._take_over_latest_pass()
            self._compiled_pass.evaluate()
        self._raise_does_not_settle(self._pass_budget)

    def _raise_does_not_settle(self, passes_taken: int) -> None:
        """
        :param passes_taken: The passes that changed the statechart so far.
        :raises TickDoesNotSettleError: Always, naming the nodes the latest pass
            changed.
        """
        raise TickDoesNotSettleError(
            pass_limit=self._pass_budget,
            passes_taken=passes_taken,
            unsettled_nodes=self._nodes_changed_by_latest_pass(),
        )

    def _current_state(self) -> bytes:
        """
        :return: Everything a pass reads that passes change, as one value that can be
            compared and remembered.
        """
        return b"".join(
            [
                self.statechart.life_cycle_state.data.tobytes(),
                self.statechart.observation_state.data.tobytes(),
                self.statechart.last_observation_state.data.tobytes(),
                self._own_transition_taken.data.tobytes(),
            ]
        )

    def _state_after_latest_pass(self) -> bytes:
        """
        :return: What :meth:`_current_state` becomes once the latest pass is taken over.
        """
        return b"".join(
            [
                self._next_life_cycle.tobytes(),
                self._next_observation.tobytes(),
                self._next_last_observation.tobytes(),
                self._next_own_transition_taken.tobytes(),
            ]
        )

    def _latest_pass_changed_anything(self) -> bool:
        """
        :return: Whether the latest pass changed a life cycle state, an observation or a
            last observation.
        """
        return not (
            np.array_equal(self._next_life_cycle, self.statechart.life_cycle_state.data)
            and np.array_equal(
                self._next_observation, self.statechart.observation_state.data
            )
            and np.array_equal(
                self._next_last_observation,
                self.statechart.last_observation_state.data,
            )
        )

    def _nodes_changed_by_latest_pass(self) -> List[StatechartNode]:
        """
        :return: The nodes whose life cycle state, observation or last observation the
            latest pass changed, in node order.
        """
        changed = (
            (self._next_life_cycle != self.statechart.life_cycle_state.data)
            | (self._next_observation != self.statechart.observation_state.data)
            | (
                self._next_last_observation
                != self.statechart.last_observation_state.data
            )
        )
        return [self._nodes[index] for index in np.flatnonzero(changed)]

    def _take_over_latest_pass(self) -> None:
        """
        Writes the result of the latest pass into the states the next pass reads.
        """
        np.copyto(self.statechart.life_cycle_state.data, self._next_life_cycle)
        np.copyto(self.statechart.observation_state.data, self._next_observation)
        np.copyto(
            self.statechart.last_observation_state.data,
            self._next_last_observation,
        )
        np.copyto(self._own_transition_taken.data, self._next_own_transition_taken)

    def _collect_tick_observations(self, context: StatechartContext) -> None:
        """
        Calls :meth:`~cramph.node.StatechartNode.on_tick`
        once for every node running at the start of the tick and keeps what it
        returned for the passes.

        :param context: The context passed to every `on_tick`.
        """
        self._has_tick_observation.data.fill(0)
        running_indices = np.flatnonzero(
            self._life_cycle_at_cycle_start.data == float(LifeCycleValues.RUNNING)
        )
        for index in running_indices:
            tick_observation = self._nodes[index].on_tick(context=context)
            if tick_observation is None:
                continue
            self._tick_observation.data[index] = tick_observation
            self._has_tick_observation.data[index] = 1

    def _life_cycle_changes_of_latest_pass(self) -> List[LifeCycleChange]:
        """
        :return: The life cycle changes of the latest pass, in node order.
        """
        life_cycle = self.statechart.life_cycle_state.data
        return [
            LifeCycleChange(
                node=self._nodes[index],
                previous_state=LifeCycleValues(int(life_cycle[index])),
                new_state=LifeCycleValues(int(self._next_life_cycle[index])),
            )
            for index in np.flatnonzero(self._next_life_cycle != life_cycle)
        ]


@dataclass(repr=False, eq=False)
class StateHistoryItem:
    """
    A snapshot of a :class:`Statechart`'s life cycle and observation state at one
    tick.
    """

    tick_count: int
    """
    The number of ticks run when the snapshot was taken.
    """

    life_cycle_state: LifeCycleState
    """
    The life cycle state of every node at that tick.
    """

    observation_state: ObservationState
    """
    The observation state of every node at that tick.
    """

    def __post_init__(self):
        """
        Deep-copies the given states, so later mutation of the live states does not
        affect this snapshot.
        """
        self.life_cycle_state = deepcopy(self.life_cycle_state)
        self.observation_state = deepcopy(self.observation_state)

    def records(self, node: StatechartNode) -> bool:
        """
        :param node: The node to look up.
        :return: Whether `node` had joined the statechart when this snapshot was taken.
        """
        return node.index < len(self.life_cycle_state.data)

    def __eq__(self, other: StateHistoryItem) -> bool:
        """
        :param other: The item to compare against.
        :return: True if `other` has the same life cycle and observation state.
        .. note:: :attr:`tick_count` is not compared.
        """
        return (
            other.life_cycle_state == self.life_cycle_state
            and other.observation_state == self.observation_state
        )

    def __repr__(self) -> str:
        """
        :return: The name of every node this snapshot records, mapped to its
            observation state and life cycle state name.
        """
        merged = {
            node.name: (
                f"{self.observation_state[node].name} | "
                f"{self.life_cycle_state[node].name}"
            )
            for node in self.life_cycle_state.keys()
            if self.records(node)
        }
        return str(merged)


@dataclass(frozen=True)
class RunTicks:
    """
    The tick a node's run started and, once it has ended, the tick it ended on.
    """

    start_tick: int
    """
    The tick this run started on.
    """

    end_tick: Optional[int]
    """
    The tick this run ended on, None while it is still running.
    """


@dataclass
class StateHistoryObserver(ABC):
    """
    Observes the snapshots a :class:`StateHistory` records.
    """

    @abstractmethod
    def on_state_change(self, history: StateHistory) -> None:
        """
        Observe the newest snapshot after it has been appended.

        :param history: The history containing the changed state.
        """


@dataclass
class StateHistory:
    """
    The recorded sequence of :class:`StateHistoryItem` snapshots of a
    :class:`Statechart`.
    """

    history: List[StateHistoryItem] = field(default_factory=list)
    """
    The snapshots in the order in which they were recorded, without consecutive
    duplicates.
    """

    observers: List[StateHistoryObserver] = field(
        default_factory=list, init=False, repr=False, compare=False
    )
    """
    The observers subscribed to newly recorded snapshots.
    """

    def add_observer(self, observer: StateHistoryObserver) -> None:
        """
        Subscribe an observer once by identity.

        :param observer: The observer to notify when a changed state is recorded.
        """
        if any(registered is observer for registered in self.observers):
            return
        self.observers.append(observer)

    def remove_observer(self, observer: StateHistoryObserver) -> None:
        """
        Remove an observer's subscription if it is present.

        :param observer: The observer whose subscription should end.
        """
        self.observers[:] = [
            registered for registered in self.observers if registered is not observer
        ]

    def append(self, next_item: StateHistoryItem):
        """
        Appends `next_item` and notifies the observers, unless it is equal to the last
        recorded item, in which case it is dropped to avoid storing consecutive
        duplicates.

        :param next_item: The snapshot to append.
        """
        if len(self.history) != 0:
            if next_item == self.history[-1]:
                return
        self.history.append(next_item)
        for observer in tuple(self.observers):
            observer.on_state_change(self)

    def nodes_started_in_latest_item(self) -> List[StatechartNode]:
        """
        :return: The nodes the newest snapshot shows running, or past running, that had
            not started in the snapshot before it, in index order.
        """
        return [
            change.node
            for change in self._life_cycle_changes_of_latest_item()
            if change.previous_state == LifeCycleValues.NOT_STARTED
        ]

    def nodes_ended_in_latest_item(self) -> List[StatechartNode]:
        """
        :return: The nodes that reached a terminal life cycle state in the newest
            snapshot, in index order.
        """
        return [
            change.node
            for change in self._life_cycle_changes_of_latest_item()
            if change.new_state.is_terminal
        ]

    def _life_cycle_changes_of_latest_item(self) -> List[LifeCycleChange]:
        """
        :return: Every change of a life cycle state from the snapshot before the newest
            one to the newest one; a node that joined since changed from not started.
        """
        if not self.history:
            return []
        current = self.history[-1]
        previous = self.history[-2] if len(self.history) > 1 else None
        changes = []
        for node in current.life_cycle_state.keys():
            previous_state = (
                previous.life_cycle_state[node]
                if previous is not None and previous.records(node)
                else LifeCycleValues.NOT_STARTED
            )
            current_state = current.life_cycle_state[node]
            if previous_state != current_state:
                changes.append(
                    LifeCycleChange(
                        node=node,
                        previous_state=previous_state,
                        new_state=current_state,
                    )
                )
        return changes

    def get_life_cycle_history_of_node(
        self, node: StatechartNode
    ) -> list[LifeCycleValues]:
        """
        :param node: The node to fetch the recorded life cycle state for.
        :return: The recorded life cycle state of `node` at every tick since it
            joined, in order.
        """
        return [
            history_item.life_cycle_state[node]
            for history_item in self.items_recording(node)
        ]

    def get_observation_history_of_node(
        self, node: StatechartNode
    ) -> list[ObservationStateValues]:
        """
        :param node: The node to fetch the recorded observation state for.
        :return: The recorded observation state of `node` at every tick since it
            joined, in order.
        """
        return [
            history_item.observation_state[node]
            for history_item in self.items_recording(node)
        ]

    def items_recording(self, node: StatechartNode) -> List[StateHistoryItem]:
        """
        :param node: The node to look up.
        :return: The snapshots taken since `node` joined the statechart, in order.
        """
        return [
            history_item for history_item in self.history if history_item.records(node)
        ]

    def get_current_run_ticks_of_node(self, node: StatechartNode) -> Optional[RunTicks]:
        """
        :param node: The node to look up.
        :return: The start and, once reached, end tick of `node`'s most recent run
            since its last reset, or None if it has not started since then (or
            this history is still empty).
        """
        history = self.items_recording(node)
        if not history:
            return None
        current_state = history[-1].life_cycle_state[node]
        if current_state == LifeCycleValues.NOT_STARTED:
            return None
        start_index = len(history) - 1
        while (
            start_index > 0
            and history[start_index - 1].life_cycle_state[node]
            != LifeCycleValues.NOT_STARTED
        ):
            start_index -= 1
        if not current_state.is_terminal:
            return RunTicks(start_tick=history[start_index].tick_count, end_tick=None)
        end_index = start_index
        while not history[end_index].life_cycle_state[node].is_terminal:
            end_index += 1
        return RunTicks(
            start_tick=history[start_index].tick_count,
            end_tick=history[end_index].tick_count,
        )

    def __len__(self) -> int:
        return len(self.history)


@dataclass
class RecompileCallback(ABC):
    """
    Something told whenever a statechart that already compiled compiles again, because
    nodes joined it or the kinematic structure of its world changed.
    """

    @abstractmethod
    def before_recompile(self) -> bool:
        """
        Start holding still, because the statechart is about to compile again or a node
        is about to choose its child, either of which blocks its tick until it is done.

        The statechart keeps ticking, asking again every tick, until every callback
        answers that it is at rest; only then does it block its tick.

        :return: Whether what this callback drives is at rest.
        """

    @abstractmethod
    def after_recompile(self) -> None:
        """
        React to the statechart having compiled again.
        """


@dataclass
class TakenOverNode:
    """
    A node another composite node took the place of, with what it had before, so that
    a modification that fails afterwards can put it back.
    """

    node: StatechartNode
    """
    The node whose place was taken.
    """

    new_parent: CompositeNode
    """
    The composite node that took its place and became its parent.
    """

    former_parent: CompositeNode | None
    """
    The parent the node had, or None for a top-level node.
    """

    former_conditions: dict[TransitionKind, sm.Scalar]
    """
    The transitions the former parent decided for the node, as they were.
    """

    @classmethod
    def before_taking_over(
        cls, node: StatechartNode, new_parent: CompositeNode
    ) -> TakenOverNode:
        """
        :param node: The node whose place `new_parent` is about to take.
        :param new_parent: The composite node about to take it.
        :return: The node as it is now.
        """
        return cls(
            node=node,
            new_parent=new_parent,
            former_parent=node.parent_node,
            former_conditions={
                transition_kind: node.get_condition(transition_kind)
                for transition_kind in new_parent._transitions_owned_by_parent()
            },
        )

    def put_back(self) -> None:
        """
        Gives the node its former parent, its place among that parent's nodes, and the
        transitions that parent decided for it.
        """
        self.node.parent_node = self.former_parent
        for transition_kind, condition in self.former_conditions.items():
            self.node.set_condition(transition_kind, condition)
        if self.former_parent is not None:
            self.former_parent.list_in_place_of(self.new_parent, self.node)


@dataclass
class StatechartModification:
    """
    Batches changes to a statechart, so that a compiled statechart compiles again only
    once, when the outermost of any nested modifications ends.

    If the block raises, the nodes added inside it are dropped again and the statechart
    stays as it was.
    """

    statechart: Statechart
    """
    The statechart being changed.
    """

    _node_count_at_start: int = field(init=False, default=0)
    """
    How many nodes the statechart held when this modification started.
    """

    _taken_over_count_at_start: int = field(init=False, default=0)
    """
    How many nodes had their place taken in the open modifications when this one
    started.
    """

    def __enter__(self) -> Self:
        self._node_count_at_start = len(self.statechart.nodes)
        self._taken_over_count_at_start = len(self.statechart._taken_over_nodes)
        self.statechart._open_modifications += 1
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        statechart = self.statechart
        statechart._open_modifications -= 1
        if exception is not None:
            statechart._put_back_taken_over_nodes_from(self._taken_over_count_at_start)
            statechart._drop_nodes_from(self._node_count_at_start)
        if statechart._open_modifications == 0:
            statechart._taken_over_nodes.clear()
        if statechart._open_modifications > 0 or not statechart.is_compiled:
            return
        if not statechart._changed_since_compile:
            return
        statechart.compile()


@dataclass
class Statechart(SubclassJSONSerializer):
    """
    Represents a statechart.
    A statechart is a directed graph of nodes and edges.
    Nodes have two states: observation state and life cycle state.
    Life cycle states indicate the current state in the life cycle of the node:
        - NOT_STARTED: the node has not started yet.
        - RUNNING: the node is running.
        - PAUSED: the node is paused.
        - SUCCEEDED: the node's success condition ended it.
        - FAILED: the node's fail condition ended it.
        - INTERRUPTED: the node's interrupt condition ended it, or one of its ancestors
                       ended.
    Out of these 6 states, nodes are only "active" if they are in the RUNNING state, and
    the last 3 are terminal: they are the node's outcome and only left by a reset.
    Observation states indicate the current observation of the node:
        - TrinaryFalse: the thing the node is observing is not True.
        - TrinaryUnknown: the node cannot determine the truth value yet, or is not
                          observing at all.
        - TrinaryTrue: the thing the node is observing is True.
    Only a running node observes. A node that has not started or has reached a terminal
    state reports TrinaryUnknown from the next tick on, while a paused node
    keeps its last observation because it resumes and observes again.
    An observation is re-evaluated every tick and may change in both directions, whereas a
    outcome is latched. A condition is two-valued and may read either through a
    predicate: the observation state of a node through `node.observes_true` or
    `node.observes_false`, or its life cycle state through e.g. `node.is_failed`. What a
    node observes is gone once the tick it ended in is over, so a condition that outlives the node it
    reads has to read something that outlasts it: `node.last_observed_true` keeps whether
    the observation the node took most recently was True, whatever its outcome, and a
    life cycle predicate keeps the outcome. Every tick settles the whole statechart before
    it returns, see :class:`CompiledTick`, so a node waiting on another node's
    outcome starts on the tick that outcome is reached, however deeply either is nested.
    Nodes are connected with edges, or transitions.
    There are 6 types of transitions:
        - start condition: If True, the node transitions from NOT_STARTED to RUNNING,
                           or to PAUSED while its pause condition is True.
        - pause condition: If True, the node transitions from RUNNING to PAUSED.
                           If False, the node transitions from PAUSED to RUNNING.
        - success condition: If True, the node ends from RUNNING or PAUSED as SUCCEEDED.
        - fail condition: If True, the node ends from RUNNING or PAUSED as FAILED.
        - interrupt condition: If True, the node ends from RUNNING or PAUSED as
                               INTERRUPTED.
        - reset condition: If True, the node transitions from any state to NOT_STARTED.
    The condition that ends a node decides its outcome; what the node observes at that
    moment has no say in it. A node ending takes its descendants down with it, and each
    of them is INTERRUPTED, however the node ended.
    If multiple conditions are met, the following order is used:
        1. its own reset condition, or its parent has not started
        2. its own success condition
        3. its own fail condition
        4. its own interrupt condition, or its parent has ended
        5. its own pause condition, or its parent is paused
        6. its own start condition, while its parent is running
    How to use this class:
        1. initialized with the context of the executor that runs it
        2. add nodes.
        3. set the transition conditions of nodes
        4. compile the statechart.
        5. call tick() to update the observation state and life cycle state.
            tick() raises the exception of a CancelStatechart that started, once the
            tick is complete.
        6. call is_ended() to check if the statechart is done.
    """

    context: StatechartContext = field(kw_only=True, repr=False)
    """
    The context the nodes of this statechart are expanded, built and ticked in.
    """

    pass_limit: int = field(default=20, kw_only=True, repr=False)
    """
    The most passes that may change a statechart without nested nodes within one
    tick, so that even at the limit a statechart of a few hundred nodes settles
    within a 50 Hz tick.
    """

    passes_per_nesting_level: int = field(default=2, kw_only=True, repr=False)
    """
    The passes added to :attr:`pass_limit` for every nesting level: one to pass an
    outcome on to the parent, and one for a sibling of that parent to react to it.
    """

    rx_graph: rx.PyDiGraph[StatechartNode] = field(
        default_factory=lambda: rx.PyDAG(multigraph=True), init=False, repr=False
    )
    """
    The underlying graph of the statechart.
    """

    observation_state: ObservationState = field(init=False)
    """
    Combined representation of the observation state of the statechart, to enable
    an efficient tick().
    """

    life_cycle_state: LifeCycleState = field(init=False)
    """
    Combined representation of the life cycle state of the statechart, to enable
    an efficient tick().
    """

    last_observation_state: LastObservationState = field(init=False)
    """
    Combined representation of the observation every node took most recently, to enable
    an efficient tick().
    """

    history: StateHistory = field(default_factory=StateHistory, init=False)
    """
    The history of how the state of the statechart changed over time.
    """

    _compiled_tick: Optional[CompiledTick] = field(default=None, init=False, repr=False)
    """
    Updates every node once per tick, created by :meth:`compile`.
    """

    _open_modifications: int = field(default=0, init=False, repr=False)
    """
    How many :class:`StatechartModification` blocks are open on this statechart.
    """

    _taken_over_nodes: List[TakenOverNode] = field(
        default_factory=list, init=False, repr=False
    )
    """
    The nodes another node took the place of in the open modifications, in order.
    """

    _recompile_callbacks: List[RecompileCallback] = field(
        default_factory=list, init=False, repr=False
    )
    """
    Told whenever this statechart compiles again after it had compiled.
    """

    _held_still: bool = field(default=False, init=False, repr=False)
    """
    Whether every :class:`RecompileCallback` answered that it is at rest, for the step
    blocking the tick that runs right now.
    """

    _changed_since_compile: bool = field(default=False, init=False, repr=False)
    """
    Whether nodes joined or were dropped since the latest compile.
    """

    _compiled_node_count: int = field(default=0, init=False, repr=False)
    """
    How many of the nodes, counted in index order, the latest compile covered.
    """

    _compiled_world_revision: Optional[ModelRevision] = field(
        default=None, init=False, repr=False
    )
    """
    The kinematic structure of the world the nodes were last built against.
    """

    _nodes: List[StatechartNode] = field(default_factory=list, init=False, repr=False)
    """
    Cache of all nodes in index order, appended to in :meth:`add_node`.

    Reading this instead of rebuilding the list from `rx_graph` on every access is what
    keeps :meth:`tick` cheap.
    """

    _nodes_to_rebuild: List[StatechartNode] = field(
        default_factory=list, init=False, repr=False
    )
    """
    Nodes the latest compile covered whose expressions changed since, so the next
    compile builds them again.
    """

    _choosing_nodes: List[CompositeNodeChoosingItsChild] = field(
        default_factory=list, init=False, repr=False
    )
    """
    Cache of all :class:`~cramph.composites.CompositeNodeChoosingItsChild` nodes,
    checked every tick in :meth:`_let_waiting_nodes_choose_their_child`.
    """

    _cancel_nodes: List[CancelStatechart] = field(
        default_factory=list, init=False, repr=False
    )
    """
    Cache of all :class:`CancelStatechart` nodes, checked every tick in
    :meth:`_raise_if_cancelled`.
    """

    _end_nodes: List[EndStatechart] = field(
        default_factory=list, init=False, repr=False
    )
    """
    Cache of all :class:`EndStatechart` nodes, checked every tick in :meth:`is_ended`.
    """

    def __post_init__(self):
        """
        Creates the (initially empty) life cycle, observation and last observation
        states for this statechart.
        """
        self.life_cycle_state = LifeCycleState(self)
        self.observation_state = ObservationState(self)
        self.last_observation_state = LastObservationState(self)

    def create_structure_copy(self) -> Statechart:
        """
        Creates a copy of the statechart, where every node is an instance of the base
        class of its kind, see
        :meth:`~cramph.node.StatechartNode.create_structure_copy`.

        This is useful if only the structure of the statechart is needed, for
        example, for visualization.

        :return: The structural copy.
        """
        statechart_copy = Statechart(context=self.context)
        # copy nodes in order to make sure index is correct
        for node in self.nodes:
            statechart_copy._register_node(node.create_structure_copy())
        # link parent/child
        for node in self.get_nodes_by_type(CompositeNode):
            goal_copy: CompositeNode = statechart_copy.get_node_by_index(node.index)
            for child_node in node.nodes:
                child_node_copy = statechart_copy.get_node_by_index(child_node.index)
                child_node_copy.parent_node_index = node.index
                goal_copy.nodes.append(child_node_copy)
        # copy conditions and plot specs
        for node in self.nodes:
            node_copy = statechart_copy.get_node_by_index(node.index)
            node_copy.plot_specifications = deepcopy(node.plot_specifications)
            for transition_kind in TransitionKind:
                node_copy.set_condition(
                    transition_kind,
                    statechart_copy._copy_condition(
                        node.get_condition(transition_kind)
                    ),
                )
        return statechart_copy

    def _copy_condition(self, condition: sm.Scalar) -> sm.Scalar:
        """
        :param condition: A condition of the chart this chart is a structural copy of.
        :return: The same condition, reading the nodes of this chart with the same index.
        """
        variables: List[DerivedConditionVariable] = condition.free_variables()
        if not variables:
            return condition
        return sm.Scalar(condition).substitute(
            variables,
            [
                variable.for_node(
                    self.get_node_by_index(variable.statechart_node.index)
                )
                for variable in variables
            ],
        )

    @property
    def nodes(self) -> List[StatechartNode]:
        """
        :return: All nodes of the statechart.
        """
        return list(self._nodes)

    @property
    def top_level_nodes(self) -> List[StatechartNode]:
        """
        :return: All nodes that don't belong to a CompositeNode.
        """
        return [node for node in self.nodes if node.parent_node is None]

    @property
    def edges(self) -> List[TransitionCondition]:
        """
        The edges of the underlying graph.

        .. warning:: This may return duplicate edges if a transition uses multiple nodes.

        :return: The edges of the underlying graph.
        """
        return self.rx_graph.edges()

    @property
    def unique_edges(self) -> List[TransitionCondition]:
        """
        :return: The edges of the statechart, without duplicates.
        """
        return list(set(self.edges))

    @property
    def is_compiled(self) -> bool:
        """
        :return: Whether :meth:`compile` ran.
        """
        return self._compiled_tick is not None

    def modify(self) -> StatechartModification:
        """
        :return: A block batching changes to this statechart. A compiled statechart
            compiles again once the outermost block ends, keeping the state and the
            history of the nodes it already held.
        """
        return StatechartModification(statechart=self)

    def add_recompile_callback(self, callback: RecompileCallback) -> None:
        """
        :param callback: Told whenever this statechart compiles again after it had
            compiled. A callback already registered is not added twice.
        """
        if any(registered is callback for registered in self._recompile_callbacks):
            return
        self._recompile_callbacks.append(callback)

    def request_rebuild(self, node: StatechartNode) -> None:
        """
        Builds `node` again on the next compile, because an expression it builds from
        changed, such as the children it reads.

        Called outside a :meth:`modify` block, the statechart compiles right away.

        :param node: A node of this statechart.
        """
        with self.modify():
            if node not in self._nodes_to_rebuild:
                self._nodes_to_rebuild.append(node)
            self._changed_since_compile = True

    def add_node(self, node: StatechartNode):
        """
        Adds a node to the statechart, and expands it right away if it is a
        :class:`CompositeNode`, which adds its children in turn.

        A compiled statechart compiles again once the node joined, or once the
        outermost :meth:`modify` block around the addition ends.

        :param node: The node to add.
        :raises PrerequisiteNotExpandedError: If `node` is a composite node that reads
            a composite node which has not joined this statechart yet.
        """
        with self.modify():
            self._register_node(node)
            if isinstance(node, CompositeNode):
                self._expand(node)

    def add_node_above(self, node: StatechartNode, new_parent: CompositeNode) -> None:
        """
        Adds `new_parent` to the statechart in the place of `node`, which becomes its
        child: `new_parent` gets the parent `node` had, or joins the top level if `node`
        was on it.

        :param node: A node of this statechart, held by its parent among its nodes.
        :param new_parent: A composite node outside any statechart that runs `node`.
        :raises NotInStatechartError: If `node` does not belong to this statechart.
        :raises StatechartAlreadyCompiledError: If the latest compile covers `node`.
        """
        if node._statechart is not self:
            raise NotInStatechartError(name=node.name)
        if self.is_compiled and self.latest_compile_covers(node):
            raise StatechartAlreadyCompiledError()
        with self.modify():
            self._register_node(new_parent)
            self._taken_over_nodes.append(
                TakenOverNode.before_taking_over(node, new_parent)
            )
            former_parent = node.parent_node
            new_parent.parent_node = former_parent
            if former_parent is not None:
                former_parent.list_in_place_of(node, new_parent)
            new_parent.take_over(node)
            self._expand(new_parent)

    def latest_compile_covers(self, node: StatechartNode) -> bool:
        """
        :param node: A node of this statechart.
        :return: Whether the latest compile covered `node`, which fixed its wiring.
        """
        return node.index < self._compiled_node_count

    def _put_back_taken_over_nodes_from(self, first_put_back: int) -> None:
        """
        Puts back every node whose place was taken from `first_put_back` on, the latest
        first.

        :param first_put_back: The position of the first record to undo in
            :attr:`_taken_over_nodes`.
        """
        for taken_over in reversed(self._taken_over_nodes[first_put_back:]):
            taken_over.put_back()
        del self._taken_over_nodes[first_put_back:]

    def _drop_nodes_from(self, first_dropped_index: int) -> None:
        """
        Drops every node from `first_dropped_index` on, which no compile covered yet.

        :param first_dropped_index: The index of the first node to drop.
        """
        if first_dropped_index == len(self._nodes):
            return
        self._changed_since_compile = True
        kept_nodes = self._nodes[:first_dropped_index]
        for dropped_node in self._nodes[first_dropped_index:]:
            parent_node = dropped_node.parent_node
            if parent_node in kept_nodes and dropped_node in parent_node.nodes:
                parent_node.nodes.remove(dropped_node)
            dropped_node._statechart = None
            dropped_node.index = None
            dropped_node.parent_node_index = None
        self._renumber(kept_nodes)

    def _expand(self, node: CompositeNode) -> None:
        """
        Expands `node` in :attr:`context`, once every composite node it reads while
        expanding has joined this statechart.

        :param node: The composite node that just joined this statechart.
        :raises NodesMissingContextExtensionsError: If :attr:`context` lacks an
            extension `node` requires, to expand or afterwards.
        """
        for prerequisite in node.prerequisite_nodes:
            if isinstance(prerequisite, CompositeNode) and (
                prerequisite._statechart is not self
            ):
                raise PrerequisiteNotExpandedError(node=node, prerequisite=prerequisite)
        self._check_context_holds(
            [node],
            lambda expanding_node: expanding_node.required_context_extensions
            + expanding_node.context_extensions_required_to_expand,
        )
        node.expand(self.context)

    def _register_node(self, node: StatechartNode) -> None:
        """
        Adds a node to the statechart without expanding it, and finalizes its
        initialization.

        :param node: The node to add.
        """
        node.statechart = self
        node.index = self.rx_graph.add_node(node)
        self.life_cycle_state.grow()
        self.observation_state.grow()
        self.last_observation_state.grow()
        self._nodes.append(node)
        self._changed_since_compile = True
        if isinstance(node, CancelStatechart):
            self._cancel_nodes.append(node)
        if isinstance(node, EndStatechart):
            self._end_nodes.append(node)
        if isinstance(node, CompositeNodeChoosingItsChild):
            self._choosing_nodes.append(node)

    def remove_node(self, node: StatechartNode) -> None:
        """
        Removes a node and everything below it from the statechart, and from the node
        it is a child of.

        The nodes that stay keep their order and are numbered anew without gaps.

        :param node: The node to remove.
        :raises NotInStatechartError: If `node` does not belong to this statechart.
        :raises StatechartAlreadyCompiledError: If the latest compile covers `node`.
        :raises RemovedNodeStillReferencedError: If a node that stays refers to a
            removed node through a condition or as a prerequisite.
        """
        if node._statechart is not self:
            raise NotInStatechartError(name=node.name)
        if self.is_compiled and self.latest_compile_covers(node):
            raise StatechartAlreadyCompiledError()
        removed_nodes = [node, *node.descendants]
        kept_nodes = [kept for kept in self._nodes if kept not in removed_nodes]
        self._check_not_referenced(removed_nodes, kept_nodes)
        parent_node = node.parent_node
        if parent_node is not None and node in parent_node.nodes:
            parent_node.nodes.remove(node)
        self._renumber(kept_nodes)
        self._nodes_to_rebuild = [
            rebuilt for rebuilt in self._nodes_to_rebuild if rebuilt in kept_nodes
        ]
        for removed_node in removed_nodes:
            removed_node._statechart = None
            removed_node.index = None
            removed_node.parent_node_index = None

    @staticmethod
    def _check_not_referenced(
        removed_nodes: List[StatechartNode], kept_nodes: List[StatechartNode]
    ) -> None:
        """
        :raises RemovedNodeStillReferencedError: If a node of `kept_nodes` refers to a
            node of `removed_nodes` through a condition or as a prerequisite.
        """
        for kept_node in kept_nodes:
            referenced_nodes = list(kept_node.prerequisite_nodes) + [
                dependency
                for condition in kept_node.effective_conditions
                for dependency in condition.node_dependencies
            ]
            for referenced_node in referenced_nodes:
                if referenced_node in removed_nodes:
                    raise RemovedNodeStillReferencedError(
                        removed_node=referenced_node, referencing_node=kept_node
                    )

    def _renumber(self, kept_nodes: List[StatechartNode]) -> None:
        """
        Keeps only `kept_nodes`, numbering them anew in their current order.

        The graph loses its edges, which the next compile adds again.

        :param kept_nodes: The nodes that stay, in index order.
        """
        kept_indices = [kept_node.index for kept_node in kept_nodes]
        new_index_of = {old: new for new, old in enumerate(kept_indices)}
        for state in (
            self.life_cycle_state,
            self.observation_state,
            self.last_observation_state,
        ):
            state.data = state.data[kept_indices]
        for kept_node in kept_nodes:
            if kept_node.parent_node_index is not None:
                kept_node.parent_node_index = new_index_of[kept_node.parent_node_index]
        self.rx_graph = rx.PyDAG(multigraph=True)
        for kept_node in kept_nodes:
            kept_node.index = self.rx_graph.add_node(kept_node)
        self._nodes = kept_nodes
        self._cancel_nodes = [
            cancel_node
            for cancel_node in self._cancel_nodes
            if cancel_node in kept_nodes
        ]
        self._end_nodes = [
            end_node for end_node in self._end_nodes if end_node in kept_nodes
        ]
        self._choosing_nodes = [
            choosing_node
            for choosing_node in self._choosing_nodes
            if choosing_node in kept_nodes
        ]

    def add_nodes(self, nodes: List[StatechartNode]):
        """
        Adds every node in `nodes` to the statechart in one :meth:`modify` block, see
        :meth:`add_node`.

        :param nodes: The nodes to add.
        """
        with self.modify():
            for node in nodes:
                self.add_node(node)

    def get_node_by_index(self, index: int) -> StatechartNode:
        """
        :param index: The :attr:`~StatechartNode.index` of the node to look up.
        :return: The node with the given index.
        """
        return self.rx_graph.get_node_data(index)

    def _add_transitions(self):
        """
        Rebuilds the graph's edges from the current transition conditions of every node.

        .. note:: Must run after goal expansion, because parent relationships are only
            known then.

        :raises ConditionScopeError: If a condition references a node from a different
            scope level, in which case the edges are left as they were.
        """
        conditions_by_owner = [
            (node, condition)
            for node in self.nodes
            for condition in node.effective_conditions
        ]
        for owner, condition in conditions_by_owner:
            self._validate_condition_scope(owner, condition)
        self.rx_graph.clear_edges()
        for owner, condition in conditions_by_owner:
            self._create_edge_for_condition(owner, condition)

    def _validate_condition_scope(
        self, owner: StatechartNode, condition: TransitionCondition
    ):
        """
        Checks that `condition` only depends on `owner` itself, siblings of `owner` or
        direct children of `owner`.

        :param owner: The node that owns `condition`.
        :param condition: The condition to validate.
        :raises ConditionScopeError: If `condition` depends on a node from a different
            scope level.
        """
        for variable in condition.variables:
            dependency = variable.statechart_node
            if dependency is owner:
                continue
            if dependency.parent_node is owner.parent_node:
                continue
            if dependency.parent_node is owner:
                continue
            raise ConditionScopeError(
                condition=condition,
                new_expression=condition.expression,
                dependency=dependency,
            )

    def _create_edge_for_condition(
        self, owner: StatechartNode, condition: TransitionCondition
    ):
        """
        Adds an edge from `owner` to every node `condition` depends on.

        :param owner: The node the edges originate from.
        :param condition: The condition whose node dependencies become edge targets.
        """
        for parent_node in condition.node_dependencies:
            self.rx_graph.add_edge(owner.index, parent_node.index, condition)

    def _build_nodes(self, context: StatechartContext, nodes: List[StatechartNode]):
        """
        Builds `nodes` and applies their resulting artifacts, leaving every other node
        of the statechart as it was built already.

        :param context: The build context passed to every node's build.
        :param nodes: The nodes to build.
        """
        built_node_indices = {node.index for node in self.nodes} - {
            node.index for node in nodes
        }
        for node in nodes:
            self._build_and_apply_artifacts(node, context, built_node_indices, [])

    def _build_and_apply_artifacts(
        self,
        node: StatechartNode,
        context: StatechartContext,
        built_node_indices: set[int],
        dependency_chain: List[StatechartNode],
    ):
        """
        Builds `node`, recursively building the nodes it depends on and, if it is a
        :class:`CompositeNode`, its children first, then stores the resulting
        :class:`~cramph.node.NodeArtifacts` on the node.

        Already-built nodes (tracked via `built_node_indices`) are skipped.

        :param node: The node to build.
        :param context: The build context passed to :meth:`~cramph.node.StatechartNode.build`.
        :param built_node_indices: The indices of nodes already built, updated in place.
        :param dependency_chain: The nodes currently being built, used to detect cycles.
        """
        if node.index in built_node_indices:
            return
        self._check_no_dependency_cycle(node, dependency_chain)
        chain = dependency_chain + [node]
        for dependency in node.prerequisite_nodes:
            self._build_and_apply_artifacts(
                dependency, context, built_node_indices, chain
            )
        if isinstance(node, CompositeNode):
            for child_node in node.nodes:
                self._build_and_apply_artifacts(
                    child_node, context, built_node_indices, chain
                )
        built_node_indices.add(node.index)
        node.apply_artifacts(node.build(context=context))

    def _check_no_dependency_cycle(
        self,
        node: StatechartNode,
        dependency_chain: List[StatechartNode],
    ) -> None:
        """
        Raises if `node` already appears in the chain of nodes currently being expanded
        or built, which would otherwise recurse forever.

        :param node: The node to check.
        :param dependency_chain: The nodes currently being expanded or built.
        """
        if node not in dependency_chain:
            return
        cycle_start = dependency_chain.index(node)
        raise CyclicNodeDependencyError(
            node=node, cycle=dependency_chain[cycle_start:] + [node]
        )

    def compile(self):
        """
        Compiles all components of the statechart in its :attr:`context`.
        This method must be called before tick().

        Compiling again, once nodes joined, keeps the state and the history of the
        nodes already there: only the joined nodes are completed and built, and the
        tick is compiled over every node. Every :class:`RecompileCallback` is told.
        """
        is_recompile = self.is_compiled
        if is_recompile:
            self._hold_still()
        self.sanity_check()
        self._compile_nodes(self._nodes[self._compiled_node_count :])
        if is_recompile:
            for callback in list(self._recompile_callbacks):
                callback.after_recompile()
            return
        self.history.append(
            next_item=StateHistoryItem(
                tick_count=0,
                life_cycle_state=self.life_cycle_state,
                observation_state=self.observation_state,
            )
        )

    def _compile_nodes(self, nodes: List[StatechartNode]) -> None:
        """
        Completes `nodes`, builds them, or every node if the kinematic structure of
        the world changed since the nodes were built, then compiles the tick over
        every node.

        :param nodes: The nodes no compile covered yet.
        """
        goals = [node for node in nodes if isinstance(node, CompositeNode)]
        self._check_children_of_goals(goals)
        self._check_context_holds(
            nodes, lambda compiled_node: compiled_node.required_context_extensions
        )
        if self._world_structure_changed():
            nodes_to_build = self.nodes
        else:
            nodes_to_build = self._nodes_to_rebuild + [
                node for node in nodes if node not in self._nodes_to_rebuild
            ]
        self._build_nodes(context=self.context, nodes=nodes_to_build)
        self._compile_tick()
        self._compiled_node_count = len(self._nodes)
        self._changed_since_compile = False
        self._nodes_to_rebuild = []

    def _compile_tick(self) -> None:
        """
        Compiles the tick over every node as currently built, against the current
        kinematic structure of the world.
        """
        self._add_transitions()
        self._compiled_tick = CompiledTick(statechart=self)
        self._compiled_tick.compile(context=self.context)
        self._compiled_world_revision = self._world_revision()

    def _world_revision(self) -> ModelRevision:
        """
        :return: The current kinematic structure of the world of :attr:`context`.
        """
        return self.context.world.get_world_model_manager().revision

    def _world_structure_changed(self) -> bool:
        """
        :return: Whether the kinematic structure of the world changed since the nodes
            were last built.
        """
        return self._world_revision() != self._compiled_world_revision

    def _rebuild_if_world_structure_changed(self) -> None:
        """
        Compiles again, building every node again, if the kinematic structure of the
        world changed since they were built, because expressions reading the
        structure, such as forward kinematics, describe the old one.

        The state, the history and what each node registered in
        :meth:`~cramph.node.StatechartNode.set_up` are kept, so the statechart goes on
        from where it was.
        """
        if self._world_structure_changed():
            self._when_held_still(self.compile)

    def _hold_still(self) -> bool:
        """
        Ask every :class:`RecompileCallback` to hold still, unless they already answered
        that they are at rest for the step running now.

        :return: Whether all of them are at rest.
        """
        if self._held_still:
            return True
        answers = [
            callback.before_recompile() for callback in self._recompile_callbacks
        ]
        return all(answers)

    def _when_held_still(self, step: Callable[[], None]) -> None:
        """
        Run `step`, which blocks the tick, once every :class:`RecompileCallback` is at
        rest; until then the statechart goes on ticking and asks again next tick.

        :param step: What blocks the tick.
        """
        if not self._hold_still():
            return
        self._held_still = True
        try:
            step()
        finally:
            self._held_still = False

    @staticmethod
    def _check_children_of_goals(goals: List[CompositeNode]) -> None:
        """
        Lets every goal in `goals` reject the children it was expanded with.
        """
        for goal in goals:
            goal.check_children()

    def _check_context_holds(
        self,
        nodes: list[StatechartNode],
        required_extensions_of: Callable[
            [StatechartNode], tuple[type[ContextExtension], ...]
        ],
    ) -> None:
        """
        :param nodes: The nodes to check.
        :param required_extensions_of: Gives the extension types a node requires.
        :raises NodesMissingContextExtensionsError: If :attr:`context` lacks an
            extension a node in `nodes` requires.
        """
        nodes_by_missing_extension = {}
        for node in nodes:
            for extension_type in required_extensions_of(node):
                if self.context.get_extension(extension_type) is None:
                    nodes_by_missing_extension.setdefault(extension_type, []).append(
                        node
                    )
        if nodes_by_missing_extension:
            raise NodesMissingContextExtensionsError(
                nodes_by_missing_extension=nodes_by_missing_extension
            )

    def tick(self):
        """
        Executes a single tick of the statechart in its :attr:`context`.

        Every node is brought to the state it reaches in this tick, see
        :class:`CompiledTick`, then the life cycle callbacks of every change run
        and the tick is recorded. A :class:`CancelStatechart` that started in this
        tick ends the statechart only after that, even if a
        :class:`StateHistoryObserver` of the record failed.

        If the kinematic structure of the world changed since the previous tick, every
        node is built again before this tick settles, see
        :meth:`~cramph.node.StatechartNode.build`; a change made by a callback of this
        tick is picked up by the next one.
        """
        self._rebuild_if_world_structure_changed()
        changes = self._compiled_tick.settle(self.context)
        for change in changes:
            change.run_callback(self.context)
        self._let_waiting_nodes_choose_their_child()
        try:
            self.history.append(
                next_item=StateHistoryItem(
                    tick_count=self.context.tick_count,
                    life_cycle_state=self.life_cycle_state,
                    observation_state=self.observation_state,
                )
            )
        finally:
            self._raise_if_cancelled()

    def _let_waiting_nodes_choose_their_child(self) -> None:
        """
        Lets every node waiting for a child choose one, in one :meth:`modify` block,
        so the statechart compiles at most once for all of them.

        Choosing blocks the tick the way compiling does, so it waits until every
        :class:`RecompileCallback` is at rest, and a choice is made against a world that
        holds still.
        """
        waiting_nodes = [
            node for node in self._choosing_nodes if node.is_waiting_for_a_child
        ]
        if not waiting_nodes:
            return
        self._when_held_still(lambda: self._choose_children_of(waiting_nodes))

    def _choose_children_of(
        self, waiting_nodes: List[CompositeNodeChoosingItsChild]
    ) -> None:
        """
        Let every node of `waiting_nodes` choose its child, compiling once for all.
        """
        with self.modify():
            for node in waiting_nodes:
                node.choose_child(self.context)

    def get_nodes_by_type(
        self, node_type: Type[GenericStatechartNode]
    ) -> List[GenericStatechartNode]:
        """
        :param node_type: The node type to filter for.
        :return: All nodes that are an instance of `node_type`.
        """
        return [node for node in self.nodes if isinstance(node, node_type)]

    def get_preceding_node_by_type(
        self, node: StatechartNode, node_type: Type[GenericStatechartNode]
    ) -> Optional[GenericStatechartNode]:
        """
        :param node: A node of this statechart.
        :param node_type: The node type to look for.
        :return: The closest node of `node_type` that runs before `node`, see
            :meth:`get_preceding_nodes_by_type`, or None if there is none.
        """
        return next(iter(self.get_preceding_nodes_by_type(node, node_type)), None)

    def get_preceding_nodes_by_type(
        self, node: StatechartNode, node_type: Type[GenericStatechartNode]
    ) -> list[GenericStatechartNode]:
        """
        :param node: A node of this statechart.
        :param node_type: The node type to look for.
        :return: Every node of `node_type` that runs before `node`, closest first,
            searching the nodes left of `node` and of each of its ancestors.
        """
        return [
            earlier
            for ancestor_or_self in [node, *node.path]
            for sibling in reversed(ancestor_or_self.left_siblings)
            for earlier in reversed([sibling, *sibling.descendants])
            if isinstance(earlier, node_type)
        ]

    def is_ended(self) -> bool:
        """
        :return: True if the statechart is done, meaning at least one
            :class:`EndStatechart` observes True, False otherwise.
        """
        return any(
            self.observation_state[node] == ObservationStateValues.TRUE
            for node in self._end_nodes
        )

    def _raise_if_cancelled(self):
        """
        Raises the exception of the first :class:`CancelStatechart` node that started in
        the current tick.
        """
        for node in self._cancel_nodes:
            node.raise_pending_exception()

    def cleanup_nodes(self):
        """
        Calls :meth:`~StatechartNode.cleanup` on every node, in :attr:`context`.
        """
        for node in self.nodes:
            node.cleanup(self.context)

    def draw(self, file_name: str):
        """
        Uses graphviz to draw the statechart and safe it at `file_name`.

        :param file_name: Where to save the resulting file.
        """
        StatechartGraphviz(self).to_dot_graph_pdf(file_name=file_name)

    @property
    def layers(self) -> List[List[StatechartNode]]:
        """
        :return: The nodes layer by layer, from the top-level nodes down to the most
            deeply nested children, each layer in order.
        """
        layers = []
        layer = self.top_level_nodes
        while layer:
            layers.append(layer)
            layer = [child for node in layer for child in node.children]
        return layers

    def visualize(
        self,
        backend: GraphVisualizerBackend = GraphVisualizerBackend.CYTOSCAPE,
        layout: GraphLayout = GraphLayout.LAYERED,
    ) -> GraphVisualizerBase:
        """
        Open an interactive visualization of the nodes and the nodes they run, see
        :class:`~cramph.plotters.interactive_graph.StatechartGraphVisualizer`.

        :param backend: The rendering technology to use.
        :param layout: The algorithm used to place the nodes.
        :return: The running visualizer.
        """
        visualizer = StatechartGraphVisualizer(self).create_visualizer(
            backend=backend, layout=layout
        )
        visualizer.run()
        return visualizer

    def plot_gantt_chart(
        self,
        path: str = "./ganttchart.pdf",
        context: StatechartContext = None,
        second_length_in_cm: float = 2.0,
    ):
        """
        Renders a Gantt chart of :attr:`history` and saves it at `path`.

        :param path: Where to save the resulting PDF.
        :param context: If given, the x-axis is scaled to seconds using its
            :attr:`~StatechartContext.tick_duration` instead of ticks.
        :param second_length_in_cm: Width in cm of one second on the x-axis.
        """
        HistoryGanttChartPlotter(
            self, second_width_in_cm=second_length_in_cm, context=context
        ).plot_gantt_chart(path)

    def to_json(self, **kwargs) -> dict[str, Any]:
        """
        World entities are written as references, because whoever reads a
        statechart resolves them against its own world, which has the same entities.

        :return: The JSON representation of this statechart, including all nodes
            and the transition conditions of every node the document holds.
        """
        return {
            **super().to_json(**kwargs),
            **self.nodes_from_to_json(first_node_index=0, **kwargs),
        }

    def nodes_from_to_json(self, first_node_index: int, **kwargs) -> dict[str, Any]:
        """
        World entities are written as references, see :meth:`to_json`.

        :param first_node_index: The index of the first node to write.
        :return: The JSON representation of the nodes from `first_node_index` on and
            of their transition conditions, which :meth:`add_nodes_from_json` adds to
            a statechart holding the nodes before them.
        """
        kwargs = {**kwargs, **WorldEntityReferenceWriter().create_kwargs()}
        written_nodes = self.nodes[first_node_index:]
        return {
            StatechartJSONKey.NODES: [
                to_json(node, **kwargs) for node in written_nodes
            ],
            StatechartJSONKey.CONDITIONS: [
                condition.to_json(**kwargs)
                for node in written_nodes
                for condition in node.conditions
            ],
        }

    @classmethod
    def _from_json(
        cls, data: dict[str, Any], *, context: StatechartContext, **kwargs
    ) -> Self:
        """
        Reconstructs a statechart from its JSON representation, as produced by
        :meth:`to_json`: first all nodes, then the transition conditions of every node
        the document holds, then goal/child parent links. A goal that serializes its own nodes already holds
        them, so it is not handed them a second time. The goals are not expanded again,
        because they expanded before they were serialized.

        :param data: The JSON dict.
        :param context: The context the deserialized statechart is built and run in.
        :param kwargs: Forwarded to :func:`~krrood.adapters.json_serializer.from_json`
            for every node.
        :return: The deserialized statechart.
        """
        statechart = cls(context=context)
        statechart._register_nodes_from_json(data, **kwargs)
        return statechart

    def add_nodes_from_json(self, data: dict[str, Any], **kwargs) -> None:
        """
        Adds the nodes written by :meth:`nodes_from_to_json` of a statechart holding
        the same nodes as this one before them, in one :meth:`modify` block.

        The nodes are not expanded again, because they expanded before they were
        written, and their conditions may read the nodes this statechart already
        holds.

        :param data: The JSON dict.
        :param kwargs: Forwarded to :func:`~krrood.adapters.json_serializer.from_json`
            for every node.
        """
        with self.modify():
            self._register_nodes_from_json(
                data,
                **{
                    **DeserializedNodeTracker.from_statechart(self).create_kwargs(),
                    **kwargs,
                },
            )

    def _register_nodes_from_json(self, data: dict[str, Any], **kwargs) -> None:
        """
        Registers the written nodes, then their transition conditions, then links every
        one of them to the goal it is a child of. A goal that serializes its own nodes
        already holds them, so it is not handed them a second time.
        """
        DeserializedNodeTracker.from_kwargs(kwargs)
        added_nodes = []
        for json_data in data[StatechartJSONKey.NODES]:
            node = from_json(json_data, **kwargs)
            self._register_node(node)
            added_nodes.append(node)
        for json_data in data[StatechartJSONKey.CONDITIONS]:
            transition = TransitionCondition.from_json(json_data, **kwargs)
            transition.owner._set_transition(transition)
        for node in added_nodes:
            if node.parent_node_index is None:
                continue
            parent_node = self.get_node_by_index(node.parent_node_index)
            if node not in parent_node.nodes:
                parent_node.nodes.append(node)

    def sanity_check(self):
        """
        Executes a sanity check on the statechart to ensure that it is valid.
        """
        if len(self.nodes) == 0:
            raise EmptyStatechartError()
