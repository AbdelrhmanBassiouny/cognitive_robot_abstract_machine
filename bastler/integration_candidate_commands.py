"""
Getting a build judged, and acting on what its checks said.

A pushed build collects no checks at all, so a candidate pull request is what
reaches a verdict - opened to be judged and closed unmerged either way.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bastler.stack import Configuration

from bastler.maintenance_board import PullRequestField
from bastler.maintenance_github import ForkPullRequests
from bastler.integration_reproduction import (
    ClearingReport,
    ReproductionRun,
    clear_fixed_breaks,
)
from bastler.integration_carried_pipeline import CarriedPipeline, pipeline_carried_by
from bastler.integration_verdict import (
    Candidate,
    ChecksVerdict,
    VerdictReport,
    candidate_for_everything_in_flight,
    open_candidate,
    read_checks,
)

from bastler.integration_constants import BUILD_BRANCH_PATTERN, POINTER_BRANCH, ReportKey
from bastler.integration_exit_codes import IntegrationExitCode
from bastler.integration_pass_record import PassedChecks, RecordedSubject
from bastler.integration_run import IntegrationCommand, IntegrationRun


def publish(run: IntegrationRun, build_branch: str, head: str) -> CarriedPipeline:
    """
    Move the branch a developer works from onto a build, and drop the build's own
    branch.

    The branch goes because the pointer now holds the same commit, and a rebuild that
    left one behind every time would accumulate one per run.

    A build carrying no rebuild of its own is refused instead. The branch this moves is
    the fork's default branch, and a schedule registers from the default branch, so
    publishing such a build would take the schedule down with it and leave nothing able
    to publish a later one. The check is here rather than at each caller because there
    is no publication it does not apply to.

    :param run: What this run has resolved.
    :param build_branch: The build being published.
    :param head: The commit to move the pointer to.
    :return: What of the pipeline the build carries, which is why it was published or
        was not.
    """
    carried = pipeline_carried_by(run.git, head)
    if not carried.can_rebuild:
        return carried
    remote = run.configuration.fork_remote
    run.git.run("push", "--force", remote, f"{head}:refs/heads/{POINTER_BRANCH}")
    run.git.run("push", "--delete", remote, build_branch)
    return carried


def tree_of(run: IntegrationRun, reference: str) -> str:
    """
    :param run: What this run has resolved.
    :param reference: A commit or branch.
    :return: The tree it holds, which is what two assemblies of the same branches over
        the same base share where their commits do not.
    """
    return run.git.run("rev-parse", f"{reference}^{{tree}}").strip()


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
            "--plan",
            action="append",
            default=[],
            metavar="PLAN",
            help=(
                "the plans this build was asked to carry; a candidate whose title names "
                "any is not the one a later run settles, so nothing ever publishes it"
            ),
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

        Every candidate is opened against the base its build was assembled over, which
        is the one base a build always merges with. Opened against the branch a build
        publishes to - itself an older build of the same branches - the two conflict,
        GitHub computes no merge reference, and the ``pull_request`` run that would
        check that reference out is never created, so no verdict ever arrives.

        What tells the candidate a later run settles from one carrying named plans is
        its title, since the base can no longer.

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
        candidate = open_candidate(
            run.fork(),
            arguments.build,
            run.configuration.upstream_base,
            head,
            tuple(arguments.plan),
        )
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


@dataclass(frozen=True)
class FindCandidateCommand(IntegrationCommand):
    """
    Reports the build currently being judged, if one is.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "find-candidate"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "report the candidate a build is being judged as, if one is open"

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
        Report what is being judged.

        Read off the fork rather than remembered, because the run that opened the
        candidate is over by the time anything settles it: a candidate's first check
        arrives long after it is opened - see
        :class:`~integration_verdict.CandidateCheckTiming` - so the run that opens one
        cannot also reach its verdict.

        Only the candidate judging everything in flight is reported: one carrying named
        plans answers a narrower question, and settling it would publish one plan's
        branches over everything else.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        candidate = candidate_for_everything_in_flight(run.fork())
        if candidate is None:
            print(json.dumps({}, indent=2) if arguments.json else "no candidate")
            return IntegrationExitCode.NO_CANDIDATE_OPEN
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


