"""
Getting a build judged, and acting on what its checks said.

A pushed build collects no checks at all, so a candidate pull request is what
reaches a verdict - opened to be judged and closed unmerged either way.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stack import Configuration

from maintenance_github import ForkPullRequests
from integration_reproduction import (
    ClearedBranchReport,
    ReproductionRun,
    clear_fixed_breaks,
)
from integration_verdict import (
    Candidate,
    ChecksVerdict,
    open_candidate,
    read_checks,
)

from integration_constants import POINTER_BRANCH, ReportKey
from integration_exit_codes import IntegrationExitCode
from integration_run import IntegrationCommand, IntegrationRun

# %% getting the build judged


@dataclass(frozen=True)
class OpenCandidateCommand(IntegrationCommand):
    """
    Publishes a build and opens the pull request that gets it judged.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "open-candidate"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "publish a build and open the pull request that gets it checked"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--build", required=True, help="the build branch to have judged"
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Publish the build and open its candidate.

        The build is pushed first: a pull request naming a branch the fork does not
        carry cannot be opened, and the checks are reported against the commit rather
        than the branch, so the head is read back from what was pushed.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        head = run.git.run("rev-parse", arguments.build).strip()
        run.git.run(
            "push",
            "--force",
            run.configuration.fork_remote,
            f"{arguments.build}:{arguments.build}",
        )
        candidate = open_candidate(run.fork(), arguments.build, POINTER_BRANCH, head)
        document = {
            ReportKey.CANDIDATE: candidate.number,
            ReportKey.BUILD_BRANCH: candidate.build_branch,
            ReportKey.HEAD: candidate.head,
        }
        print(
            json.dumps(document, indent=2)
            if arguments.json
            else _candidate_line(candidate)
        )
        return IntegrationExitCode.SUCCESS


# %% acting on what the checks said


@dataclass(frozen=True)
class SettleCandidateCommand(IntegrationCommand):
    """
    Reads a candidate's checks once, and acts on what they say.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "settle-candidate"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "publish the build a candidate judged green, or report why not"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--candidate", required=True, type=int, help="the candidate's number"
        )
        parser.add_argument(
            "--build", required=True, help="the build branch it is judging"
        )
        parser.add_argument(
            "--head", required=True, help="the commit its checks are reported against"
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Act on the checks as they stand, once.

        Read once rather than waited on: a caller that wants to wait asks again, and
        keeping the waiting outside makes every invocation a decision that can be read
        on its own.

        A published build's branch is deleted, since the pointer now holds the same
        commit and a rebuild would otherwise leave one behind every time. A rejected
        one is kept: its candidate names checks somebody has to look at, and a closed
        pull request whose head is gone cannot be read.

        The candidate itself is closed only once its checks have settled. Closed
        before they have, it collects none at all - GitHub creates a pull request's
        run a moment after the request is opened, and none is created for one
        already closed.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        fork = run.fork()
        candidate = Candidate(
            number=arguments.candidate,
            build_branch=arguments.build,
            head=arguments.head,
        )
        checks = read_checks(fork, candidate.head)
        published = checks.verdict is ChecksVerdict.PASSED
        if published:
            run.git.run(
                "push",
                "--force",
                run.configuration.fork_remote,
                f"{candidate.head}:refs/heads/{POINTER_BRANCH}",
            )
        if checks.verdict.has_settled:
            fork.close_pull_request(candidate.number)
        if published:
            run.git.run(
                "push",
                "--delete",
                run.configuration.fork_remote,
                candidate.build_branch,
            )
        document = {
            ReportKey.VERDICT: str(checks.verdict),
            ReportKey.CANDIDATE: candidate.number,
            ReportKey.BUILD_BRANCH: candidate.build_branch,
            ReportKey.HEAD: candidate.head,
            ReportKey.FAILED_CHECKS: [run.name for run in checks.failed],
            ReportKey.PUBLISHED: published,
        }
        print(
            json.dumps(document, indent=2)
            if arguments.json
            else _verdict_line(candidate, checks, published)
        )
        return _verdict_exit_code(checks.verdict)


def _candidate_line(candidate: Candidate) -> str:
    """:param candidate: The candidate opened.
    :return: One tab-separated line naming it."""
    return f"{candidate.build_branch}\tcandidate\t{candidate.number}"


def _verdict_line(candidate: Candidate, checks: Any, published: bool) -> str:
    """:param candidate: The candidate read.
    :param checks: What its checks say.
    :param published: Whether the base branch was moved.
    :return: One tab-separated line."""
    detail = ",".join(run.name for run in checks.failed) or (
        POINTER_BRANCH if published else ""
    )
    return f"{candidate.build_branch}\t{checks.verdict}\t{detail}"


def _verdict_exit_code(verdict: ChecksVerdict) -> IntegrationExitCode:
    """
    Map a verdict onto the status a caller acts on.

    A verdict that has not settled is answered as still running rather than as a failure:
    a caller that threw the build away would be discarding one nothing had judged. Read
    through the same property the candidate is closed on, so the two cannot come to
    disagree about which verdicts are answers.

    :param verdict: What the checks amount to.
    :return: The process exit code.
    """
    if not verdict.has_settled:
        return IntegrationExitCode.CANDIDATE_STILL_RUNNING
    if verdict is ChecksVerdict.PASSED:
        return IntegrationExitCode.SUCCESS
    return IntegrationExitCode.CANDIDATE_FAILED


# %% lifting a block a reproduction says is fixed


@dataclass(frozen=True)
class ClearFixedBreaksCommand(IntegrationCommand):
    """
    Lifts the block on every branch whose recorded breaks now pass.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "clear-fixed-breaks"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "unblock every branch whose reproduction tests now pass"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--report",
            required=True,
            type=Path,
            help="the document the reproduction run wrote",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Lift the block on every branch the reproduction run found fixed.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        cleared = self.clear(arguments.report, run.configuration, run.fork())
        if arguments.json:
            print(self.as_json(cleared))
        else:
            for unblocked in cleared:
                print(f"{unblocked.branch}\tunblocked\t{unblocked.label}")
        return IntegrationExitCode.SUCCESS

    @staticmethod
    def clear(
        report: Path, configuration: Configuration, fork: ForkPullRequests
    ) -> tuple[ClearedBranchReport, ...]:
        """
        Read what the reproduction run found, and act on it.

        :param report: The document the reproduction run wrote.
        :param configuration: The resolved configuration, naming the label to remove.
        :param fork: The fork to label and comment on.
        :return: What was written where, one entry per branch unblocked.
        """
        return clear_fixed_breaks(
            ReproductionRun.from_json(report.read_text()), configuration, fork
        )

    @staticmethod
    def as_json(cleared: Sequence[ClearedBranchReport]) -> str:
        """:param cleared: The branches unblocked.
        :return: Them as one machine-readable document."""
        return json.dumps(
            {
                ReportKey.CLEARED: [
                    {
                        ReportKey.BRANCH: unblocked.branch,
                        ReportKey.PULL_REQUEST_NUMBER: unblocked.pull_request_number,
                        ReportKey.LABEL: unblocked.label,
                        ReportKey.COMMENT: unblocked.comment,
                    }
                    for unblocked in cleared
                ]
            },
            indent=2,
        )
