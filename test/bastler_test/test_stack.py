"""
Tests for the stacked-PR helper's pure logic (no git, no network) and its personal-notes
configuration layering (real scratch git repositories, no network).

The data layer is injected - :func:`build_stack` takes a merged-branch predicate - so
status derivation, topological ordering, promotion policy, and the restack plan are all
exercised against in-memory pull-request exports. Configuration layering genuinely needs a git
remote, so those tests run against a :class:`ScratchRepository` instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Container, Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

import bastler.stack
from bastler.maintenance_git_commands import GitCommandRunner
from bastler.stack import (
    AmbiguousForkRemoteError,
    BOARD_PATH,
    CommitMoveAction,
    Command,
    BranchStatus,
    Configuration,
    ContradictoryLabelWriteError,
    ExitCode,
    ForkRemoteNotFoundError,
    LabelWrite,
    MalformedRepositoryError,
    IntegrationStrategy,
    CommitMoveChecks,
    ProposedCommitMove,
    RefusalReason,
    PromotionLink,
    PromotionLinkTooLongError,
    PullRequest,
    CONFIGURATION_PATH,
    Remote,
    Reparent,
    Repository,
    ENTRY_POINT_NAME,
    TOOLING_DIRECTORY,
    WorkingTreeTooling,
    build_stack,
    derive_status,
    landed_branches,
    load_configuration,
    next_to_promote,
    print_configuration,
    reparents,
    resolve_remotes,
    order,
    promotion_order,
    restack_plan,
)

from .constants import REPOSITORY_ROOT
from .scratch_repository import ScratchRepository
from .script_runner import PythonModuleRunner

A_LABEL_THIS_TOOL_NEVER_WRITES = "a-label-somebody-else-put-here"
"""
Stands for whatever else a pull request happens to carry - the labels a write must
preserve precisely because this tool knows nothing about them.
"""

STACK_MODULE = bastler.stack.__name__
"""
The tool under test, invoked as a subprocess wherever an exit status is the assertion.

