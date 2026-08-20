"""
The builder as a process: what a caller reaches, and what its exit status says.
"""

from __future__ import annotations

import subprocess
import sys

import integration
from integration import (
    IntegrationExitCode,
)

from maintenance_constants import CREDENTIAL_VARIABLES

from test_maintenance import (
    ForkCheckout,
    UPSTREAM_REMOTE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
)

from integration_fixtures import (
    INTEGRATION_SCRIPT,
)

# %% the command line


def run_integration(
    checkout: ForkCheckout, *arguments: str
) -> subprocess.CompletedProcess:
    """
    Invoke the builder as a subprocess, where the exit status is the assertion.

    :param checkout: The checkout to run in.
    :param arguments: The command line to pass.
    :return: The finished process.
    """
    environment = {
        key: value
        for key, value in dict(**subprocess.os.environ).items()
        if key not in set(CREDENTIAL_VARIABLES)
    }
    return subprocess.run(
        [sys.executable, str(INTEGRATION_SCRIPT), *arguments],
        cwd=checkout.project_root,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_a_command_that_exists_is_reachable_from_the_command_line():
    """
    Commands are found from their own subclasses, so one that exists cannot be left
    unreachable by forgetting to list it.
    """
    assert integration.BuildCommand() in integration.COMMANDS


def test_a_missing_credential_is_its_own_exit_status(fork_checkout: ForkCheckout):
    """
    The fork's open pull requests are what a build is derived from, so a run without a
    token is sent after a token rather than after something it cannot fix.
    """
    fork_checkout.git.remove_remote(UPSTREAM_REMOTE)

    finished = run_integration(fork_checkout, "build", "--no-test")

    assert finished.returncode == int(IntegrationExitCode.CREDENTIAL_UNAVAILABLE)
    assert IntegrationExitCode.CREDENTIAL_UNAVAILABLE.name_for_a_caller in (
        finished.stderr
    )
