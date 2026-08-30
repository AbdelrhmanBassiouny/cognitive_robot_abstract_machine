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
import subprocess
from dataclasses import dataclass
from pathlib import Path

# %% where the branch lives

PLANS_DIRECTORY = ".claude/personal/plans"
"""
The directory on the notes branch holding one subdirectory per plan.
"""

PLAN_MANIFEST_FILENAME = "plan.yaml"
"""
The filename of a plan's manifest inside its own directory.
"""

PLAN_ROADMAP_FILENAME = "roadmap.md"
"""
The filename of a plan's roadmap inside its own directory.
"""

FETCHED_REFERENCE = "FETCH_HEAD"
"""
The reference a just-fetched branch is read through.

Deliberately not ``<remote>/<branch>``: a remote given as a raw URL creates no remote-
tracking ref, and ``FETCH_HEAD`` names what was fetched either way.
"""

_PLAN_MANIFEST_PATH_PATTERN = re.compile(
    rf"^{re.escape(PLANS_DIRECTORY)}/([^/]+)/{re.escape(PLAN_MANIFEST_FILENAME)}$"
)


@dataclass(frozen=True)
class NotesSetting:
    """
    One setting locating the personal-notes branch, and the precedence that resolves it.

    Mirrors ``resolve-personal-notes-config.sh``'s own precedence - repository git
    config, then environment variable, then the zero-config default - so a clone
    configured for one is read the same way from bash and from here.
    """

    git_config_key: str
    """
    The repository-local git config key that overrides everything else.
    """

    environment_variable: str
    """
    The environment variable consulted when the git config key is unset.
    """

    default: str
    """
    The value used when neither override is present.
    """

    def resolve(self, repository_root: Path) -> str:
        """
        Resolve this setting for a given clone.

        :param repository_root: The clone whose git config is consulted.
        :return: The configured value, or :attr:`default`.
        """
        configured = _optional_git_output(
            repository_root, "config", "--get", self.git_config_key
        )
        return configured or os.environ.get(self.environment_variable) or self.default


NOTES_REMOTE_SETTING = NotesSetting(
    git_config_key="claude.personalNotesRemote",
    environment_variable="CLAUDE_PERSONAL_NOTES_REMOTE",
    default="origin",
)
"""
Which remote serves the personal-notes branch.
"""

NOTES_BRANCH_SETTING = NotesSetting(
    git_config_key="claude.personalNotesBranch",
    environment_variable="CLAUDE_PERSONAL_NOTES_BRANCH",
    default="claude/personal-notes",
)
"""
Which branch on that remote holds the plan data.
"""


# %% reading the branch


class PersonalNotesUnavailableError(RuntimeError):
    """Raised when the personal-notes branch cannot be fetched - there is no plan data
    to read, and every caller here needs some."""


class PlanFileMissingError(FileNotFoundError):
    """
    Raised when a plan directory on the notes branch lacks a file the plan is required
    to have.
    """


@dataclass
class PersonalNotesBranch:
    """
    The personal-notes branch of one clone, as a source of plan data.

    :meth:`fetch` must run before any read; every read resolves against the reference
    that fetch left behind.
    """

    repository_root: Path
    """
    The clone whose remotes and git config locate the branch.
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
        return cls(
            repository_root=repository_root,
            remote=NOTES_REMOTE_SETTING.resolve(repository_root),
            branch=NOTES_BRANCH_SETTING.resolve(repository_root),
        )

    def fetch(self) -> None:
        """
        Fetch the branch, so the reads below resolve.

        :raises PersonalNotesUnavailableError: If the branch cannot be fetched.
        """
        fetched = subprocess.run(
            ["git", "fetch", "--quiet", self.remote, self.branch],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
        )
        if fetched.returncode != 0:
            raise PersonalNotesUnavailableError(
                f"Could not fetch '{self.branch}' from '{self.remote}': "
                f"{fetched.stderr.strip()}"
            )

    def plan_identifiers(self) -> list[str]:
        """
        Every plan on the branch, in a stable order.

        :return: The plan identifiers, sorted.
        """
        listing = _git_output(
            self.repository_root, "ls-tree", "-r", "--name-only", FETCHED_REFERENCE
        )
        identifiers = [
            match.group(1)
            for match in map(_PLAN_MANIFEST_PATH_PATTERN.match, listing.splitlines())
            if match
        ]
        return sorted(identifiers)

    def read(self, path: str) -> str | None:
        """
        Read one file off the branch.

        :param path: The file's repository-relative path.
        :return: The file's content, or ``None`` if the branch has no such file.
        """
        return _optional_git_output(
            self.repository_root, "show", f"{FETCHED_REFERENCE}:{path}", strip=False
        )

    def plan_manifest(self, plan_identifier: str) -> str:
        """
        Read one plan's manifest.

        :param plan_identifier: The plan to read.
        :raises PlanFileMissingError: If the plan has no manifest.
        :return: The manifest's YAML source.
        """
        return self._read_plan_file(plan_identifier, PLAN_MANIFEST_FILENAME)

    def plan_roadmap(self, plan_identifier: str) -> str:
        """
        Read one plan's roadmap.

        :param plan_identifier: The plan to read.
        :raises PlanFileMissingError: If the plan has no roadmap.
        :return: The roadmap's markdown source.
        """
        return self._read_plan_file(plan_identifier, PLAN_ROADMAP_FILENAME)

    def _read_plan_file(self, plan_identifier: str, file_name: str) -> str:
        """
        Read one file from a plan's own directory.

        :param plan_identifier: The plan whose directory to read from.
        :param file_name: The file inside it.
        :raises PlanFileMissingError: If the file is not on the branch.
        :return: The file's content.
        """
        path = f"{PLANS_DIRECTORY}/{plan_identifier}/{file_name}"
        content = self.read(path)
        if content is None:
            raise PlanFileMissingError(
                f"'{path}' is not on '{self.branch}' - the plan is incomplete."
            )
        return content


# %% running git


def _git_output(repository_root: Path, *arguments: str) -> str:
    """
    Run one git command in a clone and return its standard output, stripped.

    :param repository_root: The clone to run in.
    :param arguments: The git subcommand and its arguments.
    :raises subprocess.CalledProcessError: If the command fails.
    :return: The command's standard output.
    """
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _optional_git_output(
    repository_root: Path, *arguments: str, strip: bool = True
) -> str | None:
    """
    Run one git command whose failure is an ordinary outcome - an unset config key, a
    path the reference does not carry - rather than an error.

    :param repository_root: The clone to run in.
    :param arguments: The git subcommand and its arguments.
    :param strip: Whether to strip surrounding whitespace, which file content must not
        be - an empty file therefore stays distinguishable from a missing one.
    :return: The command's standard output, or ``None`` if it failed.
    """
    completed = subprocess.run(
        ["git", *arguments], cwd=repository_root, capture_output=True, text=True
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() if strip else completed.stdout
