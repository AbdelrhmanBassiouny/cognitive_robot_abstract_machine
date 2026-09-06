"""
Telling a branch's owner why a scheduled build's automatic pass left it out - which
reasons are worth a comment, what the comment says, and how it avoids repeating itself.
"""

from __future__ import annotations

from types import SimpleNamespace

from integration_build_commands import BuildCommand
from integration_left_out import branches_left_out, report_left_out
from integration_tips import PullRequestStackTipOutcome, TipStatus

from test_maintenance import (
    RecordedLabelWrite,
    RecordingPullRequests,
    make_configuration,
)

from integration_fixtures import (
    create_blocked_branch,
    create_red_branch,
    create_report,
    create_tip,
    create_unreviewed_branch,
)

A_CONFLICTING_TIP = "a-conflicting-tip"
"""A tip a build skipped after it collided with a sibling."""

A_SIBLING_TIP = "a-sibling-tip"
"""The sibling :data:`A_CONFLICTING_TIP` collided with."""

AN_UNMERGEABLE_TIP = "an-unmergeable-tip"
"""A tip the build's own merge refused before it began."""

A_HEALTHY_BRANCH = "a-healthy-branch"
"""A reviewed, green branch left out only because of what it stands on."""

AN_ANCESTOR = "an-ancestor"
"""The ancestor :data:`A_HEALTHY_BRANCH` is left out underneath."""


def skipped_tip(
    branch: str = A_CONFLICTING_TIP,
    attributed_to: str = A_SIBLING_TIP,
    conflicting_paths: tuple[str, ...] = ("a_contested_file.py",),
    number: int = 1,
) -> PullRequestStackTipOutcome:
    """:return: A tip a build skipped after a raw text conflict with a sibling."""
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=number,
        status=TipStatus.SKIPPED,
        attributed_to=attributed_to,
        conflicting_paths=conflicting_paths,
    )


def integration_failed_tip(
    branch: str = AN_UNMERGEABLE_TIP,
    explanation: str = "fatal: refusing to merge unrelated histories",
    number: int = 1,
) -> PullRequestStackTipOutcome:
    """:return: A tip the build's own merge refused before it began."""
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=number,
        status=TipStatus.INTEGRATION_FAILED,
        explanation=explanation,
    )


def blocked_without_record(
    branch: str, ancestor: str | None = None
) -> PullRequestStackTipOutcome:
    """:return: One entry of a build's left-out list, blocked without a recorded tree."""
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=0,
        status=TipStatus.BLOCKED_WITHOUT_RECORD,
        attributed_to=ancestor,
    )


# %% which reasons are worth telling an owner about


def test_a_raw_conflict_skip_is_always_worth_telling():
    """
    Nothing else will ever tell this branch's owner why it collided - a build's own
    report reaches whoever reads the build, not the branch itself.
    """
    report = create_report(tips=(skipped_tip(),))

    assert skipped_tip() in branches_left_out(report)


def test_the_builds_own_refusal_to_merge_is_always_worth_telling():
    """
    The merge never even began, and the branch's own checks cannot see that either.
    """
    report = create_report(tips=(integration_failed_tip(),))

    assert integration_failed_tip() in branches_left_out(report)


def test_a_branch_blocked_by_its_own_label_needs_no_comment():
    """
    Its own label is already the reason, in plain sight on the pull request itself.
    """
    report = create_report(left_out=(create_blocked_branch(A_HEALTHY_BRANCH),))

    assert branches_left_out(report) == ()


def test_a_branch_blocked_by_an_ancestor_is_worth_telling():
    """
    A healthy, reviewed, green branch excluded only because of what it stands on has
    nothing of its own to explain that - the ancestor is the whole story.
    """
    report = create_report(
        left_out=(create_blocked_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),)
    )

    assert create_blocked_branch(A_HEALTHY_BRANCH, AN_ANCESTOR) in branches_left_out(
        report
    )


def test_a_branch_blocked_without_a_recorded_tree_is_worth_telling_when_cascaded():
    """
    ``BLOCKED_WITHOUT_RECORD`` is a distinct status from ``BLOCKED``, and cascading
    still means the same thing for it: nothing about this branch itself explains why.
    """
    report = create_report(
        left_out=(blocked_without_record(A_HEALTHY_BRANCH, AN_ANCESTOR),)
    )

    assert blocked_without_record(A_HEALTHY_BRANCH, AN_ANCESTOR) in branches_left_out(
        report
    )


def test_a_branch_with_its_own_red_checks_needs_no_comment():
    """
    Its own checks are already red on the pull request; a comment would say only what
    is already visible there.
    """
    report = create_report(left_out=(create_red_branch(A_HEALTHY_BRANCH),))

    assert branches_left_out(report) == ()


def test_a_branch_red_because_of_an_ancestor_is_worth_telling():
    """The branch's own checks are green; only its ancestor's are not."""
    report = create_report(left_out=(create_red_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),))

    assert create_red_branch(A_HEALTHY_BRANCH, AN_ANCESTOR) in branches_left_out(report)


def test_a_still_draft_branch_needs_no_comment():
    """
    A draft is nobody's to review yet, which is exactly the case a pull request is not
    the place for a note about.
    """
    report = create_report(left_out=(create_unreviewed_branch(A_HEALTHY_BRANCH),))

    assert branches_left_out(report) == ()


def test_a_reviewed_branch_standing_on_a_draft_is_worth_telling():
    """
    The branch itself left draft behind; only what it stands on has not.
    """
    report = create_report(
        left_out=(create_unreviewed_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),)
    )

    assert create_unreviewed_branch(A_HEALTHY_BRANCH, AN_ANCESTOR) in branches_left_out(
        report
    )


