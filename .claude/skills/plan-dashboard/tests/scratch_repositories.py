"""
The scratch git repositories the plan-dashboard tests read real plan data out of.

Every one of them is local: a bare repository stands in for the notes remote, so a test
exercises the same fetches and reads the scripts do without reaching the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from git_commands import GitCommandRunner
from personal_notes import (
    NOTES_BRANCH_SETTING,
    NOTES_REMOTE_SETTING,
    PLANS_DIRECTORY,
    PlanDocument,
)

GIT_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}
"""A fixed identity and a minimal path, so a scratch commit never depends on the
running user's git configuration."""

SCRATCH_REMOTE_DIRECTORY = "remote.git"
"""
The bare repository a scratch clone's notes remote points at.
"""

SEED_DIRECTORY = "seed"
"""
The checkout the notes branch is first written and pushed from.
"""

CLONE_DIRECTORY = "clone"
"""
The checkout under test, which starts out holding nothing but the remote.
"""


@dataclass(frozen=True)
class PlanFiles:
    """
    One plan's files, as seeded onto a scratch notes branch.
    """

    manifest: str
    """
    The plan's ``plan.yaml`` source.
    """

    roadmap: str
    """
    The plan's ``roadmap.md`` source.
    """

    def content_of(self, document: PlanDocument) -> str:
        """
        :param document: The document wanted.
        :return: Its source, so a caller reads by document rather than by field name.
        """
        if document is PlanDocument.MANIFEST:
            return self.manifest
        return self.roadmap


@dataclass(frozen=True)
class ScratchNotesRemote:
    """
    A scratch clone whose default remote carries a notes branch, so a test reads real
    plan data over real git with no network access.
    """

    root: Path
    """
    The directory the remote, the seed checkout and the clone are built under.
    """

    git: GitCommandRunner
    """
    The runner every one of those repositories is driven through.
    """

    @property
    def remote(self) -> Path:
        """:return: The bare repository the notes branch is pushed to."""
        return self.root / SCRATCH_REMOTE_DIRECTORY

    @property
    def checkout(self) -> Path:
        """:return: The checkout the notes branch is written and pushed from."""
        return self.root / SEED_DIRECTORY

    @property
    def clone(self) -> Path:
        """:return: The checkout under test."""
        return self.root / CLONE_DIRECTORY

    def seed(self, plans: Mapping[str, PlanFiles]) -> Path:
        """
        Write the plans onto the notes branch and clone it.

        :param plans: The plans to seed, keyed by identifier.
        :return: The clone's root.
        """
        self.git.run("init", "--quiet", "--bare", str(self.remote))

        self.checkout.mkdir()
        checkout_git = self.git.in_directory(self.checkout)
        checkout_git.run(
            "init", "--quiet", "--initial-branch", NOTES_BRANCH_SETTING.default
        )
        for plan_identifier, files in plans.items():
            plan_directory = self.checkout / PLANS_DIRECTORY / plan_identifier
            plan_directory.mkdir(parents=True)
            for document in PlanDocument:
                (plan_directory / document).write_text(files.content_of(document))
        checkout_git.run("add", ".")
        checkout_git.run("commit", "--quiet", "--message", "seed the notes branch")
        checkout_git.run(
            "push", "--quiet", str(self.remote), NOTES_BRANCH_SETTING.default
        )

        self.clone.mkdir()
        clone_git = self.git.in_directory(self.clone)
        clone_git.run("init", "--quiet")
        clone_git.run("remote", "add", NOTES_REMOTE_SETTING.default, str(self.remote))
        return self.clone
