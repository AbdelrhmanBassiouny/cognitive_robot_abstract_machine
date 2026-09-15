"""
What each of the two rounds establishes.

The first asks which prefix of the merge order turned the library's tests; the second
asks which earlier tip the tip it named fails against on its own. The second exists
because a report naming nothing is a positive claim - that no single earlier tip
reproduces the failure alone - and an un-narrowed report would state it unchecked.
"""

from __future__ import annotations

from bastler.integration_localisation import (
    LocalisationStage,
    LocalisationStep,
    TipUnderSuspicion,
)
from bastler.integration_verdict import ChecksVerdict

from .integration_fixtures import FIRST_TIP, INNOCENT_TIP, SECOND_TIP, THIRD_TIP
from .localisation_fixtures import create_localisation, create_probe

# %% what the first round localises


def test_a_prefix_round_that_passes_throughout_localises_nothing():
    """
    Every prefix of the merge order passing means the candidate's red is not reproducible
    by adding the tips one at a time - a flake, or something outside the tree. Saying so
    is the answer; inventing a culprit from the last prefix would name an innocent branch.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.PASSED),
        )
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.localised_suspect is None


def test_the_first_prefix_that_fails_names_the_tip_whose_arrival_turned_it():
    """
    The tips before it were in a passing build, so the one that turned the suite is the
    one that arrived - which is the same rule the local search follows by stopping at the
    first prefix that fails.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED, number=42),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.FAILED),
        )
    )

    assert localisation.localised_suspect == TipUnderSuspicion(
        branch=SECOND_TIP, pull_request_number=42, already_included=(FIRST_TIP,)
    )


def test_a_first_prefix_that_fails_with_nothing_before_it_is_concluded_rather_than_narrowed():
    """
    There is no earlier tip to narrow against, so the failure is the tip against the base
    alone - and a narrowing round over an empty set would dispatch nothing and wait for it.
    """
    localisation = create_localisation(
        (create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.FAILED),)
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against is None


def test_a_failure_with_earlier_tips_is_narrowed_rather_than_reported_as_the_combination():
    """
    ``breaks_against`` of ``None`` is a positive claim - that no single earlier tip
    reproduces the failure alone - and the comment says so in those words. Reporting it
    without a narrowing round would state something nothing had checked.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED),
        )
    )

    assert localisation.next_step is LocalisationStep.NARROW


# %% what the second round narrows to


def test_narrowing_names_the_latest_earlier_tip_that_reproduces_the_failure():
    """
    Asked most-recent-first, the same way a merge conflict's partner is: that is the tip
    whose commits the failing one just met.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.FAILED),
            create_probe(tip=INNOCENT_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.FAILED),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(SECOND_TIP, 42, (FIRST_TIP, INNOCENT_TIP, THIRD_TIP)),
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against == THIRD_TIP


def test_a_narrowing_round_that_reproduces_nothing_is_what_makes_the_combination_claim_true():
    """
    Every pairing passing is the evidence behind "no single one of which reproduces it
    alone" - the claim the report makes when nothing is named.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.PASSED),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(SECOND_TIP, 42, (FIRST_TIP, THIRD_TIP)),
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against is None
