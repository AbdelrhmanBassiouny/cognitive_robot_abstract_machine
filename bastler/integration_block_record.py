"""
What a block was measured in, so a later build can tell whether that tree still exists.

A branch that breaks another is blocked with a label, and a label says nothing about the
tree the break was found in. Once a head in that tree moves - a restack, a fix, a partner
merging - the tree the block is about is gone, and holding the branch out is holding it
out for a break nothing has measured since. So the heads the break was found between are
written down with the block, a build honours the block only while every one of them is
still the fork's head, and a green suite over a build carrying the branch again is what
lifts the label.

Kept as one git reference per head, on the fork itself, the way a recorded pass is:
nothing has to be created or merged to write one, and the whole set is read in a single
``ls-remote``. A record whose block has been lifted some other way is inert, since only
a labelled branch is ever read against one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from bastler.git_commands import ReferenceUpdate
from bastler.stack import Branch, Configuration, LabelWrite, Stack, resolve_ref

from bastler.maintenance_board import PullRequestField
from bastler.maintenance_git_commands import MaintenanceGitCommandRunner
from bastler.maintenance_github import ForkPullRequests

from bastler.integration_constants import ReportKey
from bastler.integration_reproduction import CLEARED_COMMENT_PREFIX, ClearedBranchReport
from bastler.integration_tips import ReadmittedBranch

if TYPE_CHECKING:
    from integration_failure import IntegrationTestFailure

BLOCK_RECORD_NAMESPACE = "refs/integration/blocked"
"""
Where a block's record lives on the fork.

