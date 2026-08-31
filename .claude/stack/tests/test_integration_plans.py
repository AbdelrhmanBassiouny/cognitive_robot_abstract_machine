"""
Carrying only one plan's branches, and what a build says about the ones it cannot place.

The full build is what a developer works from and is unchanged by any of this. What a
plan filter adds is a way to ask, when the full build is red, whether some one plan's
branches hold together on their own - the same build over fewer tips, judged the same
way.
"""

from __future__ import annotations

import argparse

import pytest

from integration_constants import POINTER_BRANCH
from integration_plans import BranchPlanIndexUnavailable, PlanFilter
from integration_candidate_commands import OpenCandidateCommand
from integration_verdict import CandidateTitle, candidate_description
from maintenance_board import BoardExport
from integration_selection import select_for_build, tips_of
from integration_tips import TipStatus

from integration_fixtures import (
    RunAgainstAGivenFork,
    create_branch_object,
    create_stack_object,
)
from test_integration_verdict import A_BUILD_BRANCH, RecordingCandidates
from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    an_api_record,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

A_PLAN = "rdr-refactor"
"""
The plan a filtered build is asked for.
"""

ANOTHER = "workflow-unification"
"""
A second plan, whose branches a build asked for the first must leave out.
"""


def a_filter(*wanted: str, index: dict[str, str] | None = None) -> PlanFilter:
    """
    :param wanted: The plans asked for.
    :param index: Which plan each branch belongs to.
    :return: The filter, over an index given here rather than read off a branch.
    """
    return PlanFilter(wanted=frozenset(wanted), plan_of=index or {})


# %% which branches a filtered build carries


def test_a_build_asked_for_one_plan_carries_only_that_plan_s_branches():
    """
    The whole affordance: when the full build is red, whether one plan holds together on
    its own is a question about a build over fewer tips rather than a topology of its
    own.
    """
    mine = create_branch_object("mine", 1)
    theirs = create_branch_object("theirs", 2)
    plans = a_filter(A_PLAN, index={mine.name: A_PLAN, theirs.name: ANOTHER})

    carried = tips_of(create_stack_object([mine, theirs]), plans)

    assert [tip.name for tip in carried] == [mine.name]


def test_a_branch_of_another_plan_is_named_rather_than_merely_absent():
    """
    A build that integrates two branches out of nineteen and says so only by omission
    reads as having covered everything, which is why every other rule reports what it
    left out too.
    """
    theirs = create_branch_object("theirs", 2)
    plans = a_filter(A_PLAN, index={theirs.name: ANOTHER})

    left_out = select_for_build(create_stack_object([theirs]), plans).left_out

    assert [(entry.branch, entry.status) for entry in left_out] == [
        (theirs.name, TipStatus.ANOTHER_PLAN)
    ]


def test_a_branch_the_index_names_no_plan_for_is_reported_as_such():
    """
    Told apart from a branch of another plan because the two mean different things to a
    reader: one is a filter working, the other is a branch nothing can place, which is a
    gap in the index rather than an answer about the build.
    """
    unplaced = create_branch_object("unplaced", 3)
    plans = a_filter(A_PLAN)

    left_out = select_for_build(create_stack_object([unplaced]), plans).left_out

    assert [entry.status for entry in left_out] == [TipStatus.NO_PLAN_RECORDED]


def test_a_build_that_named_no_plan_carries_what_it_always_did():
    """
    The unfiltered build is what a developer works from, and this is a triage affordance
    rather than a change to it.
    """
    mine = create_branch_object("mine", 1)
    theirs = create_branch_object("theirs", 2)

    carried = tips_of(create_stack_object([mine, theirs]))

    assert [tip.name for tip in carried] == [mine.name, theirs.name]


# %% naming the plans


@pytest.mark.parametrize(
    "named", [[A_PLAN, ANOTHER], [f"{A_PLAN},{ANOTHER}"], [f" {A_PLAN} ,{ANOTHER}"]]
)
def test_several_plans_are_asked_for_either_way_round(named: list[str]):
    """
    Repeated and comma-separated both fall out of one argument, and a caller that had to
    remember which is one that gets it wrong.
    """
    assert PlanFilter.over(named).wanted == frozenset({A_PLAN, ANOTHER})


def test_naming_no_plan_never_reads_the_index():
    """
    An unfiltered build must not depend on the personal-notes branch being reachable,
    which is a thing a rebuild's own credential is not obliged to be able to read.
    """
    unfiltered = PlanFilter.over([])

    assert not unfiltered.is_filtering
    assert unfiltered.plan_of == {}


