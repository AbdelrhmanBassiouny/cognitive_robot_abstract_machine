"""
Assembling and publishing the trees a round asks about.

Each probe has to be a tree a run can check out, and they are exactly the prefixes the
build itself went through - so what the search answers describes the build that failed
rather than some other ordering of it. Run against real git in a scratch fork, because
what is being checked is what the published trees hold.
"""

from __future__ import annotations

from bastler.integration_probes import ProbeWorkflowInput, dispatch
from bastler.workflow_document import WorkflowFile

from .test_maintenance import (
    ForkCheckout,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
)

from .integration_fixtures import FIRST_TIP, SECOND_TIP, THIRD_TIP
from .localisation_fixtures import (
    A_LIBRARY,
    RecordingWorkflowRuns,
    THE_PIPELINE_REFERENCE,
    assemble,
    create_probe,
    files_in,
    published,
    three_tips,
)


def test_a_prefix_round_publishes_the_merge_order_one_tip_at_a_time(
    fork_checkout: ForkCheckout,
):
    """
    Each probe has to be a tree a run can check out, and the trees are exactly the
    prefixes the build itself went through - so the answer describes the build that
    failed rather than some other ordering of it.
    """
    pull_requests = three_tips(fork_checkout)

    probes = assemble(fork_checkout, pull_requests).prefixes()
    fork_checkout.run_git("fetch", "--quiet", "origin")

    assert [probe.tip for probe in probes] == [FIRST_TIP, SECOND_TIP, THIRD_TIP]
    assert files_in(fork_checkout, probes[0].branch) == {"a-file", f"{FIRST_TIP}-file"}
    assert files_in(fork_checkout, probes[2].branch) == {
        "a-file",
        f"{FIRST_TIP}-file",
        f"{SECOND_TIP}-file",
        f"{THIRD_TIP}-file",
    }


def test_a_probe_carries_the_pull_request_of_the_tip_it_is_about(
    fork_checkout: ForkCheckout,
):
    """
    The tip a round localises is reported to its own pull request, and the number is
    read here rather than looked up again later against a board that has since moved.
    """
    pull_requests = three_tips(fork_checkout)

    probes = assemble(fork_checkout, pull_requests).prefixes()

    assert [probe.pull_request_number for probe in probes] == [1, 2, 3]


def test_a_narrowing_round_pairs_each_earlier_tip_with_the_one_under_suspicion(
    fork_checkout: ForkCheckout,
):
    """
    Which earlier tip the suspect fails against alone is a different question from which
    prefix turned the tests, and only a tree holding just those two answers it.
    """
    pull_requests = three_tips(fork_checkout)
    assembly = assemble(fork_checkout, pull_requests)

    probes = assembly.pairings(THIRD_TIP, (FIRST_TIP, SECOND_TIP))
    fork_checkout.run_git("fetch", "--quiet", "origin")

    assert [probe.tip for probe in probes] == [FIRST_TIP, SECOND_TIP]
    assert files_in(fork_checkout, probes[0].branch) == {
        "a-file",
        f"{FIRST_TIP}-file",
        f"{THIRD_TIP}-file",
    }


def test_every_probe_of_a_round_is_dispatched_at_once(fork_checkout: ForkCheckout):
    """
    The probes are independent, so dispatching them together costs one run's wall clock
    for the whole round where asking one at a time costs one per tip - which is what
    makes a linear scan the right shape rather than a bisection.
    """
    fork = RecordingWorkflowRuns()
    probes = (create_probe(tip=FIRST_TIP), create_probe(tip=SECOND_TIP))

    dispatch(fork, THE_PIPELINE_REFERENCE, A_LIBRARY, probes)

    assert [dispatched["inputs"] for dispatched in fork.dispatched] == [
        {
            ProbeWorkflowInput.BUILD: probes[0].branch,
            ProbeWorkflowInput.LIBRARY: str(A_LIBRARY),
        },
        {
            ProbeWorkflowInput.BUILD: probes[1].branch,
            ProbeWorkflowInput.LIBRARY: str(A_LIBRARY),
        },
    ]


def test_a_probe_is_dispatched_on_the_reference_carrying_the_pipeline():
    """
    A dispatch runs the workflow file the dispatched reference carries, and no prefix
    carries one - the empty prefix is bare upstream ``main``. Dispatching on the tree
    under test would only ever start working once this had landed upstream.
    """
    fork = RecordingWorkflowRuns()

    dispatch(fork, THE_PIPELINE_REFERENCE, A_LIBRARY, (create_probe(),))

    assert fork.dispatched[0]["reference"] == THE_PIPELINE_REFERENCE
    assert fork.dispatched[0]["workflow"] == str(WorkflowFile.INTEGRATION_PROBE)


def test_the_trees_a_search_published_are_taken_down_when_it_concludes(
    fork_checkout: ForkCheckout,
):
    """
    A localisation runs whenever a candidate goes red, so trees left behind accumulate -
    and once the search has answered there is nothing in one to read: a run outlives the
    branch it ran on.
    """
    pull_requests = three_tips(fork_checkout)
    assembly = assemble(fork_checkout, pull_requests)
    probes = assembly.prefixes()
    fork_checkout.run_git("fetch", "--quiet", "--prune", "origin")

    assembly.take_down(probes)
    fork_checkout.run_git("fetch", "--quiet", "--prune", "origin")

    assert published(fork_checkout, probes) == []
