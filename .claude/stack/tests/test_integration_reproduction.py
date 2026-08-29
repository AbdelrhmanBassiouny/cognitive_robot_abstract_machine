"""
The reproduction tests a break is recorded as, and the block a passing one lifts.

A break between two cleanly merging branches never makes either pull request conflicted,
so nothing GitHub reports can ever clear the label that blocks the breaking branch. The
reproduction test pushed onto that branch is the only evidence there is, and these are
the tests that it says what it is supposed to.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import integration_reproduction
from integration_reproduction import (
    REPRODUCTION_MARKER,
    REPRODUCTION_REPORT_OPTION,
    ClearedBranchReport,
    RecordedBreak,
    ReproductionOutcome,
    ReproductionReportKey,
    ReproductionRun,
    clear_fixed_breaks,
)
import integration_commands
from integration_candidate_commands import ClearFixedBreaksCommand
from integration_constants import ReportKey
from stack import DefaultLabel, LabelWrite

from recorded_break import BREAKING_BRANCH

from test_maintenance import (
    A_LABEL_THIS_TOOL_NEVER_WRITES,
    RecordingPullRequests,
    RecordedLabelWrite,
    make_configuration,
)

CLEAR_FIXED_BREAKS_COMMAND = ClearFixedBreaksCommand()
"""
The command under test, which is stateless.
"""

A_SECOND_BREAKING_BRANCH = "renames-the-fixture"
"""
A second blocked branch, for the runs that must keep two apart.
"""

A_PULL_REQUEST_NUMBER = 41
"""
The fork pull request publishing :data:`BREAKING_BRANCH`.
"""

PYTEST_INI = Path(__file__).parent.parent.parent.parent / "pytest.ini"
"""
This repository's pytest configuration, which has to register the marker.
"""

REPRODUCTIONS_DATASET = Path(__file__).parent / "dataset" / "reproductions"
"""
Reproduction tests written the way the triage skill writes them onto a branch.

Named so this suite's own directory scan passes them over - they are run by an
explicit path, and one of them fails on purpose.
"""

PLUGIN_MODULE = integration_reproduction.__name__
"""
The plugin ``pytest`` is asked to load, named off the module rather than retyped.
"""

WORKFLOW = (
    Path(__file__).parent.parent.parent.parent
    / ".github"
    / "workflows"
    / "integration-checks.yml"
)
"""
The targeted job that runs the reproductions and clears what they unblock.
"""

REPORT_PATH = "${RUNNER_TEMP}/reproductions.json"
"""
Where that job writes the run's document, which both of its steps name.
"""

CONTINUOUS_INTEGRATION_WORKFLOW = (
    Path(__file__).parent.parent.parent.parent / ".github" / "workflows" / "ci.yml"
)
"""
The repository's own workflow, one job of which installs what the targeted job installs.
"""

REQUIREMENTS_INSTALL = "${PLAN_DASHBOARD_REQUIREMENTS_FILE}"
"""
The install that identifies a job carrying the tooling dependencies and nothing else.
"""

PYTEST_INVOCATION = "python -m pytest"
"""
How either job runs the tests it collects.
"""

TEST_DIRECTORY_VARIABLE = re.compile(r"\$\{(\w*TESTS_DIRECTORY)\}")
"""
Names the shell variable a job collects a test directory through.
"""

PLUGIN_ENVIRONMENT = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
"""
What a subprocess needs to load the plugin by name.