def test_an_index_that_cannot_be_read_refuses_rather_than_filtering_on_nothing(
    monkeypatch,
):
    """
    Every branch would read as belonging to no plan, which empties the build while saying
    the filter worked - a wrong answer where a refusal is the only honest one.
    """
    monkeypatch.setattr(PlanFilter, "_read_the_index", staticmethod(lambda: _refuse()))

    with pytest.raises(BranchPlanIndexUnavailable):
        PlanFilter.over([A_PLAN])


def _refuse() -> dict[str, str]:
    """:raises BranchPlanIndexUnavailable: Always, standing in for a fetch that failed."""
    raise BranchPlanIndexUnavailable("no such remote")


# %% how a filtered build is judged


def open_a_candidate(
    checkout: ForkCheckout, build_branch: str, *plans: str
) -> RecordingCandidates:
    """
    :param checkout: The checkout holding the build.
    :param build_branch: The build to have judged.
    :param plans: The plans it was asked to carry.
    :return: The fork it was opened on, recording what was opened.
    """
    fork = RecordingCandidates()
    OpenCandidateCommand().run(
        RunAgainstAGivenFork(
            configuration=make_configuration(), git=checkout.git, given=fork
        ),
        argparse.Namespace(build=build_branch, plan=list(plans), json=True),
    )
    return fork


def test_a_filtered_build_s_candidate_is_never_the_one_the_rebuild_settles(
    fork_checkout: ForkCheckout,
):
    """
    A one-plan build is deliberately not the whole of what is in flight, so publishing
    it would drop everything else.

    Its title is what says so, since both kinds are now opened against the same base and
    the base can no longer tell them apart.
    """
    fork_checkout.run_git("checkout", "--quiet", "-b", A_BUILD_BRANCH)
    fork_checkout.commit("assembled", "one plan's branches\n")

    opened = open_a_candidate(fork_checkout, A_BUILD_BRANCH, A_PLAN).opened[0]

    assert CandidateTitle.read(opened.title) == CandidateTitle(
        A_BUILD_BRANCH, (A_PLAN,)
    )


def test_an_unfiltered_build_s_candidate_is_the_one_the_rebuild_settles(
    fork_checkout: ForkCheckout,
):
    """
    The other half of the same rule, and the one the whole cycle rests on: the build
    carrying everything in flight is the only one a later run may publish from.
    """
    fork_checkout.run_git("checkout", "--quiet", "-b", A_BUILD_BRANCH)
    fork_checkout.commit("assembled", "everything in flight\n")

    opened = open_a_candidate(fork_checkout, A_BUILD_BRANCH).opened[0]

    assert CandidateTitle.read(opened.title).judges_everything_in_flight


@pytest.mark.parametrize("plans", [(), (A_PLAN,)])
def test_every_candidate_is_opened_against_the_base_its_build_was_assembled_over(
    fork_checkout: ForkCheckout, plans: tuple[str, ...]
):
    """
    A build is the upstream base plus the merged tips, so it merges with that base by.

    construction. Opened against the branch it would replace - itself an older build of
    the same branches - the two conflict, GitHub computes no merge reference, and the
    ``pull_request`` run that would check it out is never created at all.
    """
    fork_checkout.run_git("checkout", "--quiet", "-b", A_BUILD_BRANCH)
    fork_checkout.commit("assembled", "something to judge\n")

    opened = open_a_candidate(fork_checkout, A_BUILD_BRANCH, *plans).opened[0]

    assert opened.base == UPSTREAM_BASE
    assert opened.base != POINTER_BRANCH


def test_a_filtered_build_s_candidate_says_it_is_never_published():
    """
    It sits among ordinary pull requests, based where they are based, so what it is has
    to be readable without being inferred.
    """
    described = candidate_description(A_BUILD_BRANCH, UPSTREAM_BASE, plans=(A_PLAN,))

    assert A_PLAN in described
    assert "never published" in described.lower()


@pytest.mark.parametrize("plans", [(), (A_PLAN,)])
def test_a_candidate_based_where_ordinary_work_is_based_is_still_kept_off_the_board(
    plans: tuple[str, ...],
):
    """
    Every candidate is based where every ordinary branch is based now, so nothing but
    its.

    title holds it off the one export both a build and a maintenance pass derive their
    work from - and read as work in flight it would be merged into the next build and
    restacked onto the branch it exists to replace.
    """
    export = BoardExport.from_api_records(
        [
            an_api_record(
                number=1,
                title=str(CandidateTitle(A_BUILD_BRANCH, plans)),
                head=A_BUILD_BRANCH,
                base=UPSTREAM_BASE,
            )
        ]
    )

    assert export.pull_requests == ()
