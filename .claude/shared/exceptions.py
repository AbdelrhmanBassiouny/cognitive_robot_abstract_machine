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

    def error_message(self) -> str:
        """
        :return: The call, its status, and the reason given.
        """
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        """
        :return: Advice on how to fix the error, or an empty string if there is none.
        """
        return ""

    def __str__(self) -> str:
        """
        :return: :meth:`error_message`, with :meth:`suggest_correction` appended as a
            trailing ``"Suggestion: ..."`` line when it has one.
        """
        message = self.error_message()
        correction = self.suggest_correction()
        if correction:
            message = f"{message}\nSuggestion: {correction}"
        return message


@dataclass
class GitCommandFailed(ExternalCallFailed):
    """
    Raised when a git command whose result was depended on fails.
    """

    arguments: tuple[str, ...] = ()
    """
    The git subcommand and its arguments, as invoked.
    """

    @property
    def call(self) -> str:
        """
        :return: The git command line, as invoked.
        """
        return f"git {' '.join(self.arguments)}"
