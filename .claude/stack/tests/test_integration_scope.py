"""
Which branches the integration branch is scoped to.

A scoped build carries a branch only when its pull request is labelled as being in
scope, or when its own commits change nothing but the tooling.
"""

from __future__ import annotations

import dataclasses
import tomllib

from stack import CONFIGURATION_PATH, Branch, PullRequest, Stack
from integration_changed_paths import BranchChanges
from integration_scope import IntegrationScope, IntegrationScopeSetting
from integration_selection import select_for_build, tips_of
from integration_tips import PullRequestStackTipOutcome, TipStatus

from integration_fixtures import create_branch_object, make_configuration
from test_maintenance import (
    UPSTREAM_BASE,
    UPSTREAM_REMOTE,
    ForkCheckout,
    a_stack,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
)

IN_SCOPE_LABEL = "a-label-in-scope"
"""
A label the scope under test carries a branch for.
"""

TOOLING_DIRECTORY = "the-tooling/"
"""
Where the tooling lives for the scope under test.
"""

SHARED_FILE = "a-shared-file"
"""
A path the tooling and the software both change.
"""

A_SCOPE = IntegrationScope(
    labels=frozenset({IN_SCOPE_LABEL}),
    tooling_paths=(TOOLING_DIRECTORY,),
    shared_paths=(SHARED_FILE,),
)
"""
The scope every scoped build in this module is asked for.
"""


def scoped_stack(branches: list[Branch]) -> Stack:
    """
    :param branches: The stack's nodes.
    :return: A stack whose configuration scopes the integration branch to
        :data:`A_SCOPE`, none of whose branches has landed.
    """
    return Stack(
        configuration=dataclasses.replace(
            make_configuration(), integration_scope=A_SCOPE
        ),
        branches=branches,
        is_merged=lambda name: False,
    )


def changing(branch: Branch, *paths: str) -> Branch:
    """
    :param branch: The branch to describe.
    :param paths: What its own commits change.
    :return: The same branch, read as changing those paths.
    """
    branch.changed_paths = paths
    return branch


# %% what a scoped build carries


def test_a_branch_labelled_in_scope_is_carried():
    labelled = changing(
        create_branch_object("labelled", 1, labels=[IN_SCOPE_LABEL]), "software.py"
    )

    assert tips_of(scoped_stack([labelled])) == [labelled]


def test_a_branch_changing_only_the_tooling_is_carried_without_a_label():
    tooling = changing(
        create_branch_object("tooling", 1),
        f"{TOOLING_DIRECTORY}a-tool.py",
        SHARED_FILE,
    )

    assert tips_of(scoped_stack([tooling])) == [tooling]


def test_a_branch_changing_the_software_as_well_is_left_out_as_out_of_scope():
    mixed = changing(
        create_branch_object("mixed", 1),
        f"{TOOLING_DIRECTORY}a-tool.py",
        "software.py",
    )

    assert select_for_build(scoped_stack([mixed])).left_out == (
        PullRequestStackTipOutcome(
            branch=mixed.name,
            pull_request_number=mixed.pull_request_number,
            status=TipStatus.OUT_OF_SCOPE,
            attributed_to=None,
        ),
    )


def test_a_branch_changing_only_shared_paths_is_not_a_tooling_change():
    shared = changing(create_branch_object("shared", 1), SHARED_FILE)

    assert tips_of(scoped_stack([shared])) == []


def test_a_branch_on_one_out_of_scope_is_left_out_on_its_parent_s_account():
    """
    A tip contains its stack, so carrying it would carry the parent the scope excludes.
    """
    beneath = changing(create_branch_object("beneath", 1), "software.py")
    above = changing(
        create_branch_object("above", 2, parent=beneath.name, labels=[IN_SCOPE_LABEL]),
        "software.py",
    )

    left_out = select_for_build(scoped_stack([beneath, above])).left_out

    assert left_out[1] == PullRequestStackTipOutcome(
        branch=above.name,
        pull_request_number=above.pull_request_number,
        status=TipStatus.OUT_OF_SCOPE,
        attributed_to=beneath.name,
    )


def test_a_build_scoped_to_everything_carries_an_unlabelled_software_change():
    software = changing(create_branch_object("software", 1), "software.py")
    stack = scoped_stack([software])
    stack.configuration = dataclasses.replace(
        stack.configuration, integration_scope=IntegrationScope.everything()
    )

    assert tips_of(stack) == [software]


# %% where the scope is configured


def test_the_scope_is_read_from_the_configuration_values():
    scope = IntegrationScope.from_values(
        {
            IntegrationScopeSetting.LABELS: [IN_SCOPE_LABEL],
            IntegrationScopeSetting.TOOLING_PATHS: [TOOLING_DIRECTORY],
            IntegrationScopeSetting.SHARED_PATHS: [SHARED_FILE],
        }
    )

    assert scope == A_SCOPE


def test_a_configuration_naming_no_scope_carries_everything():
    assert IntegrationScope.from_values({}) == IntegrationScope.everything()


def test_the_committed_configuration_scopes_to_tooling_and_bug_fixes():
    """
    The integration branch carries the workflow's own tooling and the bug fixes in
    flight, and nothing else.
    """
    committed = IntegrationScope.from_values(
        tomllib.loads(CONFIGURATION_PATH.read_text())
    )

    assert committed.labels == frozenset({"tooling", "bug"})
    assert committed.is_a_tooling_change((".claude/stack/stack.py",))
    assert not committed.is_a_tooling_change(("semantic_digital_twin/src/a.py",))


# %% what each branch changes, read from git


def test_a_branch_is_read_as_changing_only_what_its_own_commits_change(
    fork_checkout: ForkCheckout,
):
    """
    Neither its parent's work nor the upstream base it merged in is its own.
    """
    fork_checkout.branch_from("beneath", UPSTREAM_BASE)
    fork_checkout.branch_from("above", "beneath")
    fork_checkout.run_git("checkout", "--quiet", UPSTREAM_BASE)
    fork_checkout.commit("an-upstream-file", "landed upstream\n")
    fork_checkout.run_git("push", "--quiet", UPSTREAM_REMOTE, UPSTREAM_BASE)
    fork_checkout.run_git("fetch", "--quiet", UPSTREAM_REMOTE)
    fork_checkout.run_git("checkout", "--quiet", "above")
    fork_checkout.run_git(
        "merge", "--quiet", "--no-edit", f"{UPSTREAM_REMOTE}/{UPSTREAM_BASE}"
    )
    fork_checkout.run_git("push", "--quiet", "origin", "above")
    fork_checkout.run_git("fetch", "--quiet", "origin")
    configuration = dataclasses.replace(make_configuration(), integration_scope=A_SCOPE)
    stack = a_stack(
        fork_checkout,
        [
            PullRequest(number=1, head="beneath", base=UPSTREAM_BASE, draft=False),
            PullRequest(number=2, head="above", base="beneath", draft=False),
        ],
    )
    stack.configuration = configuration

    annotated = BranchChanges(configuration, fork_checkout.git).annotate(stack)

    assert {branch.name: branch.changed_paths for branch in annotated.branches} == {
        "beneath": (fork_checkout.file_added_by("beneath").name,),
        "above": (fork_checkout.file_added_by("above").name,),
    }
