"""
Tests for reading live pull request state over GitHub's REST API.

The transport is replaced with a recording fake, so no network access is involved - what
is under test is the pagination, the field reading, and the ``pr_data.json`` entry each
pull request renders as.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest

from build_dashboard import PullRequestLabel, PullRequestRecord, PullRequestState
from github_api import (
    PULL_REQUESTS_PER_PAGE,
    GitHubApi,
    IssueField,
    PullRequest,
    PullRequestField,
    PullRequestListFilter,
    PullRequestListParameter,
    RepositoryEndpoints,
    fetch_issue_url,
    fetch_pull_requests,
)

REPOSITORY = "owner/repository"
ENDPOINTS = RepositoryEndpoints(REPOSITORY)
TRACKING_ISSUE_NUMBER = 9
MERGE_TIMESTAMP = "2026-08-01T00:00:00Z"
UNCLASSIFIABLE_STATE = "sideways"


@dataclass
class RecordingApi(GitHubApi):
    """
    A transport serving prepared pages and recording what was asked of it.
    """

    pages: list[list[dict[str, Any]]] = field(default_factory=list)
    """
    The listing pages to serve, in order.
    """

    issues: dict[str, Any] = field(default_factory=dict)
    """
    The issue responses to serve, keyed by path.
    """

    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    """
    Every path and parameter set asked for, in order.
    """

    def get(self, path: str, parameters: Mapping[str, str] | None = None) -> Any:
        self.requests.append((path, dict(parameters or {})))
        if path in self.issues:
            return self.issues[path]
        page_number = int(parameters[PullRequestListParameter.PAGE])
        if page_number > len(self.pages):
            return []
        return self.pages[page_number - 1]


def test_a_pull_request_reads_every_field_the_dashboards_need(pull_request_detail):
    """
    The fields the dashboards classify on all survive the read.
    """
    pull_request = PullRequest.from_json(
        pull_request_detail(
            7,
            state=PullRequestState.CLOSED,
            draft=True,
            merged_at=MERGE_TIMESTAMP,
            labels=(PullRequestLabel.BUG, PullRequestLabel.MERGED),
        )
    )

    assert pull_request.number == 7
    assert pull_request.state is PullRequestState.CLOSED
    assert pull_request.draft is True
    assert pull_request.merged_at == MERGE_TIMESTAMP
    assert pull_request.labels == (PullRequestLabel.BUG, PullRequestLabel.MERGED)


def test_an_entry_is_read_back_by_the_dashboard_as_the_same_state(pull_request_detail):
    """
    A rendered entry round-trips through the reader the dashboards actually parse it
    with, rather than being asserted against a second copy of the key names.
    """
    pull_request = PullRequest.from_json(
        pull_request_detail(
            7,
            state=PullRequestState.CLOSED,
            draft=False,
            merged_at=MERGE_TIMESTAMP,
            labels=(PullRequestLabel.BUG,),
        )
    )

    record = PullRequestRecord.from_mapping(pull_request.to_pull_request_data_entry())

    assert record.state is PullRequestState.CLOSED
    assert record.draft is False
    assert record.was_merged is True
    assert record.labels == [PullRequestLabel.BUG]


def test_a_closed_entry_carries_its_null_merge_timestamp_explicitly(
    pull_request_detail,
):
    """
    ``merged_at`` is written even when null: without the key a closed entry is rejected
    rather than read as unmerged.
    """
    entry = PullRequest.from_json(
        pull_request_detail(7, state=PullRequestState.CLOSED)
    ).to_pull_request_data_entry()

    assert entry[PullRequestField.MERGED_AT] is None
    assert PullRequestRecord.from_mapping(entry).was_merged is False


def test_fetching_asks_for_open_and_closed_pull_requests_alike(pull_request_detail):
    """The listing must cover closed pull requests too - a merged item is classified
    from one."""
    api = RecordingApi(pages=[[pull_request_detail(1)]])

    fetch_pull_requests(REPOSITORY, api)

    path, parameters = api.requests[0]
    assert path == ENDPOINTS.pull_requests
    assert parameters[PullRequestListParameter.STATE] == PullRequestListFilter.ALL
    assert parameters[PullRequestListParameter.PER_PAGE] == str(PULL_REQUESTS_PER_PAGE)


def test_fetching_stops_at_the_first_short_page(pull_request_detail):
    """
    A page shorter than the page size is the last one, so nothing is asked for after it.
    """
    api = RecordingApi(
        pages=[
            [pull_request_detail(number) for number in range(PULL_REQUESTS_PER_PAGE)],
            [pull_request_detail(1000)],
        ]
    )

    pull_requests = fetch_pull_requests(REPOSITORY, api)

    assert len(pull_requests) == PULL_REQUESTS_PER_PAGE + 1
    assert "1000" in pull_requests
    assert [
        parameters[PullRequestListParameter.PAGE] for _, parameters in api.requests
    ] == ["1", "2"]


def test_fetching_keys_pull_requests_by_their_number_as_a_string(pull_request_detail):
    """
    ``pr_data.json`` is keyed by the number as a string, which is how a manifest's item
    is looked up in it.
    """
    api = RecordingApi(pages=[[pull_request_detail(42)]])

    assert list(fetch_pull_requests(REPOSITORY, api)) == ["42"]


def test_a_tracking_issue_resolves_to_the_url_github_reports():
    """The link comes from GitHub's own field, never from a composed path - a
    repository with issues disabled keeps the record as a pull request."""
    reported_url = f"https://github.com/{REPOSITORY}/pull/{TRACKING_ISSUE_NUMBER}"
    api = RecordingApi(
        issues={ENDPOINTS.issue(TRACKING_ISSUE_NUMBER): {IssueField.URL: reported_url}}
    )

    assert fetch_issue_url(REPOSITORY, TRACKING_ISSUE_NUMBER, api) == reported_url


def test_an_unknown_state_is_rejected(pull_request_detail):
    """
    A state the dashboards cannot classify fails at the read rather than rendering as
    something it is not.
    """
    detail = pull_request_detail(1)
    detail[PullRequestField.STATE.value] = UNCLASSIFIABLE_STATE

    with pytest.raises(ValueError):
        PullRequest.from_json(detail)
