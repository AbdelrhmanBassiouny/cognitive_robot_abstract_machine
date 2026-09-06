"""
Reading and writing the fork's pull requests.

The reading and the writing halves are declared separately, so a caller that must not
write - the board export - can be handed a reader and provably cannot. Every write here
was probed against the live API first: a pull request's *base branch* is the one the
credential a session carries is refused, which is why retargeting is reported for a
caller to perform rather than performed.
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
from enum import StrEnum
from typing import Any

from maintenance_board import PullRequestRecord
from maintenance_constants import CREDENTIAL_VARIABLES, GITHUB_API_ROOT
from exceptions import ExternalCallFailed
from stack import Repository

CheckRunRecord = Mapping[str, Any]
"""
One check run as the REST API answers it, before any field is read.
"""

ChangedFileRecord = Mapping[str, Any]
"""
One file a pull request changes, as the REST API answers it.
"""


class ChangedFileField(StrEnum):
    """
    The keys one changed file is answered under.
    """

    PATH = "filename"
    """Where the file sits, from the repository root."""


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
class PullRequestFiles(ABC):
    """
    Which files one pull request changes.

    Declared apart from the reads a pass makes because nothing that derives the stack
    asks: a pull request's own record carries no file list, so this is a call of its own
    per pull request rather than a field of one already fetched.
    """

    @abstractmethod
    def changed_paths(self, number: int) -> list[str]:
        """:param number: The pull request to read.
        :return: Every path it changes, from the repository root."""


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
class CandidatePullRequests(ABC):
    """
    Opening a pull request only so a build gets a run, and reading what that run said.

    Declared apart from the reads and writes a maintenance pass makes, because nothing
    that maintains the stack does any of this: a candidate exists to be judged and closed
    unmerged, and a pass handed this interface could open one by mistake.
    """

    @abstractmethod
    def open_pull_request(self, title: str, head: str, base: str, body: str) -> int:
        """:param title: The pull request's title.
        :param head: The branch to be judged.
        :param base: The branch it is opened against.
        :param body: The description.
        :return: The new pull request's number."""

    @abstractmethod
    def close_pull_request(self, number: int) -> None:
        """:param number: The pull request to close without merging."""

    @abstractmethod
    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """:param reference: The commit or branch to read the checks of.
        :return: Every check run reported against it."""


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
class GitHubRepository(ForkPullRequests, PullRequestFiles, CandidatePullRequests):
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

    def changed_paths(self, number: int) -> list[str]:
        """
        Read every path one pull request changes.

        :param number: The pull request to read.
        :return: The paths, from the repository root, oldest page first.
        """
        collected: list[str] = []
        page = 1
        while True:
            query = urllib.parse.urlencode({"per_page": self.page_size, "page": page})
            fetched: list[ChangedFileRecord] = self._call(
                "GET", f"/pulls/{number}/files?{query}"
            )
            collected.extend(str(file[ChangedFileField.PATH]) for file in fetched)
            if len(fetched) < self.page_size:
                return collected
            page += 1

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

    def open_pull_request(self, title: str, head: str, base: str, body: str) -> int:
        """
        Open a pull request, so that something judges the branch it names.

        :param title: The pull request's title.
        :param head: The branch to be judged.
        :param base: The branch it is opened against.
        :param body: The description.
        :return: The new pull request's number.
        """
        opened = self._call(
            "POST", "/pulls", {"title": title, "head": head, "base": base, "body": body}
        )
        return int(opened["number"])

    def close_pull_request(self, number: int) -> None:
        """
        Close a pull request without merging it.

        :param number: The pull request to close.
        """
        self._call("PATCH", f"/pulls/{number}", {"state": "closed"})

    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """
        Read every check run reported against a commit or a branch.

        A branch answers with the checks on whatever it points at now, which is what
        lets a branch's own state be asked for without first resolving its head.

        :param reference: The commit or branch to read.
        :return: The check runs, which may be none while the first is still queueing.
        """
        answered = self._call("GET", f"/commits/{reference}/check-runs?per_page=100")
        return list(answered["check_runs"])

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