Named off the module rather than spelled out, and run with ``-m`` rather than by path: a
module run by path puts its own directory on ``sys.path`` in place of the project root,
so its absolute imports of its siblings would not resolve.
"""


def make_configuration(upstream_setup_command: str | None = None) -> Configuration:
    return Configuration(
        in_review_label="in-review",
        rebase_label="rebase",
        needs_resolution_label="needs-resolution",
        fork_repository=Repository("a-fork-owner", "a-fork"),
        fork_remote="origin",
        upstream_repository=Repository("an-upstream-owner", "a-project"),
        upstream_remote="cram2",
        upstream_base="main",
        upstream_setup_command=upstream_setup_command,
    )


def build(prs: list[PullRequest], merged: Container[str] = frozenset()):
    return build_stack(make_configuration(), prs, lambda name: name in merged)


# %% derive_status


def test_merged_wins_over_everything():
    assert derive_status(draft=True, merged=True, in_review=True) == BranchStatus.MERGED


def test_in_review_label_beats_draft_flag():
    assert (
        derive_status(draft=True, merged=False, in_review=True)
        == BranchStatus.IN_REVIEW
    )


def test_undrafted_is_ready():
    assert (
        derive_status(draft=False, merged=False, in_review=False) == BranchStatus.READY
    )


def test_drafted_is_draft():
    assert (
        derive_status(draft=True, merged=False, in_review=False) == BranchStatus.DRAFT
    )


# %% status from the export


def test_in_review_derived_from_label():
    stack = build(
        [PullRequest(3, "feature", "main", draft=False, labels=["in-review"])]
    )
    assert stack.branches[0].status == BranchStatus.IN_REVIEW


def test_merged_derived_from_predicate_not_labels():
    stack = build(
        [PullRequest(9, "landed", "main", draft=False, labels=[])], merged={"landed"}
    )
    assert stack.branches[0].status == BranchStatus.MERGED


def test_rebase_label_sets_strategy():
    stack = build([PullRequest(1, "f", "main", draft=True, labels=["rebase"])])
    assert stack.branches[0].strategy == IntegrationStrategy.REBASE
    stack = build([PullRequest(1, "f", "main", draft=True, labels=[])])
    assert stack.branches[0].strategy == IntegrationStrategy.MERGE


# %% ordering: parent before child, even when declared out of order


def test_order_places_parent_before_child():
    prs = [
        PullRequest(3, "child", "parent", draft=True),
        PullRequest(2, "parent", "main", draft=True),
    ]
    names = [b.name for b in order(build(prs))]
    assert names.index("parent") < names.index("child")


# %% promotion policy - simplified: every ready, unblocked branch, no cap or turn order


def test_promotes_ready_root():
    prs = [PullRequest(11, "arith", "main", draft=False)]
    assert next_to_promote(build(prs)).name == "arith"


def test_nothing_promotes_when_all_draft():
    prs = [PullRequest(5, "wip", "main", draft=True)]
    assert next_to_promote(build(prs)) is None


def test_ready_child_blocked_until_parent_lands():
    prs = [
        PullRequest(1, "parent", "main", draft=True),  # still draft, not on cram2
        PullRequest(
            2, "child", "parent", draft=False
        ),  # approved but parent hasn't landed
    ]
    assert next_to_promote(build(prs)) is None


def test_child_promotable_once_parent_reaches_review():
    # there is no per-stack review-slot limit anymore, so a child may promote alongside
    # its own parent the moment the parent has reached in-review - it does not have to
    # wait for the parent to fully merge.
    prs = [
        PullRequest(1, "parent", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "child", "parent", draft=False),
    ]
    assert next_to_promote(build(prs)).name == "child"


def test_child_promotable_once_parent_merged():
    prs = [
        PullRequest(1, "parent", "main", draft=False),
        PullRequest(2, "child", "parent", draft=False),
    ]
    assert next_to_promote(build(prs, merged={"parent"})).name == "child"


def test_promotion_order_includes_every_ready_unblocked_branch_in_dependency_order():
    # two independent ready roots plus one ready child whose own parent has not yet
    # reached review - all ready roots promote together (no cap), the blocked child does
    # not.
    prs = [
        PullRequest(1, "a", "main", draft=False),
        PullRequest(2, "c", "a", draft=False),  # child of "a", but "a" is only ready
        PullRequest(3, "b", "main", draft=False),
    ]
    names = [b.name for b in promotion_order(build(prs))]
    assert names == ["a", "b"]


def test_promotion_order_withholds_a_branch_delegated_for_conflict_resolution():
    # a branch the routine delegated (needs-resolution) is stuck mid-restack, so it must
    # not be promoted even though it is otherwise ready and unblocked.
    prs = [
        PullRequest(1, "stuck", "main", draft=False, labels=["needs-resolution"]),
        PullRequest(2, "fine", "main", draft=False),
    ]
    names = [b.name for b in promotion_order(build(prs))]
    assert names == ["fine"]


def test_ci_and_session_carried_onto_branch():
    stack = build(
        [
            PullRequest(
                11,
                "f",
                "main",
                draft=False,
                ci="failure",
                session="https://claude.ai/code/session_x",
            )
        ]
    )
    assert stack.branches[0].ci == "failure"
    assert stack.branches[0].session == "https://claude.ai/code/session_x"


# %% restack plan


def test_restack_plan_excludes_merged_only():
    prs = [
        PullRequest(1, "landed", "main", draft=False),
        PullRequest(2, "review", "main", draft=False, labels=["in-review"]),
        PullRequest(3, "wip", "review", draft=True),
    ]
    plan = restack_plan(build(prs, merged={"landed"}))
    names = [entry["branch"] for entry in plan]
    assert "landed" not in names
    assert names == ["review", "wip"]  # in-review included, parent before child


def test_restack_plan_carries_parent_and_strategy():
    prs = [PullRequest(2, "wip", "base-branch", draft=True, labels=["rebase"])]
    plan = restack_plan(build(prs))
    assert plan == [{"branch": "wip", "parent": "base-branch", "strategy": "rebase"}]


def test_restack_plan_reparents_child_of_merged_parent_onto_base():
    # parent merged into main -> its commits are in the base, so the child is reparented
    # onto main (the routine mirrors this by retargeting the child PR's base on GitHub).
    prs = [
        PullRequest(1, "parent", "main", draft=False),
        PullRequest(2, "child", "parent", draft=False),
    ]
    plan = restack_plan(build(prs, merged={"parent"}))
    assert plan == [{"branch": "child", "parent": "main", "strategy": "merge"}]


# %% landed parents that no open pull request describes


def test_restack_plan_reparents_child_of_a_landed_parent_with_no_open_pull_request():
    # the board only carries OPEN pull requests, so a parent whose own PR was closed is
    # absent from it entirely - yet its commits are in the upstream base, so its child
    # must still be reparented onto that base rather than left on the landed branch.
    prs = [PullRequest(2, "child", "landed-elsewhere", draft=False)]
    plan = restack_plan(build(prs, merged={"landed-elsewhere"}))
    assert plan == [{"branch": "child", "parent": "main", "strategy": "merge"}]


def test_ready_child_blocked_when_its_only_parent_is_an_unlanded_off_board_branch():
    # an off-board parent is not evidence of a root branch: this one has not landed, so
    # the child is not promotable even though no PR describes the parent.
    prs = [PullRequest(2, "child", "unlanded-elsewhere", draft=False)]
    assert next_to_promote(build(prs)) is None


def test_ready_child_promotable_when_its_off_board_parent_has_landed():
    prs = [PullRequest(2, "child", "landed-elsewhere", draft=False)]
    assert next_to_promote(build(prs, merged={"landed-elsewhere"})).name == "child"


# %% configuration layering (personal-notes overrides)

DEFAULT_STACK_TOML = """\
in_review_label = "in-review"
rebase_label = "rebase"
needs_resolution_label = "needs-resolution"
fork_remote = "origin"
upstream_repository = "an-upstream-owner/a-project"
upstream_remote = "cram2"
upstream_base = "main"
"""


def _committed_configuration_path(scratch_repository: ScratchRepository) -> Path:
    """
    Write and commit the repo-default ``stack.toml`` into a scratch repository, beside
    the shell file the personal-notes override is fetched through.

    :param scratch_repository: The scratch repository to write into.
    :return: The path :func:`load_configuration` should be pointed at.
    """
    path = scratch_repository.install_stack_configuration(DEFAULT_STACK_TOML)
    scratch_repository.run_git(
        "remote",
        "add",
        "a-name-nobody-expects",
        "https://github.com/a-fork-owner/a-fork.git",
    )
    return path


def test_load_configuration_uses_committed_defaults_when_no_personal_notes_branch(
    scratch_repository: ScratchRepository, monkeypatch
):
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(configuration_path)

    assert configuration.upstream_remote == "cram2"


def test_load_configuration_layers_personal_notes_override_on_top_of_defaults(
    scratch_repository: ScratchRepository, monkeypatch
):
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.publish_notes_branch(
        {".claude/personal/stack.toml": 'upstream_remote = "my-fork-cram2"\n'}
    )
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(configuration_path)

    assert configuration.upstream_remote == "my-fork-cram2"
    assert configuration.upstream_base == "main"  # untouched default


def test_load_configuration_ignores_personal_notes_branch_without_a_stack_file(
    scratch_repository: ScratchRepository, monkeypatch
):
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.publish_notes_branch({"README.md": "unrelated\n"})
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(configuration_path)

    assert configuration.upstream_remote == "cram2"


def test_load_configuration_resolves_the_fork_whatever_the_remote_is_called(
    scratch_repository: ScratchRepository, monkeypatch
):
    """
    Nothing has to be configured: a checkout already knows its own fork.
    """
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(configuration_path)

    assert configuration.fork_repository == Repository("a-fork-owner", "a-fork")
    assert configuration.fork_remote == "a-name-nobody-expects"


def test_load_configuration_takes_the_fork_from_a_personal_notes_override(
    scratch_repository: ScratchRepository, monkeypatch
):
    """
    An override picks between real remotes; it cannot name a fork the checkout cannot
    push to.
    """
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.run_git(
        "remote", "add", "another", "https://github.com/someone-else/their-fork.git"
    )
    scratch_repository.publish_notes_branch(
        {".claude/personal/stack.toml": 'fork_repository = "someone-else/their-fork"\n'}
    )
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(configuration_path)

    assert configuration.fork_repository == Repository("someone-else", "their-fork")
    assert configuration.fork_remote == "another"


# %% repository references


def test_repository_splits_a_reference_into_owner_and_name():
    assert Repository.parse("an-owner/a-repository") == Repository(
        "an-owner", "a-repository"
    )


def test_repository_round_trips_through_the_form_github_uses():
    assert str(Repository.parse("an-owner/a-repository")) == "an-owner/a-repository"


@pytest.mark.parametrize("malformed", ["no-separator", "/no-owner", "no-name/"])
def test_repository_rejects_a_reference_that_is_not_owner_and_name(malformed: str):
    """
    A half-parsed reference would silently target the wrong repository.
    """
    with pytest.raises(MalformedRepositoryError):
        Repository.parse(malformed)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/an-owner/a-repository.git",
        "https://github.com/an-owner/a-repository",
        "git@github.com:an-owner/a-repository.git",
        "http://127.0.0.1:41729/git/an-owner/a-repository",
    ],
)
def test_repository_reads_the_owner_and_name_from_a_remote_url(url: str):
    """
    Every shape a fork remote takes names the same repository.

    A cloud session reaches GitHub through a local proxy, so the URL it sees shares
    neither host nor scheme with the one a laptop clone has.
    """
    assert Repository.from_remote_url(url) == Repository("an-owner", "a-repository")


@pytest.mark.parametrize("malformed", ["", "https://github.com/only-one-segment"])
def test_repository_rejects_a_remote_url_naming_no_repository(malformed: str):
    with pytest.raises(MalformedRepositoryError):
        Repository.from_remote_url(malformed)


# %% resolving which remote is the fork

UPSTREAM = Repository("an-upstream-owner", "a-project")
FORK = Repository("a-fork-owner", "a-project")


def resolve(remote_urls: dict[str, str], fork_repository: Repository | None = None):
    return resolve_remotes(remote_urls, UPSTREAM, "an-upstream-remote", fork_repository)


def test_the_fork_is_the_remote_that_is_not_the_upstream():
    """
    Names carry no meaning: the fork is identified by the repository its URL points at.
    """
    resolution = resolve(
        {
            "origin": "https://github.com/an-upstream-owner/a-project.git",
            "whatever-i-called-it": "https://github.com/a-fork-owner/a-project.git",
        }
    )

    assert resolution.fork == Remote("whatever-i-called-it", FORK)
    assert resolution.upstream == Remote("origin", UPSTREAM)


def test_the_fork_resolves_the_same_when_origin_happens_to_be_the_fork():
    resolution = resolve(
        {
            "origin": "https://github.com/a-fork-owner/a-project.git",
            "cram2": "https://github.com/an-upstream-owner/a-project.git",
        }
    )

    assert resolution.fork == Remote("origin", FORK)


def test_the_fork_resolves_from_a_checkout_that_has_only_the_fork():
    """
    A fresh cloud clone has one remote and no upstream at all.
    """
    resolution = resolve({"origin": "https://github.com/a-fork-owner/a-project.git"})

    assert resolution.fork == Remote("origin", FORK)
    assert resolution.upstream is None


def test_a_checkout_without_an_upstream_remote_is_told_how_to_add_one():
    resolution = resolve({"origin": "https://github.com/a-fork-owner/a-project.git"})

    assert resolution.upstream_setup_command == (
        "git remote add an-upstream-remote "
        "https://github.com/an-upstream-owner/a-project.git"
    )
    assert resolution.upstream_name == "an-upstream-remote"


def test_nothing_to_add_when_the_upstream_remote_is_already_there():
    resolution = resolve(
        {
            "origin": "https://github.com/a-fork-owner/a-project.git",
            "cram2": "https://github.com/an-upstream-owner/a-project.git",
        }
    )

    assert resolution.upstream_setup_command is None
    assert resolution.upstream_name == "cram2"


def test_a_checkout_with_only_the_upstream_is_rejected_rather_than_guessed():
    """
    Treating the upstream as the fork would target every push at the review repository.
    """
    with pytest.raises(ForkRemoteNotFoundError):
        resolve({"origin": "https://github.com/an-upstream-owner/a-project.git"})


def test_two_possible_forks_are_rejected_rather_than_guessed():
    with pytest.raises(AmbiguousForkRemoteError):
        resolve(
            {
                "mine": "https://github.com/a-fork-owner/a-project.git",
                "theirs": "https://github.com/another-owner/a-project.git",
            }
        )


def test_configuration_disambiguates_two_possible_forks():
    resolution = resolve(
        {
            "mine": "https://github.com/a-fork-owner/a-project.git",
            "theirs": "https://github.com/another-owner/a-project.git",
        },
        fork_repository=FORK,
    )

    assert resolution.fork == Remote("mine", FORK)


def test_a_remote_that_names_no_repository_is_ignored():
    """
    A local-path remote is not a candidate, and must not make the fork ambiguous.
    """
    resolution = resolve(
        {
            "origin": "https://github.com/a-fork-owner/a-project.git",
            "backup": "/srv/git/mirror",
        }
    )

    assert resolution.fork == Remote("origin", FORK)


# %% the configuration the shell tooling reads


def test_every_setting_is_printed_under_its_own_field_name(capsys):
    """
    Callers read one setting by name out of this output, so a key that is not a field name
    is a key nobody can look up - and a field that never prints is a setting nobody can read.
    """
    print_configuration(make_configuration())

    printed = dict(line.split("\t") for line in capsys.readouterr().out.splitlines())

    assert printed == {
        "in_review_label": "in-review",
        "rebase_label": "rebase",
        "needs_resolution_label": "needs-resolution",
        "fork_repository": "a-fork-owner/a-fork",
        "fork_remote": "origin",
        "upstream_repository": "an-upstream-owner/a-project",
        "upstream_remote": "cram2",
        "upstream_base": "main",
    }


def test_a_checkout_missing_its_upstream_remote_is_printed_the_command_that_adds_it(
    capsys,
):
    print_configuration(
        make_configuration(upstream_setup_command="git remote add cram2 a-url")
    )

    printed = dict(line.split("\t") for line in capsys.readouterr().out.splitlines())

    assert printed["upstream_setup_command"] == "git remote add cram2 a-url"


def test_nothing_is_printed_for_a_setup_command_that_is_not_needed(capsys):
    """
    An empty value would read as a command to run, so the line is absent rather than
    blank.
    """
    print_configuration(make_configuration())

    assert "upstream_setup_command" not in capsys.readouterr().out


# %% a whole stack through its lifecycle

# The unit tests above each exercise one function against one or two pull requests.
# These walk a single realistic stack through the transitions the README describes -
# approve, promote, land, restack - asserting the derived state at each step, because
# the interactions between those stages are what a per-function test cannot reach.


def a_deep_stack_beside_an_independent_branch(
    approved: Container[str] = frozenset(),
    promoted: Container[str] = frozenset(),
    withheld: Container[str] = frozenset(),
    landed: Container[str] = frozenset(),
):
    """
    Two independent stacks off `main`, the first three deep and the second a single
    branch.

    :param approved: Branches the developer has un-drafted.
    :param promoted: Branches carrying the in-review label.
    :param withheld: Branches delegated for conflict resolution.
    :param landed: Branches that are ancestors of the upstream base.
    :return: The stack as the tooling derives it.
    """
    deep = [("engine", "main"), ("engine-ui", "engine"), ("engine-docs", "engine-ui")]
    aside = [("parser", "main")]
    pull_requests = [
        PullRequest(
            number,
            name,
            parent,
            draft=name not in approved,
            labels=(["in-review"] if name in promoted else [])
            + (["needs-resolution"] if name in withheld else []),
        )
        for number, (name, parent) in enumerate([*deep, *aside], start=1)
    ]
    return build(pull_requests, merged=landed)


def test_nothing_promotes_while_the_whole_stack_is_still_draft():
    assert promotion_order(a_deep_stack_beside_an_independent_branch()) == []


def test_approving_a_root_promotes_it_and_nothing_above_it():
    """
    Un-drafting is the approval gate, and it approves one branch rather than a whole
    stack.
    """
    stack = a_deep_stack_beside_an_independent_branch(approved={"engine", "engine-ui"})

    assert [branch.name for branch in promotion_order(stack)] == ["engine"]


def test_promoting_a_parent_unblocks_the_child_behind_it():
    """
    A child may follow its parent upstream once the parent is in review - it does not
    wait for the parent to merge.
    """
    stack = a_deep_stack_beside_an_independent_branch(
        approved={"engine", "engine-ui"}, promoted={"engine"}
    )

    assert [branch.name for branch in promotion_order(stack)] == ["engine-ui"]


def test_both_stacks_promote_together_since_they_do_not_depend_on_each_other():
    stack = a_deep_stack_beside_an_independent_branch(approved={"engine", "parser"})

    assert [branch.name for branch in promotion_order(stack)] == ["engine", "parser"]


def test_a_branch_delegated_for_conflict_resolution_is_held_back_alone():
    """
    Withholding one branch must not withhold an unrelated stack.
    """
    stack = a_deep_stack_beside_an_independent_branch(
        approved={"engine", "parser"}, withheld={"engine"}
    )

    assert [branch.name for branch in promotion_order(stack)] == ["parser"]


def test_landing_a_root_reparents_only_its_own_child():
    """
    The landed branch drops out of the plan and its child moves onto the base, while the
    branch above keeps the parent it still has and the untouched stack keeps its own.
    """
    stack = a_deep_stack_beside_an_independent_branch(landed={"engine"})

    assert restack_plan(stack) == [
        {"branch": "engine-ui", "parent": "main", "strategy": "merge"},
        {"branch": "engine-docs", "parent": "engine-ui", "strategy": "merge"},
        {"branch": "parser", "parent": "main", "strategy": "merge"},
    ]


def test_landing_a_root_that_no_open_pull_request_describes_still_reparents():
    """
    The case that motivated deciding `merged` by git ancestry: a parent whose own pull
    request was closed rather than merged is absent from the board entirely, and the
    child must still be moved off it.
    """
    orphaned = build(
        [PullRequest(2, "engine-ui", "engine", draft=True)], merged={"engine"}
    )

    assert restack_plan(orphaned) == [
        {"branch": "engine-ui", "parent": "main", "strategy": "merge"}
    ]
    assert orphaned.has_landed_upstream("engine")


def test_a_stack_lands_bottom_up_over_successive_runs():
    """
    Each branch reaches the base only after the one below it has, so the plan shortens
    from the bottom as the stack drains.
    """
    after_first = a_deep_stack_beside_an_independent_branch(landed={"engine"})
    after_second = a_deep_stack_beside_an_independent_branch(
        landed={"engine", "engine-ui"}
    )

    assert [entry["branch"] for entry in restack_plan(after_first)] == [
        "engine-ui",
        "engine-docs",
        "parser",
    ]
    assert [entry["branch"] for entry in restack_plan(after_second)] == [
        "engine-docs",
        "parser",
    ]
    assert restack_plan(after_second)[0] == {
        "branch": "engine-docs",
        "parent": "main",
        "strategy": "merge",
    }


# %% label writes


def test_adding_a_label_keeps_every_label_the_pull_request_already_carries():
    """
    The label write replaces the whole set, so computing it from the addition alone
    silently wipes the rest - which has happened, stripping `in-review` off branches that
    were already promoted.
    """
    configuration = make_configuration()

    write = LabelWrite.replacing(
        [configuration.in_review_label, A_LABEL_THIS_TOOL_NEVER_WRITES],
        added=[configuration.needs_resolution_label],
    )

    assert write.labels == (
        configuration.in_review_label,
        A_LABEL_THIS_TOOL_NEVER_WRITES,
        configuration.needs_resolution_label,
    )


def test_removing_a_label_keeps_every_other_label():
    configuration = make_configuration()

    write = LabelWrite.replacing(
        [configuration.in_review_label, A_LABEL_THIS_TOOL_NEVER_WRITES],
        removed=[A_LABEL_THIS_TOOL_NEVER_WRITES],
    )

    assert write.labels == (configuration.in_review_label,)


def test_adding_a_label_already_carried_leaves_the_set_unchanged():
    carried = make_configuration().in_review_label

    write = LabelWrite.replacing([carried], added=[carried])

    assert write.labels == (carried,)


def test_removing_a_label_that_is_not_there_leaves_the_set_unchanged():
    configuration = make_configuration()

    write = LabelWrite.replacing(
        [configuration.in_review_label], removed=[configuration.rebase_label]
    )

    assert write.labels == (configuration.in_review_label,)


def test_asking_to_add_and_remove_one_label_at_once_is_refused():
    """
    Either outcome would be a guess at what the caller meant, and the wrong guess is a
    label silently kept or silently dropped.
    """
    configuration = make_configuration()

    with pytest.raises(ContradictoryLabelWriteError):
        LabelWrite.replacing(
            [configuration.in_review_label],
            added=[configuration.rebase_label],
            removed=[configuration.rebase_label],
        )


# %% move check


def a_proposed_push(
    source: str = "engine",
    destination: str = "engine",
    destination_remote: str = "origin",
) -> ProposedCommitMove:
    """
    A proposed push, defaulting to the one shape that is always allowed.

    :param source: The branch whose commits would move.
    :param destination: The branch they would land on.
    :param destination_remote: The remote holding the destination.
    :return: The proposed move.
    """
    return ProposedCommitMove(
        action=CommitMoveAction.PUSH,
        source=source,
        destination=destination,
        destination_remote=destination_remote,
    )


def checks_over_that_stack(
    checked_out_branch: str = "engine", ancestors: Container[str] = frozenset()
) -> CommitMoveChecks:
    """
    A move check over the stack above.

    :param checked_out_branch: What ``git branch --show-current`` would report.
    :param ancestors: Branches already contained in the move's source.
    :return: The move check to ask for refusals.
    """
    return CommitMoveChecks(
        stack=a_deep_stack_beside_an_independent_branch(),
        checked_out_branch=checked_out_branch,
        is_ancestor=lambda candidate, _descendant: candidate in ancestors,
    )


def test_pushing_the_checked_out_branch_onto_itself_is_allowed():
    assert checks_over_that_stack().refusals(a_proposed_push()) == []


def test_pushing_while_another_branch_is_checked_out_is_refused():
    """
    The checked-out branch is the one whose content actually moves, so a mismatch moves
    something other than what was intended.
    """
    refusals = checks_over_that_stack(checked_out_branch="parser").refusals(
        a_proposed_push()
    )

    assert [refusal.reason for refusal in refusals] == [RefusalReason.NOT_CHECKED_OUT]
    assert "parser" in refusals[0].explanation


def test_a_push_naming_a_different_branch_on_each_side_is_refused():
    refusals = checks_over_that_stack().refusals(
        a_proposed_push(destination="engine-ui")
    )

    assert [refusal.reason for refusal in refusals] == [
        RefusalReason.MISMATCHED_BRANCH_NAMES
    ]


def test_a_destination_on_the_upstream_remote_is_refused():
    """
    Every push in this workflow goes to the fork; the upstream is written only by
    opening a pull request against it.
    """
    refusals = checks_over_that_stack().refusals(
        a_proposed_push(destination_remote="cram2")
    )

    assert [refusal.reason for refusal in refusals] == [RefusalReason.NOT_THE_FORK]
    assert "cram2" in refusals[0].explanation


def test_a_push_that_would_make_a_child_an_ancestor_of_its_parent_is_refused():
    """
    GitHub reads a pull request whose head is contained in its base as merged, so this
    push would falsely close the child.
    """
    refusals = checks_over_that_stack(ancestors={"engine-ui"}).refusals(
        a_proposed_push()
    )

    assert [refusal.reason for refusal in refusals] == [RefusalReason.FALSE_MERGE]
    assert "engine-ui" in refusals[0].explanation


def test_an_unrelated_branch_contained_in_the_source_is_not_a_false_merge():
    """
    Only a child of the destination can be falsely merged by pushing to it.
    """
    assert (
        checks_over_that_stack(ancestors={"parser"}).refusals(a_proposed_push()) == []
    )


def test_every_reason_to_refuse_is_reported_rather_than_only_the_first():
    """
    Fixing one problem and re-running to discover the next is how a half-applied move
    gets made.
    """
    refusals = checks_over_that_stack(checked_out_branch="parser").refusals(
        a_proposed_push(destination="engine-ui", destination_remote="cram2")
    )

    assert [refusal.reason for refusal in refusals] == [
        RefusalReason.NOT_CHECKED_OUT,
        RefusalReason.MISMATCHED_BRANCH_NAMES,
        RefusalReason.NOT_THE_FORK,
    ]


# %% promotion links


def a_promotion_link(title: str = "A title", body: str = "A body") -> PromotionLink:
    """
    The compare-and-create link for that stack's root branch.

    :param title: The title to prefill.
    :param body: The body to prefill.
    :return: The built link.
    """
    return PromotionLink.build(make_configuration(), "engine", title, body)


def test_the_link_compares_the_upstream_base_against_the_fork_branch():
    assert a_promotion_link().url.startswith(
        "https://github.com/an-upstream-owner/a-project/compare/"
        "main...a-fork-owner:engine?expand=1"
    )


def test_the_title_and_body_are_encoded_rather_than_pasted_in_raw():
    """
    An unencoded ``&`` or ``#`` truncates the query string at that character, so the
    prefill silently loses everything after it.
    """
    url = a_promotion_link(title="Fix A & B", body="see #106").url

    assert "title=Fix%20A%20%26%20B" in url
    assert "body=see%20%23106" in url


def test_a_body_within_the_limit_is_left_whole():
    link = a_promotion_link(body="short")

    assert not link.body_was_truncated
    assert "body=short" in link.url


def test_an_oversized_body_is_truncated_rather_than_silently_dropped():
    """
    Over the limit the whole prefill is discarded by the server, so the link arrives
    with an empty description and nobody is told.
    """
    link = a_promotion_link(body="x" * 20000)

    assert link.body_was_truncated
    assert link.url.endswith(PromotionLink.TRUNCATION_MARKER)
    assert len(link.url) <= PromotionLink.URL_CHARACTER_LIMIT


def test_a_link_that_cannot_fit_even_without_a_description_is_refused():
    """
    Returning a link known to be over the limit would be the silent failure this class
    exists to prevent, so the one input that cannot be fixed by shortening the body says
    so.
    """
    with pytest.raises(PromotionLinkTooLongError):
        a_promotion_link(title="t" * 20000, body="")


# %% landed parents


def test_a_child_of_a_landed_parent_is_named_with_the_base_it_should_get():
    stack = a_deep_stack_beside_an_independent_branch(landed={"engine"})

    assert reparents(stack) == [
        Reparent(
            branch="engine-ui",
            pull_request_number=2,
            current_base="engine",
            target_base="main",
        )
    ]


def test_a_child_already_based_on_the_upstream_base_needs_no_reparent():
    assert reparents(a_deep_stack_beside_an_independent_branch()) == []


def test_a_child_of_a_landed_parent_with_no_open_pull_request_is_still_named():
    """
    The board carries only open pull requests, so a parent whose own was closed is absent
    from it entirely - the case that orphaned a real pull request for six days.
    """
    orphaned = build(
        [PullRequest(2, "engine-ui", "engine", draft=True)], merged={"engine"}
    )

    assert [reparent.branch for reparent in reparents(orphaned)] == ["engine-ui"]


def test_a_branch_that_has_landed_is_named_for_labelling_and_closing():
    stack = a_deep_stack_beside_an_independent_branch(landed={"engine"})

    assert [branch.name for branch in landed_branches(stack)] == ["engine"]


def test_nothing_has_landed_while_the_whole_stack_is_still_open():
    assert landed_branches(a_deep_stack_beside_an_independent_branch()) == []


# %% configuration named rather than inferred


def test_a_named_fork_is_used_where_inference_would_have_refused_to_guess(
    scratch_repository: ScratchRepository, monkeypatch
):
    """
    Two candidate remotes are ambiguous to inference; naming the fork settles it without
    anything being written to the checkout.
    """
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.run_git(
        "remote", "add", "another", "https://github.com/someone-else/their-fork.git"
    )
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    with pytest.raises(AmbiguousForkRemoteError):
        load_configuration(configuration_path)

    configuration = load_configuration(
        configuration_path, fork_repository=Repository("someone-else", "their-fork")
    )

    assert configuration.fork_repository == Repository("someone-else", "their-fork")
    assert configuration.fork_remote == "another"


def test_a_named_upstream_replaces_the_committed_default(
    scratch_repository: ScratchRepository, monkeypatch
):
    configuration_path = _committed_configuration_path(scratch_repository)
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    configuration = load_configuration(
        configuration_path,
        upstream_repository=Repository("a-different-upstream", "a-project"),
    )

    assert configuration.upstream_repository == Repository(
        "a-different-upstream", "a-project"
    )
    assert configuration.upstream_setup_command == (
        "git remote add cram2 https://github.com/a-different-upstream/a-project.git"
    )


# %% the command line a caller acts on the exit status of


@pytest.fixture
def offline_checkout(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A checkout carrying the package, whose personal-notes remote is a local bare
    repository.

    Resolving configuration fetches that branch, so pointing it at a local path is what
    keeps these tests off the network. The package is installed because the tool runs
    from the project root of the checkout it inspects, exactly as it does in a clone.

    :param scratch_repository: The scratch repository to point.
    :return: The same repository, now resolving its notes remote locally.
    """
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.install_package()
    return scratch_repository


