"""
The failure a merge cannot see: two tips that pass alone, merge cleanly and break
together - localising it, and telling the branch that causes it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from stack import PullRequest

import integration
from integration import (
    FailureLocationReport,
    IntegrationExitCode,
    ReportKey,
    ResolutionProvenance,
)

from test_maintenance import (
    A_LABEL_THIS_TOOL_NEVER_WRITES,
    ForkCheckout,
    RecordedLabelWrite,
    RecordingPullRequests,
    UPSTREAM_BASE,
    UPSTREAM_REMOTE,
    a_stack,
    fork_checkout,
    make_configuration,
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    A_PULL_REQUEST_NUMBER,
    INNOCENT_TIP,
    NEEDS_THE_MODULE,
    ONLY_TIP,
    REMOVES_THE_MODULE,
    branch_names_in,
    create_integration_test_failure,
    create_pull_request_object,
)

# `fork_checkout` is imported for pytest to collect as a fixture; naming it
# here keeps a linter from reading the import as unused.
__all__ = ["fork_checkout"]


# %% localising an integration test failure


BUILD_CHECK_SCRIPT = Path(__file__).parent / "dataset" / "check_the_build.py"
"""
A suite whose verdict depends on what the build actually contains, so an integration test failure
is reproduced rather than declared. Lives on the base, where every build has it.

