"""
Saying which pair of branches a candidate's red matrix job is about.

Read once rather than waited on, the same way a candidate is settled: what the search
has established lives in its document rather than in the process, so every call is a
decision that can be read on its own.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from maintenance_github import GitHubRepository
from workflow_document import WorkflowFile

from integration_constants import POINTER_BRANCH, ReportKey
from integration_exit_codes import IntegrationExitCode
from integration_block_record import BlockRecords
from integration_failure import BlockedBranchReport, IntegrationTestFailure
from integration_localisation import (
    Localisation,
    LocalisationKey,
    LocalisationStage,
    LocalisationStep,
)
from integration_probe_assembly import ProbeAssembly
from integration_probes import dispatch, library_a_candidate_failed_on
from integration_run import IntegrationCommand, IntegrationRun
from integration_tips import ResolutionProvenance
from integration_verdict import read_checks


@dataclass(frozen=True)
class LocateCandidateFailureCommand(IntegrationCommand):
    """
    Finds which tip's arrival turned the library a candidate went red on.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "locate-candidate-failure"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "find which tip turned the library a candidate's checks failed on"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--head", required=True, help="the commit the candidate's checks are on"
        )
        parser.add_argument(
            "--state",
            required=True,
            type=Path,
            help="where the search in flight is kept between calls",
        )
        parser.add_argument(
            "--dispatch-on",
            default=POINTER_BRANCH,
            help=(
                "the reference carrying this pipeline, which is what a dispatch runs the "
                "probe workflow from"
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
        Take the search one step, and say what it wants next.

        Read once rather than waited on, the same way a candidate is settled: the state
        lives in the document rather than in the process, so a caller that wants to wait
        asks again and every invocation is a decision that can be read on its own.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        fork = run.fork()
        run.refresh_remotes()
        assembly = ProbeAssembly(
            stack=BlockRecords.read(run.git, run.configuration.fork_remote).annotate(
                run.stack(fork)
            ),
            git=run.git,
            provenance=ResolutionProvenance.read(run.provenance_path()),
            named_at=datetime.now(timezone.utc),
        )
        if not arguments.state.exists():
            return self._start(run, fork, assembly, arguments)
        localisation = Localisation.from_json(
            json.loads(arguments.state.read_text())
        ).answered_by(fork.workflow_runs(str(WorkflowFile.INTEGRATION_PROBE)))
        return self._continue(run, fork, assembly, localisation, arguments)

    def _start(
        self,
        run: IntegrationRun,
        fork: GitHubRepository,
        assembly: ProbeAssembly,
        arguments: argparse.Namespace,
    ) -> IntegrationExitCode:
        """
        Open the prefix round, or say the candidate's red is not this search's.

        :param run: What this run has resolved.
        :param fork: The fork to read the candidate's checks from and dispatch on.
        :param assembly: The assembly that publishes the trees.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        library = library_a_candidate_failed_on(read_checks(fork, arguments.head))
        if library is None:
            self._print(arguments, None, IntegrationExitCode.NO_LIBRARY_CHECK_FAILED)
            return IntegrationExitCode.NO_LIBRARY_CHECK_FAILED
        localisation = Localisation(
            library=library,
            stage=LocalisationStage.PREFIXES,
            probes=assembly.prefixes(),
        )
        dispatch(fork, arguments.dispatch_on, library, localisation.probes)
        return self._wait(arguments, localisation)

    def _continue(
        self,
        run: IntegrationRun,
        fork: GitHubRepository,
        assembly: ProbeAssembly,
        localisation: Localisation,
        arguments: argparse.Namespace,
    ) -> IntegrationExitCode:
        """
        Act on what the round in flight now says.

        :param run: What this run has resolved.
        :param fork: The fork to dispatch on and report to.
        :param assembly: The assembly that publishes and takes down the trees.
        :param localisation: The round, with every probe's run read.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        match localisation.next_step:
            case LocalisationStep.WAIT:
                return self._wait(arguments, localisation)
            case LocalisationStep.NARROW:
                return self._narrow(fork, assembly, localisation, arguments)
            case LocalisationStep.CONCLUDE:
                return self._conclude(run, fork, assembly, localisation, arguments)

    def _narrow(
        self,
        fork: GitHubRepository,
        assembly: ProbeAssembly,
        localisation: Localisation,
        arguments: argparse.Namespace,
    ) -> IntegrationExitCode:
        """
        Open the round that asks which earlier tip the suspect fails against alone.

        :param fork: The fork to dispatch on.
        :param assembly: The assembly that takes the answered round down and publishes
            the next.
        :param localisation: The prefix round, which has localised a suspect.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        suspect = localisation.localised_suspect
        assembly.take_down(localisation.probes)
        narrowing = Localisation(
            library=localisation.library,
            stage=LocalisationStage.NARROWING,
            probes=assembly.pairings(suspect.branch, suspect.already_included),
            suspect=suspect,
        )
        dispatch(fork, arguments.dispatch_on, narrowing.library, narrowing.probes)
        return self._wait(arguments, narrowing)

    def _conclude(
        self,
        run: IntegrationRun,
        fork: GitHubRepository,
        assembly: ProbeAssembly,
        localisation: Localisation,
        arguments: argparse.Namespace,
    ) -> IntegrationExitCode:
        """
        Report what the search found, and block the branch when it found one.

        The finding is an :class:`IntegrationTestFailure` like any other, so a failure
        localised through CI is reported to its branch's owner in the same words as one
        localised locally, and held out of promotion by the same label.

        :param run: What this run has resolved.
        :param fork: The fork to report to.
        :param assembly: The assembly whose trees are finished with.
        :param localisation: The concluded search.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        assembly.take_down(localisation.probes)
        arguments.state.unlink(missing_ok=True)
        suspect = localisation.localised_suspect
        if suspect is None:
            self._print(arguments, localisation, IntegrationExitCode.SUCCESS)
            return IntegrationExitCode.SUCCESS
        by_name = {branch.name: branch for branch in assembly.stack.branches}
        failure = IntegrationTestFailure.measured(
            git=run.git,
            configuration=run.configuration,
            culprit=by_name[suspect.branch],
            already_included=suspect.already_included,
            breaks_against=localisation.breaks_against,
            by_name=by_name,
        )
        blocked = failure.block_the_branch_that_causes_it(
            run.configuration,
            fork,
            BlockRecords.read(run.git, run.configuration.fork_remote),
        )
        self._print(arguments, localisation, IntegrationExitCode.TESTS_FAILED, blocked)
        return IntegrationExitCode.TESTS_FAILED

    def _wait(
        self, arguments: argparse.Namespace, localisation: Localisation
    ) -> IntegrationExitCode:
        """
        Keep the search for the call that reads it next.

        :param arguments: The parsed command line.
        :param localisation: The round in flight.
        :return: The process exit code.
        """
        arguments.state.write_text(json.dumps(localisation.to_json(), indent=2))
        self._print(arguments, localisation, IntegrationExitCode.PROBES_STILL_RUNNING)
        return IntegrationExitCode.PROBES_STILL_RUNNING

    @staticmethod
    def _print(
        arguments: argparse.Namespace,
        localisation: Localisation | None,
        status: IntegrationExitCode,
        blocked: BlockedBranchReport | None = None,
    ) -> None:
        """:param arguments: The parsed command line.
        :param localisation: The search so far, where there is one.
        :param status: What this call leaves its caller with.
        :param blocked: What blocking the branch wrote, where anything was."""
        document = {
            ReportKey.STATUS: status.name_for_a_caller,
            ReportKey.EXIT_CODE: int(status),
            **({} if localisation is None else localisation.to_json()),
            ReportKey.BREAKS_AGAINST: (
                None if localisation is None else localisation.breaks_against
            ),
        }
        if not arguments.json:
            print(f"{status.name_for_a_caller}\t{document.get(LocalisationKey.STAGE)}")
            return
        if blocked is not None:
            document[ReportKey.BLOCKED] = blocked.blocked
        print(json.dumps(document, indent=2))
