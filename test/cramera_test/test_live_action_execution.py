"""
Tests for having a running demo perform an action from the viewer, through the live
bridge.

The bridge only relays the request: what an action *is* and when it is safe to run
belongs to the demo that registered itself, so these use a stand-in that records what it
was asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing_extensions import List, Optional

from cramera.live.action_execution import (
    ActionExecutionState,
    LiveActionExecution,
    NoActionExecutionRegistered,
    UnknownPerformableAction,
)
from cramera.live.bridge import Bridge

OFFERED_ACTION = "insert_cube"
"""
The one action the stand-in demo of these tests performs.
"""


@dataclass
class RecordingActionExecution(LiveActionExecution):
    """
    A stand-in demo that queues what it was asked to perform and remembers the order.
    """

    asked: List[str] = field(default_factory=list)
    """
    Every action name this execution was given, in the order it was given them.
    """

    performing: Optional[str] = None
    """
    What this stand-in considers itself to be carrying out.
    """

    def title(self) -> str:
        """
        What the viewer names this demo.
        """
        return "record demo"

    def state(self) -> ActionExecutionState:
        """
        This stand-in's current state.
        """
        return ActionExecutionState(performing=self.performing, requested=self.asked)

    def perform(self, name: str) -> None:
        """
        Record one requested action, refusing a name this stand-in does not perform.

        :param name: Name of the action the viewer asked for.
        """
        if name != OFFERED_ACTION:
            raise UnknownPerformableAction(name=name, offered=[OFFERED_ACTION])
        self.asked.append(name)


@pytest.fixture()
def bridge() -> Bridge:
    """
    A bare bridge, with no demo registered on it.
    """
    return Bridge()


@pytest.fixture()
def acting_bridge(bridge) -> tuple:
    """
    A bridge with the stand-in demo registered on it.
    """
    execution = RecordingActionExecution()
    bridge.register_action_execution(execution)
    return bridge, execution


class TestRelayingAPerformRequest:
    def test_a_request_reaches_the_demo(self, acting_bridge):
        bridge, execution = acting_bridge

        bridge.perform_action(OFFERED_ACTION)

        assert execution.asked == [OFFERED_ACTION]

    def test_the_request_answers_with_the_state_it_produced(self, acting_bridge):
        bridge, _ = acting_bridge

        payload = bridge.perform_action(OFFERED_ACTION)

        assert payload == {
            "performing": None,
            "requested": [OFFERED_ACTION],
            "title": "record demo",
        }

    def test_an_action_the_demo_does_not_perform_is_refused(self, acting_bridge):
        bridge, execution = acting_bridge

        with pytest.raises(UnknownPerformableAction):
            bridge.perform_action("fly_away")

        assert execution.asked == []

    def test_a_refusal_names_what_can_be_performed_instead(self, acting_bridge):
        bridge, _ = acting_bridge

        with pytest.raises(UnknownPerformableAction) as error:
            bridge.perform_action("fly_away")

        assert OFFERED_ACTION in error.value.suggest_correction()

    def test_asking_a_bridge_no_demo_registered_on_reports_why(self, bridge):
        with pytest.raises(NoActionExecutionRegistered):
            bridge.perform_action(OFFERED_ACTION)

    def test_the_state_of_a_bridge_no_demo_registered_on_reports_why(self, bridge):
        with pytest.raises(NoActionExecutionRegistered):
            bridge.action_execution_payload()


class TestWhatTheViewerReads:
    def test_the_state_names_the_demo_that_performs(self, acting_bridge):
        bridge, _ = acting_bridge

        assert bridge.action_execution_payload()["title"] == "record demo"

    def test_the_state_names_what_is_being_carried_out(self, acting_bridge):
        bridge, execution = acting_bridge
        execution.performing = OFFERED_ACTION

        assert bridge.action_execution_payload()["performing"] == OFFERED_ACTION

    def test_a_bridge_without_a_demo_announces_that_nothing_can_be_performed(
        self, bridge
    ):
        assert bridge.status()["perform"] is None

    def test_a_bridge_with_a_demo_announces_what_it_is_doing(self, acting_bridge):
        bridge, _ = acting_bridge

        assert bridge.status()["perform"] == {
            "performing": None,
            "requested": [],
            "title": "record demo",
        }
