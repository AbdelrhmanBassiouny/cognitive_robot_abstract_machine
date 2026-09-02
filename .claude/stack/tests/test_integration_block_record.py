"""
What a block records about the tree it was measured in, and what that lets a build do.

A block is a label, and a label says nothing about which heads the break was found
between. These hold that the heads are written down with the block, that a later reader
can tell whether they are still the fork's heads, and that a build carrying the branch
again lifts the block once the suite passes over it.
"""

from __future__ import annotations

import argparse
import dataclasses

import pytest

from stack import DefaultLabel, LabelWrite, PullRequest

from integration_block_record import (
    BLOCK_RECORD_NAMESPACE,
    BlockRecord,
    BlockRecords,
    BlockStanding,
    MeasuredHead,
    lift_readmitted,
)
from integration_build_commands import BlockBranchCommand, BuildCommand
from integration_exit_codes import IntegrationExitCode
from integration_report import IntegrationReport
from integration_reproduction import CLEARED_COMMENT_PREFIX
from integration_tips import ReadmittedBranch

from test_maintenance import (
    A_LABEL_THIS_TOOL_NEVER_WRITES,
    ForkCheckout,
    RecordedLabelWrite,
    RecordingPullRequests,
    UPSTREAM_BASE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    A_FORK_REMOTE,
    A_PULL_REQUEST_NUMBER,
    FIRST_TIP,
    GitAnsweringForTheFork,
    NEEDS_THE_MODULE,
    REMOVES_THE_MODULE,
    SECOND_TIP,
    create_branch_object,
    create_integration_test_failure,
    create_stack_object,
)
from localisation_fixtures import LocalisingRun, RecordingFork
from test_integration_failure import (
    A_SUITE_OVER_THE_BUILD,
    two_tips_that_break_only_together,
)

A_HEAD = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"
"""
A commit a branch pointed at when a break was measured over it.
"""

ANOTHER_HEAD = "9a8b7c6d5e4f30211203f4e5d6c7b8a99a8b7c6d"
"""
A commit a branch points at after it has moved.
"""

A_PARTNER_NUMBER = 2
"""
The pull request publishing the branch the blocked one was measured against.
"""


def records_on(checkout: ForkCheckout) -> BlockRecords:
    """:param checkout: The fork to read.
    :return: What that fork has recorded about its blocks."""
    return BlockRecords.read(checkout.git, A_FORK_REMOTE)


def references_on(checkout: ForkCheckout) -> dict[str, str]:
    """:param checkout: The fork to read.
    :return: Every block record reference the fork carries, with its commit."""
    listed = checkout.run_git("ls-remote", A_FORK_REMOTE, f"{BLOCK_RECORD_NAMESPACE}/*")
    return {
        line.split("\t")[1]: line.split("\t")[0]
        for line in listed.splitlines()
        if line.strip()
    }


def two_published_tips(checkout: ForkCheckout) -> tuple[MeasuredHead, MeasuredHead]:
    """
    :param checkout: The checkout to publish them from.
    :return: The heads of two tips on the fork, the first being the one a block is about.
    """
    blocked = checkout.branch_from(SECOND_TIP, UPSTREAM_BASE)
    partner = checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    return (
        MeasuredHead(SECOND_TIP, A_PULL_REQUEST_NUMBER, blocked),
        MeasuredHead(FIRST_TIP, A_PARTNER_NUMBER, partner),
    )


# %% what a block is kept as


def test_a_block_records_the_head_of_every_branch_the_break_was_measured_over(
    fork_checkout: ForkCheckout,
):
    """
    The block is about a tree, and the tree is those heads: without them, nothing can
    later say whether the tree the branch was blocked in still exists.
    """
    heads = two_published_tips(fork_checkout)
    failure = create_integration_test_failure(measured_over=heads)

    records_on(fork_checkout).record(failure)

    assert references_on(fork_checkout) == {
        BlockRecord(
            A_PULL_REQUEST_NUMBER, head.pull_request_number, head.commit
        ).reference: (head.commit)
        for head in heads
    }


