"""
Staging a collision for a resolution, and recording who wrote the one made.

A replay is only ever reported as a replay, so a resolution a machine wrote and git
reapplies unreviewed on every later build can be found again.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from integration_exit_codes import IntegrationExitCode
from integration_run import IntegrationCommand, IntegrationRun
from integration_tips import ResolutionAuthor


@dataclass(frozen=True)
class StageConflictCommand(IntegrationCommand):
    """
    Reproduces one pair's collision in a worktree of its own, for a resolution to be
    written into.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "stage-conflict"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "reproduce a pair's collision in a scratch worktree"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument("--tip", required=True, help="the branch that was skipped")
        parser.add_argument(
            "--against", required=True, help="the branch it was reported colliding with"
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Leave the collision live in a scratch worktree, and say where.

        The worktree outlives this command on purpose: what goes into the conflicted
        files is the judgement this tool does not make, so it stops here and hands back
        somewhere to make it.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        run.refresh_remotes()
        print(run.stage_conflict(arguments.against, arguments.tip).as_json())
        return IntegrationExitCode.SUCCESS


@dataclass(frozen=True)
class RecordResolutionCommand(IntegrationCommand):
    """
    Commits a staged resolution into the replay cache, under the author that wrote it.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "record-resolution"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "record a staged resolution, with who wrote it"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument("--tip", required=True, help="the branch that was skipped")
        parser.add_argument(
            "--worktree", required=True, help="the worktree the resolution was made in"
        )
        parser.add_argument(
            "--author",
            required=True,
            choices=[author.value for author in ResolutionAuthor],
            help="who wrote it, which decides how a later replay of it is reported",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """:param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code."""
        run.record_resolution(
            worktree=Path(arguments.worktree),
            tip=arguments.tip,
            author=ResolutionAuthor(arguments.author),
        )
        print(f"{arguments.tip}\trecorded-by\t{arguments.author}")
        return IntegrationExitCode.SUCCESS
