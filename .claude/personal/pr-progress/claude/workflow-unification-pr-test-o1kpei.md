# Branch retired — all work now on PR #117

This branch's own PR (#133) was folded into #117 and auto-closed as merged into
#117's branch. Nothing further happens here; commits go straight to
`claude/stack-landed-parent-detection`.

## What #117 carries from this session

- Ancestry-based landed-parent detection (`Stack.has_landed_upstream()`), 3 tests.
- `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule; both reparent sites defer to
  it; native-stack step 3 uses the MCP tool. 4 contract tests.
- SETUP step 0 now fetches `.claude/stack/` instead of asserting it is on `main`
  (it is not) + the header/README no longer describe a paste model. 3 more tests.
- **254 tests pass**, was 247 at the start.

## Live-system state, worth not forgetting

The cloud Routine's registered prompt is now a pointer that reads
`.claude/stack/ROUTINE.md` from git each run — `origin/main` first, falling back to
**this PR's branch** since `.claude/stack/` is not on `main` yet. So pushing to
`claude/stack-landed-parent-detection` changes the running workflow immediately.

PR #41 was repaired earlier: 268 files/+27,825 → 7 files/+1,318, number and thread
kept. Stack #134, seven PRs, trunk `main`.

## Due when #106 lands

- Delete the pointer prompt's fallback line (manual paste at claude.ai/code/routines).
- Delete step 0's fetch fallback (ordinary commit).
Neither breaks anything if missed; both are dead weight.

## Residue

This branch can be deleted.

