# PR #133 — Reparent a base through the MCP server, not a raw PATCH

Plan item `session-safe-pr-reparent` (workflow-unification, tracking issue #102).
Branch based on #117's head; draft, `bug` label, subscribed.

## The finding this PR exists for

The item was created to replace every reparent with close+create, because a live
attempt on PR #41 got `403 - not permitted for this session type` on a base change.
Probed on throwaway PR #129: the 403 is the **git-proxy credential**, not sessions.
`mcp__github__update_pull_request(base=…)` returns 200 on the same pull request.
Stack members still 422 (orthogonal, and dissolving clears it).

## Done

- Probe + end-to-end rehearsal on a throwaway stack (204 / 200 / 201).
- `ROUTINE.md`: one `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule; both
  reparent sites defer to it; native-stack step 3 uses the MCP tool and states the
  child keeps its number/labels/thread. `README.md` row updated.
- 4 contract tests over `ROUTINE.md`, written failing first (it had none). 251 pass.
- **PR #41 repaired live**: 268 files/+27,825 → 7 files/+1,318, number and thread
  kept, nothing pushed. Stack #128 → #134, same 7 PRs, trunk now `main`.
- Manifest: item re-scoped; `landed-parent-detection` and `routine-cutover` notes
  corrected. Roadmap section added, issue #102 commented.

## Next

- Wait on review of #133. It targets #117's branch — equally fine squashed into #117
  before that merges, since the correction belongs with the section it corrects.
- Not done, needs the user: delete throwaway branches
  `claude/reparent-probe-{head,target,upper}-o1kpei` (sessions can't delete branches).
- Open for `routine-cutover`: whether the Action's own credential can change a base.
  Much more likely now that the block is known to be narrow — still unverified.
