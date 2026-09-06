"""
What the files a pull request changed say the change is about.

The fork's tooling label was applied by hand, so a branch only carried the priority
:class:`~stack.BranchPriority` reads once somebody remembered to say so. The files a
pull request changed already answer the question, and answer it the same way every
time, which is what this reads them for.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from stack import Configuration

# %% what one path says


class PathSubject(StrEnum):
    """
    Which part of the repository one changed path belongs to.
    """

    TOOLING = "tooling"
    """The fork's own stack, integration and dashboard tooling."""

    SOFTWARE = "software"
    """The software the repository exists to build."""

    SHARED = "shared"
    """A path the other two both change, which settles neither way."""


# %% what a whole change says


@dataclass(frozen=True)
class ChangedPaths:
    """
    The paths one pull request changed, and what they make it.
    """

    paths: tuple[str, ...]
    """Every path the pull request changed, from the repository root."""

    tooling_paths: tuple[str, ...]
    """The prefixes a path below the tooling starts with."""

    shared_paths: tuple[str, ...]
    """The prefixes a path that settles neither way starts with."""

    @classmethod
    def of(cls, paths: Iterable[str], configuration: Configuration) -> ChangedPaths:
        """
        :param paths: Every path the pull request changed.
        :param configuration: The configuration naming where the tooling lives.
        :return: Those paths, ready to be asked what they make the change.
        """
        return cls(
            paths=tuple(paths),
            tooling_paths=configuration.tooling_paths,
            shared_paths=configuration.shared_paths,
        )

    def subject_of(self, path: str) -> PathSubject:
        """
        Read which part of the repository one path belongs to.

        The shared prefixes are read first, so a shared path that happens to sit inside a
        tooling directory is still shared.

        :param path: The path to classify, from the repository root.
        :return: The part it belongs to.
        """
        if any(path.startswith(prefix) for prefix in self.shared_paths):
            return PathSubject.SHARED
        if any(path.startswith(prefix) for prefix in self.tooling_paths):
            return PathSubject.TOOLING
        return PathSubject.SOFTWARE

    @property
    def subjects(self) -> tuple[PathSubject, ...]:
        """:return: What each changed path belongs to, in the order they were given."""
        return tuple(self.subject_of(path) for path in self.paths)

    @property
    def is_a_tooling_change(self) -> bool:
        """
        Whether these paths make the pull request a tooling change.

        Read as *only* the tooling rather than as touching it at all: a branch that also
        changes the software would otherwise take a tooling branch's merge priority from
        an incidental edit to one hook, which is the collision the priority exists to
        decide the other way.

        :return: Whether the change is the tooling's and nothing else's.
        """
        subjects = self.subjects
        return PathSubject.TOOLING in subjects and PathSubject.SOFTWARE not in subjects
