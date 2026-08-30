"""
One whole rebuild: prepare the checkout, settle what is already being judged, assemble.

The preparation is what only this knows about the runner it is on - a fresh checkout
has no upstream remote and no identity to commit under, and a rebuild makes merge
commits.
"""

from __future__ import annotations

import argparse
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

from git_commands import GitSetting

from integration_constants import (
    ACTOR_EMAIL_SUFFIX,
    ACTOR_VARIABLE,
    LOCALISATION_STATE_FILE,
    POINTER_BRANCH,
)
from integration_exit_codes import IntegrationExitCode
from integration_pipeline import RefreshPipeline
from integration_run import IntegrationCommand, IntegrationRun


@dataclass(frozen=True)
class RefreshCommand(IntegrationCommand):
    """
    Performs a whole rebuild: prepare, settle whatever an earlier run left being judged,
    then assemble the next build and open the candidate that judges it.
    """

    @property
    def invoked_as(self) -> str:
        """
        The name it is invoked by on the command line.
        """
        return "refresh"

    @property
    def description(self) -> str:
        """
        What it does, as ``--help`` puts it.
        """
        return "settle the build being judged, then assemble and open the next"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--dispatch-on",
            default=POINTER_BRANCH,
            help=(
                "the reference carrying this pipeline, which is what a dispatch runs the "
                "probe workflow from"
            ),
        )
        parser.add_argument(
            "--state",
            type=Path,
            default=Path(tempfile.gettempdir()) / LOCALISATION_STATE_FILE,
            help="where a localisation keeps what it has established between calls",
        )
        parser.add_argument(
            "--plan",
            action="append",
            default=[],
            metavar="PLAN",
            help=(
                "rebuild carrying only the tips belonging to this plan, to find out "
                "whether it holds together on its own; such a rebuild settles nothing "
                "and publishes nothing"
            ),
        )
        parser.add_argument(
            "--actor",
            default=os.environ.get(ACTOR_VARIABLE, ""),
            help="who the rebuild's own commits are authored as",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Prepare the checkout, then run the rebuild over it.

        The preparation is what only this command knows about the runner it is on: a
        fresh checkout has no upstream remote and no identity to commit under, and the
        rebuild makes merge commits.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        self._prepare(run, arguments.actor)
        return RefreshPipeline(
            dispatch_on=arguments.dispatch_on,
            state_document=arguments.state,
            plans=tuple(arguments.plan),
        ).run()

    @staticmethod
    def _prepare(run: IntegrationRun, actor: str) -> None:
        """
        Give the checkout what a rebuild needs and a fresh clone has not got.

        :param run: What this run has resolved.
        :param actor: Who the rebuild's own commits are authored as.
        """
        setup = run.configuration.upstream_setup_command
        if setup is not None:
            # Built by this repository's own configuration, so it is read as the argument
            # list it is rather than handed to a shell to interpret.
            run.git.run(*shlex.split(setup)[1:])
        if actor:
            run.git.configure(GitSetting(key="user.name", value=actor))
            run.git.configure(
                GitSetting(key="user.email", value=f"{actor}{ACTOR_EMAIL_SUFFIX}")
            )
