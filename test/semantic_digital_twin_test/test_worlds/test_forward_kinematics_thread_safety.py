"""
Thread-safety of :meth:`World.compose_forward_kinematics_expression`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

import pytest

_REPRO_SCRIPT = os.path.join(
    os.path.dirname(__file__), "concurrent_forward_kinematics_repro.py"
)
_THREAD_COUNT = 8
_DURATION_SECONDS = 15
_ATTEMPTS = 4

# %% regression test for a fixed native crash


@pytest.mark.slow
def test_concurrent_forward_kinematics_composition_does_not_crash():
    """
    Calling :meth:`World.compose_forward_kinematics_expression` from multiple threads at
    once, for overlapping chains of a real (branching) URDF, must not crash the process.

    Runs the reproduction in a subprocess and retries it a few times: the underlying
    failure is a native segfault, which would take the whole pytest process down if
    triggered in-process rather than raising a catchable Python exception, and the
    race is not deterministic on every single run.
    """
    crashes = []
    for attempt in range(_ATTEMPTS):
        result = subprocess.run(
            [
                sys.executable,
                _REPRO_SCRIPT,
                "--thread-count",
                str(_THREAD_COUNT),
                "--duration-seconds",
                str(_DURATION_SECONDS),
            ],
            capture_output=True,
            text=True,
            timeout=_DURATION_SECONDS + 60,
        )
        if result.returncode < 0:
            crashes.append(
                (
                    attempt,
                    signal.Signals(-result.returncode).name,
                    result.stderr[-2000:],
                )
            )

    assert (
        crashes == []
    ), f"reproduced a native crash in {len(crashes)}/{_ATTEMPTS} attempts: {crashes}"
