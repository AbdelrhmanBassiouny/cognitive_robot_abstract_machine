"""
Tests for the headless static-site build: discovering plans from a personal-notes.

remote, fetching their pull request data through an injected GitHub transport,
driving one dashboard refresh per plan, and rendering the master index - the
pipeline a Pages workflow runs with no live session.

The notes remote is a scratch bare repository, the GitHub side is an in-memory fake,
and the per-plan refresh is a recorded stub - refresh_dashboard.sh's own behavior is
covered by its own test module, not re-tested here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from build_site import SiteBuilder
from development_tooling.pr_state import GitHubApi

STUB_REFRESH_DASHBOARD_SCRIPT = (
    Path(__file__).parent / "fixtures" / "stubs" / "refresh_dashboard_stub.sh"
)

PLAN_MANIFEST = """\
schema_version: 1
id: test-plan
title: "Test Plan"
description: "A plan for the site build test."
default_repository: owner/repository
tracking_issue: 9
waves:
  - id: wave-1
    name: "Wave One"
tracks:
  - id: track-1
    name: "Track One"
    wave: wave-1
items:
  - id: an-item
    branch: a-branch
    title: "An item"
    track: track-1
    status: in_progress
    pull_request_number: 1
"""

GIT_IDENTITY_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin",
}


def run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        env=GIT_IDENTITY_ENVIRONMENT,
    )


@pytest.fixture(autouse=True)
def clean_personal_notes_environment(monkeypatch):
    """
    Strip the caller's own personal-notes settings, so a session's real remote can never
    leak into a test's resolution (and from there onto the network).
    """
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_REMOTE", raising=False)
    monkeypatch.delenv("CLAUDE_PERSONAL_NOTES_BRANCH", raising=False)


@pytest.fixture
def project_with_one_plan(tmp_path: Path) -> Path:
    """
    A scratch project clone whose ``origin`` bare remote carries a personal-notes branch
    holding one plan.
    """
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--quiet", "--bare", str(remote)],
        check=True,
        capture_output=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    run_git(seed, "init", "--quiet", "--initial-branch", "claude/personal-notes")
    plan_directory = seed / ".claude" / "personal" / "plans" / "test-plan"
    plan_directory.mkdir(parents=True)
    (plan_directory / "plan.yaml").write_text(PLAN_MANIFEST)
    (plan_directory / "roadmap.md").write_text("# Test plan roadmap\n")
    run_git(seed, "add", ".")
    run_git(seed, "commit", "--quiet", "--message", "seed notes")
    run_git(seed, "push", "--quiet", str(remote), "claude/personal-notes")

    project = tmp_path / "project"
    project.mkdir()
    run_git(project, "init", "--quiet")
    run_git(project, "remote", "add", "origin", str(remote))
    return project


class PlanDataFakeGitHubApi(GitHubApi):
    """
    Serves the one pull request and the tracking issue the test plan references.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        if path == "repos/owner/repository/issues/9":
            return {"html_url": "https://github.com/owner/repository/issues/9"}
        if path.endswith("/check-runs"):
            return {"check_runs": [{"conclusion": "success"}]}
        return {
            "number": 1,
            "state": "open",
            "draft": True,
            "merged_at": None,
            "head": {"ref": "a-branch", "sha": "sha-1"},
            "base": {"ref": "main"},
            "labels": [],
            "body": "Session: https://claude.ai/code/session_01\n",
            "additions": 10,
            "deletions": 2,
            "mergeable": True,
        }


@pytest.fixture
def built_site(project_with_one_plan, tmp_path, monkeypatch):
    """
    One full site build against the scratch plan, with the refresh stub's recordings
    exposed alongside the outputs.
    """
    arguments_file = tmp_path / "refresh-arguments"
    pull_request_data_copy = tmp_path / "pr-data-copy.json"
    monkeypatch.setenv("REFRESH_DASHBOARD_STUB_ARGUMENTS_FILE", str(arguments_file))
    monkeypatch.setenv(
        "REFRESH_DASHBOARD_STUB_PULL_REQUEST_DATA_COPY", str(pull_request_data_copy)
    )
    output_directory = tmp_path / "_site"

    builder = SiteBuilder(
        output_directory=output_directory,
        site_base_url="https://example.github.io/site",
        api=PlanDataFakeGitHubApi(),
        repository_root=project_with_one_plan,
        refresh_dashboard_script=STUB_REFRESH_DASHBOARD_SCRIPT,
    )
    summaries = builder.build()
    return summaries, output_directory, arguments_file, pull_request_data_copy


# %% site structure


def test_build_writes_one_dashboard_page_per_plan(built_site):
    _, output_directory, _, _ = built_site
    dashboard_page = output_directory / "plans" / "test-plan" / "index.html"
    assert dashboard_page.read_text() == "<html>stub dashboard</html>"


def test_build_writes_the_master_index(built_site):
    _, output_directory, _, _ = built_site
    index_page = (output_directory / "index.html").read_text()
    assert "Test Plan" in index_page
    assert "https://example.github.io/site/plans/test-plan/" in index_page


def test_build_returns_one_summary_per_plan(built_site):
    summaries, _, _, _ = built_site
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == "test-plan"
    assert summary.title == "Test Plan"
    assert summary.done == 2
    assert summary.total == 3
    assert summary.dashboard_url == "https://example.github.io/site/plans/test-plan/"


# %% what the per-plan refresh was handed


def test_refresh_runs_once_per_plan_with_its_identity_and_tracking_url(built_site):
    _, _, arguments_file, _ = built_site
    recorded_runs = arguments_file.read_text().splitlines()
    assert len(recorded_runs) == 1
    arguments = recorded_runs[0]
    assert "--plan-id test-plan" in arguments
    assert "--tracking-url https://github.com/owner/repository/issues/9" in arguments


def test_refresh_is_handed_pull_request_data_with_the_chip_fields(built_site):
    _, _, _, pull_request_data_copy = built_site
    data = json.loads(pull_request_data_copy.read_text())
    entry = data["owner/repository"]["1"]
    assert entry["state"] == "open"
    assert entry["draft"] is True
    assert entry["ci"] == "success"
    assert entry["additions"] == 10
    assert entry["deletions"] == 2
    assert entry["mergeable"] is True
    assert entry["session_url"] == "https://claude.ai/code/session_01"
