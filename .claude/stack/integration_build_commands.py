"""
Building the branch, and saying which pair of tips a failing suite is about.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from stack import (
    Configuration,
    ConfigurationKey,
)

from maintenance_github import GitHubRepository

from integration_assembly import build_integration
from integration_block_record import BlockRecords, lift_readmitted
from integration_left_out import report_left_out
from integration_plans import PlanFilter
from integration_exit_codes import IntegrationExitCode
from integration_failure import FailureLocation, print_failure_location
from integration_report import IntegrationReport, exit_code_for, print_build
from integration_run import IntegrationCommand, IntegrationRun
from integration_selection import build_branch_name, stack_to_build
from integration_suite import TestCommandNotConfiguredError
from integration_tips import ResolutionProvenance


@dataclass(frozen=True)
class BuildCommand(IntegrationCommand):
    """
    Assembles the upstream base plus every reviewed in-flight stack tip.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "build"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "assemble the upstream base plus every reviewed in-flight tip"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--restack",
            action="store_true",
            help=(
                "bring every stale tip forward first; this pushes to branches that "
                "belong to other people, which is why it is not the default"
            ),
        )
        parser.add_argument(
            "--no-test",
            dest="run_tests",
            action="store_false",
            help="skip the suite that would otherwise be run on the finished branch",
        )
        parser.add_argument(
            "--plan",
            action="append",
            default=[],
            metavar="PLAN",
            help=(
                "carry only the tips belonging to this plan; repeat it or separate "
                "several with commas. A branch the plan index names no plan for is "
                "reported rather than dropped or carried"
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )
        parser.add_argument(
            "--report-left-out",
            action="store_true",
            help=(
                "comment on every branch this build left out, saying why; only a "
                "scheduled run passes this, so an ad-hoc or triage build stays silent"
            ),
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Assemble the branch and report what went into it.

        The plans and the suite are settled before anything is built, so a request that
        cannot be served fails before it has cost a build rather than after.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        :raises BranchPlanIndexUnavailable: If plans were named and the index that says
            which branch is whose could not be read.
        """
        plans = PlanFilter.over(arguments.plan)
        test_command = self._test_command(run.configuration, arguments.run_tests)
        fork = run.fork()
        run.refresh_remotes()
        stack = stack_to_build(run, fork, restack_first=arguments.restack)
        report = build_integration(
            stack=stack,
            git=run.git,
            build_branch=build_branch_name(datetime.now(timezone.utc)),
            provenance=ResolutionProvenance.read(run.provenance_path()),
            test_command=test_command,
            plans=plans,
        )
        if arguments.json:
            print(report.as_json())
        else:
            print_build(report)
        self._lift_what_the_suite_cleared(run, fork, report)
        if arguments.report_left_out:
            self._report_left_out(run, fork, report)
        return exit_code_for(report)

    @staticmethod
    def _report_left_out(
        run: IntegrationRun, fork: GitHubRepository, report: IntegrationReport
    ) -> None:
        """
        Tell every newly left-out branch's owner why this build left it out.

        Said on standard error, so the document on standard output stays one document.

        :param run: What this run has resolved.
        :param fork: The fork to label and comment on.
        :param report: What the build did.
        """
        for told in report_left_out(report, run.configuration, fork):
            print(f"{told.branch}\tleft-out\t{told.label}", file=sys.stderr)

    @staticmethod
    def _lift_what_the_suite_cleared(
        run: IntegrationRun, fork: GitHubRepository, report: IntegrationReport
    ) -> None:
        """
        Lift the block on every readmitted branch the suite passed over.

        Only a suite that ran and passed is evidence; a build that skipped it leaves the
        label where it is. Said on standard error, so the document on standard output
        stays one document.

        :param run: What this run has resolved.
        :param fork: The fork to label and comment on.
        :param report: What the build did.
        """
        if not report.tests_passed or not report.readmitted:
            return
        lifted = lift_readmitted(
            report.readmitted,
            report.build_branch,
            run.configuration,
            fork,
            BlockRecords.read(run.git, run.configuration.fork_remote),
        )
        for cleared in lifted:
            print(f"{cleared.branch}\tunblocked\t{cleared.label}", file=sys.stderr)

    @staticmethod
    def _test_command(configuration: Configuration, run_tests: bool) -> str | None:
        """
        Settle what the suite is before anything is built, so an unrunnable request
        fails before it has cost a build rather than after.

        :param configuration: The resolved configuration.
        :param run_tests: Whether a suite was asked for.
        :return: The command to run, or ``None`` when it was asked to be skipped.
        :raises TestCommandNotConfiguredError: If one was asked for and none is named.
        """
        if not run_tests:
            return None
        if not configuration.integration_test_command:
            raise TestCommandNotConfiguredError(
                ConfigurationKey.INTEGRATION_TEST_COMMAND
            )
        return configuration.integration_test_command


@dataclass(frozen=True)
class LocateFailureCommand(IntegrationCommand):
    """
    Finds which tip's arrival breaks a build that merged cleanly.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "locate-failure"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "find which tip's arrival breaks the suite"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare ``--json`` on."""
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """:param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code."""
        test_command = BuildCommand._test_command(run.configuration, run_tests=True)
        fork = run.fork()
        run.refresh_remotes()
        report = FailureLocation(
            stack=stack_to_build(run, fork, restack_first=False),
            git=run.git,
            build_branch=build_branch_name(datetime.now(timezone.utc)),
            provenance=ResolutionProvenance.read(run.provenance_path()),
            test_command=test_command,
        ).find()
        if arguments.json:
            print(report.as_json())
        else:
            print_failure_location(report)
        return report.exit_code


@dataclass(frozen=True)
class BlockBranchCommand(IntegrationCommand):
    """
    Blocks the branch that breaks another, and tells its owner what it breaks.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "block-branch"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "block the branch that breaks another, and say what it breaks"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Localise the failure, then block and report the branch that causes it.

        Localised here rather than taken as an argument, so the branch that gets blocked
        is the one the suite actually turned on rather than the one a caller believed it
        would be.

        The stack is read the way a build reads it, so the search assembles the tips the
        failing build carried - a branch carried again after its block went stale
        included - rather than the tips a label alone would allow.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        test_command = BuildCommand._test_command(run.configuration, run_tests=True)
        fork = run.fork()
        run.refresh_remotes()
        report = FailureLocation(
            stack=stack_to_build(run, fork, restack_first=False),
            git=run.git,
            build_branch=build_branch_name(datetime.now(timezone.utc)),
            provenance=ResolutionProvenance.read(run.provenance_path()),
            test_command=test_command,
        ).find()
        localised = report.integration_test_failure
        if localised is None:
            print_failure_location(report)
            return IntegrationExitCode.SUCCESS
        blocked = localised.block_the_branch_that_causes_it(
            run.configuration,
            fork,
            BlockRecords.read(run.git, run.configuration.fork_remote),
        )
        print(blocked.as_json() if arguments.json else blocked.as_line())
        return report.exit_code
