"""
What this fork has already seen pass, and what a rebuild does with it.

A rebuild runs four times a day over a set of branches that is usually unchanged and
spends its matrix re-establishing what the previous one established. These are written
against a real scratch fork, because the record *is* a set of git references: what has
to hold is that writing one publishes something, that reading finds it, and that a
record nothing can read is absent rather than fatal.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pytest

from integration_candidate_commands import (
    PublishRecordedPassCommand,
    SettleCandidateCommand,
)
from integration_constants import POINTER_BRANCH
from integration_exit_codes import IntegrationExitCode
from integration_fixtures import (
    RunAgainstAGivenFork,
    the_pipeline_this_checkout_carries,
    write_into,
)
from integration_pass_record import (
    RECORD_NAMESPACE,
    RETENTION,
    PassRecord,
    PassedChecks,
    RecordedSubject,
)

from test_integration_verdict import RecordingCandidates
from test_maintenance import (
    ForkCheckout,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

A_DAY = date(2026, 8, 30)
"""
The day a record is written, fixed so nothing here depends on the clock.
"""

A_FORK_REMOTE = "origin"
"""
The remote the records live on.
"""

A_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
"""
A tree an assembled build had, which is what a build is recorded under.
"""


def records_on(checkout: ForkCheckout, today: date = A_DAY) -> PassedChecks:
    """:param checkout: The fork to read.
    :param today: The day to judge currency by.
    :return: What that fork has recorded."""
    return PassedChecks.read(checkout.git, A_FORK_REMOTE, today=today)


# %% what a record is kept as


def test_a_record_is_not_a_branch(fork_checkout: ForkCheckout):
    """
    A record per tree accumulates fast, and one kept under ``refs/heads/`` would be
    listed, cloned and offered for checkout as though somebody meant to work on it.
    """
    records_on(fork_checkout).record(
        fork_checkout.git,
        A_FORK_REMOTE,
        RecordedSubject.BUILD_TREE,
        A_TREE,
        fork_checkout.run_git("rev-parse", "HEAD"),
    )

    published = fork_checkout.run_git("ls-remote", A_FORK_REMOTE)

    assert RECORD_NAMESPACE in published
    assert f"refs/heads/{RECORD_NAMESPACE}" not in published


def test_a_recorded_pass_is_found_again(fork_checkout: ForkCheckout):
    """
    The whole point: the next rebuild asks about the same tree and is answered without
    running anything.
    """
    records_on(fork_checkout).record(
        fork_checkout.git,
        A_FORK_REMOTE,
        RecordedSubject.BUILD_TREE,
        A_TREE,
        fork_checkout.run_git("rev-parse", "HEAD"),
    )

    assert records_on(fork_checkout).holds(RecordedSubject.BUILD_TREE, A_TREE)


def test_a_fork_that_has_recorded_nothing_answers_that_nothing_passed(
    fork_checkout: ForkCheckout,
):
    """
    A missing record has to degrade to checking it again rather than to assuming it
    passed, and an empty fork is the first case of that.
    """
    assert not records_on(fork_checkout).holds(RecordedSubject.BUILD_TREE, A_TREE)


def test_the_two_kinds_of_record_do_not_answer_for_each_other(
    fork_checkout: ForkCheckout,
):
    """
    A build's tree and a branch's head are both hashes, so a record keyed on the hash
    alone would let a branch that passed publish a build nothing had checked.
    """
    records_on(fork_checkout).record(
        fork_checkout.git,
        A_FORK_REMOTE,
        RecordedSubject.BRANCH_HEAD,
        A_TREE,
        fork_checkout.run_git("rev-parse", "HEAD"),
    )
    recorded = records_on(fork_checkout)

    assert recorded.holds(RecordedSubject.BRANCH_HEAD, A_TREE)
    assert not recorded.holds(RecordedSubject.BUILD_TREE, A_TREE)


# %% a record that has stopped answering


def test_a_record_older_than_the_retention_window_is_checked_again(
    fork_checkout: ForkCheckout,
):
    """
    Nothing about the content decays - a changed tree is a different key - but the image
    the matrix runs in is rebuilt from the upstream base, so a pass eventually answers
    for an environment that has moved.
    """
    records_on(fork_checkout).record(
        fork_checkout.git,
        A_FORK_REMOTE,
        RecordedSubject.BUILD_TREE,
        A_TREE,
        fork_checkout.run_git("rev-parse", "HEAD"),
    )
    much_later = A_DAY + RETENTION + timedelta(days=1)

    assert not records_on(fork_checkout, today=much_later).holds(
        RecordedSubject.BUILD_TREE, A_TREE
    )


def test_writing_a_record_drops_the_ones_that_have_expired(
    fork_checkout: ForkCheckout,
):
    """
    A record per tree per branch head accumulates for as long as the fork exists, and a
    pruning nothing performs is a namespace nobody can read.
    """
    head = fork_checkout.run_git("rev-parse", "HEAD")
    records_on(fork_checkout).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, A_TREE, head
    )
    much_later = A_DAY + RETENTION + timedelta(days=1)

    remaining = records_on(fork_checkout, today=much_later).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BRANCH_HEAD, head, head
    )

    assert records_on(fork_checkout, today=much_later).records == remaining.records
    assert [record.subject for record in remaining.records] == [
        RecordedSubject.BRANCH_HEAD
    ]


def test_a_second_record_in_one_run_does_not_re_delete_what_the_first_dropped(
    fork_checkout: ForkCheckout,
):
    """
    Git refuses a push deleting a reference that is not there, so a set that kept
    reporting what it had already pruned would fail the run on its second write.
    """
    head = fork_checkout.run_git("rev-parse", "HEAD")
    records_on(fork_checkout).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, A_TREE, head
    )
    much_later = A_DAY + RETENTION + timedelta(days=1)

    after_one = records_on(fork_checkout, today=much_later).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BRANCH_HEAD, head, head
    )
    after_two = after_one.record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, head, head
    )

    assert after_two.holds(RecordedSubject.BUILD_TREE, head)


def test_a_reference_this_cannot_read_is_absent_rather_than_fatal(
    fork_checkout: ForkCheckout,
):
    """
    The namespace is on a repository something newer may also write to, and a rebuild
    that raised on a record it did not recognise would stop over a thing it was free to
    ignore.
    """
    head = fork_checkout.run_git("rev-parse", "HEAD")
    fork_checkout.run_git(
        "push", A_FORK_REMOTE, f"{head}:{RECORD_NAMESPACE}/something/else/entirely/here"
    )

    assert records_on(fork_checkout).records == ()


@pytest.mark.parametrize(
    "reference",
    [
        "refs/heads/main",
        f"{RECORD_NAMESPACE}/build-tree/notadate/{A_TREE}",
        f"{RECORD_NAMESPACE}/something-else/20260830/{A_TREE}",
    ],
)
def test_a_reference_that_is_not_a_record_reads_as_none(reference: str):
    """
    Read one at a time, so which shapes are records is decided in one place rather than
    by whatever the fork happens to be carrying.
    """
    assert PassRecord.named_by(reference) is None


# %% a fork that will not accept a record


def refuse_writes_into_the_record_namespace(checkout: ForkCheckout) -> None:
    """
    Make the fork reject every push into the record namespace, the way a credential
    without the rights to write there is rejected.

    :param checkout: The checkout whose fork to make refuse.
    """
    hook = checkout.fork_path / "hooks" / "pre-receive"
    hook.write_text(
        f"#!/bin/sh\nwhile read -r _ _ reference; do\n"
        f'  case "$reference" in {RECORD_NAMESPACE}/*) exit 1 ;; esac\n'
        f"done\nexit 0\n"
    )
    hook.chmod(0o755)


def test_a_record_the_fork_refuses_leaves_the_run_going(fork_checkout: ForkCheckout):
    """
    A record is an optimisation, so a credential that may read the fork but not write
    this namespace has to cost the reuse rather than the whole rebuild.
    """
    refuse_writes_into_the_record_namespace(fork_checkout)
    head = fork_checkout.run_git("rev-parse", "HEAD")

    after = records_on(fork_checkout).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, A_TREE, head
    )

    assert after.records == ()


def test_a_record_the_fork_refuses_is_not_claimed_to_hold(fork_checkout: ForkCheckout):
    """
    Claiming a refused write would let the next question be answered from a record the
    fork never accepted, which is the one way a pass record can say something false.
    """
    refuse_writes_into_the_record_namespace(fork_checkout)
    head = fork_checkout.run_git("rev-parse", "HEAD")

    after = records_on(fork_checkout).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, A_TREE, head
    )

    assert not after.holds(RecordedSubject.BUILD_TREE, A_TREE)
    assert not records_on(fork_checkout).holds(RecordedSubject.BUILD_TREE, A_TREE)


def test_a_fork_that_refuses_a_record_is_said_so_on_standard_error(
    fork_checkout: ForkCheckout, capsys: pytest.CaptureFixture[str]
):
    """
    Silently losing the reuse would leave a rebuild paying for a full matrix every run
    with nothing saying why.
    """
    refuse_writes_into_the_record_namespace(fork_checkout)
    head = fork_checkout.run_git("rev-parse", "HEAD")

    records_on(fork_checkout).record(
        fork_checkout.git, A_FORK_REMOTE, RecordedSubject.BUILD_TREE, A_TREE, head
    )

    assert RECORD_NAMESPACE in capsys.readouterr().err


# %% publishing a build the record already answers for


def publish_recorded_pass(checkout: ForkCheckout, build_branch: str):
    """
    :param checkout: The checkout to run in.
    :param build_branch: The build to publish if it is one already seen to pass.
    :return: The status the command exited with.
    """
    return PublishRecordedPassCommand().run(
        RunAgainstAGivenFork(configuration=make_configuration(), git=checkout.git),
        argparse.Namespace(build=build_branch, json=True),
    )


def a_build_branch(checkout: ForkCheckout, name: str) -> str:
    """:param checkout: The checkout to build in.
    :param name: The branch to assemble onto.
    :return: The tree that branch holds."""
    checkout.run_git("checkout", "--quiet", "-b", name)
    write_into(checkout.project_root, the_pipeline_this_checkout_carries())
    checkout.run_git("add", "--all")
    checkout.commit("assembled", "what the build merged\n")
    return checkout.run_git("rev-parse", f"{name}^{{tree}}")


def test_a_build_whose_tree_is_recorded_moves_the_branch_without_being_judged(
    fork_checkout: ForkCheckout,
):
    """
    A rebuild assembles the same branches over the same base four times a day, and each
    assembly is a new commit holding the same tree - so keying on the commit would answer
    "never seen before" about a build byte-for-byte identical to the published one.
    """
    build_branch = "integration-20260830-050000"
    tree = a_build_branch(fork_checkout, build_branch)
    records_on(fork_checkout, today=date.today()).record(
        fork_checkout.git,
        A_FORK_REMOTE,
        RecordedSubject.BUILD_TREE,
        tree,
        fork_checkout.run_git("rev-parse", build_branch),
    )

    status = publish_recorded_pass(fork_checkout, build_branch)

    assert status is IntegrationExitCode.SUCCESS
    assert fork_checkout.commit_on_the_fork(POINTER_BRANCH) == (
        fork_checkout.run_git("rev-parse", build_branch)
    )


def test_a_build_nothing_has_recorded_is_left_to_be_judged(
    fork_checkout: ForkCheckout,
):
    """
    A missing record has to degrade to checking it again rather than to publishing
    something no matrix ever looked at.
    """
    build_branch = "integration-20260830-050000"
    a_build_branch(fork_checkout, build_branch)

    status = publish_recorded_pass(fork_checkout, build_branch)

    assert status is IntegrationExitCode.NO_RECORDED_PASS
    assert fork_checkout.run_git("ls-remote", A_FORK_REMOTE, POINTER_BRANCH) == ""


def test_a_candidate_that_passed_records_the_tree_it_passed_over(
    fork_checkout: ForkCheckout,
):
    """
    The reading that establishes a pass is the only place that knows one happened, and a
    record nothing writes is one nothing ever reuses - which is the whole of what a
    rebuild spends its four runs a day re-establishing.
    """
    build_branch = "integration-20260830-050000"
    tree = a_build_branch(fork_checkout, build_branch)
    head = fork_checkout.run_git("rev-parse", build_branch)
    fork_checkout.run_git(
        "push", "--quiet", A_FORK_REMOTE, f"{build_branch}:{build_branch}"
    )

    SettleCandidateCommand().run(
        RunAgainstAGivenFork(
            configuration=make_configuration(),
            git=fork_checkout.git,
            given=RecordingCandidates(
                checks=[
                    {
                        "name": "test_each_lib",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            ),
        ),
        argparse.Namespace(candidate=213, build=build_branch, head=head, json=True),
    )

    assert records_on(fork_checkout, today=date.today()).holds(
        RecordedSubject.BUILD_TREE, tree
    )
