"""
Tests for the ``export`` command's core: writing a ``board.json`` that ``load_board``
round-trips, through an injected in-memory GitHub transport - no network. Resolving the
fork's repository from this checkout's remotes is ``Configuration``'s own behaviour,
covered by ``test_stack.py``, not re-tested here.
"""

from __future__ import annotations

from bastler.build_dashboard import PullRequestLabel
from bastler.pull_request_state import (
    CheckConclusion,
    ClaudeSessionLink,
    RepositoryEndpoints,
)
from bastler.stack import BOARD_DOCUMENT_NAME, export_board, load_board

from .pull_request_responses import (
    PullRequestResponse,
    RecordedFakeGitHubApi,
    check_runs_response,
)

REPOSITORY = "some-owner/some-repository"
"""
The fork the export reads.
"""

ENDPOINTS = RepositoryEndpoints(REPOSITORY)
"""
Its endpoints.
"""

PULL_REQUEST = PullRequestResponse(
    number=5,
    head="feature-branch",
    labels=(PullRequestLabel.IN_REVIEW,),
    session=ClaudeSessionLink("05"),
    additions=10,
    deletions=2,
    mergeable=True,
)
"""
The one open pull request the fork has.
"""


def make_single_pull_request_api() -> RecordedFakeGitHubApi:
    """
    :return: A transport serving :data:`PULL_REQUEST` through the three endpoints the
        fetch layer uses.
    """
    return RecordedFakeGitHubApi(
        {
            ENDPOINTS.pull_requests: [PULL_REQUEST.to_list_entry()],
            ENDPOINTS.pull_request(PULL_REQUEST.number): PULL_REQUEST.to_json(),
            ENDPOINTS.check_runs(PULL_REQUEST.head_commit): check_runs_response(
                CheckConclusion.SUCCESS
            ),
        }
    )


def test_export_writes_a_board_that_load_board_round_trips(tmp_path):
    board_path = tmp_path / BOARD_DOCUMENT_NAME

    exported_count = export_board(
        REPOSITORY, make_single_pull_request_api(), board_path
    )

    assert exported_count == 1
    pull_requests = load_board(board_path)
    assert len(pull_requests) == 1
    exported = pull_requests[0]
    assert exported.number == PULL_REQUEST.number
    assert exported.head == PULL_REQUEST.head
    assert exported.base == PULL_REQUEST.base
    assert exported.draft is PULL_REQUEST.draft
    assert exported.labels == list(PULL_REQUEST.labels)
    assert exported.continuous_integration == CheckConclusion.SUCCESS
    assert exported.session == PULL_REQUEST.session.url