@dataclass(frozen=True)
class CloseCandidateCommand(IntegrationCommand):
    """
    Closes a candidate no run can judge, so a rebuild can replace it.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "close-candidate"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "close a candidate nothing is ever going to report a check against"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--candidate", required=True, type=int, help="the candidate's number"
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
        Close the candidate without merging it.

        Told apart from the settling, which closes a candidate whose checks have
        answered: this one closes a candidate whose checks never will, so that the
        rebuild has something to replace rather than something to stop on. The build's
        own branch is left to the next rebuild's take-down, which drops what no open
        pull request refers to any more.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        run.fork().close_pull_request(arguments.candidate)
        document = {ReportKey.CANDIDATE: arguments.candidate}
        print(
            json.dumps(document, indent=2)
            if arguments.json
            else f"{arguments.candidate}\tclosed"
        )
        return IntegrationExitCode.SUCCESS


@dataclass(frozen=True)
class PublishRecordedPassCommand(IntegrationCommand):
    """
    Publishes a build whose tree this fork has already seen pass.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "publish-recorded-pass"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "publish a build whose tree has already been seen to pass"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--build", required=True, help="the build branch to publish"
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
        Publish the build if its tree is one that has already passed.

        A rebuild assembles the same branches over the same base four times a day, and
        each assembly is a new commit holding the same tree - so without this every
        unchanged build is checked again, at the cost
        :class:`~integration_verdict.CandidateCheckTiming` records.

        The build is pushed first, because a fork that does not carry the commit cannot
        be asked to move a branch onto it. It is the branch the next take-down drops if
        publishing is then refused.

        This is what publishes on the ordinary day, when nothing has moved, so it is
        refused on the same rule the judged path is: a build carrying no rebuild of its
        own is one the pointer is not moved onto.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        remote = run.configuration.fork_remote
        head = run.git.run("rev-parse", arguments.build).strip()
        tree = tree_of(run, arguments.build)
        if not PassedChecks.read(run.git, remote).holds(
            RecordedSubject.BUILD_TREE, tree
        ):
            print(json.dumps({}, indent=2) if arguments.json else "not recorded")
            return IntegrationExitCode.NO_RECORDED_PASS
        run.git.run("push", "--force", remote, f"{arguments.build}:{arguments.build}")
        carried = publish(run, arguments.build, head)
        document = {
            ReportKey.BUILD_BRANCH: arguments.build,
            ReportKey.HEAD: head,
            ReportKey.PUBLISHED: carried.can_rebuild,
            ReportKey.MISSING_PIPELINE: list(carried.missing),
        }
        print(
            json.dumps(document, indent=2)
            if arguments.json
            else _publication_line(arguments.build, carried)
        )
        if not carried.can_rebuild:
            return IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED
        return IntegrationExitCode.SUCCESS


