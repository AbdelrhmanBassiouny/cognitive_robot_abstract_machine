"""
Running git, in the two contracts a caller can need.

A tool that only derives wants a command that answers nothing when it fails - a missing
reference simply means "no answer". A tool that publishes needs the opposite, because a
push that silently did nothing must not be indistinguishable from one that worked. Both
are here: :meth:`GitCommandRunner.attempt` reports, :meth:`GitCommandRunner.run` raises.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from exceptions import GitCommandFailed

# %% what a finished command says


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
class GitSetting:
    """
    One git configuration entry, passed to a command rather than written to a file.

    A pair of bare strings says nothing about which half is which, and both halves are
    strings, so nothing catches them being swapped.
    """

    key: str
    """
    The setting's name, as ``git config`` spells it.
    """

    value: str
    """
    What to set it to.
    """

    @property
    def as_arguments(self) -> tuple[str, str]:
        """:return: The pair of arguments git takes this as."""
        return ("-c", f"{self.key}={self.value}")


DETACHED_HEAD = "HEAD"
"""
The commit a checkout is on, which is what a build publishes from: it assembles on a
detached head so no local branch is left behind for a tree already answered about.
"""

BRANCH_REFERENCE_PREFIX = "refs/heads/"
"""
Where git files a branch, written once because a push has to say it in full.

