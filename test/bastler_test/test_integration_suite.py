"""
Running the configured suite over the finished branch.
"""

from __future__ import annotations

import dataclasses
import sys

import pytest

from bastler.stack import PullRequest

import bastler.integration_build_commands
import bastler.integration_suite
from bastler.integration_exit_codes import IntegrationExitCode
from bastler.integration_report import exit_code_for
from bastler.integration_tips import ResolutionAuthor, ResolutionProvenance

from .test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

from .integration_fixtures import (
    ONLY_TIP,
    SECOND_TIP,
    a_recorded_resolution,
    build,
    two_colliding_tips,
)

# %% running the suite on the finished branch


def test_a_passing_suite_leaves_the_build_a_success(fork_checkout: ForkCheckout):
    """
    The single run on the finished branch is what replaced the per-branch CI gate.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
        test_command=f"{sys.executable} -c pass",
    )

    assert report.tests_passed is True
    assert exit_code_for(report) is IntegrationExitCode.SUCCESS


def test_a_failing_suite_is_never_reported_as_a_clean_build(
    fork_checkout: ForkCheckout,
):
    """
    A failure between two cleanly merging branches - one renaming what another calls - merges
    cleanly and
    breaks on import, so a green merge says nothing about whether the result works.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
        test_command=f"{sys.executable} -c 'raise SystemExit(1)'",
    )

    assert report.tests_passed is False
    assert exit_code_for(report) is IntegrationExitCode.TESTS_FAILED


def test_a_suite_that_was_not_run_is_neither_a_pass_nor_a_failure(
    fork_checkout: ForkCheckout,
):
    """
    ``--no-test`` has to be distinguishable from a suite that ran and passed, or a
    caller reading the document cannot tell a checked build from an unchecked one.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    assert report.tests_passed is None
    assert exit_code_for(report) is IntegrationExitCode.SUCCESS


def test_a_build_asked_for_a_suite_it_has_no_command_for_is_refused():
    """
    Reading an unconfigured suite as one that passed is the silence running it exists to
    break, so it is refused - and refused before anything is built, since a build that
    cost minutes only to find it cannot be checked has wasted them.
    """
    configuration = dataclasses.replace(
        make_configuration(), integration_test_command=""
    )

    with pytest.raises(bastler.integration_suite.TestCommandNotConfiguredError):
        bastler.integration_build_commands.BuildCommand()._test_command(
            configuration, run_tests=True
        )


def test_a_build_that_was_told_not_to_test_needs_no_command():
    """
    ``--no-test`` is the way past the refusal above, rather than a reason to configure a
    suite a checkout has no use for.
    """
    configuration = dataclasses.replace(
        make_configuration(), integration_test_command=""
    )

    assert bastler.integration_build_commands.BuildCommand()._test_command(
        configuration, run_tests=False
    ) is (None)


def test_a_failing_suite_over_a_machine_written_replay_is_its_own_status(
    fork_checkout: ForkCheckout,
):
    """
    Re-resolving into the same failure is how a build starts thrashing, so the status a
    caller acts on distinguishes this from an ordinary red suite: report and stop.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    a_recorded_resolution(fork_checkout)

    report = build(
        fork_checkout,
        pull_requests,
        provenance=ResolutionProvenance({SECOND_TIP: ResolutionAuthor.SKILL}),
        test_command=f"{sys.executable} -c 'raise SystemExit(1)'",
    )

    assert exit_code_for(report) is IntegrationExitCode.SUSPECT_REPLAY
