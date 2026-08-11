"""
The failure an outside dependency reports, stated once for every tool that has one.

git and the GitHub API are the things this tooling depends on and does not control. What
a caller needs when either refuses is identical, so it is stated here and each concrete
failure differs only in how it names the call.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExternalCallFailed(RuntimeError):
    """
    Base for a call to something outside this tooling that a caller depended on.

    Mirrors ``krrood``'s dataclass-exception idiom - typed context fields, a message the
    base composes - without importing it, since everything here is reachable from
    ``SessionStart`` and depends on the standard library alone.
    """

    status: int
    """
    The status the call came back with.
    """

    detail: str
    """
    What the far side said about it.
    """

    @property
    def call(self) -> str:
        """
        :return: The call that failed, named the way its own caller named it.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """
        :return: The call, its status, and the reason given.
        """
        return f"{self.call} failed with {self.status}: {self.detail}"
