# Branch retired — work folded into PR #117

This branch carried draft PR #133 (`session-safe-pr-reparent`, workflow-unification,
tracking issue #102). It no longer has a pull request of its own and needs no
further work here.

## Outcome

The doctrine correction was fast-forwarded onto `claude/stack-landed-parent-detection`
(#117), which is where it belongs: its only purpose was fixing a `ROUTINE.md` section
#117 had just introduced, and leaving it stacked meant #117 sat in review prescribing a
base `PATCH` already known to return 403. The user's standard — a PR must be
self-sufficient and correct, never left open with a known bug — settled it.

GitHub auto-closed #133 as *merged* when its head landed in its own base branch. That
means merged into #117's branch, not into `main`.

## What #117 now carries

- Ancestry-based landed-parent detection (`Stack.has_landed_upstream()`), 3 tests.
- The `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule, both reparent sites
  deferring to it, native-stack step 3 using the MCP tool, 4 contract tests.
- 251 tests passing; description rewritten with the 403-vs-422 table; back in draft.

Subscription moved from #133 to #117.

## Residue

This branch can be deleted — sessions cannot delete branches, so it needs the same
out-of-harness deletion the probe branches got.

