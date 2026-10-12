"""
Choosing the child of a node of a running goal on the client.

A node of a goal may choose its child only once it runs, see
:class:`~cramph.composites.CompositeNodeChoosingItsChild`. What it runs is decided by
the client, which holds what the choice is made from, so Giskard publishes the nodes
waiting for a child in its feedback, the client chooses on its copy of the statechart
and sends the nodes the choice added, and Giskard adds them to the running statechart.

.. note:: This is an interim way of getting a client's choices into a running goal,
    meant to be replaced by a proper interface between client and Giskard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock

from typing_extensions import Any, Dict, List, Optional, Self, Set, Tuple

from cramph.composites import ChildChooser, CompositeNodeChoosingItsChild
from cramph.context import StatechartContext
from cramph.data_types import LifeCycleValues
from cramph.node import StatechartNode
from cramph.statechart import Statechart
from giskardpy.middleware.ros2.action_server import ActionServerHandler
from giskardpy.middleware.ros2.exceptions import StatechartOutOfStepError
from giskardpy.middleware.ros2.feedback_publisher import MotionStatechartPayloadKey
from giskardpy.middleware.ros2.world_updates import IncomingWorldUpdates
from krrood.adapters.json_serializer import SubclassJSONSerializer, from_json, to_json
from semantic_digital_twin.adapters.ros.messages import StreamPosition
from semantic_digital_twin.adapters.world_entity_kwargs_tracker import (
    WorldEntityWithIDKwargsTracker,
)

# %% where the client sends it


class GiskardTopicSuffix(StrEnum):
    """
    The names of the topics below Giskard's node name.
    """

    CHILD_CHOICES = "child_choices"
    """
    The topic a client sends its child choices to.
    """


def child_choices_topic(giskard_node_name: str) -> str:
    """
    :param giskard_node_name: The name of Giskard's node.
    :return: The topic a client sends its child choices to.
    """
    return f"{giskard_node_name}/{GiskardTopicSuffix.CHILD_CHOICES}"


# %% what the client sends


class ChildChoicePayloadKey(StrEnum):
    """
    The keys of a child choice sent to Giskard.
    """

    GOAL_ID = "goal_id"
    """
    The goal the choice belongs to.
    """

    NODE_INDEX = "node_index"
    """
    The node the child was chosen for.
    """

    FIRST_NODE_INDEX = "first_node_index"
    """
    The index the first sent node has in the statechart.
    """

    NODES = "nodes"
    """
    The nodes the choice added, or nothing if no child is left.
    """

    REQUIRED_POSITION = "required_position"
    """
    The change of the client's world the choice was made on.
    """


@dataclass
class ChildChoiceMessage(SubclassJSONSerializer):
    """
    The child a client chose for a node of a running goal.
    """

    goal_id: int
    """
    The goal the choice belongs to.
    """

    node_index: int
    """
    The index of the node the child was chosen for.
    """

    first_node_index: int
    """
    The index the first sent node has in the statechart.
    """

    nodes: Optional[Dict[str, Any]]
    """
    The nodes the choice added, as written by
    :meth:`~cramph.statechart.Statechart.nodes_from_to_json`, the first of them the
    child, or ``None`` if no child is left.
    """

    required_position: Optional[StreamPosition] = field(default=None, kw_only=True)
    """
    The position in the client's stream the world has to contain before the nodes are
    added, ``None`` if there is nothing to wait for.
    """

    def to_json(self, **kwargs) -> Dict[str, Any]:
        return {
            **super().to_json(**kwargs),
            ChildChoicePayloadKey.GOAL_ID: self.goal_id,
            ChildChoicePayloadKey.NODE_INDEX: self.node_index,
            ChildChoicePayloadKey.FIRST_NODE_INDEX: self.first_node_index,
            ChildChoicePayloadKey.NODES: self.nodes,
            ChildChoicePayloadKey.REQUIRED_POSITION: (
                None
                if self.required_position is None
                else to_json(self.required_position, **kwargs)
            ),
        }

    @classmethod
    def _from_json(cls, data: Dict[str, Any], **kwargs) -> Self:
        required_position = data[ChildChoicePayloadKey.REQUIRED_POSITION]
        return cls(
            goal_id=data[ChildChoicePayloadKey.GOAL_ID],
            node_index=data[ChildChoicePayloadKey.NODE_INDEX],
            first_node_index=data[ChildChoicePayloadKey.FIRST_NODE_INDEX],
            nodes=data[ChildChoicePayloadKey.NODES],
            required_position=(
                None if required_position is None else from_json(required_position)
            ),
        )

    def apply_to(self, statechart: Statechart) -> Optional[StatechartNode]:
        """
        Add the sent nodes to `statechart`.

        :return: The chosen child, or ``None`` if no child is left.
        :raises StatechartOutOfStepError: If `statechart` does not hold the nodes the
            client's copy held before the choice.
        """
        if self.nodes is None:
            return None
        if self.first_node_index != len(statechart.nodes):
            raise StatechartOutOfStepError(
                node_count=len(statechart.nodes),
                first_sent_node_index=self.first_node_index,
            )
        world = statechart.context.world
        kwargs = WorldEntityWithIDKwargsTracker.from_world(world).create_kwargs()
        statechart.add_nodes_from_json(self.nodes, world=world, **kwargs)
        return statechart.get_node_by_index(self.first_node_index)


# %% Giskard's side


@dataclass
class ChildSentByClient(ChildChooser):
    """
    Lets every node of a running goal run the child the client sent for it, and wait
    until one arrived.

    The choices are taken in the order the client made them, whatever order the nodes
    ask in, so the running statechart gains its nodes in the order the client's copy
    did.
    """

    world_updates: IncomingWorldUpdates
    """
    Tells whether the world contains the change a choice was made on.
    """

    action_server: ActionServerHandler
    """
    Tells which goal is running.
    """

    _received: Dict[int, ChildChoiceMessage] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    The choices received and not yet taken, by the index of their node.
    """

    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    """
    Guards :attr:`_received`, which the thread receiving messages writes.
    """

    def receive(self, message: ChildChoiceMessage) -> None:
        """
        :param message: A choice the client sent.
        """
        with self._lock:
            self._received[message.node_index] = message

    def has_choice_for(self, node: CompositeNodeChoosingItsChild) -> bool:
        """
        A choice for another goal is dropped.

        :return: Whether a choice for `node` in the running goal was received, every
            choice made before it was taken, and the world contains what it was made
            on.
        """
        with self._lock:
            message = self._received.get(node.index)
            if message is None:
                return False
            if message.goal_id != self.action_server.goal_id:
                del self._received[node.index]
                return False
            if self._is_made_after_a_choice_still_to_take(message, node.statechart):
                return False
            return message.required_position is None or (
                self.world_updates.has_applied(message.required_position)
            )

    def _is_made_after_a_choice_still_to_take(
        self, message: ChildChoiceMessage, statechart: Statechart
    ) -> bool:
        """
        A choice whose node ended can no longer be taken, so nothing waits for it.

        :param message: A received choice.
        :param statechart: The running statechart.
        :return: Whether the client made another received choice of the same goal
            before `message`, and the node of that choice can still take it.
        """
        return any(
            earlier.goal_id == message.goal_id
            and earlier.first_node_index < message.first_node_index
            and statechart.get_node_by_index(earlier.node_index).life_cycle_state
            in (LifeCycleValues.RUNNING, LifeCycleValues.PAUSED)
            for earlier in self._received.values()
        )

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context: StatechartContext
    ) -> Optional[StatechartNode]:
        """
        Add the nodes the client sent for `node`.
        """
        with self._lock:
            message = self._received.pop(node.index)
        return message.apply_to(node.statechart)

    def cleanup(self) -> None:
        with self._lock:
            self._received.clear()


