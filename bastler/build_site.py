#!/usr/bin/env python3
"""
Build the whole plan-dashboard site statically, with no live session.

This is the headless entry point a Pages workflow runs on a schedule: it discovers every
plan on the personal-notes branch, fetches the referenced pull requests' live state
through :mod:`bastler.pull_request_state`, drives ``refresh_dashboard.sh`` once per plan - manifest
sync, including its push of merged-to-done corrections back to the notes branch, plus
the dashboard render - and renders the master index over the results.

Usage:
    python3 -m bastler.build_site \\
        --output-directory _site \\
        --site-base-url https://<owner>.github.io/<repository>

Output layout: ``<output-directory>/index.html`` plus
``<output-directory>/plans/<plan-id>/index.html`` per plan - relative paths mirror the
published site, so the index's plan links resolve on it.

The session-driven ``/plan-dashboard`` skill (Artifact publishing) is unaffected: both
paths share the same underlying modules.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import yaml

from bastler.build_dashboard import Plan, validate_plan
from bastler.build_index import PlanSummary, render_index_page
from bastler.package_layout import REPOSITORY_ROOT
from bastler.personal_notes import PersonalNotesBranch
from bastler.plan_item_bootstrap import PlanDocument
from bastler.plan_model import ItemStatus
from bastler.pull_request_state import (
    GitHubApi,
    IssueField,
    PullRequestExport,
    PullRequestFetcher,
    RepositoryEndpoints,
)

REFRESH_DASHBOARD_SCRIPT = (
    REPOSITORY_ROOT / ".claude" / "skills" / "plan-dashboard" / "refresh_dashboard.sh"
)
"""
The per-plan refresh script this build drives: manifest sync, correction push, render.
"""


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
    The pull request data file.
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

    CORRECTED = "corrected"
    """
    The items the manifest sync corrected to done.
    """

    COUNTS = "counts"
    """
    How many items carry each status.
    """


class SitePath(StrEnum):
    """
    The fixed names inside the published site.
    """

    INDEX_PAGE = "index.html"
    """A directory's page - the master index at the root, a dashboard under its plan."""

    PLANS_DIRECTORY = "plans"
    """
    Where the per-plan dashboards live, one directory per plan identifier.
    """


class PersonalNotesUnavailableError(RuntimeError):
    """
    Raised when the personal-notes branch cannot be fetched - there is nothing to build
    a site from.
    """


class MissingPlanDocumentError(LookupError):
    """
    Raised when a plan on the notes branch lacks a document the build needs.
    """


