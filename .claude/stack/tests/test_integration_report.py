"""
The exit status a build derives from what it left behind, and the document a caller
reads it as.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from integration import (
    BlockedBranchReport,
    FailureLocationReport,
    IntegrationExitCode,
    IntegrationReport,
    PullRequestStackTipOutcome,
    ReportKey,
    ResolutionAuthor,
    StagedConflict,
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


# %% the documents a caller reads


def every_document_this_module_writes() -> set[str]:
    """
    :return: Every key, at every nesting level, of one fully populated instance of each
        of the four documents this module hands to another program.

    Built from the documents rather than from :class:`ReportKey`, because what a caller
    parses is the document - an enum member nobody emits and a key emitted without a
    member are both invisible to a check that reads the enum.
    """
    outcome = PullRequestStackTipOutcome(
        branch=SECOND_TIP,
        pull_request_number=2,
        status=TipStatus.SKIPPED,
        attributed_to=FIRST_TIP,
        conflicting_paths=("a-file",),
        resolved_by=ResolutionAuthor.SKILL,
        explanation="what git said",
    )
    documents = (
        create_report(
            tips=(outcome,), tests_passed=False, unreviewed=(outcome,)
        ).as_json(),
        FailureLocationReport(
            build_branch=A_BUILD_BRANCH,
            base=UPSTREAM_BASE,
            tips_tested=(FIRST_TIP,),
            integration_test_failure=create_integration_test_failure(),
        ).as_json(),
        BlockedBranchReport(
            blocked=SECOND_TIP,
            pull_request_number=2,
            breaks_against=FIRST_TIP,
            label="integration-conflict",
            comment="what was said on its pull request",
        ).as_json(),
        StagedConflict(
            worktree=Path("/tmp/a-worktree"),
            branch=SECOND_TIP,
            attributed_to=FIRST_TIP,
            conflicting_paths=("a-file",),
        ).as_json(),
    )
    return {key for document in documents for key in keys_in(json.loads(document))}


def keys_in(document: object) -> set[str]:
    """
    :param document: A parsed document, or any part of one.
    :return: Every mapping key it holds, at every depth.
    """
    if isinstance(document, dict):
        return set(document) | {
            key for value in document.values() for key in keys_in(value)
        }
    if isinstance(document, list):
        return {key for value in document for key in keys_in(value)}
    return set()


def test_the_report_keys_are_the_ones_a_caller_parses():
    """
    The one place this module's wire format is pinned, because everything else reads
    :class:`ReportKey` on both sides and a rename there changes writer and reader
    identically.

    Concretely, and this is the situation the test exists for: rename ``EXIT_CODE``'s
    value to ``exitCode``. ``as_json`` then writes ``exitCode``, every reader in the
    repository - this suite, ``/integration-conflict-triage``, ``stacked-pr-maintenance``
    - reads it back through the same member, and nothing fails. What broke is the
    document a shell caller pipes into ``jq .exit_code``, and nothing here is looking at
    that. These literals are what looks.

    They are compared against the documents themselves rather than against the enum, so
    the failure is the caller-visible one - the key a document carries changed - rather
    than a table beside the enum disagreeing with it.
    """
    assert every_document_this_module_writes() == {
        "status",
        "exit_code",
        "build_branch",
        "base",
        "tips",
        "tests_passed",
        "unreviewed",
        "tips_tested",
        "integration_test_failure",
        "branch",
        "pull_request_number",
        "attributed_to",
        "conflicting_paths",
        "resolved_by",
        "explanation",
        "culprit",
        "culprit_pull_request_number",
        "already_included",
        "breaks_against",
        "blocked",
        "label",
        "comment",
        "worktree",
    }


def test_every_report_key_names_something_a_document_carries():
    """
    The other half, which the literals above cannot see: a member added and never
    emitted, or a key emitted without going through the enum.

    Both are silent - the first leaves a name that looks like part of the wire format
    and is not, the second puts a key in the format that nothing names.
    """
    assert every_document_this_module_writes() == {str(key) for key in ReportKey}


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
