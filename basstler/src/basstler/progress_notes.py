"""
Removes the progress notes of pull requests whose work is over.

A branch's progress notes are read only while its pull request is open. Once every pull
request from that branch has merged or closed, or the branch itself is gone, the notes are
never read again, so they are deleted rather than left to accumulate on the personal-notes
branch.

Usage:
    python3 -m basstler.progress_notes prune --directory <pr-progress-directory> \\
        --remote <name> --keep <branch>

Pruning is never fatal to a save: without a GitHub credential or a readable remote it
says why and removes nothing.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.maintenance_board import PullRequestRecord
from basstler.maintenance_git_commands import GitCommandRunner
from basstler.maintenance_github import GitHubRepository, ListedPullRequestState
from basstler.repository import Repository
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""


class PullRequestField(StrEnum):
    """
    The keys of a GitHub pull request payload this module reads.
    """

    HEAD = "head"
    """
    The pull request's source branch.
    """

    REFERENCE = "ref"
    """
    A branch's name, under :attr:`HEAD`.
    """

    HEAD_REPOSITORY = "repo"
    """
    The repository the source branch lives in, under :attr:`HEAD`.
    """

    FULL_NAME = "full_name"
    """
    A repository's ``owner/name``, under :attr:`HEAD_REPOSITORY`.
    """

    STATE = "state"
    """
    ``open`` or ``closed``; a merged pull request is closed.
    """


class ProgressNotesFile(StrEnum):
    """
    How a branch's progress notes are named within their directory.
    """

    SUFFIX = ".md"
    """
    The extension every progress-notes file carries.
    """


@dataclass(frozen=True)
class BranchPullRequests:
    """
    Which of a repository's own branches have an open pull request, and which have only
    finished ones.
    """

    open_branches: frozenset[str]
    """
    Branches with at least one open pull request.
    """

    finished_branches: frozenset[str]
    """
    Branches every pull request of which has merged or closed.
    """

    @classmethod
    def from_pull_requests(
        cls, pull_requests: list[PullRequestRecord], repository: Repository
    ) -> BranchPullRequests:
        """
        :param pull_requests: Every pull request of the repository, in any state.
        :param repository: The repository whose own branches count; a pull request from
            a fork's branch of the same name says nothing about this one.
        :return: The branches, grouped by whether any of their pull requests is open.
        """
        open_branches: set[str] = set()
        branches_with_pull_requests: set[str] = set()
        for pull_request in pull_requests:
            head = pull_request[PullRequestField.HEAD]
            head_repository = head[PullRequestField.HEAD_REPOSITORY]
            if (
                head_repository is None
                or head_repository[PullRequestField.FULL_NAME] != repository.full_name
            ):
                continue
            branch = head[PullRequestField.REFERENCE]
            branches_with_pull_requests.add(branch)
            if pull_request[PullRequestField.STATE] == ListedPullRequestState.OPEN:
                open_branches.add(branch)
        return cls(
            open_branches=frozenset(open_branches),
            finished_branches=frozenset(branches_with_pull_requests - open_branches),
        )


@dataclass(frozen=True)
class ProgressNotesDirectory:
    """
    The directory holding one progress-notes file per branch, named after the branch.
    """

    path: Path
    """
    The directory itself.
    """

    def branches(self) -> list[str]:
        """
        :return: The branch every progress-notes file in the directory belongs to.
        """
        return sorted(
            str(file.relative_to(self.path))[: -len(ProgressNotesFile.SUFFIX)]
            for file in self.path.rglob(f"*{ProgressNotesFile.SUFFIX}")
        )

    def remove_finished(
        self,
        pull_requests: BranchPullRequests,
        remote_branches: frozenset[str],
        kept_branch: str,
    ) -> list[str]:
        """
        Delete the progress notes no session will read again: those of a branch that is
        gone from the remote, or whose pull requests have all merged or closed.

        :param pull_requests: The repository's branches, grouped by pull request state.
        :param remote_branches: Every branch the remote still has.
        :param kept_branch: A branch whose notes stay whatever its state, because they are
            being saved.
        :raises EmptyRemoteBranchListError: If *remote_branches* is empty, which would
            read every branch as gone.
        :return: The branches whose notes were deleted.
        """
        if not remote_branches:
            raise EmptyRemoteBranchListError(directory=self.path)
        removed = [
            branch
            for branch in self.branches()
            if branch != kept_branch
            and (
                branch not in remote_branches
                or branch in pull_requests.finished_branches
            )
        ]
        for branch in removed:
            (self.path / f"{branch}{ProgressNotesFile.SUFFIX}").unlink()
        return removed


@dataclass
class EmptyRemoteBranchListError(ValueError):
    """
    Raised when pruning is asked to judge branches against a remote that lists none.
    """

    directory: Path
    """
    The progress-notes directory that was to be pruned.
    """

    def __str__(self) -> str:
        """
        :return: Why nothing was pruned.
        """
        return (
            f"no remote branches were listed, so every note in {self.directory} would "
            "read as belonging to a deleted branch; nothing was pruned"
        )


# %% pruning against the remote


class PruningSkipped(StrEnum):
    """
    Why a prune removed nothing without judging any branch.
    """

    NO_CREDENTIAL = "no GH_TOKEN or GITHUB_TOKEN is set"
    """
    The pull requests cannot be listed.
    """

    REMOTE_UNREADABLE = "the remote's URL or branches could not be read"
    """
    Which branches still exist is unknown.
    """


@dataclass(frozen=True)
class ProgressNotesPruning:
    """
    One prune of a progress-notes directory against a checkout's remote.
    """

    directory: ProgressNotesDirectory
    """
    The notes to prune.
    """

    git: GitCommandRunner
    """
    The checkout whose remote the branches live on.
    """

    remote: str
    """
    The remote the branches and pull requests belong to.
    """

    kept_branch: str
    """
    The branch whose notes are being saved.
    """

    def run(self) -> list[str] | PruningSkipped:
        """
        :return: The branches whose notes were deleted, or why nothing was judged.
        """
        token = GitHubRepository.environment_token()
        if token is None:
            return PruningSkipped.NO_CREDENTIAL
        url = self.git.attempt("remote", "get-url", self.remote)
        heads = self.git.attempt("ls-remote", "--heads", self.remote)
        if not (
            url.succeeded
            and Repository.names_a_repository(url.output)
            and heads.succeeded
            and heads.output
        ):
            return PruningSkipped.REMOTE_UNREADABLE
        repository = Repository.from_remote_url(url.output)
        pull_requests = BranchPullRequests.from_pull_requests(
            GitHubRepository(repository, token).pull_requests(
                ListedPullRequestState.ALL
            ),
            repository,
        )
        remote_branches = frozenset(
            line.split("refs/heads/", 1)[1] for line in heads.output.splitlines()
        )
        return self.directory.remove_finished(
            pull_requests, remote_branches, self.kept_branch
        )


# %% command line


class ProgressNotesCommand(StrEnum):
    """
    The subcommands this module's command line runs.
    """

    PRUNE = "prune"
    """
    Delete the progress notes of finished pull requests.
    """


class ProgressNotesOption(StrEnum):
    """
    The options this module's command line takes.
    """

    DIRECTORY = "--directory"
    """
    The progress-notes directory to prune.
    """

    REMOTE = "--remote"
    """
    The remote the branches and pull requests belong to.
    """

    KEEP = "--keep"
    """
    The branch whose notes are being saved, and so are never removed.
    """


class ProgressNotesArgument(StrEnum):
    """
    The names this module's command line parses its subcommand and arguments under.
    """

    SUBCOMMAND = "subcommand"
    """
    The subcommand to run, a :class:`ProgressNotesCommand`.
    """

    DIRECTORY = "directory"
    """
    The value of :attr:`ProgressNotesOption.DIRECTORY`.
    """

    REMOTE = "remote"
    """
    The value of :attr:`ProgressNotesOption.REMOTE`.
    """

    KEEP = "keep"
    """
    The value of :attr:`ProgressNotesOption.KEEP`.
    """


def main() -> int:
    """
    Prune a progress-notes directory and report which branches' notes were removed,
    or why none were judged.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subcommands = parser.add_subparsers(
        dest=ProgressNotesArgument.SUBCOMMAND, required=True
    )
    prune = subcommands.add_parser(
        ProgressNotesCommand.PRUNE,
        help="Delete the progress notes of finished pull requests",
    )
    prune.add_argument(
        ProgressNotesOption.DIRECTORY,
        dest=ProgressNotesArgument.DIRECTORY,
        required=True,
        type=Path,
    )
    prune.add_argument(
        ProgressNotesOption.REMOTE, dest=ProgressNotesArgument.REMOTE, required=True
    )
    prune.add_argument(
        ProgressNotesOption.KEEP, dest=ProgressNotesArgument.KEEP, required=True
    )
    arguments = vars(parser.parse_args())

    outcome = ProgressNotesPruning(
        directory=ProgressNotesDirectory(arguments[ProgressNotesArgument.DIRECTORY]),
        git=GitCommandRunner(Path.cwd()),
        remote=arguments[ProgressNotesArgument.REMOTE],
        kept_branch=arguments[ProgressNotesArgument.KEEP],
    ).run()
    if isinstance(outcome, PruningSkipped):
        logger.warning(f"Finished branches' progress notes were not pruned: {outcome}.")
    elif outcome:
        logger.info(
            "Removed the progress notes of finished branches:\n" + "\n".join(outcome)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
