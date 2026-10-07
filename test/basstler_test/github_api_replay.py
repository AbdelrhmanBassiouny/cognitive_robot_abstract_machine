"""
A stand-in for GitHub's REST API, answering the calls the package's client makes from
state a test declares, so the client's own request code runs with no network.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from basstler.maintenance_constants import GITHUB_API_ROOT
from basstler.maintenance_github import AUTHENTICATED_USER_PATH
from basstler.repository import Repository

REPLAYED_LOGIN = "stub-user"
"""
The login the stand-in reports for whatever credential a request carries.
"""

REPLAYED_REPOSITORY = Repository(REPLAYED_LOGIN, "octo-repo")
"""
The repository whose labels the stand-in serves, owned by that login.
"""


class HttpMethod(StrEnum):
    """
    The request methods the replayed calls are told apart by.
    """

    GET = "GET"
    """
    A read.
    """

    POST = "POST"
    """
    A creation.
    """


@dataclass(frozen=True)
class RecordedRequest:
    """
    One request the client made, kept so a test can assert on it.
    """

    method: str
    """
    The HTTP method.
    """

    path: str
    """
    The path below the API root, without its query.
    """

    payload: Any
    """
    The decoded JSON body, ``None`` for a read.
    """


@dataclass(frozen=True)
class ReplayedResponse:
    """
    What ``urlopen`` hands back: a context manager whose body is read once.
    """

    body: Any
    """
    The JSON document the call answers with.
    """

    def __enter__(self) -> ReplayedResponse:
        """:return: This response."""
        return self

    def __exit__(self, *exception: object) -> None:
        """Nothing to release."""

    def read(self) -> bytes:
        """:return: The body, encoded the way the API sends it."""
        return json.dumps(self.body).encode()


@dataclass
class UnexpectedRequestError(AssertionError):
    """
    Raised for a request this stand-in does not answer, so a client that changes the
    call it makes fails loudly rather than reading an invented answer.
    """

    request: RecordedRequest
    """
    The request nothing answers.
    """


@dataclass
class ReplayingGitHubApi:
    """
    Answers ``GET /user`` and a repository's label listing and creation, from the state
    declared here; every request made is recorded.
    """

    login: str = REPLAYED_LOGIN
    """
    Who the credential belongs to.
    """

    repository: Repository = REPLAYED_REPOSITORY
    """
    The one repository whose labels are served.
    """

    labels: set[str] = field(default_factory=set)
    """
    The labels the repository carries, growing as the client creates more.
    """

    requests: list[RecordedRequest] = field(default_factory=list)
    """
    Every request made, in order.
    """

    @property
    def labels_path(self) -> str:
        """:return: Where the repository's labels are listed and created."""
        return f"/repos/{self.repository}/labels"

    def created_labels(self) -> list[Any]:
        """:return: The body of every label creation, in order."""
        return [
            request.payload
            for request in self.requests
            if request.method == HttpMethod.POST and request.path == self.labels_path
        ]

    def __call__(self, request: urllib.request.Request) -> ReplayedResponse:
        """
        Answer one request as ``urllib.request.urlopen`` would.

        :param request: The request the client built.
        :return: The response.
        :raises UnexpectedRequestError: If nothing here answers that request.
        """
        address = urllib.parse.urlsplit(request.full_url.removeprefix(GITHUB_API_ROOT))
        recorded = RecordedRequest(
            method=request.get_method(),
            path=address.path,
            payload=None if request.data is None else json.loads(request.data),
        )
        self.requests.append(recorded)
        if (recorded.method, recorded.path) == (
            HttpMethod.GET,
            AUTHENTICATED_USER_PATH,
        ):
            return ReplayedResponse({"login": self.login})
        if (recorded.method, recorded.path) == (HttpMethod.GET, self.labels_path):
            return ReplayedResponse(self.label_page(address.query))
        if (recorded.method, recorded.path) == (HttpMethod.POST, self.labels_path):
            self.labels.add(recorded.payload["name"])
            return ReplayedResponse(recorded.payload)
        raise UnexpectedRequestError(recorded)

    def label_page(self, query: str) -> list[dict[str, str]]:
        """
        :param query: The listing's query, carrying ``page`` and ``per_page``.
        :return: That page of the label listing, in name order.
        """
        parameters = urllib.parse.parse_qs(query)
        size = int(parameters["per_page"][0])
        start = (int(parameters["page"][0]) - 1) * size
        return [{"name": name} for name in sorted(self.labels)[start : start + size]]