A destination given as a bare name is resolved against whatever the remote already has,
so a branch is named the long way round to say which namespace is meant.
"""


@dataclass(frozen=True)
class BranchPublication:
    """
    What to publish and the branch to publish it as.
    """

    source: str
    """
    The commit or reference to publish.
    """

    branch: str
    """
    The branch it becomes on the remote.
    """

    @classmethod
    def under_its_own_name(cls, branch: str) -> BranchPublication:
        """
        Publish a branch as itself.

        :param branch: The branch to publish.
        :return: The publication saying so.
        """
        return cls(source=branch, branch=branch)

    def __str__(self) -> str:
        return f"{self.source}:{BRANCH_REFERENCE_PREFIX}{self.branch}"


@dataclass(frozen=True)
class ReferenceUpdate:
    """
    One reference on a remote, and what to leave it pointing at.

    For the references a record is kept as, below ``refs/`` and outside ``refs/heads/``,
    which are overwritten by design; a branch is published through
    :class:`BranchPublication`, which decides whether history may be rewritten.
    """

    reference: str
    """
    The fully qualified reference.
    """

    commit: str | None = None
    """
    The commit to leave it at, or ``None`` to delete it.
    """

    def __str__(self) -> str:
        return f"{self.commit or ''}:{self.reference}"


@dataclass(frozen=True)
class ProposedPush:
    """
    One publication, and whether it is authorised to overwrite what is published.

    Every push a caller makes is built as one of these, so whether history may be
    rewritten is decided once rather than at each call.
    """

    remote: str
    """
    The remote to publish to.
    """

    publication: BranchPublication
    """
    What to publish and the branch to publish it as.
    """

    with_lease: bool = False
    """
    Whether published history may be overwritten, and then only if the remote is where
    this checkout last saw it.
    """

    def as_arguments(self) -> tuple[str, ...]:
        """
        :return: What to hand git, forcing only where this push authorises it.
        """
        lease = ("--force-with-lease",) if self.with_lease else ()
        return (*lease, self.remote, str(self.publication))


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

    configuration_overrides: tuple[GitSetting, ...] = ()
    """
    Settings passed to every command as ``-c <key>=<value>``, so a run can turn a git
    feature on for itself without writing it into the repository's own configuration -
    which is shared with the developer who invoked it.
    """

    def attempt(self, *arguments: str) -> GitCommandResult:
        """
        Run a command whose failure is an expected outcome.

        :param arguments: The git subcommand and its arguments.
        :return: The finished command, named by the arguments it was asked for rather
            than by the ones git was handed, so a caller reads back what it requested.
        """
        overrides = [
            part
            for setting in self.configuration_overrides
            for part in setting.as_arguments
        ]
        completed = subprocess.run(
            ["git", *overrides, *arguments],
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

    def checkout_orphan(self, branch: str) -> None:
        """
        Start a branch with no history behind it, leaving the index as it was.

        :param branch: The branch to start.
        """
        self.run("checkout", "--quiet", "--orphan", branch)

    def branch_names(self) -> tuple[str, ...]:
        """
        :return: Every branch this checkout holds, whichever one is checked out.
        """
        return tuple(
            line.strip().lstrip("* ")
            for line in self.run("branch", "--list").splitlines()
        )

    def file_names_in(self, reference: str) -> tuple[str, ...]:
        """
        :param reference: The commit or branch to read.
        :return: The names of the files that reference carries, in git's own order.
        """
        return tuple(self.run("ls-tree", "--name-only", reference).splitlines())

    def worktree_paths(self) -> tuple[str, ...]:
        """
        :return: The working trees attached to this checkout, the main one included.
        """
        return tuple(
            line.split()[0] for line in self.run("worktree", "list").splitlines()
        )

    def common_directory(self) -> Path:
        """
        Locate the directory the repository's shared state lives in - the one every
        worktree attached to it reads, rather than a worktree's own.

        Git answers relatively from inside a main working tree, so the answer is only
        meaningful against this runner's working directory. Resolving it here rather
        than at the call site is what stops it being read against the directory the
        process happens to have been started in.

        :return: An absolute path to the shared git directory.
        """
        answered = Path(self.run("rev-parse", "--git-common-dir"))
        return (self.working_directory / answered).resolve()

    def remote_reference(self, remote: str, reference: str) -> str:
        """
        Ask a remote what it holds a reference at, without fetching from it.

        :param remote: The remote to ask.
        :param reference: The fully qualified reference to look up.
        :return: What the remote answered, empty when it holds no such reference.
        """
        return self.run("ls-remote", remote, reference)

    def remote_branch_heads(self, remote: str) -> dict[str, str]:
        """
        Read what a remote has each of its branches pointing at, as this checkout last
        fetched them, in one call rather than one per branch.

        :param remote: The remote to read.
        :return: The head per branch name.
        """
        listed = self.run(
            "for-each-ref",
            "--format=%(refname:strip=3) %(objectname)",
            f"refs/remotes/{remote}/",
        )
        return dict(line.split(" ", 1) for line in listed.splitlines() if " " in line)

    def remote_branch_names(self, remote: str, pattern: str) -> tuple[str, ...]:
        """
        Ask a remote which of its branches match a shape, without fetching from it.

        :param remote: The remote to ask.
        :param pattern: A branch-name glob, matched against the branch's own name.
        :return: The names of the branches it answered with, without their prefix.
        """
        answered = self.remote_reference(remote, f"{BRANCH_REFERENCE_PREFIX}{pattern}")
        return tuple(
            line.split()[-1].removeprefix(BRANCH_REFERENCE_PREFIX)
            for line in answered.splitlines()
            if line.strip()
        )

    def remove_remote(self, remote: str) -> None:
        """
        :param remote: The remote to stop tracking.
        """
        self.run("remote", "remove", remote)

    def configure(self, setting: GitSetting) -> None:
        """
        Write a setting into this checkout's own configuration.

        Unlike :attr:`configuration_overrides`, which a run passes to each command it
        makes, this outlives the process - which is what an identity has to do, since the
        commits are made by the commands a rebuild goes on to run.

        :param setting: The setting to write.
        """
        self.run("config", setting.key, setting.value)

    def switch_to(self, branch: str) -> None:
        """
        Check out a branch that already exists, leaving where it points alone.

        :param branch: The branch to check out.
        """
        self.run("checkout", "--quiet", branch)

    def stage(self, *paths: str) -> None:
        """
        :param paths: The paths to add to the index.
        """
        self.run("add", *paths)

    def remove(self, *paths: str) -> None:
        """
        :param paths: The paths to delete and stage the deletion of.
        """
        self.run("rm", "--quiet", *paths)

    def commit(self, message: str) -> None:
        """
        :param message: The message to commit what is staged under.
        """
        self.run("commit", "--quiet", "-m", message)

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

    def merges_cleanly(self, one: str, other: str) -> bool:
        """
        Ask whether two references would merge, without merging them.

        ``merge-tree`` performs the whole three-way merge against a tree it writes and
        throws away, so this can be asked of a checkout that is mid-build without
        disturbing what it is holding.

        :param one: A reference to merge.
        :param other: The reference to merge it with.
        :return: Whether the merge would conflict.
        """
        return self.attempt("merge-tree", "--write-tree", one, other).succeeded

    def conclude_merge(self) -> GitCommandResult:
        """
        Commit a merge whose conflicts are already resolved and staged.

        :return: The finished commit.
        """
        return self.attempt("commit", "--no-edit")

    def push(self, proposed: ProposedPush) -> GitCommandResult:
        """
        Publish a branch, forcing only where the push itself says it is authorised.

        :param proposed: What to publish, and whether a rewrite is authorised.
        :return: The finished push, whose failure the caller reports rather than forces.
        """
        return self.attempt("push", "--quiet", *proposed.as_arguments())

    def write_remote_references(
        self, remote: str, updates: Sequence[ReferenceUpdate]
    ) -> None:
        """
        Leave a remote's references where the updates say, in one push.

        Overwrites whatever each reference held: these are the references a record is
        kept as, never branches, so there is no history to protect.

        :param remote: The remote to write to.
        :param updates: What each reference is left pointing at, or that it is deleted.
        """
        self.run(
            "push", "--quiet", "--force", remote, *(str(update) for update in updates)
        )

    def delete_branch(self, remote: str, branch: str) -> GitCommandResult:
        """
        Remove a published branch.

        :param remote: The remote holding it.
        :param branch: The branch to remove.
        :return: The finished push, whose failure the caller reports rather than forces.
        """
        return self.attempt("push", "--quiet", "--delete", remote, branch)

    def contains(self, candidate: str, descendant: str) -> bool:
        """
        :param candidate: The reference that may be contained.
        :param descendant: The reference that may contain it.
        :return: Whether *candidate* is an ancestor of *descendant*.
        """
        return self.attempt(
            "merge-base", "--is-ancestor", candidate, descendant
        ).succeeded
