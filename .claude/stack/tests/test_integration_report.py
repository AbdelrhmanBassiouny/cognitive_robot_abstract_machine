"""
The exit status a build derives from what it left behind, and the document a caller
reads it as.
"""

from __future__ import annotations

import json

import pytest

from integration import (
    FailureLocationReport,
    IntegrationExitCode,
    IntegrationReport,
    PullRequestStackTipOutcome,
    ReportKey,
    ResolutionAuthor,
    TipStatus,
    exit_code_for,
)

from test_maintenance import (
    UPSTREAM_BASE,
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    FIRST_TIP,
    ONLY_TIP,
    SECOND_TIP,
    THIRD_TIP,
    create_integration_test_failure,
    create_report,
    create_tip,
    create_unreviewed_branch,
)

# %% the exit status every build derives from what it left behind


def test_a_build_that_merged_everything_is_a_success():
    """
    :return: Nothing; the clean case has to stay clean or every status below is noise.
    """
    assert (
        exit_code_for(create_report(tips=(create_tip("a", TipStatus.MERGED),)))
        is IntegrationExitCode.SUCCESS
    )


@pytest.mark.parametrize(
    "status",
    [TipStatus.SKIPPED, TipStatus.INTEGRATION_FAILED],
)
def test_a_tip_left_out_of_the_build_is_never_reported_as_a_clean_build(
    status: TipStatus,
):
    """
    A caller acting on the status alone - which is what a scheduled job does - would
    otherwise read a partial build as a whole one.

    :param status: A status meaning the tip did not make it into the build.
    """
    assert (
        exit_code_for(create_report(tips=(create_tip("a", status),)))
        is IntegrationExitCode.TIP_LEFT_OUT
    )


def test_a_replayed_tip_alone_does_not_spoil_the_status():
    """
    A replay is reported, not treated as a failure: the tip is in the build and the
    branch works.

    What it must not do is read as a clean *merge*, which is the tip's own status rather
    than the build's.
    """
    assert (
        exit_code_for(create_report(tips=(create_tip("a", TipStatus.REPLAYED),)))
        is IntegrationExitCode.SUCCESS
    )


def test_a_failing_suite_outranks_a_tip_left_out():
    """
    A build missing one branch is still usable; a build whose suite fails is not.
    """
    assert (
        exit_code_for(
            create_report(
                tips=(create_tip("a", TipStatus.SKIPPED),), tests_passed=False
            )
        )
        is IntegrationExitCode.TESTS_FAILED
    )


def test_every_status_says_whether_its_tip_is_in_the_build():
    """
    Whether a tip's commits reached the branch is the status's own answer rather than a
    set of the statuses that count, so a status added later cannot default to being
    reported as left out without anybody deciding that.
    """
    assert {status for status in TipStatus if status.specification.integrated} == {
        TipStatus.MERGED,
        TipStatus.REPLAYED,
    }


def test_a_status_is_written_to_the_report_as_its_bare_name():
    """
    A status carries a whole specification, so it could serialize as the object rather
    than as the one word two other programs match on.

    It is the enum's ``str`` value that keeps the document flat, not anything the report
    does.
    """
    document = json.loads(
        create_report(tips=(create_tip(FIRST_TIP, TipStatus.SKIPPED),)).as_json()
    )

    assert (
        document[ReportKey.TIPS][0][ReportKey.STATUS]
        == TipStatus.SKIPPED.specification.name
    )


def test_every_status_names_itself_for_a_caller():
    """
    A process exit status can only be an integer, so the name accompanies the number
    rather than a caller having to decode one.
    """
    assert IntegrationExitCode.TIP_LEFT_OUT.name_for_a_caller == "tip-left-out"


def test_the_report_keys_are_the_ones_a_caller_parses():
    """
    The one place this document's wire format is pinned, because everything else reads
    the enum on both sides and a rename there changes writer and reader identically.

    Most keys are a dataclass field name that ``asdict`` produces, so a rename of those
    fails wherever they are read. ``status`` and ``exit_code`` are not - ``as_json``
    injects them through this enum - so they are pinned by nothing else, and they are the
    two ``/integration-conflict-triage`` matches on first. The same is true of everything
    ``block-branch`` emits, which no dataclass backs at all.
    """
    assert {key.name: str(key) for key in ReportKey} == {
        "STATUS": "status",
        "EXIT_CODE": "exit_code",
        "BUILD_BRANCH": "build_branch",
        "BASE": "base",
        "TIPS": "tips",
        "TESTS_PASSED": "tests_passed",
        "UNREVIEWED": "unreviewed",
        "TIPS_TESTED": "tips_tested",
        "INTEGRATION_TEST_FAILURE": "integration_test_failure",
        "BRANCH": "branch",
        "PULL_REQUEST_NUMBER": "pull_request_number",
        "ATTRIBUTED_TO": "attributed_to",
        "CONFLICTING_PATHS": "conflicting_paths",
        "RESOLVED_BY": "resolved_by",
        "EXPLANATION": "explanation",
        "CULPRIT": "culprit",
        "CULPRIT_PULL_REQUEST_NUMBER": "culprit_pull_request_number",
        "ALREADY_INCLUDED": "already_included",
        "BREAKS_AGAINST": "breaks_against",
        "BLOCKED": "blocked",
        "LABEL": "label",
        "COMMENT": "comment",
    }


def test_the_report_serialises_what_the_build_left_behind():
    """
    ``--json`` is what a caller with no model in it reads, so the document leads with
    the status rather than burying it among the outcomes.
    """
    written = create_report(tips=(create_tip(ONLY_TIP, TipStatus.SKIPPED),)).as_json()
    document = json.loads(written)

    assert (
        document[ReportKey.STATUS] == IntegrationExitCode.TIP_LEFT_OUT.name_for_a_caller
    )
    assert document[ReportKey.EXIT_CODE] == int(IntegrationExitCode.TIP_LEFT_OUT)
    assert IntegrationReport.from_json(written).tips[0].branch == ONLY_TIP


def test_a_build_survives_the_document_it_is_written_to():
    """
    The document is what one program hands another, so reading it back has to give the
    build itself rather than something that merely resembles it - which is what lets a
    reader use dot notation instead of indexing a nesting it has to know by heart.
    """
    report = create_report(
        tips=(
            create_tip(
                FIRST_TIP, TipStatus.REPLAYED, resolved_by=ResolutionAuthor.SKILL
            ),
            PullRequestStackTipOutcome(
                branch=SECOND_TIP,
                pull_request_number=2,
                status=TipStatus.SKIPPED,
                attributed_to=FIRST_TIP,
                conflicting_paths=("a-file",),
                explanation="what git said",
            ),
        ),
        unreviewed=(create_unreviewed_branch(THIRD_TIP, SECOND_TIP),),
        tests_passed=False,
    )

    assert IntegrationReport.from_json(report.as_json()) == report


def test_a_localised_failure_survives_the_document_it_is_written_to():
    """
    The half ``/integration-conflict-triage`` acts on is the pair, so it is the half a
    round trip has to preserve exactly.
    """
    report = FailureLocationReport(
        build_branch=A_BUILD_BRANCH,
        base=UPSTREAM_BASE,
        tips_tested=(FIRST_TIP, SECOND_TIP),
        integration_test_failure=create_integration_test_failure(),
    )

    assert FailureLocationReport.from_json(report.as_json()) == report
