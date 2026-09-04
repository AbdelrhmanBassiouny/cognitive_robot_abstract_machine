#!/usr/bin/env python3
"""
Read the live pull request state the dashboards cross-check against, over GitHub's REST
API.

The session-driven skill gathers this through its GitHub tools, following
``pr-data-fetching.md``; this module is the same procedure as code - one bulk,
paginated listing per repository rather than a call per item - so the headless site
build (``build_site.py``) can gather it unattended.

Also carries the small write the site build needs: pointing GitHub Pages at the branch
the built site is pushed to, so a fork publishes with no settings visit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from build_dashboard import PullRequestState

# %% the transport

GITHUB_API_BASE_URL = "https://api.github.com"
"""
The REST API root every request below is resolved against.
"""

GITHUB_API_VERSION = "2022-11-28"
"""The REST API version this module's field expectations are pinned to."""

GITHUB_TOKEN_VARIABLE = "GITHUB_TOKEN"
"""The environment variable a workflow supplies the API credential in.

Named here so the workflow and this module cannot disagree about it."""

JSON_MEDIA_TYPE = "application/vnd.github+json"
"""
The media type asking GitHub for its JSON representation.
"""

USER_AGENT = "plan-dashboard-site-build"
"""
How this module identifies itself to GitHub, which requires a user agent.
"""


class RequestHeader(StrEnum):
    """The headers a request to GitHub carries."""

    ACCEPT = "Accept"
    """
    Names the representation asked for.
    """

    AUTHORIZATION = "Authorization"
    """
    Carries the bearer token, when there is one.
    """

    API_VERSION = "X-GitHub-Api-Version"
    """
    Pins the response shape to the version the fields below were read against.
    """

    USER_AGENT = "User-Agent"
    """
    Identifies the caller, which GitHub requires of every request.
    """

    CONTENT_TYPE = "Content-Type"
    """
    Names the representation of a request body, on the calls that send one.
    """


class HttpMethod(StrEnum):
    """The HTTP methods this module sends."""

    GET = "GET"
    """
    Reads a resource.
    """

    POST = "POST"
    """
    Creates one that does not exist yet.
    """

    PUT = "PUT"
    """
    Replaces one that does.
    """


@dataclass(frozen=True)
class RepositoryEndpoints:
    """
    The REST paths this tooling addresses for one repository.

    Built here rather than spelled at each call, so a path appears once and a caller
    names what it wants instead of composing it.
    """

    repository: str
    """
    The ``owner/name`` the paths address.
    """

    @property
    def pull_requests(self) -> str:
        """:return: The pull request listing endpoint."""
        return f"repos/{self.repository}/pulls"

    def issue(self, number: int) -> str:
        """
        :param number: An issue number - a pull request stored under the same number
            resolves here too.
        :return: That issue's endpoint.
        """
        return f"repos/{self.repository}/issues/{number}"

    @property
    def pages(self) -> str:
        """:return: The repository's GitHub Pages configuration endpoint."""
        return f"repos/{self.repository}/pages"


