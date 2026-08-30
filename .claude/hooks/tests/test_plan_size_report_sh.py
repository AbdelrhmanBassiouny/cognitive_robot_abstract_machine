"""
Integration tests for plan-size-report.sh.

Runs against a local ``git init --bare`` fixture rather than a real remote, so no test
needs network access or a real personal-notes branch.
"""

import subprocess

import pytest
import yaml

import missing_requirements
import plan_item_bootstrap
import plan_manifest_tools
import plan_size_budget
from plan_item_bootstrap import (
    HOOKS_DIRECTORY,
    PLANS_DIRECTORY,
    HookScript,
    PlanDocument,
)
from missing_requirements import RequirementsFile
from plan_size_budget import PlanSize, SizeBudget, SizeReport
from scratch_repository import HOOKS_SOURCE_DIRECTORY, ScratchRepository

REQUIREMENTS_PATH = f"{HOOKS_DIRECTORY}/{RequirementsFile.FILENAME}"
"""
Where the hooks list their Python dependencies, composed from the two definitions that
own its halves rather than spelled again here.
"""

ABSENT_DISTRIBUTION = "no-such-distribution-exists"
"""
A name no environment can have installed, so a requirements file naming it is always
reported as missing.
"""


def plan_files(plan_id: str, item_count: int = 0, roadmap_line_count: int = 0) -> dict:
    """
    Build one plan's two notes-branch files.

    :param plan_id: The plan's id, used as its directory name and its ``id`` field.
    :param item_count: How many items its manifest declares.
    :param roadmap_line_count: How many lines its roadmap holds.
    :return: File contents, keyed by path relative to the notes branch's root.
    """
    plan_directory = f"{PLANS_DIRECTORY}/{plan_id}"
    manifest = {
        "id": plan_id,
        "items": [{"id": f"item-{number}"} for number in range(item_count)],
    }
    return {
        f"{plan_directory}/{PlanDocument.MANIFEST}": yaml.safe_dump(manifest),
        f"{plan_directory}/{PlanDocument.ROADMAP}": "".join(
            f"roadmap line {number}\n" for number in range(roadmap_line_count)
        ),
    }


@pytest.fixture
def report_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository carrying the real plan-size-report.sh and everything it runs,
    with no notes branch published yet - each test publishes the plans it is about.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready to publish plans and run the report against.
    """
    scratch_repository.install_hook_scripts(
        HookScript.CONFIGURATION, HookScript.PLAN_SIZE_REPORT
    )
    scratch_repository.install_hook_modules(
        plan_size_budget, plan_manifest_tools, missing_requirements, plan_item_bootstrap
    )
    scratch_repository.write(
        REQUIREMENTS_PATH,
        (HOOKS_SOURCE_DIRECTORY / RequirementsFile.FILENAME).read_text(),
    )
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def run_report(repository: ScratchRepository) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's plan-size-report.sh.

    :param repository: A fixture-built scratch repository.
    :return: The finished subprocess.
    """
    return repository.run_hook_script(HookScript.PLAN_SIZE_REPORT)


def report_line_for(report: str, plan_id: str) -> str:
    """
    Pick one plan's row out of a printed report.

    :param report: The report the script printed.
    :param plan_id: The plan whose row to return.
    :return: That row, with its trailing padding stripped.
    """
    rows = [line for line in report.splitlines() if line.startswith(f"{plan_id} ")]
    assert len(rows) == 1, f"expected exactly one row for {plan_id!r} in:\n{report}"
    return rows[0].rstrip()


# %% what the report covers


def test_reports_every_plan_on_the_notes_branch(report_repository: ScratchRepository):
    report_repository.publish_notes_branch(
        {**plan_files("plan-a", item_count=1), **plan_files("plan-b", item_count=2)}
    )
    result = run_report(report_repository)
    assert result.returncode == 0, result.stderr
    assert report_line_for(result.stdout, "plan-a").split()[1] == "1"
    assert report_line_for(result.stdout, "plan-b").split()[1] == "2"


