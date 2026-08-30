#!/usr/bin/env python3
"""
Read the live pull request state the dashboards cross-check against, over GitHub's REST
API.

The session-driven skill gathers this through its GitHub tools, following
``pr-data-fetching.md``; this module is the same procedure as code - one bulk,
paginated listing per repository rather than a call per item - so the headless site
build (``build_site.py``) can gather it unattended.

Read-only: nothing here writes to GitHub.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping
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


class RequestHeader(StrEnum):
    """The headers every request to GitHub carries."""

    ACCEPT = "Accept"
    AUTHORIZATION = "Authorization"
    API_VERSION = "X-GitHub-Api-Version"
    USER_AGENT = "User-Agent"


JSON_MEDIA_TYPE = "application/vnd.github+json"
"""
The media type asking GitHub for its JSON representation.
"""

USER_AGENT = "plan-dashboard-site-build"
"""
How this module identifies itself to GitHub, which requires a user agent.
"""


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
        :return: The decoded JSON body.
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
        with urlopen(Request(url, headers=headers)) as response:
            return json.load(response)


# %% pull request state


class PullRequestField(StrEnum):
    """The pull request fields the dashboards read.

    The same names serve both directions: GitHub's own response carries them, and
    ``pr_data.json`` records them under exactly these keys."""

    NUMBER = "number"
    STATE = "state"
    DRAFT = "draft"
    MERGED_AT = "merged_at"
    LABELS = "labels"


LABEL_NAME_FIELD = "name"
"""
The field a label object carries its name in.
"""

ISSUE_URL_FIELD = "html_url"
"""
The field an issue carries its browser URL in.
"""


class PullRequestListParameter(StrEnum):
    """The query parameters the pull request listing endpoint is called with."""

    STATE = "state"
    PER_PAGE = "per_page"
    PAGE = "page"


ALL_STATES = "all"
"""The ``state`` value asking for open and closed pull requests alike.

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
    def from_json(cls, payload: Mapping[str, Any]) -> PullRequest:
        """
        Build a pull request from one entry of GitHub's listing response.

        :param payload: One pull request object from the API.
        :return: Its live state.
        """
        return cls(
            number=payload[PullRequestField.NUMBER],
            state=PullRequestState(payload[PullRequestField.STATE]),
            draft=bool(payload.get(PullRequestField.DRAFT, False)),
            merged_at=payload.get(PullRequestField.MERGED_AT),
            labels=tuple(
                label[LABEL_NAME_FIELD]
                for label in payload.get(PullRequestField.LABELS) or ()
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
    pull_requests: dict[str, PullRequest] = {}
    page_number = 1
    while True:
        page = api.get(
            f"repos/{repository}/pulls",
            {
                PullRequestListParameter.STATE.value: ALL_STATES,
                PullRequestListParameter.PER_PAGE.value: str(PULL_REQUESTS_PER_PAGE),
                PullRequestListParameter.PAGE.value: str(page_number),
            },
        )
        for payload in page:
            pull_request = PullRequest.from_json(payload)
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
    return api.get(f"repos/{repository}/issues/{issue_number}")[ISSUE_URL_FIELD]