@dataclass
class GitHubApi:
    """
    Read access to GitHub's REST API.

    A subclass overriding :meth:`get` stands in for the live API wherever a caller
    should not reach the network.
    """

    token: str | None = None
    """The credential to authenticate with, or ``None`` for anonymous access."""

    base_url: str = GITHUB_API_BASE_URL
    """The API root requests are resolved against."""

    def get(self, path: str, parameters: Mapping[str, str] | None = None) -> Any:
        """
        Fetch one API path.

        :param path: The path below the API root, without a leading slash.
        :param parameters: The query parameters to send, if any.
        :return: The decoded JSON response.
        """
        return self._request(HttpMethod.GET, path, parameters=parameters)

    def find(self, path: str) -> Any | None:
        """
        Fetch one API path whose absence is an ordinary outcome rather than an error.

        :param path: The path below the API root, without a leading slash.
        :return: The decoded JSON response, or ``None`` if GitHub has no such resource.
        """
        try:
            return self.get(path)
        except HTTPError as error:
            if error.code != HTTPStatus.NOT_FOUND:
                raise
            return None

    def send(self, method: HttpMethod, path: str, body: Mapping[str, Any]) -> Any:
        """
        Send one writing request.

        :param method: The HTTP method to send it with.
        :param path: The path below the API root, without a leading slash.
        :param body: The JSON body to send.
        :return: The decoded JSON response, or ``None`` when GitHub answers with none.
        """
        return self._request(method, path, body=body)

    def _request(
        self,
        method: HttpMethod,
        path: str,
        parameters: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        """
        Send one request and decode its response.

        :param method: The HTTP method to send it with.
        :param path: The path below the API root, without a leading slash.
        :param parameters: The query parameters to send, if any.
        :param body: The JSON body to send, if any.
        :return: The decoded JSON response, or ``None`` when it carries none.
        """
        url = f"{self.base_url}/{path}"
        if parameters:
            url = f"{url}?{urlencode(dict(parameters))}"
        headers = {
            RequestHeader.ACCEPT.value: JSON_MEDIA_TYPE,
            RequestHeader.API_VERSION.value: GITHUB_API_VERSION,
            RequestHeader.USER_AGENT.value: USER_AGENT,
        }
        if self.token:
            headers[RequestHeader.AUTHORIZATION.value] = f"Bearer {self.token}"
        encoded_body = None
        if body is not None:
            encoded_body = json.dumps(dict(body)).encode()
            headers[RequestHeader.CONTENT_TYPE.value] = JSON_MEDIA_TYPE
        request = Request(url, data=encoded_body, headers=headers, method=method.value)
        with urlopen(request) as response:
            content = response.read()
        return json.loads(content) if content else None


# %% pull request state


class PullRequestField(StrEnum):
    """The pull request fields the dashboards read.

    The same names serve both directions: GitHub's own response carries them, and
    ``pr_data.json`` records them under exactly these keys."""

    NUMBER = "number"
    """
    The pull request's number in its repository.
    """

    STATE = "state"
    """
    Open or closed, which does not distinguish merged from closed unmerged.
    """

    DRAFT = "draft"
    """
    Whether it is still a draft.
    """

    MERGED_AT = "merged_at"
    """
    When it merged, and the only field that says it did.
    """

    LABELS = "labels"
    """
    The labels it carries, as objects rather than names.
    """


class LabelField(StrEnum):
    """The fields of one label object in a pull request's response."""

    NAME = "name"
    """
    The label's name, which is what this tooling matches on.
    """


class IssueField(StrEnum):
    """The issue fields this module reads."""

    URL = "html_url"
    """
    The issue's browser URL, which a dashboard's tracking link points at.
    """


class PullRequestListParameter(StrEnum):
    """The query parameters the pull request listing endpoint is called with."""

    STATE = "state"
    """
    Which pull requests to return.
    """

    PER_PAGE = "per_page"
    """
    How many to return per page.
    """

    PAGE = "page"
    """
    Which page to return.
    """


class PullRequestListFilter(StrEnum):
    """Which pull requests the listing endpoint returns."""

    ALL = "all"
    """Open and closed alike.

    The dashboards classify merged, closed-unmerged and open items apart, so all three
    must come back."""


PULL_REQUESTS_PER_PAGE = 100
"""How many pull requests one listing page asks for - GitHub's maximum.

A page shorter than this is the last one, which is how pagination ends."""


@dataclass(frozen=True)
class PullRequest:
    """
    One pull request's live state, as GitHub reports it.
    """

    number: int
    """
    The pull request's number in its repository.
    """

    state: PullRequestState
    """GitHub's own coarse-grained state, which does not distinguish a merged pull
    request from one closed unmerged."""

    draft: bool
    """
    Whether the pull request is currently a draft.
    """

    merged_at: str | None
    """The merge timestamp, or ``None`` if GitHub recorded no merge."""

    labels: tuple[str, ...]
    """
    The pull request's labels, by name.
    """

    @classmethod
    def from_json(cls, detail: Mapping[str, Any]) -> PullRequest:
        """
        Build a pull request from one entry of GitHub's listing response.

        :param detail: One pull request object from the API.
        :return: Its live state.
        """
        return cls(
            number=detail[PullRequestField.NUMBER],
            state=PullRequestState(detail[PullRequestField.STATE]),
            draft=bool(detail.get(PullRequestField.DRAFT, False)),
            merged_at=detail.get(PullRequestField.MERGED_AT),
            labels=tuple(
                label[LabelField.NAME]
                for label in detail.get(PullRequestField.LABELS) or ()
            ),
        )

    def to_pull_request_data_entry(self) -> dict[str, Any]:
        """
        Render this state as one ``pr_data.json`` entry.

        ``merged_at`` is always written, ``null`` included: without it a closed entry
        is rejected outright rather than silently read as unmerged.

        :return: The entry the dashboard scripts consume.
        """
        return {
            PullRequestField.STATE.value: self.state.value,
            PullRequestField.DRAFT.value: self.draft,
            PullRequestField.MERGED_AT.value: self.merged_at,
            PullRequestField.LABELS.value: list(self.labels),
        }


def fetch_pull_requests(repository: str, api: GitHubApi) -> dict[str, PullRequest]:
    """
    Fetch every pull request of one repository, in bulk.

    One paginated listing rather than a call per referenced item: a plan can reference
    dozens, and the listing already carries every field the dashboards read.

    :param repository: The repository as ``owner/name``.
    :param api: The transport to read through.
    :return: Its pull requests, keyed by number as a string.
    """
    endpoints = RepositoryEndpoints(repository)
    pull_requests: dict[str, PullRequest] = {}
    page_number = 1
    while True:
        page = api.get(
            endpoints.pull_requests,
            {
                PullRequestListParameter.STATE.value: PullRequestListFilter.ALL.value,
                PullRequestListParameter.PER_PAGE.value: str(PULL_REQUESTS_PER_PAGE),
                PullRequestListParameter.PAGE.value: str(page_number),
            },
        )
        for entry in page:
            pull_request = PullRequest.from_json(entry)
            pull_requests[str(pull_request.number)] = pull_request
        if len(page) < PULL_REQUESTS_PER_PAGE:
            return pull_requests
        page_number += 1


def fetch_issue_url(repository: str, issue_number: int, api: GitHubApi) -> str:
    """
    Resolve an issue number to the URL a link should point at.

    Read through the issues endpoint, which serves a pull request stored under the same
    number too, rather than composing the path - a repository with issues disabled
    keeps its tracking record as a pull request.

    :param repository: The repository as ``owner/name``.
    :param issue_number: The issue to resolve.
    :param api: The transport to read through.
    :return: The issue's browser URL.
    """
    return api.get(RepositoryEndpoints(repository).issue(issue_number))[IssueField.URL]
