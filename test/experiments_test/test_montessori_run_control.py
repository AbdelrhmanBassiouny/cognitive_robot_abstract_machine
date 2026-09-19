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

from cramera.live.run_clock import RunClock
from cramera.live.run_control import RunActivity, RunCommand

from experiments.montessori.run_control import SortingRunControl

from .dataset.wound_clock import WoundClock

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
def wound_clock() -> WoundClock:
    return WoundClock()


@pytest.fixture()
def timed_control(wound_clock) -> SortingRunControl:
    """
    A run in progress whose clock a test moves by hand.
    """
    control = SortingRunControl(clock=RunClock(monotonic_seconds=wound_clock.read))
    control.begin_iteration(iteration=1, simulation=RecordingSimulation())
    return control


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


# %% the clock whatever plots the run measures it along
class TestTheRunsOwnClock:
    def test_a_run_that_has_not_begun_has_got_nowhere(self, wound_clock):
        """
        A world is still being built at that point, so nothing has happened to plot.
        """
        control = SortingRunControl(clock=RunClock(monotonic_seconds=wound_clock.read))

        wound_clock.advance(30.0)

        assert control.clock.elapsed_seconds() == 0.0

    def test_a_sorting_run_carries_its_clock_along(self, timed_control, wound_clock):
        wound_clock.advance(12.0)

        assert timed_control.clock.elapsed_seconds() == 12.0

    def test_pausing_the_run_stops_its_clock(self, timed_control, wound_clock):
        wound_clock.advance(4.0)

        timed_control.apply(RunCommand.PAUSE)
        wound_clock.advance(60.0)

        assert timed_control.clock.elapsed_seconds() == 4.0

    def test_a_paused_run_says_its_clock_is_not_going(self, timed_control):
        timed_control.apply(RunCommand.PAUSE)

        assert timed_control.clock.reading().running is False

    def test_resuming_the_run_carries_its_clock_on_past_the_pause(
        self, timed_control, wound_clock
    ):
        wound_clock.advance(4.0)
        timed_control.apply(RunCommand.PAUSE)
        wound_clock.advance(60.0)

        timed_control.apply(RunCommand.RESUME)
        wound_clock.advance(2.0)

        assert timed_control.clock.elapsed_seconds() == 6.0

    def test_the_next_iteration_measures_from_its_own_start(
        self, timed_control, wound_clock
    ):
        wound_clock.advance(40.0)

        timed_control.begin_iteration(iteration=2, simulation=RecordingSimulation())
        wound_clock.advance(3.0)

        assert timed_control.clock.elapsed_seconds() == 3.0

    def test_an_iteration_begun_while_paused_starts_out_stopped(
        self, timed_control, wound_clock
    ):
        """
        A run paused across a rebuild stays paused, so its clock has to as well.
        """
        timed_control.apply(RunCommand.PAUSE)

        timed_control.begin_iteration(iteration=2, simulation=RecordingSimulation())
        wound_clock.advance(5.0)

        assert timed_control.clock.elapsed_seconds() == 0.0

    def test_a_finished_run_stops_its_clock_where_it_ended(
        self, timed_control, wound_clock
    ):
        """
        A finished run holds its final state for inspection, and a clock still running
        would say it was getting somewhere.
        """
        wound_clock.advance(9.0)

        timed_control.finish_iteration()
        wound_clock.advance(60.0)

        assert timed_control.clock.elapsed_seconds() == 9.0

    def test_resuming_a_finished_run_leaves_its_clock_where_it_ended(
        self, timed_control, wound_clock
    ):
        """
        Nothing is carrying on, so nothing may make the clock carry on either.
        """
        wound_clock.advance(9.0)
        timed_control.finish_iteration()

        timed_control.apply(RunCommand.PAUSE)
        timed_control.apply(RunCommand.RESUME)
        wound_clock.advance(60.0)

        assert timed_control.clock.elapsed_seconds() == 9.0
