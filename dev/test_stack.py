"""Tests for the stacked-PR helper's pure logic (no git, no network).

The data layer is injected — :func:`build_stack` takes a merged-branch predicate — so status
derivation, topological ordering, promotion policy, and the restack plan are all exercised against
in-memory pull-request exports.
"""
from __future__ import annotations

import pytest

from stack import (
    Config,
    PullRequest,
    build_stack,
    derive_status,
    next_to_promote,
    order,
    restack_plan,
)


def make_config(wip_cap: int = 3) -> Config:
    return Config(
        wip_cap=wip_cap,
        wip_exempt_labels=["bug"],
        in_review_label="in-review",
        rebase_label="rebase",
        priority_labels=["priority:high", "priority:medium", "priority:low"],
        short_threshold_loc=400,
        fork_remote="origin",
        upstream_remote="cram2",
        upstream_base="main",
    )


def build(prs: list[PullRequest], merged: set[str] = frozenset(), wip_cap: int = 3):
    return build_stack(make_config(wip_cap), prs, lambda name: name in merged)


# ── derive_status ──────────────────────────────────────────────────────────

def test_merged_wins_over_everything():
    assert derive_status(draft=True, merged=True, in_review=True) == "merged"


def test_in_review_label_beats_draft_flag():
    assert derive_status(draft=True, merged=False, in_review=True) == "in-review"


def test_undrafted_is_ready():
    assert derive_status(draft=False, merged=False, in_review=False) == "ready"


def test_drafted_is_draft():
    assert derive_status(draft=True, merged=False, in_review=False) == "draft"


# ── status from the export ─────────────────────────────────────────────────

def test_in_review_derived_from_label():
    stack = build([PullRequest(3, "feature", "main", draft=False, labels=["in-review"])])
    assert stack.branches[0].status == "in-review"


def test_merged_derived_from_predicate_not_labels():
    stack = build([PullRequest(9, "landed", "main", draft=False, labels=[])], merged={"landed"})
    assert stack.branches[0].status == "merged"


def test_rebase_label_sets_strategy():
    stack = build([PullRequest(1, "f", "main", draft=True, labels=["rebase"])])
    assert stack.branches[0].strategy == "rebase"
    stack = build([PullRequest(1, "f", "main", draft=True, labels=[])])
    assert stack.branches[0].strategy == "merge"


# ── ordering: parent before child, even when declared out of order ─────────

def test_order_places_parent_before_child():
    prs = [
        PullRequest(3, "child", "parent", draft=True),
        PullRequest(2, "parent", "main", draft=True),
    ]
    names = [b.name for b in order(build(prs))]
    assert names.index("parent") < names.index("child")


# ── promotion policy ───────────────────────────────────────────────────────

def test_promotes_ready_root_when_slot_free():
    prs = [PullRequest(11, "arith", "main", draft=False)]
    assert next_to_promote(build(prs)).name == "arith"


def test_nothing_promotes_when_all_draft():
    prs = [PullRequest(5, "wip", "main", draft=True)]
    assert next_to_promote(build(prs)) is None


def test_wip_cap_blocks_promotion():
    prs = [
        PullRequest(1, "a", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "b", "main", draft=False, labels=["in-review"]),
        PullRequest(3, "c", "main", draft=False, labels=["in-review"]),
        PullRequest(4, "ready-one", "main", draft=False),
    ]
    assert next_to_promote(build(prs)) is None


def test_bug_label_is_exempt_from_cap():
    prs = [
        PullRequest(1, "a", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "b", "main", draft=False, labels=["in-review"]),
        PullRequest(3, "bugfix", "main", draft=False, labels=["in-review", "bug"]),
        PullRequest(4, "ready-one", "main", draft=False),
    ]
    # only two count against the cap, so the ready branch may still promote
    assert next_to_promote(build(prs)).name == "ready-one"


def test_ready_child_blocked_until_parent_lands():
    prs = [
        PullRequest(1, "parent", "main", draft=True),      # still draft, not on cram2
        PullRequest(2, "child", "parent", draft=False),    # approved but parent hasn't landed
    ]
    assert next_to_promote(build(prs)) is None


def test_child_not_promotable_while_parent_in_review():
    # independence: the review slots must be distinct stacks, so a child is not promoted while its own
    # stack (here its parent) is still in review.
    prs = [
        PullRequest(1, "parent", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "child", "parent", draft=False),
    ]
    assert next_to_promote(build(prs)) is None


def test_child_promotable_once_parent_merged():
    # once the parent has merged its stack no longer holds a review slot, so the child may promote.
    prs = [
        PullRequest(1, "parent", "main", draft=False),
        PullRequest(2, "child", "parent", draft=False),
    ]
    assert next_to_promote(build(prs, merged={"parent"})).name == "child"


def test_cap_counts_independent_stacks_not_prs():
    # a single deep stack with several in-review branches occupies ONE slot, so an independent ready
    # branch still promotes under the cap of 3.
    prs = [
        PullRequest(1, "a1", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "a2", "a1", draft=False, labels=["in-review"]),
        PullRequest(3, "a3", "a2", draft=False, labels=["in-review"]),
        PullRequest(4, "b1", "main", draft=False),
    ]
    assert next_to_promote(build(prs, wip_cap=3)).name == "b1"


def test_three_independent_stacks_fill_the_cap():
    prs = [
        PullRequest(1, "a", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "b", "main", draft=False, labels=["in-review"]),
        PullRequest(3, "c", "main", draft=False, labels=["in-review"]),
        PullRequest(4, "d", "main", draft=False),
    ]
    assert next_to_promote(build(prs, wip_cap=3)) is None


# ── priority among several ready branches ──────────────────────────────────

def test_priority_label_wins_over_dependency_order():
    prs = [
        PullRequest(1, "first-declared", "main", draft=False),
        PullRequest(2, "urgent", "main", draft=False, labels=["priority:high"]),
    ]
    assert next_to_promote(build(prs)).name == "urgent"


def test_higher_priority_beats_lower():
    prs = [
        PullRequest(1, "low", "main", draft=False, labels=["priority:low"]),
        PullRequest(2, "high", "main", draft=False, labels=["priority:high"]),
    ]
    assert next_to_promote(build(prs)).name == "high"


def test_prioritised_beats_unprioritised():
    prs = [
        PullRequest(1, "plain", "main", draft=False),
        PullRequest(2, "ranked", "main", draft=False, labels=["priority:low"]),
    ]
    assert next_to_promote(build(prs)).name == "ranked"


def test_priority_falls_back_to_dependency_order_on_tie():
    prs = [
        PullRequest(3, "child", "parent", draft=False, labels=["priority:high"]),
        PullRequest(2, "parent", "main", draft=False, labels=["priority:high"]),
    ]
    # equal priority → parent (earlier in dependency order) promotes first
    assert next_to_promote(build(prs)).name == "parent"


def test_ci_and_session_carried_onto_branch():
    stack = build([PullRequest(11, "f", "main", draft=False, ci="failure", session="https://claude.ai/code/session_x")])
    assert stack.branches[0].ci == "failure"
    assert stack.branches[0].session == "https://claude.ai/code/session_x"


# ── restack plan ───────────────────────────────────────────────────────────

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
    # parent merged into main -> its commits are in the base, so the child is reparented onto main
    # (the routine mirrors this by retargeting the child PR's base on GitHub).
    prs = [
        PullRequest(1, "parent", "main", draft=False),
        PullRequest(2, "child", "parent", draft=False),
    ]
    plan = restack_plan(build(prs, merged={"parent"}))
    assert plan == [{"branch": "child", "parent": "main", "strategy": "merge"}]