def test_a_block_record_is_not_a_branch(fork_checkout: ForkCheckout):
    """
    A record kept as a branch would be listed, cloned and offered for checkout.
    """
    heads = two_published_tips(fork_checkout)
    branches_before = fork_checkout.run_git("ls-remote", "--heads", A_FORK_REMOTE)

    records_on(fork_checkout).record(
        create_integration_test_failure(measured_over=heads)
    )

    assert (
        fork_checkout.run_git("ls-remote", "--heads", A_FORK_REMOTE) == branches_before
    )


def test_recording_a_block_again_replaces_what_the_earlier_one_recorded(
    fork_checkout: ForkCheckout,
):
    """
    A branch blocked again after it moved was measured over a different tree, and a head
    left over from the earlier measurement would keep the new block standing for a
    partner it is no longer about.
    """
    blocked, partner = two_published_tips(fork_checkout)
    records = records_on(fork_checkout).record(
        create_integration_test_failure(measured_over=(blocked, partner))
    )
    moved = dataclasses.replace(
        blocked, commit=fork_checkout.commit_on(SECOND_TIP, "later", "more work\n")
    )

    records.record(create_integration_test_failure(measured_over=(moved,)))

    assert references_on(fork_checkout) == {
        BlockRecord(
            A_PULL_REQUEST_NUMBER, A_PULL_REQUEST_NUMBER, moved.commit
        ).reference: (moved.commit)
    }


def test_forgetting_a_block_removes_every_record_of_it(fork_checkout: ForkCheckout):
    """
    A lifted block whose record stayed behind would be read as standing the moment the
    branch is blocked again by hand, over a tree nothing measured.
    """
    heads = two_published_tips(fork_checkout)
    records = records_on(fork_checkout).record(
        create_integration_test_failure(measured_over=heads)
    )

    records.forget(A_PULL_REQUEST_NUMBER)

    assert references_on(fork_checkout) == {}


def test_a_record_is_read_back_from_its_reference():
    """
    The reference is the whole record: which pull request is blocked, which one's head
    it names, and the commit the fork has it pointing at.
    """
    record = BlockRecord(A_PULL_REQUEST_NUMBER, A_PARTNER_NUMBER, A_HEAD)

    assert BlockRecord.named_by(record.reference, A_HEAD) == record


@pytest.mark.parametrize(
    "reference",
    [
        f"{BLOCK_RECORD_NAMESPACE}/{A_PULL_REQUEST_NUMBER}",
        f"{BLOCK_RECORD_NAMESPACE}/{A_PULL_REQUEST_NUMBER}/not-a-number",
        f"{BLOCK_RECORD_NAMESPACE}/{A_PULL_REQUEST_NUMBER}/{A_PARTNER_NUMBER}/more",
        "refs/integration/passed/branch-head/20260830/0f1e2d3c",
        "refs/heads/main",
    ],
)
def test_a_reference_that_is_not_a_block_record_reads_as_none(reference: str):
    """
    A reference this cannot read is absent rather than fatal, so something newer writing
    below the namespace never stops a rebuild.
    """
    assert BlockRecord.named_by(reference, A_HEAD) is None


# %% whether a block still stands


def records_of(*records: BlockRecord) -> BlockRecords:
    """:param records: What the fork is taken to have recorded.
    :return: Those records, read through a runner nothing here drives."""
    return BlockRecords(
        git=GitAnsweringForTheFork(), remote=A_FORK_REMOTE, records=records
    )


A_RECORDED_BLOCK = records_of(
    BlockRecord(A_PULL_REQUEST_NUMBER, A_PULL_REQUEST_NUMBER, A_HEAD),
    BlockRecord(A_PULL_REQUEST_NUMBER, A_PARTNER_NUMBER, ANOTHER_HEAD),
)
"""
One block, measured over the blocked branch's head and its partner's.
"""


def test_a_block_stands_while_every_head_it_was_measured_over_is_still_the_head():
    """
    The tree the break was found in still exists, so the break is still there.
    """
    standing = A_RECORDED_BLOCK.standing_of(
        A_PULL_REQUEST_NUMBER,
        {A_PULL_REQUEST_NUMBER: A_HEAD, A_PARTNER_NUMBER: ANOTHER_HEAD},
    )

    assert standing is BlockStanding.STANDS


