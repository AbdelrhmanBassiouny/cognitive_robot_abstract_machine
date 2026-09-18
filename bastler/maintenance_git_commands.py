"""
Running git for a pass, and deciding what a pass is allowed to publish.

Every command a pass runs goes through :class:`MaintenanceGitCommandRunner`, and every
push it proposes is built as a :class:`ProposedPush` - so whether published history may
be rewritten is decided in one place rather than at each call site.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from bastler.git_commands import GitCommandResult, GitCommandRunner
from bastler.stack import Configuration, IntegrationStrategy, resolve_ref

# %% running git


# %% what a pass is allowed to publish


@dataclass(frozen=True)
class ProposedPush:
    """
    One publication, and whether it is authorised to overwrite what is published.

    Every push the executor makes is built here, so whether history may be rewritten is
    decided once rather than at each call.
    """

    remote: str
    """
    The remote to publish to.
    """

    refspec: str
    """
    What to publish, as ``<source>:<destination>``.
    """

    with_lease: bool = False
    """
    Whether published history may be overwritten, and then only if the remote is where
    this checkout last saw it.
    """

    @classmethod
    def publishing(
        cls, configuration: Configuration, branch: str, strategy: IntegrationStrategy
    ) -> ProposedPush:
        """
        Build the push that publishes a restacked branch.

        :param configuration: The resolved configuration.
        :param branch: The branch to publish.
        :param strategy: How its parent was integrated, which is what authorises a
            rewrite - and which ``build_stack`` sets to rebase only from the label.
        :return: The push.
        """
        return cls(
            remote=configuration.fork_remote,
            refspec=f"{branch}:{branch}",
            with_lease=strategy is IntegrationStrategy.REBASE,
        )


@dataclass(frozen=True)
class MaintenanceGitCommandRunner(GitCommandRunner):
    """
    The shared runner, plus the two commands that mean something only to a pass.

    Both are stack vocabulary rather than git vocabulary: what to abandon depends on
    which integration was attempted, and what may be forced is decided by the
    :class:`ProposedPush` rather than by the caller asking for it.
    """

    def abandon(self, strategy: IntegrationStrategy) -> None:
        """
        Undo whichever integration just failed.

        :param strategy: The integration that was attempted.
        """
        self.attempt(
            "rebase" if strategy is IntegrationStrategy.REBASE else "merge", "--abort"
        )

    def push(self, proposed: ProposedPush) -> GitCommandResult:
        """
        Publish a refspec, forcing only where the push itself says it is authorised.

        :param proposed: What to publish, and whether a rewrite is authorised.
        :return: The finished push, whose failure the caller reports rather than forces.
        """
        lease = ["--force-with-lease"] if proposed.with_lease else []
        return self.attempt(
            "push", "--quiet", *lease, proposed.remote, proposed.refspec
        )


# %% asking git what contains what


@dataclass(frozen=True)
class BranchAncestry:
    """
    Answers containment questions about the fork's branches.

    :class:`CommitMoveChecks` asks its false-merge question through this, so the
    question is asked of git rather than of anything this module remembers.
    """

    configuration: Configuration
    """
    The resolved configuration naming the fork remote.
    """

    git: GitCommandRunner
    """
    The runner to ask git through.
    """

    def is_ancestor(self, candidate: str, descendant: str) -> bool:
        """:param candidate: A fork branch that may be contained.
        :param descendant: A local branch that may contain it.
        :return: Whether the fork's copy of *candidate* is contained in *descendant*."""
        return self.git.contains(resolve_ref(self.configuration, candidate), descendant)
