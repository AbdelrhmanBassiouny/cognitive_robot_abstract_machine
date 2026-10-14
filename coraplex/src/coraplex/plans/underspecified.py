from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field

from typing_extensions import (
    Optional,
    TYPE_CHECKING,
    Tuple,
    Type,
)

from coraplex.datastructures.enums import ActionTrialVisualization
from coraplex.exceptions import NotAStatementNode
from coraplex.plans.context_extensions import StatementGrounding
from coraplex.plans.designator import DesignatorParameters
from coraplex.visualization import RvizVisualization
from cramph.composites import (
    Attempt,
    ChildChooser,
    CompositeNodeChoosingItsChild,
    Sequence,
    StatementNode,
)
from cramph.context import StatechartContext
from cramph.exceptions import ExecutionFailure
from cramph.node import StatechartNode
from cramph.statechart import Statechart
from giskardpy.motion_statechart.monitors.progress_monitors import Stalled

if TYPE_CHECKING:
    from coraplex.plans.executors import PlanExecutor
    from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

# %% attempting a grounded action


@dataclass(eq=False, repr=False)
class AttemptRewritingItsTask(Attempt):
    """
    An attempt whose task is rewritten by the plan transformations of its statechart
    before its failure monitors join it, so that they watch the task as it is run.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Differs from :meth:`~cramph.composites.Attempt.expand` in rewriting the task
        once it is added, before the monitors are.
        """
        self._add_child_to_statechart(self.task)
        rewriting = context.get_extension(PlanRewriting)
        if rewriting is not None:
            rewriting.rewrite(self.task)
        self._add_children_to_statechart(self.failure_monitors)


# %% the node running an underspecified action