def test_a_block_is_stale_once_the_blocked_branch_has_moved():
    """
    The case that left a branch blocked for two days after a restack had moved it:
    the tree it was blocked in was gone and nothing noticed.
    """
    standing = A_RECORDED_BLOCK.standing_of(
        A_PULL_REQUEST_NUMBER,
        {A_PULL_REQUEST_NUMBER: ANOTHER_HEAD, A_PARTNER_NUMBER: ANOTHER_HEAD},
    )

    assert standing is BlockStanding.STALE


def test_a_block_is_stale_once_the_branch_it_was_measured_against_has_moved():
    """
    Either side of a break can be the one that changes.
    """
    standing = A_RECORDED_BLOCK.standing_of(
        A_PULL_REQUEST_NUMBER,
        {A_PULL_REQUEST_NUMBER: A_HEAD, A_PARTNER_NUMBER: A_HEAD},
    )

    assert standing is BlockStanding.STALE


def test_a_block_is_stale_once_the_branch_it_was_measured_against_has_left_the_board():
    """
    A partner that merged or closed is a tree that cannot be assembled again.
    """
    standing = A_RECORDED_BLOCK.standing_of(
        A_PULL_REQUEST_NUMBER, {A_PULL_REQUEST_NUMBER: A_HEAD}
    )

    assert standing is BlockStanding.STALE


def test_a_block_nothing_recorded_a_tree_for_is_unrecorded():
    """
    A label applied by hand, or before anything wrote a record, is not one a build can
    tell has gone stale - and it has to be told apart from one that stands.
    """
    standing = records_of().standing_of(
        A_PULL_REQUEST_NUMBER, {A_PULL_REQUEST_NUMBER: A_HEAD}
    )

    assert standing is BlockStanding.UNRECORDED


def test_annotating_a_stack_reads_each_blocked_branch_against_the_fork_s_heads():
    """
    The standing is worth nothing if nothing fills the field selection reads, and it is
    answered from what the fork has each branch pointing at now rather than from what
    this checkout last fetched.
    """
    label = make_configuration().integration_conflict_label
    blocked = create_branch_object("blocked", A_PULL_REQUEST_NUMBER, labels=[label])
    partner = create_branch_object("partner", A_PARTNER_NUMBER)
    git = GitAnsweringForTheFork(
        heads={blocked.name: A_HEAD, partner.name: A_HEAD},
        references={
            BlockRecord(
                A_PULL_REQUEST_NUMBER, A_PULL_REQUEST_NUMBER, A_HEAD
            ).reference: A_HEAD,
            BlockRecord(
                A_PULL_REQUEST_NUMBER, A_PARTNER_NUMBER, ANOTHER_HEAD
            ).reference: (ANOTHER_HEAD),
        },
    )

    BlockRecords.read(git, A_FORK_REMOTE).annotate(
        create_stack_object([blocked, partner])
    )

    assert blocked.block_standing == str(BlockStanding.STALE)
    assert partner.block_standing is None


# %% lifting a block the build has outgrown


def a_readmitted_branch_on(
    checkout: ForkCheckout,
) -> tuple[ReadmittedBranch, RecordingPullRequests]:
    """
    :param checkout: The fork to record the block on.
    :return: A branch carried again after its block went stale, and the fork whose
        pull request still carries the label.
    """
    heads = two_published_tips(checkout)
    records_on(checkout).record(create_integration_test_failure(measured_over=heads))
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={
            A_PULL_REQUEST_NUMBER: [
                A_LABEL_THIS_TOOL_NEVER_WRITES,
                configuration.integration_conflict_label,
            ]
        },
        heads={A_PULL_REQUEST_NUMBER: SECOND_TIP},
    )
    return ReadmittedBranch(SECOND_TIP, A_PULL_REQUEST_NUMBER), fork