def test_a_branch_outside_the_requested_plan_needs_no_comment():
    """
    Nothing is wrong with it; a filtered build simply was not asked for it, cascaded
    exclusion included.
    """
    report = create_report(
        left_out=(
            PullRequestStackTipOutcome(
                branch=A_HEALTHY_BRANCH,
                pull_request_number=1,
                status=TipStatus.ANOTHER_PLAN,
                attributed_to=AN_ANCESTOR,
            ),
        )
    )

    assert branches_left_out(report) == ()


def test_a_merged_tip_is_not_left_out():
    """A tip that reached the build is not one its owner needs telling anything about."""
    report = create_report(tips=(create_tip("a-merged-tip", TipStatus.MERGED),))

    assert branches_left_out(report) == ()


# %% what is written, and where


def test_reporting_a_skip_labels_the_branch_and_comments_on_it():
    """
    A comment alone is missed on a pull request nobody happens to be watching just
    then, so the branch is labelled too - purely as this pass's own memory.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests()

    written = report_left_out(
        create_report(tips=(skipped_tip(number=7),)), configuration, fork
    )

    assert fork.label_writes == [
        RecordedLabelWrite(7, (configuration.integration_left_out_label,))
    ]
    assert len(fork.comments) == 1
    assert fork.comments[0].pull_request_number == 7
    assert written[0].status is TipStatus.SKIPPED


def test_a_conflict_comment_names_the_files_and_the_branch_it_collided_with():
    """
    "It was skipped" is not actionable; the paths and the other branch are.
    """
    fork = RecordingPullRequests()

    report_left_out(
        create_report(
            tips=(
                skipped_tip(conflicting_paths=("shared/module.py", "shared/other.py")),
            )
        ),
        make_configuration(),
        fork,
    )

    body = fork.comments[0].body
    assert A_SIBLING_TIP in body
    assert "shared/module.py" in body
    assert "shared/other.py" in body
    assert "/integration-conflict-triage" in body


def test_a_conflict_comment_links_the_sibling_when_its_pull_request_is_open():
    """
    A reader should be able to click straight through to the branch it collided with.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(heads={2: A_SIBLING_TIP})

    report_left_out(create_report(tips=(skipped_tip(),)), configuration, fork)

    expected_link = configuration.fork_repository.pull_request_reference(2)
    assert expected_link in fork.comments[0].body


def test_an_integration_failure_comment_names_what_git_said():
    """
    The build's own refusal is its problem, not the branch's, and the branch's owner
    is told exactly what git said rather than being sent to guess.
    """
    fork = RecordingPullRequests()

    report_left_out(
        create_report(tips=(integration_failed_tip(),)), make_configuration(), fork
    )

    body = fork.comments[0].body
    assert "fatal: refusing to merge unrelated histories" in body
    assert "the build's own problem" in body


def test_a_cascaded_block_comment_names_the_ancestor_and_says_the_branch_is_fine():
    """
    The one thing this branch's owner cannot see from their own state is what they
    stand on.
    """
    fork = RecordingPullRequests()

    report_left_out(
        create_report(left_out=(create_blocked_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),)),
        make_configuration(),
        fork,
    )

    body = fork.comments[0].body
    assert AN_ANCESTOR in body
    assert "own state is fine" in body


def test_a_cascaded_red_checks_comment_says_the_branchs_own_checks_are_fine():
    fork = RecordingPullRequests()

    report_left_out(
        create_report(left_out=(create_red_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),)),
        make_configuration(),
        fork,
    )

    body = fork.comments[0].body
    assert AN_ANCESTOR in body
    assert "own checks are fine" in body


def test_a_cascaded_draft_comment_names_the_draft_ancestor():
    fork = RecordingPullRequests()

    report_left_out(
        create_report(
            left_out=(create_unreviewed_branch(A_HEALTHY_BRANCH, AN_ANCESTOR),)
        ),
        make_configuration(),
        fork,
    )

    body = fork.comments[0].body
    assert AN_ANCESTOR in body
    assert "still a draft" in body


def test_a_branch_already_labelled_is_not_told_again():
    """
    A scheduled build runs several times a day; the label is this pass's own memory
    that it already spoke, so the same unchanged reason is not repeated every time.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(labels={1: [configuration.integration_left_out_label]})

    written = report_left_out(
        create_report(tips=(skipped_tip(number=1),)), configuration, fork
    )

    assert written == ()
    assert fork.comments == []
    assert fork.label_writes == []


# %% wired into the build command


def test_the_build_command_reports_left_out_branches_when_asked():
    """
    ``build --report-left-out`` is what a scheduled run passes; this is the wiring
    between that flag and the module actually doing the telling.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests()
    run = SimpleNamespace(configuration=configuration)

    BuildCommand._report_left_out(
        run, fork, create_report(tips=(skipped_tip(number=3),))
    )

    assert fork.label_writes == [
        RecordedLabelWrite(3, (configuration.integration_left_out_label,))
    ]


def test_a_branch_that_rejoins_a_build_is_cleared_without_a_comment():
    """
    Rejoining is not news the way being left out was, so lifting the label a build
    outgrew never turns into a second announcement.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={9: [configuration.integration_left_out_label]}, heads={9: "a-branch"}
    )

    written = report_left_out(create_report(), configuration, fork)

    assert written == ()
    assert fork.comments == []
    assert fork.label_writes == [RecordedLabelWrite(9, ())]
