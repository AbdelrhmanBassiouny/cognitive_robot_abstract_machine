"""
Runs the whole Montessori demo for a stretch of wall-clock time and checks it survives.

The failure this guards against does not raise: reading or building a CasADi value from
a thread that does not own the world corrupts the native heap, and the process dies of
SIGSEGV or a glibc abort somewhere else entirely, often minutes later. Nothing an
in-process test asserts would survive that, so the demo runs as its own process and the
verdict is read off how that process ended.

One iteration of ``--max-shapes 1`` takes about a minute on the reference machine, so a
soak worth running is measured in minutes. It needs MuJoCo and the CRAM/Giskard stack
and is far too slow for CI, so it only runs when
:data:`SOAK_SECONDS_ENVIRONMENT_VARIABLE` asks for it::

    MONTESSORI_DEMO_SOAK_SECONDS=600 pytest test/experiments_test/test_montessori_demo_soak.py

:class:`SoakOutcome`'s own reading of an exit status is checked separately, and that part
does run in CI.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import func, select
from typing_extensions import List, Optional, Tuple

from experiments.montessori.results_database import ResultsDatabase
from semantic_digital_twin.utils import rclpy_installed

SOAK_SECONDS_ENVIRONMENT_VARIABLE = "MONTESSORI_DEMO_SOAK_SECONDS"
"""
How long to keep the demo sorting, in seconds; the soak is skipped when unset.
"""

DEMO_MODULE = "experiments.montessori.franka_montessori_demo"
"""
The demo run as its own process.
"""

PLANNED_ITERATIONS = 1000
"""
Iterations asked of the demo.

High enough that the soak's own deadline is always what ends the run, so the length of a
soak is decided in one place.
"""

SHUTDOWN_SECONDS = 120.0
"""
How long the demo is given to wind down after being interrupted, before it is killed.

Generous because an interrupt can land mid-plan, and a run killed early would be
reported as having been stopped rather than as having survived.
"""

CRASH_SIGNALS = frozenset(
    {signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGILL, signal.SIGFPE}
)
"""
Signals that mean the process died of its own accord rather than being stopped.

