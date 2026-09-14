"""
A rehearsal interrupted from the keyboard ends with the interruption.

Kept apart from the rehearsal's own tests: the command initialises ROS itself, which it
cannot do while a module-wide context of those tests is still up.
"""

from __future__ import annotations

import os
import signal
import threading
import time

import pytest
import rclpy
from typing_extensions import List

from experiments.episodes.artifacts import ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE
from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    run_dashboard,
)
from experiments.tracy_experiments.pickup import pickup_demo_rehearsal
from experiments.tracy_experiments.pickup.pickup_demo_rehearsal import Rehearsal, main

A_MOMENT = 5.0
"""
Longer than a signal takes to reach the process that sent it to itself, in seconds.
"""


def interrupted_from_the_keyboard(rehearsal: Rehearsal) -> None:
    """
    A rehearsal that is interrupted while it runs, the way Ctrl+C interrupts it.

    :param rehearsal: The rehearsal interrupted.
    """
    os.kill(os.getpid(), signal.SIGINT)
    time.sleep(A_MOMENT)


def no_dashboard(feed: EventFeed) -> None:
    """
    Serve no dashboard, which a test has no browser for.

    :param feed: The events a dashboard would have shown.
    """


def test_an_interrupted_rehearsal_is_shut_down_by_the_command_itself(
    tmp_path, monkeypatch
):
    """
    An interruption from the keyboard reaches the command while ROS is still up, and the
    command shuts ROS down on its own thread, so nothing else races it to the shutdown.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))
    monkeypatch.setattr(pickup_demo_rehearsal, run_dashboard.__name__, no_dashboard)
    shut_down_on: List[str] = []

    def interrupted_noting_the_shutdown(rehearsal: Rehearsal) -> None:
        rclpy.get_default_context().on_shutdown(
            lambda: shut_down_on.append(threading.current_thread().name)
        )
        interrupted_from_the_keyboard(rehearsal)

    monkeypatch.setattr(
        Rehearsal, Rehearsal.run.__name__, interrupted_noting_the_shutdown
    )

    with pytest.raises(KeyboardInterrupt):
        main([])

    assert shut_down_on == [threading.main_thread().name]


def test_an_interrupted_rehearsal_ends_with_the_interruption(tmp_path, monkeypatch):
    """
    Interrupting shuts ROS down before the command does, so the command's own shutdown
    must not replace the interruption with an error about a shutdown already done.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))
    monkeypatch.setattr(pickup_demo_rehearsal, run_dashboard.__name__, no_dashboard)
    monkeypatch.setattr(
        Rehearsal, Rehearsal.run.__name__, interrupted_from_the_keyboard
    )

    with pytest.raises(KeyboardInterrupt):
        main([])