It is a plain module rather than an installed package, and this suite's own
``conftest.py`` has already put its directory on the path, so handing the subprocess
that path is what makes ``-p`` resolve it.
"""


def workflow() -> dict:
    """
    :return: The targeted job's workflow, as parsed YAML.
    """
    return yaml.safe_load(WORKFLOW.read_text())


def workflow_triggers() -> dict:
    """
    The events the workflow runs on.

    Read under ``True`` rather than ``"on"``: YAML 1.1 resolves a bare ``on`` key to a
    boolean, so that is the key the parsed document actually carries.

    :return: The trigger block.
    """
    return workflow()[True]


def workflow_steps() -> list[dict]:
    """
    :return: Every step of the job that runs the reproductions.
    """
    return workflow()["jobs"]["reproductions"]["steps"]


def step_script(step: dict) -> str:
    """
    :param step: One workflow step.
    :return: The shell it runs, empty for a step that runs an action instead.
    """
    return step.get("run", "")


def reproduction_job_script() -> str:
    """
    :return: The shell of the step that runs the reproductions.
    """
    return next(
        script
        for script in map(step_script, workflow_steps())
        if REPRODUCTION_REPORT_OPTION in script
    )


def tooling_job_script() -> str:
    """
    The pytest invocation of the job that installs the same dependencies.

    Found by that install rather than by the job's name, since what makes its
    collectible tree the same as the targeted job's is what it installs.

    :return: The shell of that job's pytest step.
    """
    jobs = yaml.safe_load(CONTINUOUS_INTEGRATION_WORKFLOW.read_text())["jobs"]
    for job in jobs.values():
        scripts = [step_script(step) for step in job.get("steps", [])]
        if any(REQUIREMENTS_INSTALL in script for script in scripts):
            return next(script for script in scripts if PYTEST_INVOCATION in script)
    raise AssertionError(
        f"no job in {CONTINUOUS_INTEGRATION_WORKFLOW} installs {REQUIREMENTS_INSTALL}"
    )


def collected_test_directories(script: str) -> set[str]:
    """
    :param script: The shell of a step that runs the tests.
    :return: The test directories it collects, by the variable naming each.
    """
    return set(TEST_DIRECTORY_VARIABLE.findall(script))


def clearing_job_script() -> str:
    """
    :return: The shell of the step that lifts the blocks.
    """
    return next(
        script
        for script in map(step_script, workflow_steps())
        if CLEAR_FIXED_BREAKS_COMMAND.invoked_as in script
    )


def run_reproductions(report: Path, reproduction: str, select_marked: bool) -> None:
    """
    Run one dataset reproduction under the plugin, the way the targeted job does.

    :param report: Where the run writes its document.
    :param reproduction: The dataset module to run, without its suffix.
    :param select_marked: Whether to select by the marker, as the targeted job does -
        off for the run that has to see an unmarked test collected.
    """
    selection = ["-m", REPRODUCTION_MARKER] if select_marked else []
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            PLUGIN_MODULE,
            f"{REPRODUCTION_REPORT_OPTION}={report}",
            *selection,
            str(REPRODUCTIONS_DATASET / f"{reproduction}.py"),
        ],
        check=False,
        capture_output=True,
        env=PLUGIN_ENVIRONMENT,
    )


def a_run(*outcomes: ReproductionOutcome) -> ReproductionRun:
    """
    :param outcomes: What each reproduction test did.
    :return: The run those outcomes make up.
    """
    return ReproductionRun(outcomes)


def an_outcome(
    branch: str = BREAKING_BRANCH, passed: bool = True, test: str = "test_they_agree"
) -> ReproductionOutcome:
    """
    :param branch: The branch the reproduction was recorded against.
    :param passed: Whether it passed this time.
    :param test: The test's node identifier.
    :return: One reproduction's outcome.
    """
    return ReproductionOutcome(branch=branch, test=test, passed=passed)


# %% the marker names the label it clears


def test_the_marker_is_the_label_it_clears_spelled_the_way_a_marker_can_be():
    """
    The marker exists to clear one label, so its name is derived from that label rather
    than typed again - a marker cannot carry the hyphen the label does, and two
    independent spellings drifting apart leaves a passing reproduction clearing nothing.
    """
    assert REPRODUCTION_MARKER == DefaultLabel.INTEGRATION_CONFLICT.replace("-", "_")


def test_the_marker_is_registered_in_this_repository_s_pytest_configuration():
    """
    An unregistered marker is a warning rather than a selector, so the targeted job
    would silently run nothing.
    """
    configuration = configparser.ConfigParser()
    configuration.read(PYTEST_INI)
    registered = {
        line.split(":", 1)[0].split("(", 1)[0].strip()
        for line in configuration["pytest"]["markers"].splitlines()
        if line.strip()
    }

    assert REPRODUCTION_MARKER in registered


def test_the_marker_is_not_excluded_by_default():
    """
    Excluding it the way ``slow`` is excluded would keep the breaking branch's own run
    green, which is precisely the outcome the reproduction exists to prevent: a test
    excluded from that branch's run is invisible in the one place its owner looks.
    """
    configuration = configparser.ConfigParser()
    configuration.read(PYTEST_INI)

    assert REPRODUCTION_MARKER not in configuration["pytest"]["addopts"]


# %% reading what a run of the reproductions found


def test_a_branch_whose_only_reproduction_passes_is_fixed():
    """
    The single reproduction passing is the whole clearing condition.
    """
    run = a_run(an_outcome(passed=True))

    assert run.fixed_branches == (BREAKING_BRANCH,)


def test_a_branch_whose_reproduction_still_fails_is_not_fixed():
    """
    The break is still there, so the block still stands.
    """
    run = a_run(an_outcome(passed=False))

    assert run.fixed_branches == ()


def test_a_branch_is_fixed_only_when_every_reproduction_recorded_against_it_passes():
    """
    A branch can break more than one sibling, so it collects a reproduction per break.

    Clearing on the first passing one would lift the block while a recorded break is
    still reproducible.
    """
    run = a_run(
        an_outcome(passed=True, test="test_against_one"),
        an_outcome(passed=False, test="test_against_another"),
    )

    assert run.fixed_branches == ()


def test_branches_are_judged_independently_of_each_other():
    """
    One branch still breaking something says nothing about another, and holding both for
    the worse of the two would leave a fixed branch blocked.
    """
    run = a_run(
        an_outcome(branch=BREAKING_BRANCH, passed=True),
        an_outcome(branch=A_SECOND_BREAKING_BRANCH, passed=False),
    )

    assert run.fixed_branches == (BREAKING_BRANCH,)


def test_a_run_that_collected_no_reproduction_reports_no_branch_as_fixed():
    """
    A healthy build records no breaks at all, and ``pytest`` exits 5 rather than 0 for
    it.

    That says nothing is recorded, not that everything is fixed.
    """
    assert a_run().fixed_branches == ()


def test_a_run_groups_every_reproduction_under_the_branch_it_names():
    """
    The report a caller reads is per branch, since the branch is what carries the label.
    """
    run = a_run(
        an_outcome(passed=True, test="test_against_one"),
        an_outcome(passed=False, test="test_against_another"),
    )

    assert run.breaks == (
        RecordedBreak(
            branch=BREAKING_BRANCH,
            outcomes=(
                an_outcome(passed=True, test="test_against_one"),
                an_outcome(passed=False, test="test_against_another"),
            ),
        ),
    )


# %% the document the targeted job hands back


def test_a_run_round_trips_through_the_document_the_job_writes():
    """
    The job that runs the reproductions and the command that clears labels are two
    processes, so the run reaches the second one only as this document.
    """
    run = a_run(
        an_outcome(branch=BREAKING_BRANCH, passed=True),
        an_outcome(branch=A_SECOND_BREAKING_BRANCH, passed=False),
    )

    assert ReproductionRun.from_json(run.as_json()) == run


def test_the_document_names_each_reproduction_s_branch_test_and_result():
    """
    Its keys are read by a separate process, so they are the contract rather than an
    implementation detail of ``asdict``.
    """
    document = json.loads(a_run(an_outcome(passed=False)).as_json())

    assert document[ReproductionReportKey.REPRODUCTIONS] == [
        {
            ReproductionReportKey.BRANCH: BREAKING_BRANCH,
            ReproductionReportKey.TEST: "test_they_agree",
            ReproductionReportKey.PASSED: False,
        }
    ]


# %% clearing the block


def test_clearing_removes_the_block_and_leaves_every_other_label_alone():
    """
    GitHub's label write replaces the whole set, so a clear that computed the set from
    the removal alone would strip labels this tool knows nothing about.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={
            A_PULL_REQUEST_NUMBER: [
                A_LABEL_THIS_TOOL_NEVER_WRITES,
                configuration.integration_conflict_label,
            ]
        },
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    clear_fixed_breaks(a_run(an_outcome(passed=True)), configuration, fork)

    assert fork.label_writes == [
        RecordedLabelWrite(
            A_PULL_REQUEST_NUMBER,
            LabelWrite.replacing(
                [
                    A_LABEL_THIS_TOOL_NEVER_WRITES,
                    configuration.integration_conflict_label,
                ],
                removed=[configuration.integration_conflict_label],
            ).labels,
        )
    ]