@dataclass(frozen=True)
class RefreshSummary:
    """
    What one plan's refresh reported.
    """

    corrected: list[Any]
    """
    The manifest corrections the sync pushed.
    """

    counts: dict[ItemStatus, int]
    """
    How many of the plan's items carry each status.
    """

    @classmethod
    def from_json(cls, text: str) -> RefreshSummary:
        """
        :param text: The refresh script's printed summary.
        :return: The parsed summary.
        """
        data = json.loads(text)
        return cls(
            corrected=list(data[RefreshSummaryKey.CORRECTED]),
            counts={
                ItemStatus(status): count
                for status, count in data[RefreshSummaryKey.COUNTS].items()
            },
        )

    @property
    def done(self) -> int:
        """:return: How many items are done."""
        return self.counts.get(ItemStatus.DONE, 0)

    @property
    def total(self) -> int:
        """:return: How many items the plan has."""
        return sum(self.counts.values())


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

    @classmethod
    def from_json(cls, text: str) -> SiteBuildReport:
        """
        :param text: A report as :meth:`to_json` printed it.
        :return: The parsed report.
        """
        return cls(
            [PlanBuildResult(**plan) for plan in json.loads(text)[cls.PLANS_KEY]]
        )


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
    """The URL the site will be published under - the index's plan links are absolute
    against it."""

    api: GitHubApi
    """
    The GitHub transport pull request data is fetched through.
    """

    repository_root: Path = REPOSITORY_ROOT
    """
    The clone whose configuration resolves the personal-notes remote, and in which the
    notes branch is fetched.
    """

    refresh_dashboard_script: Path = REFRESH_DASHBOARD_SCRIPT
    """
    The per-plan refresh script to drive.
    """

    PULL_REQUEST_DATA_FILENAME: ClassVar[str] = "pr_data.json"
    """
    The scratch file the fetched pull request data is handed over in.
    """

    def build(self) -> list[PlanSummary]:
        """
        Build the whole site.

        :raises PersonalNotesUnavailableError: When the personal-notes branch cannot be
            fetched.
        :return: One summary per plan, in the order rendered into the index.
        """
        notes = PersonalNotesBranch(self.repository_root)
        if not notes.fetch():
            raise PersonalNotesUnavailableError(
                "The personal-notes branch could not be fetched - nothing to build."
            )
        summaries = [
            self._build_plan(plan_identifier, notes)
            for plan_identifier in notes.plan_identifiers()
        ]
        index_page = self.output_directory / SitePath.INDEX_PAGE
        index_page.parent.mkdir(parents=True, exist_ok=True)
        index_page.write_text(render_index_page(summaries))
        return summaries

    def _build_plan(
        self, plan_identifier: str, notes: PersonalNotesBranch
    ) -> PlanSummary:
        """
        Refresh and render one plan's dashboard page.

        :param plan_identifier: The plan to build.
        :param notes: The fetched notes branch to read it from.
        :return: The plan's entry for the master index.
        """
        manifest_text = self._read_required_document(
            notes, plan_identifier, PlanDocument.MANIFEST
        )
        roadmap_text = (
            notes.read_plan_document(plan_identifier, PlanDocument.ROADMAP) or ""
        )
        mapping = yaml.safe_load(manifest_text)
        validate_plan(mapping)
        plan = Plan.from_mapping(mapping)

        dashboard_page = (
            self.output_directory
            / SitePath.PLANS_DIRECTORY
            / plan_identifier
            / SitePath.INDEX_PAGE
        )
        dashboard_page.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as scratch:
            scratch_directory = Path(scratch)
            plan_file = scratch_directory / PlanDocument.MANIFEST
            plan_file.write_text(manifest_text)
            roadmap_file = scratch_directory / PlanDocument.ROADMAP
            roadmap_file.write_text(roadmap_text)
            pull_request_data_file = scratch_directory / self.PULL_REQUEST_DATA_FILENAME
            pull_request_data_file.write_text(
                json.dumps(self._pull_request_data_of(plan))
            )

            refresh_arguments = [
                "bash",
                str(self.refresh_dashboard_script),
                RefreshArgument.PLAN_ID,
                plan_identifier,
                RefreshArgument.PLAN,
                str(plan_file),
                RefreshArgument.ROADMAP,
                str(roadmap_file),
                RefreshArgument.PULL_REQUEST_DATA,
                str(pull_request_data_file),
                RefreshArgument.OUTPUT,
                str(dashboard_page),
            ]
            tracking_url = self._tracking_url_of(plan)
            if tracking_url:
                refresh_arguments.extend([RefreshArgument.TRACKING_URL, tracking_url])
            refresh = subprocess.run(
                refresh_arguments, check=True, capture_output=True, text=True
            )

        summary = RefreshSummary.from_json(refresh.stdout)
        return PlanSummary(
            id=plan_identifier,
            title=plan.title,
            description=plan.description.strip(),
            done=summary.done,
            total=summary.total,
            dashboard_url=self._dashboard_url_of(plan_identifier),
        )

    def _dashboard_url_of(self, plan_identifier: str) -> str:
        """
        :param plan_identifier: A plan.
        :return: Where its dashboard page is published, absolute against the site URL.
        """
        return (
            f"{self.site_base_url.rstrip('/')}/{SitePath.PLANS_DIRECTORY}/"
            f"{plan_identifier}/"
        )

    @staticmethod
    def _read_required_document(
        notes: PersonalNotesBranch, plan_identifier: str, document: PlanDocument
    ) -> str:
        """
        :param notes: The fetched notes branch.
        :param plan_identifier: The plan whose document to read.
        :param document: Which document.
        :raises MissingPlanDocumentError: When the plan does not carry it.
        :return: The document's content.
        """
        content = notes.read_plan_document(plan_identifier, document)
        if content is None:
            raise MissingPlanDocumentError(
                f"{plan_identifier} has no {document} on the personal-notes branch."
            )
        return content

    def _pull_request_data_of(self, plan: Plan) -> dict[str, Any]:
        """
        Fetch the live state of every pull request a plan's items reference.

        :param plan: The parsed plan.
        :return: The ``pr_data.json`` document, chip fields included.
        """
        numbers_by_repository: dict[str, list[int]] = {}
        for item in plan.items:
            if item.pull_request_number is None:
                continue
            repository = item.repository or plan.default_repository
            numbers_by_repository.setdefault(repository, []).append(
                item.pull_request_number
            )

        document: dict[str, Any] = {}
        for repository, numbers in numbers_by_repository.items():
            states = PullRequestFetcher(repository, self.api).fetch(numbers=numbers)
            document.update(
                PullRequestExport(repository, states).to_pull_request_data_document()
            )
        return document

    def _tracking_url_of(self, plan: Plan) -> str | None:
        """
        Resolve a plan's tracking issue to its page on GitHub.

        Resolved through the issues endpoint, which covers both a real issue and a pull
        request stored under the same field, instead of guessing the URL path.

        :param plan: The parsed plan.
        :return: The tracking URL, or ``None`` when the plan has no tracking issue.
        """
        if plan.tracking_issue is None:
            return None
        endpoints = RepositoryEndpoints(plan.default_repository)
        issue = self.api.get(endpoints.issue(plan.tracking_issue))
        return issue[IssueField.HTML_URL]


def main() -> int:
    """
    Parse arguments and build the site.

    See the module docstring for the command-line contract.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        help="Directory to write the site into (created if missing)",
    )
    parser.add_argument(
        "--site-base-url",
        required=True,
        help="The URL the site will be published under, e.g. the Pages URL",
    )
    arguments = parser.parse_args()

    builder = SiteBuilder(
        output_directory=Path(arguments.output_directory),
        site_base_url=arguments.site_base_url,
        api=GitHubApi.resolve(),
    )
    print(SiteBuildReport.from_summaries(builder.build()).to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
