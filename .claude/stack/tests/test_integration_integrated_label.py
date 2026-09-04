"""
Which pull requests a build recorded itself as carrying, and the label a publication
reconciles from that record.

The record is written when a build is assembled and read when one is published, because
those are two different runs. The label is then made to say exactly what the published
build holds - which is a reconciliation over every pull request on the fork rather than
a write to the ones this build merged.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from git_commands import GitCommandResult
from stack import DefaultLabel

from maintenance_github import CheckRunRecord

from integration_candidate_commands import (
    PublishRecordedPassCommand,
    SettleCandidateCommand,
)
from integration_integrated_label import (
    INTEGRATED_RECORD_NAMESPACE,
    IntegratedLabelWrite,
    IntegratedTipRecord,
    IntegratedTipRecords,
    reconcile_integrated_label,
)
from integration_pass_record import PassRecord, RecordedSubject
from integration_report import IntegrationReport
from integration_tips import PullRequestStackTipOutcome, TipStatus

from test_maintenance import (
    A_LABEL_THIS_TOOL_NEVER_WRITES,
    RecordingPullRequests,
    make_configuration,
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    A_FORK_REMOTE,
    FIRST_TIP,
    GitAnsweringForTheFork,
    SECOND_TIP,
    THIRD_TIP,
    the_pipeline_this_checkout_carries,
)
from test_integration_verdict import a_check

A_BUILD_COMMIT = "1f0a2b3c4d5e6f708192a3b4c5d6e7f81f0a2b3c"
"""
The commit a build branch points at, which is what its records are pointed at.
"""

A_BUILD_TREE = "8c7b6a5940312e2d1c0b9a8f7e6d5c4b8c7b6a59"
"""
What that commit holds, which is what a recorded pass is keyed on.
"""

AN_EARLIER_BUILD_BRANCH = "integration-20260809-120000"
"""
A build assembled before the one under test, whose records must not answer for it.
"""

A_CARRIED_NUMBER = 11
"""
The pull request publishing the tip a build merges.
"""

A_LEFT_OUT_NUMBER = 22
"""
The pull request publishing a tip the build never attempted.
"""

A_SKIPPED_NUMBER = 33
"""
The pull request publishing a tip the build tried to merge and could not.
"""

INTEGRATED = str(DefaultLabel.INTEGRATED)
"""
The label under test, read off the member rather than spelled again here.
"""

# %% arranging a build and a fork


def an_outcome(
    branch: str, number: int, status: TipStatus
) -> PullRequestStackTipOutcome:
    """
    :param branch: The tip's branch.
    :param number: The pull request publishing it.
    :param status: What became of it.
    :return: The outcome a report carries for it.
    """
    return PullRequestStackTipOutcome(
        branch=branch, pull_request_number=number, status=status
    )


def a_report(
    tips: tuple[PullRequestStackTipOutcome, ...] = (),
    left_out: tuple[PullRequestStackTipOutcome, ...] = (),
) -> IntegrationReport:
    """
    :param tips: What became of each tip the build attempted.
    :param left_out: The tips it never attempted.
    :return: The build's report.
    """
    return IntegrationReport(
        build_branch=A_BUILD_BRANCH,
        base="main",
        tips=tips,
        tests_passed=True,
        left_out=left_out,
    )


def a_build_carrying_one_tip() -> IntegrationReport:
    """
    :return: A build that merged one tip, skipped one and never attempted a third.
    """
    return a_report(
        tips=(
            an_outcome(FIRST_TIP, A_CARRIED_NUMBER, TipStatus.MERGED),
            an_outcome(SECOND_TIP, A_SKIPPED_NUMBER, TipStatus.SKIPPED),
        ),
        left_out=(an_outcome(THIRD_TIP, A_LEFT_OUT_NUMBER, TipStatus.UNREVIEWED),),
    )


def records_on(
    git: GitAnsweringForTheFork, *written: IntegratedTipRecord
) -> IntegratedTipRecords:
    """
    :param git: The runner the fork is read through.
    :param written: The records the fork already carries.
    :return: The set, read back off that fork.
    """
    for record in written:
        git.references[record.reference] = record.commit
    return IntegratedTipRecords.read(git, A_FORK_REMOTE)


def a_fork_carrying(labels_by_number: dict[int, list[str]]) -> RecordingPullRequests:
    """
    :param labels_by_number: What each open pull request carries.
    :return: The fork stand-in, answering with exactly those pull requests.
    """
    return RecordingPullRequests(labels=dict(labels_by_number))


def reconcile(
    fork: RecordingPullRequests,
    records: IntegratedTipRecords,
) -> tuple[IntegratedLabelWrite, ...]:
    """
    :param fork: The fork to label.
    :param records: What the fork has recorded about its builds.
    :return: What the reconciliation wrote.
    """
    return reconcile_integrated_label(
        build_branch=A_BUILD_BRANCH,
        configuration=make_configuration(),
        fork=fork,
        records=records,
    )


def written_labels(fork: RecordingPullRequests) -> list[tuple[int, tuple[str, ...]]]:
    """
    :param fork: A fork that has been reconciled.
    :return: Every label set written to it, as the pull request and the set it was left
        carrying.
    """
    return [(write.pull_request_number, write.labels) for write in fork.label_writes]


# %% what a build writes down about itself


def test_a_build_records_the_pull_request_of_every_tip_it_carried():
    """
    The build's report is gone by the time anything publishes it, so what it carried has
    to survive the run that assembled it.
    """
    git = GitAnsweringForTheFork()

    IntegratedTipRecords.read(git, A_FORK_REMOTE).record(
        a_build_carrying_one_tip(), A_BUILD_COMMIT
    )

    assert git.pushes == [
        (
            "push",
            "--force",
            A_FORK_REMOTE,
            f"{A_BUILD_COMMIT}:{INTEGRATED_RECORD_NAMESPACE}"
            f"/{A_BUILD_BRANCH}/{A_CARRIED_NUMBER}",
        )
    ]


def test_a_tip_the_build_did_not_carry_is_not_recorded():
    """
    The record is what a publication turns into a label, so a tip whose commits are not
    in the finished branch must not be in it - neither one the build tried and could not
    merge, nor one it never attempted.
    """
    git = GitAnsweringForTheFork()

    records = IntegratedTipRecords.read(git, A_FORK_REMOTE).record(
        a_build_carrying_one_tip(), A_BUILD_COMMIT
    )

    assert records.carried_by(A_BUILD_BRANCH) == (A_CARRIED_NUMBER,)


def test_a_replayed_merge_counts_as_carried_the_way_the_report_already_says_it_does():
    """
    Whether a tip's commits reached the finished branch is
    :attr:`~integration_tips.TipStatusSpecification.integrated`'s answer, so this reads
    it rather than listing the statuses again.
    """
    git = GitAnsweringForTheFork()

    records = IntegratedTipRecords.read(git, A_FORK_REMOTE).record(
        a_report(tips=(an_outcome(FIRST_TIP, A_CARRIED_NUMBER, TipStatus.REPLAYED),)),
        A_BUILD_COMMIT,
    )

    assert records.carried_by(A_BUILD_BRANCH) == (A_CARRIED_NUMBER,)


def test_one_build_s_records_never_answer_for_another_s():
    """
    Several builds have records on the fork at once - the one being published, and
    whatever earlier runs left - so the build branch is what tells them apart.
    """
    records = records_on(
        GitAnsweringForTheFork(),
        IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        IntegratedTipRecord(AN_EARLIER_BUILD_BRANCH, A_LEFT_OUT_NUMBER, A_BUILD_COMMIT),
    )

    assert records.carried_by(A_BUILD_BRANCH) == (A_CARRIED_NUMBER,)


def test_a_reference_this_cannot_read_is_absent_rather_than_an_error():
    """
    A record written by something newer must never stop a rebuild, which is the rule the
    block and pass records are read by too.
    """
    assert IntegratedTipRecord.named_by("refs/heads/main", A_BUILD_COMMIT) is None
    assert (
        IntegratedTipRecord.named_by(
            f"{INTEGRATED_RECORD_NAMESPACE}/{A_BUILD_BRANCH}/not-a-number",
            A_BUILD_COMMIT,
        )
        is None
    )


def test_the_records_of_a_build_the_fork_no_longer_carries_are_dropped():
    """
    Publishing deletes the build's branch and every other ending loses it to the
    take-down, so what keeps a record is the branch it is about - and nothing has to know
    how the run that wrote it ended.
    """
    git = GitAnsweringForTheFork(heads={A_BUILD_BRANCH: A_BUILD_COMMIT})
    records = records_on(
        git,
        IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        IntegratedTipRecord(AN_EARLIER_BUILD_BRANCH, A_LEFT_OUT_NUMBER, A_BUILD_COMMIT),
    )

    kept = records.forget_dropped_builds()

    assert kept.records == (
        IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
    )
    assert git.pushes == [
        (
            "push",
            "--force",
            A_FORK_REMOTE,
            f":{INTEGRATED_RECORD_NAMESPACE}"
            f"/{AN_EARLIER_BUILD_BRANCH}/{A_LEFT_OUT_NUMBER}",
        )
    ]


def test_a_fork_with_nothing_recorded_is_not_asked_what_branches_it_has():
    """
    This runs on every publication, and there is no answer the fork could give that
    would drop a record it does not hold.
    """

    @dataclass
    class GitRefusingToBeAsked(GitAnsweringForTheFork):
        """
        A fork that fails the test rather than answering what branches it has.
        """

        def remote_branch_heads(self, remote: str) -> dict[str, str]:
            """
            :param remote: The remote asked about.
            :raises AssertionError: Always, since nothing should be asking.
            """
            raise AssertionError(
                "a set with no records asked the fork for its branches"
            )

    records = IntegratedTipRecords.read(GitRefusingToBeAsked(), A_FORK_REMOTE)

    assert records.forget_dropped_builds() is records


def test_a_fork_with_every_build_branch_still_on_it_is_not_written_to():
    """
    A push that changes nothing is one a rebuild makes four times a day.
    """
    git = GitAnsweringForTheFork(heads={A_BUILD_BRANCH: A_BUILD_COMMIT})
    records = records_on(
        git, IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT)
    )

    assert records.forget_dropped_builds().records == records.records
    assert git.pushes == []


# %% making the label say what the published build carries


def test_a_pull_request_the_published_build_carried_is_labelled():
    """
    The label exists to answer, from the pull request, whether the branch a developer
    works from holds its commits.
    """
    fork = a_fork_carrying({A_CARRIED_NUMBER: []})

    written = reconcile(
        fork,
        records_on(
            GitAnsweringForTheFork(),
            IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        ),
    )

    assert written == (
        IntegratedLabelWrite(
            pull_request_number=A_CARRIED_NUMBER, label=INTEGRATED, carried=True
        ),
    )
    assert written_labels(fork) == [(A_CARRIED_NUMBER, (INTEGRATED,))]


def test_a_pull_request_the_build_left_out_loses_the_label():
    """
    A branch the build considered and did not carry is exactly what the label has to stop
    claiming, and its tip was never even attempted - so nothing about the merge reports
    it.
    """
    fork = a_fork_carrying({A_LEFT_OUT_NUMBER: [INTEGRATED]})

    written = reconcile(
        fork,
        records_on(
            GitAnsweringForTheFork(),
            IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        ),
    )

    assert written == (
        IntegratedLabelWrite(
            pull_request_number=A_LEFT_OUT_NUMBER, label=INTEGRATED, carried=False
        ),
    )
    assert written_labels(fork) == [(A_LEFT_OUT_NUMBER, ())]


def test_a_pull_request_this_build_never_mentioned_loses_an_earlier_run_s_label():
    """
    This is the case that makes it a reconciliation rather than a write: a report names
    what its build considered, and a pull request labelled by an earlier run can be
    absent from it entirely.
    """
    fork = a_fork_carrying({A_CARRIED_NUMBER: [], A_SKIPPED_NUMBER: [INTEGRATED]})

    written = reconcile(
        fork,
        records_on(
            GitAnsweringForTheFork(),
            IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        ),
    )

    assert written == (
        IntegratedLabelWrite(
            pull_request_number=A_CARRIED_NUMBER, label=INTEGRATED, carried=True
        ),
        IntegratedLabelWrite(
            pull_request_number=A_SKIPPED_NUMBER, label=INTEGRATED, carried=False
        ),
    )


def test_a_pull_request_already_saying_the_right_thing_is_not_written_again():
    """
    A rebuild runs four times a day over a set of branches that is usually unchanged, so
    writing every pull request each time would be a write per branch per rebuild that
    changes nothing.
    """
    fork = a_fork_carrying({A_CARRIED_NUMBER: [INTEGRATED], A_LEFT_OUT_NUMBER: []})

    written = reconcile(
        fork,
        records_on(
            GitAnsweringForTheFork(),
            IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        ),
    )

    assert written == ()
    assert fork.label_writes == []


def test_the_labels_a_pull_request_carries_for_other_reasons_survive():
    """
    GitHub's label write replaces the whole set, so computing it from the intended
    change alone is what silently strips the rest.
    """
    fork = a_fork_carrying({A_CARRIED_NUMBER: [A_LABEL_THIS_TOOL_NEVER_WRITES]})

    reconcile(
        fork,
        records_on(
            GitAnsweringForTheFork(),
            IntegratedTipRecord(A_BUILD_BRANCH, A_CARRIED_NUMBER, A_BUILD_COMMIT),
        ),
    )

    assert written_labels(fork) == [
        (A_CARRIED_NUMBER, (A_LABEL_THIS_TOOL_NEVER_WRITES, INTEGRATED))
    ]


def test_a_build_nothing_recorded_leaves_every_label_where_it_is():
    """
    An unrecorded build is one assembled before this existed, and reading its silence as
    "carried nothing" would strip the label off the whole fork on the first publication
    after an upgrade.
    """
    fork = a_fork_carrying({A_CARRIED_NUMBER: [INTEGRATED]})

    assert (
        reconcile(
            fork, IntegratedTipRecords.read(GitAnsweringForTheFork(), A_FORK_REMOTE)
        )
        == ()
    )
    assert fork.label_writes == []


# %% the two publications that reach it


@dataclass
class GitPublishingABuild(GitAnsweringForTheFork):
    """
    The fork as a publication reads it: the records it keeps, plus the tree of the build
    being published, which a publication asks for the rebuild it has to carry.
    """

    tree: str = A_BUILD_TREE
    """
    What the build's commit holds, which is what a recorded pass is keyed on.
    """

    carries: Mapping[str, str] = field(
        default_factory=the_pipeline_this_checkout_carries
    )
    """
    What that tree holds of the pipeline, keyed by path.
    """

    def run(self, *arguments: str) -> str:
        """
        :param arguments: What git was asked to do.
        :return: What the fork answers, which for a publication is the build's commit or
            its tree.
        """
        if arguments[0] != "rev-parse":
            return super().run(*arguments)
        wanted = arguments[1]
        return f"{self.tree}\n" if wanted.endswith("^{tree}") else f"{A_BUILD_COMMIT}\n"

    def attempt(self, *arguments: str) -> GitCommandResult:
        """
        :param arguments: The read of one path out of the build's tree.
        :return: What that tree holds there, refusing as git does when it holds nothing.
        """
        held = self.carries.get(arguments[-1].split(":", 1)[-1])
        return GitCommandResult(
            arguments=arguments,
            exit_status=0 if held is not None else 128,
            output=held or "",
            error_output="",
        )


@dataclass(frozen=True)
class ForkAnsweringACandidate(RecordingPullRequests):
    """
    The fork a publication writes to: the pull requests it labels, plus the candidate
    whose checks decide whether it publishes at all.
    """

    checks: list[CheckRunRecord] = field(default_factory=list)
    """
    What it answers a check-run read with.
    """

    closed: list[int] = field(default_factory=list)
    """
    Every candidate closed on it.
    """

    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """
        :param reference: The commit read.
        :return: The candidate's checks.
        """
        return self.checks

    def close_pull_request(self, number: int) -> None:
        """:param number: The candidate closed."""
        self.closed.append(number)


@dataclass
class PublishingRun:
    """
    An :class:`~integration_run.IntegrationRun` stand-in for a publication, answering
    from the fork's own records rather than from a repository.
    """

    fork_answers: ForkAnsweringACandidate
    """
    The fork it hands out.
    """

    git: GitPublishingABuild = field(default_factory=GitPublishingABuild)
    """
    The runner the records are read and written through.
    """

    configuration: object = field(default_factory=make_configuration)
    """
    The resolved configuration, naming the fork remote and the label.
    """

    def fork(self) -> ForkAnsweringACandidate:
        """:return: The fork."""
        return self.fork_answers


def a_run_publishing(carried: Sequence[int]) -> PublishingRun:
    """
    :param carried: The pull requests the build being published recorded as carried.
    :return: A run whose fork has one labelled pull request the build left out and one
        unlabelled pull request it carried.
    """
    git = GitPublishingABuild()
    for number in carried:
        record = IntegratedTipRecord(A_BUILD_BRANCH, number, A_BUILD_COMMIT)
        git.references[record.reference] = record.commit
    return PublishingRun(
        fork_answers=ForkAnsweringACandidate(
            labels={A_CARRIED_NUMBER: [], A_LEFT_OUT_NUMBER: [INTEGRATED]},
            checks=[a_check()],
        ),
        git=git,
    )


def test_settling_a_green_candidate_labels_what_its_build_carried():
    """
    Settling is what moves the pointer after a matrix has judged a build, so it is one
    of the two moments the label can be made true.
    """
    run = a_run_publishing(carried=[A_CARRIED_NUMBER])

    SettleCandidateCommand().run(
        run,
        argparse.Namespace(
            candidate=41, build=A_BUILD_BRANCH, head=A_BUILD_COMMIT, json=True
        ),
    )

    assert written_labels(run.fork_answers) == [
        (A_CARRIED_NUMBER, (INTEGRATED,)),
        (A_LEFT_OUT_NUMBER, ()),
    ]


def test_publishing_a_recorded_pass_labels_what_its_build_carried():
    """
    This is what publishes on the ordinary day, when nothing has moved and no candidate is
    opened at all - so a label written only by the judged path would be stale on every
    such rebuild.
    """
    run = a_run_publishing(carried=[A_CARRIED_NUMBER])
    passed = PassRecord(
        subject=RecordedSubject.BUILD_TREE, key=A_BUILD_TREE, recorded_on=date.today()
    )
    run.git.references[passed.reference] = A_BUILD_COMMIT

    PublishRecordedPassCommand().run(
        run, argparse.Namespace(build=A_BUILD_BRANCH, json=True)
    )

    assert written_labels(run.fork_answers) == [
        (A_CARRIED_NUMBER, (INTEGRATED,)),
        (A_LEFT_OUT_NUMBER, ()),
    ]


def test_a_build_refused_publication_labels_nothing():
    """
    The label says the branch a developer works from holds these commits, so a build the
    pointer was never moved onto must not claim it - and a build carrying no rebuild of
    its own is exactly one publication refuses.
    """
    run = a_run_publishing(carried=[A_CARRIED_NUMBER])
    run.git.carries = {}

    SettleCandidateCommand().run(
        run,
        argparse.Namespace(
            candidate=41, build=A_BUILD_BRANCH, head=A_BUILD_COMMIT, json=True
        ),
    )

    assert run.fork_answers.label_writes == []
