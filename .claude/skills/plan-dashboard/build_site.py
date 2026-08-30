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

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from build_index import PlanSummary, render_index_page
from github_api import (
    GITHUB_TOKEN_VARIABLE,
    GitHubApi,
    PullRequest,
    fetch_issue_url,
    fetch_pull_requests,
)
from personal_notes import PersonalNotesBranch

# %% site layout

INDEX_PAGE_FILENAME = "index.html"
"""
The filename a static host serves for a directory URL.
"""

DASHBOARD_DIRECTORY = "plans"
"""
The subdirectory of the site holding one directory per plan's dashboard.
"""

REFRESH_DASHBOARD_SCRIPT = Path(__file__).with_name("refresh_dashboard.sh")
"""
The per-plan refresh the build drives: manifest sync, its correction push, then render.
"""

# %% the manifest fields the build reads


class PlanField(StrEnum):
    """
    The manifest fields the site build reads itself.

    Everything else a plan holds is read from the manifest file by the scripts this
    drives, not from here.
    """

    TITLE = "title"
    DESCRIPTION = "description"
    DEFAULT_REPOSITORY = "default_repository"
    TRACKING_ISSUE = "tracking_issue"
    ITEMS = "items"


class PlanItemField(StrEnum):
    """
    The fields of one plan item the site build reads itself.
    """

    REPOSITORY = "repository"
    PULL_REQUEST_NUMBER = "pull_request_number"


DONE_COUNT_KEY = "done"
"""
The status ``refresh_dashboard.sh``'s summary counts finished items under.
"""

COUNTS_KEY = "counts"
"""
The key of that summary's per-status counts.
"""


class DashboardRefreshError(RuntimeError):
    """Raised when ``refresh_dashboard.sh`` fails for one plan - a manifest that no
    longer validates, or a notes-branch write that could not be pushed."""


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
        index_page = self.output_directory / INDEX_PAGE_FILENAME
        index_page.parent.mkdir(parents=True, exist_ok=True)
        index_page.write_text(render_index_page(summaries))
        return summaries

    def _build_plan(self, plan_identifier: str) -> PlanSummary:
        """
        Refresh and render one plan's dashboard page.

        :param plan_identifier: The plan to build.
        :return: The plan's entry for the master index.
        """
        manifest_text = self.notes.plan_manifest(plan_identifier)
        roadmap_text = self.notes.plan_roadmap(plan_identifier)
        plan = yaml.safe_load(manifest_text)

        dashboard_page = (
            self.output_directory
            / DASHBOARD_DIRECTORY
            / plan_identifier
            / INDEX_PAGE_FILENAME
        )
        dashboard_page.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as scratch:
            scratch_directory = Path(scratch)
            manifest_file = scratch_directory / "plan.yaml"
            manifest_file.write_text(manifest_text)
            roadmap_file = scratch_directory / "roadmap.md"
            roadmap_file.write_text(roadmap_text)
            pull_request_data_file = scratch_directory / "pr_data.json"
            pull_request_data_file.write_text(
                json.dumps(self._pull_request_data_of(plan))
            )
            summary = self._refresh(
                plan_identifier=plan_identifier,
                manifest_file=manifest_file,
                roadmap_file=roadmap_file,
                pull_request_data_file=pull_request_data_file,
                dashboard_page=dashboard_page,
                tracking_url=self._tracking_url_of(plan),
            )

        counts = summary[COUNTS_KEY]
        return PlanSummary(
            id=plan_identifier,
            title=plan[PlanField.TITLE],
            description=(plan.get(PlanField.DESCRIPTION) or "").strip(),
            done=counts.get(DONE_COUNT_KEY, 0),
            total=sum(counts.values()),
            dashboard_url=self.dashboard_url_of(plan_identifier),
        )

    def dashboard_url_of(self, plan_identifier: str) -> str:
        """
        The published URL of one plan's dashboard page.

        :param plan_identifier: The plan to address.
        :return: Its absolute URL on the site.
        """
        return (
            f"{self.site_base_url.rstrip('/')}/{DASHBOARD_DIRECTORY}/{plan_identifier}/"
        )

    def _refresh(
        self,
        plan_identifier: str,
        manifest_file: Path,
        roadmap_file: Path,
        pull_request_data_file: Path,
        dashboard_page: Path,
        tracking_url: str | None,
    ) -> dict[str, Any]:
        """
        Drive one plan's refresh script.

        :param plan_identifier: The plan being refreshed.
        :param manifest_file: The manifest read off the notes branch.
        :param roadmap_file: The roadmap read off the notes branch.
        :param pull_request_data_file: The live pull request state to cross-check
            against.
        :param dashboard_page: Where the rendered dashboard is written.
        :param tracking_url: The plan's tracking issue URL, if it has one.
        :raises DashboardRefreshError: If the refresh fails.
        :return: The refresh's own JSON summary.
        """
        arguments = [
            "bash",
            str(self.refresh_dashboard_script),
            "--plan-id",
            plan_identifier,
            "--plan",
            str(manifest_file),
            "--roadmap",
            str(roadmap_file),
            "--pr-data",
            str(pull_request_data_file),
            "--output",
            str(dashboard_page),
        ]
        if tracking_url:
            arguments.extend(["--tracking-url", tracking_url])
        refreshed = subprocess.run(arguments, capture_output=True, text=True)
        if refreshed.returncode != 0:
            raise DashboardRefreshError(
                f"Refreshing '{plan_identifier}' failed: {refreshed.stderr.strip()}"
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


def main() -> int:
    """
    Parse arguments and build the site.

    See the module docstring for the CLI contract.
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

    repository_root = Path(__file__).resolve().parent.parent.parent.parent
    builder = SiteBuilder(
        output_directory=Path(arguments.output_directory),
        site_base_url=arguments.site_base_url,
        api=GitHubApi(token=os.environ.get(GITHUB_TOKEN_VARIABLE)),
        notes=PersonalNotesBranch.resolve(repository_root),
    )
    summaries = builder.build()
    print(
        json.dumps(
            {
                "plans": [
                    {"id": summary.id, "done": summary.done, "total": summary.total}
                    for summary in summaries
                ]
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
