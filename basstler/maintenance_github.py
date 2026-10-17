"""
Reaching GitHub's REST API, and reading and writing a repository's pull requests and
labels through it.

The reading and the writing halves are declared separately, so a caller that must not
write - the board export - can be handed a reader and provably cannot. Every write here
was probed against the live API first: a pull request's *base branch* is the one the
credential a session carries is refused, which is why retargeting is reported for a
caller to perform rather than performed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from basstler.maintenance_board import PullRequestRecord
from basstler.maintenance_constants import CREDENTIAL_VARIABLES, GITHUB_API_ROOT
from basstler.maintenance_errors import ExternalCallFailed
from basstler.repository import Repository
from basstler.repository_label import RepositoryLabel


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
            f"no GitHub token: set one of {', '.join(self.variables)}, or install the "
            f"gh CLI and run 'gh auth login'"
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
    The three writes a pass makes, each one probed against the live API first.

    Every one of them is available to the credential a session carries; a pull request's
    *base branch* is the single write that is not, which is why reparenting is the
    caller's job and none of this is.
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


@dataclass(frozen=True)
class ForkPullRequests(PullRequestReader, PullRequestWriter, ABC):
    """
    Everything a pass does to the fork's pull requests.

    A pass reads state and writes back to the same fork, so the two halves are named
    together wherever both are needed; the board export takes the reading half alone,
    which is what keeps an export from being able to write.
    """


@dataclass(frozen=True)
class RepositoryLabels(ABC):
    """
    The labels a repository carries, and adding one it lacks.
    """

    @abstractmethod
    def labels(self) -> set[str]:
        """:return: The name of every label the repository carries."""

    @abstractmethod
    def create_label(self, label: RepositoryLabel) -> None:
        """:param label: The label to add, with its purpose as the description."""


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


AUTHENTICATED_USER_PATH = "/user"
"""
Where the API reports whose credential a request carries.
"""

GITHUB_CLI = "gh"
"""
The GitHub CLI, consulted only for the token it stores once ``gh auth login`` has run.
"""


@dataclass(frozen=True)
class GitHubConnection:
    """
    Authenticated access to GitHub's REST API.

    ``gh`` is absent from some environments this runs in, so every call is a plain
    authenticated request rather than a CLI wrapper; the CLI only lends its stored token
    where no token variable is set.
    """

    token: str
    """
    The credential the requests authenticate with.
    """

    api_root: str = GITHUB_API_ROOT
    """
    The API host, overridable for a GitHub Enterprise deployment.
    """

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str]
    ) -> GitHubConnection | None:
        """
        Build a connection from whichever credential *environment* offers.

        :param environment: The variables to read the token from, including the ``PATH``
            the CLI is looked up on.
        :return: The connection, or ``None`` when no credential is available.
        """
        for variable in CREDENTIAL_VARIABLES:
            token = environment.get(variable)
            if token:
                return cls(token)
        if shutil.which(GITHUB_CLI, path=environment.get("PATH")) is None:
            return None
        stored = subprocess.run(
            [GITHUB_CLI, "auth", "token"],
            capture_output=True,
            text=True,
            env=dict(environment),
        )
        token = stored.stdout.strip()
        if stored.returncode != 0 or not token:
            return None
        return cls(token)

    def authenticated_login(self) -> str:
        """:return: The login the credential belongs to."""
        return str(self.request("GET", AUTHENTICATED_USER_PATH)["login"])

    def request(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """
        Make one authenticated API call.

        :param method: The HTTP method.
        :param path: The path below the API root, starting with a slash.
        :param payload: The JSON body, absent for a read.
        :return: The decoded response.
        :raises GitHubRequestFailed: If the API answers with an error status.
        """
        request = urllib.request.Request(
            f"{self.api_root}{path}",
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


@dataclass(frozen=True)
class GitHubRepository(ForkPullRequests, RepositoryLabels):
    """
    Every pull-request and label call this tooling makes, against one repository.
    """

    repository: Repository
    """
    The repository to read and write.
    """

    connection: GitHubConnection
    """
    The authenticated API access the calls go through.
    """

    page_size: int = 100
    """
    How many pull requests or labels to ask for per request.
    """

    @classmethod
    def from_environment(cls, repository: Repository) -> GitHubRepository:
        """
        Build a client from whichever credential the environment carries.

        :param repository: The repository to read and write.
        :return: The client.
        :raises GitHubCredentialUnavailableError: If no credential is available.
        """
        connection = GitHubConnection.from_environment(os.environ)
        if connection is None:
            raise GitHubCredentialUnavailableError(CREDENTIAL_VARIABLES)
        return cls(repository, connection)

    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: Every open pull request on the repository, oldest page first."""
        return self._every_page("/pulls", state="open")

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

    def labels(self) -> set[str]:
        """:return: The name of every label the repository carries."""
        return {label["name"] for label in self._every_page("/labels")}

    def create_label(self, label: RepositoryLabel) -> None:
        """:param label: The label to add, with its purpose as the description."""
        self._call(
            "POST", "/labels", {"name": label.value, "description": label.purpose}
        )

    def _every_page(self, path: str, **filters: str) -> list[Any]:
        """
        Read a listing to its end, one page at a time.

        :param path: The listing's path below the repository.
        :param filters: Query parameters narrowing the listing.
        :return: Every entry, oldest page first.
        """
        collected: list[Any] = []
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {**filters, "per_page": self.page_size, "page": page}
            )
            fetched = self._call("GET", f"{path}?{query}")
            collected.extend(fetched)
            if len(fetched) < self.page_size:
                return collected
            page += 1

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """
        Make one call against this repository.

        :param method: The HTTP method.
        :param path: The path below the repository, starting with a slash.
        :param payload: The JSON body, absent for a read.
        :return: The decoded response.
        """
        return self.connection.request(
            method, f"/repos/{self.repository}{path}", payload
        )
