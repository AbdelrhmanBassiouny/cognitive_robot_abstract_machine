"""
Carrying only the tooling changes, and what a build says about the branches it drops.

The full build is what a developer works from and is unchanged by any of this. What
asking for the tooling adds is a way to rebuild this workflow's own machinery out of the
branches in flight without the software those branches sit beside - the same build over
fewer tips, judged the same way.
"""

from __future__ import annotations

import argparse

from stack import PullRequest

from integration_build_commands import BuildCommand
from integration_selection import select_for_build, tips_of
from integration_tips import TipStatus
from integration_tooling import ToolingFilter

from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    FIRST_TIP,
    SECOND_TIP,
    build,
    create_branch_object,
    create_stack_object,
)

TOOLING_LABEL = make_configuration().tooling_label
"""
The label a tip must carry to reach a build asked for the tooling, read from the
configuration that names it.
"""

ANOTHER_LABEL = "documentation"
"""
A label that says nothing about whether a branch changes the tooling, so a filter
matching on any label at all is caught.
"""


def a_filter() -> ToolingFilter:
    """
    :return: The filter a build asked for the tooling carries.
    """
    return ToolingFilter.over(make_configuration(), only_the_tooling=True)


# %% which branches a build asked for the tooling carries


def test_a_build_asked_for_the_tooling_carries_only_the_labelled_tips():
    """
    The whole affordance: the machinery this workflow runs on can be rebuilt from the
    branches in flight without the software they sit beside coming along.
    """
    tooling = create_branch_object("tooling", 1, labels=[TOOLING_LABEL])
    software = create_branch_object("software", 2, labels=[ANOTHER_LABEL])

    carried = tips_of(create_stack_object([tooling, software]), a_filter())

    assert [tip.name for tip in carried] == [tooling.name]


def test_a_branch_that_is_not_a_tooling_change_is_named_rather_than_merely_absent():
    """
    A build that integrates two branches out of nineteen and says so only by omission
    reads as having covered everything, which is why every other rule reports what it
    left out too.
    """
    software = create_branch_object("software", 2)

    left_out = select_for_build(create_stack_object([software]), a_filter()).left_out

    assert [(entry.branch, entry.status) for entry in left_out] == [
        (software.name, TipStatus.NOT_A_TOOLING_CHANGE)
    ]


def test_a_tooling_branch_standing_on_one_that_is_not_is_left_out_under_it():
    """
    A tip contains its own stack, so carrying it would bring the software beneath it in
    under a tooling branch's name - which is the one thing asking for the tooling rules
    out.
    """
    software = create_branch_object("software", 1)
    tooling = create_branch_object(
        "tooling", 2, parent=software.name, labels=[TOOLING_LABEL]
    )

    left_out = select_for_build(
        create_stack_object([software, tooling]), a_filter()
    ).left_out

    assert [
        (entry.branch, entry.status, entry.attributed_to) for entry in left_out
    ] == [
        (software.name, TipStatus.NOT_A_TOOLING_CHANGE, None),
        (tooling.name, TipStatus.NOT_A_TOOLING_CHANGE, software.name),
    ]


def test_a_build_that_did_not_ask_for_the_tooling_carries_what_it_always_did():
    """
    The unfiltered build is what a developer works from, and this is an affordance
    beside it rather than a change to it.
    """
    tooling = create_branch_object("tooling", 1, labels=[TOOLING_LABEL])
    software = create_branch_object("software", 2)

    carried = tips_of(create_stack_object([tooling, software]))

    assert [tip.name for tip in carried] == [tooling.name, software.name]


# %% asking for the tooling


def test_the_label_a_filtered_build_reads_is_the_one_the_configuration_names():
    """
    Named in one place, so a fork that calls it something else is filtered by its own
    label rather than by this tooling's idea of what it should be called.
    """
    configuration = make_configuration()

    filtering = ToolingFilter.over(configuration, only_the_tooling=True)

    assert filtering.label == configuration.tooling_label
    assert filtering.is_filtering


def test_a_build_that_did_not_ask_for_the_tooling_never_filters():
    """
    Every branch would read as changing something else, which empties the build while
    saying the filter worked.
    """
    unfiltered = ToolingFilter.over(make_configuration(), only_the_tooling=False)

    assert not unfiltered.is_filtering
    assert unfiltered.leaves_out(create_branch_object("software", 1)) is None


def test_the_build_command_offers_the_flag_that_asks_for_the_tooling():
    """
    The filter is reachable only through the flag, so a flag the command does not
    declare is an affordance a caller cannot use.
    """
    parser = argparse.ArgumentParser()
    BuildCommand().declare_arguments(parser)

    assert parser.parse_args(["--tooling"]).tooling
    assert not parser.parse_args([]).tooling


# %% what a filtered build leaves behind


def test_a_filtered_build_leaves_the_software_out_of_the_branch_it_assembles(
    fork_checkout: ForkCheckout,
):
    """
    Reporting a branch as left out and merging it anyway would be the one failure a
    reader of the report could not detect, so the finished branch is asserted on too.
    """
    fork_checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    fork_checkout.branch_from(SECOND_TIP, UPSTREAM_BASE)
    pull_requests = [
        PullRequest(
            number=1,
            head=FIRST_TIP,
            base=UPSTREAM_BASE,
            draft=False,
            labels=[TOOLING_LABEL],
        ),
        PullRequest(number=2, head=SECOND_TIP, base=UPSTREAM_BASE, draft=False),
    ]

    report = build(fork_checkout, pull_requests, tooling=a_filter())

    assert [entry.branch for entry in report.tips] == [FIRST_TIP]
    assert [(entry.branch, entry.status) for entry in report.left_out] == [
        (SECOND_TIP, TipStatus.NOT_A_TOOLING_CHANGE)
    ]
    fork_checkout.git.switch_to(A_BUILD_BRANCH)
    assert fork_checkout.file_added_by(FIRST_TIP).exists()
    assert not fork_checkout.file_added_by(SECOND_TIP).exists()