def test_a_branch_whose_reproduction_still_fails_is_left_blocked():
    """
    The one thing this must never do is lift a block on evidence that says nothing.
    """
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [DefaultLabel.INTEGRATION_CONFLICT]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    clear_fixed_breaks(a_run(an_outcome(passed=False)), make_configuration(), fork)

    assert fork.label_writes == []


def test_clearing_says_on_the_pull_request_what_lifted_the_block():
    """
    The block arrived as a comment naming the branch it breaks, so its lifting is
    readable in the same place rather than only as a label quietly disappearing.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [configuration.integration_conflict_label]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    clear_fixed_breaks(a_run(an_outcome(passed=True)), configuration, fork)

    posted = fork.comments[0]
    assert posted.pull_request_number == A_PULL_REQUEST_NUMBER
    assert REPRODUCTION_MARKER in posted.body


def test_clearing_reports_what_it_wrote_and_where():
    """
    ``clear-fixed-breaks --json`` is the half a caller acts on.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [configuration.integration_conflict_label]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    cleared = clear_fixed_breaks(a_run(an_outcome(passed=True)), configuration, fork)

    assert cleared == (
        ClearedBranchReport(
            branch=BREAKING_BRANCH,
            pull_request_number=A_PULL_REQUEST_NUMBER,
            label=configuration.integration_conflict_label,
            comment=fork.comments[0].body,
        ),
    )