def test_lifting_removes_the_label_and_leaves_every_other_label_alone(
    fork_checkout: ForkCheckout,
):
    """
    GitHub's label write replaces the whole set.
    """
    readmitted, fork = a_readmitted_branch_on(fork_checkout)
    configuration = make_configuration()

    lift_readmitted(
        [readmitted], A_BUILD_BRANCH, configuration, fork, records_on(fork_checkout)
    )

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


def test_lifting_says_on_the_pull_request_which_build_carried_the_branch(
    fork_checkout: ForkCheckout,
):
    """
    The block arrived as a comment; its lifting is readable in the same place, and names
    the build whose suite is the evidence.
    """
    readmitted, fork = a_readmitted_branch_on(fork_checkout)

    lift_readmitted(
        [readmitted],
        A_BUILD_BRANCH,
        make_configuration(),
        fork,
        records_on(fork_checkout),
    )

    posted = fork.comments[0]
    assert posted.pull_request_number == A_PULL_REQUEST_NUMBER
    assert posted.body.startswith(CLEARED_COMMENT_PREFIX)
    assert A_BUILD_BRANCH in posted.body


def test_lifting_forgets_the_record_the_block_was_measured_over(
    fork_checkout: ForkCheckout,
):
    """
    A record that outlived its block would answer for the next block by hand.
    """
    readmitted, fork = a_readmitted_branch_on(fork_checkout)

    lift_readmitted(
        [readmitted],
        A_BUILD_BRANCH,
        make_configuration(),
        fork,
        records_on(fork_checkout),
    )

    assert references_on(fork_checkout) == {}


def test_a_readmitted_branch_that_has_lost_its_label_since_is_not_written_to(
    fork_checkout: ForkCheckout,
):
    """
    A block lifted by hand between the build reading the fork and the suite finishing is
    already lifted; writing again would comment on nothing.
    """
    readmitted, _ = a_readmitted_branch_on(fork_checkout)
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [A_LABEL_THIS_TOOL_NEVER_WRITES]},
        heads={A_PULL_REQUEST_NUMBER: SECOND_TIP},
    )

    lifted = lift_readmitted(
        [readmitted],
        A_BUILD_BRANCH,
        make_configuration(),
        fork,
        records_on(fork_checkout),
    )

    assert lifted == ()
    assert fork.label_writes == []
    assert fork.comments == []


# %% the build, end to end


@dataclasses.dataclass(frozen=True)
class RunWithASuite(LocalisingRun):
    """
    A run over the scratch fork whose configured suite the test chooses.
    """

    test_command: str = "true"
    """
    The suite a build is checked with.
    """

    @property
    def configuration(self):
        """:return: The resolved configuration, naming that suite."""
        return dataclasses.replace(
            make_configuration(), integration_test_command=self.test_command
        )


def a_stale_block_on(
    checkout: ForkCheckout, heads: tuple[MeasuredHead, MeasuredHead]
) -> None:
    """
    Block the first of two tips as measured over both, then move it.

    :param checkout: The fork to record the block on.
    :param heads: The two tips' heads as they were when the break was measured.
    """
    records_on(checkout).record(create_integration_test_failure(measured_over=heads))
    checkout.commit_on(heads[0].branch, "later", "the work that moved the branch\n")


def the_board_with_a_block() -> list[PullRequest]:
    """:return: Two tips, the second blocked."""
    label = make_configuration().integration_conflict_label
    return [
        PullRequest(
            number=A_PARTNER_NUMBER, head=FIRST_TIP, base=UPSTREAM_BASE, draft=False
        ),
        PullRequest(
            number=A_PULL_REQUEST_NUMBER,
            head=SECOND_TIP,
            base=UPSTREAM_BASE,
            draft=False,
            labels=[label],
        ),
    ]


def build_over(
    run: RunWithASuite, capsys
) -> tuple[IntegrationExitCode, IntegrationReport]:
    """
    :param run: The run to build in.
    :param capsys: pytest's capture, the document is read back from.
    :return: The status and the document the build printed.
    """
    status = BuildCommand().run(
        run, argparse.Namespace(restack=False, run_tests=True, plan=[], json=True)
    )
    return status, IntegrationReport.from_json(capsys.readouterr().out)


