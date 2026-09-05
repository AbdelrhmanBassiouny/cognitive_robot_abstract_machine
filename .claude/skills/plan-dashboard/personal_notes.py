#!/usr/bin/env python3
"""
Read plan data off the personal-notes branch, with no live session.

The session-driven skill does this with the bash snippets in
``plan-dashboard/SKILL.md`` step 1; this module is the same reads as code, so the
headless site build (``build_site.py``) can do them unattended. Nothing here
writes - a correction back to the branch goes through
``.claude/hooks/write-personal-notes-file.sh``, same as every other write.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from errors import PlanDashboardError
from git_commands import GitCommandRunner

# %% where the branch lives

PLANS_DIRECTORY = ".claude/personal/plans"
"""
The directory on the notes branch holding one subdirectory per plan.
"""


class PlanDocument(StrEnum):
    """
    The files every plan on the notes branch is made of.

    Named here rather than at each read, so the site build, the tests and
    ``resolve-personal-notes-config.sh``'s own equivalents all spell one filename once.
    """

    MANIFEST = "plan.yaml"
    """
    The plan's items, tracks, waves and statuses.
    """

    ROADMAP = "roadmap.md"
    """
    The narrative the manifest's items refer back to.
    """

    def path_in(self, plan_identifier: str) -> str:
        """
        :param plan_identifier: The plan whose copy of this document is wanted.
        :return: Its repository-relative path on the notes branch.
        """
        return f"{PLANS_DIRECTORY}/{plan_identifier}/{self}"


FETCHED_REFERENCE = "FETCH_HEAD"
"""
The reference a just-fetched branch is read through.

