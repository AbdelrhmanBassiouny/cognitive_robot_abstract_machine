"""
Tests for driving a Montessori sort from the viewer.

No simulation and no world: what is under test is when the sorting thread is let through
and what the physics simulation is asked to do, both of which are decided before any of
that exists.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest
from typing_extensions import List

from cramera.live.run_control import RunActivity, RunCommand

from experiments.montessori.run_control import SortingRunControl

WAIT_TIMEOUT_SECONDS = 10.0
"""
How long a test waits for the sorting thread to get through a checkpoint before calling
it stuck.
"""


@dataclass
class RecordingSimulation:
    """
    A stand-in physics simulation that records being paused and unpaused.
    """

    calls: List[str] = field(default_factory=list)
    """
    Every pause/unpause call made on it, in order.
    """

    def pause_simulation(self) -> None:
        """
        Record a pause.
        """
        self.calls.append("pause")

    def unpause_simulation(self) -> None:
        """
        Record an unpause.
        """
        self.calls.append("unpause")


@pytest.fixture()
def simulation() -> RecordingSimulation:
    return RecordingSimulation()


@pytest.fixture()
def control(simulation) -> SortingRunControl:
    control = SortingRunControl()
    control.begin_iteration(iteration=1, simulation=simulation)
    return control


def run_in_background(target) -> threading.Thread:
    """
    Start ``target`` on its own thread, standing in for the thread running the sort.

    :param target: What to run.
    """
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


# %% what the viewer sees
class TestReportingWhereTheRunStands:
    def test_a_fresh_run_has_not_started_yet(self):
        state = SortingRunControl().state()

        assert state.activity is RunActivity.STARTING
        assert state.iteration == 0
        assert state.paused is False

    def test_beginning_an_iteration_reports_it_as_sorting(self, control):
        state = control.state()

        assert state.activity is RunActivity.SORTING
        assert state.iteration == 1

    def test_finishing_an_iteration_reports_it_as_finished(self, control):
        control.finish_iteration()

        assert control.state().activity is RunActivity.FINISHED

    def test_it_names_the_demo_it_drives(self):
        assert SortingRunControl().title() == "Montessori sorting"


# %% pausing
class TestPausing:
    def test_pausing_freezes_the_physics(self, control, simulation):
        control.apply(RunCommand.PAUSE)

        assert simulation.calls == ["pause"]
        assert control.state().paused is True

    def test_resuming_starts_the_physics_again(self, control, simulation):
        control.apply(RunCommand.PAUSE)
        control.apply(RunCommand.RESUME)

        assert simulation.calls == ["pause", "unpause"]
        assert control.state().paused is False

    def test_a_checkpoint_lets_an_unpaused_run_straight_through(self, control):
        passed = threading.Event()

        run_in_background(lambda: (control.wait_while_paused(), passed.set()))

        assert passed.wait(WAIT_TIMEOUT_SECONDS)

    def test_a_checkpoint_holds_a_paused_run(self, control):
        control.apply(RunCommand.PAUSE)
        passed = threading.Event()

        run_in_background(lambda: (control.wait_while_paused(), passed.set()))

        assert not passed.wait(0.3)

    def test_resuming_releases_a_held_run(self, control):
        control.apply(RunCommand.PAUSE)
        passed = threading.Event()
        run_in_background(lambda: (control.wait_while_paused(), passed.set()))

        control.apply(RunCommand.RESUME)

        assert passed.wait(WAIT_TIMEOUT_SECONDS)

    def test_a_new_iteration_pauses_its_own_simulation(self, control):
        """
        Each iteration builds a new simulation, so a run paused across a rebuild must
        freeze the one that now exists rather than the one that is gone.
        """
        control.apply(RunCommand.PAUSE)
        rebuilt = RecordingSimulation()

        control.begin_iteration(iteration=2, simulation=rebuilt)

        assert rebuilt.calls == ["pause"]


# %% restarting
class TestRestarting:
    def test_a_restart_is_pending_until_it_is_acted_on(self, control):
        control.apply(RunCommand.RESTART)

        assert control.restart_is_pending() is True
        assert control.state().restart_pending is True

    def test_acting_on_a_restart_clears_it(self, control):
        control.apply(RunCommand.RESTART)

        control.consume_restart()

        assert control.restart_is_pending() is False

    def test_restarting_releases_a_paused_run_so_it_can_unwind(self, control):
        """
        A restart is honoured at the next checkpoint, which a paused run never reaches,
        so asking for one has to let the run go.
        """
        control.apply(RunCommand.PAUSE)
        passed = threading.Event()
        run_in_background(lambda: (control.wait_while_paused(), passed.set()))

        control.apply(RunCommand.RESTART)

        assert passed.wait(WAIT_TIMEOUT_SECONDS)
        assert control.state().paused is False


# %% looping
class TestLooping:
    def test_a_run_that_is_not_looping_wants_no_further_iteration(self, control):
        control.finish_iteration()

        assert control.wants_another_iteration() is False

    def test_looping_wants_another_iteration(self, control):
        control.apply(RunCommand.ENABLE_LOOP)

        assert control.wants_another_iteration() is True

    def test_turning_looping_off_stops_after_the_one_in_progress(self, control):
        control.apply(RunCommand.ENABLE_LOOP)
        control.apply(RunCommand.DISABLE_LOOP)

        assert control.wants_another_iteration() is False

    def test_a_pending_restart_wants_another_iteration_even_without_looping(
        self, control
    ):
        control.apply(RunCommand.RESTART)

        assert control.wants_another_iteration() is True


# %% waiting between runs
class TestIdlingBetweenRuns:
    def test_an_idle_run_waits_until_something_is_asked_of_it(self, control):
        control.finish_iteration()
        released = threading.Event()
        run_in_background(
            lambda: (control.wait_for_another_iteration(), released.set())
        )

        assert not released.wait(0.3)

        control.apply(RunCommand.RESTART)

        assert released.wait(WAIT_TIMEOUT_SECONDS)

    def test_enabling_looping_while_idle_starts_the_next_run(self, control):
        control.finish_iteration()
        released = threading.Event()
        run_in_background(
            lambda: (control.wait_for_another_iteration(), released.set())
        )

        control.apply(RunCommand.ENABLE_LOOP)

        assert released.wait(WAIT_TIMEOUT_SECONDS)
