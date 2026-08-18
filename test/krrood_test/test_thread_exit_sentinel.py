"""
How a thread stays joinable when a module load registers an exit sentinel of its own.
"""

import _thread
import pathlib
import subprocess
import sys
import threading

from krrood.thread_exit_sentinel import ThreadExitSentinel

JOIN_TIMEOUT_IN_SECONDS = 2.0
"""
How long to wait for a worker thread that has already finished its work; a thread that
cannot be joined stays alive for the life of the process, so any wait at all
distinguishes the two.
"""

SUBPROCESS_TIMEOUT_IN_SECONDS = 300.0
"""
How long the interpreter that evaluates a query on a worker thread may take, dominated
by importing the query backend and the model chain behind it.
"""

# %% a module load that takes the registration over


def take_over_exit_sentinel():
    """
    Register an exit sentinel for the calling thread and drop it, the way importing a
    module that instantiates its own main-thread object does.
    """
    _thread._set_sentinel()


# %% the sentinel of a single thread


def test_a_thread_whose_sentinel_was_taken_over_cannot_be_joined():
    """
    Without the repair, losing the registration leaves the thread alive after its target
    returned; this is the failure :class:`ThreadExitSentinel` exists to undo.
    """
    worker = threading.Thread(target=take_over_exit_sentinel, daemon=True)
    worker.start()
    worker.join(JOIN_TIMEOUT_IN_SECONDS)

    assert worker.is_alive() is True


def test_re_registering_the_sentinel_lets_the_thread_be_joined():
    """
    A thread that puts its sentinel back ends normally, even though a module load took
    the registration away while it ran.
    """

    def lose_and_regain_sentinel():
        sentinel = ThreadExitSentinel()
        take_over_exit_sentinel()
        assert sentinel.is_registered is False
        sentinel.ensure_registered()
        assert sentinel.is_registered is True

    worker = threading.Thread(target=lose_and_regain_sentinel, daemon=True)
    worker.start()
    worker.join(JOIN_TIMEOUT_IN_SECONDS)

    assert worker.is_alive() is False


def test_an_untouched_sentinel_is_left_alone():
    """
    Nothing is re-registered for a thread that still holds its own sentinel, so the lock
    :meth:`threading.Thread.join` waits on stays the same object.
    """
    locks_seen = {}

    def record_lock_around_ensuring():
        sentinel = ThreadExitSentinel()
        locks_seen["before"] = threading.current_thread()._tstate_lock
        assert sentinel.is_registered is True
        sentinel.ensure_registered()
        locks_seen["after"] = threading.current_thread()._tstate_lock

    worker = threading.Thread(target=record_lock_around_ensuring, daemon=True)
    worker.start()
    worker.join(JOIN_TIMEOUT_IN_SECONDS)

    assert locks_seen["after"] is locks_seen["before"]


# %% evaluating a query on a thread of its own


def test_a_thread_that_evaluates_a_query_ends():
    """
    Evaluating a query loads the backend module, whose own import chain registers an
    exit sentinel; the thread that triggers that load must still be joinable afterwards.

    Run in a fresh interpreter because only the first evaluation in a process loads the
    backend module, and this test session has almost certainly loaded it already.
    """
    script = (
        pathlib.Path(__file__).parent / "dataset" / "evaluate_query_on_worker_thread.py"
    )

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_IN_SECONDS,
    )

    assert result.returncode == 0, result.stderr
