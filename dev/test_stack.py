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
    promotion_order,
    restack_plan,
)


def make_config(wip_cap: int = 3) -> Config:
    return Config(
        wip_cap=wip_cap,
        wip_exempt_labels=["bug"],
        in_review_label="in-review",
        rebase_label="rebase",
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


# ── promotion_order: one branch per free slot ──────────────────────────────

def test_promotion_order_fills_every_free_slot():
    # no stacks in review yet, cap 3 -> all three independent ready roots promote at once
    prs = [
        PullRequest(1, "a", "main", draft=False),
        PullRequest(2, "b", "main", draft=False),
        PullRequest(3, "c", "main", draft=False),
    ]
    assert [b.name for b in promotion_order(build(prs, wip_cap=3))] == ["a", "b", "c"]


def test_promotion_order_limited_to_the_free_slots():
    # one slot already taken -> only two of the three ready roots fill the remaining slots
    prs = [
        PullRequest(1, "in", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "a", "main", draft=False),
        PullRequest(3, "b", "main", draft=False),
        PullRequest(4, "c", "main", draft=False),
    ]
    names = [b.name for b in promotion_order(build(prs, wip_cap=3))]
    assert len(names) == 2 and names == ["a", "b"]


def test_promotion_order_takes_at_most_one_branch_per_stack():
    # a single stack with two independently-ready branches only offers its root to one slot
    prs = [
        PullRequest(1, "root", "main", draft=False),
        PullRequest(2, "child", "root", draft=False),
        PullRequest(3, "other", "main", draft=False),
    ]
    # child is blocked anyway (parent not landed), but the rule is one-per-stack regardless
    names = [b.name for b in promotion_order(build(prs, wip_cap=3))]
    assert names == ["root", "other"]


def test_promotion_order_includes_exempt_on_top_of_the_slots():
    # cap is full with two independent stacks, yet the ready bug still promotes alongside nothing else
    prs = [
        PullRequest(1, "s1", "main", draft=False, labels=["in-review"]),
        PullRequest(2, "s2", "main", draft=False, labels=["in-review"]),
        PullRequest(3, "bugfix", "main", draft=False, labels=["bug"]),
        PullRequest(4, "feature", "main", draft=False),
    ]
    names = [b.name for b in promotion_order(build(prs, wip_cap=2))]
    assert names == ["bugfix"]


def test_tied_fresh_stacks_order_by_pr_number_oldest_first():
    # two unmarked roots share the frontier, so the round-robin can't separate them by turns; the older
    # PR (lower number), which has waited longer, must come first — declared newest-first to prove the
    # order is by PR number, not input order.
    prs = [
        PullRequest(44, "newer", "main", draft=False),
        PullRequest(11, "older", "main", draft=False),
    ]
    assert [b.name for b in promotion_order(build(prs, wip_cap=3))] == ["older", "newer"]


def test_promotion_order_is_round_robin_across_the_slots():
    # two free slots, three ready roots -> the two lowest-turn stacks win, in turn order
    prs = [
        PullRequest(1, "high", "main", draft=False, turn=3),
        PullRequest(2, "low", "main", draft=False, turn=1),
        PullRequest(3, "mid", "main", draft=False, turn=2),
        PullRequest(4, "taken", "main", draft=False, labels=["in-review"]),
    ]
    names = [b.name for b in promotion_order(build(prs, wip_cap=3))]
    assert names == ["low", "mid"]


# ── round-robin fairness (turns) ───────────────────────────────────────────

def test_round_robin_prefers_stack_with_fewer_turns():
    # a freed slot goes to the stack that has taken fewer turns
    prs = [
        PullRequest(1, "a-next", "main", draft=False, turn=1),
        PullRequest(2, "b-next", "main", draft=False, turn=0),
    ]
    assert next_to_promote(build(prs)).name == "b-next"


def test_round_robin_circles_back_when_turns_equal():
    # once every stack has taken the same number of turns, dependency order decides again
    prs = [
        PullRequest(1, "a", "main", draft=False, turn=1),
        PullRequest(2, "b", "main", draft=False, turn=1),
    ]
    assert next_to_promote(build(prs)).name == "a"


def test_fresh_stack_joins_the_back_of_the_current_round():
    # a brand-new PR (no stack-turn marker) takes the frontier turn, so it queues behind a stack that is
    # mid-rotation at a lower turn rather than jumping ahead of it.
    prs = [
        PullRequest(1, "mid-rotation", "main", draft=False, turn=0),   # round 0, still owed a turn
        PullRequest(2, "fresh", "main", draft=False),                  # no marker
        PullRequest(3, "advanced", "main", draft=False, turn=2),       # sets the frontier to 2
    ]
    # frontier = 2 → fresh's effective turn is 2, so mid-rotation (0) wins this slot
    assert next_to_promote(build(prs, wip_cap=3)).name == "mid-rotation"


def test_fresh_stack_does_not_preempt_a_stack_mid_rotation():
    prs = [
        PullRequest(1, "advanced", "main", draft=False, turn=2),
        PullRequest(2, "fresh", "main", draft=False),
    ]
    # frontier 2; fresh's effective turn ties advanced at 2 → dependency order keeps advanced ahead
    assert next_to_promote(build(prs, wip_cap=3)).name == "advanced"


def test_after_merge_continuation_yields_to_a_less_promoted_stack():
    # A merged+closed branch is GONE from the board (open PRs only); the routine already carried its
    # turn onto the reparented continuation (parent 1 -> child 2). So the just-advanced stack's
    # continuation (turn 2) now waits behind a stack still at turn 1 — the rotation keeps circling.
    prs = [
        # 'a-parent' merged and was closed, so it is absent here.
        PullRequest(1, "a-continuation", "main", draft=False, turn=2),
        PullRequest(2, "b", "main", draft=False, turn=1),
    ]
    assert next_to_promote(build(prs)).name == "b"


def test_frontier_uses_only_open_prs():
    # closed PRs simply drop off the board, so the frontier (where a fresh stack queues) is recomputed
    # from the surviving PRs each run — a fresh stack never sorts ahead of a lower-turn survivor.
    prs = [
        PullRequest(1, "low", "main", draft=False, turn=1),
        PullRequest(2, "high", "main", draft=False, turn=3),   # frontier among the survivors
        PullRequest(3, "fresh", "main", draft=False),          # eff = frontier = 3 -> back
    ]
    assert next_to_promote(build(prs, wip_cap=3)).name == "low"


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
