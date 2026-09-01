"""
What one probe's run says, and what survives the call that wrote it.

Every probe of one localisation is dispatched on the same reference, so a reader that
took the newest run would answer every probe with whichever finished last - and the
waiting lives with the caller, so a search is picked up by a later invocation sharing
nothing with the one that started it but its document.
"""

from __future__ import annotations

from integration_localisation import (
    Localisation,
    LocalisationStage,
    LocalisationStep,
    TipUnderSuspicion,
)
from integration_probes import verdict_of
from integration_verdict import ChecksVerdict

from integration_fixtures import FIRST_TIP, SECOND_TIP, THIRD_TIP
from localisation_fixtures import a_run, create_localisation, create_probe

# %% what one probe's run says


def test_a_probe_whose_run_has_not_appeared_yet_is_waited_for():
    """
    A dispatch is accepted before its run object exists, so no run at all is the
    ordinary first answer rather than a sign anything is wrong.

    What catches a dispatch that never produced one is the caller's own timeout.
    """
    localisation = create_localisation((create_probe(verdict=ChecksVerdict.ABSENT),))

    assert localisation.next_step is LocalisationStep.WAIT


def test_one_probe_still_running_holds_the_whole_round():
    """
    A round's answer is which of its probes failed, and reading that from a partial set
    would name whichever finished first rather than whichever is earliest in merge
    order.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.RUNNING),
        )
    )

    assert localisation.next_step is LocalisationStep.WAIT


# %% reading a probe's run back


def test_a_probe_reads_the_run_named_after_its_own_tree():
    """
    Every probe of one localisation is dispatched on the same reference, so a reader
    that took the newest run, or the one on that reference, would answer every probe
    with whichever finished last.
    """
    probe = create_probe(tip=SECOND_TIP)
    other = create_probe(tip=FIRST_TIP)
    runs = [a_run(other.branch, conclusion="failure"), a_run(probe.branch)]

    assert verdict_of(runs, probe.branch) is ChecksVerdict.PASSED
    assert verdict_of(runs, other.branch) is ChecksVerdict.FAILED


def test_a_probe_with_no_run_of_its_own_yet_reports_none_reported():
    """
    A dispatch is accepted before its run object exists, so this is the ordinary first
    answer - told apart from a run in progress because it is also what a dispatch that
    never started one looks like.
    """
    assert verdict_of([], "integration-probe-nothing") is ChecksVerdict.ABSENT


# %% the document a repeatable call reads and rewrites


def test_the_search_survives_the_call_that_wrote_it():
    """
    The waiting lives with the caller, so a search is picked up by a later invocation
    that shares nothing with the one that started it but this document.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED, number=42),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(THIRD_TIP, 9, (FIRST_TIP,)),
    )

    assert Localisation.from_json(localisation.to_json()) == localisation
