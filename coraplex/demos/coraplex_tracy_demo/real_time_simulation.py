"""
Runs a world's MuJoCo mirror at wall-clock speed, so the motion can be watched as it
happens.

Ported verbatim from ``experiments/push_t/real_time_simulation.py`` on
``ichumuh/cognitive_robot_abstract_machine@t-task-force`` (commit ``f0d0e967a``, "Push a
T-shaped block onto a target pose in MuJoCo"), which does not exist on this branch. Its
own docstring explains exactly why this demo needs it: the background-threaded
:class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim` this repo's other demos use
makes a caller's own reads of ``world.state`` a race against that thread's own writes --
confirmed directly here (see :mod:`tracy_equipment`'s own docstring) as the reason
Giskard's ``ParkArmsAction`` could believe a physically-simulated joint had reached its
target without the joint having actually moved.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from typing_extensions import Optional, Self

from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Actuator

# %% real-time simulation


class SimulationNotStartedError(RuntimeError):
    """
    Raised when a :class:`RealTimeSimulation` is advanced before it was started.
    """

    def __init__(self, world: World):
        super().__init__(
            f"The simulation of {world} has to be started before it can be advanced."
        )
        self.world = world
        """
        The world whose simulation was advanced too early.
        """


@dataclass
class RealTimeSimulation:
    """
    A MuJoCo simulation of a world, stepped by its owner and paced to the wall clock.

    MuJoCo's own run loop steps as fast as the machine allows, which makes anything
    watchable only by accident, and runs on a background thread, which makes the state a
    caller reads back a race. This steps the physics from the calling thread instead and
    waits out the difference between simulated and elapsed time, so a caller can drive
    the world between advances and still watch it move at life speed.
    """

    world: World
    """
    The world to simulate.

    Its state is kept in sync with the simulation both ways.
    """

    step_size: float = 1e-3
    """
    The physics time step, in seconds.
    """

    headless: bool = False
    """
    Whether to run without opening MuJoCo's viewer window.
    """

    multi_sim: MujocoSim = field(init=False)
    """
    The MuJoCo mirror of :attr:`world`.
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
        self.multi_sim = MujocoSim(
            world=self.world, headless=self.headless, step_size=self.step_size
        )

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        """
        Open the viewer and reset the simulation to the world's built pose.
        """
        self.multi_sim.simulator.start(simulate_in_thread=False, render_in_thread=False)
        self._simulated_time = 0.0
        self._start_time = time.time()

    def stop(self) -> None:
        """
        Close the viewer and tear the simulation down.
        """
        self.multi_sim.stop_simulation()
        self._start_time = None

    @property
    def is_running(self) -> bool:
        """
        Whether the simulation is still being displayed, i.e. the viewer window is open.
        """
        return self.multi_sim.simulator.renderer.is_running()

    def command(self, actuator: Actuator, set_point: float) -> None:
        """
        Hand an actuator a new set point, which it drives towards from the next
        :meth:`advance` on.

        :param actuator: The actuator to command. It has to belong to :attr:`world`.
        :param set_point: The value the actuator should drive towards.
        """
        self.multi_sim.simulator.set_actuator_control(
            actuator_name=actuator.name.name, value=set_point
        )

    def advance(self, duration: float) -> None:
        """
        Step the physics forward, refresh the viewer, and wait until the wall clock has
        caught up.

        Call this in short slices - around a frame's worth - so the world can be driven
        in between and the viewer stays smooth.

        :param duration: How many simulated seconds to advance.
        """
        if self._start_time is None:
            raise SimulationNotStartedError(world=self.world)

        simulator = self.multi_sim.simulator
        for _ in range(round(duration / simulator.step_size)):
            simulator.step()
            self._simulated_time += simulator.step_size
        simulator.renderer.sync()

        remaining = self._start_time + self._simulated_time - time.time()
        if remaining > 0:
            time.sleep(remaining)
