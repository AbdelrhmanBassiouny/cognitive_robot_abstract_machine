# Stacked-PR workflow (fork staging → cram2 review)

High-velocity, review-constrained workflow. This fork (`origin`) holds the **full stack** of
in-flight branches; **cram2** is the slow review queue. You promote the *bottom* of the stack to
cram2 one at a time, never exceeding a WIP cap. Claude does the mechanical restacking so the tower
never rots and you keep coding.

## The doctrine (why)

The reviewers are the constraint. Throughput dies from (1) big PRs and (2) unbounded work in
review. So: keep each PR small and single-concern, cap how many are in review at once, and make
stack maintenance free. (Stacked diffs + trunk-based small batches + WIP limits — Graphite/Sapling,
DORA/*Accelerate*, Reinertsen, Theory of Constraints.)

## Files

- **`stack.toml`** — the ledger: every branch, its parent, integration strategy, PR number, and
  lifecycle state (`staging` → `in-review` → `merged`). The single source of truth. Hand-edited.
- **`stack.py`** — read-only status tool (never mutates branches):
  - `python dev/stack.py status` — the whole stack, with ahead/behind drift per parent.
  - `python dev/stack.py check` — would each branch integrate cleanly onto its parent *now*
    (fast, non-mutating `git merge-tree` probe)?
  - `python dev/stack.py next` — which branch to submit to cram2 next, honouring dependency order
    and the WIP cap. **This is your "what goes to cram2 next" answer.**
  - `python dev/stack.py next --porcelain` — machine-readable `next`: prints only
    `name<TAB>pr<TAB>pr_repo` for the branch to promote (or nothing). For autonomous callers such as
    the promote Routine, which must act deterministically on "is there a branch to submit right now".
  - `python dev/stack.py restack-plan` — prints the bottom-up restack plan as JSON (one
    `{branch, parent, strategy}` per not-yet-`merged` branch, in-review ones included so they pick up a
    moved parent via a conflict-free `merge`). Feed it straight into the `restack` workflow's `args`
    so the stack lives **only** in the ledger — no hand-mirroring into the script.
  - add `--live` to any command to **derive status from live GitHub PR state** (via `gh`) instead of
    the ledger's `status` column: a PR you flip to *draft* / *ready-for-review* on GitHub updates
    what the tool shows. GitHub becomes the source of truth for the gate; the ledger then only needs
    to carry structure (branch, parent, strategy, pr, pr_repo). Requires an authenticated `gh`.
- **`../.claude/workflows/restack.js`** — the Claude Workflow that actually restacks: one
  worktree-isolated agent per branch, bottom-up, resolving conflicts + greening the targeted tests
  + pushing. It has **no hardcoded stack** — it reads the plan from `args`, so launch it as
  `Workflow({ scriptPath: ".claude/workflows/restack.js", args: <output of dev/stack.py restack-plan> })`.
  Stops at the first branch it can't restack safely (downstream depends on it); re-running caches
  completed branches.

## The state machine (your approval gate)

`draft` → **`ready`** → `in-review` → `merged`. The `draft → ready` transition is **your gate**: you
review a branch's *fork* PR and, if you approve it for upstream, set its `status = "ready"` in
`stack.toml` by hand. `stack.py next` will **only** ever promote a `ready` branch — nothing reaches
cram2 without your sign-off. The fork PR is where that review happens.

## The loop you run

1. Code at full speed on top of your stack tip (never off `cram2/main` directly).
2. **Self-review the bottom fork PR.** If good, set its `status = "ready"` in `stack.toml`. ← the gate.
3. `python dev/stack.py next` → it names the approved, unblocked branch under the WIP cap. Open/retarget
   its PR onto cram2 and set `status = "in-review"`.
4. When cram2 merges it: set `status = "merged"`, then **run the `restack` workflow** to cascade the
   new base up the stack. `status`/`check` confirm it's clean again.
5. Keep in-review count ≤ `wip_cap`. If the cap is full, keep the rest `draft`/`ready` on the fork;
   don't flood reviewers. PRs carrying a `wip_exempt_labels` label (default `bug`) do **not** count
   against the cap — a standalone bug fix shouldn't block feature throughput. With `--live`, labels
   are read from GitHub, so labelling a PR `bug` there is enough.

## Rules of hygiene

- **One branch ⇄ one session.** Never point two live sessions at the same branch (force-push races).
- **The branch is the durable state** — commit + push often; cloud containers are ephemeral.
- **Restack only after the parent has landed/updated.** Restacking onto a still-conflicting,
  unmerged parent is premature — land the parent first.
- **The ledger is the only stack definition.** `restack.js` takes its stack from `args` (via
  `dev/stack.py restack-plan`), so there is nothing to keep in sync by hand.

## The cloud Routine (paste into claude.ai/code/routines)

One autonomous cloud session that runs the whole loop hands-free on each trigger (a merge in the
fork, or a schedule). It uses **plain sequential git** — no Workflow tool, no permission prompts — and
`dev/stack.py` as the source of truth. It never exceeds `wip_cap`, and it auto-closes fork PRs whose
work has already landed upstream. Keep the prompt generic (no feature names).

```text
You maintain a stacked-PR fork-staging workflow. `origin` is my fork (the full stack); `cram2` is the
slow upstream review queue. Work only from the ledger in `dev/`. Do NOT use the Workflow tool. Use
plain git and gh. Never force-push a branch that has an open cram2 PR unless its strategy is "rebase".

SETUP
1. `git fetch origin && git fetch cram2 main`.
2. Read `dev/stack.toml` (the ledger) and use `python dev/stack.py --live status`.

PHASE 1 — AUTO-CLOSE LANDED FORK PRs
cram2 always merges with a merge commit (never squash/rebase), so a landed branch is always an
ancestor of cram2/main. For each OPEN pull request on the fork (origin), look at its head branch B:
- If `git merge-base --is-ancestor origin/B cram2/main` succeeds, B's work has landed upstream →
  CLOSE the fork PR with a comment linking the merged cram2 PR.
- NEVER close a fork PR whose cram2 equivalent (same head branch) is still OPEN. Those are being
  reviewed; leave them exactly as they are.
- Set that branch's `status = "merged"` in `dev/stack.toml`.

PHASE 2 — RESTACK
For each branch in `dev/stack.toml`, bottom-up (parent before child), if its parent moved:
integrate the parent into the branch using the branch's `strategy` (merge = default, no force-push;
rebase = force-push-with-lease). Resolve conflicts faithfully. If a generated `ormatic_interface.py`
conflicts, do NOT hand-edit it — run `scripts/regenerate_all_orm.py`. Source ROS
(`source /opt/ros/jazzy/setup.bash && source /opt/ros/overlay_ws/install/setup.bash`) and run ONLY
the tests that branch touches with `/opt/ros/cram-env/bin/python`. Push. Stop at the first branch you
cannot integrate cleanly (downstream depends on its new SHA) and report it.

PHASE 3 — PROMOTE (obey the WIP cap)
Run `python dev/stack.py next --porcelain`. It prints `name<TAB>pr<TAB>pr_repo` for the single branch
that is approved (status "ready"), unblocked, and under `wip_cap` — or nothing. If it prints a branch:
open (or retarget onto `cram2/main`) that branch's cram2 PR with an updated description, then set its
`status = "in-review"` in the ledger. If it prints nothing, the cap is full or nothing is ready — do
not promote. Bug-labelled PRs (`wip_exempt_labels`) never count against the cap.

FINISH
Commit any `dev/stack.toml` edits. Summarise: what you closed, what you restacked, what you promoted,
and anything you stopped on.
```

The promote step is gated by `stack.py next`, which only ever names a `ready` branch under the cap —
so the Routine can never flood cram2, and never promotes something you haven't approved.
