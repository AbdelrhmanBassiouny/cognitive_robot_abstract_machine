#!/usr/bin/env python3
"""
Build the whole plan-dashboard site statically, with no live session.

This is the headless entrypoint the Pages workflow runs: it discovers every plan on
the personal-notes branch, fetches the referenced pull requests' live state over
GitHub's REST API, drives ``refresh_dashboard.sh`` once per plan (manifest sync -
including its push of merged-to-done corrections back to the notes branch - plus the
dashboard render), and renders the master index over the results.

Usage:
    python3 build_site.py \\
        --output-directory _site \\
        --site-base-url https://<owner>.github.io/<repository>

Output layout: ``<output-directory>/index.html`` plus
``<output-directory>/plans/<plan-id>/index.html`` per plan, so the index's plan links
resolve on the published site.

The session-driven ``/plan-dashboard`` skill (Artifact publishing) is unaffected: both
paths drive the same underlying scripts over the same data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import yaml

from build_dashboard import ItemStatus
from build_index import PlanSummary, render_index_page
from errors import PlanDashboardError
from github_api import (
    GITHUB_TOKEN_VARIABLE,
    GitHubApi,
    PullRequest,
    fetch_issue_url,
    fetch_pull_requests,
)
from personal_notes import PersonalNotesBranch, PlanDocument
from script_arguments import ScriptArgumentParser

# %% site layout


class SitePath(StrEnum):
    """
    The fixed names inside the published site.
    """

    INDEX_PAGE = "index.html"
    """
    A directory's page - the master index at the root, a dashboard under its plan.
    """

    PLANS_DIRECTORY = "plans"
    """
    Where the per-plan dashboards live, one directory per plan identifier.
    """


REFRESH_DASHBOARD_SCRIPT = Path(__file__).with_name("refresh_dashboard.sh")
"""
The per-plan refresh the build drives: manifest sync, its correction push, then render.
"""

PULL_REQUEST_DATA_FILENAME = "pr_data.json"
"""
The scratch file each plan's fetched pull request state is handed over in.
"""


# %% the manifest fields the build reads


class PlanField(StrEnum):
    """
    The manifest fields the site build reads itself.

    Everything else a plan holds is read from the manifest file by the scripts this
    drives, not from here.
    """

    TITLE = "title"
    """
    The plan's own name, which the index entry shows.
    """

    DESCRIPTION = "description"
    """
    What the plan is for, shown under the title.
    """

    DEFAULT_REPOSITORY = "default_repository"
    """
    The repository an item's pull request number is resolved against unless the item
    names its own.
    """

    TRACKING_ISSUE = "tracking_issue"
    """
    The issue structural changes to the plan are proposed on.
    """

    ITEMS = "items"
    """
    The plan's items, which carry the pull request numbers to fetch.
    """


class PlanItemField(StrEnum):
    """
    The fields of one plan item the site build reads itself.
    """

    REPOSITORY = "repository"
    """
    The repository this item's pull request lives in, overriding the plan's default.
    """

    PULL_REQUEST_NUMBER = "pull_request_number"
    """
    The pull request whose live state the item is classified by.
    """


# %% driving one plan's refresh


class RefreshArgument(StrEnum):
    """
    The command-line options ``refresh_dashboard.sh`` takes.
    """

    PLAN_ID = "--plan-id"
    """
    The plan's identifier.
    """

    PLAN = "--plan"
    """
    The manifest file.
    """

    ROADMAP = "--roadmap"
    """
    The roadmap file.
    """

    PULL_REQUEST_DATA = "--pr-data"
    """
    The live pull request state to cross-check against.
    """

    OUTPUT = "--output"
    """
    Where to write the rendered dashboard.
    """

    TRACKING_URL = "--tracking-url"
    """
    The tracking issue's page, when the plan has one.
    """


class RefreshSummaryKey(StrEnum):
    """
    The keys of the one-line JSON summary ``refresh_dashboard.sh`` prints.
    """

    COUNTS = "counts"
    """
    How many of the plan's items carry each status.
    """


@dataclass(frozen=True)
class RefreshDashboardCommand:
    """
    One invocation of ``refresh_dashboard.sh``, as its own options rather than a list.

    Each option is a field, so a caller assembles the run by naming what it is handing
    over and the order and spelling of the command line are settled in one place.
    """

    plan_identifier: str
    """
    The plan being refreshed.
    """

    manifest_file: Path
    """
    The manifest read off the notes branch.
    """

    roadmap_file: Path
    """
    The roadmap read off the notes branch.
    """

    pull_request_data_file: Path
    """
    The live pull request state to cross-check against.
    """

    dashboard_page: Path
    """
    Where the rendered dashboard is written.
    """

    tracking_url: str | None = None
    """
    The plan's tracking issue URL, absent when the plan tracks no issue.
    """

    INTERPRETER: ClassVar[str] = "bash"
    """
    What runs the script, which is a shell script rather than a module.
    """

    def command_line(self, script: Path) -> list[str]:
        """
        :param script: The refresh script to run.
        :return: The command line running it with these options.
        """
        arguments = [
            self.INTERPRETER,
            str(script),
            RefreshArgument.PLAN_ID,
            self.plan_identifier,
            RefreshArgument.PLAN,
            str(self.manifest_file),
            RefreshArgument.ROADMAP,
            str(self.roadmap_file),
            RefreshArgument.PULL_REQUEST_DATA,
            str(self.pull_request_data_file),
            RefreshArgument.OUTPUT,
            str(self.dashboard_page),
        ]
        if self.tracking_url:
            arguments.extend([RefreshArgument.TRACKING_URL, self.tracking_url])
        return arguments


@dataclass
class DashboardRefreshError(PlanDashboardError):
    """Raised when ``refresh_dashboard.sh`` fails for one plan - a manifest that no
    longer validates, or a notes-branch write that could not be pushed."""

    plan_identifier: str
    """
    The plan whose refresh failed.
    """

    detail: str
    """
    What the refresh said about it.
    """

    def error_message(self) -> str:
        """:return: Which plan failed to refresh, and why."""
        return f"Refreshing '{self.plan_identifier}' failed: {self.detail}"


# %% what the build reports


@dataclass(frozen=True)
class PlanBuildResult:
    """
    What the build reports about one plan.
    """

    id: str
    """
    The plan's identifier.
    """

    done: int
    """
    How many of its items are done.
    """

    total: int
    """
    How many items it has.
    """

    @classmethod
    def from_summary(cls, summary: PlanSummary) -> PlanBuildResult:
        """
        :param summary: The plan's index entry.
        :return: The result reporting it.
        """
        return cls(id=summary.id, done=summary.done, total=summary.total)


@dataclass(frozen=True)
class SiteBuildReport:
    """
    The one-line JSON report the build prints on success.
    """

    plans: list[PlanBuildResult]
    """
    One result per plan built, in index order.
    """

    PLANS_KEY: ClassVar[str] = "plans"
    """
    The report's one top-level key.
    """

    @classmethod
    def from_summaries(cls, summaries: list[PlanSummary]) -> SiteBuildReport:
        """
        :param summaries: The index entries the build produced.
        :return: The report over them.
        """
        return cls([PlanBuildResult.from_summary(summary) for summary in summaries])

    def to_json(self) -> str:
        """:return: The report as JSON."""
        return json.dumps({self.PLANS_KEY: [asdict(plan) for plan in self.plans]})


# %% the build


@dataclass
class SiteBuilder:
    """
    Builds the static site: one dashboard page per plan, plus the master index.
    """

    output_directory: Path
    """
    Where the site is written.
    """

    site_base_url: str
    """
    The URL the site is published under, which the index's plan links are absolute
    against.
    """

    api: GitHubApi
    """
    The transport pull request and tracking-issue state is read through.
    """

    notes: PersonalNotesBranch
    """
    The personal-notes branch the plans are read from.
    """

    refresh_dashboard_script: Path = REFRESH_DASHBOARD_SCRIPT
    """
    The per-plan refresh script to drive.
    """

    pull_requests_by_repository: dict[str, dict[str, PullRequest]] = field(
        default_factory=dict
    )
    """Every repository's pull requests, fetched once and shared across the plans that
    reference it - plans overwhelmingly reference the same repository, and one listing
    per plan would repeat the same pages."""

    def build(self) -> list[PlanSummary]:
        """
        Build the whole site.

        :return: One summary per plan, in the order rendered into the index.
        """
        self.notes.fetch()
        summaries = [
            self._build_plan(plan_identifier)
            for plan_identifier in self.notes.plan_identifiers()
        ]
        index_page = self.output_directory / SitePath.INDEX_PAGE
        index_page.parent.mkdir(parents=True, exist_ok=True)
        index_page.write_text(render_index_page(summaries))
        return summaries

    def _build_plan(self, plan_identifier: str) -> PlanSummary:
        """
        Refresh and render one plan's dashboard page.

        :param plan_identifier: The plan to build.
        :return: The plan's entry for the master index.
        """
        manifest_text = self.notes.plan_document(plan_identifier, PlanDocument.MANIFEST)
        roadmap_text = self.notes.plan_document(plan_identifier, PlanDocument.ROADMAP)
        plan = yaml.safe_load(manifest_text)

        dashboard_page = (
            self.output_directory
            / SitePath.PLANS_DIRECTORY
            / plan_identifier
            / SitePath.INDEX_PAGE
        )
        dashboard_page.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as scratch:
            scratch_directory = Path(scratch)
            manifest_file = scratch_directory / PlanDocument.MANIFEST
            manifest_file.write_text(manifest_text)
            roadmap_file = scratch_directory / PlanDocument.ROADMAP
            roadmap_file.write_text(roadmap_text)
            pull_request_data_file = scratch_directory / PULL_REQUEST_DATA_FILENAME
            pull_request_data_file.write_text(
                json.dumps(self._pull_request_data_of(plan))
            )
            summary = self._refresh(
                RefreshDashboardCommand(
                    plan_identifier=plan_identifier,
                    manifest_file=manifest_file,
                    roadmap_file=roadmap_file,
                    pull_request_data_file=pull_request_data_file,
                    dashboard_page=dashboard_page,
                    tracking_url=self._tracking_url_of(plan),
                )
            )

        counts = summary[RefreshSummaryKey.COUNTS]
        return PlanSummary(
            id=plan_identifier,
            title=plan[PlanField.TITLE],
            description=(plan.get(PlanField.DESCRIPTION) or "").strip(),
            done=counts.get(ItemStatus.DONE, 0),
            total=sum(counts.values()),
            dashboard_url=self.dashboard_url_of(plan_identifier),
        )

    def dashboard_url_of(self, plan_identifier: str) -> str:
        """
        The published URL of one plan's dashboard page.

        :param plan_identifier: The plan to address.
        :return: Its absolute URL on the site.
        """
        base = self.site_base_url.rstrip("/")
        return f"{base}/{SitePath.PLANS_DIRECTORY}/{plan_identifier}/"

    def _refresh(self, command: RefreshDashboardCommand) -> dict[str, Any]:
        """
        Drive one plan's refresh script.

        :param command: The refresh to run.
        :raises DashboardRefreshError: If the refresh fails.
        :return: The refresh's own JSON summary.
        """
        refreshed = subprocess.run(
            command.command_line(self.refresh_dashboard_script),
            capture_output=True,
            text=True,
        )
        if refreshed.returncode != 0:
            raise DashboardRefreshError(
                plan_identifier=command.plan_identifier,
                detail=refreshed.stderr.strip(),
            )
        return json.loads(refreshed.stdout)

    def _pull_request_data_of(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Assemble the ``pr_data.json`` document for one plan's items.

        :param plan: The parsed plan manifest.
        :return: The live state of every pull request the plan references, keyed by
            repository then by pull request number.
        """
        document: dict[str, Any] = {}
        for repository, numbers in self._referenced_numbers_of(plan).items():
            pull_requests = self._pull_requests_of(repository)
            document[repository] = {
                number: pull_requests[number].to_pull_request_data_entry()
                for number in numbers
                if number in pull_requests
            }
        return document

    def _referenced_numbers_of(self, plan: dict[str, Any]) -> dict[str, set[str]]:
        """
        Which pull requests a plan's items reference, grouped by repository.

        :param plan: The parsed plan manifest.
        :return: The referenced numbers as strings, keyed by repository.
        """
        default_repository = plan.get(PlanField.DEFAULT_REPOSITORY, "")
        numbers_by_repository: dict[str, set[str]] = {}
        for item in plan.get(PlanField.ITEMS) or ():
            number = item.get(PlanItemField.PULL_REQUEST_NUMBER)
            if number is None:
                continue
            repository = item.get(PlanItemField.REPOSITORY) or default_repository
            numbers_by_repository.setdefault(repository, set()).add(str(number))
        return numbers_by_repository

    def _pull_requests_of(self, repository: str) -> dict[str, PullRequest]:
        """
        One repository's pull requests, fetched on first use and reused afterwards.

        :param repository: The repository as ``owner/name``.
        :return: Its pull requests, keyed by number as a string.
        """
        if repository not in self.pull_requests_by_repository:
            self.pull_requests_by_repository[repository] = fetch_pull_requests(
                repository, self.api
            )
        return self.pull_requests_by_repository[repository]

    def _tracking_url_of(self, plan: dict[str, Any]) -> str | None:
        """
        Resolve a plan's tracking issue to the URL its dashboard links to.

        :param plan: The parsed plan manifest.
        :return: The tracking URL, or ``None`` when the plan tracks no issue.
        """
        tracking_issue = plan.get(PlanField.TRACKING_ISSUE)
        if tracking_issue is None:
            return None
        return fetch_issue_url(
            plan.get(PlanField.DEFAULT_REPOSITORY, ""), tracking_issue, self.api
        )


# %% the command line


class SiteBuildOption(StrEnum):
    """
    The command-line options this script takes.
    """

    OUTPUT_DIRECTORY = "--output-directory"
    """
    Where to write the site.
    """

    SITE_BASE_URL = "--site-base-url"
    """
    The URL it will be published under.
    """


def main() -> int:
    """
    Parse arguments and build the site.

    See the module docstring for the CLI contract.
    """
    parser = ScriptArgumentParser(__doc__)
    parser.add(
        SiteBuildOption.OUTPUT_DIRECTORY,
        "Directory to write the site into (created if missing)",
    )
    parser.add(
        SiteBuildOption.SITE_BASE_URL,
        "The URL the site will be published under, e.g. the Pages URL",
    )
    arguments = parser.parse()

    repository_root = Path(__file__).resolve().parent.parent.parent.parent
    builder = SiteBuilder(
        output_directory=Path(arguments.output_directory),
        site_base_url=arguments.site_base_url,
        api=GitHubApi(token=os.environ.get(GITHUB_TOKEN_VARIABLE)),
        notes=PersonalNotesBranch.resolve(repository_root),
    )
    print(SiteBuildReport.from_summaries(builder.build()).to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
