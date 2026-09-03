"""
Tests for the fetch half of :mod:`bastler.pull_request_state`: transport resolution (GitHub CLI,
else a token, else a failure naming both routes), the two transports, and the
orchestration that turns GitHub API payloads into
:class:`~bastler.pull_request_state.PullRequestLiveState`.

All network-free: the transports run against the shared ``gh`` stub or a monkeypatched
opener, and the orchestration against an in-memory fake transport.
"""

from __future__ import annotations

import io
import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import pytest

import bastler.pull_request_state
from bastler.maintenance_constants import GITHUB_API_ROOT, CredentialVariable
from bastler.pull_request_state import (
    EXECUTABLE_SEARCH_PATH_VARIABLE,
    CheckConclusion,
    ClaudeSessionLink,
    CommandGitHubApi,
    GitHubAccessError,
    GitHubApi,
    ListParameter,
    PullRequestFetcher,
    PullRequestField,
    PullRequestListFilter,
    PullRequestState,
    RepositoryEndpoints,
    RequestHeader,
    TokenGitHubApi,
)

from .executable_stubs import ExecutableStubDirectory
from .pull_request_payloads import (
    PullRequestPayload,
    RecordedFakeGitHubApi,
    check_runs_payload,
)
from .test_upstream_reviews import StubEnvironmentVariable

REPOSITORY = "owner/repository"
"""
The repository every fetch in this module addresses.
"""

ENDPOINTS = RepositoryEndpoints(REPOSITORY)
"""
Its endpoints, so a test names a path the same way the production code builds it.
"""

TOKEN = "token-value"
"""
The credential a token-backed test puts in the environment.
"""


