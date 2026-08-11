"""
Running git, in the two contracts a caller can need.

A tool that only derives wants a command that answers nothing when it fails - a missing
reference simply means "no answer". A tool that publishes needs the opposite, because a
push that silently did nothing must not be indistinguishable from one that worked. Both
are here: :meth:`GitCommandRunner.attempt` reports, :meth:`GitCommandRunner.run` raises.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from errors import ExternalCallFailed

# %% what a finished command says


@dataclass
class GitCommandFailed(ExternalCallFailed):
    """
    Raised when a git command whose result was depended on fails.
    """

    arguments: tuple[str, ...] = ()
    """
    The git subcommand and its arguments, as invoked.
    """

    @property
    def call(self) -> str:
        """
        :return: The git command line, as invoked.
        """
        return f"git {' '.join(self.arguments)}"


@dataclass(frozen=True)
class GitCommandResult:
    """
    One finished git command, whether or not it succeeded.
    """

    arguments: tuple[str, ...]
    """
    The git subcommand and its arguments, as invoked.
    """

    exit_status: int
    """
    The status git exited with.
    """

    output: str
    """
    Git's stripped stdout.
    """

    error_output: str
    """
    Git's stripped stderr.
    """

    @property
    def succeeded(self) -> bool:
        """
        :return: Whether git exited zero.
        """
        return self.exit_status == 0

    def raise_if_failed(self) -> GitCommandResult:
        """
        :return: This result, when the command succeeded.
        :raises GitCommandFailed: When it did not.
        """
        if not self.succeeded:
            raise GitCommandFailed(
                status=self.exit_status,
                detail=self.error_output,
                arguments=self.arguments,
            )
        return self


# %% running git


@dataclass(frozen=True)
class GitCommandRunner:
    """
    Runs git in one checkout, in whichever of the two contracts the caller needs.

    The named methods below exist so a command is spelled once rather than at each call
    site - which is what stopped one hand-written invocation taking its arguments in the
    opposite order to its neighbours.
    """

    working_directory: Path
    """
    The checkout every command runs in.
    """

    def attempt(self, *arguments: str) -> GitCommandResult:
        """
        Run a command whose failure is an expected outcome.

        :param arguments: The git subcommand and its arguments.
        :return: The finished command.
        """
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.working_directory,
            capture_output=True,
            text=True,
        )
        return GitCommandResult(
            arguments=arguments,
            exit_status=completed.returncode,
            output=completed.stdout.strip(),
            error_output=completed.stderr.strip(),
        )

    def run(self, *arguments: str) -> str:
        """
        Run a command the caller depends on the result of.

        :param arguments: The git subcommand and its arguments.
        :return: Git's stripped stdout.
        :raises GitCommandFailed: If git exits non-zero.
        """
        return self.attempt(*arguments).raise_if_failed().output

    def fetch(self, remote: str, *references: str) -> None:
        """
        Refresh what this checkout knows about a remote.

        :param remote: The remote to fetch from.
        :param references: The branches to fetch, all of them when none is named.
        """
        self.run("fetch", "--quiet", remote, *references)

    def commit_at(self, reference: str) -> str:
        """
        :param reference: Any reference git can resolve.
        :return: The commit it names.
        """
        return self.run("rev-parse", reference)

    def checkout(self, branch: str, start_point: str) -> None:
        """
        Put a branch at a starting point and check it out.

        :param branch: The branch to move and check out.
        :param start_point: What to point it at.
        """
        self.run("checkout", "--quiet", "-B", branch, start_point)

    def checked_out_branch(self) -> str:
        """
        :return: The branch whose content a push would move.
        """
        return self.run("branch", "--show-current")

    def merge(self, reference: str) -> GitCommandResult:
        """
        :param reference: The reference to merge in.
        :return: The finished merge, whose failure is a conflict only when it left
            unmerged paths behind.
        """
        return self.attempt("merge", "--no-edit", reference)

    def rebase(self, reference: str) -> GitCommandResult:
        """
        :param reference: The reference to rebase onto.
        :return: The finished rebase, whose failure is a conflict only when it left
            unmerged paths behind.
        """
        return self.attempt("rebase", reference)

    def unmerged_paths(self) -> tuple[str, ...]:
        """
        :return: The paths the integration that just failed left conflicted.
        """
        unmerged = self.attempt("diff", "--name-only", "--diff-filter=U")
        return tuple(path for path in unmerged.output.splitlines() if path)

    def push_refspec(
        self, remote: str, refspec: str, with_lease: bool = False
    ) -> GitCommandResult:
        """
        Publish a refspec, forcing only where the caller says it is authorised.

        :param remote: The remote to publish to.
        :param refspec: What to publish, as ``<source>:<destination>``.
        :param with_lease: Whether published history may be overwritten, and then only
            if the remote is where this checkout last saw it.
        :return: The finished push, whose failure the caller reports rather than forces.
        """
        lease = ["--force-with-lease"] if with_lease else []
        return self.attempt("push", "--quiet", *lease, remote, refspec)

    def contains(self, candidate: str, descendant: str) -> bool:
        """
        :param candidate: The reference that may be contained.
        :param descendant: The reference that may contain it.
        :return: Whether *candidate* is an ancestor of *descendant*.
        """
        return self.attempt(
            "merge-base", "--is-ancestor", candidate, descendant
        ).succeeded
