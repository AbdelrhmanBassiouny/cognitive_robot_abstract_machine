"""
What is left in the job that calls the rebuild.

The rebuild itself is a procedure with tests over it, so the job is reduced to what only
a runner can do - check a tree out, put an interpreter on the path, install, and call it.
These check that it stayed that way: a status branched on in a ``run:`` block is one
nothing can run outside a runner, and so one nothing checks.
"""

from __future__ import annotations

import integration_pipeline_commands
from integration_constants import BUILD_BRANCH_FILTER
from integration_exit_codes import IntegrationExitCode
from integration_pipeline_commands import RefreshJobVariable, RefreshWorkflowInput
from tool_runner import CommandLineFlag
from workflow_document import (
    Action,
    ActivityType,
    CheckoutInput,
    GitHubContext,
    OptionalArgument,
    PassedArgument,
    TriggerEvent,
    WorkflowFile,
)

REFRESH_JOB = "refresh"
"""
The job the rebuild is, whose key the workflow's own concurrency group is named for.
"""


def refresh_job():
    """:return: The job that performs a rebuild."""
    return WorkflowFile.INTEGRATION_REFRESH.read().job(REFRESH_JOB)


def refresh_job_script() -> str:
    """:return: Every line of shell the job runs, as one text."""
    return "\n".join(step.script for step in refresh_job().steps)


def test_the_scheduled_job_calls_the_rebuild_rather_than_restating_it():
    """
    The rebuild is a procedure with tests over it; a job that branched on statuses in
    shell would be the same procedure written where nothing can run it.
    """
    assert (
        integration_pipeline_commands.RefreshCommand().invoked_as
        in refresh_job_script()
    )


def test_the_scheduled_job_branches_on_no_status_of_its_own():
    """
    An exit-code literal in YAML is one nothing checks - the branch it guards is only
    ever taken on a runner, so a wrong number is found by a rebuild doing the wrong
    thing rather than by a test.
    """
    scripts = refresh_job_script()

    assert not any(
        str(int(status)) in scripts.split() for status in IntegrationExitCode
    )
    assert "if [" not in scripts and "case " not in scripts


def test_the_scheduled_job_still_does_what_only_a_runner_can():
    """
    Checking a tree out, putting an interpreter on the path and installing are the steps
    that cannot move into the thing they install.
    """
    job = refresh_job()

    assert job.step_using(Action.CHECKOUT)
    assert job.step_using(Action.SETUP_PYTHON)


def test_the_rebuild_answers_to_a_schedule_a_dispatch_and_a_branch_leaving_draft():
    """
    Leaving draft is what makes a branch integrable at all, so it is the moment the
    build is worth redoing rather than one to wait out.
    """
    refresh = WorkflowFile.INTEGRATION_REFRESH.read()

    assert refresh.answers_to(TriggerEvent.SCHEDULE)
    assert refresh.answers_to(TriggerEvent.WORKFLOW_DISPATCH)
    assert refresh.activity_types(TriggerEvent.PULL_REQUEST) == (
        ActivityType.READY_FOR_REVIEW,
    )


def test_the_probes_are_dispatched_on_the_reference_the_tooling_was_read_from():
    """
    A dispatch runs the workflow file the dispatched reference carries, and the tree
    under test carries none - so the reference has to be one holding this pipeline,
    which is the same one the job checked the tooling out at.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert GitHubContext.DEFAULT_BRANCH in rebuilding.variable(
        RefreshJobVariable.PIPELINE_REFERENCE
    )


def test_the_dispatch_reference_is_one_expression_rather_than_several_lines():
    """
    A folded YAML scalar folds only the lines level with its first one; a continuation
    indented further keeps its newline, which parses cleanly and leaves a line break
    inside a ``${{ }}`` expression for GitHub to reject at run time.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert "\n" not in rebuilding.variable(RefreshJobVariable.PIPELINE_REFERENCE)


# %% a published pipeline older than the rebuild it is asked for


def probing_step():
    """:return: The step that asks whether the checked-out tooling can rebuild at all."""
    return next(step for step in refresh_job().steps if step.tolerates_its_own_failure)


def steps_conditioned_on(identifier: str):
    """:param identifier: A step's own ``id``.
    :return: Every step whose condition reads that step's outcome."""
    return [step for step in refresh_job().steps if identifier in step.condition]


def test_a_rebuild_the_published_pipeline_cannot_perform_is_asked_for_before_it_is_run():
    """
    A pull request's run is pinned to the default branch so that no branch's own code
    runs against a writing token - and that branch is the one this pipeline publishes,
    so it lags whatever is in flight and can predate the command the job invokes. Asking
    first is what turns that into an answer rather than a usage error.
    """
    asking = probing_step()

    assert integration_pipeline_commands.RefreshCommand().invoked_as in asking.script
    assert asking.identifier


def test_a_pipeline_that_cannot_rebuild_neither_rebuilds_nor_fails_the_run():
    """
    Failing would attach a red check to whichever branch's ready-flip asked for the
    rebuild, which is the branch the rebuild exists to carry.
    """
    conditioned = steps_conditioned_on(probing_step().identifier)
    rebuilding = [step for step in conditioned if step.environment]

    assert len(rebuilding) == 1
    assert integration_pipeline_commands.RefreshCommand().invoked_as in (
        rebuilding[0].script
    )


