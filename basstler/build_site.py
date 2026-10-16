#!/usr/bin/env python3
"""
Build every plan's dashboard and the master index as one static site.

Reads a ``plans`` directory checked out from the personal-notes branch, fetches the live
state of every pull request the plans reference, and writes the index plus one page per
plan under the output directory, ready for any static host. Nothing here needs a Claude
session, so the published site is the same for everyone who opens it.

Usage:
    python3 -m basstler.build_site \\
        --plans-directory <checkout>/.claude/personal/plans \\
        --site-url https://<owner>.github.io/<site-repository>/ \\
        --output _site

A plan whose manifest fails validation is reported and left out; every other plan is
still published.
"""

from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any

import yaml

from basstler.build_dashboard import (
    DashboardRenderer,
    Plan,
    PlanValidationError,
    PullRequestRecord,
    PullRequestsByRepository,
    validate_plan,
)
from basstler.build_index import PlanSummary, render_index_page
from basstler.maintenance_github import (
    GitHubRepository,
    GitHubRequestFailed,
    token_from_environment,
)
from basstler.plan_model import ItemStatus
from basstler.repository import Repository
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""


class SiteFile(StrEnum):
    """
    The file and directory names the site and its source are laid out with.
    """

    PAGE = "index.html"
    """
    The page a directory serves, for the index and every plan alike.
    """

    PLANS = "plans"
    """
    The site directory holding one subdirectory per plan.
    """

    NO_JEKYLL = ".nojekyll"
    """
    The marker that stops GitHub Pages from running Jekyll over already-rendered HTML.
    """

    MANIFEST = "plan.yaml"
    """
    A plan's manifest on the notes branch.
    """

    ROADMAP = "roadmap.md"
    """
    A plan's narrative on the notes branch.
    """


# %% a plan as the notes branch stores it


@dataclass
class PlanSource:
    """
    One plan's manifest and roadmap, as read from its directory on the notes branch.
    """

    directory_name: str
    """
    The plan's directory name, which is also the path its page is published under.
    """

    manifest: dict[str, Any]
    """
    The parsed ``plan.yaml``, not yet validated.
    """

    roadmap_text: str
    """
    The plan's ``roadmap.md``, or an empty string if it has none.
    """

    @classmethod
    def from_directory(cls, directory: Path) -> PlanSource:
        """
        Read one plan's directory.

        :param directory: The directory holding the plan's manifest.
        :return: The plan's source.
        """
        roadmap = directory / SiteFile.ROADMAP
        return cls(
            directory_name=directory.name,
            manifest=yaml.safe_load((directory / SiteFile.MANIFEST).read_text()),
            roadmap_text=roadmap.read_text() if roadmap.exists() else "",
        )

    @classmethod
    def every_plan_in(cls, plans_directory: Path) -> list[PlanSource]:
        """
        Read every plan under a ``plans`` directory, in directory-name order.

        :param plans_directory: The directory holding one subdirectory per plan.
        :return: Each subdirectory that carries a manifest.
        """
        return [
            cls.from_directory(manifest.parent)
            for manifest in sorted(plans_directory.glob(f"*/{SiteFile.MANIFEST}"))
        ]


# %% live pull request state


@dataclass(frozen=True)
class PullRequestReference:
    """
    One pull request a plan item names.
    """

    repository: str
    """
    The ``owner/repo`` the pull request is opened on.
    """

    number: int
    """
    The pull request's number.
    """


class PullRequestSource(ABC):
    """
    Where the live state of the pull requests a site shows comes from.
    """

    @abstractmethod
    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        """
        :param reference: The pull request to look up.
        :return: Its live state, or ``None`` if the repository has no such pull request.
        """

    @abstractmethod
    def issue_url(self, repository: str, number: int) -> str | None:
        """
        :param repository: The ``owner/repo`` the issue or pull request is opened on.
        :param number: Its number.
        :return: Its web page, or ``None`` if the repository has no such number.
        """


def pull_request_record_from_api(api_record: Mapping[str, Any]) -> PullRequestRecord:
    """
    Read the fields a dashboard classifies by out of one REST pull request object.

    :param api_record: The pull request, as the pulls API describes it.
    :return: The record a dashboard renders from.
    """
    return PullRequestRecord.from_mapping(
        {
            "state": api_record["state"],
            "draft": api_record["draft"],
            "merged_at": api_record["merged_at"],
            "labels": [label["name"] for label in api_record["labels"]],
        }
    )


@dataclass
class GitHubPullRequestSource(PullRequestSource):
    """
    Pull request state read from the GitHub REST API, once per repository.

    A repository's pull requests are listed in bulk on first use and kept, so a site
    covering many plans costs a handful of requests rather than one per item. A number
    the listing missed is read on its own.
    """

    token: str
    """
    The credential the requests authenticate with.
    """

    listed_pull_requests: dict[str, dict[int, PullRequestRecord]] = field(
        default_factory=dict
    )
    """
    Every repository listed so far, mapped to its pull requests by number.
    """

    def client_for(self, repository: str) -> GitHubRepository:
        """
        :param repository: The ``owner/repo`` to call.
        :return: A client for it.
        """
        return GitHubRepository(Repository.parse(repository), self.token)

    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        listed = self.pull_requests_of(reference.repository)
        if reference.number in listed:
            return listed[reference.number]
        api_record = self.read_if_present(
            lambda client: client.pull_request(reference.number), reference.repository
        )
        return None if api_record is None else pull_request_record_from_api(api_record)

    def issue_url(self, repository: str, number: int) -> str | None:
        api_record = self.read_if_present(
            lambda client: client.issue(number), repository
        )
        return None if api_record is None else str(api_record["html_url"])

    def pull_requests_of(self, repository: str) -> dict[int, PullRequestRecord]:
        """
        :param repository: The ``owner/repo`` to list.
        :return: Every pull request on it, by number, listed on first use.
        """
        if repository not in self.listed_pull_requests:
            self.listed_pull_requests[repository] = {
                api_record["number"]: pull_request_record_from_api(api_record)
                for api_record in self.client_for(repository).all_pull_requests()
            }
        return self.listed_pull_requests[repository]

    def read_if_present(
        self,
        read: Callable[[GitHubRepository], Mapping[str, Any]],
        repository: str,
    ) -> Mapping[str, Any] | None:
        """
        Make one read, treating an absent number as an answer rather than a failure.

        :param read: The call to make, given the repository's client.
        :param repository: The ``owner/repo`` to call.
        :return: The response, or ``None`` if the API answered that it does not exist.
        :raises GitHubRequestFailed: If the API refused the read for any other reason.
        """
        try:
            return read(self.client_for(repository))
        except GitHubRequestFailed as refused:
            if refused.status != HTTPStatus.NOT_FOUND:
                raise
            return None


