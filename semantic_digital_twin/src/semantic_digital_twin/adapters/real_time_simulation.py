"""
Runs a world's MuJoCo mirror from the calling thread, paced to the wall clock, so a
controller can drive the world between physics steps and a person can watch it move at
life speed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from typing_extensions import Optional, Self

from semantic_digital_twin.adapters.multi_sim import MujocoSim, MujocoSynchronizer
from semantic_digital_twin.exceptions import SimulationNotStartedError
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Actuator


@dataclass
class RealTimeSimulation:
    """
    A MuJoCo simulation of a world, stepped by its owner and paced to the wall clock.

    MuJoCo's own run loop steps as fast as the machine allows, which makes anything
    watchable only by accident, and runs on a background thread, which makes the state a
    caller reads back a race against that thread's writes. This steps the physics from
    the calling thread instead and waits out the difference between simulated and
    elapsed time, so a controller can tick against the world between advances, in
    lockstep with the physics, and still be watched at life speed.

    Use it as a context manager, driving the world between advances::

        with RealTimeSimulation(world) as simulation:
            for _ in range(cycles):
                executor.tick()
                simulation.advance(control_period)

    Entering starts the simulation and leaving stops it; :meth:`start` and
    :meth:`stop` do the same for a simulation that outlives one block. A joint an
    actuator drives takes the world's position as its set point on every advance,
    and :meth:`command` hands an actuator a set point directly.
    """

    world: World
    """
    The world to simulate.

    Its state is kept in sync with the simulation both ways: a joint an actuator drives
    takes the world's position as its set point, and every other degree of freedom is
    read back from the physics.
    """

    step_size: float = 1e-3
    """
    The physics time step, in seconds.
    """

    headless: bool = False
    """
    Whether to run without opening MuJoCo's viewer window.
    """

    real_time_factor: Optional[float] = 1.0
    """
    Speed of the simulation clock relative to the wall clock: ``1.0`` paces simulated
    time 1:1 with real time, ``2.0`` runs at double speed.

    ``None`` disables the pacing entirely, so :meth:`advance` returns as soon as its
    physics steps are done, for running in batch rather than watching.
    """

    sync_rate_hz: float = MujocoSynchronizer.UNTHROTTLED_SYNC_RATE_HZ
    """
    How often the simulation's state is read back into :attr:`world`, in wall-clock
    hertz.

    The synchronizer's own default throttles this to 30 Hz, which leaves a controller
    running faster than that reading a stale world every other cycle.
    """

    mujoco_mirror: MujocoSim = field(init=False)
    """
    The MuJoCo simulation mirroring :attr:`world`.
    """

    _simulated_time: float = field(init=False, default=0.0, repr=False)
    """
    Seconds of simulated time advanced since :meth:`start`.
    """

    _start_time: Optional[float] = field(init=False, default=None, repr=False)
    """
    Wall-clock time :meth:`start` was called at, or ``None`` while not running.
    """

    def __post_init__(self):
        self.mujoco_mirror = MujocoSim(
            world=self.world, headless=self.headless, step_size=self.step_size
        )
        self.mujoco_mirror.synchronizer.sync_rate_hz = self.sync_rate_hz

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        """
        Open the viewer, reset the simulation to the world's built pose, and hand every
        actuator the position its joint currently holds, so nothing rushes towards zero
        the moment the physics starts.
        """
        self.mujoco_mirror.simulator.start(
            simulate_in_thread=False, render_in_thread=False
        )
        self.mujoco_mirror.synchronizer.command_actuators_from_world_state()
        self._simulated_time = 0.0
        self._start_time = time.time()

    def stop(self) -> None:
        """
        Close the viewer and tear the simulation down.
        """
        self.mujoco_mirror.stop_simulation()
        self._start_time = None

    @property
    def is_running(self) -> bool:
        """
        Whether the simulation is still being displayed, i.e. the viewer window is open.
        """
        return self.mujoco_mirror.simulator.renderer.is_running()

    def command(self, actuator: Actuator, set_point: float) -> None:
        """
        Hand an actuator a new set point, which it drives towards from the next
        :meth:`advance` on.

        :param actuator: The actuator to command. It has to belong to :attr:`world`.
        :param set_point: The value the actuator should drive towards.
        """
        self.mujoco_mirror.simulator.set_actuator_control(
            actuator_name=actuator.name.name, value=set_point
        )

    def advance(self, duration: float) -> None:
        """
        Step the physics forward, refresh the viewer, and wait until the wall clock has
        caught up.

        Call this in short slices, around a control cycle's worth, so the world can be
        driven in between and the viewer stays smooth.

        :param duration: How many simulated seconds to advance.
        :raises SimulationNotStartedError: If :meth:`start` was not called.
        """
        if self._start_time is None:
            raise SimulationNotStartedError(self.world.root.name.name)

        simulator = self.mujoco_mirror.simulator
        for _ in range(round(duration / simulator.step_size)):
            simulator.step()
            self._simulated_time += simulator.step_size
        simulator.renderer.sync()

        if self.real_time_factor is None:
            return
        remaining = (
            self._start_time
            + self._simulated_time / self.real_time_factor
            - time.time()
        )
        if remaining > 0:
            time.sleep(remaining)
