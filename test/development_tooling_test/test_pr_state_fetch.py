"""
Tests for the fetch half of :mod:`development_tooling.pr_state`: backend resolution
(GitHub CLI, else token, else a failure naming both routes), the two transports, and
the orchestration that turns GitHub API payloads into
:class:`~development_tooling.pr_state.PullRequestLiveState`.

All network-free: the transports run against a recorded stub / a monkeypatched opener,
and the orchestration runs against an in-memory fake API.
"""

from __future__ import annotations

import io
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from development_tooling.pr_state import (
    CheckConclusion,
    CommandGitHubApi,
    GitHubAccessError,
    GitHubApi,
    PullRequestState,
    TokenGitHubApi,
    fetch_pull_request_states,
    resolve_github_api,
)

STUBS_DIRECTORY = Path(__file__).parent / "stubs"
"""
Where the recorded executable stand-ins for this suite live.
"""

# %% backend resolution


def test_no_cli_and_no_token_fails_naming_both_routes(monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GitHubAccessError) as error:
        resolve_github_api()
    assert "gh" in str(error.value)
    assert "GH_TOKEN" in str(error.value)
    assert "GITHUB_TOKEN" in str(error.value)


def test_token_backend_is_used_without_the_cli(monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("GH_TOKEN", "token-value")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    api = resolve_github_api()
    assert isinstance(api, TokenGitHubApi)
    assert api.token == "token-value"


def test_cli_backend_wins_over_a_token(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(STUBS_DIRECTORY))
    monkeypatch.setenv("GH_TOKEN", "token-value")
    assert isinstance(resolve_github_api(), CommandGitHubApi)


# %% command transport


def test_command_transport_invokes_gh_api_and_parses_the_response(
    monkeypatch, tmp_path
):
    arguments_file = tmp_path / "arguments"
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps({"number": 7}))
    monkeypatch.setenv("PATH", str(STUBS_DIRECTORY) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("GH_STUB_ARGUMENTS_FILE", str(arguments_file))
    monkeypatch.setenv("GH_STUB_RESPONSE_FILE", str(response_file))

    api = CommandGitHubApi()
    payload = api.get("repos/owner/repository/pulls/7")

    assert payload == {"number": 7}
    assert arguments_file.read_text() == "api repos/owner/repository/pulls/7\n"


def test_command_transport_appends_query_parameters(monkeypatch, tmp_path):
    arguments_file = tmp_path / "arguments"
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps([]))
    monkeypatch.setenv("PATH", str(STUBS_DIRECTORY) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("GH_STUB_ARGUMENTS_FILE", str(arguments_file))
    monkeypatch.setenv("GH_STUB_RESPONSE_FILE", str(response_file))

    CommandGitHubApi().get(
        "repos/owner/repository/pulls", {"state": "all", "per_page": "100"}
    )

    assert (
        arguments_file.read_text()
        == "api repos/owner/repository/pulls?state=all&per_page=100\n"
    )


# %% token transport


def test_token_transport_authorizes_and_parses_the_response(monkeypatch):
    captured_requests = []

    def fake_urlopen(request):
        captured_requests.append(request)
        return io.BytesIO(json.dumps({"number": 7}).encode())

    monkeypatch.setattr(
        "development_tooling.pr_state.urllib.request.urlopen", fake_urlopen
    )

    api = TokenGitHubApi(token="token-value")
    payload = api.get("repos/owner/repository/pulls/7", {"per_page": "1"})

    assert payload == {"number": 7}
    request = captured_requests[0]
    assert (
        request.full_url
        == "https://api.github.com/repos/owner/repository/pulls/7?per_page=1"
    )
    assert request.get_header("Authorization") == "Bearer token-value"


# %% fetch orchestration


def list_payload_entry(number: int, head: str) -> dict[str, Any]:
    return {
        "number": number,
        "state": "open",
        "draft": False,
        "merged_at": None,
        "head": {"ref": head, "sha": f"sha-{number}"},
        "base": {"ref": "main"},
        "labels": [],
        "body": "",
    }


def detail_payload(number: int, head: str) -> dict[str, Any]:
    return {
        "number": number,
        "state": "open",
        "draft": number == 8,
        "merged_at": None,
        "head": {"ref": head, "sha": f"sha-{number}"},
        "base": {"ref": "main"},
        "labels": [{"name": "bug"}],
        "body": f"Session: https://claude.ai/code/session_0{number}\n",
        "additions": 100 + number,
        "deletions": number,
        "mergeable": True,
    }


class RecordedFakeGitHubApi(GitHubApi):
    """
    An in-memory API returning canned payloads keyed by path, recording every request it
    serves.
    """

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.requested_paths: list[str] = []

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        self.requested_paths.append(path)
        return self.responses[path]


def make_two_pull_request_api() -> RecordedFakeGitHubApi:
    return RecordedFakeGitHubApi(
        {
            "repos/owner/repository/pulls": [
                list_payload_entry(7, "feature-one"),
                list_payload_entry(8, "feature-two"),
            ],
            "repos/owner/repository/pulls/7": detail_payload(7, "feature-one"),
            "repos/owner/repository/pulls/8": detail_payload(8, "feature-two"),
            "repos/owner/repository/commits/sha-7/check-runs": {
                "check_runs": [{"conclusion": "success"}]
            },
            "repos/owner/repository/commits/sha-8/check-runs": {"check_runs": []},
        }
    )


def test_fetch_discovers_and_assembles_every_listed_pull_request():
    api = make_two_pull_request_api()

    states = fetch_pull_request_states("owner/repository", api)

    assert [state.number for state in states] == [7, 8]
    first = states[0]
    assert first.head == "feature-one"
    assert first.base == "main"
    assert first.state is PullRequestState.OPEN
    assert first.draft is False
    assert first.labels == ["bug"]
    assert first.ci is CheckConclusion.SUCCESS
    assert first.additions == 107
    assert first.deletions == 7
    assert first.mergeable is True
    assert first.session_url == "https://claude.ai/code/session_07"


def test_fetch_reduces_an_empty_check_rollup_to_none():
    states = fetch_pull_request_states("owner/repository", make_two_pull_request_api())
    assert states[1].ci is None
    assert states[1].draft is True


def test_explicit_numbers_skip_discovery_and_fetch_directly():
    api = make_two_pull_request_api()

    states = fetch_pull_request_states("owner/repository", api, numbers=[8])

    assert [state.number for state in states] == [8]
    assert "repos/owner/repository/pulls" not in api.requested_paths


def test_fetch_paginates_until_a_short_page(monkeypatch):
    first_page = [
        list_payload_entry(number, f"branch-{number}") for number in range(100)
    ]

    class PaginatingFakeGitHubApi(GitHubApi):
        def __init__(self):
            self.list_pages_served = 0

        def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
            if path == "repos/owner/repository/pulls":
                self.list_pages_served += 1
                return first_page if parameters["page"] == "1" else []
            if path.endswith("/check-runs"):
                return {"check_runs": []}
            number = int(path.rsplit("/", maxsplit=1)[1])
            return detail_payload(number, f"branch-{number}")

    api = PaginatingFakeGitHubApi()
    states = fetch_pull_request_states("owner/repository", api)

    assert len(states) == 100
    assert api.list_pages_served == 2
