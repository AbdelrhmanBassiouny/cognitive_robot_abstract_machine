"""
Running the suite a build is checked with.

The useful suite is a property of the repository rather than of this tool, so it is
configured - and a build asked for one the checkout names none for is refused before
anything is assembled, rather than reading an absent suite as one that passed.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestCommandNotConfiguredError(ValueError):
    """
    Raised when a build is asked to run a suite this checkout does not name one for.

    Refused rather than skipped: a build reporting that it ran nothing is honest, and a
    build reporting success because there was nothing to fail is the silence the suite
    exists to break.
    """

    setting: str
    """The configuration key that would name the suite."""

    def __str__(self) -> str:
        """:return: Which setting is missing, and the way out."""
        return (
            f"no suite to run: set '{self.setting}' in stack.toml, "
            f"or build with --no-test"
        )


def run_tests(command: str | None, working_directory: Path) -> bool | None:
    """
    Run the configured suite against the finished branch.

    :param command: The suite to run, or ``None`` when it was asked to be skipped.
    :param working_directory: The assembled branch's checkout.
    :return: Whether it passed, or ``None`` when it was not run.
    """
    if command is None:
        return None
    return (
        subprocess.run(
            shlex.split(command), cwd=working_directory, capture_output=True, text=True
        ).returncode
        == 0
    )
