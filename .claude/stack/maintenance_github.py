"""
Reading and writing the fork's pull requests.

The reading and the writing halves are declared separately, so a caller that must not
write - the board export - can be handed a reader and provably cannot. Every write here
was probed against the live API first, through a Claude session's own proxied
credential: a pull request's *base branch* was the one write that credential was
refused. That probe never covered this module's own credential - the environment
variable :data:`maintenance_constants.CREDENTIAL_VARIABLES` names, which this module
authenticates its own plain requests with directly rather than through any session
proxy - so :meth:`PullRequestWriter.retarget_base` attempts it rather than assuming the
same refusal, and reports what GitHub itself says rather than a carried-over guess.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from maintenance_board import PullRequestRecord
from maintenance_constants import (
    BASE_RETARGET_REFUSAL_STATUSES,
    CREDENTIAL_VARIABLES,
    GITHUB_API_ROOT,
)
from maintenance_errors import ExternalCallFailed
from stack import Repository


@dataclass
class GitHubCredentialUnavailableError(RuntimeError):
    """
    Raised when no token is available to authenticate the API calls with.
    """

    variables: tuple[str, ...]
    """The environment variables that were consulted."""

    def __str__(self) -> str:
        """:return: What was looked for, so the caller can supply it."""
        return (
            f"no GitHub token: set one of {', '.join(self.variables)}, or run this "
            f"with a caller that has one"
        )


# %% what a pass reads and writes


@dataclass(frozen=True)
class PullRequestReader(ABC):
    """
    Reading the pull-request state a pass derives from.

    Implementations inherit rather than merely match the shape, so one that omits a read
    is refused when it is constructed rather than when the missing call is first made.
    """

    @abstractmethod
    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: Every open pull request on the fork."""

    @abstractmethod
    def pull_request(self, number: int) -> PullRequestRecord:
        """:param number: The pull request to read.
        :return: That pull request."""


@dataclass(frozen=True)
class PullRequestWriter(ABC):
    """
    The writes a pass makes.

    Labels, comments and descriptions were all probed against the live API and found
    available to a Claude session's own credential; retargeting a base was the one write
    that credential was refused. This module's own credential is never proxied through a
    session, so :meth:`retarget_base` attempts the write rather than inheriting that
    refusal, and a caller reads its return value to know whether GitHub allowed it here
    too.
    """

    @abstractmethod
    def replace_labels(self, number: int, labels: Sequence[str]) -> None:
        """:param number: The pull request to write.
        :param labels: The complete label set it must end up with."""

    @abstractmethod
    def add_comment(self, number: int, body: str) -> str:
        """:param number: The pull request to comment on.
        :param body: The comment.
        :return: The comment's URL."""

    @abstractmethod
    def set_description(self, number: int, body: str) -> None:
        """:param number: The pull request to write.
        :param body: The new description."""

    @abstractmethod
    def retarget_base(self, number: int, base: str) -> bool:
        """
        Attempt to retarget a pull request's base branch.

        :param number: The pull request to retarget.
        :param base: The branch it must target instead.
        :return: Whether GitHub allowed it. ``False`` rather than an exception for the
            two refusals a caller cannot do anything about but fall back on: this
            credential refused (``403``), or the pull request is a member of a GitHub
            Stack that must be moved through native Stack mechanics instead (``422``).
        :raises GitHubRequestFailed: For any other refusal.
        """


@dataclass(frozen=True)
class ForkPullRequests(PullRequestReader, PullRequestWriter, ABC):
    """
    Everything a pass does to the fork's pull requests.

    A pass reads state and writes back to the same fork, so the two halves are named
    together wherever both are needed; the board export takes the reading half alone,
    which is what keeps an export from being able to write.
    """


@dataclass
class GitHubRequestFailed(ExternalCallFailed):
    """
    Raised when the API refuses a call this module depends on.
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
        """:return: The request line, as issued."""
        return f"{self.method} {self.path}"


# %% the client that makes the calls


@dataclass(frozen=True)
class GitHubRepository(ForkPullRequests):
    """
    Every pull-request call this executor makes, against one repository.

    ``gh`` is absent from the environment this normally runs in, so the calls are plain
    authenticated requests rather than a CLI wrapper.
    """

    repository: Repository
    """
    The repository to read and write.
    """

    token: str
    """
    The credential the requests authenticate with.
    """

    page_size: int = 100
    """
    How many pull requests to ask for per request.
    """

    @classmethod
    def from_environment(cls, repository: Repository) -> GitHubRepository:
        """
        Build a client from whichever credential the environment carries.

        :param repository: The repository to read and write.
        :return: The client.
        :raises GitHubCredentialUnavailableError: If no token is set.
        """
        for variable in CREDENTIAL_VARIABLES:
            token = os.environ.get(variable)
            if token:
                return cls(repository, token)
        raise GitHubCredentialUnavailableError(CREDENTIAL_VARIABLES)

    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: Every open pull request on the repository, oldest page first."""
        collected: list[PullRequestRecord] = []
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {"state": "open", "per_page": self.page_size, "page": page}
            )
            fetched = self._call("GET", f"/pulls?{query}")
            collected.extend(fetched)
            if len(fetched) < self.page_size:
                return collected
            page += 1

    def pull_request(self, number: int) -> PullRequestRecord:
        """:param number: The pull request to read.
        :return: That pull request."""
        return self._call("GET", f"/pulls/{number}")

    def replace_labels(self, number: int, labels: Sequence[str]) -> None:
        """
        Write a pull request's complete label set.

        :param number: The pull request to write.
        :param labels: The complete set it must end up with, computed by
            :meth:`stack.LabelWrite.replacing` - this call replaces rather than adds.
        """
        self._call("PUT", f"/issues/{number}/labels", {"labels": list(labels)})

    def add_comment(self, number: int, body: str) -> str:
        """:param number: The pull request to comment on.
        :param body: The comment.
        :return: The comment's URL."""
        created = self._call("POST", f"/issues/{number}/comments", {"body": body})
        return str(created["html_url"])

    def set_description(self, number: int, body: str) -> None:
        """
        Rewrite a pull request's description and nothing else.

        :param number: The pull request to write.
        :param body: The new description.
        """
        self._call("PATCH", f"/pulls/{number}", {"body": body})

    def retarget_base(self, number: int, base: str) -> bool:
        """:param number: The pull request to retarget.
        :param base: The branch it must target instead.
        :return: Whether GitHub allowed it.
        :raises GitHubRequestFailed: For any refusal other than the two this call
            treats as a fallback rather than a failure."""
        try:
            self._call("PATCH", f"/pulls/{number}", {"base": base})
            return True
        except GitHubRequestFailed as refused:
            if refused.status in BASE_RETARGET_REFUSAL_STATUSES:
                return False
            raise

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """
        Make one authenticated API call.

        :param method: The HTTP method.
        :param path: The path below the repository, starting with a slash.
        :param payload: The JSON body, absent for a read.
        :return: The decoded response.
        :raises GitHubRequestFailed: If the API answers with an error status.
        """
        request = urllib.request.Request(
            f"{GITHUB_API_ROOT}/repos/{self.repository}{path}",
            method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as refused:
            raise GitHubRequestFailed(
                status=refused.code,
                detail=refused.read().decode(errors="replace"),
                method=method,
                path=path,
            ) from refused