Deliberately not ``<remote>/<branch>``: a remote given as a raw URL creates no remote-
tracking ref, and ``FETCH_HEAD`` names what was fetched either way.
"""

_PLAN_MANIFEST_PATH_PATTERN = re.compile(
    rf"^{re.escape(PLANS_DIRECTORY)}/([^/]+)/{re.escape(PlanDocument.MANIFEST)}$"
)


class NotesConfigurationKey(StrEnum):
    """
    The repository-local git config keys that locate the notes branch.
    """

    REMOTE = "claude.personalNotesRemote"
    """
    Which remote serves the branch.
    """

    BRANCH = "claude.personalNotesBranch"
    """
    Which branch on it holds the plan data.
    """


class NotesEnvironmentVariable(StrEnum):
    """
    The environment variables consulted when the git config keys are unset - the only
    channel that survives a clone made fresh for every session.
    """

    REMOTE = "CLAUDE_PERSONAL_NOTES_REMOTE"
    """
    Overrides :attr:`NotesConfigurationKey.REMOTE`'s absence.
    """

    BRANCH = "CLAUDE_PERSONAL_NOTES_BRANCH"
    """
    Overrides :attr:`NotesConfigurationKey.BRANCH`'s absence.
    """


class NotesDefault(StrEnum):
    """
    What a clone that configures neither override is read at.
    """

    REMOTE = "origin"
    """
    The remote a plain clone already has.
    """

    BRANCH = "claude/personal-notes"
    """
    Where this tooling puts a fork's own plan data.
    """


@dataclass(frozen=True)
class NotesSetting:
    """
    One setting locating the personal-notes branch, and the precedence that resolves it.

    Mirrors ``resolve-personal-notes-config.sh``'s own precedence - repository git
    config, then environment variable, then the zero-config default - so a clone
    configured for one is read the same way from bash and from here.
    """

    git_config_key: NotesConfigurationKey
    """
    The repository-local git config key that overrides everything else.
    """

    environment_variable: NotesEnvironmentVariable
    """
    The environment variable consulted when the git config key is unset.
    """

    default: NotesDefault
    """
    The value used when neither override is present.
    """

    def resolve(self, git: GitCommandRunner) -> str:
        """
        Resolve this setting for a given clone.

        :param git: The runner whose checkout's git config is consulted.
        :return: The configured value, or :attr:`default`.
        """
        configured = git.output_or_none("config", "--get", self.git_config_key)
        return (
            configured or os.environ.get(self.environment_variable) or str(self.default)
        )


NOTES_REMOTE_SETTING = NotesSetting(
    git_config_key=NotesConfigurationKey.REMOTE,
    environment_variable=NotesEnvironmentVariable.REMOTE,
    default=NotesDefault.REMOTE,
)
"""
Which remote serves the personal-notes branch.
"""

NOTES_BRANCH_SETTING = NotesSetting(
    git_config_key=NotesConfigurationKey.BRANCH,
    environment_variable=NotesEnvironmentVariable.BRANCH,
    default=NotesDefault.BRANCH,
)
"""
Which branch on that remote holds the plan data.
"""


# %% reading the branch


@dataclass
class PersonalNotesUnavailableError(PlanDashboardError):
    """
    Raised when the personal-notes branch cannot be fetched - there is no plan data to
    read, and every caller here needs some.
    """

    remote: str
    """
    The remote the fetch was attempted against.
    """

    branch: str
    """
    The branch that was asked for.
    """

    detail: str
    """
    What git said about the refusal.
    """

    def error_message(self) -> str:
        """:return: Which branch could not be fetched from where, and why."""
        return f"Could not fetch '{self.branch}' from '{self.remote}': {self.detail}"


@dataclass
class PlanFileMissingError(PlanDashboardError):
    """
    Raised when a plan directory on the notes branch lacks a file the plan is required
    to have.
    """

    branch: str
    """
    The branch that was read.
    """

    path: str
    """
    The document's repository-relative path, which the branch does not carry.
    """

    def error_message(self) -> str:
        """:return: Which document is missing from which branch."""
        return f"'{self.path}' is not on '{self.branch}' - the plan is incomplete."


@dataclass
class PersonalNotesBranch:
    """
    The personal-notes branch of one clone, as a source of plan data.

    :meth:`fetch` must run before any read; every read resolves against the reference
    that fetch left behind.
    """

    git: GitCommandRunner
    """
    The runner every read goes through, in the clone whose configuration located the
    branch.
    """

    remote: str
    """
    The remote the branch is fetched from.
    """

    branch: str
    """
    The branch holding the plan data.
    """

    @classmethod
    def resolve(cls, repository_root: Path) -> PersonalNotesBranch:
        """
        Locate the notes branch of a clone from its configuration.

        :param repository_root: The clone to resolve for.
        :return: The branch, not yet fetched.
        """
        git = GitCommandRunner(repository_root)
        return cls(
            git=git,
            remote=NOTES_REMOTE_SETTING.resolve(git),
            branch=NOTES_BRANCH_SETTING.resolve(git),
        )

    def fetch(self) -> None:
        """
        Fetch the branch, so the reads below resolve.

        :raises PersonalNotesUnavailableError: If the branch cannot be fetched.
        """
        fetched = self.git.attempt("fetch", "--quiet", self.remote, self.branch)
        if not fetched.succeeded:
            raise PersonalNotesUnavailableError(
                remote=self.remote, branch=self.branch, detail=fetched.error_output
            )

    def plan_identifiers(self) -> list[str]:
        """
        Every plan on the branch, in a stable order.

        :return: The plan identifiers, sorted.
        """
        listing = self.git.run("ls-tree", "-r", "--name-only", FETCHED_REFERENCE)
        return sorted(
            match.group(1)
            for match in map(_PLAN_MANIFEST_PATH_PATTERN.match, listing.splitlines())
            if match
        )

    def read(self, path: str) -> str | None:
        """
        Read one file off the branch.

        :param path: The file's repository-relative path.
        :return: The file's content, or ``None`` if the branch has no such file.
        """
        return self.git.output_or_none(
            "show", f"{FETCHED_REFERENCE}:{path}", strip=False
        )

    def plan_document(self, plan_identifier: str, document: PlanDocument) -> str:
        """
        Read one of a plan's own documents.

        :param plan_identifier: The plan whose directory to read from.
        :param document: The document inside it.
        :raises PlanFileMissingError: If the branch does not carry it.
        :return: The document's content.
        """
        path = document.path_in(plan_identifier)
        content = self.read(path)
        if content is None:
            raise PlanFileMissingError(branch=self.branch, path=path)
        return content
