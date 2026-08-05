"""
Resolving and reading the personal-notes branch from Python.

The personal-notes branch holds per-user data (plans, PR progress, config overrides) and
is resolved everywhere by the same precedence: git config, then an environment variable,
then a zero-config default - ``.claude/hooks/resolve-personal-notes-config.sh`` is the
bash home of that rule, and this module is its Python counterpart for code that cannot
source a shell script.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

DEFAULT_PERSONAL_NOTES_REMOTE = "origin"
"""
The remote the personal-notes branch lives on when nothing configures one.
"""

DEFAULT_PERSONAL_NOTES_BRANCH = "claude/personal-notes"
"""
The personal-notes branch name when nothing configures one.
"""

PERSONAL_PLANS_DIRECTORY = ".claude/personal/plans"
"""
Where plans live on the personal-notes branch.
"""

PLAN_MANIFEST_PATH_PATTERN = re.compile(
    rf"^{re.escape(PERSONAL_PLANS_DIRECTORY)}/([^/]+)/plan\.yaml$"
)
"""
What one plan's manifest path on the notes branch looks like, capturing its id.
"""


def _git(repository_root: Path | None, *arguments: str) -> subprocess.CompletedProcess:
    """
    Run a git command in a repository.

    :param repository_root: The repository to run in; the working directory if unset.
    :param arguments: The git subcommand and its arguments.
    :return: The completed process, output captured, not checked.
    """
    return subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        cwd=repository_root or Path.cwd(),
    )


def _resolve(
    repository_root: Path | None,
    configuration_key: str,
    environment_variable: str,
    default: str,
) -> str:
    """
    Resolve one setting by the shared precedence.

    :param repository_root: The repository whose git config to read.
    :param configuration_key: The git config key.
    :param environment_variable: The environment variable consulted next.
    :param default: The zero-config fallback.
    :return: The resolved value.
    """
    configured = _git(
        repository_root, "config", "--get", configuration_key
    ).stdout.strip()
    return configured or os.environ.get(environment_variable) or default


def resolve_personal_notes_remote(repository_root: Path | None = None) -> str:
    """:param repository_root: The repository whose configuration to read.
    :return: the personal-notes remote name or URL."""
    return _resolve(
        repository_root,
        "claude.personalNotesRemote",
        "CLAUDE_PERSONAL_NOTES_REMOTE",
        DEFAULT_PERSONAL_NOTES_REMOTE,
    )


def resolve_personal_notes_branch(repository_root: Path | None = None) -> str:
    """:param repository_root: The repository whose configuration to read.
    :return: the personal-notes branch name."""
    return _resolve(
        repository_root,
        "claude.personalNotesBranch",
        "CLAUDE_PERSONAL_NOTES_BRANCH",
        DEFAULT_PERSONAL_NOTES_BRANCH,
    )


def fetch_personal_notes_reference(
    repository_root: Path | None = None,
    remote: str | None = None,
    branch: str | None = None,
) -> str | None:
    """
    Fetch the personal-notes branch and name a readable reference for it.

    Works off ``FETCH_HEAD`` rather than a remote-tracking reference because a URL-form
    remote creates no tracking reference at all.

    :param repository_root: The repository to fetch into.
    :param remote: The notes remote; resolved by the shared precedence if unset.
    :param branch: The notes branch; resolved by the shared precedence if unset.
    :return: The reference to read the branch through, or ``None`` when the fetch fails
        (e.g. the branch does not exist yet).
    """
    remote = remote or resolve_personal_notes_remote(repository_root)
    branch = branch or resolve_personal_notes_branch(repository_root)
    fetched = _git(repository_root, "fetch", remote, branch, "--quiet")
    if fetched.returncode != 0:
        return None
    return "FETCH_HEAD"


def read_file_at_reference(
    reference: str, path: str, repository_root: Path | None = None
) -> str | None:
    """
    Read one file's content at a git reference.

    :param reference: The git reference to read through.
    :param path: The repository-relative file path.
    :param repository_root: The repository to read in.
    :return: The file content, or ``None`` when the file is absent at the reference.
    """
    result = _git(repository_root, "show", f"{reference}:{path}")
    if result.returncode != 0:
        return None
    return result.stdout


def plan_identifiers_at_reference(
    reference: str, repository_root: Path | None = None
) -> list[str]:
    """
    List every plan with a manifest at a git reference.

    :param reference: The git reference to list through.
    :param repository_root: The repository to list in.
    :return: The plan identifiers, sorted.
    """
    listing = _git(
        repository_root, "ls-tree", "-r", "--name-only", reference
    ).stdout.splitlines()
    identifiers = [
        match.group(1)
        for path in listing
        if (match := PLAN_MANIFEST_PATH_PATTERN.match(path))
    ]
    return sorted(identifiers)
