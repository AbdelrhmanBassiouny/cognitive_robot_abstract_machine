"""
What is left in the job that calls the rebuild.

The rebuild itself is a procedure with tests over it, so the job is reduced to what only
a runner can do - check a tree out, put an interpreter on the path, install, and call it.
These check that it stayed that way: a status branched on in a ``run:`` block is one
nothing can run outside a runner, and so one nothing checks.
"""

from __future__ import annotations

import integration_pipeline_commands
from integration_exit_codes import IntegrationExitCode
from workflow_document import Action, TriggerEvent, WorkflowFile

PLANS_INPUT = "plans"
"""
What a dispatch names the plans it wants a rebuild of.
"""

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
    assert refresh.trigger(TriggerEvent.PULL_REQUEST)["types"] == ["ready_for_review"]


def test_the_probes_are_dispatched_on_the_reference_the_tooling_was_read_from():
    """
    A dispatch runs the workflow file the dispatched reference carries, and the tree
    under test carries none - so the reference has to be one holding this pipeline,
    which is the same one the job checked the tooling out at.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert (
        "github.event.repository.default_branch"
        in rebuilding.environment["PIPELINE_REFERENCE"]
    )


def test_the_dispatch_reference_is_one_expression_rather_than_several_lines():
    """
    A folded YAML scalar folds only the lines level with its first one; a continuation
    indented further keeps its newline, which parses cleanly and leaves a line break
    inside a ``${{ }}`` expression for GitHub to reject at run time.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert "\n" not in rebuilding.environment["PIPELINE_REFERENCE"]


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

    assert PLANS_INPUT in declared
    assert declared[PLANS_INPUT]["default"] == ""


def test_a_rebuild_that_was_asked_for_no_plan_names_none():
    """
    An empty input passed through as a flag would name a plan of no name, which the index
    matches nothing against - so the full build, which is every scheduled run, would come
    out empty.
    """
    rebuilding = next(step for step in refresh_job().steps if step.environment)

    assert f"${{{PLANS_INPUT.upper()}:+--plan " in rebuilding.script
