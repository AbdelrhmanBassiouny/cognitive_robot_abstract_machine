"""
Removes the progress notes of pull requests whose work is over.

A branch's progress notes are read only while its pull request is open. Once every pull
request from that branch has merged or closed, or the branch itself is gone, the notes are
never read again, so they are deleted rather than left to accumulate on the personal-notes
branch.

Usage:
    python3 -m basstler.progress_notes prune --directory <pr-progress-directory> \\
        --remote-url <url> --remote-branches <file> --keep <branch>
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.maintenance_board import PullRequestRecord
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


# %% command line


def main() -> int:
    """
    Prune a progress-notes directory and print each branch whose notes were removed.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    prune = subcommands.add_parser(
        "prune", help="Delete the progress notes of finished pull requests"
    )
    prune.add_argument("--directory", required=True, type=Path)
    prune.add_argument("--remote-url", required=True)
    prune.add_argument(
        "--remote-branches",
        required=True,
        type=Path,
        help="A file naming every branch the remote has, one per line",
    )
    prune.add_argument("--keep", required=True)
    arguments = parser.parse_args()

    repository = Repository.from_remote_url(arguments.remote_url)
    remote_branches = frozenset(arguments.remote_branches.read_text().split())
    pull_requests = BranchPullRequests.from_pull_requests(
        GitHubRepository.from_environment(repository).pull_requests(
            ListedPullRequestState.ALL
        ),
        repository,
    )
    for branch in ProgressNotesDirectory(arguments.directory).remove_finished(
        pull_requests, remote_branches, arguments.keep
    ):
        logger.info(branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
