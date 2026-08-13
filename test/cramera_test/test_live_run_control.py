"""
Tests for driving a running demo from the viewer through the live bridge.

The bridge only relays commands: what pausing or restarting *means* belongs to the demo
that registered itself, so these use a stand-in that records what it was asked to do.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest
from typing_extensions import List

from cramera.live.bridge import Bridge
from cramera.live.run_control import (
    LiveRunControl,
    NoRunControlRegistered,
    RunActivity,
    RunCommand,
    RunControlState,
    UnknownRunCommand,
)


@dataclass
class RecordingRunControl(LiveRunControl):
    """
    A stand-in demo that applies commands to its own flags and remembers the order.
    """

    applied: List[RunCommand] = field(default_factory=list)
    """
    Every command this control was given, in the order it was given them.
    """

    paused: bool = False
    """
    Whether this stand-in considers itself paused.
    """

    looping: bool = False
    """
    Whether this stand-in would start another run once the current one ends.
    """

    restart_pending: bool = False
    """
    Whether a restart has been asked for and not yet acted on.
    """

    def title(self) -> str:
        """
        What the viewer names this run.
        """
        return "record demo"

    def state(self) -> RunControlState:
        """
        This stand-in's current state.
        """
        return RunControlState(
            paused=self.paused,
            looping=self.looping,
            restart_pending=self.restart_pending,
            activity=RunActivity.SORTING,
            iteration=1,
        )

    def apply(self, command: RunCommand) -> None:
        """
        Record and act on one command.

        :param command: What the viewer asked for.
        """
        self.applied.append(command)
        if command is RunCommand.PAUSE:
            self.paused = True
        elif command is RunCommand.RESUME:
            self.paused = False
        elif command is RunCommand.RESTART:
            self.restart_pending = True
        elif command is RunCommand.ENABLE_LOOP:
            self.looping = True
        elif command is RunCommand.DISABLE_LOOP:
            self.looping = False


@pytest.fixture()
def control() -> RecordingRunControl:
    return RecordingRunControl()


@pytest.fixture()
def bridge(control) -> Bridge:
    bridge = Bridge()
    bridge.register_run_control(control)
    return bridge


# %% a bridge with nothing driving it
class TestWithoutARegisteredControl:
    def test_asking_for_the_state_says_so(self):
        with pytest.raises(NoRunControlRegistered):
            Bridge().run_control_state()

    def test_commanding_it_says_so(self):
        with pytest.raises(NoRunControlRegistered):
            Bridge().apply_run_command(RunCommand.PAUSE)

    def test_the_status_reports_no_control(self):
        assert Bridge().status()["control"] is None


# %% relaying commands to the demo
class TestRelayingCommands:
    def test_a_command_reaches_the_demo(self, bridge, control):
        bridge.apply_run_command(RunCommand.PAUSE)

        assert control.applied == [RunCommand.PAUSE]

    def test_the_answer_is_the_state_the_command_produced(self, bridge):
        """
        In the same shape a polling viewer reads, so one that clicked and one that
        polled never disagree about where the run stands.
        """
        assert bridge.apply_run_command(RunCommand.PAUSE) == {
            **bridge.run_control_payload(),
            "paused": True,
        }

    def test_resuming_undoes_pausing(self, bridge):
        bridge.apply_run_command(RunCommand.PAUSE)

        assert bridge.apply_run_command(RunCommand.RESUME)["paused"] is False

    def test_looping_is_a_mode_rather_than_an_action(self, bridge):
        assert bridge.apply_run_command(RunCommand.ENABLE_LOOP)["looping"] is True
        assert bridge.apply_run_command(RunCommand.DISABLE_LOOP)["looping"] is False

    def test_restarting_is_pending_until_the_demo_acts_on_it(self, bridge):
        assert bridge.apply_run_command(RunCommand.RESTART)["restart_pending"] is True


# %% what the viewer polls
class TestTheStatusCarriesTheState:
    def test_the_status_carries_the_current_state(self, bridge):
        bridge.apply_run_command(RunCommand.ENABLE_LOOP)

        assert bridge.status()["control"]["looping"] is True

    def test_the_state_names_what_the_run_is_doing(self, bridge):
        assert bridge.status()["control"]["activity"] == RunActivity.SORTING.value

    def test_the_state_is_json_ready(self, bridge):
        assert bridge.run_control_state().to_payload() == {
            "paused": False,
            "looping": False,
            "restart_pending": False,
            "activity": RunActivity.SORTING.value,
            "iteration": 1,
        }

    def test_the_published_state_names_the_demo_it_belongs_to(self, bridge, control):
        """
        Which demo is being driven belongs to the control, not to the state it reports
        over and over, so the bridge is what puts the two together.
        """
        assert bridge.run_control_payload()["title"] == control.title()


# %% reading a command off the wire
class TestReadingACommand:
    def test_a_known_name_becomes_its_command(self):
        assert RunCommand.of_name("pause") is RunCommand.PAUSE

    def test_an_unknown_name_is_refused(self):
        with pytest.raises(UnknownRunCommand):
            RunCommand.of_name("self_destruct")

    def test_the_refusal_names_what_is_accepted(self):
        with pytest.raises(UnknownRunCommand) as refusal:
            RunCommand.of_name("")

        assert "pause" in str(refusal.value)


# %% several viewers at once
class TestConcurrentCommands:
    def test_commands_from_several_viewers_all_arrive(self, bridge, control):
        """
        The bridge answers each viewer on its own thread, so two clicking at once must
        not lose one of the commands.
        """
        senders = [
            threading.Thread(target=lambda: bridge.apply_run_command(RunCommand.PAUSE))
            for _ in range(20)
        ]
        for sender in senders:
            sender.start()
        for sender in senders:
            sender.join(timeout=30)

        assert len(control.applied) == 20