# %% the client's side


@dataclass
class ChildChoiceClient:
    """
    Answers the nodes a running goal reports as waiting for a child, by choosing on the
    client's copy of the statechart.
    """

    statechart: Statechart
    """
    The client's copy of the statechart that was sent as the goal.
    """

    chooser: ChildChooser
    """
    Chooses the children.
    """

    required_position: Optional[StreamPosition] = None
    """
    The change of the client's world every choice is made on.
    """

    _answered: Set[Tuple[int, int, int]] = field(
        default_factory=set, init=False, repr=False
    )
    """
    Every request answered, as goal, node index and the number of children the node held.
    """

    def answer(self, feedback: Dict[str, Any]) -> List[ChildChoiceMessage]:
        """
        :param feedback: The feedback of the running goal.
        :return: A choice for every node waiting for a child that was not answered
            before. A choice that is still pending is asked for again next time.
        """
        goal_id = feedback[MotionStatechartPayloadKey.GOAL_ID]
        messages = []
        for index, child_count in feedback[
            MotionStatechartPayloadKey.WAITING_FOR_CHILD
        ].items():
            request = (goal_id, int(index), child_count)
            if request in self._answered:
                continue
            message = self._choose(
                goal_id, self.statechart.get_node_by_index(int(index))
            )
            if message is None:
                continue
            self._answered.add(request)
            messages.append(message)
        return messages

    def _choose(
        self, goal_id: int, node: CompositeNodeChoosingItsChild
    ) -> Optional[ChildChoiceMessage]:
        """
        Choose the next child of `node` on the client's copy.

        :return: The message telling Giskard about the choice, or ``None`` if it is
            pending.
        """
        first_node_index = len(self.statechart.nodes)
        if not node.choose_child_with(self.chooser, self.statechart.context):
            return None
        nodes = (
            None
            if node.ran_out_of_children
            else self.statechart.nodes_from_to_json(first_node_index)
        )
        return ChildChoiceMessage(
            goal_id=goal_id,
            node_index=node.index,
            first_node_index=first_node_index,
            nodes=nodes,
            required_position=self.required_position,
        )