Heap corruption surfaces as one of these: ``SIGSEGV`` for a freed node dereferenced,
``SIGABRT`` for glibc noticing its arena is inconsistent.
"""

REPORTED_OUTPUT_LINES = 40
"""
How much of a failed run's log to quote in the failure message.
"""


@dataclass(frozen=True)
class SoakOutcome:
    """
    How a soaked demo process ended, and how much sorting it got done.
    """

    exit_status: int
    """
    The process's exit status, negative when it was ended by a signal.
    """

    was_stopped_at_the_deadline: bool
    """
    Whether the soak interrupted a still-running demo, rather than the demo ending by
    itself.
    """

    recorded_iterations: int
    """
    How many iterations the run finished and recorded.
    """

    output: str
    """
    Everything the run wrote to its standard output and error.
    """

    @property
    def crash_signal(self) -> Optional[signal.Signals]:
        """
        The signal the process died of, or None if it was not one that means a crash.
        """
        if self.exit_status >= 0:
            return None
        died_of = signal.Signals(-self.exit_status)
        return died_of if died_of in CRASH_SIGNALS else None

    @property
    def kept_going(self) -> bool:
        """
        Whether the run was still sorting when the soak ended it, or finished cleanly.
        """
        return self.was_stopped_at_the_deadline or self.exit_status == 0

    def report(self) -> str:
        """
        The end of the run's log, for a failure message to quote.
        """
        return "\n".join(self.output.splitlines()[-REPORTED_OUTPUT_LINES:])


@dataclass
class SoakedDemo:
    """
    The Montessori demo, run headless as its own process until a deadline.
    """

    database_uri: str
    """
    Where the run records the iterations it finishes.
    """

    log_path: Path
    """
    File the run's output is written to; a pipe nobody drains would block it.
    """

    seconds: float
    """
    How long to let the demo keep sorting before interrupting it.
    """

    shapes_per_iteration: int = 1
    """
    Shapes attempted per iteration.

    One keeps an iteration short enough that a soak of a few minutes is several
    iterations rather than part of one.
    """

    _process: Optional[subprocess.Popen] = field(init=False, default=None)
    """
    The launched demo, once started.
    """

    @property
    def command(self) -> List[str]:
        """
        The command the demo is launched with.
        """
        return [
            sys.executable,
            "-m",
            DEMO_MODULE,
            "--no-viewer",
            "--no-rviz",
            "--world2",
            "--max-shapes",
            str(self.shapes_per_iteration),
            "--iterations",
            str(PLANNED_ITERATIONS),
            "--database-uri",
            self.database_uri,
        ]

    def run(self) -> SoakOutcome:
        """
        Sort until the deadline, then interrupt the run and report how it ended.
        """
        with self.log_path.open("w") as log:
            # its own session, so it can be interrupted along with the simulator it
            # starts without the signal reaching the test runner
            self._process = subprocess.Popen(
                self.command,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
            )
            exit_status, was_stopped = self._sort_until_the_deadline()
        return SoakOutcome(
            exit_status=exit_status,
            was_stopped_at_the_deadline=was_stopped,
            recorded_iterations=self._count_recorded_iterations(),
            output=self.log_path.read_text(errors="replace"),
        )

    def _sort_until_the_deadline(self) -> Tuple[int, bool]:
        """
        Wait out the soak, interrupting a demo that is still going when it ends.

        :return: The run's exit status, and whether it was the soak that ended it.
        """
        try:
            return self._process.wait(timeout=self.seconds), False
        except subprocess.TimeoutExpired:
            return self._interrupt(), True

    def _interrupt(self) -> int:
        """
        Ask the run to stop, killing it if it outstays :data:`SHUTDOWN_SECONDS`.
        """
        os.killpg(os.getpgid(self._process.pid), signal.SIGINT)
        try:
            return self._process.wait(timeout=SHUTDOWN_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            return self._process.wait()

    def _count_recorded_iterations(self) -> int:
        """
        How many iterations the run committed to its results database.
        """
        import experiments.orm.ormatic_interface as ormatic_interface

        with ResultsDatabase(uri=self.database_uri).open_session() as session:
            return session.scalar(
                select(func.count()).select_from(
                    ormatic_interface.SortingIterationResultDAO
                )
            )


# %% reading an exit status
def test_a_run_killed_by_a_segmentation_fault_names_the_signal():
    """
    A corrupted heap is what this whole soak exists to catch, and it arrives as a signal
    rather than as anything the run reports about itself.
    """
    outcome = SoakOutcome(
        exit_status=-signal.SIGSEGV,
        was_stopped_at_the_deadline=False,
        recorded_iterations=3,
        output="",
    )

    assert outcome.crash_signal is signal.SIGSEGV
    assert not outcome.kept_going


def test_a_run_killed_by_a_heap_abort_names_the_signal():
    """
    glibc aborts rather than segfaults when it is the allocator that notices the
    corruption, so both readings have to count as a crash.
    """
    outcome = SoakOutcome(
        exit_status=-signal.SIGABRT,
        was_stopped_at_the_deadline=False,
        recorded_iterations=3,
        output="",
    )

    assert outcome.crash_signal is signal.SIGABRT


def test_a_run_the_soak_interrupted_did_not_crash():
    """
    The soak ends a healthy run itself, so being signalled is not on its own a failure.
    """
    outcome = SoakOutcome(
        exit_status=-signal.SIGINT,
        was_stopped_at_the_deadline=True,
        recorded_iterations=3,
        output="",
    )

    assert outcome.crash_signal is None
    assert outcome.kept_going


def test_a_run_that_finished_every_iteration_did_not_crash():
    """
    A soak longer than the iterations asked of the demo ends with the demo exiting by
    itself.
    """
    outcome = SoakOutcome(
        exit_status=0,
        was_stopped_at_the_deadline=False,
        recorded_iterations=3,
        output="",
    )

    assert outcome.crash_signal is None
    assert outcome.kept_going


def test_a_run_that_raised_did_not_keep_going():
    """
    A run that ended on an unhandled exception stopped sorting early, which the soak
    must not read as having survived.
    """
    outcome = SoakOutcome(
        exit_status=1,
        was_stopped_at_the_deadline=False,
        recorded_iterations=0,
        output="",
    )

    assert outcome.crash_signal is None
    assert not outcome.kept_going


# %% the soak itself
@pytest.mark.skipif(
    os.getenv(SOAK_SECONDS_ENVIRONMENT_VARIABLE) is None,
    reason="set %s to how many seconds the demo should keep sorting"
    % SOAK_SECONDS_ENVIRONMENT_VARIABLE,
)
@pytest.mark.skipif(
    not rclpy_installed(), reason="the demo needs the CRAM/Giskard stack"
)
def test_the_demo_keeps_sorting_for_the_whole_soak(tmp_path):
    """
    The demo sorts shape after shape for minutes on end without the process dying.

    Every iteration rebuilds the world and sorts again while the segmind monitor ticks
    its detectors on a thread of its own, which is the arrangement that used to corrupt
    the heap.
    """
    soak = SoakedDemo(
        database_uri="sqlite:///%s" % (tmp_path / "results.db"),
        log_path=tmp_path / "demo.log",
        seconds=float(os.environ[SOAK_SECONDS_ENVIRONMENT_VARIABLE]),
    )

    outcome = soak.run()

    assert (
        outcome.crash_signal is None
    ), "the demo died of %s after %d iteration(s):\n%s" % (
        outcome.crash_signal,
        outcome.recorded_iterations,
        outcome.report(),
    )
    assert outcome.kept_going, "the demo stopped sorting by itself (status %d):\n%s" % (
        outcome.exit_status,
        outcome.report(),
    )
    assert outcome.recorded_iterations >= 1, (
        "the demo recorded no finished iteration in %.0fs; a soak has to be long enough "
        "for at least one:\n%s" % (soak.seconds, outcome.report())
    )
