"""
What each branch in flight changes on its own, read from git.

A branch's own work is the commits it carries that neither its parent nor the upstream
base already holds, leaving out merge commits: the parent's work is the parent's, and an
upstream base merged in to keep a branch current is nobody's change in flight.
"""

from __future__ import annotations

from dataclasses import dataclass

from stack import Branch, Configuration, Stack

from maintenance_git_commands import MaintenanceGitCommandRunner


@dataclass(frozen=True)
class BranchChanges:
    """
    Reads the paths each branch's own commits change onto the branch.
    """

    configuration: Configuration
    """
    The configuration naming the fork, the upstream base and the scope.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner the published branches are read through, fetched beforehand.
    """

    def annotate(self, stack: Stack) -> Stack:
        """
        Fill every branch's :attr:`~stack.Branch.changed_paths`, where the scope reads
        them at all.

        :param stack: The derived stack.
        :return: The same stack, its branches carrying what they change.
        """
        if not self.configuration.integration_scope.reads_changed_paths:
            return stack
        published = self._published_branches()
        for branch in stack.branches:
            if branch.name in published:
                branch.changed_paths = self._paths_changed_by(branch, published)
        return stack

    def _paths_changed_by(self, branch: Branch, published: set[str]) -> tuple[str, ...]:
        """
        :param branch: A branch the fork publishes.
        :param published: Every branch the fork publishes.
        :return: Every path the branch's own commits change, each once, in the order git
            first names it.
        """
        remote = self.configuration.fork_remote
        excluded = [
            f"{self.configuration.upstream_remote}/{self.configuration.upstream_base}"
        ]
        if branch.parent in published:
            excluded.append(f"{remote}/{branch.parent}")
        listed = self.git.run(
            "log",
            "--no-merges",
            "--format=",
            "--name-only",
            f"{remote}/{branch.name}",
            "--not",
            *excluded,
        )
        return tuple(dict.fromkeys(line for line in listed.splitlines() if line))

    def _published_branches(self) -> set[str]:
        """
        :return: Every branch the fork publishes, read in one call rather than one per
            branch.
        """
        listed = self.git.run(
            "for-each-ref",
            "--format=%(refname:strip=3)",
            f"refs/remotes/{self.configuration.fork_remote}/",
        )
        return set(listed.splitlines())
