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

from scratch_repository import HOOKS_SOURCE_DIRECTORY, ScratchRepository
from stub_executables import StubExecutableDirectory

GITHUB_API_SCRIPT = HOOKS_SOURCE_DIRECTORY / "github-api.sh"
"""
The script under test, sourced directly - it resolves no repository paths of its own, so
it needs no scratch layout.
"""

REPOSITORY = "octo-org/octo-repo"
"""
The ``owner/repo`` the label lookups are made against.
"""


def run_github_api(
    call: str,
    stub_executables: StubExecutableDirectory,
    working_directory: Path,
    hidden_executables: tuple[str, ...] = (),
    **environment_overrides: str,
) -> subprocess.CompletedProcess[str]:
    """
    Source github-api.sh and run one call against the stubbed ``PATH``.

    :param call: The shell call to make, for example ``"github_authenticated_login"``.
    :param stub_executables: The stub directory the call resolves its executables from.
    :param working_directory: Where to run, which matters only for the calls that
        consult git.
    :param hidden_executables: Executables to make unfindable for this run.
    :param environment_overrides: Variables to set, chiefly the stubs' ``STUB_*``
        controls.
    :return: The finished subprocess.
    """
    return subprocess.run(
        [
            "bash",
            "-c",
            f'source "$1"; {call}',
            "github-api-test",
            str(GITHUB_API_SCRIPT),
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(
            hidden_executables=hidden_executables, **environment_overrides
        ),
    )


# %% credential precedence


def test_reads_the_login_through_gh_when_it_is_installed(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("gh")

    result = run_github_api(
        "github_authenticated_login",
        stub_executables,
        tmp_path,
        STUB_GH_LOGIN="octocat",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "octocat"


def test_falls_back_to_a_token_and_curl_when_gh_is_absent(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("curl")

    result = run_github_api(
        "github_authenticated_login",
        stub_executables,
        tmp_path,
        hidden_executables=("gh",),
        GITHUB_TOKEN="a-token",
        STUB_CURL_LOGIN="hubot",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hubot"


def test_fails_when_neither_gh_nor_a_token_is_available(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    result = run_github_api(
        "github_authenticated_login",
        stub_executables,
        tmp_path,
        hidden_executables=("gh",),
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    # Both routes out of the failure have to be named, or the reader is left guessing
    # which of the two they are missing.
    assert "gh" in result.stderr
    assert "GH_TOKEN" in result.stderr
    assert "GITHUB_TOKEN" in result.stderr


# %% label existence


def test_reports_a_label_that_exists(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("gh")

    result = run_github_api(
        f"github_repository_has_label {REPOSITORY} merged",
        stub_executables,
        tmp_path,
    )

    assert result.returncode == 0, result.stderr


def test_reports_a_label_that_is_missing(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("gh")

    result = run_github_api(
        f"github_repository_has_label {REPOSITORY} in-review",
        stub_executables,
        tmp_path,
        STUB_GH_MISSING_LABELS="in-review",
    )

    assert result.returncode != 0


def test_reports_a_missing_label_through_the_curl_fallback_too(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("curl")

    result = run_github_api(
        f"github_repository_has_label {REPOSITORY} in-review",
        stub_executables,
        tmp_path,
        hidden_executables=("gh",),
        GH_TOKEN="a-token",
        STUB_CURL_MISSING_LABELS="in-review",
    )

    assert result.returncode != 0


def test_reports_an_existing_label_through_the_curl_fallback_too(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("curl")

    result = run_github_api(
        f"github_repository_has_label {REPOSITORY} merged",
        stub_executables,
        tmp_path,
        hidden_executables=("gh",),
        GH_TOKEN="a-token",
    )

    assert result.returncode == 0, result.stderr


# %% label creation


def test_creates_a_label(stub_executables: StubExecutableDirectory, tmp_path: Path):
    stub_executables.install("gh")
    call_log = tmp_path / "gh-calls.txt"

    result = run_github_api(
        f"github_create_label {REPOSITORY} bug 'Something is broken'",
        stub_executables,
        tmp_path,
        STUB_GH_CALL_LOG=str(call_log),
    )

    assert result.returncode == 0, result.stderr
    logged_call = call_log.read_text()
    assert f"repos/{REPOSITORY}/labels" in logged_call
    assert "name=bug" in logged_call
    assert "description=Something is broken" in logged_call


def test_reports_a_creation_that_the_api_refuses(
    stub_executables: StubExecutableDirectory, tmp_path: Path
):
    stub_executables.install("gh")

    result = run_github_api(
        f"github_create_label {REPOSITORY} bug 'Something is broken'",
        stub_executables,
        tmp_path,
        STUB_GH_CREATE_LABEL_FAILS="1",
    )

    assert result.returncode != 0


# %% parsing a remote into owner/repo


@pytest.mark.parametrize(
    "remote_url",
    [
        f"https://github.com/{REPOSITORY}",
        f"https://github.com/{REPOSITORY}.git",
        f"git@github.com:{REPOSITORY}.git",
        f"ssh://git@github.com/{REPOSITORY}.git",
        # A Claude Code cloud session's clone, rewritten through its local git
        # proxy: no github.com host anywhere in the URL.
        f"http://local_proxy@127.0.0.1:41729/git/{REPOSITORY}",
    ],
)
def test_parses_owner_and_repository_out_of_a_url(
    stub_executables: StubExecutableDirectory, tmp_path: Path, remote_url: str
):
    result = run_github_api(
        f"github_repository_of_remote {remote_url}", stub_executables, tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == REPOSITORY


def test_resolves_a_remote_name_through_git(
    stub_executables: StubExecutableDirectory, scratch_repository: ScratchRepository
):
    scratch_repository.run_git(
        "remote", "add", "myfork", f"https://github.com/{REPOSITORY}.git"
    )

    result = run_github_api(
        "github_repository_of_remote myfork",
        stub_executables,
        scratch_repository.project_root,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == REPOSITORY


def test_rejects_a_remote_that_is_neither_a_known_name_nor_a_github_url(
    stub_executables: StubExecutableDirectory, scratch_repository: ScratchRepository
):
    result = run_github_api(
        "github_repository_of_remote not-a-remote",
        stub_executables,
        scratch_repository.project_root,
    )

    assert result.returncode != 0
    assert "not-a-remote" in result.stderr


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
    result = run_github_api(
        f"github_repository_of_remote {local_remote}",
        stub_executables,
        scratch_repository.project_root,
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
