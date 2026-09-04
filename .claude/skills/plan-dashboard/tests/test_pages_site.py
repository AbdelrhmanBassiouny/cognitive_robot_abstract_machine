"""
Tests for pointing a repository's Pages site at the branch the built dashboards are
pushed to.

The transport is a recording fake, so no network access and no repository settings are
involved - what is under test is which requests each starting state produces, and that
the reported URL comes from GitHub rather than from a formula here.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import pytest

from github_api import GitHubApi, HttpMethod, RepositoryEndpoints
from publish_site import DEFAULT_SITE_BRANCH
from pages_site import (
    SITE_ROOT_PATH,
    PagesBuildType,
    PagesField,
    PagesSite,
    PagesUnavailableError,
)

REPOSITORY = "owner/repository"
SITE_BRANCH = DEFAULT_SITE_BRANCH
SITE_URL = "https://owner.github.io/repository/"
PAGES_PATH = RepositoryEndpoints(REPOSITORY).pages


def pages_configuration(branch: str, url: str | None = SITE_URL) -> dict[str, Any]:
    """
    A Pages configuration as GitHub reports it.

    :param branch: The branch it serves from.
    :param url: The URL it reports, or ``None`` for a site GitHub gives no URL for.
    :return: The configuration.
    """
    return {
        PagesField.URL.value: url,
        PagesField.SOURCE.value: {
            PagesField.BRANCH.value: branch,
            PagesField.PATH.value: SITE_ROOT_PATH,
        },
    }


@dataclass
class RecordingApi(GitHubApi):
    """
    A transport serving a prepared configuration and recording every request.
    """

    configuration: dict[str, Any] | None = None
    """
    The configuration the repository starts with, or ``None`` if Pages is off.
    """

    requests: list[tuple[HttpMethod, str, Mapping[str, Any] | None]] = field(
        default_factory=list
    )
    """
    Every method, path and body sent, in order.
    """

    def get(self, path: str, parameters: Mapping[str, str] | None = None) -> Any:
        self.requests.append((HttpMethod.GET, path, None))
        return self.configuration

    def find(self, path: str) -> Any | None:
        self.requests.append((HttpMethod.GET, path, None))
        return self.configuration

    def send(self, method: HttpMethod, path: str, body: Mapping[str, Any]) -> Any:
        self.requests.append((method, path, body))
        self.configuration = pages_configuration(
            body[PagesField.SOURCE.value][PagesField.BRANCH.value]
        )
        return self.configuration


@pytest.fixture
def site() -> Callable[[dict[str, Any] | None], PagesSite]:
    """
    Build a site over a transport starting from a given configuration.

    :return: The builder, called with the starting configuration or ``None``.
    """

    def build(configuration: dict[str, Any] | None) -> PagesSite:
        return PagesSite(
            repository=REPOSITORY, api=RecordingApi(configuration=configuration)
        )

    return build


def test_a_repository_without_pages_has_it_enabled_on_the_site_branch(site):
    """
    A fork that has never had Pages is configured by the first run, so publishing needs
    no settings visit.
    """
    pages = site(None)

    assert pages.serve_from(SITE_BRANCH) == SITE_URL
    method, path, body = pages.api.requests[-1]
    assert (method, path) == (HttpMethod.POST, PAGES_PATH)
    assert body == {
        PagesField.BUILD_TYPE.value: PagesBuildType.LEGACY,
        PagesField.SOURCE.value: {
            PagesField.BRANCH.value: SITE_BRANCH,
            PagesField.PATH.value: SITE_ROOT_PATH,
        },
    }


def test_a_repository_already_serving_the_site_branch_is_left_alone(site):
    """
    Every run would otherwise rewrite settings that already say what they should - the
    configuration is read, and nothing is sent.
    """
    pages = site(pages_configuration(SITE_BRANCH))

    assert pages.serve_from(SITE_BRANCH) == SITE_URL
    assert [method for method, _, _ in pages.api.requests] == [HttpMethod.GET]


def test_a_repository_serving_something_else_is_repointed(site):
    """
    A site already published from another branch is moved rather than left serving pages
    this build no longer writes.
    """
    pages = site(pages_configuration("some-other-branch"))

    pages.serve_from(SITE_BRANCH)

    assert [method for method, _, _ in pages.api.requests] == [
        HttpMethod.GET,
        HttpMethod.PUT,
        HttpMethod.GET,
    ]


def test_the_url_is_the_one_github_reports(site):
    """
    A custom domain or an owner-root repository is served from somewhere no formula over
    the repository name would arrive at, so the URL is read, never composed.
    """
    pages = site(pages_configuration(SITE_BRANCH, url="https://plans.example.org/"))

    assert pages.serve_from(SITE_BRANCH) == "https://plans.example.org/"


def test_a_site_github_reports_no_url_for_is_an_error(site):
    """
    The build would otherwise render every page against an empty base URL and publish a
    site whose index links go nowhere.
    """
    pages = site(pages_configuration(SITE_BRANCH, url=None))

    with pytest.raises(PagesUnavailableError) as raised:
        pages.serve_from(SITE_BRANCH)

    assert SITE_BRANCH in str(raised.value)
