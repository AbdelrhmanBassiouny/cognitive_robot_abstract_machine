"""
What one run has resolved, and what a command that uses it is.

Held apart from the commands themselves so each family of them can import this without
the registry that finds them importing each family back.
"""

from __future__ import annotations

import json
import argparse
import tempfile
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path

from bastler.command_line import Command
from bastler.stack import (
    Configuration,
    Stack,
    build_stack,
    resolve_ref,
)

from bastler.maintenance_board import BoardExport
from bastler.maintenance_git_commands import (
    BranchAncestry,
    MaintenanceGitCommandRunner,
)
from bastler.maintenance_github import GitHubRepository

from bastler.integration_constants import ReportKey, PROVENANCE_FILENAME, RERERE_SETTINGS
from bastler.integration_exit_codes import IntegrationExitCode
from bastler.integration_tips import ResolutionAuthor, ResolutionProvenance


@dataclass(frozen=True)
class StagedConflict:
    """
    Where one pair's collision was reproduced, and which paths it is on.

    Named in the same words a build's own report names a skipped tip and what it
    collided with, since that is the pair a staged collision reproduces.
    """

    worktree: Path
    """
    The checkout the collision is live in, which a resolution is written into.
    """

    branch: str
    """
    The tip that was skipped.
    """

    attributed_to: str
    """
    The branch it was reported colliding with.
    """

    conflicting_paths: tuple[str, ...]
    """
    The paths left unmerged, which are the files to resolve.
    """

    def as_json(self) -> str:
        """:return: The staged collision as one machine-readable document."""
        return json.dumps(
            {
                ReportKey.WORKTREE: str(self.worktree),
                ReportKey.BRANCH: self.branch,
                ReportKey.ATTRIBUTED_TO: self.attributed_to,
                ReportKey.CONFLICTING_PATHS: list(self.conflicting_paths),
            },
            indent=2,
        )


@dataclass(frozen=True)
class IntegrationRun:
    """
    What one run has resolved so far, built lazily as a command asks for it.

    The credential is resolved before anything is fetched, so a checkout without one is
    sent after a token rather than after whichever network call happened to come first -
    the fork's open pull requests are what a build is derived from, and no amount of
    fetching substitutes for them.
    """

    configuration: Configuration
    """
    The resolved configuration naming both repositories and the base.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner every git command goes through.
    """

    def fork(self) -> GitHubRepository:
        """:return: The fork, as this run's credential can read it."""
        return GitHubRepository.from_environment(self.configuration.fork_repository)

    def stack(self, fork: GitHubRepository) -> Stack:
        """
        Derive the stack from the fork's open pull requests, read fresh.

        Read rather than loaded from ``board.json``: a build is only as good as its idea
        of what is in flight, and a snapshot left behind by an earlier pass is worse
        than no snapshot at all. What is in flight is what the export carries, which is
        every open pull request except a candidate.

        :param fork: The fork to read the open pull requests from.
        :return: The derived stack.
        """
        export = BoardExport.from_api_records(fork.open_pull_requests())
        ancestry = BranchAncestry(self.configuration, self.git)
        upstream = (
            f"{self.configuration.upstream_remote}/{self.configuration.upstream_base}"
        )
        return build_stack(
            self.configuration,
            list(export.pull_requests),
            lambda name: ancestry.is_ancestor(name, upstream),
        )

    def refresh_remotes(self) -> None:
        """
        Fetch both remotes, so a build merges what is published rather than what this
        checkout last happened to see.
        """
        self.git.fetch(self.configuration.fork_remote)
        self.git.fetch(self.configuration.upstream_remote)

    def provenance_path(self) -> Path:
        """:return: Where this repository records who wrote each cached resolution -
        beside the cache itself, which is shared by every worktree."""
        return self.git.common_directory() / PROVENANCE_FILENAME

    def replaying(self, working_directory: Path) -> MaintenanceGitCommandRunner:
        """:param working_directory: The checkout to run in.
        :return: A runner with resolution replay turned on for its commands alone."""
        return MaintenanceGitCommandRunner(
            working_directory=working_directory,
            configuration_overrides=RERERE_SETTINGS,
        )

    def stage_conflict(self, already_included: str, tip: str) -> StagedConflict:
        """
        Reproduce one pair's collision in a worktree of its own.

        The merge is left conflicted rather than abandoned: recording a resolution means
        resolving *this* conflict, and rerere keys its cache on the conflict's own shape.

        :param already_included: The branch that reached the build first.
        :param tip: The branch that was skipped against it.
        :return: Where the collision is live, and which paths it is on.
        :raises GitCommandFailed: If the worktree cannot be added.
        """
        worktree = Path(tempfile.mkdtemp(prefix="stack-resolve-"))
        self.git.run(
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            resolve_ref(self.configuration, already_included),
        )
        resolving = self.replaying(worktree)
        resolving.merge(resolve_ref(self.configuration, tip))
        return StagedConflict(
            worktree=worktree,
            branch=tip,
            attributed_to=already_included,
            conflicting_paths=tuple(resolving.unmerged_paths()),
        )

    def record_resolution(
        self, worktree: Path, tip: str, author: ResolutionAuthor
    ) -> Path:
        """
        Commit a staged resolution, so a later build replays it, and say who wrote it.

        :param worktree: The worktree the resolution was made in.
        :param tip: The branch that was skipped.
        :param author: Who wrote the resolution.
        :return: The provenance manifest that now claims it.
        :raises GitCommandFailed: If the resolution cannot be committed.
        """
        resolving = self.replaying(worktree)
        resolving.run("add", "--all")
        resolving.conclude_merge().raise_if_failed()
        self.git.attempt("worktree", "remove", "--force", str(worktree))
        path = self.provenance_path()
        return ResolutionProvenance.read(path).claiming(tip, author).write(path)


@dataclass(frozen=True)
class IntegrationCommand(Command):
    """
    One command this builder answers.

    Adds to the shared :class:`command_line.Command` only what is this builder's own:
    what a command is handed, and what it answers with.
    """

    @abstractmethod
    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """
        Perform the command.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
