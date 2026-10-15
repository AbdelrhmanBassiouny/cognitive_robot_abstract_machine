"""
Exceptions raised across the personal-notes modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass
class NotesBranchMissingError(RuntimeError):
    """
    Raised when no remote tried holds the personal-notes branch.
    """

    branch: str
    """
    The personal-notes branch that was looked for.
    """

    attempted_remotes: tuple[str, ...]
    """
    Every remote it was fetched from, in order.
    """

    def __str__(self) -> str:
        """
        :return: What was tried, and how to create the branch.
        """
        return (
            f"Branch '{self.branch}' doesn't exist yet (tried: "
            f"{', '.join(self.attempted_remotes)}). Run "
            "./create-personal-notes-branch.sh first."
        )


@dataclass
class UnsafeNotesPathError(ValueError):
    """
    Raised when a path to write on the personal-notes branch could leave it.
    """

    path: PurePosixPath
    """
    The refused path.
    """

    def __str__(self) -> str:
        """
        :return: The path, and what a path must look like instead.
        """
        return (
            f"{self.path} must be relative to the notes branch's root, with no '..' "
            "component"
        )
