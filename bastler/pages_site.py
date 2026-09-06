#!/usr/bin/env python3
"""
Point a repository's GitHub Pages site at the branch the built dashboards are pushed to,
and report the URL it is served from.

Publishing through a branch rather than ``actions/deploy-pages`` is what lets the site
be rebuilt from a pull request at all: the ``github-pages`` environment only accepts
deployments from the default branch, so a deploy from a pull request run is rejected
outright - "Branch refs/pull/<n>/merge is not allowed to deploy to github-pages due to
environment protection rules" - and pull request events are most of what moves a
dashboard. A branch push has no such gate.

Usage:
    python3 -m bastler.pages_site --repository <owner/name> --branch <branch>

Prints the site's URL, which is read from GitHub rather than composed here: a custom
domain or an owner-root repository is served from somewhere no formula would guess.

Requires a credential with Pages write access in the environment (the
``GITHUB_TOKEN`` variable an Actions runner provides); enabling Pages is the one write
this package makes to a repository's own settings.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from bastler.maintenance_constants import CredentialVariable
from bastler.pull_request_state import (
    GitHubAccessError,
    HttpMethod,
    RepositoryEndpoints,
    TokenGitHubApi,
)

# %% the transport this module needs


class PagesTransport(Protocol):
    """
    The GitHub REST capability :class:`PagesSite` needs: reading and writing a
    repository's Pages configuration.

    Declared as its own protocol rather than depending on
    :class:`~bastler.pull_request_state.TokenGitHubApi` directly, since that is one
    concrete transport and this is the whole of what a Pages configuration is read and
    written through.
    """

    def get(self, path: str) -> Any:
        """
        :param path: The endpoint path, without a leading slash.
        :return: The parsed JSON response.
        """

    def find(self, path: str) -> Any | None:
        """
        :param path: The endpoint path, without a leading slash.
        :return: The parsed JSON response, or ``None`` if it does not exist.
        """

    def send(self, method: HttpMethod, path: str, body: dict[str, Any]) -> Any:
        """
        :param method: The HTTP method to send it with.
        :param path: The endpoint path, without a leading slash.
        :param body: The JSON body to send.
        :return: The parsed JSON response, or ``None`` when GitHub answers with none.
        """


# %% the Pages configuration


class PagesField(StrEnum):
    """
    The fields of a repository's Pages configuration this module reads or writes.
    """

    SOURCE = "source"
    """
    Where the site is built from, as a branch and a directory within it.
    """

    BRANCH = "branch"
    """
    The branch inside :attr:`SOURCE`.
    """

    PATH = "path"
    """
    The directory within that branch.
    """

    URL = "html_url"
    """
    Where GitHub reports the site is served from.
    """

    BUILD_TYPE = "build_type"
    """
    Which of GitHub's two build routes serves it.
    """


class PagesBuildType(StrEnum):
    """
    GitHub's two routes for building a Pages site.
    """

    LEGACY = "legacy"
    """
    Built from a branch's contents, which is the route this module configures.
    """

    WORKFLOW = "workflow"
    """
    Deployed by an Action, which the ``github-pages`` environment gates to the default
    branch - the rejection this module exists to route around.
    """


SITE_ROOT_PATH = "/"
"""
The directory within the branch that the site is served from.
"""


@dataclass
class PagesUnavailableError(RuntimeError):
    """
    Raised when a repository's Pages site can be neither read nor configured - the site
    would be built and pushed with nothing serving it.
    """

    repository: str
    """
    The repository whose site was being configured.
    """

    branch: str
    """
    The branch it was pointed at.
    """

    def __str__(self) -> str:
        """:return: Which repository reports no site, and where it was pointed."""
        return (
            f"GitHub reports no Pages URL for '{self.repository}' after pointing it at "
            f"'{self.branch}'."
        )


@dataclass
class PagesSite:
    """
    One repository's GitHub Pages site.
    """

    repository: str
    """
    The repository as ``owner/name``.
    """

    api: PagesTransport
    """
    The transport the configuration is read and written through.
    """

    def serve_from(self, branch: str) -> str:
        """
        Ensure the site is served from a branch, and report where.

        Enables Pages on a repository that has never had it, and repoints one already
        serving from somewhere else, so a fresh fork needs no settings visit.

        :param branch: The branch the built site is pushed to.
        :raises PagesUnavailableError: If GitHub reports no URL for the site afterwards.
        :return: The site's URL.
        """
        path = RepositoryEndpoints(self.repository).pages
        configuration = self.api.find(path)
        if configuration is None:
            configuration = self.api.send(
                HttpMethod.POST, path, self._source_body(branch)
            )
        elif not self._serves_from(configuration, branch):
            self.api.send(HttpMethod.PUT, path, self._source_body(branch))
            configuration = self.api.get(path)

        url = (configuration or {}).get(PagesField.URL)
        if not url:
            raise PagesUnavailableError(repository=self.repository, branch=branch)
        return url

    @staticmethod
    def _source_body(branch: str) -> dict[str, Any]:
        """
        The body asking GitHub to build the site from a branch.

        :param branch: The branch to serve from.
        :return: The request body.
        """
        return {
            PagesField.BUILD_TYPE.value: PagesBuildType.LEGACY.value,
            PagesField.SOURCE.value: {
                PagesField.BRANCH.value: branch,
                PagesField.PATH.value: SITE_ROOT_PATH,
            },
        }

    @staticmethod
    def _serves_from(configuration: dict[str, Any], branch: str) -> bool:
        """
        Whether a Pages configuration already serves the site from a branch's root.

        :param configuration: The configuration GitHub reported.
        :param branch: The branch the built site is pushed to.
        :return: Whether it is already pointed there.
        """
        source = configuration.get(PagesField.SOURCE) or {}
        return (
            source.get(PagesField.BRANCH) == branch
            and source.get(PagesField.PATH) == SITE_ROOT_PATH
        )


def main() -> int:
    """
    Point the site at the given branch and print its URL.

    See the module docstring for the CLI contract.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="The repository whose Pages site is configured, owner/name",
    )
    parser.add_argument(
        "--branch", required=True, help="The branch the built site is pushed to"
    )
    arguments = parser.parse_args()

    token = os.environ.get(CredentialVariable.GITHUB_TOKEN)
    if not token:
        raise GitHubAccessError(
            f"The {CredentialVariable.GITHUB_TOKEN} environment variable is not set."
        )

    site = PagesSite(repository=arguments.repository, api=TokenGitHubApi(token=token))
    print(site.serve_from(arguments.branch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
