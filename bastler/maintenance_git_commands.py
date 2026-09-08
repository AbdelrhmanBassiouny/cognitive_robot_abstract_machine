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

from bastler.git_commands import (
    BranchPublication,
    GitCommandRunner,
    ProposedPush,
)
from bastler.stack import Configuration, IntegrationStrategy, resolve_ref

# %% running git


# %% what a pass is allowed to publish


@dataclass(frozen=True)
class RestackPush(ProposedPush):
    """
    The push that publishes a restacked branch.

    A category rather than a shape: what it adds is where the lease comes from, so the
    strategy decides a rewrite rather than the caller asking for one.
    """

    @classmethod
    def publishing(
        cls, configuration: Configuration, branch: str, strategy: IntegrationStrategy
    ) -> RestackPush:
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
            publication=BranchPublication.under_its_own_name(branch),
            with_lease=strategy is IntegrationStrategy.REBASE,
        )


@dataclass(frozen=True)
class MaintenanceGitCommandRunner(GitCommandRunner):
    """
    The shared runner, plus the one command that means something only to a pass.

    Abandoning is stack vocabulary rather than git vocabulary: what to undo depends on
    which integration was attempted.
    """

    def abandon(self, strategy: IntegrationStrategy) -> None:
        """
        Undo whichever integration just failed.

        :param strategy: The integration that was attempted.
        """
        self.attempt(
            "rebase" if strategy is IntegrationStrategy.REBASE else "merge", "--abort"
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
