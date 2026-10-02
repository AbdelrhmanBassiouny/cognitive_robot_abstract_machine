"""
Tests for repository.py: reading a GitHub repository out of a reference or a remote URL.
"""

import pytest

from basstler.repository import MalformedRepositoryError, Repository

# %% repository references


def test_repository_splits_a_reference_into_owner_and_name():
    assert Repository.parse("an-owner/a-repository") == Repository(
        "an-owner", "a-repository"
    )


def test_repository_round_trips_through_the_form_github_uses():
    assert str(Repository.parse("an-owner/a-repository")) == "an-owner/a-repository"


@pytest.mark.parametrize("malformed", ["no-separator", "/no-owner", "no-name/"])
def test_repository_rejects_a_reference_that_is_not_owner_and_name(malformed: str):
    """
    A half-parsed reference would silently target the wrong repository.
    """
    with pytest.raises(MalformedRepositoryError):
        Repository.parse(malformed)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/an-owner/a-repository.git",
        "https://github.com/an-owner/a-repository",
        "git@github.com:an-owner/a-repository.git",
        "http://127.0.0.1:41729/git/an-owner/a-repository",
    ],
)
def test_repository_reads_the_owner_and_name_from_a_remote_url(url: str):
    """
    Every shape a fork remote takes names the same repository.

    A cloud session reaches GitHub through a local proxy, so the URL it sees shares
    neither host nor scheme with the one a laptop clone has.
    """
    assert Repository.from_remote_url(url) == Repository("an-owner", "a-repository")


@pytest.mark.parametrize("malformed", ["", "https://github.com/only-one-segment"])
def test_repository_rejects_a_remote_url_naming_no_repository(malformed: str):
    with pytest.raises(MalformedRepositoryError):
        Repository.from_remote_url(malformed)