def test_counts_the_manifest_and_roadmap_lines_together(
    report_repository: ScratchRepository,
):
    files = plan_files("plan-a", item_count=1, roadmap_line_count=4)
    report_repository.publish_notes_branch(files)
    manifest_line_count = len(
        files[f"{PLANS_DIRECTORY}/plan-a/{PlanDocument.MANIFEST}"].splitlines()
    )
    result = run_report(report_repository)
    assert report_line_for(result.stdout, "plan-a").split()[2:5] == [
        str(manifest_line_count),
        "4",
        str(manifest_line_count + 4),
    ]


def test_a_plan_within_the_budget_is_reported_as_within_it(
    report_repository: ScratchRepository,
):
    report_repository.publish_notes_branch(plan_files("plan-a", item_count=1))
    result = run_report(report_repository)
    assert report_line_for(result.stdout, "plan-a").endswith(SizeReport.WITHIN_BUDGET)


def test_a_plan_over_the_budget_is_reported_as_over_it(
    report_repository: ScratchRepository,
):
    item_count = SizeBudget().maximum_items + 1
    report_repository.publish_notes_branch(plan_files("plan-a", item_count=item_count))
    (overrun,) = SizeBudget().overruns(
        PlanSize(
            plan_id="plan-a",
            item_count=item_count,
            manifest_line_count=0,
            roadmap_line_count=0,
        )
    )
    result = run_report(report_repository)
    assert report_line_for(result.stdout, "plan-a").endswith(str(overrun))


def test_generated_data_beside_the_plans_is_not_reported_as_a_plan(
    report_repository: ScratchRepository,
):
    report_repository.publish_notes_branch(
        {
            **plan_files("plan-a", item_count=1),
            f"{PLANS_DIRECTORY}/_generated/branch-index.tsv": "a-branch\tplan-a\n",
        }
    )
    result = run_report(report_repository)
    assert not [
        line for line in result.stdout.splitlines() if line.startswith("_generated")
    ]


# %% refusals


def test_rejects_an_unexpected_argument(report_repository: ScratchRepository):
    report_repository.publish_notes_branch(plan_files("plan-a"))
    result = report_repository.run_hook_script(HookScript.PLAN_SIZE_REPORT, "plan-a")
    assert result.returncode == 1
    assert result.stderr.startswith("Unexpected argument: plan-a\n")


def test_fails_when_the_notes_branch_does_not_exist(
    report_repository: ScratchRepository,
):
    result = run_report(report_repository)
    assert result.returncode == 1
    assert "doesn't exist yet" in result.stderr


def test_reports_whichever_requirement_is_missing(
    report_repository: ScratchRepository,
):
    report_repository.write(REQUIREMENTS_PATH, f"{ABSENT_DISTRIBUTION}>=2\n")
    report_repository.publish_notes_branch(plan_files("plan-a"))

    result = run_report(report_repository)

    assert result.returncode == 1
    assert ABSENT_DISTRIBUTION in result.stderr
    assert REQUIREMENTS_PATH in result.stderr


def test_runs_when_every_requirement_is_installed(
    report_repository: ScratchRepository,
):
    report_repository.publish_notes_branch(plan_files("plan-a"))

    result = run_report(report_repository)

    assert result.returncode == 0, result.stderr
    assert ABSENT_DISTRIBUTION not in result.stderr


def test_the_requirements_path_matches_the_shell_configuration_that_owns_it(
    report_repository: ScratchRepository,
):
    """
    ``REQUIREMENTS_PATH`` mirrors ``HOOKS_REQUIREMENTS_FILE`` in the shell
    configuration; this is what stops the mirror drifting, since the two are edited in
    different files.
    """
    resolved = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HookScript.CONFIGURATION.path}" && '
            'printf "%s\\n" "${HOOKS_REQUIREMENTS_FILE}"',
        ],
        cwd=report_repository.project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert resolved.stdout.strip() == REQUIREMENTS_PATH