def run_stack(
    checkout: ScratchRepository, *arguments: str, tool: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """
    Invoke the tool as a caller does, so its exit status is exercised rather than
    assumed.

    :param checkout: The repository to run in.
    :param arguments: The command and its flags.
    :param tool: Which copy of the tool to invoke, when it is not the checkout's own
        installed package - the working tree's own committed copy, or a copy pinned
        outside it.
    :return: The finished subprocess.
    """
    if tool is None:
        return PythonModuleRunner(
            project_root=checkout.project_root, module_name=STACK_MODULE
        ).run(*arguments)
    return subprocess.run(
        [sys.executable, str(tool), *arguments],
        capture_output=True,
        text=True,
        cwd=checkout.project_root,
    )


def test_an_unknown_command_is_a_usage_error(offline_checkout: ScratchRepository):
    assert run_stack(offline_checkout, "not-a-command").returncode == ExitCode.USAGE


def test_a_label_write_prints_the_complete_set_one_label_per_line(
    offline_checkout: ScratchRepository,
):
    """
    One per line rather than a joined list: a label may contain whatever a separator
    would have been.
    """
    result = run_stack(
        offline_checkout,
        "labels",
        "--current",
        "in-review",
        "--current",
        "bug",
        "--add",
        "rebase",
    )

    assert result.returncode == ExitCode.SUCCESS
    assert result.stdout.splitlines() == ["in-review", "bug", "rebase"]


def test_a_contradictory_label_write_is_refused_rather_than_guessed_at(
    offline_checkout: ScratchRepository,
):
    result = run_stack(
        offline_checkout, "labels", "--add", "rebase", "--remove", "rebase"
    )

    assert result.returncode == ExitCode.USAGE
    assert "rebase" in result.stderr


def test_a_checkout_whose_fork_cannot_be_identified_says_so_by_status(
    offline_checkout: ScratchRepository,
):
    """
    A caller has to tell "I cannot know which remote is yours" from every other failure
    without reading stderr, because that one is the question it can put to the user.
    """
    result = run_stack(offline_checkout, "configuration")

    assert result.returncode == ExitCode.REMOTES_UNRESOLVED


def test_a_readable_checkout_with_no_board_reports_the_missing_board_instead(
    offline_checkout: ScratchRepository,
):
    offline_checkout.run_git(
        "remote", "add", "whatever", "https://github.com/a-fork-owner/a-fork.git"
    )

    result = run_stack(offline_checkout, "status")

    assert result.returncode == ExitCode.BOARD_UNAVAILABLE


def test_a_named_fork_and_upstream_are_used_where_inference_would_have_refused(
    offline_checkout: ScratchRepository,
):
    """
    Two candidate remotes are ambiguous, so a caller that already knows the answer must
    be able to say so rather than be blocked by the guess it does not need.
    """
    offline_checkout.run_git(
        "remote", "add", "whatever", "https://github.com/a-fork-owner/a-fork.git"
    )
    offline_checkout.run_git(
        "remote", "add", "another", "https://github.com/someone-else/their-fork.git"
    )

    assert (
        run_stack(offline_checkout, "configuration").returncode
        == ExitCode.REMOTES_UNRESOLVED
    )

    result = run_stack(
        offline_checkout,
        "configuration",
        "--fork",
        "a-fork-owner/a-fork",
        "--upstream",
        "an-upstream-owner/a-project",
    )

    assert result.returncode == ExitCode.SUCCESS
    printed = dict(line.split("\t") for line in result.stdout.splitlines())
    assert printed["fork_repository"] == "a-fork-owner/a-fork"
    assert printed["fork_remote"] == "whatever"
    assert printed["upstream_repository"] == "an-upstream-owner/a-project"


def test_a_fork_that_is_not_owner_and_name_is_a_usage_error(
    offline_checkout: ScratchRepository,
):
    result = run_stack(offline_checkout, "configuration", "--fork", "not-a-repository")

    assert result.returncode == ExitCode.USAGE


def test_a_promotion_link_is_built_from_the_resolved_repositories(
    offline_checkout: ScratchRepository,
):
    offline_checkout.run_git(
        "remote", "add", "whatever", "https://github.com/a-fork-owner/a-fork.git"
    )

    result = run_stack(
        offline_checkout, "promotion-link", "--branch", "engine", "--title", "A title"
    )

    assert result.returncode == ExitCode.SUCCESS
    assert result.stdout.strip().endswith(
        "...a-fork-owner:engine?expand=1&title=A%20title&body="
    )


# %% pinning the tool where a branch switch cannot reach it


TOOL_WITH_A_DIFFERENT_COMMAND_SET = (
    Path(__file__).parent / "fixtures" / "tool_with_a_different_command_set.py"
)
"""
Stands in for the version of the tool another branch happens to carry.
"""

A_BRANCH_CARRYING_ANOTHER_VERSION = "a-branch-of-the-stack"
"""
Named for what it is to a pass: one more branch to restack, which happens to carry its
own copy of the tool.
"""

MAINTENANCE_EXECUTOR_NAME = "maintenance.py"
"""
The executor beside the tool, which a pinned copy has to be able to run as well.
"""


@dataclass(frozen=True)
class ToolingCheckout:
    """
    A scratch checkout carrying the tool as a committed file, the way a pass meets it.
    """

    repository: ScratchRepository
    """
    The checkout the tool was installed into.
    """

    tool: Path
    """
    The tool in that checkout's working tree, which a branch switch may replace.
    """

    git: GitCommandRunner
    """
    The runner every branch switch of this checkout goes through.
    """

    starting_branch: str
    """
    The branch carrying the real tool, checked out until something switches away.
    """

    @classmethod
    def install_into(cls, repository: ScratchRepository) -> ToolingCheckout:
        """
        Commit this repository's own tooling into a scratch checkout, and give it a
        second branch carrying a version whose commands differ.

        Both versions are committed here so that :meth:`check_out_another_tool_version`
        is nothing but a branch switch: what replaces the tool in the working tree is
        then version control alone, which is the whole hazard being reproduced.

        :param repository: The checkout to install into.
        :return: The checkout, and where its copy of the tool now sits.
        """
        directory = TOOLING_DIRECTORY.relative_to(REPOSITORY_ROOT)
        for source in WorkingTreeTooling().files:
            repository.write(str(directory / source.name), source.read_text())
        repository.commit_everything("carry the stack tooling")

        git = GitCommandRunner(repository.project_root)
        installed = cls(
            repository,
            repository.project_root / directory / ENTRY_POINT_NAME,
            git,
            git.checked_out_branch(),
        )
        git.checkout(A_BRANCH_CARRYING_ANOTHER_VERSION, "HEAD")
        installed.tool.write_text(TOOL_WITH_A_DIFFERENT_COMMAND_SET.read_text())
        repository.commit_everything("carry a tool whose commands differ")
        git.checkout(installed.starting_branch, installed.starting_branch)
        return installed

    def check_out_another_tool_version(self) -> None:
        """
        Switch to the branch whose tooling directory holds the other version - what any
        branch switch made in the checkout a pass runs from does, whether a step of the
        pass or the session driving it made the switch.
        """
        self.git.checkout(
            A_BRANCH_CARRYING_ANOTHER_VERSION, A_BRANCH_CARRYING_ANOTHER_VERSION
        )

    def pin_the_tool(self) -> Path:
        """
        Pin the tool the way step 0 of a pass does, from the checkout's own copy.

        :return: The pinned copy's entry point, as printed on stdout.
        """
        result = run_stack(self.repository, Command.PIN_TOOLING, tool=self.tool)
        assert result.returncode == ExitCode.SUCCESS, result.stderr
        return Path(result.stdout.strip())


@pytest.fixture
def tooling_checkout(scratch_repository: ScratchRepository) -> ToolingCheckout:
    """
    A scratch checkout carrying the tool as a committed file.

    :param scratch_repository: The repository to install the tooling into.
    :return: The installed checkout.
    """
    return ToolingCheckout.install_into(scratch_repository)


def a_tooling_directory(path: Path, file_names: Iterable[str]) -> Path:
    """
    Build a directory standing in for a tooling directory, without copying the real one.

    :param path: Where to build it.
    :param file_names: The files it holds; each gets its own name as its content, so two
        directories differ exactly when their file names do.
    :return: The directory built.
    """
    path.mkdir(parents=True)
    for name in file_names:
        (path / name).write_text(name)
    return path


def test_a_branch_switch_replaces_the_tool_in_the_working_tree(
    tooling_checkout: ToolingCheckout,
):
    """
    The hazard the pin exists for.

    The tool is tracked content, which version control moves like any other file, so a
    command a pass validated in step 0 can be gone by the time a later step calls it.
    """
    tooling_checkout.check_out_another_tool_version()

    result = run_stack(
        tooling_checkout.repository,
        Command.LABELS,
        "--add",
        A_LABEL_THIS_TOOL_NEVER_WRITES,
        tool=tooling_checkout.tool,
    )

    assert result.returncode == ExitCode.USAGE


def test_the_pinned_tool_answers_after_a_branch_switch_replaced_the_working_tree_one(
    tooling_checkout: ToolingCheckout,
):
    """
    The fix: what a pass pinned in step 0 is what drives every later step of it.
    """
    pinned = tooling_checkout.pin_the_tool()

    tooling_checkout.check_out_another_tool_version()

    result = run_stack(
        tooling_checkout.repository,
        Command.LABELS,
        "--add",
        A_LABEL_THIS_TOOL_NEVER_WRITES,
        tool=pinned,
    )
    assert result.returncode == ExitCode.SUCCESS
    assert result.stdout.split() == [A_LABEL_THIS_TOOL_NEVER_WRITES]


def test_the_pinned_copy_lies_outside_the_checkout_it_was_taken_from(
    tooling_checkout: ToolingCheckout,
):
    """
    Anywhere inside the working tree is somewhere a checkout could still reach it.
    """
    pinned = tooling_checkout.pin_the_tool()

    assert not pinned.is_relative_to(tooling_checkout.repository.project_root)


def test_every_file_beside_the_tool_is_pinned_with_it(tmp_path: Path):
    """
    The tool is several modules and its configuration, so pinning the entry point alone
    would pin a program that cannot start.
    """
    beside_the_tool = {
        ENTRY_POINT_NAME,
        CONFIGURATION_PATH.name,
        MAINTENANCE_EXECUTOR_NAME,
    }
    source = a_tooling_directory(tmp_path / "source", beside_the_tool)

    pinned = WorkingTreeTooling(source).pin_to(tmp_path / "pinned")

    assert {path.name for path in pinned.directory.iterdir()} == beside_the_tool


def test_the_board_snapshot_is_left_behind_rather_than_pinned(tmp_path: Path):
    """
    The board is a snapshot of one pass, so a copy of it would be stale the moment the
    next pass exported its own - and stale in a way nothing downstream could see.
    """
    source = a_tooling_directory(
        tmp_path / "source", {ENTRY_POINT_NAME, BOARD_PATH.name}
    )

    pinned = WorkingTreeTooling(source).pin_to(tmp_path / "pinned")

    assert not (pinned.directory / BOARD_PATH.name).exists()


def test_the_pinned_copy_carries_what_the_maintenance_executor_imports(tmp_path: Path):
    """
    The executor runs out of the pinned directory too, importing the tool and every
    module beside it, so a copy it cannot start from is not a pinned tool.

    Those imports are absolute (``bastler.maintenance_board`` and its siblings), so the
    copy's own parent - the directory holding the pinned ``bastler/`` - has to be on the
    import path, exactly as it is for the checkout's own copy.
    """
    pinned = WorkingTreeTooling().pin_to(tmp_path / "pinned")

    result = subprocess.run(
        [sys.executable, str(pinned.directory / MAINTENANCE_EXECUTOR_NAME), "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(pinned.directory.parent)},
    )

    assert result.returncode == ExitCode.SUCCESS, result.stderr


def test_a_sibling_directory_the_tool_imports_from_is_pinned_with_it(tmp_path: Path):
    """
    The tool is not always one directory.

    A module beside it may put a sibling on the import path, and a copy without that sibling is a program that cannot start - so the
    copy keeps the tool where it stood relative to what it imports, and the same insert
    resolves inside the copy.
    """
    tree = tmp_path / "tree"
    shared = tree / "shared"
    shared.mkdir(parents=True)
    (shared / "carried.py").write_text("ANSWER = 'carried'\n")
    tooling = a_tooling_directory(tree / "stack", {ENTRY_POINT_NAME})
    (tooling / ENTRY_POINT_NAME).write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))\n"
        "from carried import ANSWER\n"
        "print(ANSWER)\n"
    )

    pinned = WorkingTreeTooling(tooling).pin_to(tmp_path / "pinned")

    answered = subprocess.run(
        [sys.executable, str(pinned.entry_point)], capture_output=True, text=True
    )
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout.strip() == "carried"


