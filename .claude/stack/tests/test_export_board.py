"""
Tests for the ``export`` command's pieces: resolving the fork's ``owner/repository``

from its git remote, and writing a ``board.json`` that ``load_board`` round-trips.
The GitHub side is an injected in-memory transport - no network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from development_tooling.pr_state import GitHubApi

from stack import export_board, github_repository_of_fork_remote, load_board


def make_config(fork_remote: str = "origin"):
    from stack import Config

    return Config(
        in_review_label="in-review",
        rebase_label="rebase",
        needs_resolution_label="needs-resolution",
        fork_remote=fork_remote,
        upstream_remote="cram2",
        upstream_base="main",
    )


def repository_with_remote(tmp_path: Path, url: str) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", str(root)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", url],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


# %% fork-remote repository resolution


def test_https_remote_resolves_to_its_trailing_segments(tmp_path, monkeypatch):
    root = repository_with_remote(
        tmp_path, "https://github.com/some-owner/some-repository.git"
    )
    monkeypatch.chdir(root)
    assert (
        github_repository_of_fork_remote(make_config()) == "some-owner/some-repository"
    )


def test_proxy_form_remote_without_a_github_host_still_resolves(tmp_path, monkeypatch):
    root = repository_with_remote(
        tmp_path, "http://local_proxy@127.0.0.1:12345/git/some-owner/some-repository"
    )
    monkeypatch.chdir(root)
    assert (
        github_repository_of_fork_remote(make_config()) == "some-owner/some-repository"
    )


# %% board export


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