def remove_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    :param monkeypatch: pytest's monkeypatch fixture.
    """
    for variable in CredentialVariable:
        monkeypatch.delenv(variable, raising=False)


def put_stub_first_on_path(
    monkeypatch: pytest.MonkeyPatch, stub_bin: ExecutableStubDirectory
) -> None:
    """
    Install the ``gh`` stub and make it the ``gh`` a lookup finds.

    :param monkeypatch: pytest's monkeypatch fixture.
    :param stub_bin: The stub directory to install into.
    """
    stub_bin.install(CommandGitHubApi.EXECUTABLE)
    monkeypatch.setenv(
        EXECUTABLE_SEARCH_PATH_VARIABLE,
        stub_bin.ahead_of(os.environ[EXECUTABLE_SEARCH_PATH_VARIABLE]),
    )


# %% transport resolution


def test_no_cli_and_no_token_fails_naming_both_routes(monkeypatch):
    monkeypatch.setenv(EXECUTABLE_SEARCH_PATH_VARIABLE, "")
    remove_credentials(monkeypatch)
    with pytest.raises(GitHubAccessError) as error:
        GitHubApi.resolve()
    assert CommandGitHubApi.EXECUTABLE in str(error.value)
    for variable in CredentialVariable:
        assert variable in str(error.value)


def test_the_token_transport_is_used_without_the_cli(monkeypatch):
    monkeypatch.setenv(EXECUTABLE_SEARCH_PATH_VARIABLE, "")
    remove_credentials(monkeypatch)
    monkeypatch.setenv(CredentialVariable.GH_TOKEN, TOKEN)
    api = GitHubApi.resolve()
    assert isinstance(api, TokenGitHubApi)
    assert api.token == TOKEN


def test_the_second_credential_variable_is_read_when_the_first_is_absent(monkeypatch):
    monkeypatch.setenv(EXECUTABLE_SEARCH_PATH_VARIABLE, "")
    remove_credentials(monkeypatch)
    monkeypatch.setenv(CredentialVariable.GITHUB_TOKEN, TOKEN)
    api = GitHubApi.resolve()
    assert isinstance(api, TokenGitHubApi)
    assert api.token == TOKEN


def test_the_cli_transport_wins_over_a_token(monkeypatch, stub_bin):
    put_stub_first_on_path(monkeypatch, stub_bin)
    monkeypatch.setenv(CredentialVariable.GH_TOKEN, TOKEN)
    assert isinstance(GitHubApi.resolve(), CommandGitHubApi)


# %% command transport


@pytest.fixture
def stub_call_log(monkeypatch, stub_bin, tmp_path):
    """
    The ``gh`` stub installed first on ``PATH``, recording every invocation into the
    returned file.
    """
    put_stub_first_on_path(monkeypatch, stub_bin)
    call_log = tmp_path / "gh-calls"
    monkeypatch.setenv(StubEnvironmentVariable.CALL_LOG, str(call_log))
    return call_log


def test_the_command_transport_invokes_gh_api_and_parses_the_response(
    monkeypatch, stub_call_log
):
    response = {PullRequestField.NUMBER: 7}
    monkeypatch.setenv(StubEnvironmentVariable.API_JSON, json.dumps(response))

    payload = CommandGitHubApi().get(ENDPOINTS.pull_request(7))

    assert payload == response
    assert (
        stub_call_log.read_text()
        == f"{CommandGitHubApi.API_SUBCOMMAND} {ENDPOINTS.pull_request(7)}\n"
    )


def test_the_command_transport_appends_query_parameters(monkeypatch, stub_call_log):
    monkeypatch.setenv(StubEnvironmentVariable.API_JSON, json.dumps([]))

    CommandGitHubApi().get(
        ENDPOINTS.pull_requests,
        {ListParameter.STATE: PullRequestListFilter.ALL, ListParameter.PER_PAGE: "100"},
    )

    assert (
        stub_call_log.read_text()
        == f"{CommandGitHubApi.API_SUBCOMMAND} {ENDPOINTS.pull_requests}"
        "?state=all&per_page=100\n"
    )


# %% token transport


def test_the_token_transport_authorizes_and_parses_the_response(monkeypatch):
    captured_requests: list[urllib.request.Request] = []
    response = {PullRequestField.NUMBER: 7}

    def fake_urlopen(request: urllib.request.Request) -> io.BytesIO:
        captured_requests.append(request)
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(
        bastler.pull_request_state.urllib.request, "urlopen", fake_urlopen
    )

    payload = TokenGitHubApi(token=TOKEN).get(
        ENDPOINTS.pull_request(7), {ListParameter.PER_PAGE: "1"}
    )

    assert payload == response
    request = captured_requests[0]
    assert (
        request.full_url == f"{GITHUB_API_ROOT}/{ENDPOINTS.pull_request(7)}?per_page=1"
    )
    assert request.get_header(RequestHeader.AUTHORIZATION) == f"Bearer {TOKEN}"
    assert (
        request.get_header(RequestHeader.ACCEPT) == TokenGitHubApi.ACCEPTED_MEDIA_TYPE
    )


# %% fetch orchestration

FIRST = PullRequestPayload(
    number=7,
    head="feature-one",
    labels=("bug",),
    session=ClaudeSessionLink("07"),
    additions=107,
    deletions=7,
    mergeable=True,
)
"""
An open, ready pull request whose checks passed.
"""

SECOND = PullRequestPayload(
    number=8,
    head="feature-two",
    draft=True,
    labels=("bug",),
    session=ClaudeSessionLink("08"),
    additions=108,
    deletions=8,
    mergeable=True,
)
"""
An open draft on which no check has run.
"""


def make_two_pull_request_api() -> RecordedFakeGitHubApi:
    """
    :return: A transport serving :data:`FIRST` and :data:`SECOND` through the three
        endpoints the fetcher uses.
    """
    return RecordedFakeGitHubApi(
        {
            ENDPOINTS.pull_requests: [FIRST.to_list_entry(), SECOND.to_list_entry()],
            ENDPOINTS.pull_request(FIRST.number): FIRST.to_json(),
            ENDPOINTS.pull_request(SECOND.number): SECOND.to_json(),
            ENDPOINTS.check_runs(FIRST.head_commit): check_runs_payload(
                CheckConclusion.SUCCESS
            ),
            ENDPOINTS.check_runs(SECOND.head_commit): check_runs_payload(),
        }
    )


def test_fetch_discovers_and_assembles_every_listed_pull_request():
    states = PullRequestFetcher(REPOSITORY, make_two_pull_request_api()).fetch()

    assert [state.number for state in states] == [FIRST.number, SECOND.number]
    first = states[0]
    assert first.head == FIRST.head
    assert first.base == FIRST.base
    assert first.state is PullRequestState.OPEN
    assert first.draft is FIRST.draft
    assert first.labels == list(FIRST.labels)
    assert first.continuous_integration is CheckConclusion.SUCCESS
    assert first.additions == FIRST.additions
    assert first.deletions == FIRST.deletions
    assert first.mergeable is FIRST.mergeable
    assert first.session_url == FIRST.session.url


def test_fetch_reduces_an_empty_check_rollup_to_none():
    states = PullRequestFetcher(REPOSITORY, make_two_pull_request_api()).fetch()
    assert states[1].continuous_integration is None
    assert states[1].draft is SECOND.draft


def test_explicit_numbers_skip_discovery_and_fetch_directly():
    api = make_two_pull_request_api()

    states = PullRequestFetcher(REPOSITORY, api).fetch(numbers=[SECOND.number])

    assert [state.number for state in states] == [SECOND.number]
    assert ENDPOINTS.pull_requests not in api.requested_paths


@dataclass
class PaginatingFakeGitHubApi(GitHubApi):
    """
    A transport whose list endpoint serves one full page and then an empty one.
    """

    payloads: list[PullRequestPayload]
    """
    The pull requests the full page lists.
    """

    list_pages_served: int = field(default=0, init=False)
    """
    How many list pages have been requested.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        if path == ENDPOINTS.pull_requests:
            self.list_pages_served += 1
            first_page = parameters[ListParameter.PAGE] == "1"
            return (
                [payload.to_list_entry() for payload in self.payloads]
                if first_page
                else []
            )
        responses = {}
        for payload in self.payloads:
            responses[ENDPOINTS.pull_request(payload.number)] = payload.to_json()
            responses[ENDPOINTS.check_runs(payload.head_commit)] = check_runs_payload()
        return responses[path]


def test_fetch_paginates_until_a_short_page():
    payloads = [
        PullRequestPayload(number=number, head=f"branch-{number}")
        for number in range(PullRequestFetcher.PAGE_SIZE)
    ]
    api = PaginatingFakeGitHubApi(payloads)

    states = PullRequestFetcher(REPOSITORY, api).fetch()

    assert len(states) == PullRequestFetcher.PAGE_SIZE
    assert api.list_pages_served == 2
