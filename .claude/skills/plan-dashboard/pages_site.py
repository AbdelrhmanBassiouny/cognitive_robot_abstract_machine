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
    python3 pages_site.py --repository <owner/name> --branch <branch>

Prints the site's URL, which is read from GitHub rather than composed here: a custom
domain or an owner-root repository is served from somewhere no formula would guess.

Requires a credential with Pages write access in the environment (see
``github_api.GITHUB_TOKEN_VARIABLE``); enabling Pages is the one write the dashboards'
tooling makes to a repository's own settings.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from github_api import GITHUB_TOKEN_VARIABLE, GitHubApi, HttpMethod

# %% the Pages configuration


class PagesField(StrEnum):
    """
    The fields of a repository's Pages configuration this module reads or writes.
    """

    SOURCE = "source"
    BRANCH = "branch"
    PATH = "path"
    URL = "html_url"
    BUILD_TYPE = "build_type"


SITE_ROOT_PATH = "/"
"""
The directory within the branch that the site is served from.
"""

LEGACY_BUILD_TYPE = "legacy"
"""
GitHub's name for building the site from a branch's contents.

The alternative, ``workflow``, is the Actions deployment this module exists to avoid.
"""


class PagesUnavailableError(RuntimeError):
    """Raised when a repository's Pages site can be neither read nor configured - the
    site would be built and pushed with nothing serving it."""


@dataclass
class PagesSite:
    """
    One repository's GitHub Pages site.
    """

    repository: str
    """
    The repository as ``owner/name``.
    """

    api: GitHubApi
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
        configuration = self.api.find(self._path)
        if configuration is None:
            configuration = self.api.send(
                HttpMethod.POST, self._path, self._source_payload(branch)
            )
        elif not self._serves_from(configuration, branch):
            self.api.send(HttpMethod.PUT, self._path, self._source_payload(branch))
            configuration = self.api.get(self._path)

        url = (configuration or {}).get(PagesField.URL)
        if not url:
            raise PagesUnavailableError(
                f"GitHub reports no Pages URL for '{self.repository}' after pointing it "
                f"at '{branch}'."
            )
        return url

    @property
    def _path(self) -> str:
        """
        The API path of this repository's Pages configuration.
        """
        return f"repos/{self.repository}/pages"

    @staticmethod
    def _source_payload(branch: str) -> dict[str, Any]:
        """
        The body asking GitHub to build the site from a branch.

        :param branch: The branch to serve from.
        :return: The request body.
        """
        return {
            PagesField.BUILD_TYPE.value: LEGACY_BUILD_TYPE,
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
        "--repository", required=True, help="The repository, owner/name"
    )
    parser.add_argument(
        "--branch", required=True, help="The branch the built site is pushed to"
    )
    arguments = parser.parse_args()

    site = PagesSite(
        repository=arguments.repository,
        api=GitHubApi(token=os.environ.get(GITHUB_TOKEN_VARIABLE)),
    )
    print(site.serve_from(arguments.branch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
