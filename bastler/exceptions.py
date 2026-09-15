"""
The failure an outside dependency reports, stated once for every tool that has one.

git and the GitHub API are the things this tooling depends on and does not control. What
a caller needs when either refuses is identical - naming the call, saying what went
wrong, and offering a correction if there is one - so the shape is stated here and each
concrete failure supplies its own three answers.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from bastler.dataclass_exception import DataclassException


@dataclass
class ExternalCallFailed(RuntimeError, DataclassException):
    """
    Base for a call to something outside this tooling that a caller depended on.

    Adds the typed context every such call shares - ``status``, ``detail``, and the
    abstract ``call`` a concrete subclass names - to :class:`DataclassException`'s
    generic composition.
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
    @abstractmethod
    def call(self) -> str:
        """
        :return: The call that failed, named the way its own caller named it.
        """


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

    def error_message(self) -> str:
        """
        :return: The call, its status, and the reason given.
        """
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        """
        :return: No git command carries generic advice yet.
        """
        return ""


@dataclass
class GitHubRequestFailed(ExternalCallFailed):
    """
    Raised when the GitHub API refuses a call whose result was depended on.
    """

    method: str = ""
    """
    The HTTP method used.
    """

    path: str = ""
    """
    The API path called, without the host.
    """

    @property
    def call(self) -> str:
        """
        :return: The request line, as issued.
        """
        return f"{self.method} {self.path}"

    def error_message(self) -> str:
        """
        :return: The call, its status, and the reason given.
        """
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        """
        :return: No request carries generic advice yet.
        """
        return ""
