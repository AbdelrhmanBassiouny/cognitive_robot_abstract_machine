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


def test_ready_child_promotable_once_parent_in_review():
    prs = [
        PullRequest(1, "parent", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "child", "parent", draft=False),
    ]
    assert next_to_promote(build(prs)).name == "child"


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