def test_a_branch_that_is_not_blocked_is_not_written_to_at_all():
    """
    A reproduction passes on every run once the break is fixed, so every later run would
    re-clear a label that is already gone and comment again saying so.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [A_LABEL_THIS_TOOL_NEVER_WRITES]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    cleared = clear_fixed_breaks(a_run(an_outcome(passed=True)), configuration, fork)

    assert (cleared, fork.label_writes, fork.comments) == ((), [], [])


def test_a_fixed_branch_with_no_open_pull_request_is_skipped_rather_than_guessed_at():
    """
    The label lives on a pull request, so a branch without one has no block to lift -
    and inventing a number for it would write to somebody else's.
    """
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [DefaultLabel.INTEGRATION_CONFLICT]},
        heads={A_PULL_REQUEST_NUMBER: A_SECOND_BREAKING_BRANCH},
    )

    cleared = clear_fixed_breaks(
        a_run(an_outcome(passed=True)), make_configuration(), fork
    )

    assert (cleared, fork.label_writes) == ((), [])


# %% running the reproductions for real


@pytest.mark.parametrize(
    "reproduction, break_is_fixed",
    [("a_fixed_break", True), ("an_unfixed_break", False)],
)
def test_a_reproduction_s_own_result_decides_whether_its_branch_is_fixed(
    tmp_path: Path, reproduction: str, break_is_fixed: bool
):
    """
    The report is written by a real ``pytest`` run rather than assembled by hand, so the
    marker, the plugin and the document are exercised the way the targeted job runs
    them.

    The branch is read back off the run rather than restated here: which branch the
    dataset names is the dataset's to say, and what this pins is that a reproduction
    passing is what makes the branch it names fixed.
    """
    report = tmp_path / "reproductions.json"

    run_reproductions(report, reproduction, select_marked=True)
    run = ReproductionRun.from_json(report.read_text())
    recorded = run.breaks[0]

    assert (recorded.is_fixed, run.fixed_branches) == (
        break_is_fixed,
        (recorded.branch,) if break_is_fixed else (),
    )


def test_a_reproduction_is_recorded_against_the_branch_its_marker_names(tmp_path: Path):
    """
    The marker's argument is the whole link between a passing test and a label to
    remove; without it a reproduction says something is fixed but not whose.
    """
    report = tmp_path / "reproductions.json"

    run_reproductions(report, "a_fixed_break", select_marked=True)
    run = ReproductionRun.from_json(report.read_text())

    assert [outcome.branch for outcome in run.outcomes] == [BREAKING_BRANCH]


def test_an_unmarked_test_is_not_read_as_a_reproduction_of_anything(tmp_path: Path):
    """
    Every other test in the repository runs under this plugin whenever the targeted job
    widens its selection, and none of them records a break.
    """
    report = tmp_path / "reproductions.json"

    run_reproductions(report, "an_ordinary_test", select_marked=False)

    assert ReproductionRun.from_json(report.read_text()).breaks == ()


# %% the command a caller runs


def test_the_command_is_reachable_by_the_name_the_targeted_job_invokes_it_by():
    """
    The workflow and the builder are wired by this name alone, so it is asserted against
    the command rather than left to the workflow to be right about.
    """
    assert CLEAR_FIXED_BREAKS_COMMAND.invoked_as in {
        command.invoked_as for command in integration_commands.COMMANDS
    }


def test_the_command_reads_the_run_document_the_targeted_job_wrote(tmp_path: Path):
    """
    The job and the command are separate processes, so the document on disk is the only
    thing that carries a run between them.
    """
    report = tmp_path / "reproductions.json"
    report.write_text(a_run(an_outcome(passed=True)).as_json())
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [configuration.integration_conflict_label]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    cleared = CLEAR_FIXED_BREAKS_COMMAND.clear(report, configuration, fork)

    assert [report.branch for report in cleared] == [BREAKING_BRANCH]


def test_the_command_reports_every_branch_it_unblocked_as_one_document(tmp_path: Path):
    """
    ``--json`` is what a later step in the same job acts on.
    """
    report = tmp_path / "reproductions.json"
    report.write_text(a_run(an_outcome(passed=True)).as_json())
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [configuration.integration_conflict_label]},
        heads={A_PULL_REQUEST_NUMBER: BREAKING_BRANCH},
    )

    cleared = CLEAR_FIXED_BREAKS_COMMAND.clear(report, configuration, fork)
    document = json.loads(CLEAR_FIXED_BREAKS_COMMAND.as_json(cleared))

    assert document[ReportKey.CLEARED] == [
        {
            ReportKey.BRANCH: BREAKING_BRANCH,
            ReportKey.PULL_REQUEST_NUMBER: A_PULL_REQUEST_NUMBER,
            ReportKey.LABEL: configuration.integration_conflict_label,
            ReportKey.COMMENT: cleared[0].comment,
        }
    ]


# %% the targeted job that runs them


def test_the_job_selects_the_marker_the_plugin_records():
    """
    A workflow cannot import a constant, so the one place the marker is spelled a second
    time is this file - and a selection that named something else would run nothing while
    still reporting success.
    """
    assert f"-m {REPRODUCTION_MARKER}" in reproduction_job_script()


def test_the_job_collects_only_the_trees_its_dependencies_cover():
    """
    Collecting the repository root loads every ``conftest.py``, the robotics stack's
    included, and that one imports ``numpy`` - so a runner carrying the tooling
    dependencies alone dies during collection before it reaches a reproduction, and the
    job fails without having run one.

    Which trees it can import is decided by what it installs, so they are read off the
    job that installs the same thing rather than listed a second time here.
    """
    assert collected_test_directories(
        reproduction_job_script()
    ) == collected_test_directories(tooling_job_script())


def test_the_job_loads_the_plugin_that_writes_the_document():
    """
    Without the plugin the run happens and the document is never written.
    """
    assert f"-p {PLUGIN_MODULE}" in reproduction_job_script()


def test_the_job_hands_the_document_it_wrote_to_the_command_that_reads_it():
    """
    Two steps, two processes, one path.

    A mismatch leaves the second step reading a file that is not there, or worse, a
    stale one from an earlier run.
    """
    written = REPRODUCTION_REPORT_OPTION
    steps = workflow_steps()

    assert [step for step in steps if written in step_script(step)] and all(
        REPORT_PATH in step_script(step)
        for step in steps
        if written in step_script(step)
        or CLEAR_FIXED_BREAKS_COMMAND.invoked_as in step_script(step)
    )


def test_the_job_invokes_the_command_by_the_name_the_builder_answers_to():
    """
    The builder and the workflow are wired by this name alone.
    """
    assert CLEAR_FIXED_BREAKS_COMMAND.invoked_as in clearing_job_script()


def test_the_job_runs_on_a_pull_request_so_a_pushed_fix_is_noticed():
    """
    Nothing else notices that a break is fixed: the branch's owner pushes the fix, and
    this is the run that reads the reproduction and lifts the block.
    """
    assert "pull_request" in workflow_triggers()
