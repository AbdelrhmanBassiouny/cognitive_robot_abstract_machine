#!/usr/bin/env python3
"""
Build the whole plan-dashboard site statically, with no live session.

This is the headless entrypoint a Pages workflow runs on a schedule: it discovers
every plan on the personal-notes branch, fetches the referenced pull requests' live
state through :mod:`development_tooling.pr_state`, drives ``refresh_dashboard.sh``
once per plan (manifest sync - including its push of merged-to-done corrections back
to the notes branch - plus the dashboard render), and renders the master index over
the results.

Usage:
    python3 build_site.py \\
        --output-directory _site \\
        --site-base-url https://<owner>.github.io/<repository>

Output layout: ``<output-directory>/index.html`` plus
``<output-directory>/plans/<plan-id>/index.html`` per plan - relative paths mirror
the published site, so the index's plan links resolve on it.

The session-driven ``/plan-dashboard`` skill (Artifact publishing) is unaffected:
both paths share the same underlying scripts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from build_index import PlanSummary, render_index_page

# The shared PR-state and personal-notes layers live in the repository-root
# development_tooling package; this script is planned to move inside it, at which
# point this path insertion goes away.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from development_tooling.personal_notes import (
    PERSONAL_PLANS_DIRECTORY,
    fetch_personal_notes_reference,
    plan_identifiers_at_reference,
    read_file_at_reference,
)
from development_tooling.pr_state import (
    GitHubApi,
    fetch_pull_request_states,
    resolve_github_api,
)


class PersonalNotesUnavailableError(RuntimeError):
    """Raised when the personal-notes branch cannot be fetched - there is nothing to
    build a site from."""


@dataclass
class SiteBuilder:
    """
    Builds the static site: one dashboard page per plan, plus the master index.
    """

    output_directory: Path
    """Where the site is written."""

    site_base_url: str
    """The URL the site will be published under - the index's plan links are
    absolute against it."""

    api: GitHubApi
    """The GitHub transport pull request data is fetched through."""

    repository_root: Path
    """
    The repository clone whose configuration resolves the personal-notes remote, and in
    which the notes branch is fetched.
    """

    refresh_dashboard_script: Path
    """The per-plan refresh script to drive (sync, correction push, render)."""

    def build(self) -> list[PlanSummary]:
        """
        Build the whole site.

        :raises PersonalNotesUnavailableError: When the personal-notes branch cannot be
            fetched.
        :return: One summary per plan, in the order rendered into the index.
        """
        reference = fetch_personal_notes_reference(repository_root=self.repository_root)
        if reference is None:
            raise PersonalNotesUnavailableError(
                "The personal-notes branch could not be fetched - nothing to build."
            )
        summaries = [
            self._build_plan(plan_identifier, reference)
            for plan_identifier in plan_identifiers_at_reference(
                reference, repository_root=self.repository_root
            )
        ]
        index_page = self.output_directory / "index.html"
        index_page.parent.mkdir(parents=True, exist_ok=True)
        index_page.write_text(render_index_page(summaries))
        return summaries

    def _build_plan(self, plan_identifier: str, reference: str) -> PlanSummary:
        """
        Refresh and render one plan's dashboard page.

        :param plan_identifier: The plan to build.
        :param reference: The git reference the notes branch was fetched to.
        :return: The plan's entry for the master index.
        """
        plan_mapping = yaml.safe_load(
            self._read_plan_file(plan_identifier, reference, "plan.yaml")
        )
        roadmap_text = (
            read_file_at_reference(
                reference,
                f"{PERSONAL_PLANS_DIRECTORY}/{plan_identifier}/roadmap.md",
                repository_root=self.repository_root,
            )
            or ""
        )

        dashboard_page = (
            self.output_directory / "plans" / plan_identifier / "index.html"
        )
        dashboard_page.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as scratch:
            scratch_directory = Path(scratch)
            plan_file = scratch_directory / "plan.yaml"
            plan_file.write_text(
                self._read_plan_file(plan_identifier, reference, "plan.yaml")
            )
            roadmap_file = scratch_directory / "roadmap.md"
            roadmap_file.write_text(roadmap_text)
            pull_request_data_file = scratch_directory / "pr_data.json"
            pull_request_data_file.write_text(
                json.dumps(self._pull_request_data_of(plan_mapping))
            )

            refresh_arguments = [
                "bash",
                str(self.refresh_dashboard_script),
                "--plan-id",
                plan_identifier,
                "--plan",
                str(plan_file),
                "--roadmap",
                str(roadmap_file),
                "--pr-data",
                str(pull_request_data_file),
                "--output",
                str(dashboard_page),
            ]
            tracking_url = self._tracking_url_of(plan_mapping)
            if tracking_url:
                refresh_arguments.extend(["--tracking-url", tracking_url])
            refresh = subprocess.run(
                refresh_arguments, check=True, capture_output=True, text=True
            )

        counts = json.loads(refresh.stdout)["counts"]
        return PlanSummary(
            id=plan_identifier,
            title=plan_mapping["title"],
            description=plan_mapping.get("description", "").strip(),
            done=counts.get("done", 0),
            total=sum(counts.values()),
            dashboard_url=(
                f"{self.site_base_url.rstrip('/')}/plans/{plan_identifier}/"
            ),
        )

    def _read_plan_file(
        self, plan_identifier: str, reference: str, file_name: str
    ) -> str:
        """
        Read one of a plan's files off the notes reference.

        :param plan_identifier: The plan whose file to read.
        :param reference: The git reference the notes branch was fetched to.
        :param file_name: The file inside the plan's directory.
        :return: The file content.
        """
        content = read_file_at_reference(
            reference,
            f"{PERSONAL_PLANS_DIRECTORY}/{plan_identifier}/{file_name}",
            repository_root=self.repository_root,
        )
        if content is None:
            raise FileNotFoundError(
                f"{plan_identifier} has no {file_name} on the personal-notes branch."
            )
        return content

    def _pull_request_data_of(self, plan_mapping: dict[str, Any]) -> dict[str, Any]:
        """
        Fetch the live state of every pull request a plan's items reference.

        :param plan_mapping: The parsed plan manifest.
        :return: The ``pr_data.json`` document, chip fields included.
        """
        default_repository = plan_mapping.get("default_repository", "")
        numbers_by_repository: dict[str, list[int]] = {}
        for item in plan_mapping.get("items", []):
            number = item.get("pull_request_number")
            if number is None:
                continue
            repository = item.get("repository") or default_repository
            numbers_by_repository.setdefault(repository, []).append(number)

        document: dict[str, Any] = {}
        for repository, numbers in numbers_by_repository.items():
            states = fetch_pull_request_states(repository, self.api, numbers=numbers)
            document[repository] = {
                str(state.number): state.to_pull_request_data_entry()
                for state in states
            }
        return document

    def _tracking_url_of(self, plan_mapping: dict[str, Any]) -> str | None:
        """
        Resolve a plan's tracking issue to its ``html_url``.

        Resolved through the issues endpoint, which covers both a real issue and a pull
        request stored under the same field (a repository with Issues disabled), instead
        of guessing the URL path.

        :param plan_mapping: The parsed plan manifest.
        :return: The tracking URL, or ``None`` when the plan has no tracking issue.
        """
        tracking_issue = plan_mapping.get("tracking_issue")
        if tracking_issue is None:
            return None
        repository = plan_mapping.get("default_repository", "")
        issue = self.api.get(f"repos/{repository}/issues/{tracking_issue}")
        return issue["html_url"]


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

    builder = SiteBuilder(
        output_directory=Path(arguments.output_directory),
        site_base_url=arguments.site_base_url,
        api=resolve_github_api(),
        repository_root=Path(__file__).parent.parent.parent.parent,
        refresh_dashboard_script=Path(__file__).with_name("refresh_dashboard.sh"),
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