@dataclass(eq=False, repr=False)
class UnderspecifiedNode(CompositeNodeChoosingItsChild):
    """
    Runs an action described by an underspecified `a(...)` / `an(...)` statement.

    The statement is grounded only when this node starts, against the world the nodes
    before it left behind, and the grounded actions are tried until one succeeds. The
    node fails once the statement yields no further action. If you want to limit the
    number of attempts, add a limit clause to the statement.
    """

    statement: Match = field(
        kw_only=True, metadata=JSONMetadata(serialize=False).as_dict()
    )
    """
    The underspecified statement the actions are grounded from.

    Not serialized: a process ticking the statechart elsewhere receives the chosen
    actions rather than grounding them itself.
    """

    _proposals: Optional[Iterator[DesignatorParameters]] = field(
        default=None, init=False, repr=False
    )
    """
    The grounded actions of the statement, open from the first pull until they are
    exhausted or released by :meth:`stop_grounding`.
    """

    _candidates_pulled: int = field(default=0, init=False, repr=False)
    """
    How many actions the current run through the statement has grounded.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (StatementGrounding,)

    @property
    def grounding(self) -> StatementGrounding:
        """
        :return: How the statement is grounded, as the context of the statechart says.
        """
        return self.context.require_extension(StatementGrounding)

    @property
    def candidate_limit(self) -> int:
        """
        :return: How many actions are grounded: the statement's own limit, or the
            context's if it has none.
        """
        return self.statement._limit_ or self.grounding.candidates_to_try

    @property
    def reached_candidate_limit(self) -> bool:
        """
        :return: Whether the last run through the statement stopped because it grounded
            :attr:`candidate_limit` actions.
        """
        return self._candidates_pulled == self.candidate_limit

    def ground_next_child(self, trial: ActionTrial) -> Optional[StatechartNode]:
        """
        Grounds the statement into the next action that succeeds its trial, against the
        world as it is now.

        An action that fails its trial is discarded without ever touching the real
        world, so a bad parameterization cannot poison a later attempt. The statement is
        left suspended in between, so the next call resumes where this one stopped.

        :param trial: The trial every grounded action is tried in first.
        :return: The node running that action, given up on once it stops approaching its
            goal, or None once the statement ran out of actions that succeed their
            trial.
        """
        proposal = self._pull_next_proposal()
        while proposal is not None:
            if trial.succeeds(proposal):
                return self._attempt_of(proposal)
            proposal = self._pull_next_proposal()
        self.stop_grounding()
        return None

    def stop_grounding(self) -> None:
        """
        Releases the statement's grounded actions once no further child will be asked
        for.

        A suspended generator keeps every value its frame holds alive, so closing it
        frees whatever the statement only holds to ground actions with. The next
        :meth:`ground_next_child` grounds the statement anew.
        """
        if self._proposals is None:
            return
        self._proposals.close()
        self._proposals = None

    def cleanup(self, context: StatechartContext) -> None:
        self.stop_grounding()

    def _pull_next_proposal(self) -> Optional[DesignatorParameters]:
        """
        :return: The next grounded action, or None once the statement is exhausted or
            :attr:`candidate_limit` actions were grounded.
        """
        if self._proposals is None:
            self._candidates_pulled = 0
            self._proposals = self.grounding.query_backend.evaluate(self.statement)
        if self.reached_candidate_limit:
            self.stop_grounding()
            return None
        proposal = next(self._proposals, None)
        if proposal is None:
            self._proposals = None
            return None
        self._candidates_pulled += 1
        return proposal

    @staticmethod
    def _attempt_of(proposal: DesignatorParameters) -> StatechartNode:
        """
        :return: `proposal`, in a sequence of its own for the nodes a plan
            transformation puts beside it, given up on once it stops approaching its
            goal, so this node can try the next action instead.
        """
        steps = Sequence(name=f"{proposal.name}/steps", nodes=[proposal])
        return Attempt(
            name=f"{proposal.name}/attempt",
            task=steps,
            failure_monitors=[Stalled(monitored_node=steps)],
        )

    @property
    def chosen_actions(self) -> List[StatechartNode]:
        """
        :return: The grounded action every child chosen so far runs, in the order they
            were chosen, each found below whatever runs it.
        """
        return [
            next(
                node
                for node in [child, *child.descendants]
                if isinstance(node, self.statement._type_)
            )
            for child in self.children
        ]

    def adopt_chosen_child(self, child: StatechartNode) -> None:
        """
        Run `child` next, rewritten by the plan transformations of the statechart, if it
        carries any.
        """
        super().adopt_chosen_child(child)
        rewriting = self.statechart.context.get_extension(PlanRewriting)
        if rewriting is not None:
            rewriting.rewrite(child)

    def to_json(self, **kwargs) -> Dict[str, Any]:
        """
        :return: The JSON representation of the node choosing its child that this is, so
            a process ticking the statechart elsewhere needs nothing of coraplex.
        """
        return {
            **super().to_json(**kwargs),
            JSONField.TYPE: get_full_class_name(CompositeNodeChoosingItsChild),
        }

    def __repr__(self):
        return f"{self.statement._type_.__name__}"


# %% trying a grounded action out before it is executed for real


@dataclass
class ActionTrial:
    """
    Tries grounded actions against a copy of the world, to check that a candidate can
    succeed before it is attempted for real.

    One copy serves every candidate: after each attempt its model is rolled back and its
    state restored, and when the executor's world has changed since, the copy replays
    those model and state changes instead of being taken anew. Collision rules changed
    after the copy was taken are not carried over.

    Trials never publish to a synchronizer and always run simulated, in an executor of
    :attr:`trial_executor_type` over the copy, with the context extensions of
    :attr:`executor` rebound to the copy. While the executor is debugging, the copy is
    shown in RViz under its own frame prefix and marker topic.
    """

    executor: PlanExecutor
    """
    The executor the candidates are grounded for.

    Only ever read from: a trial never mutates its world, and the candidates themselves
    are left untouched too, so they can still run for real afterwards.
    """

    trial_executor_type: Type[PlanExecutor]
    """
    The executor that runs a candidate in the copy, which simulates the robot.
    """

    copy_marker_alpha: float = field(default=0.9, kw_only=True)
    """
    The opacity the copy is drawn with while debugging, so it can be told apart from the
    world it copies where the two overlap.
    """

    _copied_world: Optional[World] = field(default=None, init=False, repr=False)
    """
    The copy candidates are tried against.
    """

    _source_versions: Optional[Tuple[int, int]] = field(
        default=None, init=False, repr=False
    )
    """
    The model and state versions of the executor's world when the copy last matched it,
    used to notice that it has moved on and the copy has to be caught up.
    """

    _replayed_modification_blocks: int = field(default=0, init=False, repr=False)
    """
    How many of the modification blocks of the executor's world the copy already holds.
    """

    _visualization: Optional[RvizVisualization] = field(
        default=None, init=False, repr=False
    )
    """
    The RViz publishing of the current copy, while the executor is debugging.
    """

    @property
    def world(self) -> World:
        """
        :return: The world the candidates are grounded in.
        """
        return self.executor.world

    def succeeds(self, action: DesignatorParameters) -> bool:
        """
        Run `action` against the copy and restore the copy afterwards.

        The action is rebuilt from its own parameters, rebound onto the copy, because an
        action that modifies the model (attaching a grasped body, say) requires the
        entities it is given to belong to the world being modified, and because a
        statechart node belongs to one statechart only.

        The version to roll back to is read here rather than when the copy is taken, so
        each attempt undoes only its own modifications.

        :param action: The grounded action to try out.
        :return: True if `action` runs to completion without raising an
            :class:`~cramph.exceptions.ExecutionFailure`.
        """
        world = self._copy()
        candidate = self._on_the_copy(action, world)
        version = world.get_world_model_manager().version

        with world.reset_state_context():
            try:
                executor = self._trial_executor(world)
                statechart = Statechart(context=executor.context)
                # The candidate runs in a sequence of its own, the way it runs for real,
                # so the nodes a plan transformation puts beside it are tried with it.
                statechart.add_node(Sequence(nodes=[candidate]))
                executor.compile(statechart)
                executor.execute()
                return True
            except ExecutionFailure as failure:
                logger.info(f"{action} failed its trial: {failure}")
                return False
            finally:
                # Undo the model changes before leaving the reset context restores the
                # state, which needs the degrees of freedom it was snapshotted with.
                world.rollback_to_version(version)

    def _trial_executor(self, world: World) -> PlanExecutor:
        """
        :param world: The copy a candidate is tried in.
        :return: An executor running a candidate in `world`, configured like
            :attr:`executor`, the robot and everything else its context extensions refer
            to rebound to `world`.
        """
        return self.trial_executor_type(
            world,
            context_extensions=[
                world.rebind_world_entities(extension)
                for extension in self.executor.context_extensions
            ],
            collision_avoidance=self.executor.collision_avoidance,
        )

    @classmethod
    def _on_the_copy(
        cls, action: DesignatorParameters, world: World
    ) -> DesignatorParameters:
        """
        :param action: The grounded action to try out.
        :param world: The copy to try it against.
        :return: A new action with the parameters of `action`, referring to `world`.
            The actions among those parameters are built anew the same way, since each
            of them becomes a node of the statechart the trial runs.
        """
        return type(action)(
            **{
                name: (
                    cls._on_the_copy(value, world)
                    if isinstance(value, DesignatorParameters)
                    else world.rebind_world_entities(value)
                )
                for name, value in action.designator_parameter.items()
            }
        )

    def _copy(self) -> World:
        """
        :return: The copy to try candidates against, caught up with the executor's world
            if that has changed since the copy last matched it.
        """
        versions = (
            self.world.get_world_model_manager().version,
            self.world.state.version,
        )
        if self._copied_world is None:
            self._take_copy()
        elif self._source_versions != versions:
            self._catch_up()
        self._source_versions = versions
        return self._copied_world

    def _take_copy(self) -> None:
        """
        Copy the executor's world and, while the executor is debugging, start publishing
        the copy.
        """
        self._copied_world = deepcopy(self.world)
        self._replayed_modification_blocks = len(
            self.world.get_world_model_manager().model_modification_blocks
        )
        if self.executor.debug:
            self._visualization = RvizVisualization(
                self._copied_world,
                ros_node=self.executor.ros_node,
                collision_visualization=True,
                frame_prefix=ActionTrialVisualization.FRAME_PREFIX,
                marker_topic=ActionTrialVisualization.MARKER_TOPIC,
                marker_alpha=self.copy_marker_alpha,
            ).start()

    def _catch_up(self) -> None:
        """
        Bring the copy up to date with the executor's world: replay the modifications
        made to it since, the way copying it replays all of them, and take over its
        state.

        The copy's own modifications are all rolled back by then, so it still matches
        the world as it was when it last caught up.
        """
        modification_blocks = (
            self.world.get_world_model_manager().model_modification_blocks
        )
        with self._copied_world.modify_world():
            for block in modification_blocks[self._replayed_modification_blocks :]:
                block.update_references_for_world_and_apply(world=self._copied_world)
            self._copied_world.state.merge_state(self.world.state)
        self._replayed_modification_blocks = len(modification_blocks)

    def discard(self) -> None:
        """
        Release the copy, so the next trial takes a fresh one.
        """
        self._stop_visualization()
        self._copied_world = None
        self._source_versions = None

    def _stop_visualization(self) -> None:
        """
        Stop publishing the current copy, if it is being published.
        """
        if self._visualization is None:
            return
        self._visualization.stop()
        self._visualization = None


# %% grounding underspecified actions while the statechart runs


@dataclass
class UnderspecifiedChildChooser(ChildChooser):
    """
    Grounds the statement of every :class:`~cramph.composites.StatementNode` of a
    statechart into the action it runs next.

    A grounded action is tried out first, so one that fails its trial is discarded
    without ever touching the real world, and a bad parameterization cannot poison a
    later attempt.
    """

    executor: PlanExecutor
    """
    The executor whose statechart holds the nodes, which also tries their candidates.
    """

    trial_executor_type: Type[PlanExecutor]
    """
    The executor the candidates are tried in, see :class:`ActionTrial`.
    """

    trial: ActionTrial = field(init=False)
    """
    The trial every node tries its candidates against, so they all try them in one copy
    of the world.
    """

    def __post_init__(self):
        self.trial = ActionTrial(
            executor=self.executor, trial_executor_type=self.trial_executor_type
        )

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context: StatechartContext
    ) -> Optional[StatechartNode]:
        """
        :return: The node running the next grounded action that succeeds its trial,
            given up on once it stops approaching its goal, or None once the statement
            ran out of actions that succeed their trial.
        :raises NotAStatementNode: If `node` carries no statement to ground.
        """
        if not isinstance(node, StatementNode):
            raise NotAStatementNode(node=node)
        grounding = context.require_extension(StatementGrounding)
        proposal = node.next_candidate(
            grounding.query_backend, grounding.candidates_to_try
        )
        while proposal is not None:
            if self.trial.succeeds(proposal):
                return self._attempt_of(proposal)
            proposal = node.next_candidate(
                grounding.query_backend, grounding.candidates_to_try
            )
        node.stop_grounding()
        return None

    @staticmethod
    def _attempt_of(proposal: DesignatorParameters) -> StatechartNode:
        """
        :return: `proposal`, in a sequence of its own for the nodes a plan
            transformation puts beside it, given up on once it stops approaching its
            goal, so its node can try the next action instead.
        """
        steps = Sequence(name=f"{proposal.name}/steps", nodes=[proposal])
        return Attempt(
            name=f"{proposal.name}/attempt",
            task=steps,
            failure_monitors=[Stalled(monitored_node=steps)],
        )

    def cleanup(self) -> None:
        """
        Release the trial's world copy.
        """
        self.trial.discard()
