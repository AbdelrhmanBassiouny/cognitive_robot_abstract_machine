"""
Which branches a build is made of.

Pure: what a stack's shape and its pull requests' review state decide, with no
repository involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from stack import BranchStatus, Stack

import integration
from integration import (
    IntegrationExitCode,
    TipStatus,
    exit_code_for,
    select_for_build,
    stack_to_build,
    tips_of,
)

from integration_fixtures import (
    create_blocked_branch,
    create_branch_object,
    create_report,
    create_stack_object,
    create_tip,
    create_unreviewed_branch,
    make_configuration,
)

BLOCKING_LABEL = make_configuration().needs_resolution_label
"""
One of the labels that withholds a branch, read from the configuration that names them.
"""

A_FORK = object()
"""
Stands in for the fork, which the stack reader is handed and this stand-in ignores.
"""

# %% which branches a build is made of


def test_only_the_tip_of_a_stack_is_merged():
    """
    A tip contains its own stack, so merging its parent as well would merge the same
    commits twice and say nothing new.
    """
    bottom = create_branch_object("bottom", 1)
    top = create_branch_object("top", 2, parent=bottom.name)

    tips = tips_of(create_stack_object([bottom, top]))

    assert [tip.name for tip in tips] == [top.name]


def test_a_branch_already_landed_upstream_is_left_out():
    """
    Its commits are in the base the build starts from, so merging it adds nothing.
    """
    landed = create_branch_object("landed", 1)
    in_flight = create_branch_object("in-flight", 2)

    tips = tips_of(
        create_stack_object([landed, in_flight], landed=frozenset({landed.name}))
    )

    assert [tip.name for tip in tips] == [in_flight.name]


def test_tips_are_merged_in_ascending_pull_request_order():
    """
    Once a conflict can skip a tip, merge order decides *which* tip is skipped - so it
    is stated rather than left to whatever order the board happened to arrive in.
    """
    earlier = create_branch_object("earlier", 2)
    middle = create_branch_object("middle", 5)
    later = create_branch_object("later", 9)

    tips = tips_of(create_stack_object([later, earlier, middle]))

    assert [tip.name for tip in tips] == [earlier.name, middle.name, later.name]


def test_a_draft_branch_is_left_out():
    """
    A draft is work its own author has not reviewed yet, and this repository's
    convention is that leaving draft is that review.

    A build carries only what has had it.
    """
    reviewed = create_branch_object("reviewed", 1)
    unreviewed = create_branch_object("unreviewed", 2, status=BranchStatus.DRAFT)

    tips = tips_of(create_stack_object([reviewed, unreviewed]))

    assert [tip.name for tip in tips] == [reviewed.name]


def test_a_branch_promoted_upstream_is_still_carried():
    """
    ``in-review`` takes precedence over ``ready`` in :func:`derive_status`, so a status
    test written against ``ready`` alone would drop every branch already promoted - the
    most reviewed work there is, and still not in the base.
    """
    promoted = create_branch_object("promoted", 1, status=BranchStatus.IN_REVIEW)

    tips = tips_of(create_stack_object([promoted]))

    assert [tip.name for tip in tips] == [promoted.name]


def test_a_ready_branch_standing_on_a_draft_is_left_out_with_it():
    """
    A tip carries its whole stack, so merging one that sits on a draft would put that
    draft's commits in the build under a ready branch's name - which is the reading of
    "only ready pull requests" that quietly does the opposite.
    """
    unreviewed = create_branch_object("unreviewed", 1, status=BranchStatus.DRAFT)
    reviewed = create_branch_object("reviewed", 2, parent=unreviewed.name)

    tips = tips_of(create_stack_object([unreviewed, reviewed]))

    assert [tip.name for tip in tips] == []


def test_the_last_reviewed_branch_below_a_draft_is_the_one_merged():
    """
    A stack that goes draft part way up still has reviewed work beneath the draft, and
    that work is carried: the merge point is the last branch reached before the first
    draft, not the stack's own tip.
    """
    bottom = create_branch_object("bottom", 1)
    middle = create_branch_object("middle", 2, parent=bottom.name)
    top = create_branch_object("top", 3, parent=middle.name, status=BranchStatus.DRAFT)

    tips = tips_of(create_stack_object([bottom, middle, top]))

    assert [tip.name for tip in tips] == [middle.name]


def test_an_unreviewed_branch_is_named_rather_than_silently_dropped():
    """
    A build that carries nine of nineteen branches and says so only by omission reads as
    having covered everything.

    Each one left out names itself and why.
    """
    draft = create_branch_object("unreviewed", 7, status=BranchStatus.DRAFT)

    left_out_branches = select_for_build(create_stack_object([draft])).left_out

    assert [
        (left_out.branch, left_out.pull_request_number)
        for left_out in left_out_branches
    ] == [(draft.name, draft.pull_request_number)]
    assert left_out_branches[0].attributed_to is None


def test_a_branch_nobody_reviewed_carries_the_status_that_says_so():
    """
    A branch left out for want of review is one of the outcomes a build reports, not a
    separate kind of thing - so it says what happened to it in the same vocabulary, and
    that status says the build never carried it.
    """
    draft = create_branch_object("unreviewed", 7, status=BranchStatus.DRAFT)

    left_out_branches = select_for_build(create_stack_object([draft])).left_out

    assert left_out_branches[0].status is TipStatus.UNREVIEWED
    assert not left_out_branches[0].is_integrated


def test_a_branch_left_out_for_its_ancestor_names_that_ancestor():
    """
    "Your branch was left out" is not actionable when the branch is out of draft and its
    author can see nothing wrong with it - the draft beneath it is the thing to act on.
    """
    beneath = create_branch_object("beneath", 1, status=BranchStatus.DRAFT)
    above = create_branch_object("above", 2, parent=beneath.name)

    left_out_branches = select_for_build(create_stack_object([beneath, above])).left_out

    assert {
        left_out.branch: left_out.attributed_to for left_out in left_out_branches
    } == {
        beneath.name: None,
        above.name: beneath.name,
    }


def test_leaving_a_branch_out_as_unreviewed_is_not_a_failed_build():
    """
    Excluding a draft is the policy working, not a build going wrong - so it must not
    reach the exit status that means a tip the build tried to carry did not make it.
    """
    status = exit_code_for(
        create_report(
            tips=(create_tip("carried", TipStatus.MERGED),),
            left_out=(create_unreviewed_branch("a-draft"),),
        )
    )

    assert status is IntegrationExitCode.SUCCESS


def test_a_reviewed_branch_whose_only_child_is_a_draft_becomes_the_merge_point():
    """
    The same rule with nothing else to carry the parent: it is the deepest reviewed
    branch, so it is merged itself rather than vanishing behind a child no build takes.
    """
    reviewed = create_branch_object("reviewed", 1)
    unreviewed = create_branch_object(
        "unreviewed", 2, parent=reviewed.name, status=BranchStatus.DRAFT
    )

    tips = tips_of(create_stack_object([reviewed, unreviewed]))

    assert [tip.name for tip in tips] == [reviewed.name]


# %% the branches a label withholds


def test_a_branch_carrying_a_blocking_label_is_left_out():
    """
    The label says this branch conflicts with its base or has broken a sibling. Carrying
    it puts a known conflict or a known break into the branch this workflow exists to
    build from, which is the one thing it is for.
    """
    blocked = create_branch_object("blocked", 1, labels=[BLOCKING_LABEL])

    selection = select_for_build(create_stack_object([blocked]))

    assert selection.integrated == ()
    assert [absent.branch for absent in selection.left_out] == [blocked.name]


def test_a_blocked_branch_says_a_label_is_why_rather_than_want_of_review():
    """
    "Unreviewed" sends its author to review a branch they have already reviewed. The
    status names the rule that actually left it out, so the action it implies is the
    one that would let it back in.
    """
    blocked = create_branch_object("blocked", 1, labels=[BLOCKING_LABEL])

    left_out = select_for_build(create_stack_object([blocked])).left_out

    assert left_out[0].status is TipStatus.BLOCKED
    assert not left_out[0].is_integrated
    assert left_out[0].attributed_to is None


def test_a_branch_standing_on_a_blocked_one_is_left_out_naming_it():
    """
    A tip contains its whole stack, so carrying one that stands on a blocked branch
    carries the blocked branch's commits under another name - and its author, whose own
    branch is unlabelled, is told nothing they can act on unless it names the one below.
    """
    beneath = create_branch_object("beneath", 1, labels=[BLOCKING_LABEL])
    above = create_branch_object("above", 2, parent=beneath.name)

    left_out = select_for_build(create_stack_object([beneath, above])).left_out

    assert {absent.branch: absent.attributed_to for absent in left_out} == {
        beneath.name: None,
        above.name: beneath.name,
    }
    assert {absent.status for absent in left_out} == {TipStatus.BLOCKED}


@pytest.mark.parametrize("label", make_configuration().blocking_labels)
def test_every_configured_blocking_label_holds_a_branch_out(label: str):
    """
    One collection decides what a pass withholds and what a build leaves out, so a label
    added to it is honoured here without anything being written down twice.
    """
    blocked = create_branch_object("blocked", 1, labels=[label])

    assert select_for_build(create_stack_object([blocked])).integrated == ()


def test_leaving_a_blocked_branch_out_is_not_a_failed_build():
    """
    Withholding it is the rule working, exactly as excluding a draft is - so it must not
    reach the status that means a tip the build tried to carry did not make it.
    """
    status = exit_code_for(
        create_report(
            tips=(create_tip("carried", TipStatus.MERGED),),
            left_out=(create_blocked_branch("blocked"),),
        )
    )

    assert status is IntegrationExitCode.SUCCESS


# %% which stack a build is made from


@dataclass
class RunReadingStacksInTurn:
    """An :class:`~integration.IntegrationRun` stand-in handing out one stack per read.

    What it is for is the difference between them: a restack writes labels and moves
    tips, so a second read has to see something the first could not.
    """

    stacks: list[Stack]
    """The stacks to hand out, in the order they are read."""

    git: str = "a-git-runner"
    """Stands in for the runner, which only the restack is handed."""

    reads: int = 0
    """How many times the stack has been read."""

    def stack(self, fork: object) -> Stack:
        """
        :param fork: Ignored - this stand-in reads no pull requests.
        :return: The next stack, or the last one once they run out.
        """
        self.reads += 1
        return self.stacks[min(self.reads, len(self.stacks)) - 1]

    def refresh_remotes(self) -> None:
        """Fetches nothing."""


def test_a_build_that_restacks_is_made_from_the_stack_the_restack_left_behind(
    monkeypatch,
):
    """
    A restack writes the label that withholds a branch it could not move, so a stack read
    before it cannot say which branches this pass has just blocked - and a build made
    from that snapshot carries them.
    """
    before = create_stack_object([create_branch_object("a-branch", 1)])
    after = create_stack_object(
        [create_branch_object("a-branch", 1, labels=[BLOCKING_LABEL])]
    )
    run = RunReadingStacksInTurn([before, after])
    monkeypatch.setattr(integration, "restack", lambda *arguments: None)

    assert stack_to_build(run, A_FORK, restack_first=True) is after


def test_a_build_that_restacks_restacks_before_reading_again(monkeypatch):
    """
    Reading twice buys nothing if the second read happens first.
    """
    reads_when_restacked: list[int] = []
    run = RunReadingStacksInTurn([create_stack_object([])])
    monkeypatch.setattr(
        integration,
        "restack",
        lambda *arguments: reads_when_restacked.append(run.reads),
    )

    stack_to_build(run, A_FORK, restack_first=True)

    assert reads_when_restacked == [1] and run.reads == 2


def test_a_build_that_does_not_restack_reads_the_stack_once():
    """
    Nothing has moved, so a second read would cost an API call to be told the same thing.
    """
    only = create_stack_object([])
    run = RunReadingStacksInTurn([only])

    assert stack_to_build(run, A_FORK, restack_first=False) is only
    assert run.reads == 1
