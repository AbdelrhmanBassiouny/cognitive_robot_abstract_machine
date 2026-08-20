"""
Which branches a build is made of.

Pure: what a stack's shape and its pull requests' review state decide, with no
repository involved.
"""

from __future__ import annotations


from stack import BranchStatus

from integration import (
    IntegrationExitCode,
    TipStatus,
    exit_code_for,
    select_for_build,
    tips_of,
)

from integration_fixtures import (
    create_branch_object,
    create_report,
    create_stack_object,
    create_tip,
    create_unreviewed_branch,
)

# %% which branches a build is made of


def test_only_the_tip_of_a_stack_is_merged():
    """
    A tip contains its own stack, so merging its parent as well would merge the same
    commits twice and say nothing new.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("bottom", 1),
                create_branch_object("top", 2, parent="bottom"),
            ]
        )
    )

    assert [tip.name for tip in tips] == ["top"]


def test_a_branch_already_landed_upstream_is_left_out():
    """
    Its commits are in the base the build starts from, so merging it adds nothing.
    """
    tips = tips_of(
        create_stack_object(
            [create_branch_object("landed", 1), create_branch_object("in-flight", 2)],
            landed=frozenset({"landed"}),
        )
    )

    assert [tip.name for tip in tips] == ["in-flight"]


def test_tips_are_merged_in_ascending_pull_request_order():
    """
    Once a conflict can skip a tip, merge order decides *which* tip is skipped - so it
    is stated rather than left to whatever order the board happened to arrive in.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("later", 9),
                create_branch_object("earlier", 2),
                create_branch_object("middle", 5),
            ]
        )
    )

    assert [tip.name for tip in tips] == ["earlier", "middle", "later"]


def test_a_draft_branch_is_left_out():
    """
    A draft is work its own author has not reviewed yet, and this repository's
    convention is that leaving draft is that review.

    A build carries only what has had it.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("reviewed", 1),
                create_branch_object("unreviewed", 2, status=BranchStatus.DRAFT),
            ]
        )
    )

    assert [tip.name for tip in tips] == ["reviewed"]


def test_a_branch_promoted_upstream_is_still_carried():
    """
    ``in-review`` takes precedence over ``ready`` in :func:`derive_status`, so a status
    test written against ``ready`` alone would drop every branch already promoted - the
    most reviewed work there is, and still not in the base.
    """
    tips = tips_of(
        create_stack_object(
            [create_branch_object("promoted", 1, status=BranchStatus.IN_REVIEW)]
        )
    )

    assert [tip.name for tip in tips] == ["promoted"]


def test_a_ready_branch_standing_on_a_draft_is_left_out_with_it():
    """
    A tip carries its whole stack, so merging one that sits on a draft would put that
    draft's commits in the build under a ready branch's name - which is the reading of
    "only ready pull requests" that quietly does the opposite.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("unreviewed", 1, status=BranchStatus.DRAFT),
                create_branch_object("reviewed", 2, parent="unreviewed"),
            ]
        )
    )

    assert [tip.name for tip in tips] == []


def test_the_last_reviewed_branch_below_a_draft_is_the_one_merged():
    """
    A stack that goes draft part way up still has reviewed work beneath the draft, and
    that work is carried: the merge point is the last branch reached before the first
    draft, not the stack's own tip.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("bottom", 1),
                create_branch_object("middle", 2, parent="bottom"),
                create_branch_object(
                    "top", 3, parent="middle", status=BranchStatus.DRAFT
                ),
            ]
        )
    )

    assert [tip.name for tip in tips] == ["middle"]


def test_an_unreviewed_branch_is_named_rather_than_silently_dropped():
    """
    A build that carries nine of nineteen branches and says so only by omission reads as
    having covered everything.

    Each one left out names itself and why.
    """
    unreviewed = select_for_build(
        create_stack_object(
            [create_branch_object("unreviewed", 7, status=BranchStatus.DRAFT)]
        )
    ).unreviewed

    assert [
        (left_out.branch, left_out.pull_request_number) for left_out in unreviewed
    ] == [("unreviewed", 7)]
    assert unreviewed[0].attributed_to is None


def test_a_branch_nobody_reviewed_carries_the_status_that_says_so():
    """
    A branch left out for want of review is one of the outcomes a build reports, not a
    separate kind of thing - so it says what happened to it in the same vocabulary, and
    that status says the build never carried it.
    """
    unreviewed = select_for_build(
        create_stack_object(
            [create_branch_object("unreviewed", 7, status=BranchStatus.DRAFT)]
        )
    ).unreviewed

    assert unreviewed[0].status is TipStatus.UNREVIEWED
    assert not unreviewed[0].is_integrated


def test_a_branch_left_out_for_its_ancestor_names_that_ancestor():
    """
    "Your branch was left out" is not actionable when the branch is out of draft and its
    author can see nothing wrong with it - the draft beneath it is the thing to act on.
    """
    unreviewed = select_for_build(
        create_stack_object(
            [
                create_branch_object("beneath", 1, status=BranchStatus.DRAFT),
                create_branch_object("above", 2, parent="beneath"),
            ]
        )
    ).unreviewed

    assert {left_out.branch: left_out.attributed_to for left_out in unreviewed} == {
        "beneath": None,
        "above": "beneath",
    }


def test_leaving_a_branch_out_as_unreviewed_is_not_a_failed_build():
    """
    Excluding a draft is the policy working, not a build going wrong - so it must not
    reach the exit status that means a tip the build tried to carry did not make it.
    """
    status = exit_code_for(
        create_report(
            tips=(create_tip("carried", TipStatus.MERGED),),
            unreviewed=(create_unreviewed_branch("a-draft"),),
        )
    )

    assert status is IntegrationExitCode.SUCCESS


def test_a_reviewed_branch_whose_only_child_is_a_draft_becomes_the_merge_point():
    """
    The same rule with nothing else to carry the parent: it is the deepest reviewed
    branch, so it is merged itself rather than vanishing behind a child no build takes.
    """
    tips = tips_of(
        create_stack_object(
            [
                create_branch_object("reviewed", 1),
                create_branch_object(
                    "unreviewed", 2, parent="reviewed", status=BranchStatus.DRAFT
                ),
            ]
        )
    )

    assert [tip.name for tip in tips] == ["reviewed"]
