"""
What a shutdown registered to run at interpreter exit keeps alive, and when it runs.
"""

from __future__ import annotations

import gc
import subprocess
import sys
import weakref
from dataclasses import dataclass
from pathlib import Path

from physics_simulators.shutdown_at_exit import ShutdownAtExit

from .dataset.shutdown_at_exit_run import SHUTDOWN_RAN, ShutdownCase

RUN_SCRIPT = Path(__file__).parent / "dataset" / "shutdown_at_exit_run.py"
"""
The script each case is run in an interpreter of its own.
"""

# %% something whose shutdown runs at interpreter exit


@dataclass
class ShutsDownAtExit:
    """
    A stand-in for anything that asks for its shutdown to be run when the interpreter
    exits.
    """

    times_shut_down: int = 0
    """
    How often :meth:`shut_down` has been called.
    """

    def shut_down(self) -> None:
        """
        The shutdown that is registered to run at interpreter exit.
        """
        self.times_shut_down += 1


def output_of(case: ShutdownCase) -> str:
    """
    Run one case to the end of its own interpreter.

    :param case: What the run leaves behind when it reaches the end.
    :return: What the run printed.
    """
    return subprocess.run(
        [sys.executable, str(RUN_SCRIPT), case],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


# %% what a registration holds


def test_a_registration_does_not_keep_its_object_alive():
    subject = ShutsDownAtExit()
    reference = weakref.ref(subject)
    ShutdownAtExit.register(subject.shut_down)

    del subject
    gc.collect()

    assert reference() is None


def test_the_shutdown_runs_for_an_object_that_is_still_in_use():
    subject = ShutsDownAtExit()
    registration = ShutdownAtExit.register(subject.shut_down)

    registration()

    assert subject.times_shut_down == 1
    registration.cancel()


def test_the_shutdown_of_a_collected_object_does_nothing():
    registration = ShutdownAtExit.register(ShutsDownAtExit().shut_down)
    gc.collect()

    registration()


# %% when the interpreter exits


def test_a_registered_shutdown_runs_when_the_interpreter_exits():
    assert output_of(ShutdownCase.REGISTERED).splitlines() == [SHUTDOWN_RAN]


def test_a_cancelled_shutdown_does_not_run_when_the_interpreter_exits():
    assert output_of(ShutdownCase.CANCELLED).splitlines() == []


def test_the_shutdown_of_a_collected_object_does_not_run_when_the_interpreter_exits():
    assert output_of(ShutdownCase.COLLECTED).splitlines() == []