# %% the site


@dataclass
class PublishedPlan:
    """
    One plan rendered to its page, with the entry the index lists it under.
    """

    page: str
    """
    The plan's rendered dashboard.
    """

    summary: PlanSummary
    """
    The plan's entry in the index.
    """


@dataclass
class PlanSite:
    """
    Every plan's dashboard plus the index linking them, rendered into one directory.
    """

    plans_directory: Path
    """
    The notes branch's ``plans`` directory, holding one subdirectory per plan.
    """

    site_url: str
    """
    The address the site is served from, which the index's links are built on.
    """

    pull_request_source: PullRequestSource
    """
    Where the live pull request state comes from.
    """

    def plan_url(self, directory_name: str) -> str:
        """
        :param directory_name: The plan's directory name.
        :return: The address its page is served from.
        """
        return f"{self.site_url.rstrip('/')}/{SiteFile.PLANS}/{directory_name}/"

    def build(self, output: Path) -> list[PlanSummary]:
        """
        Render the whole site into a directory.

        :param output: The directory to write the site into.
        :return: The index entry of every plan that was published.
        """
        published = {
            source.directory_name: self.publish(source)
            for source in PlanSource.every_plan_in(self.plans_directory)
            if self.is_publishable(source)
        }
        for directory_name, plan in published.items():
            page = output / SiteFile.PLANS / directory_name / SiteFile.PAGE
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(plan.page)

        summaries = [plan.summary for plan in published.values()]
        output.mkdir(parents=True, exist_ok=True)
        (output / SiteFile.PAGE).write_text(render_index_page(summaries))
        (output / SiteFile.NO_JEKYLL).touch()
        return summaries

    @staticmethod
    def is_publishable(source: PlanSource) -> bool:
        """
        :param source: The plan to check.
        :return: Whether its manifest passes validation, logging why if it does not.
        """
        try:
            validate_plan(source.manifest)
        except PlanValidationError as error:
            logger.warning(f"{source.directory_name} is not published: {error}")
            return False
        return True

    def publish(self, source: PlanSource) -> PublishedPlan:
        """
        Render one valid plan.

        :param source: The plan to render.
        :return: Its page and its index entry.
        """
        plan = Plan.from_mapping(source.manifest)
        renderer = DashboardRenderer(
            plan=plan,
            roadmap_text=source.roadmap_text,
            pull_requests_by_repository=self.pull_requests_of(plan),
            tracking_url=self.tracking_url_of(plan),
        )
        page, dashboard_summary = renderer.render()
        summary = PlanSummary(
            id=plan.id,
            title=plan.title,
            description=plan.description,
            done=dashboard_summary.status_counts.get(ItemStatus.DONE, 0),
            total=len(plan.items),
            dashboard_url=self.plan_url(source.directory_name),
        )
        return PublishedPlan(page=page, summary=summary)

    def pull_requests_of(self, plan: Plan) -> PullRequestsByRepository:
        """
        :param plan: The plan whose items to look up.
        :return: The live state of every pull request its items name, in the shape the
            dashboard renders from; a number the repository does not have is left out.
        """
        pull_requests: PullRequestsByRepository = {}
        for item in plan.items:
            if item.pull_request_number is None:
                continue
            reference = PullRequestReference(
                repository=item.repository or plan.default_repository,
                number=item.pull_request_number,
            )
            record = self.pull_request_source.pull_request(reference)
            if record is not None:
                pull_requests.setdefault(reference.repository, {})[
                    str(reference.number)
                ] = record
        return pull_requests

    def tracking_url_of(self, plan: Plan) -> str | None:
        """
        :param plan: The plan whose tracking issue to link.
        :return: The tracking issue's page, or ``None`` if the plan has none.
        """
        if plan.tracking_issue is None:
            return None
        return self.pull_request_source.issue_url(
            plan.default_repository, plan.tracking_issue
        )


def main() -> int:
    """
    Parse arguments and build the site. See the module docstring for the CLI contract.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--plans-directory",
        required=True,
        type=Path,
        help="The notes branch's plans directory",
    )
    parser.add_argument(
        "--site-url", required=True, help="The address the site is served from"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="The directory to write the site to"
    )
    arguments = parser.parse_args()

    site = PlanSite(
        plans_directory=arguments.plans_directory,
        site_url=arguments.site_url,
        pull_request_source=GitHubPullRequestSource(token=token_from_environment()),
    )
    summaries = site.build(arguments.output)
    logger.info(f"published {len(summaries)} plans to {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
