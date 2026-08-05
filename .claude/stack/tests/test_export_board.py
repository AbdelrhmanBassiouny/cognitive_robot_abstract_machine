"""
Tests for the ``export`` command's core: writing a ``board.json`` that ``load_board``
round-trips, through an injected in-memory GitHub transport - no network. Resolving
the fork's repository from this checkout's remotes is ``Configuration``'s own
behavior, covered by ``test_stack.py``, not re-tested here.
"""

from __future__ import annotations

from typing import Any

from development_tooling.pr_state import GitHubApi

from stack import export_board, load_board


class SinglePullRequestFakeGitHubApi(GitHubApi):
    """
    Serves one open pull request through the three endpoints the fetch layer uses.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        if path.endswith("/pulls"):
            return [{"number": 5}]
        if path.endswith("/check-runs"):
            return {"check_runs": [{"conclusion": "success"}]}
        return {
            "number": 5,
            "state": "open",
            "draft": False,
            "merged_at": None,
            "head": {"ref": "feature-branch", "sha": "sha-5"},
            "base": {"ref": "main"},
            "labels": [{"name": "in-review"}],
            "body": "Session: https://claude.ai/code/session_05\n",
            "additions": 10,
            "deletions": 2,
            "mergeable": True,
        }


def test_export_writes_a_board_load_board_round_trips(tmp_path):
    board_path = tmp_path / "board.json"

    exported_count = export_board(
        "some-owner/some-repository", SinglePullRequestFakeGitHubApi(), board_path
    )

    assert exported_count == 1
    pull_requests = load_board(board_path)
    assert len(pull_requests) == 1
    exported = pull_requests[0]
    assert exported.number == 5
    assert exported.head == "feature-branch"
    assert exported.base == "main"
    assert exported.draft is False
    assert exported.labels == ["in-review"]
    assert exported.ci == "success"
    assert exported.session == "https://claude.ai/code/session_05"
