"""
Tests for the exchange of child choices between a running statechart and the client's
copy of it, see :mod:`giskardpy.middleware.ros2.child_choices`, without a ROS graph.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from cramph.composites import (
    ChildChooser,
    ChildChooserAccess,
    CompositeNodeChoosingItsChild,
)
from cramph.context import StatechartContext
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.executor import StatechartExecutor
from cramph.node import StatechartNode
from cramph.nodes_for_testing import NodeSucceedingOnObservingTrue
from cramph.statechart import Statechart
from giskardpy.middleware.ros2.child_choices import (
    ChildChoiceClient,
    ChildChoiceMessage,
    ChildSentByClient,
)
from giskardpy.middleware.ros2.exceptions import StatechartOutOfStepError
from giskardpy.middleware.ros2.feedback_publisher import (
    ActionFeedbackPublisher,
    MotionStatechartPayloadKey,
)
from semantic_digital_twin.adapters.ros.messages import MetaData, StreamPosition
from semantic_digital_twin.world import World

# %% mimics


@dataclass
class ActionServerRunningOneGoal:
    """
    Stands in for the action server while one goal runs.
    """

    goal_id: int = 0
    """
    The goal that is running.
    """


@dataclass
class WorldUpdatesCaughtUpOnDemand:
    """
    Stands in for the incoming world updates, catching up with a client when told to.
    """

    caught_up: bool = True
    """
    Whether every position asked about counts as applied.
    """

    def has_applied(self, position: StreamPosition) -> bool:
        return self.caught_up


@dataclass
class ChooserGivingAFreshChild(ChildChooser):
    """
    Gives every node that asks a new child that succeeds on the tick after it starts.
    """

    given_children: int = 0
    """
    How many children were given so far.
    """

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context: StatechartContext
    ) -> StatechartNode | None:
        self.given_children += 1
        return _node_succeeding_at_once(f"child {self.given_children}")


# %% helpers


def _node_succeeding_at_once(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that succeeds on the tick after it starts.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.TRUE
    )


@dataclass
class TwoChoosingNodes:
    """
    A statechart in which the choosing node with the higher index starts first.
    """

    statechart: Statechart
    """
    The statechart holding the nodes.
    """

    starting_late: CompositeNodeChoosingItsChild
    """
    The choosing node with the lower index, starting once :attr:`delay` succeeded.
    """

    starting_first: CompositeNodeChoosingItsChild
    """
    The choosing node with the higher index, starting with the statechart.
    """

    delay: NodeSucceedingOnObservingTrue
    """
    Succeeds on the tick after the statechart started.
    """

    @classmethod
    def in_context(cls, context: StatechartContext) -> TwoChoosingNodes:
        """
        :param context: The context the statechart is built in.
        """
        statechart = Statechart(context=context)
        starting_late = CompositeNodeChoosingItsChild(name="starting late")
        starting_first = CompositeNodeChoosingItsChild(name="starting first")
        delay = _node_succeeding_at_once("delay")
        statechart.add_nodes([starting_late, starting_first, delay])
        starting_late.start_condition = delay.is_succeeded
        return cls(
            statechart=statechart,
            starting_late=starting_late,
            starting_first=starting_first,
            delay=delay,
        )


@dataclass
class ClientAndRunningStatechart:
    """
    A client holding a copy of a statechart that runs elsewhere, and the two ends of the
    exchange of child choices between them.
    """

    world_updates: WorldUpdatesCaughtUpOnDemand = field(
        default_factory=WorldUpdatesCaughtUpOnDemand
    )
    """
    Tells the running side whether its world contains what the client chose on.
    """

    action_server: ActionServerRunningOneGoal = field(
        default_factory=ActionServerRunningOneGoal
    )
    """
    Tells both ends which goal is running.
    """

    executor: StatechartExecutor = field(init=False)
    """
    Ticks the running statechart.
    """

    running: TwoChoosingNodes = field(init=False)
    """
    The statechart that runs.
    """

    copy: TwoChoosingNodes = field(init=False)
    """
    The client's copy of the running statechart.
    """

    receiving_chooser: ChildSentByClient = field(init=False)
    """
    Takes the client's choices on the running side.
    """

    client: ChildChoiceClient = field(init=False)
    """
    Chooses on the client's copy.
    """

    def __post_init__(self) -> None:
        self.receiving_chooser = ChildSentByClient(
            world_updates=self.world_updates, action_server=self.action_server
        )
        self.executor = StatechartExecutor(context=StatechartContext(world=World()))
        self.executor.context.add_extension(
            ChildChooserAccess(chooser=self.receiving_chooser)
        )
        self.running = TwoChoosingNodes.in_context(self.executor.context)

        client_chooser = ChooserGivingAFreshChild()
        client_context = StatechartContext(world=World())
        client_context.add_extension(ChildChooserAccess(chooser=client_chooser))
        self.copy = TwoChoosingNodes.in_context(client_context)
        self.client = ChildChoiceClient(
            statechart=self.copy.statechart,
            chooser=client_chooser,
            required_position=StreamPosition(
                origin=MetaData(node_name="client", process_id=0), sequence_number=1
            ),
        )

    def start(self) -> None:
        """
        Compile the running statechart, which starts it.
        """
        self.executor.compile(self.running.statechart)

    def let_the_client_answer(self) -> list[ChildChoiceMessage]:
        """
        Hand the feedback of the running statechart to the client and the client's
        choices back, each as the JSON that travels between them.

        :return: The choices the client sent.
        """
        feedback = ActionFeedbackPublisher(
            executor=self.executor, action_server=self.action_server
        ).create_states()
        feedback[MotionStatechartPayloadKey.GOAL_ID] = self.action_server.goal_id
        sent_choices = [
            ChildChoiceMessage.from_json(json.loads(json.dumps(choice.to_json())))
            for choice in self.client.answer(json.loads(json.dumps(feedback)))
        ]
        for choice in sent_choices:
            self.receiving_chooser.receive(choice)
        return sent_choices

    def let_both_nodes_be_answered_before_any_choice_is_taken(self) -> None:
        """
        Let the client answer both choosing nodes, the one starting first before the
        other, while the running side cannot take a choice yet.
        """
        self.world_updates.caught_up = False
        choices = self.let_the_client_answer()
        self.executor.tick()
        choices += self.let_the_client_answer()
        answered_nodes = [choice.node_index for choice in choices]
        assert answered_nodes == [
            self.copy.starting_first.index,
            self.copy.starting_late.index,
        ]
        self.world_updates.caught_up = True


@pytest.fixture()
def exchange_before_start() -> ClientAndRunningStatechart:
    """
    :return: A statechart that is about to run and a client answering its nodes waiting
        for a child.
    """
    return ClientAndRunningStatechart()


@pytest.fixture()
def exchange(
    exchange_before_start: ClientAndRunningStatechart,
) -> ClientAndRunningStatechart:
    """
    :return: A running statechart and a client answering its nodes waiting for a child.
    """
    exchange_before_start.start()
    return exchange_before_start


# %% choices are taken in the order the client made them


def test_choices_are_taken_in_the_order_the_client_made_them(
    exchange: ClientAndRunningStatechart,
):
    exchange.let_both_nodes_be_answered_before_any_choice_is_taken()

    exchange.executor.tick()
    exchange.executor.tick()

    assert [node.name for node in exchange.running.statechart.nodes] == [
        node.name for node in exchange.copy.statechart.nodes
    ]
    assert [child.name for child in exchange.running.starting_first.children] == [
        child.name for child in exchange.copy.starting_first.children
    ]
    assert [child.name for child in exchange.running.starting_late.children] == [
        child.name for child in exchange.copy.starting_late.children
    ]


def test_a_choice_made_later_waits_for_the_one_made_before_it(
    exchange: ClientAndRunningStatechart,
):
    exchange.let_both_nodes_be_answered_before_any_choice_is_taken()

    assert not exchange.receiving_chooser.has_choice_for(exchange.running.starting_late)


# %% a choice out of step is still rejected


def test_a_choice_skipping_nodes_the_statechart_never_got_is_rejected(
    exchange: ClientAndRunningStatechart,
):
    waiting_node = exchange.running.starting_first
    exchange.receiving_chooser.receive(
        ChildChoiceMessage(
            goal_id=exchange.action_server.goal_id,
            node_index=waiting_node.index,
            first_node_index=len(exchange.running.statechart.nodes) + 1,
            nodes={},
        )
    )

    with pytest.raises(StatechartOutOfStepError):
        exchange.executor.tick()


def test_a_choice_made_after_one_whose_node_ended_untaken_is_rejected(
    exchange_before_start: ClientAndRunningStatechart,
):
    exchange = exchange_before_start
    ended_node = exchange.running.starting_first
    ended_node.interrupt_condition = exchange.running.delay.is_succeeded
    exchange.start()
    exchange.let_both_nodes_be_answered_before_any_choice_is_taken()
    assert ended_node.life_cycle_state == LifeCycleValues.INTERRUPTED

    with pytest.raises(StatechartOutOfStepError):
        exchange.executor.tick()
