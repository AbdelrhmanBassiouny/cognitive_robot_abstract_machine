#!/usr/bin/env python3
"""
Classify one item's dependencies as ready or not-ready to build on, reusing
build_dashboard.py's own live-state classification and readiness rule.

plan-item-kickoff and plan-item-resolve both need this exact question
answered - "is it actually safe to stack new work on top of item X's
dependencies?" - and previously re-derived the rule
(:meth:`build_dashboard.Item.is_ready_to_unblock_dependents`) in their own
SKILL.md prose instead of calling the code that already implements and tests
it. This script is that single call site.

Usage:
    python3 check_dependency_readiness.py \\
        --plan /tmp/plan.yaml \\
        --pr-data /tmp/pr_data.json \\
        --item <item-id> \\
        [--plans-dir /tmp/plans]

pr_data.json shape: identical to build_dashboard.py's module docstring, and
--plans-dir is the same directory build_dashboard.py takes, so a dependency
naming <plan-id>/<item-id> resolves the way the dashboard resolves it.

Prints a one-line JSON list to stdout, one entry per entry in the item's
``depends_on``, in that order:
    [{"identifier": "<dependency reference>", "title": "<dependency title>",
      "live_state": "<LiveState value>", "is_ready": <bool>}, ...]
A dependency that doesn't resolve to a known item is reported with
``"title": null, "live_state": null, "is_ready": false`` - a broken
``depends_on`` reference is never silently treated as ready.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from bastler.build_dashboard import (
    Dependency,
    DependencyResolver,
    LiveState,
    Plan,
    PlanDirectory,
    PlanValidationError,
    PullRequestsByRepository,
    load_pull_requests_by_repository,
    validate_plan,
)


class UnknownItemError(ValueError):
    """
    Raised when the requested item id doesn't exist in the plan.
    """


class ReadinessField(StrEnum):
    """
    The keys one dependency's readiness carries once serialized.
    """

    IDENTIFIER = "identifier"
    TITLE = "title"
    LIVE_STATE = "live_state"
    IS_READY = "is_ready"


@dataclass(frozen=True)
class DependencyReadiness:
    """
    One ``depends_on`` entry, and whether it is safe to build on.
    """

    identifier: str
    """
    The entry, as the manifest wrote it.
    """

    title: str | None
    """
    The referenced item's title, or ``None`` when nothing resolves it.
    """

    live_state: LiveState | None
    """
    The referenced item's live GitHub state, or ``None`` when nothing resolves it.
    """

    is_ready: bool
    """
    Whether a dependent can safely stack its own branch on it.
    """

    @classmethod
    def of(cls, dependency: Dependency) -> DependencyReadiness:
        """
        Report one dependency whose live state has already been classified.

        :param dependency: The dependency to report.
        :return: That dependency's readiness.
        """
        return cls(
            identifier=dependency.reference.text,
            title=dependency.title,
            live_state=dependency.live_state,
            is_ready=dependency.is_ready_to_unblock_dependents(),
        )

    def to_json(self) -> dict[str, Any]:
        """
        This readiness as the one entry the script prints for it.
        """
        return {
            ReadinessField.IDENTIFIER.value: self.identifier,
            ReadinessField.TITLE.value: self.title,
            ReadinessField.LIVE_STATE.value: (
                self.live_state.value if self.live_state else None
            ),
            ReadinessField.IS_READY.value: self.is_ready,
        }


def dependency_readiness(
    plan: Plan,
    item_identifier: str,
    pull_requests_by_repository: PullRequestsByRepository,
    plan_directory: PlanDirectory | None = None,
) -> list[DependencyReadiness]:
    """
    Classify every dependency of ``item_identifier`` as ready or not.

    :param plan: The already-validated plan.
    :param item_identifier: The effective identifier (``id`` or ``branch``) of the item
        whose dependencies should be checked.
    :param pull_requests_by_repository: Live pull request state for every repository
        referenced by the plan's items, and by any plan they depend on.
    :param plan_directory: The other plans a ``<plan-id>/<item-id>`` dependency resolves
        against, or ``None`` when only this plan's own items are available.
    :raises UnknownItemError: If ``item_identifier`` isn't in the plan.
    :return: One readiness per entry in the item's ``depends_on``, in that order.
    """
    item = next(
        (item for item in plan.items if item.identifier == item_identifier), None
    )
    if item is None:
        raise UnknownItemError(f"no item {item_identifier!r} in plan {plan.id!r}")

    resolver = DependencyResolver(plan=plan, plan_directory=plan_directory)
    resolver.classify_live_states(pull_requests_by_repository)
    return [
        DependencyReadiness.of(dependency)
        for dependency in resolver.dependencies_of(item)
    ]


def main() -> int:
    """
    Parse arguments, classify the item's dependencies, and print the result.

    See the module docstring for the CLI contract.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--plan", required=True, help="Path to plan.yaml")
    parser.add_argument(
        "--pr-data",
        required=True,
        help='Path to a JSON file: {"owner/repo": {"pr_number": {...}}}',
    )
    parser.add_argument("--item", required=True, help="The item id to check")
    parser.add_argument(
        "--plans-dir",
        default=None,
        help=(
            "Path to the directory holding every plan (<plan-id>/plan.yaml), "
            "required only by a manifest whose depends_on names another plan"
        ),
    )
    arguments = parser.parse_args()

    plan_directory = (
        PlanDirectory.at(Path(arguments.plans_dir)) if arguments.plans_dir else None
    )
    raw_plan = yaml.safe_load(Path(arguments.plan).read_text())
    try:
        validate_plan(raw_plan, plan_directory)
    except PlanValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    plan = Plan.from_mapping(raw_plan)

    raw_pull_request_data = json.loads(Path(arguments.pr_data).read_text())
    pull_requests_by_repository = load_pull_requests_by_repository(
        raw_pull_request_data
    )

    try:
        results = dependency_readiness(
            plan, arguments.item, pull_requests_by_repository, plan_directory
        )
    except UnknownItemError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps([readiness.to_json() for readiness in results]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
