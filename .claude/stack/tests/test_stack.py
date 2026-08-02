"""
Tests for the stacked-PR helper's pure logic (no git, no network) and its personal-notes
configuration layering (real scratch git repositories, no network).

The data layer is injected - :func:`build_stack` takes a merged-branch predicate - so
status derivation, topological ordering, promotion policy, and the restack plan are all
exercised against in-memory pull-request exports. Configuration layering genuinely needs a git
remote, so those tests run against a :class:`ScratchRepository` instead.
"""

from __future__ import annotations

from collections.abc import Container
from pathlib import Path

import pytest

from scratch_repository import ScratchRepository

from stack import (
    AmbiguousForkRemoteError,
    BranchStatus,
    Configuration,
    ForkRemoteNotFoundError,
    MalformedRepositoryError,
    IntegrationStrategy,
    PullRequest,
    Remote,
    Repository,
    build_stack,
    derive_status,
    load_configuration,
    next_to_promote,
    print_configuration,
    resolve_remotes,
    order,
    promotion_order,
    restack_plan,
)


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
    Write and commit the repo-default ``stack.toml`` into a scratch repository.

    :param scratch_repository: The scratch repository to write into.
    :return: The path :func:`load_configuration` should be pointed at.
    """
    path = scratch_repository.write(".claude/stack/stack.toml", DEFAULT_STACK_TOML)
    scratch_repository.commit_everything("add stack.toml")
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


def a_stack_of_two_towers(
    approved: Container[str] = frozenset(),
    promoted: Container[str] = frozenset(),
    withheld: Container[str] = frozenset(),
    landed: Container[str] = frozenset(),
):
    """
    Two independent towers off `main`, the first three deep and the second one deep.

    :param approved: Branches the developer has un-drafted.
    :param promoted: Branches carrying the in-review label.
    :param withheld: Branches delegated for conflict resolution.
    :param landed: Branches that are ancestors of the upstream base.
    :return: The stack as the tooling derives it.
    """
    tower = [("engine", "main"), ("engine-ui", "engine"), ("engine-docs", "engine-ui")]
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
        for number, (name, parent) in enumerate([*tower, *aside], start=1)
    ]
    return build(pull_requests, merged=landed)


def test_nothing_promotes_while_the_whole_stack_is_still_draft():
    assert promotion_order(a_stack_of_two_towers()) == []


def test_approving_a_root_promotes_it_and_nothing_above_it():
    """
    Un-drafting is the approval gate, and it approves one branch rather than a tower.
    """
    stack = a_stack_of_two_towers(approved={"engine", "engine-ui"})

    assert [branch.name for branch in promotion_order(stack)] == ["engine"]


def test_promoting_a_parent_unblocks_the_child_behind_it():
    """
    A child may follow its parent upstream once the parent is in review - it does not
    wait for the parent to merge.
    """
    stack = a_stack_of_two_towers(approved={"engine", "engine-ui"}, promoted={"engine"})

    assert [branch.name for branch in promotion_order(stack)] == ["engine-ui"]


def test_both_towers_promote_together_since_they_do_not_depend_on_each_other():
    stack = a_stack_of_two_towers(approved={"engine", "parser"})

    assert [branch.name for branch in promotion_order(stack)] == ["engine", "parser"]


def test_a_branch_delegated_for_conflict_resolution_is_held_back_alone():
    """
    Withholding one branch must not withhold an unrelated tower.
    """
    stack = a_stack_of_two_towers(approved={"engine", "parser"}, withheld={"engine"})

    assert [branch.name for branch in promotion_order(stack)] == ["parser"]


def test_landing_a_root_reparents_only_its_own_child():
    """
    The landed branch drops out of the plan and its child moves onto the base, while the
    branch above keeps the parent it still has and the untouched tower keeps its own.
    """
    stack = a_stack_of_two_towers(landed={"engine"})

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


def test_a_tower_lands_bottom_up_over_successive_runs():
    """
    Each branch reaches the base only after the one below it has, so the plan shortens
    from the bottom as the stack drains.
    """
    after_first = a_stack_of_two_towers(landed={"engine"})
    after_second = a_stack_of_two_towers(landed={"engine", "engine-ui"})

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
