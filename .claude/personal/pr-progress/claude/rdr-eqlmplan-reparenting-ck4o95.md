## Task

Reparent the rdr-refactor branches whose parents are merged/closed/deferred, which the
last stacking-maintenance pass missed. Operational pass, not a code change: no commit is
expected on this branch.

## Root cause (established)

`load_stack()` on `main` fetches only `[pr.head for pr in prs]`, so a parent that is not
itself an open PR head is never fetched; `is_merged` then runs `merge-base --is-ancestor`
through `_git_succeeds`, which cannot tell exit 128 (ref missing) from exit 1 (not an
ancestor). Reproduced on this clone: `stack.py reparents` printed nothing before the fork
branch refs were fetched, and printed #64 and #192 after. Already fixed by **PR #198**
(`unfetched-parent-branches`, workflow-unification, track stack-tooling, open, non-draft,
`cram2-link-sent`, mergeable clean, up to date with main). So: run the pass with #198's
tooling, do not write a new fix.

## What the fixed tooling finds

- #64  D-core-underspecified   parent D-core-aid landed upstream        -> reparent to main
- #192 match-query-interface-refactor parent landed                     -> reparent to main
- #178 plan-graph-executing-node parent merged into its grandparent     -> montessori_fast_inline_monitor
- #79  D-ui-rendering          parent D-ui-splice-fix closed unmerged   -> gone, hand to owner
- #21  rdr/oo-recognition      parent rdr/oo-plan closed unmerged       -> gone, hand to owner

Separately, #81 (rdr-why-answer) is *based* on D-core-engine (#68, deferred) while the plan
says it depends on d-core-backend. Open PR, so the stack tooling reads it as tracked; this is
the plan-side case PR #184 (deferred-dependency-drift-check) addresses.

## Done

- Fetched fork/upstream refs, reproduced the silent miss, root-caused it.
- Built a worktree at scratchpad/wt198 from #198 (already contains current main) and ran the
  read-only diagnosis from it.

## Next

- Step 1: retarget #64, #192, #178 via MCP `update_pull_request`.
- Step 2: `maintenance.py run-report --json` from the #198 worktree.
- Report #79 and #21 to their owners; decide their real targets with the developer.
- Update rdr-refactor / match-query-ergonomics / montessori-eql-stack manifests, republish
  their dashboards.

