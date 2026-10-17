"""
The package's GitHub client: where its credential comes from, and the label and login
calls it makes - run against an in-process stand-in for the API, never the network.
"""

from __future__ import annotations

import pytest

from basstler.maintenance_constants import CREDENTIAL_VARIABLES
from basstler.maintenance_github import (
    GITHUB_CLI,
    GitHubConnection,
    GitHubCredentialUnavailableError,
    GitHubRepository,
)
from basstler.repository_label import RepositoryLabel

from .executable_stubs import ExecutableStubDirectory, StubbedExecutable
from .github_api_replay import REPLAYED_LOGIN, ReplayingGitHubApi

PREFERRED_TOKEN = "a-preferred-token"
"""
A token set in the first credential variable the client reads.
"""

FALLBACK_TOKEN = "a-fallback-token"
"""
A token set in the second.
"""

STORED_TOKEN = "a-token-gh-stores"
"""
The token the stubbed ``gh`` lends.
"""

LABEL_PAGE_SIZE = 2
"""
A page size smaller than the label set, so a listing needs more than one page.
"""

# %% where the credential comes from


def test_the_first_token_variable_wins(stub_bin: ExecutableStubDirectory):
    stub_bin.install(StubbedExecutable.GH)
    environment = stub_bin.subprocess_environment(
        STUB_GH_TOKEN=STORED_TOKEN,
        **dict(zip(CREDENTIAL_VARIABLES, (PREFERRED_TOKEN, FALLBACK_TOKEN))),
    )

    connection = GitHubConnection.from_environment(environment)

    assert connection == GitHubConnection(PREFERRED_TOKEN)


def test_the_second_token_variable_is_read_without_the_first(
    stub_bin: ExecutableStubDirectory,
):
    environment = stub_bin.subprocess_environment(
        hidden_executables=(StubbedExecutable.GH,),
        **{CREDENTIAL_VARIABLES[1]: FALLBACK_TOKEN},
    )

    assert GitHubConnection.from_environment(environment) == GitHubConnection(
        FALLBACK_TOKEN
    )


def test_the_cli_lends_its_stored_token_when_no_variable_is_set(
    stub_bin: ExecutableStubDirectory,
):
    stub_bin.install(StubbedExecutable.GH)
    environment = stub_bin.subprocess_environment(STUB_GH_TOKEN=STORED_TOKEN)

    assert GitHubConnection.from_environment(environment) == GitHubConnection(
        STORED_TOKEN
    )


def test_a_cli_that_is_not_logged_in_lends_nothing(stub_bin: ExecutableStubDirectory):
    stub_bin.install(StubbedExecutable.GH)

    assert GitHubConnection.from_environment(stub_bin.subprocess_environment()) is None


def test_no_credential_without_a_variable_or_the_cli(stub_bin: ExecutableStubDirectory):
    environment = stub_bin.subprocess_environment(
        hidden_executables=(StubbedExecutable.GH,)
    )

    assert GitHubConnection.from_environment(environment) is None


def test_a_missing_credential_names_every_way_to_supply_one():
    message = str(GitHubCredentialUnavailableError(CREDENTIAL_VARIABLES))

    assert all(variable in message for variable in CREDENTIAL_VARIABLES)
    assert GITHUB_CLI in message


# %% the calls


@pytest.fixture
def repository_client(github_api: ReplayingGitHubApi) -> GitHubRepository:
    """
    A client for the stand-in's repository, paging in small pages.

    :param github_api: The stand-in the client's requests reach.
    :return: The client.
    """
    return GitHubRepository(
        github_api.repository,
        GitHubConnection(PREFERRED_TOKEN),
        page_size=LABEL_PAGE_SIZE,
    )


def test_the_login_is_the_credential_owners(github_api: ReplayingGitHubApi):
    assert GitHubConnection(PREFERRED_TOKEN).authenticated_login() == REPLAYED_LOGIN


def test_the_labels_are_read_to_the_last_page(
    github_api: ReplayingGitHubApi, repository_client: GitHubRepository
):
    github_api.labels = set(RepositoryLabel)

    assert repository_client.labels() == set(RepositoryLabel)


def test_a_created_label_carries_its_purpose(
    github_api: ReplayingGitHubApi, repository_client: GitHubRepository
):
    repository_client.create_label(RepositoryLabel.REBASE)

    assert github_api.created_labels() == [
        {
            "name": RepositoryLabel.REBASE.value,
            "description": RepositoryLabel.REBASE.purpose,
        }
    ]
