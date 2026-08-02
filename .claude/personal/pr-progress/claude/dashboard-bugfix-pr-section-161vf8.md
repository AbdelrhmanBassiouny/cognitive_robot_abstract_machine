## Branch `claude/dashboard-bugfix-pr-section-161vf8` — surface bug-fix PRs on the plan dashboard

**Goal.** Make bug-fix pull requests visible and filterable in the plan
dashboard's "What to do next" sidebar.

**Design.** A first attempt at a separate top "Bug fixes" group with a red
outline was rejected: the sidebar groups by *action*, and being a bug fix is not
one — such items already sit in ready-to-start, blocker-may-be-cleared or
ready-to-review — and a fifth outline would collide with the existing per-group
outlines, which are not mutually exclusive with it. It is an attribute: a `bug`
chip wherever the item already appears, plus an opt-in filter.

**Done — two commits, pushed, 206 tests passing.**
- `Item.is_bug_fix` from the pull request's `bug` label, via a new
  `_pull_request_record_of` lookup. First real consumer of `PullRequestLabel.BUG`.
- Four near-identical sidebar blocks collapsed into one `next_step_group` Jinja
  macro, each `{% call %}` body supplying its own reason line.
- "Bug fixes only" checkbox: hides non-bug entries and any group left holding
  none; rendered only when some entry is a bug fix, so it can never empty the
  card. Per-group counts precomputed and swapped by CSS, matching the done-items
  toggle rather than doing arithmetic at runtime.
- Example demonstrates both (`#103` labelled `bug`); all three walkthrough
  screenshots regenerated, `dashboard-bug-filter.png` new. A test pins that the
  example keeps producing the chip and the toggle.
- Docs: `SKILL.md`, hooks README label list, `pr-data-fetching.md`, walkthrough.

**Placement (settled).** Stays on fork `main`, independent of the #101/#106
chain, like #103/#105/#119. No `bug` label — it surfaces bug fixes, does not fix
one. `ready-to-promote-upstream-links` now `depends_on` it, since its fifth
sidebar group is one macro call after this lands and a fifth copied block
before. Posted on tracking issue #102.

**Open as draft PR #120** (fork `main`, no `bug` label, session link in the
description, subscribed to activity). No scheduled check-in armed, per the
no-scheduled-checks rule — reacting to webhook events only.

**CI (2026-08-01).** `test_each_lib (semantic_digital_twin)` red, 3 failures in
`test_adapters/test_multi_sim.py`: the known `test_world_sim_state_sync`
settling flake plus two texture/material regression tests asserting `'' != ''`.
Not reachable by this diff (six files, all under `.claude/`), and the other 12
jobs passed. Complication recorded rather than glossed: main's own run at this
branch's base `82501888` was green, so these are *not* demonstrably already-red
on main the way #101/#103's flakes were. The two texture tests are
self-contained (`tmp_path`), so the job's cached asset directory — the one real
PR-vs-main difference — does not explain them; a freshly resolved MuJoCo version
is the plausible environmental candidate. Could not reproduce locally: mujoco
and the robotics stack are absent from this session's environment. Reported once
on the PR asking for a re-run.

**CI resolved (2026-08-02).** The branch was restacked onto the new main
(`9b090fc1`, PR #402) and CI re-ran. Main's *own* run at that commit
(30760195910) now fails `test_each_lib (semantic_digital_twin)` with exactly the
two texture assertions, `2 failed, 1048 passed` — so they are a real regression
on main's tree, and the earlier "cannot call this pre-existing" caveat is
answered. Green at `82501888` (07-31) → red here (08-01) → red on main (08-02)
with no repo-side change to those tests, which supports the environmental
(freshly resolved MuJoCo) hypothesis. `test_world_sim_state_sync` passed on
main's run, confirming it is the separate flake. A second, new failure on this
PR — `coraplex/demos/coraplex_real_tracy/test_demo.py` — is a teardown race
(demo passed, then `rclpy-executor` SIGABRT at interpreter shutdown, exit 134);
main's Examples-and-Demos run at the same commit was green, so that one is
flake. Neither is reachable from this branch (11 files, all `.claude/`).
Reported on the PR; nothing to fix here.

**Spun out, not fixed here.** `_compute_ready_to_review` treats a *merged*
dependency as not-open, so an item whose dependency fully landed is excluded
while one whose dependency is merely open is included. Now its own plan item
`ready-to-review-merged-dependency` (`not_started`), whose first step is
confirming with the developer that it is an oversight rather than intent.
