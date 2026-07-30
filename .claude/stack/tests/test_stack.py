"""
Tests for the stacked-PR helper's pure logic (no git, no network) and its personal-notes
config layering (real scratch git repositories, no network).

The data layer is injected - :func:`build_stack` takes a merged-branch predicate - so
status derivation, topological ordering, promotion policy, and the restack plan are all
exercised against in-memory pull-request exports. Config layering genuinely needs a git
remote, so those tests run against a :class:`ScratchRepository` instead.
"""

from __future__ import annotations

from pathlib import Path

from scratch_repository import ScratchRepository

from stack import (
    BranchStatus,
    Config,
    IntegrationStrategy,
    PullRequest,
    build_stack,
    derive_status,
    load_config,
    next_to_promote,
    order,
    promotion_order,
    restack_plan,
)


def make_config() -> Config:
    return Config(
        in_review_label="in-review",
        rebase_label="rebase",
        needs_resolution_label="needs-resolution",
        fork_remote="origin",
        upstream_remote="cram2",
        upstream_base="main",
    )


def build(prs: list[PullRequest], merged: frozenset[str] = frozenset()):
    return build_stack(make_config(), prs, lambda name: name in merged)


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


# %% config layering (personal-notes overrides)

DEFAULT_STACK_TOML = """\
in_review_label = "in-review"
rebase_label = "rebase"
needs_resolution_label = "needs-resolution"
fork_remote = "origin"
upstream_remote = "cram2"
upstream_base = "main"
"""


def _committed_config_path(scratch_repository: ScratchRepository) -> Path:
    """
    Write and commit the repo-default ``stack.toml`` into a scratch repository.

    :param scratch_repository: The scratch repository to write into.
    :return: The path :func:`load_config` should be pointed at.
    """
    path = scratch_repository.write(".claude/stack/stack.toml", DEFAULT_STACK_TOML)
    scratch_repository.commit_everything("add stack.toml")
    return path


def test_load_config_uses_committed_defaults_when_no_personal_notes_branch(
    scratch_repository: ScratchRepository, monkeypatch
):
    config_path = _committed_config_path(scratch_repository)
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    config = load_config(config_path)

    assert config.upstream_remote == "cram2"


def test_load_config_layers_personal_notes_override_on_top_of_defaults(
    scratch_repository: ScratchRepository, monkeypatch
):
    config_path = _committed_config_path(scratch_repository)
    scratch_repository.publish_notes_branch(
        {".claude/personal/stack.toml": 'upstream_remote = "my-fork-cram2"\n'}
    )
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    config = load_config(config_path)

    assert config.upstream_remote == "my-fork-cram2"
    assert config.fork_remote == "origin"  # untouched default


def test_load_config_ignores_personal_notes_branch_without_a_stack_file(
    scratch_repository: ScratchRepository, monkeypatch
):
    config_path = _committed_config_path(scratch_repository)
    scratch_repository.publish_notes_branch({"README.md": "unrelated\n"})
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)

    config = load_config(config_path)

    assert config.upstream_remote == "cram2"