@dataclass(frozen=True)
class TakeDownUnreferencedBuildsCommand(IntegrationCommand):
    """
    Deletes the build branches nothing is judging any more.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "take-down-unreferenced-builds"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "delete the build branches no open pull request refers to"

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
        Take down every published build no open pull request refers to.

        A build branch exists to be judged, and :func:`publish` drops the one build that
        reaches a verdict it can act on - so every other outcome leaves one behind, and
        four rebuilds a day leave four. What keeps a branch is a pull request still open
        against it: the candidate judging it, or a filtered build somebody asked for and
        is working from.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        remote = run.configuration.fork_remote
        judged = {
            PullRequestField.HEAD.read(record)
            for record in run.fork().open_pull_requests()
        }
        taken_down = tuple(
            branch
            for branch in run.git.remote_branch_names(remote, BUILD_BRANCH_PATTERN)
            if branch not in judged
        )
        for branch in taken_down:
            run.git.delete_branch(remote, branch).raise_if_failed()
        document = {ReportKey.TAKEN_DOWN: list(taken_down)}
        print(
            json.dumps(document, indent=2)
            if arguments.json
            else "\n".join(taken_down) or "nothing to take down"
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

        A build that passed has its *tree* recorded, so a later assembly of the same
        branches over the same base - which produces a new commit every time and the same
        tree every time - is published without spending a matrix on it again.

        Passing is not on its own enough to be published: a build carrying no rebuild of
        its own is refused, and says which of the pipeline it is missing.

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
        passed = checks.verdict is ChecksVerdict.PASSED
        if checks.verdict.has_settled:
            fork.close_pull_request(candidate.number)
        carried = self._publish_what_passed(run, candidate) if passed else None
        report = VerdictReport(
            candidate=candidate,
            checks=checks,
            published=carried is not None and carried.can_rebuild,
            missing_pipeline=carried.missing if carried else (),
        )
        print(
            json.dumps(report.to_json(), indent=2)
            if arguments.json
            else _verdict_line(candidate, checks, report.published)
        )
        return _verdict_exit_code(checks.verdict, report.published)

    @staticmethod
    def _publish_what_passed(
        run: IntegrationRun, candidate: Candidate
    ) -> CarriedPipeline:
        """
        Remember that this tree passed, and move the pointer onto it.

        The pass is recorded whether or not the pointer moves: what passed is a fact
        about the tree, and a build refused for carrying no rebuild is refused again on
        the same rule rather than re-judged.

        :param run: What this run has resolved.
        :param candidate: The build that passed.
        :return: What of the pipeline it carries.
        """
        remote = run.configuration.fork_remote
        PassedChecks.read(run.git, remote).record(
            run.git,
            remote,
            RecordedSubject.BUILD_TREE,
            tree_of(run, candidate.head),
            candidate.head,
        )
        return publish(run, candidate.build_branch, candidate.head)


def _candidate_line(candidate: Candidate) -> str:
    """:param candidate: The candidate opened.
    :return: One tab-separated line naming it."""
    return f"{candidate.build_branch}\tcandidate\t{candidate.number}"


def _publication_line(build_branch: str, carried: CarriedPipeline) -> str:
    """:param build_branch: The build that was to be published.
    :param carried: What of the pipeline it carries.
    :return: One tab-separated line, naming what is missing where nothing moved."""
    if carried.can_rebuild:
        return f"{build_branch}\tpublished\t{POINTER_BRANCH}"
    return f"{build_branch}\tnot published\t{','.join(carried.missing)}"


def _verdict_line(candidate: Candidate, checks: Any, published: bool) -> str:
    """:param candidate: The candidate read.
    :param checks: What its checks say.
    :param published: Whether the base branch was moved.
    :return: One tab-separated line."""
    detail = ",".join(run.name for run in checks.failed) or (
        POINTER_BRANCH if published else ""
    )
    return f"{candidate.build_branch}\t{checks.verdict}\t{detail}"


def _verdict_exit_code(verdict: ChecksVerdict, published: bool) -> IntegrationExitCode:
    """
    Map what was read onto the status a caller acts on.

    A verdict that has not settled is answered as still running rather than as a failure:
    a caller that threw the build away would be discarding one nothing had judged. Read
    through the same property the candidate is closed on, so the two cannot come to
    disagree about which verdicts are answers.

    A build that passed and was not published gets its own status rather than the success
    of the verdict it earned, since what a rebuild does next turns on whether the pointer
    moved. Read off the same field the document carries, so a run cannot exit success
    over a report saying it published nothing.

    :param verdict: What the checks amount to.
    :param published: Whether the branch a developer works from was moved onto the build.
    :return: The process exit code.
    """
    if not verdict.has_settled:
        return IntegrationExitCode.CANDIDATE_STILL_RUNNING
    if verdict is not ChecksVerdict.PASSED:
        return IntegrationExitCode.CANDIDATE_FAILED
    if published:
        return IntegrationExitCode.SUCCESS
    return IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED


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
        clearing = self.clear(arguments.report, run.configuration, run.fork())
        if arguments.json:
            print(clearing.as_json())
        else:
            print("\n".join(clearing.as_lines()))
        return IntegrationExitCode.SUCCESS

    @staticmethod
    def clear(
        report: Path, configuration: Configuration, fork: ForkPullRequests
    ) -> ClearingReport:
        """
        Read what the reproduction run found, and act on it.

        Answered with the run as well as the lifting, since a run that lifted nothing
        has two different things it can mean.

        :param report: The document the reproduction run wrote.
        :param configuration: The resolved configuration, naming the label to remove.
        :param fork: The fork to label and comment on.
        :return: What the run established, and what was written where.
        """
        reproduced = ReproductionRun.from_json(report.read_text())
        return ClearingReport(
            run=reproduced,
            cleared=clear_fixed_breaks(reproduced, configuration, fork),
        )