def test_a_directory_the_tool_never_imports_from_is_left_where_it_is(tmp_path: Path):
    """
    Pinning a sibling nothing reaches would copy whatever happens to sit beside the
    tool, which on a real checkout is most of the repository.
    """
    tree = tmp_path / "tree"
    (tree / "unrelated").mkdir(parents=True)
    (tree / "unrelated" / "elsewhere.py").write_text("")
    tooling = a_tooling_directory(tree / "stack", {ENTRY_POINT_NAME})

    pinned = WorkingTreeTooling(tooling).pin_to(tmp_path / "pinned")

    assert not (pinned.directory.parent / "unrelated").exists()


def test_pinning_the_same_tool_twice_names_the_same_copy(tmp_path: Path):
    """
    A pass that pins again - resuming, or re-running a step - keeps the copy it had.
    """
    source = a_tooling_directory(tmp_path / "source", {ENTRY_POINT_NAME})
    root = tmp_path / "pinned"

    first = WorkingTreeTooling(source).pin_to(root)
    second = WorkingTreeTooling(source).pin_to(root)

    assert first.entry_point == second.entry_point


def test_a_tool_that_differs_is_pinned_beside_rather_than_over_the_other_copy(
    tmp_path: Path,
):
    """
    Two versions can be in flight at once, so a later pass must not overwrite the copy
    an earlier one is still running.
    """
    root = tmp_path / "pinned"
    one_version = a_tooling_directory(tmp_path / "one", {ENTRY_POINT_NAME})
    another_version = a_tooling_directory(
        tmp_path / "another", {ENTRY_POINT_NAME, MAINTENANCE_EXECUTOR_NAME}
    )

    pinned = WorkingTreeTooling(one_version).pin_to(root)
    pinned_again = WorkingTreeTooling(another_version).pin_to(root)

    assert pinned.directory != pinned_again.directory