def test_a_blocked_branch_whose_head_moved_is_carried_again_and_unblocked_on_a_green_suite(
    fork_checkout: ForkCheckout, capsys
):
    """
    The whole defect in one build: a branch blocked in a tree that no longer exists is
    tried again, and the suite passing over a build carrying it is what lifts the label
    - with nobody having written a reproduction test.
    """
    a_stale_block_on(fork_checkout, two_published_tips(fork_checkout))
    fork = RecordingFork(
        labels={A_PULL_REQUEST_NUMBER: [DefaultLabel.INTEGRATION_CONFLICT]},
        heads={A_PULL_REQUEST_NUMBER: SECOND_TIP},
    )
    run = RunWithASuite(fork_checkout, the_board_with_a_block(), fork)

    status, report = build_over(run, capsys)

    assert status is IntegrationExitCode.SUCCESS
    assert [entry.branch for entry in report.tips] == [FIRST_TIP, SECOND_TIP]
    assert report.readmitted == (ReadmittedBranch(SECOND_TIP, A_PULL_REQUEST_NUMBER),)
    assert fork.label_writes == [RecordedLabelWrite(A_PULL_REQUEST_NUMBER, ())]
    assert references_on(fork_checkout) == {}


def test_a_blocked_branch_whose_tree_still_exists_is_left_out_as_before(
    fork_checkout: ForkCheckout, capsys
):
    """
    Nothing has changed since the break was measured, so the break is still there and a
    build carrying the branch would only reproduce it.
    """
    records_on(fork_checkout).record(
        create_integration_test_failure(measured_over=two_published_tips(fork_checkout))
    )
    fork = RecordingFork(
        labels={A_PULL_REQUEST_NUMBER: [DefaultLabel.INTEGRATION_CONFLICT]},
        heads={A_PULL_REQUEST_NUMBER: SECOND_TIP},
    )
    run = RunWithASuite(fork_checkout, the_board_with_a_block(), fork)

    _, report = build_over(run, capsys)

    assert [entry.branch for entry in report.tips] == [FIRST_TIP]
    assert report.readmitted == ()
    assert fork.label_writes == []


def test_a_readmitted_branch_that_still_breaks_the_build_is_blocked_again_over_the_new_tree(
    fork_checkout: ForkCheckout,
):
    """
    Carrying a branch again is speculative, and the search that follows a red suite has
    to assemble the same tips the build did: a search that honoured the stale block
    would look for the culprit in a tree that does not contain it.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)
    culprit = next(entry for entry in pull_requests if entry.head == REMOVES_THE_MODULE)
    partner = next(entry for entry in pull_requests if entry.head == NEEDS_THE_MODULE)
    culprit.labels = [DefaultLabel.INTEGRATION_CONFLICT]
    records_on(fork_checkout).record(
        create_integration_test_failure(
            culprit=culprit.head,
            number=culprit.number,
            measured_over=(
                MeasuredHead(
                    culprit.head,
                    culprit.number,
                    fork_checkout.published_commit(A_FORK_REMOTE, UPSTREAM_BASE),
                ),
                MeasuredHead(
                    partner.head,
                    partner.number,
                    fork_checkout.published_commit(A_FORK_REMOTE, partner.head),
                ),
            ),
        )
    )
    fork = RecordingFork(
        labels={culprit.number: [DefaultLabel.INTEGRATION_CONFLICT]},
        heads={culprit.number: culprit.head},
    )
    run = RunWithASuite(fork_checkout, pull_requests, fork, A_SUITE_OVER_THE_BUILD)

    status = BlockBranchCommand().run(run, argparse.Namespace(json=True))

    assert status is IntegrationExitCode.TESTS_FAILED
    assert references_on(fork_checkout) == {
        BlockRecord(culprit.number, culprit.number, head).reference: head
        for head in [fork_checkout.published_commit(A_FORK_REMOTE, culprit.head)]
    } | {
        BlockRecord(culprit.number, partner.number, head).reference: head
        for head in [fork_checkout.published_commit(A_FORK_REMOTE, partner.head)]
    }
