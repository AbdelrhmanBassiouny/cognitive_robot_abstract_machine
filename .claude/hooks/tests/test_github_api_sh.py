"""
Integration tests for github-api.sh's four GitHub lookups and its credential precedence.

Run against the stub ``gh`` and ``curl`` in ``stubs/``, placed earlier on ``PATH`` than
any real one, so no test reaches GitHub or needs credentials. The two backends are
exercised separately: ``gh`` when it is installed, a token plus ``curl`` when it is not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from github_api import (
    GitHubApiCall,
    GitHubApiRunner,
    GitHubRemoteUrl,
    RepositoryLabel,
)
from scratch_repository import HOOKS_SOURCE_DIRECTORY, ScratchRepository, ShellProgram
from stub_executables import (
    GitHubCredentialVariable,
    StubbedExecutable,
    StubExecutableDirectory,
)
from tooling_files import HookScript

REPOSITORY = "octo-org/octo-repo"
"""
The ``owner/repo`` the label lookups are made against.
"""

LOGIN_THROUGH_GH = "octocat"
"""
The login the stub ``gh`` is told to report.
"""

LOGIN_THROUGH_CURL = "hubot"
"""
The login the stub ``curl`` is told to report, distinct so a test proves which backend
answered.
"""

LABEL_DESCRIPTION = "Something is broken"
"""
The description a created label is given.
"""

# %% credential precedence


def test_reads_the_login_through_gh_when_it_is_installed(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.GH)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.AUTHENTICATED_LOGIN, STUB_GH_LOGIN=LOGIN_THROUGH_GH
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LOGIN_THROUGH_GH


def test_falls_back_to_a_token_and_curl_when_gh_is_absent(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.CURL)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.AUTHENTICATED_LOGIN,
        hidden_executables=(StubbedExecutable.GH,),
        GITHUB_TOKEN="a-token",
        STUB_CURL_LOGIN=LOGIN_THROUGH_CURL,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LOGIN_THROUGH_CURL


def test_fails_when_neither_gh_nor_a_token_is_available(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.AUTHENTICATED_LOGIN,
        hidden_executables=(StubbedExecutable.GH,),
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    # Both routes out of the failure have to be named, or the reader is left guessing
    # which of the two they are missing.
    assert StubbedExecutable.GH in result.stderr
    assert GitHubCredentialVariable.GH_TOKEN in result.stderr
    assert GitHubCredentialVariable.GITHUB_TOKEN in result.stderr


# %% the labels the tooling knows about


def test_the_labels_match_the_ones_the_shell_declares():
    declared = subprocess.run(
        [
            "bash",
            str(ShellProgram.PRINT_PULL_REQUEST_LABELS.path),
            str(HOOKS_SOURCE_DIRECTORY / HookScript.CONFIGURATION.value),
        ],
        capture_output=True,
        text=True,
    )

    assert declared.returncode == 0, declared.stderr
    assert declared.stdout.split() == [label.value for label in RepositoryLabel]


# %% label existence


def test_reports_a_label_that_exists(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.GH)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.LABEL_EXISTS, REPOSITORY, RepositoryLabel.MERGED
    )

    assert result.returncode == 0, result.stderr


def test_reports_a_label_that_is_missing(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.GH)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.LABEL_EXISTS,
        REPOSITORY,
        RepositoryLabel.IN_REVIEW,
        STUB_GH_MISSING_LABELS=RepositoryLabel.IN_REVIEW,
    )

    assert result.returncode != 0


def test_reports_a_missing_label_through_the_curl_fallback_too(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.CURL)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.LABEL_EXISTS,
        REPOSITORY,
        RepositoryLabel.IN_REVIEW,
        hidden_executables=(StubbedExecutable.GH,),
        GH_TOKEN="a-token",
        STUB_CURL_MISSING_LABELS=RepositoryLabel.IN_REVIEW,
    )

    assert result.returncode != 0


def test_reports_an_existing_label_through_the_curl_fallback_too(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.CURL)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.LABEL_EXISTS,
        REPOSITORY,
        RepositoryLabel.MERGED,
        hidden_executables=(StubbedExecutable.GH,),
        GH_TOKEN="a-token",
    )

    assert result.returncode == 0, result.stderr


# %% label creation


def test_creates_a_label(stub_executables: StubExecutableDirectory, tmp_path: Path):
    stub_executables.install(StubbedExecutable.GH)
    call_log = tmp_path / "gh-calls.txt"

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.CREATE_LABEL,
        REPOSITORY,
        RepositoryLabel.BUG,
        LABEL_DESCRIPTION,
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    logged_call = call_log.read_text()
    assert f"repos/{REPOSITORY}/labels" in logged_call
    assert f"name={RepositoryLabel.BUG}" in logged_call
    assert f"description={LABEL_DESCRIPTION}" in logged_call


def test_reports_a_creation_that_the_api_refuses(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install(StubbedExecutable.GH)

    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.CREATE_LABEL,
        REPOSITORY,
        RepositoryLabel.BUG,
        LABEL_DESCRIPTION,
        STUB_GH_CREATE_LABEL_FAILS="1",
    )

    assert result.returncode != 0


# %% parsing a remote into owner/repo


@pytest.mark.parametrize("url_form", list(GitHubRemoteUrl))
def test_parses_owner_and_repository_out_of_a_url(
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
    url_form: GitHubRemoteUrl,
):
    result = GitHubApiRunner(stub_executables, tmp_path).run(
        GitHubApiCall.REPOSITORY_OF_REMOTE, url_form.for_repository(REPOSITORY)
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == REPOSITORY


def test_resolves_a_remote_name_through_git(
    stub_executables: StubExecutableDirectory, scratch_repository: ScratchRepository
):
    remote_name = "myfork"
    scratch_repository.run_git(
        "remote",
        "add",
        remote_name,
        GitHubRemoteUrl.HTTPS_WITH_SUFFIX.for_repository(REPOSITORY),
    )

    result = GitHubApiRunner(stub_executables, scratch_repository.project_root).run(
        GitHubApiCall.REPOSITORY_OF_REMOTE, remote_name
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == REPOSITORY


def test_rejects_a_remote_that_is_neither_a_known_name_nor_a_github_url(
    stub_executables: StubExecutableDirectory, scratch_repository: ScratchRepository
):
    unknown_remote = "not-a-remote"

    result = GitHubApiRunner(stub_executables, scratch_repository.project_root).run(
        GitHubApiCall.REPOSITORY_OF_REMOTE, unknown_remote
    )

    assert result.returncode != 0
    assert unknown_remote in result.stderr


@pytest.mark.parametrize(
    "local_remote", ["/srv/git/octo-repo.git", "../sibling-clone", "./notes.git"]
)
def test_rejects_a_local_path_rather_than_reading_an_owner_out_of_it(
    stub_executables: StubExecutableDirectory,
    scratch_repository: ScratchRepository,
    local_remote: str,
):
    # A path has trailing segments that look exactly like "<owner>/<repo>", so a parser
    # that only counted segments would report a directory name as a GitHub account - and
    # any ownership check built on that would then compare a real login against a
    # directory name and refuse a perfectly valid setup.
    result = GitHubApiRunner(stub_executables, scratch_repository.project_root).run(
        GitHubApiCall.REPOSITORY_OF_REMOTE, local_remote
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