def test_a_rebuild_that_was_never_attempted_says_so():
    """
    A job that answers green having done nothing is the state this pipeline has already
    been in once, and it reads as a rebuild that worked.
    """
    conditioned = steps_conditioned_on(probing_step().identifier)

    assert [step for step in conditioned if not step.environment]


# %% a rebuild carrying one plan


def test_a_dispatch_can_ask_for_a_rebuild_of_particular_plans():
    """
    Asking whether one plan holds together on its own is a thing a person reaches for
    when the full build is red, so it has to be reachable from where they start a
    rebuild.
    """
    declared = WorkflowFile.INTEGRATION_REFRESH.read().dispatch_inputs

    assert str(RefreshWorkflowInput.PLANS) in declared
    assert declared[str(RefreshWorkflowInput.PLANS)].default == ""


def test_the_rebuild_is_told_which_reference_the_tooling_came_from():
    """
    A probe is dispatched on a reference carrying this pipeline rather than on the tree
    under test, which carries no workflow of its own - so the job has to hand on the one
    it read the tooling at, and setting the variable without passing it would leave the
    rebuild defaulting to the branch it publishes.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert rebuilding.passes(
        PassedArgument(
            variable=str(RefreshJobVariable.PIPELINE_REFERENCE),
            argument=str(CommandLineFlag.DISPATCH_ON),
        )
    )


def test_a_rebuild_that_was_asked_for_no_plan_names_none():
    """
    An empty input passed through as a flag would name a plan of no name, which the index
    matches nothing against - so the full build, which is every scheduled run, would come
    out empty.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert rebuilding.passes(
        OptionalArgument(
            variable=str(RefreshJobVariable.PLANS),
            argument=str(CommandLineFlag.PLAN),
        )
    )


# %% which tooling a rebuild runs


def checkout_reference() -> str:
    """:return: The reference the job checks the tooling out at."""
    return refresh_job().step_using(Action.CHECKOUT).given(CheckoutInput.REFERENCE)


def test_the_checkout_reference_is_one_expression_rather_than_several_lines():
    """
    A folded YAML scalar folds only the lines level with its first one; a continuation
    indented further keeps its newline, which parses cleanly and leaves a line break
    inside a ``${{ }}`` expression for GitHub to reject at run time.
    """
    assert "\n" not in checkout_reference()


def test_a_pull_request_rebuild_reads_the_tooling_from_the_default_branch():
    """
    A ``pull_request`` run checks out that pull request's merge reference by default, so
    an unguarded checkout would run whatever ``integration.py`` the triggering branch
    happens to carry, against a token that can write.

    The rebuild is never about the branch that triggered it.
    """
    assert GitHubContext.DEFAULT_BRANCH in checkout_reference()


def test_every_other_rebuild_reads_the_tooling_from_the_reference_it_was_started_on():
    """
    Pinning every trigger to the default branch would mean a change to the pipeline could
    only ever run once it was already published there - and publishing is what the
    pipeline does, so a change that broke publishing could not be fixed by running the
    fix. Dispatching a reference is how a change is tried before it lands.
    """
    reference = checkout_reference()

    assert reference.index(GitHubContext.REFERENCE) > reference.index(
        GitHubContext.DEFAULT_BRANCH
    )


def test_a_pull_request_from_a_fork_does_not_start_a_rebuild():
    """
    A fork's pull request is handed no secret, so the run could only fail on a token it
    has not got - and fail on somebody else's pull request, where the failure reads as
    theirs. Not running says the same thing without the noise.
    """
    compared = (
        f"{GitHubContext.PULL_REQUEST_HEAD_REPOSITORY} == {GitHubContext.REPOSITORY}"
    )

    assert compared in refresh_job().condition


# %% settling a candidate when its checks finish


def refresh_workflow():
    """:return: The parsed refresh workflow."""
    return WorkflowFile.INTEGRATION_REFRESH.read()


def test_a_candidate_is_settled_when_its_checks_finish_rather_than_at_the_next_slot():
    """
    A run cannot reach a verdict on the candidate it opened, so a first-time build waits
    for a later run - and on the schedule alone that is up to six hours after the matrix
    it is waiting for has already answered.
    """
    assert refresh_workflow().activity_types(TriggerEvent.WORKFLOW_RUN) == (
        ActivityType.COMPLETED,
    )


def test_the_run_a_rebuild_answers_to_is_named_off_the_workflow_that_reports_it():
    """
    ``workflow_run`` matches on a workflow's name rather than on its file, so a name.

    retyped here and later changed there leaves the trigger answering to nothing at all
    - silently, and in the direction that stops the pipeline rather than the one that
    over-runs it.
    """
    assert refresh_workflow().watched_workflows(TriggerEvent.WORKFLOW_RUN) == (
        WorkflowFile.CONTINUOUS_INTEGRATION.read().name,
    )


def test_only_a_build_s_own_checks_start_a_rebuild():
    """
    Every pull request in flight runs that same workflow, so an unfiltered trigger would
    be a full rebuild per push to any of them.
    """
    assert refresh_workflow().branches(TriggerEvent.WORKFLOW_RUN) == (
        BUILD_BRANCH_FILTER,
    )
