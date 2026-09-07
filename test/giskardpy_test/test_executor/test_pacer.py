from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

import pytest

from giskardpy.data_types.exceptions import (
    NonPositiveRealTimeFactorError,
    SimulationStoppedError,
)
from giskardpy.executor import (
    Executor,
    NoPacing,
    RealTimePacer,
    SimulationPacer,
    SimulationTimePacer,
)
from giskardpy.simulation_clock import SimulationClock
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import MotionStatechartNode, EndMotion
from giskardpy.motion_statechart.monitors.payload_monitors import CountSeconds
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.world import World


def test_simulation_pacer_timing_real_time(monkeypatch):
    pacer = SimulationPacer(real_time_factor=1.0)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 1.0, rtol=0.01)


def test_simulation_pacer_timing_2x(monkeypatch):
    pacer = SimulationPacer(real_time_factor=2.0)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    actual = perf_counter() - start_time
    assert np.isclose(actual, 0.5, rtol=0.01)


def test_simulation_pacer_timing_halfx(monkeypatch):
    pacer = SimulationPacer(real_time_factor=0.5)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 2.0, rtol=0.01)


def test_no_pacing_does_not_wait():
    pacer = NoPacing()
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert perf_counter() - start_time < 0.01


def test_real_time_pacer_holds_the_target_frequency():
    pacer = RealTimePacer()
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 1.0, rtol=0.01)


def test_a_simulation_cannot_be_configured_to_stand_still():
    with pytest.raises(NonPositiveRealTimeFactorError):
        SimulationPacer(real_time_factor=0.0)


def test_with_executor():
    msc = MotionStatechart()
    msc.add_node(counter := CountSeconds(seconds=1.0))
    msc.add_node(EndMotion.when_true(counter))

    kin_sim = Executor(
        context=MotionStatechartContext(
            world=World(),
            qp_controller_config=QPControllerConfig.create_with_simulation_defaults(),
        ),
        pacer=SimulationPacer(real_time_factor=2.0),
    )
    kin_sim.compile(msc)
    kin_sim.tick_until_end(timeout=1000)
    # we tick 20 (hz) * 2 (real_time_factor) per second and sleep for 1s.
    # +2 because the endmotion needs to extra ticks
    assert kin_sim.control_cycles == 42


# %% a simulation clock a test drives


@dataclass
class ReplayedSimulationClock(SimulationClock):
    """
    A simulation clock reporting prepared times, one per read, so a test decides exactly
    what a control loop waiting on simulated time gets to see.

    Reads past the end of the prepared times all report the last of them, which is what
    a simulation whose time has come to a halt looks like.
    """

    times: list[float]
    """
    What successive reads of :attr:`time` report, earliest first.
    """

    has_stopped: bool = False
    """
    Whether the simulation this clock belongs to has ended.
    """

    reads: int = field(default=0, init=False)
    """
    How many times :attr:`time` has been read so far.
    """

    @property
    def time(self) -> float:
        reading = self.times[min(self.reads, len(self.times) - 1)]
        self.reads += 1
        return reading


def build_pacer(clock: SimulationClock, target_frequency: float) -> SimulationTimePacer:
    """
    A pacer on ``clock`` that polls without waiting, so a test runs at full speed.
    """
    pacer = SimulationTimePacer(simulation_clock=clock, poll_interval=0.0)
    pacer.target_frequency = target_frequency
    return pacer


# %% pacing against a simulation whose time stops


def test_a_stopped_simulation_does_not_block_the_control_loop():
    clock = ReplayedSimulationClock(times=[0.0], has_stopped=True)
    pacer = build_pacer(clock, target_frequency=50)

    with pytest.raises(SimulationStoppedError) as raised:
        pacer.sleep()

    assert raised.value.simulation_time == 0.0
    assert raised.value.next_cycle_time == 1 / pacer.target_frequency


def test_a_paused_simulation_is_waited_for_rather_than_given_up_on():
    clock = ReplayedSimulationClock(times=[0.0, 0.0, 0.0, 1 / 50])
    pacer = build_pacer(clock, target_frequency=50)

    pacer.sleep()

    # Every standing-still reading was waited out rather than read as a stall.
    assert clock.reads >= len(clock.times)


def test_a_cycle_the_simulation_completed_before_stopping_still_counts():
    clock = ReplayedSimulationClock(times=[0.0, 1 / 50], has_stopped=True)
    pacer = build_pacer(clock, target_frequency=50)

    pacer.sleep()

    # The time the simulation stopped at was read, rather than the earlier one it had
    # when the cycle began being waited for.
    assert clock.reads >= len(clock.times)


def test_a_simulation_that_ran_ahead_leaves_no_backlog_of_cycles():
    cycle_duration = 1 / 50
    clock = ReplayedSimulationClock(times=[0.0, 1.0])
    pacer = build_pacer(clock, target_frequency=50)

    pacer.sleep()
    clock.has_stopped = True
    with pytest.raises(SimulationStoppedError) as raised:
        pacer.sleep()

    # The simulation jumped a whole second in one cycle. The next cycle is due within
    # one cycle of where it actually got, rather than at the first of the fifty targets
    # it overshot on the way there.
    assert raised.value.simulation_time == 1.0
    assert 1.0 < raised.value.next_cycle_time <= 1.0 + cycle_duration


def test_the_tick_loop_gives_up_when_its_simulation_stops():
    msc = MotionStatechart()
    msc.add_node(counter := CountSeconds(seconds=1.0))
    msc.add_node(EndMotion.when_true(counter))

    executor = Executor(
        context=MotionStatechartContext(
            world=World(),
            qp_controller_config=QPControllerConfig.create_with_simulation_defaults(),
        ),
        pacer=SimulationTimePacer(
            simulation_clock=ReplayedSimulationClock(times=[0.0], has_stopped=True),
            poll_interval=0.0,
        ),
    )
    executor.compile(msc)

    with pytest.raises(SimulationStoppedError):
        executor.tick_until_end(timeout=1000)