Kept as a real Python file rather than a string, so it is syntax-checked and readable as
the program it is.
"""


def two_tips_that_break_only_together(checkout: ForkCheckout) -> list[PullRequest]:
    """
    Build tips that each pass alone, merge cleanly, and fail the suite together.

    The shape an integration test failure really takes: one branch's test comes to depend on
    something another branch removes. Neither is wrong, neither conflicts textually, and
    only a build carrying both can see it. An innocent tip merges first, so a search that
    blamed everything already in the build would be caught naming it.

    :param checkout: The checkout to build them in.
    :return: The board entries.
    """
    checkout.git.switch_to(UPSTREAM_BASE)
    (checkout.project_root / "a_module.py").write_text("VALUE = 1\n")
    (checkout.project_root / BUILD_CHECK_SCRIPT.name).write_text(
        BUILD_CHECK_SCRIPT.read_text()
    )
    checkout.git.stage("a_module.py", BUILD_CHECK_SCRIPT.name)
    checkout.git.commit("the module both tips are about")
    checkout.git.push_refspec("origin", UPSTREAM_BASE)
    checkout.git.push_refspec(UPSTREAM_REMOTE, UPSTREAM_BASE)
    checkout.git.fetch(UPSTREAM_REMOTE)

    checkout.branch_from(INNOCENT_TIP, UPSTREAM_BASE)

    checkout.git.checkout(NEEDS_THE_MODULE, UPSTREAM_BASE)
    (checkout.project_root / "test_needs_the_module.py").write_text(
        "import a_module\n\n\ndef test_it_is_there():\n    assert a_module.VALUE\n"
    )
    checkout.git.stage("test_needs_the_module.py")
    checkout.git.commit("a test that needs the module")
    checkout.git.push_refspec("origin", "needs-the-module:needs-the-module")

    checkout.git.checkout(REMOVES_THE_MODULE, UPSTREAM_BASE)
    checkout.git.remove("a_module.py")
    checkout.git.commit("the module goes away")
    checkout.git.push_refspec("origin", f"{REMOVES_THE_MODULE}:{REMOVES_THE_MODULE}")
    checkout.git.fetch("origin")
    checkout.git.switch_to(UPSTREAM_BASE)
    return [
        create_pull_request_object(1, INNOCENT_TIP, UPSTREAM_BASE),
        create_pull_request_object(2, NEEDS_THE_MODULE, UPSTREAM_BASE),
        create_pull_request_object(3, REMOVES_THE_MODULE, UPSTREAM_BASE),
    ]


def locate_break(
    checkout: ForkCheckout, pull_requests: list[PullRequest], test_command: str
) -> integration.BreakLocationReport:
    """
    Run one search for the breaking tip against the scratch fork.

    :param checkout: The checkout to build in.
    :param pull_requests: The board entries the stack is derived from.
    :param test_command: The suite that decides whether a build works.
    :return: What it localised.
    """
    return integration.FailureLocation(
        stack=a_stack(checkout, pull_requests),
        git=checkout.git,
        build_branch=A_BUILD_BRANCH,
        provenance=ResolutionProvenance({}),
        test_command=test_command,
    ).find()


A_SUITE_OVER_THE_BUILD = f"{sys.executable} {BUILD_CHECK_SCRIPT.name}"
"""
The command that runs :data:`BUILD_CHECK_SCRIPT` against whatever a build contains.
"""


def test_the_search_names_the_tip_whose_arrival_broke_the_suite(
    fork_checkout: ForkCheckout,
):
    """
    A build that merged cleanly and then failed says nothing about which branch to look
    at. Adding tips one at a time until the suite turns does, and it is the same order
    the build itself used - so the answer describes the build that failed rather than
    some other ordering of it.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = locate_break(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert report.integration_test_failure is not None
    assert report.integration_test_failure.culprit == REMOVES_THE_MODULE


def test_the_search_names_the_tip_the_culprit_actually_breaks_against(
    fork_checkout: ForkCheckout,
):
    """
    Naming everything already in the build is not actionable when only one of them is
    involved - the innocent tip merged first has nothing to do with it.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = locate_break(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert report.integration_test_failure.breaks_against == NEEDS_THE_MODULE


def test_searching_a_build_that_works_localises_nothing(fork_checkout: ForkCheckout):
    """
    There is no break to attribute, and inventing one would send somebody after a branch
    that is fine.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    report = locate_break(
        fork_checkout,
        [create_pull_request_object(1, ONLY_TIP, UPSTREAM_BASE)],
        f"{sys.executable} -c pass",
    )

    assert report.integration_test_failure is None
    assert report.exit_code is IntegrationExitCode.SUCCESS


def test_a_localised_break_is_never_reported_as_a_clean_search(
    fork_checkout: ForkCheckout,
):
    """
    The exit status is the only half a caller with no model in it reads, and a search
    that found the break is the case it most needs to hear about.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = locate_break(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert report.exit_code is IntegrationExitCode.TESTS_FAILED


def test_the_search_leaves_no_branch_of_its_own_behind(fork_checkout: ForkCheckout):
    """
    Narrowing asks one question per candidate, and a branch per question would
    accumulate a ref for every break ever localised. Only the build it assembled is a
    thing anybody meant to keep.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)
    before = branch_names_in(fork_checkout)

    report = locate_break(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert branch_names_in(fork_checkout) - before == {report.build_branch}


def test_the_search_report_serialises_what_it_localised(fork_checkout: ForkCheckout):
    """
    ``--json`` is what the triage skill reads, so the pair has to survive the document.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    written = locate_break(
        fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD
    ).as_json()

    assert (
        json.loads(written)[ReportKey.STATUS]
        == IntegrationExitCode.TESTS_FAILED.name_for_a_caller
    )
    localised = FailureLocationReport.from_json(written).integration_test_failure
    assert localised.culprit == REMOVES_THE_MODULE
    assert localised.breaks_against == NEEDS_THE_MODULE


# %% telling the branch that breaks another


def test_blocking_a_failure_holds_the_branch_that_causes_it_out_of_promotion():
    """
    A comment alone is missed, so the branch is held out of promotion until somebody
    acts, which the label is what does.
    """
    configuration = make_configuration()
    fork = RecordingPullRequests(
        labels={A_PULL_REQUEST_NUMBER: [A_LABEL_THIS_TOOL_NEVER_WRITES]}
    )

    create_integration_test_failure().block_the_branch_that_causes_it(
        configuration, fork
    )

    assert fork.label_writes == [
        RecordedLabelWrite(
            A_PULL_REQUEST_NUMBER,
            (
                A_LABEL_THIS_TOOL_NEVER_WRITES,
                configuration.integration_conflict_label,
            ),
        )
    ]


def test_blocking_a_failure_names_both_branches_to_the_one_that_broke_it():
    """
    "Your branch was skipped" is not actionable. The comment has to name what the branch
    breaks, since that is the half its owner cannot see from their own checks.
    """
    fork = RecordingPullRequests()

    create_integration_test_failure().block_the_branch_that_causes_it(
        make_configuration(), fork
    )

    posted = fork.comments[0]
    assert posted.pull_request_number == A_PULL_REQUEST_NUMBER
    assert NEEDS_THE_MODULE in posted.body


def test_the_block_is_reported_as_a_document_a_caller_can_read():
    """
    ``block-branch --json`` is the half a caller acts on, and its keys are backed by no
    dataclass ``asdict`` writes out, so nothing else would catch one drifting.
    """
    configuration = make_configuration()

    blocked = create_integration_test_failure().block_the_branch_that_causes_it(
        configuration, RecordingPullRequests()
    )
    document = json.loads(blocked.as_json())

    assert document[ReportKey.BLOCKED] == REMOVES_THE_MODULE
    assert document[ReportKey.PULL_REQUEST_NUMBER] == A_PULL_REQUEST_NUMBER
    assert document[ReportKey.BREAKS_AGAINST] == NEEDS_THE_MODULE
    assert document[ReportKey.LABEL] == configuration.integration_conflict_label
    assert document[ReportKey.COMMENT] == blocked.comment


def test_a_failure_only_the_combination_causes_names_no_branch_as_its_partner():
    """
    Narrowing does not always land on a single earlier tip, and reporting the whole
    build as the culprit's partner would send its owner to branches that are innocent.
    """
    fork = RecordingPullRequests()

    create_integration_test_failure(
        breaks_against=None
    ).block_the_branch_that_causes_it(make_configuration(), fork)

    assert NEEDS_THE_MODULE not in fork.comments[0].body
