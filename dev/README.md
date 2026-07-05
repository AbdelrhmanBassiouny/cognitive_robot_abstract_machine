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
  - add `--live` to any command to **derive status from live GitHub PR state** (via `gh`) instead of
    the ledger's `status` column: a PR you flip to *draft* / *ready-for-review* on GitHub updates
    what the tool shows. GitHub becomes the source of truth for the gate; the ledger then only needs
    to carry structure (branch, parent, strategy, pr, pr_repo). Requires an authenticated `gh`.
- **`../.claude/workflows/restack.js`** — the Claude Workflow that actually restacks: one
  worktree-isolated agent per branch, bottom-up, resolving conflicts + greening the targeted tests
  + pushing. Run it with the `Workflow` tool / `/workflows`. Stops at the first branch it can't
  restack safely (downstream depends on it); re-running caches completed branches.

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
   don't flood reviewers.

## Rules of hygiene

- **One branch ⇄ one session.** Never point two live sessions at the same branch (force-push races).
- **The branch is the durable state** — commit + push often; cloud containers are ephemeral.
- **Keep `.claude/workflows/restack.js`'s `STACK` array in sync with `stack.toml`** (workflow
  scripts can't read files, so the order is mirrored).
- **Restack only after the parent has landed/updated.** Restacking onto a still-conflicting,
  unmerged parent is premature — land the parent first.
