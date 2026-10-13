"""
Which branches in flight the integration branch carries at all.

The integration branch is worked from, so what it carries is a choice about what to work
with ahead of review rather than a property of the branches: a pull request is in scope
when it carries one of the scope's labels, or when its own commits change nothing but the
tooling - which the files say the same way every time, whether or not anybody labelled it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stack import Branch


class IntegrationScopeSetting(StrEnum):
    """
    The configuration keys a scope is read from, in either configuration file.
    """

    LABELS = "integration_scope_labels"
    """The pull request labels that put a branch in scope."""

    TOOLING_PATHS = "tooling_paths"
    """The path prefixes below which a changed file belongs to the tooling."""

    SHARED_PATHS = "shared_paths"
    """The path prefixes the tooling and the software both change."""


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


@dataclass(frozen=True)
class IntegrationScope:
    """
    What a branch has to be for the integration branch to carry it.
    """

    labels: frozenset[str]
    """The pull request labels that put a branch in scope, whatever it changes."""

    tooling_paths: tuple[str, ...]
    """Prefixes, from the repository root, of the paths that belong to the tooling. A
    trailing ``/`` keeps a directory from also matching a file named like it."""

    shared_paths: tuple[str, ...]
    """Prefixes of the paths the tooling and the software both change, read before
    :attr:`tooling_paths` so a shared path inside a tooling directory is still shared."""

    @classmethod
    def everything(cls) -> IntegrationScope:
        """:return: The scope of a configuration that names none, which carries every
        branch."""
        return cls(labels=frozenset(), tooling_paths=(), shared_paths=())

    @classmethod
    def from_values(cls, values: Mapping[str, object]) -> IntegrationScope:
        """
        Read a scope out of the layered configuration.

        :param values: The configuration, with any key absent read as naming nothing.
        :return: The scope it describes.
        """
        return cls(
            labels=frozenset(values.get(IntegrationScopeSetting.LABELS, ())),
            tooling_paths=tuple(values.get(IntegrationScopeSetting.TOOLING_PATHS, ())),
            shared_paths=tuple(values.get(IntegrationScopeSetting.SHARED_PATHS, ())),
        )

    @property
    def carries_everything(self) -> bool:
        """:return: Whether no branch is ever out of scope."""
        return not self.labels and not self.tooling_paths

    def __str__(self) -> str:
        """:return: The scope as one line, the way a configuration listing prints it."""
        return (
            f"labels {', '.join(sorted(self.labels))}; "
            f"tooling paths {', '.join(self.tooling_paths)}; "
            f"shared paths {', '.join(self.shared_paths)}"
        )

    def __bool__(self) -> bool:
        """:return: Whether this scope names anything at all, so a configuration that
        names none reads as having no such setting, like any other empty one."""
        return not self.carries_everything

    @property
    def reads_changed_paths(self) -> bool:
        """:return: Whether what a branch changes can put it in scope at all."""
        return bool(self.tooling_paths)

    def subject_of(self, path: str) -> PathSubject:
        """
        :param path: A changed path, from the repository root.
        :return: The part of the repository it belongs to.
        """
        if path.startswith(self.shared_paths):
            return PathSubject.SHARED
        if path.startswith(self.tooling_paths):
            return PathSubject.TOOLING
        return PathSubject.SOFTWARE

    def is_a_tooling_change(self, paths: Iterable[str]) -> bool:
        """
        Read changed paths as a tooling change only when they touch the tooling and
        nothing of the software, so an incidental edit to one hook does not bring a
        feature in with it.

        :param paths: Every path a change touches.
        :return: Whether the change is the tooling's and nothing else's.
        """
        subjects = {self.subject_of(path) for path in paths}
        return PathSubject.TOOLING in subjects and PathSubject.SOFTWARE not in subjects

    def covers(self, branch: Branch) -> bool:
        """
        :param branch: The branch to decide about, its :attr:`~stack.Branch.changed_paths`
            read beforehand.
        :return: Whether the integration branch may carry it.
        """
        if self.carries_everything:
            return True
        if self.labels.intersection(branch.labels):
            return True
        return self.is_a_tooling_change(branch.changed_paths)