Below ``refs/`` rather than under ``refs/heads/``, so a record is not a branch: nothing
lists one, clones it, or offers to check it out.
"""


class BlockStanding(StrEnum):
    """
    Whether the tree a block was measured in still exists.
    """

    STANDS = "stands"
    """
    Every head the break was measured over is still the fork's head, so the break is
    still there.
    """

    STALE = "stale"
    """
    A head has moved, or a branch has left the board, so the tree the block is about is
    gone and the branch is worth carrying again.
    """

    UNRECORDED = "unrecorded"
    """
    Nothing recorded the tree, so no build can tell when it is gone: a label applied by
    hand, or before anything wrote a record.
    """


# %% the heads a break was found between


@dataclass(frozen=True)
class MeasuredHead:
    """
    One branch's head as it was when a break was measured over it.
    """

    branch: str
    """
    The branch.
    """

    pull_request_number: int
    """
    The fork pull request that publishes it, which is what a record names it by.
    """

    commit: str
    """
    What the fork had it pointing at.
    """

    @classmethod
    def of(
        cls,
        git: MaintenanceGitCommandRunner,
        configuration: Configuration,
        branch: Branch,
    ) -> MeasuredHead:
        """
        Read a branch's head as the fork publishes it.

        :param git: The runner to read through.
        :param configuration: The resolved configuration, naming the fork remote.
        :param branch: The branch to measure.
        :return: Its head.
        """
        return cls(
            branch=branch.name,
            pull_request_number=branch.pull_request_number,
            commit=git.commit_at(resolve_ref(configuration, branch.name)),
        )

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> MeasuredHead:
        """
        :param document: One head's object, as a report's document wrote it.
        :return: The head it describes.
        """
        return cls(
            branch=document[ReportKey.BRANCH],
            pull_request_number=document[ReportKey.PULL_REQUEST_NUMBER],
            commit=document[ReportKey.COMMIT],
        )


# %% what a block is kept as


@dataclass(frozen=True)
class BlockRecord:
    """
    One head a block was measured over, kept as a reference on the fork.
    """

    blocked_pull_request_number: int
    """
    The pull request whose branch is blocked.
    """

    pull_request_number: int
    """
    The pull request whose branch's head this records - the blocked one's own, or one it
    was measured against.
    """

    commit: str
    """
    What the fork had that branch pointing at when the break was measured.
    """

    @property
    def reference(self) -> str:
        """:return: The git reference this record is kept as."""
        return (
            f"{BLOCK_RECORD_NAMESPACE}/{self.blocked_pull_request_number}/"
            f"{self.pull_request_number}"
        )

    @classmethod
    def named_by(cls, reference: str, commit: str) -> BlockRecord | None:
        """
        Read a record back out of the reference it is kept as.

        :param reference: A reference on the fork.
        :param commit: What it points at.
        :return: The record it is, or ``None`` when it is not one - a reference below
            the namespace that this cannot read is absent rather than an error, so a
            record written by something newer never stops a rebuild.
        """
        if not reference.startswith(f"{BLOCK_RECORD_NAMESPACE}/"):
            return None
        parts = reference[len(BLOCK_RECORD_NAMESPACE) + 1 :].split("/")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return None
        blocked, measured = parts
        return cls(
            blocked_pull_request_number=int(blocked),
            pull_request_number=int(measured),
            commit=commit,
        )


@dataclass(frozen=True)
class BlockRecords:
    """
    Every block this fork has recorded a tree for, and what they let a build decide.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner the fork is read and written through.
    """

    remote: str
    """
    The fork remote.
    """

    records: tuple[BlockRecord, ...]
    """
    The records the fork carries.
    """

    @classmethod
    def read(cls, git: MaintenanceGitCommandRunner, remote: str) -> BlockRecords:
        """
        Read the whole set off the fork in one call.

        :param git: The runner to read through.
        :param remote: The fork remote.
        :return: What the fork has recorded.
        """
        listed = git.run("ls-remote", remote, f"{BLOCK_RECORD_NAMESPACE}/*")
        found = (
            BlockRecord.named_by(line.split("\t")[-1].strip(), line.split("\t")[0])
            for line in listed.splitlines()
            if line.strip()
        )
        return cls(
            git=git,
            remote=remote,
            records=tuple(record for record in found if record is not None),
        )

    def about(self, blocked_pull_request_number: int) -> tuple[BlockRecord, ...]:
        """
        :param blocked_pull_request_number: The pull request whose block to ask about.
        :return: Every head its block was measured over.
        """
        return tuple(
            record
            for record in self.records
            if record.blocked_pull_request_number == blocked_pull_request_number
        )

    def standing_of(
        self,
        blocked_pull_request_number: int,
        heads_by_pull_request: Mapping[int, str],
    ) -> BlockStanding:
        """
        Say whether the tree a block was measured in still exists.

        :param blocked_pull_request_number: The pull request whose block to ask about.
        :param heads_by_pull_request: What the fork has each branch on the board pointing
            at now, by the pull request that publishes it.
        :return: Whether the block still stands.
        """
        recorded = self.about(blocked_pull_request_number)
        if not recorded:
            return BlockStanding.UNRECORDED
        unmoved = all(
            heads_by_pull_request.get(record.pull_request_number) == record.commit
            for record in recorded
        )
        return BlockStanding.STANDS if unmoved else BlockStanding.STALE

    def record(self, failure: IntegrationTestFailure) -> BlockRecords:
        """
        Write down the tree a failure was measured in, replacing whatever an earlier
        block of the same branch recorded.

        Replaced rather than added to: a head left over from an earlier measurement
        would keep the new block standing for a partner it is no longer about.

        :param failure: The localised failure being blocked for.
        :return: What the fork now holds.
        """
        written = tuple(
            BlockRecord(
                blocked_pull_request_number=failure.culprit_pull_request_number,
                pull_request_number=head.pull_request_number,
                commit=head.commit,
            )
            for head in failure.measured_over
        )
        replaced = self.about(failure.culprit_pull_request_number)
        rewritten = {record.reference for record in written}
        dropped = tuple(
            record for record in replaced if record.reference not in rewritten
        )
        self.git.write_remote_references(
            self.remote,
            [
                *(
                    ReferenceUpdate(record.reference, record.commit)
                    for record in written
                ),
                *(ReferenceUpdate(record.reference) for record in dropped),
            ],
        )
        return BlockRecords(
            git=self.git,
            remote=self.remote,
            records=(
                *(record for record in self.records if record not in replaced),
                *written,
            ),
        )

    def forget(self, blocked_pull_request_number: int) -> BlockRecords:
        """
        Drop every record of one block, once the block is lifted.

        :param blocked_pull_request_number: The pull request whose block was lifted.
        :return: What the fork now holds.
        """
        recorded = self.about(blocked_pull_request_number)
        if not recorded:
            return self
        self.git.write_remote_references(
            self.remote, [ReferenceUpdate(record.reference) for record in recorded]
        )
        return BlockRecords(
            git=self.git,
            remote=self.remote,
            records=tuple(record for record in self.records if record not in recorded),
        )

    def forget_lifted(self, stack: Stack) -> BlockRecords:
        """
        Drop the records of every block that is gone: a pull request that has lost the
        label, or has left the board.

        A block lifted by a reproduction test, or by hand, cannot drop its own record -
        neither writes to the fork - and a record with no label is read against nothing
        until the branch is labelled again, when it would answer for a tree nothing
        measured. The build is the one reader that can drop it, so it does.

        :param stack: The derived stack, naming what is on the board and what it carries.
        :return: What the fork now holds.
        """
        label = stack.configuration.integration_conflict_label
        still_blocked = {
            branch.pull_request_number
            for branch in stack.branches
            if label in branch.labels
        }
        records = self
        for number in {record.blocked_pull_request_number for record in self.records}:
            if number not in still_blocked:
                records = records.forget(number)
        return records

    def annotate(self, stack: Stack) -> Stack:
        """
        Read, for every branch the break label withholds, whether its block still
        stands, so a build can carry the ones whose tree is gone.

        :param stack: The derived stack.
        :return: The same stack, those branches carrying the standing of their block.
        """
        heads = self.git.remote_branch_heads(self.remote)
        by_pull_request = {
            branch.pull_request_number: heads[branch.name]
            for branch in stack.branches
            if branch.name in heads
        }
        label = stack.configuration.integration_conflict_label
        for branch in stack.branches:
            if label not in branch.labels:
                continue
            branch.block_standing = str(
                self.standing_of(branch.pull_request_number, by_pull_request)
            )
        return stack


# %% lifting a block the build has outgrown


def readmission_comment(branch: str, build_branch: str) -> str:
    """
    Write the comment telling a branch's owner that a build lifted its block.

    :param branch: The branch carried again.
    :param build_branch: The build whose suite is the evidence.
    :return: The comment body.
    """
    return (
        f"{CLEARED_COMMENT_PREFIX} `{branch}` was carried again in `{build_branch}` "
        f"after the tree it was blocked in had moved on, and the suite passes over that "
        f"build, so the label is removed.\n\nA block is only ever about the tree the "
        f"break was found in. Once this branch or one it was measured against moved, "
        f"that tree was gone, and a build carrying the branch again is what says "
        f"whether the break went with it."
    )


def lift_readmitted(
    readmitted: Sequence[ReadmittedBranch],
    build_branch: str,
    configuration: Configuration,
    fork: ForkPullRequests,
    records: BlockRecords,
) -> tuple[ClearedBranchReport, ...]:
    """
    Lift the block on every readmitted branch a green suite ran over.

    A branch that has lost the label since the build read the fork is left alone: its
    block is already lifted, and writing again would comment on nothing.

    :param readmitted: The branches carried again that reached the build.
    :param build_branch: The build whose suite passed.
    :param configuration: The resolved configuration, naming the label to remove.
    :param fork: The fork to label and comment on.
    :param records: What the fork has recorded, which the lifted blocks leave.
    :return: What was written where, one entry per branch unblocked.
    """
    label = configuration.integration_conflict_label
    lifted: list[ClearedBranchReport] = []
    for branch in readmitted:
        number = branch.pull_request_number
        labels = PullRequestField.LABELS.read(fork.pull_request(number), number)
        if label not in labels:
            continue
        fork.replace_labels(
            number, LabelWrite.replacing(labels, removed=[label]).labels
        )
        comment = readmission_comment(branch.branch, build_branch)
        fork.add_comment(number, comment)
        records = records.forget(number)
        lifted.append(
            ClearedBranchReport(
                branch=branch.branch,
                pull_request_number=number,
                label=label,
                comment=comment,
            )
        )
    return tuple(lifted)
