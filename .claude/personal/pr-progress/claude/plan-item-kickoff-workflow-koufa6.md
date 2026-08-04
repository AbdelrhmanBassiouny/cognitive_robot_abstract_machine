## Plan
`stack-maintenance-executor` (workflow-unification, stack-tooling track) — a deterministic
executor for the stacked-PR maintenance pass. Draft PR #139 off #106's head.

## Done
- Credential probe (item's step 0) on throwaway PR #138, now closed: labels PUT 200,
  comments POST 201, body-only PATCH 200, base-branch PATCH 403 as the control on the same
  PR. The 403 is scoped to the `base` field, not to writes.
- `.claude/stack/maintenance.py`, five commands: `board --write`, `fast-forward`,
  `restack`, `promote`, `run-report --json`. Separate entry point, zero edits to `stack.py`.
- Scope widened on the user's instruction once the probe came back: all three writes moved
  into code. Conflicts are labelled + commented and the label is cleared again once
  `mergeable_state` stops being `dirty` (closing a loop nothing previously closed);
  `promote` writes the compare link into the PR description and manages `cram2-link-sent`.
- 30 new tests, TDD, real git + a recording write stand-in. 351 pass, was 321. Eight
  mutations checked, each caught by exactly the test naming it.
- Two ambient-state bugs found and fixed, both invisible locally:
  (1) `board --write` made a local `board.json` routine, breaking two tests (one
  pre-existing) that assert on a missing board → autouse fixture sets it aside;
  (2) CI caught credential resolution having moved ahead of board derivation, so `restack`
  reported a missing token instead of the missing board → reordered, and the CLI tests now
  strip the credential.
- SKILL.md steps 1–5 + Finish rewritten; `.gitignore` gains `board.json`.
- Manifest + roadmap saved; dashboard republished.

## Next
- Watch #139's CI after the ordering fix (8dfd3d89). Re-draft after any push.
- Residue needing out-of-harness deletion: branch `claude/credential-probe-koufa6`.
- `.gitignore`'s `board.json` line is duplicated with #110 — whoever lands second drops one.
- Still not run against the live fork: `restack`, `promote`, `run-report` (they rewrite real
  descriptions and push real branches).
